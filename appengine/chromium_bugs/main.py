#!/usr/bin/env python
#
# Copyright 2012 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import logging
import os
import re
import urllib
import urlparse
import webapp2

from google.appengine.api import users
from google.appengine.ext.webapp import util

# pylint warning disabled until httpagentparser can be added to the wheelhouse.
# http://crbug.com/410984
import httpagentparser # pylint: disable=F0401
import settings
from third_party import ezt

import gae_ts_mon


WIZARD_TEMPLATE_PATH = 'templates/wizard.ezt'
WIZARD_HTML_TEMPLATE = ezt.Template(WIZARD_TEMPLATE_PATH)

legacy_template = """Chrome Version       : %s
OS Version: %s
URLs (if applicable) :
Other browsers tested:
  Add OK or FAIL after other browsers where you have tested this issue:
     Safari:
    Firefox:
    IE/Edge:

What steps will reproduce the problem?
1.
2.
3.

What is the expected result?


What happens instead%s?


Please provide any additional information below. Attach a screenshot if
possible.
%s
"""

DEFAULT_BUG_TEMPLATE_NAME = 'Defect%20report%20from%20user'
MAC_BUG_TEMPLATE_NAME = 'Defect%20on%20Mac%20OS'
LINUX_BUG_TEMPLATE_NAME = 'Defect%20on%20Linux'
CHROME_OS_BUG_TEMPLATE_NAME = 'Defect%20on%20Chrome%20OS'
WINDOWS_BUG_TEMPLATE_NAME = 'Defect%20on%20Windows'

MISSING_TOKEN_HTML = (
    '<html><body>'
    '<h1>Not signed in</h1>'
    '<p>Please go back and sign in to bugs.chromium.org before '
    'using this wizard.</p>'
    ''
    '</body></html>'
    )

# The continue_url  must match these.
ALLOWED_CONTINUE_SCHEMES = ['http', 'https']
ALLOWED_CONTINUE_DOMAINS = [
  re.compile(r'^localhost:8080$'),
  re.compile(r'^bugs(-staging|-dev)?\.chromium\.org$'),
  re.compile(r'^([-a-z0-9.]+-dot-)?monorail-(prod|staging|dev)\.appspot\.com$'),
  ]

INVALID_CONTINUE_HTML = (
    '<html><body>'
    '<h1>Invalid continue parameter</h1>'
    '<p>This wizard can only be used with '
    'bugs.chromium.org.</p>'
    ''
    '</body></html>'
    )


