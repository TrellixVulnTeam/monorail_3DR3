# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock

from common import constants
from common.waterfall import failure_type
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from gae_libs.pipelines import pipeline_handlers
from services import ci_failure
from services import step_util
from services.parameters import BuildKey
from services.parameters import CompileFailureInfo
from services.parameters import TestFailureInfo
from waterfall import build_failure_analysis_pipelines
from waterfall.test import wf_testcase


class BuildFailureAnalysisPipelinesTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _CreateAndSaveWfAnalysis(self,
                               master_name,
                               builder_name,
                               build_number,
                               not_passed_steps,
                               status,
                               build_completed=True):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.not_passed_steps = not_passed_steps
    analysis.status = status
    analysis.build_completed = build_completed
    analysis.put()

  def testAnalysisIsNeededWhenBuildWasNeverAnalyzed(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    failed_steps = ['a']

    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenNotForcedAfterCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a', 'b']
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.COMPLETED)

    failed_steps = ['a', 'b']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNotNeededWhenForcedBeforeCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = []
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.RUNNING)

    failed_steps = ['a']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, True)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNeededWhenForcedAfterCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.COMPLETED)

    failed_steps = ['a']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, True)
    self.assertTrue(need_analysis)

  def testNewAnalysisIsNotNeededWhenFailedStepsNotProvided(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.COMPLETED)

    failed_steps = None
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNotNeededWhenNewFailedStepsBeforeCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.RUNNING)

    failed_steps = ['a', 'b']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertFalse(need_analysis)

  def testNewAnalysisIsNeededWhenNewFailedStepsAfterCompletedAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.COMPLETED)

    failed_steps = ['a', 'b']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, False, False)

    self.assertTrue(need_analysis)

  def testNewAnalysisIsNeededWhenBuildCompletedAfterLastAnalysis(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    not_passed_steps = ['a']
    self._CreateAndSaveWfAnalysis(
        master_name,
        builder_name,
        build_number,
        not_passed_steps,
        analysis_status.COMPLETED,
        build_completed=False)

    failed_steps = ['a']
    need_analysis = build_failure_analysis_pipelines.NeedANewAnalysis(
        master_name, builder_name, build_number, failed_steps, True, False)

    self.assertTrue(need_analysis)

  @mock.patch.object(ci_failure, 'GetBuildFailureInfo')
  def testStartCompilePipelineForNewAnalysis(self, mock_info):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    failure_info = {
        'failed': True,
        'chromium_revision': 'rev',
        'failure_type': failure_type.COMPILE
    }
    mock_info.return_value = failure_info, True

    compile_pipeline_input = (
        build_failure_analysis_pipelines.AnalyzeCompileFailureInput(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            current_failure_info=CompileFailureInfo.FromSerializable(
                failure_info),
            build_completed=False,
            force=False))

    self.MockGeneratorPipeline(
        build_failure_analysis_pipelines.AnalyzeCompileFailurePipeline,
        compile_pipeline_input, None)

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name,
        builder_name,
        build_number,
        failed_steps=['a'],
        build_completed=False,
        force=False,
        queue_name=constants.DEFAULT_QUEUE)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)

  @mock.patch.object(
      step_util,
      'LegacyGetStepMetadata',
      return_value={
          'canonical_step_name': 'a',
          'isolate_target_name': 'a'
      })
  @mock.patch.object(ci_failure, 'GetBuildFailureInfo')
  def testStartTestPipelineForNewAnalysis(self, mock_info, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    failure_info = {
        'failed': True,
        'chromium_revision': 'rev',
        'failure_type': failure_type.TEST
    }
    mock_info.return_value = (failure_info, True)

    test_pipeline_input = (
        build_failure_analysis_pipelines.AnalyzeTestFailureInput(
            build_key=BuildKey(
                master_name=master_name,
                builder_name=builder_name,
                build_number=build_number),
            current_failure_info=TestFailureInfo.FromSerializable(failure_info),
            build_completed=False,
            force=False))

    self.MockGeneratorPipeline(
        build_failure_analysis_pipelines.AnalyzeTestFailurePipeline,
        test_pipeline_input, None)

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name,
        builder_name,
        build_number,
        failed_steps=['a'],
        build_completed=False,
        force=False,
        queue_name=constants.DEFAULT_QUEUE)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)

  @mock.patch.object(
      build_failure_analysis_pipelines, 'NeedANewAnalysis', return_value=False)
  @mock.patch.object(logging, 'info')
  def testNotStartPipelineForRunningAnalysis(self, mocked_logging, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    not_passed_steps = ['a']

    self._CreateAndSaveWfAnalysis(master_name, builder_name, build_number,
                                  not_passed_steps, analysis_status.RUNNING)

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name,
        builder_name,
        build_number,
        failed_steps=['a'],
        build_completed=True,
        force=False,
        queue_name=constants.DEFAULT_QUEUE)

    mocked_logging.assert_called_once_with(
        'An analysis is not needed for build %s, %s, %s', 'm', 'b', 123)

  @mock.patch.object(
      ci_failure,
      'GetBuildFailureInfo',
      return_value=({
          'failed': False,
          'chromium_revision': 'rev',
          'failure_type': failure_type.COMPILE
      }, False))
  @mock.patch.object(build_failure_analysis_pipelines,
                     'AnalyzeCompileFailurePipeline')
  def testNotStartPipelineForAnalysisWithNoFailure(self, mocked_pipeline, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124

    build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
        master_name,
        builder_name,
        build_number,
        failed_steps=['a'],
        build_completed=False,
        force=False,
        queue_name=constants.DEFAULT_QUEUE)

    self.assertFalse(mocked_pipeline.called)
