# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from dto.test_location import TestLocation
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from services import git
from services import swarmed_test_util
from services.flake_failure import heuristic_analysis
from waterfall.test import wf_testcase


class HeuristicAnalysisTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.policy = datastore_stub_util.PseudoRandomHRConsistencyPolicy(
        probability=0)
    self.testbed.init_datastore_v3_stub(consistency_policy=self.policy)
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  def testGenerateSuspectedRanges(self):
    self.assertEqual([(None, 'r1')],
                     heuristic_analysis.GenerateSuspectedRanges(['r1'],
                                                                ['r1', 'r2']))
    self.assertEqual([('r1', 'r2')],
                     heuristic_analysis.GenerateSuspectedRanges(['r2'],
                                                                ['r1', 'r2']))
    self.assertEqual([(None, 'r1'), ('r3', 'r4'), ('r4', 'r5')],
                     heuristic_analysis.GenerateSuspectedRanges(
                         ['r1', 'r4', 'r5'], ['r1', 'r2', 'r3', 'r4', 'r5']))
    self.assertEqual([], heuristic_analysis.GenerateSuspectedRanges([], []))

  def testGetSuspectedRevisions(self):
    region_1 = Region(1, 5, 'r1', 'a', 'a@email.com', '2017-08-11 19:38:42')
    region_2 = Region(6, 10, 'r2', 'b', 'b@email.com', '2017-08-12 19:38:42')
    blame = Blame('r2', 'a.cc')
    blame.AddRegion(region_1)
    blame.AddRegion(region_2)
    revision_range = ['r2', 'r3']
    expected_suspected_revisions = ['r2']

    self.assertEqual(
        expected_suspected_revisions,
        heuristic_analysis.GetSuspectedRevisions(blame, revision_range))
    self.assertEqual([], heuristic_analysis.GetSuspectedRevisions([], ['r1']))
    self.assertEqual([], heuristic_analysis.GetSuspectedRevisions(
        blame, ['r4']))
    self.assertEqual([], heuristic_analysis.GetSuspectedRevisions(None, None))

  def testListCommitPositionsFromSuspectedRanges(self):
    self.assertEqual(  # No heuristic results.
        [], heuristic_analysis.ListCommitPositionsFromSuspectedRanges({}, []))
    self.assertEqual(  # Blame list not available.
        [],
        heuristic_analysis.ListCommitPositionsFromSuspectedRanges(
            {}, [('r1', 'r2')]))
    self.assertEqual(  # Blame list available. This should be the expected case.
        [1, 2],
        heuristic_analysis.ListCommitPositionsFromSuspectedRanges({
            'r1': 1,
            'r2': 2,
        }, [('r1', 'r2')]))
    self.assertEqual(  # First revision is suspected.
        [1],
        heuristic_analysis.ListCommitPositionsFromSuspectedRanges({
            'r1': 1,
            'r2': 2,
        }, [(None, 'r1')]))
    self.assertEqual(  # Two suspects in a row 'r3' and 'r4'.
        [1, 2, 3, 4],
        heuristic_analysis.ListCommitPositionsFromSuspectedRanges({
            'r1': 1,
            'r2': 2,
            'r3': 3,
            'r4': 4,
        }, [(None, 'r1'), ('r2', 'r3'), ('r3', 'r4')]))

  @mock.patch.object(git, 'GetCommitsInfo')
  @mock.patch.object(git, 'GetCommitPositionFromRevision')
  def testSaveFlakeCulpritsForSuspectedRevisions(self, mocked_commit_position,
                                                 mocked_commit_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    suspected_revision = 'r1'
    suspected_commit_position = 995
    suspected_revisions = [suspected_revision]

    mocked_commit_position.return_value = suspected_commit_position

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(commit_position=1000, git_hash=suspected_revision)
    ]
    analysis.Save()

    mocked_commit_info.return_value = {
        suspected_revision: {
            'revision': suspected_revision,
            'repo_name': 'chromium',
            'commit_position': suspected_commit_position,
            'url': 'url',
            'author': 'author@email.com'
        }
    }

    heuristic_analysis.SaveFlakeCulpritsForSuspectedRevisions(
        analysis.key.urlsafe(), suspected_revisions)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    suspect = FlakeCulprit.Get('chromium', suspected_revision)
    self.assertIsNotNone(suspect)
    self.assertIn(suspect.key.urlsafe(), analysis.suspect_urlsafe_keys)

  @mock.patch.object(git, 'GetCommitsInfo')
  @mock.patch.object(git, 'GetCommitPositionFromRevision')
  def testSaveFlakeCulpritsForSuspectedRevisionsNoChangeLog(
      self, mocked_commit_position, mocked_commit_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    suspected_revision = 'r1'
    suspected_commit_position = 995
    suspected_revisions = [suspected_revision]

    mocked_commit_position.return_value = suspected_commit_position

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)

    analysis.data_points = [
        DataPoint.Create(commit_position=1000, git_hash=suspected_revision)
    ]
    analysis.Save()

    mocked_commit_info.return_value = None
    heuristic_analysis.SaveFlakeCulpritsForSuspectedRevisions(
        analysis.key.urlsafe(), suspected_revisions)

    suspect = FlakeCulprit.Get('chromium', suspected_revision)
    self.assertIsNone(suspect)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  @mock.patch.object(git, 'GetCommitPositionFromRevision')
  def testSaveFlakeCulpritsForSuspectedRevisionsExistingCulprit(
      self, mocked_commit_position, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    suspected_revision = 'r1'
    suspect_commit_position = 995
    suspected_revisions = [suspected_revision]
    mocked_commit_position.return_value = suspect_commit_position

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.data_points = [
        DataPoint.Create(commit_position=1000, git_hash=suspected_revision)
    ]

    suspect = FlakeCulprit.Create('chromium', suspected_revision,
                                  suspect_commit_position)
    suspect.url = 'url'
    suspect.put()

    analysis.suspect_urlsafe_keys = [suspect.key.urlsafe()]
    analysis.Save()

    mocked_fn.return_value = None
    heuristic_analysis.SaveFlakeCulpritsForSuspectedRevisions(
        analysis.key.urlsafe(), suspected_revisions)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    self.assertIn(suspect.key.urlsafe(), analysis.suspect_urlsafe_keys)

  @mock.patch.object(swarmed_test_util, 'GetTestLocation')
  @mock.patch.object(CachedGitilesRepository, 'GetBlame')
  @mock.patch.object(git, 'GetCommitsBetweenRevisionsInOrder')
  def testIdentifySuspectedRanges(self, mock_revisions, mock_blame,
                                  mock_test_location):
    mock_blame.return_value = [Blame('r1000', 'a/b.cc')]
    mock_test_location.return_value = TestLocation(file='a/b.cc', line=1)
    mock_revisions.return_value = ['r997', 'r998', 'r999', 'r1000']

    suspected_revision = 'r1000'
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000, git_hash='r1000', pass_rate=0.5),
        DataPoint.Create(commit_position=997, git_hash='r997', pass_rate=1.0)
    ]

    analysis.Save()

    self.assertEqual([suspected_revision],
                     heuristic_analysis.IdentifySuspectedRevisions(analysis))

  @mock.patch.object(swarmed_test_util, 'GetTestLocation', return_value=None)
  def testIdentifysuspectedRangesNoTestLocation(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000, git_hash='r1000')
    ]
    analysis.Save()

    self.assertEqual([],
                     heuristic_analysis.IdentifySuspectedRevisions(analysis))

  @mock.patch.object(swarmed_test_util, 'GetTestLocation')
  @mock.patch.object(CachedGitilesRepository, 'GetBlame', return_value=None)
  def testIdentifySuspectedRangesFailedToGetBlame(self, _, mock_test_location):
    mock_test_location.return_value = TestLocation(file='a/b.cc', line=1)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000, git_hash='r1000', pass_rate=0.5),
        DataPoint.Create(commit_position=997, git_hash='r997', pass_rate=1.0)
    ]

    analysis.Save()

    self.assertEqual([],
                     heuristic_analysis.IdentifySuspectedRevisions(analysis))

  @mock.patch.object(swarmed_test_util, 'GetTestLocation')
  @mock.patch.object(CachedGitilesRepository, 'GetBlame')
  @mock.patch.object(git, 'GetCommitsBetweenRevisionsInOrder', return_value=[])
  def testIdentifySuspectedRangesFailedToGetRevisions(self, _, mock_blame,
                                                      mock_test_location):
    mock_blame.return_value = [Blame('r1000', 'a/b.cc')]
    mock_test_location.return_value = TestLocation(file='a/b.cc', line=1)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000, git_hash='r1000', pass_rate=0.5),
        DataPoint.Create(commit_position=997, git_hash='r997', pass_rate=1.0)
    ]

    analysis.Save()

    self.assertEqual([],
                     heuristic_analysis.IdentifySuspectedRevisions(analysis))

  @mock.patch.object(heuristic_analysis, 'IdentifySuspectedRevisions')
  @mock.patch.object(heuristic_analysis,
                     'SaveFlakeCulpritsForSuspectedRevisions')
  def testRunHeuristicAnalysis(self, mock_save, mock_revisions):
    mock_revisions.return_value = ['r1', 'r2']

    analysis = MasterFlakeAnalysis.Create('m', 'b', 321, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.5, commit_position=1000, build_number=100)
    ]
    analysis.Save()

    heuristic_analysis.RunHeuristicAnalysis(analysis)

    mock_revisions.assert_called_once_with(analysis)
    mock_save.assert_called_once_with(analysis.key.urlsafe(), ['r1', 'r2'])
