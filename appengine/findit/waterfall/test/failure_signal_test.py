# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from waterfall.failure_signal import FailureSignal


class FailureSignalTest(unittest.TestCase):

  def testAddFileWithLineNumber(self):
    signal = FailureSignal()
    signal.AddFile('a.cc', 1)
    signal.AddFile('a.cc', 11)
    signal.AddFile('a.cc', 11)
    self.assertEqual({'a.cc': [1, 11]}, signal.files)

  def testAddFileWithoutLineNumber(self):
    signal = FailureSignal()
    signal.AddFile('a.cc', None)
    self.assertEqual({'a.cc': []}, signal.files)

  def testAddKeyWord(self):
    signal = FailureSignal()
    signal.AddKeyword(' ')
    signal.AddKeyword('a')
    signal.AddKeyword('b')
    signal.AddKeyword('a')
    self.assertEqual({'a': 2, 'b': 1}, signal.keywords)

  def testAddTarget(self):
    signal = FailureSignal()
    signal.AddTarget({'target': 'a.exe'})
    signal.AddTarget({'target': 'b.o', 'source': 'b.cpp'})
    signal.AddTarget({'target': 'b.o', 'source': 'b.cpp'})
    self.assertEqual([{
        'target': 'a.exe'
    }, {
        'target': 'b.o',
        'source': 'b.cpp'
    }], signal.failed_targets)

  def testAddEdge(self):
    signal = FailureSignal()
    signal.AddEdge({'rule': "CXX",'output_nodes': ['b.o'],
                    'dependencies': ['b.h']})
    signal.AddEdge({'rule': "CXX",'output_nodes': ['a.o', 'aa.o'],
                    'dependencies': ['a.h', 'a.c']})
    signal.AddEdge({'rule': "CXX",'output_nodes': ['a.o', 'aa.o'],
                    'dependencies': ['a.h', 'a.c']})
    self.assertEqual([{
        "rule": 'CXX',
        "output_nodes": ['b.o'],
        'dependencies': ['b.h']
    }, {
        'rule': 'CXX',
        'output_nodes': ['a.o', 'aa.o'],
        'dependencies': ['a.h', 'a.c']
    }], signal.failed_edges)

  def testToFromDict(self):
    data = {
        'files': {
            'a.cc': [2],
            'd.cc': []
        },
        'keywords': {
            'k1': 3
        },
        'failed_output_nodes': [
            'obj/path/to/file.o',
        ],
        'failed_edges': [{
            'rule': 'CXX',
            'output_nodes': ['a.o', 'aa.o'],
            'dependencies': ['a.h', 'a.c']
        }]
    }
    signal = FailureSignal.FromDict(data)
    self.assertEqual(data, signal.ToDict())

  def testToFromDictWithFailedTargets(self):
    data = {
        'files': {
            'a.cc': [2],
            'd.cc': []
        },
        'keywords': {
            'k1': 3
        },
        'failed_targets': [{
            'target': 'a.o',
            'source': 'b/a.cc'
        }],
    }
    signal = FailureSignal.FromDict(data)
    self.assertEqual(data, signal.ToDict())

  def testMergeFrom(self):
    test_signals = [
        {
            'files': {
                'a.cc': [2],
                'd.cc': []
            },
            'keywords': {},
            'failed_targets': [{
                'target': 'a.o',
                'source': 'a.cc'
            }, {
                'target': 'b.o',
                'source': 'b.cc'
            }],
            'failed_edges': [{
                'rule': 'CXX',
                'output_nodes': ['a.o', 'aa.o'],
                'dependencies': ['a.h', 'a.c']
            }]
        },
        {
            'files': {
                'a.cc': [2, 3, 4],
                'b.cc': [],
                'd.cc': [1]
            },
            'keywords': {},
            'failed_targets': [{
                'target': 'a.o',
                'source': 'a.cc'
            }, {
                'target': 'c.exe'
            }],
            'failed_edges': [{
                'rule': 'LINK',
                'output_nodes': ['b.o'],
                'dependencies': []
            }]
        },
    ]
    step_signal = FailureSignal()

    for test_signal in test_signals:
      step_signal.MergeFrom(test_signal)

    expected_step_signal_files = {'a.cc': [2, 3, 4], 'd.cc': [1], 'b.cc': []}
    expected_step_failed_targets = [{
        'target': 'a.o',
        'source': 'a.cc'
    }, {
        'target': 'b.o',
        'source': 'b.cc'
    }, {
        'target': 'c.exe'
    }]
    expected_step_failed_edges = [{
        'rule': 'CXX',
        'output_nodes': ['a.o', 'aa.o'],
        'dependencies': ['a.h', 'a.c']
    }, {
        'rule': 'LINK',
        'output_nodes': ['b.o'],
        'dependencies': []
    }]
    self.assertEqual(expected_step_signal_files, step_signal.files)
    self.assertEqual(expected_step_failed_targets, step_signal.failed_targets)
    self.assertEqual(expected_step_failed_edges, step_signal.failed_edges)
