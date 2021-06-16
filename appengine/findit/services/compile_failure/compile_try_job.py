# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for compile-try-job-related operations.

It provides functions to:
  * Decide if a new compile try job is needed.
  * Get failed targets.
  * Get parameters for starting a new compile try job.
"""

import copy
import logging

from google.appengine.ext import ndb

from common import constants
from common import exceptions
from common.waterfall import failure_type
from libs import analysis_status
from model import analysis_approach_type
from model import result_status
from model.base_build_model import BaseBuildModel
from model.wf_analysis import WfAnalysis
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import build_failure_analysis
from services import git
from services import try_job as try_job_service
from services.compile_failure import compile_failure_analysis
from services.parameters import CompileTryJobResult
from services.parameters import RunCompileTryJobParameters
from waterfall import suspected_cl_util
from waterfall import waterfall_config


def _GetOutputNodes(signals):
  if not signals or 'compile' not in signals:
    return []

  # Compile failures with no output nodes will be considered unique.
  return signals['compile'].failed_output_nodes or []


def _GetMatchingCompileFailureGroups(output_nodes):
  groups = try_job_service.GetMatchingFailureGroups(failure_type.COMPILE)
  # Output nodes should already be unique and sorted.
  return [group for group in groups if group.output_nodes == output_nodes]


def _IsCompileFailureUniqueAcrossPlatforms(
    master_name, builder_name, build_number, build_failure_type, blame_list,
    signals, heuristic_result):

  if build_failure_type != failure_type.COMPILE:
    logging.info('Expected compile failure but get %s failure.',
                 failure_type.GetDescriptionForFailureType(build_failure_type))
    return True

  output_nodes = _GetOutputNodes(signals)
  if not output_nodes:
    return True
  groups = _GetMatchingCompileFailureGroups(output_nodes)
  suspected_cls_with_failures = (
      compile_failure_analysis.GetSuspectedCLsWithCompileFailures(
          heuristic_result))

  return try_job_service.IsBuildFailureUniqueAcrossPlatforms(
      master_name,
      builder_name,
      build_number,
      build_failure_type,
      blame_list,
      suspected_cls_with_failures,
      groups,
      output_nodes=output_nodes)


def _NeedANewCompileTryJob(master_name, builder_name, build_number,
                           failure_info):

  compile_failure = failure_info.failed_steps.get('compile') or None
  if compile_failure:
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.failure_result_map['compile'] = BaseBuildModel.CreateBuildKey(
        master_name, builder_name, compile_failure.first_failure)
    analysis.put()

    if (compile_failure.supported and
        compile_failure.first_failure == compile_failure.current_failure):
      return True

  return False


def NeedANewCompileTryJob(start_try_job_input):
  """Decides if a new compile try job is needed.

  A new compile try job is needed if:
  1. It passed preliminary checks in try_job_service.NeedANewWaterfallTryJob,
  2. It's for a compile failure,
  3. It's a first failure,
  4. There is no other running or completed try job.

  Returns:
    A bool to indicate if a new try job is needed.
    A key to the entity of the try job.
  """
  master_name, builder_name, build_number = (
      start_try_job_input.build_key.GetParts())
  need_new_try_job = try_job_service.NeedANewWaterfallTryJob(
      master_name, builder_name, build_number, start_try_job_input.force)

  if not need_new_try_job:
    return False, None

  try_job_type = start_try_job_input.heuristic_result.failure_info.failure_type
  if try_job_type != failure_type.COMPILE:
    logging.error('Checking for a compile try job but got a %s failure.',
                  failure_type.GetDescriptionForFailureType(try_job_type))
    return False, None

  need_new_try_job = _NeedANewCompileTryJob(
      master_name, builder_name, build_number,
      start_try_job_input.heuristic_result.failure_info)

  # TODO(chanli): enable the feature to trigger single try job for a group
  # when notification is ready.
  # We still call _IsBuildFailureUniqueAcrossPlatforms just so we have data for
  # failure groups.

  # TODO(chanli): Add checking for culprits of the group when enabling
  # single try job: add current build to suspected_cl.builds if the try job for
  # this group has already completed.
  if need_new_try_job:
    _IsCompileFailureUniqueAcrossPlatforms(
        master_name, builder_name, build_number, try_job_type,
        start_try_job_input.heuristic_result.failure_info.builds[str(
            build_number)].blame_list,
        start_try_job_input.heuristic_result.signals,
        start_try_job_input.heuristic_result.heuristic_result)

  try_job_was_created, try_job_key = try_job_service.ReviveOrCreateTryJobEntity(
      master_name, builder_name, build_number, start_try_job_input.force)
  need_new_try_job = need_new_try_job and try_job_was_created
  return need_new_try_job, try_job_key


def _GetFailedTargetsFromSignals(signals, master_name, builder_name):
  compile_targets = []

  if not signals or 'compile' not in signals:
    return compile_targets

  if signals['compile'].failed_output_nodes:
    return signals['compile'].failed_output_nodes

  strict_regex = waterfall_config.EnableStrictRegexForCompileLinkFailures(
      master_name, builder_name)
  for source_target in signals['compile'].failed_targets or []:
    # For link failures, we pass the executable targets directly to try-job, and
    # there is no 'source' for link failures.
    # For compile failures, only pass the object files as the compile targets
    # for the bots that we use strict regex to extract such information.
    if not source_target.source or strict_regex:
      compile_targets.append(source_target.target)

  return compile_targets


def _GetLastPassCompile(build_number, failed_steps):
  if (failed_steps.get('compile') and
      failed_steps['compile'].first_failure == build_number and
      failed_steps['compile'].last_pass is not None):
    return failed_steps['compile'].last_pass
  return None


def _GetGoodRevisionCompile(master_name, builder_name, build_number,
                            failure_info):
  last_pass = _GetLastPassCompile(build_number, failure_info.failed_steps)
  if last_pass is None:
    logging.warning(
        'Couldn"t start try job for build %s, %s, %d because'
        ' last_pass is not found.', master_name, builder_name, build_number)
    return None

  return failure_info.builds[str(last_pass)].chromium_revision


def GetParametersToScheduleCompileTryJob(start_compile_try_job_input,
                                         urlsafe_try_job_key):

  master_name, builder_name, build_number = (
      start_compile_try_job_input.build_key.GetParts())
  failure_info = start_compile_try_job_input.heuristic_result.failure_info

  parameters = try_job_service.PrepareParametersToScheduleTryJob(
      master_name, builder_name, build_number, failure_info,
      start_compile_try_job_input.heuristic_result.heuristic_result,
      urlsafe_try_job_key)

  parameters['good_revision'] = _GetGoodRevisionCompile(
      master_name, builder_name, build_number, failure_info)
  parameters['compile_targets'] = _GetFailedTargetsFromSignals(
      start_compile_try_job_input.heuristic_result.signals, master_name,
      builder_name)

  return RunCompileTryJobParameters.FromSerializable(parameters)


def _GetRevisionsInRange(sub_ranges):
  """Get revisions in regression range by flattening sub_ranges.

  sub_ranges is in a format like [[None, 'r1', 'r2'], ['r3', 'r4', 'r5']].
  """
  return [
      revision for sub_range in sub_ranges for revision in sub_range if revision
  ]


def CompileFailureIsFlaky(result):
  """Decides if the compile failure is flaky.

  A compile failure should be flaky if compile try job failed at good revision.
  """
  if not result:
    return False

  try_job_result = result.report.result
  sub_ranges = (
      result.report.metadata.get('sub_ranges') or []
      if result.report.metadata else [])

  if (not try_job_result or  # There is some issue with try job, cannot decide.
      not sub_ranges or  # Missing range information.
      # All passed. It could be because of flaky compile, but is not guaranteed.
      'failed' not in try_job_result.values()):
    return False

  tested_revisions = try_job_result.keys()
  # Looks for the good revision which will not be in sub_ranges.
  good_revision = list(
      set(tested_revisions) - set(_GetRevisionsInRange(sub_ranges)))
  return bool(good_revision)


@ndb.transactional
def UpdateTryJobResult(parameters, culprits):
  master_name, builder_name, build_number = parameters.build_key.GetParts()
  try_job = WfTryJob.Get(master_name, builder_name, build_number)
  new_result = parameters.result.ToSerializable() if parameters.result else {}
  try_job_id = parameters.result.try_job_id if parameters.result else None
  if culprits:
    try_job_service.UpdateTryJobResult(try_job.compile_results, new_result,
                                       try_job_id)
  try_job.status = analysis_status.COMPLETED
  try_job.put()


def _GetUpdatedAnalysisResult(analysis, flaky_compile):

  # Analysis only needs to update if the compile failure is actually flaky.
  if (not analysis.result or not analysis.result.get('failures') or
      not flaky_compile):
    return analysis.result

  analysis_result = copy.deepcopy(analysis.result)
  for failure in analysis_result['failures']:
    if failure['step_name'] == constants.COMPILE_STEP_NAME:
      failure['flaky'] = True

  return analysis_result


def _GetUpdatedSuspectedCLs(analysis, culprits):
  """Returns a list of combined suspected CLs from heuristic and try job.

  Args:
    analysis: The WfAnalysis entity corresponding to the try job.
    culprits: A dict of suspected CLs found by the try job.

  Returns:
    A combined list of suspected CLs from those already in analysis and those
    found by this try job.
  """
  suspected_cls = analysis.suspected_cls[:] if analysis.suspected_cls else []
  suspected_cl_revisions = [cl['revision'] for cl in suspected_cls]

  for revision, try_job_suspected_cl in culprits.iteritems():
    if revision not in suspected_cl_revisions:
      suspected_cl_copy = copy.deepcopy(try_job_suspected_cl)
      suspected_cl_revisions.append(revision)
      failures = {'compile': []}
      suspected_cl_copy['failures'] = failures
      suspected_cl_copy['top_score'] = None
      suspected_cls.append(suspected_cl_copy)

  return suspected_cls


@ndb.transactional
def UpdateWfAnalysisWithTryJobResult(master_name, builder_name, build_number,
                                     result, culprits, flaky_compile):
  if not culprits and not flaky_compile:
    return

  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  assert analysis
  # Update analysis result and suspected CLs with results of this try job if
  # culprits were found or failures are flaky.
  updated_result = _GetUpdatedAnalysisResult(analysis, flaky_compile)
  updated_result_status = try_job_service.GetResultAnalysisStatus(
      analysis, result) if not flaky_compile else result_status.FLAKY
  updated_suspected_cls = _GetUpdatedSuspectedCLs(analysis, culprits)
  analysis.UpdateWithNewFindings(
      updated_result_status=updated_result_status,
      updated_suspected_cls=updated_suspected_cls,
      updated_result=updated_result)


def UpdateSuspectedCLs(master_name, builder_name, build_number, culprits):
  if not culprits:
    return

  # Creates or updates each suspected_cl.
  for culprit in culprits.values():
    revision = culprit['revision']
    failures = {'compile': []}

    suspected_cl_util.UpdateSuspectedCL(culprit['repo_name'], revision,
                                        culprit.get('commit_position'),
                                        analysis_approach_type.TRY_JOB,
                                        master_name, builder_name, build_number,
                                        failure_type.COMPILE, failures, None)


def GetBuildProperties(pipeline_input):
  properties = try_job_service.GetBuildProperties(pipeline_input,
                                                  failure_type.COMPILE)
  properties['target_buildername'] = pipeline_input.build_key.builder_name
  properties['compile_targets'] = pipeline_input.compile_targets

  return properties


def ScheduleCompileTryJob(parameters, runner_id):
  master_name, builder_name, build_number = (parameters.build_key.GetParts())
  properties = GetBuildProperties(parameters)
  tryserver_mastername, tryserver_buildername = try_job_service.GetTrybot()

  build_id, error = try_job_service.TriggerTryJob(
      master_name, builder_name, tryserver_mastername,
      tryserver_buildername, properties,
      failure_type.GetDescriptionForFailureType(failure_type.COMPILE),
      parameters.cache_name, parameters.dimensions, runner_id)

  if error:
    raise exceptions.RetryException(error.reason, error.message)
  try_job = WfTryJob.Get(master_name, builder_name, build_number)
  try_job.compile_results.append({'try_job_id': build_id})
  try_job.try_job_ids.append(build_id)
  try_job.put()
  try_job = try_job_service.UpdateTryJob(
      master_name, builder_name, build_number, build_id, failure_type.COMPILE)

  # Create a corresponding WfTryJobData entity to capture as much metadata as
  # early as possible.
  try_job_service.CreateTryJobData(
      build_id,
      try_job.key,
      bool(parameters.compile_targets),
      bool(parameters.suspected_revisions),
      failure_type.COMPILE,
      runner_id=runner_id)

  return build_id


def OnTryJobStateChanged(try_job_id, build_json, run_try_job_params):
  """Updates TryJobData entity with new build state.

  Args:
    try_job_id (str): The build id of the try job.
    build_json (dict): The up-to-date build info.
    run_try_job_params (RunCompileTryJobParameters): Parameters to run try job.

  Returns:
    CompileTryJobResult if the try job has completed; otherwise None.
  """
  result, state = try_job_service.OnTryJobStateChanged(
      try_job_id, failure_type.COMPILE, build_json)

  if state in [analysis_status.COMPLETED, analysis_status.ERROR]:
    # TODO(crbug/869684): Use a gauge metric to track intermittent statuses.
    master_name, builder_name, _ = run_try_job_params.build_key.GetParts()
    compile_failure_analysis.RecordCompileFailureAnalysisStateChange(
        master_name, builder_name, state, analysis_approach_type.TRY_JOB)

  if result is not None:
    result = CompileTryJobResult.FromSerializable(result)
  return result


def IdentifyCompileTryJobCulprit(parameters):
  """Processes try job result and identifies culprit."""
  culprits = None
  flaky_compile = False

  master_name, builder_name, build_number = parameters.build_key.GetParts()
  result = parameters.result
  try_job_id = result.try_job_id if result else None
  if try_job_id and result and result.report:
    failed_revision = result.report.culprit
    failed_revisions = [failed_revision] if failed_revision else []
    culprits = try_job_service.GetCulpritsWithoutNoBlameAccountsCLS(
        git.GetCommitsInfo(failed_revisions))

    # In theory there are 2 cases where compile failure could be flaky:
    # 1. All revisions passed in the try job (try job will not run at good
    # revision in this case),
    # 2. The compile even failed at good revision.
    # We cannot guarantee in the first case the compile failure is flaky
    # because it's also possible the difference between buildbot and trybot
    # causes this.
    # So currently we'll only consider the second case.
    if not culprits and CompileFailureIsFlaky(result):
      flaky_compile = True

    if culprits:
      result.culprit = {'compile': culprits[failed_revision]}
      try_job_data = WfTryJobData.Get(try_job_id)
      try_job_data.culprits = {'compile': failed_revision}
      try_job_data.put()

  # Store try-job results.
  UpdateTryJobResult(parameters, culprits)

  # Saves cls found by heuristic approach to determine a culprit is found
  # by both heuristic and try job when sending notifications.
  # This part must be before UpdateWfAnalysisWithTryJobResult().
  heuristic_cls = build_failure_analysis.GetHeuristicSuspectedCLs(
      master_name, builder_name, build_number)

  # Add try-job results to WfAnalysis.
  UpdateWfAnalysisWithTryJobResult(master_name, builder_name, build_number,
                                   result, culprits, flaky_compile)

  # TODO (chanli): Update suspected_cl for builds in the same group with
  # current build.
  # Updates suspected_cl.
  UpdateSuspectedCLs(master_name, builder_name, build_number, culprits)

  return culprits, heuristic_cls


def OnTryJobTimeout(try_job_id, run_try_job_params):
  try_job_service.OnTryJobTimeout(try_job_id, failure_type.COMPILE)
  master_name, builder_name, _ = (run_try_job_params.build_key.GetParts())
  compile_failure_analysis.RecordCompileFailureAnalysisStateChange(
      master_name, builder_name, analysis_status.ERROR,
      analysis_approach_type.TRY_JOB)
