# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the API v1."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import endpoints
import logging
from mock import Mock, patch, ANY
import os
import time
import unittest
import webtest

from google.appengine.api import oauth
from google.appengine.ext import testbed
from protorpc import messages
from protorpc import message_types

from features import send_notifications
from framework import authdata
from framework import exceptions
from framework import framework_constants
from framework import permissions
from framework import profiler
from framework import template_helpers
from proto import api_pb2_v1
from proto import project_pb2
from proto import tracker_pb2
from search import frontendsearchpipeline
from services import api_svc_v1
from services import service_manager
from services import template_svc
from services import tracker_fulltext
from testing import fake
from testing import testing_helpers
from testing_utils import testing
from tracker import tracker_bizobj


def MakeFakeServiceManager():
  return service_manager.Services(
      user=fake.UserService(),
      usergroup=fake.UserGroupService(),
      project=fake.ProjectService(),
      config=fake.ConfigService(),
      issue=fake.IssueService(),
      issue_star=fake.IssueStarService(),
      features=fake.FeaturesService(),
      template=Mock(spec=template_svc.TemplateService),
      cache_manager=fake.CacheManager())


class FakeMonorailApiRequest(object):

  def __init__(self, request, services, perms=None):
    self.profiler = profiler.Profiler()
    self.cnxn = None
    self.auth = authdata.AuthData.FromEmail(
        self.cnxn, request['requester'], services)
    self.me_user_id = self.auth.user_id
    self.project_name = None
    self.project = None
    self.viewed_username = None
    self.viewed_user_auth = None
    self.config = None
    if 'userId' in request:
      self.viewed_username = request['userId']
      self.viewed_user_auth = authdata.AuthData.FromEmail(
          self.cnxn, self.viewed_username, services)
    else:
      assert 'groupName' in request
      self.viewed_username = request['groupName']
      try:
        self.viewed_user_auth = authdata.AuthData.FromEmail(
          self.cnxn, self.viewed_username, services)
      except exceptions.NoSuchUserException:
        self.viewed_user_auth = None
    if 'projectId' in request:
      self.project_name = request['projectId']
      self.project = services.project.GetProjectByName(
        self.cnxn, self.project_name)
      self.config = services.config.GetProjectConfig(
          self.cnxn, self.project_id)
    self.perms = perms or permissions.GetPermissions(
        self.auth.user_pb, self.auth.effective_ids, self.project)
    self.granted_perms = set()

    self.params = {
      'can': request.get('can', 1),
      'start': request.get('startIndex', 0),
      'num': request.get('maxResults', 100),
      'q': request.get('q', ''),
      'sort': request.get('sort', ''),
      'groupby': '',
      'projects': request.get('additionalProject', []) + [self.project_name]}
    self.use_cached_searches = True
    self.errors = template_helpers.EZTError()
    self.mode = None

    self.query_project_names = self.GetParam('projects')
    self.group_by_spec = self.GetParam('groupby')
    self.sort_spec = self.GetParam('sort')
    self.query = self.GetParam('q')
    self.can = self.GetParam('can')
    self.start = self.GetParam('start')
    self.num = self.GetParam('num')
    self.warnings = []

  def CleanUp(self):
    self.cnxn = None

  @property
  def project_id(self):
    return self.project.project_id if self.project else None

  def GetParam(self, query_param_name, default_value=None,
               _antitamper_re=None):
    return self.params.get(query_param_name, default_value)


class FakeFrontendSearchPipeline(object):

  def __init__(self):
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, owner_id=222, status='New', summary='sum')
    issue2 = fake.MakeTestIssue(
        project_id=12345, local_id=2, owner_id=222, status='New', summary='sum')
    self.allowed_results = [issue1, issue2]
    self.visible_results = [issue1]
    self.total_count = len(self.allowed_results)
    self.config = None
    self.projectId = 0

  def SearchForIIDs(self):
    pass

  def MergeAndSortIssues(self):
    pass

  def Paginate(self):
    pass


class MonorailApiBadAuthTest(testing.EndpointsTestCase):

  api_service_cls = api_svc_v1.MonorailApi

  def setUp(self):
    super(MonorailApiBadAuthTest, self).setUp()
    self.requester = RequesterMock(email='requester@example.com')
    self.mock(endpoints, 'get_current_user', lambda: None)
    self.request = {'userId': 'user@example.com'}

  def testUsersGet_BadOAuth(self):
    """The requester's token is invalid, e.g., because it expired."""
    oauth.get_current_user = Mock(
        return_value=RequesterMock(email='test@example.com'))
    oauth.get_current_user.side_effect = oauth.Error()
    with self.assertRaises(webtest.AppError) as cm:
      self.call_api('users_get', self.request)
    self.assertTrue(cm.exception.message.startswith('Bad response: 401'))


