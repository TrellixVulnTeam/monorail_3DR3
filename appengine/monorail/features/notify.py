# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Task handlers for email notifications of issue changes.

Email notificatons are sent when an issue changes, an issue that is blocking
another issue changes, or a bulk edit is done.  The users notified include
the project-wide mailing list, issue owners, cc'd users, starrers,
also-notify addresses, and users who have saved queries with email notification
set.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import json
import logging
import os

from third_party import ezt

from google.appengine.api import mail
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.runtime import apiproxy_errors

import settings
from features import autolink
from features import notify_helpers
from features import notify_reasons
from framework import authdata
from framework import emailfmt
from framework import exceptions
from framework import framework_bizobj
from framework import framework_helpers
from framework import framework_views
from framework import jsonfeed
from framework import monorailrequest
from framework import permissions
from framework import template_helpers
from framework import urls
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views
from proto import tracker_pb2

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as sg_mail
from sendgrid.helpers.mail import To as sg_to
from sendgrid.helpers.mail import From as sg_from
from sendgrid.helpers.mail import Content as sg_content

class NotifyIssueChangeTask(notify_helpers.NotifyTaskBase):
  """JSON servlet that notifies appropriate users after an issue change."""

  _EMAIL_TEMPLATE = 'tracker/issue-change-notification-email.ezt'
  _LINK_ONLY_EMAIL_TEMPLATE = (
      'tracker/issue-change-notification-email-link-only.ezt')

  def HandleRequest(self, mr):
    """Process the task to notify users after an issue change.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format which is useful just for debugging.
      The main goal is the side-effect of sending emails.
    """
    issue_id = mr.GetPositiveIntParam('issue_id')
    if not issue_id:
      return {
          'params': {},
          'notified': [],
          'message': 'Cannot proceed without a valid issue ID.',
      }
    commenter_id = mr.GetPositiveIntParam('commenter_id')
    seq_num = mr.seq
    omit_ids = [commenter_id]
    hostport = mr.GetParam('hostport')
    old_owner_id = mr.GetPositiveIntParam('old_owner_id')
    send_email = bool(mr.GetIntParam('send_email'))
    comment_id = mr.GetPositiveIntParam('comment_id')
    params = dict(
        issue_id=issue_id, commenter_id=commenter_id,
        seq_num=seq_num, hostport=hostport, old_owner_id=old_owner_id,
        omit_ids=omit_ids, send_email=send_email, comment_id=comment_id)

    logging.info('issue change params are %r', params)
    # TODO(jrobbins): Re-enable the issue cache for notifications after
    # the stale issue defect (monorail:2514) is 100% resolved.
    issue = self.services.issue.GetIssue(mr.cnxn, issue_id, use_cache=False)
    project = self.services.project.GetProject(mr.cnxn, issue.project_id)
    config = self.services.config.GetProjectConfig(mr.cnxn, issue.project_id)

    if issue.is_spam:
      # Don't send email for spam issues.
      return {
          'params': params,
          'notified': [],
      }

    all_comments = self.services.issue.GetCommentsForIssue(
        mr.cnxn, issue.issue_id)
    if comment_id:
      logging.info('Looking up comment by comment_id')
      for c in all_comments:
        if c.id == comment_id:
          comment = c
          logging.info('Comment was found by comment_id')
          break
      else:
        raise ValueError('Comment %r was not found' % comment_id)
    else:
      logging.info('Looking up comment by seq_num')
      comment = all_comments[seq_num]

    # Only issues that any contributor could view sent to mailing lists.
    contributor_could_view = permissions.CanViewIssue(
        set(), permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        project, issue)
    starrer_ids = self.services.issue_star.LookupItemStarrers(
        mr.cnxn, issue.issue_id)
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        tracker_bizobj.UsersInvolvedInIssues([issue]), [old_owner_id],
        tracker_bizobj.UsersInvolvedInComment(comment),
        issue.cc_ids, issue.derived_cc_ids, starrer_ids, omit_ids)

    # Make followup tasks to send emails
    tasks = []
    if send_email:
      tasks = self._MakeEmailTasks(
          mr.cnxn, project, issue, config, old_owner_id, users_by_id,
          all_comments, comment, starrer_ids, contributor_could_view,
          hostport, omit_ids, mr.perms)

    notified = notify_helpers.AddAllEmailTasks(tasks)

    return {
        'params': params,
        'notified': notified,
        }

  def _MakeEmailTasks(
      self, cnxn, project, issue, config, old_owner_id,
      users_by_id, all_comments, comment, starrer_ids,
      contributor_could_view, hostport, omit_ids, perms):
    """Formulate emails to be sent."""
    detail_url = framework_helpers.IssueCommentURL(
        hostport, project, issue.local_id, seq_num=comment.sequence)

    # TODO(jrobbins): avoid the need to make a MonorailRequest object.
    mr = monorailrequest.MonorailRequest(self.services)
    mr.project_name = project.project_name
    mr.project = project
    mr.perms = perms

    # We do not autolink in the emails, so just use an empty
    # registry of autolink rules.
    # TODO(jrobbins): offer users an HTML email option w/ autolinks.
    autolinker = autolink.Autolink()
    was_created = ezt.boolean(comment.sequence == 0)

    email_data = {
        # Pass open_related and closed_related into this method and to
        # the issue view so that we can show it on new issue email.
        'issue': tracker_views.IssueView(issue, users_by_id, config),
        'summary': issue.summary,
        'comment': tracker_views.IssueCommentView(
            project.project_name, comment, users_by_id,
            autolinker, {}, mr, issue),
        'comment_text': comment.content,
        'detail_url': detail_url,
        'was_created': was_created,
        }

    # Generate three versions of email body: link-only is just the link,
    # non-members see some obscured email addresses, and members version has
    # all full email addresses exposed.
    body_link_only = self.link_only_email_template.GetResponse(
      {'detail_url': detail_url, 'was_created': was_created})
    body_for_non_members = self.email_template.GetResponse(email_data)
    framework_views.RevealAllEmails(users_by_id)
    email_data['comment'] = tracker_views.IssueCommentView(
        project.project_name, comment, users_by_id,
        autolinker, {}, mr, issue)
    body_for_members = self.email_template.GetResponse(email_data)

    logging.info('link-only body is:\n%r' % body_link_only)
    logging.info('body for non-members is:\n%r' % body_for_non_members)
    logging.info('body for members is:\n%r' % body_for_members)

    commenter_email = users_by_id[comment.user_id].email
    omit_addrs = set([commenter_email] +
                     [users_by_id[omit_id].email for omit_id in omit_ids])

    auth = authdata.AuthData.FromUserID(
        cnxn, comment.user_id, self.services)
    commenter_in_project = framework_bizobj.UserIsInProject(
        project, auth.effective_ids)
    noisy = tracker_helpers.IsNoisy(len(all_comments) - 1, len(starrer_ids))

    # Give each user a bullet-list of all the reasons that apply for that user.
    group_reason_list = notify_reasons.ComputeGroupReasonList(
        cnxn, self.services, project, issue, config, users_by_id,
        omit_addrs, contributor_could_view, noisy=noisy,
        starrer_ids=starrer_ids, old_owner_id=old_owner_id,
        commenter_in_project=commenter_in_project)

    commenter_view = users_by_id[comment.user_id]
    detail_url = framework_helpers.FormatAbsoluteURLForDomain(
        hostport, issue.project_name, urls.ISSUE_DETAIL,
        id=issue.local_id)
    email_tasks = notify_helpers.MakeBulletedEmailWorkItems(
        group_reason_list, issue, body_link_only, body_for_non_members,
        body_for_members, project, hostport, commenter_view, detail_url,
        seq_num=comment.sequence)

    return email_tasks


