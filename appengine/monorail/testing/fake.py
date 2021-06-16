# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Fake object classes that are useful for unit tests."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging
import re
import sys
import time

from six import string_types

import settings
from features import filterrules_helpers
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import monorailrequest
from framework import permissions
from framework import profiler
from framework import validate
from proto import features_pb2
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from proto import usergroup_pb2
from services import caches
from services import config_svc
from services import features_svc
from services import project_svc
from tracker import tracker_bizobj
from tracker import tracker_constants

# Many fakes return partial or constant values, regardless of their arguments.
# pylint: disable=unused-argument

BOUNDARY = '-----thisisaboundary'
OWNER_ROLE = 'OWNER_ROLE'
COMMITTER_ROLE = 'COMMITTER_ROLE'
CONTRIBUTOR_ROLE = 'CONTRIBUTOR_ROLE'
EDITOR_ROLE = 'EDITOR_ROLE'
FOLLOWER_ROLE = 'FOLLOWER_ROLE'

def Hotlist(
    hotlist_name, hotlist_id, hotlist_item_fields=None,
    is_private=False, owner_ids=None, editor_ids=None, follower_ids=None,
    default_col_spec=None, summary=None, description=None):
  hotlist_id = hotlist_id or hash(hotlist_name)
  return features_pb2.MakeHotlist(
      hotlist_name, hotlist_item_fields=hotlist_item_fields,
      hotlist_id=hotlist_id, is_private=is_private, owner_ids=owner_ids or [],
      editor_ids=editor_ids or [], follower_ids=follower_ids or [],
      default_col_spec=default_col_spec, summary=summary,
      description=description)

def HotlistItem(issue_id, rank=None, adder_id=None, date_added=None, note=None):
  return features_pb2.MakeHotlistItem(issue_id=issue_id, rank=rank,
                                      adder_id=adder_id, date_added=date_added,
                                      note=None)

def Project(
    project_name='proj', project_id=None, state=project_pb2.ProjectState.LIVE,
    access=project_pb2.ProjectAccess.ANYONE, moved_to=None,
    cached_content_timestamp=None,
    owner_ids=None, committer_ids=None, contributor_ids=None):
  """Returns a project protocol buffer with the given attributes."""
  project_id = project_id or hash(project_name)
  return project_pb2.MakeProject(
      project_name, project_id=project_id, state=state, access=access,
      moved_to=moved_to, cached_content_timestamp=cached_content_timestamp,
      owner_ids=owner_ids, committer_ids=committer_ids,
      contributor_ids=contributor_ids)


def MakePhase(phase_id, name='', rank=0):
  return tracker_pb2.Phase(phase_id=phase_id, name=name, rank=rank)


def MakeApprovalValue(
    approval_id,
    status=tracker_pb2.ApprovalStatus.NOT_SET,
    setter_id=None,
    set_on=None,
    approver_ids=None,
    phase_id=None):
  if approver_ids is None:
    approver_ids = []
  return tracker_pb2.ApprovalValue(
      approval_id=approval_id,
      status=status,
      setter_id=setter_id,
      set_on=set_on,
      approver_ids=approver_ids,
      phase_id=phase_id)


def MakeFieldValue(
    field_id,
    int_value=None,
    str_value=None,
    user_id=None,
    date_value=None,
    url_value=None,
    derived=None,
    phase_id=None):
  return tracker_pb2.FieldValue(
      field_id=field_id,
      int_value=int_value,
      str_value=str_value,
      user_id=user_id,
      date_value=date_value,
      url_value=url_value,
      derived=derived,
      phase_id=phase_id)


def MakeTestIssue(
    project_id, local_id, summary, status, owner_id, labels=None,
    derived_labels=None, derived_status=None, merged_into=0, star_count=0,
    derived_owner_id=0, issue_id=None, reporter_id=None, opened_timestamp=None,
    closed_timestamp=None, modified_timestamp=None, is_spam=False,
    component_ids=None, project_name=None, field_values=None, cc_ids=None,
    derived_cc_ids=None, assume_stale=True, phases=None, approval_values=None,
    merged_into_external=None, attachment_count=0, derived_component_ids=None):
  """Easily make an Issue for testing."""
  issue = tracker_pb2.Issue()
  issue.project_id = project_id
  issue.project_name = project_name
  issue.local_id = local_id
  issue.issue_id = issue_id if issue_id else 100000 + local_id
  issue.reporter_id = reporter_id if reporter_id else owner_id
  issue.summary = summary
  issue.status = status
  issue.owner_id = owner_id
  issue.derived_owner_id = derived_owner_id
  issue.star_count = star_count
  issue.merged_into = merged_into
  issue.merged_into_external = merged_into_external
  issue.is_spam = is_spam
  issue.attachment_count = attachment_count
  if cc_ids:
    issue.cc_ids = cc_ids
  if derived_cc_ids:
    issue.derived_cc_ids = derived_cc_ids
  issue.assume_stale = assume_stale
  if opened_timestamp:
    issue.opened_timestamp = opened_timestamp
    issue.owner_modified_timestamp = opened_timestamp
    issue.status_modified_timestamp = opened_timestamp
    issue.component_modified_timestamp = opened_timestamp
  if modified_timestamp:
    issue.modified_timestamp = modified_timestamp
  if closed_timestamp:
    issue.closed_timestamp = closed_timestamp
  if labels is not None:
    if isinstance(labels, string_types):
      labels = labels.split()
    issue.labels.extend(labels)
  if derived_labels is not None:
    if isinstance(derived_labels, string_types):
      derived_labels = derived_labels.split()
    issue.derived_labels.extend(derived_labels)
  if derived_status is not None:
    issue.derived_status = derived_status
  if component_ids is not None:
    issue.component_ids = component_ids
  if derived_component_ids is not None:
    issue.derived_component_ids = derived_component_ids
  if field_values is not None:
    issue.field_values = field_values
  if phases is not None:
    issue.phases = phases
  if approval_values is not None:
    issue.approval_values = approval_values
  return issue


def MakeTestConfig(project_id, labels, statuses):
  """Convenient function to make a ProjectIssueConfig object."""
  config = tracker_bizobj.MakeDefaultProjectIssueConfig(project_id)
  if isinstance(labels, string_types):
    labels = labels.split()
  if isinstance(statuses, string_types):
    statuses = statuses.split()
  config.well_known_labels = [
      tracker_pb2.LabelDef(label=lab) for lab in labels]
  config.well_known_statuses = [
      tracker_pb2.StatusDef(status=stat) for stat in statuses]
  return config


class MonorailConnection(object):
  """Fake connection to databases for use in tests."""

  def Commit(self):
    pass

  def Close(self):
    pass


class MonorailRequest(monorailrequest.MonorailRequest):
  """Subclass of MonorailRequest suitable for testing."""

  def __init__(self, services, user_info=None, project=None, perms=None,
               hotlist=None, **kwargs):
    """Construct a test MonorailRequest.

    Typically, this is constructed via testing.helpers.GetRequestObjects,
    which also causes url parsing and optionally initializes the user,
    project, and permissions info.

    Args:
      services: connections to backends.
      user_info: a dict of user attributes to set on a MonorailRequest object.
        For example, "user_id: 5" causes self.auth.user_id=5.
      project: the Project pb for this request.
      perms: a PermissionSet for this request.
    """
    super(MonorailRequest, self).__init__(services, **kwargs)

    if user_info is not None:
      for key in user_info:
        setattr(self.auth, key, user_info[key])
      if 'user_id' in user_info:
        self.auth.effective_ids = {user_info['user_id']}

    self.perms = perms or permissions.ADMIN_PERMISSIONSET
    self.profiler = profiler.Profiler()
    self.project = project
    self.hotlist = hotlist
    if hotlist is not None:
      self.hotlist_id = hotlist.hotlist_id

class UserGroupService(object):
  """Fake UserGroupService class for testing other code."""

  def __init__(self):
    # Test-only sequence of expunged users.
    self.expunged_users_in_groups = []

    self.group_settings = {}
    self.group_members = {}
    self.group_addrs = {}
    self.role_dict = {}

  def TestAddGroupSettings(
      self, group_id, email, who_can_view=None, anyone_can_join=False,
      who_can_add=None, external_group_type=None,
      last_sync_time=0, friend_projects=None):
    """Set up a fake group for testing.

    Args:
      group_id: int user ID of the new user group.
      email: string email address to identify the user group.
      who_can_view: string enum 'owners', 'members', or 'anyone'.
      anyone_can_join: optional boolean to allow any users to join the group.
      who_can_add: optional list of int user IDs of users who can add
          more members to the group.
    """
    friend_projects = friend_projects or []
    group_settings = usergroup_pb2.MakeSettings(
        who_can_view or 'members',
        external_group_type, last_sync_time, friend_projects)
    self.group_settings[group_id] = group_settings
    self.group_addrs[group_id] = email
    # TODO(jrobbins): store the other settings.

  def TestAddMembers(self, group_id, user_ids, role='member'):
    self.group_members.setdefault(group_id, []).extend(user_ids)
    for user_id in user_ids:
      self.role_dict.setdefault(group_id, {})[user_id] = role

  def LookupAllMemberships(self, _cnxn, user_ids, use_cache=True):
    return {
        user_id: self.LookupMemberships(_cnxn, user_id)
        for user_id in user_ids
    }

  def LookupMemberships(self, _cnxn, user_id):
    memberships = {
        group_id for group_id, member_ids in self.group_members.items()
        if user_id in member_ids}
    return memberships

  def DetermineWhichUserIDsAreGroups(self, _cnxn, user_ids):
    return [uid for uid in user_ids
            if uid in self.group_settings]

  def GetAllUserGroupsInfo(self, cnxn):
    infos = []
    for group_id in self.group_settings:
      infos.append(
          (self.group_addrs[group_id],
           len(self.group_members.get(group_id, [])),
           self.group_settings[group_id], group_id))

    return infos

  def GetAllGroupSettings(self, _cnxn, group_ids):
    return {gid: self.group_settings[gid]
            for gid in group_ids
            if gid in self.group_settings}

  def GetGroupSettings(self, cnxn, group_id):
    return self.GetAllGroupSettings(cnxn, [group_id]).get(group_id)

  def CreateGroup(self, cnxn, services, email, who_can_view_members,
                  ext_group_type=None, friend_projects=None):
    friend_projects = friend_projects or []
    group_id = services.user.LookupUserID(
        cnxn, email, autocreate=True, allowgroups=True)
    self.group_addrs[group_id] = email
    group_settings = usergroup_pb2.MakeSettings(
        who_can_view_members, ext_group_type, 0, friend_projects)
    self.UpdateSettings(cnxn, group_id, group_settings)
    return group_id

  def DeleteGroups(self, cnxn, group_ids):
    member_ids_dict, owner_ids_dict = self.LookupMembers(cnxn, group_ids)
    citizens_id_dict = collections.defaultdict(list)
    for g_id, user_ids in member_ids_dict.items():
      citizens_id_dict[g_id].extend(user_ids)
    for g_id, user_ids in owner_ids_dict.items():
      citizens_id_dict[g_id].extend(user_ids)
    for g_id, citizen_ids in citizens_id_dict.items():
      # Remove group members, friend projects and settings
      self.RemoveMembers(cnxn, g_id, citizen_ids)
      self.group_settings.pop(g_id, None)

  def LookupComputedMemberships(self, cnxn, domain, use_cache=True):
    group_email = 'everyone@%s' % domain
    group_id = self.LookupUserGroupID(cnxn, group_email, use_cache=use_cache)
    if group_id:
      return [group_id]

    return []

  def LookupUserGroupID(self, cnxn, group_email, use_cache=True):
    for group_id in self.group_settings:
      if group_email == self.group_addrs.get(group_id):
        return group_id
    return None

  def LookupMembers(self, _cnxn, group_id_list):
    members_dict = {}
    owners_dict = {}
    for gid in group_id_list:
      members_dict[gid] = []
      owners_dict[gid] = []
      for mid in self.group_members.get(gid, []):
        if self.role_dict.get(gid, {}).get(mid) == 'owner':
          owners_dict[gid].append(mid)
        elif self.role_dict.get(gid, {}).get(mid) == 'member':
          members_dict[gid].append(mid)
    return members_dict, owners_dict

  def LookupAllMembers(self, _cnxn, group_id_list):
    direct_members, direct_owners = self.LookupMembers(
        _cnxn, group_id_list)
    members_dict = {}
    owners_dict = {}
    for gid in group_id_list:
      members = direct_members[gid]
      owners = direct_owners[gid]
      owners_dict[gid] = owners
      members_dict[gid] = members
      group_ids = set([uid for uid in members + owners
                       if uid in self.group_settings])
      while group_ids:
        indirect_members, indirect_owners = self.LookupMembers(
            _cnxn, group_ids)
        child_members = set()
        child_owners = set()
        for _, children in indirect_members.items():
          child_members.update(children)
        for _, children in indirect_owners.items():
          child_owners.update(children)
        members_dict[gid].extend(list(child_members))
        owners_dict[gid].extend(list(child_owners))
        group_ids = set(self.DetermineWhichUserIDsAreGroups(
            _cnxn, list(child_members) + list(child_owners)))
      members_dict[gid] = list(set(members_dict[gid]))
    return members_dict, owners_dict


  def RemoveMembers(self, _cnxn, group_id, old_member_ids):
    current_member_ids = self.group_members.get(group_id, [])
    revised_member_ids = [mid for mid in current_member_ids
                          if mid not in old_member_ids]
    self.group_members[group_id] = revised_member_ids

  def UpdateMembers(self, _cnxn, group_id, member_ids, new_role):
    self.RemoveMembers(_cnxn, group_id, member_ids)
    self.TestAddMembers(group_id, member_ids, new_role)

  def UpdateSettings(self, _cnxn, group_id, group_settings):
    self.group_settings[group_id] = group_settings

  def ExpandAnyUserGroups(self, cnxn, user_ids):
    # TODO(jojwang): Update fake.DetermineWhichUserIDsAreGroups
    # to return unique ids so set does not have to be called outside
    # the method.
    group_ids = set(self.DetermineWhichUserIDsAreGroups(cnxn, user_ids))
    direct_ids = [uid for uid in user_ids if uid not in group_ids]
    member_ids_dict, owner_ids_dict = self.LookupAllMembers(cnxn, group_ids)

    indirect_ids = set()
    for gid in group_ids:
      indirect_ids.update(member_ids_dict[gid])
      indirect_ids.update(owner_ids_dict[gid])
    # It's possible that a user has both direct and indirect memberships of
    # one group. In this case, mark the user as direct member only.
    indirect_ids = [iid for iid in indirect_ids if iid not in direct_ids]

    return direct_ids, list(indirect_ids)

  def ExpandAnyGroupEmailRecipients(self, cnxn, user_ids):
    group_ids = set(self.DetermineWhichUserIDsAreGroups(cnxn, user_ids))
    group_settings_dict = self.GetAllGroupSettings(cnxn, group_ids)
    member_ids_dict, owner_ids_dict = self.LookupAllMembers(cnxn, group_ids)
    indirect_ids = set()
    direct_ids = {uid for uid in user_ids if uid not in group_ids}
    for gid, group_settings in group_settings_dict.items():
      if group_settings.notify_members:
        indirect_ids.update(member_ids_dict.get(gid, set()))
        indirect_ids.update(owner_ids_dict.get(gid, set()))
      if group_settings.notify_group:
        direct_ids.add(gid)

    return list(direct_ids), list(indirect_ids)

  def LookupVisibleMembers(
      self, cnxn, group_id_list, perms, effective_ids, services):
    settings_dict = self.GetAllGroupSettings(cnxn, group_id_list)
    group_ids = list(settings_dict.keys())

    direct_member_ids_dict, direct_owner_ids_dict = self.LookupMembers(
        cnxn, group_ids)
    all_member_ids_dict, all_owner_ids_dict = self.LookupAllMembers(
        cnxn, group_ids)
    visible_member_ids_dict = {}
    visible_owner_ids_dict = {}
    for gid in group_ids:
      member_ids = all_member_ids_dict[gid]
      owner_ids = all_owner_ids_dict[gid]
      if permissions.CanViewGroupMembers(
          perms, effective_ids, settings_dict[gid], member_ids, owner_ids, []):
        visible_member_ids_dict[gid] = direct_member_ids_dict[gid]
        visible_owner_ids_dict[gid] = direct_owner_ids_dict[gid]

    return visible_member_ids_dict, visible_owner_ids_dict

  def ValidateFriendProjects(self, cnxn, services, friend_projects):
    project_names = list(filter(None, re.split('; |, | |;|,', friend_projects)))
    id_dict = services.project.LookupProjectIDs(cnxn, project_names)
    missed_projects = []
    result = []
    for p_name in project_names:
      if p_name in id_dict:
        result.append(id_dict[p_name])
      else:
        missed_projects.append(p_name)
    error_msg = ''
    if missed_projects:
      error_msg = 'Project(s) %s do not exist' % ', '.join(missed_projects)
      return None, error_msg
    else:
      return result, None

  def ExpungeUsersInGroups(self, cnxn, ids):
    self.expunged_users_in_groups.extend(ids)


