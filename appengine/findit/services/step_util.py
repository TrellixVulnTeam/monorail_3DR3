# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for logic about build test steps."""

import hashlib
import inspect
import json
import logging

from go.chromium.org.luci.buildbucket.proto import common_pb2
from google.protobuf.field_mask_pb2 import FieldMask

from common.constants import SUPPORTED_ISOLATED_SCRIPT_TESTS
from common.findit_http_client import FinditHttpClient
from common.waterfall import buildbucket_client
from gae_libs.caches import PickledMemCache
from infra_api_clients import logdog_util
from libs.cache_decorator import Cached
from libs.test_results.blink_web_test_results import BlinkWebTestResults
from model.isolated_target import IsolatedTarget
from services import constants
from services import swarming
from waterfall import build_util
from waterfall import waterfall_config

_HTTP_CLIENT = FinditHttpClient()

# Caches element retrieved from step metadata for a week.
_METADATA_ELEMENT_CACHE_EXPIRE_TIME_SECONDS = 7 * 24 * 60 * 60

# Caches metadata of a step in a specific build for 2 days.
_METADATA_CACHE_EXPIRE_TIME_SECONDS = 2 * 24 * 60 * 60


# TODO(crbug/804617): Modify this function to use new LUCI API when ready.
def _GetCandidateBounds(master_name, builder_name, upper_bound, lower_bound,
                        requested_commit_position):
  """ Bisects the build number range and search for the earliest build whose
      commit position >= requested_commit_position.

  This function is still based on the assumption that build numbers are
  consecutive. But because it asserts all results from GetBuildInfo, so
  the worst case is that it hits assertion error on missing builds and aborts
  analysis, and it should not happen often since the gaps between build
  numbers should be not too many.
  """
  while upper_bound - lower_bound > 1:
    candidate_build_number = (upper_bound - lower_bound) / 2 + lower_bound
    candidate_build = build_util.GetBuildInfo(master_name, builder_name,
                                              candidate_build_number)
    assert candidate_build

    if candidate_build.commit_position == requested_commit_position:
      # Exact match.
      lower_bound = candidate_build_number - 1
      upper_bound = candidate_build_number
    elif candidate_build.commit_position > requested_commit_position:
      # Go left.
      upper_bound = candidate_build_number
    else:
      # Go right.
      lower_bound = candidate_build_number
  return upper_bound, lower_bound


def _GetLowerBoundBuildNumber(
    lower_bound_build_number,
    upper_bound_build_number,
    # The default window is the number of builds
    # Findit will look back for an analysis.
    default_build_number_window_size=500):
  """Determines the lowest bound build number relative to an upper bound.

  Args:
    lower_bound_build_number (int): An optional int to return directly.
    upper_bound_build)number (int): A non-optional int to use as a reference
        point.
    default_build_number_window_size (int): A fallback window to use to
        determine the lower bound.
  """
  if lower_bound_build_number is not None:
    return lower_bound_build_number

  if upper_bound_build_number > default_build_number_window_size:
    return upper_bound_build_number - default_build_number_window_size

  # For new builders, there may not be that many builds yet. This is a temporary
  # workaround and wil be replaced when the isolate index service is ready and
  # this function will no longer be necessary.
  return upper_bound_build_number / 2


def _GetLowerBoundBuild(master_name, builder_name, lower_bound_build_number,
                        upper_bound_build_number, step_name):
  """Gets a valid lower build near build_number."""
  # Search 10 below then 10 above for a valid build.
  return (GetValidBuild(
      master_name, builder_name, lower_bound_build_number, step_name, False,
      min(10, lower_bound_build_number)) or GetValidBuild(
          master_name, builder_name, lower_bound_build_number, step_name, True,
          min(10, upper_bound_build_number - lower_bound_build_number)))