class NotifyBlockingChangeTask(notify_helpers.NotifyTaskBase):
  """JSON servlet that notifies appropriate users after a blocking change."""

  _EMAIL_TEMPLATE = 'tracker/issue-blocking-change-notification-email.ezt'
  _LINK_ONLY_EMAIL_TEMPLATE = (
      'tracker/issue-change-notification-email-link-only.ezt')

  def HandleRequest(self, mr):
    """Process the task to notify users after an issue blocking change.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format which is useful just for debugging.
      The main goal is the side-effect of sending emails.
    """
    issue_id = mr.GetPositiveIntParam('issue_id')
    if not issue_id:
      return {
          'params': {},
          'notified': [],
          'message': 'Cannot proceed without a valid issue ID.',
      }
    commenter_id = mr.GetPositiveIntParam('commenter_id')
    omit_ids = [commenter_id]
    hostport = mr.GetParam('hostport')
    delta_blocker_iids = mr.GetIntListParam('delta_blocker_iids')
    send_email = bool(mr.GetIntParam('send_email'))
    params = dict(
        issue_id=issue_id, commenter_id=commenter_id,
        hostport=hostport, delta_blocker_iids=delta_blocker_iids,
        omit_ids=omit_ids, send_email=send_email)

    logging.info('blocking change params are %r', params)
    issue = self.services.issue.GetIssue(mr.cnxn, issue_id)
    if issue.is_spam:
      return {
        'params': params,
        'notified': [],
        }

    upstream_issues = self.services.issue.GetIssues(
        mr.cnxn, delta_blocker_iids)
    logging.info('updating ids %r', [up.local_id for up in upstream_issues])
    upstream_projects = tracker_helpers.GetAllIssueProjects(
        mr.cnxn, upstream_issues, self.services.project)
    upstream_configs = self.services.config.GetProjectConfigs(
        mr.cnxn, list(upstream_projects.keys()))

    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user, [commenter_id])
    commenter_view = users_by_id[commenter_id]

    tasks = []
    if send_email:
      for upstream_issue in upstream_issues:
        one_issue_email_tasks = self._ProcessUpstreamIssue(
            mr.cnxn, upstream_issue,
            upstream_projects[upstream_issue.project_id],
            upstream_configs[upstream_issue.project_id],
            issue, omit_ids, hostport, commenter_view)
        tasks.extend(one_issue_email_tasks)

    notified = notify_helpers.AddAllEmailTasks(tasks)

    return {
        'params': params,
        'notified': notified,
        }

  def _ProcessUpstreamIssue(
      self, cnxn, upstream_issue, upstream_project, upstream_config,
      issue, omit_ids, hostport, commenter_view):
    """Compute notifications for one upstream issue that is now blocking."""
    upstream_detail_url = framework_helpers.FormatAbsoluteURLForDomain(
        hostport, upstream_issue.project_name, urls.ISSUE_DETAIL,
        id=upstream_issue.local_id)
    logging.info('upstream_detail_url = %r', upstream_detail_url)
    detail_url = framework_helpers.FormatAbsoluteURLForDomain(
        hostport, issue.project_name, urls.ISSUE_DETAIL,
        id=issue.local_id)

    # Only issues that any contributor could view are sent to mailing lists.
    contributor_could_view = permissions.CanViewIssue(
        set(), permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
        upstream_project, upstream_issue)

    # Now construct the e-mail to send

    # Note: we purposely do not notify users who starred an issue
    # about changes in blocking.
    users_by_id = framework_views.MakeAllUserViews(
        cnxn, self.services.user,
        tracker_bizobj.UsersInvolvedInIssues([upstream_issue]), omit_ids)

    is_blocking = upstream_issue.issue_id in issue.blocked_on_iids

    email_data = {
        'issue': tracker_views.IssueView(
            upstream_issue, users_by_id, upstream_config),
        'summary': upstream_issue.summary,
        'detail_url': upstream_detail_url,
        'is_blocking': ezt.boolean(is_blocking),
        'downstream_issue_ref': tracker_bizobj.FormatIssueRef(
            (None, issue.local_id)),
        'downstream_issue_url': detail_url,
        }

    # TODO(jrobbins): Generate two versions of email body: members
    # vesion has other member full email addresses exposed.  But, don't
    # expose too many as we iterate through upstream projects.
    body_link_only = self.link_only_email_template.GetResponse(
        {'detail_url': upstream_detail_url, 'was_created': ezt.boolean(False)})
    body = self.email_template.GetResponse(email_data)

    omit_addrs = {users_by_id[omit_id].email for omit_id in omit_ids}

    # Get the transitive set of owners and Cc'd users, and their UserView's.
    # Give each user a bullet-list of all the reasons that apply for that user.
    # Starrers are not notified of blocking changes to reduce noise.
    group_reason_list = notify_reasons.ComputeGroupReasonList(
        cnxn, self.services, upstream_project, upstream_issue,
        upstream_config, users_by_id, omit_addrs, contributor_could_view)
    one_issue_email_tasks = notify_helpers.MakeBulletedEmailWorkItems(
        group_reason_list, upstream_issue, body_link_only, body, body,
        upstream_project, hostport, commenter_view, detail_url)

    return one_issue_email_tasks


