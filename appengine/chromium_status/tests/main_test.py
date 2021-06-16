#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import json
import logging
import optparse
import os
import re
import sys
import unittest
import urllib2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import local_gae


class TestCase(unittest.TestCase):
  def setUp(self):
    super(TestCase, self).setUp()
    # Restart the server on each test. It's a bit slow but safer.
    self.local_gae = local_gae.LocalGae()
    self.local_gae.start_server(logging.getLogger().isEnabledFor(logging.DEBUG))
    self.url = 'http://127.0.0.1:%d/' % self.local_gae.port
    self.clear_cookies()

  def tearDown(self):
    if self.local_gae:
      self.local_gae.stop_server()
    self.local_gae = None
    super(TestCase, self).tearDown()

  def get(self, suburl):
    return self.local_gae.get(suburl)

  def post(self, suburl, data):
    return self.local_gae.post(suburl, data)

  def clear_cookies(self):
    self.local_gae.clear_cookies()

  def login(self, username, admin=False):
    self.local_gae.login(username, admin)

  def set_admin_pwd(self, password):
    # There will be no entities until main() has been called. So do a dummy
    # request first.
    hashvalue = hashlib.sha1(password).hexdigest()
    try:
      self.get('doesnt_exist')
    except urllib2.HTTPError:
      pass

    output = self.local_gae.query(
        'import base_page\n'

        # First verify the default value exists.
        'n = db.GqlQuery("SELECT * FROM Passwords").count()\n'
        'assert n == 1, "n == 1"\n'

        # Then override its value with |password|.
        'p = db.GqlQuery("SELECT * FROM Passwords").get()\n'
        + ('p.password_sha1 = %r\n' % hashvalue) +
        'p.put()\n'
        'print db.GqlQuery("SELECT * FROM Passwords").count(),\n')
    self.assertEqual(output, '1')

  def set_global_config(self, app_name, public_access):
    cmd = (
        'import base_page\n'

        # Verify the default config exists.
        'n = db.GqlQuery("SELECT * FROM GlobalConfig").count()\n'
        'assert n == 1, "n == 1"\n'

        # Then make sure access is sane.
        'config = base_page.GlobalConfig(app_name=%r)\n' % app_name +
        'config.public_access = %r\n' % public_access +
        'config.put()\n'
        'print "ok",\n'
    )
    output = self.local_gae.query(cmd)
    self.assertEqual(output, 'ok')


class PublicTestCase(TestCase):
  def setUp(self):
    super(PublicTestCase, self).setUp()
    self.set_global_config(app_name='bogus_app', public_access=True)


class StatusTest(PublicTestCase):
  def test_all_status(self):
    out = self.get('allstatus').splitlines()
    out = [i for i in out if i]
    self.assertEquals(2, len(out))
    self.assertEquals('Who,When,GeneralStatus,Message', out[0])
    self.assertTrue(
        re.match('none,.+?, \d+?, .+?,open,welcome to status', out[1]), out[1])

  def test_status(self):
    self.assertEqual('1', self.get('status'))

  def test_current(self):
    out = self.get('current')
    self.assertTrue(100 < len(out))
    self.assertTrue(out.startswith('<html>'))

  def test_current_raw(self):
    # Default value.
    self.assertEqual('welcome to status', self.get('current?format=raw'))

  def test_current_json(self):
    # pylint: disable=E1103
    out = json.loads(self.get('current?format=json'))
    expected = [
        'date', 'username', 'message', 'general_state', 'can_commit_freely',
    ]
    # TODO(maruel): Test actual values.
    self.assertEqual(sorted(expected), sorted(out.keys()))

  def test_status_push(self):
    self.assertEqual('welcome to status', self.get('current?format=raw'))
    self.assertEqual('welcome to status', self.get('current?format=raw'))
    # Set a password, force status with password.
    self.set_admin_pwd('bleh')
    data = {
        'message': 'foo',
        'password': 'bleh',
        'username': 'user1',
    }
    self.assertEqual('OK', self.post('status', data))
    self.assertEqual('foo', self.get('current?format=raw'))
    data['message'] = 'bar'
    data['password'] = 'wrong password'
    self.assertRaises(urllib2.HTTPError, self.post, 'status', data)
    # Wasn't updated since the password was wrong.
    self.assertEqual('foo', self.get('current?format=raw'))
    data['message'] = 'boo'
    data['password'] = 'bleh'
    self.assertEqual('OK', self.post('status', data))
    self.assertEqual('boo', self.get('current?format=raw'))

  def test_root(self):
    self.assertTrue(100 < len(self.get('')))


