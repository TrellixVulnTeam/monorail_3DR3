# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from datetime import datetime
import mock

from common.constants import NO_BLAME_ACTION_ACCOUNTS
from common.waterfall import failure_type
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from libs import time_util
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import Contributor
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from pipelines.compile_failure.analyze_compile_failure_pipeline import (
    AnalyzeCompileFailureInput)
from services import build_failure_analysis
from services.parameters import BuildKey
from services.parameters import CompileFailureInfo
from services.parameters import TestFailedStep
from waterfall.failure_signal import FailureSignal
from waterfall.test import wf_testcase


def ChangeLogFromDict(data):
  touched_files = [
      FileChangeInfo.FromDict(touched_file)
      for touched_file in data.get('touched_files', [])
  ]

  author = Contributor(
      data.get('author', {}).get('name', 'author'),
      data.get('author', {}).get('email', 'email'),
      data.get('author', {}).get('time', 'time'))
  committer = Contributor(
      data.get('committer', {}).get('name', 'committer'),
      data.get('committer', {}).get('email', 'email'),
      data.get('committer', {}).get('time', 'time'))
  return ChangeLog(author, committer, data.get('revision'),
                   data.get('commit_position'), data.get('message'),
                   touched_files, data.get('commit_url'),
                   data.get('code_review_url'), data.get('reverted_revision'),
                   data.get('review_server_host'), data.get('review_change_id'))


