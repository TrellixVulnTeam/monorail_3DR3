# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for gerrit_api.py"""

import copy
import json
import mock
import requests
import tempfile
import time
import unittest
import requests.packages.urllib3

from infra.libs import gerrit_api


GERRIT_JSON_HEADER = ')]}\'\n'

HEADERS = {
    'Accept': 'application/json',
    'Accept-encoding': 'gzip',
    'Authorization': 'Basic Z2l0LWNvbW1pdC1ib3RAY2hyb21pdW0ub3JnOnNlY3JldA==',
}

HEADERS_WITH_CONTENT_TYPE = HEADERS.copy()
HEADERS_WITH_CONTENT_TYPE['Content-Type'] = 'application/json;charset=UTF-8'

TEST_PAYLOAD = {
    'drafts': 'KEEP',
    'labels': {
        'Code-Review': 1,
    },
    'message': 'Test message.',
    'notify': 'NONE',
    'tag': 'cq',
    'on_behalf_of': 'john@doe.net',
    'notify_details': {'TO': {'accounts': [123]}},
}

TEST_PAYLOAD_LABELS_ONLY = {
    'drafts': 'KEEP',
    'labels': {
        'Code-Review': 1,
    },
    'notify': 'OWNER',
}

TEST_CHANGE_INFO = {
    'id': 'project~branch~12345~change',
    'change_id': 12345,
    'created': '2014-02-11 12:14:28.135200000',
    'updated': '2014-03-11 00:20:08.946000000',
    'current_revision': 'THIRD',
    'owner': {
        'name': 'Some Person',
    },
    'revisions': {
        'THIRD': {
            '_number': 3,
        },
        'SECOND': {
            '_number': 2,
        },
        'FIRST': {
            '_number': 1,
        },
    },
    'labels': {
        'Commit-Queue': {
            'recommended': { '_account_id': 1 }
        },
        'Test-Label': {
            'disliked': { '_account_id' : 42 }
        },
        'Code-Review': {
            'approved': { '_account_id': 2 }
        },
    },
    'messages': [
        {
            'id': 1,
            'author': 'test-user@test.org',
            'date': '2014-02-11 12:10:14.311200000',
            'message': 'MESSAGE1',
        },
        {
            'id': 2,
            'date': '2014-02-11 12:11:14.311200000',
            'message': 'MESSAGE2',
            '_revision_number': 2,
        },
    ],
}

MOCK_AUTH=('git-commit-bot@chromium.org', 'secret')

def _create_mock_return(content, code):
  r = requests.Response()
  r._content = content
  r.status_code = code
  return r


