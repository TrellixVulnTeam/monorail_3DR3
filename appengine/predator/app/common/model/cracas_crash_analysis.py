# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import urllib

from google.appengine.ext import ndb

from analysis.type_enums import CrashClient
from common.model.chrome_crash_analysis import ChromeCrashAnalysis

_PLATFORM_TO_PRODUCT_NAME = {'win': 'Chrome',
                             'mac': 'Chrome_Mac',
                             'ios': 'Chrome_iOS',
                             'linux': 'Chrome_Linux'}

_CRACAS_BASE_URL = 'https://crash.corp.google.com/browse'

# TODO(katesonia): Consider moving JsonProperty to LocalStructuredProperty or
# StructuredProperty instead because JsonProperty's format is unpredictable.


class CracasCrashAnalysis(ChromeCrashAnalysis):
  """Represents an analysis of a Chrome crash on Cracas."""

  @property
  def client_id(self):  # pragma: no cover
    return CrashClient.CRACAS

  @property
  def crash_url(self):  # pragma: no cover
    product_name = _PLATFORM_TO_PRODUCT_NAME.get(self.platform)
    query = ('product.name=\'%s\' AND custom_data.ChromeCrashProto.'
             'magic_signature_1.name=\'%s\' AND '
             'custom_data.ChromeCrashProto.channel=\'%s\'') % (
                 product_name, self.signature, self.channel)
    return _CRACAS_BASE_URL + '?' + urllib.urlencode(
        {'q': query}).replace('+', '%20')

  def ToJson(self):
    """Converts the crash analysis to a json message for rerun."""
    json_output = super(CracasCrashAnalysis, self).ToJson()
    try:
      json_output['stack_trace'] = json.loads(json_output['stack_trace'])
    except ValueError:  # pragma: no cover.
      # Support legacy cracas data with a signle stacktrace instead of a list of
      # stacktraces.
      json_output['stack_trace'] = [json_output['stack_trace']]

    return json_output