class CacheManager(object):

  def __init__(self, invalidate_tbl=None):
    self.last_call = None
    self.cache_registry = collections.defaultdict(list)
    self.processed_invalidations_up_to = 0

  def RegisterCache(self, cache, kind):
    """Register a cache to be notified of future invalidations."""
    self.cache_registry[kind].append(cache)

  def DoDistributedInvalidation(self, cnxn):
    """Drop any cache entries that were invalidated by other jobs."""
    self.last_call = 'DoDistributedInvalidation', cnxn

  def StoreInvalidateRows(self, cnxn, kind, keys):
    """Store database rows to let all frontends know to invalidate."""
    self.last_call = 'StoreInvalidateRows', cnxn, kind, keys

  def StoreInvalidateAll(self, cnxn, kind):
    """Store a database row to let all frontends know to invalidate."""
    self.last_call = 'StoreInvalidateAll', cnxn, kind



class UserService(object):

  def __init__(self):
    """Creates a test-appropriate UserService object."""
    self.users_by_email = {}  # {email: user_id, ...}
    self.users_by_id = {}  # {user_id: email, ...}
    self.test_users = {}  # {user_id: user_pb, ...}
    self.visited_hotlists = {}  # user_id:[(hotlist_id, viewed), ...]
    self.invite_rows = []  # (parent_id, child_id)
    self.linked_account_rows = []  # (parent_id, child_id)
    self.prefs_dict = {}  # {user_id: UserPrefs}

  def TestAddUser(self, email, user_id, add_user=True, banned=False):
    """Add a user to the fake UserService instance.

    Args:
      email: Email of the user.
      user_id: int user ID.
      add_user: Flag whether user pb should be created, i.e. whether a
          Monorail account should be created
      banned: Boolean to set the user as banned

    Returns:
      The User PB that was added, or None.
    """
    self.users_by_email[email] = user_id
    self.users_by_id[user_id] = email

    user = None
    if add_user:
      user = user_pb2.MakeUser(user_id)
      user.is_site_admin = False
      user.email = email
      user.obscure_email = True
      if banned:
        user.banned = 'is banned'
      self.test_users[user_id] = user

    return user

  def GetUser(self, cnxn, user_id):
    return self.GetUsersByIDs(cnxn, [user_id])[user_id]

  def _CreateUser(self, _cnxn, email):
    if email in self.users_by_email:
      return
    user_id = framework_helpers.MurmurHash3_x86_32(email)
    self.TestAddUser(email, user_id)

  def _CreateUsers(self, cnxn, emails):
    for email in emails:
      self._CreateUser(cnxn, email)

  def LookupUserID(self, cnxn, email, autocreate=False, allowgroups=False):
    email_dict = self.LookupUserIDs(
        cnxn, [email], autocreate=autocreate, allowgroups=allowgroups)
    if email in email_dict:
      return email_dict[email]
    raise exceptions.NoSuchUserException('%r not found' % email)

  def GetUsersByIDs(self, cnxn, user_ids, use_cache=True, skip_missed=False):
    user_dict = {}
    for user_id in user_ids:
      if user_id and self.test_users.get(user_id):
        user_dict[user_id] = self.test_users[user_id]
      elif not skip_missed:
        user_dict[user_id] = user_pb2.MakeUser(user_id)
    return user_dict

  def LookupExistingUserIDs(self, cnxn, emails):
    email_dict = {
        email: self.users_by_email[email]
        for email in emails
        if email in self.users_by_email}
    return email_dict

  def LookupUserIDs(self, cnxn, emails, autocreate=False,
                    allowgroups=False):
    email_dict = {}
    needed_emails = [email.lower() for email in emails
                     if email
                     and not framework_constants.NO_VALUE_RE.match(email)]
    for email in needed_emails:
      user_id = self.users_by_email.get(email)
      if not user_id:
        if autocreate and validate.IsValidEmail(email):
          self._CreateUser(cnxn, email)
          user_id = self.users_by_email.get(email)
        elif not autocreate:
          raise exceptions.NoSuchUserException('%r' % email)
      if user_id:
        email_dict[email] = user_id
    return email_dict

  def LookupUserEmail(self, _cnxn, user_id):
    email = self.users_by_id.get(user_id)
    if not email:
      raise exceptions.NoSuchUserException('No user has ID %r' % user_id)
    return email

  def LookupUserEmails(self, cnxn, user_ids, ignore_missed=False):
    if ignore_missed:
      user_dict = {}
      for user_id in user_ids:
        try:
          user_dict[user_id] = self.LookupUserEmail(cnxn, user_id)
        except exceptions.NoSuchUserException:
          continue
      return user_dict
    user_dict = {
        user_id: self.LookupUserEmail(cnxn, user_id)
        for user_id in user_ids}
    return user_dict

  def UpdateUser(self, _cnxn, user_id, user):
    """Updates the user pb."""
    self.test_users[user_id] = user

  def UpdateUserBan(self, _cnxn, user_id, user, is_banned=None,
        banned_reason=None):
    """Updates the user pb."""
    self.test_users[user_id] = user
    user.banned = banned_reason if is_banned else ''

  def GetPendingLinkedInvites(self, cnxn, user_id):
    invite_as_parent = [row[1] for row in self.invite_rows
                        if row[0] == user_id]
    invite_as_child = [row[0] for row in self.invite_rows
                       if row[1] == user_id]
    return invite_as_parent, invite_as_child

  def InviteLinkedParent(self, cnxn, parent_id, child_id):
    self.invite_rows.append((parent_id, child_id))

  def AcceptLinkedChild(self, cnxn, parent_id, child_id):
    if (parent_id, child_id) not in self.invite_rows:
      raise exceptions.InputException('No such invite')
    self.linked_account_rows.append((parent_id, child_id))
    self.invite_rows = [
        (p_id, c_id) for (p_id, c_id) in self.invite_rows
        if p_id != parent_id and c_id != child_id]
    self.GetUser(cnxn, parent_id).linked_child_ids.append(child_id)
    self.GetUser(cnxn, child_id).linked_parent_id = parent_id

  def UnlinkAccounts(self, _cnxn, parent_id, child_id):
    """Delete a linked-account relationship."""
    if not parent_id:
      raise exceptions.InputException('Parent account is missing')
    if not child_id:
      raise exceptions.InputException('Child account is missing')
    self.linked_account_rows = [(p, c) for (p, c) in self.linked_account_rows
                                if (p, c) != (parent_id, child_id)]

  def UpdateUserSettings(
      self, cnxn, user_id, user, notify=None, notify_starred=None,
      email_compact_subject=None, email_view_widget=None,
      notify_starred_ping=None, obscure_email=None, after_issue_update=None,
      is_site_admin=None, is_banned=None, banned_reason=None,
      keep_people_perms_open=None, preview_on_hover=None,
      vacation_message=None):
    # notifications
    if notify is not None:
      user.notify_issue_change = notify
    if notify_starred is not None:
      user.notify_starred_issue_change = notify_starred
    if notify_starred_ping is not None:
      user.notify_starred_ping = notify_starred_ping
    if email_compact_subject is not None:
      user.email_compact_subject = email_compact_subject
    if email_view_widget is not None:
      user.email_view_widget = email_view_widget

    # display options
    if after_issue_update is not None:
      user.after_issue_update = user_pb2.IssueUpdateNav(after_issue_update)
    if preview_on_hover is not None:
      user.preview_on_hover = preview_on_hover
    if keep_people_perms_open is not None:
      user.keep_people_perms_open = keep_people_perms_open

    # misc
    if obscure_email is not None:
      user.obscure_email = obscure_email

    # admin
    if is_site_admin is not None:
      user.is_site_admin = is_site_admin
    if is_banned is not None:
      if is_banned:
        user.banned = banned_reason or 'No reason given'
      else:
        user.reset('banned')

    # user availability
    if vacation_message is not None:
      user.vacation_message = vacation_message

    return self.UpdateUser(cnxn, user_id, user)

  def GetUsersPrefs(self, cnxn, user_ids, use_cache=True):
    for user_id in user_ids:
      if user_id not in self.prefs_dict:
        self.prefs_dict[user_id] = user_pb2.UserPrefs(user_id=user_id)
    return self.prefs_dict

  def GetUserPrefs(self, cnxn, user_id, use_cache=True):
    """Return a UserPrefs PB for the requested user ID."""
    prefs_dict = self.GetUsersPrefs(cnxn, [user_id], use_cache=use_cache)
    return prefs_dict[user_id]

  def GetUserPrefsByEmail(self, cnxn, email, use_cache=True):
    """Return a UserPrefs PB for the requested email, or an empty UserPrefs."""
    try:
      user_id = self.LookupUserID(cnxn, email)
      user_prefs = self.GetUserPrefs(cnxn, user_id, use_cache=use_cache)
    except exceptions.NoSuchUserException:
      user_prefs = user_pb2.UserPrefs()
    return user_prefs

  def SetUserPrefs(self, cnxn, user_id, pref_values):
    userprefs = self.GetUserPrefs(cnxn, user_id)
    names_to_overwrite = {upv.name for upv in pref_values}
    userprefs.prefs = [upv for upv in userprefs.prefs
                       if upv.name not in names_to_overwrite]
    userprefs.prefs.extend(pref_values)

  def ExpungeUsers(self, cnxn, user_ids):
    for user_id in user_ids:
      self.test_users.pop(user_id, None)
      self.prefs_dict.pop(user_id, None)
      email = self.users_by_id.pop(user_id, None)
      if email:
        self.users_by_email.pop(email, None)

    self.invite_rows = [row for row in self.invite_rows
                        if row[0] not in user_ids and row[1] not in user_ids]
    self.linked_account_rows = [
        row for row in self.linked_account_rows
        if row[0] not in user_ids and row[1] not in user_ids]

  def TotalUsersCount(self, cnxn):
    return len(self.users_by_id) - 1 if (
        framework_constants.DELETED_USER_ID in self.users_by_id
        ) else len(self.users_by_id)

  def GetAllUserEmailsBatch(self, cnxn, limit=1000, offset=0):
    sorted_user_ids = sorted(self.users_by_id.keys())
    sorted_user_ids = [
        user_id for user_id in sorted_user_ids
        if user_id != framework_constants.DELETED_USER_ID]
    emails = []
    for i in range(offset, offset + limit):
      try:
        user_id = sorted_user_ids[i]
        if user_id != framework_constants.DELETED_USER_ID:
          emails.append(self.users_by_id[user_id])
      except IndexError:
        break
    return emails

  def GetRecentlyVisitedHotlists(self, _cnxn, user_id):
    try:
      return self.visited_hotlists[user_id]
    except KeyError:
      return []

  def AddVisitedHotlist(self, _cnxn, user_id, hotlist_id, commit=True):
    try:
      user_visited_tuples = self.visited_hotlists[user_id]
      self.visited_hotlists[user_id] = [
          hid for hid in user_visited_tuples if hid != hotlist_id]
    except KeyError:
      self.visited_hotlists[user_id] = []
    self.visited_hotlists[user_id].append(hotlist_id)

  def ExpungeUsersHotlistsHistory(self, cnxn, user_ids, commit=True):
    for user_id in user_ids:
      self.visited_hotlists.pop(user_id, None)