class MainHandler(webapp2.RequestHandler):

  def get(self):
    uas = self.request.headers['User-Agent']
    role = self.request.get('role')
    continue_url = self.request.get('continue')
    token = self.request.get('token')

    self.response.headers.add(
        'Strict-Transport-Security',
        'max-age=31536000; includeSubDomains; preload')

    if continue_url and not token:
      logging.info('Missing token')
      self.response.out.write(MISSING_TOKEN_HTML)
      return

    if not continue_url:
      continue_url = 'https://bugs.chromium.org/p/chromium/issues/entry.do'

    parsed = urlparse.urlparse(continue_url)
    scheme_is_allowed = parsed.scheme in ALLOWED_CONTINUE_SCHEMES
    domain_is_allowed = any(
        regex.match(parsed.netloc) for regex in ALLOWED_CONTINUE_DOMAINS)
    continue_is_allowed = scheme_is_allowed and domain_is_allowed
    if not continue_is_allowed:
      logging.info('Bad continue param: %r', continue_url)
      self.response.out.write(INVALID_CONTINUE_HTML)
      return

    validate_url = continue_url.split('?')[0]

    if not validate_url.endswith('.do'):
      logging.info('validate_url does not end in .do: %r', validate_url)
      self.response.out.write(
        'Malformed "continue" query string parameter: %r' %
        urllib.quote(validate_url))
      return

    issue_entry_page_url = validate_url[:-3]

    user = users.get_current_user()
    if role or (user and re.match(
        r".*?@chromium\.org\Z", user.email(), re.DOTALL | re.IGNORECASE)):
      logging.info('Redirecting because you have a role or @chromium.org acct')
      logging.info('role = %r', role)
      logging.info('email = %r', user and user.email())
      self.redirect(issue_entry_page_url.encode('utf8'))
      return

    ua = httpagentparser.detect(uas)
    name = ''
    os_version = ''
    browser = None
    browser_version = None
    chrome_version = "<Copy from: 'about:version'>"
    chrome_ua = ""
    template_name = DEFAULT_BUG_TEMPLATE_NAME
    # Mac
    # {'flavor': {'version': 'X 10.6.6', 'name': 'MacOS'},
    #  'os': {'name': 'Macintosh'},
    #  'browser': {'version': '11.0.696.16', 'name': 'Chrome'}}

    # Win
    # {'os': {'version': 'NT 6.1', 'name': 'Windows'},
    # 'browser': {'version': '11.0.696.16', 'name': 'Chrome'}}

    if ua:
      if ua.has_key('os') and ua['os'].has_key('name'):
        name = ua['os']['name']
        if name == 'Windows':
          if 'version' in ua['os']:
            os_version = ua['os']['version']
          else:
            os_version = 'Unknown'

          match = re.search(
            r"(\d+\.\d+)", os_version, re.DOTALL | re.IGNORECASE)
          if match:
            version = match.group(1)
          else:
            version = ''
          if version == '6.2':
            os_version += ' (Windows 8)'
          elif version == '6.1':
            os_version += ' (Windows 7, Windows Server 2008 R2)'
          elif version == '6.0':
            os_version += ' (Windows Vista, Windows Server 2008)'
          elif version == '5.2':
            os_version += ' (Windows Server 2003, Windows XP 64)'
          elif version == '5.1':
            os_version += ' (Windows XP)'
          elif version == '5.0':
            os_version += ' (Windows 2000)'

          template_name = WINDOWS_BUG_TEMPLATE_NAME
        elif name == 'Macintosh':
          template_name = MAC_BUG_TEMPLATE_NAME
          if ua.has_key('flavor') and ua['flavor'].has_key('version'):
            os_version = ua['flavor']['version']
        elif name == 'Linux':
          template_name = LINUX_BUG_TEMPLATE_NAME
        # We might be able to do flavors
        elif name == 'ChromeOS':
          template_name = CHROME_OS_BUG_TEMPLATE_NAME
          os_version = ua['os']['version']

      if ua.has_key('browser'):
        browser = ua['browser']['name']
        browser_version = ua['browser']['version']
        if browser == "Chrome":
          chrome_version = browser_version
          chrome_ua = '\nUserAgentString: %s\n' % uas

    if not token or self.ShouldDoLegacyBehavior(browser, browser_version):
      # Allow us to measure number of users who came through new.crbug.com
      # by putting in a phrase that we can query for: "instead of that".
      # Also, when bugs.chromium.org is in a scheduled read-only period, direct
      # users straight to the classic issue entry page.
      detectable_phrase = '' if token else ' of that'
      comment = legacy_template % (
        chrome_version, os_version, detectable_phrase, chrome_ua)
      url = (issue_entry_page_url + '?template=' + template_name + '&' +
             urllib.urlencode({'comment': comment}))
      self.redirect(url.encode('utf8'))
      return

    channel_guess_os_name = {
        'macintosh': 'mac',
        'windows': 'win',
        'linux': 'linux',
        'ios': 'ios',
        'chromeos': 'cros',
        # Android cannot be guessed.
        }.get(name.lower(), name.lower())

    app_version = os.environ.get('CURRENT_VERSION_ID')
    page_data = {
        'app_version': app_version,
        'chrome_version': chrome_version,
        'channel_guess_os_name': channel_guess_os_name,
        'os_name': name,
        'os_version': os_version,
        'chrome_ua': chrome_ua,
        'issue_entry_page_url': issue_entry_page_url,
        'continue_url': continue_url,
        'token': token,
        }
    # TODO(jrobbins): Use WIZARD_HTML_TEMPLATE for speed.
    ezt.Template(WIZARD_TEMPLATE_PATH, base_format=ezt.FORMAT_HTML).generate(
      self.response.out, page_data)


  # pylint: disable=R0201
  def ShouldDoLegacyBehavior(self, browser, version):
    """Return True if this request should produce the old templat+UA behavior.

    This feature is intended to allow A/B testing so that we can measure how
    the new issue wizard affects user behavior, report quantity, and quality.
    """
    # We have a lot of old data that we can use for comparison, so let's
    # just forget about experiments for now.  If we need to do one, we
    # could deploy a different version of the app for a period of time.
    # token = self.request.get('token')
    # if hash(token) % 100 < 10:  # 10% experiment
    #   logging.info('routing user to non-wizard')
    #   return True

    # Old versions of IE do not support pushState, send them through
    # the legacy issue entry page.
    try:
      version = version or '0'
      version_number = int(version.split('.')[0])
    except ValueError:
      version_number = 0

    if browser == 'Microsoft Internet Explorer' and version_number < 10:
      return True

    # If the site is read-only, let the user see that error message.
    # If the site is read-write during a scheduled read-only window,
    # users will still be able to enter issue via the classic issue form.
    for start, duration in settings.READ_ONLY_WINDOWS:
      now = datetime.datetime.utcnow()
      if start < now < start + duration:
        logging.info('Site is scheduled to be in read-only mode %r < %r < %r',
                     start, now, start + duration)
        return True

    return False


application = webapp2.WSGIApplication(
    [('/', MainHandler),
     ('/wizard.html', MainHandler),
     ('/wizard.do', MainHandler)],
    debug=True)
gae_ts_mon.initialize(application)
