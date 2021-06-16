# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import datetime
import json
import unittest

import gae_ts_mon
import mock
import webapp2

from google.appengine.api.runtime import runtime
from .test_support import test_case

from infra_libs.ts_mon import config
from infra_libs.ts_mon import handlers
from infra_libs.ts_mon import shared
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import metrics
from infra_libs.ts_mon.common import targets


class HelperFunctionsTest(unittest.TestCase):
  def test_find_gaps(self):
    self.assertEqual(
        list(zip(range(5), handlers.find_gaps([1, 3, 5]))),
        list(enumerate([0, 2, 4, 6, 7])))
    self.assertEqual(
        list(zip(range(5), handlers.find_gaps([0, 1, 2, 3, 5]))),
        list(enumerate([4, 6, 7, 8, 9])))
    self.assertEqual(
        list(zip(range(3), handlers.find_gaps([]))), list(enumerate([0, 1, 2])))
    self.assertEqual(
        list(zip(range(3), handlers.find_gaps([2]))), list(
            enumerate([0, 1, 3])))


class HandlersTest(test_case.TestCase):
  def setUp(self):
    super(HandlersTest, self).setUp()

    config.reset_for_unittest()
    target = targets.TaskTarget(
        'test_service', 'test_job', 'test_region', 'test_host')
    self.mock_state = interface.State(target=target)
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()

  def tearDown(self):
    mock.patch.stopall()
    config.reset_for_unittest()
    super(HandlersTest, self).tearDown()

  def test_assign_task_num(self):
    time_now = datetime.datetime(2016, 2, 8, 1, 0, 0)
    time_current = time_now - datetime.timedelta(
        seconds=shared.INSTANCE_EXPIRE_SEC-1)
    time_expired = time_now - datetime.timedelta(
        seconds=shared.INSTANCE_EXPIRE_SEC+1)

    with shared.instance_namespace_context():
      shared.Instance(id='expired', task_num=0, last_updated=time_expired).put()
      shared.Instance(id='inactive', task_num=-1, last_updated=time_expired).put()
      shared.Instance(id='new', task_num=-1, last_updated=time_current).put()
      shared.Instance(id='current', task_num=2, last_updated=time_current).put()

      handlers._assign_task_num(time_fn=lambda: time_now)

      expired = shared.Instance.get_by_id('expired')
      inactive = shared.Instance.get_by_id('inactive')
      new = shared.Instance.get_by_id('new')
      current = shared.Instance.get_by_id('current')

    self.assertIsNone(expired)
    self.assertIsNone(inactive)
    self.assertIsNotNone(new)
    self.assertIsNotNone(current)
    self.assertEqual(2, current.task_num)
    self.assertEqual(1, new.task_num)


