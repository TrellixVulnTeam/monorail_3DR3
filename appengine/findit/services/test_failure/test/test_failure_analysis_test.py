# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from libs import analysis_status
from libs.gitiles.diff import ChangeType
from model import analysis_approach_type
from model.base_build_model import BaseBuildModel
from model.wf_analysis import WfAnalysis
from services import build_failure_analysis
from services import ci_failure
from services import deps
from services import git
from services import monitoring
from services import step_util
from services.parameters import TestFailureInfo
from services.parameters import TestHeuristicAnalysisOutput
from services.parameters import TestHeuristicAnalysisParameters
from services.parameters import TestHeuristicResult
from services.test.build_failure_analysis_test import ChangeLogFromDict
from services.test_failure import ci_test_failure
from services.test_failure import extract_test_signal
from services.test_failure import test_failure_analysis
from waterfall.test import wf_testcase

SAMPLE_HEURISTIC_RESULT = {
    'failures': [
        {
            'step_name':
                'a',
            'first_failure':
                98,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    'modified f99_2.cc (and it was in log)': 2,
                },
            }],
        },
        {
            'step_name':
                'b',
            'first_failure':
                98,
            'last_pass':
                96,
            'supported':
                True,
            'suspected_cls': [
                {
                    'build_number': 97,
                    'repo_name': 'chromium',
                    'revision': 'r97_1',
                    'commit_position': None,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    },
                },
                {
                    'build_number': 98,
                    'repo_name': 'chromium',
                    'revision': 'r98_1',
                    'commit_position': None,
                    'url': None,
                    'score': 4,
                    'hints': {
                        'modified f98.cc[123, 456] (and it was in log)': 4,
                    },
                }
            ],
            'tests': [
                {
                    'test_name':
                        'Unittest1.Subtest1',
                    'first_failure':
                        98,
                    'last_pass':
                        97,
                    'suspected_cls': [{
                        'build_number': 97,
                        'repo_name': 'chromium',
                        'revision': 'r97_1',
                        'commit_position': None,
                        'url': None,
                        'score': 5,
                        'hints': {
                            'added x/y/f99_1.cc (and it was in log)': 5,
                        },
                    }]
                },
                {
                    'test_name':
                        'Unittest2.Subtest1',
                    'first_failure':
                        98,
                    'last_pass':
                        97,
                    'suspected_cls': [{
                        'build_number': 98,
                        'repo_name': 'chromium',
                        'revision': 'r98_1',
                        'commit_position': None,
                        'url': None,
                        'score': 4,
                        'hints': {
                            ('modified f98.cc[123] '
                             '(and it was in log)'): 4,
                        },
                    }]
                },
                {
                    'test_name':
                        'Unittest3.Subtest2',
                    'first_failure':
                        98,
                    'last_pass':
                        96,
                    'suspected_cls': [{
                        'build_number': 98,
                        'repo_name': 'chromium',
                        'revision': 'r98_1',
                        'commit_position': None,
                        'url': None,
                        'score': 4,
                        'hints': {
                            ('modified f98.cc[456] '
                             '(and it was in log)'): 4,
                        },
                    }]
                },
                {
                    'test_name': 'Unittest3.Subtest3',
                    'first_failure': 98,
                    'last_pass': 96,
                    'suspected_cls': []
                }
            ]
        }
    ]
}


