# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import mock
import textwrap

from libs import analysis_status
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from services import git
from services import issue_generator
from waterfall import buildbot
from waterfall.test.wf_testcase import WaterfallTestCase

_EXPECTED_GROUP_DESC = textwrap.dedent("""
Tests in step is flaky.

5 flake occurrences of tests below have been detected within
the past 24 hours:

suite.test0
suite.test1
suite.test2

Please try to find and revert the culprit if the culprit is obvious.
Otherwise please find an appropriate owner.

""")

_EXPECTED_GROUP_FIRST_COMMENT = textwrap.dedent("""
List of all flake occurrences can be found at:
https://analysis.chromium.org/p/chromium/flake-portal/flakes?bug_id={}.

If the result above is wrong, please file a bug using this link:
{}

Automatically posted by Flake Portal (https://goo.gl/Ne6KtC).""")

_EXPECTED_GROUP_COMMENT = textwrap.dedent("""
5+ new flake occurrences of tests in this bug have been detected
within the past 24 hours.

List of all flake occurrences can be found at:
https://analysis.chromium.org/p/chromium/flake-portal/flakes?bug_id={}.

{}

If the result above is wrong, please file a bug using this link:
{}

Automatically posted by Flake Portal (https://goo.gl/Ne6KtC).""")


class IssueGeneratorTest(WaterfallTestCase):

  def testGenerateAnalysisLink(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    self.assertIn(analysis.key.urlsafe(),
                  issue_generator._GenerateAnalysisLink(analysis))

  def testGenerateWrongCulpritLink(self):
    commit_position = 1000
    culprit = FlakeCulprit.Create('c', 'r', commit_position, 'http://')
    link = issue_generator._GenerateWrongCulpritLink(culprit)
    self.assertIn(str(commit_position), link)
    self.assertIn(culprit.key.urlsafe(), link)

  def testGenerateMessageTextWithCulprit(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    task_id = 'task_id'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.status = analysis_status.COMPLETED
    analysis.data_points = [DataPoint.Create(task_ids=[task_id])]
    culprit = FlakeCulprit.Create('c', 'r', 123, 'http://')
    culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())
    culprit.put()
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.confidence_in_culprit = 0.6713
    comment = issue_generator._GenerateMessageText(analysis)
    self.assertIn('r123', comment)
    self.assertIn(culprit.key.urlsafe(), comment)

  @mock.patch.object(buildbot, 'CreateBuildbucketUrl')
  @mock.patch.object(
      MasterFlakeAnalysis,
      'GetRepresentativeSwarmingTaskId',
      return_value='task_id')
  def testGenerateMessageTextNoCulprit(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.original_master_name = master_name
    analysis.original_builder_name = builder_name
    analysis.original_build_number = build_number
    analysis.status = analysis_status.COMPLETED
    comment = issue_generator._GenerateMessageText(analysis)
    self.assertTrue('longstanding' in comment, comment)

  # Tests for FlakeDetectionGroupIssueGenerator.
  def _GetIssueGenerator(self, new_issue=True):
    luci_project = 'chromium'
    normalized_step_name = 'step'

    flake0 = Flake.Create(luci_project, normalized_step_name, 'suite.test0',
                          'suite.test0')
    flake0.tags = ['component::Blink']
    flake0.put()
    flake1 = Flake.Create(luci_project, normalized_step_name, 'suite.test1',
                          'suite.test1')
    flake1.tags = ['component::Blink/Infra']
    flake1.put()
    flake2 = Flake.Create(luci_project, normalized_step_name, 'suite.test2',
                          'suite.test2')
    flake2.put()
    flake3 = Flake.Create(luci_project, 'other_step', 'other_test',
                          'other_test')
    flake3.put()

    issue_generator_new = issue_generator.FlakeDetectionGroupIssueGenerator(
        flakes=[flake0, flake1, flake2],
        num_occurrences=5,
        canonical_step_name=normalized_step_name)

    flake_issue = FlakeIssue.Create(luci_project, 12345)
    flake_issue.put()
    issue_generator_old = issue_generator.FlakeDetectionGroupIssueGenerator(
        flakes=[flake1, flake2, flake3],
        num_occurrences=5,
        flake_issue=flake_issue,
        flakes_with_same_occurrences=False)

    return issue_generator_new if new_issue else issue_generator_old

  def testGetComponents(self):
    self.assertItemsEqual(['Blink', 'Blink/Infra'],
                          self._GetIssueGenerator().GetComponents())

  def testGetSummary(self):
    self.assertEqual('Flakes are found in step.',
                     self._GetIssueGenerator().GetSummary())

  def testGetDescription(self):
    expected_description = _EXPECTED_GROUP_DESC
    self.assertEqual(expected_description,
                     self._GetIssueGenerator().GetDescription())

  def testGetLabels(self):
    self.assertListEqual(
        ['Type-Bug', 'Test-Flaky', 'Pri-1', 'Test-Flake-Detected'],
        self._GetIssueGenerator().GetLabels())

  def testGetFirstCommentWhenBugJustCreated(self):
    issue_generator_new = self._GetIssueGenerator()
    flake_issue = FlakeIssue.Create('chromium', 12345)
    flake_issue.put()
    issue_generator_new.SetFlakeIssue(flake_issue)
    wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?'
        'status=Unconfirmed&labels=Pri-1,Test-Flake-Detection-Wrong,Type-Bug&'
        'components=Infra%3ETest%3EFlakiness&'
        'summary=Flake%20Detection%20-%20Wrong%20result%3A%20'
        'Tests in step&comment=Link%20to%20flake%20details%3A%20'
        'https://analysis.chromium.org/p/chromium/flake-portal/flakes?bug_id={}'
        '%0A%0AIssue%20Description:%0A%0A').format(flake_issue.issue_id)
    expected_description = _EXPECTED_GROUP_FIRST_COMMENT.format(
        flake_issue.issue_id, wrong_result_link)
    self.assertEqual(expected_description,
                     issue_generator_new.GetFirstCommentWhenBugJustCreated())

  def testGetComment(self):
    issue_generator_old = self._GetIssueGenerator(new_issue=False)
    bug_id = issue_generator_old._flake_issue.issue_id
    wrong_result_link = (
        'https://bugs.chromium.org/p/chromium/issues/entry?'
        'status=Unconfirmed&labels=Pri-1,Test-Flake-Detection-Wrong,Type-Bug&'
        'components=Infra%3ETest%3EFlakiness&'
        'summary=Flake%20Detection%20-%20Wrong%20result%3A%20'
        '12345&comment=Link%20to%20flake%20details%3A%20'
        'https://analysis.chromium.org/p/chromium/flake-portal/flakes?bug_id={}'
        '%0A%0AIssue%20Description:%0A%0A').format(bug_id)
    sheriff_queue_message = (
        'Since these tests are still flaky, this issue has been moved back onto'
        ' the Sheriff Bug Queue if it hasn\'t already.')
    expected_description = _EXPECTED_GROUP_COMMENT.format(
        bug_id, sheriff_queue_message, wrong_result_link)
    self.assertEqual(expected_description, issue_generator_old.GetComment())

  def testGetFlakyTestCustomizedFieldGroupWithIssue(self):
    self.assertIsNone(
        self._GetIssueGenerator(new_issue=False).GetFlakyTestCustomizedField())

  def testGetMonorailProjectGroup(self):
    self.assertEqual('chromium', self._GetIssueGenerator().GetMonorailProject())

  def testGetAutoAssignOwnerNoCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()
    self.assertIsNone(issue_generator._GetAutoAssignOwner(analysis))

  @mock.patch.object(git, 'GetAuthor')
  def testGetAutoAssignOwnerNonChromiumAccount(self, mock_author):
    revision = 'r'
    culprit = FlakeCulprit.Create('c', revision, 123, 'http://')
    culprit.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.Save()

    author = mock.MagicMock()
    author.email = 'author@something_else.com'
    mock_author.return_value = author

    self.assertIsNone(issue_generator._GetAutoAssignOwner(analysis))

  @mock.patch.object(git, 'GetAuthor')
  def testGetAutoAssignOwnerChromiumAccount(self, mock_author):
    revision = 'r'
    culprit = FlakeCulprit.Create('c', revision, 123, 'http://')
    culprit.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.Save()

    author = mock.MagicMock()
    author.email = 'author@chromium.org'
    mock_author.return_value = author

    self.assertEqual(author.email,
                     issue_generator._GetAutoAssignOwner(analysis))

  @mock.patch.object(git, 'GetAuthor')
  def testGetAutoAssignOwnerGoogleAccount(self, mock_author):
    revision = 'r'
    culprit = FlakeCulprit.Create('c', revision, 123, 'http://')
    culprit.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.culprit_urlsafe_key = culprit.key.urlsafe()
    analysis.Save()

    author = mock.MagicMock()
    author.email = 'author@google.com'
    mock_author.return_value = author

    self.assertEqual(author.email,
                     issue_generator._GetAutoAssignOwner(analysis))

  def testGenerateDuplicateComment(self):
    commit_position = 12345
    culprit = FlakeCulprit.Create('c', str(commit_position), commit_position,
                                  'http://')
    culprit.put()

    comment = issue_generator.GenerateDuplicateComment(culprit)
    self.assertIn(str(commit_position), comment)
    self.assertIn(culprit.key.urlsafe(), comment)
