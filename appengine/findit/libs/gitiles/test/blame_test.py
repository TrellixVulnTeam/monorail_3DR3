# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs.gitiles.blame import Blame, Region


class BlameTest(unittest.TestCase):
  REGION1 = Region(1, 5, 'abc', 'a', 'a@email.com', '2014-08-14 19:38:42')
  REGION1_EXPECTED_JSON = {
      'start': 1,
      'count': 5,
      'revision': 'abc',
      'author_name': 'a',
      'author_email': 'a@email.com',
      'author_time': '2014-08-14 19:38:42'
  }

  REGION2 = Region(6, 10, 'def', 'b', 'b@email.com', '2014-08-19 19:38:42')
  REGION2_EXPECTED_JSON = {
      'start': 6,
      'count': 10,
      'revision': 'def',
      'author_name': 'b',
      'author_email': 'b@email.com',
      'author_time': '2014-08-19 19:38:42'
  }

  def testAddRegions(self):
    blame1 = Blame('def', 'a/c.cc')
    blame1.AddRegions([self.REGION1, self.REGION2])

    blame2 = Blame('def', 'a/c.cc')
    blame2.AddRegion(self.REGION1)
    blame2.AddRegion(self.REGION2)

    self.assertEqual(blame1, blame2)

  def testRegionToDict(self):
    self.assertEqual(self.REGION1_EXPECTED_JSON, self.REGION1.ToDict())
    self.assertEqual(self.REGION2_EXPECTED_JSON, self.REGION2.ToDict())

  def testBlameToDict(self):
    blame = Blame('def', 'a/c.cc')
    blame.AddRegions([self.REGION1, self.REGION2])
    blame_json = blame.ToDict()
    self.assertEqual(3, len(blame_json))
    self.assertEqual('def', blame_json['revision'])
    self.assertEqual('a/c.cc', blame_json['path'])
    self.assertEqual(self.REGION1_EXPECTED_JSON, blame_json['regions'][0])
    self.assertEqual(self.REGION2_EXPECTED_JSON, blame_json['regions'][1])