class NotifyBulkChangeTask(notify_helpers.NotifyTaskBase):
  """JSON servlet that notifies appropriate users after a bulk edit."""

  _EMAIL_TEMPLATE = 'tracker/issue-bulk-change-notification-email.ezt'

  def HandleRequest(self, mr):
    """Process the task to notify users after an issue blocking change.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format which is useful just for debugging.
      The main goal is the side-effect of sending emails.
    """
    issue_ids = mr.GetIntListParam('issue_ids')
    hostport = mr.GetParam('hostport')
    if not issue_ids:
      return {
          'params': {},
          'notified': [],
          'message': 'Cannot proceed without a valid issue IDs.',
      }

    old_owner_ids = mr.GetIntListParam('old_owner_ids')
    comment_text = mr.GetParam('comment_text')
    commenter_id = mr.GetPositiveIntParam('commenter_id')
    amendments = mr.GetParam('amendments')
    send_email = bool(mr.GetIntParam('send_email'))
    params = dict(
        issue_ids=issue_ids, commenter_id=commenter_id, hostport=hostport,
        old_owner_ids=old_owner_ids, comment_text=comment_text,
        send_email=send_email, amendments=amendments)

    logging.info('bulk edit params are %r', params)
    issues = self.services.issue.GetIssues(mr.cnxn, issue_ids)
    # TODO(jrobbins): For cross-project bulk edits, prefetch all relevant
    # projects and configs and pass a dict of them to subroutines.  For
    # now, all issue must be in the same project.
    project_id = issues[0].project_id
    project = self.services.project.GetProject(mr.cnxn, project_id)
    config = self.services.config.GetProjectConfig(mr.cnxn, project_id)
    issues = [issue for issue in issues if not issue.is_spam]
    anon_perms = permissions.GetPermissions(None, set(), project)

    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user, [commenter_id])
    ids_in_issues = {}
    starrers = {}

    non_private_issues = []
    for issue, old_owner_id in zip(issues, old_owner_ids):
      # TODO(jrobbins): use issue_id consistently rather than local_id.
      starrers[issue.local_id] = self.services.issue_star.LookupItemStarrers(
          mr.cnxn, issue.issue_id)
      named_ids = set()  # users named in user-value fields that notify.
      for fd in config.field_defs:
        named_ids.update(notify_reasons.ComputeNamedUserIDsToNotify(
            issue.field_values, fd))
      direct, indirect = self.services.usergroup.ExpandAnyUserGroups(
          mr.cnxn, list(issue.cc_ids) + list(issue.derived_cc_ids) +
          [issue.owner_id, old_owner_id, issue.derived_owner_id] +
          list(named_ids))
      ids_in_issues[issue.local_id] = set(starrers[issue.local_id])
      ids_in_issues[issue.local_id].update(direct)
      ids_in_issues[issue.local_id].update(indirect)
      ids_in_issue_needing_views = (
          ids_in_issues[issue.local_id] |
          tracker_bizobj.UsersInvolvedInIssues([issue]))
      new_ids_in_issue = [user_id for user_id in ids_in_issue_needing_views
                          if user_id not in users_by_id]
      users_by_id.update(
          framework_views.MakeAllUserViews(
              mr.cnxn, self.services.user, new_ids_in_issue))

      anon_can_view = permissions.CanViewIssue(
          set(), anon_perms, project, issue)
      if anon_can_view:
        non_private_issues.append(issue)

    commenter_view = users_by_id[commenter_id]
    omit_addrs = {commenter_view.email}

    tasks = []
    if send_email:
      email_tasks = self._BulkEditEmailTasks(
          mr.cnxn, issues, old_owner_ids, omit_addrs, project,
          non_private_issues, users_by_id, ids_in_issues, starrers,
          commenter_view, hostport, comment_text, amendments, config)
      tasks = email_tasks

    notified = notify_helpers.AddAllEmailTasks(tasks)
    return {
        'params': params,
        'notified': notified,
        }

  def _BulkEditEmailTasks(
      self, cnxn, issues, old_owner_ids, omit_addrs, project,
      non_private_issues, users_by_id, ids_in_issues, starrers,
      commenter_view, hostport, comment_text, amendments, config):
    """Generate Email PBs to notify interested users after a bulk edit."""
    # 1. Get the user IDs of everyone who could be notified,
    # and make all their user proxies. Also, build a dictionary
    # of all the users to notify and the issues that they are
    # interested in.  Also, build a dictionary of additional email
    # addresses to notify and the issues to notify them of.
    users_by_id = {}
    ids_to_notify_of_issue = {}
    additional_addrs_to_notify_of_issue = collections.defaultdict(list)

    users_to_queries = notify_reasons.GetNonOmittedSubscriptions(
        cnxn, self.services, [project.project_id], {})
    config = self.services.config.GetProjectConfig(
        cnxn, project.project_id)
    for issue, old_owner_id in zip(issues, old_owner_ids):
      issue_participants = set(
          [tracker_bizobj.GetOwnerId(issue), old_owner_id] +
          tracker_bizobj.GetCcIds(issue))
      # users named in user-value fields that notify.
      for fd in config.field_defs:
        issue_participants.update(
            notify_reasons.ComputeNamedUserIDsToNotify(issue.field_values, fd))
      for user_id in ids_in_issues[issue.local_id]:
        # TODO(jrobbins): implement batch GetUser() for speed.
        if not user_id:
          continue
        auth = authdata.AuthData.FromUserID(
            cnxn, user_id, self.services)
        if (auth.user_pb.notify_issue_change and
            not auth.effective_ids.isdisjoint(issue_participants)):
          ids_to_notify_of_issue.setdefault(user_id, []).append(issue)
        elif (auth.user_pb.notify_starred_issue_change and
              user_id in starrers[issue.local_id]):
          # Skip users who have starred issues that they can no longer view.
          starrer_perms = permissions.GetPermissions(
              auth.user_pb, auth.effective_ids, project)
          granted_perms = tracker_bizobj.GetGrantedPerms(
              issue, auth.effective_ids, config)
          starrer_can_view = permissions.CanViewIssue(
              auth.effective_ids, starrer_perms, project, issue,
              granted_perms=granted_perms)
          if starrer_can_view:
            ids_to_notify_of_issue.setdefault(user_id, []).append(issue)
        logging.info(
            'ids_to_notify_of_issue[%s] = %s',
            user_id,
            [i.local_id for i in ids_to_notify_of_issue.get(user_id, [])])

      # Find all subscribers that should be notified.
      subscribers_to_consider = notify_reasons.EvaluateSubscriptions(
          cnxn, issue, users_to_queries, self.services, config)
      for sub_id in subscribers_to_consider:
        auth = authdata.AuthData.FromUserID(cnxn, sub_id, self.services)
        sub_perms = permissions.GetPermissions(
            auth.user_pb, auth.effective_ids, project)
        granted_perms = tracker_bizobj.GetGrantedPerms(
            issue, auth.effective_ids, config)
        sub_can_view = permissions.CanViewIssue(
            auth.effective_ids, sub_perms, project, issue,
            granted_perms=granted_perms)
        if sub_can_view:
          ids_to_notify_of_issue.setdefault(sub_id, [])
          if issue not in ids_to_notify_of_issue[sub_id]:
            ids_to_notify_of_issue[sub_id].append(issue)

      if issue in non_private_issues:
        for notify_addr in issue.derived_notify_addrs:
          additional_addrs_to_notify_of_issue[notify_addr].append(issue)

    # 2. Compose an email specifically for each user, and one email to each
    # notify_addr with all the issues that it.
    # Start from non-members first, then members to reveal email addresses.
    email_tasks = []
    needed_user_view_ids = [uid for uid in ids_to_notify_of_issue
                            if uid not in users_by_id]
    users_by_id.update(framework_views.MakeAllUserViews(
        cnxn, self.services.user, needed_user_view_ids))
    member_ids_to_notify_of_issue = {}
    non_member_ids_to_notify_of_issue = {}
    member_additional_addrs = {}
    non_member_additional_addrs = {}
    addr_to_addrperm = {}  # {email_address: AddrPerm object}
    all_user_prefs = self.services.user.GetUsersPrefs(
        cnxn, ids_to_notify_of_issue)

    # TODO(jrobbins): Merge ids_to_notify_of_issue entries for linked accounts.

    for user_id in ids_to_notify_of_issue:
      if not user_id:
        continue  # Don't try to notify NO_USER_SPECIFIED
      if users_by_id[user_id].email in omit_addrs:
        logging.info('Omitting %s', user_id)
        continue
      user_issues = ids_to_notify_of_issue[user_id]
      if not user_issues:
        continue  # user's prefs indicate they don't want these notifications
      auth = authdata.AuthData.FromUserID(
          cnxn, user_id, self.services)
      is_member = bool(framework_bizobj.UserIsInProject(
          project, auth.effective_ids))
      if is_member:
        member_ids_to_notify_of_issue[user_id] = user_issues
      else:
        non_member_ids_to_notify_of_issue[user_id] = user_issues
      addr = users_by_id[user_id].email
      omit_addrs.add(addr)
      addr_to_addrperm[addr] = notify_reasons.AddrPerm(
          is_member, addr, users_by_id[user_id].user,
          notify_reasons.REPLY_NOT_ALLOWED, all_user_prefs[user_id])

    for addr, addr_issues in additional_addrs_to_notify_of_issue.items():
      auth = None
      try:
        auth = authdata.AuthData.FromEmail(cnxn, addr, self.services)
      except:  # pylint: disable=bare-except
        logging.warning('Cannot find user of email %s ', addr)
      if auth:
        is_member = bool(framework_bizobj.UserIsInProject(
            project, auth.effective_ids))
      else:
        is_member = False
      if is_member:
        member_additional_addrs[addr] = addr_issues
      else:
        non_member_additional_addrs[addr] = addr_issues
      omit_addrs.add(addr)
      addr_to_addrperm[addr] = notify_reasons.AddrPerm(
          is_member, addr, None, notify_reasons.REPLY_NOT_ALLOWED, None)

    for user_id, user_issues in non_member_ids_to_notify_of_issue.items():
      addr = users_by_id[user_id].email
      email = self._FormatBulkIssuesEmail(
          addr_to_addrperm[addr], user_issues, users_by_id,
          commenter_view, hostport, comment_text, amendments, config, project)
      email_tasks.append(email)
      logging.info('about to bulk notify non-member %s (%s) of %s',
                   users_by_id[user_id].email, user_id,
                   [issue.local_id for issue in user_issues])

    for addr, addr_issues in non_member_additional_addrs.items():
      email = self._FormatBulkIssuesEmail(
          addr_to_addrperm[addr], addr_issues, users_by_id, commenter_view,
          hostport, comment_text, amendments, config, project)
      email_tasks.append(email)
      logging.info('about to bulk notify non-member additional addr %s of %s',
                   addr, [addr_issue.local_id for addr_issue in addr_issues])

    framework_views.RevealAllEmails(users_by_id)
    commenter_view.RevealEmail()

    for user_id, user_issues in member_ids_to_notify_of_issue.items():
      addr = users_by_id[user_id].email
      email = self._FormatBulkIssuesEmail(
          addr_to_addrperm[addr], user_issues, users_by_id,
          commenter_view, hostport, comment_text, amendments, config, project)
      email_tasks.append(email)
      logging.info('about to bulk notify member %s (%s) of %s',
                   addr, user_id, [issue.local_id for issue in user_issues])

    for addr, addr_issues in member_additional_addrs.items():
      email = self._FormatBulkIssuesEmail(
          addr_to_addrperm[addr], addr_issues, users_by_id, commenter_view,
          hostport, comment_text, amendments, config, project)
      email_tasks.append(email)
      logging.info('about to bulk notify member additional addr %s of %s',
                   addr, [addr_issue.local_id for addr_issue in addr_issues])

    # 4. Add in the project's issue_notify_address.  This happens even if it
    # is the same as the commenter's email address (which would be an unusual
    # but valid project configuration).  Only issues that any contributor could
    # view are included in emails to the all-issue-activity mailing lists.
    if (project.issue_notify_address
        and project.issue_notify_address not in omit_addrs):
      non_private_issues_live = []
      for issue in issues:
        contributor_could_view = permissions.CanViewIssue(
            set(), permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET,
            project, issue)
        if contributor_could_view:
          non_private_issues_live.append(issue)

      if non_private_issues_live:
        project_notify_addrperm = notify_reasons.AddrPerm(
            True, project.issue_notify_address, None,
            notify_reasons.REPLY_NOT_ALLOWED, None)
        email = self._FormatBulkIssuesEmail(
            project_notify_addrperm, non_private_issues_live,
            users_by_id, commenter_view, hostport, comment_text, amendments,
            config, project)
        email_tasks.append(email)
        omit_addrs.add(project.issue_notify_address)
        logging.info('about to bulk notify all-issues %s of %s',
                     project.issue_notify_address,
                     [issue.local_id for issue in non_private_issues])

    return email_tasks

  def _FormatBulkIssuesEmail(
      self, addr_perm, issues, users_by_id, commenter_view,
      hostport, comment_text, amendments, config, project):
    """Format an email to one user listing many issues."""

    from_addr = emailfmt.FormatFromAddr(
        project, commenter_view=commenter_view, reveal_addr=addr_perm.is_member,
        can_reply_to=False)

    subject, body = self._FormatBulkIssues(
        issues, users_by_id, commenter_view, hostport, comment_text,
        amendments, config, addr_perm)
    body = notify_helpers._TruncateBody(body)

    return dict(from_addr=from_addr, to=addr_perm.address, subject=subject,
                body=body)

  def _FormatBulkIssues(
      self, issues, users_by_id, commenter_view, hostport, comment_text,
      amendments, config, addr_perm):
    """Format a subject and body for a bulk issue edit."""
    project_name = issues[0].project_name

    any_link_only = False
    issue_views = []
    for issue in issues:
      # TODO(jrobbins): choose config from dict of prefetched configs.
      issue_view = tracker_views.IssueView(issue, users_by_id, config)
      issue_view.link_only = ezt.boolean(False)
      if addr_perm and notify_helpers.ShouldUseLinkOnly(addr_perm, issue):
        issue_view.link_only = ezt.boolean(True)
        any_link_only = True
      issue_views.append(issue_view)

    email_data = {
        'any_link_only': ezt.boolean(any_link_only),
        'hostport': hostport,
        'num_issues': len(issues),
        'issues': issue_views,
        'comment_text': comment_text,
        'commenter': commenter_view,
        'amendments': amendments,
    }

    if len(issues) == 1:
      # TODO(jrobbins): use compact email subject lines based on user pref.
      if addr_perm and notify_helpers.ShouldUseLinkOnly(addr_perm, issues[0]):
        subject = 'issue %s in %s' % (issues[0].local_id, project_name)
      else:
        subject = 'issue %s in %s: %s' % (
            issues[0].local_id, project_name, issues[0].summary)
      # TODO(jrobbins): Look up the sequence number instead and treat this
      # more like an individual change for email threading.  For now, just
      # add "Re:" because bulk edits are always replies.
      subject = 'Re: ' + subject
    else:
      subject = '%d issues changed in %s' % (len(issues), project_name)

    body = self.email_template.GetResponse(email_data)

    return subject, body


