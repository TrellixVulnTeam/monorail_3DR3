# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math

from google.appengine.ext import ndb

from analysis import detect_regression_range
from analysis import log_util
from analysis.changelist_classifier import ChangelistClassifier
from analysis.chrome_crash_data import CracasCrashData
from analysis.chrome_crash_data import FracasCrashData
from analysis.linear.changelist_features.file_path_idf import FilePathIdfFeature
from analysis.linear.changelist_features.number_of_touched_files import (
    NumberOfTouchedFilesFeature)
from analysis.linear.changelist_features.min_distance import MinDistanceFeature
from analysis.linear.changelist_features.top_frame_index import (
    TopFrameIndexFeature)
from analysis.linear.changelist_features.touch_crashed_component import (
    TouchCrashedComponentFeature)
from analysis.linear.changelist_features.touch_crashed_directory import (
    TouchCrashedDirectoryFeature)
from analysis.linear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from analysis.linear.changelist_features.touch_crashed_file_meta import (
    TouchCrashedFileMetaFeature)
from analysis.linear.feature import WrapperMetaFeature
from analysis.linear.weight import MetaWeight
from analysis.linear.weight import Weight
from analysis.predator import Predator
from analysis.type_enums import CrashClient
from common.model.cracas_crash_analysis import CracasCrashAnalysis
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from common.model.inverted_index import ChromeCrashInvertedIndex
from common.predator_app import PredatorApp
from gae_libs import appengine_util
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher


class PredatorForChromeCrash(PredatorApp):  # pylint: disable=W0223
  """Find culprits for crash reports from the Chrome Crash server."""

  @classmethod
  def _ClientID(cls): # pragma: no cover
    if cls is PredatorForChromeCrash:
      logging.warning('PredatorForChromeCrash is abstract, '
          'but someone constructed an instance and called _ClientID')
    else:
      logging.warning(
          'PredatorForChromeCrash subclass %s forgot to implement _ClientID',
          cls.__name__)
    raise NotImplementedError()

  def __init__(self, get_repository, config):
    super(PredatorForChromeCrash, self).__init__(get_repository, config)
    meta_weight = MetaWeight({
        'TouchCrashedFileMeta': MetaWeight({
            'MinDistance': Weight(2.),
            'TopFrameIndex': Weight(1.),
            'TouchCrashedFile': Weight(1.),
            'FilePathIdf': Weight(1.)
        }),
        'TouchCrashedDirectory': Weight(1.),
        'NumberOfTouchedFiles': Weight(0.5)
    })

    min_distance_feature = MinDistanceFeature(get_repository)
    top_frame_index_feature = TopFrameIndexFeature()
    touch_crashed_file_feature = TouchCrashedFileFeature()
    file_path_idf_feature = FilePathIdfFeature(ChromeCrashInvertedIndex)

    meta_feature = WrapperMetaFeature(
        [TouchCrashedFileMetaFeature([min_distance_feature,
                                      top_frame_index_feature,
                                      touch_crashed_file_feature,
                                      file_path_idf_feature]),
         TouchCrashedDirectoryFeature(options=config.feature_options[
             'TouchCrashedDirectory']),
         TouchCrashedComponentFeature(
             self._component_classifier,
             options=config.feature_options['TouchCrashedComponent']),
         NumberOfTouchedFilesFeature()])

    self._predator = Predator(ChangelistClassifier(get_repository,
                                                   meta_feature,
                                                   meta_weight),
                              self._component_classifier,
                              self._project_classifier)

  def _Predator(self):  # pragma: no cover
    return self._predator

  def _CheckPolicy(self, crash_data):
    """Checks if ``CrashData`` meets policy requirements."""
    if not super(PredatorForChromeCrash, self)._CheckPolicy(crash_data):
      return False

    if crash_data.platform not in self.client_config[
        'supported_platform_list_by_channel'].get(crash_data.channel, []):
      # Bail out if either the channel or platform is not supported yet.
      log_util.LogInfo(
          self._log, 'NotSupported',
          'Analysis of channel %s, platform %s is not supported.' %
          (crash_data.channel, crash_data.platform))
      return False

    return True

  def GetCrashData(self, raw_crash_data):
    """Returns parsed ``ChromeCrashData`` from raw json crash data."""
    return self.CrashDataCls()(raw_crash_data,
                               ChromeDependencyFetcher(self._get_repository),
                               top_n_frames=self.client_config['top_n'])

  @classmethod
  def CrashDataCls(cls):
    """The class of stacktrace parser."""
    raise NotImplementedError()


class PredatorForCracas(PredatorForChromeCrash):

  @classmethod
  def _ClientID(cls):
    return CrashClient.CRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Create stuff here.
    return CracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline CracasCrashAnalysis.Get stuff here.
    return CracasCrashAnalysis.Get(crash_identifiers)

  def ResultMessageToClient(self, crash_identifiers):
    """Converts a culprit result into a publishable result for client.

    Args:
      crash_identifiers (dict): Dict containing identifiers that can uniquely
        identify CrashAnalysis entity.

    Returns:
      A dict of the given ``crash_identifiers``, this model's
      ``client_id``, and a publishable version of this model's ``result``.
    """
    message = super(PredatorForCracas, self).ResultMessageToClient(
        crash_identifiers)
    result = message['result']
    # According to b/62866274, Cracas cannot parse ``null`` in the json, so
    # change it to an empty list.
    if 'regression_range' in result and result['regression_range'] is None:
      result['regression_range'] = []

    return message

  @classmethod
  def CrashDataCls(cls):
    """The class of crash data."""
    return CracasCrashData


def NormalizeConfidenceScore(score):
  """Normalize (-inf, inf) score into [0, 1] score."""
  return 1 / (1 + math.exp(-score))


class PredatorForFracas(PredatorForChromeCrash):  # pylint: disable=W0223
  @classmethod
  def _ClientID(cls):
    return CrashClient.FRACAS

  def CreateAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Create stuff here.
    return FracasCrashAnalysis.Create(crash_identifiers)

  def GetAnalysis(self, crash_identifiers):
    # TODO: inline FracasCrashAnalysis.Get stuff here.
    return FracasCrashAnalysis.Get(crash_identifiers)

  @classmethod
  def CrashDataCls(cls):
    """The class of crash data."""
    return FracasCrashData

  def ResultMessageToClient(self, crash_identifiers):
    """Converts a culprit result into a publishable result for client.

    Args:
      crash_identifiers (dict): Dict containing identifiers that can uniquely
        identify CrashAnalysis entity.

    Returns:
      A dict of the given ``crash_identifiers``, this model's
      ``client_id``, and a publishable version of this model's ``result``.
    """
    message = super(PredatorForFracas, self).ResultMessageToClient(
        crash_identifiers)
    result = message['result']

    # Fracas assume that the confidence score is in [0, 1], Normalize the
    # confidence into [0, 1]
    if 'suspected_cls' in result:
      for suspected_cl in result['suspected_cls']:
        suspected_cl['confidence'] = NormalizeConfidenceScore(
            suspected_cl['confidence'])

    return message
