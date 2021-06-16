# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os.path
import shutil
import sys
import tempfile
import time
import unittest

import mock

from infra.services.service_manager import cloudtail_factory
from infra.services.service_manager import config_watcher
from infra.services.service_manager import service
from infra.services.service_manager import service_thread


class ParseConfigTest(unittest.TestCase):
  def test_minimal_config(self):
    c = config_watcher.parse_config('{"name": "foo", "cmd": []}')
    self.assertEquals({'name': 'foo', 'cmd': []}, c)

  def test_name_required(self):
    c = config_watcher.parse_config('{"cmd": []}')
    self.assertIsNone(c)

  def test_cmd_required(self):
    c = config_watcher.parse_config('{"name": "foo"}')
    self.assertIsNone(c)
    c = config_watcher.parse_config('{"name": "foo", "cmd": "not-a-list"}')
    self.assertIsNone(c)

  def test_cmd_stringifies(self):
    c = config_watcher.parse_config('{"name": "foo", "cmd": [1, 2]}')
    self.assertEquals(['1', '2'], c['cmd'])


class ConfigWatcherTest(unittest.TestCase):
  def setUp(self):
    self.config_directory = tempfile.mkdtemp()

    self.mock_sleep = mock.create_autospec(time.sleep, spec_set=True)

    self.mock_ownservice_ctor = mock.patch(
        'infra.services.service_manager.service.OwnService',
        autospec=True).start()
    self.mock_thread_ctor = mock.patch(
        'infra.services.service_manager.service_thread.ServiceThread',
        autospec=True).start()
    self.mock_thread = self.mock_thread_ctor.return_value
    self.mock_ownservice = self.mock_ownservice_ctor.return_value
    self.mock_ownservice.start.return_value = True
    self.mock_ownservice.has_version_changed.return_value = False
    self.mock_cloudtail = cloudtail_factory.DummyCloudtailFactory()

    self.cw = config_watcher.ConfigWatcher(
        self.config_directory,
        42,
        43,
        '/state',
        '/rootdir',
        self.mock_cloudtail,
        _sleep_fn=self.mock_sleep)

  def tearDown(self):
    mock.patch.stopall()

    shutil.rmtree(self.config_directory)

  def _set_config(self, name, contents, mtime=None):
    filename = os.path.join(self.config_directory, name)
    with open(filename, 'w') as fh:
      fh.write(contents)
    if mtime is not None:
      os.utime(filename, (mtime, mtime))

  def _remove_config(self, name):
    os.unlink(os.path.join(self.config_directory, name))

  @mock.patch('os._exit', autospec=True)
  def test_already_running(self, mock_exit):
    self.mock_ownservice.start.return_value = False
    mock_exit.side_effect = SystemExit

    with self.assertRaises(SystemExit):
      self.cw.run()

    self.assertFalse(self.mock_sleep.called)
    mock_exit.assert_called_once_with(0)

  def test_version_changed(self):
    self.mock_ownservice.has_version_changed.return_value = True

    self.cw._iteration()
    self.assertTrue(self.cw._stop)

  def test_add(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}')

    self.cw._iteration()

    self.mock_thread_ctor.assert_called_once_with(
        43,
        '/state',
        {'name': 'foo', 'cmd': ['baz']},
        self.mock_cloudtail)
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

  def test_invalid_cmd(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": "foo"}')
    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

  def test_add_invalid_json(self):
    self._set_config('foo.json', '{"name": ')
    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

  def test_missing_required_fields(self):
    # for coverage, essentially.
    self._set_config('foo.json', '{}')
    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

  def test_add_filename_does_not_match_name(self):
    self._set_config(
      'foo.json',
      '{"name": "bar", "cmd": ["baz"]}')

    self.cw._iteration()

    self.mock_thread_ctor.assert_called_once_with(
        43,
        '/state',
        {'name': 'bar', 'cmd': ['baz']},
        self.mock_cloudtail)
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

  def test_add_duplicate_name(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}')
    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)

    self._set_config(
      'bar.json',
      '{"name": "foo", "cmd": ["baz"]}')
    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)

  def test_change(self):
    self._set_config(
      'foo.json',
      """{"name": "foo",
          "cmd": ["whatever.tool"]
         }
      """,
      100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(
        43,
        '/state',
        {'name': 'foo',
         'cmd': ['whatever.tool']},
        self.mock_cloudtail)

    self._set_config(
      'foo.json',
      """{"name": "foo",
          "cmd": ["whatever.tool", "1", "2", "3"]
         }
      """,
      200)

    self.cw._iteration()
    self.mock_thread.restart_with_new_config.assert_called_once_with(
        {'name': 'foo',
         'cmd': ['whatever.tool', '1', '2', '3']}
    )

  def test_change_duplicate_name(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}',
      100)
    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)
    self.assertEqual(1, self.mock_thread.start_service.call_count)
    self.assertEqual(0, self.mock_thread.stop_service.call_count)

    self._set_config(
      'bar.json',
      '{"name": "bar", "cmd": ["baz"]}',
      200)
    self.cw._iteration()
    self.assertEqual(2, self.mock_thread_ctor.call_count)
    self.assertEqual(2, self.mock_thread.start_service.call_count)
    self.assertEqual(0, self.mock_thread.stop_service.call_count)

    self._set_config(
      'bar.json',
      '{"name": "foo", "cmd": ["baz"]}',
      300)
    self.cw._iteration()
    self.assertEqual(2, self.mock_thread_ctor.call_count)
    self.assertEqual(2, self.mock_thread.start_service.call_count)
    self.assertEqual(1, self.mock_thread.stop_service.call_count)

  def test_add_bad_config_then_change(self):
    self._set_config('foo.json', '{"name": ', 100)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}',
      200)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(
        43,
        '/state',
        {'name': 'foo', 'cmd': ['baz']},
        self.mock_cloudtail)
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

  def test_add_bad_config_then_remove(self):
    self._set_config('foo.json', '{"name": ', 100)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    self._remove_config('foo.json')

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

  def test_add_good_config_then_make_bad(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}',
      100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(
        43,
        '/state',
        {'name': 'foo', 'cmd': ['baz']},
        self.mock_cloudtail)
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

    self._set_config('foo.json', '{"name": ', 200)

    self.cw._iteration()
    self.mock_thread.stop_service.assert_called_once_with()

  def test_add_bad_config_then_touch(self):
    self._set_config('foo.json', '{"name": }', 100)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    self._set_config('foo.json', '{"name": ', 200)

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

  def test_remove_config(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}',
      100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(
        43,
        '/state',
        {'name': 'foo',
         'cmd': ['baz']
        },
        self.mock_cloudtail)
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

    self._remove_config('foo.json')

    self.cw._iteration()
    self.mock_thread.stop_service.assert_called_once_with()

  def test_remove_and_add_config_again(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}',
      100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(
        43, '/state',
        {'name': 'foo',
         'cmd': ['baz']
        },
        self.mock_cloudtail)
    self.mock_thread.start.assert_called_once_with()
    self.mock_thread.start_service.assert_called_once_with()

    self._remove_config('foo.json')

    self.cw._iteration()
    self.mock_thread.stop_service.assert_called_once_with()

    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}',
      100)

    self.cw._iteration()
    self.assertEqual(1, self.mock_thread_ctor.call_count)
    self.assertEqual(1, self.mock_thread.start_service.call_count)
    self.mock_thread.restart_with_new_config.assert_called_once_with(
        {'name': 'foo',
         'cmd': ['baz']
        })

  def test_run_stop(self):
    self._set_config(
      'foo.json',
      '{"name": "foo", "cmd": ["baz"]}',
      100)

    self.cw._iteration()
    self.mock_thread_ctor.assert_called_once_with(
        43,
        '/state',
        {'name': 'foo', 'cmd': ['baz']},
        self.mock_cloudtail)

    def sleep_impl(_duration):
      self.cw.stop()
    self.mock_sleep.side_effect = sleep_impl

    self.cw.run()

    self.mock_sleep.assert_called_once_with(42)
    self.mock_thread.stop.assert_called_once_with()
    self.assertFalse(self.mock_thread.stop_service.called)

  def test_run_stop_bad_config(self):
    self._set_config('foo.json', '{"name": ')

    self.cw._iteration()
    self.assertFalse(self.mock_thread_ctor.called)

    def sleep_impl(_duration):
      self.cw.stop()
    self.mock_sleep.side_effect = sleep_impl

    self.cw.run()

    self.mock_sleep.assert_called_once_with(42)
    self.assertFalse(self.mock_thread_ctor.called)
