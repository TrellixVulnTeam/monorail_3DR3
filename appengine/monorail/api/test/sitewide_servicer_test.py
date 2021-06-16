# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the sitewide servicer."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import unittest

import mock
from components.prpc import codes
from components.prpc import context
from components.prpc import server

import settings
from api import sitewide_servicer
from api.api_proto import common_pb2
from api.api_proto import sitewide_pb2
from framework import monorailcontext
from framework import xsrf
from services import service_manager
from testing import fake


class SitewideServicerTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = fake.MonorailConnection()
    self.services = service_manager.Services(
        usergroup=fake.UserGroupService(),
        user=fake.UserService())
    self.user_1 = self.services.user.TestAddUser('owner@example.com', 111)
    self.sitewide_svcr = sitewide_servicer.SitewideServicer(
        self.services, make_rate_limiter=False)

  def CallWrapped(self, wrapped_handler, *args, **kwargs):
    return wrapped_handler.wrapped(self.sitewide_svcr, *args, **kwargs)

  @mock.patch('services.secrets_svc.GetXSRFKey')
  @mock.patch('time.time')
  def testRefreshToken(self, mockTime, mockGetXSRFKey):
    """We can refresh an expired token."""
    mockGetXSRFKey.side_effect = lambda: 'fakeXSRFKey'
    # The token is at the brink of being too old
    mockTime.side_effect = lambda: 1 + xsrf.REFRESH_TOKEN_TIMEOUT_SEC

    token_path = 'token_path'
    token = xsrf.GenerateToken(111, token_path, 1)

    request = sitewide_pb2.RefreshTokenRequest(
        token=token, token_path=token_path)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.sitewide_svcr.RefreshToken, mc, request)

    self.assertEqual(
        sitewide_pb2.RefreshTokenResponse(
            token='QSaKMyXhY752g7n8a34HyTo4NjQwMDE=',
            token_expires_sec=870901),
        response)

  @mock.patch('services.secrets_svc.GetXSRFKey')
  @mock.patch('time.time')
  def testRefreshToken_InvalidToken(self, mockTime, mockGetXSRFKey):
    """We reject attempts to refresh an invalid token."""
    mockGetXSRFKey.side_effect = ['fakeXSRFKey']
    mockTime.side_effect = [123]

    token_path = 'token_path'
    token = 'invalidToken'

    request = sitewide_pb2.RefreshTokenRequest(
        token=token, token_path=token_path)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    with self.assertRaises(xsrf.TokenIncorrect):
      self.CallWrapped(self.sitewide_svcr.RefreshToken, mc, request)

  @mock.patch('services.secrets_svc.GetXSRFKey')
  @mock.patch('time.time')
  def testRefreshToken_TokenTooOld(self, mockTime, mockGetXSRFKey):
    """We reject attempts to refresh a token that's too old."""
    mockGetXSRFKey.side_effect = lambda: 'fakeXSRFKey'
    mockTime.side_effect = lambda: 2 + xsrf.REFRESH_TOKEN_TIMEOUT_SEC

    token_path = 'token_path'
    token = xsrf.GenerateToken(111, token_path, 1)

    request = sitewide_pb2.RefreshTokenRequest(
        token=token, token_path=token_path)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')

    with self.assertRaises(xsrf.TokenIncorrect):
      self.CallWrapped(self.sitewide_svcr.RefreshToken, mc, request)

  def testGetServerStatus_Normal(self):
    request = sitewide_pb2.GetServerStatusRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.sitewide_svcr.GetServerStatus, mc, request)

    self.assertEqual(
        sitewide_pb2.GetServerStatusResponse(),
        response)

  @mock.patch('settings.banner_message', 'Message')
  def testGetServerStatus_BannerMessage(self):
    request = sitewide_pb2.GetServerStatusRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.sitewide_svcr.GetServerStatus, mc, request)

    self.assertEqual(
        sitewide_pb2.GetServerStatusResponse(banner_message='Message'),
        response)

  @mock.patch('settings.banner_time', (2019, 6, 13, 18, 30))
  def testGetServerStatus_BannerTime(self):
    request = sitewide_pb2.GetServerStatusRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.sitewide_svcr.GetServerStatus, mc, request)

    self.assertEqual(
        sitewide_pb2.GetServerStatusResponse(banner_time=1560450600),
        response)

  @mock.patch('settings.read_only', True)
  def testGetServerStatus_ReadOnly(self):
    request = sitewide_pb2.GetServerStatusRequest()
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='owner@example.com')
    response = self.CallWrapped(self.sitewide_svcr.GetServerStatus, mc, request)

    self.assertEqual(
        sitewide_pb2.GetServerStatusResponse(read_only=True),
        response)
