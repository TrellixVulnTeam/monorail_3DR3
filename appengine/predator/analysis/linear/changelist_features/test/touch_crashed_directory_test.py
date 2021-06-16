# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis.analysis_testcase import AnalysisTestCase
from analysis.crash_match import CrashedDirectory
from analysis.crash_report import CrashReport
from analysis.linear.changelist_features.touch_crashed_directory import (
    TouchCrashedDirectoryBaseFeature)
from analysis.linear.changelist_features.touch_crashed_directory import (
    TouchCrashedDirectoryFeature)
from analysis.linear.changelist_features.touch_crashed_directory import (
    TouchParentDirectoryFeature)
from analysis.linear.changelist_features.touch_crashed_directory import (
    TouchGrandParentDirectoryFeature)
from analysis.linear.changelist_features.touch_crashed_directory import (
    _IsTestFile)
from analysis.linear.changelist_features.min_distance import Distance
from analysis.linear.changelist_features.min_distance import MinDistanceFeature
from analysis.linear.feature import ChangedFile
from analysis.suspect import Suspect
from analysis.stacktrace import CallStack
from analysis.stacktrace import StackFrame
from analysis.stacktrace import Stacktrace
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
from libs.gitiles.gitiles_repository import GitilesRepository
import libs.math.logarithms as lmath