class AbstractStarService(object):
  """Fake StarService."""

  def __init__(self):
    self.stars_by_item_id = {}
    self.stars_by_starrer_id = {}
    self.expunged_item_ids = []

  def ExpungeStars(self, _cnxn, item_id, commit=True, limit=None):
    self.expunged_item_ids.append(item_id)
    old_starrers = self.stars_by_item_id.get(item_id, [])
    self.stars_by_item_id[item_id] = []
    for old_starrer in old_starrers:
      if self.stars_by_starrer_id.get(old_starrer):
        self.stars_by_starrer_id[old_starrer] = [
            it for it in self.stars_by_starrer_id[old_starrer]
            if it != item_id]

  def ExpungeStarsByUsers(self, _cnxn, user_ids, limit=None):
    for user_id in user_ids:
      item_ids = self.stars_by_starrer_id.pop(user_id, [])
      for item_id in item_ids:
        starrers = self.stars_by_item_id.get(item_id, None)
        if starrers:
          self.stars_by_item_id[item_id] = [
              starrer for starrer in starrers if starrer != user_id]

  def LookupItemStarrers(self, _cnxn, item_id):
    return self.stars_by_item_id.get(item_id, [])

  def LookupStarredItemIDs(self, _cnxn, starrer_user_id):
    return self.stars_by_starrer_id.get(starrer_user_id, [])

  def IsItemStarredBy(self, cnxn, item_id, starrer_user_id):
    return item_id in self.LookupStarredItemIDs(cnxn, starrer_user_id)

  def CountItemStars(self, cnxn, item_id):
    return len(self.LookupItemStarrers(cnxn, item_id))

  def CountItemsStars(self, cnxn, item_ids):
    return {item_id: self.CountItemStars(cnxn, item_id)
            for item_id in item_ids}

  def _SetStar(self, cnxn, item_id, starrer_user_id, starred):
    if starred and not self.IsItemStarredBy(cnxn, item_id, starrer_user_id):
      self.stars_by_item_id.setdefault(item_id, []).append(starrer_user_id)
      self.stars_by_starrer_id.setdefault(starrer_user_id, []).append(item_id)

    elif not starred and self.IsItemStarredBy(cnxn, item_id, starrer_user_id):
      self.stars_by_item_id[item_id].remove(starrer_user_id)
      self.stars_by_starrer_id[starrer_user_id].remove(item_id)

  def SetStar(self, cnxn, item_id, starrer_user_id, starred):
    self._SetStar(cnxn, item_id, starrer_user_id, starred)

  def SetStarsBatch(self, cnxn, item_id, starrer_user_ids, starred):
    for starrer_user_id in starrer_user_ids:
      self._SetStar(cnxn, item_id, starrer_user_id, starred)


class UserStarService(AbstractStarService):
  pass


class ProjectStarService(AbstractStarService):
  pass


class HotlistStarService(AbstractStarService):
  pass


class IssueStarService(AbstractStarService):

  # pylint: disable=arguments-differ
  def SetStar(
      self, cnxn, services, _config, issue_id, starrer_user_id,
      starred):
    super(IssueStarService, self).SetStar(
        cnxn, issue_id, starrer_user_id, starred)
    try:
      issue = services.issue.GetIssue(cnxn, issue_id)
      issue.star_count += (1 if starred else -1)
    except exceptions.NoSuchIssueException:
      pass

  # pylint: disable=arguments-differ
  def SetStarsBatch(
      self, cnxn, _service, _config, issue_id, starrer_user_ids,
      starred):
    super(IssueStarService, self).SetStarsBatch(
        cnxn, issue_id, starrer_user_ids, starred)


class ProjectService(object):
  """Fake ProjectService object.

  Provides methods for creating users and projects, which are accessible
  through parts of the real ProjectService interface.
  """

  def __init__(self):
    self.test_projects = {}  # project_name -> project_pb
    self.projects_by_id = {}  # project_id -> project_pb
    self.test_star_manager = None
    self.indexed_projects = {}
    self.unindexed_projects = set()
    self.index_counter = 0
    self.project_commitments = {}
    self.ac_exclusion_ids = {}
    self.no_expand_ids = {}

  def TestAddProject(
      self, name, summary='', state=project_pb2.ProjectState.LIVE,
      owner_ids=None, committer_ids=None, contrib_ids=None,
      issue_notify_address=None, state_reason='',
      description=None, project_id=None, process_inbound_email=None,
      access=None):
    """Add a project to the fake ProjectService object.

    Args:
      name: The name of the project. Will replace any existing project under
        the same name.
      summary: The summary string of the project.
      state: Initial state for the project from project_pb2.ProjectState.
      owner_ids: List of user ids for project owners
      committer_ids: List of user ids for project committers
      contrib_ids: List of user ids for project contributors
      issue_notify_address: email address to send issue change notifications
      state_reason: string describing the reason the project is in its current
        state.
      description: The description string for this project
      project_id: A unique integer identifier for the created project.
      process_inbound_email: True to make this project accept inbound email.
      access: One of the values of enum project_pb2.ProjectAccess.

    Returns:
      A populated project PB.
    """
    proj_pb = project_pb2.Project()
    proj_pb.project_id = project_id or hash(name) % 100000
    proj_pb.project_name = name
    proj_pb.summary = summary
    proj_pb.state = state
    proj_pb.state_reason = state_reason
    if description is not None:
      proj_pb.description = description

    self.TestAddProjectMembers(owner_ids, proj_pb, OWNER_ROLE)
    self.TestAddProjectMembers(committer_ids, proj_pb, COMMITTER_ROLE)
    self.TestAddProjectMembers(contrib_ids, proj_pb, CONTRIBUTOR_ROLE)

    if issue_notify_address is not None:
      proj_pb.issue_notify_address = issue_notify_address
    if process_inbound_email is not None:
      proj_pb.process_inbound_email = process_inbound_email
    if access is not None:
      proj_pb.access = access

    self.test_projects[name] = proj_pb
    self.projects_by_id[proj_pb.project_id] = proj_pb
    return proj_pb

  def TestAddProjectMembers(self, user_id_list, proj_pb, role):
    if user_id_list is not None:
      for user_id in user_id_list:
        if role == OWNER_ROLE:
          proj_pb.owner_ids.append(user_id)
        elif role == COMMITTER_ROLE:
          proj_pb.committer_ids.append(user_id)
        elif role == CONTRIBUTOR_ROLE:
          proj_pb.contributor_ids.append(user_id)

  def LookupProjectIDs(self, cnxn, project_names):
    return {
        project_name: self.test_projects[project_name].project_id
        for project_name in project_names
        if project_name in self.test_projects}

  def LookupProjectNames(self, cnxn, project_ids):
    projects_dict = self.GetProjects(cnxn, project_ids)
    return {p.project_id: p.project_name
            for p in projects_dict.values()}

  def CreateProject(
      self, _cnxn, project_name, owner_ids, committer_ids,
      contributor_ids, summary, description,
      state=project_pb2.ProjectState.LIVE, access=None,
      read_only_reason=None,
      home_page=None, docs_url=None, source_url=None,
      logo_gcs_id=None, logo_file_name=None):
    """Create and store a Project with the given attributes."""
    if project_name in self.test_projects:
      raise exceptions.ProjectAlreadyExists()
    project = self.TestAddProject(
        project_name, summary=summary, state=state,
        owner_ids=owner_ids, committer_ids=committer_ids,
        contrib_ids=contributor_ids, description=description,
        access=access)
    return project.project_id

  def ExpungeProject(self, _cnxn, project_id):
    project = self.projects_by_id.get(project_id)
    if project:
      self.test_projects.pop(project.project_name, None)

  def GetProjectsByName(self, _cnxn, project_name_list, use_cache=True):
    return {
        pn: self.test_projects[pn] for pn in project_name_list
        if pn in self.test_projects}

  def GetProjectByName(self, _cnxn, name, use_cache=True):
    return self.test_projects.get(name)

  def GetProjectList(self, cnxn, project_id_list, use_cache=True):
    project_dict = self.GetProjects(cnxn, project_id_list, use_cache=use_cache)
    return [project_dict[pid] for pid in project_id_list
            if pid in project_dict]

  def GetVisibleLiveProjects(
      self, _cnxn, logged_in_user, effective_ids, domain=None, use_cache=True):
    project_ids = list(self.projects_by_id.keys())
    visible_project_ids = []
    for pid in project_ids:
      can_view = permissions.UserCanViewProject(
          logged_in_user, effective_ids, self.projects_by_id[pid])
      different_domain = framework_helpers.GetNeededDomain(
          self.projects_by_id[pid].project_name, domain)
      if can_view and not different_domain:
        visible_project_ids.append(pid)

    return visible_project_ids

  def GetProjects(self, _cnxn, project_ids, use_cache=True):
    result = {}
    for project_id in project_ids:
      project = self.projects_by_id.get(project_id)
      if project:
        result[project_id] = project
      else:
        raise exceptions.NoSuchProjectException(project_id)
    return result

  def GetAllProjects(self, _cnxn, use_cache=True):
    result = {}
    for project_id in self.projects_by_id:
      project = self.projects_by_id.get(project_id)
      result[project_id] = project
    return result


  def GetProject(self, cnxn, project_id, use_cache=True):
    """Load the specified project from the database."""
    project_id_dict = self.GetProjects(cnxn, [project_id], use_cache=use_cache)
    if project_id not in project_id_dict:
      raise exceptions.NoSuchProjectException()
    return project_id_dict[project_id]

  @staticmethod
  def IsValidProjectName(string):
    """Return true if the given string is a valid project name."""
    return project_svc.RE_PROJECT_NAME.match(string)

  def GetProjectCommitments(self, _cnxn, project_id):
    if project_id in self.project_commitments:
      return self.project_commitments[project_id]

    project_commitments = project_pb2.ProjectCommitments()
    project_commitments.project_id = project_id
    return project_commitments

  def TestStoreProjectCommitments(self, project_commitments):
    key = project_commitments.project_id
    self.project_commitments[key] = project_commitments

  def GetProjectAutocompleteExclusion(self, cnxn, project_id):
    return (self.ac_exclusion_ids.get(project_id, []),
            self.no_expand_ids.get(project_id, []))

  def UpdateProject(
      self,
      _cnxn,
      project_id,
      summary=None,
      description=None,
      state=None,
      state_reason=None,
      access=None,
      issue_notify_address=None,
      attachment_bytes_used=None,
      attachment_quota=None,
      moved_to=None,
      process_inbound_email=None,
      only_owners_remove_restrictions=None,
      read_only_reason=None,
      cached_content_timestamp=None,
      only_owners_see_contributors=None,
      delete_time=None,
      recent_activity=None,
      revision_url_format=None,
      home_page=None,
      docs_url=None,
      source_url=None,
      logo_gcs_id=None,
      logo_file_name=None,
      issue_notify_always_detailed=None):
    project = self.projects_by_id.get(project_id)
    if not project:
      raise exceptions.NoSuchProjectException(
          'Project "%s" not found!' % project_id)

    # TODO(jrobbins): implement all passed arguments - probably as a utility
    # method shared with the real persistence implementation.
    if read_only_reason is not None:
      project.read_only_reason = read_only_reason
    if attachment_bytes_used is not None:
      project.attachment_bytes_used = attachment_bytes_used

  def UpdateProjectRoles(
      self, _cnxn, project_id, owner_ids, committer_ids,
      contributor_ids, now=None):
    project = self.projects_by_id.get(project_id)
    if not project:
      raise exceptions.NoSuchProjectException(
          'Project "%s" not found!' % project_id)

    project.owner_ids = owner_ids
    project.committer_ids = committer_ids
    project.contributor_ids = contributor_ids

  def MarkProjectDeletable(
      self, _cnxn, project_id, _config_service):
    project = self.projects_by_id[project_id]
    project.project_name = 'DELETABLE_%d' % project_id
    project.state = project_pb2.ProjectState.DELETABLE

  def UpdateRecentActivity(self, _cnxn, _project_id, now=None):
    pass

  def GetUserRolesInAllProjects(self, _cnxn, effective_ids):
    owned_project_ids = set()
    membered_project_ids = set()
    contrib_project_ids = set()

    for project in self.projects_by_id.values():
      if not effective_ids.isdisjoint(project.owner_ids):
        owned_project_ids.add(project.project_id)
      elif not effective_ids.isdisjoint(project.committer_ids):
        membered_project_ids.add(project.project_id)
      elif not effective_ids.isdisjoint(project.contributor_ids):
        contrib_project_ids.add(project.project_id)

    return owned_project_ids, membered_project_ids, contrib_project_ids

  def ExpungeUsersInProjects(self, cnxn, user_ids, limit=None):
    for project in self.projects_by_id.values():
      project.owner_ids = [owner_id for owner_id in project.owner_ids
                           if owner_id not in user_ids]
      project.committer_ids = [com_id for com_id in project.committer_ids
                              if com_id not in user_ids]
      project.contributor_ids = [con_id for con_id in project.contributor_ids
                                 if con_id not in user_ids]


