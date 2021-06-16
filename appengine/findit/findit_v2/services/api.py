# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This encapsulate the main Findit APIs for external requests."""

import logging

from common.constants import DEFAULT_SERVICE_ACCOUNT

from findit_v2.model.luci_build import LuciFailedBuild
from findit_v2.services import build_util
from findit_v2.services import projects
from findit_v2.services.analysis.compile_failure import compile_analysis
from findit_v2.services.analysis.test_failure import test_analysis
from findit_v2.services.detection import api as detection_api
from findit_v2.services.failure_type import StepTypeEnum


def OnSupportedBuildCompletion(project, bucket, builder_name, build_id,
                               build_result):
  """Processes a completed build from a builder Findit is supporting.

  Args:
    project (str): Luci project of the build.
    build_id (int): Id of the build.

  Returns:
    False if it is unsupported or skipped; otherwise True.
  """
  if build_result != 'FAILURE':
    # Skip builds that didn't fail.
    logging.debug('Build %s/%s/%s/%s is not a failure', project, bucket,
                  builder_name, build_id)
    return False

  build, context = build_util.GetBuildAndContextForAnalysis(project, build_id)
  if not build:
    return False

  detection_api.OnBuildFailure(context, build)
  return True


def OnRerunBuildCompletion(project, build_id):
  """Processes a completed rerun builds.

  Args:
    project (str): Luci project of the build.
    build_id (int): Id of the build.

  Returns:
    False if it is unsupported or skipped; otherwise True.
  """
  rerun_build, context = build_util.GetBuildAndContextForAnalysis(
      project, build_id)
  if not rerun_build:
    return False

  if rerun_build.created_by != 'user:{}'.format(DEFAULT_SERVICE_ACCOUNT):
    logging.info('Build %d is not triggered by Findit.', rerun_build.id)
    return False

  return detection_api.OnRerunBuildCompletion(context, rerun_build)


def OnBuildCompletion(project, bucket, builder_name, build_id, build_result):
  """Processes the completed build.

  Args:
    project (str): Luci project of the build.
    bucket (str): Luci bucket of the build.
    builder_name (str): Luci builder name of the build.
    build_id (int): Id of the build.
    build_result (str): Status of the build. E.g. SUCCESS, FAILURE, etc.

  Returns:
    False if it is unsupported or skipped; otherwise True.
  """
  # Skip builders that are not in the whitelist of a supported project/bucket.
  builder_type = projects.GetBuilderType(project, bucket, builder_name)

  if builder_type == projects.BuilderTypeEnum.SUPPORTED:
    return OnSupportedBuildCompletion(project, bucket, builder_name, build_id,
                                      build_result)

  if builder_type == projects.BuilderTypeEnum.RERUN:
    return OnRerunBuildCompletion(project, build_id)

  logging.info('Unsupported build %s/%s/%s/%s.', project, bucket, builder_name,
               build_id)
  return False


def OnBuildFailureAnalysisResultRequested(request):
  """Returns the findings of an analysis for a failed build.

  Since Findit v2 only supports compile failure on cros builds, this api will
  simply respond an empty response on other failures. This is to prevent Findit
  spending too many pixels to tell users many failures are not supported.

  Args:
    request(findit_result.BuildFailureAnalysisRequest): request for a build
      failure.

  Returns:
    (findit_result.BuildFailureAnalysisResponseCollection): Analysis results
      for the requested build.
  """
  build_id = request.build_id
  build_alternative_id = request.build_alternative_id
  if build_id:
    build_entity = LuciFailedBuild.get_by_id(build_id)
    if not build_entity:
      logging.debug('No LuciFailedBuild entity for build %d.', request.build_id)
      return []
  else:
    build_entity = LuciFailedBuild.GetBuildByNumber(
        build_alternative_id.project, build_alternative_id.bucket,
        build_alternative_id.builder, build_alternative_id.number)
    if not build_entity:
      logging.debug('No LuciFailedBuild entity for build %s/%s/%s/%d.',
                    build_alternative_id.project, build_alternative_id.bucket,
                    build_alternative_id.builder, build_alternative_id.number)
      return []

  if build_entity.build_failure_type == StepTypeEnum.COMPILE:
    return compile_analysis.OnCompileFailureAnalysisResultRequested(
        request, build_entity)
  if build_entity.build_failure_type == StepTypeEnum.TEST:
    return test_analysis.OnTestFailureAnalysisResultRequested(
        request, build_entity)

  logging.debug(
      'Findit v2 only supports compile or test failure analysis, '
      'so no results for %d with %s failures.', build_id,
      build_entity.build_failure_type)
  return []