class TouchCrashedDirectoryBaseFeatureTest(AnalysisTestCase):
  """Tests ``TouchCrashedDirectoryBaseFeature``."""

  def setUp(self):
    super(TouchCrashedDirectoryBaseFeatureTest, self).setUp()
    frame1 = StackFrame(0, 'src/', 'func', 'p/f.cc',
                        'src/p/f.cc', [2, 3], 'h://repo')
    stack = CallStack(0, frame_list=[frame1])
    stack_trace = Stacktrace([stack], stack)
    deps = {'src/': Dependency('src/', 'h://repo', '8')}
    dep_rolls = {'src/': DependencyRoll('src/', 'h://repo', '2', '6')}

    self._report = CrashReport('8', 'sig', 'linux', stack_trace, ('2', '6'),
                               deps, dep_rolls)
    self._feature = TouchCrashedDirectoryFeature()

  def testMatchWhenCrashedDirectryIsEmpty(self):
    """Tests ``Match`` returns False when the crashed directory is empty."""
    self.assertFalse(self._feature.Match(None, FileChangeInfo.FromDict({
            'change_type': 'add',
            'new_path': 'p/a.cc',
            'old_path': None,
    })))

  def testCrashedGroupFactoryReturnsNoneWhenFrameIsEmpty(self):
    """Tests ``CrashedGroupFactory`` returns None if frame is empty."""
    self.assertIsNone(self._feature.CrashedGroupFactory(None))

  def testGetCrashedDirectory(self):
    """Tests ``GetCrashedDirectory`` get directory according to level."""
    level_0_feature = TouchCrashedDirectoryBaseFeature(level=0)
    self.assertEqual(level_0_feature.GetCrashedDirectory('a/b/c.cc'), 'a/b')

    level_1_feature = TouchCrashedDirectoryBaseFeature(level=1)
    self.assertEqual(level_1_feature.GetCrashedDirectory('a/b/c.cc'), 'a')

    level_2_feature = TouchCrashedDirectoryBaseFeature(level=2)
    self.assertEqual(level_2_feature.GetCrashedDirectory('a/b/c.cc'), '')

    level_3_feature = TouchCrashedDirectoryBaseFeature(level=3)
    self.assertEqual(level_3_feature.GetCrashedDirectory('a/b/c.cc'), '')

  def testFeatureValueIsOneWhenThereIsMatchedDirectory(self):
    """Test that feature value is 1 when there is matched directory."""
    changelog = self.GetDummyChangeLog()._replace(
        touched_files=[FileChangeInfo.FromDict({
            'change_type': 'add',
            'new_path': 'p/a.cc',
            'old_path': None,
        })])
    suspect = Suspect(changelog, 'src/')
    feature_value = self._feature(self._report)(suspect)
    self.assertEqual(1.0, feature_value.value)

  def testFeatureValueIsZeroWhenNoMatchedDirectory(self):
    """Test that the feature returns 0 when there no matched directory."""
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    feature_value = self._feature(self._report)(suspect)
    self.assertEqual(0.0, feature_value.value)

  def testFeatureValueIsZeroWhenAFileIsDeleted(self):
    """Tests that the feature returns 0 when a file is deleted."""
    changelog = self.GetDummyChangeLog()._replace(
        # File deleted in the same directory:
        touched_files=[FileChangeInfo.FromDict({
            'change_type': 'delete',
            'new_path': None,
            'old_path': 'p/a.cc',
        })])
    suspect = Suspect(changelog, 'src/')
    feature_value = self._feature(self._report)(suspect)
    self.assertEqual(0.0, feature_value.value)

  def testIncludeTestFilesFlag(self):
    """Tests the ``include_test_files`` flag."""
    # Change in a test file:
    changelog = self.GetDummyChangeLog()._replace(
        touched_files=[FileChangeInfo.FromDict({
            'change_type': 'modify',
            'new_path': 'p/a_unittest.cc',
            'old_path': 'p/a_unittest.cc',
        })])
    suspect = Suspect(changelog, 'src/')

    feature_with_flag = TouchCrashedDirectoryFeature(include_test_files=True)
    feature_value = feature_with_flag(self._report)(suspect)
    self.assertEqual(1.0, feature_value.value)

    feature_without_flag = TouchCrashedDirectoryFeature(
        include_test_files=False)
    feature_value = feature_without_flag(self._report)(suspect)
    self.assertEqual(0.0, feature_value.value)

  def testIsTestFile(self):
    """Tests the ``_IsTestFile`` function."""
    self.assertTrue(_IsTestFile('decoder-unittest.cc'))
    self.assertTrue(_IsTestFile('gn_helpers_unittest.py'))
    self.assertTrue(_IsTestFile('cpu_unittest.cc'))
    self.assertTrue(_IsTestFile('browser_browsertest.cc'))
    self.assertTrue(_IsTestFile('rtree_perftest.cc'))
    self.assertTrue(_IsTestFile('mach_ports_performancetest.cc'))
    self.assertTrue(_IsTestFile('address_ui_test.cc'))

    self.assertFalse(_IsTestFile('callback.h'))
    self.assertFalse(_IsTestFile('location.cc'))
    self.assertFalse(_IsTestFile('gtest_xml_unittest_result_printer.cc'))
    self.assertFalse(_IsTestFile('shortest.cc'))

  def testCrashedGroupFactoryReturnsNoneWhenDirectoryIsBlacklisted(self):
    """Tests that ``CrashGroupFactory`` returns None when dir blacklisted."""
    feature = TouchCrashedDirectoryBaseFeature(
        options={'blacklist': ['bad_dir']}, level=0)
    frame = StackFrame(0, 'src/', 'func', 'bad_dir/f.cc',
                       'src/bad_dir/f.cc', [2, 3], 'h://repo')
    self.assertIsNone(feature.CrashedGroupFactory(frame))

  def testFilePathMatchAfterFileRename(self):
    """Tests the feature can match old file with new file after file name."""
    feature = TouchCrashedDirectoryBaseFeature(
        options={'replace_path': {'old/dir': 'new/dir'}})

    self.assertTrue(
        feature.Match(CrashedDirectory('new/dir/a'),
                      FileChangeInfo(ChangeType.MODIFY, 'old/dir/a/FileName.cc',
                                     'old/dir/a/FileName.cc')))



class TouchCrashedDirectoryFeatureTest(AnalysisTestCase):
  """Tests ``TouchCrashedDirectoryFeature``."""

  def testFeatureName(self):
    feature = TouchCrashedDirectoryFeature()
    self.assertEqual(feature.name, 'TouchCrashedDirectory')


class TouchParentDirectoryFeatureTest(AnalysisTestCase):
  """Tests ``TouchParentDirectoryFeature``."""

  def testFeatureName(self):
    feature = TouchParentDirectoryFeature()
    self.assertEqual(feature.name, 'TouchParentDirectory')


class TouchGrandParentDirectoryFeatureTest(AnalysisTestCase):
  """Tests ``TouchGrandParentDirectoryFeature``."""

  def testFeatureName(self):
    feature = TouchGrandParentDirectoryFeature()
    self.assertEqual(feature.name, 'TouchGrandParentDirectory')
