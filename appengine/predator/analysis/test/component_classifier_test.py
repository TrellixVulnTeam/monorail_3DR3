# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.analysis_testcase import AnalysisTestCase
from analysis.stacktrace import StackFrame
from analysis.stacktrace import CallStack
from analysis.component import Component
from analysis.component_classifier import ComponentClassifier
from analysis.component_classifier import MergeComponents
from analysis.suspect import Suspect
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType


COMPONENT_CONFIG = {
    'component_info': [
        {
            'dirs': ['src/comp1'],
            'component': 'Comp1>Dummy'
        },
        {
            'dirs': ['src/comp2'],
            'function': 'func2.*',
            'component': 'Comp2>Dummy',
            'team': 'comp2-team'
        }
    ],
    'top_n': 4
}

_MOCK_REPO_TO_DEP_PATH = {
    'https://chromium.git': 'src',
    'https://chromium.v8.git': 'src/v8',
}


class ComponentClassifierTest(AnalysisTestCase):
  """Tests ``ComponentClassifier`` class."""

  def setUp(self):
    super(ComponentClassifierTest, self).setUp()
    components = [Component(info['component'], info['dirs'],
                            info.get('function'), info.get('team'))
                  for info in COMPONENT_CONFIG['component_info']]
    # Only construct the classifier once, rather than making a new one every
    # time we call a method on it.
    self.classifier = ComponentClassifier(
        components, COMPONENT_CONFIG['top_n'], _MOCK_REPO_TO_DEP_PATH)

  def testClassifyStackFrameEmptyFrame(self):
    """Tests that ``ClassifyStackFrame`` returns None for empty frame."""
    frame = StackFrame(0, None, 'func', 'comp1/a.cc', 'src/comp1/a.cc', [2])
    self.assertIsNone(self.classifier.ClassifyStackFrame(frame))

    frame = StackFrame(0, 'src/', 'func', None, 'src/comp1/a.cc', [2])
    self.assertIsNone(self.classifier.ClassifyStackFrame(frame))

  def testClassifyCallStack(self):
    """Tests ``ClassifyCallStack`` method."""
    callstack = CallStack(
        0, [StackFrame(0, 'src/', 'func', 'comp1/a.cc', 'src/comp1/a.cc', [2],
                       repo_url='https://chromium.git')])
    self.assertEqual(self.classifier.ClassifyCallStack(callstack),
                     ['Comp1>Dummy'])

    callstack = CallStack(
        0, [StackFrame(0, 'dummy/', 'no_func', 'comp2/a.cc',
                       'dummy/comp2.cc', [32], repo_url='dummy_url')])
    self.assertEqual(self.classifier.ClassifyCallStack(callstack), [])

    crash_stack = CallStack(0, frame_list=[
        StackFrame(0, 'src/', 'func', 'comp1/a.cc', 'src/comp1/a.cc', [2],
                   repo_url='https://chromium.git'),
        StackFrame(1, 'src/', 'ff', 'comp1/a.cc', 'src/comp1/a.cc', [21],
                   repo_url='https://chromium.git'),
        StackFrame(2, 'src/', 'func2', 'comp2/b.cc', 'src/comp2/b.cc', [8],
                   repo_url='https://chromium.git')])

    self.assertEqual(self.classifier.ClassifyCallStack(crash_stack),
                     ['Comp1>Dummy', 'Comp2>Dummy'])

  def testMergeComponents(self):
    """Tests ``MergeComponents`` merge components with the same hierarchy."""
    components1 = ['A', 'A>B>C', 'A>B', 'E>F', 'G>H>I', 'G>H']
    merged_components1 = MergeComponents(components1)
    expected_components1 = ['A>B>C', 'E>F', 'G>H>I']
    self.assertListEqual(merged_components1, expected_components1)

    components2 = ['A', 'AB>C', 'AB>E', 'AB>ED']
    merged_components2 = MergeComponents(components2)
    expected_components2 = ['A', 'AB>C', 'AB>E', 'AB>ED']
    self.assertListEqual(merged_components2, expected_components2)

    components3 = ['A', 'A>B', 'A>C']
    merged_components3 = MergeComponents(components3)
    expected_components3 = ['A>B', 'A>C']
    self.assertListEqual(merged_components3, expected_components3)

  def testMatchComponents(self):
    """Tests classifier matches the component with longest directory path."""
    components = [
        Component('Blink>JavaScript', ['src/v8', 'src/v8/src/base/blabla...'],
                  None, None),
        Component('Blink>JavaScript>GC', ['src/v8/src/heap'], None, None)]

    classifier = ComponentClassifier(components, 3, _MOCK_REPO_TO_DEP_PATH)
    self.assertEqual(classifier.ClassifyFilePath('src/v8/src/heap/a.cc'),
                     'Blink>JavaScript>GC')

  def testClassifyTouchedFile(self):
    """Tests ``ClassifyTouchedFile`` method."""
    touched_file = FileChangeInfo(ChangeType.MODIFY, 'comp1/a.cc', 'comp1/b.cc')
    self.assertEqual(self.classifier.ClassifyTouchedFile('src', touched_file),
                     'Comp1>Dummy')

  def testClassifyRepoUrl(self):
    """Tests ``ClassifyRepoUrl`` method."""
    components = [
        Component('Blink>JavaScript', ['src/v8', 'src/v8/src/base/blabla...'],
                  None, None)]

    classifier = ComponentClassifier(components, 3, _MOCK_REPO_TO_DEP_PATH)
    self.assertEqual(['Blink>JavaScript'],
                     classifier.ClassifyRepoUrl('https://chromium.v8.git'))
