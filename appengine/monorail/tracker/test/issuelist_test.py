# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issuelist module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

from google.appengine.ext import testbed
from third_party import ezt

import settings
from framework import framework_helpers
from framework import permissions
from framework import table_view_helpers
from proto import tracker_pb2
from proto import user_pb2
from search import frontendsearchpipeline
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import issuelist
from tracker import tablecell
from tracker import tracker_bizobj
from tracker import tracker_constants


class IssueListUnitTest(unittest.TestCase):
  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        usergroup=fake.UserGroupService(),
        issue=fake.IssueService(),
        issue_star=fake.IssueStarService(),
        cache_manager=fake.CacheManager(),
        features=fake.FeaturesService(),
        user=fake.UserService())
    self.servlet = issuelist.IssueList(
        'req', 'res', services=self.services)
    self.project = self.services.project.TestAddProject('proj')
    self.issue1 = fake.MakeTestIssue(
        1, 1, 'issue_summary', 'New', 111, project_name='proj')
    self.services.issue.TestAddIssue(self.issue1)
    self.mr = testing_helpers.MakeMonorailRequest(project=self.project)
    self.mr.project_name = self.project.project_name
    self.mr.auth.effective_ids = {111}
    self.mr.me_user_id = 111

    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

  @mock.patch('search.frontendsearchpipeline._StartBackendSearch')
  @mock.patch('search.frontendsearchpipeline._FinishBackendSearch')
  def testGatherPageData(self, mockFinishBackendSearch, mockStartBackendSearch):
    url_params = [(name, self.mr.GetParam(name)) for name in
                  framework_helpers.RECOGNIZED_PARAMS]
    mockStartBackendSearch.return_value = []
    page_data = self.servlet.GatherPageData(self.mr)
    mockStartBackendSearch.assert_called_with(
        self.mr.cnxn, ['proj'], [self.project.project_id],
        mock.ANY, {}, {}, {}, set(),
        self.services, [self.mr.me_user_id], 0, self.mr.num, url_params,
        [''], self.mr.can, self.mr.group_by_spec, self.mr.sort_spec,
        self.mr.warnings, self.mr.use_cached_searches)
    mockFinishBackendSearch.assert_called_with([])
    self.assertEqual(page_data['list_mode'], ezt.boolean(True))

  def testGetTableViewData(self):
    # TODO(jrobbins): write tests for this method.
    pass

  def testGatherHelpData_GridSwitchesToIDs(self):
    servlet = issuelist.IssueList('req', 'res', services=self.services)
    mr = testing_helpers.MakeMonorailRequest()
    page_data = {'results': [1, 2, 3]}

    # Don't show cue if in issue list mode (the default).
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertNotEqual('showing_ids_instead_of_tiles', help_data['cue'])

    mr.mode = 'grid'
    # Don't show cue if showing already IDs (the default).
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertNotEqual('showing_ids_instead_of_tiles', help_data['cue'])

    mr.cells = 'counts'
    # Don't show cue if showing counts.
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertNotEqual('showing_ids_instead_of_tiles', help_data['cue'])

    mr.cells = 'tiles'
    # Don't show cue if there were <= 1000 results
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertNotEqual('showing_ids_instead_of_tiles', help_data['cue'])

    # Show cue if there are more than 1000 results
    page_data = {'results': [1] * (settings.max_tiles_in_grid + 1)}
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertEqual('showing_ids_instead_of_tiles', help_data['cue'])

  def testGatherHelpData_KeystrokeHelp(self):
    servlet = issuelist.IssueList('req', 'res', services=self.services)
    mr = testing_helpers.MakeMonorailRequest()

    page_data = {'table_data': []}

    # Signed in users see a cue to try "?" to see keyboard shortcuts.
    mr.auth.user_id = 111
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertEqual('dit_keystrokes', help_data['cue'])

    # Anon users do not see the cue.
    mr.auth.user_id = 0
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertEqual(None, help_data['cue'])

  def testGatherHelpData_ItalicsMeanDerived(self):
    servlet = issuelist.IssueList('req', 'res', services=self.services)
    mr = testing_helpers.MakeMonorailRequest()

    page_data = {'table_data': []}

    cell = table_view_helpers.TableCell(
        table_view_helpers.CELL_TYPE_ATTR, [1, 2, 3],
        derived_values=[4, 5, 6])
    page_data_with_derived = {
        'table_data': [table_view_helpers.TableRow([cell])]
        }

    # Users see a cue about italics, iff there are any
    # derived values shown in the list.
    help_data = servlet.GatherHelpData(mr, page_data_with_derived)
    self.assertEqual('italics_mean_derived', help_data['cue'])
    help_data = servlet.GatherHelpData(mr, page_data)
    self.assertNotEqual('italics_mean_derived', help_data['cue'])


CELL_FACTORIES = {
    'id': tablecell.TableCellID,
    'summary': table_view_helpers.TableCellSummary,
    'status': tablecell.TableCellStatus,
    'owner': tablecell.TableCellOwner,
    }


class IssueListFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testAnyDerivedValues(self):
    cell1 = table_view_helpers.TableCell(
        table_view_helpers.CELL_TYPE_SUMMARY, ['this is a summary'])
    cell2 = table_view_helpers.TableCell(
        table_view_helpers.CELL_TYPE_ATTR, ['value'],
        derived_values=['derived'])

    table_data = [
        table_view_helpers.TableRow([cell1]),
        table_view_helpers.TableRow([])]
    self.assertFalse(issuelist._AnyDerivedValues(table_data))

    table_data = [
        table_view_helpers.TableRow([cell1, cell2]),
        table_view_helpers.TableRow([])]
    self.assertTrue(issuelist._AnyDerivedValues(table_data))

  def testMakeTableData_Normal(self):
    issue = fake.MakeTestIssue(
        789, 123, 'summary', 'New', 0,
        labels=['Type-Defect', 'Priority-Medium'])
    issue.project_name = 'proj'
    visible_results = [issue]

    # Standard columns
    lower_columns = _GetColumns()
    table_data = issuelist._MakeTableData(
        visible_results, [], lower_columns, [], {}, CELL_FACTORIES, {}, set(),
        self.config)
    self.assertEqual(1, len(table_data))
    row = table_data[0]
    self.assertEqual(len(lower_columns), len(row.cells))
    self.assertEqual([], row.group.cells)

    # Also test row info that we pass to JS code.
    self.assertEqual(123, row.local_id)
    self.assertEqual('proj', row.project_name)
    self.assertEqual('proj:123', row.issue_ref)
    self.assertEqual('/p/proj/issues/detail?id=123', row.issue_url)

    # 2 columns -> 2 cells with 1 value in each cell.
    lower_columns = ['type', 'priority']
    table_data = issuelist._MakeTableData(
        visible_results, [], lower_columns, [], {}, CELL_FACTORIES, {}, set(),
        self.config)
    self.assertEqual(1, len(table_data))
    row = table_data[0]
    self.assertEqual(len(lower_columns), len(row.cells))
    self.assertEqual(0, row.cells[0].col_index)
    self.assertEqual(1, len(row.cells[0].values))
    self.assertEqual('Defect', row.cells[0].values[0].item)
    self.assertEqual(1, row.cells[1].col_index)
    self.assertEqual(1, len(row.cells[1].values))
    self.assertEqual('Medium', row.cells[1].values[0].item)
    self.assertEqual([], row.group.cells)

  def testMakeTableData_Combined(self):
    issue = fake.MakeTestIssue(
        789, 1, 'summary', 'New', 0, labels=['Type-Defect', 'Priority-Medium'])
    visible_results = [issue]

    # A combined column -> 1 cell with 2 values in it.
    lower_columns = ['type/priority']
    table_data = issuelist._MakeTableData(
        visible_results, [], lower_columns, [], {}, CELL_FACTORIES, {}, set(),
        self.config)
    self.assertEqual(1, len(table_data))
    row = table_data[0]
    self.assertEqual(len(lower_columns), len(row.cells))
    self.assertEqual(0, row.cells[0].col_index)
    self.assertEqual(2, len(row.cells[0].values))
    self.assertEqual('Defect', row.cells[0].values[0].item)
    self.assertEqual('Medium', row.cells[0].values[1].item)
    self.assertEqual([], row.group.cells)

  def testMakeTableData_GroupBy(self):
    issue = fake.MakeTestIssue(
        789, 1, 'summary', 'New', 0, labels=['Type-Defect', 'Priority-Medium'])
    visible_results = [issue]

    # 2 columns -> 2 cells with 1 value in each cell, row is part of a 1-row
    # group of issues with type=defect.
    lower_columns = ['type', 'priority']
    table_data = issuelist._MakeTableData(
        visible_results, [], lower_columns, ['type'], {}, CELL_FACTORIES,
        {}, set(), self.config)
    self.assertEqual(1, len(table_data))
    row = table_data[0]
    self.assertEqual(len(lower_columns), len(row.cells))
    self.assertEqual(0, row.cells[0].col_index)
    self.assertEqual(1, len(row.cells[0].values))
    self.assertEqual('Defect', row.cells[0].values[0].item)
    self.assertEqual(1, row.cells[1].col_index)
    self.assertEqual(1, len(row.cells[1].values))
    self.assertEqual('Medium', row.cells[1].values[0].item)
    self.assertEqual(1, len(row.group.cells))
    self.assertEqual('Defect', row.group.cells[0].values[0].item)

  def testShouldPreviewOnHover(self):
    saved_flag = settings.enable_quick_edit
    user = user_pb2.User()

    settings.enable_quick_edit = True
    user.preview_on_hover = True
    self.assertTrue(issuelist._ShouldPreviewOnHover(user))
    user.preview_on_hover = False
    self.assertFalse(issuelist._ShouldPreviewOnHover(user))

    settings.enable_quick_edit = False
    user.preview_on_hover = True
    self.assertFalse(issuelist._ShouldPreviewOnHover(user))
    user.preview_on_hover = False
    self.assertFalse(issuelist._ShouldPreviewOnHover(user))

    settings.enable_quick_edit = saved_flag

  def testGetAllPhaseNames(self):
    issues = [
        fake.MakeTestIssue(789, 1, 'summary', 'New', 0,
                           phases=[
                               tracker_pb2.Phase(name='chicken'),
                               tracker_pb2.Phase(name='cow'),
                               tracker_pb2.Phase(name='dog'),
                               tracker_pb2.Phase(name='goat')]),
        fake.MakeTestIssue(789, 2, 'summary', 'New', 0,
                           phases=[
                               tracker_pb2.Phase(name='CHICKEN'),
                               tracker_pb2.Phase(name='hippo')]),
        fake.MakeTestIssue(789, 2, 'summary', 'New', 0),
        ]
    self.assertItemsEqual(
        issuelist._GetAllPhaseNames(issues),
        ['chicken', 'cow', 'dog', 'goat', 'hippo'])

  def testGetAllPhaseNames_None(self):
    self.assertItemsEqual(
        issuelist._GetAllPhaseNames(None), [])


def _GetColumns():
  """Return a list of all well known column names."""

  columns = tracker_constants.DEFAULT_COL_SPEC.split()
  columns.extend(tracker_constants.OTHER_BUILT_IN_COLS)
  return [c.lower() for c in columns]