def GetValidBuild(master_name, builder_name, requested_build_number, step_name,
                  search_ascending, maximum_search_distance):
  """Gets a valid bound at or near the requested build number.

    A build is considered valid if it exists, has a commit position, and has a
    swarming task available.

  Args:
    master_name (str): The name of the master to check.
    builder_name (str): The name of the builder to check.
    requested_build_number (int): The build number to get a valid build at or
        near.
    step_name (str): The name of the step.
    search_ascending (bool): Whether to return a build at least as high as the
        requested build number.
    maximum_search_distance (int): The maximum number of builds to check.

  Returns:
    (BuildInfo): A valid BuildInfo at or near requested_build_number, or None if
        not found.
  """
  candidate_build_number = requested_build_number
  increment = 0
  direction = 1 if search_ascending else -1

  while increment <= maximum_search_distance:
    candidate_build_number = requested_build_number + increment * direction

    candidate_build = build_util.GetBuildInfo(master_name, builder_name,
                                              candidate_build_number)
    if (candidate_build and candidate_build.commit_position is not None and
        (candidate_build.result != common_pb2.INFRA_FAILURE or
         swarming.CanFindSwarmingTaskFromBuildForAStep(
             _HTTP_CLIENT, master_name, builder_name, candidate_build_number,
             step_name))):
      return candidate_build

    increment += 1

  logging.warning('Failed to find valid build for %s/%s/%s within %s builds',
                  master_name, builder_name, requested_build_number,
                  maximum_search_distance)
  return None


def GetBoundingIsolatedTargets(master_name, builder_name, target_name,
                               commit_position):
  """Determines the IsolatedTarget instances surrounding a commit position.

  Args:
    master_name (str): The name of the master to search by.
    builder_name (str): The name of the builder to search by.
    target_name (str): The name of the target to search by, e.g.
        'browser_tests'.
    commit_position (int): The desired commit position to find neighboring
        IsolatedTargets.

  Returns:
    (IsolatedTarget, IsolatedTarget): The lower and upper bound IsolatedTargets.
  """
  upper_bound_targets = (
      IsolatedTarget.FindIsolateAtOrAfterCommitPositionByMaster(
          master_name, builder_name, constants.GITILES_HOST,
          constants.GITILES_PROJECT, constants.GITILES_REF, target_name,
          commit_position))
  lower_bound_targets = (
      IsolatedTarget.FindIsolateBeforeCommitPositionByMaster(
          master_name, builder_name, constants.GITILES_HOST,
          constants.GITILES_PROJECT, constants.GITILES_REF, target_name,
          commit_position))

  assert upper_bound_targets, ((
      'Unable to detect isolated targets at for {}/{} with minimum commit '
      'position {}').format(master_name, builder_name, commit_position))

  assert lower_bound_targets, ((
      'Unable to detect isolated targets at for {}/{} below commit position'
      ' {}').format(master_name, builder_name, commit_position))

  return lower_bound_targets[0], upper_bound_targets[0]


