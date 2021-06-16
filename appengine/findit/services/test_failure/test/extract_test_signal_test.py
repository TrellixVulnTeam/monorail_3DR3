# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import os

from libs.test_results import test_results_util
from model.wf_analysis import WfAnalysis
from model.wf_step import WfStep
from services import extract_signal
from services import step_util
from services import swarmed_test_util
from services.parameters import TestFailureInfo
from services.test_failure import extract_test_signal
from waterfall.test import wf_testcase

_ABC_TEST_FAILURE_LOG = """
    ...
    ../../content/common/gpu/media/v4l2_video_encode_accelerator.cc:306:12:
    ...
"""

_FAILURE_SIGNALS = {
    'abc_test': {
        'files': {
            'content/common/gpu/media/v4l2_video_encode_accelerator.cc': [306]
        },
        'keywords': {}
    }
}

_FAILURE_INFO = {
    'master_name': 'm',
    'builder_name': 'b',
    'build_number': 123,
    'failed': True,
    'chromium_revision': 'a_git_hash',
    'failed_steps': {
        'abc_test': {
            'last_pass': 122,
            'current_failure': 123,
            'first_failure': 123,
            'supported': True
        }
    }
}


class ExtractTestSignalTest(wf_testcase.WaterfallTestCase):

  def _CreateAndSaveWfAnanlysis(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.put()

  def _GetGtestResultLog(self, file_name):
    file_name = os.path.join(
        os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'test',
        'data', file_name)
    with open(file_name, 'r') as f:
      return json.loads(f.read())

  @mock.patch.object(
      swarmed_test_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value=None)
  @mock.patch.object(
      step_util, 'GetWaterfallBuildStepLog', return_value=_ABC_TEST_FAILURE_LOG)
  def testBailOutForUnsupportedStep(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    supported_step_name = 'abc_test'
    unsupported_step_name = 'unsupported_step6'
    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            supported_step_name: {
                'last_pass': 122,
                'current_failure': 123,
                'first_failure': 123,
                'supported': True
            },
            unsupported_step_name: {
                'last_pass': 122,
                'current_failure': 123,
                'first_failure': 123,
                'supported': False
            }
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(failure_info), None)
    self.assertEqual(_FAILURE_SIGNALS, signals)

  def testGetSignalFromStepLogForBWT(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'blink_web_tests'

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'blink_web_tests': {
                'last_pass': 122,
                'current_failure': 123,
                'first_failure': 123,
                'supported': True
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.log_data = json.dumps({
        'fast/test.html':
            'dGhpcmRfcGFydHkvYmxpbmsvd2ViX3Rlc3RzL2Zhc3QvdGVzdC5odG1s'
    })
    step.isolated = True
    step.put()

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(failure_info), None)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual({
        'third_party/blink/web_tests/fast/test.html': []
    }, signals['blink_web_tests']['files'])

  @mock.patch.object(
      step_util, 'GetWaterfallBuildStepLog', return_value=_ABC_TEST_FAILURE_LOG)
  @mock.patch.object(swarmed_test_util,
                     'RetrieveShardedTestResultsFromIsolatedServer')
  # crbug.com/827693
  def disabled_testGetSignalFromStepLog(self, mock_gtest, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'

    # Mock both stdiolog and gtest json results to test whether Findit will
    # go to step log first when both logs exist.
    mock_gtest.return_value = self._GetGtestResultLog('m_b_123_abc_test.json')
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(_FAILURE_INFO), None)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    expected_files = {'a/b/u2s1.cc': [567], 'a/b/u3s2.cc': [110]}

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual(expected_files, signals['abc_test']['files'])

  @mock.patch.object(
      step_util, 'GetWaterfallBuildStepLog', return_value=_ABC_TEST_FAILURE_LOG)
  @mock.patch.object(swarmed_test_util,
                     'RetrieveShardedTestResultsFromIsolatedServer')
  def testGetSignalFromStepLogFlaky(self, mock_gtest, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    step_name = 'abc_test'

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 123,
                'current_failure': 124,
                'first_failure': 124,
                'supported': True,
            }
        }
    }

    mock_gtest.return_value = self._GetGtestResultLog('m_b_124_abc_test.json')
    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(failure_info), None)

    step = WfStep.Get(master_name, builder_name, build_number, step_name)

    self.assertIsNotNone(step)
    self.assertIsNotNone(step.log_data)
    self.assertEqual('flaky', step.log_data)
    self.assertEqual({}, signals['abc_test']['files'])

  @mock.patch.object(
      step_util,
      'GetWaterfallBuildStepLog',
      return_value='If used, test should fail!')
  def testWfStepStdioLogAlreadyDownloaded(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'abc_test'
    step = WfStep.Create(master_name, builder_name, build_number, step_name)
    step.log_data = _ABC_TEST_FAILURE_LOG
    step.put()

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(_FAILURE_INFO), None)

    self.assertEqual(_FAILURE_SIGNALS, signals)

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNone(analysis.signals)

  def testExtractSignalsForTestFailureForTestsFlaky(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'supported': True,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, build_number, 'abc_test')
    step.isolated = True
    step.log_data = 'flaky'
    step.put()

    expected_signals = {'abc_test': {'files': {}, 'tests': {}}}

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(failure_info), None)
    self.assertEqual(expected_signals, signals)

  def testExtractSignalsForTestFailureForTests(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'supported': True,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, build_number, 'abc_test')
    step.isolated = True
    step.log_data = json.dumps({
        'Unittest2.Subtest1':
            base64.b64encode(
                'ERROR:x_test.cc:1234\na/b/u2s1.cc:567: Failure\nERROR:[2]: '
                '2594735000 bogo-microseconds\nERROR:x_test.cc:1234\na/b/'
                'u3s2.cc:123: Failure\n'),
        'Unittest3.Subtest2':
            base64.b64encode(
                'a/b/u3s2.cc:110: Failure\na/b/u3s2.cc:123: Failure\n')
    })
    step.put()

    expected_signals = {
        'abc_test': {
            'files': {
                'a/b/u2s1.cc': [567],
                'a/b/u3s2.cc': [123, 110]
            },
            'tests': {
                'Unittest2.Subtest1': {
                    'files': {
                        'a/b/u2s1.cc': [567],
                        'a/b/u3s2.cc': [123]
                    },
                    'keywords': {}
                },
                'Unittest3.Subtest2': {
                    'files': {
                        'a/b/u3s2.cc': [110, 123]
                    },
                    'keywords': {}
                }
            }
        }
    }

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(failure_info), None)
    self.assertEqual(expected_signals, signals)

  def testLogNotJsonLoadable(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'supported': True,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    step = WfStep.Create(master_name, builder_name, build_number, 'abc_test')
    step.isolated = True
    step.log_data = "Not Json loadable"
    step.put()

    self._CreateAndSaveWfAnanlysis(master_name, builder_name, build_number)

    expected_signals = {'abc_test': {'files': {}, 'tests': {}}}

    signals = extract_test_signal.ExtractSignalsForTestFailure(
        TestFailureInfo.FromSerializable(failure_info), None)
    self.assertEqual(expected_signals, signals)

  @mock.patch.object(
      swarmed_test_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value=None)
  @mock.patch.object(extract_signal, 'GetStdoutLog', return_value=None)
  # crbug.com/1056607
  def disabled_testExtractSignalsForTestFailureNoFailureLog(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'supported': True,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    self.assertEqual({},
                     extract_test_signal.ExtractSignalsForTestFailure(
                         TestFailureInfo.FromSerializable(failure_info), None))

  @mock.patch.object(
      swarmed_test_util,
      'RetrieveShardedTestResultsFromIsolatedServer',
      return_value='merged_test_results')
  @mock.patch.object(
      test_results_util, 'GetTestResultObject', return_value=None)
  @mock.patch.object(extract_signal, 'GetStdoutLog', return_value='log')
  # crbug.com/827693
  def disabled_testExtractSignalsForTestFailureNoTestResult(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    failure_info = {
        'master_name': master_name,
        'builder_name': builder_name,
        'build_number': build_number,
        'failed': True,
        'chromium_revision': 'a_git_hash',
        'failed_steps': {
            'abc_test': {
                'last_pass': 221,
                'current_failure': 223,
                'first_failure': 222,
                'supported': True,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 223,
                        'first_failure': 222,
                        'last_pass': 221
                    }
                }
            }
        }
    }

    expected_signals = {'abc_test': {'files': {}, 'keywords': {}}}
    self.assertEqual(
        expected_signals,
        extract_test_signal.ExtractSignalsForTestFailure(
            TestFailureInfo.FromSerializable(failure_info), None))