class ConfigService(object):
  """Fake version of ConfigService that just works in-RAM."""

  def __init__(self, user_id=None):
    self.project_configs = {}
    self.next_field_id = 123
    self.next_component_id = 345
    self.next_template_id = 23
    self.expunged_configs = []
    self.expunged_users_in_configs = []
    self.component_ids_to_templates = {}
    self.label_to_id = {}
    self.id_to_label = {}
    self.strict = False  # Set true to raise more exceptions like real class.

  def TestAddLabelsDict(self, label_to_id):
    self.label_to_id = label_to_id
    self.id_to_label = {
        label_id: label
        for label, label_id in list(self.label_to_id.items())}

  def ExpungeConfig(self, _cnxn, project_id):
    self.expunged_configs.append(project_id)

  def ExpungeUsersInConfigs(self, _cnxn, user_ids, limit=None):
    self.expunged_users_in_configs.extend(user_ids)

  def GetLabelDefRows(self, cnxn, project_id, use_cache=True):
    """This always returns empty results.  Mock it to test other cases."""
    return []

  def GetLabelDefRowsAnyProject(self, cnxn, where=None):
    """This always returns empty results.  Mock it to test other cases."""
    return []

  def LookupLabel(self, cnxn, project_id, label_id):
    if label_id in self.id_to_label:
      return self.id_to_label[label_id]
    if label_id == 999:
      return None
    return 'label_%d_%d' % (project_id, label_id)

  def LookupLabelID(self, cnxn, project_id, label, autocreate=True):
    if label in self.label_to_id:
      return self.label_to_id[label]
    return 1

  def LookupLabelIDs(self, cnxn, project_id, labels, autocreate=False):
    return [idx for idx, _label in enumerate(labels)]

  def LookupIDsOfLabelsMatching(self, cnxn, project_id, regex):
    return [1, 2, 3]

  def LookupStatus(self, cnxn, project_id, status_id):
    return 'status_%d_%d' % (project_id, status_id)

  def LookupStatusID(self, cnxn, project_id, status, autocreate=True):
    if status:
      return 1
    else:
      return 0

  def LookupStatusIDs(self, cnxn, project_id, statuses):
    return [idx for idx, _status in enumerate(statuses)]

  def LookupClosedStatusIDs(self, cnxn, project_id):
    return [7, 8, 9]

  def StoreConfig(self, _cnxn, config):
    self.project_configs[config.project_id] = config

  def GetProjectConfig(self, _cnxn, project_id, use_cache=True):
    if project_id in self.project_configs:
      return self.project_configs[project_id]
    elif self.strict:
      raise exceptions.NoSuchProjectException()
    else:
      return tracker_bizobj.MakeDefaultProjectIssueConfig(project_id)

  def GetProjectConfigs(self, _cnxn, project_ids, use_cache=True):
    config_dict = {}
    for project_id in project_ids:
      if project_id in self.project_configs:
        config_dict[project_id] = self.project_configs[project_id]
      elif not self.strict:
        config_dict[project_id] = tracker_bizobj.MakeDefaultProjectIssueConfig(
            project_id)
    return config_dict

  def UpdateConfig(
      self, cnxn, project, well_known_statuses=None,
      statuses_offer_merge=None, well_known_labels=None,
      excl_label_prefixes=None, default_template_for_developers=None,
      default_template_for_users=None, list_prefs=None, restrict_to_known=None,
      approval_defs=None):
    project_id = project.project_id
    project_config = self.GetProjectConfig(cnxn, project_id, use_cache=False)

    if well_known_statuses is not None:
      tracker_bizobj.SetConfigStatuses(project_config, well_known_statuses)

    if statuses_offer_merge is not None:
      project_config.statuses_offer_merge = statuses_offer_merge

    if well_known_labels is not None:
      tracker_bizobj.SetConfigLabels(project_config, well_known_labels)

    if excl_label_prefixes is not None:
      project_config.exclusive_label_prefixes = excl_label_prefixes

    if approval_defs is not None:
      tracker_bizobj.SetConfigApprovals(project_config, approval_defs)

    if default_template_for_developers is not None:
      project_config.default_template_for_developers = (
          default_template_for_developers)
    if default_template_for_users is not None:
      project_config.default_template_for_users = default_template_for_users

    if list_prefs:
      default_col_spec, default_sort_spec, x_attr, y_attr, m_d_q = list_prefs
      project_config.default_col_spec = default_col_spec
      project_config.default_sort_spec = default_sort_spec
      project_config.default_x_attr = x_attr
      project_config.default_y_attr = y_attr
      project_config.member_default_query = m_d_q

    if restrict_to_known is not None:
      project_config.restrict_to_known = restrict_to_known

    self.StoreConfig(cnxn, project_config)
    return project_config

  def CreateFieldDef(
      self,
      cnxn,
      project_id,
      field_name,
      field_type_str,
      applic_type,
      applic_pred,
      is_required,
      is_niche,
      is_multivalued,
      min_value,
      max_value,
      regex,
      needs_member,
      needs_perm,
      grants_perm,
      notify_on,
      date_action_str,
      docstring,
      admin_ids,
      editor_ids,
      approval_id=None,
      is_phase_field=False,
      is_restricted_field=False):
    config = self.GetProjectConfig(cnxn, project_id)
    field_type = tracker_pb2.FieldTypes(field_type_str)
    field_id = self.next_field_id
    self.next_field_id += 1
    fd = tracker_bizobj.MakeFieldDef(
        field_id, project_id, field_name, field_type, applic_type, applic_pred,
        is_required, is_niche, is_multivalued, min_value, max_value, regex,
        needs_member, needs_perm, grants_perm, notify_on, date_action_str,
        docstring, False, approval_id, is_phase_field, is_restricted_field)
    fd.admin_ids = admin_ids
    fd.editor_ids = editor_ids
    config.field_defs.append(fd)
    self.StoreConfig(cnxn, config)
    return field_id

  def LookupFieldID(self, cnxn, project_id, field):
    config = self.GetProjectConfig(cnxn, project_id)
    for fd in config.field_defs:
      if fd.field_name == field:
        return fd.field_id

    return None

  def SoftDeleteFieldDefs(self, cnxn, project_id, field_ids):
    config = self.GetProjectConfig(cnxn, project_id)
    for fd in config.field_defs:
      if fd.field_id in field_ids:
        fd.is_deleted = True
    self.StoreConfig(cnxn, config)

  def UpdateFieldDef(
      self,
      cnxn,
      project_id,
      field_id,
      field_name=None,
      applicable_type=None,
      applicable_predicate=None,
      is_required=None,
      is_niche=None,
      is_multivalued=None,
      min_value=None,
      max_value=None,
      regex=None,
      needs_member=None,
      needs_perm=None,
      grants_perm=None,
      notify_on=None,
      date_action=None,
      docstring=None,
      admin_ids=None,
      editor_ids=None,
      is_restricted_field=None):
    config = self.GetProjectConfig(cnxn, project_id)
    fd = tracker_bizobj.FindFieldDefByID(field_id, config)
    # pylint: disable=multiple-statements
    if field_name is not None: fd.field_name = field_name
    if applicable_type is not None: fd.applicable_type = applicable_type
    if applicable_predicate is not None:
      fd.applicable_predicate = applicable_predicate
    if is_required is not None: fd.is_required = is_required
    if is_niche is not None: fd.is_niche = is_niche
    if is_multivalued is not None: fd.is_multivalued = is_multivalued
    if min_value is not None: fd.min_value = min_value
    if max_value is not None: fd.max_value = max_value
    if regex is not None: fd.regex = regex
    if date_action is not None:
      fd.date_action = config_svc.DATE_ACTION_ENUM.index(date_action)
    if docstring is not None: fd.docstring = docstring
    if admin_ids is not None: fd.admin_ids = admin_ids
    if editor_ids is not None:
      fd.editor_ids = editor_ids
    if is_restricted_field is not None:
      fd.is_restricted_field = is_restricted_field
    self.StoreConfig(cnxn, config)

  def CreateComponentDef(
      self, cnxn, project_id, path, docstring, deprecated, admin_ids, cc_ids,
      created, creator_id, label_ids):
    config = self.GetProjectConfig(cnxn, project_id)
    cd = tracker_bizobj.MakeComponentDef(
        self.next_component_id, project_id, path, docstring, deprecated,
        admin_ids, cc_ids, created, creator_id, label_ids=label_ids)
    config.component_defs.append(cd)
    self.next_component_id += 1
    self.StoreConfig(cnxn, config)
    return self.next_component_id - 1

  def UpdateComponentDef(
      self, cnxn, project_id, component_id, path=None, docstring=None,
      deprecated=None, admin_ids=None, cc_ids=None, created=None,
      creator_id=None, modified=None, modifier_id=None, label_ids=None):
    config = self.GetProjectConfig(cnxn, project_id)
    cd = tracker_bizobj.FindComponentDefByID(component_id, config)
    if path is not None:
      assert path
      cd.path = path
    # pylint: disable=multiple-statements
    if docstring is not None: cd.docstring = docstring
    if deprecated is not None: cd.deprecated = deprecated
    if admin_ids is not None: cd.admin_ids = admin_ids
    if cc_ids is not None: cd.cc_ids = cc_ids
    if created is not None: cd.created = created
    if creator_id is not None: cd.creator_id = creator_id
    if modified is not None: cd.modified = modified
    if modifier_id is not None: cd.modifier_id = modifier_id
    if label_ids is not None: cd.label_ids = label_ids
    self.StoreConfig(cnxn, config)

  def DeleteComponentDef(self, cnxn, project_id, component_id):
    """Delete the specified component definition."""
    config = self.GetProjectConfig(cnxn, project_id)
    config.component_defs = [
        cd for cd in config.component_defs
        if cd.component_id != component_id]
    self.StoreConfig(cnxn, config)

  def InvalidateMemcache(self, issues, key_prefix=''):
    pass

  def InvalidateMemcacheForEntireProject(self, project_id):
    pass


