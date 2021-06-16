# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from datetime import time
from datetime import timedelta
import json

from analysis.type_enums import CrashClient
from common.model.fracas_crash_analysis import FracasCrashAnalysis
from frontend.handlers.dashboard import DashBoard
from libs import time_util


class FracasDashBoard(DashBoard):

  @property
  def crash_analysis_cls(self):
    return FracasCrashAnalysis

  @property
  def client(self):
    return CrashClient.FRACAS
