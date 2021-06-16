# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit test for Template creation servlet."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import unittest
import settings

from mock import Mock

from third_party import ezt

from framework import permissions
from services import service_manager
from services import template_svc
from testing import fake
from testing import testing_helpers
from tracker import templatecreate
from tracker import tracker_bizobj
from tracker import tracker_views
from proto import tracker_pb2


class TemplateCreateTest(unittest.TestCase):
  """Tests for the TemplateCreate servlet."""

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        template=Mock(spec=template_svc.TemplateService),
        user=fake.UserService())
    self.servlet = templatecreate.TemplateCreate('req', 'res',
        services=self.services)
    self.project = self.services.project.TestAddProject('proj')

    self.fd_1 = tracker_bizobj.MakeFieldDef(
        1, self.project.project_id, 'StringFieldName',
        tracker_pb2.FieldTypes.STR_TYPE, None, '', False,
        False, False, None, None, '', False, '', '',
        tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'some approval thing', False, approval_id=2)

    self.fd_2 = tracker_bizobj.MakeFieldDef(
        2, self.project.project_id, 'UXApproval',
        tracker_pb2.FieldTypes.APPROVAL_TYPE, None, '', False, False, False,
        None, None, '', False, '', '', tracker_pb2.NotifyTriggers.NEVER,
        'no_action', 'Approval for UX review', False)
    self.fd_3 = tracker_bizobj.MakeFieldDef(
        3, self.project.project_id, 'TestApproval',
        tracker_pb2.FieldTypes.APPROVAL_TYPE, None, '', False, False, False,
        None, None, '', False, '', '', tracker_pb2.NotifyTriggers.NEVER,
        'no_action', 'Approval for Test review', False)
    self.fd_4 =  tracker_bizobj.MakeFieldDef(
        4, self.project.project_id, 'Target',
        tracker_pb2.FieldTypes.INT_TYPE, None, '', False, False, False, None,
        None, '', False, '', '', tracker_pb2.NotifyTriggers.NEVER, 'no_action',
        'milestone target', False, is_phase_field=True)
    self.fd_5 = tracker_bizobj.MakeFieldDef(
        5,
        self.project.project_id,
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
    self.fd_6 = tracker_bizobj.MakeFieldDef(
        6,
        self.project.project_id,
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
    ad_2 = tracker_pb2.ApprovalDef(approval_id=2)
    ad_3 = tracker_pb2.ApprovalDef(approval_id=3)

    self.config = self.services.config.GetProjectConfig(
        'fake cnxn', self.project.project_id)
    self.config.approval_defs.extend([ad_2, ad_3])
    self.config.field_defs.extend(
        [self.fd_1, self.fd_2, self.fd_3, self.fd_4, self.fd_5, self.fd_6])

    first_tmpl = tracker_bizobj.MakeIssueTemplate(
        'sometemplate', 'summary', None, None, 'content', [], [], [],
        [])
    self.services.config.StoreConfig(None, self.config)

    templates = testing_helpers.DefaultTemplates()
    templates.append(first_tmpl)
    self.services.template.GetProjectTemplates = Mock(
        return_value=templates)

    self.mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testAssertBasePermission(self):
    # Anon users can never do it
    self.mr.perms = permissions.READ_ONLY_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

    # Project owner can do it.
    self.mr.perms = permissions.OWNER_ACTIVE_PERMISSIONSET
    self.servlet.AssertBasePermission(self.mr)

    # Project member cannot do it
    self.mr.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)
    self.mr.perms = permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET
    self.assertRaises(
        permissions.PermissionException,
        self.servlet.AssertBasePermission, self.mr)

  def testGatherPageData(self):
    precomp_view_info = tracker_views._PrecomputeInfoForValueViews(
        [], [], [], self.config, [])
    fv = tracker_views._MakeFieldValueView(
        self.fd_1, self.config, precomp_view_info, {})
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(self.servlet.PROCESS_TAB_TEMPLATES,
                     page_data['admin_tab_mode'])
    self.assertTrue(page_data['allow_edit'])
    self.assertEqual(page_data['uneditable_fields'], ezt.boolean(False))
    self.assertTrue(page_data['new_template_form'])
    self.assertFalse(page_data['initial_members_only'])
    self.assertEqual(page_data['template_name'], '')
    self.assertEqual(page_data['initial_summary'], '')
    self.assertFalse(page_data['initial_must_edit_summary'])
    self.assertEqual(page_data['initial_content'], '')
    self.assertEqual(page_data['initial_status'], '')
    self.assertEqual(page_data['initial_owner'], '')
    self.assertFalse(page_data['initial_owner_defaults_to_member'])
    self.assertEqual(page_data['initial_components'], '')
    self.assertFalse(page_data['initial_component_required'])
    self.assertEqual(page_data['fields'][2].field_name, fv.field_name)
    self.assertEqual(page_data['initial_admins'], '')
    self.assertEqual(page_data['approval_subfields_present'], ezt.boolean(True))
    self.assertEqual(page_data['phase_fields_present'], ezt.boolean(False))

  def testProcessFormData_Reject(self):
    self.services.user.TestAddUser('user@example.com', 222)
    self.mr.auth.effective_ids = {222}
    post_data = fake.PostData(
      name=['sometemplate'],
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
      approval_2=['phase_1'],
      approval_3=['phase_2']
    )

    self.mox.StubOutWithMock(self.servlet, 'PleaseCorrect')
    self.servlet.PleaseCorrect(
        self.mr,
        initial_members_only=ezt.boolean(True),
        template_name='sometemplate',
        initial_content='TLDR',
        initial_must_edit_summary=ezt.boolean(True),
        initial_description='HEY WHY',
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
        prechecked_approvals=['2_phase_1', '3_phase_2'],
        required_approval_ids=[]
        )
    self.mox.ReplayAll()
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.mox.VerifyAll()
    self.assertEqual('Owner not found.', self.mr.errors.owner)
    self.assertEqual('Unknown component he3', self.mr.errors.components)
    self.assertEqual(
        'Template with name sometemplate already exists', self.mr.errors.name)
    self.assertEqual('Defined gates must have assigned approvals.',
                     self.mr.errors.phase_approvals)
    self.assertIsNone(url)

  def testProcessFormData_RejectRestrictedFields(self):
    self.services.template.GetTemplateByName = Mock(return_value=None)
    self.mr.perms = permissions.PermissionSet([])
    post_data_add_fv = fake.PostData(
        name=['secondtemplate'],
        members_only=['on'],
        summary=['TLDR'],
        summary_must_be_edited=['on'],
        content=['HEY WHY'],
        status=['Accepted'],
        label=['label-One', 'label-Two'],
        custom_1=['Hey'],
        custom_5=['7'],
        component_required=['on'],
        owner_defaults_to_member=['no'],
        add_approvals=['no'],
        phase_0=[''],
        phase_1=[''],
        phase_2=[''],
        phase_3=[''],
        phase_4=[''],
        phase_5=['OOPs'],
        approval_2=['phase_0'],
        approval_3=['phase_2'])
    post_data_label_edits_enum = fake.PostData(
        name=['secondtemplate'],
        members_only=['on'],
        summary=['TLDR'],
        summary_must_be_edited=['on'],
        content=['HEY WHY'],
        status=['Accepted'],
        label=['label-One', 'label-Two', 'RestrictedEnumField-7'],
        component_required=['on'],
        owner_defaults_to_member=['no'],
        add_approvals=['no'],
        phase_0=[''],
        phase_1=[''],
        phase_2=[''],
        phase_3=[''],
        phase_4=[''],
        phase_5=['OOPs'],
        approval_2=['phase_0'],
        approval_3=['phase_2'])

    self.assertRaises(
        AssertionError, self.servlet.ProcessFormData, self.mr, post_data_add_fv)
    self.assertRaises(
        AssertionError, self.servlet.ProcessFormData, self.mr,
        post_data_label_edits_enum)

  def testProcessFormData_Accept(self):
    self.services.user.TestAddUser('user@example.com', 222)
    self.mr.auth.effective_ids = {222}
    self.services.template.GetTemplateByName = Mock(return_value=None)
    post_data = fake.PostData(
        name=['secondtemplate'],
        members_only=['on'],
        summary=['TLDR'],
        summary_must_be_edited=['on'],
        content=['HEY WHY'],
        status=['Accepted'],
        label=['label-One', 'label-Two', 'RestrictedEnumField-7'],
        custom_1=['NO'],
        custom_5=['37'],
        component_required=['on'],
        owner_defaults_to_member=['no'],
        add_approvals=['no'],
        phase_0=[''],
        phase_1=[''],
        phase_2=[''],
        phase_3=[''],
        phase_4=[''],
        phase_5=['OOPs'],
        approval_2=['phase_0'],
        approval_3=['phase_2'])

    url = self.servlet.ProcessFormData(self.mr, post_data)

    self.assertTrue('/adminTemplates?saved=1&ts' in url)

    self.assertEqual(0,
        self.services.template.UpdateIssueTemplateDef.call_count)

    # errors in phases should not matter if add_approvals is not 'on'
    self.assertIsNone(self.mr.errors.phase_approvals)

  def testProcessFormData_AcceptPhases(self):
    self.services.user.TestAddUser('user@example.com', 222)
    self.mr.auth.effective_ids = {222}
    self.services.template.GetTemplateByName = Mock(return_value=None)
    post_data = fake.PostData(
      name=['secondtemplate'],
      members_only=['on'],
      summary=['TLDR'],
      summary_must_be_edited=['on'],
      content=['HEY WHY'],
      status=['Accepted'],
      label=['label-One', 'label-Two'],
      custom_1=['NO'],
      component_required=['on'],
      owner_defaults_to_member=['no'],
      add_approvals = ['on'],
      phase_0=['Canary'],
      phase_1=['Stable'],
      phase_2=[''],
      phase_3=[''],
      phase_4=[''],
      phase_5=[''],
      approval_2=['phase_0'],
      approval_3=['phase_1'],
      approval_3_required=['on']
    )

    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('/adminTemplates?saved=1&ts' in url)

    fv = tracker_pb2.FieldValue(field_id=1, str_value='NO', derived=False)
    phases = [
        tracker_pb2.Phase(name='Canary', rank=0, phase_id=0),
        tracker_pb2.Phase(name='Stable', rank=1, phase_id=1)
    ]
    approval_values = [
        tracker_pb2.ApprovalValue(approval_id=2, phase_id=0),
        tracker_pb2.ApprovalValue(
            approval_id=3, status=tracker_pb2.ApprovalStatus(
                tracker_pb2.ApprovalStatus.NEEDS_REVIEW), phase_id=1)
        ]
    self.services.template.CreateIssueTemplateDef.assert_called_once_with(
        self.mr.cnxn, 47925, 'secondtemplate', 'HEY WHY', 'TLDR', True,
        'Accepted', True, False, True, 0, ['label-One', 'label-Two'], [], [],
        [fv], phases=phases, approval_values=approval_values)
