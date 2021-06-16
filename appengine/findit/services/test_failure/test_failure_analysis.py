# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a function to analyze test failures."""

import copy
from collections import defaultdict
import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from libs import analysis_status
from model import analysis_approach_type
from model import result_status
from model.base_build_model import BaseBuildModel
from model.wf_analysis import WfAnalysis
from services import build_failure_analysis
from services import ci_failure
from services import deps
from services import git
from services import monitoring
from services import step_util
from services.parameters import TestHeuristicAnalysisOutput
from services.parameters import TestHeuristicResult
from services.test_failure import ci_test_failure
from services.test_failure import extract_test_signal
from waterfall.failure_signal import FailureSignal


def _AnalyzeTestFailureOnOneBuild(build_number,
                                  step_name,
                                  test_name,
                                  failure_signal,
                                  change_log,
                                  deps_info,
                                  step_analysis_result,
                                  cl_failure_map,
                                  has_lower_level_info=False):

  new_suspected_cl_dict, max_score = build_failure_analysis.AnalyzeOneCL(
      build_number, failure_signal, change_log, deps_info)

  if not new_suspected_cl_dict:
    return

  step_analysis_result['suspected_cls'].append(new_suspected_cl_dict)

  if not has_lower_level_info:
    build_failure_analysis.SaveFailureToMap(
        cl_failure_map, new_suspected_cl_dict, step_name, test_name, max_score)


