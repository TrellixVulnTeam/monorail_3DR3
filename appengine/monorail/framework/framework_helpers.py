# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions and classes used throughout Monorail."""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import logging
import random
import string
import textwrap
import threading
import time
import traceback
import urllib
import urlparse

from google.appengine.api import app_identity

from third_party import ezt
from third_party import six

import settings
from framework import framework_bizobj
from framework import framework_constants
from framework import template_helpers
from framework import timestr
from framework import urls
from proto import user_pb2
from services import client_config_svc


# For random key generation
RANDOM_KEY_LENGTH = 128
RANDOM_KEY_CHARACTERS = string.ascii_letters + string.digits

# params recognized by FormatURL, in the order they will appear in the url
RECOGNIZED_PARAMS = ['can', 'start', 'num', 'q', 'colspec', 'groupby', 'sort',
                     'show', 'format', 'me', 'table_title', 'projects',
                     'hotlist_id']


def retry(tries, delay=1, backoff=2):
  """A retry decorator with exponential backoff.

  Functions are retried when Exceptions occur.

  Args:
    tries: int Number of times to retry, set to 0 to disable retry.
    delay: float Initial sleep time in seconds.
    backoff: float Must be greater than 1, further failures would sleep
             delay*=backoff seconds.
  """
  if backoff <= 1:
    raise ValueError("backoff must be greater than 1")
  if tries < 0:
    raise ValueError("tries must be 0 or greater")
  if delay <= 0:
    raise ValueError("delay must be greater than 0")

  def decorator(func):
    def wrapper(*args, **kwargs):
      _tries, _delay = tries, delay
      _tries += 1  # Ensure we call func at least once.
      while _tries > 0:
        try:
          ret = func(*args, **kwargs)
          return ret
        except Exception:
          _tries -= 1
          if _tries == 0:
            logging.error('Exceeded maximum number of retries for %s.',
                          func.__name__)
            raise
          trace_str = traceback.format_exc()
          logging.warning('Retrying %s due to Exception: %s',
                          func.__name__, trace_str)
          time.sleep(_delay)
          _delay *= backoff  # Wait longer the next time we fail.
    return wrapper
  return decorator


class PromiseCallback(object):
  """Executes the work of a Promise and then dereferences everything."""

  def __init__(self, promise, callback, *args, **kwargs):
    self.promise = promise
    self.callback = callback
    self.args = args
    self.kwargs = kwargs

  def __call__(self):
    try:
      self.promise._WorkOnPromise(self.callback, *self.args, **self.kwargs)
    finally:
      # Make sure we no longer hold onto references to anything.
      self.promise = self.callback = self.args = self.kwargs = None


class Promise(object):
  """Class for promises to deliver a value in the future.

  A thread is started to run callback(args), that thread
  should return the value that it generates, or raise an expception.
  p.WaitAndGetValue() will block until a value is available.
  If an exception was raised, p.WaitAndGetValue() will re-raise the
  same exception.
  """

  def __init__(self, callback, *args, **kwargs):
    """Initialize the promise and immediately call the supplied function.

    Args:
      callback: Function that takes the args and returns the promise value.
      *args:  Any arguments to the target function.
      **kwargs: Any keyword args for the target function.
    """

    self.has_value = False
    self.value = None
    self.event = threading.Event()
    self.exception = None

    promise_callback = PromiseCallback(self, callback, *args, **kwargs)

    # Execute the callback in another thread.
    promise_thread = threading.Thread(target=promise_callback)
    promise_thread.start()

  def _WorkOnPromise(self, callback, *args, **kwargs):
    """Run callback to compute the promised value.  Save any exceptions."""
    try:
      self.value = callback(*args, **kwargs)
    except Exception as e:
      trace_str = traceback.format_exc()
      logging.info('Exception while working on promise: %s\n', trace_str)
      # Add the stack trace at this point to the exception.  That way, in the
      # logs, we can see what happened further up in the call stack
      # than WaitAndGetValue(), which re-raises exceptions.
      e.pre_promise_trace = trace_str
      self.exception = e
    finally:
      self.has_value = True
      self.event.set()

  def WaitAndGetValue(self):
    """Block until my value is available, then return it or raise exception."""
    self.event.wait()
    if self.exception:
      raise self.exception  # pylint: disable=raising-bad-type
    return self.value