# TODO(crbug/804617): Modify this function to use new LUCI API when ready.
def GetValidBoundingBuildsForStep(
    master_name, builder_name, step_name, lower_bound_build_number,
    upper_bound_build_number, requested_commit_position):
  """Finds the two builds immediately before and after a commit position.

  TODO (lijeffrey): use case in regression_range_analysis_pipeline.py is not
  verified to be supported yet because that feature is not fully supported.

  The builds should also have useful artifacts for the step. Meaning:
  - The build completed without exception, or
  - The build completed the step without exception but exceptioned out later.

  Args:
    master_name (str): The name of the master.
    builder_name (str): The name of the builder.
    step_name (str): The name of the step.
    lower_bound_build_number (int): The earliest build number to search.
    upper_bound_build_number (int): The latest build number to search.
    requested_commit_position (int): The specified commit_position to find the
        bounding build numbers.

  Returns:
    (BuildInfo, Buildinfo): The two nearest builds that bound the requested
        commit position, with the first being earlier of the two. For example,
        if build_1 has commit position 100, build_2 has commit position 110,
        and 105 is requested, returns (build_1, build_2). Returns None for
        either or both of the builds if they cannot be determined. If the
        requested commit is before the lower bound, returns (None, BuildInfo).
        If the requested commit is after the upper bound, returns
        (BuildInfo, None). The calling code should check for the returned builds
        and decide what to do accordingly.
        If a given commit position is included in the blame list of either
        boundary build, that boundary build is returned as both the lower and
        upper bound build.
  """
  logging.debug(
      'GetBoundingBuildsForStep being called for %s/%s/%s with build '
      'number bounds (%d, %d) at commit position %d', master_name, builder_name,
      step_name, lower_bound_build_number or -1, upper_bound_build_number or -1,
      requested_commit_position)

  assert upper_bound_build_number is not None, 'upper_bound can\'t be None'

  latest_build_info = build_util.GetBuildInfo(master_name, builder_name,
                                              upper_bound_build_number)
  logging.debug('latest_build_info: %r', latest_build_info)

  assert latest_build_info, 'Couldn\'t find build info for %s/%s/%s' % (
      master_name, builder_name, upper_bound_build_number)
  assert latest_build_info.commit_position is not None

  lower_bound_build_number = _GetLowerBoundBuildNumber(
      lower_bound_build_number, upper_bound_build_number)
  logging.info('Found lower_bound_build_number to be %d.',
               lower_bound_build_number)

  earliest_build_info = _GetLowerBoundBuild(master_name, builder_name,
                                            lower_bound_build_number,
                                            upper_bound_build_number, step_name)

  logging.debug('earliest_build_info: %r', earliest_build_info)
  assert earliest_build_info, 'Couldn\'t find build info for %s/%s/%s' % (
      master_name, builder_name, lower_bound_build_number)
  assert earliest_build_info.commit_position is not None
  assert (latest_build_info.commit_position >=
          earliest_build_info.commit_position)

  if requested_commit_position <= earliest_build_info.commit_position:
    if not swarming.CanFindSwarmingTaskFromBuildForAStep(
        _HTTP_CLIENT, master_name, builder_name, lower_bound_build_number,
        step_name):
      # TODO(crbug.com/831828): Support newly added test steps for this case.
      # Cannot find valid artifact in earliest_build for the step.
      return None, None
    if requested_commit_position == earliest_build_info.commit_position:
      return earliest_build_info, earliest_build_info
    else:
      return None, earliest_build_info

  if requested_commit_position >= latest_build_info.commit_position:
    if not swarming.CanFindSwarmingTaskFromBuildForAStep(
        _HTTP_CLIENT, master_name, builder_name, upper_bound_build_number,
        step_name):
      # Cannot find valid artifact in latest_build for the step.
      return None, None
    if latest_build_info.commit_position == requested_commit_position:
      return latest_build_info, latest_build_info
    else:
      return latest_build_info, None

  # Gets candidata builds.
  upper_bound, lower_bound = _GetCandidateBounds(
      master_name, builder_name, upper_bound_build_number,
      lower_bound_build_number, requested_commit_position)

  # Get valid builds at or near the candidate build bounds.
  lower_bound_build = GetValidBuild(master_name, builder_name, lower_bound,
                                    step_name, False,
                                    lower_bound - lower_bound_build_number)

  upper_bound_build = GetValidBuild(master_name, builder_name, upper_bound,
                                    step_name, True,
                                    upper_bound_build_number - upper_bound)

  return lower_bound_build, upper_bound_build


def IsStepSupportedByFindit(test_result_object, step_name, master_name):
  """Checks if a test step is currently supported by Findit.

  Currently Findit supports all gtest test steps;
  for isolated-script-tests, Findit only supports blink_web_tests.

  * If there isn't a parser for the test_result of the step, it's not supported;
  * If the step is an isolated-script-test step but not blink_web_tests,
    it's not supported.
  * If the step is set to unsupported in config, it's not supported.
  """
  if not test_result_object:
    return False

  if not waterfall_config.StepIsSupportedForMaster(step_name, master_name):
    return False

  # TODO(crbug/836317): remove the special check for step_name when Findit
  # supports all isolated_script_tests.
  if (isinstance(test_result_object, BlinkWebTestResults) and
      step_name not in SUPPORTED_ISOLATED_SCRIPT_TESTS):
    return False
  return True


