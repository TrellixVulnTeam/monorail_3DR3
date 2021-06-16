# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a function to analyze compile failures."""

from collections import defaultdict
import logging

from common import constants
from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from libs import analysis_status
from model import analysis_approach_type
from model.wf_analysis import WfAnalysis
from services import build_failure_analysis
from services import ci_failure
from services import deps
from services import git
from services import monitoring
from services.compile_failure import extract_compile_signal
from services.parameters import CompileFailureSignals
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileHeuristicResult
from waterfall import waterfall_config
from waterfall.failure_signal import FailureSignal


def _Analyze(start_build_number,
             failed_build_number,
             builds,
             step_name,
             failure_signal,
             change_logs,
             deps_info,
             step_analysis_result,
             cl_failure_map,
             use_ninja_output=False):

  for build_number, build in builds.iteritems():
    if (build_number > failed_build_number or
        build_number < start_build_number):
      continue

    for revision in build.blame_list:
      # TODO(crbug/842980): Deprecate blame_list in builds.
      if not change_logs.get(revision):
        continue

      new_suspected_cl_dict, max_score = build_failure_analysis.AnalyzeOneCL(
          build_number, failure_signal, change_logs[revision], deps_info,
          use_ninja_output)

      if not new_suspected_cl_dict:
        continue

      if use_ninja_output:
        step_analysis_result['new_compile_suspected_cls'].append(
            new_suspected_cl_dict)
      else:
        step_analysis_result['suspected_cls'].append(new_suspected_cl_dict)

        build_failure_analysis.SaveFailureToMap(
            cl_failure_map, new_suspected_cl_dict, step_name, None, max_score)


def AnalyzeCompileFailure(failure_info, change_logs, deps_info,
                          failure_signals):
  """Analyzes given failure signals, and figure out culprits of compile failure.

  Args:
    failure_info (CompileFailureInfo): Output of pipeline
      DetectFirstFailurePipeline.
    change_logs (dict): Output of pipeline PullChangelogPipeline.
    deps_info (dict): Output of pipeline ExtractDEPSInfoPipeline.
    failure_signals (dict): Output of pipeline ExtractSignalPipeline.

  Returns:
    A dict with the following form:
    {
      'failures': [
        {
          'step_name': 'compile',
          'supported': True
          'first_failure': 230,
          'last_pass': 229,
          'suspected_cls': [
            {
              'build_number': 230,
              'repo_name': 'chromium',
              'revision': 'a_git_hash',
              'commit_position': 56789,
              'score': 11,
              'hints': {
                'add a/b/x.cc': 5,
                'delete a/b/y.cc': 5,
                'modify e/f/z.cc': 1,
                ...
              }
            },
            ...
          ],
        },
        ...
      ]
    }

    And a list of suspected_cls format as below:
    [
        {
            'repo_name': 'chromium',
            'revision': 'r98_1',
            'commit_position': None,
            'url': None,
            'failures': {
                'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
            },
            'top_score': 4
        },
        ...
    ]
  """
  analysis_result = {'failures': []}
  cl_failure_map = defaultdict(build_failure_analysis.CLInfo)

  step_name = constants.COMPILE_STEP_NAME

  if not failure_signals:
    logging.debug('No failure signals when analyzing a compile failure.')
    return analysis_result, []

  if step_name not in failure_info.failed_steps:
    logging.debug('No failed compile step when analyzing a compile failure.')
    return analysis_result, []

  builds = failure_info.builds
  compile_failure_info = failure_info.failed_steps[step_name]

  failed_build_number = compile_failure_info.current_failure
  start_build_number = build_failure_analysis.GetLowerBoundForAnalysis(
      compile_failure_info)
  step_analysis_result = build_failure_analysis.InitializeStepLevelResult(
      step_name, compile_failure_info)

  if not step_analysis_result['supported']:
    return analysis_result, []

  failure_signal = FailureSignal.FromDict(failure_signals[step_name])
  _Analyze(start_build_number, failed_build_number, builds, step_name,
           failure_signal, change_logs, deps_info, step_analysis_result,
           cl_failure_map)

  if waterfall_config.GetDownloadBuildDataSettings().get(
      'use_ninja_output_log'):
    step_analysis_result['new_compile_suspected_cls'] = []
    _Analyze(
        start_build_number,
        failed_build_number,
        builds,
        step_name,
        failure_signal,
        change_logs,
        deps_info,
        step_analysis_result,
        cl_failure_map,
        use_ninja_output=True)

    if (not step_analysis_result['suspected_cls'] and
        step_analysis_result.get('new_compile_suspected_cls')):
      step_analysis_result['use_ninja_dependencies'] = True
      step_analysis_result['suspected_cls'] = step_analysis_result[
          'new_compile_suspected_cls']
      for new_suspected_cl_dict in step_analysis_result['suspected_cls']:
        # Top score for new heuristic is always 2.
        build_failure_analysis.SaveFailureToMap(
            cl_failure_map, new_suspected_cl_dict, step_name, None, 2)

  # TODO(stgao): sort CLs by score.
  analysis_result['failures'].append(step_analysis_result)

  suspected_cls = build_failure_analysis.ConvertCLFailureMapToList(
      cl_failure_map)

  return analysis_result, suspected_cls


