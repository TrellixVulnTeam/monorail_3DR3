# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for services.template_svc module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

from mock import Mock, patch

from proto import tracker_pb2
from services import template_svc
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants


class TemplateSetTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.ts2lc = template_svc.TemplateSetTwoLevelCache(
        cache_manager=fake.CacheManager(),
        template_service=Mock(spec=template_svc.TemplateService))
    self.ts2lc.template_service.template_tbl = Mock()

  def testFetchItems_Empty(self):
    self.ts2lc.template_service.template_tbl.Select .return_value = []
    actual = self.ts2lc.FetchItems(cnxn=None, keys=[1, 2])
    self.assertEqual({1: [], 2: []}, actual)

  def testFetchItems_Normal(self):
    # pylint: disable=unused-argument
    def mockSelect(cnxn, cols, project_id, order_by):
      assert project_id in (1, 2)
      if project_id == 1:
        return [
          (8, 1, 'template-8', 'content', 'summary', False, 111, 'status',
              False, False, False),
          (9, 1, 'template-9', 'content', 'summary', False, 111, 'status',
              True, False, False)]
      else:
        return [
          (7, 2, 'template-7', 'content', 'summary', False, 111, 'status',
              False, False, False)]

    self.ts2lc.template_service.template_tbl.Select.side_effect = mockSelect
    actual = self.ts2lc.FetchItems(cnxn=None, keys=[1, 2])
    expected = {
      1: [(8, 'template-8', False), (9, 'template-9', True)],
      2: [(7, 'template-7', False)],
    }
    self.assertEqual(expected, actual)


class TemplateDefTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.template_def_2lc = template_svc.TemplateDefTwoLevelCache(
        cache_manager=fake.CacheManager(),
        template_service=Mock(spec=template_svc.TemplateService))
    self.template_def_2lc.template_service.template_tbl = Mock()
    self.template_def_2lc.template_service.template2label_tbl = Mock()
    self.template_def_2lc.template_service.template2component_tbl = Mock()
    self.template_def_2lc.template_service.template2admin_tbl = Mock()
    self.template_def_2lc.template_service.template2fieldvalue_tbl = Mock()
    self.template_def_2lc.template_service.issuephasedef_tbl = Mock()
    self.template_def_2lc.template_service.template2approvalvalue_tbl = Mock()

  def testFetchItems_Empty(self):
    self.template_def_2lc.template_service.template_tbl.Select\
        .return_value = []
    self.template_def_2lc.template_service.template2label_tbl.Select\
        .return_value = []
    self.template_def_2lc.template_service.template2component_tbl.Select\
        .return_value = []
    self.template_def_2lc.template_service.template2admin_tbl.Select\
        .return_value = []
    self.template_def_2lc.template_service.template2fieldvalue_tbl.Select\
        .return_value = []
    self.template_def_2lc.template_service.issuephasedef_tbl.Select\
        .return_value = []
    self.template_def_2lc.template_service.template2approvalvalue_tbl.Select\
        .return_value = []

    actual = self.template_def_2lc.FetchItems(cnxn=None, keys=[1, 2])
    self.assertEqual({}, actual)

  def testFetchItems_Normal(self):
    template_9_row = (9, 1, 'template-9', 'content', 'summary',
        False, 111, 'status',
        False, False, False)
    template_8_row = (8, 1, 'template-8', 'content', 'summary',
        False, 111, 'status',
        False, False, False)
    template_7_row = (7, 2, 'template-7', 'content', 'summary',
        False, 111, 'status',
        False, False, False)

    self.template_def_2lc.template_service.template_tbl.Select\
        .return_value = [template_7_row, template_8_row,
            template_9_row]
    self.template_def_2lc.template_service.template2label_tbl.Select\
        .return_value = [(9, 'label-1'), (7, 'label-2')]
    self.template_def_2lc.template_service.template2component_tbl.Select\
        .return_value = [(9, 13), (7, 14)]
    self.template_def_2lc.template_service.template2admin_tbl.Select\
        .return_value = [(9, 111), (7, 222)]

    fv1_row = (15, None, 'fv-1', None, None, None, False)
    fv2_row = (16, None, 'fv-2', None, None, None, False)
    fv1 = tracker_bizobj.MakeFieldValue(*fv1_row)
    fv2 = tracker_bizobj.MakeFieldValue(*fv2_row)
    self.template_def_2lc.template_service.template2fieldvalue_tbl.Select\
        .return_value = [((9,) + fv1_row[:-1]), ((7,) + fv2_row[:-1])]

    av1_row = (17, 9, 19, 'na')
    av2_row = (18, 7, 20, 'not_set')
    av1 = tracker_pb2.ApprovalValue(approval_id=17, phase_id=19,
                                    status=tracker_pb2.ApprovalStatus('NA'))
    av2 = tracker_pb2.ApprovalValue(approval_id=18, phase_id=20,
                                    status=tracker_pb2.ApprovalStatus(
                                        'NOT_SET'))
    phase1_row = (19, 'phase-1', 1)
    phase2_row = (20, 'phase-2', 2)
    phase1 = tracker_pb2.Phase(phase_id=19, name='phase-1', rank=1)
    phase2 = tracker_pb2.Phase(phase_id=20, name='phase-2', rank=2)

    self.template_def_2lc.template_service.template2approvalvalue_tbl.Select\
        .return_value = [av1_row, av2_row]
    self.template_def_2lc.template_service.issuephasedef_tbl.Select\
        .return_value = [phase1_row, phase2_row]

    actual = self.template_def_2lc.FetchItems(cnxn=None, keys=[7, 8, 9])
    self.assertEqual(3, len(list(actual.keys())))
    self.assertTrue(isinstance(actual[7], tracker_pb2.TemplateDef))
    self.assertTrue(isinstance(actual[8], tracker_pb2.TemplateDef))
    self.assertTrue(isinstance(actual[9], tracker_pb2.TemplateDef))

    self.assertEqual(7, actual[7].template_id)
    self.assertEqual(8, actual[8].template_id)
    self.assertEqual(9, actual[9].template_id)

    self.assertEqual(['label-2'], actual[7].labels)
    self.assertEqual([], actual[8].labels)
    self.assertEqual(['label-1'], actual[9].labels)

    self.assertEqual([14], actual[7].component_ids)
    self.assertEqual([], actual[8].component_ids)
    self.assertEqual([13], actual[9].component_ids)

    self.assertEqual([222], actual[7].admin_ids)
    self.assertEqual([], actual[8].admin_ids)
    self.assertEqual([111], actual[9].admin_ids)

    self.assertEqual([fv2], actual[7].field_values)
    self.assertEqual([], actual[8].field_values)
    self.assertEqual([fv1], actual[9].field_values)

    self.assertEqual([phase2], actual[7].phases)
    self.assertEqual([], actual[8].phases)
    self.assertEqual([phase1], actual[9].phases)

    self.assertEqual([av2], actual[7].approval_values)
    self.assertEqual([], actual[8].approval_values)
    self.assertEqual([av1], actual[9].approval_values)


class TemplateServiceTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = Mock()
    self.template_service = template_svc.TemplateService(fake.CacheManager())
    self.template_service.template_set_2lc = Mock()
    self.template_service.template_def_2lc = Mock()

  def testCreateDefaultProjectTemplates_Normal(self):
    self.template_service.CreateIssueTemplateDef = Mock()
    self.template_service.CreateDefaultProjectTemplates(self.cnxn, 789)

    expected_calls = [
        mock.call(self.cnxn, 789, tpl['name'], tpl['content'], tpl['summary'],
          tpl['summary_must_be_edited'], tpl['status'],
          tpl.get('members_only', False), True, False, None, tpl['labels'],
          [], [], [], [])
        for tpl in tracker_constants.DEFAULT_TEMPLATES]
    self.template_service.CreateIssueTemplateDef.assert_has_calls(
        expected_calls, any_order=True)

  def testGetTemplateByName_Normal(self):
    """GetTemplateByName returns a template that exists."""
    result_dict = {789: [(1, 'one', 0)]}
    template = tracker_pb2.TemplateDef(name='one')
    self.template_service.template_set_2lc.GetAll.return_value = (
        result_dict, None)
    self.template_service.template_def_2lc.GetAll.return_value = (
        {1: template}, None)
    actual = self.template_service.GetTemplateByName(self.cnxn, 'one', 789)
    self.assertEqual(actual.template_id, template.template_id)

  def testGetTemplateByName_NotFound(self):
    """When GetTemplateByName is given the name of a template that does not
    exist."""
    result_dict = {789: [(1, 'one', 0)]}
    template = tracker_pb2.TemplateDef(name='one')
    self.template_service.template_set_2lc.GetAll.return_value = (
        result_dict, None)
    self.template_service.template_def_2lc.GetAll.return_value = (
        {1: template}, None)
    actual = self.template_service.GetTemplateByName(self.cnxn, 'two', 789)
    self.assertEqual(actual, None)

  def testGetTemplateById_Normal(self):
    """GetTemplateById_Normal returns a template that exists."""
    template = tracker_pb2.TemplateDef(template_id=1, name='one')
    self.template_service.template_def_2lc.GetAll.return_value = (
        {1: template}, None)
    actual = self.template_service.GetTemplateById(self.cnxn, 1)
    self.assertEqual(actual.template_id, template.template_id)

  def testGetTemplateById_NotFound(self):
    """When GetTemplateById is given the ID of a template that does not
    exist."""
    self.template_service.template_def_2lc.GetAll.return_value = (
        {}, None)
    actual = self.template_service.GetTemplateById(self.cnxn, 1)
    self.assertEqual(actual, None)

  def testGetTemplatesById_Normal(self):
    """GetTemplatesById_Normal returns a template that exists."""
    template = tracker_pb2.TemplateDef(template_id=1, name='one')
    self.template_service.template_def_2lc.GetAll.return_value = (
        {1: template}, None)
    actual = self.template_service.GetTemplatesById(self.cnxn, 1)
    self.assertEqual(actual[0].template_id, template.template_id)

  def testGetTemplatesById_NotFound(self):
    """When GetTemplatesById is given the ID of a template that does not
    exist."""
    self.template_service.template_def_2lc.GetAll.return_value = (
        {}, None)
    actual = self.template_service.GetTemplatesById(self.cnxn, 1)
    self.assertEqual(actual, [])

  def testGetProjectTemplates_Normal(self):
    template_set = [(1, 'one', 0), (2, 'two', 1)]
    result_dict = {789: template_set}
    self.template_service.template_set_2lc.GetAll.return_value = (
        result_dict, None)
    self.template_service.template_def_2lc.GetAll.return_value = (
        {1: tracker_pb2.TemplateDef()}, None)

    self.assertEqual([tracker_pb2.TemplateDef()],
        self.template_service.GetProjectTemplates(self.cnxn, 789))
    self.template_service.template_set_2lc.GetAll.assert_called_once_with(
        self.cnxn, [789])

  def testExpungeProjectTemplates(self):
    template_id_rows = [(1,), (2,)]
    self.template_service.template_tbl.Select = Mock(
        return_value=template_id_rows)
    self.template_service.template2label_tbl.Delete = Mock()
    self.template_service.template2component_tbl.Delete = Mock()
    self.template_service.template_tbl.Delete = Mock()

    self.template_service.ExpungeProjectTemplates(self.cnxn, 789)

    self.template_service.template_tbl.Select\
        .assert_called_once_with(self.cnxn, project_id=789, cols=['id'])
    self.template_service.template2label_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=[1, 2])
    self.template_service.template2component_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=[1, 2])
    self.template_service.template_tbl.Delete\
        .assert_called_once_with(self.cnxn, project_id=789)