class LkgrTest(PublicTestCase):
  def test_lkgr(self):
    self.assertEqual('', self.get('lkgr'))

  def test_lkgr_set(self):
    self.set_admin_pwd('bleh')
    data = {
        'revision': 42,
        'password': 'bleh',
        'success': '1',
        'steps': '',
    }
    out = self.post('revisions', data)
    self.assertEqual('', out)
    self.assertEqual('42', self.get('lkgr'))
    self.assertRaises(urllib2.HTTPError, self.get, 'git-lkgr')
    data['git_hash'] = 'c305f265aba93cc594a0fece50346c3af7fe3301'
    out = self.post('revisions', data)
    self.assertEqual('', out)
    self.assertEqual('c305f265aba93cc594a0fece50346c3af7fe3301',
                     self.get('git-lkgr'))
    data['password'] = 'wrongpassword'
    data['revision'] = 23
    self.assertRaises(urllib2.HTTPError, self.post, 'revisions', data)
    self.assertEqual('42', self.get('lkgr'))
    self.assertEqual('c305f265aba93cc594a0fece50346c3af7fe3301',
                     self.get('git-lkgr'))
    data['password'] = 'bleh'
    data['revision'] = 31337
    out = self.post('revisions', data)
    self.assertEqual('', out)
    self.assertEqual('31337', self.get('lkgr'))
    self.assertEqual('c305f265aba93cc594a0fece50346c3af7fe3301',
                     self.get('git-lkgr'))
    data['git_hash'] = '988881adc9fc3655077dc2d4d757d480b5ea0e11'
    out = self.post('revisions', data)
    self.assertEqual('', out)
    self.assertEqual('31337', self.get('lkgr'))
    self.assertEqual('988881adc9fc3655077dc2d4d757d480b5ea0e11',
                     self.get('git-lkgr'))


