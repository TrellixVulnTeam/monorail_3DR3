# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from gae_libs import appengine_util


class AppengineUtilTest(unittest.TestCase):

  @mock.patch.object(
      appengine_util.app_identity,
      'get_application_id',
      side_effect=[
          'findit-for-me-staging',
          'findit-for-me-dev',
      ])
  def testStagingApp(self, _):
    self.assertTrue(appengine_util.IsStaging())
    self.assertTrue(appengine_util.IsStaging())

  @mock.patch.object(
      appengine_util.app_identity,
      'get_application_id',
      side_effect=['findit-for-me'])
  def testNonStagingApp(self, _):
    self.assertFalse(appengine_util.IsStaging())

  @mock.patch.object(appengine_util, 'IsInGAE', return_value=True)
  @mock.patch.object(appengine_util, 'IsStaging', return_value=True)
  def testIsNotProductionApp(self, *_):
    self.assertFalse(appengine_util.IsInProductionApp())

  @mock.patch.object(appengine_util, 'IsInGAE', return_value=True)
  @mock.patch.object(appengine_util, 'IsStaging', return_value=False)
  def testIsProductionApp(self, *_):
    self.assertTrue(appengine_util.IsInProductionApp())

  @mock.patch.object(
      appengine_util.app_identity,
      'get_application_id',
      side_effect=['google.com:findit-for-me'])
  def testIsInternalInstance(self, *_):
    self.assertTrue(appengine_util.IsInternalInstance())
