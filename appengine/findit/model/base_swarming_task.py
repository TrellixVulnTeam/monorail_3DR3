# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import analysis_status
from libs import time_util


class BaseSwarmingTask(ndb.Model):
  """Represents the progress of a general swarming task."""
  # The id of the Swarming task scheduled or running on Swarming Server.
  task_id = ndb.StringProperty(indexed=True)

  # A dict to keep track of running information for each test:
  # number of total runs, number of each status (such as 'SUCCESS' or 'FAILED')
  tests_statuses = ndb.JsonProperty(indexed=False, compressed=True)

  # The status of the swarming task.
  status = ndb.IntegerProperty(default=analysis_status.PENDING, indexed=False)

  # An error dict containing an error code and message should this task fail
  # unexpectedly. For example:
  # {
  #     'code': 1,
  #     'message': 'Timed out'
  # }
  error = ndb.JsonProperty(indexed=False)

  # The revision of the failed build.
  build_revision = ndb.StringProperty(indexed=False)

  # Time when the task is created according to Swarming.
  created_time = ndb.DateTimeProperty(indexed=True)
  # Time when the task is started according to Swarming.
  started_time = ndb.DateTimeProperty(indexed=False)
  # Time when the task is completed according to Swarming.
  completed_time = ndb.DateTimeProperty(indexed=False)
  # The time this entity was created.
  requested_time = ndb.DateTimeProperty(indexed=True)

  # A URL to call back the pipeline monitoring the progress of this task.
  callback_url = ndb.StringProperty(indexed=False)

  # A target name for the callback.
  callback_target = ndb.StringProperty(indexed=False)

  # parameters need to be stored and analyzed later.
  parameters = ndb.JsonProperty(default={}, indexed=False, compressed=True)

  canonical_step_name = ndb.StringProperty(indexed=False)

  # The number of seconds this task is expected to complete within.
  timeout_seconds = ndb.IntegerProperty(indexed=False)

  def Reset(self):
    """Resets the task as if it's a new task."""
    self.task_id = None
    self.tests_statuses = {}
    self.status = analysis_status.PENDING
    self.error = None
    self.build_revision = None
    self.created_time = None
    self.started_time = None
    self.completed_time = None
    self.requested_time = time_util.GetUTCNow()
    self.callback_url = None
    self.callback_target = None
    self.parameters = {}
    self.canonical_step_name = None
    self.timeout_seconds = None