# For now, this class will not be used to send approval comment notifications
# TODO(jojwang): monorail:3588, it might make sense for this class to handle
# sending comment notifications for approval custom_subfield changes.
class NotifyApprovalChangeTask(notify_helpers.NotifyTaskBase):
  """JSON servlet that notifies appropriate users after an approval change."""

  _EMAIL_TEMPLATE = 'tracker/approval-change-notification-email.ezt'

  def HandleRequest(self, mr):
    """Process the task to notify users after an approval change.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format which is useful just for debugging.
      The main goal is the side-effect of sending emails.
    """

    send_email = bool(mr.GetIntParam('send_email'))
    issue_id = mr.GetPositiveIntParam('issue_id')
    approval_id = mr.GetPositiveIntParam('approval_id')
    comment_id = mr.GetPositiveIntParam('comment_id')
    hostport = mr.GetParam('hostport')

    params = dict(
        temporary='',
        hostport=hostport,
        issue_id=issue_id
        )
    logging.info('approval change params are %r', params)

    issue, approval_value = self.services.issue.GetIssueApproval(
        mr.cnxn, issue_id, approval_id, use_cache=False)
    project = self.services.project.GetProject(mr.cnxn, issue.project_id)
    config = self.services.config.GetProjectConfig(mr.cnxn, issue.project_id)

    approval_fd = tracker_bizobj.FindFieldDefByID(approval_id, config)
    if approval_fd is None:
      raise exceptions.NoSuchFieldDefException()

    # GetCommentsForIssue will fill the sequence for all comments, while
    # other method for getting a single comment will not.
    # The comment sequence is especially useful for Approval issues with
    # many comment sections.
    comment = None
    all_comments = self.services.issue.GetCommentsForIssue(mr.cnxn, issue_id)
    for c in all_comments:
      if c.id == comment_id:
        comment = c
        break
    if not comment:
      raise exceptions.NoSuchCommentException()

    field_user_ids = set()
    relevant_fds = [fd for fd in config.field_defs if
                    not fd.approval_id or
                    fd.approval_id is approval_value.approval_id]
    for fd in relevant_fds:
      field_user_ids.update(
          notify_reasons.ComputeNamedUserIDsToNotify(issue.field_values, fd))
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user, [issue.owner_id],
        approval_value.approver_ids,
        tracker_bizobj.UsersInvolvedInComment(comment),
        list(field_user_ids))

    tasks = []
    if send_email:
      tasks = self._MakeApprovalEmailTasks(
          hostport, issue, project, approval_value, approval_fd.field_name,
          comment, users_by_id, list(field_user_ids), mr.perms)

    notified = notify_helpers.AddAllEmailTasks(tasks)

    return {
        'params': params,
        'notified': notified,
        'tasks': tasks,
        }

  def _MakeApprovalEmailTasks(
      self, hostport, issue, project, approval_value, approval_name,
      comment, users_by_id, user_ids_from_fields, perms):
    """Formulate emails to be sent."""

    # TODO(jojwang): avoid need to make MonorailRequest and autolinker
    # for comment_view OR make make tracker_views._ParseTextRuns public
    # and only pass text_runs to email_data.
    mr = monorailrequest.MonorailRequest(self.services)
    mr.project_name = project.project_name
    mr.project = project
    mr.perms = perms
    autolinker = autolink.Autolink()

    approval_url = framework_helpers.IssueCommentURL(
        hostport, project, issue.local_id, seq_num=comment.sequence)

    comment_view = tracker_views.IssueCommentView(
        project.project_name, comment, users_by_id, autolinker, {}, mr, issue)
    domain_url = framework_helpers.FormatAbsoluteURLForDomain(
        hostport, project.project_name, '/issues/')

    commenter_view = users_by_id[comment.user_id]
    email_data = {
        'domain_url': domain_url,
        'approval_url': approval_url,
        'comment': comment_view,
        'issue_local_id': issue.local_id,
        'summary': issue.summary,
        }
    subject = '%s Approval: %s (Issue %s)' % (
        approval_name, issue.summary, issue.local_id)
    email_body = self.email_template.GetResponse(email_data)
    body = notify_helpers._TruncateBody(email_body)

    recipient_ids = self._GetApprovalEmailRecipients(
        approval_value, comment, issue, user_ids_from_fields,
        omit_ids=[comment.user_id])
    direct, indirect = self.services.usergroup.ExpandAnyGroupEmailRecipients(
        mr.cnxn, recipient_ids)
    # group ids were found in recipient_ids.
    # Re-set recipient_ids to remove group_ids
    if indirect:
      recipient_ids = set(direct + indirect)
      users_by_id.update(framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, indirect))  # already contains direct

    # TODO(jojwang): monorail:3588, refine email contents based on direct
    # and indirect user_ids returned.

    email_tasks = []
    for rid in recipient_ids:
      # TODO(jojwang): monorail:3588, add reveal_addr based on
      # recipient member status
      from_addr = emailfmt.FormatFromAddr(
          project, commenter_view=commenter_view, can_reply_to=False)
      dest_email = users_by_id[rid].email
      email_tasks.append(
          dict(from_addr=from_addr, to=dest_email, subject=subject, body=body)
      )

    return email_tasks

  def _GetApprovalEmailRecipients(
      self, approval_value, comment, issue, user_ids_from_fields,
      omit_ids=None):
    # TODO(jojwang): monorail:3588, reorganize this, since now, comment_content
    # and approval amendments happen in the same comment.
    # NOTE: user_ids_from_fields are all the notify_on=ANY_COMMENT users.
    # However, these users will still be excluded from notifications
    # meant for approvers only eg. (status changed to REVIEW_REQUESTED).
    recipient_ids = []
    if comment.amendments:
      for amendment in comment.amendments:
        if amendment.custom_field_name == 'Status':
          if (approval_value.status is
              tracker_pb2.ApprovalStatus.REVIEW_REQUESTED):
            recipient_ids = approval_value.approver_ids
          else:
            recipient_ids.extend([issue.owner_id])
            recipient_ids.extend(user_ids_from_fields)

        elif amendment.custom_field_name == 'Approvers':
          recipient_ids.extend(approval_value.approver_ids)
          recipient_ids.append(issue.owner_id)
          recipient_ids.extend(user_ids_from_fields)
          recipient_ids.extend(amendment.removed_user_ids)
    else:
      # No amendments, just a comment.
      recipient_ids.extend(approval_value.approver_ids)
      recipient_ids.append(issue.owner_id)
      recipient_ids.extend(user_ids_from_fields)

    if omit_ids:
      recipient_ids = [rid for rid in recipient_ids if rid not in omit_ids]

    return list(set(recipient_ids))


