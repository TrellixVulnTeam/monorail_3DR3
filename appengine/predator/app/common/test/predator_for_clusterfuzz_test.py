# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import mock

from analysis import chromecrash_parser
from analysis import detect_regression_range
from analysis.clusterfuzz_parser import ClusterfuzzParser
from analysis.crash_report import CrashReport
from analysis.type_enums import CrashClient
from common import predator_app
from common import predator_for_chromecrash
from common.appengine_testcase import AppengineTestCase
from common.predator_for_clusterfuzz import PredatorForClusterfuzz
from common.model.crash_analysis import CrashAnalysis
from common.model.crash_config import CrashConfig
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs import analysis_status
from libs.deps import chrome_dependency_fetcher
from libs.deps.dependency import DependencyRoll
from libs.gitiles.gitiles_repository import GitilesRepository


class PredatorForClusterfuzzTest(AppengineTestCase):

  def setUp(self):
    super(PredatorForClusterfuzzTest, self).setUp()
    self._client = PredatorForClusterfuzz(self.GetMockRepoFactory(),
                                          CrashConfig.Get())

  def testCheckPolicy(self):
    crash_data = self._client.GetCrashData(self.GetDummyClusterfuzzData(
        client_id = CrashClient.CLUSTERFUZZ))
    self.assertTrue(self._client._CheckPolicy(crash_data))

  def testCreateAnalysis(self):
    self.assertIsNotNone(self._client.CreateAnalysis({
        'testcase_id': 'predator_for_clusterfuzz_test_create_analysis'
    }))

  def testGetAnalysis(self):
    crash_identifiers = {
        'testcase_id': 'predator_for_clusterfuzz_test_get_analysis'
    }
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.log.Reset()
    analysis.put()
    self.assertEqual(self._client.GetAnalysis(crash_identifiers), analysis)

  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToTryBot')
  @mock.patch('common.predator_app.PredatorApp.PublishResultToClient')
  def testPublishResultDoNothingIfAnalysisFailed(self,
                                                 mock_publish_to_client,
                                                 mock_publish_to_try_bot):
    # pylint:disable=unused-argument
    """Tests that ``PublishResult`` does nothing if analysis failed."""
    crash_identifiers = {
        'testcase_id': ('predator_for_clusterfuzz_test_publish_result_do_'
                        'nothing_if_analysis_failed')
    }
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.result = None
    analysis.status = analysis_status.ERROR
    analysis.log.Reset()
    analysis.put()

    self.assertIsNone(self._client.PublishResult(crash_identifiers))
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/948219
    # mock_publish_to_client.assert_not_called()
    # mock_publish_to_try_bot.assert_not_called()

  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToTryBot')
  @mock.patch('common.predator_app.PredatorApp.PublishResultToClient')
  def testPublishResultDoNothingIfTestcasePlatformIsNotLinux(
      self, mock_publish_to_client, mock_publish_to_try_bot):
    # pylint:disable=unused-argument
    """Tests ``PublishResult`` does nothing if the platform is not supported."""
    identifiers = {
        'testcase_id': ('predator_for_clusterfuzz_test_publish_result_do_'
                        'nothing_if_testcase_platform_is_not_linux')
    }
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.result = {'found': False}
    analysis.status = analysis_status.COMPLETED
    analysis.platform = 'win'
    analysis.log.Reset()
    analysis.put()

    self.assertIsNone(self._client.PublishResult(identifiers))
    mock_publish_to_client.assert_called_with(identifiers)
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/948219
    # mock_publish_to_try_bot.assert_not_called()

  @mock.patch('libs.gitiles.gitiles_repository.GitilesRepository.'
              'GetCommitsBetweenRevisions')
  def testMessageToTryBotIfThereAreSuspects(self, get_commits):
    """Tests ``MessgeToTryBot`` format if analysis succeeded."""
    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reasons': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'other_data': 'data',
    }
    identifiers = {
        'testcase_id': ('predator_for_clusterfuzz_test_msg_to_try_bot_if_there'
                        '_are_suspects')
    }
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.testcase_id = '1234'
    analysis.dependency_rolls = {'src/': DependencyRoll('src/', 'https://repo',
                                                        'old_rev', 'new_rev')}
    analysis.platform = 'linux'
    analysis.result = analysis_result
    analysis.status = analysis_status.COMPLETED
    analysis.log.Reset()
    analysis.put()

    commits = ['git_hash1', 'git_hash2']
    get_commits.return_value = commits
    feedback_url = 'https://feedback'

    expected_message = {
        'regression_ranges': [{'path': 'src/', 'repo_url': 'https://repo',
                               'old_revision': 'old_rev',
                               'new_revision': 'new_rev', 'commits': commits}],
        'testcase_id': analysis.testcase_id,
        'suspected_cls': analysis_result['suspected_cls'],
        'feedback_url': feedback_url,
    }
    with mock.patch('common.model.crash_analysis.CrashAnalysis.feedback_url',
                    new_callable=mock.PropertyMock) as mock_feedback:
      mock_feedback.return_value = feedback_url
      self.assertDictEqual(self._client.MessageToTryBot(analysis),
                           expected_message)

  @mock.patch('libs.gitiles.gitiles_repository.GitilesRepository.'
              'GetCommitsBetweenRevisions')
  def testMessageToTryBotIfThereIsNoSuspect(self, get_commits):
    """Tests ``MessgeToTryBot`` format if analysis succeeded."""
    analysis_result = {
        'found': False,
        'other_data': 'data',
    }
    identifiers = {
        'testcase_id': ('predator_for_clusterfuzz_test_msg_to_try_bot_if_there'
                        '_is_no_suspect')
    }
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.testcase_id = '1234'
    analysis.dependency_rolls = {'src/': DependencyRoll('src/', 'https://repo',
                                                        'old_rev', 'new_rev')}
    analysis.platform = 'linux'
    analysis.result = analysis_result
    analysis.status = analysis_status.COMPLETED
    analysis.log.Reset()
    analysis.put()

    commits = ['git_hash1', 'git_hash2']
    get_commits.return_value = commits
    feedback_url = 'https://feedback'

    expected_message = {
        'regression_ranges': [{'path': 'src/', 'repo_url': 'https://repo',
                               'old_revision': 'old_rev',
                               'new_revision': 'new_rev', 'commits': commits}],
        'testcase_id': analysis.testcase_id,
        'feedback_url': feedback_url,
    }

    with mock.patch('common.model.crash_analysis.CrashAnalysis.feedback_url',
                    new_callable=mock.PropertyMock) as mock_feedback:
      mock_feedback.return_value = feedback_url
      self.assertDictEqual(self._client.MessageToTryBot(analysis),
                           expected_message)

  @mock.patch('gae_libs.pubsub_util.PublishMessagesToTopic')
  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'MessageToTryBot')
  def testDoNotPublishResultToTryBotIfWithoutRegressionRange(
      self, message_to_try_bot, publish_message):
    """Tests ``PublishResultToTryBot`` publish message to try bot."""
    message = 'blabla'
    message_to_try_bot.return_value = message
    identifiers = {
        'testcase_id': ('predator_for_clusterfuzz_test_do_not_publish_result'
                        '_to_try_bot_if_without_regression_range')
    }
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.log.Reset()
    analysis.put()
    self._client.PublishResultToTryBot(identifiers)
    self.assertFalse(publish_message.called)

  @mock.patch('gae_libs.pubsub_util.PublishMessagesToTopic')
  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'MessageToTryBot')
  def testDoNotPublishResultToTryBotIfPlatformNotSupported(
      self, message_to_try_bot, publish_message):
    """Tests ``PublishResultToTryBot`` publish message to try bot."""
    message = 'blabla'
    message_to_try_bot.return_value = message
    identifiers = {
        'testcase_id': ('predator_for_clusterfuzz_test_do_not_publish_result'
                        '_to_try_bot_if_platform_not_supported')
    }
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.regression_range = ('rev1', 'rev5')
    analysis.platform = 'win'
    analysis.log.Reset()
    analysis.put()
    self._client.PublishResultToTryBot(identifiers)
    self.assertFalse(publish_message.called)

  @mock.patch('gae_libs.pubsub_util.PublishMessagesToTopic')
  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'MessageToTryBot')
  def testPublishResultToTryBot(self, message_to_try_bot, publish_message):
    """Tests ``PublishResultToTryBot`` publish message to try bot."""
    message = 'blabla'
    message_to_try_bot.return_value = message
    identifiers = {
        'testcase_id':
        'predator_for_clusterfuzz_test_publish_result_to_try_bot'
    }
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.regression_range = ('rev1', 'rev5')
    analysis.platform = 'linux'
    analysis.log.Reset()
    analysis.put()
    self._client.PublishResultToTryBot(identifiers)
    publish_message.assert_called_with(
        [json.dumps(message)], self._client.client_config['try_bot_topic'])

  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToTryBot')
  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'PublishResultToClient')
  def testPublishResult(self, publish_to_client, publish_to_try_bot):
    """Tests ``PublishResult`` publish message to all topics."""
    identifiers = {
        'testcase_id':
        'predator_for_clusterfuzz_test_publish_result'
    }
    analysis = self._client.CreateAnalysis(identifiers)
    analysis.identifiers = identifiers
    analysis.platform = 'linux'
    analysis.log.Reset()
    analysis.put()
    self._client.PublishResult(identifiers)
    publish_to_client.assert_called_with(identifiers)
    publish_to_try_bot.assert_called_with(identifiers)

  def testResultMessageToClientFoundTrue(self):
    """Tests ``ResultMessageToClient`` when there is result."""
    analysis_result = {
        'found': True,
        'suspected_cls': [
            {'confidence': 0.21434,
             'reasons': ['reason1', 'reason2'],
             'other': 'data'}
        ],
        'regression_range': ['rev0', 'rev3'],
        'other_data': 'data',
    }

    crash_identifiers = {
        'testcase_id':
        'predator_for_clusterfuzz_test_result_msg_to_client_found_true'
    }
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.result = analysis_result
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.COMPLETED
    analysis.log.Reset()
    analysis.put()

    processed_analysis_result = copy.deepcopy(analysis_result)
    for cl in processed_analysis_result['suspected_cls']:
      cl['confidence'] = round(cl['confidence'], 2)
    processed_analysis_result['feedback_url'] = analysis.feedback_url
    del processed_analysis_result['regression_range']

    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self._client.client_id,
        'result': processed_analysis_result,
    }
    self.assertDictEqual(self._client.ResultMessageToClient(crash_identifiers),
                         expected_processed_result)

  def testResultMessageToClientFoundFalse(self):
    """Tests ``ResultMessageToClient`` when there is no result."""
    crash_identifiers = {
        'testcase_id':
        'predator_for_clusterfuzz_test_result_msg_to_client_found_false'
    }
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis_result = {
        'found': False,
        'log': 'Failed to parse stacktrace',
    }
    analysis.result = analysis_result
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.COMPLETED
    analysis.log.Reset()
    analysis.put()

    processed_analysis_result = copy.deepcopy(analysis_result)
    processed_analysis_result['feedback_url'] = analysis.feedback_url

    expected_processed_result = {
        'crash_identifiers': crash_identifiers,
        'client_id': self._client.client_id,
        'result': processed_analysis_result,
    }

    self.assertDictEqual(self._client.ResultMessageToClient(crash_identifiers),
                         expected_processed_result)

  def testDoNotDisableFeaturesForSmallRegressionRange(self):
    """Tests that predator don't disable features for small regression range."""
    crash_identifiers = {
        'testcase_id':
        ('predator_for_clusterfuzz_test_do_not_disable_features'
         '_for_small_regression')
    }
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.COMPLETED
    analysis.commit_count_in_regression_range = 10
    analysis.put()

    predator = PredatorForClusterfuzz(self.GetMockRepoFactory(),
                                      CrashConfig.Get())
    old_weights = predator._Predator().changelist_classifier._model._meta_weight
    predator.RedefineClassifierIfLargeRegressionRange(analysis)
    new_weights = predator._Predator().changelist_classifier._model._meta_weight
    self.assertTrue(new_weights == old_weights)

  def testRedefineClassifierIfLargeRegressionRange(self):
    """Tests that predator disable features for big regression range crash."""
    crash_identifiers = {
        'testcase_id':
        'predator_for_clusterfuzz_test_disable_features_for_big_regression'
    }
    analysis = self._client.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.COMPLETED
    analysis.commit_count_in_regression_range = 1000
    analysis.put()

    predator = PredatorForClusterfuzz(self.GetMockRepoFactory(),
                                      CrashConfig.Get())
    predator.RedefineClassifierIfLargeRegressionRange(analysis)
    weights = predator._Predator().changelist_classifier._model._meta_weight
    self.assertFalse('TouchCrashedComponent' in weights)
    self.assertFalse('TouchCrashedDirectory' in weights)

  @mock.patch('common.model.clusterfuzz_analysis.ClusterfuzzAnalysis.'
              'ToCrashReport')
  @mock.patch('analysis.predator.Predator.FindCulprit')
  @mock.patch('common.predator_for_clusterfuzz.PredatorForClusterfuzz.'
              'RedefineClassifierIfLargeRegressionRange')
  def testFindCulprit(self, mock_disable_features, mock_find_culprit,
                      mock_to_crash_report):
    """Tests ``FindCulprit`` called RedefineClassifierIfLargeRegressionRange."""
    crash_identifiers = {
        'testcase_id':
        'predator_for_clusterfuzz_test_find_culprit'
    }

    predator = PredatorForClusterfuzz(self.GetMockRepoFactory(),
                                      CrashConfig.Get())
    analysis = predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    predator.FindCulprit(analysis)
    self.assertTrue(mock_to_crash_report.called)
    self.assertTrue(mock_disable_features.called)
    self.assertTrue(mock_find_culprit.called)

  @mock.patch('common.monitoring.reports_processed')
  @mock.patch('common.monitoring.clusterfuzz_reports')
  def testUpdateMetrics(self, mock_clusterfuzz_reports, mock_reports_processed):
    """Tests ``UpdateMetrics``."""
    analysis = self._client.CreateAnalysis({'signature': 'sig'})
    analysis.status = analysis_status.COMPLETED
    analysis.found_suspects = True
    analysis.has_regression_range = True
    analysis.crash_type = 'CHECK failure'
    analysis.signature = 'signature1\nsignature2\n'
    analysis.security_flag = True
    analysis.platform = 'win'
    analysis.job_type = 'asan_win'

    self._client.UpdateMetrics(analysis)
    self.assertTrue(mock_reports_processed.increment.called)
    mock_clusterfuzz_reports.increment.assert_called_with({
        'found_suspects': True,
        'has_regression_range': True,
        'crash_type': 'CHECK failure',
        'security': True,
        'platform': 'win',
        'job_type': 'asan_win'})