class IssueService(object):
  """Fake version of IssueService that just works in-RAM."""
  # pylint: disable=unused-argument

  def __init__(self, user_id=None):
    self.user_id = user_id
    # Dictionary {project_id: issue_pb_dict}
    # where issue_pb_dict is a dictionary of the form
    # {local_id: issue_pb}
    self.issues_by_project = {}
    self.issues_by_iid = {}
    # Dictionary {project_id: comment_pb_dict}
    # where comment_pb_dict is a dictionary of the form
    # {local_id: comment_pb_list}
    self.comments_by_project = {}
    self.comments_by_iid = {}
    self.comments_by_cid = {}
    self.attachments_by_id = {}

    # Set of issue IDs for issues that have been indexed by calling
    # IndexIssues().
    self.indexed_issue_iids = set()

    # Set of issue IDs for issues that have been moved by calling MoveIssue().
    self.moved_back_iids = set()

    # Dict of issue IDs mapped to other issue IDs to represent moved issues.
    self.moved_issues = {}

    # Test-only indication that the indexer would have been called
    # by the real DITPersist.
    self.indexer_called = False

    # Test-only sequence of updated and enqueued.
    self.updated_issues = []
    self.enqueued_issues = []  # issue_ids

    # Test-only sequence of expunged issues and projects.
    self.expunged_issues = []
    self.expunged_former_locations = []
    self.expunged_local_ids = []
    self.expunged_users_in_issues = []

    # Test-only indicators that methods were called.
    self.get_all_issues_in_project_called = False
    self.update_issues_called = False
    self.enqueue_issues_called = False
    self.get_issue_acitivity_called = False

    # The next id to return if it is > 0.
    self.next_id = -1

  def UpdateIssues(
      self, cnxn, issues, update_cols=None, just_derived=False,
      commit=True, invalidate=True):
    self.update_issues_called = True
    assert all(issue.assume_stale == False for issue in issues)
    self.updated_issues.extend(issues)

  def GetIssueActivity(
      self, cnxn, num=50, before=None, after=None,
      project_ids=None, user_ids=None, ascending=False):
    self.get_issue_acitivity_called = True
    comments_dict = self.comments_by_cid
    comments = []
    for value in comments_dict.values():
      if project_ids is not None:
        if value.issue_id > 0 and value.issue_id in self.issues_by_iid:
          issue = self.issues_by_iid[value.issue_id]
          if issue.project_id in project_ids:
            comments.append(value)
      elif user_ids is not None:
        if value.user_id in user_ids:
          comments.append(value)
      else:
        comments.append(value)
    return comments

  def EnqueueIssuesForIndexing(self, _cnxn, issue_ids):
    self.enqueue_issues_called = True
    for i in issue_ids:
      if i not in self.enqueued_issues:
        self.enqueued_issues.extend(issues)

  def ExpungeIssues(self, _cnxn, issue_ids):
    self.expunged_issues.extend(issue_ids)

  def ExpungeFormerLocations(self, _cnxn, project_id):
    self.expunged_former_locations.append(project_id)

  def ExpungeLocalIDCounters(self, _cnxn, project_id):
    self.expunged_local_ids.append(project_id)

  def TestAddIssue(self, issue, importer_id=None):
    project_id = issue.project_id
    self.issues_by_project.setdefault(project_id, {})
    self.issues_by_project[project_id][issue.local_id] = issue
    self.issues_by_iid[issue.issue_id] = issue
    if issue.issue_id not in self.enqueued_issues:
      self.enqueued_issues.append(issue.issue_id)
      self.enqueue_issues_called = True

    # Adding a new issue should add the first comment to the issue
    comment = tracker_pb2.IssueComment()
    comment.project_id = issue.project_id
    comment.issue_id = issue.issue_id
    comment.content = issue.summary
    comment.timestamp = issue.opened_timestamp
    comment.is_description = True
    if issue.reporter_id:
      comment.user_id = issue.reporter_id
    if importer_id:
      comment.importer_id = importer_id
    comment.sequence = 0
    self.TestAddComment(comment, issue.local_id)

  def TestAddMovedIssueRef(self, source_project_id, source_local_id,
      target_project_id, target_local_id):
    self.moved_issues[(source_project_id, source_local_id)] = (
        target_project_id, target_local_id)

  def TestAddComment(self, comment, local_id):
    pid = comment.project_id
    if not comment.id:
      comment.id = len(self.comments_by_cid)

    self.comments_by_project.setdefault(pid, {})
    self.comments_by_project[pid].setdefault(local_id, []).append(comment)
    self.comments_by_iid.setdefault(comment.issue_id, []).append(comment)
    self.comments_by_cid[comment.id] = comment

  def TestAddAttachment(self, attachment, comment_id, issue_id):
    if not attachment.attachment_id:
      attachment.attachment_id = len(self.attachments_by_id)

    aid = attachment.attachment_id
    self.attachments_by_id[aid] = attachment, comment_id, issue_id
    comment = self.comments_by_cid[comment_id]
    if attachment not in comment.attachments:
      comment.attachments.extend([attachment])

  def SoftDeleteAttachment(
      self, _cnxn, _issue, comment, attach_id, _user_service, delete=True,
      index_now=False):
    attachment = None
    for attach in comment.attachments:
      if attach.attachment_id == attach_id:
        attachment = attach
    if not attachment:
      return
    attachment.deleted = delete

  def GetAttachmentAndContext(self, _cnxn, attachment_id):
    if attachment_id in self.attachments_by_id:
      attach, comment_id, issue_id = self.attachments_by_id[attachment_id]
      if not attach.deleted:
        return attach, comment_id, issue_id

    raise exceptions.NoSuchAttachmentException()

  def GetComments(
      self, _cnxn, where=None, order_by=None, content_only=False, **kwargs):
    # This is a very limited subset of what the real GetComments() can do.
    cid = kwargs.get('id')

    comment = self.comments_by_cid.get(cid)
    if comment:
      return [comment]
    else:
      return []

  def GetComment(self, cnxn, comment_id):
    """Get the requested comment, or raise an exception."""
    comments = self.GetComments(cnxn, id=comment_id)
    if len(comments) == 1:
      return comments[0]

    raise exceptions.NoSuchCommentException()

  def ResolveIssueRefs(self, cnxn, ref_projects, default_project_name, refs):
    result = []
    misses = []
    for project_name, local_id in refs:
      project = ref_projects.get(project_name or default_project_name)
      if not project or project.state == project_pb2.ProjectState.DELETABLE:
        continue  # ignore any refs to issues in deleted projects
      try:
        issue = self.GetIssueByLocalID(cnxn, project.project_id, local_id)
        result.append(issue.issue_id)
      except exceptions.NoSuchIssueException:
        misses.append((project.project_id, local_id))

    return result, misses

  def LookupIssueRefs(self, cnxn, issue_ids):
    issue_dict = self.GetIssuesDict(cnxn, issue_ids)
    return {
      issue_id: (issue.project_name, issue.local_id)
      for issue_id, issue in issue_dict.items()}

  def GetAllIssuesInProject(
      self, _cnxn, project_id, min_local_id=None, use_cache=True):
    self.get_all_issues_in_project_called = True
    if project_id in self.issues_by_project:
      return list(self.issues_by_project[project_id].values())
    else:
      return []

  def GetIssuesByLocalIDs(
      self, _cnxn, project_id, local_id_list, use_cache=True, shard_id=None):
    results = []
    for local_id in local_id_list:
      if (project_id in self.issues_by_project
          and local_id in self.issues_by_project[project_id]):
        results.append(self.issues_by_project[project_id][local_id])

    return results

  def GetIssueByLocalID(self, _cnxn, project_id, local_id, use_cache=True):
    try:
      return self.issues_by_project[project_id][local_id]
    except KeyError:
      raise exceptions.NoSuchIssueException()

  def GetAnyOnHandIssue(self, issue_ids, start=None, end=None):
    return None  # Treat them all like misses.

  def GetIssue(self, _cnxn, issue_id, use_cache=True):
    if issue_id in self.issues_by_iid:
      return self.issues_by_iid[issue_id]
    else:
      raise exceptions.NoSuchIssueException()

  def GetCurrentLocationOfMovedIssue(self, cnxn, project_id, local_id):
    key = (project_id, local_id)
    if key in self.moved_issues:
      ref = self.moved_issues[key]
      return ref[0], ref[1]
    return None, None

  def GetPreviousLocations(self, cnxn, issue):
    return []

  def GetCommentsByUser(self, cnxn, user_id):
    """Get all comments created by a user"""
    comments = []
    for cid in self.comments_by_cid:
      comment = self.comments_by_cid[cid]
      if comment.user_id == user_id and not comment.is_description:
        comments.append(comment)
    return comments

  def GetCommentsByID(self, cnxn, comment_ids, _sequences, use_cache=True,
      shard_id=None):
    """Return all IssueComment PBs by comment ids."""
    comments = [self.comments_by_cid[cid] for cid in comment_ids]
    return comments

  def GetIssueIDsReportedByUser(self, cnxn, user_id):
    """Get all issues created by a user"""
    ids = []
    for iid in self.issues_by_iid:
      issue = self.issues_by_iid[iid]
      if issue.reporter_id == user_id:
        ids.append(iid)
    return ids

  def LookupIssueIDs(self, _cnxn, project_local_id_pairs):
    hits = []
    misses = []
    for (project_id, local_id) in project_local_id_pairs:
      try:
        issue = self.issues_by_project[project_id][local_id]
        hits.append(issue.issue_id)
      except KeyError:
        misses.append((project_id, local_id))

    return hits, misses

  def LookupIssueID(self, _cnxn, project_id, local_id):
    try:
      issue = self.issues_by_project[project_id][local_id]
    except KeyError:
      raise exceptions.NoSuchIssueException()
    return issue.issue_id

  def GetCommentsForIssue(self, _cnxn, issue_id):
    comments = self.comments_by_iid.get(issue_id, [])
    for idx, c in enumerate(comments):
      c.sequence = idx

    return comments

  def InsertIssue(self, cnxn, issue):
    issue.issue_id = issue.project_id * 1000000 + issue.local_id
    self.issues_by_project.setdefault(issue.project_id, {})
    self.issues_by_project[issue.project_id][issue.local_id] = issue
    self.issues_by_iid[issue.issue_id] = issue
    return issue.issue_id

  def CreateIssue(
      self, cnxn, services, project_id,
      summary, status, owner_id, cc_ids, labels, field_values,
      component_ids, reporter_id, marked_description, blocked_on=None,
      blocking=None, attachments=None, timestamp=None, index_now=False,
      phases=None, approval_values=None, importer_id=None,
      dangling_blocked_on=None, dangling_blocking=None):
    issue = tracker_pb2.Issue()
    issue.project_id = project_id
    if services and services.project:
      project = services.project.GetProject(cnxn, project_id)
      issue.project_name = project.project_name
    issue.summary = summary
    issue.status = status
    if owner_id:
      issue.owner_id = owner_id
    issue.cc_ids.extend(cc_ids)
    issue.labels.extend(labels)
    issue.field_values.extend(field_values)
    issue.component_ids.extend(component_ids)
    issue.reporter_id = reporter_id
    if timestamp:
      issue.opened_timestamp = timestamp

    if blocked_on:
      issue.blocked_on_iids.extend(blocked_on)
      issue.blocked_on_ranks.extend(
          list(range(sys.maxint - 1, sys.maxint - len(blocked_on) - 1, -1)))
    if blocking:
      issue.blocking.extend(blocking)

    if blocking:
      issue.blocking_iids.extend(blocking)

    if dangling_blocked_on is not None:
      issue.dangling_blocked_on_refs = dangling_blocked_on
    if dangling_blocking is not None:
      issue.dangling_blocking_refs = dangling_blocking

    if phases:
      issue.phases = phases

    if approval_values:
      issue.approval_values = approval_values

    issue.local_id = self.AllocateNextLocalID(cnxn, project_id)
    issue.issue_id = project_id * 1000000 + issue.local_id

    self.TestAddIssue(issue, importer_id=importer_id)
    comment = self.comments_by_iid[issue.issue_id][0]
    comment.content = marked_description
    return issue.local_id, comment

  def GetIssueApproval(self, cnxn, issue_id, approval_id, use_cache=True):
    issue = self.GetIssue(cnxn, issue_id, use_cache=use_cache)
    approval = tracker_bizobj.FindApprovalValueByID(
        approval_id, issue.approval_values)
    if approval:
      return issue, approval
    raise exceptions.NoSuchIssueApprovalException()

  def UpdateIssueApprovalStatus(
      self, cnxn, issue_id, approval_id, status, setter_id, set_on,
      commit=True):
    issue = self.GetIssue(cnxn, issue_id)
    for av in issue.approval_values:
      if av.approval_id == approval_id:
        av.status = status
        av.setter_id = setter_id
        av.set_on = set_on
        return
    return

  def UpdateIssueApprovalApprovers(
      self, cnxn, issue_id, approval_id, approver_ids, commit=True):
    issue = self.GetIssue(cnxn, issue_id)
    for av in issue.approval_values:
      if av.approval_id == approval_id:
        av.approver_ids = approver_ids
        return
    return

  def UpdateIssueStructure(
      self, cnxn, config, issue, template, reporter_id, comment_content,
      commit=True, invalidate=True):
    approval_defs_by_id = {ad.approval_id: ad for ad in config.approval_defs}
    issue_avs_by_id = {av.approval_id: av for av in issue.approval_values}

    new_issue_approvals = []

    for template_av in template.approval_values:
      existing_issue_av = issue_avs_by_id.get(template_av.approval_id)
      # Keep approval values as-if fi it exists in issue and template
      if existing_issue_av:
        existing_issue_av.phase_id = template_av.phase_id
        new_issue_approvals.append(existing_issue_av)
      else:
        new_issue_approvals.append(template_av)

      # Update all approval surveys so latest ApprovalDef survey changes
      # appear in the converted issue's approval values.
      ad = approval_defs_by_id.get(template_av.approval_id)
      if ad:
        self.CreateIssueComment(
            cnxn, issue, reporter_id, ad.survey,
            is_description=True, approval_id=ad.approval_id, commit=False)
      else:
        logging.info('ApprovalDef not found for approval %r', template_av)

    template_phase_by_name = {
        phase.name.lower(): phase for phase in template.phases}
    issue_phase_by_id = {phase.phase_id: phase for phase in issue.phases}
    updated_fvs = []
    # Trim issue FieldValues or update FieldValue phase_ids
    for fv in issue.field_values:
      # If a fv's phase has the same name as a template's phase, update
      # the fv's phase_id to that of the template phase's. Otherwise,
      # remove the fv.
      if fv.phase_id:
        issue_phase = issue_phase_by_id.get(fv.phase_id)
        if issue_phase and issue_phase.name:
          template_phase = template_phase_by_name.get(issue_phase.name.lower())
          if template_phase:
            fv.phase_id = template_phase.phase_id
            updated_fvs.append(fv)
      # keep all fvs that do not belong to phases.
      else:
        updated_fvs.append(fv)

    fd_names_by_id = {fd.field_id: fd.field_name for fd in config.field_defs}
    amendment = tracker_bizobj.MakeApprovalStructureAmendment(
        [fd_names_by_id.get(av.approval_id) for av in new_issue_approvals],
        [fd_names_by_id.get(av.approval_id) for av in issue.approval_values])

    issue.approval_values = new_issue_approvals
    issue.phases = template.phases
    issue.field_values = updated_fvs

    return self.CreateIssueComment(
        cnxn, issue, reporter_id, comment_content,
        amendments=[amendment], commit=False)

  def SetUsedLocalID(self, cnxn, project_id):
    self.next_id = self.GetHighestLocalID(cnxn, project_id) + 1

  def AllocateNextLocalID(self, cnxn, project_id):
    return self.GetHighestLocalID(cnxn, project_id) + 1

  def GetHighestLocalID(self, _cnxn, project_id):
    if self.next_id > 0:
      return self.next_id - 1
    else:
      issue_dict = self.issues_by_project.get(project_id, {})
      highest = max([0] + [issue.local_id for issue in issue_dict.values()])
      return highest

  def _MakeIssueComment(
      self, project_id, user_id, content, inbound_message=None,
      amendments=None, attachments=None, kept_attachments=None, timestamp=None,
      is_spam=False, is_description=False, approval_id=None, importer_id=None):
    comment = tracker_pb2.IssueComment()
    comment.project_id = project_id
    comment.user_id = user_id
    comment.content = content or ''
    comment.is_spam = is_spam
    comment.is_description = is_description
    if not timestamp:
      timestamp = int(time.time())
    comment.timestamp = int(timestamp)
    if inbound_message:
      comment.inbound_message = inbound_message
    if amendments:
      comment.amendments.extend(amendments)
    if approval_id:
      comment.approval_id = approval_id
    if importer_id:
      comment.importer_id = importer_id
    return comment

  def CopyIssues(self, cnxn, dest_project, issues, user_service, copier_id):
    created_issues = []
    for target_issue in issues:
      new_issue = tracker_pb2.Issue()
      new_issue.project_id = dest_project.project_id
      new_issue.project_name = dest_project.project_name
      new_issue.summary = target_issue.summary
      new_issue.labels.extend(target_issue.labels)
      new_issue.field_values.extend(target_issue.field_values)
      new_issue.reporter_id = copier_id

      timestamp = int(time.time())
      new_issue.opened_timestamp = timestamp
      new_issue.modified_timestamp = timestamp

      target_comments = self.GetCommentsForIssue(cnxn, target_issue.issue_id)
      initial_summary_comment = target_comments[0]

      # Note that blocking and merge_into are not copied.
      new_issue.blocked_on_iids = target_issue.blocked_on_iids
      new_issue.blocked_on_ranks = target_issue.blocked_on_ranks

      # Create the same summary comment as the target issue.
      comment = self._MakeIssueComment(
          dest_project.project_id, copier_id, initial_summary_comment.content,
          is_description=True)

      new_issue.local_id = self.AllocateNextLocalID(
          cnxn, dest_project.project_id)
      issue_id = self.InsertIssue(cnxn, new_issue)
      comment.issue_id = issue_id
      self.InsertComment(cnxn, comment)
      created_issues.append(new_issue)

    return created_issues

  def MoveIssues(self, cnxn, dest_project, issues, user_service):
    move_to = dest_project.project_id
    self.issues_by_project.setdefault(move_to, {})
    moved_back_iids = set()
    for issue in issues:
      if issue.issue_id in self.moved_back_iids:
        moved_back_iids.add(issue.issue_id)
      self.moved_back_iids.add(issue.issue_id)
      project_id = issue.project_id
      self.issues_by_project[project_id].pop(issue.local_id)
      issue.local_id = self.AllocateNextLocalID(cnxn, move_to)
      self.issues_by_project[move_to][issue.local_id] = issue
      issue.project_id = move_to
      issue.project_name = dest_project.project_name
    return moved_back_iids

  def GetCommentsForIssues(self, _cnxn, issue_ids, content_only=False):
    comments_dict = {}
    for issue_id in issue_ids:
      comments_dict[issue_id] = self.comments_by_iid[issue_id]

    return comments_dict

  def InsertComment(self, cnxn, comment, commit=True):
    issue = self.GetIssue(cnxn, comment.issue_id)
    self.TestAddComment(comment, issue.local_id)

  # pylint: disable=unused-argument
  def DeltaUpdateIssue(
      self, cnxn, services, reporter_id, project_id,
      config, issue, delta, index_now=False, comment=None, attachments=None,
      iids_to_invalidate=None, rules=None, predicate_asts=None,
      is_description=False, timestamp=None, kept_attachments=None,
      importer_id=None, inbound_message=None):
    # Return a bogus amendments list if any of the fields changed
    amendments, _ = tracker_bizobj.ApplyIssueDelta(
        cnxn, self, issue, delta, config)

    if not amendments and (not comment or not comment.strip()):
      return [], None

    comment_pb = self.CreateIssueComment(
        cnxn, issue, reporter_id, comment, attachments=attachments,
        amendments=amendments, is_description=is_description,
        kept_attachments=kept_attachments, importer_id=importer_id,
        inbound_message=inbound_message)

    self.indexer_called = index_now
    return amendments, comment_pb

  def InvalidateIIDs(self, cnxn, iids_to_invalidate):
    pass

  # pylint: disable=unused-argument
  def CreateIssueComment(
      self, _cnxn, issue, user_id, content,
      inbound_message=None, amendments=None, attachments=None,
      kept_attachments=None, timestamp=None, is_spam=False,
      is_description=False, approval_id=None, commit=True,
      importer_id=None):
    # Add a comment to an issue
    comment = tracker_pb2.IssueComment()
    comment.id = len(self.comments_by_cid)
    comment.project_id = issue.project_id
    comment.issue_id = issue.issue_id
    comment.content = content
    comment.user_id = user_id
    if timestamp is not None:
      comment.timestamp = timestamp
    else:
      comment.timestamp = 1234567890
    if amendments:
      comment.amendments.extend(amendments)
    if inbound_message:
      comment.inbound_message = inbound_message
    comment.is_spam = is_spam
    comment.is_description = is_description
    if approval_id:
      comment.approval_id = approval_id

    pid = issue.project_id
    self.comments_by_project.setdefault(pid, {})
    self.comments_by_project[pid].setdefault(issue.local_id, []).append(comment)
    self.comments_by_iid.setdefault(issue.issue_id, []).append(comment)
    self.comments_by_cid[comment.id] = comment

    if attachments:
      for filename, filecontent, mimetype in attachments:
        aid = len(self.attachments_by_id)
        attach = tracker_pb2.Attachment(
            attachment_id=aid,
            filename=filename,
            filesize=len(filecontent),
            mimetype=mimetype,
            gcs_object_id='gcs_object_id(%s)' % filename)
        comment.attachments.append(attach)
        self.attachments_by_id[aid] = attach, pid, comment.id

    if kept_attachments:
      comment.attachments.extend([
          self.attachments_by_id[aid][0]
          for aid in kept_attachments])

    return comment

  def GetOpenAndClosedIssues(self, _cnxn, issue_ids):
    open_issues = []
    closed_issues = []
    for issue_id in issue_ids:
      try:
        issue = self.issues_by_iid[issue_id]
        if issue.status == 'Fixed':
          closed_issues.append(issue)
        else:
          open_issues.append(issue)
      except KeyError:
        continue

    return open_issues, closed_issues

  def GetIssuesDict(
      self, _cnxn, issue_ids, use_cache=True, shard_id=None):
    return {
        iid: self.issues_by_iid[iid]
        for iid in issue_ids
        if iid in self.issues_by_iid}

  def GetIssues(self, _cnxn, issue_ids, use_cache=True, shard_id=None):
    results = [self.issues_by_iid[issue_id] for issue_id in issue_ids
               if issue_id in self.issues_by_iid]

    return results

  def SoftDeleteIssue(
      self, _cnxn, project_id, local_id, deleted, user_service):
    issue = self.issues_by_project[project_id][local_id]
    issue.deleted = deleted

  def SoftDeleteComment(
      self, cnxn, issue, comment, deleted_by_user_id, user_service,
      delete=True, reindex=False, is_spam=False):
    pid = comment.project_id
    # Find the original comment by the sequence number.
    c = None
    by_iid_idx = -1
    for by_iid_idx, c in enumerate(self.comments_by_iid[issue.issue_id]):
      if c.sequence == comment.sequence:
        break
    comment = c
    by_project_idx = (
        self.comments_by_project[pid][issue.local_id].index(comment))
    comment.is_spam = is_spam
    if delete:
      comment.deleted_by = deleted_by_user_id
    else:
      comment.reset('deleted_by')
    self.comments_by_project[pid][issue.local_id][by_project_idx] = comment
    self.comments_by_iid[issue.issue_id][by_iid_idx] = comment
    self.comments_by_cid[comment.id] = comment

  def DeleteComponentReferences(self, _cnxn, component_id):
    for _, issue in self.issues_by_iid.items():
      issue.component_ids = [
          cid for cid in issue.component_ids if cid != component_id]

  def RunIssueQuery(
      self, cnxn, left_joins, where, order_by, shard_id=None, limit=None):
    """This always returns empty results.  Mock it to test other cases."""
    return [], False

  def GetIIDsByLabelIDs(self, cnxn, label_ids, project_id, shard_id):
    """This always returns empty results.  Mock it to test other cases."""
    return []

  def GetIIDsByParticipant(self, cnxn, user_ids, project_ids, shard_id):
    """This always returns empty results.  Mock it to test other cases."""
    return []

  def SortBlockedOn(self, cnxn, issue, blocked_on_iids):
    return blocked_on_iids, [0] * len(blocked_on_iids)

  def ApplyIssueRerank(
      self, cnxn, parent_id, relations_to_change, commit=True, invalidate=True):
    issue = self.GetIssue(cnxn, parent_id)
    relations_dict = dict(
        list(zip(issue.blocked_on_iids, issue.blocked_on_ranks)))
    relations_dict.update(relations_to_change)
    issue.blocked_on_ranks = sorted(issue.blocked_on_ranks, reverse=True)
    issue.blocked_on_iids = sorted(
        issue.blocked_on_iids, key=relations_dict.get, reverse=True)

  def SplitRanks(self, cnxn, parent_id, target_id, open_ids, split_above=False):
    pass

  def ExpungeUsersInIssues(self, cnxn, user_ids_by_email, limit=None):
    user_ids = list(user_ids_by_email.values())
    self.expunged_users_in_issues.extend(user_ids)
    return []


