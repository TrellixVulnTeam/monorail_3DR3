# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the APIs that each type of failure analysis must implement. """

from collections import defaultdict
import logging

from go.chromium.org.luci.buildbucket.proto import common_pb2
from google.appengine.ext import ndb
from google.protobuf.field_mask_pb2 import FieldMask

from common.waterfall import buildbucket_client
from findit_v2.model import luci_build
from findit_v2.model.culprit_action import CulpritAction
from findit_v2.model.gitiles_commit import GitilesCommit
from findit_v2.model.gitiles_commit import Culprit
from findit_v2.model.gitiles_commit import Suspect
from findit_v2.model.messages.findit_result import Culprit as CulpritPb
from findit_v2.model.messages.findit_result import (GitilesCommit as
                                                    GitilesCommitPb)
from findit_v2.services import projects
from findit_v2.services import constants
from libs import analysis_status
from libs import time_util
from services import gerrit
from services import git

# Max number a rerun build on one commit can be tried.
_MAX_RERUN_BUILDS_TRIES = 3

# Build statuses that indicate a build is usable since it's
# 1. just created,
# 2. still running,
# 3. ended with deterministic results.
_EXPECTED_BUILD_STATUSES = [
    common_pb2.SCHEDULED,
    common_pb2.STARTED,
    common_pb2.FAILURE,
    common_pb2.SUCCESS,
]


def _UpdateToEarlierBuild(failure_info, build2):
  """Compares builds by their ids.

  Build ids are monotonically decreasing, so the earlier build has a greater id.
  """
  if (not failure_info.get('last_passed_build') or
      (build2 and failure_info['last_passed_build']['id'] < build2['id'])):
    failure_info['last_passed_build'] = build2