def _ParseStepLogIfAppropriate(data, log_name):
  """PConditionally parses the contents of data, based on the log type."""
  if not data:
    return None

  if log_name.lower() == 'json.output[ninja_info]':
    # Check if data is malformatted.
    try:
      json.loads(data)
    except ValueError:
      logging.error('json.output[ninja_info] is malformatted')
      return None

  if log_name.lower() not in ['stdout', 'json.output[ninja_info]']:
    try:
      return json.loads(data) if data else None
    except ValueError:
      logging.error(
          'Failed to json load data for %s. Data is: %s.' % (log_name, data))
      return None

  return data


def _GetStepLogViewUrl(build, full_step_name, log_name, partial_match=False):
  """Gets view url of the requested log.

  Args:
    build (buildbucket_proto.build_pb2.Build proto): Information about a build.
    full_step_name (str): Full name of the step.
    log_name (str): Type of the log.
    partial_match (bool): If the step_name is not found among the steps in the
      builder, allow the function to retrieve the step log for a step whose name
      contains step_name as a prefix.

  Returns:
    (str): view_url of the requested log.
  """
  for step in build.steps or []:
    if step.name == full_step_name:
      for log in step.logs or []:
        if log.name.lower() == log_name:
          return log.view_url

  if partial_match:
    for step in build.steps or []:
      if step.name.startswith(full_step_name):
        for log in step.logs or []:
          if log.name.lower() == log_name:
            return log.view_url

  return None


def GetStepLogFromBuildObject(build,
                              full_step_name,
                              http_client,
                              log_name='stdout',
                              partial_match=False):
  """Returns specific log of the specified step from build_pb2.Build object.

  Args:
    build (build_pb2.Build): See
    https://cs.chromium.org/chromium/infra/go/src/go.chromium.org/luci/buildbucket/proto/build.proto # pylint:disable=line-too-long
    full_step_name (str): Full name of the step.
    http_client (FinditHttpClient): Http_client to make the request.
    log_name (str): Name of the log.
    partial_match (bool): If the step_name is not found among the steps in the
      builder, allow the function to retrieve the step log for a step whose name
      contains step_name as a prefix.

  Returns:
    Requested Log after processing based on the log_name.
    - return the log as it is if the log name is 'stdout' or
      'json.output[ninja_info]'
    - return the deserialized log otherwise.
  """
  log_view_url = _GetStepLogViewUrl(build, full_step_name, log_name,
                                    partial_match)
  if not log_view_url:
    logging.exception('Didn\'t retrieve log_view_url at build: %s for %s of %s.'
                      % (build.id, log_name, full_step_name))
    return None

  data = logdog_util.GetLogFromViewUrl(log_view_url, http_client)

  return _ParseStepLogIfAppropriate(data, log_name)


def GetStepLogForLuciBuild(build_id,
                           full_step_name,
                           http_client,
                           log_name='stdout',
                           partial_match=False):
  """Returns specific log of the specified step in a LUCI build.

  Args:
    build_id(str): Buildbucket id.
    full_step_name(str): Full name of the step.
    http_client(FinditHttpClient): Http_client to make the request.
    log_name(str): Name of the log.

  Returns:
    Requested Log after processing based on the log_name.
    - return the log as it is if the log name is 'stdout' or
      'json.output[ninja_info]'
    - return the deserialized log otherwise.
  """

  build = buildbucket_client.GetV2Build(build_id,
                                        FieldMask(paths=['id', 'steps']))
  if not build:
    logging.exception('Error retrieving buildbucket build id: %s' % build_id)
    return None

  return GetStepLogFromBuildObject(build, full_step_name, http_client, log_name,
                                   partial_match)