def FormatAbsoluteURLForDomain(
    host, project_name, servlet_name, scheme='https', **kwargs):
  """A variant of FormatAbsoluteURL for when request objects are not available.

  Args:
    host: string with hostname and optional port, e.g. 'localhost:8080'.
    project_name: the destination project name, if any.
    servlet_name: site or project-local url fragement of dest page.
    scheme: url scheme, e.g., 'http' or 'https'.
    **kwargs: additional query string parameters may be specified as named
      arguments to this function.

  Returns:
    A full url beginning with 'http[s]://'.
  """
  path_and_args = FormatURL(None, servlet_name, **kwargs)

  if host:
    domain_port = host.split(':')
    domain_port[0] = GetPreferredDomain(domain_port[0])
    host = ':'.join(domain_port)

  absolute_domain_url = '%s://%s' % (scheme, host)
  if project_name:
    return '%s/p/%s%s' % (absolute_domain_url, project_name, path_and_args)
  return absolute_domain_url + path_and_args


def FormatAbsoluteURL(
    mr, servlet_name, include_project=True, project_name=None,
    scheme=None, copy_params=True, **kwargs):
  """Return an absolute URL to a servlet with old and new params.

  Args:
    mr: info parsed from the current request.
    servlet_name: site or project-local url fragement of dest page.
    include_project: if True, include the project home url as part of the
      destination URL (as long as it is specified either in mr
      or as the project_name param.)
    project_name: the destination project name, to override
      mr.project_name if include_project is True.
    scheme: either 'http' or 'https', to override mr.request.scheme.
    copy_params: if True, copy well-known parameters from the existing request.
    **kwargs: additional query string parameters may be specified as named
      arguments to this function.

  Returns:
    A full url beginning with 'http[s]://'.  The destination URL will be in
    the same domain as the current request.
  """
  path_and_args = FormatURL(
      [(name, mr.GetParam(name)) for name in RECOGNIZED_PARAMS]
      if copy_params else None,
      servlet_name, **kwargs)
  scheme = scheme or mr.request.scheme

  project_base = ''
  if include_project:
    project_base = '/p/%s' % (project_name or mr.project_name)

  return '%s://%s%s%s' % (scheme, mr.request.host, project_base, path_and_args)


def FormatMovedProjectURL(mr, moved_to):
  """Return a transformation of the given url into the given project.

  Args:
    mr: common information parsed from the HTTP request.
    moved_to: A string from a project's moved_to field that matches
      framework_bizobj.RE_PROJECT_NAME.

  Returns:
    The url transposed into the given destination project.
  """
  project_name = moved_to
  _, _, path, parameters, query, fragment_identifier = urlparse.urlparse(
      mr.current_page_url)
  # Strip off leading "/p/<moved from project>"
  path = '/' + path.split('/', 3)[3]
  rest_of_url = urlparse.urlunparse(
    ('', '', path, parameters, query, fragment_identifier))
  return '/p/%s%s' % (project_name, rest_of_url)


def GetNeededDomain(project_name, current_domain):
  """Return the branded domain for the project iff not on current_domain."""
  if (not current_domain or
      '.appspot.com' in current_domain or
      ':' in current_domain):
    return None
  desired_domain = settings.branded_domains.get(
      project_name, settings.branded_domains.get('*'))
  if desired_domain == current_domain:
    return None
  return desired_domain


def FormatURL(recognized_params, servlet_path, **kwargs):
  """Return a project relative URL to a servlet with old and new params."""
  # Standard params not overridden in **kwargs come first, followed by kwargs.
  # The exception is the 'id' param. If present then the 'id' param always comes
  # first. See bugs.chromium.org/p/monorail/issues/detail?id=374
  all_params = []
  if kwargs.get('id'):
    all_params.append(('id', kwargs['id']))
  # TODO(jojwang): update all calls to FormatURL to only include non-None
  # recognized_params
  if recognized_params:
    all_params.extend(
        param for param in recognized_params if param[0] not in kwargs)

  all_params.extend(
      # Ignore the 'id' param since we already added it above.
      sorted([kwarg for kwarg in kwargs.items() if kwarg[0] != 'id']))
  return _FormatQueryString(servlet_path, all_params)


