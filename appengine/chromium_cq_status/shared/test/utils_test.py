# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contextlib import contextmanager
from datetime import datetime
import os

from webtest.app import AppError
from third_party.testing_utils import testing
import main
from shared import utils



class MockWebApp(object):
  def __init__(self):
    self.response = MockResponse()

class MockResponse(object):
  def __init__(self):
    self.body = ''
    self.headers = MockHeaders()

  def write(self, text):
    self.body += text

class MockHeaders(object):
  def __init__(self):
    self.is_cross_origin = False
    self.is_json_content = False

  def add_header(self, key, value): # pragma: no cover
    if key == "Access-Control-Allow-Origin":
      self.is_cross_origin = (value == "*")
    elif key == 'Content-Type':
      self.is_json_content = (value == 'application/json')


@contextmanager
def mock_host_acls(acls):
  old = utils.HOST_ACLS['Development']
  try:
    utils.HOST_ACLS['Development'] = acls
    yield
  finally:
    utils.HOST_ACLS['Development'] = old


class TestPermissions(testing.AppengineTestCase):
  app_module = main.app

  def test_has_permission_chromium(self):
    with mock_host_acls(utils.HOST_ACLS['chromium-cq-status.appspot.com']):
      # No user.
      self.assertTrue(utils.has_permission('read'))
      self.assertFalse(utils.has_permission('write'))

      self.mock_current_user('random', 'random@person.com')
      self.assertTrue(utils.has_permission('read'))
      self.assertFalse(utils.has_permission('write'))

      self.mock_current_user(is_admin=True)
      self.assertTrue(utils.has_permission('read'))
      self.assertTrue(utils.has_permission('write'))

      self.mock_current_user('real', 'real@chromium.org')
      self.assertTrue(utils.has_permission('read'))
      self.assertTrue(utils.has_permission('write'))

      self.mock_current_user('real', 'real@google.com')
      self.assertTrue(utils.has_permission('read'))
      self.assertTrue(utils.has_permission('write'))

  def test_has_permission_internal(self):
    with mock_host_acls(utils.HOST_ACLS['internal-cq-status.appspot.com']):
      # No user.
      self.assertFalse(utils.has_permission('read'))
      self.assertFalse(utils.has_permission('write'))

      self.mock_current_user('random', 'random@person.com')
      self.assertFalse(utils.has_permission('read'))
      self.assertFalse(utils.has_permission('write'))

      self.mock_current_user(is_admin=True)
      self.assertTrue(utils.has_permission('read'))
      self.assertTrue(utils.has_permission('write'))

      self.mock_current_user('real', 'real@chromium.org')
      self.assertFalse(utils.has_permission('read'))
      self.assertFalse(utils.has_permission('write'))

      self.mock_current_user('real', 'real@google.com')
      self.assertTrue(utils.has_permission('read'))
      self.assertTrue(utils.has_permission('write'))

  def test_read_access_decorator(self):
    # No user, which has read access.
    self.assertTrue(utils.has_permission('read'))
    self.test_app.get('/recent')

    # Simulate read access requiring valid user.
    with mock_host_acls(utils.HOST_ACLS['internal-cq-status.appspot.com']):
      self.assertFalse(utils.has_permission('read'))
      self.test_app.get('/recent')

  def test_host_permissions(self):
    try:
      old = os.environ.pop('SERVER_SOFTWARE')
      utils.HOST_ACLS[None] = {'read': 'something', 'write': True}
      self.assertEqual(utils.get_host_permissions('read'), 'something')
    finally:
      utils.HOST_ACLS.pop(None)
      os.environ['SERVER_SOFTWARE'] = old

  def test_password_sha1(self):
    self.assertEquals(
        '018d644a17b71b65cef51fa0a523a293f2b3266f',
        utils.password_sha1('cq'))


class TestUtils(testing.AppengineTestCase):
  def test_filter_dict(self):
    self.assertEquals(
        {'b': 2, 'c': 3},
        utils.filter_dict({'a': 1, 'b': 2, 'c': 3}, ('b', 'c', 'd')))

  def test_to_unix_timestamp(self):
    self.assertEquals(100,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100)))
    self.assertEquals(100.1,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100.1)))
    self.assertEquals(100.5,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100.5)))
    self.assertEquals(100.9,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(100.9)))
    self.assertEquals(-100,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(-100)))
    self.assertEquals(-100.1,
        utils.to_unix_timestamp(datetime.utcfromtimestamp(-100.1)))

  def test_compressed_json_dumps(self):
    self.assertEquals('{"a":["0",1,2.5],"b":null}',
        utils.compressed_json_dumps({'a': ['0', 1, 2.5], 'b': None}))

  def test_cross_origin_json_success(self):
    webapp = MockWebApp()
    @utils.cross_origin_json
    def produce_json(self): # pylint: disable=W0613
      return {'valid': True}
    produce_json(webapp)
    self.assertEquals('{"valid":true}', webapp.response.body)
    self.assertTrue(webapp.response.headers.is_cross_origin)
    self.assertTrue(webapp.response.headers.is_json_content)

  def test_cross_origin_json_falsey_success(self):
    webapp = MockWebApp()
    @utils.cross_origin_json
    def produce_falsey_json(self): # pylint: disable=W0613
      return False
    produce_falsey_json(webapp)
    self.assertEquals('false', webapp.response.body)
    self.assertTrue(webapp.response.headers.is_cross_origin)
    self.assertTrue(webapp.response.headers.is_json_content)

  def test_cross_origin_json_fail(self):
    webapp = MockWebApp()
    @utils.cross_origin_json
    def produce_no_json(self): # pylint: disable=W0613
      pass
    produce_no_json(webapp)
    self.assertEquals('', webapp.response.body)
    self.assertTrue(webapp.response.headers.is_cross_origin)
    self.assertFalse(webapp.response.headers.is_json_content)

  def test_memcachize(self):
    use_cache = False
    def check(cache_timestamp, kwargs): # pylint: disable=W0613
      return use_cache
    c = 0
    @utils.memcachize(cache_check=check)
    def test(a, b):
      return a + b + c
    self.assertEquals(test(a=1, b=2), 3)
    c = 1
    use_cache = True
    self.assertEquals(test(a=1, b=2), 3)
    self.assertEquals(test(a=2, b=1), 4)
    use_cache = False
    self.assertEquals(test(a=1, b=2), 4)

  def test_memcachize_limit(self):
    large_value = '0' * long(2e6)
    @utils.memcachize(cache_check=None)
    def get_large_value():
      return large_value
    self.assertEquals(get_large_value(), large_value)
    self.assertEquals(get_large_value(), large_value)

  def test_is_gerrit_issue(self):
    self.assertTrue(utils.is_gerrit_issue('123'))
    self.assertTrue(utils.is_gerrit_issue('123123'))
    self.assertFalse(utils.is_gerrit_issue('123123123'))
    self.assertFalse(utils.is_gerrit_issue('werid stuff'))

  def test_guess_legacy_codereview_hostname(self):
    self.assertEquals(utils.guess_legacy_codereview_hostname('123'),
                      'chromium-review.googlesource.com')
    self.assertEquals(utils.guess_legacy_codereview_hostname(1234567),
                      'codereview.chromium.org')

  def test_get_full_patchset_url(self):
    self.assertEquals(
        utils.get_full_patchset_url(
          'chromium-review.googlesource.com', '123', '567'),
        'https://chromium-review.googlesource.com/#/c/123/567')
    self.assertEquals(
        utils.get_full_patchset_url('codereview.chromium.org', '123', '567'),
        'https://codereview.chromium.org/123/#ps567')
