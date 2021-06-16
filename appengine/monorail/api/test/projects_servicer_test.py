# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the projects servicer."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
from mock import patch

from components.prpc import codes
from components.prpc import context
from components.prpc import server

from api import projects_servicer
from api.api_proto import common_pb2
from api.api_proto import issue_objects_pb2
from api.api_proto import project_objects_pb2
from api.api_proto import projects_pb2
from framework import authdata
from framework import exceptions
from framework import framework_constants
from framework import monorailcontext
from framework import permissions
from proto import tracker_pb2
from proto import project_pb2
from tracker import tracker_bizobj
from tracker import tracker_constants
from testing import fake
from testing import testing_helpers
from services import service_manager


class ProjectsServicerTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService(),
        project_star=fake.ProjectStarService(),
        features=fake.FeaturesService())

    self.admin = self.services.user.TestAddUser('admin@example.com', 123)
    self.admin.is_site_admin = True
    self.owner = self.services.user.TestAddUser('owner@example.com', 111)
    self.services.user.TestAddUser('user_222@example.com', 222)
    self.services.user.TestAddUser('user_333@example.com', 333)
    self.services.user.TestAddUser('user_444@example.com', 444)
    self.services.user.TestAddUser('user_666@example.com', 666)

    # User group 888 has members: user_555 and proj@monorail.com
    self.services.user.TestAddUser('group888@googlegroups.com', 888)
    self.services.usergroup.TestAddGroupSettings(
        888, 'group888@googlegroups.com')
    self.services.usergroup.TestAddMembers(888, [555, 1001])

    # User group 999 has members: user_111 and user_444
    self.services.user.TestAddUser('group999@googlegroups.com', 999)
    self.services.usergroup.TestAddGroupSettings(
        999, 'group999@googlegroups.com')
    self.services.usergroup.TestAddMembers(999, [111, 444])

    # User group 777 has members: user_666 and group 999.
    self.services.user.TestAddUser('group777@googlegroups.com', 777)
    self.services.usergroup.TestAddGroupSettings(
        777, 'group777@googlegroups.com')
    self.services.usergroup.TestAddMembers(777, [666, 999])

    self.project = self.services.project.TestAddProject(
        'proj', project_id=789)
    self.project.owner_ids.extend([111])
    self.project.committer_ids.extend([222])
    self.project.contributor_ids.extend([333])
    self.projects_svcr = projects_servicer.ProjectsServicer(
        self.services, make_rate_limiter=False)
    self.prpc_context = context.ServicerContext()
    self.prpc_context.set_code(codes.StatusCode.OK)

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.projects_svcr, *args, **kwargs)

  def testListProjects_Normal(self):
    """We can get a list of all projects on the site."""
    request = projects_pb2.ListProjectsRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.projects_svcr.ListProjects, mc, request)
    self.assertEqual(2, len(response.projects))

  def testGetConfig_Normal(self):
    """We can get a project config."""
    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.projects_svcr.GetConfig, mc, request)
    self.assertEqual('proj', response.project_name)

  def testGetConfig_NoSuchProject(self):
    """We reject a request to get a config for a non-existent project."""
    request = projects_pb2.GetConfigRequest(project_name='unknown-proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    with self.assertRaises(exceptions.NoSuchProjectException):
      self.CallWrapped(self.projects_svcr.GetConfig, mc, request)

  def testGetConfig_PermissionDenied(self):
    """We reject a request to get a config for a non-viewable project."""
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    request = projects_pb2.GetConfigRequest(project_name='proj')

    # User is a member of the members-only project.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.projects_svcr.GetConfig, mc, request)
    self.assertEqual('proj', response.project_name)

    # User is not a member of the members-only project.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.projects_svcr.GetConfig, mc, request)

  @patch('businesslogic.work_env.WorkEnv.ListProjectTemplates')
  def testListProjectTemplates_Normal(self, mockListProjectTemplates):
    fd_1 = tracker_pb2.FieldDef(
        field_name='FirstField', field_id=1,
        field_type=tracker_pb2.FieldTypes.STR_TYPE)
    fd_2 = tracker_pb2.FieldDef(
        field_name='LegalApproval', field_id=2,
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    component = tracker_pb2.ComponentDef(component_id=1, path='dude')
    status_def = tracker_pb2.StatusDef(status='New', means_open=True)
    config = tracker_pb2.ProjectIssueConfig(
        project_id=789, field_defs=[fd_1, fd_2], component_defs=[component],
        well_known_statuses=[status_def])
    self.services.config.StoreConfig(self.cnxn, config)
    admin1 = self.services.user.TestAddUser('admin@example.com', 222)
    appr1 = self.services.user.TestAddUser('approver@example.com', 333)
    setter = self.services.user.TestAddUser('setter@example.com', 444)
    template = tracker_pb2.TemplateDef(
        name='Chicken', content='description', summary='summary',
        status='New', admin_ids=[admin1.user_id],
        field_values=[tracker_bizobj.MakeFieldValue(
            fd_1.field_id, None, 'Cow', None, None, None, False)],
        component_ids=[component.component_id],
        approval_values=[tracker_pb2.ApprovalValue(
            approval_id=2, approver_ids=[appr1.user_id],
            setter_id=setter.user_id)])
    mockListProjectTemplates.return_value = [template]

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    request = projects_pb2.ListProjectTemplatesRequest(project_name='proj')
    response = self.CallWrapped(
        self.projects_svcr.ListProjectTemplates, mc, request)
    self.assertEqual(
        response,
        projects_pb2.ListProjectTemplatesResponse(
            templates=[project_objects_pb2.TemplateDef(
                template_name='Chicken',
                content='description',
                summary='summary',
                status_ref=common_pb2.StatusRef(
                    status='New',
                    is_derived=False,
                    means_open=True),
                owner_defaults_to_member=True,
                admin_refs=[
                  common_pb2.UserRef(
                      user_id=admin1.user_id,
                      display_name=testing_helpers.ObscuredEmail(admin1.email),
                      is_derived=False)],
                field_values=[
                  issue_objects_pb2.FieldValue(
                    field_ref=common_pb2.FieldRef(
                        field_id=fd_1.field_id,
                        field_name=fd_1.field_name,
                        type=common_pb2.STR_TYPE),
                    value='Cow')],
                component_refs=[
                    common_pb2.ComponentRef(
                        path=component.path, is_derived=False)],
                approval_values=[
                  issue_objects_pb2.Approval(
                    field_ref=common_pb2.FieldRef(
                        field_id=fd_2.field_id,
                        field_name=fd_2.field_name,
                        type=common_pb2.APPROVAL_TYPE),
                    setter_ref=common_pb2.UserRef(
                        user_id=setter.user_id,
                        display_name=testing_helpers.ObscuredEmail(
                            setter.email)),
                    phase_ref=issue_objects_pb2.PhaseRef(),
                    approver_refs=[common_pb2.UserRef(
                        user_id=appr1.user_id,
                        display_name=testing_helpers.ObscuredEmail(appr1.email),
                        is_derived=False)])],
          )]))

  def testListProjectTemplates_NoProjectName(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    request = projects_pb2.ListProjectTemplatesRequest()
    with self.assertRaises(exceptions.InputException):
      self.CallWrapped(self.projects_svcr.ListProjectTemplates, mc, request)

  def testListProjectTemplates_NoSuchProject(self):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    request = projects_pb2.ListProjectTemplatesRequest(project_name='ghost')
    with self.assertRaises(exceptions.NoSuchProjectException):
      self.CallWrapped(self.projects_svcr.ListProjectTemplates, mc, request)

  def testListProjectTemplates_PermissionDenied(self):
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')
    request = projects_pb2.GetConfigRequest(project_name='proj')
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.projects_svcr.ListProjectTemplates, mc, request)

  def testGetPresentationConfig_Normal(self):
    """Test getting project summary, thumbnail url, custom issue entry, etc."""
    config = tracker_pb2.ProjectIssueConfig(project_id=789)
    self.project.summary = 'project summary'
    config.custom_issue_entry_url = 'issue entry url'
    config.member_default_query = 'default query'
    config.default_col_spec = 'ID Summary'
    config.default_sort_spec = 'Priority Status'
    config.default_x_attr = 'Priority'
    config.default_y_attr = 'Status'
    self.project.revision_url_format = 'revision url format'
    self.services.config.StoreConfig(self.cnxn, config)

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    request = projects_pb2.GetPresentationConfigRequest(project_name='proj')
    response = self.CallWrapped(
        self.projects_svcr.GetPresentationConfig, mc, request)

    self.assertEqual('project summary', response.project_summary)
    self.assertEqual('issue entry url', response.custom_issue_entry_url)
    self.assertEqual('default query', response.default_query)
    self.assertEqual('ID Summary', response.default_col_spec)
    self.assertEqual('Priority Status', response.default_sort_spec)
    self.assertEqual('Priority', response.default_x_attr)
    self.assertEqual('Status', response.default_y_attr)
    self.assertEqual('revision url format', response.revision_url_format)

  def testGetPresentationConfig_SavedQueriesAllowed(self):
    """Only project members or higher can see project saved queries."""
    self.services.features.UpdateCannedQueries(self.cnxn, 789, [
        tracker_pb2.SavedQuery(query_id=101, name='test', query='owner:me'),
        tracker_pb2.SavedQuery(query_id=202, name='hello', query='world')
    ])

    # User 333 is a contributor.
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user_333@example.com')

    request = projects_pb2.GetPresentationConfigRequest(project_name='proj')
    response = self.CallWrapped(self.projects_svcr.GetPresentationConfig, mc,
        request)

    self.assertEqual(2, len(response.saved_queries))

    self.assertEqual(101, response.saved_queries[0].query_id)
    self.assertEqual('test', response.saved_queries[0].name)
    self.assertEqual('owner:me', response.saved_queries[0].query)

    self.assertEqual(202, response.saved_queries[1].query_id)
    self.assertEqual('hello', response.saved_queries[1].name)
    self.assertEqual('world', response.saved_queries[1].query)

  def testGetPresentationConfig_SavedQueriesDenied(self):
    """Only project members or higher can see project saved queries."""
    self.services.features.UpdateCannedQueries(self.cnxn, 789, [
        tracker_pb2.SavedQuery(query_id=101, name='test', query='owner:me'),
        tracker_pb2.SavedQuery(query_id=202, name='hello', query='world')
    ])

    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='nonmember@example.com')

    request = projects_pb2.GetPresentationConfigRequest(project_name='proj')
    response = self.CallWrapped(self.projects_svcr.GetPresentationConfig, mc,
        request)

    self.assertEqual(0, len(response.saved_queries))

  def testGetCustomPermissions_Normal(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111,
            perms=['FooPerm', 'BarPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['BarPerm', 'FooPerm'], response.permissions)

  def testGetCustomPermissions_PermissionsAreDedupped(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111,
            perms=['FooPerm', 'FooPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222,
            perms=['FooPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['FooPerm'], response.permissions)

  def testGetCustomPermissions_PermissionsAreSorted(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111,
            perms=['FooPerm', 'BarPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222,
            perms=['BazPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['BarPerm', 'BazPerm', 'FooPerm'], response.permissions)

  def testGetCustomPermissions_IgnoreStandardPermissions(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111,
            perms=permissions.STANDARD_PERMISSIONS + ['FooPerm'])]

    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual(['FooPerm'], response.permissions)

  def testGetCustomPermissions_NoCustomPermissions(self):
    self.project.extra_perms = []
    request = projects_pb2.GetConfigRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='foo@example.org')
    response = self.CallWrapped(
        self.projects_svcr.GetCustomPermissions, mc, request)
    self.assertEqual([], response.permissions)

  def assertVisibleMembers(self, expected_user_ids, expected_group_ids,
                           requester=None):
    request = projects_pb2.GetVisibleMembersRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=requester)
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.GetVisibleMembers, mc, request)
    self.assertEqual(
        expected_user_ids,
        [user_ref.user_id for user_ref in response.user_refs])
    # Assert that we get the full email address.
    self.assertEqual(
        [self.services.user.LookupUserEmail(self.cnxn, user_id)
         for user_id in expected_user_ids],
        [user_ref.display_name for user_ref in response.user_refs])
    self.assertEqual(
        expected_group_ids,
        [group_ref.user_id for group_ref in response.group_refs])
    # Assert that we get the full email address.
    self.assertEqual(
        [self.services.user.LookupUserEmail(self.cnxn, user_id)
         for user_id in expected_group_ids],
        [group_ref.display_name for group_ref in response.group_refs])
    return response

  def testGetVisibleMembers_Normal(self):
    # Not logged in - Test users have their email addresses obscured to
    # non-project members by default.
    self.assertVisibleMembers([], [])
    # Logged in as non project member
    self.assertVisibleMembers([], [], requester='foo@example.com')
    # Logged in as owner
    self.assertVisibleMembers([111, 222, 333], [],
                              requester='owner@example.com')
    # Logged in as committer
    self.assertVisibleMembers([111, 222, 333], [],
                              requester='user_222@example.com')
    # Logged in as contributor
    self.assertVisibleMembers([111, 222, 333], [],
                              requester='user_333@example.com')

  def testGetVisibleMembers_OnlyOwnersSeeContributors(self):
    self.project.only_owners_see_contributors = True
    # Not logged in
    with self.assertRaises(permissions.PermissionException):
      self.assertVisibleMembers([111, 222], [])
    # Logged in with a non-member
    with self.assertRaises(permissions.PermissionException):
      self.assertVisibleMembers([111, 222], [], requester='foo@example.com')
    # Logged in as owner
    self.assertVisibleMembers([111, 222, 333], [],
                              requester='owner@example.com')
    # Logged in as committer
    self.assertVisibleMembers([111, 222, 333], [],
                              requester='user_222@example.com')
    # Logged in as contributor
    with self.assertRaises(permissions.PermissionException):
      self.assertVisibleMembers(
          [111, 222], [], requester='user_333@example.com')

  def testGetVisibleMembers_MemberIsGroup(self):
    self.project.contributor_ids.extend([999])
    self.assertVisibleMembers([999, 111, 222, 333, 444], [999],
                              requester='owner@example.com')

  def testGetVisibleMembers_AcExclusion(self):
    self.services.project.ac_exclusion_ids[self.project.project_id] = [333]
    self.assertVisibleMembers([111, 222], [], requester='owner@example.com')

  def testGetVisibleMembers_NoExpand(self):
    self.services.project.no_expand_ids[self.project.project_id] = [999]
    self.project.contributor_ids.extend([999])
    self.assertVisibleMembers([999, 111, 222, 333], [999],
                              requester='owner@example.com')

  def testGetVisibleMembers_ObscuredEmails(self):
    # Unobscure the owner's email. Non-project members can see.
    self.services.user.UpdateUserSettings(
        self.cnxn, 111, self.owner, obscure_email=False)

    # Not logged in
    self.assertVisibleMembers([111], [])
    # Logged in as not a project member
    self.assertVisibleMembers([111], [], requester='foo@example.com')
    # Logged in as owner
    self.assertVisibleMembers(
        [111, 222, 333], [], requester='owner@example.com')
    # Logged in as committer
    self.assertVisibleMembers(
        [111, 222, 333], [], requester='user_222@example.com')
    # Logged in as contributor
    self.assertVisibleMembers(
        [111, 222, 333], [], requester='user_333@example.com')

  def testListStatuses(self):
    request = projects_pb2.ListStatusesRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListStatuses, mc, request)
    self.assertFalse(response.restrict_to_known)
    self.assertEqual(
        [('New', True),
         ('Accepted', True),
         ('Started', True),
         ('Fixed', False),
         ('Verified', False),
         ('Invalid', False),
         ('Duplicate', False),
         ('WontFix', False),
         ('Done', False)],
        [(status_def.status, status_def.means_open)
         for status_def in response.status_defs])
    self.assertEqual(
        [('Duplicate', False)],
        [(status_def.status, status_def.means_open)
         for status_def in response.statuses_offer_merge])

  def testListComponents(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Foo', 'Foo Component', True, [],
        [], True, 111, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar', 'Bar Component', False, [],
        [], True, 111, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar>Baz', 'Baz Component',
        False, [], [], True, 111, [])

    request = projects_pb2.ListComponentsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListComponents, mc, request)

    self.assertEqual(
        [project_objects_pb2.ComponentDef(
            path='Foo',
            docstring='Foo Component',
            deprecated=True),
         project_objects_pb2.ComponentDef(
             path='Bar',
             docstring='Bar Component',
             deprecated=False),
         project_objects_pb2.ComponentDef(
             path='Bar>Baz',
             docstring='Baz Component',
             deprecated=False)],
        list(response.component_defs))

  def testListComponents_IncludeAdminInfo(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Foo', 'Foo Component', True, [],
        [], 1234567, 111, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar', 'Bar Component', False, [],
        [], 1234568, 111, [])
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Bar>Baz', 'Baz Component',
        False, [], [], 1234569, 111, [])
    creator_ref = common_pb2.UserRef(
        user_id=111,
        display_name='owner@example.com')

    request = projects_pb2.ListComponentsRequest(
        project_name='proj', include_admin_info=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListComponents, mc, request)

    self.assertEqual(
        [project_objects_pb2.ComponentDef(
            path='Foo',
            docstring='Foo Component',
            deprecated=True,
            created=1234567,
            creator_ref=creator_ref),
         project_objects_pb2.ComponentDef(
             path='Bar',
             docstring='Bar Component',
             deprecated=False,
             created=1234568,
             creator_ref=creator_ref),
         project_objects_pb2.ComponentDef(
             path='Bar>Baz',
             docstring='Baz Component',
             deprecated=False,
             created=1234569,
             creator_ref=creator_ref),
            ],
        list(response.component_defs))

  def AddField(self, name, **kwargs):
    if kwargs.get('needs_perm'):
      kwargs['needs_member'] = True
    kwargs.setdefault('cnxn', self.cnxn)
    kwargs.setdefault('project_id', self.project.project_id)
    kwargs.setdefault('field_name', name)
    kwargs.setdefault('field_type_str', 'USER_TYPE')
    for arg in ('applic_type', 'applic_pred', 'is_required', 'is_niche',
                'is_multivalued', 'min_value', 'max_value', 'regex',
                'needs_member', 'needs_perm', 'grants_perm', 'notify_on',
                'date_action_str', 'docstring'):
      kwargs.setdefault(arg, None)
    for arg in ('admin_ids', 'editor_ids'):
      kwargs.setdefault(arg, [])

    self.services.config.CreateFieldDef(**kwargs)

  def testListFields_Normal(self):
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE)

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    self.assertEqual(
        [111, 222],
        sorted([user_ref.user_id for user_ref in field.user_choices]))
    self.assertEqual(
        ['owner@example.com', 'user_222@example.com'],
        sorted([user_ref.display_name for user_ref in field.user_choices]))

  def testListFields_DontIncludeUserChoices(self):
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE)

    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual(0, len(field.user_choices))

  def testListFields_IncludeAdminInfo(self):
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE, is_niche=True,
                  applic_type='Foo Applic Type')

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_admin_info=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    self.assertEqual(True, field.is_niche)
    self.assertEqual('Foo Applic Type', field.applicable_type)

  def testListFields_EnumFieldChoices(self):
    self.AddField('Type', field_type_str='ENUM_TYPE')

    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Type', field.field_ref.field_name)
    self.assertEqual(
        ['Defect', 'Enhancement', 'Task', 'Other'],
        [label.label for label in field.enum_choices])

  def testListFields_CustomPermission(self):
    self.AddField('Foo Field', needs_perm='FooPerm')
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=111,
            perms=['UnrelatedPerm']),
        project_pb2.Project.ExtraPerms(
            member_id=222,
            perms=['FooPerm'])]

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    self.assertEqual(
        [222],
        sorted([user_ref.user_id for user_ref in field.user_choices]))
    self.assertEqual(
        ['user_222@example.com'],
        sorted([user_ref.display_name for user_ref in field.user_choices]))

  def testListFields_IndirectPermission(self):
    """Test that the permissions of effective ids are also considered."""
    self.AddField('Foo Field', needs_perm='FooPerm')
    self.project.contributor_ids.extend([999])
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=999,
            perms=['FooPerm', 'BarPerm'])]

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    # Users 111 and 444 are members of group 999, which has the needed
    # permission.
    self.assertEqual(
        [111, 444, 999],
        sorted([user_ref.user_id for user_ref in field.user_choices]))
    self.assertEqual(
        ['group999@googlegroups.com', 'owner@example.com',
         'user_444@example.com'],
        sorted([user_ref.display_name for user_ref in field.user_choices]))

  def testListFields_TwiceIndirectPermission(self):
    """Test that only direct memberships are considered."""
    self.AddField('Foo Field', needs_perm='FooPerm')
    self.project.contributor_ids.extend([777])
    self.project.contributor_ids.extend([999])
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=777, perms=['FooPerm', 'BarPerm'])
    ]

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)
    self.assertEqual(
        [666, 777, 999],
        sorted([user_ref.user_id for user_ref in field.user_choices]))
    self.assertEqual(
        [
            'group777@googlegroups.com', 'group999@googlegroups.com',
            'user_666@example.com'
        ], sorted([user_ref.display_name for user_ref in field.user_choices]))

  def testListFields_NoPermissionsNeeded(self):
    self.AddField('Foo Field')

    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(1, len(response.field_defs))
    field = response.field_defs[0]
    self.assertEqual('Foo Field', field.field_ref.field_name)

  def testListFields_MultipleFields(self):
    self.AddField('Bar Field', needs_perm=permissions.VIEW)
    self.AddField('Foo Field', needs_perm=permissions.EDIT_ISSUE)

    request = projects_pb2.ListFieldsRequest(
        project_name='proj', include_user_choices=True)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(2, len(response.field_defs))
    field_defs = sorted(
        response.field_defs, key=lambda field: field.field_ref.field_name)

    self.assertEqual(
        ['Bar Field', 'Foo Field'],
        [field.field_ref.field_name for field in field_defs])
    self.assertEqual(
        [[111, 222, 333],
         [111, 222]],
        [sorted(user_ref.user_id for user_ref in field.user_choices)
         for field in field_defs])
    self.assertEqual(
        [['owner@example.com', 'user_222@example.com', 'user_333@example.com'],
         ['owner@example.com', 'user_222@example.com']],
        [sorted(user_ref.display_name for user_ref in field.user_choices)
         for field in field_defs])

  def testListFields_NoFields(self):
    request = projects_pb2.ListFieldsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.ListFields, mc, request)

    self.assertEqual(0, len(response.field_defs))

  def testGetLabelOptions_Normal(self):
    request = projects_pb2.GetLabelOptionsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetLabelOptions, mc, request)

    expected_label_names = [
        label[0] for label in tracker_constants.DEFAULT_WELL_KNOWN_LABELS]
    expected_label_names += [
        'Restrict-View-EditIssue', 'Restrict-AddIssueComment-EditIssue',
        'Restrict-View-CoreTeam']
    self.assertEqual(
        sorted(expected_label_names),
        sorted(label.label for label in response.label_options))

  def testGetLabelOptions_CustomPermissions(self):
    self.project.extra_perms = [
        project_pb2.Project.ExtraPerms(
            member_id=222,
            perms=['FooPerm', 'BarPerm'])]

    request = projects_pb2.GetLabelOptionsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetLabelOptions, mc, request)

    expected_label_names = [
        label[0] for label in tracker_constants.DEFAULT_WELL_KNOWN_LABELS]
    expected_label_names += [
        'Restrict-View-EditIssue', 'Restrict-AddIssueComment-EditIssue']
    expected_label_names += [
        'Restrict-%s-%s' % (std_perm, custom_perm)
        for std_perm in permissions.STANDARD_ISSUE_PERMISSIONS
        for custom_perm in ('BarPerm', 'FooPerm')]

    self.assertEqual(
        sorted(expected_label_names),
        sorted(label.label for label in response.label_options))

  def testGetLabelOptions_FieldMasksLabel(self):
    self.AddField('Type', field_type_str='ENUM_TYPE')

    request = projects_pb2.GetLabelOptionsRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetLabelOptions, mc, request)

    expected_label_names = [
        label[0] for label in tracker_constants.DEFAULT_WELL_KNOWN_LABELS
        if not label[0].startswith('Type-')
    ]
    expected_label_names += [
        'Restrict-View-EditIssue', 'Restrict-AddIssueComment-EditIssue',
        'Restrict-View-CoreTeam']
    self.assertEqual(
        sorted(expected_label_names),
        sorted(label.label for label in response.label_options))

  def CallGetStarCount(self):
    request = projects_pb2.GetProjectStarCountRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(
        self.projects_svcr.GetProjectStarCount, mc, request)
    return response.star_count

  def CallStar(self, requester='owner@example.com', starred=True):
    request = projects_pb2.StarProjectRequest(
        project_name='proj', starred=starred)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester=requester)
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.StarProject, mc, request)
    return response.star_count

  def testStarCount_Normal(self):
    self.assertEqual(0, self.CallGetStarCount())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceSameUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

  def testStarCount_StarTwiceDifferentUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='user_222@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceSameUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(1, self.CallGetStarCount())

    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallStar(starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testStarCount_RemoveStarTwiceDifferentUser(self):
    self.assertEqual(1, self.CallStar())
    self.assertEqual(2, self.CallStar(requester='user_222@example.com'))
    self.assertEqual(2, self.CallGetStarCount())

    self.assertEqual(1, self.CallStar(starred=False))
    self.assertEqual(
        0, self.CallStar(requester='user_222@example.com', starred=False))
    self.assertEqual(0, self.CallGetStarCount())

  def testCheckProjectName_OK(self):
    """We can check a project name."""
    request = projects_pb2.CheckProjectNameRequest(project_name='foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckProjectName, mc, request)

    self.assertEqual('', response.error)

  def testCheckProjectName_InvalidProjectName(self):
    """We reject an invalid project name."""
    request = projects_pb2.CheckProjectNameRequest(project_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckProjectName, mc, request)

    self.assertNotEqual('', response.error)

  def testCheckProjectName_NotAllowed(self):
    """Users that can't create a project shouldn't get any information."""
    request = projects_pb2.CheckProjectNameRequest(project_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.projects_svcr.CheckProjectName, mc, request)

  def testCheckProjectName_ProjectAlreadyExists(self):
    """There is already a project with that name."""
    request = projects_pb2.CheckProjectNameRequest(project_name='proj')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckProjectName, mc, request)

    self.assertNotEqual('', response.error)

  def testCheckComponentName_OK(self):
    request = projects_pb2.CheckComponentNameRequest(
        project_name='proj',
        component_name='Component')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckComponentName, mc, request)

    self.assertEqual('', response.error)

  def testCheckComponentName_ParentComponentOK(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Component', 'Docstring',
        False, [], [], 0, 111, [])
    request = projects_pb2.CheckComponentNameRequest(
        project_name='proj',
        parent_path='Component',
        component_name='Path')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckComponentName, mc, request)

    self.assertEqual('', response.error)

  def testCheckComponentName_InvalidComponentName(self):
    request = projects_pb2.CheckComponentNameRequest(
        project_name='proj',
        component_name='Component-')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckComponentName, mc, request)

    self.assertNotEqual('', response.error)

  def testCheckComponentName_ComponentAlreadyExists(self):
    self.services.config.CreateComponentDef(
        self.cnxn, self.project.project_id, 'Component', 'Docstring',
        False, [], [], 0, 111, [])
    request = projects_pb2.CheckComponentNameRequest(
        project_name='proj',
        component_name='Component')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(
        self.projects_svcr.CheckComponentName, mc, request)

    self.assertNotEqual('', response.error)

  def testCheckComponentName_NotAllowedToViewProject(self):
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    request = projects_pb2.CheckComponentNameRequest(
        project_name='proj',
        parent_path='Component',
        component_name='Path')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user_444@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.projects_svcr.CheckComponentName, mc, request)

  def testCheckComponentName_ParentComponentDoesntExist(self):
    request = projects_pb2.CheckComponentNameRequest(
        project_name='proj',
        parent_path='Component',
        component_name='Path')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(exceptions.NoSuchComponentException):
      self.CallWrapped(self.projects_svcr.CheckComponentName, mc, request)

  def testCheckFieldName_OK(self):
    request = projects_pb2.CheckFieldNameRequest(
        project_name='proj',
        field_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.projects_svcr.CheckFieldName, mc, request)
    self.assertEqual('', response.error)

  def testCheckFieldName_InvalidFieldName(self):
    request = projects_pb2.CheckFieldNameRequest(
        project_name='proj',
        field_name='**Foo**')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.projects_svcr.CheckFieldName, mc, request)
    self.assertNotEqual('', response.error)

  def testCheckFieldName_InvalidFieldName_ApproverSuffix(self):
    request = projects_pb2.CheckFieldNameRequest(
        project_name='proj',
        field_name='Foo-aPprOver')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.projects_svcr.CheckFieldName, mc, request)
    self.assertNotEqual('', response.error)

  def testCheckFieldName_FieldAlreadyExists(self):
    self.AddField('Foo')
    request = projects_pb2.CheckFieldNameRequest(
        project_name='proj',
        field_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.projects_svcr.CheckFieldName, mc, request)
    self.assertNotEqual('', response.error)

  def testCheckFieldName_FieldIsPrefixOfAnother(self):
    self.AddField('Foo-Bar')
    request = projects_pb2.CheckFieldNameRequest(
        project_name='proj',
        field_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.projects_svcr.CheckFieldName, mc, request)
    self.assertNotEqual('', response.error)

  def testCheckFieldName_AnotherFieldIsPrefix(self):
    self.AddField('Foo')
    request = projects_pb2.CheckFieldNameRequest(
        project_name='proj',
        field_name='Foo-Bar')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='admin@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    response = self.CallWrapped(self.projects_svcr.CheckFieldName, mc, request)
    self.assertNotEqual('', response.error)

  def testCheckFieldName_NotAllowedToViewProject(self):
    self.project.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    request = projects_pb2.CheckFieldNameRequest(
        project_name='proj',
        field_name='Foo')
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user_444@example.com')
    mc.LookupLoggedInUserPerms(self.project)
    with self.assertRaises(permissions.PermissionException):
      self.CallWrapped(self.projects_svcr.CheckFieldName, mc, request)