def _FormatQueryString(url, params):
  """URLencode a list of parameters and attach them to the end of a URL."""
  param_string = '&'.join(
      '%s=%s' % (name, urllib.quote(six.text_type(value).encode('utf-8')))
      for name, value in params if value is not None)
  if not param_string:
    qs_start_char = ''
  elif '?' in url:
    qs_start_char = '&'
  else:
    qs_start_char = '?'
  return '%s%s%s' % (url, qs_start_char, param_string)


def WordWrapSuperLongLines(s, max_cols=100):
  """Reformat input that was not word-wrapped by the browser.

  Args:
    s: the string to be word-wrapped, it may have embedded newlines.
    max_cols: int maximum line length.

  Returns:
    Wrapped text string.

  Rather than wrap the whole thing, we only wrap super-long lines and keep
  all the reasonable lines formated as-is.
  """
  lines = [textwrap.fill(line, max_cols) for line in s.splitlines()]
  wrapped_text = '\n'.join(lines)

  # The split/join logic above can lose one final blank line.
  if s.endswith('\n') or s.endswith('\r'):
    wrapped_text += '\n'

  return wrapped_text


def StaticCacheHeaders():
  """Returns HTTP headers for static content, based on the current time."""
  year_from_now = int(time.time()) + framework_constants.SECS_PER_YEAR
  headers = [
      ('Cache-Control',
       'max-age=%d, private' % framework_constants.SECS_PER_YEAR),
      ('Last-Modified', timestr.TimeForHTMLHeader()),
      ('Expires', timestr.TimeForHTMLHeader(when=year_from_now)),
  ]
  logging.info('static headers are %r', headers)
  return headers


def ComputeListDeltas(old_list, new_list):
  """Given an old and new list, return the items added and removed.

  Args:
    old_list: old list of values for comparison.
    new_list: new list of values for comparison.

  Returns:
    Two lists: one with all the values added (in new_list but was not
    in old_list), and one with all the values removed (not in new_list
    but was in old_lit).
  """
  if old_list == new_list:
    return [], []  # A common case: nothing was added or removed.

  added = set(new_list)
  added.difference_update(old_list)
  removed = set(old_list)
  removed.difference_update(new_list)
  return list(added), list(removed)


def GetRoleName(effective_ids, project):
  """Determines the name of the role a member has for a given project.

  Args:
    effective_ids: set of user IDs to get the role name for.
    project: Project PB containing the different the different member lists.

  Returns:
    The name of the role.
  """
  if not effective_ids.isdisjoint(project.owner_ids):
    return 'Owner'
  if not effective_ids.isdisjoint(project.committer_ids):
    return 'Committer'
  if not effective_ids.isdisjoint(project.contributor_ids):
    return 'Contributor'
  return None


def GetHotlistRoleName(effective_ids, hotlist):
  """Determines the name of the role a member has for a given hotlist."""
  if not effective_ids.isdisjoint(hotlist.owner_ids):
    return 'Owner'
  if not effective_ids.isdisjoint(hotlist.editor_ids):
    return 'Editor'
  if not effective_ids.isdisjoint(hotlist.follower_ids):
    return 'Follower'
  return None