class TemplateService(object):
  """Fake version of TemplateService that just works in-RAM."""

  def __init__(self):
    self.templates_by_id = {}  # template_id: template_pb
    self.templates_by_project_id = {}  # project_id: [template_id]

  def TestAddIssueTemplateDef(
      self, template_id, project_id, name, content="", summary="",
      summary_must_be_edited=False, status='New', members_only=False,
      owner_defaults_to_member=False, component_required=False, owner_id=None,
      labels=None, component_ids=None, admin_ids=None, field_values=None,
      phases=None, approval_values=None):
    template = tracker_bizobj.MakeIssueTemplate(
        name,
        summary,
        status,
        owner_id,
        content,
        labels,
        field_values or [],
        admin_ids or [],
        component_ids,
        summary_must_be_edited=summary_must_be_edited,
        owner_defaults_to_member=owner_defaults_to_member,
        component_required=component_required,
        members_only=members_only,
        phases=phases,
        approval_values=approval_values)
    template.template_id = template_id
    self.templates_by_id[template_id] = template
    if project_id not in self.templates_by_project_id:
      self.templates_by_project_id[project_id] = []
    self.templates_by_project_id[project_id].append(template_id)
    return template

  def GetTemplateById(self, cnxn, template_id):
    return self.templates_by_id.get(template_id)

  def GetTemplatesById(self, cnxn, template_ids):
    return filter(
        lambda template: template.template_id in template_ids,
        self.templates_by_id.values())

  def GetProjectTemplates(self, cnxn, project_id):
    template_ids = self.templates_by_project_id[project_id]
    return self.GetTemplatesById(cnxn, template_ids)

  def ExpungeUsersInTemplates(self, cnxn, user_ids, limit=None):
    for _, template in self.templates_by_id.items():
      template.admin_ids = [user_id for user_id in template.admin_ids
                            if user_id not in user_ids]
      if template.owner_id in user_ids:
        template.owner_id = None
      template.field_values = [fv for fv in template.field_values
                               if fv.user_id in user_ids]

