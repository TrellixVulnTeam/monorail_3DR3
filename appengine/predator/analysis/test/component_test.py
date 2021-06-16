# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis import component
from analysis import stacktrace


class ComponentTest(unittest.TestCase):
  """Tests ``Component`` class."""

  def testMatchesFilePath(self):
    """Tests ``MatchesFilePath``."""
    component_object = component.Component('name', ['dirs', 'a/b/c'])
    success, directory = component_object.MatchesFilePath('dirs/a.cc')
    self.assertTrue(success)
    self.assertEqual(directory, 'dirs')

    success, directory = component_object.MatchesFilePath('dummy')
    self.assertFalse(success)
    self.assertIsNone(directory, 'dirs')

  def testMatchesLowerCaseFilePath(self):
    """Tests ``MatchesFilePath`` matches lower case file paths."""
    component_object = component.Component('name', ['Dirs', 'A/B/C'])
    success, directory = component_object.MatchesFilePath('dirs/a.cc')
    self.assertTrue(success)
    self.assertEqual(directory, 'Dirs')

    success, directory = component_object.MatchesFilePath('a/b/c/d.h')
    self.assertTrue(success)
    self.assertEqual(directory, 'A/B/C')
