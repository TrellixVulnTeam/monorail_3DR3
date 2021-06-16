# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock

from common import exceptions
from common.swarmbucket import swarmbucket
from common.waterfall import failure_type
from dto.start_waterfall_try_job_inputs import StartCompileTryJobInput
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from libs.gitiles.change_log import Contributor
from model import analysis_approach_type
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import build_failure_analysis
from services import try_job as try_job_service
from services.compile_failure import compile_failure_analysis
from services.compile_failure import compile_try_job
from services.parameters import BaseFailedSteps
from services.parameters import BuildKey
from services.parameters import CompileFailureInfo
from services.parameters import CompileFailureSignals
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileHeuristicResult
from services.parameters import CompileTryJobReport
from services.parameters import CompileTryJobResult
from services.parameters import IdentifyCompileTryJobCulpritParameters
from services.parameters import RunCompileTryJobParameters
from services.test.git_test import MockedChangeLog
from waterfall import buildbot
from waterfall import suspected_cl_util
from waterfall.test import wf_testcase


class CompileTryJobTest(wf_testcase.WaterfallTestCase):

  def _MockGetChangeLog(self, revision):
    mock_change_logs = {}
    mock_change_logs['rev1'] = MockedChangeLog(
        commit_position=1,
        code_review_url='url_1',
        author=Contributor('author1', 'author1@abc.com', '2018-05-17 00:49:48'))
    mock_change_logs['rev2'] = MockedChangeLog(
        commit_position=2,
        code_review_url='url_2',
        author=Contributor('author2', 'author2@abc.com', '2018-05-17 00:49:48'))
    return mock_change_logs.get(revision)

  def setUp(self):
    super(CompileTryJobTest, self).setUp()

    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)

  @mock.patch.object(logging, 'info')
  def testDoNotGroupUnknownBuildFailure(self, mock_logging):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 1

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with UNKNOWN failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.UNKNOWN, None,
            None, None))
    mock_logging.assert_called_once_with(
        'Expected compile failure but get %s failure.', 'unknown')

  @mock.patch.object(logging, 'info')
  def testDoNotGroupInfraBuildFailure(self, mock_logging):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 2

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with INFRA failure.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.INFRA, None,
            None, None))
    mock_logging.assert_called_once_with(
        'Expected compile failure but get %s failure.', 'infra')

  def testDoNotGroupCompileWithNoOutputNodes(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 3

    blame_list = ['a']

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': []
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have zero failed output nodes.
    # Observe that the build failure is unique, but there is no new group
    # creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

  def testAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 4

    blame_list = ['a']

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['abc.obj']
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual([master_name, builder_name, build_number],
                     analysis.failure_group_key)

  def testSecondAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 5
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['abc.obj']
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))

    analysis_2 = WfAnalysis.Get(master_name_2, builder_name, build_number)
    self.assertEqual([master_name, builder_name, build_number],
                     analysis_2.failure_group_key)

  def testGroupCompilesWithRelatedFailuresWithHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 6
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['abc.obj']
        }
    })

    heuristic_result = CompileHeuristicResult.FromSerializable({
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev1',
            }],
        }]
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testGroupCompilesWithRelatedFailuresWithoutHeuristicResult(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 7
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['abc.obj']
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, None))
    self.assertIsNone(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDisjointBlameLists(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 8
    master_name_2 = 'm2'

    blame_list_1 = ['a']

    blame_list_2 = ['b']

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['abc.obj']
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list_1, signals, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list_2, signals, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDifferentHeuristicResults(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 9
    master_name_2 = 'm2'

    blame_list = ['a']

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['abc.obj']
        }
    })

    heuristic_result_1 = CompileHeuristicResult.FromSerializable({
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev1',
            }],
        }]
    })

    heuristic_result_2 = CompileHeuristicResult.FromSerializable({
        'failures': [{
            'step_name': 'step1',
            'suspected_cls': [{
                'revision': 'rev2',
            }],
        }]
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result_1))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals, heuristic_result_2))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  def testDoNotGroupCompilesWithDifferentOutputNodes(self):
    master_name = 'm1'
    builder_name = 'bc'
    build_number = 10
    master_name_2 = 'm2'

    blame_list = ['a']

    signals_1 = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['abc.obj']
        }
    })

    signals_2 = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_output_nodes': ['def.obj']
        }
    })

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals_1, None))
    self.assertIsNotNone(
        WfFailureGroup.Get(master_name, builder_name, build_number))

    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have different failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        compile_try_job._IsCompileFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, signals_2, None))
    self.assertTrue(
        WfFailureGroup.Get(master_name_2, builder_name, build_number))

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobIfNotFirstTimeFailure(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    failure_info = {
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 221,
                'last_pass': 220,
                'supported': True
            }
        },
        'builds': {
            '220': {
                'blame_list': ['220-1', '220-2'],
                'chromium_revision': '220-2'
            },
            '221': {
                'blame_list': ['221-1', '221-2'],
                'chromium_revision': '221-2'
            },
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    WfAnalysis.Create(master_name, builder_name, build_number).put()
    mock_fn.return_value = False
    expected_key = WfTryJob.Create(master_name, builder_name,
                                   build_number).key.urlsafe()

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_key, try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobIfOneWithResultExists(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220,
                'supported': True
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [['rev', 'failed']]
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertFalse(need_try_job)
    self.assertEqual(try_job_key, try_job.key.urlsafe())

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewCompileTryJobIfExistingOneHasError(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220,
                'supported': True
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.ERROR
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertTrue(need_try_job)
    self.assertEqual(try_job.key.urlsafe(), try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewTryJobIfExistingOneHasError(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 220,
                'supported': True
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = analysis_status.ERROR
    try_job.put()

    WfAnalysis.Create(master_name, builder_name, build_number).put()

    mock_fn.return_value = False

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertTrue(need_try_job)
    self.assertEqual(try_job.key.urlsafe(), try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewTestTryJob(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222,
                'supported': True
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'compile': 'm/b/223'}
    analysis.put()

    mock_fn.return_value = False

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNeedANewCompileTryJob(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {
            'compile': {
                'current_failure': 223,
                'first_failure': 223,
                'last_pass': 222,
                'supported': True
            }
        },
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'compile': 'm/b/223'}
    analysis.put()

    mock_fn.return_value = False

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertTrue(need_try_job)
    self.assertIsNotNone(try_job_key)

  @mock.patch.object(
      try_job_service, 'NeedANewWaterfallTryJob', return_value=False)
  def testNotNeedANewCompileTryJob(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=None, signals=None, heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertFalse(need_try_job)
    self.assertIsNone(try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobForOtherType(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.UNKNOWN
    }

    mock_fn.return_value = False

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertFalse(need_try_job)
    self.assertIsNone(try_job_key)

  @mock.patch.object(try_job_service, '_ShouldBailOutForOutdatedBuild')
  def testNotNeedANewCompileTryJobForCompileTypeNoFailureInfo(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed_steps': {},
        'builds': {
            '222': {
                'blame_list': ['222-1'],
                'chromium_revision': '222-1'
            },
            '223': {
                'blame_list': ['223-1', '223-2', '223-3'],
                'chromium_revision': '223-3'
            }
        },
        'failure_type': failure_type.COMPILE
    }

    mock_fn.return_value = False
    expected_try_job_key = WfTryJob.Create(master_name, builder_name,
                                           build_number).key.urlsafe()

    params = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    need_try_job, try_job_key = compile_try_job.NeedANewCompileTryJob(params)

    self.assertFalse(need_try_job)
    self.assertEqual(expected_try_job_key, try_job_key)

  def testUseFailedOutputNodesFromSignals(self):
    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_targets': [
                {
                    'target': 'a.exe'
                },
                {
                    'source': 'b.cc',
                    'target': 'b.o'
                },
            ],
            'failed_output_nodes': ['a', 'b'],
        }
    })

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(signals, 'm', 'b'),
        ['a', 'b'])

  def testGetFailedTargetsFromSignals(self):
    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(
            CompileFailureSignals.FromSerializable({}), 'm', 'b'), [])

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(
            CompileFailureSignals.FromSerializable({
                'compile': {}
            }), 'm', 'b'), [])

    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_targets': [{
                'target': 'a.exe'
            }, {
                'source': 'b.cc',
                'target': 'b.o'
            }]
        }
    })

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(signals, 'm', 'b'),
        ['a.exe'])

  def testUseObjectFilesAsFailedTargetIfStrictRegexUsed(self):
    signals = CompileFailureSignals.FromSerializable({
        'compile': {
            'failed_targets': [{
                'source': 'b.cc',
                'target': 'b.o'
            },]
        }
    })

    self.assertEqual(
        compile_try_job._GetFailedTargetsFromSignals(signals, 'master1',
                                                     'builder1'), ['b.o'])

  def testGetLastPassCurrentBuildIsNotFirstFailure(self):
    failed_steps = BaseFailedSteps.FromSerializable({
        'compile': {
            'first_failure': 1,
            'last_pass': 0
        }
    })
    self.assertIsNone(compile_try_job._GetLastPassCompile(2, failed_steps))

  def testGetLastPassCompile(self):
    failed_steps = BaseFailedSteps.FromSerializable({
        'compile': {
            'first_failure': 1,
            'last_pass': 0
        }
    })
    self.assertEqual(0, compile_try_job._GetLastPassCompile(1, failed_steps))

  def testGetGoodRevisionCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = CompileFailureInfo.FromSerializable({
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    })
    self.assertEqual(
        'rev1',
        compile_try_job._GetGoodRevisionCompile(master_name, builder_name,
                                                build_number, failure_info))

  def testNotGetGoodRevisionCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    failure_info = CompileFailureInfo.FromSerializable({
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    })
    self.assertIsNone(
        compile_try_job._GetGoodRevisionCompile(master_name, builder_name,
                                                build_number, failure_info))

  @mock.patch('services.swarmbot_util.GetCacheName', return_value='cache')
  @mock.patch.object(swarmbucket, 'GetDimensionsForBuilder')
  def testGetParametersToScheduleTestTryJob(self, mock_dimensions, *_):
    mock_dimensions.return_value = ['os:Mac-10.9', 'cpu:x86-64']
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    failure_info = {
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0,
                'supported': True,
            }
        },
        'builds': {
            '0': {
                'chromium_revision': 'rev1'
            },
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    }

    good_revision = 'rev1'
    bad_revision = 'rev2'
    cache_name = 'cache'
    dimensions = ['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit']

    expected_parameters_dict = {
        'build_key': {
            'master_name': master_name,
            'builder_name': builder_name,
            'build_number': build_number
        },
        'bad_revision': bad_revision,
        'suspected_revisions': [],
        'good_revision': good_revision,
        'compile_targets': [],
        'dimensions': dimensions,
        'cache_name': 'cache',
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    expected_parameter = RunCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision=good_revision,
        bad_revision=bad_revision,
        suspected_revisions=[],
        cache_name=cache_name,
        dimensions=dimensions,
        compile_targets=[],
        urlsafe_try_job_key='urlsafe_try_job_key')

    start_compile_try_job_input = StartCompileTryJobInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        heuristic_result=CompileHeuristicAnalysisOutput(
            failure_info=CompileFailureInfo.FromSerializable(failure_info),
            signals=None,
            heuristic_result=None),
        build_completed=True,
        force=False)
    parameter = compile_try_job.GetParametersToScheduleCompileTryJob(
        start_compile_try_job_input, 'urlsafe_try_job_key')
    self.assertEqual(expected_parameter, parameter)
    self.assertEqual(expected_parameters_dict, parameter.ToSerializable())

  def testCompileFailureIsNotFlaky(self):
    try_job_result = {'rev': 'failed'}
    report = CompileTryJobReport(
        culprit='rev', result=try_job_result, metadata={'sub_ranges': []})
    result = CompileTryJobResult(report=report)

    self.assertFalse(compile_try_job.CompileFailureIsFlaky(result))

  def testCompileFailureIsFlakyNoResult(self):
    self.assertFalse(compile_try_job.CompileFailureIsFlaky(None))

  def testCompileFailureIsFlaky(self):
    try_job_result = {
        'r0': 'failed',
        'r1': 'passed',
        'r2': 'passed',
        'r3': 'passed',
        'r4': 'passed',
    }
    metadata = {'sub_ranges': [[None, 'r1', 'r2'], ['r3', 'r4']]}
    report = CompileTryJobReport(result=try_job_result, metadata=metadata)
    result = CompileTryJobResult(report=report)
    self.assertTrue(compile_try_job.CompileFailureIsFlaky(result))

  def testUpdateTryJobResultNoCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    WfTryJob.Create(master_name, builder_name, build_number).put()
    parameters = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable({}))
    compile_try_job.UpdateTryJobResult(parameters, None)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

  def testUpdateTryJobResultUpdate(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    result = {'culprit': {'compile': 'rev'}, 'try_job_id': '2'}
    culprits = {'rev': {'revision': 'rev'}}
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [{'try_job_id': '2'}]
    try_job.put()

    parameters = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable(result))

    expected_results = [{
        'try_job_id': '2',
        'culprit': {
            'compile': 'rev'
        },
        'report': None,
        'url': None
    }]

    compile_try_job.UpdateTryJobResult(parameters, culprits)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    self.assertEqual(expected_results, try_job.compile_results)

  def testUpdateTryJobResultAppend(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    result = {'culprit': {'compile': 'rev'}, 'try_job_id': '2'}
    culprits = {'rev': {'revision': 'rev'}}
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [{'try_job_id': '1'}]
    try_job.put()

    parameters = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable(result))

    expected_results = [{
        'try_job_id': '1'
    },
                        {
                            'culprit': {
                                'compile': 'rev'
                            },
                            'try_job_id': '2',
                            'report': None,
                            'url': None
                        }]

    compile_try_job.UpdateTryJobResult(parameters, culprits)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.COMPLETED, try_job.status)
    self.assertListEqual(expected_results, try_job.compile_results)

  @mock.patch.object(compile_try_job, '_GetUpdatedAnalysisResult')
  def testUpdateWfAnalysisWithTryJobResultNoCulprit(self, mock_fn):
    compile_try_job.UpdateWfAnalysisWithTryJobResult('m', 'b', 1, None, None,
                                                     False)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(
      try_job_service,
      'GetResultAnalysisStatus',
      return_value=result_status.FOUND_UNTRIAGED)
  @mock.patch.object(
      compile_try_job, '_GetUpdatedSuspectedCLs', return_value=[])
  def testUpdateWfAnalysisWithTryJobResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = {
        'failures': [{
            'step_name': 'compile',
        }]
    }
    analysis.put()
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}

    compile_try_job.UpdateWfAnalysisWithTryJobResult(
        master_name, builder_name, build_number, None, culprits, False)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(result_status.FOUND_UNTRIAGED, analysis.result_status)

  @mock.patch.object(
      try_job_service, 'GetResultAnalysisStatus', return_value=None)
  @mock.patch.object(
      compile_try_job, '_GetUpdatedSuspectedCLs', return_value=None)
  def testNoNeedToUpdateWfAnalysisWithTryJobResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}

    compile_try_job.UpdateWfAnalysisWithTryJobResult(
        master_name, builder_name, build_number, None, culprits, False)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNone(analysis.result_status)

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLsNoCulprit(self, mock_fn):
    compile_try_job.UpdateSuspectedCLs('m', 'b', 1, None)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(suspected_cl_util, 'UpdateSuspectedCL')
  def testUpdateSuspectedCLs(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    culprits = {'rev': {'revision': 'rev', 'repo_name': 'chromium'}}
    compile_try_job.UpdateSuspectedCLs(master_name, builder_name, build_number,
                                       culprits)
    mock_fn.assert_called_with(
        'chromium', 'rev', None, analysis_approach_type.TRY_JOB, master_name,
        builder_name, build_number, failure_type.COMPILE, {'compile': []}, None)

  def testGetUpdatedAnalysisResultFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = {
        'failures': [{
            'step_name': 'Failure_reason'
        }, {
            'step_name': 'compile',
        }]
    }
    analysis.put()

    expected_result = {
        'failures': [{
            'step_name': 'Failure_reason'
        }, {
            'step_name': 'compile',
            'flaky': True
        }]
    }
    self.assertEqual(expected_result,
                     compile_try_job._GetUpdatedAnalysisResult(analysis, True))

  @mock.patch.object(buildbot, 'CreateBuildbucketUrl')
  def testGetBuildPropertiesWithCompileTargets(self, mock_build_url):
    master_name = u'm'
    builder_name = u'b'
    build_number = 1

    build_url = 'https://ci.chromium.org/b/800000000001'
    mock_build_url.return_value = build_url

    pipeline_input = RunCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='1',
        bad_revision='2',
        suspected_revisions=[],
        compile_targets=[])

    expected_properties = {
        'recipe': 'findit/chromium/compile',
        'good_revision': '1',
        'bad_revision': '2',
        'target_mastername': master_name,
        'target_buildername': 'b',
        'suspected_revisions': [],
        'referenced_build_url': build_url,
        'compile_targets': [],
    }
    properties = compile_try_job.GetBuildProperties(pipeline_input)

    self.assertEqual(properties, expected_properties)

  def testGetUpdatedSuspectedCLs(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r123_2',
        'commit_position': 1232,
        'url': 'url_2',
        'failures': {
            'compile': []
        },
        'top_score': 4
    }]
    analysis.put()

    culprits = {
        'r123_1': {
            'revision': 'r123_1',
            'commit_position': 1231,
            'url': 'url_1',
            'repo_name': 'chromium'
        },
        'r123_2': {
            'revision': 'r123_2',
            'commit_position': 1232,
            'url': 'url_2',
            'repo_name': 'chromium'
        }
    }

    expected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r123_2',
        'commit_position': 1232,
        'url': 'url_2',
        'failures': {
            'compile': []
        },
        'top_score': 4
    },
                    {
                        'revision': 'r123_1',
                        'commit_position': 1231,
                        'url': 'url_1',
                        'repo_name': 'chromium',
                        'failures': {
                            'compile': []
                        },
                        'top_score': None
                    }]

    self.assertListEqual(
        expected_cls, compile_try_job._GetUpdatedSuspectedCLs(
            analysis, culprits))

  @mock.patch.object(compile_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(try_job_service, 'TriggerTryJob', return_value=('1', None))
  def testSuccessfullyScheduleNewTryJobForCompileWithSuspectedRevisions(
      self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    build_id = '1'

    WfTryJob.Create(master_name, builder_name, build_number).put()

    parameters = RunCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision=good_revision,
        bad_revision=bad_revision,
        suspected_revisions=['r5'],
        cache_name=None,
        dimensions=[],
        compile_targets=[])
    try_job_id = compile_try_job.ScheduleCompileTryJob(parameters, 'pipeline')

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Get(build_id)

    expected_try_job_id = '1'
    self.assertEqual(expected_try_job_id, try_job_id)
    self.assertEqual(expected_try_job_id,
                     try_job.compile_results[-1]['try_job_id'])
    self.assertTrue(expected_try_job_id in try_job.try_job_ids)
    self.assertIsNotNone(try_job_data)
    self.assertEqual(try_job_data.build_number, build_number)
    self.assertEqual(
        try_job_data.try_job_type,
        failure_type.GetDescriptionForFailureType(failure_type.COMPILE))
    self.assertFalse(try_job_data.has_compile_targets)
    self.assertTrue(try_job_data.has_heuristic_results)

  class MockedError(object):

    def __init__(self, message, reason):
      self.message = message
      self.reason = reason

  @mock.patch.object(compile_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(
      try_job_service,
      'TriggerTryJob',
      return_value=(None, MockedError('message', 'reason')))
  def testScheduleTestTryJobRaise(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'

    parameters = RunCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision=good_revision,
        bad_revision=bad_revision,
        suspected_revisions=['r5'],
        cache_name=None,
        dimensions=[],
        compile_targets=[])

    with self.assertRaises(exceptions.RetryException):
      compile_try_job.ScheduleCompileTryJob(parameters, 'pipeline')

  def _CreateEntities(self,
                      master_name,
                      builder_name,
                      build_number,
                      try_job_id,
                      try_job_status=None,
                      compile_results=None):
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.status = try_job_status
    try_job.compile_results = compile_results
    try_job.put()

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

  def testIdentifyCulpritForCompileTryJobSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'culprit': 'rev2'
        },
        'try_job_id': try_job_id,
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        compile_results=[compile_result])
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    expected_culprit = 'rev2'
    expected_culprit_info = {
        'revision': 'rev2',
        'repo_name': 'chromium',
        'commit_position': 2,
        'url': 'url_2',
        'author': 'author2@abc.com',
    }
    expected_compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'culprit': 'rev2',
            'previously_checked_out_revision': None,
            'previously_cached_revision': None,
            'last_checked_out_revision': None,
            'metadata': None
        },
        'try_job_id': try_job_id,
        'culprit': {
            'compile': expected_culprit_info
        },
        'url': None
    }
    expected_analysis_suspected_cls = [{
        'revision': 'rev2',
        'commit_position': 2,
        'url': 'url_2',
        'repo_name': 'chromium',
        'author': 'author2@abc.com',
        'failures': {
            'compile': []
        },
        'top_score': None
    }]

    expected_culprits = {'rev2': expected_culprit_info}
    parameters = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable(compile_result))

    culprits, _ = compile_try_job.IdentifyCompileTryJobCulprit(parameters)
    self.assertEqual(expected_culprits, culprits)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(analysis_status.COMPLETED, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual({'compile': expected_culprit}, try_job_data.culprits)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, expected_analysis_suspected_cls)

  @mock.patch.object(
      build_failure_analysis, 'GetHeuristicSuspectedCLs', return_value=[])
  @mock.patch.object(
      compile_try_job, 'CompileFailureIsFlaky', return_value=True)
  def testIdentifyCulpritForCompileTryJobSuccessFlaky(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'passed'
            },
        },
        'try_job_id': try_job_id,
    }

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        compile_results=[compile_result])
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    parameters = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable(compile_result))
    culprits, _ = compile_try_job.IdentifyCompileTryJobCulprit(parameters)
    self.assertEqual(culprits, {})

  def testIdentifyCompileTryJobCulpritNoResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    compile_result = {}

    self._CreateEntities(
        master_name,
        builder_name,
        build_number,
        try_job_id,
        try_job_status=analysis_status.RUNNING,
        compile_results=[compile_result])
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

    parameters = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable(compile_result))
    culprits, _ = compile_try_job.IdentifyCompileTryJobCulprit(parameters)
    self.assertIsNone(culprits)

  @mock.patch.object(try_job_service, 'OnTryJobTimeout')
  @mock.patch.object(compile_failure_analysis,
                     'RecordCompileFailureAnalysisStateChange')
  def testOnTryJobTimeout(self, mock_mon, _):
    parameter = RunCompileTryJobParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        cache_name=None,
        dimensions=[],
        compile_targets=[],
        urlsafe_try_job_key='urlsafe_try_job_key')
    compile_try_job.OnTryJobTimeout('id', parameter)
    mock_mon.assert_called_once_with('m', 'b', analysis_status.ERROR,
                                     analysis_approach_type.TRY_JOB)

  @mock.patch.object(compile_failure_analysis,
                     'RecordCompileFailureAnalysisStateChange')
  @mock.patch.object(
      try_job_service,
      'OnTryJobStateChanged',
      return_value=(None, analysis_status.PENDING))
  def testOnTryJobStateChangedNoResult(self, mock_fn, mock_mon):
    parameter = RunCompileTryJobParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        cache_name=None,
        dimensions=[],
        compile_targets=[],
        urlsafe_try_job_key='urlsafe_try_job_key')
    self.assertIsNone(
        compile_try_job.OnTryJobStateChanged('try_job_id', {}, parameter))
    mock_fn.assert_called_once_with('try_job_id', failure_type.COMPILE, {})
    self.assertFalse(mock_mon.called)

  @mock.patch.object(compile_failure_analysis,
                     'RecordCompileFailureAnalysisStateChange')
  @mock.patch.object(
      try_job_service,
      'OnTryJobStateChanged',
      return_value=({}, analysis_status.COMPLETED))
  def testOnTryJobStateChanged(self, mock_fn, mock_mon):
    parameter = RunCompileTryJobParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        good_revision='rev1',
        bad_revision='rev2',
        suspected_revisions=[],
        cache_name=None,
        dimensions=[],
        compile_targets=[],
        urlsafe_try_job_key='urlsafe_try_job_key')
    self.assertEqual(
        CompileTryJobResult.FromSerializable({}),
        compile_try_job.OnTryJobStateChanged('try_job_id', {}, parameter))
    mock_fn.assert_called_once_with('try_job_id', failure_type.COMPILE, {})
    mock_mon.assert_called_once_with('m', 'b', analysis_status.COMPLETED,
                                     analysis_approach_type.TRY_JOB)
