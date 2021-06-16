# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the client config service."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import base64
import unittest

from services import client_config_svc


class LoadApiClientConfigsTest(unittest.TestCase):

  class FakeResponse(object):
    def __init__(self, content):
      self.content = content

  def setUp(self):
    self.handler = client_config_svc.LoadApiClientConfigs()

  def testProcessResponse_InvalidJSON(self):
    r = self.FakeResponse('}{')
    with self.assertRaises(ValueError):
      self.handler._process_response(r)

  def testProcessResponse_NoContent(self):
    r = self.FakeResponse('{"wrong-key": "some-value"}')
    with self.assertRaises(KeyError):
      self.handler._process_response(r)

  def testProcessResponse_NotB64(self):
    # 'asd' is not a valid base64-encoded string.
    r = self.FakeResponse('{"content": "asd"}')
    with self.assertRaises(TypeError):
      self.handler._process_response(r)

  def testProcessResponse_NotProto(self):
    # 'asdf' is a valid base64-encoded string.
    r = self.FakeResponse('{"content": "asdf"}')
    with self.assertRaises(Exception):
      self.handler._process_response(r)

  def testProcessResponse_Success(self):
    with open(client_config_svc.CONFIG_FILE_PATH) as f:
      r = self.FakeResponse('{"content": "%s"}' % base64.b64encode(f.read()))
    c = self.handler._process_response(r)
    assert '123456789.apps.googleusercontent.com' in c


class ClientConfigServiceTest(unittest.TestCase):

  def setUp(self):
    self.client_config_svc = client_config_svc.GetClientConfigSvc()
    self.client_email = '123456789@developer.gserviceaccount.com'
    self.client_id = '123456789.apps.googleusercontent.com'

  def testGetDisplayNames(self):
    display_names_map = self.client_config_svc.GetDisplayNames()
    self.assertIn(self.client_email, display_names_map)
    self.assertEqual('johndoe@example.com',
                     display_names_map[self.client_email])

  def testGetQPMDict(self):
    qpm_map = self.client_config_svc.GetQPM()
    self.assertIn(self.client_email, qpm_map)
    self.assertEqual(1, qpm_map[self.client_email])
    self.assertNotIn('bugdroid1@chromium.org', qpm_map)

  def testGetClientIDEmails(self):
    auth_client_ids, auth_emails = self.client_config_svc.GetClientIDEmails()
    self.assertIn(self.client_id, auth_client_ids)
    self.assertIn(self.client_email, auth_emails)

  def testForceLoad(self):
    EXPIRES_IN = client_config_svc.ClientConfigService.EXPIRES_IN
    NOW = 1493007338
    # First time it will always read the config
    self.client_config_svc.load_time = NOW
    self.client_config_svc.GetConfigs(use_cache=True)
    self.assertNotEqual(NOW, self.client_config_svc.load_time)

    # use_cache is false and it will read the config
    self.client_config_svc.load_time = NOW
    self.client_config_svc.GetConfigs(
        use_cache=False, cur_time=NOW + 1)
    self.assertNotEqual(NOW, self.client_config_svc.load_time)

    # Cache expires after some time and it will read the config
    self.client_config_svc.load_time = NOW
    self.client_config_svc.GetConfigs(
        use_cache=True, cur_time=NOW + EXPIRES_IN + 1)
    self.assertNotEqual(NOW, self.client_config_svc.load_time)

    # otherwise it should just use the cache
    self.client_config_svc.load_time = NOW
    self.client_config_svc.GetConfigs(
        use_cache=True, cur_time=NOW + EXPIRES_IN - 1)
    self.assertEqual(NOW, self.client_config_svc.load_time)


class ClientConfigServiceFunctionsTest(unittest.TestCase):

  def setUp(self):
    self.client_email = '123456789@developer.gserviceaccount.com'

  def testGetServiceAccountMap(self):
    service_account_map = client_config_svc.GetServiceAccountMap()
    self.assertIn(self.client_email, service_account_map)
    self.assertEqual(
        'johndoe@example.com',
        service_account_map[self.client_email])
    self.assertNotIn('bugdroid1@chromium.org', service_account_map)

  def testGetQPMDict(self):
    qpm_map = client_config_svc.GetQPMDict()
    self.assertIn(self.client_email, qpm_map)
    self.assertEqual(1, qpm_map[self.client_email])
    self.assertNotIn('bugdroid1@chromium.org', qpm_map)
