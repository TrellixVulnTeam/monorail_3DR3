# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for extracting test failure signals.

It provides functions to:
  * Extract failure signals for test failure
"""

import base64
import json
import logging

from libs.test_results import test_results_util
from model.wf_step import WfStep
from services import extract_signal
from services import constants
from services import swarmed_test_util
from services.test_failure import test_results_service
from waterfall import extractors
from waterfall.failure_signal import FailureSignal


def ExtractSignalsForTestFailure(failure_info, http_client):
  signals = {}

  master_name = failure_info.master_name
  builder_name = failure_info.builder_name
  build_number = failure_info.build_number
  failed_steps = failure_info.failed_steps or {}

  for step_name in failed_steps:
    failure_log = None
    if not failed_steps[step_name].supported:
      # Bail out if the step is not supported.
      continue

    # 1. Tries to get stored failure log from step.
    step = (
        WfStep.Get(master_name, builder_name, build_number, step_name) or
        WfStep.Create(master_name, builder_name, build_number, step_name))
    if step.log_data and step.log_data != constants.TOO_LARGE_LOG:
      failure_log = step.log_data
    else:
      json_formatted_log = True
      # 2. Gets test results.
      list_isolated_data = failed_steps[step_name].list_isolated_data
      list_isolated_data = (
          list_isolated_data.ToSerializable() if list_isolated_data else [])
      merged_test_results = (
          swarmed_test_util.RetrieveShardedTestResultsFromIsolatedServer(
              list_isolated_data, http_client))
      if merged_test_results:
        test_results = test_results_util.GetTestResultObject(
            merged_test_results)
        if test_results:
          failure_log, _ = (
              test_results_service.GetFailedTestsInformationFromTestResult(
                  test_results))
          failure_log = json.dumps(
              failure_log) if failure_log else constants.FLAKY_FAILURE_LOG
        else:
          failure_log = constants.WRONG_FORMAT_LOG

      if not merged_test_results or failure_log in [
          constants.INVALID_FAILURE_LOG, constants.WRONG_FORMAT_LOG
      ]:
        # 3. Gets stdout log.
        json_formatted_log = False
        failure_log = extract_signal.GetStdoutLog(
            master_name, builder_name, build_number, step_name, http_client)

      try:
        if not failure_log:
          raise extract_signal.FailedToGetFailureLogError(
              'Failed to pull failure log (stdio or ninja output) of step %s of'
              ' %s/%s/%d' % (step_name, master_name, builder_name,
                             build_number))
      except extract_signal.FailedToGetFailureLogError:
        return {}

      # Save step log in datastore and avoid downloading again during retry.
      step.log_data = extract_signal.ExtractStorablePortionOfLog(
          failure_log, json_formatted_log
      ) if step.log_data != constants.TOO_LARGE_LOG else step.log_data
      step.isolated = step.isolated or json_formatted_log

      try:
        step.put()
      except Exception as e:  # pragma: no cover
        # Sometimes, the step log is too large to save in datastore.
        logging.exception(e)

    if step.isolated:
      try:
        json_failure_log = (
            json.loads(failure_log)
            if failure_log != constants.FLAKY_FAILURE_LOG else {})
      except ValueError:
        json_failure_log = {}
        logging.warning('failure_log %s is not valid JSON.' % failure_log)

      signals[step_name] = {'tests': {}}
      step_signal = FailureSignal()

      for test_name, test_failure_log in json_failure_log.iteritems():
        signals[step_name]['tests'][test_name] = extractors.ExtractSignal(
            master_name, builder_name, step_name, test_name,
            base64.b64decode(test_failure_log)).ToDict()

        # Save signals in test failure log to step level.
        step_signal.MergeFrom(signals[step_name]['tests'][test_name])

      signals[step_name]['files'] = step_signal.files
    else:
      signals[step_name] = extractors.ExtractSignal(
          master_name, builder_name, step_name, None, failure_log).ToDict()

  return signals
