# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to provide Findit service APIs through Cloud Endpoints:

Current APIs include:
1. Analysis of compile/test failures in Chromium waterfalls.
   Analyzes failures and detects suspected CLs.
2. Analysis of flakes on Commit Queue.
"""

from collections import defaultdict
import json
import logging

import endpoints
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.protobuf import json_format
from google.protobuf.field_mask_pb2 import FieldMask
from protorpc import messages
from protorpc import remote

import gae_ts_mon

from common import acl
from common import constants
from common import exceptions
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from findit_v2.model.messages import findit_result
from findit_v2.services import api as findit_v2_api
from gae_libs import appengine_util
from gae_libs.caches import PickledMemCache
from libs import analysis_status
from libs import time_util
from libs.cache_decorator import Cached
from model import analysis_approach_type
from model.base_build_model import BaseBuildModel
from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake_type import FlakeType
from model.suspected_cl_confidence import SuspectedCLConfidence
from model.test_inventory import LuciTest
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from services import monitoring
from services.apis import AsyncProcessFlakeReport
from waterfall import buildbot
from waterfall import suspected_cl_util
from waterfall import waterfall_config

# This is used by the underlying ProtoRpc when creating names for the ProtoRPC
# messages below. This package name will show up as a prefix to the message
# class names in the discovery doc and client libraries.
package = 'FindIt'

# How many seconds to cache requests for repeat analyses.
ANALYSIS_CACHE_TIME = 5 * 60


# These subclasses of Message are basically definitions of Protocol RPC
# messages. https://cloud.google.com/appengine/docs/python/tools/protorpc/
class _BuildFailure(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)
  # All failed steps of the build reported by the client.
  failed_steps = messages.StringField(4, repeated=True, required=False)


class _BuildFailureCollection(messages.Message):
  """Represents a request from a client, eg. builder_alerts."""
  builds = messages.MessageField(_BuildFailure, 1, repeated=True)


class _AnalysisApproach(messages.Enum):
  HEURISTIC = analysis_approach_type.HEURISTIC
  TRY_JOB = analysis_approach_type.TRY_JOB


class _SuspectedCL(messages.Message):
  repo_name = messages.StringField(1, required=True)
  revision = messages.StringField(2, required=True)
  commit_position = messages.IntegerField(3, variant=messages.Variant.INT32)
  confidence = messages.IntegerField(4, variant=messages.Variant.INT32)
  analysis_approach = messages.EnumField(_AnalysisApproach, 5)
  revert_cl_url = messages.StringField(6)
  revert_committed = messages.BooleanField(7, default=False)


class _TryJobStatus(messages.Enum):
  # Try job is pending or running. Can expect result from try job.
  RUNNING = 1
  # There is no try job, try job completed or try job finished with error.
  # Result from try job is ready or no need to continue waiting for it.
  FINISHED = 2


class _BuildFailureAnalysisResult(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)
  step_name = messages.StringField(4, required=True)
  is_sub_test = messages.BooleanField(
      5, variant=messages.Variant.BOOL, required=True)
  test_name = messages.StringField(6)
  first_known_failed_build_number = messages.IntegerField(
      7, variant=messages.Variant.INT32)
  suspected_cls = messages.MessageField(_SuspectedCL, 8, repeated=True)
  analysis_approach = messages.EnumField(_AnalysisApproach, 9)
  try_job_status = messages.EnumField(_TryJobStatus, 10)
  is_flaky_test = messages.BooleanField(11, variant=messages.Variant.BOOL)
  # Indicates if Findit has any kind of findings: found the culprit or
  # confirmed the test is flaky.
  has_findings = messages.BooleanField(12, variant=messages.Variant.BOOL)
  # If analysis is finished.
  is_finished = messages.BooleanField(13, variant=messages.Variant.BOOL)
  # If the failure is supported.
  is_supported = messages.BooleanField(14, variant=messages.Variant.BOOL)


class _BuildFailureAnalysisResultCollection(messages.Message):
  """Represents a response to the client, eg. builder_alerts."""
  results = messages.MessageField(_BuildFailureAnalysisResult, 1, repeated=True)


class _BuildStep(messages.Message):
  master_name = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)
  step_name = messages.StringField(4, required=True)


class _Flake(messages.Message):
  name = messages.StringField(1, required=True)
  is_step = messages.BooleanField(2, required=False, default=False)
  bug_id = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=False)
  build_steps = messages.MessageField(_BuildStep, 4, repeated=True)


class _Build(messages.Message):
  master_name = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)


class _FlakeAnalysis(messages.Message):
  queued = messages.BooleanField(1, required=True)


class _DisabledTestVariant(messages.Message):
  variant = messages.StringField(1, repeated=True)


class _DisabledTestData(messages.Message):
  luci_project = messages.StringField(1, required=True)
  normalized_test_name = messages.StringField(2, required=True)
  normalized_step_name = messages.StringField(3, required=True)
  disabled_test_variants = messages.MessageField(
      _DisabledTestVariant, 4, repeated=True)


class _DisabledTestsResponse(messages.Message):
  test_data = messages.MessageField(_DisabledTestData, 1, repeated=True)
  test_count = messages.IntegerField(2, variant=messages.Variant.INT32)


class _DisabledTestRequestType(messages.Enum):
  NAME_ONLY = 1
  ALL = 2
  COUNT = 3


class _DisabledTestsRequest(messages.Message):
  include_tags = messages.StringField(1, repeated=True)
  exclude_tags = messages.StringField(2, repeated=True)
  request_type = messages.EnumField(
      _DisabledTestRequestType, 3, default=_DisabledTestRequestType.NAME_ONLY)


class _StepAndTestName(messages.Message):
  step_ui_name = messages.StringField(1, required=True)
  test_name = messages.StringField(2, required=True)


class _CQFlakesRequest(messages.Message):
  project = messages.StringField(1, required=True)
  bucket = messages.StringField(2, required=True)
  builder = messages.StringField(3, required=True)
  tests = messages.MessageField(_StepAndTestName, 4, repeated=True)


class _CQFlake(messages.Message):
  test = messages.MessageField(_StepAndTestName, 1, required=True)
  affected_gerrit_changes = messages.IntegerField(2, repeated=True)
  monorail_issue = messages.IntegerField(3, required=True)


class _CQFlakeResponse(messages.Message):
  flakes = messages.MessageField(_CQFlake, 1, repeated=True)


@ndb.tasklet
def _GetCQFlakeAsync(project, bucket, builder, test):
  """Decides whether a test is flaky on CQ.

  As of 2019-12-06, the algorithm used to determine whether a test is flaky on
  CQ is as following:
  1. >= 3 different CLs have a failed step due to this test within the past 24h.
  2. >= 1 CL have a failed step due to this test within the past 12h.
  3. A bug has been filed for this flaky test.

  These rules are designed to be conservative and are subject to change based on
  user feedback.

  Args:
    project (str): Luci project name.
    bucket (str): Luci bucket name.
    builder (str): Luci builder name.
    test (_StepAndTestName): The test to check if it's flaky.

  Returns:
    A _CQFlake if the test is flaky, otherwise, None.
  """
  query = FlakeOccurrence.query(
      ndb.OR(FlakeOccurrence.flake_type == FlakeType.RETRY_WITH_PATCH,
             FlakeOccurrence.flake_type == FlakeType.CQ_FALSE_REJECTION),
      FlakeOccurrence.build_configuration.luci_project == project,
      FlakeOccurrence.build_configuration.luci_bucket == bucket,
      FlakeOccurrence.build_configuration.luci_builder == builder,
      FlakeOccurrence.step_ui_name == test.step_ui_name,
      FlakeOccurrence.test_name == test.test_name,
      FlakeOccurrence.time_happened >= time_util.GetDatetimeBeforeNow(hours=24))
  occurrences = yield query.fetch_async()

  unique_cls = {o.gerrit_cl_id for o in occurrences}
  active_start = time_util.GetDatetimeBeforeNow(hours=12)
  is_active = any(o.time_happened > active_start for o in occurrences)

  if len(unique_cls) < 3 or not is_active:
    raise ndb.Return(None)

  parent_flake = yield occurrences[0].key.parent().get_async()
  if not parent_flake or not parent_flake.flake_issue_key:
    raise ndb.Return(None)

  issue = yield parent_flake.flake_issue_key.get_async()
  destination_issue_key = yield issue.GetMostUpdatedIssueAsync(key_only=True)
  if not destination_issue_key:
    raise ndb.Return(None)

  raise ndb.Return(
      _CQFlake(
          test=test,
          # A list of CLs used for communication and debugging, so 5 is enough.
          affected_gerrit_changes=list(unique_cls)[:5],
          monorail_issue=int(destination_issue_key.id().split('@')[1])))


@Cached(
    PickledMemCache(),  # Since the return values are < 1MB.
    expire_time=ANALYSIS_CACHE_TIME)
def _AsyncProcessFailureAnalysisRequests(builds):
  """Pushes a task on the backend to process requests of failure analysis."""
  target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)
  payload = json.dumps({'builds': builds})
  taskqueue.add(
      url=constants.WATERFALL_PROCESS_FAILURE_ANALYSIS_REQUESTS_URL,
      payload=payload,
      target=target,
      queue_name=constants.WATERFALL_FAILURE_ANALYSIS_REQUEST_QUEUE)
  # Needed for @Cached to work, but ignored by caller.
  return 'Only semantically None.'


def _ValidateOauthUser():
  """Validates the oauth user and raises an exception if not authorized.
  Returns:
    A tuple (user_email, is_admin).
    user_email (str): The email address of the oauth user.
    is_admin (bool): True if the oauth user is an Admin.

  Raises:
    endpoints.UnauthorizedException if the user has no permission.
  """
  try:
    return acl.ValidateOauthUserForNewAnalysis()
  except exceptions.UnauthorizedException as e:
    raise endpoints.UnauthorizedException('Unauthorized: %s' % e.message)


# Create a Cloud Endpoints API.
# https://cloud.google.com/appengine/docs/python/endpoints/create_api
@endpoints.api(name='findit', version='v1', description='FindIt API')
class FindItApi(remote.Service):
  """FindIt API v1."""

  def _GetAdditionalInformationForCL(self, repo_name, revision, confidences,
                                     build, reference_build_key):
    """Gets additional information for a cl.

    Currently additional information contains:
        confidence of the result;
        approaches that found this cl: HEURISTIC, TRY_JOB or both;
        revert_cl_url if the cl has been reverted by Findit;
        if the revert has been committed.
    """
    additional_info = {}

    cl = WfSuspectedCL.Get(repo_name, revision)
    if not cl:
      return additional_info

    master_name = buildbot.GetMasterNameFromUrl(build.master_url)
    builder_name = build.builder_name
    current_build = build.build_number

    # If the CL is found by a try job, only the first failure will be recorded.
    # So we might need to go to the first failure to get CL information.
    build_info = cl.GetBuildInfo(master_name, builder_name, current_build)
    first_build_info = None if not reference_build_key else cl.GetBuildInfo(
        *BaseBuildModel.GetBuildInfoFromBuildKey(reference_build_key))
    additional_info['confidence'], additional_info['cl_approach'] = (
        suspected_cl_util.GetSuspectedCLConfidenceScoreAndApproach(
            confidences, build_info, first_build_info))

    # Gets the revert_cl_url for the CL if there is one.
    if cl.revert_cl_url:
      additional_info['revert_cl_url'] = cl.revert_cl_url

    additional_info['revert_committed'] = (
        cl.revert_submission_status == analysis_status.COMPLETED)

    return additional_info

  def _GenerateBuildFailureAnalysisResult(
      self,
      build,
      step_name,
      suspected_cls_in_result=None,
      first_failure=None,
      test_name=None,
      analysis_approach=_AnalysisApproach.HEURISTIC,
      confidences=None,
      try_job_status=None,
      is_flaky_test=False,
      reference_build_key=None,
      has_findings=True,
      is_finished=True,
      is_supported=True):

    suspected_cls_in_result = suspected_cls_in_result or []
    suspected_cls = []
    for suspected_cl in suspected_cls_in_result:
      repo_name = suspected_cl['repo_name']
      revision = suspected_cl['revision']
      commit_position = suspected_cl['commit_position']
      additional_info = self._GetAdditionalInformationForCL(
          repo_name, revision, confidences, build, reference_build_key)
      if additional_info.get('cl_approach'):
        cl_approach = (
            _AnalysisApproach.HEURISTIC if
            additional_info['cl_approach'] == analysis_approach_type.HEURISTIC
            else _AnalysisApproach.TRY_JOB)
      else:
        cl_approach = analysis_approach

      suspected_cls.append(
          _SuspectedCL(
              repo_name=repo_name,
              revision=revision,
              commit_position=commit_position,
              confidence=additional_info.get('confidence'),
              analysis_approach=cl_approach,
              revert_cl_url=additional_info.get('revert_cl_url'),
              revert_committed=additional_info.get('revert_committed')))

    return _BuildFailureAnalysisResult(
        master_url=build.master_url,
        builder_name=build.builder_name,
        build_number=build.build_number,
        step_name=step_name,
        is_sub_test=test_name is not None,
        test_name=test_name,
        first_known_failed_build_number=first_failure,
        suspected_cls=suspected_cls,
        analysis_approach=analysis_approach,
        try_job_status=try_job_status,
        is_flaky_test=is_flaky_test,
        has_findings=has_findings,
        is_finished=is_finished,
        is_supported=is_supported)

  def _GetStatusAndCulpritFromTryJob(self,
                                     try_job,
                                     swarming_task,
                                     build_failure_type,
                                     step_name,
                                     test_name=None):
    """Returns the culprit found by try-job for the given step or test."""

    if swarming_task and swarming_task.status in (analysis_status.PENDING,
                                                  analysis_status.RUNNING):
      return _TryJobStatus.RUNNING, None

    if not try_job or try_job.failed:
      return _TryJobStatus.FINISHED, None

    if not try_job.completed:
      return _TryJobStatus.RUNNING, None

    if build_failure_type == failure_type.COMPILE:
      if not try_job.compile_results:  # pragma: no cover.
        return _TryJobStatus.FINISHED, None
      return (_TryJobStatus.FINISHED, try_job.compile_results[-1].get(
          'culprit', {}).get(step_name))

    if not try_job.test_results:  # pragma: no cover.
      return _TryJobStatus.FINISHED, None

    if test_name is None:
      step_info = try_job.test_results[-1].get('culprit', {}).get(step_name)
      if not step_info or step_info.get('tests'):  # pragma: no cover.
        # TODO(chanli): For some steps like checkperms/sizes/etc, the culprit
        # finding try-job might have test-level results.
        return _TryJobStatus.FINISHED, None
      return _TryJobStatus.FINISHED, step_info

    ref_name = (
        swarming_task.parameters.get('ref_name')
        if swarming_task and swarming_task.parameters else None)
    return (_TryJobStatus.FINISHED,
            try_job.test_results[-1].get('culprit', {}).get(
                ref_name or step_name, {}).get('tests', {}).get(test_name))

  def _CheckIsFlaky(self, swarming_task, test_name):
    """Checks if the test is flaky."""
    if not swarming_task or not swarming_task.classified_tests:
      return False

    return test_name in swarming_task.classified_tests.get('flaky_tests', [])

  def _PopulateResult(self,
                      results,
                      build,
                      step_name,
                      build_failure_type=None,
                      heuristic_result=None,
                      confidences=None,
                      reference_build_key=None,
                      swarming_task=None,
                      try_job=None,
                      test_name=None,
                      has_findings=True,
                      is_finished=True,
                      is_supported=True):
    """Appends an analysis result for the given step or test.

    Try-job results are always given priority over heuristic results.
    """
    if not has_findings or not is_finished:
      results.append(
          self._GenerateBuildFailureAnalysisResult(
              build,
              step_name,
              has_findings=has_findings,
              is_finished=is_finished,
              is_supported=is_supported))
      return

    # Default to heuristic analysis.
    suspected_cls = heuristic_result['suspected_cls']
    analysis_approach = _AnalysisApproach.HEURISTIC

    # Check if the test is flaky.
    is_flaky_test = self._CheckIsFlaky(swarming_task, test_name)

    if is_flaky_test:
      suspected_cls = []
      try_job_status = _TryJobStatus.FINISHED  # There will be no try job.
    else:
      # Check analysis result from try-job.
      try_job_status, culprit = self._GetStatusAndCulpritFromTryJob(
          try_job,
          swarming_task,
          build_failure_type,
          step_name,
          test_name=test_name)
      if culprit:
        suspected_cls = [culprit]
        analysis_approach = _AnalysisApproach.TRY_JOB

    if not is_flaky_test and not suspected_cls:
      # No findings for the test.
      has_findings = False

    if try_job_status == _TryJobStatus.RUNNING:
      is_finished = False

    results.append(
        self._GenerateBuildFailureAnalysisResult(
            build,
            step_name,
            suspected_cls,
            heuristic_result['first_failure'],
            test_name,
            analysis_approach,
            confidences,
            try_job_status,
            is_flaky_test,
            reference_build_key,
            has_findings,
            is_finished,
            is_supported=is_supported))

  def _GetAllSwarmingTasks(self, failure_result_map):
    """Returns all swarming tasks related to one build.

    Args:
      A dict to map each step/test with the key to the build when it failed the
      first time.
      {
          'step1': 'm/b/1',
          'step2': {
              'test1': 'm/b/1',
              'test2': 'm/b/2'
          }
      }

    Returns:
      A dict of swarming tasks like below:
      {
          'step1': {
              'm/b/1': WfSwarmingTask(
                  key=Key('WfBuild', 'm/b/1', 'WfSwarmingTask', 'step1'),...)
          },
          ...
      }
    """
    if not failure_result_map:
      return {}

    swarming_tasks = defaultdict(dict)
    for step_name, step_map in failure_result_map.iteritems():
      if isinstance(step_map, basestring):
        swarming_tasks[step_name][step_map] = (
            WfSwarmingTask.Get(
                *BaseBuildModel.GetBuildInfoFromBuildKey(step_map),
                step_name=step_name))
      else:
        for task_key in step_map.values():
          if not swarming_tasks[step_name].get(task_key):
            swarming_tasks[step_name][task_key] = (
                WfSwarmingTask.Get(
                    *BaseBuildModel.GetBuildInfoFromBuildKey(task_key),
                    step_name=step_name))

    return swarming_tasks

  def _GetAllTryJobs(self, failure_result_map):
    """Returns all try jobs related to one build.

    Args:
      A dict to map each step/test with the key to the build when it failed the
      first time.
      {
          'step1': 'm/b/1',
          'step2': {
              'test1': 'm/b/1',
              'test2': 'm/b/2'
          }
      }

    Returns:
      A dict of try jobs like below:
      {
          'm/b/1': WfTryJob(
              key=Key('WfBuild', 'm/b/1'),...)
          ...
      }
    """
    if not failure_result_map:
      return {}

    try_jobs = {}
    for step_map in failure_result_map.values():
      if isinstance(step_map, basestring):
        try_jobs[step_map] = WfTryJob.Get(*step_map.split('/'))
      else:
        for task_key in step_map.values():
          if not try_jobs.get(task_key):
            try_jobs[task_key] = WfTryJob.Get(*task_key.split('/'))

    return try_jobs

  def _GetSwarmingTaskAndTryJobForFailure(
      self, step_name, test_name, failure_result_map, swarming_tasks, try_jobs):
    """Gets swarming task and try job for the specific step/test."""
    if not failure_result_map:
      return None, None, None

    if test_name:
      try_job_key = failure_result_map.get(step_name, {}).get(test_name)
    else:
      try_job_key = failure_result_map.get(step_name)

    if not isinstance(try_job_key, basestring):
      if try_job_key:
        # Mismatch between failure_info and failure_result_map, cannot trust the
        # data.
        logging.error(
            'Try_job_key in wrong format - failure_result_map: %s;'
            ' step_name: %s; test_name: %s.',
            json.dumps(failure_result_map, default=str), step_name, test_name)
      return None, None, None

    # Gets the swarming task for the test.
    swarming_task = swarming_tasks.get(step_name, {}).get(try_job_key)

    # Get the try job for the step/test.
    try_job = try_jobs.get(try_job_key)

    return try_job_key, swarming_task, try_job

  def _GenerateResultsForBuild(self, build, heuristic_analysis, results,
                               confidences):

    # Checks has_findings and is_finished for heuristic analysis.
    has_findings = bool(heuristic_analysis and heuristic_analysis.result and
                        not heuristic_analysis.failed)
    is_finished = heuristic_analysis.completed

    if not has_findings:
      # No result.
      for step_name in build.failed_steps:
        is_supported = True  # The step may be analyzed now.
        self._PopulateResult(
            results,
            build,
            step_name,
            has_findings=has_findings,
            is_finished=is_finished,
            is_supported=is_supported)
      return

    steps_with_result = [
        f.get('step_name') for f in heuristic_analysis.result['failures']
    ]
    steps_without_result = [
        step_name for step_name in build.failed_steps
        if step_name not in steps_with_result
    ]

    for step_name in steps_without_result:
      has_findings = False  # No findings for the step.
      is_supported = True  # The step may be analyzed now.
      self._PopulateResult(
          results,
          build,
          step_name,
          has_findings=has_findings,
          is_finished=is_finished,
          is_supported=is_supported)

    swarming_tasks = self._GetAllSwarmingTasks(
        heuristic_analysis.failure_result_map)
    try_jobs = self._GetAllTryJobs(heuristic_analysis.failure_result_map)

    for failure in heuristic_analysis.result['failures']:
      step_name = failure.get('step_name')
      is_supported = failure.get('supported', False)

      if not is_supported:
        has_findings = False
        self._PopulateResult(
            results,
            build,
            step_name,
            has_findings=has_findings,
            is_finished=is_finished,
            is_supported=is_supported)
        continue

      if failure.get('tests'):  # Test-level analysis.
        for test in failure['tests']:
          test_name = test['test_name']
          reference_build_key, swarming_task, try_job = (
              self._GetSwarmingTaskAndTryJobForFailure(
                  step_name, test_name, heuristic_analysis.failure_result_map,
                  swarming_tasks, try_jobs))
          self._PopulateResult(
              results,
              build,
              step_name,
              heuristic_analysis.failure_type,
              test,
              confidences,
              reference_build_key,
              swarming_task,
              try_job,
              test_name=test_name)
      else:
        reference_build_key, swarming_task, try_job = (
            self._GetSwarmingTaskAndTryJobForFailure(
                step_name, None, heuristic_analysis.failure_result_map,
                swarming_tasks, try_jobs))
        self._PopulateResult(
            results, build, step_name, heuristic_analysis.failure_type, failure,
            confidences, reference_build_key, swarming_task, try_job)

  @gae_ts_mon.instrument_endpoint()
  @endpoints.method(
      _BuildFailureCollection,
      _BuildFailureAnalysisResultCollection,
      path='buildfailure',
      name='buildfailure')
  def AnalyzeBuildFailures(self, request):
    """Returns analysis results for the given build failures in the request.

    Analysis of build failures will be triggered automatically on demand.

    Args:
      request (_BuildFailureCollection): A list of build failures.

    Returns:
      _BuildFailureAnalysisResultCollection
      A list of analysis results for the given build failures.
    """
    _ValidateOauthUser()

    results = []
    supported_builds = []
    confidences = SuspectedCLConfidence.Get()

    for build in request.builds:
      master_name = buildbot.GetMasterNameFromUrl(build.master_url)
      if not (master_name and waterfall_config.MasterIsSupported(master_name)):
        logging.info('%s/%s/%s is not supported', build.master_url,
                     build.builder_name, build.build_number)
        continue

      supported_builds.append({
          'master_name': master_name,
          'builder_name': build.builder_name,
          'build_number': build.build_number,
          'failed_steps': sorted(build.failed_steps),
      })

      # If the build failure was already analyzed and a new analysis is
      # scheduled to analyze new failed steps, the returned WfAnalysis will
      # still have the result from last completed analysis.
      # If there is no analysis yet, no result is returned.
      heuristic_analysis = WfAnalysis.Get(master_name, build.builder_name,
                                          build.build_number)
      if not heuristic_analysis:
        continue

      self._GenerateResultsForBuild(build, heuristic_analysis, results,
                                    confidences)

    logging.info('%d build failure(s), while %d are supported',
                 len(request.builds), len(supported_builds))

    if appengine_util.IsStaging():
      # Findit staging accepts requests, but not actually run any analyses.
      logging.info('Got build failure requests on staging. No analysis runs on '
                   'staging.')
      return _BuildFailureAnalysisResultCollection(results=[])
    try:
      supported_builds.sort()
      _AsyncProcessFailureAnalysisRequests(supported_builds)
    except Exception:  # pragma: no cover.
      # If we fail to post a task to the task queue, we ignore and wait for next
      # request.
      logging.exception('Failed to add analysis request to task queue: %s',
                        repr(supported_builds))

    return _BuildFailureAnalysisResultCollection(results=results)

  @gae_ts_mon.instrument_endpoint()
  @endpoints.method(_Flake, _FlakeAnalysis, path='flake', name='flake')
  def AnalyzeFlake(self, request):
    """Analyze a flake on Commit Queue. Currently only supports flaky tests."""
    user_email, is_admin = _ValidateOauthUser()

    def CreateFlakeAnalysisRequest(flake):
      analysis_request = FlakeAnalysisRequest.Create(flake.name, flake.is_step,
                                                     flake.bug_id)
      for step in flake.build_steps:
        analysis_request.AddBuildStep(step.master_name, step.builder_name,
                                      step.build_number, step.step_name,
                                      time_util.GetUTCNow())
      return analysis_request

    flake_analysis_request = CreateFlakeAnalysisRequest(request)
    logging.info('Flake report: %s', flake_analysis_request)

    try:
      AsyncProcessFlakeReport(flake_analysis_request, user_email, is_admin)
      queued = True
    except Exception:
      # Ignore the report when fail to queue it for async processing.
      queued = False
      logging.exception('Failed to queue flake report for async processing')

    return _FlakeAnalysis(queued=queued)

  def _GetV2CulpritFromV1(self, v1_suspected_cls):
    """Constructs [findit_result.Culprit] based on [_SuspectedCL]."""
    culprits = []
    for suspected_cl in v1_suspected_cls or []:
      if suspected_cl.analysis_approach != _AnalysisApproach.TRY_JOB:
        # Suspected CL is not included in v2 results for now.

        continue

      culprit = findit_result.Culprit(
          commit=findit_result.GitilesCommit(
              host='chromium.googlesource.com',
              project='chromium/src',
              ref='refs/heads/master',
              id=suspected_cl.revision,
              commit_position=suspected_cl.commit_position))
      culprits.append(culprit)
    return culprits

  def _GetV2ResultFromV1(self, request, v1_results):
    if not v1_results:
      return None

    v2_results = []
    for v1_result in v1_results:
      v2_result = findit_result.BuildFailureAnalysisResponse(
          build_id=request.build_id,
          build_alternative_id=request.build_alternative_id,
          step_name=v1_result.step_name,
          test_name=v1_result.test_name,
          culprits=self._GetV2CulpritFromV1(v1_result.suspected_cls),
          is_finished=v1_result.is_finished,
          is_supported=True,
      )
      v2_results.append(v2_result)
    return v2_results

  def _GetV2AnalysisResultFromV1(self, request):
    """Constructs v2 analysis results based on v1 analysis.

    This is a temporary work around to make sure Findit's analysis results for
    chromium build failures are still available on SoM during v1 to v2
    migration.

    Args:
      request (findit_result.BuildFailureAnalysisRequest)

    Returns:
      [findit_result.BuildFailureAnalysisResponse] for results of a v1 analysis,
      otherwise return None.
    """
    if (request.build_alternative_id and
        request.build_alternative_id.project != 'chromium'):
      return None

    build = None
    if request.build_id:
      build = buildbucket_client.GetV2Build(
          request.build_id,
          fields=FieldMask(
              paths=['id', 'number', 'builder', 'output.properties']))
    elif request.build_alternative_id:
      build = buildbucket_client.GetV2BuildByBuilderAndBuildNumber(
          request.build_alternative_id.project,
          request.build_alternative_id.bucket,
          request.build_alternative_id.builder,
          request.build_alternative_id.number,
          fields=FieldMask(
              paths=['id', 'number', 'builder', 'output.properties']))

    if not build:
      logging.error('Failed to download build when requesting for %s', request)
      return None

    if build.builder.project != 'chromium':
      return None

    properties = json_format.MessageToDict(build.output.properties)
    build_number = build.number
    master_name = properties.get('target_mastername',
                                 properties.get('mastername'))
    if not build_number or not master_name:
      logging.error('Missing master_name or build_number for build %d',
                    build.id)
      return None

    heuristic_analysis = WfAnalysis.Get(master_name, build.builder.builder,
                                        build_number)
    if not heuristic_analysis:
      return None

    results = []
    v1_build_request = _BuildFailure(
        builder_name=build.builder.builder, build_number=build_number)
    self._GenerateResultsForBuild(v1_build_request, heuristic_analysis, results,
                                  None)
    return self._GetV2ResultFromV1(request, results)

  @gae_ts_mon.instrument_endpoint()
  @endpoints.method(
      findit_result.BuildFailureAnalysisRequestCollection,
      findit_result.BuildFailureAnalysisResponseCollection,
      path='lucibuildfailure',
      name='lucibuildfailure')
  def AnalyzeLuciBuildFailures(self, api_input):
    """Returns analysis results for the given build failures in the request.

    This API is a replacement of AnalyzeBuildFailures since that one requires
    buildbot concept. And this API has access to Findit v2 results and can
    potentially get results from v1, while AnalyzeBuildFailures only gets
    results from v1.

    Args:
      api_input (findit_result.BuildFailureAnalysisRequestCollection):
        A list of build failures.

    Returns:
      findit_result.BuildFailureAnalysisResponseCollection:
        A list of analysis results for the given build failures.
    """
    _ValidateOauthUser()

    results = []
    build_count_with_responses = 0
    build_count_with_v1_responses = 0

    for request in api_input.requests:
      build_results = self._GetV2AnalysisResultFromV1(request)
      if build_results:
        build_count_with_v1_responses += 1
        continue

      build_results = findit_v2_api.OnBuildFailureAnalysisResultRequested(
          request)

      if not build_results:
        continue

      build_count_with_responses += 1
      results.extend(build_results)

    logging.info(
        '%d build failure(s), while findit_v2 can provide results for'
        '%d, and findit_v1 can provide results for %d.',
        len(api_input.requests), build_count_with_responses,
        build_count_with_v1_responses)
    return findit_result.BuildFailureAnalysisResponseCollection(
        responses=results)

  def _GetDisabledTestsQuery(self, tags_to_include):
    disabled_tests_query = LuciTest.query(LuciTest.disabled == True)  # pylint: disable=singleton-comparison
    for tag in tags_to_include:
      disabled_tests_query = disabled_tests_query.filter(LuciTest.tags == tag)
    return disabled_tests_query

  def _FilterOutDisabledTestsByExclusiveTags(self, disabled_tests_query,
                                             tags_to_exclude):
    disabled_tests = disabled_tests_query.fetch()
    return [
        test for test in disabled_tests
        if not any(tag in tags_to_exclude for tag in test.tags)
    ]

  def _GetDisabledTestsByTags(self, tags_to_include, tags_to_exclude):
    disabled_tests_query = self._GetDisabledTestsQuery(tags_to_include)
    if not tags_to_exclude:
      return disabled_tests_query.fetch()
    return self._FilterOutDisabledTestsByExclusiveTags(disabled_tests_query,
                                                       tags_to_exclude)

  def _GetDisabledTestCountsForTags(self, tags_to_include, tags_to_exclude):
    disabled_tests_query = self._GetDisabledTestsQuery(tags_to_include)
    if not tags_to_exclude:
      return disabled_tests_query.count()
    return len(
        self._FilterOutDisabledTestsByExclusiveTags(disabled_tests_query,
                                                    tags_to_exclude))

  def _CreateDisabledTestData(self, disabled_tests, request_type):
    tests = []
    for test in disabled_tests:
      test_data = _DisabledTestData(
          luci_project=test.luci_project,
          normalized_step_name=test.normalized_step_name,
          normalized_test_name=test.normalized_test_name,
      )
      if request_type == _DisabledTestRequestType.NAME_ONLY:
        tests.append(test_data)
        continue

      disabled_test_variants = []
      summarized_disabled_test_variants = LuciTest.SummarizeDisabledVariants(
          test.disabled_test_variants)
      for variant in summarized_disabled_test_variants:
        disabled_test_variants.append(
            _DisabledTestVariant(
                variant=[configuration for configuration in variant]))
      test_data.disabled_test_variants = disabled_test_variants
      tests.append(test_data)
    return tests

  @gae_ts_mon.instrument_endpoint()
  @endpoints.method(
      _DisabledTestsRequest,
      _DisabledTestsResponse,
      path='disabledtests',
      name='disabledtests')
  def FilterDisabledTests(self, request):
    """Filters the disabled tests according to the provided filters.

    Currently supports filtering by tags.
      - include_tags: return tests which contain all the tags in include_tags.
      - exlcude_tags: filter out tests which contain any tag in exclude_tags.
      - if no tags are specified, the default will return all disabled tests.

    Args:
      request (_DisabledTestsRequest): Specifies which filters to apply.

    Returns:
      _DisabledTestsResponse: a count of the disabled tests or a list of
        disabled tests that satisfied the filters
    """
    _ValidateOauthUser()

    if request.request_type == _DisabledTestRequestType.COUNT:
      return _DisabledTestsResponse(
          test_count=self._GetDisabledTestCountsForTags(request.include_tags,
                                                        request.exclude_tags))
    tests = self._GetDisabledTestsByTags(request.include_tags,
                                         request.exclude_tags)
    return _DisabledTestsResponse(
        test_data=self._CreateDisabledTestData(tests, request.request_type))

  @gae_ts_mon.instrument_endpoint()
  @endpoints.method(
      _CQFlakesRequest,
      _CQFlakeResponse,
      path='get_cq_flakes',
      name='get_cq_flakes')
  def GetCQFlakes(self, request):
    """Gets flaky tests that are affecting CQ.

    Args:
      request (_CQFlakesRequest): A list of tests (with related info) to check
                                  whether they're flaky.

    Returns:
      A _CQFlakeResponse that contains a list of tests determined as flaky along
      with a list of sample Gerrit changes supporting why they're flaky.
    """
    logging.info('Request: %s', request)
    futures = [
        _GetCQFlakeAsync(request.project, request.bucket, request.builder, t)
        for t in request.tests
    ]
    flakes = [f.get_result() for f in futures if f.get_result()]
    monitoring.OnCqFlakeResponses(True, len(flakes))
    monitoring.OnCqFlakeResponses(False, len(request.tests) - len(flakes))

    response = _CQFlakeResponse(flakes=flakes)
    logging.info('Response: %s', response)
    return response
