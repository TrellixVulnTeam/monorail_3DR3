# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import re
import urllib

from common.findit_http_client import FinditHttpClient
from infra_api_clients.codereview import cl_info
from infra_api_clients.codereview import codereview
from libs import time_util


class Gerrit(codereview.CodeReview):
  """Stub for implementing Gerrit support."""
  HTTP_CLIENT = FinditHttpClient(follow_redirects=False)

  def __init__(self, host, settings=None):
    super(Gerrit, self).__init__(host)
    settings = settings or {}
    self.commit_bot_emails = settings.get('commit_bot_emails',
                                          ['commit-bot@chromium.org'])

  def _HandleResponse(self, status_code, content, _response_headers):
    if status_code != 200:
      if status_code == 409:
        # Submit rule failed. Content should tell which rule failed like:
        # Change 677630: needs Code-Review
        logging.error('Committing revert failed: %s', content)
      return None
    # Remove XSSI magic prefix
    if content.startswith(')]}\''):
      content = content[4:]
    return json.loads(content)

  def _AuthenticatedRequest(self,
                            path_parts,
                            payload=None,
                            method='GET',
                            headers=None):
    # Prepend /a/ to make the request authenticated.
    if path_parts[0] != 'a':
      path_parts = ['a'] + list(path_parts)
    path_parts = [urllib.quote(p, safe='~') for p in path_parts]
    url = 'https://%s/%s' % (self._server_hostname, '/'.join(path_parts))
    headers = headers or {}
    # This header tells gerrit to send compact (non-pretty) JSON which is
    # more efficient and encouraged for automated tools.
    headers['Accept'] = 'application/json'
    if method == 'GET':
      return self.HTTP_CLIENT.Get(url, params=payload, headers=headers)
    elif method == 'POST':
      return self.HTTP_CLIENT.Post(url, data=payload, headers=headers)
    raise NotImplementedError()  # pragma: no cover

  def _GetBugLine(self, description, bug_id=None):
    bug_line_pattern = re.compile('^\s*((BUGS?|ISSUE)\s*[=:]\s*.*)$',
                                  re.IGNORECASE)
    for line in reversed(description.splitlines()):
      if bug_line_pattern.match(line):
        if bug_id is not None:
          return line.strip() + ', {}\n'.format(bug_id)
        return line.strip() + '\n'

    # Nothing was found, return the bug_id if it was specified else an empty
    # string.
    if bug_id is not None:
      return 'Bug: {}\n'.format(bug_id)
    return ''

  def _GetCQTryBotLine(self, description):
    cq_trybot_line_pattern = re.compile(
        '^\s*(CQ_INCLUDE_TRYBOTS=.*|Cq-Include-Trybots:.*)$', re.IGNORECASE)
    for line in reversed(description.splitlines()):
      if cq_trybot_line_pattern.match(line):
        return line.strip() + '\n'
    return ''

  def _GetRevisedCLDescription(self, description):
    """Adds '> ' in front of the original cl description."""
    return ''.join(['> ' + l for l in description.splitlines(True)])

  def _GetCQFlagsOrExplanation(self, commit_timestamp):
    delta = time_util.GetUTCNow() - commit_timestamp
    if delta.days > 1:
      return (
          '# Not skipping CQ checks because original CL landed > 1 day ago.\n\n'
      )
    return 'No-Presubmit: true\nNo-Tree-Checks: true\nNo-Try: true\n'

  def _GenerateRevertCLDescription(self, change_id, revert_reason, bug_id=None):
    original_cl_info = self.GetClDetails(change_id)
    original_cl_subject = original_cl_info.subject
    original_cl_change_id = original_cl_info.change_id
    original_cl_description = original_cl_info.description
    original_cl_commit_revision = original_cl_info.commits[0].revision
    original_cl_commit_timestamp = original_cl_info.commits[0].timestamp

    revert_cl_description = (
        'Revert "%s"\n\n' % (original_cl_subject
                             if original_cl_subject else original_cl_change_id))
    revert_cl_description += 'This reverts commit %s.\n\n' % (
        original_cl_commit_revision)
    revert_cl_description += 'Reason for revert:\n%s\n\n' % revert_reason
    revert_cl_description += 'Original change\'s description:\n%s\n\n' % (
        self._GetRevisedCLDescription(original_cl_description))
    revert_cl_description += self._GetCQFlagsOrExplanation(
        original_cl_commit_timestamp)

    # Add the bug id from the culprit change, and append a custom bug id if
    # it is provided.
    revert_cl_description += self._GetBugLine(
        original_cl_description, bug_id=bug_id)

    revert_cl_description += self._GetCQTryBotLine(original_cl_description)
    # Strips the break lines at the end of description to make sure no empty
    # lines between footers in this generated description and added footers by
    # git cl.
    revert_cl_description = revert_cl_description.rstrip()
    return revert_cl_description

  def _Get(self, path_parts, params=None, headers=None):
    """Makes a simple get to Gerrit's API and parses the json output."""
    return self._HandleResponse(*self._AuthenticatedRequest(
        path_parts, payload=params, headers=headers))

  def _Post(self, path_parts, body=None, headers=None):
    headers = headers or {}
    if body:  # pragma: no branch
      headers['Content-Type'] = 'application/json'
      body = json.dumps(body)
    return self._HandleResponse(*self._AuthenticatedRequest(
        path_parts, payload=body, method='POST', headers=headers))

  def GetCodeReviewUrl(self, change_id):
    return 'https://%s/q/%s' % (self._server_hostname, change_id)

  def _SetReview(self,
                 change_id,
                 message,
                 should_email=True,
                 reviewers=None,
                 omit_duplicates=True):
    parts = ['changes', change_id, 'revisions', 'current', 'review']
    body = {'message': message}
    if reviewers:
      body['reviewers'] = reviewers
    if not should_email:
      body['notify'] = 'NONE'
    if omit_duplicates:
      body['omit_duplicate_comments'] = True
    result = self._Post(parts, body=body)
    return result

  def PostMessage(self,
                  change_id,
                  message,
                  should_email=True,
                  omit_duplicates=True):
    result = self._SetReview(
        change_id, message, should_email, omit_duplicates=omit_duplicates)
    return result is not None  # A successful post will return an empty dict.

  def CreateRevert(self,
                   reason,
                   change_id,
                   patchset_id=None,
                   footer=None,
                   bug_id=None):
    """Create a revert using Gerrit's Revert Change api.

    Returns:
      A dict containing the response of the Revert Change api, described by:
      https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#revert-change
    """
    parts = ['changes', change_id, 'revert']
    revert_cl_description = self._GenerateRevertCLDescription(
        change_id, reason, bug_id=bug_id)
    body = {'message': revert_cl_description}
    reverting_change = self._Post(parts, body=body)
    if not reverting_change or 'change_id' not in reverting_change:
      return None
    return reverting_change

  def SubmitRevert(self, change_id):
    parts = ['changes', change_id, 'submit']
    return bool(self._Post(parts))

  def AddReviewers(self, change_id, reviewers, message=None):
    new_reviewers = []

    for reviewer in reviewers:
      # reviewer must be an email string.
      if len(reviewer.split('@')) != 2:
        logging.error('Reviewer\'s email is in wrong format: %s', reviewer)
        continue
      new_reviewers.append({'reviewer': reviewer})

    if not new_reviewers:
      # No new reviewers need to be added.
      return True

    response = self._SetReview(change_id, message, reviewers=new_reviewers)
    # The corresponding result of adding each reviewer will be returned in
    # a map of inputs to AddReviewerResults as below:
    # {
    #   'reviewers': {
    #     'jane.roe@example.com': {
    #       'input': 'jane.roe@example.com',
    #       'reviewers': [
    #         {
    #           '_account_id': 1000097,
    #           'name': 'Jane Roe',
    #           'email': 'jane.roe@example.com',
    #                    'approvals': {
    #                                   'Verified': ' 0',
    #                                   'Code-Review': ' 0'
    #                                 },
    #         },
    #       ]
    #     },
    #     'john.doe@example.com': {
    #       'input': 'john.doe@example.com',
    #       'reviewers': []  # This reviewer has been added before.
    #     }
    #   }
    # }
    if not response or not response.get('reviewers'):
      logging.error('Failed to add reviewers and post message to cl %s.',
                    change_id)
      return False
    return True

  def QueryCls(self, query_params, query_options=None):
    """Queries changes by provided parameters.

    Args:
      query_params(dict): query parameters.
      query_options (list): A list of query_options that need to be
        included in response.

    Returns:
      A list of ClInfo objects.
    """
    if not query_params:
      logging.error('Empty query parameters')
      return []

    query = ' '.join(['%s:"%s"' % (k, v) for k, v in query_params.iteritems()])
    params = [('q', query)]

    # Parameters to include additional fields in response.
    # See https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#query-options  # pylint:disable=line-too-long
    query_options = query_options or ['CURRENT_REVISION', 'CURRENT_COMMIT']
    params.extend([('o', field) for field in query_options])

    # The query url should look like:
    # https://host/a/changes/?q=k1:v1+k2:v2&o=ALL_REVISIONS&o=ALL_COMMITS
    changes_info = self._Get(['changes', ''], params=params)

    return [
        self._ParseClInfo(
            change_info,
            change_info.get('change_id') or change_info.get('_number'))
        for change_info in changes_info
    ]

  def GetClDetails(self,
                   change_id,
                   project='chromium/src',
                   branch='master',
                   query_options=None):
    assert project, 'project name is required'
    assert branch, 'branch name is required'

    query_options = query_options or ['CURRENT_REVISION', 'CURRENT_COMMIT']
    params = [('o', field) for field in query_options]

    # Uses full_change_id or the legacy numeric ID of the change.
    full_change_id = change_id if change_id.isdigit() else (
        '%s~%s~%s' % (project, branch, change_id))
    change_info = self._Get(
        ['changes', full_change_id, 'detail'], params=params)
    return self._ParseClInfo(change_info, change_id)

  def _ParseClInfo(self, change_info, change_id):
    if not change_info:  # pragma: no cover
      return None
    result = cl_info.ClInfo(self._server_hostname, change_id)

    result.reviewers = [
        x['email']
        for x in change_info.get('reviewers', {}).get('REVIEWER', [])
    ]
    result.cc = [
        x['email'] for x in change_info.get('reviewers', {}).get('CC', [])
    ]
    result.closed = change_info['status'] == 'MERGED'
    result.owner_email = change_info['owner'].get('email')
    result.subject = change_info['subject']
    result.revert_of = change_info.get('revert_of')

    # If the status is merged, look at the commit details for the current
    # commit.
    if result.closed:  # pragma: no branch
      current_revision = change_info['current_revision']
      revision_info = change_info['revisions'][current_revision]
      patchset_id = revision_info['_number']
      commit_timestamp = time_util.DatetimeFromString(change_info['submitted'])
      revision_commit = revision_info['commit']
      parent_revisions = [c['commit'] for c in revision_commit['parents']
                         ] if revision_commit else []
      result.commits.append(
          cl_info.Commit(patchset_id, current_revision, parent_revisions,
                         commit_timestamp))

      # Detect manual commits.
      committer = revision_commit['committer']['email']
      if committer not in self.commit_bot_emails:
        result.AddCqAttempt(patchset_id, committer, commit_timestamp)

      result.description = revision_commit['message']

      # Checks for if the culprit owner has turned off auto revert.
      result.auto_revert_off = codereview.IsAutoRevertOff(result.description)

    # Saves information for each patch set.
    for revision, revision_info in change_info['revisions'].iteritems():
      patchset_id = revision_info['_number']
      commit_info = revision_info.get('commit') or {}
      parent_revisions = [c['commit'] for c in commit_info['parents']
                         ] if commit_info else []
      result.patchsets[revision] = cl_info.PatchSet(patchset_id, revision,
                                                    parent_revisions)

    # TO FIND COMMIT ATTEMPTS:
    # In messages look for "Patch Set 1: Commit-Queue+2"
    # or "Patch Set 4: Code-Review+1 Commit-Queue+2".
    cq_pattern = re.compile('^Patch Set \d+:( Code-Review..)? Commit-Queue\+2$')
    revert_tag = 'autogenerated:gerrit:revert'
    revert_pattern = re.compile(
        'Created a revert of this change as (?P<change_id>I[a-f\d]{40})')

    for message in change_info.get('messages', []):
      if cq_pattern.match(message['message'].splitlines()[0]):
        patchset_id = message['_revision_number']
        author = message['author']['email']
        timestamp = time_util.DatetimeFromString(message['date'])
        result.AddCqAttempt(patchset_id, author, timestamp)

      # TO FIND REVERT(S):
      if message.get('tag') == revert_tag:
        patchset_id = message['_revision_number']
        author = message['author']['email']
        timestamp = time_util.DatetimeFromString(message['date'])
        reverting_change_id = revert_pattern.match(
            message['message']).group('change_id')
        reverting_cl = self.GetClDetails(reverting_change_id)
        result.reverts.append(
            cl_info.Revert(patchset_id, reverting_cl, author, timestamp))
    return result