class MonorailApiTest(testing.EndpointsTestCase):

  api_service_cls = api_svc_v1.MonorailApi

  def setUp(self):
    super(MonorailApiTest, self).setUp()
    # Load queue.yaml.
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    self.taskqueue_stub._root_path = os.path.dirname(
        os.path.dirname(os.path.dirname( __file__ )))

    self.requester = RequesterMock(email='requester@example.com')
    self.mock(endpoints, 'get_current_user', lambda: self.requester)
    self.config = None
    self.services = MakeFakeServiceManager()
    self.mock(api_svc_v1.MonorailApi, '_services', self.services)
    self.services.user.TestAddUser('requester@example.com', 111)
    self.services.user.TestAddUser('user@example.com', 222)
    self.services.user.TestAddUser('group@example.com', 123)
    self.services.usergroup.TestAddGroupSettings(123, 'group@example.com')
    self.request = {
          'userId': 'user@example.com',
          'ownerProjectsOnly': False,
          'requester': 'requester@example.com',
          'projectId': 'test-project',
          'issueId': 1}
    self.mock(api_svc_v1.MonorailApi, 'mar_factory',
              lambda x, y, z: FakeMonorailApiRequest(
                  self.request, self.services))

    # api_base_checks is tested in AllBaseChecksTest,
    # so mock it to reduce noise.
    self.mock(api_svc_v1, 'api_base_checks',
              lambda x, y, z, u, v, w: ('id', 'email'))

    self.mock(tracker_fulltext, 'IndexIssues', lambda x, y, z, u, v: None)

  def SetUpComponents(
      self, project_id, component_id, component_name, component_doc='doc',
      deprecated=False, admin_ids=None, cc_ids=None, created=100000,
      creator=111):
    admin_ids = admin_ids or []
    cc_ids = cc_ids or []
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)
    cd = tracker_bizobj.MakeComponentDef(
        component_id, project_id, component_name, component_doc, deprecated,
        admin_ids, cc_ids, created, creator, modifier_id=creator)
    self.config.component_defs.append(cd)

  def SetUpFieldDefs(
      self, field_id, project_id, field_name, field_type_int,
      min_value=0, max_value=100, needs_member=False, docstring='doc',
      approval_id=None, is_phase_field=False):
    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', project_id)
    self.services.config.StoreConfig('fake cnxn', self.config)
    fd = tracker_bizobj.MakeFieldDef(
        field_id, project_id, field_name, field_type_int, '',
        '', False, False, False, min_value, max_value, None, needs_member,
        None, '', tracker_pb2.NotifyTriggers.NEVER, 'no_action', docstring,
        False, approval_id=approval_id, is_phase_field=is_phase_field)
    self.config.field_defs.append(fd)

  def testUsersGet_NoProject(self):
    """The viewed user has no projects."""

    self.services.project.TestAddProject(
        'public-project', owner_ids=[111])
    resp = self.call_api('users_get', self.request).json_body
    expected = {
        'id': '222',
        'kind': 'monorail#user'}
    self.assertEqual(expected, resp)

  def testUsersGet_PublicProject(self):
    """The viewed user has one public project."""
    self.services.template.GetProjectTemplates.return_value = \
        testing_helpers.DefaultTemplates()
    self.services.project.TestAddProject(
        'public-project', owner_ids=[222])
    resp = self.call_api('users_get', self.request).json_body

    self.assertEqual(1, len(resp['projects']))
    self.assertEqual('public-project', resp['projects'][0]['name'])

  def testUsersGet_PrivateProject(self):
    """The viewed user has one project but the requester cannot view."""

    self.services.project.TestAddProject(
        'private-project', owner_ids=[222],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY)
    resp = self.call_api('users_get', self.request).json_body
    self.assertNotIn('projects', resp)

  def testUsersGet_OwnerProjectOnly(self):
    """The viewed user has different roles of projects."""
    self.services.template.GetProjectTemplates.return_value = \
        testing_helpers.DefaultTemplates()
    self.services.project.TestAddProject(
        'owner-project', owner_ids=[222])
    self.services.project.TestAddProject(
        'member-project', owner_ids=[111], committer_ids=[222])
    resp = self.call_api('users_get', self.request).json_body
    self.assertEqual(2, len(resp['projects']))

    self.request['ownerProjectsOnly'] = True
    resp = self.call_api('users_get', self.request).json_body
    self.assertEqual(1, len(resp['projects']))
    self.assertEqual('owner-project', resp['projects'][0]['name'])

  def testIssuesGet_GetIssue(self):
    """Get the requested issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    self.SetUpFieldDefs(1, 12345, 'Field1', tracker_pb2.FieldTypes.INT_TYPE)

    fv = tracker_pb2.FieldValue(
        field_id=1,
        int_value=11)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, owner_id=222, reporter_id=111,
        status='New', summary='sum', component_ids=[1], field_values=[fv])
    self.services.issue.TestAddIssue(issue1)

    resp = self.call_api('issues_get', self.request).json_body
    self.assertEqual(1, resp['id'])
    self.assertEqual('New', resp['status'])
    self.assertEqual('open', resp['state'])
    self.assertFalse(resp['canEdit'])
    self.assertTrue(resp['canComment'])
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('user@example.com', resp['owner']['name'])
    self.assertEqual('API', resp['components'][0])
    self.assertEqual('Field1', resp['fieldValues'][0]['fieldName'])
    self.assertEqual('11', resp['fieldValues'][0]['fieldValue'])

  def testIssuesInsert_BadRequest(self):
    """The request does not specify summary or status."""

    with self.assertRaises(webtest.AppError):
      self.call_api('issues_insert', self.request)

    issue_dict = {
      'status': 'New',
      'summary': 'Test issue',
      'owner': {'name': 'notexist@example.com'}}
    self.request.update(issue_dict)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    with self.call_should_fail(400):
      self.call_api('issues_insert', self.request)

    # Invalid field value
    self.SetUpFieldDefs(1, 12345, 'Field1', tracker_pb2.FieldTypes.INT_TYPE)
    issue_dict = {
      'status': 'New',
      'summary': 'Test issue',
      'owner': {'name': 'requester@example.com'},
      'fieldValues': [{'fieldName': 'Field1', 'fieldValue': '111'}]}
    self.request.update(issue_dict)
    with self.call_should_fail(400):
      self.call_api('issues_insert', self.request)

  def testIssuesInsert_NoPermission(self):
    """The requester has no permission to create issues."""

    issue_dict = {
      'status': 'New',
      'summary': 'Test issue'}
    self.request.update(issue_dict)

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)
    with self.call_should_fail(403):
      self.call_api('issues_insert', self.request)

  def testIssuesInsert_CreateIssue(self):
    """Create an issue as requested."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    self.SetUpFieldDefs(1, 12345, 'Field1', tracker_pb2.FieldTypes.INT_TYPE)

    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, owner_id=222, reporter_id=111,
        status='New', summary='Test issue')
    self.services.issue.TestAddIssue(issue1)

    issue_dict = {
      'blockedOn': [{'issueId': 1}],
      'cc': [{'name': 'user@example.com'}, {'name': ''}, {'name': ' '}],
      'description': 'description',
      'labels': ['label1', 'label2'],
      'owner': {'name': 'requester@example.com'},
      'status': 'New',
      'summary': 'Test issue',
      'fieldValues': [{'fieldName': 'Field1', 'fieldValue': '11'}]}
    self.request.update(issue_dict)

    resp = self.call_api('issues_insert', self.request).json_body
    self.assertEqual('New', resp['status'])
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('requester@example.com', resp['owner']['name'])
    self.assertEqual('user@example.com', resp['cc'][0]['name'])
    self.assertEqual(1, resp['blockedOn'][0]['issueId'])
    self.assertEqual([u'label1', u'label2'], resp['labels'])
    self.assertEqual('Test issue', resp['summary'])
    self.assertEqual('Field1', resp['fieldValues'][0]['fieldName'])
    self.assertEqual('11', resp['fieldValues'][0]['fieldValue'])

    new_issue = self.services.issue.GetIssueByLocalID(
        'fake cnxn', 12345, resp['id'])

    starrers = self.services.issue_star.LookupItemStarrers(
        'fake cnxn', new_issue.issue_id)
    self.assertIn(111, starrers)

  def testIssuesInsert_EmptyOwnerCcNames(self):
    """Create an issue as requested."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    self.SetUpFieldDefs(1, 12345, 'Field1', tracker_pb2.FieldTypes.INT_TYPE)

    issue_dict = {
      'cc': [{'name': 'user@example.com'}, {'name': ''}],
      'description': 'description',
      'owner': {'name': ''},
      'status': 'New',
      'summary': 'Test issue'}
    self.request.update(issue_dict)

    resp = self.call_api('issues_insert', self.request).json_body
    self.assertEqual('New', resp['status'])
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertTrue('owner' not in resp)
    self.assertEqual('user@example.com', resp['cc'][0]['name'])
    self.assertEqual(len(resp['cc']), 1)
    self.assertEqual('Test issue', resp['summary'])

    new_issue = self.services.issue.GetIssueByLocalID(
        'fake cnxn', 12345, resp['id'])
    self.assertIsNone(new_issue.owner_id)

  def testIssuesList_NoPermission(self):
    """No permission for additional projects."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    self.services.project.TestAddProject(
        'test-project2', owner_ids=[222],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=123456)
    self.request['additionalProject'] = ['test-project2']
    with self.call_should_fail(403):
      self.call_api('issues_list', self.request)

  def testIssuesList_SearchIssues(self):
    """Find issues of one project."""

    self.mock(frontendsearchpipeline, 'FrontendSearchPipeline',
              lambda cnxn, serv, auth, me, q, q_proj_names,
              num, start, url_params, can, group_spec, sort_spec,
              warnings, errors, use_cache, profiler,
              display_mode, project:
              FakeFrontendSearchPipeline())

    self.services.project.TestAddProject(
        'test-project', owner_ids=[111],  # requester
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)
    resp = self.call_api('issues_list', self.request).json_body
    self.assertEqual(2, int(resp['totalResults']))
    self.assertEqual(1, len(resp['items']))
    self.assertEqual(1, resp['items'][0]['id'])

  def testIssuesCommentsList_GetComments(self):
    """Get comments of requested issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary', status='New',
        issue_id=10001, owner_id=222, reporter_id=111)
    self.services.issue.TestAddIssue(issue1)

    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=222,
        content='this is a comment',
        timestamp=1437700000)
    self.services.issue.TestAddComment(comment, 1)

    resp = self.call_api('issues_comments_list', self.request).json_body
    self.assertEqual(2, resp['totalResults'])
    comment1 = resp['items'][0]
    comment2 = resp['items'][1]
    self.assertEqual('requester@example.com', comment1['author']['name'])
    self.assertEqual('test summary', comment1['content'])
    self.assertEqual('user@example.com', comment2['author']['name'])
    self.assertEqual('this is a comment', comment2['content'])

  def testParseImportedReporter_Normal(self):
    """Normal attempt to post a comment under the requester's name."""
    mar = FakeMonorailApiRequest(self.request, self.services)
    container = api_pb2_v1.ISSUES_COMMENTS_INSERT_REQUEST_RESOURCE_CONTAINER
    request = container.body_message_class()

    monorail_api = self.api_service_cls()
    monorail_api._set_services(self.services)
    reporter_id, timestamp = monorail_api.parse_imported_reporter(mar, request)
    self.assertEqual(111, reporter_id)
    self.assertIsNone(timestamp)

    # API users should not need to specify anything for author when posting
    # as the signed-in user, but it is OK if they specify their own email.
    request.author = api_pb2_v1.AtomPerson(name='requester@example.com')
    request.published = datetime.datetime.now()  # Ignored
    monorail_api = self.api_service_cls()
    monorail_api._set_services(self.services)
    reporter_id, timestamp = monorail_api.parse_imported_reporter(mar, request)
    self.assertEqual(111, reporter_id)
    self.assertIsNone(timestamp)

  def testParseImportedReporter_Import_Allowed(self):
    """User is importing a comment posted by a different user."""
    project = self.services.project.TestAddProject(
        'test-project', owner_ids=[222], contrib_ids=[111],
        project_id=12345)
    project.extra_perms = [project_pb2.Project.ExtraPerms(
      member_id=111, perms=['ImportComment'])]
    mar = FakeMonorailApiRequest(self.request, self.services)
    container = api_pb2_v1.ISSUES_COMMENTS_INSERT_REQUEST_RESOURCE_CONTAINER
    request = container.body_message_class()
    request.author = api_pb2_v1.AtomPerson(name='user@example.com')
    NOW = 1234567890
    request.published = datetime.datetime.utcfromtimestamp(NOW)
    monorail_api = self.api_service_cls()
    monorail_api._set_services(self.services)

    reporter_id, timestamp = monorail_api.parse_imported_reporter(mar, request)

    self.assertEqual(222, reporter_id)  # that is user@
    self.assertEqual(NOW, timestamp)

  def testParseImportedReporter_Import_NotAllowed(self):
    """User is importing a comment posted by a different user without perm."""
    mar = FakeMonorailApiRequest(self.request, self.services)
    container = api_pb2_v1.ISSUES_COMMENTS_INSERT_REQUEST_RESOURCE_CONTAINER
    request = container.body_message_class()
    request.author = api_pb2_v1.AtomPerson(name='user@example.com')
    NOW = 1234567890
    request.published = datetime.datetime.fromtimestamp(NOW)
    monorail_api = self.api_service_cls()
    monorail_api._set_services(self.services)

    with self.assertRaises(permissions.PermissionException):
      monorail_api.parse_imported_reporter(mar, request)

  def testIssuesCommentsInsert_ApprovalFields(self):
    """Attempts to update approval field values are blocked."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2, issue_id=1234501)
    self.services.issue.TestAddIssue(issue1)

    self.SetUpFieldDefs(
        1, 12345, 'Field_int', tracker_pb2.FieldTypes.INT_TYPE)
    self.SetUpFieldDefs(
        2, 12345, 'ApprovalChild', tracker_pb2.FieldTypes.STR_TYPE,
        approval_id=1)

    self.request['updates'] = {
        'fieldValues':  [{'fieldName': 'Field_int', 'fieldValue': '11'},
                        {'fieldName': 'ApprovalChild', 'fieldValue': 'str'}]}

    with self.call_should_fail(403):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_NoCommentPermission(self):
    """No permission to comment an issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 2)
    self.services.issue.TestAddIssue(issue1)

    with self.call_should_fail(403):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_CommentPermissionOnly(self):
    """User has permission to comment, even though they cannot edit."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[], project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222)
    self.services.issue.TestAddIssue(issue1)

    self.request['content'] = 'This is just a comment'
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('This is just a comment', resp['content'])

  def testIssuesCommentsInsert_Amendments_Normal(self):
    """Insert comments with amendments."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[111],
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    issue2 = fake.MakeTestIssue(
        12345, 2, 'Issue 2', 'New', 222, project_name='test-project')
    issue3 = fake.MakeTestIssue(
        12345, 3, 'Issue 3', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)
    self.services.issue.TestAddIssue(issue3)

    self.request['updates'] = {
        'summary': 'new summary',
        'status': 'Started',
        'owner': 'requester@example.com',
        'cc': ['user@example.com'],
        'labels': ['add_label', '-remove_label'],
        'blockedOn': ['2'],
        'blocking': ['3'],
        }
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('Started', resp['updates']['status'])
    self.assertEqual(0, issue1.merged_into)

  def testIssuesCommentsInsert_Amendments_NoPerms(self):
    """Can't insert comments using account that lacks permissions."""

    project1 = self.services.project.TestAddProject(
        'test-project', owner_ids=[], project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    self.request['updates'] = {
        'summary': 'new summary',
        }
    with self.call_should_fail(403):
      self.call_api('issues_comments_insert', self.request)

    project1.contributor_ids = [1]  # Does not grant edit perm.
    with self.call_should_fail(403):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_Amendments_BadOwner(self):
    """Can't set owner to someone who is not a project member."""

    _project1 = self.services.project.TestAddProject(
        'test-project', owner_ids=[111], project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    self.request['updates'] = {
        'owner': 'user@example.com',
        }
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_MergeInto(self):
    """Insert comment that merges an issue into another issue."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222], committer_ids=[111],
        project_id=12345)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    issue2 = fake.MakeTestIssue(
        12345, 2, 'Issue 2', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.services.issue.TestAddIssue(issue2)
    self.services.issue_star.SetStarsBatch(
        'cnxn', 'service', 'config', issue1.issue_id, [111, 222, 333], True)
    self.services.issue_star.SetStarsBatch(
        'cnxn', 'service', 'config', issue2.issue_id, [555], True)

    self.request['updates'] = {
        'summary': 'new summary',
        'status': 'Duplicate',
        'owner': 'requester@example.com',
        'cc': ['user@example.com'],
        'labels': ['add_label', '-remove_label'],
        'mergedInto': '2',
        }
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual('requester@example.com', resp['author']['name'])
    self.assertEqual('Duplicate', resp['updates']['status'])
    self.assertEqual(issue2.issue_id, issue1.merged_into)
    issue2_comments = self.services.issue.GetCommentsForIssue(
      'cnxn', issue2.issue_id)
    self.assertEqual(2, len(issue2_comments))  # description and merge
    source_starrers = self.services.issue_star.LookupItemStarrers(
        'cnxn', issue1.issue_id)
    self.assertItemsEqual([111, 222, 333], source_starrers)
    target_starrers = self.services.issue_star.LookupItemStarrers(
        'cnxn', issue2.issue_id)
    self.assertItemsEqual([111, 222, 333, 555], target_starrers)

  def testIssuesCommentsInsert_CustomFields(self):
    """Update custom field values."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222,
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.SetUpFieldDefs(
        1, 12345, 'Field_int', tracker_pb2.FieldTypes.INT_TYPE)
    self.SetUpFieldDefs(
        2, 12345, 'Field_enum', tracker_pb2.FieldTypes.ENUM_TYPE)

    self.request['updates'] = {
        'fieldValues': [{'fieldName': 'Field_int', 'fieldValue': '11'},
                        {'fieldName': 'Field_enum', 'fieldValue': 'str'}]}
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual(
        {'fieldName': 'Field_int', 'fieldValue': '11'},
        resp['updates']['fieldValues'][0])

  def testIssuesCommentsInsert_IsDescription(self):
    """Add a new issue description."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111], project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    # Note: the initially issue description will be "Issue 1".

    self.request['content'] = 'new desc'
    self.request['updates'] = {'is_description': True}
    resp = self.call_api('issues_comments_insert', self.request).json_body
    self.assertEqual('new desc', resp['content'])
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue1.issue_id)
    self.assertEqual(2, len(comments))
    self.assertTrue(comments[1].is_description)
    self.assertEqual('new desc', comments[1].content)

  def testIssuesCommentsInsert_MoveToProject_NoPermsSrc(self):
    """Don't move issue when user has no perms to edit issue."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[], project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, labels=[],
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.services.project.TestAddProject(
        'test-project2', owner_ids=[111], project_id=12346)

    # The user has no permission in test-project.
    self.request['projectId'] = 'test-project'
    self.request['updates'] = {
        'moveToProject': 'test-project2'}
    with self.call_should_fail(403):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_MoveToProject_NoPermsDest(self):
    """Don't move issue to a different project where user has no perms."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111], project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, labels=[],
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.services.project.TestAddProject(
        'test-project2', owner_ids=[], project_id=12346)

    # The user has no permission in test-project2.
    self.request['projectId'] = 'test-project'
    self.request['updates'] = {
        'moveToProject': 'test-project2'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_MoveToProject_NoSuchProject(self):
    """Don't move issue to a different project that does not exist."""
    project1 = self.services.project.TestAddProject(
        'test-project', owner_ids=[222], project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, labels=[],
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    # Project doesn't exist.
    project1.owner_ids = [111, 222]
    self.request['updates'] = {
        'moveToProject': 'not exist'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_MoveToProject_SameProject(self):
    """Don't move issue to the project it is already in."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111], project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, labels=[],
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    # The issue is already in destination
    self.request['updates'] = {
        'moveToProject': 'test-project'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_MoveToProject_Restricted(self):
    """Don't move restricted issue to a different project."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111], project_id=12345)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, labels=['Restrict-View-Google'],
        project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    self.services.project.TestAddProject(
        'test-project2', owner_ids=[111],
        project_id=12346)

    #  Issue has restrict labels, so it cannot move.
    self.request['projectId'] = 'test-project'
    self.request['updates'] = {
        'moveToProject': 'test-project2'}
    with self.call_should_fail(400):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsInsert_MoveToProject_Normal(self):
    """Move issue."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111, 222],
        project_id=12345)
    self.services.project.TestAddProject(
        'test-project2', owner_ids=[111, 222],
        project_id=12346)
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)
    issue2 = fake.MakeTestIssue(
        12346, 1, 'Issue 1', 'New', 222, project_name='test-project2')
    self.services.issue.TestAddIssue(issue2)

    self.request['updates'] = {
        'moveToProject': 'test-project2'}
    resp = self.call_api('issues_comments_insert', self.request).json_body

    self.assertEqual(
        'Moved issue test-project:1 to now be issue test-project2:2.',
        resp['content'])

  def testIssuesCommentsInsert_Import_Allowed(self):
    """Post a comment attributed to another user, with permission."""
    project = self.services.project.TestAddProject(
        'test-project', committer_ids=[111, 222], project_id=12345)
    project.extra_perms = [project_pb2.Project.ExtraPerms(
      member_id=111, perms=['ImportComment'])]
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    self.request['author'] = {'name': 'user@example.com'}  # 222
    self.request['content'] = 'a comment'
    self.request['updates'] = {
        'owner': 'user@example.com',
        }

    resp = self.call_api('issues_comments_insert', self.request).json_body

    self.assertEqual('a comment', resp['content'])
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue1.issue_id)
    self.assertEqual(2, len(comments))
    self.assertEqual(222, comments[1].user_id)
    self.assertEqual('a comment', comments[1].content)


  def testIssuesCommentsInsert_Import_Self(self):
    """Specifying the comment author is OK if it is the requester."""
    self.services.project.TestAddProject(
        'test-project', committer_ids=[111, 222], project_id=12345)
    # Note: No ImportComment permission has been granted.
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    self.request['author'] = {'name': 'requester@example.com'}  # 111
    self.request['content'] = 'a comment'
    self.request['updates'] = {
        'owner': 'user@example.com',
        }

    resp = self.call_api('issues_comments_insert', self.request).json_body

    self.assertEqual('a comment', resp['content'])
    comments = self.services.issue.GetCommentsForIssue('cnxn', issue1.issue_id)
    self.assertEqual(2, len(comments))
    self.assertEqual(111, comments[1].user_id)
    self.assertEqual('a comment', comments[1].content)

  def testIssuesCommentsInsert_Import_Denied(self):
    """Cannot post a comment attributed to another user without permission."""
    self.services.project.TestAddProject(
        'test-project', committer_ids=[111, 222], project_id=12345)
    # Note: No ImportComment permission has been granted.
    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, project_name='test-project')
    self.services.issue.TestAddIssue(issue1)

    self.request['author'] = {'name': 'user@example.com'}  # 222
    self.request['content'] = 'a comment'
    self.request['updates'] = {
        'owner': 'user@example.com',
        }

    with self.call_should_fail(403):
      self.call_api('issues_comments_insert', self.request)

  def testIssuesCommentsDelete_NoComment(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary',
        issue_id=10001, status='New', owner_id=222, reporter_id=222)
    self.services.issue.TestAddIssue(issue1)
    self.request['commentId'] = 1
    with self.call_should_fail(404):
      self.call_api('issues_comments_delete', self.request)

  def testIssuesCommentsDelete_NoDeletePermission(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary',
        issue_id=10001, status='New', owner_id=222, reporter_id=222)
    self.services.issue.TestAddIssue(issue1)
    self.request['commentId'] = 0
    with self.call_should_fail(403):
      self.call_api('issues_comments_delete', self.request)

  def testIssuesCommentsDelete_DeleteUndelete(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    issue1 = fake.MakeTestIssue(
        project_id=12345, local_id=1, summary='test summary',
        issue_id=10001, status='New', owner_id=222, reporter_id=111)
    self.services.issue.TestAddIssue(issue1)
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=111,
        content='this is a comment',
        timestamp=1437700000)
    self.services.issue.TestAddComment(comment, 1)
    self.request['commentId'] = 1

    comments = self.services.issue.GetCommentsForIssue(None, 10001)

    self.call_api('issues_comments_delete', self.request)
    self.assertEqual(111, comments[1].deleted_by)

    self.call_api('issues_comments_undelete', self.request)
    self.assertIsNone(comments[1].deleted_by)

  def approvalRequest(self, approval, request_fields=None, comment=None,
                      issue_labels=None):
    request = {'userId': 'user@example.com',
               'requester': 'requester@example.com',
               'projectId': 'test-project',
               'issueId': 1,
               'approvalName': 'Legal-Review',
               'sendEmail': False,
    }
    if request_fields:
      request.update(request_fields)

    self.SetUpFieldDefs(
        1, 12345, 'Legal-Review', tracker_pb2.FieldTypes.APPROVAL_TYPE)

    issue1 = fake.MakeTestIssue(
        12345, 1, 'Issue 1', 'New', 222, approval_values=[approval],
        labels=issue_labels)
    self.services.issue.TestAddIssue(issue1)

    self.services.issue.DeltaUpdateIssueApproval = Mock(return_value=comment)

    self.mock(api_svc_v1.MonorailApi, 'mar_factory',
              lambda x, y, z: FakeMonorailApiRequest(
                  request, self.services))
    return request, issue1

  def getFakeComments(self):
    return [
        tracker_pb2.IssueComment(
            id=123, issue_id=1234501, project_id=12345, user_id=111,
            content='1st comment', timestamp=1437700000, approval_id=1),
        tracker_pb2.IssueComment(
            id=223, issue_id=1234501, project_id=12345, user_id=111,
            content='2nd comment', timestamp=1437700000, approval_id=2),
        tracker_pb2.IssueComment(
            id=323, issue_id=1234501, project_id=12345, user_id=111,
            content='3rd comment', timestamp=1437700000, approval_id=1,
            is_description=True),
        tracker_pb2.IssueComment(
            id=423, issue_id=1234501, project_id=12345, user_id=111,
            content='4th comment', timestamp=1437700000)]

  def testApprovalsCommentsList_NoViewPermission(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(approval_id=1)
    request, _issue = self.approvalRequest(
        approval, issue_labels=['Restrict-View-Google'])

    with self.call_should_fail(403):
      self.call_api('approvals_comments_list', request)

  def testApprovalsCommentsList_NoApprovalFound(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(approval_id=1)
    request, _issue = self.approvalRequest(approval)
    self.config.field_defs = []  # empty field_defs of approval fd

    with self.call_should_fail(400):
      self.call_api('approvals_comments_list', request)

  def testApprovalsCommentsList(self):
    """Get comments of requested issue approval."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222], project_id=12345)
    self.services.issue.GetCommentsForIssue = Mock(
        return_value=self.getFakeComments())

    approval = tracker_pb2.ApprovalValue(approval_id=1)
    request, _issue = self.approvalRequest(approval)

    response = self.call_api('approvals_comments_list', request).json_body
    self.assertEqual(response['kind'], 'monorail#approvalCommentList')
    self.assertEqual(response['totalResults'], 2)
    self.assertEqual(len(response['items']), 2)

  def testApprovalsCommentsList_MaxResults(self):
    """get comments of requested issue approval with maxResults."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222], project_id=12345)
    self.services.issue.GetCommentsForIssue = Mock(
        return_value=self.getFakeComments())

    approval = tracker_pb2.ApprovalValue(approval_id=1)
    request, _issue = self.approvalRequest(
        approval, request_fields={'maxResults': 1})

    response = self.call_api('approvals_comments_list', request).json_body
    self.assertEqual(response['kind'], 'monorail#approvalCommentList')
    self.assertEqual(response['totalResults'], 2)
    self.assertEqual(len(response['items']), 1)
    self.assertEqual(response['items'][0]['content'], '1st comment')

  @patch('testing.fake.IssueService.GetCommentsForIssue')
  def testApprovalsCommentsList_StartIndex(self, mockGetComments):
    """get comments of requested issue approval with maxResults."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222], project_id=12345)
    mockGetComments.return_value = self.getFakeComments()

    approval = tracker_pb2.ApprovalValue(approval_id=1)
    request, _issue = self.approvalRequest(
        approval, request_fields={'startIndex': 1})

    response = self.call_api('approvals_comments_list', request).json_body
    self.assertEqual(response['kind'], 'monorail#approvalCommentList')
    self.assertEqual(response['totalResults'], 2)
    self.assertEqual(len(response['items']), 1)
    self.assertEqual(response['items'][0]['content'], '3rd comment')

  def testApprovalsCommentsInsert_NoCommentPermission(self):
    """No permission to comment on an issue, including approvals."""

    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        access=project_pb2.ProjectAccess.MEMBERS_ONLY,
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(approval_id=1)
    request, _issue = self.approvalRequest(approval)

    with self.call_should_fail(403):
      self.call_api('approvals_comments_insert', request)

  def testApprovalsCommentsInsert_NoApprovalDefFound(self):
    """No approval with approvalName found."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(approval_id=1)
    request, _issue = self.approvalRequest(approval)
    self.config.field_defs = []

    with self.call_should_fail(400):
      self.call_api('approvals_comments_insert', request)

    # Test wrong field_type is also caught.
    self.SetUpFieldDefs(
        1, 12345, 'Legal-Review', tracker_pb2.FieldTypes.STR_TYPE)
    with self.call_should_fail(400):
      self.call_api('approvals_comments_insert', request)

  def testApprovalscommentsInsert_NoIssueFound(self):
    """No issue found in project."""
    request = {'userId': 'user@example.com',
               'requester': 'requester@example.com',
               'projectId': 'test-project',
               'issueId': 1,
               'approvalName': 'Legal-Review',
    }
    # No issue created.
    with self.call_should_fail(400):
      self.call_api('approvals_comments_insert', request)

  def testApprovalsCommentsInsert_NoIssueApprovalFound(self):
    """No approval with the given name found in the issue."""

    request = {'userId': 'user@example.com',
               'requester': 'requester@example.com',
               'projectId': 'test-project',
               'issueId': 1,
               'approvalName': 'Legal-Review',
               'sendEmail': False,
    }

    self.SetUpFieldDefs(
        1, 12345, 'Legal-Review', tracker_pb2.FieldTypes.APPROVAL_TYPE)

    # issue 1 does not contain the Legal-Review approval.
    issue1 = fake.MakeTestIssue(12345, 1, 'Issue 1', 'New', 222)
    self.services.issue.TestAddIssue(issue1)

    with self.call_should_fail(400):
      self.call_api('approvals_comments_insert', request)

  def testApprovalsCommentsInsert_FieldValueChanges_NotFound(self):
    """Approval's subfield value not found."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    approval = tracker_pb2.ApprovalValue(approval_id=1)

    request, _issue = self.approvalRequest(
        approval,
        request_fields={
            'approvalUpdates': {
                'fieldValues': [
                    {'fieldName': 'DoesNotExist', 'fieldValue': 'cow'}]
            },
        })
    with self.call_should_fail(400):
      self.call_api('approvals_comments_insert', request)

    # Test field belongs to another approval
    self.config.field_defs.append(
        tracker_bizobj.MakeFieldDef(
            2, 12345, 'DoesNotExist', tracker_pb2.FieldTypes.STR_TYPE,
            '', '', False, False, False, None, None, None, False,
            None, '', tracker_pb2.NotifyTriggers.NEVER, 'no_action',
            'parent approval is wrong', False, approval_id=4))
    with self.call_should_fail(400):
      self.call_api('approvals_comments_insert', request)

  @patch('time.time')
  def testApprovalCommentsInsert_FieldValueChanges(self, mock_time):
    """Field value changes are properly processed."""
    test_time = 6789
    mock_time.return_value = test_time
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=111,
        content='cows moo',
        timestamp=143770000)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222], project_id=12345)
    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[444])

    request, issue = self.approvalRequest(
        approval,
        request_fields={'approvalUpdates': {
            'fieldValues': [
                {'fieldName': 'CowLayerName', 'fieldValue': 'cow'},
                {'fieldName': 'CowType', 'fieldValue': 'skim'},
                {'fieldName': 'CowType', 'fieldValue': 'milk'},
                {'fieldName': 'CowType', 'fieldValue': 'chocolate',
                 'operator': 'remove'}]
        }},
        comment=comment)
    self.config.field_defs.extend(
        [tracker_bizobj.MakeFieldDef(
            2, 12345, 'CowLayerName', tracker_pb2.FieldTypes.STR_TYPE,
            '', '', False, False, False, None, None, None, False,
            None, '', tracker_pb2.NotifyTriggers.NEVER, 'no_action',
            'sub field value of approval 1', False, approval_id=1),
        tracker_bizobj.MakeFieldDef(
            3, 12345, 'CowType', tracker_pb2.FieldTypes.ENUM_TYPE,
            '', '', False, False, True, None, None, None, False,
            None, '', tracker_pb2.NotifyTriggers.NEVER, 'no_action',
            'enum sub field value of approval 1', False, approval_id=1)])

    response = self.call_api('approvals_comments_insert', request).json_body
    fvs_add = [tracker_bizobj.MakeFieldValue(
        2, None, 'cow', None, None, None, False)]
    labels_add = ['CowType-skim', 'CowType-milk']
    labels_remove = ['CowType-chocolate']
    approval_delta = tracker_bizobj.MakeApprovalDelta(
        None, 111, [], [], fvs_add, [], [],
        labels_add, labels_remove, set_on=test_time)
    self.services.issue.DeltaUpdateIssueApproval.assert_called_with(
        None, 111, self.config, issue, approval, approval_delta,
        comment_content=None, is_description=None)
    self.assertEqual(response['content'], comment.content)

  @patch('time.time')
  def testApprovalsCommentsInsert_StatusChanges_Normal(self, mock_time):
    test_time = 6789
    mock_time.return_value = test_time
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=111,  # requester
        content='this is a comment',
        timestamp=1437700000,
        amendments=[tracker_bizobj.MakeApprovalStatusAmendment(
            tracker_pb2.ApprovalStatus.REVIEW_REQUESTED)])
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222], project_id=12345)
    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[444],
        status=tracker_pb2.ApprovalStatus.NOT_SET)

    request, issue = self.approvalRequest(
        approval,
        request_fields={'approvalUpdates': {'status': 'reviewRequested'}},
        comment=comment)
    response = self.call_api('approvals_comments_insert', request).json_body
    approval_delta = tracker_bizobj.MakeApprovalDelta(
        tracker_pb2.ApprovalStatus.REVIEW_REQUESTED, 111, [], [], [], [], [],
        [], [], set_on=test_time)
    self.services.issue.DeltaUpdateIssueApproval.assert_called_with(
        None, 111, self.config, issue, approval, approval_delta,
        comment_content=None, is_description=None)

    self.assertEqual(response['author']['name'], 'requester@example.com')
    self.assertEqual(response['content'], comment.content)
    self.assertTrue(response['canDelete'])
    self.assertEqual(response['approvalUpdates'],
                     {'kind': 'monorail#approvalCommentUpdate',
                      'status': 'reviewRequested'})

  def testApprovalsCommentsInsert_StatusChanges_NoPerms(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[444],
        status=tracker_pb2.ApprovalStatus.NOT_SET)
    request, _issue = self.approvalRequest(
        approval,
        request_fields={'approvalUpdates': {'status': 'approved'}})
    with self.call_should_fail(403):
      self.call_api('approvals_comments_insert', request)

  @patch('time.time')
  def testApprovalsCommentsInsert_StatusChanges_ApproverPerms(self, mock_time):
    test_time = 6789
    mock_time.return_value = test_time
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=1234501,
        project_id=12345, user_id=111,
        content='this is a comment',
        timestamp=1437700000,
        amendments=[tracker_bizobj.MakeApprovalStatusAmendment(
            tracker_pb2.ApprovalStatus.NOT_APPROVED)])
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[111],  # requester
        status=tracker_pb2.ApprovalStatus.NOT_SET)
    request, issue = self.approvalRequest(
        approval,
        request_fields={'approvalUpdates': {'status': 'notApproved'}},
        comment=comment)
    response = self.call_api('approvals_comments_insert', request).json_body

    approval_delta = tracker_bizobj.MakeApprovalDelta(
        tracker_pb2.ApprovalStatus.NOT_APPROVED, 111, [], [], [], [], [],
        [], [], set_on=test_time)
    self.services.issue.DeltaUpdateIssueApproval.assert_called_with(
        None, 111, self.config, issue, approval, approval_delta,
        comment_content=None, is_description=None)
    self.assertEqual(response['author']['name'], 'requester@example.com')
    self.assertEqual(response['content'], comment.content)
    self.assertTrue(response['canDelete'])
    self.assertEqual(response['approvalUpdates'],
                     {'kind': 'monorail#approvalCommentUpdate',
                      'status': 'notApproved'})

  def testApprovalsCommentsInsert_ApproverChanges_NoPerms(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[444],
        status=tracker_pb2.ApprovalStatus.NOT_SET)
    request, _issue = self.approvalRequest(
        approval,
        request_fields={'approvalUpdates': {'approvers': 'someone@test.com'}})
    with self.call_should_fail(403):
      self.call_api('approvals_comments_insert', request)

  @patch('time.time')
  def testApprovalsCommentsInsert_ApproverChanges_ApproverPerms(
      self, mock_time):
    test_time = 6789
    mock_time.return_value = test_time
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=1234501,
        project_id=12345, user_id=111,
        content='this is a comment',
        timestamp=1437700000,
        amendments=[tracker_bizobj.MakeApprovalApproversAmendment(
            [222], [123])])
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[111],  # requester
        status=tracker_pb2.ApprovalStatus.NOT_SET)
    request, issue = self.approvalRequest(
        approval,
        request_fields={
            'approvalUpdates':
            {'approvers': ['user@example.com', '-group@example.com']}},
        comment=comment)
    response = self.call_api('approvals_comments_insert', request).json_body

    approval_delta = tracker_bizobj.MakeApprovalDelta(
        None, 111, [222], [123], [], [], [], [], [], set_on=test_time)
    self.services.issue.DeltaUpdateIssueApproval.assert_called_with(
        None, 111, self.config, issue, approval, approval_delta,
        comment_content=None, is_description=None)
    self.assertEqual(response['author']['name'], 'requester@example.com')
    self.assertEqual(response['content'], comment.content)
    self.assertTrue(response['canDelete'])
    self.assertEqual(response['approvalUpdates'],
                     {'kind': 'monorail#approvalCommentUpdate',
                      'approvers': ['user@example.com', '-group@example.com']})

  @patch('time.time')
  def testApprovalsCommentsInsert_IsSurvey(self, mock_time):
    test_time = 6789
    mock_time.return_value = test_time
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=111,
        content='this is a comment',
        timestamp=1437700000)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[111],  # requester
        status=tracker_pb2.ApprovalStatus.NOT_SET)
    request, issue = self.approvalRequest(
        approval,
        request_fields={'content': 'updated survey', 'is_description': True},
        comment=comment)
    response = self.call_api('approvals_comments_insert', request).json_body

    approval_delta = tracker_bizobj.MakeApprovalDelta(
        None, 111, [], [], [], [], [], [], [], set_on=test_time)
    self.services.issue.DeltaUpdateIssueApproval.assert_called_with(
        None, 111, self.config, issue, approval, approval_delta,
        comment_content='updated survey', is_description=True)
    self.assertEqual(response['author']['name'], 'requester@example.com')
    self.assertTrue(response['canDelete'])

  @patch('time.time')
  @patch('features.send_notifications.PrepareAndSendApprovalChangeNotification')
  def testApprovalsCommentsInsert_SendEmail(
      self, mockPrepareAndSend, mock_time,):
    test_time = 6789
    mock_time.return_value = test_time
    comment = tracker_pb2.IssueComment(
        id=123, issue_id=10001,
        project_id=12345, user_id=111,
        content='this is a comment',
        timestamp=1437700000)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)

    approval = tracker_pb2.ApprovalValue(
        approval_id=1, approver_ids=[111],  # requester
        status=tracker_pb2.ApprovalStatus.NOT_SET)
    request, issue = self.approvalRequest(
        approval,
        request_fields={'content': comment.content, 'sendEmail': True},
        comment=comment)

    response = self.call_api('approvals_comments_insert', request).json_body

    mockPrepareAndSend.assert_called_with(
        issue.issue_id, approval.approval_id, ANY, comment.id, send_email=True)

    approval_delta = tracker_bizobj.MakeApprovalDelta(
        None, 111, [], [], [], [], [], [], [], set_on=test_time)
    self.services.issue.DeltaUpdateIssueApproval.assert_called_with(
        None, 111, self.config, issue, approval, approval_delta,
        comment_content=comment.content, is_description=None)
    self.assertEqual(response['author']['name'], 'requester@example.com')
    self.assertTrue(response['canDelete'])

  def testGroupsSettingsList_AllSettings(self):
    resp = self.call_api('groups_settings_list', self.request).json_body
    all_settings = resp['groupSettings']
    self.assertEqual(1, len(all_settings))
    self.assertEqual('group@example.com', all_settings[0]['groupName'])

  def testGroupsSettingsList_ImportedSettings(self):
    self.services.user.TestAddUser('imported@example.com', 234)
    self.services.usergroup.TestAddGroupSettings(
        234, 'imported@example.com', external_group_type='mdb')
    self.request['importedGroupsOnly'] = True
    resp = self.call_api('groups_settings_list', self.request).json_body
    all_settings = resp['groupSettings']
    self.assertEqual(1, len(all_settings))
    self.assertEqual('imported@example.com', all_settings[0]['groupName'])

  def testGroupsCreate_NoPermission(self):
    self.request['groupName'] = 'group'
    with self.call_should_fail(403):
      self.call_api('groups_create', self.request)

  def SetUpGroupRequest(self, group_name, who_can_view_members='MEMBERS',
                        ext_group_type=None, perms=None,
                        requester='requester@example.com'):
    request = {
        'groupName': group_name,
        'requester': requester,
        'who_can_view_members': who_can_view_members,
        'ext_group_type': ext_group_type}
    self.request.pop("userId", None)
    self.mock(api_svc_v1.MonorailApi, 'mar_factory',
              lambda x, y, z: FakeMonorailApiRequest(
                  request, self.services, perms=perms))
    return request

  def testGroupsCreate_Normal(self):
    request = self.SetUpGroupRequest('newgroup@example.com', 'MEMBERS',
                                     'MDB', permissions.ADMIN_PERMISSIONSET)

    resp = self.call_api('groups_create', request).json_body
    self.assertIn('groupID', resp)

  def testGroupsGet_NoPermission(self):
    request = self.SetUpGroupRequest('group@example.com')
    with self.call_should_fail(403):
      self.call_api('groups_get', request)

  def testGroupsGet_Normal(self):
    request = self.SetUpGroupRequest('group@example.com',
                                     perms=permissions.ADMIN_PERMISSIONSET)
    self.services.usergroup.TestAddMembers(123, [111], 'member')
    self.services.usergroup.TestAddMembers(123, [222], 'owner')
    resp = self.call_api('groups_get', request).json_body
    self.assertEqual(123, resp['groupID'])
    self.assertEqual(['requester@example.com'], resp['groupMembers'])
    self.assertEqual(['user@example.com'], resp['groupOwners'])
    self.assertEqual('group@example.com', resp['groupSettings']['groupName'])

  def testGroupsUpdate_NoPermission(self):
    request = self.SetUpGroupRequest('group@example.com')
    with self.call_should_fail(403):
      self.call_api('groups_update', request)

  def testGroupsUpdate_Normal(self):
    request = self.SetUpGroupRequest('group@example.com')
    request = self.SetUpGroupRequest('group@example.com',
                                     perms=permissions.ADMIN_PERMISSIONSET)
    request['last_sync_time'] = 123456789
    request['groupOwners'] = ['requester@example.com']
    request['groupMembers'] = ['user@example.com']
    resp = self.call_api('groups_update', request).json_body
    self.assertFalse(resp.get('error'))

  def testComponentsList(self):
    """Get components for a project."""
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    resp = self.call_api('components_list', self.request).json_body

    self.assertEqual(1, len(resp['components']))
    cd = resp['components'][0]
    self.assertEqual(1, cd['componentId'])
    self.assertEqual('API', cd['componentPath'])
    self.assertEqual(1, cd['componentId'])
    self.assertEqual('test-project', cd['projectName'])

  def testComponentsCreate_NoPermission(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    cd_dict = {
      'componentName': 'Test'}
    self.request.update(cd_dict)

    with self.call_should_fail(403):
      self.call_api('components_create', self.request)

  def testComponentsCreate_Invalid(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    # Component with invalid name
    cd_dict = {
      'componentName': 'c>d>e'}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_create', self.request)

    # Name already in use
    cd_dict = {
      'componentName': 'API'}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_create', self.request)

    # Parent component does not exist
    cd_dict = {
      'componentName': 'test',
      'parentPath': 'NotExist'}
    self.request.update(cd_dict)
    with self.call_should_fail(404):
      self.call_api('components_create', self.request)


  def testComponentsCreate_Normal(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    cd_dict = {
      'componentName': 'Test',
      'description':'test comp',
      'cc': ['requester@example.com', '']}
    self.request.update(cd_dict)

    resp = self.call_api('components_create', self.request).json_body
    self.assertEqual('test comp', resp['description'])
    self.assertEqual('requester@example.com', resp['creator'])
    self.assertEqual([u'requester@example.com'], resp['cc'])
    self.assertEqual('Test', resp['componentPath'])

    cd_dict = {
      'componentName': 'TestChild',
      'parentPath': 'API'}
    self.request.update(cd_dict)
    resp = self.call_api('components_create', self.request).json_body

    self.assertEqual('API>TestChild', resp['componentPath'])

  def testComponentsDelete_Invalid(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    # Fail to delete a non-existent component
    cd_dict = {
      'componentPath': 'NotExist'}
    self.request.update(cd_dict)
    with self.call_should_fail(404):
      self.call_api('components_delete', self.request)

    # The user has no permission to delete component
    cd_dict = {
      'componentPath': 'API'}
    self.request.update(cd_dict)
    with self.call_should_fail(403):
      self.call_api('components_delete', self.request)

    # The user tries to delete component that had subcomponents
    self.services.project.TestAddProject(
        'test-project2', owner_ids=[111],
        project_id=123456)
    self.SetUpComponents(123456, 1, 'Parent')
    self.SetUpComponents(123456, 2, 'Parent>Child')
    cd_dict = {
      'componentPath': 'Parent',
      'projectId': 'test-project2',}
    self.request.update(cd_dict)
    with self.call_should_fail(403):
      self.call_api('components_delete', self.request)

  def testComponentsDelete_Normal(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')

    cd_dict = {
      'componentPath': 'API'}
    self.request.update(cd_dict)
    _ = self.call_api('components_delete', self.request).json_body
    self.assertEqual(0, len(self.config.component_defs))

  def testComponentsUpdate_Invalid(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[222],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    self.SetUpComponents(12345, 2, 'Test', admin_ids=[111])

    # Fail to update a non-existent component
    cd_dict = {
      'componentPath': 'NotExist'}
    self.request.update(cd_dict)
    with self.call_should_fail(404):
      self.call_api('components_update', self.request)

    # The user has no permission to edit component
    cd_dict = {
      'componentPath': 'API'}
    self.request.update(cd_dict)
    with self.call_should_fail(403):
      self.call_api('components_update', self.request)

    # The user tries an invalid component name
    cd_dict = {
      'componentPath': 'Test',
      'updates': [{'field': 'LEAF_NAME', 'leafName': 'c>e'}]}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_update', self.request)

    # The user tries a name already in use
    cd_dict = {
      'componentPath': 'Test',
      'updates': [{'field': 'LEAF_NAME', 'leafName': 'API'}]}
    self.request.update(cd_dict)
    with self.call_should_fail(400):
      self.call_api('components_update', self.request)

  def testComponentsUpdate_Normal(self):
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111],
        project_id=12345)
    self.SetUpComponents(12345, 1, 'API')
    self.SetUpComponents(12345, 2, 'Parent')
    self.SetUpComponents(12345, 3, 'Parent>Child')

    cd_dict = {
      'componentPath': 'API',
      'updates': [
          {'field': 'DESCRIPTION', 'description': ''},
          {'field': 'CC', 'cc': [
              'requester@example.com', 'user@example.com', '', ' ']},
          {'field': 'DEPRECATED', 'deprecated': True}]}
    self.request.update(cd_dict)
    _ = self.call_api('components_update', self.request).json_body
    component_def = tracker_bizobj.FindComponentDef(
        'API', self.config)
    self.assertIsNotNone(component_def)
    self.assertEqual('', component_def.docstring)
    self.assertItemsEqual([111, 222], component_def.cc_ids)
    self.assertTrue(component_def.deprecated)

    cd_dict = {
      'componentPath': 'Parent',
      'updates': [
          {'field': 'LEAF_NAME', 'leafName': 'NewParent'}]}
    self.request.update(cd_dict)
    _ = self.call_api('components_update', self.request).json_body
    cd_parent = tracker_bizobj.FindComponentDef(
        'NewParent', self.config)
    cd_child = tracker_bizobj.FindComponentDef(
        'NewParent>Child', self.config)
    self.assertIsNotNone(cd_parent)
    self.assertIsNotNone(cd_child)


class RequestMock(object):

  def __init__(self):
    self.projectId = None
    self.issueId = None


class RequesterMock(object):

  def __init__(self, email=None):
    self._email = email

  def email(self):
    return self._email


class AllBaseChecksTest(unittest.TestCase):

  def setUp(self):
    self.services = MakeFakeServiceManager()
    self.services.user.TestAddUser('test@example.com', 111)
    self.user_2 = self.services.user.TestAddUser('test@google.com', 222)
    self.services.project.TestAddProject(
        'test-project', owner_ids=[111], project_id=123,
        access=project_pb2.ProjectAccess.MEMBERS_ONLY)
    self.auth_client_ids = ['123456789.apps.googleusercontent.com']
    oauth.get_client_id = Mock(return_value=self.auth_client_ids[0])
    oauth.get_current_user = Mock(
        return_value=RequesterMock(email='test@example.com'))
    oauth.get_authorized_scopes = Mock()

  def testUnauthorizedRequester(self):
    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(None, None, None, None, [], [])

  def testNoUser(self):
    requester = RequesterMock(email='notexist@example.com')
    with self.assertRaises(exceptions.NoSuchUserException):
      api_svc_v1.api_base_checks(
          None, requester, self.services, None, self.auth_client_ids, [])

  def testAllowedDomain_MonorailScope(self):
    oauth.get_authorized_scopes.return_value = [
        framework_constants.MONORAIL_SCOPE]
    oauth.get_current_user.return_value = RequesterMock(
        email=self.user_2.email)
    whitelisted_client_ids = []
    whitelisted_emails = []
    client_id, email = api_svc_v1.api_base_checks(
        None, None, self.services, None,
        whitelisted_client_ids, whitelisted_emails)
    self.assertEqual(client_id, self.auth_client_ids[0])
    self.assertEqual(email, self.user_2.email)

  def testAllowedDomain_NoMonorailScope(self):
    oauth.get_authorized_scopes.return_value = []
    oauth.get_current_user.return_value = RequesterMock(
        email=self.user_2.email)
    whitelisted_client_ids = []
    whitelisted_emails = []
    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(None, None, self.services, None,
                                 whitelisted_client_ids, whitelisted_emails)

  def testAllowedDomain_BadEmail(self):
    oauth.get_authorized_scopes.return_value = [
        framework_constants.MONORAIL_SCOPE]
    oauth.get_current_user.return_value = RequesterMock(
        email='chicken@chicken.test')
    whitelisted_client_ids = []
    whitelisted_emails = []
    self.services.user.TestAddUser('chicken@chicken.test', 333)
    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(None, None, self.services, None,
                                 whitelisted_client_ids, whitelisted_emails)

  def testNoOauthUser(self):
    oauth.get_current_user.side_effect = oauth.Error()
    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(
          None, None, self.services, None, [], [])

  def testBannedUser(self):
    banned_email = 'banned@example.com'
    self.services.user.TestAddUser(banned_email, 222, banned=True)
    requester = RequesterMock(email=banned_email)
    with self.assertRaises(permissions.BannedUserException):
      api_svc_v1.api_base_checks(
          None, requester, self.services, None, self.auth_client_ids, [])

  def testNoProject(self):
    request = RequestMock()
    request.projectId = 'notexist-project'
    requester = RequesterMock(email='test@example.com')
    with self.assertRaises(exceptions.NoSuchProjectException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testNonLiveProject(self):
    archived_project = 'archived-project'
    self.services.project.TestAddProject(
        archived_project, owner_ids=[111],
        state=project_pb2.ProjectState.ARCHIVED)
    request = RequestMock()
    request.projectId = archived_project
    requester = RequesterMock(email='test@example.com')
    with self.assertRaises(permissions.PermissionException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testNoViewProjectPermission(self):
    nonmember_email = 'nonmember@example.com'
    self.services.user.TestAddUser(nonmember_email, 222)
    requester = RequesterMock(email=nonmember_email)
    request = RequestMock()
    request.projectId = 'test-project'
    with self.assertRaises(permissions.PermissionException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testAllPass(self):
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    api_svc_v1.api_base_checks(
        request, requester, self.services, None, self.auth_client_ids, [])

  def testNoIssue(self):
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    request.issueId = 12345
    with self.assertRaises(exceptions.NoSuchIssueException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testNoViewIssuePermission(self):
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    request.issueId = 1
    issue1 = fake.MakeTestIssue(
        project_id=123, local_id=1, summary='test summary',
        status='New', owner_id=111, reporter_id=111)
    issue1.deleted = True
    self.services.issue.TestAddIssue(issue1)
    with self.assertRaises(permissions.PermissionException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, self.auth_client_ids, [])

  def testAnonymousClients(self):
    # Some clients specifically pass "anonymous" as the client ID.
    oauth.get_client_id = Mock(return_value='anonymous')
    requester = RequesterMock(email='test@example.com')
    request = RequestMock()
    request.projectId = 'test-project'
    api_svc_v1.api_base_checks(
        request, requester, self.services, None, [], ['test@example.com'])

    # Any client_id is OK if the email is whitelisted.
    oauth.get_client_id = Mock(return_value='anything')
    api_svc_v1.api_base_checks(
        request, requester, self.services, None, [], ['test@example.com'])

    # Reject request when neither client ID nor email is whitelisted.
    with self.assertRaises(endpoints.UnauthorizedException):
      api_svc_v1.api_base_checks(
          request, requester, self.services, None, [], [])
