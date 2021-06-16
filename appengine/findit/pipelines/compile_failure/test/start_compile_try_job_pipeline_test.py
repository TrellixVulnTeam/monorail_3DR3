# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.monitoring import aborted_pipelines
from common.waterfall import failure_type
from dto.start_waterfall_try_job_inputs import StartCompileTryJobInput
from gae_libs.pipelines import pipeline_handlers
from model.wf_try_job import WfTryJob
from pipelines.compile_failure import (identify_compile_try_job_culprit_pipeline
                                       as culprit_pipeline)
from pipelines.compile_failure import start_compile_try_job_pipeline
from pipelines.compile_failure.run_compile_try_job_pipeline import (
    RunCompileTryJobPipeline)
from pipelines.compile_failure.start_compile_try_job_pipeline import (
    StartCompileTryJobPipeline)
from services import try_job as try_job_service
from services.compile_failure import compile_try_job
from services.parameters import BuildKey
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileTryJobResult
from services.parameters import IdentifyCompileTryJobCulpritParameters
from services.parameters import RunCompileTryJobParameters
from waterfall.test import wf_testcase


class StartCompileTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testNotScheduleTryJobIfBuildNotCompleted(self):
    heuristic_result = {
        'failure_info': {},
        'signals': {},
        'heuristic_result': {}
    }
    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=False,
        force=False)
    pipeline = StartCompileTryJobPipeline(start_try_job_params)
    result = pipeline.RunImpl(start_try_job_params)
    self.assertEqual(list(result), [])

  @mock.patch.object(RunCompileTryJobPipeline, 'TimeoutSeconds', return_value=0)
  @mock.patch.object(compile_try_job, 'GetParametersToScheduleCompileTryJob')
  @mock.patch.object(compile_try_job, 'NeedANewCompileTryJob')
  def testCompileTryJob(self, mock_fn, mock_parameter, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    build_key = BuildKey(
        master_name=master_name,
        builder_name=builder_name,
        build_number=build_number)
    try_job_type = failure_type.COMPILE
    failure_info = {
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0
            }
        }
    }
    good_revision = 'r1'
    bad_revision = 'r2'
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()

    mock_fn.return_value = True, try_job.key.urlsafe()
    parameters = {
        'build_key': {
            'master_name': master_name,
            'builder_name': builder_name,
            'build_number': build_number
        },
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'compile_targets': [],
        'suspected_revisions': [],
        'cache_name': 'cache_name',
        'dimensions': [],
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    pipeline_input = RunCompileTryJobParameters.FromSerializable(parameters)
    mock_parameter.return_value = pipeline_input
    expected_compile_result = {
        'report': {
            'culprit': None,
            'last_checked_out_revision': None,
            'previously_cached_revision': None,
            'previously_checked_out_revision': None,
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'metadata': {}
        },
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
        'culprit': None
    }
    self.MockAsynchronousPipeline(
        start_compile_try_job_pipeline.RunCompileTryJobPipeline, pipeline_input,
        expected_compile_result)
    identify_culprit_input = IdentifyCompileTryJobCulpritParameters(
        build_key=build_key,
        result=CompileTryJobResult.FromSerializable(expected_compile_result))
    self.MockGeneratorPipeline(
        culprit_pipeline.IdentifyCompileTryJobCulpritPipeline,
        identify_culprit_input, False)

    heuristic_result = {
        'failure_info': failure_info,
        'signals': {},
        'heuristic_result': {}
    }

    start_try_job_params = StartCompileTryJobInput(
        build_key=build_key,
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=True,
        force=False)
    pipeline = StartCompileTryJobPipeline(start_try_job_params)
    pipeline.start()
    self.execute_queued_tasks()

  @mock.patch.object(RunCompileTryJobPipeline, 'TimeoutSeconds', return_value=0)
  @mock.patch.object(try_job_service, 'GetCurrentTryJobID', return_value=None)
  @mock.patch.object(compile_try_job, 'GetParametersToScheduleCompileTryJob')
  @mock.patch.object(compile_try_job, 'NeedANewCompileTryJob')
  def testCompileTryJobNoTryJobResult(self, mock_fn, mock_parameter, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.COMPILE
    failure_info = {
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'compile': {
                'first_failure': 1,
                'last_pass': 0
            }
        }
    }
    good_revision = 'r1'
    bad_revision = 'r2'
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()

    mock_fn.return_value = True, try_job.key.urlsafe()
    parameters = {
        'build_key': {
            'master_name': master_name,
            'builder_name': builder_name,
            'build_number': build_number
        },
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'compile_targets': [],
        'suspected_revisions': [],
        'cache_name': 'cache_name',
        'dimensions': [],
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    pipeline_input = RunCompileTryJobParameters.FromSerializable(parameters)
    mock_parameter.return_value = pipeline_input
    self.MockAsynchronousPipeline(
        start_compile_try_job_pipeline.RunCompileTryJobPipeline, pipeline_input,
        {})
    identify_culprit_input = IdentifyCompileTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=CompileTryJobResult.FromSerializable({}))
    self.MockGeneratorPipeline(
        culprit_pipeline.IdentifyCompileTryJobCulpritPipeline,
        identify_culprit_input, False)

    heuristic_result = {
        'failure_info': failure_info,
        'signals': {},
        'heuristic_result': {}
    }
    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=True,
        force=False)
    pipeline = StartCompileTryJobPipeline(start_try_job_params)
    pipeline.start()
    self.execute_queued_tasks()

  @mock.patch.object(
      compile_try_job, 'NeedANewCompileTryJob', return_value=(False, None))
  @mock.patch.object(start_compile_try_job_pipeline, 'RunCompileTryJobPipeline')
  def testNotNeedCompileTryJob(self, mock_pipeline, _):
    failure_info = {'failure_type': failure_type.COMPILE}
    heuristic_result = {
        'failure_info': failure_info,
        'signals': {},
        'heuristic_result': {}
    }
    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=True,
        force=False)
    pipeline = StartCompileTryJobPipeline(start_try_job_params)
    result = pipeline.RunImpl(start_try_job_params)
    self.assertEqual(list(result), [])
    self.assertFalse(mock_pipeline.called)

  @mock.patch.object(compile_try_job, 'NeedANewCompileTryJob')
  @mock.patch.object(compile_try_job, 'GetParametersToScheduleCompileTryJob')
  @mock.patch.object(start_compile_try_job_pipeline, 'RunCompileTryJobPipeline')
  def testNoCompileTryJobBecauseNoGoodRevision(self, mock_pipeline,
                                               mock_parameter, mock_fn):

    mock_parameter.return_value = RunCompileTryJobParameters(good_revision=None)
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()
    mock_fn.return_value = (True, try_job.key.urlsafe())
    failure_info = {'failure_type': failure_type.COMPILE}
    heuristic_result = {
        'failure_info': failure_info,
        'signals': {},
        'heuristic_result': {}
    }
    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=True,
        force=False)
    pipeline = StartCompileTryJobPipeline(start_try_job_params)
    result = pipeline.RunImpl(start_try_job_params)
    self.assertEqual(list(result), [])
    self.assertFalse(mock_pipeline.called)

  @mock.patch.object(aborted_pipelines, 'increment')
  def testOnAbortResumedTryJob(self, mock_mon):
    failure_info = {'failure_type': failure_type.COMPILE}
    heuristic_result = {
        'failure_info': failure_info,
        'signals': {},
        'heuristic_result': None
    }
    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=True,
        force=False)
    pipeline = StartCompileTryJobPipeline(start_try_job_params)
    pipeline.OnAbort(start_try_job_params)
    mock_mon.assert_called_once_with({'type': 'compile'})

  @mock.patch.object(aborted_pipelines, 'increment')
  def testOnAbort(self, mock_mon):
    failure_info = {'failure_type': failure_type.COMPILE}
    heuristic_result = {
        'failure_info': failure_info,
        'signals': {},
        'heuristic_result': {}
    }
    start_try_job_params = StartCompileTryJobInput(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=1),
        heuristic_result=CompileHeuristicAnalysisOutput.FromSerializable(
            heuristic_result),
        build_completed=True,
        force=False)
    pipeline = StartCompileTryJobPipeline(start_try_job_params)
    pipeline.OnAbort(start_try_job_params)
    self.assertFalse(mock_mon.called)