class TSMonJSHandlerTest(test_case.TestCase):
  def setUp(self):
    super(TSMonJSHandlerTest, self).setUp()

    config.reset_for_unittest()
    target = targets.TaskTarget(
        'test_service', 'test_job', 'test_region', 'test_host')
    self.mock_state = interface.State(target=target)
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()
    self.request = webapp2.Request.blank('/_/ts_mon_js')
    self.response = webapp2.Response()
    self.ts_mon_handler = handlers.TSMonJSHandler(
        request=self.request, response=self.response)
    self.ts_mon_handler.register_metrics([
      metrics.BooleanMetric(
          'frontend/boolean_test', 'Boolean metric test',
          field_spec=[metrics.StringField('client_id')]),
    ])
    self.ts_mon_handler.xsrf_is_valid = mock.Mock(return_value=True)
    self.mock_timestamp = 1537821859
    def time_fn():
      return self.mock_timestamp
    self.ts_mon_handler.time_fn = time_fn

  def tearDown(self):
    mock.patch.stopall()
    config.reset_for_unittest()
    super(TSMonJSHandlerTest, self).tearDown()

  def test_time_fn(self):
    """Test self.time_fn."""
    request = webapp2.Request.blank('/_/ts_mon_js')
    response = webapp2.Response()
    ts_mon_handler = handlers.TSMonJSHandler(request, response)
    self.assertTrue(isinstance(ts_mon_handler.time_fn(), float))

  def test_post_metrics_no_metrics(self):
    """Test case when class is not set up properly by calling register_metrics.
    """
    request = webapp2.Request.blank('/_/ts_mon_js')
    response = webapp2.Response()
    ts_mon_handler = handlers.TSMonJSHandler(request=request, response=response)
    ts_mon_handler.post()
    self.assertEqual(response.status_int, 400)
    self.assertIn('No metrics', response.body)

  def test_post_metrics_invalid_json(self):
    """Test case when JSON request body is invalid."""
    self.request.body = 'rutabaga'
    self.ts_mon_handler.post()
    self.assertEqual(self.response.status_int, 400)

  def test_post_metrics_invalid_xsrf(self):
    """Test case when XSRF token is invalid."""
    self.request.body = '{}'
    self.ts_mon_handler.xsrf_is_valid = mock.Mock(return_value=False)
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 403)
    self.ts_mon_handler.xsrf_is_valid.assert_called_once_with({})

  def test_post_metrics_must_be_dict(self):
    """Test case when body is not a dict."""
    self.request.body = '[]'
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertIn('dictionary', self.response.body)

  def test_post_no_metrics_key(self):
    """Test case when dict does not contain 'metrics' key."""
    self.request.body = '{}'
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertIn('Key "metrics"', self.response.body)

  def test_post_metrics_unregistered_metric_name(self):
    """Test case when a metric name isn't registered."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/not_defined',
            'ValueType': 2,
          },
          'Cells': [{
            'value': 'rutabaga',
            'fields': {
              'client_id': '789',
              'rutabaga_id': '789',
            },
          }],
        },
      ],
    })
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertIn('is not defined', self.response.body)

  def test_post_metrics_malcious_metric_name(self):
    """Metric name is echoed back in a safely escaped form."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/not_defined<script>alert(1)</script>',
            'ValueType': 2,
          },
          'Cells': [{
            'value': 'rutabaga',
            'fields': {
              'client_id': '789',
              'rutabaga_id': '789',
            },
          }],
        },
      ],
    })
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertNotIn('<script>', self.response.body)
    self.assertIn('is not defined', self.response.body)

  def test_post_metrics_invalid_fields(self):
    """Test case when metric name is fine but fields are not."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/boolean_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': True,
            'fields': {
              'client_id': '789',
              'rutabaga_id': '789',
            },
          }],
        },
      ],
    })
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertIn('fields do not match', self.response.body)

  def test_post_metrics_maliciou_fields(self):
    """Invalid fields are echoed in a safely escaped format."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/boolean_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': True,
            'fields': {
              'client_id<script>alert(1)</script>': '789',
              'rutabaga_id': '789',
            },
          }],
        },
      ],
    })
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertNotIn('<script>', self.response.body)
    self.assertIn('fields do not match', self.response.body)

  def test_post_rejects_cumulative_without_start_time(self):
    """Test case where start_time is not supplied for CumulativeDistribution."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/cumulative_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': 'rutabaga',
            'fields': {
              'client_id': '789',
            },
          }],
        },
      ],
    })
    self.ts_mon_handler.register_metrics([
      metrics.CumulativeDistributionMetric(
          'frontend/cumulative_test', 'Cumulative metric test',
          field_spec=[metrics.StringField('client_id')]),
    ])
    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertIn('Cumulative metrics', self.response.body)

  def test_post_rejects_start_time_in_future(self):
    """Test rejects when start_time is in the future."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/cumulative_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': 'rutabaga',
            'fields': {
              'client_id': '789',
            },
            'start_time': self.mock_timestamp + 1,
          }],
        },
      ],
    })
    self.ts_mon_handler.register_metrics([
      metrics.CumulativeDistributionMetric(
          'frontend/cumulative_test', 'Cumulative metric test',
          field_spec=[metrics.StringField('client_id')]),
    ])

    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertIn('Invalid start_time', self.response.body)

  def test_post_rejects_start_time_in_past(self):
    """Test rejects when start_time is >1 month in the past."""
    one_month_seconds = 60*60*24*30
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/cumulative_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': 'rutabaga',
            'fields': {
              'client_id': '789',
            },
            'start_time': self.mock_timestamp - one_month_seconds * 2,
          }],
        },
      ],
    })
    self.ts_mon_handler.register_metrics([
      metrics.CumulativeDistributionMetric(
          'frontend/cumulative_test', 'Cumulative metric test',
          field_spec=[metrics.StringField('client_id')]),
    ])

    self.ts_mon_handler.post()

    self.assertEqual(self.response.status_int, 400)
    self.assertIn('Invalid start_time', self.response.body)

  def test_post_distribution_metrics_not_a_dict(self):
    """Test case when a distribution metric value is not a dict."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/cumulative_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': 'rutabaga',
            'fields': {
              'client_id': '789',
            },
            'start_time': self.mock_timestamp - 60,
          }],
        },
      ],
    })
    self.ts_mon_handler.register_metrics([
      metrics.CumulativeDistributionMetric(
          'frontend/cumulative_test', 'Cumulative metric test',
          field_spec=[metrics.StringField('client_id')]),
    ])

    self.ts_mon_handler.post()
    self.assertEqual(self.response.status_int, 400)
    self.assertIn('Distribution metric values must be a dict',
        self.response.body)

  def test_post_metrics_normal(self):
    """Test successful POST case."""
    self.request.body = json.dumps({
      'metrics': [
        {
          'MetricInfo': {
            'Name': 'frontend/boolean_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': True,
            'fields': {
              'client_id': '789',
            },
          }],
        }, {
          'MetricInfo': {
            'Name': 'frontend/cumulative_test',
            'ValueType': 2,
          },
          'Cells': [{
            'value': {
              'sum': 1234,
              'count': 4321,
              'buckets': {
                0: 123,
                1: 321,
                2: 213,
              },
            },
            'fields': {
              'client_id': '789',
            },
            'start_time': self.mock_timestamp - 60,
          }],
        },
      ],
    })
    self.ts_mon_handler.register_metrics([
      metrics.CumulativeDistributionMetric(
          'frontend/cumulative_test', 'Cumulative metric test',
          field_spec=[metrics.StringField('client_id')]),
    ])

    self.ts_mon_handler.post()
    self.assertEqual(self.response.status_int, 201)
