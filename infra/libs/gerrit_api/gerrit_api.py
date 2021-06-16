# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Yet another wrapper around Gerrit REST API."""

import base64
import cookielib
import functools
import json
import logging
import requests
import requests.packages.urllib3
import requests_cache
import time
import urllib

from infra_libs import instrumented_requests


LOGGER = logging.getLogger(__name__)
NOTIFY_NONE = 'NONE'
NOTIFY_OWNER = 'OWNER'
NOTIFY_OWNER_REVIEWERS = 'OWNER_REVIEWERS'
NOTIFY_ALL = 'ALL'

def _not_read_only(f):
  @functools.wraps(f)
  def wrapper(self, *args, **kwargs):
    if self._read_only:
      raise AccessViolationException(
          'Method call of method not accessible for read_only Gerrit instance.')
    return f(self, *args, **kwargs)
  return wrapper


class AccessViolationException(Exception):
  """A method was called which would require write access to Gerrit."""

class RevisionConflictException(Exception):
  """Committing failed because of a revision conflict."""

class UnexpectedResponseException(Exception):
  """Gerrit returned something unexpected."""

  def __init__(self, http_code, body):  # pragma: no cover
    super(UnexpectedResponseException, self).__init__()
    self.http_code = http_code
    self.body = body

  def __str__(self):  # pragma: no cover
    return 'Unexpected response (HTTP %d): %s' % (self.http_code, self.body)


class BlockCookiesPolicy(cookielib.DefaultCookiePolicy):
  def set_ok(self, cookie, request):
    return False # pragma: no cover