class UserSettings(object):
  """Abstract class providing static methods for user settings forms."""

  @classmethod
  def GatherUnifiedSettingsPageData(
      cls, logged_in_user_id, settings_user_view, settings_user,
      settings_user_prefs):
    """Gather EZT variables needed for the unified user settings form.

    Args:
      logged_in_user_id: The user ID of the acting user.
      settings_user_view: The UserView of the target user.
      settings_user: The User PB of the target user.
      settings_user_prefs: UserPrefs object for the view user.

    Returns:
      A dictionary giving the names and values of all the variables to
      be exported to EZT to support the unified user settings form template.
    """

    settings_user_prefs_view = template_helpers.EZTItem(
      **{name: None for name in framework_bizobj.USER_PREF_DEFS})
    if settings_user_prefs:
      for upv in settings_user_prefs.prefs:
        if upv.value == 'true':
          setattr(settings_user_prefs_view, upv.name, True)
        elif upv.value == 'false':
          setattr(settings_user_prefs_view, upv.name, None)

    logging.info('settings_user_prefs_view is %r' % settings_user_prefs_view)
    return {
        'settings_user': settings_user_view,
        'settings_user_pb': template_helpers.PBProxy(settings_user),
        'settings_user_is_banned': ezt.boolean(settings_user.banned),
        'self': ezt.boolean(logged_in_user_id == settings_user_view.user_id),
        'profile_url_fragment': (
            settings_user_view.profile_url[len('/u/'):]),
        'preview_on_hover': ezt.boolean(settings_user.preview_on_hover),
        'settings_user_prefs': settings_user_prefs_view,
        }

  @classmethod
  def ProcessBanForm(
      cls, cnxn, user_service, post_data, user_id, user):
    """Process the posted form data from the ban user form.

    Args:
      cnxn: connection to the SQL database.
      user_service: An instance of UserService for saving changes.
      post_data: The parsed post data from the form submission request.
      user_id: The user id of the target user.
      user: The user PB of the target user.
    """
    user_service.UpdateUserBan(
        cnxn, user_id, user, is_banned='banned' in post_data,
            banned_reason=post_data.get('banned_reason', ''))

  @classmethod
  def ProcessSettingsForm(
      cls, we, post_data, user, admin=False):
    """Process the posted form data from the unified user settings form.

    Args:
      we: A WorkEnvironment with cnxn and services.
      post_data: The parsed post data from the form submission request.
      user: The user PB of the target user.
      admin: Whether settings reserved for admins are supported.
    """
    obscure_email = 'obscure_email' in post_data

    kwargs = {}
    if admin:
      kwargs.update(is_site_admin='site_admin' in post_data)
      kwargs.update(is_banned='banned' in post_data,
                    banned_reason=post_data.get('banned_reason', ''))

    we.UpdateUserSettings(
        user, notify='notify' in post_data,
        notify_starred='notify_starred' in post_data,
        email_compact_subject='email_compact_subject' in post_data,
        email_view_widget='email_view_widget' in post_data,
        notify_starred_ping='notify_starred_ping' in post_data,
        preview_on_hover='preview_on_hover' in post_data,
        obscure_email=obscure_email,
        vacation_message=post_data.get('vacation_message', ''),
        **kwargs)

    user_prefs = []
    for pref_name in ['restrict_new_issues', 'public_issue_notice']:
      user_prefs.append(user_pb2.UserPrefValue(
          name=pref_name,
          value=('true' if pref_name in post_data else 'false')))
    we.SetUserPrefs(user.user_id, user_prefs)


def GetHostPort(project_name=None):
  """Get string domain name and port number."""

  app_id = app_identity.get_application_id()
  if ':' in app_id:
    domain, app_id = app_id.split(':')
  else:
    domain = ''

  if domain.startswith('google'):
    hostport = '%s.googleplex.com' % app_id
  else:
    hostport = '%s.appspot.com' % app_id

  live_site_domain = GetPreferredDomain(hostport)
  if project_name:
    project_needed_domain = GetNeededDomain(project_name, live_site_domain)
    if project_needed_domain:
      return project_needed_domain

  return live_site_domain


def IssueCommentURL(
    hostport, project, local_id, seq_num=None):
  """Return a URL pointing directly to the specified comment."""
  servlet_name = urls.ISSUE_DETAIL
  detail_url = FormatAbsoluteURLForDomain(
      hostport, project.project_name, servlet_name, id=local_id)
  if seq_num:
    detail_url += '#c%d' % seq_num

  return detail_url


