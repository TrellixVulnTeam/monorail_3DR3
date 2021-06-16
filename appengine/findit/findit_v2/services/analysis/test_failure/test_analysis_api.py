# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Special logic of pre test analysis.

Build with test failures will be pre-processed to determine if a new analysis is
needed or not.
"""
from collections import defaultdict

from google.appengine.ext import ndb

from services import deps
from services import git

from findit_v2.model import luci_build
from findit_v2.model import test_failure
from findit_v2.model.test_failure import TestFailure
from findit_v2.model.test_failure import TestFailureAnalysis
from findit_v2.model.test_failure import TestFailureGroup
from findit_v2.model.test_failure import TestRerunBuild
from findit_v2.services import constants
from findit_v2.services.analysis.analysis_api import AnalysisAPI
from findit_v2.services.failure_type import StepTypeEnum


class TestAnalysisAPI(AnalysisAPI):

  @property
  def step_type(self):
    return StepTypeEnum.TEST

  def _GetMergedFailureKey(self, failure_entities, referred_build_id,
                           step_ui_name, atomic_failure):
    return TestFailure.GetMergedFailureKey(failure_entities, referred_build_id,
                                           step_ui_name, atomic_failure)

  def _GetFailuresInBuild(self, project_api, build, failed_steps):
    return project_api.GetTestFailures(build, failed_steps)

  def _GetFailuresWithMatchingFailureGroups(self, project_api, context, build,
                                            first_failures_in_current_build):
    return project_api.GetFailuresWithMatchingTestFailureGroups(
        context, build, first_failures_in_current_build)

  def _CreateFailure(self, failed_build_key, step_ui_name,
                     first_failed_build_id, last_passed_build_id,
                     merged_failure_key, atomic_failure, properties):
    """Creates a TestFailure entity."""
    assert (not atomic_failure or len(atomic_failure) == 1), (
        'Atomic test failure should be a frozenset of a single element.')
    return TestFailure.Create(
        failed_build_key=failed_build_key,
        step_ui_name=step_ui_name,
        test=next(iter(atomic_failure)) if atomic_failure else None,
        first_failed_build_id=first_failed_build_id,
        last_passed_build_id=last_passed_build_id,
        # Default to first_failed_build_id, will be updated later if matching
        # group exists.
        failure_group_build_id=first_failed_build_id,
        merged_failure_key=merged_failure_key,
        properties=properties)

  def GetFailureEntitiesForABuild(self, build):
    more = True
    cursor = None
    test_failure_entities = []
    while more:
      entities, cursor, more = TestFailure.query(
          ancestor=ndb.Key(luci_build.LuciFailedBuild, build.id)).fetch_page(
              500, start_cursor=cursor)
      test_failure_entities.extend(entities)

    assert test_failure_entities, (
        'No test failure saved in datastore for build {}'.format(build.id))
    return test_failure_entities

  def _CreateFailureGroup(self, context, build, test_failure_keys,
                          last_passed_gitiles_id, last_passed_commit_position,
                          first_failed_commit_position):
    group_entity = TestFailureGroup.Create(
        luci_project=context.luci_project_name,
        luci_bucket=build.builder.bucket,
        build_id=build.id,
        gitiles_host=context.gitiles_host,
        gitiles_project=context.gitiles_project,
        gitiles_ref=context.gitiles_ref,
        last_passed_gitiles_id=last_passed_gitiles_id,
        last_passed_commit_position=last_passed_commit_position,
        first_failed_gitiles_id=context.gitiles_id,
        first_failed_commit_position=first_failed_commit_position,
        test_failure_keys=test_failure_keys)
    return group_entity

  def _CreateFailureAnalysis(
      self, luci_project, context, build, last_passed_gitiles_id,
      last_passed_commit_position, first_failed_commit_position,
      rerun_builder_id, test_failure_keys):
    analysis = TestFailureAnalysis.Create(
        luci_project=luci_project,
        luci_bucket=build.builder.bucket,
        luci_builder=build.builder.builder,
        build_id=build.id,
        gitiles_host=context.gitiles_host,
        gitiles_project=context.gitiles_project,
        gitiles_ref=context.gitiles_ref,
        last_passed_gitiles_id=last_passed_gitiles_id,
        last_passed_commit_position=last_passed_commit_position,
        first_failed_gitiles_id=context.gitiles_id,
        first_failed_commit_position=first_failed_commit_position,
        rerun_builder_id=rerun_builder_id,
        test_failure_keys=test_failure_keys)
    return analysis

  def _GetFailuresInAnalysis(self, analysis):
    return ndb.get_multi(analysis.test_failure_keys)

  def _FetchRerunBuildsOfAnalysis(self, analysis):
    return TestRerunBuild.query(ancestor=analysis.key).order(
        TestRerunBuild.gitiles_commit.commit_position).fetch()

  def _GetFailureAnalysis(self, analyzed_build_id):
    analysis = TestFailureAnalysis.GetVersion(analyzed_build_id)
    assert analysis, 'Failed to get TestFailureAnalysis for build {}'.format(
        analyzed_build_id)
    return analysis

  def _GetFailuresToRerun(self, failure_entities):
    """Gets atomic failures in a dict format."""
    return test_failure.GetTestFailures(failure_entities)

  def _GetExistingRerunBuild(self, analysis_key, rerun_commit):
    return TestRerunBuild.SearchBuildOnCommit(analysis_key, rerun_commit)

  def _CreateRerunBuild(self, rerun_builder, new_build, rerun_commit,
                        analysis_key):
    return TestRerunBuild.Create(
        luci_project=rerun_builder.project,
        luci_bucket=rerun_builder.bucket,
        luci_builder=rerun_builder.builder,
        build_id=new_build.id,
        legacy_build_number=new_build.number,
        gitiles_host=rerun_commit.gitiles_host,
        gitiles_project=rerun_commit.gitiles_project,
        gitiles_ref=rerun_commit.gitiles_ref,
        gitiles_id=rerun_commit.gitiles_id,
        commit_position=rerun_commit.commit_position,
        status=new_build.status,
        create_time=new_build.create_time.ToDatetime(),
        parent_key=analysis_key)

  def _GetRerunBuildTags(self, analyzed_build_id):
    return [
        {
            'key': constants.RERUN_BUILD_PURPOSE_TAG_KEY,
            'value': constants.TEST_RERUN_BUILD_PURPOSE,
        },
        {
            'key': constants.ANALYZED_BUILD_ID_TAG_KEY,
            'value': str(analyzed_build_id),
        },
    ]

  def _GetRerunBuildInputProperties(self, project_api, test_failures,
                                    analyzed_build_id):
    return project_api.GetTestRerunBuildInputProperties(test_failures,
                                                        analyzed_build_id)

  def _GetFailureKeysToAnalyze(self, failure_entities, project_api):
    """Gets failures that'll actually be analyzed in the analysis.

    Placeholder for project specific logic, for example in-build failure
    grouping for ChromeOS test failure analysis.
    """
    return project_api.GetFailureKeysToAnalyzeTestFailures(failure_entities)

  def GetSkippedFailures(self, project_api, failures):
    """Gets failures that other failures depend on but haven't been analyzed.

    Possible reasons for such case to happen: Findit skips analyzing some
    failures per project specified requests, but the following failure
    analyses require the results of them. In this case Findit has stored the
    failures but didn't start an analysis.

    Note a similar case that is not covered here: for example Findit just starts
    to support a builder, and the first build it gets is build 100. And there
    are some failures in build 100 have happened since build 98. Findit doesn't
    save any information about build 98 or 99, and it will not go back and
    trigger new analyses on them either.

    """
    failures_needs_analysis = defaultdict(list)

    for failure in failures:
      merged_failure = failure.GetMergedFailure()
      if not merged_failure:
        continue

      if merged_failure == failure or project_api.FailureShouldBeAnalyzed(
          merged_failure):
        continue

      failures_needs_analysis[merged_failure.build_id].append(merged_failure)
    return failures_needs_analysis

  def _ClearSkipFlag(self, project_api, failure_entities):
    project_api.ClearSkipFlag(failure_entities)

  def _GetFailureGroupByContext(self, context):
    groups = TestFailureGroup.query(
        TestFailureGroup.luci_project == context.luci_project_name).filter(
            TestFailureGroup.first_failed_commit.gitiles_id == context
            .gitiles_id).fetch()
    return groups[0] if groups else None

  def GetSuspectedCulprits(self, project_api, context, build,
                           first_failures_in_current_build):
    failure_info = project_api.GetTestFailureInfo(
        context, build, first_failures_in_current_build)
    # Projects that support heuristic analysis must implement GetFailureInfo
    if not failure_info:
      return None
    signals = project_api.ExtractSignalsForTestFailure(failure_info)

    change_logs = git.PullChangeLogs(
        first_failures_in_current_build['last_passed_build']['commit_id'],
        context.gitiles_id)

    deps_info = deps.ExtractDepsInfo(failure_info, change_logs)

    return project_api.HeuristicAnalysisForTest(failure_info, change_logs,
                                                deps_info, signals)
