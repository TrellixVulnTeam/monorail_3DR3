# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for servlet base class module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import mock
import unittest

from google.appengine.api import app_identity
from google.appengine.ext import testbed

import webapp2

from framework import framework_constants
from framework import servlet
from framework import xsrf
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers


class TestableServlet(servlet.Servlet):
  """A tiny concrete subclass of abstract class Servlet."""

  def __init__(self, request, response, services=None, do_post_redirect=True):
    super(TestableServlet, self).__init__(request, response, services=services)
    self.do_post_redirect = do_post_redirect
    self.seen_post_data = None

  def ProcessFormData(self, _mr, post_data):
    self.seen_post_data = post_data
    if self.do_post_redirect:
      return '/This/Is?The=Next#Page'
    else:
      self.response.write('sending raw data to browser')


class ServletTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        project_star=fake.ProjectStarService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())
    services.user.TestAddUser('user@example.com', 111)
    self.page_class = TestableServlet(
        webapp2.Request.blank('/'), webapp2.Response(), services=services)
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def testDefaultValues(self):
    self.assertEqual(None, self.page_class._MAIN_TAB_MODE)
    self.assertTrue(self.page_class._TEMPLATE_PATH.endswith('/templates/'))
    self.assertEqual(None, self.page_class._PAGE_TEMPLATE)

  def testGatherBaseData(self):
    project = self.page_class.services.project.TestAddProject(
        'testproj', state=project_pb2.ProjectState.LIVE)
    project.cached_content_timestamp = 12345

    (_request, mr) = testing_helpers.GetRequestObjects(
        path='/p/testproj/feeds', project=project)
    nonce = '1a2b3c4d5e6f7g'

    base_data = self.page_class.GatherBaseData(mr, nonce)

    self.assertEqual(base_data['nonce'], nonce)
    self.assertEqual(base_data['projectname'], 'testproj')
    self.assertEqual(base_data['project'].cached_content_timestamp, 12345)
    self.assertEqual(base_data['project_alert'], None)

    self.assertTrue(base_data['currentPageURL'].endswith('/p/testproj/feeds'))
    self.assertTrue(
        base_data['currentPageURLEncoded'].endswith('%2Fp%2Ftestproj%2Ffeeds'))

  def testFormHandlerURL(self):
    self.assertEqual('/edit.do', self.page_class._FormHandlerURL('/'))
    self.assertEqual(
      '/something/edit.do',
      self.page_class._FormHandlerURL('/something/'))
    self.assertEqual(
      '/something/edit.do',
      self.page_class._FormHandlerURL('/something/edit.do'))
    self.assertEqual(
      '/something/detail_ezt.do',
      self.page_class._FormHandlerURL('/something/detail_ezt'))

  def testProcessForm_BadToken(self):
    user_id = 111
    token = 'no soup for you'

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={
            'yesterday': 'thursday',
            'today': 'friday',
            'token': token
        },
        user_info={'user_id': user_id},
        method='POST',
    )
    self.assertRaises(
        xsrf.TokenIncorrect, self.page_class._DoFormProcessing, request, mr)
    self.assertEqual(None, self.page_class.seen_post_data)

  def testProcessForm_XhrAllowed_BadToken(self):
    user_id = 111
    token = 'no soup for you'

    self.page_class.ALLOW_XHR = True

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={
            'yesterday': 'thursday',
            'today': 'friday',
            'token': token
        },
        user_info={'user_id': user_id},
        method='POST',
    )
    self.assertRaises(
        xsrf.TokenIncorrect, self.page_class._DoFormProcessing, request, mr)
    self.assertEqual(None, self.page_class.seen_post_data)

  def testProcessForm_XhrAllowed_AcceptsPathToken(self):
    user_id = 111
    token = xsrf.GenerateToken(user_id, '/we/we/we')

    self.page_class.ALLOW_XHR = True

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={
            'yesterday': 'thursday',
            'today': 'friday',
            'token': token
        },
        user_info={'user_id': user_id},
        method='POST',
    )
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._DoFormProcessing(request, mr)
    self.assertEqual(302, cm.exception.code)  # forms redirect on success

    self.assertDictEqual(
        {
            'yesterday': 'thursday',
            'today': 'friday',
            'token': token
        }, dict(self.page_class.seen_post_data))

  def testProcessForm_XhrAllowed_AcceptsXhrToken(self):
    user_id = 111
    token = xsrf.GenerateToken(user_id, 'xhr')

    self.page_class.ALLOW_XHR = True

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={'yesterday': 'thursday', 'today': 'friday', 'token': token},
        user_info={'user_id': user_id},
        method='POST',
    )
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._DoFormProcessing(request, mr)
    self.assertEqual(302, cm.exception.code)  # forms redirect on success

    self.assertDictEqual(
        {
            'yesterday': 'thursday',
            'today': 'friday',
            'token': token
        }, dict(self.page_class.seen_post_data))

  def testProcessForm_RawResponse(self):
    user_id = 111
    token = xsrf.GenerateToken(user_id, '/we/we/we')

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={'yesterday': 'thursday', 'today': 'friday', 'token': token},
        user_info={'user_id': user_id},
        method='POST',
    )
    self.page_class.do_post_redirect = False
    self.page_class._DoFormProcessing(request, mr)
    self.assertEqual(
        'sending raw data to browser',
        self.page_class.response.body)

  def testProcessForm_Normal(self):
    user_id = 111
    token = xsrf.GenerateToken(user_id, '/we/we/we')

    request, mr = testing_helpers.GetRequestObjects(
        path='/we/we/we?so=excited',
        params={'yesterday': 'thursday', 'today': 'friday', 'token': token},
        user_info={'user_id': user_id},
        method='POST',
    )
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._DoFormProcessing(request, mr)
    self.assertEqual(302, cm.exception.code)  # forms redirect on success

    self.assertDictEqual(
        {'yesterday': 'thursday', 'today': 'friday', 'token': token},
        dict(self.page_class.seen_post_data))

  def testCalcProjectAlert(self):
    project = fake.Project(
        project_name='alerttest', state=project_pb2.ProjectState.LIVE)

    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(project_alert, None)

    project.state = project_pb2.ProjectState.ARCHIVED
    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(
        project_alert,
        'Project is archived: read-only by members only.')

    delete_time = int(time.time() + framework_constants.SECS_PER_DAY * 1.5)
    project.delete_time = delete_time
    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(project_alert, 'Scheduled for deletion in 1 day.')

    delete_time = int(time.time() + framework_constants.SECS_PER_DAY * 2.5)
    project.delete_time = delete_time
    project_alert = servlet._CalcProjectAlert(project)
    self.assertEqual(project_alert, 'Scheduled for deletion in 2 days.')

  def testCheckForMovedProject_NoRedirect(self):
    project = fake.Project(
        project_name='proj', state=project_pb2.ProjectState.LIVE)
    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    self.page_class._CheckForMovedProject(mr, request)

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/source/browse/p/adminAdvanced', project=project)
    self.page_class._CheckForMovedProject(mr, request)

  def testCheckForMovedProject_Redirect(self):
    project = fake.Project(project_name='proj', moved_to='http://example.com')
    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._CheckForMovedProject(mr, request)
    self.assertEqual(302, cm.exception.code)  # redirect because project moved

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/source/browse/p/adminAdvanced', project=project)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._CheckForMovedProject(mr, request)
    self.assertEqual(302, cm.exception.code)  # redirect because project moved

  def testCheckForMovedProject_AdminAdvanced(self):
    """We do not redirect away from the page that edits project state."""
    project = fake.Project(project_name='proj', moved_to='http://example.com')
    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/adminAdvanced', project=project)
    self.page_class._CheckForMovedProject(mr, request)

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/adminAdvanced?ts=123234', project=project)
    self.page_class._CheckForMovedProject(mr, request)

    request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj/adminAdvanced.do', project=project)
    self.page_class._CheckForMovedProject(mr, request)

  @mock.patch('settings.branded_domains',
              {'proj': 'branded.example.com', '*': 'bugs.chromium.org'})
  def testMaybeRedirectToBrandedDomain_RedirBrandedProject(self):
    """We redirect for a branded project if the user typed a different host."""
    project = fake.Project(project_name='proj')
    request, _mr = testing_helpers.GetRequestObjects(
        path='/p/proj/path', project=project)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._MaybeRedirectToBrandedDomain(request, 'proj')
    self.assertEqual(302, cm.exception.code)  # forms redirect on success
    self.assertEqual('https://branded.example.com/p/proj/path?redir=1',
                     cm.exception.location)

    request, _mr = testing_helpers.GetRequestObjects(
      path='/p/proj/path?query', project=project)
    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._MaybeRedirectToBrandedDomain(request, 'proj')
    self.assertEqual(302, cm.exception.code)  # forms redirect on success
    self.assertEqual('https://branded.example.com/p/proj/path?query&redir=1',
                     cm.exception.location)

  @mock.patch('settings.branded_domains',
              {'proj': 'branded.example.com', '*': 'bugs.chromium.org'})
  def testMaybeRedirectToBrandedDomain_AvoidRedirLoops(self):
    """Don't redirect for a branded project if already redirected."""
    project = fake.Project(project_name='proj')
    request, _mr = testing_helpers.GetRequestObjects(
        path='/p/proj/path?redir=1', project=project)
    # No redirect happens.
    self.page_class._MaybeRedirectToBrandedDomain(request, 'proj')

  @mock.patch('settings.branded_domains',
              {'proj': 'branded.example.com', '*': 'bugs.chromium.org'})
  def testMaybeRedirectToBrandedDomain_NonProjectPage(self):
    """Don't redirect for a branded project if not in any project."""
    request, _mr = testing_helpers.GetRequestObjects(
        path='/u/user@example.com')
    # No redirect happens.
    self.page_class._MaybeRedirectToBrandedDomain(request, None)

  @mock.patch('settings.branded_domains',
              {'proj': 'branded.example.com', '*': 'bugs.chromium.org'})
  def testMaybeRedirectToBrandedDomain_AlreadyOnBrandedHost(self):
    """Don't redirect for a branded project if already on branded domain."""
    project = fake.Project(project_name='proj')
    request, _mr = testing_helpers.GetRequestObjects(
        path='/p/proj/path', project=project)
    request.host = 'branded.example.com'
    # No redirect happens.
    self.page_class._MaybeRedirectToBrandedDomain(request, 'proj')

  @mock.patch('settings.branded_domains',
              {'proj': 'branded.example.com', '*': 'bugs.chromium.org'})
  def testMaybeRedirectToBrandedDomain_Localhost(self):
    """Don't redirect for a branded project on localhost."""
    project = fake.Project(project_name='proj')
    request, _mr = testing_helpers.GetRequestObjects(
        path='/p/proj/path', project=project)
    request.host = 'localhost:8080'
    # No redirect happens.
    self.page_class._MaybeRedirectToBrandedDomain(request, 'proj')

    request.host = '0.0.0.0:8080'
    # No redirect happens.
    self.page_class._MaybeRedirectToBrandedDomain(request, 'proj')

  @mock.patch('settings.branded_domains',
              {'proj': 'branded.example.com', '*': 'bugs.chromium.org'})
  def testMaybeRedirectToBrandedDomain_NotBranded(self):
    """Don't redirect for a non-branded project."""
    project = fake.Project(project_name='other')
    request, _mr = testing_helpers.GetRequestObjects(
        path='/p/other/path?query', project=project)
    request.host = 'branded.example.com'  # But other project is unbranded.

    with self.assertRaises(webapp2.HTTPException) as cm:
      self.page_class._MaybeRedirectToBrandedDomain(request, 'other')
    self.assertEqual(302, cm.exception.code)  # forms redirect on success
    self.assertEqual('https://bugs.chromium.org/p/other/path?query&redir=1',
                     cm.exception.location)

  def testGatherHelpData_Normal(self):
    project = fake.Project(project_name='proj')
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    help_data = self.page_class.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])
    self.assertEqual(None, help_data['account_cue'])

  def testGatherHelpData_VacationReminder(self):
    project = fake.Project(project_name='proj')
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    mr.auth.user_id = 111
    mr.auth.user_pb.vacation_message = 'Gone skiing'
    help_data = self.page_class.GatherHelpData(mr, {})
    self.assertEqual('you_are_on_vacation', help_data['cue'])

    self.page_class.services.user.SetUserPrefs(
        'cnxn', 111,
        [user_pb2.UserPrefValue(name='you_are_on_vacation', value='true')])
    help_data = self.page_class.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])
    self.assertEqual(None, help_data['account_cue'])

  def testGatherHelpData_YouAreBouncing(self):
    project = fake.Project(project_name='proj')
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    mr.auth.user_id = 111
    mr.auth.user_pb.email_bounce_timestamp = 1497647529
    help_data = self.page_class.GatherHelpData(mr, {})
    self.assertEqual('your_email_bounced', help_data['cue'])

    self.page_class.services.user.SetUserPrefs(
        'cnxn', 111,
        [user_pb2.UserPrefValue(name='your_email_bounced', value='true')])
    help_data = self.page_class.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])
    self.assertEqual(None, help_data['account_cue'])

  def testGatherHelpData_ChildAccount(self):
    """Display a warning when user is signed in to a child account."""
    project = fake.Project(project_name='proj')
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/proj', project=project)
    mr.auth.user_pb.linked_parent_id = 111
    help_data = self.page_class.GatherHelpData(mr, {})
    self.assertEqual(None, help_data['cue'])
    self.assertEqual('switch_to_parent_account', help_data['account_cue'])
    self.assertEqual('user@example.com', help_data['parent_email'])

  def testGatherDebugData_Visibility(self):
    project = fake.Project(
        project_name='testtest', state=project_pb2.ProjectState.LIVE)
    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/foo/servlet_path', project=project)
    debug_data = self.page_class.GatherDebugData(mr, {})
    self.assertEqual('off', debug_data['dbg'])

    _request, mr = testing_helpers.GetRequestObjects(
        path='/p/foo/servlet_path?debug=1', project=project)
    debug_data = self.page_class.GatherDebugData(mr, {})
    self.assertEqual('on', debug_data['dbg'])


