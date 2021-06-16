# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import taskqueue

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from services import flake_issue_util


class ProcessFlakesCronJob(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    taskqueue.add(
        method='GET',
        queue_name=constants.FLAKE_DETECTION_MULTITASK_QUEUE,
        target=constants.FLAKE_DETECTION_BACKEND,
        url='/flake/detection/task/process-flakes')
    return {'return_code': 200}


class FlakeAutoAction(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    flake_tuples_to_report = flake_issue_util.GetFlakesWithEnoughOccurrences()
    flake_groups_without_bug, flake_groups_with_bug = (
        flake_issue_util.GetFlakeGroupsForActionsOnBugs(flake_tuples_to_report))
    flake_issue_util.ReportFlakesToMonorail(flake_groups_without_bug,
                                            flake_groups_with_bug)

    # Reporting to Flake Analyzer needs to come after reporting to Monorail
    # because it makes Flake Analyzer's job easier if it can reuse the issues
    # filed by Flake Detection.
    flake_issue_util.ReportFlakesToFlakeAnalyzer(flake_tuples_to_report)
    return {'return_code': 200}
