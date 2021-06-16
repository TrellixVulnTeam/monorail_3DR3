#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import code
import getpass
import logging
import os
import sys

ROOT = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
GAE_SDK = os.path.join(ROOT, '..', 'gcloud', 'platform', 'google_appengine')
LIB = os.path.join(GAE_SDK, 'lib')
sys.path.insert(0, GAE_SDK)
sys.path.append(os.path.join(LIB, 'yaml', 'lib'))
sys.path.append(os.path.join(LIB, 'fancy_urllib'))
sys.path.append(os.path.join(LIB, 'webob'))
sys.path.append(ROOT)

from google.appengine.ext.remote_api import remote_api_stub


def auth_func():
  user = os.environ.get('EMAIL_ADDRESS')
  if user:
    print('User: %s' % user)
  else:
    user = raw_input('Username:')
  try:
    pwd = open('.pwd').readline().strip()
  except IOError:
    pwd = getpass.getpass('Password:')
  return user, pwd


def main():
  if len(sys.argv) < 2:
    app_id = 'chromium-status'
  else:
    app_id = sys.argv[1]
  if len(sys.argv) > 2:
    host = sys.argv[2]
  else:
    host = '%s.appspot.com' % app_id
  logging.basicConfig(level=logging.ERROR)

  # pylint: disable=W0612
  from google.appengine.api import memcache
  from google.appengine.ext import db
  remote_api_stub.ConfigureRemoteDatastore(
      app_id, '/_ah/remote_api', auth_func, host)

  from appengine_module.chromium_status import base_page
  from appengine_module.chromium_status import git_lkgr
  from appengine_module.chromium_status import static_blobs
  from appengine_module.chromium_status import status
  from appengine_module.chromium_status import utils

  utils.bootstrap()

  def remove(entity, functor, batch=100):
    """Remove entries."""
    count = 0
    items = []
    while True:
      entries = [i for i in entity.all().fetch(limit=batch) if functor(i)]
      count += len(entries)
      print '%s' % count
      if entries:
        db.delete(entries)
      else:
        break

  # Symbols presented to the user.
  predefined_vars = locals()

  prompt = (
      'App Engine interactive console for "%s".\n'
      'Available symbols:\n'
      '  %s\n') % (app_id, ', '.join(sorted(predefined_vars)))
  code.interact(prompt, None, predefined_vars)


if __name__ == '__main__':
  sys.exit(main())
