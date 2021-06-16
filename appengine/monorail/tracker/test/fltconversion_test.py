# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the flt launch issues conversion task."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import copy
import unittest
import settings
import mock

from businesslogic import work_env
from framework import exceptions
from framework import permissions
from services import service_manager
from services import template_svc
from tracker import fltconversion
from tracker import tracker_bizobj
from testing import fake
from testing import testing_helpers
from proto import tracker_pb2

class FLTConvertTask(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        template=mock.Mock(spec=template_svc.TemplateService),)
    self.mr = testing_helpers.MakeMonorailRequest()
    self.task = fltconversion.FLTConvertTask(
        'req', 'res', services=self.services)
    self.task.mr = self.mr
    self.issue = fake.MakeTestIssue(
        789, 1, 'summary', 'New', 111, issue_id=78901)
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    self.work_env = work_env.WorkEnv(
        self.mr, self.services, 'Testing')
    self.issue1 = fake.MakeTestIssue(
        789, 1, 'sum', 'New', 111, issue_id=78901,
        labels=[
            'Launch-M-Approved-71-Stable', 'Launch-M-Target-70-Beta',
            'Launch-UI-Yes', 'Launch-Privacy-NeedInfo',
            'pm-jojwang', 'tl-annajo', 'ux-shiba', 'Type-Launch'])
    self.issue2 = fake.MakeTestIssue(
        789, 2, 'sum', 'New', 111, issue_id=78902,
        labels=[
            'Launch-M-Target-71-Stable', 'Launch-M-Approved-70-Beta',
            'pm-jojwang', 'tl-annajo', 'OS-Chrome', 'OS-Android',
            'Type-Launch'])
    self.issue3 = fake.MakeTestIssue(
        789, 3, 'sum', 'New', 111, issue_id=78903,
        labels=['Launch-M-Approved-71-Stable',
                'Launch-M-Approved-79-Stable-Exp', 'Launch-M-Target-70-Beta',
                'Launch-M-Target-70-Stable', 'Launch-UI-Yes',
                'Launch-Exp-Leadership-Yes', 'pm-annajo', 'tl-jojwang',
                'OS-Chrome', 'Type-Launch'])
    self.issue4 = fake.MakeTestIssue(
        789, 4, 'sum', 'New', 111, issue_id=78904,
        labels=['Launch-UI-Yes', 'OS-Chrome', 'Type-Launch'])
    self.issue5 = fake.MakeTestIssue(
        789, 5, 'sum', 'New', 111, issue_id=78905,
        labels=['Launch-M-Approved-71-Stable',
                'Launch-M-Approved-79-Stable-Exp', 'Launch-M-Target-70-Beta',
                'Launch-M-Target-70-Stable', 'Launch-UI-Yes',
                'Launch-Privacy-NeedInfo', 'Launch-Exp-Leadership-Yes',
                'pm-annajo', 'tl-jojwang', 'OS-Chrome', 'Type-Launch'])

    self.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=7, status=tracker_pb2.ApprovalStatus.NOT_SET),
        tracker_pb2.ApprovalValue(
            approval_id=8, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)]
    self.phases = [tracker_pb2.Phase(name='Stable', phase_id=88),
              tracker_pb2.Phase(name='Beta', phase_id=89)]

  def testAssertBasePermission(self):
    self.mr.auth.user_pb.is_site_admin = True
    settings.app_id = 'monorail-staging'
    self.task.AssertBasePermission(self.mr)

    settings.app_id = 'monorail-prod'
    self.task.AssertBasePermission(self.mr)

    self.mr.auth.user_pb.is_site_admin = False
    self.assertRaises(permissions.PermissionException,
                      self.task.AssertBasePermission, self.mr)

  def testHandleRequest(self):
    # Set up Objects
    project_info = fltconversion.ProjectInfo(
        self.config, 'q=query', self.approval_values, self.phases,
        11, 12, 13, 16, 14, 15, fltconversion.BROWSER_PHASE_MAP,
        fltconversion.BROWSER_APPROVALS_TO_LABELS,
        fltconversion.BROWSER_M_LABELS_RE)

    self.config.field_defs = [
        tracker_pb2.FieldDef(field_id=7, field_name='Chrome-UX',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(field_id=8, field_name='Chrome-Privacy',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    ]

    # Set up mocks
    patcher = mock.patch(
        'search.frontendsearchpipeline.FrontendSearchPipeline',
        spec=True, visible_results=[self.issue1, self.issue2])
    mockPipeline = patcher.start()

    self.task.services.issue.GetIssue = mock.Mock(
        side_effect=[self.issue1, self.issue2])

    self.task.FetchAndAssertProjectInfo = mock.Mock(return_value=project_info)

    with self.work_env as we:
      we.ListIssues = mock.Mock(return_value=mockPipeline)

    def side_effect(_cnxn, email):
      if email == 'jojwang@chromium.org':
        return 111
      if email == 'annajo@google.com':
        return 222
      if email == 'shiba@google.com':
        return 333
      raise exceptions.NoSuchUserException
    self.task.services.user.LookupUserID = mock.Mock(side_effect=side_effect)

    self.task.ExecuteIssueChanges = mock.Mock(return_value=[])

    # Call
    json = self.task.HandleRequest(self.mr)

    # assert
    self.assertEqual(json['converted_issues'], [1, 2])

    new_approvals1 = [
        tracker_pb2.ApprovalValue(
            approval_id=7, status=tracker_pb2.ApprovalStatus.APPROVED),
        tracker_pb2.ApprovalValue(
            approval_id=8, status=tracker_pb2.ApprovalStatus.NEED_INFO)]
    new_fvs1 = [
      # M-Approved Stable
      tracker_bizobj.MakeFieldValue(
          15, 71, None, None, None, None, False, phase_id=88),
      # M-Target Beta
      tracker_bizobj.MakeFieldValue(
          14, 70, None, None, None, None, False, phase_id=89),
      # PM field
      tracker_bizobj.MakeFieldValue(
          11, None, None, 111, None, None, False),
      # TL field
      tracker_bizobj.MakeFieldValue(
          12, None, None, 222, None, None, False),
      # UX field
      tracker_bizobj.MakeFieldValue(
          16, None, None, 333, None, None, False)
    ]


    new_approvals2 = [
        tracker_pb2.ApprovalValue(
            approval_id=7, status=tracker_pb2.ApprovalStatus.NOT_SET),
        tracker_pb2.ApprovalValue(
            approval_id=8, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    ]
    new_fvs2 = [
        tracker_bizobj.MakeFieldValue(
            14, 71, None, None, None, None, False, phase_id=88),
        tracker_bizobj.MakeFieldValue(
            15, 70, None, None, None, None, False, phase_id=89),
        # PM field
        tracker_bizobj.MakeFieldValue(
            11, None, None, 111, None, None, False),
        # TL field
        tracker_bizobj.MakeFieldValue(
            12, None, None, 222, None, None, False)]

    execute_calls = [
        mock.call(
            self.config, self.issue1, new_approvals1, self.phases, new_fvs1),
        mock.call(
            self.config, self.issue2, new_approvals2, self.phases, new_fvs2)]
    self.task.ExecuteIssueChanges.assert_has_calls(execute_calls)

    patcher.stop()

  def testHandleRequest_UndoConversion(self):
    # test Delete() is actually called
    mr = testing_helpers.MakeMonorailRequest(path='url/url?launch=delete')
    self.task.UndoConversion = mock.Mock(return_value={'deleteing': [1, 2]})
    actualReturn = self.task.HandleRequest(mr)
    self.assertEqual({'deleteing': [1, 2]}, actualReturn)

  def testUndoConversion(self):
    # Set up objects
    self.issue1.field_values = [
        # Test non phase and TL/PM/TE field_values are not deleted
        tracker_bizobj.MakeFieldValue(
            17, None, 'strvalue', None, None, None, False)]
    issue1 = copy.deepcopy(self.issue1)
    issue2 = copy.deepcopy(self.issue2)
    fvs = [
        tracker_bizobj.MakeFieldValue(
            11, None, None, 222, None, None, False),
        tracker_bizobj.MakeFieldValue(
            12, None, None, 111, None, None, False),
        tracker_bizobj.MakeFieldValue(
            16, None, None, 111, None, None, False)]
    self.config.field_defs = [
        tracker_pb2.FieldDef(field_id=11, field_name='PM'),
        tracker_pb2.FieldDef(field_id=12, field_name='TL'),
        tracker_pb2.FieldDef(field_id=13, field_name='TE'),
        tracker_pb2.FieldDef(field_id=16, field_name='UX')]
    # Make element edits made during conversion that should be undone.
    issue1.labels.extend(['Type-FLT-Launch', 'FLT-Conversion'])
    issue1.labels.remove('Type-Launch')
    issue2.labels.extend(['Type-FLT-Launch', 'FLT-Conversion'])
    issue2.labels.remove('Type-Launch')
    issue1.approval_values = self.approval_values
    issue2.approval_values = self.approval_values
    issue1.phases = self.phases
    issue2.phases = self.phases
    issue1.field_values.extend(fvs)

    # Set up mocks
    patcher = mock.patch(
        'search.frontendsearchpipeline.FrontendSearchPipeline',
        spec=True, visible_results=[issue1, issue2])  # converted issues
    mockPipeline = patcher.start()
    self.task.services.project.GetProjectByName = mock.Mock()
    self.task.services.config.GetProjectConfig = mock.Mock(
        return_value=self.config)
    self.task.services.issue.GetIssue = mock.Mock(
        side_effect=[issue1, issue2])
    self.task.services.issue._UpdateIssuesApprovals = mock.Mock()
    self.task.services.issue.UpdateIssue = mock.Mock()

    with self.work_env as we:
      we.ListIssues = mock.Mock(return_value=mockPipeline)

    json = self.task.UndoConversion(self.mr)
    self.assertEqual(json['deleting'], [1, 2])
    # assert convert issue1 is back to the pre-conversion state, self.issue1.
    self.assertEqual(issue1, self.issue1)
    self.assertEqual(issue2, self.issue2)

    # assert UpdateIssue calls were made with pre-conversion state issues.
    update_calls = [
        mock.call(self.mr.cnxn, self.issue1),
        mock.call(self.mr.cnxn, self.issue2)]
    self.task.services.issue._UpdateIssuesApprovals.assert_has_calls(
        update_calls)
    self.task.services.issue.UpdateIssue.assert_has_calls(update_calls)
    patcher.stop()

  def testVerifyConversion(self):
    # Set up objects
    self.issue1.labels.extend(
        # Launch-M-Target-70-Stable-Exp should be ignored
        ['Rollout-Type-Default', 'Launch-M-Target-70-Stable-Exp'])
    self.issue1.phases = [tracker_pb2.Phase(name='Beta', phase_id=1),
                          tracker_pb2.Phase(name='Stable', phase_id=2)]
    self.issue1.approval_values = [
      tracker_pb2.ApprovalValue(
          approval_id=1, status=tracker_pb2.ApprovalStatus.NOT_SET),
      tracker_pb2.ApprovalValue(
          approval_id=2, status=tracker_pb2.ApprovalStatus.APPROVED),
      tracker_pb2.ApprovalValue(
          approval_id=3, status=tracker_pb2.ApprovalStatus.NEED_INFO),
    ]
    self.issue1.field_values = [
        # problem = expected field for TL
        tracker_bizobj.MakeFieldValue(4, None, None, 111, None, None, False),
        tracker_pb2.FieldValue(field_id=7, int_value=70, phase_id=1),
        tracker_pb2.FieldValue(field_id=8, int_value=71, phase_id=2),
    ]

    self.issue2.labels.extend(['Rollout-Type-Finch'])
    self.issue2.phases = [tracker_pb2.Phase(name='Beta', phase_id=1),
                          tracker_pb2.Phase(name='Stable-Full', phase_id=2),
                          tracker_pb2.Phase(name='Stable-Exp', phase_id=3)]
    self.issue2.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=1, status=tracker_pb2.ApprovalStatus.NOT_SET),
        tracker_pb2.ApprovalValue(
            approval_id=2, status=tracker_pb2.ApprovalStatus.NOT_SET),
        tracker_pb2.ApprovalValue(
            # problem = approval Chrome-Privacy has status approved for None
            approval_id=3, status=tracker_pb2.ApprovalStatus.APPROVED),
    ]
    self.issue2.field_values = [
        # problem = no phase field for label 'Launch-M-Approved-70-Beta'
        tracker_pb2.FieldValue(field_id=7, int_value=71, phase_id=2),
        tracker_bizobj.MakeFieldValue(4, None, None, 111, None, None, False),
        tracker_bizobj.MakeFieldValue(5, None, None, 111, None, None, False),
        ]

    self.issue3.labels.extend(['Rollout-Type-Default'])
    self.issue3.phases = [tracker_pb2.Phase(name='Feature Freeze', phase_id=4),
                          tracker_pb2.Phase(name='Branch', phase_id=5),
                          tracker_pb2.Phase(name='Stable', phase_id=6)]
    self.issue3.approval_values = [
      tracker_pb2.ApprovalValue(
          approval_id=9, status=tracker_pb2.ApprovalStatus.APPROVED),
      tracker_pb2.ApprovalValue(
          approval_id=10, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)]
    # problem = no phase field label Launch-M-Target-70-Stable
    # problem = missing a field for TL
    self.issue3.field_values = [
        tracker_pb2.FieldValue(field_id=8, int_value=71, phase_id=6),
        tracker_bizobj.MakeFieldValue(4, None, None, 111, None, None, False)
    ]

    self.issue4.labels.extend(['Rollout-Type-Default'])
    # problem = incorrect phases for OS default launch
    self.issue4.phases = [tracker_pb2.Phase(name='Branch', phase_id=5),
                          tracker_pb2.Phase(name='Stable-Exp', phase_id=7)]
    # problem = approval ChromeOS-UX has status 'NEEDS_REVIEW'
    # for label value Yes
    self.issue4.approval_values = [
      tracker_pb2.ApprovalValue(
          approval_id=9, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)]

    self.issue5.labels.extend(['Rollout-Type-Finch'])
    self.issue5.phases = [tracker_pb2.Phase(name='Branch', phase_id=5),
                          tracker_pb2.Phase(name='Feature Freeze', phase_id=4),
                          tracker_pb2.Phase(name='Stable-Exp', phase_id=7),
                          tracker_pb2.Phase(name='Stable-Full', phase_id=8)]
    self.issue5.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=9, status=tracker_pb2.ApprovalStatus.APPROVED),
        # problem = approval ChromeOS-Privacy has status 'REVIEW_REQUESTED'
        # for label value NeedInfo
        tracker_pb2.ApprovalValue(
            approval_id=11, status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED),
        # problem = approval ChromeOS-Leadership-Exp has status 'NA' for label
        # value Yes.
        tracker_pb2.ApprovalValue(
            approval_id=13, status=tracker_pb2.ApprovalStatus.NA)
    ]

    # problem = no phase field for label Launch-M-Approved-79-Stable-Exp
    # problem = no phase field for label Launch-M-Target-70-Stable
    self.issue5.field_values = [
        tracker_pb2.FieldValue(field_id=8, int_value=71, phase_id=8),
        tracker_bizobj.MakeFieldValue(4, None, None, 111, None, None, False),
        tracker_bizobj.MakeFieldValue(5, None, None, 111, None, None, False)]

    self.config.field_defs = [
        tracker_pb2.FieldDef(field_id=1, field_name='Chrome-Test'),
        tracker_pb2.FieldDef(field_id=2, field_name='Chrome-UX'),
        tracker_pb2.FieldDef(field_id=3, field_name='Chrome-Privacy'),
        tracker_pb2.FieldDef(field_id=4, field_name='PM'),
        tracker_pb2.FieldDef(field_id=5, field_name='TL'),
        tracker_pb2.FieldDef(field_id=6, field_name='TE'),
        tracker_pb2.FieldDef(field_id=12, field_name='UX'),
        tracker_pb2.FieldDef(field_id=7, field_name='M-Target'),
        tracker_pb2.FieldDef(field_id=8, field_name='M-Approved'),
        tracker_pb2.FieldDef(field_id=9, field_name='ChromeOS-UX'),
        tracker_pb2.FieldDef(field_id=10, field_name='ChromeOS-Enterprise'),
        tracker_pb2.FieldDef(field_id=11, field_name='ChromeOS-Privacy'),
        tracker_pb2.FieldDef(field_id=13, field_name='ChromeOS-Leadership-Exp')
    ]

    # Set up mocks
    patcher = mock.patch(
        'search.frontendsearchpipeline.FrontendSearchPipeline',
        spec=True, allowed_results=[
            self.issue1, self.issue2, self.issue3, self.issue4, self.issue5])
    mockPipeline = patcher.start()
    self.task.services.project.GetProjectByName = mock.Mock()
    self.task.services.config.GetProjectConfig = mock.Mock(
        return_value=self.config)
    self.task.services.issue.GetIssue = mock.Mock(
        side_effect=[
            self.issue1, self.issue2, self.issue3, self.issue4, self.issue5])
    self.task.services.user.LookupUserID = mock.Mock(return_value=111)
    with self.work_env as we:
      we.ListIssues = mock.Mock(return_value=mockPipeline)

    # Assert
    json = self.task.VerifyConversion(self.mr)
    self.assertEqual(json['issues verified'],
                     ['issue 1', 'issue 2', 'issue 3', 'issue 4', 'issue 5'])
    problems = json['problems found']
    expected_problems = [
        'issue 1: missing a field for TL',
        'issue 1: missing a field for UX',
        'issue 2: approval Chrome-Privacy has status \'APPROVED\' for '
        'label value None',
        'issue 2: no phase field for label Launch-M-Approved-70-Beta',
        'issue 3: missing a field for TL',
        'issue 3: no phase field for label Launch-M-Target-70-Stable',
        'issue 4: incorrect phases for OS default launch.',
        'issue 4: approval ChromeOS-UX has status \'NEEDS_REVIEW\' for '
        'label value Yes',
        'issue 5: approval ChromeOS-Privacy has status \'REVIEW_REQUESTED\' '
        'for label value NeedInfo',
        'issue 5: approval ChromeOS-Leadership-Exp has status \'NA\' for label '
        'value Yes',
        'issue 5: no phase field for label Launch-M-Approved-79-Stable-Exp',
        'issue 5: no phase field for label Launch-M-Target-70-Stable',
    ]
    self.assertEqual(problems, expected_problems)
    patcher.stop()

  def testFetchAndAssertProjectInfo(self):

    # test no 'launch' in request
    self.assertRaisesRegexp(
        AssertionError, r'bad launch type:',
        self.task.FetchAndAssertProjectInfo, self.mr)

    # test bad 'launch' in request
    mr = testing_helpers.MakeMonorailRequest(path='url/url?launch=bad')
    self.assertRaisesRegexp(
        AssertionError, r'bad launch type: bad',
        self.task.FetchAndAssertProjectInfo, mr)

    self.task.services.project.GetProjectByName = mock.Mock()
    self.task.services.config.GetProjectConfig = mock.Mock(
        return_value=self.config)

    mr = testing_helpers.MakeMonorailRequest(path='url/url?launch=default')
    # test no template
    self.task.services.template.GetTemplateByName = mock.Mock(
        return_value=None)
    self.assertRaisesRegexp(
        AssertionError, r'not found in chromium project',
        self.task.FetchAndAssertProjectInfo, mr)

    # test template has no phases/approvals
    template = tracker_bizobj.MakeIssueTemplate(
        'template', 'sum', 'New', 111, 'content', [], [], [], [])
    self.task.services.template.GetTemplateByName = mock.Mock(
        return_value=template)
    self.assertRaisesRegexp(
        AssertionError, 'no approvals or phases in',
        self.task.FetchAndAssertProjectInfo, mr)

    # test phases not recognized
    template.phases = [tracker_pb2.Phase(name='WeirdPhase')]
    template.approval_values = [tracker_pb2.ApprovalValue()]
    self.assertRaisesRegexp(
        AssertionError, 'one or more phases not recognized',
        self.task.FetchAndAssertProjectInfo, mr)

    template.phases = [tracker_pb2.Phase(name='Stable'),
                       tracker_pb2.Phase(name='Stable-Exp')]
    template.approval_values = [
        tracker_pb2.ApprovalValue(approval_id=1),
        tracker_pb2.ApprovalValue(approval_id=2),
        tracker_pb2.ApprovalValue(approval_id=3)]

    # test approvals not recognized
    self.assertRaisesRegexp(
        AssertionError, 'one or more approvals not recognized',
        self.task.FetchAndAssertProjectInfo, mr)

    self.config.field_defs = [
        tracker_pb2.FieldDef(field_id=1, field_name='ChromeOS-Enterprise',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(field_id=2, field_name='Chrome-UX',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(field_id=3, field_name='Chrome-Privacy',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    ]

    # test approvals not in config's approval_defs
    self.assertRaisesRegexp(
        AssertionError, 'one or more approvals not in config.approval_defs',
        self.task.FetchAndAssertProjectInfo, mr)

    self.config.approval_defs = [
        tracker_pb2.ApprovalDef(approval_id=1),
        tracker_pb2.ApprovalDef(approval_id=2),
        tracker_pb2.ApprovalDef(approval_id=3)]

    # test no pm field exists in project
    self.assertRaisesRegexp(
        AssertionError, 'project has no FieldDef %s' % fltconversion.PM_FIELD,
        self.task.FetchAndAssertProjectInfo, mr)

    self.config.field_defs.extend([
      tracker_pb2.FieldDef(field_id=4, field_name='PM',
                           field_type=tracker_pb2.FieldTypes.USER_TYPE),
      tracker_pb2.FieldDef(field_id=5, field_name='TL',
                           field_type=tracker_pb2.FieldTypes.USER_TYPE),
      tracker_pb2.FieldDef(field_id=9, field_name='UX',
                           field_type=tracker_pb2.FieldTypes.USER_TYPE),
      tracker_pb2.FieldDef(field_id=6, field_name='TE')
    ])

    # test no USER_TYPE te field exists in project
    self.assertRaisesRegexp(
        AssertionError, 'project has no FieldDef %s' % fltconversion.TE_FIELD,
        self.task.FetchAndAssertProjectInfo, mr)

    self.config.field_defs[-1].field_type = tracker_pb2.FieldTypes.USER_TYPE
    self.config.field_defs.extend([
        tracker_pb2.FieldDef(
            field_id=7, field_name='M-Target', is_phase_field=True),
        tracker_pb2.FieldDef(
            field_id=8, field_name='M-Approved', is_multivalued=True,
            field_type=tracker_pb2.FieldTypes.INT_TYPE)
        ])

    # test no M-Target INT_TYPE multivalued Phase FieldDefs
    self.assertRaisesRegexp(
        AssertionError,
        'project has no FieldDef %s' % fltconversion.MTARGET_FIELD,
        self.task.FetchAndAssertProjectInfo, mr)

    self.config.field_defs[-2].field_type = tracker_pb2.FieldTypes.INT_TYPE
    self.config.field_defs[-2].is_multivalued = True

    # test no M-Approved INT_TYPE multivalued Phase FieldDefs
    self.assertRaisesRegexp(
        AssertionError,
        'project has no FieldDef %s' % fltconversion.MAPPROVED_FIELD,
        self.task.FetchAndAssertProjectInfo, mr)

    self.config.field_defs[-1].is_phase_field = True

    self.assertEqual(
        self.task.FetchAndAssertProjectInfo(mr),
        fltconversion.ProjectInfo(
            self.config, fltconversion.QUERY_MAP['default'],
            template.approval_values, template.phases, 4, 5, 6, 9, 7, 8,
            fltconversion.BROWSER_PHASE_MAP,
            fltconversion.BROWSER_APPROVALS_TO_LABELS,
            fltconversion.BROWSER_M_LABELS_RE))

    # FINCH special case
    # test approvals for Finch not required
    mr = testing_helpers.MakeMonorailRequest(path='url/url?launch=finch')
    self.assertRaisesRegexp(
        AssertionError, 'finch template not set up correctly',
        self.task.FetchAndAssertProjectInfo, mr)

    for av in template.approval_values:
      av.status = tracker_pb2.ApprovalStatus.NEEDS_REVIEW

    self.assertEqual(
        self.task.FetchAndAssertProjectInfo(mr),
        fltconversion.ProjectInfo(
            self.config, fltconversion.QUERY_MAP['finch'],
            template.approval_values, template.phases, 4, 5, 6, 9, 7, 8,
            fltconversion.BROWSER_PHASE_MAP,
            fltconversion.BROWSER_APPROVALS_TO_LABELS,
            fltconversion.BROWSER_M_LABELS_RE))

  def testFetchAndAssertProjectInfo_OS(self):
    self.task.services.project.GetProjectByName = mock.Mock()
    self.task.services.config.GetProjectConfig = mock.Mock(
        return_value=self.config)

    mr = testing_helpers.MakeMonorailRequest(path='url/url?launch=os')
    template = tracker_bizobj.MakeIssueTemplate(
        'template', 'sum', 'New', 111, 'content', [], [], [], [])
    self.task.services.template.GetTemplateByName = mock.Mock(
        return_value=template)

    # test phases not recognized
    template.phases = [tracker_pb2.Phase(name='Chrome-Test')]
    template.approval_values = [tracker_pb2.ApprovalValue()]
    self.assertRaisesRegexp(
        AssertionError, 'one or more phases not recognized',
        self.task.FetchAndAssertProjectInfo, mr)

    template.phases = [tracker_pb2.Phase(name='feature freeze'),
                       tracker_pb2.Phase(name='branch')]

    # test template not set up correctly
    template.approval_values = [
        tracker_pb2.ApprovalValue(approval_id=1),
        tracker_pb2.ApprovalValue(approval_id=2),
        tracker_pb2.ApprovalValue(approval_id=3)]
    self.assertRaisesRegexp(
        AssertionError, 'os template not set up correctly',
        self.task.FetchAndAssertProjectInfo, mr)

    for av in template.approval_values:
      av.status = tracker_pb2.ApprovalStatus.NEEDS_REVIEW

    # test approvals not recognized
    self.assertRaisesRegexp(
        AssertionError, 'one or more approvals not recognized',
        self.task.FetchAndAssertProjectInfo, mr)

    self.config.field_defs = [
        tracker_pb2.FieldDef(field_id=1, field_name='ChromeOS-Enterprise',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(field_id=2, field_name='ChromeOS-UX',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(field_id=3, field_name='ChromeOS-Privacy',
                             field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    ]

    # Skip remaining checks. No different from Browser process.
    self.config.approval_defs = [
        tracker_pb2.ApprovalDef(approval_id=1),
        tracker_pb2.ApprovalDef(approval_id=2),
        tracker_pb2.ApprovalDef(approval_id=3)]

    self.config.field_defs.extend([
      tracker_pb2.FieldDef(field_id=4, field_name='PM',
                           field_type=tracker_pb2.FieldTypes.USER_TYPE),
      tracker_pb2.FieldDef(field_id=5, field_name='TL',
                           field_type=tracker_pb2.FieldTypes.USER_TYPE),
      tracker_pb2.FieldDef(field_id=6, field_name='TE',
                           field_type=tracker_pb2.FieldTypes.USER_TYPE),
      tracker_pb2.FieldDef(field_id=9, field_name='UX',
                           field_type=tracker_pb2.FieldTypes.USER_TYPE)
    ])
    self.config.field_defs.extend([
        tracker_pb2.FieldDef(
            field_id=7, field_name='M-Target', is_phase_field=True,
            is_multivalued=True, field_type=tracker_pb2.FieldTypes.INT_TYPE),
        tracker_pb2.FieldDef(
            field_id=8, field_name='M-Approved', is_phase_field=True,
            is_multivalued=True, field_type=tracker_pb2.FieldTypes.INT_TYPE)
    ])

    self.assertEqual(
        self.task.FetchAndAssertProjectInfo(mr),
        fltconversion.ProjectInfo(
            self.config, fltconversion.QUERY_MAP['os'],
            template.approval_values, template.phases, 4, 5, 6, 9, 7, 8,
            fltconversion.OS_PHASE_MAP, fltconversion.OS_APPROVALS_TO_LABELS,
            fltconversion.OS_M_LABELS_RE))

  @mock.patch('time.time')
  def testExecuteIssueChanges(self, mockTime):
    mockTime.return_value = 123
    self.task.services.issue._UpdateIssuesApprovals = mock.Mock()
    self.task.services.issue.DeltaUpdateIssue = mock.Mock(
        return_value=([], None))
    self.task.services.issue.InsertComment = mock.Mock()
    self.config.approval_defs = [
        tracker_pb2.ApprovalDef(
            # test empty survey
            approval_id=1, survey='', approver_ids=[111, 222]),
        tracker_pb2.ApprovalDef(approval_id=2), # test missing survey
        tracker_pb2.ApprovalDef(survey='Missing approval_id should not error.'),
        tracker_pb2.ApprovalDef(approval_id=3, survey='Q1\nQ2\n\nQ3'),
        tracker_pb2.ApprovalDef(approval_id=4, survey='Q1\nQ2\n\nQ3 two'),
        tracker_pb2.ApprovalDef()]

    new_avs = [tracker_pb2.ApprovalValue(
        approval_id=1, status=tracker_pb2.ApprovalStatus.APPROVED),
               tracker_pb2.ApprovalValue(approval_id=4),
               tracker_pb2.ApprovalValue(approval_id=2),
               tracker_pb2.ApprovalValue(approval_id=3)]

    phases = [tracker_pb2.Phase(phase_id=1, name='Phase1', rank=1)]
    new_fvs = [tracker_bizobj.MakeFieldValue(
        11, 70, None, None, None, None, False, phase_id=1),
               tracker_bizobj.MakeFieldValue(
                   12, None, 'strfield', None, None, None, False)]
    _amendments = self.task.ExecuteIssueChanges(
        self.config, self.issue, new_avs, phases, new_fvs)

    # approver_ids set in ExecuteIssueChanges()
    new_avs[0].approver_ids = [111, 222]
    self.issue.approval_values = new_avs
    self.issue.phases = phases
    delta = tracker_pb2.IssueDelta(
        labels_add=['Type-FLT-Launch', 'FLT-Conversion'],
        labels_remove=['Type-Launch'], field_vals_add=new_fvs)
    cmt_1 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='', is_description=True, approval_id=1, timestamp=123)
    cmt_2 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='', is_description=True, approval_id=2, timestamp=123)
    cmt_3 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='<b>Q1</b>\n<b>Q2</b>\n<b></b>\n<b>Q3</b>',
        is_description=True, approval_id=3, timestamp=123)
    cmt_4 = tracker_pb2.IssueComment(
        issue_id=78901, project_id=789, user_id=self.mr.auth.user_id,
        content='<b>Q1</b>\n<b>Q2</b>\n<b></b>\n<b>Q3 two</b>',
        is_description=True, approval_id=4, timestamp=123)


    comment_calls = [mock.call(self.mr.cnxn, cmt_1),
                     mock.call(self.mr.cnxn, cmt_4),
                     mock.call(self.mr.cnxn, cmt_2),
                     mock.call(self.mr.cnxn, cmt_3)]
    self.task.services.issue.InsertComment.assert_has_calls(comment_calls)

    self.task.services.issue._UpdateIssuesApprovals.assert_called_once_with(
        self.mr.cnxn, self.issue)
    self.task.services.issue.DeltaUpdateIssue.assert_called_once_with(
        self.mr.cnxn, self.task.services, self.mr.auth.user_id, 789,
        self.config, self.issue, delta,
        comment=fltconversion.CONVERSION_COMMENT)

  def testConvertPeopleLabels(self):
    self.task.services.user.LookupUserID = mock.Mock(
        side_effect=[1, 2, 3, 4, 5, 6])
    labels = [
        'pm-u1', 'pm-u2', 'tl-u2', 'test-3', 'test-4', 'ux-u5', 'ux-6']
    fvs = self.task.ConvertPeopleLabels(self.mr, labels, 11, 12, 13, 14)
    expected = [
        tracker_bizobj.MakeFieldValue(11, None, None, 1, None, None, False),
        tracker_bizobj.MakeFieldValue(12, None, None, 2, None, None, False),
        tracker_bizobj.MakeFieldValue(13, None, None, 3, None, None, False),
        tracker_bizobj.MakeFieldValue(13, None, None, 4, None, None, False),
        tracker_bizobj.MakeFieldValue(14, None, None, 5, None, None, False),
        tracker_bizobj.MakeFieldValue(14, None, None, 6, None, None, False),
        ]
    self.assertEqual(fvs, expected)

  def testConvertPeopleLabels_NoUsers(self):
    def side_effect(_cnxn, _email):
      raise exceptions.NoSuchUserException()
    labels = []
    self.task.services.user.LookupUserID = mock.Mock(side_effect=side_effect)
    self.assertFalse(
        len(self.task.ConvertPeopleLabels(self.mr, labels, 11, 12, 13, 14)))

  def testCreateUserFieldValue_Chromium(self):
    self.task.services.user.LookupUserID = mock.Mock(return_value=1)
    actual = self.task.CreateUserFieldValue(self.mr, 'ldap', 11)
    expected = tracker_bizobj.MakeFieldValue(
        11, None, None, 1, None, None, False)
    self.assertEqual(actual, expected)
    self.task.services.user.LookupUserID.assert_called_once_with(
        self.mr.cnxn, 'ldap@chromium.org')

  def testCreateUserFieldValue_Goog(self):
    def side_effect(_cnxn, email):
      if email.endswith('chromium.org'):
        raise exceptions.NoSuchUserException()
      else:
        return 2
    self.task.services.user.LookupUserID = mock.Mock(side_effect=side_effect)
    actual = self.task.CreateUserFieldValue(self.mr, 'ldap', 11)
    expected = tracker_bizobj.MakeFieldValue(
        11, None, None, 2, None, None, False)
    self.assertEqual(actual, expected)
    self.task.services.user.LookupUserID.assert_any_call(
        self.mr.cnxn, 'ldap@chromium.org')
    self.task.services.user.LookupUserID.assert_any_call(
        self.mr.cnxn, 'ldap@google.com')

  def testCreateUserFieldValue_NoUserFound(self):
    def side_effect(_cnxn, _email):
      raise exceptions.NoSuchUserException()
    self.task.services.user.LookupUserID = mock.Mock(side_effect=side_effect)
    self.assertIsNone(self.task.CreateUserFieldValue(self.mr, 'ldap', 11))


class ConvertMLabels(unittest.TestCase):

  def setUp(self):
    self.target_id = 24
    self.approved_id = 27
    self.beta_phase = tracker_pb2.Phase(phase_id=1, name='bEtA')
    self.stable_phase = tracker_pb2.Phase(phase_id=2, name='StAbLe')
    self.stable_full_phase = tracker_pb2.Phase(phase_id=3, name='stable-FULL')
    self.stable_exp_phase = tracker_pb2.Phase(phase_id=4, name='STABLE-exp')
    self.feature_freeze_phase = tracker_pb2.Phase(
        phase_id=5, name='FEATURE Freeze')
    self.branch_phase = tracker_pb2.Phase(phase_id=6, name='bRANCH')

  def testConvertMLabels_NormalFinch(self):

    phases = [self.stable_exp_phase, self.beta_phase, self.stable_full_phase]
    labels = [
        'launch-m-approved-81-beta',  # beta:M-Approved=81
        'launch-m-target-80-stable-car',  # ignore
        'a-Launch-M-Target-80-Stable-car',  # ignore
        'launch-m-target-70-Stable',  # stable-full:M-Target=70
        'LAUNCH-M-TARGET-71-STABLE',  # stable-full:M-Target=71
        'launch-m-target-70-stable-exp',  # stable-exp:M-Target=70
        'launch-m-target-69-stable-exp',  # stable-exp:M-Target=69
        'launch-M-APPROVED-70-Stable-Exp',  # stable-exp:M-Approved-70
        'launch-m-approved-73-stable',  # stable-full:M-Approved-73
        'launch-m-error-73-stable',  # ignore
        'launch-m-approved-8-stable',  #ignore
        'irrelevant label-weird',  # ignore
    ]
    actual_fvs = fltconversion.ConvertMLabels(
        labels, phases, self.target_id, self.approved_id,
        fltconversion.BROWSER_M_LABELS_RE, fltconversion.BROWSER_PHASE_MAP)

    expected_fvs = [
      tracker_pb2.FieldValue(
          field_id=self.approved_id, int_value=81,
          phase_id=self.beta_phase.phase_id, derived=False,),
      tracker_pb2.FieldValue(
          field_id=self.target_id, int_value=70,
          phase_id=self.stable_full_phase.phase_id, derived=False),
      tracker_pb2.FieldValue(
          field_id=self.target_id, int_value=71,
          phase_id=self.stable_full_phase.phase_id, derived=False),
      tracker_pb2.FieldValue(
          field_id=self.target_id, int_value=70,
          phase_id=self.stable_exp_phase.phase_id, derived=False),
      tracker_pb2.FieldValue(
          field_id=self.target_id, int_value=69,
          phase_id=self.stable_exp_phase.phase_id, derived=False),
      tracker_pb2.FieldValue(
          field_id=self.approved_id, int_value=70,
          phase_id=self.stable_exp_phase.phase_id, derived=False),
      tracker_pb2.FieldValue(
          field_id=self.approved_id, int_value=73,
          phase_id=self.stable_full_phase.phase_id, derived=False)
    ]

    self.assertEqual(actual_fvs, expected_fvs)

  def testConvertMLabels_OS(self):
    phases = [self.feature_freeze_phase, self.branch_phase, self.stable_phase]
    labels = [
        'launch-m-approved-81-beta',  # ignore
        'launch-m-target-80-stable-car',  # ignore
        'a-Launch-M-Target-80-Stable-car',  # ignore
        'launch-m-target-70-Stable',  # stable:M-Target=70
        'LAUNCH-M-TARGET-71-STABLE',  # stable:M-Target=71
        'launch-m-target-70-stable-exp',  # ignore
        'launch-M-APPROVED-70-Stable-Exp',  # ignore
        'launch-m-approved-73-stable',  # stable:M-Approved-73
        'launch-m-error-73-stable',  # ignore
        'launch-m-approved-8-stable',  #ignore
        'irrelevant label-weird',  # ignore
        ]
    actual_fvs = fltconversion.ConvertMLabels(
        labels, phases, self.target_id, self.approved_id,
        fltconversion.OS_M_LABELS_RE, fltconversion.OS_PHASE_MAP)

    expected_fvs = [
      tracker_pb2.FieldValue(
          field_id=self.target_id, int_value=70,
          phase_id=self.stable_phase.phase_id, derived=False,),
      tracker_pb2.FieldValue(
          field_id=self.target_id, int_value=71,
          phase_id=self.stable_phase.phase_id, derived=False),
      tracker_pb2.FieldValue(
          field_id=self.approved_id, int_value=73,
          phase_id=self.stable_phase.phase_id, derived=False)
    ]

    self.assertEqual(actual_fvs, expected_fvs)


class ConvertLaunchLabels(unittest.TestCase):

  def setUp(self):
    self.project_fds = [
        tracker_pb2.FieldDef(
            field_id=1, project_id=789, field_name='String',
            field_type=tracker_pb2.FieldTypes.STR_TYPE),
        tracker_pb2.FieldDef(
            field_id=2, project_id=789, field_name='Chrome-UX',
            field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE),
        tracker_pb2.FieldDef(
            field_id=3, project_id=789, field_name='Chrome-Privacy',
            field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
        ]
    approvalUX = tracker_pb2.ApprovalValue(
        approval_id=2, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    approvalPrivacy = tracker_pb2.ApprovalValue(approval_id=3)
    self.approvals = [approvalUX, approvalPrivacy]

  def testConvertLaunchLabels_Normal(self):
    labels = [
        'Launch-UX-NotReviewed', 'Launch-Privacy-Yes', 'Launch-NotRelevant']
    actual = fltconversion.ConvertLaunchLabels(
        labels, self.approvals, self.project_fds,
        fltconversion.BROWSER_APPROVALS_TO_LABELS)
    expected = [
      tracker_pb2.ApprovalValue(
          approval_id=2, status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW),
      tracker_pb2.ApprovalValue(
          approval_id=3, status=tracker_pb2.ApprovalStatus.APPROVED)
    ]
    self.assertEqual(actual, expected)

  def testConvertLaunchLabels_ExtraAndMissingLabels(self):
    labels = [
        'Blah-Launch-Privacy-Yes',  # Missing, this is not a valid Label
        'Launch-Security-Yes',  # Extra, no matching approval in given approvals
        'Launch-UI-Yes']  # Missing Launch-Privacy
    actual = fltconversion.ConvertLaunchLabels(
        labels, self.approvals, self.project_fds,
        fltconversion.BROWSER_APPROVALS_TO_LABELS)
    expected = [
        tracker_pb2.ApprovalValue(
            approval_id=2, status=tracker_pb2.ApprovalStatus.APPROVED),
      tracker_pb2.ApprovalValue(
          approval_id=3, status=tracker_pb2.ApprovalStatus.NOT_SET)
        ]
    self.assertEqual(actual, expected)

class ExtractLabelLDAPs(unittest.TestCase):

  def testExtractLabelLDAPs_Normal(self):
    labels = [
        'tl-USER1',
        'pm-',
        'tL-User2',
        'test-user4',
        'PM-USER3',
        'pm',
        'test-user5',
        'test-',
        'ux-user9']
    (actual_pm, actual_tl, actual_tests,
     actual_ux) = fltconversion.ExtractLabelLDAPs(labels)
    self.assertEqual(actual_pm, 'user3')
    self.assertEqual(actual_tl, 'user2')
    self.assertEqual(actual_tests, ['user4', 'user5'])
    self.assertEqual(actual_ux, ['user9'])

  def testExtractLabelLDAPs_NoLabels(self):
    (actual_pm, actual_tl, actual_tests,
     actual_ux) = fltconversion.ExtractLabelLDAPs([])
    self.assertIsNone(actual_pm)
    self.assertIsNone(actual_tl)
    self.assertFalse(len(actual_tests))
    self.assertFalse(len(actual_ux))
