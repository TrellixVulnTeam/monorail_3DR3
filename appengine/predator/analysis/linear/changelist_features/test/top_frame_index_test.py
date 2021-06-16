# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_match import CrashMatch
from analysis.crash_match import FrameInfo
from analysis.linear.changelist_features import top_frame_index
from analysis.linear.changelist_features.touch_crashed_file_meta import (
    CrashedFile)
from analysis.suspect import Suspect
from analysis.stacktrace import StackFrame
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType

_MAXIMUM = 7


class TopFrameIndexFeatureTest(AnalysisTestCase):
  """Tests ``TopFrameIndexFeature``."""

  def _GetDummyReport(self):
    return None

  def _GetMockSuspect(self):
    """Returns a ``Suspect`` with the desired top frame index."""
    dep_path = 'src/'
    return Suspect(self.GetDummyChangeLog(), dep_path)

  def testTopFrameIndexNone(self):
    """Test that the feature returns 0 when there are no matched files."""
    report = self._GetDummyReport()
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    self.assertEqual(0.0,
                     top_frame_index.TopFrameIndexFeature(3)(report)(
                         suspect, {}).value)

  def testTopFrameIndexValueForTopFrame(self):
    """Test that the feature returns 1 when the top frame index is 0."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect()
    frame = StackFrame(index=0, dep_path=suspect.dep_path,
                       function='func', file_path='a.cc',
                       raw_file_path='a.cc', crashed_line_numbers=[7])
    crashed = CrashedFile(frame)
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'a.cc', 'a.cc')],
                   [FrameInfo(frame=frame, priority = 0)])
    }
    self.assertEqual(1.0,
                     top_frame_index.TopFrameIndexFeature(_MAXIMUM)(report)(
                         suspect, matches).value)

  def testTopFrameIndexValueForBottonFrame(self):
    """Test that feature returns 0 when the frame index is larger than max."""
    report = self._GetDummyReport()
    suspect = self._GetMockSuspect()
    frame = StackFrame(index=_MAXIMUM + 1, dep_path=suspect.dep_path,
                       function='func', file_path='a.cc',
                       raw_file_path='a.cc', crashed_line_numbers=[7])
    crashed = CrashedFile(frame)
    matches = {
        crashed:
        CrashMatch(crashed,
                   [FileChangeInfo(ChangeType.MODIFY, 'a.cc', 'a.cc')],
                   [FrameInfo(frame=frame, priority = 0)])
    }
    self.assertEqual(0.0,
                     top_frame_index.TopFrameIndexFeature(_MAXIMUM)(report)(
                         suspect, matches).value)
