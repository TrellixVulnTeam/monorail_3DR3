# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import logging

from google.appengine.ext import ndb

from common.waterfall import buildbucket_client
from dto.commit_id_range import CommitID
from dto.commit_id_range import CommitIDRange
from dto.flake_analysis_error import FlakeAnalysisError
from dto.int_range import IntRange
from gae_libs.model.versioned_model import VersionedModel
from libs import analysis_status
from libs import time_util
from model import result_status
from model import triage_status
from model.base_analysis import BaseAnalysis
from model.base_build_model import BaseBuildModel
from model.base_triaged_model import TriagedModel
from model.flake.flake import Flake
from model.flake.analysis.data_point import DataPoint
from services.flake_failure import pass_rate_util


class MasterFlakeAnalysis(BaseAnalysis, BaseBuildModel, VersionedModel,
                          TriagedModel):
  """Represents an analysis of a flaky test on a Waterfall test cycle."""

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[0][1].split('/')[3]

  @ndb.ComputedProperty
  def canonical_step_name(self):
    return self.step_name.split(' on ')[0]

  @ndb.ComputedProperty
  def test_name(self):
    return base64.urlsafe_b64decode(self.key.pairs()[0][1].split('/')[4])

  @property
  def error_message(self):
    if not self.error:
      return None
    return self.error.get('message')

  @staticmethod
  def _CreateAnalysisId(master_name, builder_name, build_number, step_name,
                        test_name):
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    return '%s/%s/%s/%s/%s' % (master_name, builder_name, build_number,
                               step_name, encoded_test_name)

  @staticmethod
  def GetBuildConfigurationFromKey(master_flake_analysis_key):
    """Extracts master_name and builder_name from key."""
    if not master_flake_analysis_key:
      return None, None

    components = master_flake_analysis_key.pairs()[0][1].split('/')
    master_name = components[0]
    builder_name = components[1]
    return master_name, builder_name

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, master_name, builder_name, build_number, step_name,
             test_name):  # pragma: no cover.
    # TODO(wylieb): Populate original_* fields with these, add test case for
    # Create.
    return super(MasterFlakeAnalysis, cls).Create(
        MasterFlakeAnalysis._CreateAnalysisId(
            master_name, builder_name, build_number, step_name, test_name))

  def GetError(self):
    """Returns an analysis' error or a generic one."""
    return self.error or FlakeAnalysisError(
        title='Flake analysis encountered an unknown error',
        description='unknown').ToSerializable()

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def GetVersion(cls,
                 master_name,
                 builder_name,
                 build_number,
                 step_name,
                 test_name,
                 version=None):  # pragma: no cover.
    return super(MasterFlakeAnalysis, cls).GetVersion(
        key=MasterFlakeAnalysis._CreateAnalysisId(
            master_name, builder_name, build_number, step_name, test_name),
        version=version)

  def LogInfo(self, message):
    logging.info('%s/%s/%s/%s/%s %s', self.master_name, self.builder_name,
                 self.build_number, self.step_name, self.test_name, message)

  def LogWarning(self, message):
    logging.warning('%s/%s/%s/%s/%s %s', self.master_name, self.builder_name,
                    self.build_number, self.step_name, self.test_name, message)

  def LogError(self, message):
    logging.error('%s/%s/%s/%s/%s %s', self.master_name, self.builder_name,
                  self.build_number, self.step_name, self.test_name, message)

  def CanRunHeuristicAnalysis(self):
    """Determies whether heuristic analysis can be attempted."""
    already_run_statuses = [
        analysis_status.SKIPPED, analysis_status.COMPLETED,
        analysis_status.ERROR
    ]

    return ((self.suspected_build_id is not None or
             self.suspected_flake_build_number is not None) and
            self.heuristic_analysis_status not in already_run_statuses)

  def UpdateTriageResult(self,
                         triage_result,
                         suspect_info,
                         user_name,
                         version_number=None):
    """Updates triage result for a flake analysis.

    If there is culprit for the analysis, triage will be at CL level;
    otherwise the triage will be for suspected_flake_build.
    """
    super(MasterFlakeAnalysis, self).UpdateTriageResult(
        triage_result, suspect_info, user_name, version_number=version_number)

    if triage_result == triage_status.TRIAGED_CORRECT:
      self.result_status = result_status.FOUND_CORRECT
      if suspect_info.get('culprit_revision'):
        self.correct_culprit = True
    else:
      self.result_status = result_status.FOUND_INCORRECT
      if suspect_info.get('culprit_revision'):
        self.correct_culprit = False

  def GetDataPointOfSuspectedBuild(self):
    """Gets the corresponding data point to the suspected flake build."""
    if self.suspected_flake_build_number is not None:
      for data_point in self.data_points:
        if data_point.build_number == self.suspected_flake_build_number:
          return data_point

    return None

  # TODO(crbug.com/872992): This function is used only for falling back to
  # searching buildbot when builds aren't on LUCI. Remove once LUCI migration is
  # complete.
  def GetLowestUpperBoundBuildNumber(self, requested_commit_position):
    """Gets an upper bound build number to search nearby builds with."""
    lowest_build_number = self.build_number

    for data_point in self.data_points:
      if (data_point.build_number is not None and
          data_point.build_number < lowest_build_number and
          requested_commit_position <= data_point.commit_position):
        lowest_build_number = data_point.build_number

    return lowest_build_number

  def GetLatestRegressionRange(self):
    """Gets the latest stable -> flaky commit positions in data_points.

    Returns:
      (CommitIDRange): The commit position of the latest
          stable data_point and commit position of the earliest subsequent flaky
          data point. Either point can be None if no flaky or stable points are
          found.
    """
    if not self.data_points:
      return CommitIDRange(lower=None, upper=None)

    if len(self.data_points) == 1:
      data_point = self.data_points[0]

      if pass_rate_util.IsStableDefaultThresholds(data_point.pass_rate):
        # A lower bound stable is found, but no upper bound. The caller of this
        # function should interpret this as the flakiness being unreproducible.
        return CommitIDRange(
            lower=CommitID(
                commit_position=data_point.commit_position,
                revision=data_point.git_hash),
            upper=None)

      # The flakiness is reproducible, but no lower bound (stable) has been
      # identified yet.
      return CommitIDRange(
          lower=None,
          upper=CommitID(
              commit_position=data_point.commit_position,
              revision=data_point.git_hash))

    # For the latest regression range, sort in reverse order by commit position.
    data_points = sorted(
        self.data_points, key=lambda k: k.commit_position, reverse=True)

    # Disregard the data point created by the check for recent flakiness (if
    # any).
    # TODO(crbug.com/843846): Remove this data sanitization once change for
    # not appending that data point is committed.
    if (data_points and
        pass_rate_util.IsStableDefaultThresholds(data_points[0].pass_rate)):
      data_points = data_points[1:]

    # Identify the adjacent flaky and stable data points with the highest commit
    # positions.
    latest_stable_index = None
    for i, data_point in enumerate(data_points):
      if pass_rate_util.IsStableDefaultThresholds(data_point.pass_rate):
        latest_stable_index = i
        break

    if latest_stable_index is None:
      # All data points are flaky. The caller should interpret this as no
      # findings yet.
      return CommitIDRange(
          lower=None,
          upper=CommitID(
              commit_position=data_points[-1].commit_position,
              revision=data_points[-1].git_hash))

    # A regression range has been identified.
    assert latest_stable_index > 0, (
        'Non-reproducible flaky tests should only have 1 data point')
    adjacent_flaky_data_point = data_points[latest_stable_index - 1]
    assert not pass_rate_util.IsStableDefaultThresholds(
        adjacent_flaky_data_point.pass_rate)

    return CommitIDRange(
        lower=CommitID(
            commit_position=data_points[latest_stable_index].commit_position,
            revision=data_points[latest_stable_index].git_hash),
        upper=CommitID(
            commit_position=adjacent_flaky_data_point.commit_position,
            revision=adjacent_flaky_data_point.git_hash))

  def Reset(self):
    super(MasterFlakeAnalysis, self).Reset()
    self.original_master_name = None
    self.original_builder_name = None
    self.original_build_number = None
    self.original_step_name = None
    self.original_test_name = None
    self.bug_id = None
    self.error = None
    self.correct_regression_range = None
    self.correct_culprit = None
    self.suspected_build_id = None
    self.suspected_flake_build_number = None
    self.suspect_urlsafe_keys = []
    self.culprit_urlsafe_key = None
    self.data_points = []
    self.result_status = None
    self.last_attempted_build_number = None
    self.last_attempted_swarming_task_id = None
    self.last_attempted_revision = None
    self.heuristic_analysis_status = None

    # Reset booleans that track the actions taken by this analysis.
    self.has_filed_bug = False
    self.has_commented_on_bug = False
    self.has_commented_on_cl = False
    self.has_created_autorevert = False
    self.has_submitted_autorevert = False

  def GetDataPointsWithinCommitPositionRange(self, int_range):
    """Filters data_points by lower and upper bound commit positions.

    Args:
      int_range (IntRange): The upper and lower bound commit positions to
          include in the returned results.

    Returns:
      A list of DataPoints filtered by the input commit positions.
    """
    lower = int_range.lower
    upper = int_range.upper if int_range.upper is not None else float('inf')

    def PositionInBounds(data_point):
      return (data_point.commit_position >= lower and
              data_point.commit_position <= upper)

    return filter(PositionInBounds, self.data_points)

  def RemoveDataPointWithCommitPosition(self, commit_position):
    self.data_points = filter(lambda x: x.commit_position != commit_position,
                              self.data_points)

  def FindMatchingDataPointWithCommitPosition(self, commit_position):
    """Finds the data point with the same commit_position as the given one.

    Args:
      commit_position (int): DataPoint with the matching commit position to
          search for in the list.

    Returns:
      A DataPoint with the matching commit_position if found, else None.
    """
    if commit_position is None:
      return None

    return next((data_point for data_point in self.data_points
                 if data_point.commit_position == commit_position), None)

  def InitializeRunning(self):
    """Sets up necessary information for an analysis when it begins."""
    if self.status != analysis_status.RUNNING:
      self.Update(
          start_time=time_util.GetUTCNow(), status=analysis_status.RUNNING)

  def UpdateSuspectedBuild(self, lower_bound_target, upper_bound_target):
    """Sets the suspected build number if appropriate.

      A suspected build cycle can be set when a regression range is identified
      and spans at most a single build cycle.

    Args:
      lower_bound_target (IsolatedTarget): The earlier isolated target whose
          commit position to check.
      upper_bound_build (IsolatedTarget): The later isolated target whose commit
          position to check.
    """
    lower_bound = lower_bound_target.commit_position
    upper_bound = upper_bound_target.commit_position
    assert upper_bound > lower_bound, ((
        'Upper bound target commit position {} must be greater than lower '
        'bound target {} commit position').format(upper_bound, lower_bound))

    lower_bound_data_point = self.FindMatchingDataPointWithCommitPosition(
        lower_bound)
    upper_bound_data_point = self.FindMatchingDataPointWithCommitPosition(
        upper_bound)

    if (self.suspected_flake_build_number is None and
        self.suspected_build_id is None and lower_bound_data_point and
        upper_bound_data_point):
      assert pass_rate_util.IsStableDefaultThresholds(
          lower_bound_data_point.pass_rate), (
              'Lower bound must be stable in order to have a suspect')
      assert not pass_rate_util.IsStableDefaultThresholds(
          upper_bound_data_point.pass_rate), (
              'Upper bound must be flaky in order to have a suspect')
      build_id = upper_bound_target.build_id

      # Temporarily maintain suspected_flake_build_number to support legacy
      # analyses.
      suspected_build_number = buildbucket_client.GetBuildNumberFromBuildId(
          build_id)
      self.Update(
          suspected_build_id=build_id,
          suspected_flake_build_number=suspected_build_number)

  def UpdateSuspectedBuildUsingBuildInfo(self, lower_bound_build,
                                         upper_bound_build):
    """Sets the suspected build number if appropriate.

      A suspected build cycle can be set when a regression range is identified
      and spans at most a single build cycle.

      TODO(crbug.com/872992): This function should be deprecated as soon as the
      LUCI migration is 100% complete.

    Args:
      lower_bound_build (BuildInfo): The earlier build whose commit position to
          check.
      upper_bound_build (BuildInfo): The later build whose commit
          position to check, assumed to be 1 build cycle apart from
          lower_bound_build.
    """
    lower_bound_commit_position = lower_bound_build.commit_position
    upper_bound_commit_position = upper_bound_build.commit_position
    assert upper_bound_commit_position > lower_bound_commit_position, (
        'Upper bound {} must be > lower bound {}'.format(
            upper_bound_commit_position, lower_bound_commit_position))

    lower_bound_data_point = self.FindMatchingDataPointWithCommitPosition(
        lower_bound_commit_position)
    upper_bound_data_point = self.FindMatchingDataPointWithCommitPosition(
        upper_bound_commit_position)

    if (self.suspected_flake_build_number is None and lower_bound_data_point and
        upper_bound_data_point):  # pragma: no branch
      assert pass_rate_util.IsStableDefaultThresholds(
          lower_bound_data_point.pass_rate), (
              'Lower bound build must be stable in order to have a suspect')
      assert not pass_rate_util.IsStableDefaultThresholds(
          upper_bound_data_point.pass_rate), (
              'Upper bound build must be flaky in order to have a suspect')
      self.Update(suspected_flake_build_number=upper_bound_build.build_number)

  def Update(self, **kwargs):
    """Updates fields according to what's specified in kwargs.

      Fields specified in kwargs will be updated accordingly, while those not
      present in kwargs will be untouched.

    Args:
      confidence_in_culprit (float): Confidence score for the suspected culprit
          CL, if any.
      culprit_urlsafe_key (str): The urlsafe-key coresponding to a FlakeCulprit
          that caused flakiness.
      end_time (datetime): The timestamp that the overall analysis is completed.
      error (dict): Dict containing error information.
      last_attempted_swarming_revision (str): The last attempted try job
          revision.
      last_attempted_swarming_revision (str): The ID of the last attempted
          swarming task.
      result_status (int): The triage result status of this analysis.
      status (int): The status of the regression-range identification analysis.
      start_time (datetime): The timestamp that the overall analysis started.
      suspected_build (int): The suspected build number.
    """
    any_changes = False

    for arg, value in kwargs.iteritems():
      current_value = getattr(self, arg, None)
      if current_value != value:
        setattr(self, arg, value)
        any_changes = True

    if any_changes:
      self.put()

  def GetRepresentativeSwarmingTaskId(self):
    """Gets a representative swarming task for logs of flakiness if any."""
    if self.data_points:
      # The first data point triggered always that of the occurrence that
      # triggered the analysis and is thus the most reliable.
      return self.data_points[0].GetSwarmingTaskId()
    return None

  def GetLatestDataPoint(self):
    """Gets the analysis' data point with the highest commit position."""
    if self.flakiness_verification_data_points:
      return sorted(
          self.flakiness_verification_data_points,
          key=lambda k: k.commit_position)[-1]

    if self.data_points:
      return sorted(
          self.data_points, key=lambda k: k.commit_position, reverse=True)[0]

    # No data points.
    return None

  # The original build/step/test in which a flake actually occurred.
  # A CQ trybot step has to be mapped to a Waterfall buildbot step.
  # A gtest suite.PRE_PRE_test has to be normalized to suite.test.
  original_master_name = ndb.StringProperty(indexed=True)
  original_builder_name = ndb.StringProperty(indexed=True)
  original_build_number = ndb.IntegerProperty(indexed=True)
  original_step_name = ndb.StringProperty(indexed=True)
  original_test_name = ndb.StringProperty(indexed=True)
  original_build_id = ndb.StringProperty(indexed=False)

  # The bug id in which this flake is reported.
  bug_id = ndb.IntegerProperty(indexed=True)

  # The Flake entity that was responsible for triggering this analysis.
  flake_key = ndb.KeyProperty(Flake, indexed=False)

  # A bit to track if a bug filing has been attempted.
  has_attempted_filing = ndb.BooleanProperty(default=False)

  # Error code and message, if any.
  error = ndb.JsonProperty(indexed=False)

  # Boolean whether the suspected regression range/build number is correct.
  correct_regression_range = ndb.BooleanProperty(indexed=True)

  # Boolean whether the suspected CL for found in the regression range
  # is correct.
  correct_culprit = ndb.BooleanProperty(indexed=True)

  # The suspected build number to have introduced the flakiness.
  # TODO(crbug.com/799324): Remove once build numbers are deprecated in LUCI.
  suspected_flake_build_number = ndb.IntegerProperty()

  # The build id of the build cycle suspected to contain the culprit.
  suspected_build_id = ndb.IntegerProperty()

  # The confidence in the suspected CL to have introduced the flakiness.
  confidence_in_culprit = ndb.FloatProperty(indexed=False)

  # TODO(crbug.com/799308): Use KeyProperty instead.
  # The urlsafe key to a FlakeCulprit associated with the try job results.
  culprit_urlsafe_key = ndb.StringProperty(indexed=False)

  # TODO(crbug.com/799308): Use KeyProperty instead.
  # A list of url-safe keys to FlakeCulprits identified by heuristic analysis.
  suspect_urlsafe_keys = ndb.StringProperty(repeated=True)

  # Heuristic anlysis status. Can be PENDING if not yet ran, SKIPPED if wil not
  # be run, COMPLETED or ERROR if already ran.
  heuristic_analysis_status = ndb.IntegerProperty(indexed=False)

  # The data points used to plot the flakiness graph over a commit history as
  # prescribed by the analysis' lookback algorithm.
  data_points = ndb.LocalStructuredProperty(
      DataPoint, repeated=True, compressed=True)

  # The data points corresponding to specific commit positions independnt of
  # the analysis' lookback algorithm. For example, Findit may want to check if
  # a test is still flaky before filing a bug or a developer may want to check
  # if a flaky test has been fixed.
  flakiness_verification_data_points = ndb.LocalStructuredProperty(
      DataPoint, repeated=True, compressed=True)

  # Whether the analysis was triggered by a manual request through check flake,
  # Findit's automatic analysis upon detection, or Findit API.
  triggering_source = ndb.IntegerProperty(default=None, indexed=True)

  # Who triggered the analysis. Used for differentiating between manual and
  # automatic runs, and determining the most active users to gather feedback.
  triggering_user_email = ndb.StringProperty(default=None, indexed=False)

  # Whether the user email is obscured.
  triggering_user_email_obscured = ndb.BooleanProperty(
      default=False, indexed=True)

  # Overall conclusion of analysis result for the flake. Found untriaged, Found
  # Correct, etc. used to filter what is displayed on the check flake dashboard.
  result_status = ndb.IntegerProperty(indexed=True)

  # The build number corresponding to the last attempted swarming task.
  last_attempted_build_number = ndb.IntegerProperty(indexed=False)

  # The task id of the last-attempted swarming task.
  last_attempted_swarming_task_id = ndb.StringProperty(indexed=False)

  # The revision the last-attempted try job tried to run on.
  last_attempted_revision = ndb.StringProperty(indexed=False)

  # Store the root pipeline id to look up the pipeline from the analysis.
  root_pipeline_id = ndb.StringProperty(indexed=False)

  # How many times the swarming task has been attempted (and failed) for a
  # particular build during an analysis. Reset when the build number is changed.
  swarming_task_attempts_for_build = ndb.IntegerProperty(
      default=0, indexed=False)

  # Track if this analysis has created a bug.
  has_filed_bug = ndb.BooleanProperty(default=False, indexed=False)

  # Track if this analysis has commented on a bug.
  has_commented_on_bug = ndb.BooleanProperty(default=False, indexed=False)

  # Track if this analysis has commented on a cl.
  has_commented_on_cl = ndb.BooleanProperty(default=False, indexed=False)

  # Track if this analysis has created a revert for a test.
  has_created_autorevert = ndb.BooleanProperty(default=False, indexed=False)

  # Track if this analysis has submitted a revert cl for a test.
  has_submitted_autorevert = ndb.BooleanProperty(default=False, indexed=True)

  # Track the time the autorevert has been submitted.
  autorevert_submission_time = ndb.DateTimeProperty(indexed=True)

  # Post-analysis/recent flakiness verification fields. These fields should be
  # used mutually-exclusively from those during main analysis.

  # Whether a check for recent flakiness is in progress. Used to update the UI
  # and to prevent a scheduling of multiple checks for recent flakiness when one
  # is already in progress. Values are expected to be either None or those
  # defined in |libs.analysis_status.py|
  analyze_recent_flakiness_status = ndb.IntegerProperty(indexed=False)

  # Any error associated with flakiness verification.
  analyze_recent_flakiness_error = ndb.JsonProperty(indexed=False)

  # The url path to the pipeline status page for checking recent flakiness. Do
  # not override |pipeline_status_path| for debugging reasons.
  analyze_recent_flakiness_pipeline_status_path = (
      ndb.StringProperty(indexed=False))