class AnalysisAPI(object):

  @property
  def step_type(self):
    """Type of the steps that are being analyzed."""
    raise NotImplementedError

  def _GetMergedFailureKey(self, failure_entities, referred_build_id,
                           step_ui_name, atomic_failure):
    """Gets the key to the entity that a failure should merge into.

    Args:
      failure_entities (dict of list of failure entities): Mapping ids of
        referred builds to failure entities in those builds that the current
        failure could potentially merge into. This dict could potentially be
        modified, if the referred build was not included before.
      referred_build_id (int): Id of current failure's first failed build or
        failure group.
      step_ui_name (str): Step name of current failure.
      atomic_failure (frozenset): Atomic failure.
    """
    raise NotImplementedError

  def _GetFailuresInBuild(self, project_api, build, failed_steps):
    """Gets detailed failure information from a build.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      build (buildbucket build.proto): ALL info about the build.
      failed_steps (list of step proto): Info about failed steps in the build.

    Returns:
      (dict): Information about failures in the build.
      {
        'step_name': {
          'failures': {
            atomic_failure: {
              'first_failed_build': {
                'id': 8765432109,
                'number': 123,
                'commit_id': 654321
              },
              'last_passed_build': None,
              'properties': {
                # Arbitrary information about the failure if exists.
              }
            },
          'first_failed_build': {
            'id': 8765432109,
            'number': 123,
            'commit_id': 654321
          },
          'last_passed_build': None,
          'properties': {
            # Arbitrary information about the failure if exists.
          }
        },
      }
    """
    raise NotImplementedError

  def _GetFailuresWithMatchingFailureGroups(self, project_api, context, build,
                                            first_failures_in_current_build):
    """Gets reusable failure groups for given failure(s).

    Args:
      project_api (ProjectAPI): API for project specific logic.
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build.
      first_failures_in_current_build (dict): A dict for failures that happened
        the first time in current build.
      {
        'failures': {
          'step': {
            'atomic_failures': [
              # E.g. frozenset(['target4']) for compile failures if has target
              # level failure info. It's possible to be a multi-element set.
              # E.g. frozenset(['test1']) for test failures if has test
              # level failure info, it must be a single element set.
            ],
            'last_passed_build': {
              'id': 8765432109,
              'number': 122,
              'commit_id': 'git_sha1'
            },
          },
        },
        'last_passed_build': {
          # In this build all the failures that happened in the build being
          # analyzed passed.
          'id': 8765432108,
          'number': 121,
          'commit_id': 'git_sha0'
        }
      }
    """
    raise NotImplementedError

  def _CreateFailure(self, failed_build_key, step_ui_name,
                     first_failed_build_id, last_passed_build_id,
                     merged_failure_key, atomic_failure, properties):
    """Creates and returns an AtomicFailure entity."""
    raise NotImplementedError

  def GetFailureEntitiesForABuild(self, build):
    """Returns all AtomicFailure entities of the build."""
    raise NotImplementedError

  def _CreateFailureGroup(self, context, build, failure_keys,
                          last_passed_gitiles_id, last_passed_commit_position,
                          first_failed_commit_position):
    """Creates and returns a failure group for the failures."""
    raise NotImplementedError

  def _CreateFailureAnalysis(
      self, luci_project, context, build, last_passed_gitiles_id,
      last_passed_commit_position, first_failed_commit_position,
      rerun_builder_id, failure_keys):
    """Creates and returns an analysis entities for the  analyzed failures."""
    raise NotImplementedError

  def _CreateRerunBuild(self, rerun_builder, new_build, rerun_commit,
                        analysis_key):
    """Creates and returns a rerun build entity."""
    raise NotImplementedError

  def _GetFailuresInAnalysis(self, analysis):
    """Gets AtomicFailure entities that are being analyzed in an analysis."""
    raise NotImplementedError

  def _FetchRerunBuildsOfAnalysis(self, analysis):
    """Gets all existing rerun builds for an analysis."""
    raise NotImplementedError

  def _GetFailureAnalysis(self, analyzed_build_id):
    raise NotImplementedError

  def _FailureHappenedInRerunBuild(self, failure_entity,
                                   failures_in_rerun_build):
    """Checks if the same failure has also happened in a rerun build."""
    if failure_entity.GetFailureIdentifier():
      return failure_entity.GetFailureIdentifier().issubset(
          set(failures_in_rerun_build))

    # Both analyzed build and rerun build have no atomic level failure info, so
    # the same failed step will be used to decide that the same failure happens
    # again.
    return not bool(failures_in_rerun_build)

  def _GetFailuresToRerun(self, failure_entities):
    """Gets atomic failures in a dict format.

    Returns:
      {
        'compile': ['target1.o', ...], # for compile failures
        'step': ['test1', ...], # for test failures
        ...
      }
    """
    raise NotImplementedError

  def _GetExistingRerunBuild(self, analysis_key, rerun_commit):
    """Gets existing rerun build for an analysis on the commit."""
    raise NotImplementedError

  def _GetRerunBuildTags(self, analyzed_build_id):
    """Gets tags for rerun builds.

    Currently there are 2 tags:
    - purpose: indicates the rerun build is triggered by Findit for an analysis,
    - analyzed_build_id: links back the rerun build to the analysis.
    """
    raise NotImplementedError

  def _GetRerunDimensions(self, project_api, analyzed_build_id):
    """Gets project specific override dimensions for rerun jobs."""
    # By default, all types of analyses derive override dimensions (if any) the
    # same way, varying only by project.
    return project_api.GetRerunDimensions(analyzed_build_id)

  def _GetRerunBuildInputProperties(self, project_api, rerun_failures,
                                    analyzed_build_id):
    """Gets project specific input properties to rerun failures."""
    raise NotImplementedError

  def _GetFailureGroupByContext(self, context):
    """Gets the failure group of a build.

    There should be at most one group for each build.
    """
    raise NotImplementedError

  def GetSkippedFailures(self, project_api, failures):
    """Gets failures that other failures depend on but haven't been analyzed."""
    # pylint:disable=unused-argument
    return {}

  def _ClearSkipFlag(self, project_api, failure_entities):
    """For failures that were skipped on purpose then require to be analyzed,
      updates them to be picked up by an analysis.

    So far this is a special case for CrOS: CrOS can tell Findit to skip
    analyzing a failed build if there are too many failures. Those failures
    will have a flag in properties indicates that they don't need analysis.
    But a following build with failures that need analysis might be merged into
    some of the skipped failures, if so those particular failures need to update
    to be analyzed.
    """
    # pylint:disable=unused-argument
    return

  def GetSuspectedCulprits(self, project_api, context, build,
                           first_failures_in_current_build):
    """Finds suspected CLs in the build's changelog by analyzing failure logs.

    Projects can use this method to perform analysis of the failure in a
    static manner, i.e. without actually compiling or executing code. e.g by
    comparing the paths affected by the changes in the changelog against the
    output generated by the failed steps in the build.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build.
      first_failures_in_current_build (dict): A dict for failures that happened
        the first time in current build.
        {
          'failures': {
            'step': {
              'atomic_failures': ['test1', 'test2', ...],
              'last_passed_build': {
                'id': 8765432109,
                'number': 122,
                'commit_id': 'git_sha1'
              },
            },
          },
          'last_passed_build': {
            # In this build all the failures that happened in the build being
            # analyzed passed.
            'id': 8765432108,
            'number': 121,
            'commit_id': 'git_sha0'
          }
        }
      }
    Returns:
      A map from (step, target/test) name to a list of suspected commits in the
      following format:
      NB: Repo details (host, project, ref) are assumed from the context.
      {
        ('compile', frozenset(['base_unittests'])): [
          {
            'revision': 'abcdef',
            'commit_position': 213021,
            'hints': {
              'add a/b/x.cc': 5,
              'delete a/b/y.cc': 5,
              'modify c/z.cc': 1,
            }
          }
        ]
      }
    """
    raise NotImplementedError()

  def OnCulpritFound(self, context, analyzed_build_id, culprit_commit):
    """Subclasses may override this to take action when a culprit is identified.

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      analyzed_build_id: Buildbucket id of the continuous build being analyzed.
      culprit: The Culprit entity for the change identified as causing the
          failures.

    Returns:
      The CulpritAction entity describing the action taken, None if no action
      was performed.
    """
    # pylint:disable=unused-argument
    return None

  def _GetFailureKeysToAnalyze(self, failure_entities, project_api):
    """Gets failures that'll actually be analyzed in the analysis.

    Placeholder for project specific logic, for example in-build failure
    grouping for ChromeOS test failure analysis.
    """
    return [f.key for f in failure_entities if
            project_api.FailureShouldBeAnalyzed(f)]

  def SaveFailures(self, context, build, detailed_failures):
    """Saves the failed build and failures in data store.

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build.
      detailed_failures (dict): A dict of detailed failures.
       {
        'step_name': {
          'failures': {
            atomic_failure: {
              'first_failed_build': {
                'id': 8765432109,
                'number': 123,
                'commit_id': 654321
              },
              'last_passed_build': None,
              'properties': {}
            },
            ...
          },
          'first_failed_build': {
            'id': 8765432109,
            'number': 123,
            'commit_id': 654321
          },
          'last_passed_build': None
        },
      }
    """
    build_entity = luci_build.SaveFailedBuild(context, build, self.step_type)

    failed_build_key = build_entity.key
    failure_entities = []

    first_failures = {}
    for step_ui_name, step_info in detailed_failures.iteritems():
      # If there's no atomic level info, uses step_level info to create failure
      # entity.
      failures = step_info['failures'] or {frozenset([]): step_info}

      for atomic_failure, failure in failures.iteritems():
        first_failed_build_id = failure.get('first_failed_build', {}).get('id')
        merged_failure_key = self._GetMergedFailureKey(
            first_failures, first_failed_build_id, step_ui_name, atomic_failure)

        new_entity = self._CreateFailure(
            failed_build_key=failed_build_key,
            step_ui_name=step_ui_name,
            first_failed_build_id=first_failed_build_id,
            last_passed_build_id=(failure.get('last_passed_build') or
                                  {}).get('id'),
            merged_failure_key=merged_failure_key,
            atomic_failure=atomic_failure,
            properties=failure.get('properties'))
        failure_entities.append(new_entity)

    ndb.put_multi(failure_entities)

  def _UpdateFailuresWithPreviousBuildInfo(self, step_info, prev_build_info):
    """Updates failures in a step with the previous build's info."""
    # Updates step level last pass build id.
    step_info[
        'last_passed_build'] = step_info['last_passed_build'] or prev_build_info

    # Updates last pass build id for atomic failures.
    for failure in step_info['failures'].itervalues():
      failure[
          'last_passed_build'] = failure['last_passed_build'] or prev_build_info

  def _GetPreviousSameTypeFailuresInPreviousBuild(self, project_api, prev_build,
                                                  detailed_failures):
    """Gets failures in the previous build.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      prev_build (buildbucket build.proto): SIMPLE info about the build.
      detailed_failures (dict): A dict of detailed failures.
    """
    detailed_prev_build = buildbucket_client.GetV2Build(
        prev_build.id, fields=FieldMask(paths=['*']))

    # Looks for steps in previous build. Here only the failed steps of requested
    # type in current build are relevant.
    prev_steps = {
        s.name: s
        for s in detailed_prev_build.steps
        if detailed_failures.get(s.name)
    }
    # Looks for steps that failed in both current build and this build.
    prev_failed_steps = [
        step for step in prev_steps.itervalues()
        if step.status == common_pb2.FAILURE
    ]

    prev_failures = self._GetFailuresInBuild(
        project_api, detailed_prev_build,
        prev_failed_steps) if prev_failed_steps else {}
    return prev_steps, prev_failures

  def UpdateFailuresWithFirstFailureInfo(self, context, build,
                                         detailed_failures):
    """Updates detailed_failures with first failure info.

    For failures occurred in the build, traverses through previous builds on
    the same builder backwards to look for when each of them happened the first
    time (if the failures happened continuously).

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build that is
        currently being analyzed.
      detailed_failures (dict): A dict of detailed failures.
        {
          'step_name': {
            'failures': {
              atom_failure: {
                'first_failed_build': {
                  'id': 8765432109,
                  'number': 123,
                  'commit_id': 654321
                },
                'last_passed_build': None,
                'properties': {
                  # Arbitrary information about the failure if exists.
                }
              },
              ...
            },
            'first_failed_build': {
              'id': 8765432109,
              'number': 123,
              'commit_id': 654321
            },
            'last_passed_build': None,
            'properties': {
              # Arbitrary information about the failure if exists.
            },
          },
        }
    """
    luci_project = context.luci_project_name
    project_api = projects.GetProjectAPI(luci_project)

    # Gets previous builds, the builds are sorted by build number in descending
    # order.
    # No steps info in each build considering the response size.
    # Requests to buildbucket for each failed build separately.
    search_builds_response = buildbucket_client.SearchV2BuildsOnBuilder(
        build.builder,
        build_range=(None, build.id),
        page_size=constants.MAX_BUILDS_TO_CHECK)
    previous_builds = search_builds_response.builds

    for prev_build in previous_builds:
      if prev_build.id == build.id:
        # TODO(crbug.com/969124): remove the check when SearchBuilds RPC works
        # as expected.
        continue

      prev_build_info = {
          'id': prev_build.id,
          'number': prev_build.number,
          'commit_id': prev_build.input.gitiles_commit.id,
      }

      if prev_build.status == common_pb2.SUCCESS:
        # Found a passed build, update all failures.
        for step_info in detailed_failures.itervalues():
          self._UpdateFailuresWithPreviousBuildInfo(step_info, prev_build_info)
        return

      prev_steps, prev_failures = (
          self._GetPreviousSameTypeFailuresInPreviousBuild(
              project_api, prev_build, detailed_failures))

      need_go_back = False
      for step_ui_name, step_info in detailed_failures.iteritems():
        if not prev_steps.get(step_ui_name):
          # For some reason the step didn't run in the previous build.
          need_go_back = True
          continue

        if prev_steps.get(step_ui_name) and prev_steps[
            step_ui_name].status == common_pb2.SUCCESS:
          # The step passed in the previous build, update all failures in this
          # step.
          self._UpdateFailuresWithPreviousBuildInfo(step_info, prev_build_info)
          continue

        if not prev_failures.get(step_ui_name):
          # The step didn't pass nor fail, Findit cannot get useful information
          # from it, going back.
          need_go_back = True
          continue

        failures = step_info['failures']
        if not failures:
          # Same step failed, but there's no atomic level failure info.
          if step_info['last_passed_build']:
            # Last pass has been found for this failure, skip the failure.
            continue
          step_info['first_failed_build'] = prev_build_info
          need_go_back = True
          continue

        step_last_passed_found = True
        for atomic_failure_identifier, failure in failures.iteritems():
          if failure['last_passed_build']:
            # Last pass has been found for this failure, skip the failure.
            continue

          if prev_failures[step_ui_name]['failures'].get(
              atomic_failure_identifier):
            # The same failure happened in the previous build, going back.
            failure['first_failed_build'] = prev_build_info
            step_info['first_failed_build'] = prev_build_info
            need_go_back = True
            step_last_passed_found = False
          else:
            # The failure didn't happen in the previous build, first failure
            # found.
            failure['last_passed_build'] = prev_build_info

        if step_last_passed_found:
          step_info['last_passed_build'] = prev_build_info

      if not need_go_back:
        return

  def GetFirstFailuresInCurrentBuild(self, build, detailed_failures):
    """Gets failures that happened the first time in the current build.

    Failures without last_passed_build will not be included even if they failed
    the first time in current build (they have statuses other than SUCCESS or
    FAILURE in all previous builds), because Findit cannot decide the left
    boundary of the regression range.

    If first failures have different last_passed_build, use the earliest one.

    Args:
      build (buildbucket build.proto): ALL info about the build.
      detailed_failures (dict): A dict of detailed failures.
        {
          'step_name': {
            'failures': {
              atom_failure: {
                'first_failed_build': {
                  'id': 8765432109,
                  'number': 123,
                  'commit_id': 654321
                },
                'last_passed_build': None,
                'properties': {
                  # Arbitrary information about the failure if exists.
                }
              },
              ...
            },
            'first_failed_build': {
              'id': 8765432109,
              'number': 123,
              'commit_id': 654321
            },
            'last_passed_build': None,
            'properties': {
              # Arbitrary information about the failure if exists.
            },
          },
        }
    Returns:
      dict: A dict for failures that happened the first time in current build.
      {
        'failures': {
          'step': {
            'atomic_failures': [
              # E.g. frozenset(['target4']) for compile failures
              # E.g. frozenset(['test1']) for test failures
            ],
            'last_passed_build': {
              'id': 8765432109,
              'number': 122,
              'commit_id': 'git_sha1'
            },
          },
        },
        'last_passed_build': {
          # In this build all the failures that happened in the build being
          # analyzed passed.
          'id': 8765432108,
          'number': 121,
          'commit_id': 'git_sha0'
        }
      }
    """
    first_failures_in_current_build = {
        'failures': {},
        'last_passed_build': None
    }
    for step_ui_name, step_info in detailed_failures.iteritems():
      if not step_info[
          'failures'] and step_info['first_failed_build']['id'] != build.id:
        # This step already failed before current build, also there's no atomic
        # level failure info for the step, so just assumes the step in whole is
        # not a first time failure in current build.
        continue

      if step_info['first_failed_build']['id'] == build.id and step_info[
          'last_passed_build']:
        # All failures in this step are first failures and last pass was found.
        first_failures_in_current_build['failures'][step_ui_name] = {
            'atomic_failures': step_info['failures'].keys(),
            'last_passed_build': step_info['last_passed_build'],
        }

        _UpdateToEarlierBuild(first_failures_in_current_build,
                              step_info['last_passed_build'])
        continue

      first_failures_in_step = {
          'atomic_failures': [],
          'last_passed_build': step_info['last_passed_build'],
      }
      for atomic_failure_identifier, failure in step_info['failures'].iteritems(
      ):
        if failure['first_failed_build']['id'] != build.id or not failure[
            'last_passed_build']:
          continue
        first_failures_in_step['atomic_failures'].append(
            atomic_failure_identifier)
        _UpdateToEarlierBuild(first_failures_in_step,
                              failure['last_passed_build'])

      if not first_failures_in_step['atomic_failures']:
        continue
      # Some failures are first time failures in current build.
      first_failures_in_current_build['failures'][
          step_ui_name] = first_failures_in_step

      _UpdateToEarlierBuild(first_failures_in_current_build,
                            first_failures_in_step['last_passed_build'])
    return first_failures_in_current_build

  def _GetFailuresWithoutMatchingFailureGroups(self, current_build_id,
                                               first_failures_in_current_build,
                                               failures_with_existing_group):
    """Regenerates first_failures_in_current_build without any failures with
      existing group.

    Args:
      current_build_id (int): Id of the current build that's being analyzed.
      first_failures_in_current_build (dict): A dict for failures that happened
        the first time in current build.
        {
          'failures': {
            'step name': {
              'atomic_failures': [
                frozenset(['target4']),
                frozenset(['target1', 'target2'])],
              'last_passed_build': {
                'id': 8765432109,
                'number': 122,
                'commit_id': 'git_sha1'
              },
            },
          },
          'last_passed_build': {
            'id': 8765432109,
            'number': 122,
            'commit_id': 'git_sha1'
          }
        }
      failures_with_existing_group (dict): Failures with their failure group id.
        {
          'step name': {
            frozenset(['target4']):  8765432000,
          ]
        }

    Returns:
      failures_without_existing_group (dict): updated version of
        first_failures_in_current_build, no failures with existing group.
    """
    failures_without_existing_group = {
        'failures': {},
        'last_passed_build': None
    }

    # Uses current_build's id as the failure group id for all the failures
    # without existing groups.
    for step_ui_name, step_failure in first_failures_in_current_build[
        'failures'].iteritems():
      step_failures_without_existing_group = []
      for atomic_failure in step_failure['atomic_failures']:
        step_failures_with_group = failures_with_existing_group.get(
            step_ui_name, {})
        if (atomic_failure in step_failures_with_group and
            step_failures_with_group[atomic_failure] != current_build_id):
          # Failure is grouped into another failure.
          continue
        step_failures_without_existing_group.append(atomic_failure)
      if step_failures_without_existing_group:
        failures_without_existing_group['failures'][step_ui_name] = {
            'atomic_failures': step_failures_without_existing_group,
            'last_passed_build': step_failure['last_passed_build'],
        }
        _UpdateToEarlierBuild(failures_without_existing_group,
                              step_failure['last_passed_build'])
    return failures_without_existing_group

  def _UpdateFailureEntitiesWithGroupInfo(self, build,
                                          failures_with_existing_group):
    """Updates failure_group_build_id for failures that found matching group.

    Args:
      build (buildbucket build.proto): ALL info about the build.
      failures_with_existing_group (dict): A dict of failures from
          first_failures_in_current_build that found a matching group.
          {
            'step name': {
              frozenset(['target4']):  8765432000,
            ]
          }
    """
    failure_entities = self.GetFailureEntitiesForABuild(build)
    entities_to_save = []
    group_failures = {}
    for failure_entity in failure_entities:
      failure_group_build_id = failures_with_existing_group.get(
          failure_entity.step_ui_name,
          {}).get(failure_entity.GetFailureIdentifier())
      if failure_group_build_id:
        merged_failure_key = self._GetMergedFailureKey(
            group_failures, failure_group_build_id, failure_entity.step_ui_name,
            failure_entity.GetFailureIdentifier())
        failure_entity.failure_group_build_id = failure_group_build_id
        failure_entity.merged_failure_key = merged_failure_key
        entities_to_save.append(failure_entity)

    ndb.put_multi(entities_to_save)

  def GetFirstFailuresInCurrentBuildWithoutGroup(
      self, project_api, context, build, first_failures_in_current_build):
    """Gets first failures without existing failure groups.

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build.
      first_failures_in_current_build (dict): A dict for failures that happened
        the first time in current build.
        {
          'failures': {
            'step name': {
              'atomic_failures': [
                frozenset(['target4']),
                frozenset(['target1', 'target2'])],
              'last_passed_build': {
                'id': 8765432109,
                'number': 122,
                'commit_id': 'git_sha1'
              },
            },
          },
          'last_passed_build': {
            'id': 8765432109,
            'number': 122,
            'commit_id': 'git_sha1'
          }
        }

    Returns:
      failures_without_existing_group (dict): updated version of
        first_failures_in_current_build, no failures with existing group.
    """

    failures_with_existing_group = (
        self._GetFailuresWithMatchingFailureGroups(
            project_api, context, build, first_failures_in_current_build))

    if not failures_with_existing_group:
      # All failures need a new group.
      return first_failures_in_current_build

    self._UpdateFailureEntitiesWithGroupInfo(build,
                                             failures_with_existing_group)

    return self._GetFailuresWithoutMatchingFailureGroups(
        build.id, first_failures_in_current_build, failures_with_existing_group)

  def _GetFirstFailuresWithoutGroup(self, build,
                                    failures_without_existing_group):
    """Gets keys to the failures that failed the first time in the build and
      are not in any existing groups.

    Args:
      build (buildbucket build.proto): ALL info about the build.
      failures_without_existing_group (dict): A dict for failures that happened
        the first time in current build and with no matching group.
        {
        'failures': {
          'compile': {
            'atomic_failures': ['target4', 'target1', 'target2'],
            'last_passed_build': {
              'id': 8765432109,
              'number': 122,
              'commit_id': 'git_sha1'
            },
          },
        },
        'last_passed_build': {
          'id': 8765432109,
          'number': 122,
          'commit_id': 'git_sha1'
        }
      }
    """
    failure_entities = self.GetFailureEntitiesForABuild(build)
    first_failures = {
        s: failure['atomic_failures'] for s, failure in
        failures_without_existing_group['failures'].iteritems()
    }
    return [
        f for f in failure_entities if f.GetFailureIdentifier() in (
            first_failures.get(f.step_ui_name) or [frozenset([])])
    ]

  def SaveFailureAnalysis(self, project_api, context, build,
                          failures_without_existing_group,
                          should_group_failures):
    """Creates and saves failure entity for the build being analyzed if there
      are first failures in the build.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      context (findit_v2.services.context.Context): Scope of the analysis.
      build (buildbucket build.proto): ALL info about the build.
      failures_without_existing_group (dict): A dict for failures that happened
        the first time in current build and with no matching group.
        {
          'failures': {
            'step': {
              'atomic_failures': [
                'target4',  # if compile failure
                'test' # if test failure],
              'last_passed_build': {
                'id': 8765432109,
                'number': 122,
                'commit_id': 'git_sha1'
              },
            },
          },
          'last_passed_build': {
            'id': 8765432109,
            'number': 122,
            'commit_id': 'git_sha1'
          }
        }
      should_group_failures (bool): Project config for if failures should be
        grouped to reduce duplicated analyses.
    """
    rerun_builder_id = project_api.GetRerunBuilderId(build)

    repo_url = git.GetRepoUrlFromContext(context)
    last_passed_gitiles_id = failures_without_existing_group[
        'last_passed_build']['commit_id']
    last_passed_commit_position = git.GetCommitPositionFromRevision(
        last_passed_gitiles_id, repo_url, ref=context.gitiles_ref)
    first_failed_commit_position = git.GetCommitPositionFromRevision(
        context.gitiles_id, repo_url, ref=context.gitiles_ref)

    # Gets failures that failed the first time in the build.
    first_failures = self._GetFirstFailuresWithoutGroup(
        build, failures_without_existing_group)
    failure_keys = [
        f.key for f in first_failures if project_api.FailureShouldBeAnalyzed(f)]

    if should_group_failures:
      group = self._CreateFailureGroup(
          context, build, failure_keys, last_passed_gitiles_id,
          last_passed_commit_position, first_failed_commit_position)
      group.put()
      failure_keys = self._GetFailureKeysToAnalyze(first_failures, project_api)

    if not failure_keys:
      # There could be no failures that actually need to be analyzed.
      return None

    analysis = self._CreateFailureAnalysis(
        context.luci_project_name, context, build, last_passed_gitiles_id,
        last_passed_commit_position, first_failed_commit_position,
        rerun_builder_id, failure_keys)
    analysis.Save()
    return analysis

  def _GetCulpritCommit(self, left_bound_commit, right_bound_commit):
    assert left_bound_commit and right_bound_commit, (
        'Requiring two bounds to determine a bisecting commit')

    left_commit_position = left_bound_commit.commit_position
    right_commit_position = right_bound_commit.commit_position
    assert left_commit_position <= right_commit_position, (
        'left bound commit is after right.')

    if right_commit_position == left_commit_position + 1:
      # Cannot further divide the regression range, culprit is the
      # right_bound_commit.
      return right_bound_commit

    return None

  def _BisectGitilesCommit(self, context, left_bound_commit, right_bound_commit,
                           commit_position_to_git_hash_map):
    """ Gets the culprit commit, otherwise next commit to check using bisection.

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
        left_bound_commit (GitilesCommit): left bound of the regression range,
        not inclusive. It should be the last passed commit found so far.
      right_bound_commit (GitilesCommit): right bound of the regression range,
        inclusive. It should be the first failed commit found so far.
      commit_position_to_git_hash_map (dict): A map of commit_positions to
        git_hashes.

    Return:
      GitilesCommit: Commit to bisect next.
    """
    left_commit_position = left_bound_commit.commit_position
    right_commit_position = right_bound_commit.commit_position

    bisect_commit_position = left_commit_position + (
        right_commit_position - left_commit_position) / 2

    bisect_commit_gitiles_id = (commit_position_to_git_hash_map or
                                {}).get(bisect_commit_position)

    if not bisect_commit_gitiles_id:
      logging.error('Failed to get git_hash for change %s/%s/%s/%d',
                    context.gitiles_host, context.gitiles_project,
                    context.gitiles_ref, bisect_commit_position)
      return None

    return GitilesCommit(
        gitiles_host=context.gitiles_host,
        gitiles_project=context.gitiles_project,
        gitiles_ref=context.gitiles_ref,
        gitiles_id=bisect_commit_gitiles_id,
        commit_position=bisect_commit_position)

  def _UpdateFailureRegressionRanges(self, rerun_builds_info, failure_ranges):
    """Updates regression ranges for each failure based on rerun build results.

    Args:
      rerun_builds_info (list of (GitilesCommit, dict)): Gitiles commit each
        rerun build runs on and failures in them ({} if no failures).
        Format is like:
        [
          (GitilesCommit,
          {
            'compile': [a.o', 'b.o'],  # If the rerun build is for compile.
            'browser_tests': ['t1, 't2'],  # If the rerun build is for test.
            ...
          })
        ]
      failure_ranges (list): A dict for regression ranges of each
        failure. All failures have the same range, which is
        (analysis.last_passed_commit, analysis.first_failed_commit].
        Format is like:
        [
          {
            'failure': AtomicFailure,
            'last_passed_commit': GitilesCommit,
            'first_failed_commit': GitilesCommit
          },
          {
            'failure': AtomicFailure,
            'last_passed_commit': GitilesCommit,
            'first_failed_commit': GitilesCommit
          },
        ]
      After processing, each failure will have their own updated regression
      range.
    """
    for commit, failures_in_rerun_build in rerun_builds_info:
      for failure_range in failure_ranges:
        failure = failure_range['failure']
        if (commit.commit_position <
            failure_range['last_passed_commit'].commit_position or
            commit.commit_position >
            failure_range['first_failed_commit'].commit_position):
          # Commit is outside of this failure's regression range, so the rerun
          # build must be irrelevant to this failure.
          continue

        if (not failures_in_rerun_build.get(failure.step_ui_name) or
            not self._FailureHappenedInRerunBuild(
                failure, failures_in_rerun_build[failure.step_ui_name])):
          # Target/test passes in the rerun build, updates its last_pass.
          failure_range['last_passed_commit'] = max(
              failure_range['last_passed_commit'],
              commit,
              key=lambda c: c.commit_position)
        else:
          # Target/test fails in the rerun build, updates its first_failure.
          failure_range['first_failed_commit'] = min(
              failure_range['first_failed_commit'],
              commit,
              key=lambda c: c.commit_position)

  def _GroupFailuresByRegressionRange(self, failure_ranges):
    """Gets groups of failures with the same regression range.

    Args:
      failure_ranges (list): A list for regression ranges of each
        failure. It has been updated by UpdateFailureRegressionRanges so each
        failure has their own updated regression range.
        Format is like:
        [
          {
            'failure': AtomicFailure,
            'last_passed_commit': GitilesCommit,
            'first_failed_commit': GitilesCommit
          },
          {
            'failure': AtomicFailure,
            'last_passed_commit': GitilesCommit,
            'first_failed_commit': GitilesCommit
          },
        ]

    Returns:
      (list of dict): Failures with the same regression range and the range.
      [
        {
          'failures': [AtomicFailure, ...],
          'last_passed_commit': GitilesCommit,
          'first_failed_commit': GitilesCommit
        },
        ...
      ]
    """

    def range_info():
      # Returns a template for range_to_failures values.
      return {
          'failures': [],
          'last_passed_commit': None,
          'first_failed_commit': None,
      }

    # Groups failures with the same range. After processing it should look like:
    # {
    #   (600123, 600134): {
    #     'failures': [AtomicFailure, ...],
    #     'last_passed_commit': GitilesCommit for 600123
    #     'first_failed_commit': GitilesCommit for 600134
    #   },
    #   ...
    # }
    range_to_failures = defaultdict(range_info)
    for failure_range in failure_ranges:
      failure = failure_range['failure']
      last_passed_commit = failure_range['last_passed_commit']
      first_failed_commit = failure_range['first_failed_commit']
      commit_position_range = (last_passed_commit.commit_position,
                               first_failed_commit.commit_position)
      range_to_failures[commit_position_range]['failures'].append(failure)
      range_to_failures[commit_position_range][
          'last_passed_commit'] = last_passed_commit
      range_to_failures[commit_position_range][
          'first_failed_commit'] = first_failed_commit

    return range_to_failures.values()

  def _GetRegressionRangesForFailures(self, analysis):
    """Gets updated regression ranges and failures having that range.

      Uses completed rerun builds in this analysis to narrow down regression
      ranges for each failures.

      For example, if initially the regression range is (r0, r10] and atomic
      failures failure1 and failure2 are to be analyzed.
      1. When there's no rerun build, all failures have the same range (r0, r10]
      2. 1st rerun build on r5, all passed. Then all failures have a smaller
        range (r5, r10]
      3. 2nd rerun build on r7, failure1 failed, failure2 passed. So now the
        regression range for failure1 is (r5, r7], and for failure2 is
        (r7, r10].
      4. 3rd rerun build on r6, and it only checks on failure1. and both of
       them failed. The regression range is updated to (r5, r6].
      6. 4th rerun build on r8 and it only checks on failure2, and it failed. So
       the regression range is updated to (r7, r8].

      Returns:
      (list of dict): Failures with the same regression range and the range.
      [
        {
          'failures': [AtomicFailure entity for failure1],
          'last_passed_commit': GitilesCommit(gitiles_id=r5),
          'first_failed_commit': GitilesCommit(gitiles_id=r6)
        },
        {
          'failures': [AtomicFailure entity for failure2],
          'last_passed_commit': GitilesCommit(gitiles_id=r7),
          'first_failed_commit': GitilesCommit(gitiles_id=r8)
        },
      ]
      """
    failure_entities = self._GetFailuresInAnalysis(analysis)
    rerun_builds = self._FetchRerunBuildsOfAnalysis(analysis)
    if not rerun_builds:
      return [{
          'failures': failure_entities,
          'last_passed_commit': analysis.last_passed_commit,
          'first_failed_commit': analysis.first_failed_commit,
      }]

    # Gets rerun builds results.
    # Specifically, if a rerun build failed, gets its failures.
    # Otherwise just keep an empty list indicating a successful build.
    rerun_builds_info = [
        (rerun_build.gitiles_commit, rerun_build.GetFailuresInBuild())
        for rerun_build in rerun_builds
        if rerun_build.status in [common_pb2.FAILURE, common_pb2.SUCCESS]
    ]

    # A list for regression ranges of each failure.
    # Initially all failures have the same (and the widest) range. By checking
    # rerun build results, each failure's regression range could be narrower and
    # different from others.
    failure_ranges = []
    for failure in failure_entities:
      if failure.culprit_commit_key:
        # Skips the failures if it already found the culprit.
        continue
      failure_ranges.append({
          'failure': failure,
          'last_passed_commit': analysis.last_passed_commit,
          'first_failed_commit': analysis.first_failed_commit,
      })

    # Updates regression range for each failed targets.
    self._UpdateFailureRegressionRanges(rerun_builds_info, failure_ranges)

    # Groups failed targets with the same regression range, and returns these
    # groups along with their regression range.
    return self._GroupFailuresByRegressionRange(failure_ranges)

  def _GetUsableBuild(self, existing_builds):
    """Checks if existing rerun builds can be used."""
    for rerun_build in existing_builds:
      if rerun_build.status in _EXPECTED_BUILD_STATUSES:
        # If any of the rerun builds is running fine, Findit can use it.
        return rerun_build
    return None

  # pylint: disable=E1120
  @ndb.transactional(xg=True)
  def TriggerRerunBuild(self, context, analyzed_build_id, analysis_key,
                        rerun_builder, rerun_commit, atomic_failures):
    """Triggers a rerun build if there's no existing one.

    Creates and saves a rerun build entity if a new build is triggered.

    Checking for existing build and saving new build are in one transaction to
    make sure no unnecessary duplicated rerun builds can be triggered.

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      analyzed_build_id (int): Build id of the build that's being analyzed.
      analysis_key (Key to CompileFailureAnalysis): Key to the running analysis.
      rerun_builder (BuilderId): Builder to rerun the build.
      rerun_commit (GitilesCommit): Gitiles commit the build runs on.
      atomic_failures (dict): A dict of failures to rerun.
      {
        'compile': ['target1.o', ...], # for compile failures
        'step': ['test1', ...], # for test failures
        ...
      }

    Returns:
      str: error message of triggering the rerun build.
    """
    # Checks if there're rerun builds on that commit already.
    existing_builds = self._GetExistingRerunBuild(analysis_key, rerun_commit)
    if existing_builds and self._GetUsableBuild(existing_builds):
      logging.debug('Found existing rerun build for analysis %s on commit %d.',
                    analysis_key.urlsafe(), rerun_commit.commit_position)
      return None

    if len(existing_builds) >= _MAX_RERUN_BUILDS_TRIES:
      # Number of rerun builds on the same commit has exceeded limit, should not
      # trigger more builds.
      return 'Number of rerun builds on commit {} has exceeded limit.'.format(
          rerun_commit.gitiles_id)

    luci_project = context.luci_project_name
    project_api = projects.GetProjectAPI(luci_project)
    input_properties = self._GetRerunBuildInputProperties(
        project_api, atomic_failures, analyzed_build_id)
    if input_properties is None:
      return ('Failed to get input properties to trigger rerun build'
              'for build {}.'.format(analyzed_build_id))
    rerun_dimensions = self._GetRerunDimensions(project_api, analyzed_build_id)

    rerun_tags = self._GetRerunBuildTags(analyzed_build_id)
    gitiles_commit_pb = common_pb2.GitilesCommit(
        project=rerun_commit.gitiles_project,
        host=rerun_commit.gitiles_host,
        ref=rerun_commit.gitiles_ref,
        id=rerun_commit.gitiles_id)
    new_build = buildbucket_client.TriggerV2Build(
        rerun_builder,
        gitiles_commit_pb,
        input_properties,
        tags=rerun_tags,
        dimensions=rerun_dimensions)

    if not new_build:
      return ('Failed to trigger rerun build for {} in build {},'
              'on commit {}'.format(atomic_failures, analyzed_build_id,
                                    rerun_commit.gitiles_id))

    rerun_build = self._CreateRerunBuild(rerun_builder, new_build, rerun_commit,
                                         analysis_key)
    rerun_build.put()
    return None

  def SaveSuspectsToFailures(self, context, analysis, suspects):
    """Saves suspected commits to the failures they are suspected to cause.

    The heuristic analysis identifies commits in the regression range that may
    be associated with specific failed tests or targets and tags them with hints
    about why those commits may be culprits.

    This method tries to match the suspects to the specific failures in this
    analysis and creates/updates appropriate records in datastore.

    Args:
        context (findit_v2.services.context.Context): Scope of the analysis.
        analysis (findit_v2.model.BaseFailureAnalysis): analysis entity.
        suspects (dict): Result of GetSuspectedCulprits, mapping
        (step, frozenset([test]) or (step, frozenset([target1, target2, ...]) to
        a list of suspected commit: a dict with 'revision', 'commit_position',
        and 'hints' keys. The 'hints' value is a dict that maps a string
        describing the hint to an integer score.
    """
    failures = self._GetFailuresInAnalysis(analysis)
    for f in failures:
      suspects_for_failure = suspects.get(
          (f.step_ui_name, f.GetFailureIdentifier()), [])
      # If the suspect is not associated with an atom failure, but for the whole
      # step, add it to all failures in that step.
      suspects_for_step = suspects.get((f.step_ui_name, frozenset()), [])

      all_suspects = suspects_for_step + suspects_for_failure
      if not all_suspects:
        continue

      for suspect in all_suspects:
        suspect_instance = Suspect.GetOrCreate(
            context.gitiles_host, context.gitiles_project,
            context.gitiles_ref, suspect['revision'],
            suspect.get('commit_position'), suspect['hints'])
        if suspect_instance.key not in f.suspect_commit_key:
          f.suspect_commit_key.append(suspect_instance.key)
      f.put()

  def _SaveCulpritInFailures(self, failure_entities, culprit_commit):
    """Saves the culprit to failure entities.

    Args:
      failure_entities (list of CompileFailure or TestFailure): Failure entities
        that are caused by the culprit_commit.
      culprit_commit (GitilesCommit): The commit that caused compile failure(s).
    """
    culprit_entity = Culprit.GetOrCreate(
        gitiles_host=culprit_commit.gitiles_host,
        gitiles_project=culprit_commit.gitiles_project,
        gitiles_ref=culprit_commit.gitiles_ref,
        gitiles_id=culprit_commit.gitiles_id,
        commit_position=culprit_commit.commit_position,
        failure_urlsafe_keys=[cf.key.urlsafe() for cf in failure_entities])

    for failure in failure_entities:
      failure.culprit_commit_key = culprit_entity.key
    ndb.put_multi(failure_entities)
    return culprit_entity

  def _GetSuspectToRerun(self, context, failures, last_passed_commit,
                         first_failed_commit, commit_position_to_git_hash_map):
    """Tries to get a commit to rerun next based on the failures' suspects.

    If suspects exist in the commit range, find the latest one (the one with the
    highest commit position) and choose the commit immediately previous to it.
    If the most recent suspect is at the beginning of the regression range,
    (directly after last_passed_commit) choose _it_ for rerunning.

    Args:
      context (findit_v2.services.context.Context): Scope of the analysis.
      failures: Failure entities associated with Suspects via their
        suspect_commit_key property.
      last_passed_commit, first_failed_commit (GitilesCommit): define the range
        to search for suspects.
      commit_position_to_git_hash_map (dict): A map of commit_positions to
        git_hashes.
    """
    rerun_commit = None
    most_recent_suspect = None

    def previous_commit(child_commit):
      """This is for finding the previous commit via the mapping above."""
      previous_cp = child_commit.commit_position - 1
      previous_hash = (commit_position_to_git_hash_map or {}).get(previous_cp)
      if previous_hash:
        return GitilesCommit(
            gitiles_host=context.gitiles_host,
            gitiles_project=context.gitiles_project,
            gitiles_ref=context.gitiles_ref,
            gitiles_id=previous_hash,
            commit_position=previous_cp)
      return None

    # Gather all suspect keys and deduplicate.
    all_suspect_keys_in_failures = set(
        sum((failure.suspect_commit_key for failure in failures), []))

    # Find the most recent suspect.
    for suspect in (s_key.get() for s_key in all_suspect_keys_in_failures):
      if (
          # Suspect is in range.
          last_passed_commit.commit_position < suspect.commit_position and
          suspect.commit_position <= first_failed_commit.commit_position) and (
              # It is the most recent suspect in the range so far.
              not most_recent_suspect or
              suspect.commit_position > most_recent_suspect.commit_position):
        most_recent_suspect = suspect

    if most_recent_suspect:
      if (most_recent_suspect.commit_position ==
          last_passed_commit.commit_position + 1):
        # This means that the previous commit of this suspect is known to be
        # good. To confirm that this suspect is indeed the culprit, trigger a
        # re-run at its revision.
        rerun_commit = most_recent_suspect
      else:
        # Before testing the suspect, we should test its previous commit,
        # because getting a failure at the suspect doesn't tell us much if its
        # parent is not determined to be passing.
        rerun_commit = previous_commit(most_recent_suspect)
    return rerun_commit

  def RerunBasedAnalysis(self, context, analyzed_build_id):
    """
    Checks rerun build results and looks for either the culprit or the next
    commit to test. Then wraps up the analysis with culprit or continues the
    analysis by triggering the next rerun build.

      Args:
        context (findit_v2.services.context.Context): Scope of the analysis.
        analyzed_build_id (int): Build id of the build that's being analyzed.
    """
    analysis = self._GetFailureAnalysis(analyzed_build_id)
    assert not analysis.completed, (
        'RerunBasedAnalysis is called for a completed analysis '
        'for build {}.'.format(analyzed_build_id))

    rerun_builder = luci_build.ParseBuilderId(analysis.rerun_builder_id)

    # Gets a map from commit_position to gitiles_ids (git_hash/ revision) for
    # the commits between lass_passed_commit and first_failed_commit, bounds are
    # included.
    commit_position_to_git_hash_map = git.MapCommitPositionsToGitHashes(
        analysis.first_failed_commit.gitiles_id,
        analysis.first_failed_commit.commit_position,
        analysis.last_passed_commit.commit_position,
        repo_url=git.GetRepoUrlFromContext(context),
        ref=context.gitiles_ref)

    # Flag to check if analysis completes successfully.
    # True if all failures have culprits, False otherwise.
    all_culprits_found = True
    # List of error messages for each failure_range.
    analysis_errors = []

    # Gets updated regression range for the targets based on rerun build
    # results. The format is like:
    # [
    #   {
    #     'failures': {'compile': ['target1', 'target2']},
    #     'last_passed_commit': left_bound_commit,
    #     'first_failed_commit': right_bound_commit},
    #   {
    #     'failures': {'compile': ['target3']},
    #     'last_passed_commit': other_left_bound_commit,
    #     'first_failed_commit': other_right_bound_commit},
    # ]
    # It's possible that failures have different regression range so that
    # multiple rerun builds got triggered for different failures on different
    # commit. Though this case should be rare.
    updated_ranges = self._GetRegressionRangesForFailures(analysis)
    for failure_ranges in updated_ranges:
      last_passed_commit = failure_ranges['last_passed_commit']
      first_failed_commit = failure_ranges['first_failed_commit']
      failures = failure_ranges['failures']

      culprit_commit = self._GetCulpritCommit(last_passed_commit,
                                              first_failed_commit)
      if culprit_commit:
        # Analysis for these failures has run to the end.
        culprit_entity = self._SaveCulpritInFailures(failures, culprit_commit)
        self.OnCulpritFound(context, analyzed_build_id, culprit_entity)
        analysis_errors.append(None)
        continue

      rerun_commit = self._GetSuspectToRerun(
          context, failures, last_passed_commit, first_failed_commit,
          commit_position_to_git_hash_map)
      if not rerun_commit:
        # In the absence of suspects, perform regular bisection
        rerun_commit = self._BisectGitilesCommit(
            context, last_passed_commit, first_failed_commit,
            commit_position_to_git_hash_map)

      # No culprit found for these failures, analysis continues.
      all_culprits_found = False
      if not rerun_commit:
        # TODO (crbug.com/957760): Properly recover failed analysis.
        analysis_error = (
            'Failed to find the next commit to run from the range {}..{}'
            .format(last_passed_commit.commit_position,
                    first_failed_commit.commit_position))
        analysis_errors.append(analysis_error)
        continue

      # Triggers a rerun build unless there's an existing one.
      # It's possible if the existing one is still running so that Findit
      # doesn't know that build's result.
      analysis_error = self.TriggerRerunBuild(
          context, analyzed_build_id, analysis.key, rerun_builder, rerun_commit,
          self._GetFailuresToRerun(failures))

      analysis_errors.append(analysis_error)

    analysis.start_time = analysis.start_time or time_util.GetUTCNow()
    if all(analysis_errors):
      analysis.status = analysis_status.ERROR
      analysis.end_time = time_util.GetUTCNow()
    elif all_culprits_found:
      analysis.status = analysis_status.COMPLETED
      analysis.end_time = time_util.GetUTCNow()
    else:
      analysis.status = analysis_status.RUNNING

    error_str = '\n'.join([e for e in analysis_errors if e])
    analysis.error = error_str if error_str else analysis.error
    analysis.put()

  def GetCulpritsForFailures(self, failures):
    """Gets culprits for the requested failures."""
    culprit_keys = set([
        failure.culprit_commit_key
        for failure in failures
        if failure and failure.culprit_commit_key
    ])
    culprits = []
    for culprit_key in culprit_keys:
      culprit_entity = culprit_key.get()
      culprit_message = CulpritPb(
          commit=GitilesCommitPb(
              host=culprit_entity.gitiles_host,
              project=culprit_entity.gitiles_project,
              ref=culprit_entity.gitiles_ref,
              id=culprit_entity.gitiles_id,
              commit_position=culprit_entity.commit_position))
      culprits.append(culprit_message)
    return culprits

  def AnalyzeSkippedFailures(self, project_api, context, build,
                             failures_to_analyze):
    self._ClearSkipFlag(project_api, failures_to_analyze)
    group = self._GetFailureGroupByContext(context)
    analysis = self._CreateFailureAnalysis(
        context.luci_project_name, context, build,
        group.last_passed_commit.gitiles_id,
        group.last_passed_commit.commit_position,
        group.first_failed_commit.commit_position,
        project_api.GetRerunBuilderId(build),
        [f.key for f in failures_to_analyze])
    analysis.Save()
    self.RerunBasedAnalysis(context, build.id)

  @staticmethod
  @ndb.transactional
  def _CheckPreviousRevertAction(culprit):
    assert ndb.in_transaction()
    previous_action = CulpritAction.CreateKey(culprit).get()
    if previous_action:
      if previous_action.action_type == CulpritAction.REVERT:
        logging.info(
            'There is already a REVERT action on this culprit, bailing out')
        return previous_action
      # We are about to overwrite previous_action with a new action. Logging the
      # the details.
      logging.warning('Overwriting culprit notification on %s at %s' % (
          previous_action.key.parent().id(),  # Culprit id string.
          previous_action.create_timestamp,  # Datetime, rendered as isoformat.
      ))
    return None

  @classmethod
  @ndb.transactional
  def _RequestReview(cls, project_api, revert_description, culprit):
    """Requests manual review of the created revert with appropriate message.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      revert_description(str): Description for the revert.
      culprit: The culprit entity.

    Returns:
      The CulpritAction entity describing the action taken, None if no action
      was performed.
    """
    previous_revert_action = cls._CheckPreviousRevertAction(culprit)
    if previous_revert_action:
      return previous_revert_action
    bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT,
        None,
        culprit.gitiles_id,
        ds_key=culprit.key.id())
    request_review_message = project_api.REQUEST_REVIEW.format(
        bug_link=bug_link)
    project_api.AsyncRequestReview(culprit, revert_description,
                                   request_review_message)
    action = CulpritAction.Create(culprit, CulpritAction.REVERT)
    action.put()
    return action

  @classmethod
  @ndb.transactional
  def _CommitRevert(cls, project_api, revert_description, culprit):
    """Commits a previously created revert, and saves action to datastore.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      revert_description (str): Description for the revert.
      culprit: The culprit entity.

    Returns:
      The CulpritAction entity describing the action taken, None if no action
      was performed.
    """
    previous_revert_action = cls._CheckPreviousRevertAction(culprit)
    if previous_revert_action:
      return previous_revert_action
    bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT,
        None,
        culprit.gitiles_id,
        ds_key=culprit.key.id())
    request_confirmation_message = project_api.REQUEST_CONFIRMATION.format(
        bug_link=bug_link)
    project_api.AsyncCommitRevert(culprit, revert_description,
                                  request_confirmation_message)
    action = CulpritAction.Create(culprit, CulpritAction.REVERT)
    action.put()
    return action

  @staticmethod
  def _CheckIfReverted(cl_details, culprit, service_account):
    """Checks if the CL given has been reverted, and by which account.

    Args:
      cl_details: Details about the CL as returned by
          gerrit_client.GetClDetails()
      culprit: The culprit entity.
      service_account: The service account used for auto-actions.

    Returns:
      A pair of booleans (reverted, by_service_account) the first indicates
      whether the CL has been reverted, and the second one whether the revert
      was created by the given service account.

    """
    reverts = cl_details.GetRevertCLsByRevision(culprit.gitiles_id)
    for r in reverts:
      if r.reverting_user_email == service_account:
        return True, True
    if reverts:
      return True, False
    return False, False


  @ndb.transactional(xg=True)
  def _Notify(self, project_api, culprit, log_message, silent=False):
    """Posts notification to the culprit CL and save the change to datastore.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      culprit: The culprit entity.
      log_message: A short string about why this action is being taken, to be
          logged for debugging purposes.
      silent: Boolean indicating whether to bypass sending email. Useful when
          action has already been taken and we're only confirming the findings.

    Returns:
      The CulpritAction entity describing the action taken, None if no action
      was performed.
    """
    previous_action = CulpritAction.CreateKey(culprit).get()
    if previous_action:
      return previous_action
    logging.info('Notifying culprit %s, %s', culprit.key.id(), log_message)
    message = self._ComposeRevertDescription(project_api, culprit, silent)
    project_api.AsyncNotifyCulprit(culprit, message, silent_notification=silent)
    action = CulpritAction.Create(culprit, CulpritAction.CULPRIT_NOTIFIED)
    action.put()
    return action

  @staticmethod
  def _ComposeRevertDescription(project_api, culprit, confirm_only=False):
    """Composes the body of a message to be used in auto-actions.

    This done by populating fields in a project-specific template.

    Args:
      project_api (ProjectAPI): API for project specific logic.
      culprit: The culprit entity.
      confirm_only: If this notification is not requesting the sheriffs to take
          action, but simply providing confirmation.

    Returns:
      A string containing the populated notification.
    """
    bug_link = gerrit.CreateFinditWrongBugLink(
        gerrit.FINDIT_BUILD_FAILURE_COMPONENT,
        None,
        culprit.gitiles_id,
        ds_key=culprit.key.id())
    sample_failure = ndb.Key(urlsafe=culprit.failure_urlsafe_keys[0]).get()
    sample_build = (
        'https://ci.chromium.org/b/%d' % sample_failure.first_failed_build_id)
    sample_step = sample_failure.step_ui_name
    return project_api.ACTION_REASON.format(
        verb='confrmed' if confirm_only else 'identified',
        revision=culprit.gitiles_id,
        bug_link=bug_link,
        build=sample_build,
        step=sample_step)

  @staticmethod
  def _NoAction(culprit, log_message):
    """Logs consistent message when no culprit action is to be taken.

    Args:
      culprit: The culprit entity.
      log_message: A short string about why this action is being taken, to be
          logged for debugging purposes.
    """
    logging.info('Not taking any action for culprit %s, %s', culprit.key.id(),
                 log_message)
    return None
