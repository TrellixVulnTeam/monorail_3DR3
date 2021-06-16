# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issuelist module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mox
import mock
import unittest
import time

from google.appengine.ext import testbed
from third_party import ezt

from features import hotlistissues
from features import hotlist_helpers
from framework import framework_views
from framework import permissions
from framework import sorting
from framework import template_helpers
from framework import xsrf
from services import service_manager
from testing import fake
from testing import testing_helpers


class HotlistIssuesUnitTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.services = service_manager.Services(
        issue_star=fake.IssueStarService(),
        config=fake.ConfigService(),
        user=fake.UserService(),
        issue=fake.IssueService(),
        project=fake.ProjectService(),
        features=fake.FeaturesService(),
        cache_manager=fake.CacheManager(),
        hotlist_star=fake.HotlistStarService())
    self.servlet = hotlistissues.HotlistIssues(
        'req', 'res', services=self.services)
    self.user1 = self.services.user.TestAddUser('testuser@gmail.com', 111)
    self.user2 = self.services.user.TestAddUser('testuser2@gmail.com', 222, )
    self.services.project.TestAddProject('project-name', project_id=1)
    self.issue1 = fake.MakeTestIssue(
        1, 1, 'issue_summary', 'New', 111, project_name='project-name')
    self.services.issue.TestAddIssue(self.issue1)
    self.issue2 = fake.MakeTestIssue(
        1, 2, 'issue_summary2', 'New', 111, project_name='project-name')
    self.services.issue.TestAddIssue(self.issue2)
    self.issue3 = fake.MakeTestIssue(
        1, 3, 'issue_summary3', 'New', 222, project_name='project-name')
    self.services.issue.TestAddIssue(self.issue3)
    self.issues = [self.issue1, self.issue2, self.issue3]
    self.hotlist_item_fields = [
        (issue.issue_id, rank, 111, 1205079300, '') for
        rank, issue in enumerate(self.issues)]
    self.test_hotlist = self.services.features.TestAddHotlist(
        'hotlist', hotlist_id=123, owner_ids=[222], editor_ids=[111],
        hotlist_item_fields=self.hotlist_item_fields)
    self.hotlistissues = self.test_hotlist.items
    # Unless perms is specified,
    # MakeMonorailRequest will return an mr with admin permissions.
    self.mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.test_hotlist, path='/u/222/hotlists/123',
        services=self.services, perms=permissions.EMPTY_PERMISSIONSET)
    self.mr.hotlist_id = self.test_hotlist.hotlist_id
    self.mr.auth.user_id = 111
    self.mr.auth.effective_ids = {111}
    self.mr.viewed_user_auth.user_id = 111
    sorting.InitializeArtValues(self.services)

    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.testbed.deactivate()

  def testAssertBasePermissions(self):
    private_hotlist = self.services.features.TestAddHotlist(
        'privateHotlist', hotlist_id=321, owner_ids=[222],
        hotlist_item_fields=self.hotlist_item_fields, is_private=True)
    # non-members cannot view private hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=private_hotlist, perms=permissions.EMPTY_PERMISSIONSET)
    mr.auth.effective_ids = {333}
    mr.hotlist_id = private_hotlist.hotlist_id
    self.assertRaises(permissions.PermissionException,
                      self.servlet.AssertBasePermission, mr)

    # members can view private hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=private_hotlist, perms=permissions.EMPTY_PERMISSIONSET)
    mr.auth.effective_ids = {222, 444}
    mr.hotlist_id = private_hotlist.hotlist_id
    self.servlet.AssertBasePermission(mr)

    # non-members can view public hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.test_hotlist, perms=permissions.EMPTY_PERMISSIONSET)
    mr.auth.effective_ids = {333, 444}
    mr.hotlist_id = self.test_hotlist.hotlist_id
    self.servlet.AssertBasePermission(mr)

    # members can view public hotlists
    mr = testing_helpers.MakeMonorailRequest(
        hotlist=self.test_hotlist, perms=permissions.EMPTY_PERMISSIONSET)
    mr.auth.effective_ids = {111, 333}
    mr.hotlist_id = self.test_hotlist.hotlist_id
    self.servlet.AssertBasePermission(mr)

  def testGatherPageData(self):
    self.mr.mode = 'list'
    self.mr.auth.effective_ids = {111}
    self.mr.auth.user_id = 111
    self.mr.sort_spec = 'rank stars'
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(ezt.boolean(False), page_data['owner_permissions'])
    self.assertEqual(ezt.boolean(True), page_data['editor_permissions'])
    self.assertEqual(ezt.boolean(False), page_data['grid_mode'])
    self.assertEqual(ezt.boolean(True), page_data['allow_rerank'])

    self.mr.sort_spec = 'stars ranks'
    page_data = self.servlet.GatherPageData(self.mr)
    self.assertEqual(ezt.boolean(False), page_data['allow_rerank'])

  def testGetTableViewData(self):
    now = time.time()
    self.mox.StubOutWithMock(time, 'time')
    time.time().MultipleTimes().AndReturn(now)
    self.mox.ReplayAll()

    self.mr.auth.user_id = 222
    self.mr.col_spec = 'Stars Projects Rank'
    table_view_data = self.servlet.GetTableViewData(self.mr)
    self.assertEqual(table_view_data['edit_hotlist_token'], xsrf.GenerateToken(
        self.mr.auth.user_id, '/u/222/hotlists/hotlist.do'))
    self.assertEqual(table_view_data['add_issues_selected'], ezt.boolean(False))

    self.user2.obscure_email = False
    table_view_data = self.servlet.GetTableViewData(self.mr)
    self.assertEqual(table_view_data['edit_hotlist_token'], xsrf.GenerateToken(
        self.mr.auth.user_id, '/u/222/hotlists/hotlist.do'))
    self.mox.VerifyAll()

  def testGetGridViewData(self):
    # TODO(jojwang): Write this test
    pass

  def testProcessFormData_NoNewIssues(self):
    post_data = fake.PostData(remove=['false'], add_local_ids=[''])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue(url.endswith('u/222/hotlists/hotlist'))
    self.assertEqual(self.test_hotlist.items, self.hotlistissues)

  def testProcessFormData_AddBadIssueRef(self):
    self.servlet.PleaseCorrect = mock.Mock()
    post_data = fake.PostData(
        remove=['false'], add_local_ids=['no-such-project:999'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertIsNone(url)
    self.servlet.PleaseCorrect.assert_called_once()

  def testProcessFormData_RemoveBadIssueRef(self):
    post_data = fake.PostData(
        remove=['true'], add_local_ids=['no-such-project:999'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertIn('u/222/hotlists/hotlist', url)
    self.assertEqual(self.test_hotlist.items, self.hotlistissues)

  def testProcessFormData_NormalEditIssues(self):
    issue4 = fake.MakeTestIssue(
        1, 4, 'issue_summary4', 'New', 222, project_name='project-name')
    self.services.issue.TestAddIssue(issue4)
    issue5 = fake.MakeTestIssue(
        1, 5, 'issue_summary5', 'New', 222, project_name='project-name')
    self.services.issue.TestAddIssue(issue5)

    post_data = fake.PostData(remove=['false'],
                              add_local_ids=['project-name:4, project-name:5'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('u/222/hotlists/hotlist' in url)
    self.assertEqual(len(self.test_hotlist.items), 5)
    self.assertEqual(
        self.test_hotlist.items[3].issue_id, issue4.issue_id)
    self.assertEqual(
        self.test_hotlist.items[4].issue_id, issue5.issue_id)

    post_data = fake.PostData(remove=['true'], remove_local_ids=[
        'project-name:4, project-name:1, project-name:2'])
    url = self.servlet.ProcessFormData(self.mr, post_data)
    self.assertTrue('u/222/hotlists/hotlist' in url)
    self.assertTrue(len(self.test_hotlist.items), 2)
    issue_ids = [issue.issue_id for issue in self.test_hotlist.items]
    self.assertTrue(issue5.issue_id in issue_ids)
    self.assertTrue(self.issue3.issue_id in issue_ids)

  def testProcessFormData_NoPermissions(self):
    post_data = fake.PostData(remove=['false'],
                              add_local_ids=['project-name:4, project-name:5'])
    self.mr.auth.effective_ids = {333}
    self.mr.auth.user_id = 333
    with self.assertRaises(permissions.PermissionException):
      self.servlet.ProcessFormData(self.mr, post_data)
