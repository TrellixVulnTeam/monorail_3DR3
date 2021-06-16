# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from collections import namedtuple
import logging
import math
import os

from analysis import crash_util
from analysis.crash_match import CrashedComponent
from analysis.linear.feature import Feature
from analysis.linear.feature import FeatureValue


class TouchCrashedComponentFeature(Feature):
  """Returns either one or zero.

  When a suspect touched crashed component, we return value 0. When the there is
  no directory match, we return 0.
  """
  def __init__(self, component_classifier, options=None):
    self._component_classifier = component_classifier
    blacklist = options.get('blacklist', []) if options else []
    self._blacklist = [component.lower() for component in blacklist]
    self._path_mappings = []
    if options and 'replace_path' in options:
      self._path_mappings.append(
          crash_util.ReplacePath(options['replace_path']))

  @property
  def name(self):
    return 'TouchCrashedComponent'

  def CrashedGroupFactory(self, frame):
    """Factory function to create ``CrashedComponent``."""
    component = self._component_classifier.ClassifyStackFrame(frame)
    if not component or component.lower() in self._blacklist:
      return None

    return CrashedComponent(component)

  def GetMatchFunction(self, dep_path):
    """Returns a function to match a crashed component with a touched file."""

    def Match(crashed_component, touched_file):
      """Determines if a touched_file matches this crashed component.

      Args:
        crashed_component (CrashedComponent): The crashed component.
        touched_file (FileChangeInfo): touched file to examine.

      Returns:
        Boolean indicating whether it is a match or not.
      """
      path = os.path.join(dep_path, touched_file.changed_path)
      touched_component = self._component_classifier.ClassifyFilePath(
          crash_util.MapPath(path, self._path_mappings))

      return crashed_component.value == touched_component

    return Match

  def __call__(self, report):
    """
    Args:
      report (CrashReport): the crash report being analyzed.

    Returns:
      A ``FeatureValue`` with name, log-domain value, reason and changed_files.
    """
    dep_to_grouped_frame_infos = crash_util.IndexFramesWithCrashedGroup(
        report.stacktrace, self.CrashedGroupFactory, report.dependencies)

    def FeatureValueGivenReport(suspect):
      """Compute ``FeatureValue`` for a suspect.

      Args:
        suspect (Suspect): The suspected changelog and some meta information
          about it.

      Returns:
        The ``FeatureValue`` of this feature.
      """
      grouped_frame_infos = dep_to_grouped_frame_infos.get(suspect.dep_path, {})
      matches = crash_util.MatchSuspectWithFrameInfos(
          suspect, grouped_frame_infos, self.GetMatchFunction(suspect.dep_path))

      if not matches:
        return FeatureValue(name=self.name,
                            value=0.0,
                            reason=None,
                            changed_files=None)

      crashed_components = [component.value for component in matches]
      plural = len(crashed_components) > 1

      reason = [
          'Suspected changelist touched file(s) associated with the '
          'component%s %s, which we believe is related to this testcase based '
          'on information in OWNERS files.' % (
              's' if plural else '', ', '.join(crashed_components))]

      return FeatureValue(
          name=self.name,
          value=1.0,
          reason=reason,
          changed_files=None)

    return FeatureValueGivenReport