class NotifyRulesDeletedTask(notify_helpers.NotifyTaskBase):
  """JSON servlet that sends one email."""

  _EMAIL_TEMPLATE = 'project/rules-deleted-notification-email.ezt'

  def HandleRequest(self, mr):
    """Process the task to notify project owners after a filter rule
      has been deleted.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format which is useful for debugging.
    """
    project_id = mr.GetPositiveIntParam('project_id')
    rules = mr.GetListParam('filter_rules')
    hostport = mr.GetParam('hostport')

    params = dict(
        project_id=project_id,
        rules=rules,
        hostport=hostport,
        )
    logging.info('deleted filter rules params are %r', params)

    project = self.services.project.GetProject(mr.cnxn, project_id)
    emails_by_id = self.services.user.LookupUserEmails(
        mr.cnxn, project.owner_ids, ignore_missed=True)

    tasks = self._MakeRulesDeletedEmailTasks(
        hostport, project, emails_by_id, rules)
    notified = notify_helpers.AddAllEmailTasks(tasks)

    return {
        'params': params,
        'notified': notified,
        'tasks': tasks,
        }

  def _MakeRulesDeletedEmailTasks(self, hostport, project, emails_by_id, rules):

    rules_url = framework_helpers.FormatAbsoluteURLForDomain(
        hostport, project.project_name, urls.ADMIN_RULES)

    email_data = {
        'project_name': project.project_name,
        'rules': rules,
        'rules_url': rules_url,
    }
    logging.info(email_data)
    subject = '%s Project: Deleted Filter Rules' % project.project_name
    email_body = self.email_template.GetResponse(email_data)
    body = notify_helpers._TruncateBody(email_body)

    email_tasks = []
    for rid in project.owner_ids:
      from_addr = emailfmt.FormatFromAddr(
          project, reveal_addr=True, can_reply_to=False)
      dest_email = emails_by_id.get(rid)
      email_tasks.append(
          dict(from_addr=from_addr, to=dest_email, subject=subject, body=body))

    return email_tasks


