# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for Template editing/viewing servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import logging
import unittest
import settings

from mock import Mock

from third_party import ezt

from framework import permissions
from services import service_manager
from services import template_svc
from testing import fake
from testing import testing_helpers
from tracker import templatedetail
from tracker import tracker_bizobj
from proto import tracker_pb2


class TemplateDetailTest(unittest.TestCase):
  """Tests for the TemplateDetail servlet."""

  def setUp(self):
    self.cnxn = 'fake cnxn'
    mock_template_service = Mock(spec=template_svc.TemplateService)
    self.services = service_manager.Services(project=fake.ProjectService(),
                                             config=fake.ConfigService(),
                                             template=mock_template_service,
                                             usergroup=fake.UserGroupService(),
                                             user=fake.UserService())
    self.servlet = templatedetail.TemplateDetail('req', 'res',
                                               services=self.services)

    self.services.user.TestAddUser('gatsby@example.com', 111)
    self.services.user.TestAddUser('sport@example.com', 222)
    self.services.user.TestAddUser('gatsby@example.com', 111)
    self.services.user.TestAddUser('daisy@example.com', 333)

    self.project = self.services.project.TestAddProject('proj')
    self.services.project.TestAddProjectMembers(
        [333], self.project, 'CONTRIBUTOR_ROLE')

    self.template = self.test_template = tracker_bizobj.MakeIssueTemplate(
        'TestTemplate', 'sum', 'New', 111, 'content', ['label1', 'label2'],
        [], [222], [], summary_must_be_edited=True,
        owner_defaults_to_member=True, component_required=False,
        members_only=False)
    self.template.template_id = 12345
    self.services.template.GetTemplateByName = Mock(
        return_value=self.template)

    self.mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.mr.template_name = 'TestTemplate'

    self.mox = mox.Mox()

    self.fd_1 =  tracker_bizobj.MakeFieldDef(
        1, 789, 'UXReview', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False, approval_id=2)
    self.fd_2 =  tracker_bizobj.MakeFieldDef(
        2, 789, 'UXReview', tracker_pb2.FieldTypes.STR_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'Approval for UX review', False)
    self.fd_3 = tracker_bizobj.MakeFieldDef(
        3, 789, 'TestApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'Approval for Test',
        False)
    self.fd_4 = tracker_bizobj.MakeFieldDef(
        4, 789, 'SecurityApproval', tracker_pb2.FieldTypes.APPROVAL_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action', 'Approval for Security',
        False)
    self.fd_5 = tracker_bizobj.MakeFieldDef(
        5, 789, 'GateTarget', tracker_pb2.FieldTypes.INT_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'milestone target', False, is_phase_field=True)
    self.fd_6 = tracker_bizobj.MakeFieldDef(
        6, 789, 'Choices', tracker_pb2.FieldTypes.ENUM_TYPE, None,
        '', False, False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'milestone target', False, is_phase_field=True)
    self.fd_7 = tracker_bizobj.MakeFieldDef(
        7,
        789,
        'RestrictedField',
        tracker_pb2.FieldTypes.INT_TYPE,
        None,
        '',
        False,
        False,
        False,
        None,
        None,
        '',
        False,
        '',
        '',
        tracker_pb2.NotifyTriggers.NEVER,
        'no_action',
        'RestrictedField',
        False,
        is_restricted_field=True)
    self.fd_8 = tracker_bizobj.MakeFieldDef(
        8,
        789,
        'RestrictedEnumField',
        tracker_pb2.FieldTypes.ENUM_TYPE,
        None,
        '',
        False,
        False,
        False,
        None,
        None,
        '',
        False,
        '',
        '',
        tracker_pb2.NotifyTriggers.NEVER,
        'no_action',
        'RestrictedEnumField',
        False,
        is_restricted_field=True)
    self.fd_9 = tracker_bizobj.MakeFieldDef(
        9,
        789,
        'RestrictedField_2',
        tracker_pb2.FieldTypes.INT_TYPE,
        None,
        '',
        False,
        False,
        False,
        None,
        None,
        '',
        False,
        '',
        '',
        tracker_pb2.NotifyTriggers.NEVER,
        'no_action',
        'RestrictedField_2',
        False,
        is_restricted_field=True)
    self.fd_10 = tracker_bizobj.MakeFieldDef(
        10,
        789,
        'RestrictedEnumField_2',
        tracker_pb2.FieldTypes.ENUM_TYPE,
        None,
        '',
        False,
        False,
        False,
        None,
        None,
        '',
        False,
        '',
        '',
        tracker_pb2.NotifyTriggers.NEVER,
        'no_action',
        'RestrictedEnumField_2',
        False,
        is_restricted_field=True)

    self.ad_3 = tracker_pb2.ApprovalDef(approval_id=3)
    self.ad_4 = tracker_pb2.ApprovalDef(approval_id=4)

    self.cd_1 = tracker_bizobj.MakeComponentDef(
        1, 789, 'BackEnd', 'doc', False, [111], [], 100000, 222)
    self.template.component_ids.append(1)

    self.canary_phase = tracker_pb2.Phase(
        name='Canary', phase_id=1, rank=1)
    self.av_3 = tracker_pb2.ApprovalValue(approval_id=3, phase_id=1)
    self.stable_phase = tracker_pb2.Phase(
        name='Stable', phase_id=2, rank=3)
    self.av_4 = tracker_pb2.ApprovalValue(approval_id=4, phase_id=2)
    self.template.phases.extend([self.stable_phase, self.canary_phase])
    self.template.approval_values.extend([self.av_3, self.av_4])

    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.templates = testing_helpers.DefaultTemplates()
    self.template.labels.extend(
        ['GateTarget-Should-Not', 'GateTarget-Be-Masked',
         'Choices-Wrapped', 'Choices-Burritod'])
    self.templates.append(self.template)
    self.services.template.GetProjectTemplates = Mock(
        return_value=self.templates)
    self.services.template.FindTemplateByName = Mock(return_value=self.template)
    self.config.component_defs.append(self.cd_1)
    self.config.field_defs.extend(
        [
            self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_5, self.fd_6,
            self.fd_7, self.fd_8, self.fd_9, self.fd_10
        ])
    self.config.approval_defs.extend([self.ad_3, self.ad_4])
    self.services.config.StoreConfig(None, self.config)

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission_Anyone(self):
    self.mr.auth.effective_ids = {222}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {333}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

  def testAssertBasePermision_MembersOnly(self):
    self.template.members_only = True
    self.mr.auth.effective_ids = {222}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {333}
    self.servlet.AssertBasePermission(self.mr)

    self.mr.auth.effective_ids = {444}
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData(self):
    self.mr.perms = permissions.PermissionSet([])
    self.mr.auth.effective_ids = {222}  # template admin
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_TEMPLATES,
                     page_data['admin_tab_mode'])
    self.assertTrue(page_data['allow_edit'])
    self.assertEqual(page_data['uneditable_fields'], ezt.boolean(True))
    self.assertFalse(page_data['new_template_form'])
    self.assertFalse(page_data['initial_members_only'])
    self.assertEqual(page_data['template_name'], 'TestTemplate')
    self.assertEqual(page_data['initial_summary'], 'sum')
    self.assertTrue(page_data['initial_must_edit_summary'])
    self.assertEqual(page_data['initial_content'], 'content')
    self.assertEqual(page_data['initial_status'], 'New')
    self.assertEqual(page_data['initial_owner'], 'gatsby@example.com')
    self.assertTrue(page_data['initial_owner_defaults_to_member'])
    self.assertEqual(page_data['initial_components'], 'BackEnd')
    self.assertFalse(page_data['initial_component_required'])
    self.assertItemsEqual(
        page_data['labels'],
        ['label1', 'label2', 'GateTarget-Should-Not', 'GateTarget-Be-Masked'])
    self.assertEqual(page_data['initial_admins'], 'sport@example.com')
    self.assertTrue(page_data['initial_add_approvals'])
    self.assertEqual(len(page_data['initial_phases']), 6)
    phases = [phase for phase in page_data['initial_phases'] if phase.name]
    self.assertEqual(len(phases), 2)
    self.assertEqual(len(page_data['approvals']), 2)
    self.assertItemsEqual(page_data['prechecked_approvals'],
                          ['3_phase_0', '4_phase_1'])
    self.assertTrue(page_data['fields'][3].is_editable)  #nonRestrictedField
    self.assertIsNone(page_data['fields'][4].is_editable)  #restrictedField

  def testProcessFormData_Reject(self):
    self.mr.auth.effective_ids = {222}
    post_data = fake.PostData(
      name=['TestTemplate'],
      members_only=['on'],
      summary=['TLDR'],
      summary_must_be_edited=['on'],
      content=['HEY WHY'],
      status=['Accepted'],
      owner=['someone@world.com'],
      label=['label-One', 'label-Two'],
      custom_1=['NO'],
      custom_2=['MOOD'],
      components=['hey, hey2,he3'],
      component_required=['on'],
      owner_defaults_to_member=['no'],
      add_approvals = ['on'],
      phase_0=['Canary'],
      phase_1=['Stable-Exp'],
      phase_2=['Stable'],
      phase_3=[''],
      phase_4=[''],
      phase_5=[''],
      approval_3=['phase_0'],
      approval_4=['phase_2']
    )

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        self.mr,
        initial_members_only=ezt.boolean(True),
        template_name='TestTemplate',
        initial_summary='TLDR',
        initial_must_edit_summary=ezt.boolean(True),
        initial_content='HEY WHY',
        initial_status='Accepted',
        initial_owner='someone@world.com',
        initial_owner_defaults_to_member=ezt.boolean(False),
        initial_components='hey, hey2, he3',
        initial_component_required=ezt.boolean(True),
        initial_admins='',
        labels=['label-One', 'label-Two'],
        fields=mox.IgnoreArg(),
        initial_add_approvals=ezt.boolean(True),
        initial_phases=[tracker_pb2.Phase(name=name) for
                        name in ['Canary', 'Stable-Exp', 'Stable', '', '', '']],
        approvals=mox.IgnoreArg(),
        prechecked_approvals=['3_phase_0', '4_phase_2'],
        required_approval_ids=[]
        )
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Owner not found.', self.mr.errors.owner)
    self.assertEqual('Unknown component he3', self.mr.errors.components)
    self.assertIsNone(url)
    self.assertEqual('Defined gates must have assigned approvals.',
                     self.mr.errors.phase_approvals)

  def testProcessFormData_RejectRestrictedFields(self):
    """Template admins cannot set restricted fields by default."""
    self.mr.perms = permissions.PermissionSet([])
    self.mr.auth.effective_ids = {222}  # template admin
    post_data_add_fv = fake.PostData(
        name=['TestTemplate'],
        members_only=['on'],
        summary=['TLDR'],
        summary_must_be_edited=[''],
        content=['HEY WHY'],
        status=['Accepted'],
        owner=['daisy@example.com'],
        label=['label-One', 'label-Two'],
        custom_1=['NO'],
        custom_2=['MOOD'],
        custom_7=['37'],
        components=['BackEnd'],
        component_required=['on'],
        owner_defaults_to_member=['on'],
        add_approvals=['no'],
        phase_0=[''],
        phase_1=[''],
        phase_2=[''],
        phase_3=[''],
        phase_4=[''],
        phase_5=['OOPs'],
        approval_3=['phase_0'],
        approval_4=['phase_2'])
    post_data_label_edits_enum = fake.PostData(
        name=['TestTemplate'],
        members_only=['on'],
        summary=['TLDR'],
        summary_must_be_edited=[''],
        content=['HEY WHY'],
        status=['Accepted'],
        owner=['daisy@example.com'],
        label=['label-One', 'label-Two', 'RestrictedEnumField-7'],
        components=['BackEnd'],
        component_required=['on'],
        owner_defaults_to_member=['on'],
        add_approvals=['no'],
        phase_0=[''],
        phase_1=[''],
        phase_2=[''],
        phase_3=[''],
        phase_4=[''],
        phase_5=['OOPs'],
        approval_3=['phase_0'],
        approval_4=['phase_2'])

    self.assertRaises(
        AssertionError, self.servlet.ProcessFormData, self.mr, post_data_add_fv)
    self.assertRaises(
        AssertionError, self.servlet.ProcessFormData, self.mr,
        post_data_label_edits_enum)

  def testProcessFormData_Accept(self):
    self.fd_7.editor_ids = [222]
    self.fd_8.editor_ids = [222]
    self.mr.perms = permissions.PermissionSet([])
    self.mr.auth.effective_ids = {222}  # template admin
    temp_restricted_fv = tracker_bizobj.MakeFieldValue(
        9, 3737, None, None, None, None, False)
    self.template.field_values.append(temp_restricted_fv)
    self.template.labels.append('RestrictedEnumField_2-b')
    post_data = fake.PostData(
        name=['TestTemplate'],
        members_only=['on'],
        summary=['TLDR'],
        summary_must_be_edited=[''],
        content=['HEY WHY'],
        status=['Accepted'],
        owner=['daisy@example.com'],
        label=['label-One', 'label-Two', 'RestrictedEnumField-7'],
        custom_1=['NO'],
        custom_2=['MOOD'],
        custom_7=['37'],
        components=['BackEnd'],
        component_required=['on'],
        owner_defaults_to_member=['on'],
        add_approvals=['no'],
        phase_0=[''],
        phase_1=[''],
        phase_2=[''],
        phase_3=[''],
        phase_4=[''],
        phase_5=['OOPs'],
        approval_3=['phase_0'],
        approval_4=['phase_2'])
    url = self.servlet.ProcessFormData(self.mr, post_data)

    self.assertTrue('/templates/detail?saved=1&template=TestTemplate&' in url)

    self.services.template.UpdateIssueTemplateDef.assert_called_once_with(
        self.mr.cnxn,
        47925,
        12345,
        status='Accepted',
        component_required=True,
        phases=[],
        approval_values=[],
        name='TestTemplate',
        field_values=[
            tracker_pb2.FieldValue(field_id=1, str_value='NO', derived=False),
            tracker_pb2.FieldValue(field_id=2, str_value='MOOD', derived=False),
            tracker_pb2.FieldValue(field_id=7, int_value=37, derived=False),
            tracker_pb2.FieldValue(field_id=9, int_value=3737, derived=False)
        ],
        labels=[
            'label-One', 'label-Two', 'RestrictedEnumField-7',
            'RestrictedEnumField_2-b'
        ],
        owner_defaults_to_member=True,
        admin_ids=[],
        content='HEY WHY',
        component_ids=[1],
        summary_must_be_edited=False,
        summary='TLDR',
        members_only=True,
        owner_id=333)

  def testProcessFormData_AcceptPhases(self):
    self.mr.auth.effective_ids = {222}
    post_data = fake.PostData(
      name=['TestTemplate'],
      members_only=['on'],
      summary=['TLDR'],
      summary_must_be_edited=[''],
      content=['HEY WHY'],
      status=['Accepted'],
      owner=['daisy@example.com'],
      label=['label-One', 'label-Two'],
      custom_1=['NO'],
      custom_2=['MOOD'],
      components=['BackEnd'],
      component_required=['on'],
      owner_defaults_to_member=['on'],
      add_approvals = ['on'],
      phase_0=['Canary'],
      phase_1=['Stable'],
      phase_2=[''],
      phase_3=[''],
      phase_4=[''],
      phase_5=[''],
      approval_3=['phase_0'],
      approval_4=['phase_1']
    )
    url = self.servlet.ProcessFormData(self.mr, post_data)

    self.assertTrue('/templates/detail?saved=1&template=TestTemplate&' in url)

    self.services.template.UpdateIssueTemplateDef.assert_called_once_with(
        self.mr.cnxn, 47925, 12345, status='Accepted', component_required=True,
        phases=[
            tracker_pb2.Phase(name='Canary', rank=0, phase_id=0),
            tracker_pb2.Phase(name='Stable', rank=1, phase_id=1)],
        approval_values=[tracker_pb2.ApprovalValue(approval_id=3, phase_id=0),
                         tracker_pb2.ApprovalValue(approval_id=4, phase_id=1)],
        name='TestTemplate', field_values=[
            tracker_pb2.FieldValue(field_id=1, str_value='NO', derived=False),
            tracker_pb2.FieldValue(
                field_id=2, str_value='MOOD', derived=False)],
        labels=['label-One', 'label-Two'], owner_defaults_to_member=True,
        admin_ids=[], content='HEY WHY', component_ids=[1],
        summary_must_be_edited=False, summary='TLDR', members_only=True,
        owner_id=333)

  def testProcessFormData_Delete(self):
    post_data = fake.PostData(
      deletetemplate=['Submit'],
      name=['TestTemplate'],
      members_only=['on'],
    )
    url = self.servlet.ProcessFormData(self.mr, post_data)

    self.assertTrue('/p/None/adminTemplates?deleted=1' in url)
    self.services.template.DeleteIssueTemplateDef\
        .assert_called_once_with(self.mr.cnxn, 47925, 12345)