def _CanonicalStepNameKeyGenerator(func, args, kwargs, namespace=None):
  """Generates a key to a cached canonical step name.

  Using the step_name as key, assuming it's practically not possible for 2 steps
  with different canonical_step_names have exactly the same step_name.

  Args:
    func (function): An arbitrary function.
    args (list): Positional arguments passed to ``func``.
    kwargs (dict): Keyword arguments passed to ``func``.
    namespace (str): A prefix to the key for the cache.

  Returns:
    A string to represent a call to the given function with the given arguments.
  """
  params = inspect.getcallargs(func, *args, **kwargs)
  step_name = params.get('step_name')
  assert step_name, 'No step name provided when requesting step_metadata.'
  encoded_params = hashlib.md5(step_name).hexdigest()
  return '%s-%s' % (namespace, encoded_params)


def _PlatformKeyGenerator(func, args, kwargs, namespace=None):
  """Generates a key to a cached platform.

  Using the step_name and builder_name as key.

  Args:
    func (function): An arbitrary function.
    args (list): Positional arguments passed to ``func``.
    kwargs (dict): Keyword arguments passed to ``func``.
    namespace (str): A prefix to the key for the cache.

  Returns:
    A string to represent a call to the given function with the given arguments.
  """
  params = inspect.getcallargs(func, *args, **kwargs)
  builder_name = params.get('builder_name')
  assert builder_name, 'No builder name provided when platform.'
  step_name = params.get('step_name')
  assert step_name, 'No step name provided when platform.'
  encoded_params = hashlib.md5('%s|%s' % (builder_name, step_name)).hexdigest()
  return '%s-%s' % (namespace, encoded_params)


def GetWaterfallBuildStepLog(master_name,
                             builder_name,
                             build_number,
                             full_step_name,
                             http_client,
                             log_name='stdout'):
  """Returns specific log of the specified step."""

  build = build_util.DownloadBuildData(master_name, builder_name, build_number)

  if build.build_id:
    # This build should be a LUCI build.
    return GetStepLogForLuciBuild(build.build_id, full_step_name, http_client,
                                  log_name)

  # This build is a buildbot build, fall back to the legacy way of getting log.
  data = logdog_util.GetStepLogLegacy(build.log_location, full_step_name,
                                      log_name, http_client)

  return _ParseStepLogIfAppropriate(data, log_name)


# TODO(crbug.com/987718): Remove after Findit v2 migration and buildbot info
# is deprecated.
@Cached(
    PickledMemCache(),
    namespace='step_metadata',
    expire_time=_METADATA_CACHE_EXPIRE_TIME_SECONDS,
    result_validator=lambda step_metadata: isinstance(step_metadata, dict))
def LegacyGetStepMetadata(master_name, builder_name, build_number, step_name):
  return GetWaterfallBuildStepLog(master_name,
                                  builder_name, build_number, step_name,
                                  FinditHttpClient(), 'step_metadata')


@Cached(
    PickledMemCache(),
    namespace='step_metadata',
    expire_time=_METADATA_CACHE_EXPIRE_TIME_SECONDS,
    result_validator=lambda step_metadata: isinstance(step_metadata, dict))
def GetStepMetadata(build_id, step_name, partial_match=False):
  return GetStepLogForLuciBuild(build_id, step_name, FinditHttpClient(),
                                'step_metadata', partial_match)


# TODO(crbug.com/987718): Remove after Findit v2 migration and buildbot info
# is deprecated.
@Cached(
    PickledMemCache(),
    namespace='step_metadata',
    expire_time=_METADATA_ELEMENT_CACHE_EXPIRE_TIME_SECONDS,
    key_generator=_CanonicalStepNameKeyGenerator)
def LegacyGetCanonicalStepName(master_name, builder_name, build_number,
                               step_name):
  step_metadata = LegacyGetStepMetadata(master_name, builder_name, build_number,
                                        step_name)
  return step_metadata.get(
      'canonical_step_name') if step_metadata else step_name.split()[0]