def HeuristicAnalysisForCompile(heuristic_params):
  """Identifies culprit CL.


  Args:
    heuristic_params (CompileHeuristicAnalysisParameters): A structured object
    with 2 fields:
      failure_info (CompileFailureInfo): An object of failure info for the
      current failed build.
      build_completed (bool): If the build is completed.

  Returns:
    A CompileHeuristicAnalysisOutput object with information about
    failure_info, signals and heuristic_result.
  """
  failure_info = heuristic_params.failure_info
  master_name = failure_info.master_name
  builder_name = failure_info.builder_name
  build_number = failure_info.build_number

  # 1. Detects first failed builds for failed compile step,
  # updates failure_info.
  failure_info = ci_failure.CheckForFirstKnownFailure(
      master_name, builder_name, build_number, failure_info)

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.failure_info = failure_info.ToSerializable()
  analysis.put()

  # Lacking chromium_revision indicates something is wrong in Findit,
  assert failure_info.chromium_revision, (
      'No end_revision when pulling change logs.')

  # 2. Extracts failure signal.
  signals = extract_compile_signal.ExtractSignalsForCompileFailure(
      failure_info, FinditHttpClient())

  # 3. Gets change_logs.
  change_logs = git.PullChangeLogs(
      ci_failure.GetGoodRevision(failure_info), failure_info.chromium_revision)

  # 4. Gets deps info.
  deps_info = deps.ExtractDepsInfo(failure_info, change_logs)

  # 5. Analyzes the compile failure using information collected above.
  heuristic_result, suspected_cls = AnalyzeCompileFailure(
      failure_info, change_logs, deps_info, signals)

  # Save results and other info to analysis.
  build_failure_analysis.SaveAnalysisAfterHeuristicAnalysisCompletes(
      master_name, builder_name, build_number, heuristic_result, suspected_cls)

  # Save suspected_cls to data_store.
  build_failure_analysis.SaveSuspectedCLs(suspected_cls, master_name,
                                          builder_name, build_number,
                                          failure_info.failure_type)

  # Monitors analysis status change.
  RecordCompileFailureAnalysisStateChange(master_name, builder_name,
                                          analysis_status.COMPLETED,
                                          analysis_approach_type.HEURISTIC)

  return CompileHeuristicAnalysisOutput(
      failure_info=failure_info,
      signals=CompileFailureSignals.FromSerializable(signals),
      heuristic_result=CompileHeuristicResult.FromSerializable(
          heuristic_result))


def RecordCompileFailureAnalysisStateChange(master_name, builder_name, status,
                                            analysis_type):
  """Records state changes for compile failure anlaysis."""
  monitoring.OnWaterfallAnalysisStateChange(
      master_name=master_name,
      builder_name=builder_name,
      failure_type=failure_type.GetDescriptionForFailureType(
          failure_type.COMPILE),
      canonical_step_name='compile',
      isolate_target_name='N/A',
      status=analysis_status.STATUS_TO_DESCRIPTION[status],
      analysis_type=analysis_approach_type.STATUS_TO_DESCRIPTION[analysis_type])


def GetSuspectedCLsWithCompileFailures(heuristic_result):
  """Generates a list of suspected CLs with compile failures.

  Args:
    heuristic_result(CompileHeuristicResult): the heuristic_result from which to
      generate the list of suspected CLs with failures.

  Returns:
    A list of suspected CLs with failures that each could look like:
        [step_name, revision, None]
    This is to make the result be consistent with test failure analyses, where
    the supected CL info would be [step_name, revision, test_name].
  """

  if not heuristic_result:
    return []

  suspected_cls_with_failures = []
  # Iterates through the failures and suspected_cls, appending suspected
  # CLs and failures to the list.
  for failure in heuristic_result['failures']:
    for suspected_cl in failure.suspected_cls:
      suspected_cls_with_failures.append(
          [failure.step_name, suspected_cl.revision, None])

  return suspected_cls_with_failures