# TODO(akuegel): Add more test cases and remove the pragma no covers.
class GerritAgentTestCase(unittest.TestCase):

  def setUp(self):
    self.gerrit = gerrit_api.Gerrit('chromium-review.googlesource.com',
                                    gerrit_api.Credentials(auth=MOCK_AUTH))
    self.gerrit_read_only = gerrit_api.Gerrit(
        'chromium-review.googlesource.com',
        gerrit_api.Credentials(auth=MOCK_AUTH),
        read_only=True)

  @mock.patch.object(requests.Session, 'request')
  def test_with_timeout_and_retries(self, mock_request):
    mock_request.return_value = _create_mock_return(
        '%s[]' % GERRIT_JSON_HEADER, 200)
    g = gerrit_api.Gerrit('chromium-review.googlesource.com',
                          gerrit_api.Credentials(auth=MOCK_AUTH),
                          retry_config=requests.packages.urllib3.util.Retry(
                            total=1, status_forcelist=[500, 503]),
                          timeout=(1, 2))
    g._request(method='GET', request_path='/self')
    mock_request.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url='https://chromium-review.googlesource.com/a/self',
        headers=HEADERS,
        hooks=g._instrumentation_hooks,
        timeout=(1, 2))

  @mock.patch.object(requests.Session, 'request')
  def test_request_no_leading_slash(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s[]' % GERRIT_JSON_HEADER, 200)
    result = self.gerrit._request(method='GET',
                                  request_path='changes/?q=query:no_results')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             '?q=query:no_results'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEqual(result, (200, []))

  @mock.patch.object(gerrit_api.Gerrit, '_sleep')
  @mock.patch.object(time, 'time')
  @mock.patch.object(requests.Session, 'request')
  def test_request_throttled(self, mock_method, time_mock_method, sleep_mock):
    gerrit_throttled = gerrit_api.Gerrit('chromium-review.googlesource.com',
                                         gerrit_api.Credentials(auth=MOCK_AUTH),
                                         0.1)
    mock_method.return_value = _create_mock_return(None, 404)
    time_mock_method.return_value = 100
    gerrit_throttled._request(method='GET', request_path='/accounts/self')
    # Call it twice to test the throttling.
    gerrit_throttled._request(method='GET', request_path='/accounts/self')
    sleep_mock.assert_called_once_with(0)
    time_mock_method.return_value = 101
    # Call it again after exceeding the throttle to cover the other branch.
    gerrit_throttled._request(method='GET', request_path='/accounts/self')

  @mock.patch.object(requests.Session, 'request')
  def test_get_account(self, mock_method):
    mock_method.return_value = _create_mock_return(
        ('%s{"_account_id":1000096,"name":"John Doe","email":'
         '"john.doe@test.com","username":"john"}') % GERRIT_JSON_HEADER,
        200)
    result = self.gerrit.get_account('self')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url='https://chromium-review.googlesource.com/a/accounts/self',
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    expected_result = {
        '_account_id': 1000096,
        'name': 'John Doe',
        'email': 'john.doe@test.com',
        'username': 'john'
    }
    self.assertEqual(result, expected_result)

  @mock.patch.object(requests.Session, 'request')
  def test_get_account_404(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 404)
    result = self.gerrit.get_account('does.not@exist.com')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com'
             '/a/accounts/does.not%40exist.com'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEqual(result, None)

  @mock.patch.object(requests.Session, 'request')
  def test_get_account_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 201)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.get_account, 'self')

  @mock.patch.object(requests.Session, 'request')
  def test_list_group_members(self, mock_method):
    mock_method.return_value = _create_mock_return(
        ('%s[{"_account_id":1000057,"name":"Jane Roe","email":'
         '"jane.roe@example.com","username": "jane"}]') % GERRIT_JSON_HEADER,
        200)
    result = self.gerrit.list_group_members('test-group')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com/a/groups/'
             'test-group/members'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    expected_result = [{
        '_account_id': 1000057,
        'name': 'Jane Roe',
        'email': 'jane.roe@example.com',
        'username': 'jane'
    }]
    self.assertEqual(result, expected_result)

  @mock.patch.object(requests.Session, 'request')
  def test_list_group_members_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.list_group_members, 'test-group')

  def test_list_group_members_wrong_group(self):
    self.assertRaises(ValueError, self.gerrit.list_group_members, 'a/b/c')

  @mock.patch.object(requests.Session, 'request')
  def test_add_group_members(self, mock_method):
    mock_method.return_value = _create_mock_return(
        ('%s[{"_account_id":1000057,"name":"Jane Roe","email":'
         '"jane.roe@example.com","username": "jane"}]') % GERRIT_JSON_HEADER,
        200)
    members = ['jane.roe@example.com']
    payload = { 'members': members }
    result = self.gerrit.add_group_members('test-group', members)
    mock_method.assert_called_once_with(
        data=json.dumps(payload),
        method='POST',
        params=None,
        url=('https://chromium-review.googlesource.com/a/groups/'
             'test-group/members.add'),
        headers=HEADERS_WITH_CONTENT_TYPE,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    expected_result = [{
        '_account_id': 1000057,
        'name': 'Jane Roe',
        'email': 'jane.roe@example.com',
        'username': 'jane'
    }]
    self.assertEqual(result, expected_result)

  @mock.patch.object(requests.Session, 'request')
  def test_add_group_members_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.add_group_members, 'test-group', ['a@b.com'])

  def test_add_group_members_wrong_group(self):
    self.assertRaises(ValueError, self.gerrit.add_group_members, 'a/b/c', [])

  def test_add_group_members_read_only(self):
    self.assertRaises(gerrit_api.AccessViolationException,
                      self.gerrit_read_only.add_group_members,
                      'test-group', ['a@b.com'])

  @mock.patch.object(requests.Session, 'request')
  def test_delete_group_members(self, mock_method):
    mock_method.return_value = _create_mock_return(
        ('%s[{"_account_id":1000057,"name":"Jane Roe","email":'
         '"jane.roe@example.com","username": "jane"}]') % GERRIT_JSON_HEADER,
        204)
    members = ['jane.roe@example.com']
    payload = { 'members': members }
    result = self.gerrit.delete_group_members('test-group', members)
    mock_method.assert_called_once_with(
        data=json.dumps(payload),
        method='POST',
        params=None,
        url=('https://chromium-review.googlesource.com/a/groups/'
             'test-group/members.delete'),
        headers=HEADERS_WITH_CONTENT_TYPE,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    expected_result = [{
        '_account_id': 1000057,
        'name': 'Jane Roe',
        'email': 'jane.roe@example.com',
        'username': 'jane'
    }]
    self.assertEqual(result, expected_result)

  @mock.patch.object(requests.Session, 'request')
  def test_delete_group_members_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(
        gerrit_api.UnexpectedResponseException,
        self.gerrit.delete_group_members, 'test-group', ['a@b.com'])

  def test_delete_group_members_wrong_group(self):
    self.assertRaises(ValueError, self.gerrit.delete_group_members, 'a/b/c', [])

  def test_delete_group_members_read_only(self):
    self.assertRaises(gerrit_api.AccessViolationException,
                      self.gerrit_read_only.delete_group_members,
                      'test-group', ['a@b.com'])

  @mock.patch.object(requests.Session, 'request')
  def test_set_project_parent(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s"parent"' % GERRIT_JSON_HEADER, 200)
    result = self.gerrit.set_project_parent('project', 'parent')
    payload = {
        'parent': 'parent',
        'commit_message': 'Changing parent project to parent'
    }
    mock_method.assert_called_once_with(
        data=json.dumps(payload),
        method='PUT',
        params=None,
        url=('https://chromium-review.googlesource.com/a/projects/'
             'project/parent'),
        headers=HEADERS_WITH_CONTENT_TYPE,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEqual(result, 'parent')

  @mock.patch.object(requests.Session, 'request')
  def test_set_project_parent_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.set_project_parent, 'a', 'b')

  @mock.patch.object(requests.Session, 'request')
  def test_query(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps([TEST_CHANGE_INFO])), 200)
    result = self.gerrit.query(project='test',
                               with_labels=False, with_revisions=False,
                               owner='test@chromium.org')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'q':'project:test owner:test@chromium.org', 'o': ['MESSAGES']},
        url='https://chromium-review.googlesource.com/a/changes/',
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, [TEST_CHANGE_INFO])

  @mock.patch.object(requests.Session, 'request')
  def test_query_with_query_name(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps([TEST_CHANGE_INFO])), 200)
    result = self.gerrit.query(project='test', query_name='pending_cls',
                               owner='1012155')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'q':'project:test query:pending_cls owner:1012155',
                'o': ['CURRENT_REVISION', 'LABELS', 'MESSAGES']},
        url='https://chromium-review.googlesource.com/a/changes/',
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, [TEST_CHANGE_INFO])

  @mock.patch.object(requests.Session, 'request')
  def test_query_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 400)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.query, 'a', with_messages=False,
                      with_labels=False, with_revisions=False)

  @mock.patch.object(requests.Session, 'request')
  def test_get_issue(self, mock_method):
    # By default, Gerrit doesn't return revisions data.
    info_without_revisions = TEST_CHANGE_INFO.copy()
    info_without_revisions.pop('revisions')
    info_without_revisions.pop('current_revision')
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps(info_without_revisions)), 200)
    result = self.gerrit.get_issue('test/project~weird/branch~hash')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             'test%2Fproject~weird%2Fbranch~hash/detail'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, info_without_revisions)

  @mock.patch.object(requests.Session, 'request')
  def test_get_issue_with_files(self, mock_method):
    info_with_files = copy.deepcopy(TEST_CHANGE_INFO)
    current = info_with_files['current_revision']
    info_with_files['revisions'][current]['files'] = {
        "first.py": {
          "lines_deleted": 8,
          "size_delta": -412,
          "size": 7782
        },
        "first.java": {
          "lines_inserted": 1,
          "size_delta": 23,
          "size": 6762
        },
    }
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps(info_with_files)), 200)
    result = self.gerrit.get_issue('test/project~weird/branch~hash',
                                   current_files=True)
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'o': ['CURRENT_FILES', 'CURRENT_REVISION']},
        url=('https://chromium-review.googlesource.com/a/changes/'
             'test%2Fproject~weird%2Fbranch~hash/detail'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, info_with_files)

  @mock.patch.object(requests.Session, 'request')
  def test_get_issue_generic(self, mock_method):
    # By default, Gerrit doesn't return revisions data.
    info_without_revisions = TEST_CHANGE_INFO.copy()
    info_without_revisions.pop('revisions')
    info_without_revisions.pop('current_revision')
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps(info_without_revisions)), 200)
    result = self.gerrit.get_issue('test/project~weird/branch~hash',
                                   options=['CURRENT_COMMIT'])
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'o': ['CURRENT_COMMIT']},
        url=('https://chromium-review.googlesource.com/a/changes/'
             'test%2Fproject~weird%2Fbranch~hash/detail'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, info_without_revisions)


  @mock.patch.object(requests.Session, 'request')
  def test_get_issue_with_files_and_revisions(self, mock_method):
    info = copy.deepcopy(TEST_CHANGE_INFO)
    current = info['current_revision']
    info['revisions'][current]['files'] = {
        "first.py": {
          "lines_deleted": 8,
          "size_delta": -412,
          "size": 7782
        },
        "first.java": {
          "lines_inserted": 1,
          "size_delta": 23,
          "size": 6762
        },
    }
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps(info)), 200)
    result = self.gerrit.get_issue('test/project~weird/branch~hash',
                                   current_files=True,
                                   revisions='ALL_REVISIONS')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'o': ['CURRENT_FILES', 'ALL_REVISIONS']},
        url=('https://chromium-review.googlesource.com/a/changes/'
             'test%2Fproject~weird%2Fbranch~hash/detail'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, info)

  @mock.patch.object(requests.Session, 'request')
  def test_get_issue_with_all_revisions(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER, json.dumps(TEST_CHANGE_INFO)), 200)
    result = self.gerrit.get_issue('test/project~weird/branch~hash',
                                   revisions='ALL_REVISIONS')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params={'o': ['ALL_REVISIONS']},
        url=('https://chromium-review.googlesource.com/a/changes/'
             'test%2Fproject~weird%2Fbranch~hash/detail'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, TEST_CHANGE_INFO)

  @mock.patch.object(requests.Session, 'request')
  def test_get_issue_not_found(self, mock_method):
    mock_method.return_value = _create_mock_return('Not found', 404)
    result = self.gerrit.get_issue('unknown~branch~hash')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             'unknown~branch~hash/detail'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    self.assertEquals(result, None)

  @mock.patch.object(requests.Session, 'request')
  def test_get_issue_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 500)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.get_issue, 'issue')

  @mock.patch.object(requests.Session, 'request')
  def test_set_review(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER,
                  json.dumps({'labels':{'Code-Review':1}})), 200)
    self.gerrit.set_review('change_id', 'revision_id', 'Test message.',
                           { 'Code-Review': 1 }, tag='cq',
                           on_behalf_of='john@doe.net',
                           notify_details={'TO': {'accounts': [123]}})
    mock_method.assert_called_once_with(
        data=json.dumps(TEST_PAYLOAD),
        method='POST',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             'change_id/revisions/revision_id/review'),
        headers=HEADERS_WITH_CONTENT_TYPE,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)

  @mock.patch.object(requests.Session, 'request')
  def test_set_review_only_label(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER,
                  json.dumps({'labels':{'Code-Review':1}})), 200)
    self.gerrit.set_review('change_id', 'revision_id',
                           labels={ 'Code-Review': 1 }, notify='OWNER')
    mock_method.assert_called_once_with(
        data=json.dumps(TEST_PAYLOAD_LABELS_ONLY),
        method='POST',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             'change_id/revisions/revision_id/review'),
        headers=HEADERS_WITH_CONTENT_TYPE,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)

  @mock.patch.object(requests.Session, 'request')
  def test_set_review_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 500)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.set_review, 'change_id', 'revision_id')

  @mock.patch.object(requests.Session, 'request')
  def test_submit_revision(self, mock_method):
    mock_method.return_value = _create_mock_return(
        '%s%s' % (GERRIT_JSON_HEADER,
                  json.dumps({'status': 'MERGE'})), 200)
    self.gerrit.submit_revision('change_id', 'current_revision_id')
    mock_method.assert_called_once_with(
        data=json.dumps({'wait_for_merge': True}),
        method='POST',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             'change_id/revisions/current_revision_id/submit'),
        headers=HEADERS_WITH_CONTENT_TYPE,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)

  @mock.patch.object(requests.Session, 'request')
  def test_submit_revision_revision_conflict(self, mock_method):
    mock_method.return_value = _create_mock_return(
        'revision revision_id is not current revision', 409)
    self.assertRaises(gerrit_api.RevisionConflictException,
                      self.gerrit.submit_revision, 'change_id', 'revision_id')

  @mock.patch.object(requests.Session, 'request')
  def test_submit_revision_unexpected_response(self, mock_method):
    mock_method.return_value = _create_mock_return(None, 500)
    self.assertRaises(gerrit_api.UnexpectedResponseException,
                      self.gerrit.submit_revision, 'change_id', 'revision_id')

  @mock.patch.object(requests.Session, 'request')
  def test_get_related_changes(self, mock_method):
    mock_method.side_effect = iter([
      _create_mock_return('{"changes": []}', 200),
      _create_mock_return('error', 500),
    ])
    self.gerrit.get_related_changes('change_id', 'revision_id')
    mock_method.assert_called_once_with(
        data=None,
        method='GET',
        params=None,
        url=('https://chromium-review.googlesource.com/a/changes/'
             'change_id/revisions/revision_id/related'),
        headers=HEADERS,
        hooks=self.gerrit._instrumentation_hooks,
        timeout=None)
    with self.assertRaises(gerrit_api.UnexpectedResponseException):
      self.gerrit.get_related_changes('change_id', 'revision_id')