class BuildFailureAnalysisTest(wf_testcase.WaterfallTestCase):

  def _MockGetChangeLog(self, revision):

    class MockChangeLog(object):

      def __init__(self, revision, touched_files, **kwargs):
        self.author = kwargs.get('author') or Contributor(
            'name',
            'email@chromium.org',
            # use revision as the date as well for testing purpose.
            datetime.strptime('Jun %s 04:35:32 2015' % revision,
                              '%b %d %H:%M:%S %Y'))
        self.touched_files = touched_files
        self.revision = revision

    MOCK_CHANGE_LOGS = {}
    MOCK_CHANGE_LOGS['1'] = MockChangeLog('1', [])
    MOCK_CHANGE_LOGS['2'] = MockChangeLog('2', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.ADD,
            'old_path': 'dev/null',
            'new_path': 'third_party/dep/f.cc'
        })
    ])
    MOCK_CHANGE_LOGS['3'] = MockChangeLog('3', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f.cc',
            'new_path': 'third_party/dep/f.cc'
        })
    ])
    MOCK_CHANGE_LOGS['4'] = MockChangeLog('4', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f2.cc',
            'new_path': 'third_party/dep/f2.cc'
        })
    ])
    MOCK_CHANGE_LOGS['5'] = MockChangeLog('5', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f3.cc',
            'new_path': 'third_party/dep/f3.cc'
        })
    ])
    MOCK_CHANGE_LOGS['6'] = MockChangeLog('6', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f.cc',
            'new_path': 'third_party/dep/f.cc'
        })
    ])
    MOCK_CHANGE_LOGS['7'] = MockChangeLog('7', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f.cc',
            'new_path': 'third_party/dep/f.cc'
        })
    ])
    MOCK_CHANGE_LOGS['8'] = MockChangeLog('8', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f.cc',
            'new_path': 'third_party/dep/f.cc'
        })
    ])
    MOCK_CHANGE_LOGS['9'] = MockChangeLog('9', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.DELETE,
            'old_path': 'third_party/dep/f.cc',
            'new_path': 'dev/null'
        })
    ])
    MOCK_CHANGE_LOGS['10'] = MockChangeLog('10', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f2.cc',
            'new_path': 'third_party/dep/f2.cc'
        })
    ])
    MOCK_CHANGE_LOGS['11'] = MockChangeLog('11', [
        FileChangeInfo.FromDict({
            'change_type': ChangeType.MODIFY,
            'old_path': 'third_party/dep/f2.cc',
            'new_path': 'third_party/dep/f2.cc'
        })
    ])

    return MOCK_CHANGE_LOGS.get(revision, MockChangeLog('12', []))

  def _MockGetChangeLogs(self, start_revision, end_revision):
    return [
        self._MockGetChangeLog(str(r))
        for r in range(int(start_revision) + 1,
                       int(end_revision) + 1)
    ]

  def _MockGetBlame(self, path, revision):
    if revision == '10' or revision == '11' or path == 'f_not_exist.cc':
      return None
    blame = Blame(revision, path)

    blame.AddRegions([
        Region(1, 2, '7', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 07, 04, 35, 32)),
        Region(3, 3, '5', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 05, 04, 35, 32)),
        Region(7, 1, '8', u'test2@chromium.org', u'test2@chromium.org',
               datetime(2015, 06, 8, 04, 35, 32)),
        Region(8, 1, '7', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 07, 21, 35, 32)),
        Region(9, 10, '12', u'test3@chromium.org', u'test3@chromium.org',
               datetime(2015, 06, 12, 04, 35, 32))
    ])
    return blame

  def testCheckNinjaDependencies(self):
    failed_edges = [{
        'dependencies': [
            'src/a/b/f1.cc', 'd/e/a2_test.cc', 'b/c/f2.cc', 'd/e/f3.h',
            'x/y/f4.py', 'f5_impl.cc'
        ]
    }]

    failure_signal = FailureSignal()
    failure_signal.failed_edges = failed_edges
    change_log_json = {
        'revision':
            '12',
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/b/f1.cc'
            },
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'd/e/a2.cc'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'a/b/c/f2.h',
                'new_path': 'a/b/c/f2.h'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'd/e/f3.h',
                'new_path': 'd/e/f3.h'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'x/y/f4.py',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'h/f5.h',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.RENAME,
                'old_path': 't/y/x.cc',
                'new_path': 's/z/x.cc'
            },
        ]
    }
    deps_info = {}

    justification = build_failure_analysis.CheckFiles(
        failure_signal, ChangeLogFromDict(change_log_json), deps_info, True)
    self.assertIsNotNone(justification)
    # The score is 2 because:
    # CL only touches dependencies
    self.assertEqual(2, justification['score'])

  def testCheckFilesAgainstSuspectedCL(self):
    failure_signal_json = {
        'files': {
            'src/a/b/f1.cc': [],
            'd/e/a2_test.cc': [],
            'b/c/f2.cc': [10, 20],
            'd/e/f3.h': [],
            'x/y/f4.py': [],
            'f5_impl.cc': []
        }
    }
    change_log_json = {
        'revision':
            '12',
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/b/f1.cc'
            },
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'd/e/a2.cc'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'a/b/c/f2.h',
                'new_path': 'a/b/c/f2.h'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'd/e/f3.h',
                'new_path': 'd/e/f3.h'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'x/y/f4.py',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'h/f5.h',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.RENAME,
                'old_path': 't/y/x.cc',
                'new_path': 's/z/x.cc'
            },
        ]
    }
    deps_info = {}

    justification = build_failure_analysis.CheckFiles(
        FailureSignal.FromDict(failure_signal_json),
        ChangeLogFromDict(change_log_json), deps_info)
    self.assertIsNotNone(justification)
    # The score is 15 because:
    # +5 added a/b/f1.cc (same file src/a/b/f1.cc in failure_signal log)
    # +1 added d/e/a2.cc (related file a2_test.cc in failure_signal log)
    # +1 modified b/c/f2.h (related file a/b/c/f2.cc in failure_signal log)
    # +2 modified d/e/f3.h (same file d/e/f3.h in failure_signal log)
    # +5 deleted x/y/f4.py (same file x/y/f4.py in failure_signal log)
    # +1 deleted h/f5.h (related file f5_impl.cc in failure_signal log)
    # +0 renamed t/y/x.cc -> s/z/x.cc (no related file in failure_signal log)
    self.assertEqual(15, justification['score'])

  def testCheckFilesAgainstUnrelatedCL(self):
    failure_signal_json = {'files': {'src/a/b/f.cc': [],}}
    change_log_json = {
        'revision':
            '12',
        'touched_files': [{
            'change_type': ChangeType.ADD,
            'old_path': '/dev/null',
            'new_path': 'a/d/f1.cc'
        },]
    }
    deps_info = {}

    justification = build_failure_analysis.CheckFiles(
        FailureSignal.FromDict(failure_signal_json),
        ChangeLogFromDict(change_log_json), deps_info)
    self.assertIsNone(justification)

  def _testCheckFileInDependencyRoll(self,
                                     file_path_in_log,
                                     rolls,
                                     expected_score,
                                     line_numbers,
                                     expected_hints=None):
    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)
    self.mock(CachedGitilesRepository, 'GetBlame', self._MockGetBlame)
    self.mock(CachedGitilesRepository, 'GetChangeLogs', self._MockGetChangeLogs)
    justification = build_failure_analysis._Justification()
    build_failure_analysis._CheckFileInDependencyRolls(
        file_path_in_log, rolls, justification, line_numbers)
    self.assertEqual(expected_score, justification.score)
    if expected_hints:
      self.assertEqual(expected_hints, dict(justification._hints))

  def testCheckFileInDependencyRollWhenUnrelatedDependencyIsRolled(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # An unrelated dependency was rolled to a new revision.
            'path': 'src/third_party/dep2',
            'repo_url': 'https://url_dep2',
            'old_revision': '6',
            'new_revision': '8',
        },
    ]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenRelatedDependencyIsRolled(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Dependency was rolled to a new revision.
            'path': 'src/third_party/dep',
            'repo_url': 'https://url_dep',
            'old_revision': '6',
            'new_revision': '8',
        },
    ]
    expected_score = 1
    expected_hints = {
        ('rolled dependency third_party/dep with changes in '
         'https://url_dep/+log/6..8?pretty=fuller (and f.cc was in log)'):
            1
    }

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None, expected_hints)

  def testCheckFileInDependencyRollWhenRelatedDependencyIsAdded(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Dependency was newly-added.
            'path': 'src/third_party/dep',
            'repo_url': 'https://url_dep',
            'old_revision': None,
            'new_revision': '9',
        },
    ]
    expected_score = 5

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenRelatedDependencyIsDeleted(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Dependency was deleted.
            'path': 'src/third_party/dep',
            'repo_url': 'https://url_dep',
            'old_revision': '7',
            'new_revision': None,
        },
    ]
    expected_score = 5

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenFileIsAddedWithinTheRoll(self):
    rolls = [
        {  # One region in blame.
            'path': 'src/third_party/dep',
            'repo_url': 'https://url_dep',
            'old_revision': '1',
            'new_revision': '2',
        }
    ]
    file_path_in_log = 'third_party/dep/f.cc'
    expected_score = 5
    expected_hints = {
        ('rolled dependency third_party/dep with changes in '
         'https://url_dep/+log/1..2?pretty=fuller '
         '(and f.cc(added) was in log)'):
            5
    }

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None, expected_hints)

  def testCheckFileInDependencyRollWhenFileIsAddedAndChangedWithinTheRoll(self):
    file_path_in_log = 'third_party/dep/f.cc'
    rolls = [
        {  # Multiple regions in blame, but they are all after old revision.
            'path': 'src/third_party/dep',
            'repo_url': 'https://url_dep',
            'old_revision': '1',
            'new_revision': '3',
        },
    ]
    expected_score = 5

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenFileIsNotTouchedWithinTheRoll(self):
    rolls = [{
        'path': 'src/third_party/dep',
        'repo_url': 'https://url_dep',
        'old_revision': '3',
        'new_revision': '5',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None)

  def testCheckFileInDependencyRollWhenLinesAreChangedWithinTheRoll(self):
    rolls = [{
        'path': 'src/third_party/dep',
        'repo_url': 'https://url_dep',
        'old_revision': '6',
        'new_revision': '8',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    line_numbers = [2, 7, 12]
    expected_score = 4
    expected_hints = {
        ('rolled dependency third_party/dep with changes in '
         'https://url_dep/+log/6..8?pretty=fuller '
         '(and f.cc[2, 7] was in log)'):
            4
    }

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers, expected_hints)

  def testCheckFileInDependencyRollWhenFileIsNotChanged(self):
    rolls = [{
        'path': 'src/third_party/dep',
        'repo_url': 'https://url_dep',
        'old_revision': '8',
        'new_revision': '9',
    }]
    file_path_in_log = 'third_party/dep/not_this_file.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFileInDependencyRollWhenFileIsDeleted(self):
    rolls = [{
        'path': 'src/third_party/dep',
        'repo_url': 'https://url_dep',
        'old_revision': '8',
        'new_revision': '10',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    expected_score = 5
    expected_hints = {
        ('rolled dependency third_party/dep with changes in '
         'https://url_dep/+log/8..10?pretty=fuller '
         '(and f.cc(deleted) was in log)'):
            5
    }

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        None, expected_hints)

  def testCheckFileInDependencyRollWhenFileIsModifiedWithoutBlame(self):
    rolls = [{
        'path': 'src/third_party/dep',
        'repo_url': 'https://url_dep',
        'old_revision': '10',
        'new_revision': '11',
    }]
    file_path_in_log = 'third_party/dep/f2.cc'
    line_numbers = [2, 7, 8]
    expected_score = 1

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFileInDependencyRollRolledDowngrade(self):
    rolls = [{
        'path': 'src/third_party/dep',
        'repo_url': 'https://url_dep',
        'old_revision': '8',
        'new_revision': '6',
    }]
    file_path_in_log = 'third_party/dep/f.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFileInDependencyRollFileNotExist(self):
    rolls = [{
        'path': 'src/third_party/dep',
        'repo_url': 'https://url_dep',
        'old_revision': '6',
        'new_revision': '8',
    }]
    file_path_in_log = 'third_party/dep/f_not_exist.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFileInDependencyRollOnV8(self):
    rolls = [{
        'path': 'src/v8',
        'repo_url': 'https://chromium.googlesource.com/v8/v8.git',
        'old_revision': '6',
        'new_revision': '8',
    }]
    file_path_in_log = 'v8/f.cc'
    line_numbers = [2, 7, 8]
    expected_score = 0

    self._testCheckFileInDependencyRoll(file_path_in_log, rolls, expected_score,
                                        line_numbers)

  def testCheckFilesAgainstDEPSRollWithUnrelatedLinesChanged(self):
    failure_signal_json = {'files': {'src/third_party/dep1/f.cc': [123],}}
    change_log_json = {
        'revision':
            '12',
        'touched_files': [{
            'change_type': ChangeType.MODIFY,
            'old_path': 'DEPS',
            'new_path': 'DEPS'
        },]
    }
    deps_info = {
        'deps_rolls': {
            '12': [{
                'path': 'src/third_party/dep1',
                'repo_url': 'https://url_dep1',
                'old_revision': '7',
                'new_revision': '9',
            },]
        }
    }
    self.mock(CachedGitilesRepository, 'GetChangeLog', self._MockGetChangeLog)
    self.mock(CachedGitilesRepository, 'GetChangeLogs', self._MockGetChangeLogs)
    self.mock(CachedGitilesRepository, 'GetBlame', self._MockGetBlame)
    justification = build_failure_analysis.CheckFiles(
        FailureSignal.FromDict(failure_signal_json),
        ChangeLogFromDict(change_log_json), deps_info)
    self.assertIsNotNone(justification)
    # The score is 1 because:
    # +1 rolled third_party/dep1/ and src/third_party/dep1/f.cc was in log.
    self.assertEqual(1, justification['score'])

  def testGetChangedLinesTrue(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '8'
    }
    touched_file = FileChangeInfo.FromDict({
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    })
    line_numbers = [2, 7, 8]
    commit_revision = '7'
    self.mock(CachedGitilesRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([2, 8], changed_line_numbers)

  def testGetChangedLinesDifferentRevision(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '9'
    }
    touched_file = FileChangeInfo.FromDict({
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    })
    line_numbers = [2, 7, 8]
    commit_revision = '9'
    self.mock(CachedGitilesRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([], changed_line_numbers)

  def testGetChangedLinesDifferentLine(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '8'
    }
    touched_file = FileChangeInfo.FromDict({
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    })
    line_numbers = [15]
    commit_revision = '7'
    self.mock(CachedGitilesRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([], changed_line_numbers)

  def testGetChangedLinesNoneBlame(self):
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': '10'
    }
    touched_file = FileChangeInfo.FromDict({
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    })
    line_numbers = [2, 7, 8]
    commit_revision = '7'
    self.mock(CachedGitilesRepository, 'GetBlame', self._MockGetBlame)
    changed_line_numbers = (
        build_failure_analysis._GetChangedLinesForChromiumRepo(
            repo_info, touched_file, line_numbers, commit_revision))

    self.assertEqual([], changed_line_numbers)

  def testCheckFileSameLineChanged(self):

    def MockGetChangedLines(*_):
      return [1, 3]

    self.mock(build_failure_analysis, '_GetChangedLinesForChromiumRepo',
              MockGetChangedLines)
    touched_file = FileChangeInfo.FromDict({
        'change_type': ChangeType.MODIFY,
        'old_path': 'a/b/c.cc',
        'new_path': 'a/b/c.cc'
    })
    file_path_in_log = 'a/b/c.cc'
    justification = build_failure_analysis._Justification()
    file_name_occurrences = {'c.cc': 1}
    line_numbers = [1, 3]
    repo_info = {
        'repo_url': 'https://chromium.googlesource.com/chromium/src.git',
        'revision': 'dummy_abcd1234'
    }
    commit_revision = 'dummy_1'
    build_failure_analysis._CheckFile(touched_file, file_path_in_log,
                                      justification, file_name_occurrences,
                                      line_numbers, repo_info, commit_revision)

    expected_justification = {
        'score': 4,
        'hints': {
            'modified c.cc[1, 3] (and it was in log)': 4
        }
    }
    self.assertEqual(expected_justification, justification.ToDict())

  def testGetResultAnalysisStatusFoundUntriaged(self):
    dummy_result = {
        'failures': [{
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
                'score': 1,
                'hints': {
                    'modified f99_2.cc (and it was in log)': 1,
                },
            }],
        }, {
            'step_name':
                'b',
            'first_failure':
                98,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': None,
                'score': 5,
                'hints': {
                    'added x/y/f99_1.cc (and it was in log)': 5,
                },
            }],
        }]
    }

    self.assertEqual(
        result_status.FOUND_UNTRIAGED,
        build_failure_analysis.GetResultAnalysisStatus(dummy_result))

  def testGetResultAnalysisStatusNoResult(self):
    self.assertIsNone(build_failure_analysis.GetResultAnalysisStatus(None))

  def testGetResultAnalysisStatusUnsupported(self):
    dummy_result = {
        'failures': [{
            'step_name': 'a',
            'first_failure': 98,
            'last_pass': None,
            'supported': False,
            'suspected_cls': [],
        }, {
            'step_name': 'b',
            'first_failure': 98,
            'last_pass': None,
            'supported': False,
            'suspected_cls': [],
        }]
    }

    self.assertEqual(
        result_status.UNSUPPORTED,
        build_failure_analysis.GetResultAnalysisStatus(dummy_result))

  def testGetResultAnalysisStatusNotFoundUntriaged(self):
    dummy_result = {
        'failures': [{
            'step_name': 'a',
            'first_failure': 98,
            'last_pass': None,
            'supported': True,
            'suspected_cls': [],
        }, {
            'step_name': 'b',
            'first_failure': 98,
            'last_pass': None,
            'supported': False,
            'suspected_cls': [],
        }]
    }

    self.assertEqual(
        result_status.NOT_FOUND_UNTRIAGED,
        build_failure_analysis.GetResultAnalysisStatus(dummy_result))

  def testGetSuspectedCLsWithOnlyCLInfo(self):
    suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r98_1',
        'commit_position': None,
        'url': None,
        'failures': {
            'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
        },
        'top_score': 4
    }]

    expected_new_suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r98_1',
        'commit_position': None,
        'url': None
    }]

    self.assertEqual(
        expected_new_suspected_cls,
        build_failure_analysis._GetSuspectedCLsWithOnlyCLInfo(suspected_cls))

  @mock.patch.object(
      build_failure_analysis,
      'GetResultAnalysisStatus',
      return_value=result_status.FOUND_UNTRIAGED)
  @mock.patch.object(
      build_failure_analysis, '_GetSuspectedCLsWithOnlyCLInfo', return_value=[])
  def testSaveAnalysisAfterHeuristicAnalysisCompletes(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 98
    analysis_result = {'result': {}}

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.start_time = datetime(2016, 06, 26, 23)
    analysis.put()

    build_failure_analysis.SaveAnalysisAfterHeuristicAnalysisCompletes(
        master_name, builder_name, build_number, analysis_result, [])

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testSaveSuspectedCLs(self):
    suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r98_1',
        'commit_position': None,
        'url': None,
        'failures': {
            'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
        },
        'top_score': 4
    }]
    master_name = 'm'
    builder_name = 'b'
    build_number = 98
    test_type = failure_type.TEST

    build_failure_analysis.SaveSuspectedCLs(
        suspected_cls, master_name, builder_name, build_number, test_type)

    suspected_cl = WfSuspectedCL.Get('chromium', 'r98_1')
    self.assertIsNotNone(suspected_cl)

  def testCreateCLInfo(self):
    cl_info = build_failure_analysis.CLInfo()
    self.assertEqual(0, cl_info.top_score)

  def testSaveStepFailureToMap(self):
    cl_failure_map = defaultdict(build_failure_analysis.CLInfo)
    new_suspected_cl_dict = {
        'repo_name': 'chromium',
        'revision': 'rev',
        'commit_position': 1,
        'url': 'url'
    }
    step_name = 'step'
    top_score = 5
    build_failure_analysis.SaveFailureToMap(
        cl_failure_map, new_suspected_cl_dict, step_name, None, top_score)

    self.assertEqual(cl_failure_map[('chromium', 'rev', 1)].top_score, 5)

  def testSaveTestFailureToMap(self):
    cl_failure_map = defaultdict(build_failure_analysis.CLInfo)
    new_suspected_cl_dict = {
        'repo_name': 'chromium',
        'revision': 'rev',
        'commit_position': 1,
        'url': 'url'
    }
    step_name = 'step'
    test_name = 'test'
    top_score = 5
    build_failure_analysis.SaveFailureToMap(
        cl_failure_map, new_suspected_cl_dict, step_name, test_name, top_score)

    self.assertEqual(5, cl_failure_map[('chromium', 'rev', 1)].top_score)
    self.assertEqual([test_name], cl_failure_map[('chromium', 'rev',
                                                  1)].failures[step_name])

  def testConvertCLFailureMapToList(self):
    repo_name = 'chromium'
    revision = 'rev'
    commit_position = 1

    cl_failure_map = {
        (repo_name, revision, commit_position): build_failure_analysis.CLInfo()
    }
    suspected_cls = build_failure_analysis.ConvertCLFailureMapToList(
        cl_failure_map)
    self.assertEqual(repo_name, suspected_cls[0]['repo_name'])

  def testCreateCLInfoDict(self):
    justification_dict = {'score': 5, 'hints': {'hint': 5}}
    build_number = 120
    change_log = {
        'author': {
            'name':
                'someone@chromium.org',
            'email':
                'someone@chromium.org',
            'time':
                datetime.strptime('Wed Jun 11 19:35:32 2014',
                                  '%a %b %d %H:%M:%S %Y'),
        },
        'committer': {
            'name':
                'someone@chromium.org',
            'email':
                'someone@chromium.org',
            'time':
                datetime.strptime('Wed Jun 11 19:35:32 2014',
                                  '%a %b %d %H:%M:%S %Y'),
        },
        'message':
            'Cr-Commit-Position: refs/heads/master@{#175976}',
        'commit_position':
            175976,
        'touched_files': [{
            'new_path': 'added_file.js',
            'change_type': 'add',
            'old_path': '/dev/null'
        }],
        'commit_url':
            'https://chromium.googlesource.com/chromium/src.git/+/rev1',
        'code_review_url':
            None,
        'revision':
            'rev1',
        'reverted_revision':
            None,
        'review_server_host':
            None,
        'review_change_id':
            None,
    }

    cl_info = build_failure_analysis.CreateCLInfoDict(
        justification_dict, build_number, ChangeLogFromDict(change_log))

    expected_cl_info = {
        'build_number': build_number,
        'repo_name': 'chromium',
        'revision': 'rev1',
        'commit_position': 175976,
        'url': 'https://chromium.googlesource.com/chromium/src.git/+/rev1',
        'score': 5,
        'hints': {
            'hint': 5
        }
    }

    self.assertEqual(expected_cl_info, cl_info)

  def testGetLowerBoundForAnalysisStructuredLastPass(self):
    failure_info = TestFailedStep(
        last_pass=120, current_failure=121, first_failure=121)
    self.assertEqual(
        121, build_failure_analysis.GetLowerBoundForAnalysis(failure_info))

  def testGetLowerBoundForAnalysisStructuredFirstFailure(self):
    failure_info = TestFailedStep(
        last_pass=None, current_failure=121, first_failure=121)
    self.assertEqual(
        121, build_failure_analysis.GetLowerBoundForAnalysis(failure_info))

  def testInitializeStepLevelResultStructured(self):
    step_name = 'step'
    step_failure_info = TestFailedStep(
        last_pass=119, current_failure=121, first_failure=120, supported=True)

    expected_result = {
        'step_name': step_name,
        'first_failure': 120,
        'last_pass': 119,
        'suspected_cls': [],
        'supported': True
    }
    self.assertEqual(
        expected_result,
        build_failure_analysis.InitializeStepLevelResult(
            step_name, step_failure_info))

  def testAddFileChangeMultipleOccurance(self):
    justification = build_failure_analysis._Justification()
    justification.AddFileChange(
        change_action='modified',
        changed_src_file_path='file_path',
        file_path_in_log='file_path',
        score=2,
        num_file_name_occurrences=2)
    self.assertEqual(justification.score, 2)

  @mock.patch.object(build_failure_analysis, 'CheckFiles')
  @mock.patch.object(build_failure_analysis, 'CreateCLInfoDict')
  def testAnalyzeOneCL(self, mock_check_files, mock_info_dict):
    build_number = 123
    justification = build_failure_analysis._Justification()
    justification._score = 1
    justification._hints = {'hint': 1}
    mock_check_files.return_value = justification
    mock_info_dict.return_value = {
        'build_number': build_number,
        'repo_name': 'chromium',
        'revision': 'rev',
        'commit_position': 123,
        'url': 'url',
        'score': 1,
        'hints': {
            'hint': 1
        }
    }
    _, max_score = build_failure_analysis.AnalyzeOneCL(build_number, {}, {}, {})
    self.assertEqual(1, max_score)

  @mock.patch.object(build_failure_analysis, 'CheckFiles', return_value=None)
  def testAnalyzeOneCLNotSuspected(self, _):
    build_number = 123
    result, max_score = build_failure_analysis.AnalyzeOneCL(
        build_number, {}, {}, {})
    self.assertIsNone(result)
    self.assertIsNone(max_score)

  def testAnalyzeOneCLShouldNotBlameChange(self):
    change_log = ChangeLogFromDict({
        'author': {
            'email': NO_BLAME_ACTION_ACCOUNTS[0]
        }
    })
    result, max_score = build_failure_analysis.AnalyzeOneCL(
        123, {}, change_log, {})
    self.assertIsNone(result)
    self.assertIsNone(max_score)

  def testGetHeuristicSuspectedCLs(self):
    repo_name = 'chromium'
    revision = 'r123_2'

    culprit = WfSuspectedCL.Create(repo_name, revision, None)
    culprit.put()

    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.suspected_cls = [{
        'repo_name': repo_name,
        'revision': revision,
        'commit_position': None,
        'url': None,
        'failures': {
            'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
        },
        'top_score': 4
    }]
    analysis.put()

    suspected_cls = [culprit.key.urlsafe()]

    self.assertEqual(
        suspected_cls,
        build_failure_analysis.GetHeuristicSuspectedCLs('m', 'b',
                                                        123).ToSerializable())

  def testGetHeuristicSuspectedCLsNoAnalysis(self):
    self.assertEqual([],
                     build_failure_analysis.GetHeuristicSuspectedCLs(
                         'm', 'b', 123).ToSerializable())

  @mock.patch.object(time_util, 'GetUTCNow')
  def testResetAnalysisForANewAnalysis(self, mock_now):
    master_name = 'm'
    builder_name = 'b'
    build_number = 98
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    now_time = datetime(2018, 7, 31, 0, 0, 0)
    mock_now.return_value = now_time

    build_failure_analysis.ResetAnalysisForANewAnalysis(
        master_name, builder_name, build_number, True, 'pipeline_status_path',
        '12345')
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.RUNNING, analysis.status)
    self.assertEqual(now_time, analysis.start_time)

  def testUpdateAbortedAnalysisNoTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    parameter = AnalyzeCompileFailureInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        current_failure_info=CompileFailureInfo.FromSerializable({}),
        build_completed=False,
        force=True)
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    analysis, run_try_job, heuristic_aborted = (
        build_failure_analysis.UpdateAbortedAnalysis(parameter))
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertTrue(analysis.aborted)
    self.assertFalse(run_try_job)
    self.assertTrue(heuristic_aborted)

  def testUpdateAbortedAnalysisTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    parameter = AnalyzeCompileFailureInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        current_failure_info=CompileFailureInfo.FromSerializable({}),
        build_completed=False,
        force=True)
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.failure_info = {'failed_steps': {}}
    analysis.put()
    analysis, run_try_job, heuristic_aborted = (
        build_failure_analysis.UpdateAbortedAnalysis(parameter))
    self.assertEqual(analysis_status.ERROR, analysis.status)
    self.assertTrue(analysis.aborted)
    self.assertTrue(run_try_job)
    self.assertTrue(heuristic_aborted)

  def testUpdateAbortedAnalysisErrorAfterHeuristic(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 124
    parameter = AnalyzeCompileFailureInput(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        current_failure_info=CompileFailureInfo.FromSerializable({}),
        build_completed=False,
        force=True)
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = analysis_status.COMPLETED
    analysis.put()
    analysis, run_try_job, heuristic_aborted = (
        build_failure_analysis.UpdateAbortedAnalysis(parameter))
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertTrue(analysis.aborted)
    self.assertFalse(run_try_job)
    self.assertFalse(heuristic_aborted)