class TestFailureAnalysisTest(wf_testcase.WaterfallTestCase):

  def testAnalyzeTestFailureTestLevel(self):
    failure_info = {
        'failed': True,
        'chromium_revision': 'r99_2',
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.TEST,
        'failed_steps': {
            'a': {
                'current_failure': 99,
                'first_failure': 98,
                'supported': True
            },
            'b': {
                'current_failure':
                    99,
                'first_failure':
                    98,
                'last_pass':
                    96,
                'supported':
                    True,
                'list_isolated_data': [{
                    'isolatedserver': 'https://isolateserver.appspot.com',
                    'namespace': 'default-gzip',
                    'digest': 'isolatedhashabctest-223'
                }],
                'tests': {
                    'Unittest1.Subtest1': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 97
                    },
                    'Unittest2.Subtest1': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 97
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 96
                    },
                    'Unittest3.Subtest3': {
                        'current_failure': 99,
                        'first_failure': 98,
                        'last_pass': 96
                    }
                }
            },
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            },
            97: {
                'blame_list': ['r97_1'],
            },
            96: {
                'blame_list': ['r96_1', 'r96_2'],
            },
        }
    }
    change_logs = {
        'r99_1':
            ChangeLogFromDict({
                'revision':
                    'r99_1',
                'touched_files': [{
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },],
                'author': {
                    'email': 'author@abc.com'
                }
            }),
        'r99_2':
            ChangeLogFromDict({
                'revision':
                    'r99_2',
                'touched_files': [{
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },],
                'author': {
                    'email': 'author@abc.com'
                }
            }),
        'r98_1':
            ChangeLogFromDict({
                'revision':
                    'r98_1',
                'touched_files': [{
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },],
                'author': {
                    'email': 'author@abc.com'
                }
            }),
        'r97_1':
            ChangeLogFromDict({
                'revision':
                    'r97_1',
                'touched_files': [
                    {
                        'change_type': ChangeType.ADD,
                        'old_path': '/dev/null',
                        'new_path': 'x/y/f99_1.cc'
                    },
                    {
                        'change_type': ChangeType.MODIFY,
                        'old_path': 'a/b/f99_1.cc',
                        'new_path': 'a/b/f99_1.cc'
                    },
                ],
                'author': {
                    'email': 'author@abc.com'
                }
            }),
        'r96_1':
            ChangeLogFromDict({
                'revision':
                    'r96_1',
                'touched_files': [{
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f96_1.cc',
                    'new_path': 'a/b/f96_1.cc'
                },],
                'author': {
                    'email': 'author@abc.com'
                }
            }),
    }
    deps_info = {}
    failure_signals_json = {
        'a': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
        },
        'b': {
            'files': {
                'x/y/f99_1.cc': [],
                'y/z/f98.cc': [123, 456],
            },
            'tests': {
                'Unittest1.Subtest1': {
                    'files': {
                        'x/y/f99_1.cc': [],
                    },
                },
                'Unittest2.Subtest1': {
                    'files': {
                        'y/z/f98.cc': [123],
                    },
                },
                'Unittest3.Subtest2': {
                    'files': {
                        'y/z/f98.cc': [456],
                    },
                }
            }
        }
    }

    def MockGetChangedLines(repo_info, touched_file, line_numbers, _):
      # Only need line_numbers, ignoring the first two parameters.
      del repo_info, touched_file
      if line_numbers:
        return line_numbers

    self.mock(build_failure_analysis, '_GetChangedLinesForChromiumRepo',
              MockGetChangedLines)

    expected_suspected_cl = [
        {
            'repo_name': 'chromium',
            'revision': 'r99_2',
            'commit_position': None,
            'url': None,
            'failures': {
                'a': []
            },
            'top_score': 2
        },
        {
            'repo_name': 'chromium',
            'revision': 'r97_1',
            'commit_position': None,
            'url': None,
            'failures': {
                'b': ['Unittest1.Subtest1']
            },
            'top_score': 5
        },
        {
            'repo_name': 'chromium',
            'revision': 'r98_1',
            'commit_position': None,
            'url': None,
            'failures': {
                'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
            },
            'top_score': 4
        },
    ]

    analysis_result, suspected_cls = (
        test_failure_analysis.AnalyzeTestFailure(
            TestFailureInfo.FromSerializable(failure_info), change_logs,
            deps_info, failure_signals_json))

    self.assertEqual(SAMPLE_HEURISTIC_RESULT, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  def testAnalyzeTestFailureForUnsupportedStep(self):
    failure_info = {
        'master_name': 'master1',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.TEST,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'unsupported_step1': {
                'current_failure': 99,
                'first_failure': 98,
                'supported': False,
            },
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            },
        }
    }
    change_logs = {}
    deps_info = {}
    failure_signals_json = {
        'not_supported': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
        }
    }
    expected_analysis_result = {
        'failures': [{
            'step_name': 'unsupported_step1',
            'supported': False,
            'first_failure': 98,
            'last_pass': None,
            'suspected_cls': [],
        },]
    }

    analysis_result, suspected_cls = (
        test_failure_analysis.AnalyzeTestFailure(
            TestFailureInfo.FromSerializable(failure_info), change_logs,
            deps_info, failure_signals_json))
    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual([], suspected_cls)

  def testAnalyzeTestFailureNoSignal(self):
    self.assertEqual(({
        'failures': []
    }, []), test_failure_analysis.AnalyzeTestFailure({}, {}, {}, {}))

  @mock.patch.object(
      extract_test_signal,
      'ExtractSignalsForTestFailure',
      return_value='signals')
  @mock.patch.object(git, 'PullChangeLogs', return_value={})
  @mock.patch.object(deps, 'ExtractDepsInfo', return_value={})
  @mock.patch.object(
      test_failure_analysis,
      'AnalyzeTestFailure',
      return_value=(SAMPLE_HEURISTIC_RESULT, []))
  @mock.patch.object(build_failure_analysis,
                     'SaveAnalysisAfterHeuristicAnalysisCompletes')
  @mock.patch.object(build_failure_analysis, 'SaveSuspectedCLs')
  @mock.patch.object(ci_test_failure, 'CheckFirstKnownFailureForSwarmingTests')
  @mock.patch.object(test_failure_analysis,
                     'RecordTestFailureAnalysisStateChange')
  @mock.patch.object(ci_failure, 'CheckForFirstKnownFailure')
  def testHeuristicAnalysisForTest(self, mock_failure_info, mock_mon, *_):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.COMPILE,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'test': {
                'current_failure': 99,
                'first_failure': 98,
                'supported': True,
            }
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            }
        }
    }

    mock_failure_info.return_value = TestFailureInfo.FromSerializable(
        failure_info)
    WfAnalysis.Create('m', 'b', 99).put()
    heuristic_params = TestHeuristicAnalysisParameters(
        failure_info=TestFailureInfo.FromSerializable(failure_info),
        build_completed=True)
    result = test_failure_analysis.HeuristicAnalysisForTest(heuristic_params)
    expected_result = {
        'failure_info': failure_info,
        'heuristic_result': SAMPLE_HEURISTIC_RESULT
    }
    self.assertEqual(
        TestHeuristicAnalysisOutput.FromSerializable(expected_result), result)
    mock_mon.assert_called_once_with('m', 'b', analysis_status.COMPLETED,
                                     analysis_approach_type.HEURISTIC)

  def testUpdateAnalysisResult(self):
    analysis_result = {
        'failures': [
            {
                'step_name': 'another_step1',
                'flaky': True
            },
            {
                'tests': [
                    {
                        'last_pass': 123,
                        'first_failure': 123,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test1'
                    },
                    {
                        'last_pass': 123,
                        'first_failure': 123,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test2'
                    },
                    {
                        'last_pass': 123,
                        'first_failure': 123,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test3'
                    },
                ],
                'step_name':
                    'browser_tests on platform'
            },
            {
                'step_name': 'another_step2'
            },
        ]
    }

    flaky_failures = {
        'browser_tests on platform': ['TestSuite1.test1', 'TestSuite1.test2']
    }

    updated_result, all_flaked = (
        test_failure_analysis.UpdateAnalysisResultWithFlakeInfo(
            analysis_result, flaky_failures))

    expected_result = {
        'failures': [
            {
                'step_name': 'another_step1',
                'flaky': True
            },
            {
                'tests': [
                    {
                        'last_pass': 123,
                        'first_failure': 123,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test1',
                        'flaky': True
                    },
                    {
                        'last_pass': 123,
                        'first_failure': 123,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test2',
                        'flaky': True
                    },
                    {
                        'last_pass': 123,
                        'first_failure': 123,
                        'suspected_cls': [],
                        'test_name': 'TestSuite1.test3'
                    },
                ],
                'step_name':
                    'browser_tests on platform',
                'flaky':
                    False
            },
            {
                'step_name': 'another_step2'
            },
        ]
    }

    self.assertFalse(all_flaked)
    self.assertEqual(expected_result, updated_result)

  def testUpdateAnalysisResultAllFlaky(self):
    analysis_result = {
        'failures': [{
            'tests': [
                {
                    'last_pass': 123,
                    'first_failure': 123,
                    'suspected_cls': [],
                    'test_name': 'TestSuite1.test1'
                },
                {
                    'last_pass': 123,
                    'first_failure': 123,
                    'suspected_cls': [],
                    'test_name': 'TestSuite1.test2'
                },
            ],
            'step_name':
                'browser_tests on platform'
        }]
    }

    flaky_failures = {
        'browser_tests on platform': ['TestSuite1.test1', 'TestSuite1.test2']
    }

    updated_result, all_flaked = (
        test_failure_analysis.UpdateAnalysisResultWithFlakeInfo(
            analysis_result, flaky_failures))

    expected_result = {
        'failures': [{
            'tests': [
                {
                    'last_pass': 123,
                    'first_failure': 123,
                    'suspected_cls': [],
                    'test_name': 'TestSuite1.test1',
                    'flaky': True
                },
                {
                    'last_pass': 123,
                    'first_failure': 123,
                    'suspected_cls': [],
                    'test_name': 'TestSuite1.test2',
                    'flaky': True
                },
            ],
            'step_name':
                'browser_tests on platform',
            'flaky':
                True
        }]
    }

    self.assertTrue(all_flaked)
    self.assertEqual(expected_result, updated_result)

  def testUpdateAnalysisResultOnlyStep(self):
    analysis_result = {'failures': [{'step_name': 'another_step1'}]}

    flaky_failures = {
        'browser_tests on platform': ['TestSuite1.test1', 'TestSuite1.test2']
    }

    _, all_flaked = (
        test_failure_analysis.UpdateAnalysisResultWithFlakeInfo(
            analysis_result, flaky_failures))

    self.assertFalse(all_flaked)

  def testGetFirstTimeFailedSteps(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': 'm/b/99',
            'test2': 'm/b/100'
        },
        'non_swarming': 'm/b/100',
        'step2': {
            'test3': 'm/b/99'
        },
        'step3': {
            'test4': 'm/b/100',
            'test5': 'm/b/98'
        }
    }
    analysis.put()

    self.assertItemsEqual(['step1', 'step3'],
                          test_failure_analysis.GetFirstTimeFailedSteps(
                              master_name, builder_name, build_number))

  def testGetsFirstFailureAtTestLevelNoAnalysis(self):
    result = (
        test_failure_analysis.GetsFirstFailureAtTestLevel(
            'm', 'b', 1, TestFailureInfo.FromSerializable({}), False))
    self.assertEqual(result, {})

  def testGetsFirstFailureAtTestLevelNoFailureResultMap(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    WfAnalysis.Create(master_name, builder_name, build_number).put()

    failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'chromium_revision': None,
        'builds': {
            2: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 2,
                        'last_pass': 1,
                        'base_test_name': 'Unittest2.Subtest1'
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                },
                'supported': True
            },
            'a_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'supported': True
            }
        },
        'failure_type': failure_type.TEST
    }

    expected_result = {'abc_test': ['Unittest2.Subtest1']}
    expected_failure_result_map = {
        'abc_test': {
            'Unittest2.Subtest1':
                BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                              build_number),
            'Unittest3.Subtest2':
                BaseBuildModel.CreateBuildKey(master_name, builder_name, 1)
        }
    }

    result = (
        test_failure_analysis.GetsFirstFailureAtTestLevel(
            master_name, builder_name, build_number,
            TestFailureInfo.FromSerializable(failure_info), False))
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)

    self.assertEqual(result, expected_result)
    self.assertEqual(analysis.failure_result_map, expected_failure_result_map)

  def testGetsFirstFailureAtTestLevel(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'a_tests': {'Unittest1.Subtest1': 'm/b/1'}}
    analysis.put()

    failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'chromium_revision': None,
        'builds': {
            2: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 2,
                        'last_pass': 1,
                        'base_test_name': 'Unittest2.Subtest1'
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                },
                'supported': True
            },
            'a_tests': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest1.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                },
                'supported': True
            }
        },
        'failure_type': failure_type.TEST
    }

    expected_result = {'abc_test': ['Unittest2.Subtest1']}
    result = (
        test_failure_analysis.GetsFirstFailureAtTestLevel(
            master_name, builder_name, build_number,
            TestFailureInfo.FromSerializable(failure_info), False))
    self.assertEqual(result, expected_result)

  def testGetsFirstFailureAtTestLevelForRerun(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 2
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_result_map = {'a_tests': {'Unittest1.Subtest1': 'm/b/2'}}
    analysis.put()

    failure_info = {
        'failed': True,
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 2,
        'chromium_revision': None,
        'builds': {
            2: {
                'blame_list': [],
                'chromium_revision': None
            }
        },
        'failed_steps': {
            'abc_test': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest2.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 2,
                        'last_pass': 1,
                        'base_test_name': 'Unittest2.Subtest1'
                    },
                    'Unittest3.Subtest2': {
                        'current_failure': 2,
                        'first_failure': 1,
                        'last_pass': 0,
                        'base_test_name': 'Unittest3.Subtest2'
                    }
                },
                'supported': True
            },
            'a_tests': {
                'current_failure': 2,
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'Unittest1.Subtest1': {
                        'current_failure': 2,
                        'first_failure': 2,
                        'last_pass': 1,
                        'base_test_name': 'Unittest1.Subtest1'
                    }
                },
                'supported': False
            }
        },
        'failure_type': failure_type.TEST
    }

    expected_result = {'abc_test': ['Unittest2.Subtest1']}
    result = (
        test_failure_analysis.GetsFirstFailureAtTestLevel(
            master_name, builder_name, build_number,
            TestFailureInfo.FromSerializable(failure_info), True))
    self.assertEqual(result, expected_result)

  @mock.patch.object(test_failure_analysis, 'UpdateAnalysisResultWithFlakeInfo')
  def testUpdateAnalysisWithFlakeInfoNoFlaky(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 31
    test_failure_analysis.UpdateAnalysisWithFlakesFoundBySwarmingReruns(
        master_name, builder_name, build_number, {})
    self.assertFalse(mock_fn.called)

  @mock.patch.object(test_failure_analysis, 'UpdateAnalysisResultWithFlakeInfo')
  def testUpdateAnalysisWithFlakeInfoNoAnalysisResult(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 32
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    test_failure_analysis.UpdateAnalysisWithFlakesFoundBySwarmingReruns(
        master_name, builder_name, build_number, {'a': ['b']})
    self.assertFalse(mock_fn.called)

  @mock.patch.object(test_failure_analysis, 'UpdateAnalysisResultWithFlakeInfo')
  def testUpdateAnalysisWithFlakeInfoNoNewFlakes(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 33
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = {
        'failures': [{
            'step_name': 'a',
            'tests': [{
                'test_name': 'b'
            }, {
                'test_name': 'test2'
            }]
        }]
    }
    analysis.flaky_tests = {'a': ['b']}
    analysis.put()

    test_failure_analysis.UpdateAnalysisWithFlakesFoundBySwarmingReruns(
        master_name, builder_name, build_number, {'a': ['b']})
    self.assertFalse(mock_fn.called)

  def testUpdateAnalysisWithFlakeInfo(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 34
    flaky_tests = {'a_test': ['test1'], 'b_test': ['test1']}

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = {
        'failures': [{
            'step_name': 'a_test',
            'tests': [{
                'test_name': 'test1'
            }, {
                'test_name': 'test2'
            }]
        }, {
            'step_name': 'b_test',
            'tests': [{
                'test_name': 'test1'
            }]
        }, {
            'step_name': 'c_test',
            'flaky': True
        }, {
            'step_name': 'd_test'
        }]
    }
    analysis.put()

    expected_result = {
        'failures': [
            {
                'step_name':
                    'a_test',
                'flaky':
                    False,
                'tests': [{
                    'test_name': 'test1',
                    'flaky': True
                }, {
                    'test_name': 'test2'
                }]
            },
            {
                'step_name': 'b_test',
                'flaky': True,
                'tests': [{
                    'test_name': 'test1',
                    'flaky': True
                }]
            },
            {
                'step_name': 'c_test',
                'flaky': True
            },
            {
                'step_name': 'd_test'
            },
        ]
    }

    test_failure_analysis.UpdateAnalysisWithFlakesFoundBySwarmingReruns(
        master_name, builder_name, build_number, flaky_tests)
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_result, analysis.result)
    self.assertEqual(flaky_tests, analysis.flaky_tests)

  @mock.patch.object(monitoring, 'OnWaterfallAnalysisStateChange')
  def testRecordTestFailureAnalysisStateChangeNoStepName(self, mock_mon):
    test_failure_analysis.RecordTestFailureAnalysisStateChange(
        'm', 'b', analysis_status.COMPLETED, analysis_approach_type.HEURISTIC)
    mock_mon.assert_called_once_with(
        master_name='m',
        builder_name='b',
        failure_type='test',
        canonical_step_name='Unknown',
        isolate_target_name='Unknown',
        status='Completed',
        analysis_type='Heuristic')

  @mock.patch.object(
      step_util, 'LegacyGetCanonicalStepName', return_value='step3')
  def testGetSuspectedCLsWithFailures(self, _):
    heuristic_result = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [],
            },
            {
                'step_name': 'step2',
                'suspected_cls': [
                    {
                        'revision': 'r1',
                    },
                    {
                        'revision': 'r2',
                    },
                ],
            },
            {
                'step_name':
                    'step3',
                'suspected_cls': [{
                    'revision': 'r3',
                }],
                'tests': [
                    {
                        'test_name': 'super_test_1',
                        'suspected_cls': [{
                            'revision': 'abc'
                        }]
                    },
                    {
                        'test_name':
                            'super_test_2',
                        'suspected_cls': [{
                            'revision': 'def'
                        }, {
                            'revision': 'ghi'
                        }]
                    },
                ]
            }
        ]
    }
    expected_suspected_revisions = [['step2', 'r1', None],
                                    ['step2', 'r2', None],
                                    ['step3', 'abc', 'super_test_1'],
                                    ['step3', 'def', 'super_test_2'],
                                    ['step3', 'ghi', 'super_test_2']]
    self.assertEqual(
        expected_suspected_revisions,
        sorted(
            test_failure_analysis.GetSuspectedCLsWithFailures(
                'm', 'b', 123,
                TestHeuristicResult.FromSerializable(heuristic_result))))

  def testGetSuspectedCLsWithTestFailuresNoHeuristicResult(self):
    heuristic_result = TestHeuristicResult.FromSerializable({})
    expected_suspected_revisions = []
    self.assertEqual(
        expected_suspected_revisions,
        sorted(
            test_failure_analysis.GetSuspectedCLsWithFailures(
                'm', 'b', 123, heuristic_result)))
