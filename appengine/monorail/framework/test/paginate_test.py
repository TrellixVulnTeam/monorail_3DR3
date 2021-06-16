# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for pagination classes."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from google.appengine.ext import testbed

from framework import exceptions
from framework import paginate
from testing import testing_helpers
from proto import secrets_pb2


class PageTokenTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def testGeneratePageToken_DiffRequests(self):
    request_cont_1 = secrets_pb2.ListRequestContents(
        parent='same', page_size=1, order_by='same', query='same')
    request_cont_2 = secrets_pb2.ListRequestContents(
        parent='same', page_size=2, order_by='same', query='same')
    start = 10
    self.assertNotEqual(
        paginate.GeneratePageToken(request_cont_1, start),
        paginate.GeneratePageToken(request_cont_2, start))

  def testValidateAndParsePageToken(self):
    request_cont_1 = secrets_pb2.ListRequestContents(
        parent='projects/chicken', page_size=1, order_by='boks', query='hay')
    start = 2
    token = paginate.GeneratePageToken(request_cont_1, start)
    self.assertEqual(
        start,
        paginate.ValidateAndParsePageToken(token, request_cont_1))

  def testValidateAndParsePageToken_InvalidContents(self):
    request_cont_1 = secrets_pb2.ListRequestContents(
        parent='projects/chicken', page_size=1, order_by='boks', query='hay')
    start = 2
    token = paginate.GeneratePageToken(request_cont_1, start)

    request_cont_diff = secrets_pb2.ListRequestContents(
        parent='projects/goose', page_size=1, order_by='boks', query='hay')
    with self.assertRaises(exceptions.PageTokenException):
      paginate.ValidateAndParsePageToken(token, request_cont_diff)

  def testValidateAndParsePageToken_InvalidSerializedToken(self):
    request_cont = secrets_pb2.ListRequestContents()
    with self.assertRaises(exceptions.PageTokenException):
      paginate.ValidateAndParsePageToken('sldkfj87', request_cont)

  def testValidateAndParsePageToken_InvalidTokenFormat(self):
    request_cont = secrets_pb2.ListRequestContents()
    with self.assertRaises(exceptions.PageTokenException):
      paginate.ValidateAndParsePageToken('///sldkfj87', request_cont)


class PaginateTest(unittest.TestCase):

  def testVirtualPagination(self):
    # Paginating 0 results on a page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list')
    total_count = 0
    items_per_page = 100
    start = 0
    vp = paginate.VirtualPagination(total_count, items_per_page, start)
    self.assertEqual(vp.num, 100)
    self.assertEqual(vp.start, 1)
    self.assertEqual(vp.last, 0)
    self.assertFalse(vp.visible)

    # Paginating 12 results on a page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list')
    vp = paginate.VirtualPagination(12, 100, 0)
    self.assertEqual(vp.num, 100)
    self.assertEqual(vp.start, 1)
    self.assertEqual(vp.last, 12)
    self.assertTrue(vp.visible)

    # Paginating 12 results on a page that can hold 10.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list?num=10')
    vp = paginate.VirtualPagination(12, 10, 0)
    self.assertEqual(vp.num, 10)
    self.assertEqual(vp.start, 1)
    self.assertEqual(vp.last, 10)
    self.assertTrue(vp.visible)

    # Paginating 12 results starting at 5 on page that can hold 10.
    mr = testing_helpers.MakeMonorailRequest(
        path='/issues/list?start=5&num=10')
    vp = paginate.VirtualPagination(12, 10, 5)
    self.assertEqual(vp.num, 10)
    self.assertEqual(vp.start, 6)
    self.assertEqual(vp.last, 12)
    self.assertTrue(vp.visible)

    # Paginating 123 results on a page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list')
    vp = paginate.VirtualPagination(123, 100, 0)
    self.assertEqual(vp.num, 100)
    self.assertEqual(vp.start, 1)
    self.assertEqual(vp.last, 100)
    self.assertTrue(vp.visible)

    # Paginating 123 results on second page that can hold 100.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list?start=100')
    vp = paginate.VirtualPagination(123, 100, 100)
    self.assertEqual(vp.num, 100)
    self.assertEqual(vp.start, 101)
    self.assertEqual(vp.last, 123)
    self.assertTrue(vp.visible)

    # Paginating a huge number of objects will show at most 1000 per page.
    mr = testing_helpers.MakeMonorailRequest(path='/issues/list?num=9999')
    vp = paginate.VirtualPagination(12345, 9999, 0)
    self.assertEqual(vp.num, 1000)
    self.assertEqual(vp.start, 1)
    self.assertEqual(vp.last, 1000)
    self.assertTrue(vp.visible)

    # Test urls for a hotlist pagination
    mr = testing_helpers.MakeMonorailRequest(
        path='/u/hotlists/17?num=5&start=4')
    mr.hotlist_id = 17
    mr.auth.user_id = 112
    vp = paginate.VirtualPagination(12, 5, 4,
                                    list_page_url='/u/112/hotlists/17')
    self.assertEqual(vp.num, 5)
    self.assertEqual(vp.start, 5)
    self.assertEqual(vp.last, 9)
    self.assertTrue(vp.visible)
    self.assertEqual('/u/112/hotlists/17?num=5&start=9', vp.next_url)
    self.assertEqual('/u/112/hotlists/17?num=5&start=0', vp.prev_url)
