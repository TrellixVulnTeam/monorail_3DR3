# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from analysis import chromecrash_parser
from analysis import detect_regression_range
from analysis.component_classifier import ComponentClassifier
from analysis.chrome_crash_data import CracasCrashData
from analysis.crash_report import CrashReport
from analysis.culprit import Culprit
from analysis.project_classifier import ProjectClassifier
from analysis.suspect import Suspect
from analysis.stacktrace import CallStack
from analysis.stacktrace import Stacktrace
from analysis.type_enums import CrashClient
from common import predator_app
from common import predator_for_chromecrash
from common.appengine_testcase import AppengineTestCase
from common.predator_for_chromecrash import NormalizeConfidenceScore
from common.predator_for_chromecrash import PredatorForChromeCrash
from common.predator_for_chromecrash import PredatorForCracas
from common.predator_for_chromecrash import PredatorForFracas
from common.model import crash_analysis
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from common.model.crash_config import CrashConfig
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs import analysis_status
from libs.deps import chrome_dependency_fetcher
from libs.deps.dependency import DependencyRoll
from libs.gitiles.gitiles_repository import GitilesRepository


MOCK_GET_REPOSITORY = lambda _: None # pragma: no cover


class _PredatorForChromeCrash(PredatorForChromeCrash):  # pylint: disable = W
  # We allow overriding the default ``get_repository`` because one unittest
  # needs to.
  def __init__(self, get_repository=MOCK_GET_REPOSITORY, config=None):
    super(_PredatorForChromeCrash, self).__init__(get_repository, config)

  @classmethod
  def _ClientID(cls): # pragma: no cover
    """Avoid throwing a NotImplementedError.

    Since this method is called from ``PredatorForChromeCrash.__init__``
    in order to construct the Azalea object, we need to not throw
    exceptions since we want to be able to test the PredatorForChromeCrash
    class itself.
    """
    return 'ChromeCrash'


def _PredatorForFracas(config=None):
  """A helper to pass in the standard pipeline class."""
  return PredatorForFracas(MOCK_GET_REPOSITORY, config or {})


class PredatorForChromeCrashTest(AppengineTestCase):

  # TODO(wrengr): what was the purpose of this test? As written it's
  # just testing that mocking works. I'm guessing it was to check that
  # we fail when the analysis is for the wrong client_id; but if so,
  # then we shouldn't need to mock FindCulprit...
  @mock.patch(
      'common.predator_for_chromecrash.PredatorForChromeCrash.FindCulprit')
  def testFindCulprit(self, mock_find_culprit):
    mock_find_culprit.return_value = None

    # TODO(wrengr): would be less fragile to call
    # PredatorForFracas.CreateAnalysis instead; though if I'm right about
    # the original purpose of this test, then this is one of the few
    # places where calling FracasCrashAnalysis directly would actually
    # make sense.
    analysis = FracasCrashAnalysis.Create({'signature': 'sig'})
    predator_client = _PredatorForChromeCrash(
        GitilesRepository.Factory(HttpClientAppengine()), CrashConfig.Get())
    self.assertIsNone(predator_client.FindCulprit(analysis))


class PredatorForFracasTest(AppengineTestCase):

  def setUp(self):
    super(PredatorForFracasTest, self).setUp()
    self._client = _PredatorForFracas(config=CrashConfig.Get())

  def testCheckPolicyBlacklistSignature(self):
    raw_crash_data = self.GetDummyChromeCrashData(
        client_id = CrashClient.FRACAS,
        signature='Blacklist marker signature')
    crash_data = self._client.GetCrashData(raw_crash_data)
    self.assertFalse(self._client._CheckPolicy(crash_data))

  def testCheckPolicyUnsupportedPlatform(self):
    raw_crash_data = self.GetDummyChromeCrashData(
        client_id = CrashClient.FRACAS,
        platform='unsupported_platform')
    crash_data = self._client.GetCrashData(raw_crash_data)
    self.assertFalse(self._client._CheckPolicy(crash_data))

  def testScheduleNewAnalysisSkipsUnsupportedChannel(self):
    raw_crash_data = self.GetDummyChromeCrashData(
        client_id = CrashClient.FRACAS,
        channel='unsupported_channel')
    crash_data = self._client.GetCrashData(raw_crash_data)
    self.assertFalse(self._client._CheckPolicy(crash_data))

  def testCheckPolicySuccess(self):
    crash_data = self._client.GetCrashData(self.GetDummyChromeCrashData(
        client_id = CrashClient.FRACAS))
    self.assertTrue(self._client._CheckPolicy(crash_data))

  def testCreateAnalysis(self):
    self.assertIsNotNone(self._client.CreateAnalysis(
        {'signature': 'sig'}))

  def testGetAnalysis(self):
    crash_identifiers = {'signature': 'sig'}
    # TODO(wrengr): would be less fragile to call
    # PredatorForFracas.CreateAnalysis instead.
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.put()
    self.assertEqual(self._client.GetAnalysis(crash_identifiers), analysis)

  @mock.patch('google.appengine.ext.ndb.Key.urlsafe')
  @mock.patch('gae_libs.appengine_util.GetDefaultVersionHostname')
  def testProcessResultForPublishing(self, mocked_get_default_host,
                                     mocked_urlsafe):
    mocked_host = 'http://host'
    mocked_get_default_host.return_value = mocked_host
    urlsafe_key = 'abcde'
    mocked_urlsafe.return_value = urlsafe_key

    crash_identifiers = {
        'testcase_id':
        'predator_for_chromecrash_test_process_result_for_publishing'
    }
    analysis = FracasCrashAnalysis.Create(crash_identifiers)
    analysis.result = {'other': 'data'}
    analysis.status = analysis_status.COMPLETED
    analysis.identifiers = crash_identifiers
    analysis.log.Reset()
    analysis.put()
    expected_processed_suspect = {
        'client_id': self._client.client_id,
        'crash_identifiers': crash_identifiers,
        'result': {
            'feedback_url': crash_analysis._FEEDBACK_URL_TEMPLATE % (
                mocked_host, CrashClient.FRACAS, urlsafe_key),
            'other': 'data'
        }
    }

    self.assertDictEqual(self._client.ResultMessageToClient(crash_identifiers),
                         expected_processed_suspect)

  def testNormalizeConfidenceScore(self):
    """Tests ``NormalizeConfidenceScore`` function."""
    score = 100
    normalized_score = NormalizeConfidenceScore(score)
    self.assertTrue(normalized_score >= 0)
    self.assertTrue(normalized_score <= 1)

  def testResultMessageToClientNormalizeScore(self):
    """Tests the confidence for all suspected cls to Fracas is within [0, 1]."""
    message = {'client': 'fracas',
               'other_data': 'blabla',
               'result': {
                   'suspected_cls': [
                       {'confidence': 302,
                        'other': 'blabla...'},
                       {'confidence': -234,
                        'other': 'blabla...'},
                       {'confidence': 0,
                        'other': 'bla...'},
                   ]
               }}
    with mock.patch(
        'common.predator_app.PredatorApp.'
        'ResultMessageToClient') as mock_result_message_to_client:
      mock_result_message_to_client.return_value = message
      updated_message = self._client.ResultMessageToClient({'sig': 's'})
      for suspected_cl in updated_message['result']['suspected_cls']:
        self.assertTrue(suspected_cl['confidence'] <= 1)
        self.assertTrue(suspected_cl['confidence'] >= 0)