class OutboundEmailTask(jsonfeed.InternalTask):
  """JSON servlet that sends one email."""

  def HandleRequest(self, mr):
    """Process the task to send one email message.

    Args:
      mr: common information parsed from the HTTP request.

    Returns:
      Results dictionary in JSON format which is useful just for debugging.
      The main goal is the side-effect of sending emails.
    """
    # To avoid urlencoding the email body, the most salient parameters to this
    # method are passed as a json-encoded POST body.
    try:
      email_params = json.loads(self.request.body)
    except ValueError:
      logging.error(self.request.body)
      raise
    # If running on a GAFYD domain, you must define an app alias on the
    # Application Settings admin web page.
    sender = email_params.get('from_addr')
    reply_to = email_params.get('reply_to')
    to = email_params.get('to')

    if not to:
      # Cannot proceed if we cannot create a valid EmailMessage.
      return {'note': 'Skipping because no "to" address found.'}

    # Don't send emails to any banned users.
    try:
      user_id = self.services.user.LookupUserID(mr.cnxn, to)
      user = self.services.user.GetUser(mr.cnxn, user_id)
      if user.banned:
        logging.info('Not notifying banned user %r', user.email)
        return {'note': 'Skipping because user is banned.'}
    except exceptions.NoSuchUserException:
      pass

    references = email_params.get('references')
    subject = email_params.get('subject')
    body = email_params.get('body')
    html_body = email_params.get('html_body')

    if settings.local_mode:
      to_format = settings.send_local_email_to
    else:
      to_format = settings.send_all_email_to

    if to_format:
      to_user, to_domain = to.split('@')
      to = to_format % {'user': to_user, 'domain': to_domain}
    logging.info(
        'Email:\n sender: %s\n reply_to: %s\n to: %s\n references: %s\n '
        'subject: %s\n body: %s\n html body: %s',
        sender, reply_to, to, references, subject, body, html_body)
    if html_body:
      logging.info('Readable HTML:\n%s', html_body.replace('<br/>', '<br/>\n'))

    message = mail.EmailMessage(
        sender=sender, to=to, subject=subject, body=body)
    if html_body:
      message.html = html_body
    if reply_to:
      message.reply_to = reply_to
    if references:
      message.headers = {'References': references}
    if settings.unit_test_mode:
      logging.info('Sending message "%s" in test mode.', message.subject)
    else:
      sg = SendGridAPIClient(os.environ['SENDGRID_API_KEY'])
      retry_count = 3
      logging.info('build_sendgrid_message')
      sendgrid_from = sg_from(sender)
      sendgrid_to = sg_to(to)
      sendgrid_content = sg_content("text/plain", body)
      sendgrid_message = sg_mail(
      from_email=sendgrid_from, to_emails=sendgrid_to, subject=subject, html_content=sendgrid_content)
      logging.info('sendgrid_message: %s', sendgrid_message)

      for i in range(retry_count):
        try:
          sg_response = sg.send(sendgrid_message)
          logging.info('viaSendgrid status_code: %s, body: %s, headers: %s', sg_response.status_code, sg_response.body, sg_response.headers)
          #message.send()
          break
        except apiproxy_errors.DeadlineExceededError as ex:
          logging.warning('Sending email timed out on try: %d', i)
          #logging.warning(str(ex))
          logging.warning(e.message)

    return dict(
        sender=sender, to=to, subject=subject, body=body, html_body=html_body,
        reply_to=reply_to, references=references)