class ProjectIsRestrictedTest(unittest.TestCase):

  def testNonRestrictedProject(self):
    proj = project_pb2.Project()
    mr = testing_helpers.MakeMonorailRequest()
    mr.project = proj

    proj.access = project_pb2.ProjectAccess.ANYONE
    proj.state = project_pb2.ProjectState.LIVE
    self.assertFalse(servlet._ProjectIsRestricted(mr))

    proj.state = project_pb2.ProjectState.ARCHIVED
    self.assertFalse(servlet._ProjectIsRestricted(mr))

  def testRestrictedProject(self):
    proj = project_pb2.Project()
    mr = testing_helpers.MakeMonorailRequest()
    mr.project = proj

    proj.state = project_pb2.ProjectState.LIVE
    proj.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.assertTrue(servlet._ProjectIsRestricted(mr))

class VersionBaseTest(unittest.TestCase):

  @mock.patch('settings.local_mode', True)
  def testLocalhost(self):
    request = webapp2.Request.blank('/', base_url='http://localhost:8080')
    actual = servlet._VersionBaseURL(request)
    expected = 'http://localhost:8080'
    self.assertEqual(expected, actual)

  @mock.patch('settings.local_mode', False)
  @mock.patch('google.appengine.api.app_identity.get_default_version_hostname')
  def testProd(self, mock_gdvh):
    mock_gdvh.return_value = 'monorail-prod.appspot.com'
    request = webapp2.Request.blank('/', base_url='https://bugs.chromium.org')
    actual = servlet._VersionBaseURL(request)
    expected = 'https://test-dot-monorail-prod.appspot.com'
    self.assertEqual(expected, actual)