def AnalyzeTestFailure(failure_info, change_logs, deps_info, failure_signals):
  """Analyzes given failure signals, and figure out culprits of test failure.

  Args:
    failure_info (TestFailureInfo): Output of pipeline
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

  if not failure_signals:
    logging.debug('No failure signals when analyzing a test failure.')
    return analysis_result, []

  failed_steps = failure_info.failed_steps
  builds = failure_info.builds

  cl_failure_map = defaultdict(build_failure_analysis.CLInfo)

  for step_name, step_failure_info in failed_steps.iteritems():
    is_test_level = step_failure_info.tests is not None

    failed_build_number = step_failure_info.current_failure
    start_build_number = (
        build_failure_analysis.GetLowerBoundForAnalysis(step_failure_info))
    step_analysis_result = (
        build_failure_analysis.InitializeStepLevelResult(
            step_name, step_failure_info))

    if is_test_level:
      step_analysis_result['tests'] = []
      tests = step_failure_info.tests or {}
      for test_name, test_failure in tests.iteritems():
        test_analysis_result = {
            'test_name': test_name,
            'first_failure': test_failure.first_failure,
            'last_pass': test_failure.last_pass,
            'suspected_cls': [],
        }
        step_analysis_result['tests'].append(test_analysis_result)

    if step_analysis_result['supported']:
      step_failure_signal = FailureSignal.FromDict(failure_signals[step_name])
      for build_number, build in builds.iteritems():
        if (build_number > failed_build_number or
            build_number < start_build_number):
          continue

        for revision in build.blame_list:
          # TODO(crbug/842980): Deprecate blame_list in builds.
          if not change_logs.get(revision):
            continue

          if is_test_level:
            # Checks files at test level.
            for test_analysis_result in step_analysis_result['tests']:
              test_name = test_analysis_result['test_name']
              test_signal = FailureSignal.FromDict(
                  failure_signals[step_name]['tests'].get(test_name) or {})

              _AnalyzeTestFailureOnOneBuild(build_number, step_name, test_name,
                                            test_signal, change_logs[revision],
                                            deps_info, test_analysis_result,
                                            cl_failure_map)

          # Checks Files on step level using step level signals
          # regardless of test level signals so we can make sure
          # no duplicate justifications added to the step result.
          _AnalyzeTestFailureOnOneBuild(
              build_number,
              step_name,
              None,
              step_failure_signal,
              change_logs[revision],
              deps_info,
              step_analysis_result,
              cl_failure_map,
              has_lower_level_info=is_test_level)

    # TODO(stgao): sort CLs by score.
    analysis_result['failures'].append(step_analysis_result)

  suspected_cls = build_failure_analysis.ConvertCLFailureMapToList(
      cl_failure_map)

  return analysis_result, suspected_cls


def HeuristicAnalysisForTest(heuristic_params):
  """Identifies culprit CL.

  Args:
    heuristic_params (TestHeuristicAnalysisParameters): A structured object
    with 2 fields:
      failure_info (TestFailureInfo): An object of failure info for the
      current failed build.
      build_completed (bool): If the build is completed.

  Returns:
    A TestHeuristicAnalysisOutput object with information about
    failure_info and heuristic_result.
  """
  failure_info = heuristic_params.failure_info
  master_name = failure_info.master_name
  builder_name = failure_info.builder_name
  build_number = failure_info.build_number

  # 1. Detects first failed builds for failed test step, updates failure_info.
  failure_info = ci_failure.CheckForFirstKnownFailure(
      master_name, builder_name, build_number, failure_info)

  # Checks first failed builds for each failed test.
  ci_test_failure.CheckFirstKnownFailureForSwarmingTests(
      master_name, builder_name, build_number, failure_info)

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  analysis.failure_info = failure_info.ToSerializable()
  analysis.put()

  # Lacking chromium_revision indicates something is wrong in Findit,
  assert failure_info.chromium_revision, (
      'No end_revision when pulling change logs.')

  # 2. Extracts failure signal.
  signals = extract_test_signal.ExtractSignalsForTestFailure(
      failure_info, FinditHttpClient())

  # 3. Gets change_logs.
  change_logs = git.PullChangeLogs(
      ci_failure.GetGoodRevision(failure_info), failure_info.chromium_revision)

  # 4. Gets deps info.
  deps_info = deps.ExtractDepsInfo(failure_info, change_logs)

  # 5. Analyzes the test failure using information collected above.
  heuristic_result, suspected_cls = AnalyzeTestFailure(
      failure_info, change_logs, deps_info, signals)

  # Save results and other info to analysis.
  build_failure_analysis.SaveAnalysisAfterHeuristicAnalysisCompletes(
      master_name, builder_name, build_number, heuristic_result, suspected_cls)

  # Save suspected_cls to data_store.
  build_failure_analysis.SaveSuspectedCLs(
      suspected_cls, failure_info.master_name, failure_info.builder_name,
      failure_info.build_number, failure_info.failure_type)

  # Monitors analysis status change.
  # Only record one metric for each analysis.
  RecordTestFailureAnalysisStateChange(master_name, builder_name,
                                       analysis_status.COMPLETED,
                                       analysis_approach_type.HEURISTIC)

  return TestHeuristicAnalysisOutput(
      failure_info=failure_info,
      heuristic_result=TestHeuristicResult.FromSerializable(heuristic_result))


def UpdateAnalysisResultWithFlakeInfo(analysis_result, flaky_failures):
  """Updates WfAnalysis' result and result_analysis on flaky failures.

  If found flaky tests from swarming reruns, or flaky tests or compile from
  try jobs, updates WfAnalysis.
  """
  all_flaked = True
  updated_result = copy.deepcopy(analysis_result)
  for failure in updated_result.get('failures') or {}:
    step_name = failure.get('step_name')
    if step_name in flaky_failures:
      failure['flaky'] = True
      for test in failure.get('tests') or []:
        if test.get('test_name') in flaky_failures[step_name]:
          test['flaky'] = True
        else:
          all_flaked = False
          failure['flaky'] = False
    else:
      # Checks all other steps to see if all failed steps/ tests are flaky.
      if not failure.get('flaky'):
        all_flaked = False

  return updated_result, all_flaked


@ndb.transactional
def UpdateAnalysisWithFlakesFoundBySwarmingReruns(master_name, builder_name,
                                                  build_number, flaky_tests):
  """Updates WfAnalysis about flaky tests found by swarming reruns.

  Args:
    master_name(str): Name of the master.
    builder_name(str): Name of the builder.
    build_number(int): Number of the build.
    flaky_tests(dict): A dict of flaky tests.
  """

  if not flaky_tests:
    return

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  assert analysis
  if not analysis.result or analysis.flaky_tests == flaky_tests:
    return

  updated_result, all_flaked = UpdateAnalysisResultWithFlakeInfo(
      analysis.result, flaky_tests)
  updated_result_status = result_status.FLAKY if all_flaked else None
  analysis.UpdateWithNewFindings(
      updated_result_status=updated_result_status,
      updated_result=updated_result,
      flaky_tests=flaky_tests)


def GetFirstTimeFailedSteps(master_name, builder_name, build_number):
  """Gets steps that have tests failed first time in the build."""
  current_build_key = BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                                    build_number)
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  assert analysis, "Cannot get WfAnalysis entity for %s" % current_build_key

  first_failed_steps = []
  for step, tests in (analysis.failure_result_map or {}).iteritems():
    if isinstance(tests, basestring):  # Non-swarming.
      continue

    if current_build_key in tests.values():
      first_failed_steps.append(step)
  return first_failed_steps


@ndb.transactional
def GetsFirstFailureAtTestLevel(master_name, builder_name, build_number,
                                failure_info, force):
  """Gets first time failed steps and tests in the build that has not been
    analyzed.

  This function will also update analysis.failure_result_map for new failures
  that has not been analyzed.

  But if force is True, this function will return all first time failures in the
  build and not update analysis.failure_result_map.

  Args:
    master_name(str): Name of the master.
    builder_name(str): Name of the builder.
    build_number(int): Number of the build.
    failure_info(TestFailureInfo): Information about the build failure.
    force(bool): If the analysis is a forced rerun.
  """
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)

  if not analysis:
    return {}

  # A dict to store all the first time failed steps and/ or tests which
  # have not triggered a swarming task yet.
  result_steps = defaultdict(list)
  failure_result_map = analysis.failure_result_map

  for failed_step_name, step_failure_details in (
      failure_info.failed_steps.iteritems()):
    if not step_failure_details.tests or not step_failure_details.supported:
      # Not a test type Findit currently handles.
      continue

    if not force:
      if failure_result_map.get(failed_step_name):
        # The step has been processed.
        continue
      else:
        failure_result_map[failed_step_name] = {}

    for failed_test_name, test_failure_details in (
        step_failure_details.tests.iteritems()):
      if not force:
        # Updates analysis.failure_result_map only when the analysis runs at the
        # first time.
        task_key = '%s/%s/%s' % (master_name, builder_name,
                                 test_failure_details.first_failure)
        failure_result_map[failed_step_name][failed_test_name] = task_key

      if (test_failure_details.first_failure == test_failure_details
          .current_failure):
        # First time failure, add to result_steps.
        result_steps[failed_step_name].append(
            test_failure_details.base_test_name)

  if not force:
    analysis.put()
  return result_steps


def RecordTestFailureAnalysisStateChange(master_name, builder_name, status,
                                         analysis_type):
  """Records state changes for test failure analysis."""
  monitoring.OnWaterfallAnalysisStateChange(
      master_name=master_name,
      builder_name=builder_name,
      failure_type=failure_type.GetDescriptionForFailureType(failure_type.TEST),
      canonical_step_name='Unknown',
      isolate_target_name='Unknown',
      status=analysis_status.STATUS_TO_DESCRIPTION[status],
      analysis_type=analysis_approach_type.STATUS_TO_DESCRIPTION[analysis_type])


def GetSuspectedCLsWithFailures(master_name, builder_name, build_number,
                                heuristic_result):
  """Generates a list of suspected CLs with failures.

  Args:
    master_name (str): Name of the master.
    builder_name (str): Name of the builder.
    build_number (int): Number of the failed build.
    heuristic_result (TestHeuristicResult): the heuristic_result from which to
      generate the list of suspected CLs with failures.

  Returns:
    A list of suspected CLs with failures that each could look like:

        [step_name, revision, test_name]

    or could look like:

        [step_name, revision, None]
  """

  if not heuristic_result:
    return []

  suspected_cls_with_failures = []
  # Iterates through the failures, tests, and suspected_cls, appending suspected
  # CLs and failures to the list.
  for failure in heuristic_result['failures']:
    if failure.tests:
      for test in failure.tests:
        for suspected_cl in test.suspected_cls or []:
          suspected_cls_with_failures.append([
              step_util.LegacyGetCanonicalStepName(
                  master_name, builder_name, build_number, failure.step_name),
              suspected_cl.revision, test.test_name
          ])
    else:
      for suspected_cl in failure.suspected_cls:
        suspected_cls_with_failures.append(
            [failure.step_name, suspected_cl.revision, None])

  return suspected_cls_with_failures