class SpamService(object):
  """Fake version of SpamService that just works in-RAM."""

  def __init__(self, user_id=None):
    self.user_id = user_id
    self.reports_by_issue_id = collections.defaultdict(list)
    self.comment_reports_by_issue_id = collections.defaultdict(dict)
    self.manual_verdicts_by_issue_id = collections.defaultdict(dict)
    self.manual_verdicts_by_comment_id = collections.defaultdict(dict)
    self.expunged_users_in_spam = []

  def LookupIssuesFlaggers(self, cnxn, issue_ids):
    return {
        issue_id: (self.reports_by_issue_id.get(issue_id, []),
                   self.comment_reports_by_issue_id.get(issue_id, {}))
        for issue_id in issue_ids}

  def LookupIssueFlaggers(self, cnxn, issue_id):
    return self.LookupIssuesFlaggers(cnxn, [issue_id])[issue_id]

  def FlagIssues(self, cnxn, issue_service, issues, user_id, flagged_spam):
    for issue in issues:
      if flagged_spam:
        self.reports_by_issue_id[issue.issue_id].append(user_id)
      else:
        self.reports_by_issue_id[issue.issue_id].remove(user_id)

  def FlagComment(self, cnxn, issue_id, comment_id, reported_user_id, user_id,
                  flagged_spam):
    if not comment_id in self.comment_reports_by_issue_id[issue_id]:
      self.comment_reports_by_issue_id[issue_id][comment_id] = []
    if flagged_spam:
      self.comment_reports_by_issue_id[issue_id][comment_id].append(user_id)
    else:
      self.comment_reports_by_issue_id[issue_id][comment_id].remove(user_id)

  def RecordManualIssueVerdicts(
      self, cnxn, issue_service, issues, user_id, is_spam):
    for issue in issues:
      self.manual_verdicts_by_issue_id[issue.issue_id][user_id] = is_spam

  def RecordManualCommentVerdict(
      self, cnxn, issue_service, user_service, comment_id,
      user_id, is_spam):
    self.manual_verdicts_by_comment_id[comment_id][user_id] = is_spam

  def RecordClassifierIssueVerdict(self, cnxn, issue, is_spam, confidence,
        failed_open):
    return

  def RecordClassifierCommentVerdict(self, cnxn, issue, is_spam, confidence,
        failed_open):
    return

  def ClassifyComment(self, comment, commenter):
    return {'outputLabel': 'ham',
            'outputMulti': [{'label': 'ham', 'score': '1.0'}],
            'failed_open': False}

  def ClassifyIssue(self, issue, firstComment, reporter):
    return {'outputLabel': 'ham',
            'outputMulti': [{'label': 'ham', 'score': '1.0'}],
            'failed_open': False}

  def ExpungeUsersInSpam(self, cnxn, user_ids):
    self.expunged_users_in_spam.extend(user_ids)