def MurmurHash3_x86_32(key, seed=0x0):
  """Implements the x86/32-bit version of Murmur Hash 3.0.

  MurmurHash3 is written by Austin Appleby, and is placed in the public
  domain. See https://code.google.com/p/smhasher/ for details.

  This pure python implementation of the x86/32 bit version of MurmurHash3 is
  written by Fredrik Kihlander and also placed in the public domain.
  See https://github.com/wc-duck/pymmh3 for details.

  The MurmurHash3 algorithm is chosen for these reasons:
  * It is fast, even when implemented in pure python.
  * It is remarkably well distributed, and unlikely to cause collisions.
  * It is stable and unchanging (any improvements will be in MurmurHash4).
  * It is well-tested, and easily usable in other contexts (such as bulk
    data imports).

  Args:
    key (string): the data that you want hashed
    seed (int): An offset, treated as essentially part of the key.

  Returns:
    A 32-bit integer (can be interpreted as either signed or unsigned).
  """
  key = bytearray(key.encode('utf-8'))

  def fmix(h):
    h ^= h >> 16
    h  = (h * 0x85ebca6b) & 0xFFFFFFFF
    h ^= h >> 13
    h  = (h * 0xc2b2ae35) & 0xFFFFFFFF
    h ^= h >> 16
    return h;

  length = len(key)
  nblocks = int(length // 4)

  h1 = seed;

  c1 = 0xcc9e2d51
  c2 = 0x1b873593

  # body
  for block_start in range(0, nblocks * 4, 4):
    k1 = key[ block_start + 3 ] << 24 | \
         key[ block_start + 2 ] << 16 | \
         key[ block_start + 1 ] <<  8 | \
         key[ block_start + 0 ]

    k1 = c1 * k1 & 0xFFFFFFFF
    k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF
    k1 = (c2 * k1) & 0xFFFFFFFF;

    h1 ^= k1
    h1  = ( h1 << 13 | h1 >> 19 ) & 0xFFFFFFFF
    h1  = ( h1 * 5 + 0xe6546b64 ) & 0xFFFFFFFF

  # tail
  tail_index = nblocks * 4
  k1 = 0
  tail_size = length & 3

  if tail_size >= 3:
    k1 ^= key[ tail_index + 2 ] << 16
  if tail_size >= 2:
    k1 ^= key[ tail_index + 1 ] << 8
  if tail_size >= 1:
    k1 ^= key[ tail_index + 0 ]

  if tail_size != 0:
    k1  = ( k1 * c1 ) & 0xFFFFFFFF
    k1  = ( k1 << 15 | k1 >> 17 ) & 0xFFFFFFFF
    k1  = ( k1 * c2 ) & 0xFFFFFFFF
    h1 ^= k1

  return fmix( h1 ^ length )


def MakeRandomKey(length=RANDOM_KEY_LENGTH, chars=RANDOM_KEY_CHARACTERS):
  """Return a string with lots of random characters."""
  chars = [random.choice(chars) for _ in range(length)]
  return ''.join(chars)


def IsServiceAccount(email, client_emails=None):
  """Return a boolean value whether this email is a service account."""
  if email.endswith('gserviceaccount.com'):
    return True
  if client_emails is None:
    _, client_emails = (
        client_config_svc.GetClientConfigSvc().GetClientIDEmails())
  return email in client_emails


def GetPreferredDomain(domain):
  """Get preferred domain to display.

  The preferred domain replaces app_id for default version of monorail-prod
  and monorail-staging.
  """
  return settings.preferred_domains.get(domain, domain)


def GetUserAvailability(user, is_group=False):
  """Return (str, str) that explains why the user might not be available."""
  if not user.user_id:
    return None, None
  if user.banned:
    return 'Banned', 'banned'
  if user.vacation_message:
    return user.vacation_message, 'none'
  if user.email_bounce_timestamp:
    return 'Email to this user bounced', 'none'
  # No availability shown for user groups, or addresses that are
  # likely to be mailing lists.
  if is_group or (user.email and '-' in user.email):
    return None, None
  if not user.last_visit_timestamp:
    return 'User never visited', 'never'
  secs_ago = int(time.time()) - user.last_visit_timestamp
  last_visit_str = timestr.FormatRelativeDate(
      user.last_visit_timestamp, days_only=True)
  if secs_ago > 30 * framework_constants.SECS_PER_DAY:
    return 'Last visit > 30 days ago', 'none'
  if secs_ago > 15 * framework_constants.SECS_PER_DAY:
    return ('Last visit %s' % last_visit_str), 'unsure'
  return None, None