@Cached(
    PickledMemCache(),
    namespace='step_metadata',
    expire_time=_METADATA_ELEMENT_CACHE_EXPIRE_TIME_SECONDS,
    key_generator=_CanonicalStepNameKeyGenerator)
def GetCanonicalStepName(build_id, step_name, partial_match=False):
  """ Returns the canonical_step_name in the step_metadata.

  Args:
    build_id: Build id of the build.
    step_name: The original step name to get canonical_step_name for, and the
      step name may contain hardware information and 'with(out) patch' suffixes.
    partial_match: If the step_name is not found among the steps in the builder,
      allow the function to retrieve step metadata from a step whose name
      contains step_name as a prefix.

  Returns:
    The canonical_step_name if it exists, otherwise, step_name.split()[0].
  """
  step_metadata = GetStepMetadata(build_id, step_name, partial_match)
  return step_metadata.get(
      'canonical_step_name') if step_metadata else step_name.split()[0]


# TODO(crbug.com/987718): Remove after Findit v2 migration and buildbot info
# is deprecated.
def LegacyGetIsolateTargetName(master_name, builder_name, build_number,
                               step_name):
  """ Returns the isolate_target_name in the step_metadata.

  Args:
    master_name: Master name of the build.
    builder_name: Builder name of the build.
    build_number: Build number of the build.
    step_name: The original step name to get isolate_target_name for, and the
      step name may contain hardware information and 'with(out) patch' suffixes.

  Returns:
    The isolate_target_name if it exists, otherwise, None.
  """
  step_metadata = LegacyGetStepMetadata(master_name, builder_name, build_number,
                                        step_name)
  return step_metadata.get('isolate_target_name') if step_metadata else None


@Cached(
    PickledMemCache(),
    namespace='isolate_target',
    expire_time=_METADATA_ELEMENT_CACHE_EXPIRE_TIME_SECONDS,
    key_generator=_CanonicalStepNameKeyGenerator)
def GetIsolateTargetName(build_id, step_name, partial_match=False):
  """ Returns the isolate_target_name in the step_metadata.

  Args:
    build_id: Build id of the build.
    step_name: The original step name to get isolate_target_name for, and the
      step name may contain hardware information and 'with(out) patch' suffixes.
    partial_match: If the step_name is not found among the steps in the builder,
      allow the function to retrieve step metadata from a step whose name
      contains step_name as a prefix.

  Returns:
    The isolate_target_name if it exists, otherwise, None.
  """
  step_metadata = GetStepMetadata(build_id, step_name, partial_match)
  return step_metadata.get('isolate_target_name') if step_metadata else None


@Cached(
    PickledMemCache(),
    namespace='step_os',
    expire_time=_METADATA_ELEMENT_CACHE_EXPIRE_TIME_SECONDS,
    key_generator=_PlatformKeyGenerator)
def GetOS(build_id, builder_name, step_name, partial_match=False):
  # pylint:disable=unused-argument
  """Returns the operating system in the step_metadata.

  Args:
    build_id (int): Build id of the build.
    builder_name (str): Builder name of the build.
    step_name (str): The original step name used to get the step metadata.

  Returns:
    The operating system if it exists, otherwise, None.
  """
  step_metadata = GetStepMetadata(build_id, step_name, partial_match)
  return step_metadata.get('dimensions',
                           {}).get('os') if step_metadata else None


def StepIsSupportedForMaster(master_name, builder_name, build_number,
                             step_name):
  if step_name == 'compile':
    canonical_step_name = step_name
  else:
    canonical_step_name = LegacyGetCanonicalStepName(master_name, builder_name,
                                                     build_number, step_name)
  return waterfall_config.StepIsSupportedForMaster(canonical_step_name,
                                                   master_name)


def GetStepStartAndEndTime(build, full_step_name):
  """Gets a step's start_time and end_time from Build.

  Returns:
    (start_time, end_time)
  """
  for step in build.steps or []:
    if step.name == full_step_name:
      return step.start_time.ToDatetime(), step.end_time.ToDatetime()

  return None, None