class FeaturesService(object):
  """A fake implementation of FeaturesService."""
  def __init__(self):
    # Test-only sequence of expunged projects and users.
    self.expunged_saved_queries = []
    self.expunged_users_in_saved_queries = []
    self.expunged_filter_rules = []
    self.expunged_users_in_filter_rules = []
    self.expunged_quick_edit = []
    self.expunged_users_in_quick_edits = []
    self.expunged_hotlist_ids = []
    self.expunged_users_in_hotlists = []

    # filter rules, project_id => filterrule_pb
    self.test_rules = collections.defaultdict(list)

    # TODO(crbug/monorail/7104): Confirm that these are never reassigned
    # to empty {} and then change these to collections.defaultdicts instead.
    # hotlists
    self.test_hotlists = {}  # (hotlist_name, owner_id) => hotlist_pb
    self.hotlists_by_id = {}
    self.hotlists_id_by_user = {}  # user_id => [hotlist_id, hotlist_id, ...]
    self.hotlists_id_by_issue = {}  # issue_id => [hotlist_id, hotlist_id, ...]

    # saved queries
    self.saved_queries = []  # [(pid, uid, sq), ...]

  def TestAddFilterRule(
      self, project_id, predicate, default_status=None, default_owner_id=None,
      add_cc_ids=None, add_labels=None, add_notify=None, warning=None,
      error=None):
    rule = filterrules_helpers.MakeRule(
        predicate, default_status=default_status,
        default_owner_id=default_owner_id, add_cc_ids=add_cc_ids,
        add_labels=add_labels, add_notify=add_notify, warning=warning,
        error=error)
    self.test_rules[project_id].append(rule)
    return rule

  def TestAddHotlist(self, name, summary='', owner_ids=None, editor_ids=None,
                     follower_ids=None, description=None, hotlist_id=None,
                     is_private=False, hotlist_item_fields=None,
                     default_col_spec=None):
    """Add a hotlist to the fake FeaturesService object.

    Args:
      name: the name of the hotlist. Will replace any existing hotlist under
        the same name.
      summary: the summary string of the hotlist
      owner_ids: List of user ids for the hotlist owners
      editor_ids: List of user ids for the hotlist editors
      follower_ids: List of user ids for the hotlist followers
      description: The description string for this hotlist
      hotlist_id: A unique integer identifier for the created hotlist
      is_private: A boolean indicating whether the hotlist is private/public
      hotlist_item_fields: a list of tuples ->
        [(issue_id, rank, adder_id, date_added, note),...]
      default_col_spec: string of default columns for the hotlist.

    Returns:
      A populated hotlist PB.
    """
    hotlist_pb = features_pb2.Hotlist()
    hotlist_pb.hotlist_id = hotlist_id or hash(name) % 100000
    hotlist_pb.name = name
    hotlist_pb.summary = summary
    hotlist_pb.is_private = is_private
    hotlist_pb.default_col_spec = default_col_spec
    if description is not None:
      hotlist_pb.description = description

    self.TestAddHotlistMembers(owner_ids, hotlist_pb, OWNER_ROLE)
    self.TestAddHotlistMembers(follower_ids, hotlist_pb, FOLLOWER_ROLE)
    self.TestAddHotlistMembers(editor_ids, hotlist_pb, EDITOR_ROLE)

    if hotlist_item_fields is not None:
      for(issue_id, rank, adder_id, date, note) in hotlist_item_fields:
        hotlist_pb.items.append(
            features_pb2.Hotlist.HotlistItem(
                issue_id=issue_id, rank=rank, adder_id=adder_id,
                date_added=date, note=note))
        try:
          self.hotlists_id_by_issue[issue_id].append(hotlist_pb.hotlist_id)
        except KeyError:
          self.hotlists_id_by_issue[issue_id] = [hotlist_pb.hotlist_id]

    owner_id = None
    if hotlist_pb.owner_ids:
      owner_id = hotlist_pb.owner_ids[0]
    self.test_hotlists[(name, owner_id)] = hotlist_pb
    self.hotlists_by_id[hotlist_pb.hotlist_id] = hotlist_pb
    return hotlist_pb

  def TestAddHotlistMembers(self, user_id_list, hotlist_pb, role):
    if user_id_list is not None:
      for user_id in user_id_list:
        if role == OWNER_ROLE:
          hotlist_pb.owner_ids.append(user_id)
        elif role == EDITOR_ROLE:
          hotlist_pb.editor_ids.append(user_id)
        elif role == FOLLOWER_ROLE:
          hotlist_pb.follower_ids.append(user_id)
        try:
          self.hotlists_id_by_user[user_id].append(hotlist_pb.hotlist_id)
        except KeyError:
          self.hotlists_id_by_user[user_id] = [hotlist_pb.hotlist_id]

  def CheckHotlistName(self, cnxn, name, owner_ids):
    if not framework_bizobj.IsValidHotlistName(name):
      raise exceptions.InputException(
          '%s is not a valid name for a Hotlist' % name)
    if self.LookupHotlistIDs(cnxn, [name], owner_ids):
      raise features_svc.HotlistAlreadyExists()

  def CreateHotlist(
      self, _cnxn, hotlist_name, summary, description, owner_ids, editor_ids,
      issue_ids=None, is_private=None, default_col_spec=None, ts=None):
    """Create and store a Hotlist with the given attributes."""
    if not framework_bizobj.IsValidHotlistName(hotlist_name):
      raise exceptions.InputException()
    if not owner_ids:  # Should never happen.
      raise features_svc.UnownedHotlistException()
    if (hotlist_name, owner_ids[0]) in self.test_hotlists:
      raise features_svc.HotlistAlreadyExists()
    hotlist_item_fields = [
        (issue_id, rank*100, owner_ids[0] or None, ts, '') for
        rank, issue_id in enumerate(issue_ids or [])]
    return self.TestAddHotlist(hotlist_name, summary=summary,
                               owner_ids=owner_ids, editor_ids=editor_ids,
                               description=description, is_private=is_private,
                               hotlist_item_fields=hotlist_item_fields,
                               default_col_spec=default_col_spec)

  def UpdateHotlist(
      self, cnxn, hotlist_id, name=None, summary=None, description=None,
      is_private=None, default_col_spec=None, owner_id=None,
      add_editor_ids=None):
    hotlist = self.hotlists_by_id.get(hotlist_id)
    if not hotlist:
      raise features_svc.NoSuchHotlistException(
          'Hotlist "%s" not found!' % hotlist_id)

    if owner_id:
      old_owner_id = hotlist.owner_ids[0]
      self.test_hotlists.pop((hotlist.name, old_owner_id), None)
      self.test_hotlists[(hotlist.name, owner_id)] = hotlist

    if add_editor_ids:
      for editor_id in add_editor_ids:
        self.hotlists_id_by_user.get(editor_id, []).append(hotlist_id)

    if name is not None:
      hotlist.name = name
    if summary is not None:
      hotlist.summary = summary
    if description is not None:
      hotlist.description = description
    if is_private is not None:
      hotlist.is_private = is_private
    if default_col_spec is not None:
      hotlist.default_col_spec = default_col_spec
    if owner_id is not None:
      hotlist.owner_ids = [owner_id]
    if add_editor_ids:
      hotlist.editor_ids.extend(add_editor_ids)

  def RemoveHotlistEditors(self, cnxn, hotlist_id, remove_editor_ids):
    hotlist = self.hotlists_by_id.get(hotlist_id)
    if not hotlist:
      raise features_svc.NoSuchHotlistException(
          'Hotlist "%s" not found!' % hotlist_id)
    for editor_id in remove_editor_ids:
      hotlist.editor_ids.remove(editor_id)
      self.hotlists_id_by_user[editor_id].remove(hotlist_id)

  def AddIssuesToHotlists(self, cnxn, hotlist_ids, added_tuples, issue_svc,
                          chart_svc, commit=True):
    for hotlist_id in hotlist_ids:
      self.UpdateHotlistItems(cnxn, hotlist_id, [], added_tuples, commit=commit)

  def RemoveIssuesFromHotlists(self, cnxn, hotlist_ids, issue_ids, issue_svc,
                               chart_svc, commit=True):
    for hotlist_id in hotlist_ids:
      self.UpdateHotlistItems(cnxn, hotlist_id, issue_ids, [], commit=commit)

  def UpdateHotlistIssues(
      self,
      cnxn,
      hotlist_id,
      updated_items,
      remove_issue_ids,
      issue_svc,
      chart_svc,
      commit=True):
    if not updated_items and not remove_issue_ids:
      raise exceptions.InputException('No changes to make')

    hotlist = self.hotlists_by_id.get(hotlist_id)
    if not hotlist:
      raise NoSuchHotlistException()

    updated_ids = [item.issue_id for item in updated_items]
    items = [
        item for item in hotlist.items
        if item.issue_id not in updated_ids + remove_issue_ids
    ]
    hotlist.items = sorted(updated_items + items, key=lambda item: item.rank)

    # Remove all removed and updated issues.
    for issue_id in remove_issue_ids + updated_ids:
      try:
        self.hotlists_id_by_issue[issue_id].remove(hotlist_id)
      except (ValueError, KeyError):
        pass
    # Add all new or updated issues.
    for item in updated_items:
      self.hotlists_id_by_issue.setdefault(item.issue_id, []).append(hotlist_id)

  def UpdateHotlistItems(
      self, cnxn, hotlist_id, remove, added_issue_tuples, commit=True):
    hotlist = self.hotlists_by_id.get(hotlist_id)
    if not hotlist:
      raise features_svc.NoSuchHotlistException(
          'Hotlist "%s" not found!' % hotlist_id)
    current_issues_ids = {
        item.issue_id for item in hotlist.items}
    items = [
        item for item in hotlist.items if
        item.issue_id not in remove]

    if hotlist.items:
      items_sorted = sorted(hotlist.items, key=lambda item: item.rank)
      rank_base = items_sorted[-1].rank + 10
    else:
      rank_base = 1

    new_hotlist_items = [
        features_pb2.MakeHotlistItem(
            issue_id, rank+rank_base*10, adder_id, date, note)
        for rank, (issue_id, adder_id, date, note) in
        enumerate(added_issue_tuples)
        if issue_id not in current_issues_ids]
    items.extend(new_hotlist_items)
    hotlist.items = items

    for issue_id in remove:
      try:
        self.hotlists_id_by_issue[issue_id].remove(hotlist_id)
      except ValueError:
        pass
    for item in new_hotlist_items:
      try:
        self.hotlists_id_by_issue[item.issue_id].append(hotlist_id)
      except KeyError:
        self.hotlists_id_by_issue[item.issue_id] = [hotlist_id]

  def UpdateHotlistItemsFields(
      self, cnxn, hotlist_id, new_ranks=None, new_notes=None, commit=True):
    hotlist = self.hotlists_by_id.get(hotlist_id)
    if not hotlist:
      raise features_svc.NoSuchHotlistException(
          'Hotlist "%s" not found!' % hotlist_id)
    if new_ranks is None:
      new_ranks = {}
    if new_notes is None:
      new_notes = {}
    for hotlist_item in hotlist.items:
      if hotlist_item.issue_id in new_ranks:
        hotlist_item.rank = new_ranks[hotlist_item.issue_id]
      if hotlist_item.issue_id in new_notes:
        hotlist_item.note = new_notes[hotlist_item.issue_id]

    hotlist.items.sort(key=lambda item: item.rank)

  def TransferHotlistOwnership(
      self, cnxn, hotlist, new_owner_id, remain_editor, commit=True):
    """Transfers ownership of a hotlist to a new owner."""
    new_editor_ids = hotlist.editor_ids
    if remain_editor:
      new_editor_ids.extend(hotlist.owner_ids)
    if new_owner_id in new_editor_ids:
      new_editor_ids.remove(new_owner_id)
    new_follower_ids = hotlist.follower_ids
    if new_owner_id in new_follower_ids:
      new_follower_ids.remove(new_owner_id)
    self.UpdateHotlistRoles(
        cnxn, hotlist.hotlist_id, [new_owner_id], new_editor_ids,
        new_follower_ids, commit=commit)

  def LookupUserHotlists(self, cnxn, user_ids):
    """Return dict of {user_id: [hotlist_id, hotlist_id...]}."""
    users_hotlists_dict = {
        user_id: self.hotlists_id_by_user.get(user_id, [])
        for user_id in user_ids
    }
    return users_hotlists_dict

  def LookupIssueHotlists(self, cnxn, issue_ids):
    """Return dict of {issue_id: [hotlist_id, hotlist_id...]}."""
    issues_hotlists_dict = {
        issue_id: self.hotlists_id_by_issue[issue_id]
        for issue_id in issue_ids
        if issue_id in self.hotlists_id_by_issue}
    return issues_hotlists_dict

  def LookupHotlistIDs(self, cnxn, hotlist_names, owner_ids):
    id_dict = {}
    for name in hotlist_names:
      for owner_id in owner_ids:
        hotlist = self.test_hotlists.get((name, owner_id))
        if hotlist:
          if not hotlist.owner_ids:  # Should never happen.
            logging.warn('Unowned Hotlist: id:%r, name:%r',
                         hotlist.hotlist_id, hotlist.name)
            continue
          id_dict[(name.lower(), owner_id)] = hotlist.hotlist_id
    return id_dict

  def GetHotlists(self, cnxn, hotlist_ids, use_cache=True):
    """Returns dict of {hotlist_id: hotlist PB}."""
    result = {}
    for hotlist_id in hotlist_ids:
      hotlist = self.hotlists_by_id.get(hotlist_id)
      if hotlist:
        result[hotlist_id] = hotlist
      else:
        raise features_svc.NoSuchHotlistException()
    return result

  def GetHotlistsByUserID(self, cnxn, user_id, use_cache=True):
    """Get a list of hotlist PBs for a given user."""
    hotlist_id_dict = self.LookupUserHotlists(cnxn, [user_id])
    hotlists = self.GetHotlists(cnxn, hotlist_id_dict.get(
        user_id, []), use_cache=use_cache)
    return list(hotlists.values())

  def GetHotlistsByIssueID(self, cnxn, issue_id, use_cache=True):
    """Get a list of hotlist PBs for a given issue."""
    hotlist_id_dict = self.LookupIssueHotlists(cnxn, [issue_id])
    hotlists = self.GetHotlists(cnxn, hotlist_id_dict.get(
        issue_id, []), use_cache=use_cache)
    return list(hotlists.values())

  def GetHotlist(self, cnxn, hotlist_id, use_cache=True):
    """Return hotlist PB."""
    hotlist_id_dict = self.GetHotlists(cnxn, [hotlist_id], use_cache=use_cache)
    return hotlist_id_dict.get(hotlist_id)

  def GetHotlistsByID(self, cnxn, hotlist_ids, use_cache=True):
    hotlists_dict = {}
    missed_ids = []
    for hotlist_id in hotlist_ids:
      hotlist = self.hotlists_by_id.get(hotlist_id)
      if hotlist:
        hotlists_dict[hotlist_id] = hotlist
      else:
        missed_ids.append(hotlist_id)
    return hotlists_dict, missed_ids

  def GetHotlistByID(self, cnxn, hotlist_id, use_cache=True):
    hotlists_dict, _ = self.GetHotlistsByID(
        cnxn, [hotlist_id], use_cache=use_cache)
    return hotlists_dict[hotlist_id]

  def UpdateHotlistRoles(
      self, cnxn, hotlist_id, owner_ids, editor_ids, follower_ids, commit=True):
    hotlist = self.hotlists_by_id.get(hotlist_id)
    if not hotlist:
      raise features_svc.NoSuchHotlistException(
          'Hotlist "%s" not found!' % hotlist_id)

    # Remove hotlist_ids to clear old roles
    for user_id in (hotlist.owner_ids + hotlist.editor_ids +
                    hotlist.follower_ids):
      if hotlist_id in self.hotlists_id_by_user[user_id]:
        self.hotlists_id_by_user[user_id].remove(hotlist_id)
    old_owner_id = None
    if hotlist.owner_ids:
      old_owner_id = hotlist.owner_ids[0]
    self.test_hotlists.pop((hotlist.name, old_owner_id), None)

    hotlist.owner_ids = owner_ids
    hotlist.editor_ids = editor_ids
    hotlist.follower_ids = follower_ids

    # Add new hotlist roles
    for user_id in owner_ids+editor_ids+follower_ids:
      try:
        if hotlist_id not in self.hotlists_id_by_user[user_id]:
          self.hotlists_id_by_user[user_id].append(hotlist_id)
      except KeyError:
        self.hotlists_id_by_user[user_id] = [hotlist_id]
    new_owner_id = None
    if owner_ids:
      new_owner_id = owner_ids[0]
    self.test_hotlists[(hotlist.name, new_owner_id)] = hotlist

  def DeleteHotlist(self, cnxn, hotlist_id, commit=True):
    hotlist = self.hotlists_by_id.pop(hotlist_id, None)
    if hotlist is not None:
      self.test_hotlists.pop((hotlist.name, hotlist.owner_ids[0]), None)
      user_ids = hotlist.owner_ids+hotlist.editor_ids+hotlist.follower_ids
      for user_id in user_ids:
        try:
          self.hotlists_id_by_user[user_id].remove(hotlist_id)
        except (ValueError, KeyError):
          pass
      for item in hotlist.items:
        try:
          self.hotlists_id_by_issue[item.issue_id].remove(hotlist_id)
        except (ValueError, KeyError):
          pass
      for owner_id in hotlist.owner_ids:
        self.test_hotlists.pop((hotlist.name, owner_id), None)

  def ExpungeHotlists(
      self, cnxn, hotlist_ids, star_svc, user_svc, chart_svc, commit=True):
    self.expunged_hotlist_ids.extend(hotlist_ids)
    for hotlist_id in hotlist_ids:
      self.DeleteHotlist(cnxn, hotlist_id)

  def ExpungeUsersInHotlists(
      self, cnxn, user_ids, star_svc, user_svc, chart_svc):
    self.expunged_users_in_hotlists.extend(user_ids)

  # end of Hotlist functions

  def GetRecentCommands(self, cnxn, user_id, project_id):
    return [], []

  def ExpungeSavedQueriesExecuteInProject(self, _cnxn, project_id):
    self.expunged_saved_queries.append(project_id)

  def ExpungeSavedQueriesByUsers(self, cnxn, user_ids, limit=None):
    self.expunged_users_in_saved_queries.extend(user_ids)

  def ExpungeFilterRules(self, _cnxn, project_id):
    self.expunged_filter_rules.append(project_id)

  def ExpungeFilterRulesByUser(self, cnxn, user_ids_by_email):
    emails = user_ids_by_email.keys()
    user_ids = user_ids_by_email.values()
    project_rules_dict = collections.defaultdict(list)
    for project_id, rules in self.test_rules.iteritems():
      for rule in rules:
        if rule.default_owner_id in user_ids:
          project_rules_dict[project_id].append(rule)
          continue
        if any(cc_id in user_ids for cc_id in rule.add_cc_ids):
          project_rules_dict[project_id].append(rule)
          continue
        if any(addr in emails for addr in rule.add_notify_addrs):
          project_rules_dict[project_id].append(rule)
          continue
        if any((email in rule.predicate) for email in emails):
          project_rules_dict[project_id].append(rule)
          continue
      self.test_rules[project_id] = [
          rule for rule in rules
          if rule not in project_rules_dict[project_id]]
    return project_rules_dict

  def ExpungeQuickEditHistory(self, _cnxn, project_id):
    self.expunged_quick_edit.append(project_id)

  def ExpungeQuickEditsByUsers(self, cnxn, user_ids, limit=None):
    self.expunged_users_in_quick_edits.extend(user_ids)

  def GetFilterRules(self, cnxn, project_id):
    return []

  def GetCannedQueriesByProjectID(self, cnxn, project_id):
    return [sq for (pid, _, sq) in self.saved_queries if pid == project_id]

  def GetSavedQueriesByUserID(self, cnxn, user_id):
    return [sq for (_, uid, sq) in self.saved_queries if uid == user_id]

  def UpdateCannedQueries(self, cnxn, project_id, canned_queries):
    self.saved_queries.extend(
      [(project_id, None, cq) for cq in canned_queries])

  def UpdateUserSavedQueries(self, cnxn, user_id, saved_queries):
    self.saved_queries = [
      (pid, uid, sq) for (pid, uid, sq) in self.saved_queries
      if uid != user_id]
    for sq in saved_queries:
      if sq.executes_in_project_ids:
        self.saved_queries.extend(
          [(eipid, user_id, sq) for eipid in sq.executes_in_project_ids])
      else:
        self.saved_queries.append((None, user_id, sq))

  def GetSubscriptionsInProjects(self, cnxn, project_ids):
    sq_by_uid = {}
    for pid, uid, sq in self.saved_queries:
      if pid in project_ids:
        if uid in sq_by_uid:
          sq_by_uid[uid].append(sq)
        else:
          sq_by_uid[uid] = [sq]

    return sq_by_uid

  def GetSavedQuery(self, cnxn, query_id):
    return tracker_pb2.SavedQuery()


class PostData(object):
  """A dictionary-like object that also implements getall()."""

  def __init__(self, *args, **kwargs):
    self.dictionary = dict(*args, **kwargs)

  def getall(self, key):
    """Return all values, assume that the value at key is already a list."""
    return self.dictionary.get(key, [])

  def get(self, key, default=None):
    """Return first value, assume that the value at key is already a list."""
    return self.dictionary.get(key, [default])[0]

  def __getitem__(self, key):
    """Return first value, assume that the value at key is already a list."""
    return self.dictionary[key][0]

  def __contains__(self, key):
    return key in self.dictionary

  def keys(self):
    """Return the keys in the POST data."""
    return list(self.dictionary.keys())


class FakeFile:
  def __init__(self, data=None):
    self.data = data

  def read(self):
    return self.data

  def write(self, content):
    return

  def __enter__(self):
    return self

  def __exit__(self, __1, __2, __3):
    return None


def gcs_open(filename, mode):
  return FakeFile(filename)
