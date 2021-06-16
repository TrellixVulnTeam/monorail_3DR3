# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.changelist_classifier import ChangelistClassifier
from analysis.linear.changelist_features.min_distance import MinDistanceFeature
from analysis.linear.changelist_features.number_of_touched_files import (
    NumberOfTouchedFilesFeature)
from analysis.linear.changelist_features.top_frame_index import (
    TopFrameIndexFeature)
from analysis.linear.changelist_features.touch_crashed_component import (
    TouchCrashedComponentFeature)
from analysis.linear.changelist_features.touch_crashed_file import (
    TouchCrashedFileFeature)
from analysis.linear.changelist_features.touch_crashed_file_meta import (
    TouchCrashedFileMetaFeature)
from analysis.linear.feature import WrapperMetaFeature
from analysis.linear.weight import MetaWeight
from analysis.linear.weight import Weight
from analysis.predator import Predator
from analysis.type_enums import CrashClient
from analysis.uma_sampling_profiler_data import UMASamplingProfilerData
from common.model.uma_sampling_profiler_analysis import (
    UMASamplingProfilerAnalysis)
from common.predator_app import PredatorApp
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher


class PredatorForUMASamplingProfiler(PredatorApp):
  """Finds culprits for regressions/improvements from UMA Sampling Profiler."""

  @classmethod
  def _ClientID(cls):
    return CrashClient.UMA_SAMPLING_PROFILER

  def __init__(self, get_repository, config):
    """Set the paramaters of the model - i.e. the weights and features.

    For some explanation of why the paramaters were set this way see these docs:
      https://docs.google.com/a/google.com/document/d/1TdDEDlUJX81-5yvB9IfdJFq5-kJBb_DwAgDH9cGfNao/edit?usp=sharing
      https://docs.google.com/a/google.com/document/d/1FHaghBX_FANjtiUP7D1pihZGxzEYdXA3Y7t0rSA4bWU/edit?usp=sharing
    As well as the following CLs:
      https://chromium-review.googlesource.com/c/599071
      https://chromium-review.googlesource.com/c/585784
    """
    super(PredatorForUMASamplingProfiler, self).__init__(get_repository, config)
    meta_weight = MetaWeight({
        'TouchCrashedFileMeta': MetaWeight({
            'MinDistance': Weight(2.),
            'TopFrameIndex': Weight(0.),
            'TouchCrashedFile': Weight(1.),
        })
    })

    min_distance_feature = MinDistanceFeature(get_repository)
    top_frame_index_feature = TopFrameIndexFeature()
    touch_crashed_file_feature = TouchCrashedFileFeature()
    meta_feature = WrapperMetaFeature(
        [TouchCrashedFileMetaFeature([min_distance_feature,
                                      top_frame_index_feature,
                                      touch_crashed_file_feature],
                                     include_renamed_paths=True)])

    self._predator = Predator(ChangelistClassifier(get_repository,
                                                   meta_feature,
                                                   meta_weight),
                              self._component_classifier,
                              self._project_classifier)

  def _Predator(self):
    return self._predator

  def CreateAnalysis(self, regression_identifiers):
    """Creates ``UMASamplingProfilerAnalysis``.

    regression_identifiers is used as the key.
    """
    return UMASamplingProfilerAnalysis.Create(regression_identifiers)

  def GetAnalysis(self, regression_identifiers):
    """Gets ``UMASamplingProfilerAnalysis`` using regression_identifiers."""
    return UMASamplingProfilerAnalysis.Get(regression_identifiers)

  def GetCrashData(self, raw_regression_data):
    """Gets ``UMASamplingProfilerData`` from ``raw_regression_data``."""
    return UMASamplingProfilerData(
        raw_regression_data, ChromeDependencyFetcher(self._get_repository))
