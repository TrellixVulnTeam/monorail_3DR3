# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the project_svc module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import unittest

import mox
import mock

from google.appengine.ext import testbed

from framework import framework_constants
from framework import sql
from proto import project_pb2
from proto import user_pb2
from services import config_svc
from services import project_svc
from testing import fake

NOW = 12345678


def MakeProjectService(cache_manager, my_mox):
  project_service = project_svc.ProjectService(cache_manager)
  project_service.project_tbl = my_mox.CreateMock(sql.SQLTableManager)
  project_service.user2project_tbl = my_mox.CreateMock(sql.SQLTableManager)
  project_service.extraperm_tbl = my_mox.CreateMock(sql.SQLTableManager)
  project_service.membernotes_tbl = my_mox.CreateMock(sql.SQLTableManager)
  project_service.usergroupprojects_tbl = my_mox.CreateMock(
      sql.SQLTableManager)
  project_service.acexclusion_tbl = my_mox.CreateMock(
      sql.SQLTableManager)
  return project_service


class ProjectTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()
    self.project_service = MakeProjectService(self.cache_manager, self.mox)

  def tearDown(self):
    self.testbed.deactivate()

  def testDeserializeProjects(self):
    project_rows = [
        (
            123, 'proj1', 'test proj 1', 'test project', 'live', 'anyone', '',
            '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, False),
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'anyone', '',
            '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, True)
    ]
    role_rows = [
        (123, 111, 'owner'), (123, 444, 'owner'),
        (123, 222, 'committer'),
        (123, 333, 'contributor'),
        (234, 111, 'owner')]
    extraperm_rows = []

    project_dict = self.project_service.project_2lc._DeserializeProjects(
        project_rows, role_rows, extraperm_rows)

    self.assertItemsEqual([123, 234], list(project_dict.keys()))
    self.assertEqual(123, project_dict[123].project_id)
    self.assertEqual('proj1', project_dict[123].project_name)
    self.assertEqual(NOW, project_dict[123].recent_activity)
    self.assertItemsEqual([111, 444], project_dict[123].owner_ids)
    self.assertItemsEqual([222], project_dict[123].committer_ids)
    self.assertItemsEqual([333], project_dict[123].contributor_ids)
    self.assertEqual(234, project_dict[234].project_id)
    self.assertItemsEqual([111], project_dict[234].owner_ids)
    self.assertEqual(False, project_dict[123].issue_notify_always_detailed)
    self.assertEqual(True, project_dict[234].issue_notify_always_detailed)


class ProjectServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()
    self.config_service = self.mox.CreateMock(config_svc.ConfigService)
    self.project_service = MakeProjectService(self.cache_manager, self.mox)

    self.proj1 = fake.Project(project_name='proj1', project_id=123)
    self.proj2 = fake.Project(project_name='proj2', project_id=234)

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def SetUpCreateProject(self):
    # Check for existing project: there should be none.
    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_name', 'project_id'],
        project_name=['proj1']).AndReturn([])

    # Inserting the project gives the project ID.
    self.project_service.project_tbl.InsertRow(
        self.cnxn, project_name='proj1',
        summary='Test project summary', description='Test project description',
        home_page=None, docs_url=None, source_url=None,
        logo_file_name=None, logo_gcs_id=None,
        state='LIVE', access='ANYONE').AndReturn(123)

    # Insert the users.  There are none.
    self.project_service.user2project_tbl.InsertRows(
        self.cnxn, ['project_id', 'user_id', 'role_name'], [])

  def testCreateProject(self):
    self.SetUpCreateProject()
    self.mox.ReplayAll()
    self.project_service.CreateProject(
        self.cnxn, 'proj1', owner_ids=[], committer_ids=[], contributor_ids=[],
        summary='Test project summary', description='Test project description')
    self.mox.VerifyAll()

  def SetUpLookupProjectIDs(self):
    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_name', 'project_id'],
        project_name=['proj2']).AndReturn([('proj2', 234)])

  def testLookupProjectIDs(self):
    self.SetUpLookupProjectIDs()
    self.project_service.project_names_to_ids.CacheItem('proj1', 123)
    self.mox.ReplayAll()
    id_dict = self.project_service.LookupProjectIDs(
        self.cnxn, ['proj1', 'proj2'])
    self.mox.VerifyAll()
    self.assertEqual({'proj1': 123, 'proj2': 234}, id_dict)

  def testLookupProjectNames(self):
    self.SetUpGetProjects()  # Same as testGetProjects()
    self.project_service.project_2lc.CacheItem(123, self.proj1)
    self.mox.ReplayAll()
    name_dict = self.project_service.LookupProjectNames(
        self.cnxn, [123, 234])
    self.mox.VerifyAll()
    self.assertEqual({123: 'proj1', 234: 'proj2'}, name_dict)

  def SetUpGetProjects(self, roles=None, extra_perms=None):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'anyone', '',
            '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, False)
    ]
    self.project_service.project_tbl.Select(
        self.cnxn, cols=project_svc.PROJECT_COLS,
        project_id=[234]).AndReturn(project_rows)
    self.project_service.user2project_tbl.Select(
        self.cnxn, cols=['project_id', 'user_id', 'role_name'],
        project_id=[234]).AndReturn(roles or [])
    self.project_service.extraperm_tbl.Select(
        self.cnxn, cols=project_svc.EXTRAPERM_COLS,
        project_id=[234]).AndReturn(extra_perms or [])

  def testGetProjects(self):
    self.project_service.project_2lc.CacheItem(123, self.proj1)
    self.SetUpGetProjects()
    self.mox.ReplayAll()
    project_dict = self.project_service.GetProjects(
        self.cnxn, [123, 234])
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 234], list(project_dict.keys()))
    self.assertEqual('proj1', project_dict[123].project_name)
    self.assertEqual('proj2', project_dict[234].project_name)

  def testGetProjects_ExtraPerms(self):
    self.SetUpGetProjects(extra_perms=[(234, 222, 'BarPerm'),
                                       (234, 111, 'FooPerm')])
    self.mox.ReplayAll()
    project_dict = self.project_service.GetProjects(self.cnxn, [234])
    self.mox.VerifyAll()
    self.assertItemsEqual([234], list(project_dict.keys()))
    self.assertEqual(
        [project_pb2.Project.ExtraPerms(
             member_id=111, perms=['FooPerm']),
         project_pb2.Project.ExtraPerms(
             member_id=222, perms=['BarPerm'])],
        project_dict[234].extra_perms)


  def testGetVisibleLiveProjects_AnyoneAccessWithUser(self):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'anyone', '',
            '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, False)
    ]

    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'],
        state=project_pb2.ProjectState.LIVE).AndReturn(project_rows)
    self.SetUpGetProjects()
    self.mox.ReplayAll()
    user_a = user_pb2.User(email='a@example.com')
    project_ids = self.project_service.GetVisibleLiveProjects(
        self.cnxn, user_a, set([111]))

    self.mox.VerifyAll()
    self.assertItemsEqual([234], project_ids)

  def testGetVisibleLiveProjects_AnyoneAccessWithAnon(self):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'anyone', '',
            '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, False)
    ]

    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'],
        state=project_pb2.ProjectState.LIVE).AndReturn(project_rows)
    self.SetUpGetProjects()
    self.mox.ReplayAll()
    project_ids = self.project_service.GetVisibleLiveProjects(
        self.cnxn, None, None)

    self.mox.VerifyAll()
    self.assertItemsEqual([234], project_ids)

  def testGetVisibleLiveProjects_RestrictedAccessWithMember(self):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'members_only',
            '', '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, False, None, None, None, None, None, None, False)
    ]
    self.proj2.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.proj2.contributor_ids.append(111)
    self.project_service.project_2lc.CacheItem(234, self.proj2)

    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'],
        state=project_pb2.ProjectState.LIVE).AndReturn(project_rows)
    self.mox.ReplayAll()
    user_a = user_pb2.User(email='a@example.com')
    project_ids = self.project_service.GetVisibleLiveProjects(
        self.cnxn, user_a, set([111]))

    self.mox.VerifyAll()
    self.assertItemsEqual([234], project_ids)

  def testGetVisibleLiveProjects_RestrictedAccessWithNonMember(self):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'members_only',
            '', '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, False)
    ]
    self.proj2.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.project_service.project_2lc.CacheItem(234, self.proj2)

    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'],
        state=project_pb2.ProjectState.LIVE).AndReturn(project_rows)
    self.mox.ReplayAll()
    user_a = user_pb2.User(email='a@example.com')
    project_ids = self.project_service.GetVisibleLiveProjects(
        self.cnxn, user_a, set([111]))

    self.mox.VerifyAll()
    self.assertItemsEqual([], project_ids)

  def testGetVisibleLiveProjects_RestrictedAccessWithAnon(self):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'members_only',
            '', '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, False)
    ]
    self.proj2.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.project_service.project_2lc.CacheItem(234, self.proj2)

    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'],
        state=project_pb2.ProjectState.LIVE).AndReturn(project_rows)
    self.mox.ReplayAll()
    project_ids = self.project_service.GetVisibleLiveProjects(
        self.cnxn, None, None)

    self.mox.VerifyAll()
    self.assertItemsEqual([], project_ids)

  def testGetVisibleLiveProjects_RestrictedAccessWithSiteAdmin(self):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'live', 'members_only',
            '', '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, False)
    ]
    self.proj2.access = project_pb2.ProjectAccess.MEMBERS_ONLY
    self.project_service.project_2lc.CacheItem(234, self.proj2)

    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'],
        state=project_pb2.ProjectState.LIVE).AndReturn(project_rows)
    self.mox.ReplayAll()
    user_a = user_pb2.User(email='a@example.com')
    user_a.is_site_admin = True
    project_ids = self.project_service.GetVisibleLiveProjects(
        self.cnxn, user_a, set([111]))

    self.mox.VerifyAll()
    self.assertItemsEqual([234], project_ids)

  def testGetVisibleLiveProjects_ArchivedProject(self):
    project_rows = [
        (
            234, 'proj2', 'test proj 2', 'test project', 'archived', 'anyone',
            '', '', None, '', 0, 50 * 1024 * 1024, NOW, NOW, None, True, False,
            False, None, None, None, None, None, None, False)
    ]
    self.proj2.state = project_pb2.ProjectState.ARCHIVED
    self.project_service.project_2lc.CacheItem(234, self.proj2)

    self.project_service.project_tbl.Select(
        self.cnxn, cols=['project_id'],
        state=project_pb2.ProjectState.LIVE).AndReturn(project_rows)
    self.mox.ReplayAll()
    user_a = user_pb2.User(email='a@example.com')
    project_ids = self.project_service.GetVisibleLiveProjects(
        self.cnxn, user_a, set([111]))

    self.mox.VerifyAll()
    self.assertItemsEqual([], project_ids)

  def testGetProjectsByName(self):
    self.project_service.project_names_to_ids.CacheItem('proj1', 123)
    self.project_service.project_2lc.CacheItem(123, self.proj1)
    self.SetUpLookupProjectIDs()
    self.SetUpGetProjects()
    self.mox.ReplayAll()
    project_dict = self.project_service.GetProjectsByName(
        self.cnxn, ['proj1', 'proj2'])
    self.mox.VerifyAll()
    self.assertItemsEqual(['proj1', 'proj2'], list(project_dict.keys()))
    self.assertEqual(123, project_dict['proj1'].project_id)
    self.assertEqual(234, project_dict['proj2'].project_id)

  def SetUpExpungeProject(self):
    self.project_service.user2project_tbl.Delete(
        self.cnxn, project_id=234)
    self.project_service.usergroupprojects_tbl.Delete(
        self.cnxn, project_id=234)
    self.project_service.extraperm_tbl.Delete(
        self.cnxn, project_id=234)
    self.project_service.membernotes_tbl.Delete(
        self.cnxn, project_id=234)
    self.project_service.acexclusion_tbl.Delete(
        self.cnxn, project_id=234)
    self.project_service.project_tbl.Delete(
        self.cnxn, project_id=234)

  def testExpungeProject(self):
    self.SetUpExpungeProject()
    self.mox.ReplayAll()
    self.project_service.ExpungeProject(self.cnxn, 234)
    self.mox.VerifyAll()

  def SetUpUpdateProject(self, project_id, delta):
    self.project_service.project_tbl.SelectValue(
        self.cnxn, 'project_name', project_id=project_id).AndReturn('projN')
    self.project_service.project_tbl.Update(
        self.cnxn, delta, project_id=project_id)

  def testUpdateProject(self):
    delta = {'summary': 'An even better one-line summary'}
    self.SetUpUpdateProject(234, delta)
    self.mox.ReplayAll()
    self.project_service.UpdateProject(
        self.cnxn, 234, summary='An even better one-line summary')
    self.mox.VerifyAll()

  def testUpdateProject_NotifyAlwaysDetailed(self):
    delta = {'issue_notify_always_detailed': True}
    self.SetUpUpdateProject(234, delta)
    self.mox.ReplayAll()
    self.project_service.UpdateProject(
        self.cnxn, 234, issue_notify_always_detailed=True)
    self.mox.VerifyAll()

  def SetUpUpdateProjectRoles(
      self, project_id, owner_ids, committer_ids, contributor_ids):
    self.project_service.project_tbl.SelectValue(
        self.cnxn, 'project_name', project_id=project_id).AndReturn('projN')
    self.project_service.project_tbl.Update(
        self.cnxn, {'cached_content_timestamp': NOW}, project_id=project_id,
        commit=False)

    self.project_service.user2project_tbl.Delete(
        self.cnxn, project_id=project_id, role_name='owner', commit=False)
    self.project_service.user2project_tbl.Delete(
        self.cnxn, project_id=project_id, role_name='committer', commit=False)
    self.project_service.user2project_tbl.Delete(
        self.cnxn, project_id=project_id, role_name='contributor',
        commit=False)

    self.project_service.user2project_tbl.InsertRows(
        self.cnxn, ['project_id', 'user_id', 'role_name'],
        [(project_id, user_id, 'owner') for user_id in owner_ids],
        commit=False)
    self.project_service.user2project_tbl.InsertRows(
        self.cnxn, ['project_id', 'user_id', 'role_name'],
        [(project_id, user_id, 'committer') for user_id in committer_ids],
        commit=False)
    self.project_service.user2project_tbl.InsertRows(
        self.cnxn, ['project_id', 'user_id', 'role_name'],
        [(project_id, user_id, 'contributor') for user_id in contributor_ids],
        commit=False)

    self.cnxn.Commit()

  def testUpdateProjectRoles(self):
    self.SetUpUpdateProjectRoles(234, [111, 222], [333], [])
    self.mox.ReplayAll()
    self.project_service.UpdateProjectRoles(
        self.cnxn, 234, [111, 222], [333], [], now=NOW)
    self.mox.VerifyAll()

  def SetUpMarkProjectDeletable(self):
    delta = {
        'project_name': 'DELETABLE_123',
        'state': 'deletable',
        }
    self.project_service.project_tbl.Update(self.cnxn, delta, project_id=123)
    self.config_service.InvalidateMemcacheForEntireProject(123)

  def testMarkProjectDeletable(self):
    self.SetUpMarkProjectDeletable()
    self.mox.ReplayAll()
    self.project_service.MarkProjectDeletable(
        self.cnxn, 123, self.config_service)
    self.mox.VerifyAll()

  def testUpdateRecentActivity_SignificantlyLaterActivity(self):
    activity_time = NOW + framework_constants.SECS_PER_HOUR * 3
    delta = {'recent_activity_timestamp': activity_time}
    self.SetUpGetProjects()
    self.SetUpUpdateProject(234, delta)
    self.mox.ReplayAll()
    self.project_service.UpdateRecentActivity(self.cnxn, 234, now=activity_time)
    self.mox.VerifyAll()

  def testUpdateRecentActivity_NotSignificant(self):
    activity_time = NOW + 123
    self.SetUpGetProjects()
    # ProjectUpdate is not called.
    self.mox.ReplayAll()
    self.project_service.UpdateRecentActivity(self.cnxn, 234, now=activity_time)
    self.mox.VerifyAll()

  def SetUpGetUserRolesInAllProjects(self):
    rows = [
        (123, 'committer'),
        (234, 'owner'),
        ]
    self.project_service.user2project_tbl.Select(
        self.cnxn, cols=['project_id', 'role_name'],
        user_id={111, 888}).AndReturn(rows)

  def testGetUserRolesInAllProjects(self):
    self.SetUpGetUserRolesInAllProjects()
    self.mox.ReplayAll()
    actual = self.project_service.GetUserRolesInAllProjects(
        self.cnxn, {111, 888})
    owned_project_ids, membered_project_ids, contrib_project_ids = actual
    self.mox.VerifyAll()
    self.assertItemsEqual([234], owned_project_ids)
    self.assertItemsEqual([123], membered_project_ids)
    self.assertItemsEqual([], contrib_project_ids)

  def SetUpUpdateExtraPerms(self):
    self.project_service.extraperm_tbl.Delete(
        self.cnxn, project_id=234, user_id=111, commit=False)
    self.project_service.extraperm_tbl.InsertRows(
        self.cnxn, project_svc.EXTRAPERM_COLS,
        [(234, 111, 'SecurityTeam')], commit=False)
    self.project_service.project_tbl.Update(
        self.cnxn, {'cached_content_timestamp': NOW},
        project_id=234, commit=False)
    self.cnxn.Commit()

  def testUpdateExtraPerms(self):
    self.SetUpGetProjects(roles=[(234, 111, 'owner')])
    self.SetUpUpdateExtraPerms()
    self.mox.ReplayAll()
    self.project_service.UpdateExtraPerms(
        self.cnxn, 234, 111, ['SecurityTeam'], now=NOW)
    self.mox.VerifyAll()

  def testExpungeUsersInProjects(self):
    self.project_service.extraperm_tbl.Delete = mock.Mock()
    self.project_service.acexclusion_tbl.Delete = mock.Mock()
    self.project_service.membernotes_tbl.Delete = mock.Mock()
    self.project_service.user2project_tbl.Delete = mock.Mock()

    user_ids = [111, 222]
    limit= 16
    self.project_service.ExpungeUsersInProjects(
        self.cnxn, user_ids, limit=limit)

    call = [mock.call(self.cnxn, user_id=user_ids, limit=limit, commit=False)]
    self.project_service.extraperm_tbl.Delete.assert_has_calls(call)
    self.project_service.acexclusion_tbl.Delete.assert_has_calls(call)
    self.project_service.membernotes_tbl.Delete.assert_has_calls(call)
    self.project_service.user2project_tbl.Delete.assert_has_calls(call)