class PredatorForCracasTest(AppengineTestCase):
  """Tests ``PredatorForCracas`` class."""

  def setUp(self):
    super(PredatorForCracasTest, self).setUp()
    self.predator = PredatorForCracas(MOCK_GET_REPOSITORY, CrashConfig.Get())

  def testClientID(self):
    """Tests ``_ClientID`` method."""
    self.assertEqual(self.predator.client_id, CrashClient.CRACAS)

  def testCreateAnalysis(self):
    """Tests ``CreateAnalysis`` creates ``CracasCrashAnalysis`` entity."""
    analysis = self.predator.CreateAnalysis({'id': 2})
    self.assertEqual(type(analysis), CracasCrashAnalysis)

  def testGetAnalysis(self):
    """Tests ``GetAnalysis`` get entity by key."""
    ids = {'id': 2}
    analysis = self.predator.CreateAnalysis(ids)
    analysis.put()
    self.assertEqual(analysis, self.predator.GetAnalysis(ids))

  @mock.patch('common.predator_app.PredatorApp.ResultMessageToClient')
  def testResultMessageToClientIfRegressionRangIsNone(self, mock_super_method):
    """Tests ``ResultMessageToClient`` method when regression range is None."""
    mock_super_method.side_effect = lambda *args: {'result': args[0]}
    crash_identifiers = {'regression_range': None}
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.regression_range = None
    analysis.identifiers = crash_identifiers
    analysis.put()

    msg = self.predator.ResultMessageToClient(crash_identifiers)
    self.assertEqual(msg['result']['regression_range'], [])

  @mock.patch('common.predator_app.PredatorApp.ResultMessageToClient')
  def testResultMessageToClientIfRegressionRangIsNotNone(
      self, mock_super_method):
    """Tests ``ResultMessageToClient`` method when regression range is None."""
    mock_super_method.side_effect = lambda *args: {'result': args[0]}
    crash_identifiers = {'regression_range': ['rev0', 'rev1']}
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.regression_range = ['rev0', 'rev1']
    analysis.identifiers = crash_identifiers
    analysis.put()

    msg = self.predator.ResultMessageToClient(crash_identifiers)
    self.assertEqual(msg['result']['regression_range'], ['rev0', 'rev1'])

  @mock.patch('common.predator_app.PredatorApp.ResultMessageToClient')
  def testResultMessageToClient(self, mock_super_method):
    """Tests ``ResultMessageToClient`` when regression range is not None."""
    mock_super_method.side_effect = lambda *args: {'result': args[0]}
    crash_identifiers = {'regression_range': ['2', '3']}
    analysis = self.predator.CreateAnalysis(crash_identifiers)
    analysis.identifiers = crash_identifiers

    msg = self.predator.ResultMessageToClient(crash_identifiers)
    self.assertEqual(msg['result'], crash_identifiers)

  def testCrashDataCls(self):
    """Tests ``CrashDataCls`` returns the class of the crash data."""
    crash_data = self.predator.GetCrashData(self.GetDummyChromeCrashData())
    self.assertTrue(isinstance(crash_data, self.predator.CrashDataCls()))
    self.assertEqual(self.predator.CrashDataCls(), CracasCrashData)