class AccessControl(TestCase):
  def _check_post_thru_ui(self, fails=False, fails_main_page=False):
    if fails_main_page:
      self.assertRaises(urllib2.HTTPError, self.get, '')
      self.assertRaises(
          urllib2.HTTPError, self.post, '',
          {'message': 'foo', 'last_status_key': 'junk'})
    else:
      main_page = self.get('')
      last_status_key = re.search(
          r'name="last_status_key" value="(.*?)"', main_page)
      if fails:
        # last_status_key doesn't appear if you aren't an admin.
        self.assertEqual(None, last_status_key)
        self.assertRaises(
            urllib2.HTTPError, self.post, '',
            {'message': 'foo', 'last_status_key': 'junk'})
      else:
        self.post('', {'message': 'foo',
                  'last_status_key': last_status_key.group(1)})
        self.assertEqual('foo', self.get('current?format=raw'))

  def _check_current_page(self, fails=False, seeks_login=False):
    if fails:
      self.assertRaises(urllib2.HTTPError, self.get, 'current')
    elif seeks_login:
      out = self.get('current')
      self.assertTrue(100 < len(out))
      self.assertTrue(out.startswith('<html>'))
      self.assertTrue('Login Required' in out)
    else:
      out = self.get('current')
      self.assertTrue(100 < len(out))
      self.assertTrue(out.startswith('<html>'))
      self.assertTrue('<title>Login</title>' not in out)
      self.assertTrue('Login Required' not in out)

  def _check_current_raw_page(self, fails=False, seeks_login=False):
    if fails:
      self.assertRaises(urllib2.HTTPError, self.get, 'current?format=raw')
    elif seeks_login:
      out = self.get('current?format=raw')
      self.assertTrue(100 < len(out))
      self.assertTrue(out.startswith('<html>'))
      self.assertTrue('<title>Login</title>' in out)
    else:
      out = self.get('current?format=raw')
      self.assertTrue(not out.startswith('<html>'))
      self.assertTrue('<title>Login</title>' not in out)
      self.assertTrue('Login Required' not in out)

  def _check_post_thru_status_fails(self):
    self.assertRaises(urllib2.HTTPError, self.post,
                      'status', {'message': 'foo'})

  def test_default_denies_chromium(self):
    # Confirm default config does not allow chromium.org access.
    self.login('bob@chromium.org')
    self._check_current_page(fails=True)
    self._check_current_raw_page(fails=True)
    self._check_post_thru_ui(fails=True, fails_main_page=True)
    self._check_post_thru_status_fails()

  def test_private_requires_login(self):
    # Confirm private access redirects to a login screen.
    self._check_current_page(seeks_login=True)
    self._check_current_raw_page(seeks_login=True)

  def test_private_allows_google(self):
    self.login('bob@google.com')
    self._check_current_page()
    self._check_current_raw_page()
    self._check_post_thru_ui()
    # Status, however, requires bot login.
    self._check_post_thru_status_fails()

  def test_private_denies_other(self):
    self.login('bob@example.com')
    self._check_current_page(fails=True)
    self._check_current_raw_page(fails=True)
    self._check_post_thru_ui(fails=True, fails_main_page=True)
    self._check_post_thru_status_fails()

  def test_public_allows_chromium(self):
    self.set_global_config(app_name='foo', public_access=True)
    self.login('bob@chromium.org')
    self._check_current_page()
    self._check_current_raw_page()
    self._check_post_thru_ui()
    # Status, however, requires bot login.
    self._check_post_thru_status_fails()

  def test_public_is_limited(self):
    self.set_global_config(app_name='foo', public_access=True)
    self.login('bar@baz.com')
    self._check_current_page()
    self._check_current_raw_page()
    self._check_post_thru_ui(fails=True)
    self._check_post_thru_status_fails()

  def test_non_bot_admins_cant_forge(self):
    self.login('admin@google.com')
    data = {
        'message': 'foo',
        'username': 'bogus@google.com',
    }
    self.assertRaises(urllib2.HTTPError, self.post, 'status', data)
    self.assertNotEqual('foo', self.get('current?format=raw'))

  def test_update_global_config(self):
    """Verify updating the global config affects the active instance"""
    result = self.local_gae.query(
        'import base_page\n'

        # Verify the default config exists.
        'n = base_page.GlobalConfig.all().count()\n'
        'assert n == 1, "n == 1"\n'

        # Verify there is a config, and shows False.
        'q = base_page.GlobalConfig.all()\n'
        'assert q.count() == 1, "q.count() == 1"\n'
        'config = q.get()\n'
        'assert not config.public_access, "not config.public_access"\n'

        # Make the instance public.
        'config.public_access = True\n'
        'config.put()\n'
        'print "ok",\n')
    self.assertEqual('ok', result)
    # Login and try various operations.
    self.login('bob@chromium.org')
    self._check_current_page()
    self._check_current_raw_page()
    self._check_post_thru_ui()
    # Verify the config now shows True.
    result = self.local_gae.query(
        'import base_page\n'
        'q = base_page.GlobalConfig.all()\n'
        'assert q.count() == 1, "q.count() == 1"\n'
        'print q.get().public_access\n')
    self.assertEqual('True\n', result)


def _init_logging(argv):
  """Set up our logging by re-using some of the unittest flags"""
  parser = optparse.OptionParser()
  parser.add_option('-v', action='count', default=0)
  (opts, _) = parser.parse_args([x for x in argv if x.startswith('-v')])

  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  logging.basicConfig(level=levels[min(2, opts.v)])


if __name__ == '__main__':
  _init_logging(sys.argv)
  unittest.main()