class CreateIssueTemplateDefTest(TemplateServiceTest):

  def setUp(self):
    super(CreateIssueTemplateDefTest, self).setUp()

    self.template_service.template_tbl.InsertRow = Mock(return_value=1)
    self.template_service.template2label_tbl.InsertRows = Mock()
    self.template_service.template2component_tbl.InsertRows = Mock()
    self.template_service.template2admin_tbl.InsertRows = Mock()
    self.template_service.template2fieldvalue_tbl.InsertRows = Mock()
    self.template_service.issuephasedef_tbl.InsertRow = Mock(return_value=81)
    self.template_service.template2approvalvalue_tbl.InsertRows = Mock()
    self.template_service.template_set_2lc._StrToKey = Mock(return_value=789)

  def testCreateIssueTemplateDef(self):
    fv = tracker_bizobj.MakeFieldValue(
        1, None, 'somestring', None, None, None, False)
    av_23 = tracker_pb2.ApprovalValue(
        approval_id=23, phase_id=11,
        status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    av_24 = tracker_pb2.ApprovalValue(approval_id=24, phase_id=11)
    approval_values = [av_23, av_24]
    phases = [tracker_pb2.Phase(
        name='Canary', rank=11, phase_id=11)]

    actual_template_id = self.template_service.CreateIssueTemplateDef(
        self.cnxn, 789, 'template', 'content', 'summary', True, 'Available',
        True, True, True, owner_id=111, labels=['label'], component_ids=[3],
        admin_ids=[222], field_values=[fv], phases=phases,
        approval_values=approval_values)

    self.assertEqual(1, actual_template_id)

    self.template_service.template_tbl.InsertRow\
        .assert_called_once_with(self.cnxn, project_id=789, name='template',
            content='content', summary='summary', summary_must_be_edited=True,
            owner_id=111, status='Available', members_only=True,
            owner_defaults_to_member=True, component_required=True,
            commit=False)
    self.template_service.template2label_tbl.InsertRows\
        .assert_called_once_with(self.cnxn, template_svc.TEMPLATE2LABEL_COLS,
            [(1, 'label')], commit=False)
    self.template_service.template2component_tbl.InsertRows\
        .assert_called_once_with(self.cnxn,
            template_svc.TEMPLATE2COMPONENT_COLS,
            [(1, 3)], commit=False)
    self.template_service.template2admin_tbl.InsertRows\
        .assert_called_once_with(self.cnxn, template_svc.TEMPLATE2ADMIN_COLS,
            [(1, 222)], commit=False)
    self.template_service.template2fieldvalue_tbl.InsertRows\
        .assert_called_once_with(self.cnxn,
            template_svc.TEMPLATE2FIELDVALUE_COLS,
            [(1, 1, None, 'somestring', None, None, None)], commit=False)
    self.template_service.issuephasedef_tbl.InsertRow\
        .assert_called_once_with(self.cnxn, name='Canary',
            rank=11, commit=False)
    self.template_service.template2approvalvalue_tbl.InsertRows\
        .assert_called_once_with(self.cnxn,
            template_svc.TEMPLATE2APPROVALVALUE_COLS,
            [(23, 1, 81, 'needs_review'), (24, 1, 81, 'not_set')], commit=False)
    self.cnxn.Commit.assert_called_once_with()
    self.template_service.template_set_2lc.InvalidateKeys\
        .assert_called_once_with(self.cnxn, [789])


class UpdateIssueTemplateDefTest(TemplateServiceTest):

  def setUp(self):
    super(UpdateIssueTemplateDefTest, self).setUp()

    self.template_service.template_tbl.Update = Mock()
    self.template_service.template2label_tbl.Delete = Mock()
    self.template_service.template2label_tbl.InsertRows = Mock()
    self.template_service.template2admin_tbl.Delete = Mock()
    self.template_service.template2admin_tbl.InsertRows = Mock()
    self.template_service.template2approvalvalue_tbl.Delete = Mock()
    self.template_service.issuephasedef_tbl.InsertRow = Mock(return_value=1)
    self.template_service.template2approvalvalue_tbl.InsertRows = Mock()
    self.template_service.template_set_2lc._StrToKey = Mock(return_value=789)

  def testUpdateIssueTemplateDef(self):
    av_20 = tracker_pb2.ApprovalValue(approval_id=20, phase_id=11)
    av_21 = tracker_pb2.ApprovalValue(approval_id=21, phase_id=11)
    approval_values = [av_20, av_21]
    phases = [tracker_pb2.Phase(
        name='Canary', phase_id=11, rank=11)]
    self.template_service.UpdateIssueTemplateDef(
        self.cnxn, 789, 1, content='content', summary='summary',
        component_required=True, labels=[], admin_ids=[111],
        phases=phases, approval_values=approval_values)

    new_values = dict(
        content='content', summary='summary', component_required=True)
    self.template_service.template_tbl.Update\
        .assert_called_once_with(self.cnxn, new_values, id=1, commit=False)
    self.template_service.template2label_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.template2label_tbl.InsertRows\
        .assert_called_once_with(self.cnxn, template_svc.TEMPLATE2LABEL_COLS,
            [], commit=False)
    self.template_service.template2admin_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.template2admin_tbl.InsertRows\
        .assert_called_once_with(self.cnxn, template_svc.TEMPLATE2ADMIN_COLS,
            [(1, 111)], commit=False)
    self.template_service.template2approvalvalue_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.issuephasedef_tbl.InsertRow\
        .assert_called_once_with(self.cnxn, name='Canary',
            rank=11, commit=False)
    self.template_service.template2approvalvalue_tbl.InsertRows\
        .assert_called_once_with(self.cnxn,
            template_svc.TEMPLATE2APPROVALVALUE_COLS,
            [(20, 1, 1, 'not_set'), (21, 1, 1, 'not_set')], commit=False)
    self.cnxn.Commit.assert_called_once_with()
    self.template_service.template_set_2lc.InvalidateKeys\
        .assert_called_once_with(self.cnxn, [789])
    self.template_service.template_def_2lc.InvalidateKeys\
        .assert_called_once_with(self.cnxn, [1])


class DeleteTemplateTest(TemplateServiceTest):

  def testDeleteIssueTemplateDef(self):
    self.template_service.template2label_tbl.Delete = Mock()
    self.template_service.template2component_tbl.Delete = Mock()
    self.template_service.template2admin_tbl.Delete = Mock()
    self.template_service.template2fieldvalue_tbl.Delete = Mock()
    self.template_service.template2approvalvalue_tbl.Delete = Mock()
    self.template_service.template_tbl.Delete = Mock()
    self.template_service.template_set_2lc._StrToKey = Mock(return_value=789)

    self.template_service.DeleteIssueTemplateDef(self.cnxn, 789, 1)

    self.template_service.template2label_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.template2component_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.template2admin_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.template2fieldvalue_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.template2approvalvalue_tbl.Delete\
        .assert_called_once_with(self.cnxn, template_id=1, commit=False)
    self.template_service.template_tbl.Delete\
        .assert_called_once_with(self.cnxn, id=1, commit=False)
    self.cnxn.Commit.assert_called_once_with()
    self.template_service.template_set_2lc.InvalidateKeys\
        .assert_called_once_with(self.cnxn, [789])
    self.template_service.template_def_2lc.InvalidateKeys\
        .assert_called_once_with(self.cnxn, [1])


class ExpungeUsersInTemplatesTest(TemplateServiceTest):

  def setUp(self):
    super(ExpungeUsersInTemplatesTest, self).setUp()

    self.template_service.template2admin_tbl.Delete = Mock()
    self.template_service.template2fieldvalue_tbl.Delete = Mock()
    self.template_service.template_tbl.Update = Mock()

  def testExpungeUsersInTemplates(self):
    user_ids = [111, 222]
    self.template_service.ExpungeUsersInTemplates(self.cnxn, user_ids, limit=60)

    self.template_service.template2admin_tbl.Delete.assert_called_once_with(
            self.cnxn, admin_id=user_ids, commit=False, limit=60)
    self.template_service.template2fieldvalue_tbl\
        .Delete.assert_called_once_with(
            self.cnxn, user_id=user_ids, commit=False, limit=60)
    self.template_service.template_tbl.Update.assert_called_once_with(
        self.cnxn, {'owner_id': None}, owner_id=user_ids, commit=False)


class UnpackTemplateTest(unittest.TestCase):

  def testEmpty(self):
    with self.assertRaises(ValueError):
      template_svc.UnpackTemplate(())

  def testNormal(self):
    row = (1, 2, 'name', 'content', 'summary', False, 3, 'status', False,
        False, False)
    self.assertEqual(
        tracker_pb2.TemplateDef(template_id=1, name='name',
          content='content', summary='summary', summary_must_be_edited=False,
          owner_id=3, status='status', members_only=False,
          owner_defaults_to_member=False,
          component_required=False),
        template_svc.UnpackTemplate(row))
