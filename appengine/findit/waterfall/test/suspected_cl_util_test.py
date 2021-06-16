# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from google.appengine.ext import ndb

from common.waterfall import failure_type
from libs import analysis_status
from libs import time_util
from model import analysis_approach_type
from model import suspected_cl_status
from model.base_build_model import BaseBuildModel
from model.base_suspected_cl import BaseSuspectedCL
from model.suspected_cl_confidence import ConfidenceInformation
from model.suspected_cl_confidence import SuspectedCLConfidence
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import suspected_cl_util
from waterfall.test import wf_testcase

SAMPLE_HEURISTIC_1 = ConfidenceInformation(
    correct=100, total=100, confidence=1.0, score=5)

SAMPLE_HEURISTIC_2 = ConfidenceInformation(
    correct=90, total=100, confidence=0.9, score=4)

SAMPLE_TRY_JOB = ConfidenceInformation(
    correct=99, total=100, confidence=0.99, score=None)

SAMPLE_HEURISTIC_TRY_JOB = ConfidenceInformation(
    correct=98, total=100, confidence=0.98, score=None)


class SuspectedCLUtilTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(SuspectedCLUtilTest, self).setUp()

    self.cl_confidences = SuspectedCLConfidence.Create()
    self.cl_confidences.compile_heuristic = [
        SAMPLE_HEURISTIC_1, SAMPLE_HEURISTIC_2
    ]
    self.cl_confidences.test_heuristic = [
        SAMPLE_HEURISTIC_2, SAMPLE_HEURISTIC_1
    ]
    self.cl_confidences.compile_try_job = SAMPLE_TRY_JOB
    self.cl_confidences.test_try_job = SAMPLE_TRY_JOB
    self.cl_confidences.compile_heuristic_try_job = SAMPLE_HEURISTIC_TRY_JOB
    self.cl_confidences.test_heuristic_try_job = SAMPLE_HEURISTIC_TRY_JOB
    self.cl_confidences.Save()

  def testCreateWfSuspectedCL(self):
    approach = analysis_approach_type.HEURISTIC
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    compile_failure_type = failure_type.COMPILE
    repo_name = 'chromium'
    revision = 'r1'
    commit_position = 1
    failures = {'compile': []}
    top_score = 5

    mocked_utcnow = datetime(2016, 10, 4, 0, 0, 0)
    self.MockUTCNow(mocked_utcnow)

    self.assertIsNone(WfSuspectedCL.Get(repo_name, revision))

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, compile_failure_type, failures, top_score)

    expected_builds = {
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number): {
            'approaches': [approach],
            'failure_type': compile_failure_type,
            'failures': failures,
            'status': None,
            'top_score': top_score
        }
    }

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual([analysis_approach_type.HEURISTIC],
                     suspected_cl.approaches)
    self.assertEqual([compile_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)
    self.assertEqual(mocked_utcnow, suspected_cl.identified_time)
    self.assertEqual(mocked_utcnow, suspected_cl.updated_time)

  def testUpdateWfSuspectedCLAddAnotherApproach(self):
    approach = analysis_approach_type.TRY_JOB
    master_name = 'm'
    builder_name = 'b'
    build_number = 122
    test_failure_type = failure_type.TEST
    repo_name = 'chromium'
    revision = 'r2'
    commit_position = 2
    failures = {'step_1': ['test1', 'test2']}
    top_score = None

    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.approaches = [analysis_approach_type.HEURISTIC]
    suspected_cl.builds = {
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': None,
            'top_score': 4
        }
    }
    suspected_cl.failure_type = [test_failure_type]
    suspected_cl.put()

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, test_failure_type, failures, top_score)

    expected_builds = {
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number): {
            'approaches': [
                analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB
            ],
            'failure_type':
                test_failure_type,
            'failures':
                failures,
            'status':
                None,
            'top_score':
                4
        }
    }

    expected_approaches = [
        analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB
    ]

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual(expected_approaches, suspected_cl.approaches)
    self.assertEqual([test_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)

  def testUpdateWfSuspectedCLAddSameBuild(self):
    approach = analysis_approach_type.HEURISTIC
    master_name = 'm'
    builder_name = 'b'
    build_number = 122
    test_failure_type = failure_type.TEST
    repo_name = 'chromium'
    revision = 'r2'
    commit_position = 2
    failures = {'step_1': ['test1', 'test2']}
    top_score = 4

    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.approaches = [analysis_approach_type.HEURISTIC]
    suspected_cl.builds = {
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': None,
            'top_score': 4
        }
    }
    suspected_cl.failure_type = [test_failure_type]
    suspected_cl.put()

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, test_failure_type, failures, top_score)

    expected_builds = {
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': None,
            'top_score': 4
        }
    }

    expected_approaches = [analysis_approach_type.HEURISTIC]

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual(expected_approaches, suspected_cl.approaches)
    self.assertEqual([test_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)

  def testUpdateWfSuspectedCLAddAnotherHeuristic(self):
    approach = analysis_approach_type.HEURISTIC
    master_name = 'm'
    builder_name = 'b'
    build_number = 122
    test_failure_type = failure_type.TEST
    repo_name = 'chromium'
    revision = 'r2'
    commit_position = 2
    failures = {'step_1': ['test1', 'test2']}
    top_score = 4

    suspected_cl = WfSuspectedCL.Create(repo_name, revision, commit_position)
    suspected_cl.approaches = [analysis_approach_type.HEURISTIC]
    suspected_cl.builds = {
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number - 1): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': {
                'step': ['test']
            },
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        },
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number - 2): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        }
    }
    suspected_cl.failure_type = [test_failure_type]
    suspected_cl.put()

    suspected_cl_util.UpdateSuspectedCL(
        repo_name, revision, commit_position, approach, master_name,
        builder_name, build_number, test_failure_type, failures, top_score)

    expected_builds = {
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number - 1): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': {
                'step': ['test']
            },
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        },
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number - 2): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        },
        BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                      build_number): {
            'approaches': [analysis_approach_type.HEURISTIC],
            'failure_type': test_failure_type,
            'failures': failures,
            'status': suspected_cl_status.CORRECT,
            'top_score': 4
        }
    }

    suspected_cl = WfSuspectedCL.Get(repo_name, revision)

    self.assertIsNotNone(suspected_cl)
    self.assertEqual([analysis_approach_type.HEURISTIC],
                     suspected_cl.approaches)
    self.assertEqual([test_failure_type], suspected_cl.failure_type)
    self.assertEqual(expected_builds, suspected_cl.builds)

  def testGetCLInfo(self):
    self.assertEqual(['chromium', 'rev1'],
                     suspected_cl_util.GetCLInfo('chromium/rev1'))

  def testGetConfidenceScoreTestHeuristic(self):
    build = {
        'failure_type': failure_type.TEST,
        'failures': None,
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.HEURISTIC],
        'top_score': 5
    }

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.test_heuristic[1].confidence),
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreCompileHeuristic(self):
    build = {
        'failure_type': failure_type.COMPILE,
        'failures': None,
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.HEURISTIC],
        'top_score': 4
    }

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.compile_heuristic[1].confidence),
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreTestTryJob(self):
    build = {
        'failure_type': failure_type.TEST,
        'failures': None,
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.TRY_JOB],
        'top_score': 5
    }

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.test_try_job.confidence),
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreCompileTryJob(self):
    build = {
        'failure_type': failure_type.COMPILE,
        'failures': None,
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.TRY_JOB],
        'top_score': 5
    }

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.test_try_job.confidence),
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreTestHeuristicTryJob(self):
    build = {
        'failure_type':
            failure_type.TEST,
        'failures':
            None,
        'status':
            suspected_cl_status.CORRECT,
        'approaches': [
            analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB
        ],
        'top_score':
            5
    }

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.test_heuristic_try_job.confidence),
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreCompileHeuristicTryJob(self):
    build = {
        'failure_type':
            failure_type.COMPILE,
        'failures':
            None,
        'status':
            suspected_cl_status.CORRECT,
        'approaches': [
            analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB
        ],
        'top_score':
            5
    }

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.compile_heuristic_try_job.confidence),
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreNone(self):
    self.assertIsNone(
        suspected_cl_util.GetSuspectedCLConfidenceScore(None, None))

  def testGetConfidenceScoreUnexpected(self):
    build = {
        'failure_type': failure_type.COMPILE,
        'failures': None,
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.HEURISTIC],
        'top_score': 2
    }

    self.assertIsNone(
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreCompileNone(self):
    build = {'failure_type': failure_type.COMPILE, 'approaches': []}
    self.assertIsNone(
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreUnexpectedTest(self):
    build = {
        'failure_type': failure_type.TEST,
        'failures': None,
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.HEURISTIC],
        'top_score': 2
    }

    self.assertIsNone(
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetConfidenceScoreTestNone(self):
    build = {'failure_type': failure_type.TEST, 'approaches': []}
    self.assertIsNone(
        suspected_cl_util.GetSuspectedCLConfidenceScore(self.cl_confidences,
                                                        build))

  def testGetSuspectedCLConfidenceScoreAndApproachNone(self):
    confidence, approach = (
        suspected_cl_util.GetSuspectedCLConfidenceScoreAndApproach(
            self.cl_confidences, None, None))
    self.assertIsNone(confidence)
    self.assertIsNone(approach)

  def testGetSuspectedCLConfidenceScoreAndApproachUseFirstBuild(self):
    build = {
        'failure_type': failure_type.COMPILE,
        'failures': None,
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.TRY_JOB],
        'top_score': 5
    }

    first_build = {
        'failure_type':
            failure_type.COMPILE,
        'failures':
            None,
        'status':
            suspected_cl_status.CORRECT,
        'approaches': [
            analysis_approach_type.TRY_JOB, analysis_approach_type.HEURISTIC
        ],
        'top_score':
            5
    }

    confidence, approach = (
        suspected_cl_util.GetSuspectedCLConfidenceScoreAndApproach(
            self.cl_confidences, build, first_build))

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.compile_heuristic_try_job.confidence),
        confidence)
    self.assertEqual(analysis_approach_type.TRY_JOB, approach)

  def testGetSuspectedCLConfidenceScoreAndApproachUseNewStep(self):
    build = {
        'failure_type': failure_type.TEST,
        'failures': {
            'a': [],
            'b': []
        },
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.HEURISTIC],
        'top_score': 5
    }

    first_build = {
        'failure_type':
            failure_type.TEST,
        'failures': {
            'a': ['t1']
        },
        'status':
            suspected_cl_status.CORRECT,
        'approaches': [
            analysis_approach_type.TRY_JOB, analysis_approach_type.HEURISTIC
        ],
        'top_score':
            5
    }

    confidence, approach = (
        suspected_cl_util.GetSuspectedCLConfidenceScoreAndApproach(
            self.cl_confidences, build, first_build))

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.test_heuristic[1].confidence), confidence)
    self.assertEqual(analysis_approach_type.HEURISTIC, approach)

  def testGetSuspectedCLConfidenceScoreAndApproachUseNewTest(self):
    build = {
        'failure_type': failure_type.TEST,
        'failures': {
            'a': ['t1', 't2']
        },
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.HEURISTIC],
        'top_score': 5
    }

    first_build = {
        'failure_type':
            failure_type.TEST,
        'failures': {
            'a': ['t1']
        },
        'status':
            suspected_cl_status.CORRECT,
        'approaches': [
            analysis_approach_type.TRY_JOB, analysis_approach_type.HEURISTIC
        ],
        'top_score':
            5
    }

    confidence, approach = (
        suspected_cl_util.GetSuspectedCLConfidenceScoreAndApproach(
            self.cl_confidences, build, first_build))

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.test_heuristic[1].confidence), confidence)
    self.assertEqual(analysis_approach_type.HEURISTIC, approach)

  def testGetSuspectedCLConfidenceScoreAndApproachUseLessTest(self):
    build = {
        'failure_type': failure_type.TEST,
        'failures': {
            'a': ['t1']
        },
        'status': suspected_cl_status.CORRECT,
        'approaches': [analysis_approach_type.HEURISTIC],
        'top_score': 5
    }

    first_build = {
        'failure_type':
            failure_type.TEST,
        'failures': {
            'a': ['t1', 't2']
        },
        'status':
            suspected_cl_status.CORRECT,
        'approaches': [
            analysis_approach_type.TRY_JOB, analysis_approach_type.HEURISTIC
        ],
        'top_score':
            5
    }

    confidence, approach = (
        suspected_cl_util.GetSuspectedCLConfidenceScoreAndApproach(
            self.cl_confidences, build, first_build))

    self.assertEqual(
        suspected_cl_util._RoundConfidentToInteger(
            self.cl_confidences.test_heuristic_try_job.confidence), confidence)
    self.assertEqual(analysis_approach_type.TRY_JOB, approach)

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2017, 7, 17))
  def testUpdateCulpritNotificationStatus(self, _):
    culprit = BaseSuspectedCL.Create('repo', 'revision', 123)
    culprit.put()
    suspected_cl_util.UpdateCulpritNotificationStatus(culprit.key.urlsafe(),
                                                      analysis_status.COMPLETED)
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()

    self.assertEqual(culprit.cr_notification_status, analysis_status.COMPLETED)
    self.assertEqual(datetime(2017, 7, 17), culprit.cr_notification_time)

  def testUpdateCulpritNotificationStatusRunning(self):
    culprit = BaseSuspectedCL.Create('repo', 'revision', 123)
    culprit.put()

    suspected_cl_util.UpdateCulpritNotificationStatus(culprit.key.urlsafe(),
                                                      analysis_status.RUNNING)
    culprit = ndb.Key(urlsafe=culprit.key.urlsafe()).get()

    self.assertEqual(culprit.cr_notification_status, analysis_status.RUNNING)