class Gerrit(object):
  """Wrapper around a single Gerrit host. Not thread-safe.

  Args:
    host (str): gerrit host name.
    creds (Credentials): provides credentials for the Gerrit host.
    throttle_delay_sec (int): minimal time delay between two requests, to
      avoid hammering the Gerrit server.
    read_only (bool): if True, mutating methods will raise
      AccessViolationException.
    timeout (float or tuple of floats): passed as is to requests library.
      None by default, which means block forever.
    retry_config (requests.packages.urllib3.util.Retry): override default retry
      config.
    instrumentation_id (str): monitoring identifier for HTTP requests.
      'gerrit' by default. See also `infra_libs.instrumented_requests library`.
  """

  def __init__(self, host, creds, throttle_delay_sec=0, read_only=False,
               retry_config=None, timeout=None, instrumentation_id='gerrit'):
    self._auth_header = 'Basic %s' % (
        base64.b64encode('%s:%s' % creds[host]))
    self._url_base = 'https://%s/a' % host.rstrip('/')
    self._throttle = throttle_delay_sec
    self._read_only = read_only
    self._last_call_ts = None
    self._timeout = timeout
    self.session = requests.Session()
    # Do not use cookies with Gerrit. This breaks interaction with Google's
    # Gerrit instances. Do not use cookies as advised by the Gerrit team.
    self.session.cookies.set_policy(BlockCookiesPolicy())
    if retry_config is None:
      retry_config = requests.packages.urllib3.util.Retry(
          total=4, backoff_factor=2, status_forcelist=[500, 503])
    else:
      # The |requests| package actually vendors in its own copy of urllib3,
      # Additionally, urllib3.util.retry module checks type using
      # isinstance(retry_config, Retry) and will return False if one provides
      # anything other than a requests.packages.urllib3.util.retry.Retry object.
      # So, help users of this package detect such errors early.
      assert isinstance(retry_config, requests.packages.urllib3.util.Retry)
    self.session.mount(self._url_base, requests.adapters.HTTPAdapter(
        max_retries=retry_config))
    # Instrumentation hooks cache indexed by method.
    self._instrumentation_hooks = {
      'response':
        instrumented_requests.instrumentation_hook(instrumentation_id),
    }

  def _sleep(self, time_since_last_call):
    time.sleep(self._throttle - time_since_last_call) # pragma: no cover

  def _request(self, method, request_path, params=None, body=None):
    """Sends HTTP request to Gerrit.

    Args:
      method: HTTP method (e.g 'GET', 'POST', ...).
      request_path: URL of the endpoint, relative to host (e.g. '/accounts/id').
      params: dict with query parameters.
      body: optional request body, will be serialized to JSON.

    Returns:
      Tuple (response code, deserialized JSON response).
    """
    if not request_path.startswith('/'):
      request_path = '/' + request_path

    full_url = '%s%s' % (self._url_base, request_path)

    # Wait to avoid Gerrit quota, don't wait if a response is in the cache.
    if self._throttle and not _is_response_cached(method, full_url):
      if self._last_call_ts:
        time_since_last_call = time.time() - self._last_call_ts
        if time_since_last_call < self._throttle:
          self._sleep(time_since_last_call)
      self._last_call_ts = time.time()

    headers = {
        # This makes the server return compact JSON.
        'Accept': 'application/json',
        # This means responses will be gzip compressed.
        'Accept-encoding': 'gzip',
        'Authorization': self._auth_header,
    }

    if body is not None:
      body = json.dumps(body)
      headers['Content-Type'] = 'application/json;charset=UTF-8'

    LOGGER.debug('%s %s', method, full_url)
    response = self.session.request(
        method=method,
        url=full_url,
        params=params,
        data=body,
        headers=headers,
        hooks=self._instrumentation_hooks,
        timeout=self._timeout)

    # Gerrit prepends )]}' to response.
    prefix = ')]}\'\n'
    body = response.text
    if body and body.startswith(prefix):
      body = json.loads(body[len(prefix):])

    return response.status_code, body

  def get_account(self, account_id):
    """Returns a dict describing a Gerrit account or None if no such account.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-accounts.html#get-account

    Args:
      account_id: email, numeric account id, or 'self'.

    Returns:
      None if no such account, AccountInfo dict otherwise.
    """
    assert '/' not in account_id
    code, body = self._request(
        'GET', '/accounts/%s' % urllib.quote(account_id, safe=''))
    if code == 200:
      return body
    if code == 404:
      return None
    raise UnexpectedResponseException(code, body)

  def list_group_members(self, group):
    """Lists the direct members of a group.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-groups.html#group-members

    Args:
      group: name of a group to list

    Returns:
      List of AccountInfo dicts.

    Raises:
      UnexpectedResponseException: if call failed.
    """
    if '/' in group:
      raise ValueError('Invalid group name: %s' % group)
    code, body = self._request(
        method='GET',
        request_path='/groups/%s/members' % group)
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  @_not_read_only
  def add_group_members(self, group, members):
    """Adds a bunch of members to a group.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-groups.html#_add_group_members

    Args:
      group: name of a group to add members to.
      members: iterable with emails of accounts to add to the group.

    Returns:
      None

    Raises:
      UnexpectedResponseException: if call failed.
    """
    if '/' in group:
      raise ValueError('Invalid group name: %s' % group)
    code, body = self._request(
        method='POST',
        request_path='/groups/%s/members.add' % group,
        body={'members': list(members)})
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  @_not_read_only
  def delete_group_members(self, group, members):
    """Deletes a bunch of members from a group.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-groups.html#delete-group-members

    Args:
      group: name of a group to delete members from.
      members: iterable with emails of accounts to delete from the group.

    Returns:
      None

    Raises:
      UnexpectedResponseException: if call failed.
    """
    if '/' in group:
      raise ValueError('Invalid group name: %s' % group)
    code, body = self._request(
        method='POST',
        request_path='/groups/%s/members.delete' % group,
        body={'members': list(members)})
    if code != 204:
      raise UnexpectedResponseException(code, body)
    # TODO(phajdan.jr): Make return consistent with doc and add_group_members.
    return body

  def is_account_active(self, account_id): # pragma: no cover
    if '/' in account_id:
      raise ValueError('Invalid account id: %s' % account_id)
    code, body = self._request(
        method='GET',
        request_path='/accounts/%s/active' % urllib.quote(account_id, safe=''))
    if code == 200:
      return True
    if code == 204:
      return False
    raise UnexpectedResponseException(code, body)

  @_not_read_only
  def activate_account(self, account_id): # pragma: no cover
    """Sets account state to 'active'.

    Args:
      account_id (str): account to update.

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    if '/' in account_id:
      raise ValueError('Invalid account id: %s' % account_id)
    code, body = self._request(
        method='PUT',
        request_path='/accounts/%s/active' % account_id)
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)

  def get_projects(self, prefix=''): # pragma: no cover
    """Returns list of projects with names starting with a prefix.

    Args:
      prefix (str): optional project name prefix to limit the listing to.

    Returns:
      Dict <project name> -> {'state': 'ACTIVE', 'parent': 'All-Projects'}

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    code, body = self._request(
        method='GET',
        request_path='/projects/?p=%s&t' % urllib.quote(prefix, safe=''))
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)
    return body

  def get_project_parent(self, project): # pragma: no cover
    """Retrieves the name of a project's parent project.

    Returns None If |project| is not registered on Gerrit or doesn't have
    a parent (like 'All-Projects').

    Args:
      project (str): project to query.

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    code, body = self._request(
        method='GET',
        request_path='/projects/%s/parent' % urllib.quote(project, safe=''))
    if code == 404:
      return None
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)
    assert isinstance(body, unicode)
    return body if body else None

  @_not_read_only
  def set_project_parent(self, project, parent, commit_message=None):
    """Changes project's parent project.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-projects.html#set-project-parent

    Args:
      project (str): project to change.
      parent (str): parent to set.
      commit_message (str): message for corresponding refs/meta/config commit.

    Raises:
      UnexpectedResponseException: if gerrit does not answer as expected.
    """
    commit_message = (
        commit_message or ('Changing parent project to %s' % parent))
    code, body = self._request(
        method='PUT',
        request_path='/projects/%s/parent' % urllib.quote(project, safe=''),
        body={'parent': parent, 'commit_message': commit_message})
    if code not in (200, 201):
      raise UnexpectedResponseException(code, body)
    return body

  def query(
      self,
      project,
      query_name=None,
      with_messages=True,
      with_labels='LABELS',
      with_revisions='CURRENT_REVISION',
      option_params=None,
      **kwargs):
    """Queries the Gerrit API changes endpoint. Returns a list of ChangeInfo
    dictionaries.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#list-changes

    Args:
      project: (str) The project name.
      query_name: (str) The name of the named query stored for the CQ user.
      with_messages: (bool) If True, adds the o=MESSAGES option.
      with_labels: either False, 'LABELS' (default), or 'DETAILED'.
      with_revisions: either False, 'CURRENT_REVISION' (default), or
        'ALL_REVISIONS'.
      option_params: (iterable of str) iterable of option params.
      kwargs: Allows to specify additional query parameters.
    """

    # We always restrict queries with the project name.
    query_params = 'project:%s' % project

    if query_name:
      query_params += ' query:%s' % query_name
    for operator, value in kwargs.iteritems():
      query_params += ' %s:%s' % (operator, value)

    option_params = set(option_params or [])
    if with_messages:
      option_params.add('MESSAGES')
    if with_labels:
      assert with_labels in ('LABELS', 'DETAILED_LABELS')
      option_params.add(with_labels)
    if with_revisions:
      assert with_revisions in ('ALL_REVISIONS', 'CURRENT_REVISION')
      option_params.add(with_revisions)
    option_params = sorted(option_params)

    # The requests library takes care of url encoding the params. For example
    # the spaces above in query_params will be replaced by '+'.
    params = {
        'q': query_params,
        'o': option_params
    }
    code, body = self._request(method='GET', request_path='/changes/',
                               params=params)
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  def get_issue(self, issue_id, revisions=None, current_files=None,
                options=None):
    """Returns a ChangeInfo dictionary for a given issue_id or None if it
    doesn't exist.

    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#get-change-detail

    Args:
      issue_id is gerrit issue id like project~branch~change_id.
      revisions either None (default) or 'CURRENT_REVISION' or 'ALL_REVISIONS'.
    """
    request_path = '/changes/%s/detail' % urllib.quote(issue_id, safe='~')
    options = options or []

    if current_files:
      options.append('CURRENT_FILES')
      if revisions is None:
        revisions = 'CURRENT_REVISION'

    if revisions is not None:
      assert revisions in ('CURRENT_REVISION', 'ALL_REVISIONS')
      options.append(revisions)

    params = None
    if options:
      params = {'o': options}

    code, body = self._request(method='GET', request_path=request_path,
                               params=params)
    if code == 404:
      return None
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  @_not_read_only
  def set_review(self, change_id, revision_id, message=None, labels=None,
                 notify=NOTIFY_NONE, max_message=300, tag=None,
                 on_behalf_of=None, notify_details=None):
    """Uses the Set Review endpoint of the Gerrit API to add messages and/or set
    labels for a patchset.

    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#set-review

    Args:
      change_id: (str) The id of the change list.
      revision_id: (str) The id of the affected revision.
      message: (str) The message to add to the patchset.
      labels: (dict) The dictionary which maps label names to their new value.
      notify: (str) Who should get a notification.
      tag: (str) Apply this tag to the review comment message and labels (votes)
        https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#review-input
      on_behalf_of: (str) The account_id of the user on whose behalf to set
        labels.
      notify_details: (dict) The mapping from either of 3 keys "TO", "CC", "BCC"
        to structure {"accounts": [account_id, "email", "or even name"]}.
    """
    if message:
      tail = u'\n(message too large)'
      if len(message) > max_message:
        message = message[:max_message-len(tail)] + tail # pragma: no cover
      logging.info('change_id: %s; comment: %s' % (change_id, message.strip()))
    payload = {'drafts': 'KEEP'}
    for var, attr in [(message, 'message'), (notify, 'notify'),
                     (labels, 'labels'), (tag, 'tag'),
                     (on_behalf_of, 'on_behalf_of'),
                     (notify_details, 'notify_details')]:
      if var is not None:
        payload[attr] = var
    code, body = self._request(
        method='POST',
        request_path='/changes/%s/revisions/%s/review' % (
            urllib.quote(change_id, safe='~'),
            urllib.quote(revision_id, safe='')),
        body=payload)
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  @_not_read_only
  def submit_revision(self, change_id, current_revision_id):
    """Uses the Submit Revision endpoint of the Gerrit API to submit a change
    list. Returns a SubmitInfo object corresponding to the status of the submit.
    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#submit-revision

    Args:
      change_id: (str) The id of the change list.
      current_revision_id: (str) The id of the current revision.
    """
    code, body = self._request(
        method='POST',
        request_path='/changes/%s/revisions/%s/submit' % (
            urllib.quote(change_id, safe='~'),
            urllib.quote(current_revision_id, safe='')),
        body={'wait_for_merge': True})
    if code == 409:
      raise RevisionConflictException(body)
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body

  def get_related_changes(self, change_id, revision_id):
    """Returns related changes.

    Documentation:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#get-related-changes


    Args:
      change_id: (str) The id of the change list.
      current_revision_id: (str) The id of the revision (patchset).
    """
    code, body = self._request(
        method='GET',
        request_path='/changes/%s/revisions/%s/related' % (
            urllib.quote(change_id, safe='~'),
            urllib.quote(revision_id, safe='')))
    if code != 200:
      raise UnexpectedResponseException(code, body)
    return body


def _is_response_cached(method, full_url):
  """Returns True if response to GET request is in requests_cache.

  Args:
    method (str): http verb ('GET', 'POST', etc.)
    full_url (str): url, including the protocol
  Returns:
    is_cached (bool):
  """
  if method != 'GET':
    return False # pragma: no cover
  try:
    cache = requests_cache.get_cache()
  except AttributeError: # pragma: no cover
    cache = None
  return cache.has_url(full_url) if cache else False
