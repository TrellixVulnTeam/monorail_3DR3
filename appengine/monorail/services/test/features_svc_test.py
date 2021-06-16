# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for features_svc module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import mox
import time
import unittest
import mock

from google.appengine.api import memcache
from google.appengine.ext import testbed

import settings

from features import filterrules_helpers
from features import features_constants
from framework import exceptions
from framework import framework_constants
from framework import sql
from proto import tracker_pb2
from proto import features_pb2
from services import chart_svc
from services import features_svc
from services import star_svc
from services import user_svc
from testing import fake
from tracker import tracker_bizobj
from tracker import tracker_constants


# NOTE: we are in the process of moving away from mox towards mock.
# This file is a mix of both. All new tests or big test updates should make
# use of the mock package.
def MakeFeaturesService(cache_manager, my_mox):
  features_service = features_svc.FeaturesService(cache_manager,
      fake.ConfigService())
  features_service.hotlist_tbl = my_mox.CreateMock(sql.SQLTableManager)
  features_service.hotlist2issue_tbl = my_mox.CreateMock(sql.SQLTableManager)
  features_service.hotlist2user_tbl = my_mox.CreateMock(sql.SQLTableManager)
  return features_service


class HotlistTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()
    self.features_service = MakeFeaturesService(self.cache_manager, self.mox)

  def tearDown(self):
    self.testbed.deactivate()

  def testDeserializeHotlists(self):
    hotlist_rows = [
        (123, 'hot1', 'test hot 1', 'test hotlist', False, ''),
        (234, 'hot2', 'test hot 2', 'test hotlist', False, '')]

    ts = 20021111111111
    issue_rows = [
        (123, 567, 10, 111, ts, ''), (123, 678, 9, 111, ts, ''),
        (234, 567, 0, 111, ts, '')]
    role_rows = [
        (123, 111, 'owner'), (123, 444, 'owner'),
        (123, 222, 'editor'),
        (123, 333, 'follower'),
        (234, 111, 'owner')]
    hotlist_dict = self.features_service.hotlist_2lc._DeserializeHotlists(
        hotlist_rows, issue_rows, role_rows)

    self.assertItemsEqual([123, 234], list(hotlist_dict.keys()))
    self.assertEqual(123, hotlist_dict[123].hotlist_id)
    self.assertEqual('hot1', hotlist_dict[123].name)
    self.assertItemsEqual([111, 444], hotlist_dict[123].owner_ids)
    self.assertItemsEqual([222], hotlist_dict[123].editor_ids)
    self.assertItemsEqual([333], hotlist_dict[123].follower_ids)
    self.assertEqual(234, hotlist_dict[234].hotlist_id)
    self.assertItemsEqual([111], hotlist_dict[234].owner_ids)


class HotlistIDTwoLevelCache(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()
    self.features_service = MakeFeaturesService(self.cache_manager, self.mox)
    self.hotlist_id_2lc = self.features_service.hotlist_id_2lc

  def tearDown(self):
    memcache.flush_all()
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testGetAll(self):
    cached_keys = [('name1', 111), ('name2', 222)]
    self.hotlist_id_2lc.CacheItem(cached_keys[0], 121)
    self.hotlist_id_2lc.CacheItem(cached_keys[1], 122)

    # Set up DB query mocks.
    # Test that a ('name1', 222) or ('name3', 333) hotlist
    # does not get returned by GetAll even though these hotlists
    # exist and are returned by the DB queries.
    from_db_keys = [
        ('name1', 333), ('name3', 222), ('name3', 555)]
    self.features_service.hotlist2user_tbl.Select = mock.Mock(return_value=[
        (123, 333),  # name1 hotlist
        (124, 222),  # name3 hotlist
        (125, 222),  # name1 hotlist, should be ignored
        (126, 333),  # name3 hotlist, should be ignored
        (127, 555),  # wrongname hotlist, should be ignored
    ])
    self.features_service.hotlist_tbl.Select = mock.Mock(
        return_value=[(123, 'Name1'), (124, 'Name3'),
                      (125, 'Name1'), (126, 'Name3')])

    hit, misses = self.hotlist_id_2lc.GetAll(
        self.cnxn, cached_keys + from_db_keys)

    # Assertions
    self.features_service.hotlist2user_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['hotlist_id', 'user_id'], user_id=[555, 333, 222],
        role_name='owner')
    hotlist_ids = [123, 124, 125, 126, 127]
    self.features_service.hotlist_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['id', 'name'], id=hotlist_ids, is_deleted=False,
        where=[('LOWER(name) IN (%s,%s)', ['name3', 'name1'])])

    self.assertEqual(hit,{
        ('name1', 111): 121,
        ('name2', 222): 122,
        ('name1', 333): 123,
        ('name3', 222): 124})
    self.assertEqual(from_db_keys[-1:], misses)


class FeaturesServiceTest(unittest.TestCase):

  def MakeMockTable(self):
    return self.mox.CreateMock(sql.SQLTableManager)

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.cache_manager = fake.CacheManager()
    self.config_service = fake.ConfigService()

    self.features_service = features_svc.FeaturesService(self.cache_manager,
        self.config_service)
    self.issue_service = fake.IssueService()
    self.chart_service = self.mox.CreateMock(chart_svc.ChartService)

    for table_var in [
        'user2savedquery_tbl', 'quickedithistory_tbl',
        'quickeditmostrecent_tbl', 'savedquery_tbl',
        'savedqueryexecutesinproject_tbl', 'project2savedquery_tbl',
        'filterrule_tbl', 'hotlist_tbl', 'hotlist2issue_tbl',
        'hotlist2user_tbl']:
      setattr(self.features_service, table_var, self.MakeMockTable())

  def tearDown(self):
    memcache.flush_all()
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  ### quickedit command history

  def testGetRecentCommands(self):
    self.features_service.quickedithistory_tbl.Select(
        self.cnxn, cols=['slot_num', 'command', 'comment'],
        user_id=1, project_id=12345).AndReturn(
        [(1, 'status=New', 'Brand new issue')])
    self.features_service.quickeditmostrecent_tbl.SelectValue(
        self.cnxn, 'slot_num', default=1, user_id=1, project_id=12345
        ).AndReturn(1)
    self.mox.ReplayAll()
    slots, recent_slot_num = self.features_service.GetRecentCommands(
        self.cnxn, 1, 12345)
    self.mox.VerifyAll()

    self.assertEqual(1, recent_slot_num)
    self.assertEqual(
        len(tracker_constants.DEFAULT_RECENT_COMMANDS), len(slots))
    self.assertEqual('status=New', slots[0][1])

  def testStoreRecentCommand(self):
    self.features_service.quickedithistory_tbl.InsertRow(
        self.cnxn, replace=True, user_id=1, project_id=12345,
        slot_num=1, command='status=New', comment='Brand new issue')
    self.features_service.quickeditmostrecent_tbl.InsertRow(
        self.cnxn, replace=True, user_id=1, project_id=12345,
        slot_num=1)
    self.mox.ReplayAll()
    self.features_service.StoreRecentCommand(
        self.cnxn, 1, 12345, 1, 'status=New', 'Brand new issue')
    self.mox.VerifyAll()

  def testExpungeQuickEditHistory(self):
    self.features_service.quickeditmostrecent_tbl.Delete(
        self.cnxn, project_id=12345)
    self.features_service.quickedithistory_tbl.Delete(
        self.cnxn, project_id=12345)
    self.mox.ReplayAll()
    self.features_service.ExpungeQuickEditHistory(
        self.cnxn, 12345)
    self.mox.VerifyAll()

  def testExpungeQuickEditsByUsers(self):
    user_ids = [333, 555, 777]
    commit = False

    self.features_service.quickeditmostrecent_tbl.Delete = mock.Mock()
    self.features_service.quickedithistory_tbl.Delete = mock.Mock()

    self.features_service.ExpungeQuickEditsByUsers(
        self.cnxn, user_ids, limit=50)

    self.features_service.quickeditmostrecent_tbl.Delete.\
assert_called_once_with(self.cnxn, user_id=user_ids, commit=commit, limit=50)
    self.features_service.quickedithistory_tbl.Delete.\
assert_called_once_with(self.cnxn, user_id=user_ids, commit=commit, limit=50)

  ### Saved User and Project Queries

  def testGetSavedQuery_Valid(self):
    self.features_service.savedquery_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERY_COLS, id=[1]).AndReturn(
        [(1, 'query1', 100, 'owner:me')])
    self.features_service.savedqueryexecutesinproject_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS,
        query_id=[1]).AndReturn([(1, 12345)])
    self.mox.ReplayAll()
    saved_query = self.features_service.GetSavedQuery(
        self.cnxn, 1)
    self.mox.VerifyAll()
    self.assertEqual(1, saved_query.query_id)
    self.assertEqual('query1', saved_query.name)
    self.assertEqual(100, saved_query.base_query_id)
    self.assertEqual('owner:me', saved_query.query)
    self.assertEqual([12345], saved_query.executes_in_project_ids)

  def testGetSavedQuery_Invalid(self):
    self.features_service.savedquery_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERY_COLS, id=[99]).AndReturn([])
    self.features_service.savedqueryexecutesinproject_tbl.Select(
        self.cnxn, cols=features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS,
        query_id=[99]).AndReturn([])
    self.mox.ReplayAll()
    saved_query = self.features_service.GetSavedQuery(
        self.cnxn, 99)
    self.mox.VerifyAll()
    self.assertIsNone(saved_query)

  def SetUpUsersSavedQueries(self):
    query = tracker_bizobj.MakeSavedQuery(1, 'query1', 100, 'owner:me')
    self.features_service.saved_query_cache.CacheItem(1, [query])
    self.features_service.user2savedquery_tbl.Select(
        self.cnxn,
        cols=features_svc.SAVEDQUERY_COLS + ['user_id', 'subscription_mode'],
        left_joins=[('SavedQuery ON query_id = id', [])],
        order_by=[('rank', [])], user_id=[2]).AndReturn(
        [(2, 'query2', 100, 'status:New', 2, 'Sub_Mode')])
    self.features_service.savedqueryexecutesinproject_tbl.Select(
          self.cnxn, cols=features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS,
          query_id=set([2])).AndReturn([(2, 12345)])

  def testGetUsersSavedQueriesDict(self):
    self.SetUpUsersSavedQueries()
    self.mox.ReplayAll()
    results_dict = self.features_service._GetUsersSavedQueriesDict(
        self.cnxn, [1, 2])
    self.mox.VerifyAll()
    self.assertIn(1, results_dict)
    self.assertIn(2, results_dict)

  def testGetSavedQueriesByUserID(self):
    self.SetUpUsersSavedQueries()
    self.mox.ReplayAll()
    saved_queries = self.features_service.GetSavedQueriesByUserID(
        self.cnxn, 2)
    self.mox.VerifyAll()
    self.assertEqual(1, len(saved_queries))
    self.assertEqual(2, saved_queries[0].query_id)

  def SetUpCannedQueriesForProjects(self, project_ids):
    query = tracker_bizobj.MakeSavedQuery(
        2, 'project-query-2', 110, 'owner:goose@chaos.honk')
    self.features_service.canned_query_cache.CacheItem(12346, [query])
    self.features_service.canned_query_cache.CacheAll = mock.Mock()
    self.features_service.project2savedquery_tbl.Select(
        self.cnxn, cols=['project_id'] + features_svc.SAVEDQUERY_COLS,
        left_joins=[('SavedQuery ON query_id = id', [])],
        order_by=[('rank', [])], project_id=project_ids).AndReturn(
        [(12345, 1, 'query1', 100, 'owner:me')])

  def testGetCannedQueriesForProjects(self):
    project_ids = [12345, 12346]
    self.SetUpCannedQueriesForProjects(project_ids)
    self.mox.ReplayAll()
    results_dict = self.features_service.GetCannedQueriesForProjects(
        self.cnxn, project_ids)
    self.mox.VerifyAll()
    self.assertIn(12345, results_dict)
    self.assertIn(12346, results_dict)
    self.features_service.canned_query_cache.CacheAll.assert_called_once_with(
        results_dict)

  def testGetCannedQueriesByProjectID(self):
    project_id= 12345
    self.SetUpCannedQueriesForProjects([project_id])
    self.mox.ReplayAll()
    result = self.features_service.GetCannedQueriesByProjectID(
        self.cnxn, project_id)
    self.mox.VerifyAll()
    self.assertEqual(1, len(result))
    self.assertEqual(1, result[0].query_id)

  def SetUpUpdateSavedQueries(self, commit=True):
    query1 = tracker_bizobj.MakeSavedQuery(1, 'query1', 100, 'owner:me')
    query2 = tracker_bizobj.MakeSavedQuery(None, 'query2', 100, 'status:New')
    saved_queries = [query1, query2]
    savedquery_rows = [
        (sq.query_id or None, sq.name, sq.base_query_id, sq.query)
        for sq in saved_queries]
    self.features_service.savedquery_tbl.Delete(
        self.cnxn, id=[1], commit=commit)
    self.features_service.savedquery_tbl.InsertRows(
        self.cnxn, features_svc.SAVEDQUERY_COLS, savedquery_rows, commit=commit,
        return_generated_ids=True).AndReturn([11, 12])
    return saved_queries

  def testUpdateSavedQueries(self):
    saved_queries = self.SetUpUpdateSavedQueries()
    self.mox.ReplayAll()
    self.features_service._UpdateSavedQueries(
        self.cnxn, saved_queries, True)
    self.mox.VerifyAll()

  def testUpdateCannedQueries(self):
    self.features_service.project2savedquery_tbl.Delete(
        self.cnxn, project_id=12345, commit=False)
    canned_queries = self.SetUpUpdateSavedQueries(False)
    project2savedquery_rows = [(12345, 0, 1), (12345, 1, 12)]
    self.features_service.project2savedquery_tbl.InsertRows(
        self.cnxn, features_svc.PROJECT2SAVEDQUERY_COLS,
        project2savedquery_rows, commit=False)
    self.features_service.canned_query_cache.Invalidate = mock.Mock()
    self.cnxn.Commit()
    self.mox.ReplayAll()
    self.features_service.UpdateCannedQueries(
        self.cnxn, 12345, canned_queries)
    self.mox.VerifyAll()
    self.features_service.canned_query_cache.Invalidate.assert_called_once_with(
        self.cnxn, 12345)

  def testUpdateUserSavedQueries(self):
    saved_queries = self.SetUpUpdateSavedQueries(False)
    self.features_service.savedqueryexecutesinproject_tbl.Delete(
        self.cnxn, query_id=[1], commit=False)
    self.features_service.user2savedquery_tbl.Delete(
        self.cnxn, user_id=1, commit=False)
    user2savedquery_rows = [
      (1, 0, 1, 'noemail'), (1, 1, 12, 'noemail')]
    self.features_service.user2savedquery_tbl.InsertRows(
        self.cnxn, features_svc.USER2SAVEDQUERY_COLS,
        user2savedquery_rows, commit=False)
    self.features_service.savedqueryexecutesinproject_tbl.InsertRows(
        self.cnxn, features_svc.SAVEDQUERYEXECUTESINPROJECT_COLS, [],
        commit=False)
    self.cnxn.Commit()
    self.mox.ReplayAll()
    self.features_service.UpdateUserSavedQueries(
        self.cnxn, 1, saved_queries)
    self.mox.VerifyAll()

  ### Subscriptions

  def testGetSubscriptionsInProjects(self):
    sqeip_join_str = (
        'SavedQueryExecutesInProject ON '
        'SavedQueryExecutesInProject.query_id = User2SavedQuery.query_id')
    user_join_str = (
        'User ON '
        'User.user_id = User2SavedQuery.user_id')
    now = 1519418530
    self.mox.StubOutWithMock(time, 'time')
    time.time().MultipleTimes().AndReturn(now)
    absence_threshold = now - settings.subscription_timeout_secs
    where = [
        ('(User.banned IS NULL OR User.banned = %s)', ['']),
        ('User.last_visit_timestamp >= %s', [absence_threshold]),
        ('(User.email_bounce_timestamp IS NULL OR '
         'User.email_bounce_timestamp = %s)', [0]),
        ]
    self.features_service.user2savedquery_tbl.Select(
        self.cnxn, cols=['User2SavedQuery.user_id'], distinct=True,
        joins=[(sqeip_join_str, []), (user_join_str, [])],
        subscription_mode='immediate', project_id=12345,
        where=where).AndReturn(
        [(1, 'asd'), (2, 'efg')])
    self.SetUpUsersSavedQueries()
    self.mox.ReplayAll()
    result = self.features_service.GetSubscriptionsInProjects(
        self.cnxn, 12345)
    self.mox.VerifyAll()
    self.assertIn(1, result)
    self.assertIn(2, result)

  def testExpungeSavedQueriesExecuteInProject(self):
    self.features_service.savedqueryexecutesinproject_tbl.Delete(
        self.cnxn, project_id=12345)
    self.features_service.project2savedquery_tbl.Select(
        self.cnxn, cols=['query_id'], project_id=12345).AndReturn(
        [(1, 'asd'), (2, 'efg')])
    self.features_service.project2savedquery_tbl.Delete(
        self.cnxn, project_id=12345)
    self.features_service.savedquery_tbl.Delete(
        self.cnxn, id=[1, 2])
    self.mox.ReplayAll()
    self.features_service.ExpungeSavedQueriesExecuteInProject(
        self.cnxn, 12345)
    self.mox.VerifyAll()

  def testExpungeSavedQueriesByUsers(self):
    user_ids = [222, 444, 666]
    commit = False

    sv_rows = [(8,), (9,)]
    self.features_service.user2savedquery_tbl.Select = mock.Mock(
        return_value=sv_rows)
    self.features_service.user2savedquery_tbl.Delete = mock.Mock()
    self.features_service.savedqueryexecutesinproject_tbl.Delete = mock.Mock()
    self.features_service.savedquery_tbl.Delete = mock.Mock()

    self.features_service.ExpungeSavedQueriesByUsers(
        self.cnxn, user_ids, limit=50)

    self.features_service.user2savedquery_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['query_id'], user_id=user_ids, limit=50)
    self.features_service.user2savedquery_tbl.Delete.assert_called_once_with(
        self.cnxn, query_id=[8, 9], commit=commit)
    self.features_service.savedqueryexecutesinproject_tbl.\
Delete.assert_called_once_with(
        self.cnxn, query_id=[8, 9], commit=commit)
    self.features_service.savedquery_tbl.Delete.assert_called_once_with(
        self.cnxn, id=[8, 9], commit=commit)


  ### Filter Rules

  def testDeserializeFilterRules(self):
    filterrule_rows = [
        (12345, 0, 'predicate1', 'default_status:New'),
        (12345, 1, 'predicate2', 'default_owner_id:1 add_cc_id:2'),
    ]
    result_dict = self.features_service._DeserializeFilterRules(
        filterrule_rows)
    self.assertIn(12345, result_dict)
    self.assertEqual(2, len(result_dict[12345]))
    self.assertEqual('New', result_dict[12345][0].default_status)
    self.assertEqual(1, result_dict[12345][1].default_owner_id)
    self.assertEqual([2], result_dict[12345][1].add_cc_ids)

  def testDeserializeRuleConsequence_Multiple(self):
    consequence = ('default_status:New default_owner_id:1 add_cc_id:2'
                   ' add_label:label-1 add_label:label.2'
                   ' add_notify:admin@example.com')
    (default_status, default_owner_id, add_cc_ids, add_labels,
     add_notify, warning, error
     ) = self.features_service._DeserializeRuleConsequence(
        consequence)
    self.assertEqual('New', default_status)
    self.assertEqual(1, default_owner_id)
    self.assertEqual([2], add_cc_ids)
    self.assertEqual(['label-1', 'label.2'], add_labels)
    self.assertEqual(['admin@example.com'], add_notify)
    self.assertEqual(None, warning)
    self.assertEqual(None, error)

  def testDeserializeRuleConsequence_Warning(self):
    consequence = ('warning:Do not use status:New if there is an owner')
    (_status, _owner_id, _cc_ids, _labels, _notify,
     warning, _error) = self.features_service._DeserializeRuleConsequence(
        consequence)
    self.assertEqual(
        'Do not use status:New if there is an owner',
        warning)

  def testDeserializeRuleConsequence_Error(self):
    consequence = ('error:Pri-0 issues require an owner')
    (_status, _owner_id, _cc_ids, _labels, _notify,
     _warning, error) = self.features_service._DeserializeRuleConsequence(
        consequence)
    self.assertEqual(
        'Pri-0 issues require an owner',
        error)

  def SetUpGetFilterRulesByProjectIDs(self):
    filterrule_rows = [
        (12345, 0, 'predicate1', 'default_status:New'),
        (12345, 1, 'predicate2', 'default_owner_id:1 add_cc_id:2'),
    ]

    self.features_service.filterrule_tbl.Select(
        self.cnxn, cols=features_svc.FILTERRULE_COLS,
        project_id=[12345]).AndReturn(filterrule_rows)

  def testGetFilterRulesByProjectIDs(self):
    self.SetUpGetFilterRulesByProjectIDs()
    self.mox.ReplayAll()
    result = self.features_service._GetFilterRulesByProjectIDs(
        self.cnxn, [12345])
    self.mox.VerifyAll()
    self.assertIn(12345, result)
    self.assertEqual(2, len(result[12345]))

  def testGetFilterRules(self):
    self.SetUpGetFilterRulesByProjectIDs()
    self.mox.ReplayAll()
    result = self.features_service.GetFilterRules(
        self.cnxn, 12345)
    self.mox.VerifyAll()
    self.assertEqual(2, len(result))

  def testSerializeRuleConsequence(self):
    rule = filterrules_helpers.MakeRule(
        'predicate', 'New', 1, [1, 2], ['label1', 'label2'], ['admin'])
    result = self.features_service._SerializeRuleConsequence(rule)
    self.assertEqual('add_label:label1 add_label:label2 default_status:New'
                     ' default_owner_id:1 add_cc_id:1 add_cc_id:2'
                     ' add_notify:admin', result)

  def testUpdateFilterRules(self):
    self.features_service.filterrule_tbl.Delete(self.cnxn, project_id=12345)
    rows = [
        (12345, 0, 'predicate1', 'add_label:label1 add_label:label2'
                                 ' default_status:New default_owner_id:1'
                                 ' add_cc_id:1 add_cc_id:2 add_notify:admin'),
        (12345, 1, 'predicate2', 'add_label:label2 add_label:label3'
                                 ' default_status:Fixed default_owner_id:2'
                                 ' add_cc_id:1 add_cc_id:2 add_notify:admin2')
    ]
    self.features_service.filterrule_tbl.InsertRows(
        self.cnxn, features_svc.FILTERRULE_COLS, rows)
    rule1 = filterrules_helpers.MakeRule(
        'predicate1', 'New', 1, [1, 2], ['label1', 'label2'], ['admin'])
    rule2 = filterrules_helpers.MakeRule(
        'predicate2', 'Fixed', 2, [1, 2], ['label2', 'label3'], ['admin2'])
    self.mox.ReplayAll()
    self.features_service.UpdateFilterRules(
        self.cnxn, 12345, [rule1, rule2])
    self.mox.VerifyAll()

  def testExpungeFilterRules(self):
    self.features_service.filterrule_tbl.Delete(self.cnxn, project_id=12345)
    self.mox.ReplayAll()
    self.features_service.ExpungeFilterRules(
        self.cnxn, 12345)
    self.mox.VerifyAll()

  def testExpungeFilterRulesByUser(self):
    emails = {'chicken@farm.test': 333, 'cow@fart.test': 222}
    project_1_keep_rows = [
        (1, 1, 'label:no-match-here', 'add_label:should-be-deleted-inserted')]
    project_16_keep_rows =[
        (16, 20, 'label:no-match-here', 'add_label:should-be-deleted-inserted'),
        (16, 21, 'owner:rainbow@test.com', 'add_label:delete-and-insert')]
    random_row = [
        (19, 9, 'label:no-match-in-project', 'add_label:no-DELETE-INSERTROW')]
    rows_to_delete = [
        (1, 45, 'owner:cow@fart.test', 'add_label:happy-cows'),
        (1, 46, 'owner:cow@fart.test', 'add_label:balloon'),
        (16, 47, 'label:queue-eggs', 'add_notify:chicken@farm.test'),
        (17, 48, 'owner:farmer@farm.test', 'add_cc_id:111 add_cc_id:222'),
        (17, 48, 'label:queue-chickens', 'default_owner_id:333'),
    ]
    rows = (rows_to_delete + project_1_keep_rows + project_16_keep_rows +
            random_row)
    self.features_service.filterrule_tbl.Select = mock.Mock(return_value=rows)
    self.features_service.filterrule_tbl.Delete = mock.Mock()

    rules_dict = self.features_service.ExpungeFilterRulesByUser(
        self.cnxn, emails)
    expected_dict = {
        1: [tracker_pb2.FilterRule(
            predicate=rows[0][2], add_labels=['happy-cows']),
            tracker_pb2.FilterRule(
                predicate=rows[1][2], add_labels=['balloon'])],
        16: [tracker_pb2.FilterRule(
            predicate=rows[2][2], add_notify_addrs=['chicken@farm.test'])],
        17: [tracker_pb2.FilterRule(
            predicate=rows[3][2], add_cc_ids=[111, 222])],
    }
    self.assertItemsEqual(rules_dict, expected_dict)

    self.features_service.filterrule_tbl.Select.assert_called_once_with(
        self.cnxn, features_svc.FILTERRULE_COLS)

    calls = [mock.call(self.cnxn, project_id=project_id, rank=rank,
                       predicate=predicate, consequence=consequence,
                       commit=False)
             for (project_id, rank, predicate, consequence) in rows_to_delete]
    self.features_service.filterrule_tbl.Delete.assert_has_calls(
        calls, any_order=True)

  def testExpungeFilterRulesByUser_EmptyUsers(self):
    self.features_service.filterrule_tbl.Select = mock.Mock()
    self.features_service.filterrule_tbl.Delete = mock.Mock()

    rules_dict = self.features_service.ExpungeFilterRulesByUser(self.cnxn, {})
    self.assertEqual(rules_dict, {})
    self.features_service.filterrule_tbl.Select.assert_not_called()
    self.features_service.filterrule_tbl.Delete.assert_not_called()

  def testExpungeFilterRulesByUser_NoMatch(self):
    rows = [
        (17, 48, 'owner:farmer@farm.test', 'add_cc_id:111 add_cc_id: 222'),
        (19, 9, 'label:no-match-in-project', 'add_label:no-DELETE-INSERTROW'),
        ]
    self.features_service.filterrule_tbl.Select = mock.Mock(return_value=rows)
    self.features_service.filterrule_tbl.Delete = mock.Mock()

    emails = {'cow@fart.test': 222}
    rules_dict = self.features_service.ExpungeFilterRulesByUser(
        self.cnxn, emails)
    self.assertItemsEqual(rules_dict, {})

    self.features_service.filterrule_tbl.Select.assert_called_once_with(
        self.cnxn, features_svc.FILTERRULE_COLS)
    self.features_service.filterrule_tbl.Delete.assert_not_called()

  ### Hotlists

  def SetUpCreateHotlist(self):
    # Check for the existing hotlist: there should be none.
    # Two hotlists named 'hot1' exist but neither are owned by the user.
    self.features_service.hotlist2user_tbl.Select(
        self.cnxn, cols=['hotlist_id', 'user_id'],
        user_id=[567], role_name='owner').AndReturn([])

    self.features_service.hotlist_tbl.Select(
        self.cnxn, cols=['id', 'name'], id=[], is_deleted=False,
        where =[(('LOWER(name) IN (%s)'), ['hot1'])]).AndReturn([])

    # Inserting the hotlist returns the id.
    self.features_service.hotlist_tbl.InsertRow(
        self.cnxn, name='hot1', summary='hot 1', description='test hotlist',
        is_private=False,
        default_col_spec=features_constants.DEFAULT_COL_SPEC).AndReturn(123)

    # Insert the issues: there are none.
    self.features_service.hotlist2issue_tbl.InsertRows(
        self.cnxn, features_svc.HOTLIST2ISSUE_COLS,
        [], commit=False)

    # Insert the users: there is one owner and one editor.
    self.features_service.hotlist2user_tbl.InsertRows(
        self.cnxn, ['hotlist_id', 'user_id', 'role_name'],
        [(123, 567, 'owner'), (123, 678, 'editor')])

  def testCreateHotlist(self):
    self.SetUpCreateHotlist()
    self.mox.ReplayAll()
    self.features_service.CreateHotlist(
        self.cnxn, 'hot1', 'hot 1', 'test hotlist', [567], [678])
    self.mox.VerifyAll()

  def testCreateHotlist_InvalidName(self):
    with self.assertRaises(exceptions.InputException):
      self.features_service.CreateHotlist(
          self.cnxn, '***Invalid name***', 'Misnamed Hotlist',
          'A Hotlist with an invalid name', [567], [678])

  def testCreateHotlist_NoOwner(self):
    with self.assertRaises(features_svc.UnownedHotlistException):
      self.features_service.CreateHotlist(
          self.cnxn, 'unowned-hotlist', 'Unowned Hotlist',
          'A Hotlist that is not owned', [], [])

  def testCreateHotlist_HotlistAlreadyExists(self):
    self.features_service.hotlist_id_2lc.CacheItem(('fake-hotlist', 567), 123)
    with self.assertRaises(features_svc.HotlistAlreadyExists):
      self.features_service.CreateHotlist(
          self.cnxn, 'Fake-Hotlist', 'Misnamed Hotlist',
          'This name is already in use', [567], [678])

  def testTransferHotlistOwnership(self):
    hotlist_id = 123
    new_owner_id = 222
    hotlist = fake.Hotlist(hotlist_name='unique', hotlist_id=hotlist_id,
                           owner_ids=[111], editor_ids=[222, 333],
                           follower_ids=[444])
    # LookupHotlistIDs, proposed new owner, owns no hotlist with the same name.
    self.features_service.hotlist2user_tbl.Select = mock.Mock(
        return_value=[(223, new_owner_id), (567, new_owner_id)])
    self.features_service.hotlist_tbl.Select = mock.Mock(return_value=[])

    # UpdateHotlistRoles
    self.features_service.GetHotlist = mock.Mock(return_value=hotlist)
    self.features_service.hotlist2user_tbl.Delete = mock.Mock()
    self.features_service.hotlist2user_tbl.InsertRows = mock.Mock()

    self.features_service.TransferHotlistOwnership(
        self.cnxn, hotlist, new_owner_id, True)

    self.features_service.hotlist2user_tbl.Delete.assert_called_once_with(
        self.cnxn, hotlist_id=hotlist_id, commit=False)

    self.features_service.GetHotlist.assert_called_once_with(
        self.cnxn, hotlist_id, use_cache=False)
    insert_rows = [(hotlist_id, new_owner_id, 'owner'),
                   (hotlist_id, 333, 'editor'),
                   (hotlist_id, 111, 'editor'),
                   (hotlist_id, 444, 'follower')]
    self.features_service.hotlist2user_tbl.InsertRows.assert_called_once_with(
        self.cnxn, features_svc.HOTLIST2USER_COLS, insert_rows, commit=False)

  def testLookupHotlistIDs(self):
    # Set up DB query mocks.
    self.features_service.hotlist2user_tbl.Select = mock.Mock(return_value=[
        (123, 222), (125, 333)])
    self.features_service.hotlist_tbl.Select = mock.Mock(
        return_value=[(123, 'q3-TODO'), (125, 'q4-TODO')])

    self.features_service.hotlist_id_2lc.CacheItem(
        ('q4-todo', 333), 124)

    ret = self.features_service.LookupHotlistIDs(
        self.cnxn, ['q3-todo', 'Q4-TODO'], [222, 333, 444])
    self.assertEqual(ret, {('q3-todo', 222) : 123, ('q4-todo', 333): 124})
    self.features_service.hotlist2user_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['hotlist_id', 'user_id'], user_id=[444, 333, 222],
        role_name='owner')
    self.features_service.hotlist_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['id', 'name'], id=[123, 125], is_deleted=False,
        where=[
            (('LOWER(name) IN (%s,%s)'), ['q3-todo', 'q4-todo'])])

  def SetUpLookupUserHotlists(self):
    self.features_service.hotlist2user_tbl.Select(
        self.cnxn, cols=['user_id', 'hotlist_id'],
        user_id=[111], left_joins=[('Hotlist ON hotlist_id = id', [])],
        where=[('Hotlist.is_deleted = %s', [False])]).AndReturn([(111, 123)])

  def testLookupUserHotlists(self):
    self.SetUpLookupUserHotlists()
    self.mox.ReplayAll()
    ret = self.features_service.LookupUserHotlists(
        self.cnxn, [111])
    self.assertEqual(ret, {111: [123]})
    self.mox.VerifyAll()

  def SetUpLookupIssueHotlists(self):
    self.features_service.hotlist2issue_tbl.Select(
        self.cnxn, cols=['hotlist_id', 'issue_id'],
        issue_id=[987], left_joins=[('Hotlist ON hotlist_id = id', [])],
        where=[('Hotlist.is_deleted = %s', [False])]).AndReturn([(123, 987)])

  def testLookupIssueHotlists(self):
    self.SetUpLookupIssueHotlists()
    self.mox.ReplayAll()
    ret = self.features_service.LookupIssueHotlists(
        self.cnxn, [987])
    self.assertEqual(ret, {987: [123]})
    self.mox.VerifyAll()

  def SetUpGetHotlists(
      self, hotlist_id, hotlist_rows=None, issue_rows=None, role_rows=None):
    if not hotlist_rows:
      hotlist_rows = [(hotlist_id, 'hotlist2', 'test hotlist 2',
                       'test hotlist', False, '')]
    if not issue_rows:
      issue_rows=[]
    if not role_rows:
      role_rows=[]
    self.features_service.hotlist_tbl.Select(
        self.cnxn, cols=features_svc.HOTLIST_COLS,
        id=[hotlist_id], is_deleted=False).AndReturn(hotlist_rows)
    self.features_service.hotlist2user_tbl.Select(
        self.cnxn, cols=['hotlist_id', 'user_id', 'role_name'],
        hotlist_id=[hotlist_id]).AndReturn(role_rows)
    self.features_service.hotlist2issue_tbl.Select(
        self.cnxn, cols=features_svc.HOTLIST2ISSUE_COLS,
        hotlist_id=[hotlist_id],
        order_by=[('rank DESC', []), ('issue_id', [])]).AndReturn(issue_rows)

  def SetUpUpdateHotlist(self, hotlist_id):
    hotlist_rows = [
        (hotlist_id, 'hotlist2', 'test hotlist 2', 'test hotlist', False, '')
    ]
    role_rows = [(hotlist_id, 111, 'owner')]

    self.features_service.hotlist_tbl.Select = mock.Mock(
        return_value=hotlist_rows)
    self.features_service.hotlist2user_tbl.Select = mock.Mock(
        return_value=role_rows)
    self.features_service.hotlist2issue_tbl.Select = mock.Mock(return_value=[])

    self.features_service.hotlist_tbl.Update = mock.Mock()
    self.features_service.hotlist2user_tbl.Delete = mock.Mock()
    self.features_service.hotlist2user_tbl.InsertRows = mock.Mock()

  def testUpdateHotlist(self):
    hotlist_id = 456
    self.SetUpUpdateHotlist(hotlist_id)

    self.features_service.UpdateHotlist(
        self.cnxn,
        hotlist_id,
        summary='A better one-line summary',
        owner_id=333,
        add_editor_ids=[444, 555])
    delta = {'summary': 'A better one-line summary'}
    self.features_service.hotlist_tbl.Update.assert_called_once_with(
        self.cnxn, delta, id=hotlist_id, commit=False)
    self.features_service.hotlist2user_tbl.Delete.assert_called_once_with(
        self.cnxn, hotlist_id=hotlist_id, role='owner', commit=False)
    add_role_rows = [
        (hotlist_id, 333, 'owner'), (hotlist_id, 444, 'editor'),
        (hotlist_id, 555, 'editor')
    ]
    self.features_service.hotlist2user_tbl.InsertRows.assert_called_once_with(
        self.cnxn, features_svc.HOTLIST2USER_COLS, add_role_rows, commit=False)

  def testUpdateHotlist_NoRoleChanges(self):
    hotlist_id = 456
    self.SetUpUpdateHotlist(hotlist_id)

    self.features_service.UpdateHotlist(self.cnxn, hotlist_id, name='chicken')
    delta = {'name': 'chicken'}
    self.features_service.hotlist_tbl.Update.assert_called_once_with(
        self.cnxn, delta, id=hotlist_id, commit=False)
    self.features_service.hotlist2user_tbl.Delete.assert_not_called()
    self.features_service.hotlist2user_tbl.InsertRows.assert_not_called()

  def testUpdateHotlist_NoOwnerChange(self):
    hotlist_id = 456
    self.SetUpUpdateHotlist(hotlist_id)

    self.features_service.UpdateHotlist(
        self.cnxn, hotlist_id, name='chicken', add_editor_ids=[
            333,
        ])
    delta = {'name': 'chicken'}
    self.features_service.hotlist_tbl.Update.assert_called_once_with(
        self.cnxn, delta, id=hotlist_id, commit=False)
    self.features_service.hotlist2user_tbl.Delete.assert_not_called()
    self.features_service.hotlist2user_tbl.InsertRows.assert_called_once_with(
        self.cnxn,
        features_svc.HOTLIST2USER_COLS, [
            (hotlist_id, 333, 'editor'),
        ],
        commit=False)

  def SetUpRemoveHotlistEditors(self):
    hotlist = fake.Hotlist(
        hotlist_name='hotlist',
        hotlist_id=456,
        owner_ids=[111],
        editor_ids=[222, 333, 444])
    self.features_service.GetHotlist = mock.Mock(return_value=hotlist)
    self.features_service.hotlist2user_tbl.Delete = mock.Mock()
    return hotlist

  def testRemoveHotlistEditors(self):
    """We can remove editors from a hotlist."""
    hotlist = self.SetUpRemoveHotlistEditors()
    remove_editor_ids = [222, 333]
    self.features_service.RemoveHotlistEditors(
        self.cnxn, hotlist.hotlist_id, remove_editor_ids=remove_editor_ids)
    self.features_service.hotlist2user_tbl.Delete.assert_called_once_with(
        self.cnxn, hotlist_id=hotlist.hotlist_id, user_id=remove_editor_ids)
    self.assertEqual(hotlist.editor_ids, [444])

  def testRemoveHotlistEditors_NoOp(self):
    """A NoOp update does not trigger and sql table calls."""
    hotlist = self.SetUpRemoveHotlistEditors()
    with self.assertRaises(exceptions.InputException):
      self.features_service.RemoveHotlistEditors(
          self.cnxn, hotlist.hotlist_id, remove_editor_ids=[])

  def SetUpUpdateHotlistItemsFields(self, hotlist_id, issue_ids):
    hotlist_rows = [(hotlist_id, 'hotlist', '', '', True, '')]
    insert_rows = [(345, 11, 112, 333, 2002, ''),
                   (345, 33, 332, 333, 2002, ''),
                   (345, 55, 552, 333, 2002, '')]
    issue_rows = [(345, 11, 1, 333, 2002, ''), (345, 33, 3, 333, 2002, ''),
             (345, 55, 3, 333, 2002, '')]
    self.SetUpGetHotlists(
        hotlist_id, hotlist_rows=hotlist_rows, issue_rows=issue_rows)
    self.features_service.hotlist2issue_tbl.Delete(
        self.cnxn, hotlist_id=hotlist_id,
        issue_id=issue_ids, commit=False)
    self.features_service.hotlist2issue_tbl.InsertRows(
        self.cnxn, cols=features_svc.HOTLIST2ISSUE_COLS,
        row_values=insert_rows, commit=True)

  def testUpdateHotlistItemsFields_Ranks(self):
    hotlist_item_fields = [
        (11, 1, 333, 2002, ''), (33, 3, 333, 2002, ''),
        (55, 3, 333, 2002, '')]
    hotlist = fake.Hotlist(hotlist_name='hotlist', hotlist_id=345,
                           hotlist_item_fields=hotlist_item_fields)
    self.features_service.hotlist_2lc.CacheItem(345, hotlist)
    relations_to_change = {11: 112, 33: 332, 55: 552}
    issue_ids = [11, 33, 55]
    self.SetUpUpdateHotlistItemsFields(345, issue_ids)
    self.mox.ReplayAll()
    self.features_service.UpdateHotlistItemsFields(
        self.cnxn, 345, new_ranks=relations_to_change)
    self.mox.VerifyAll()

  def testUpdateHotlistItemsFields_Notes(self):
    pass

  def testGetHotlists(self):
    hotlist1 = fake.Hotlist(hotlist_name='hotlist1', hotlist_id=123)
    self.features_service.hotlist_2lc.CacheItem(123, hotlist1)
    self.SetUpGetHotlists(456)
    self.mox.ReplayAll()
    hotlist_dict = self.features_service.GetHotlists(
        self.cnxn, [123, 456])
    self.mox.VerifyAll()
    self.assertItemsEqual([123, 456], list(hotlist_dict.keys()))
    self.assertEqual('hotlist1', hotlist_dict[123].name)
    self.assertEqual('hotlist2', hotlist_dict[456].name)

  def testGetHotlistsByID(self):
    hotlist1 = fake.Hotlist(hotlist_name='hotlist1', hotlist_id=123)
    self.features_service.hotlist_2lc.CacheItem(123, hotlist1)
    # NOTE: The setup function must take a hotlist_id that is different
    # from what was used in previous tests, otherwise the methods in the
    # setup function will never get called.
    self.SetUpGetHotlists(456)
    self.mox.ReplayAll()
    _, actual_missed = self.features_service.GetHotlistsByID(
        self.cnxn, [123, 456])
    self.mox.VerifyAll()
    self.assertEqual(actual_missed, [])

  def testGetHotlistsByUserID(self):
    self.SetUpLookupUserHotlists()
    self.SetUpGetHotlists(123)
    self.mox.ReplayAll()
    hotlists = self.features_service.GetHotlistsByUserID(self.cnxn, 111)
    self.assertEqual(len(hotlists), 1)
    self.assertEqual(hotlists[0].hotlist_id, 123)
    self.mox.VerifyAll()

  def testGetHotlistsByIssueID(self):
    self.SetUpLookupIssueHotlists()
    self.SetUpGetHotlists(123)
    self.mox.ReplayAll()
    hotlists = self.features_service.GetHotlistsByIssueID(self.cnxn, 987)
    self.assertEqual(len(hotlists), 1)
    self.assertEqual(hotlists[0].hotlist_id, 123)
    self.mox.VerifyAll()

  def SetUpUpdateHotlistRoles(
      self, hotlist_id, owner_ids, editor_ids, follower_ids):

    self.features_service.hotlist2user_tbl.Delete(
        self.cnxn, hotlist_id=hotlist_id, commit=False)

    insert_rows = [(hotlist_id, user_id, 'owner') for user_id in owner_ids]
    insert_rows.extend(
        [(hotlist_id, user_id, 'editor') for user_id in editor_ids])
    insert_rows.extend(
        [(hotlist_id, user_id, 'follower') for user_id in follower_ids])
    self.features_service.hotlist2user_tbl.InsertRows(
        self.cnxn, ['hotlist_id', 'user_id', 'role_name'],
        insert_rows, commit=False)

    self.cnxn.Commit()

  def testUpdateHotlistRoles(self):
    self.SetUpGetHotlists(456)
    self.SetUpUpdateHotlistRoles(456, [111, 222], [333], [])
    self.mox.ReplayAll()
    self.features_service.UpdateHotlistRoles(
        self.cnxn, 456, [111, 222], [333], [])
    self.mox.VerifyAll()

  def SetUpUpdateHotlistIssues(self, items):
    hotlist = fake.Hotlist(hotlist_name='hotlist', hotlist_id=456)
    hotlist.items = items
    self.features_service.GetHotlist = mock.Mock(return_value=hotlist)
    self.features_service.hotlist2issue_tbl.Delete = mock.Mock()
    self.features_service.hotlist2issue_tbl.InsertRows = mock.Mock()
    self.issue_service.GetIssues = mock.Mock()
    return hotlist

  def testUpdateHotlistIssues_ChangeIssues(self):
    original_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78902, rank=11, adder_id=333, date_added=2345),  # update
        features_pb2.Hotlist.HotlistItem(
            issue_id=78904, rank=0, adder_id=333, date_added=2345)  # same
    ]
    hotlist = self.SetUpUpdateHotlistIssues(original_items)
    updated_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78902, rank=13, adder_id=333, date_added=2345),  # update
        features_pb2.Hotlist.HotlistItem(
            issue_id=78903, rank=23, adder_id=333, date_added=2345)  # new
    ]

    self.features_service.UpdateHotlistIssues(
        self.cnxn, hotlist.hotlist_id, updated_items, [], self.issue_service,
        self.chart_service)

    insert_rows = [
        (hotlist.hotlist_id, 78902, 13, 333, 2345, ''),
        (hotlist.hotlist_id, 78903, 23, 333, 2345, '')
    ]
    self.features_service.hotlist2issue_tbl.InsertRows.assert_called_once_with(
        self.cnxn,
        cols=features_svc.HOTLIST2ISSUE_COLS,
        row_values=insert_rows,
        commit=False)
    self.features_service.hotlist2issue_tbl.Delete.assert_called_once_with(
        self.cnxn,
        hotlist_id=hotlist.hotlist_id,
        issue_id=[78902, 78903],
        commit=False)

    # New hotlist itmes includes updated_items and unchanged items.
    expected_all_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78904, rank=0, adder_id=333, date_added=2345),
        features_pb2.Hotlist.HotlistItem(
            issue_id=78902, rank=13, adder_id=333, date_added=2345),
        features_pb2.Hotlist.HotlistItem(
            issue_id=78903, rank=23, adder_id=333, date_added=2345)
    ]
    self.assertEqual(hotlist.items, expected_all_items)

    # Assert we're storing the new snapshots of the affected issues.
    self.issue_service.GetIssues.assert_called_once_with(
        self.cnxn, [78902, 78903])

  def testUpdateHotlistIssues_RemoveIssues(self):
    original_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78901, rank=10, adder_id=222, date_added=2348),  # remove
        features_pb2.Hotlist.HotlistItem(
            issue_id=78904, rank=0, adder_id=333, date_added=2345),  # same
    ]
    hotlist = self.SetUpUpdateHotlistIssues(original_items)
    remove_issue_ids = [78901]

    self.features_service.UpdateHotlistIssues(
        self.cnxn, hotlist.hotlist_id, [], remove_issue_ids, self.issue_service,
        self.chart_service)

    self.features_service.hotlist2issue_tbl.Delete.assert_called_once_with(
        self.cnxn,
        hotlist_id=hotlist.hotlist_id,
        issue_id=remove_issue_ids,
        commit=False)

    # New hotlist itmes includes updated_items and unchanged items.
    expected_all_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78904, rank=0, adder_id=333, date_added=2345)
    ]
    self.assertEqual(hotlist.items, expected_all_items)

    # Assert we're storing the new snapshots of the affected issues.
    self.issue_service.GetIssues.assert_called_once_with(self.cnxn, [78901])

  def testUpdateHotlistIssues_RemoveAndChange(self):
    original_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78901, rank=10, adder_id=222, date_added=2348),  # remove
        features_pb2.Hotlist.HotlistItem(
            issue_id=78902, rank=11, adder_id=333, date_added=2345),  # update
        features_pb2.Hotlist.HotlistItem(
            issue_id=78904, rank=0, adder_id=333, date_added=2345)  # same
    ]
    hotlist = self.SetUpUpdateHotlistIssues(original_items)
    # test 78902 gets added back with `updated_items`
    remove_issue_ids = [78901, 78902]
    updated_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78902, rank=13, adder_id=333, date_added=2345),
    ]

    self.features_service.UpdateHotlistIssues(
        self.cnxn, hotlist.hotlist_id, updated_items, remove_issue_ids,
        self.issue_service, self.chart_service)

    delete_calls = [
        mock.call(
            self.cnxn,
            hotlist_id=hotlist.hotlist_id,
            issue_id=remove_issue_ids,
            commit=False),
        mock.call(
            self.cnxn,
            hotlist_id=hotlist.hotlist_id,
            issue_id=[78902],
            commit=False)
    ]
    self.assertEqual(
        self.features_service.hotlist2issue_tbl.Delete.mock_calls, delete_calls)

    insert_rows = [
        (hotlist.hotlist_id, 78902, 13, 333, 2345, ''),
    ]
    self.features_service.hotlist2issue_tbl.InsertRows.assert_called_once_with(
        self.cnxn,
        cols=features_svc.HOTLIST2ISSUE_COLS,
        row_values=insert_rows,
        commit=False)

    # New hotlist itmes includes updated_items and unchanged items.
    expected_all_items = [
        features_pb2.Hotlist.HotlistItem(
            issue_id=78904, rank=0, adder_id=333, date_added=2345),
        features_pb2.Hotlist.HotlistItem(
            issue_id=78902, rank=13, adder_id=333, date_added=2345),
    ]
    self.assertEqual(hotlist.items, expected_all_items)

    # Assert we're storing the new snapshots of the affected issues.
    self.issue_service.GetIssues.assert_called_once_with(
        self.cnxn, [78901, 78902])

  def testUpdateHotlistIssues_NoChanges(self):
    with self.assertRaises(exceptions.InputException):
      self.features_service.UpdateHotlistIssues(
          self.cnxn, 456, [], None, self.issue_service, self.chart_service)

  def SetUpUpdateHotlistItems(self, cnxn, hotlist_id, remove, added_tuples):
    self.features_service.hotlist2issue_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, issue_id=remove, commit=False)
    rank = 1
    added_tuples_with_rank = [(issue_id, rank+10*mult, user_id, ts, note) for
                              mult, (issue_id, user_id, ts, note) in
                              enumerate(added_tuples)]
    insert_rows = [(hotlist_id, issue_id,
                    rank, user_id, date, note) for
                   (issue_id, rank, user_id, date, note) in
                   added_tuples_with_rank]
    self.features_service.hotlist2issue_tbl.InsertRows(
        cnxn, cols=features_svc.HOTLIST2ISSUE_COLS,
        row_values=insert_rows, commit=False)

  def testAddIssuesToHotlists(self):
    added_tuples = [
            (111, None, None, ''),
            (222, None, None, ''),
            (333, None, None, '')]
    issues = [
      tracker_pb2.Issue(issue_id=issue_id)
      for issue_id, _, _, _ in added_tuples
    ]
    self.SetUpGetHotlists(456)
    self.SetUpUpdateHotlistItems(
        self.cnxn, 456, [], added_tuples)
    self.SetUpGetHotlists(567)
    self.SetUpUpdateHotlistItems(
        self.cnxn, 567, [], added_tuples)

    self.mox.StubOutWithMock(self.issue_service, 'GetIssues')
    self.issue_service.GetIssues(self.cnxn,
        [111, 222, 333]).AndReturn(issues)
    self.chart_service.StoreIssueSnapshots(self.cnxn, issues,
        commit=False)
    self.mox.ReplayAll()
    self.features_service.AddIssuesToHotlists(
        self.cnxn, [456, 567], added_tuples, self.issue_service,
        self.chart_service, commit=False)
    self.mox.VerifyAll()

  def testRemoveIssuesFromHotlists(self):
    issue_rows = [
      (456, 555, 1, None, None, ''),
      (456, 666, 11, None, None, ''),
    ]
    issues = [tracker_pb2.Issue(issue_id=issue_rows[0][1])]
    self.SetUpGetHotlists(456, issue_rows=issue_rows)
    self.SetUpUpdateHotlistItems(
        self. cnxn, 456, [555], [])
    issue_rows = [
      (789, 555, 1, None, None, ''),
      (789, 666, 11, None, None, ''),
    ]
    self.SetUpGetHotlists(789, issue_rows=issue_rows)
    self.SetUpUpdateHotlistItems(
        self. cnxn, 789, [555], [])
    self.mox.StubOutWithMock(self.issue_service, 'GetIssues')
    self.issue_service.GetIssues(self.cnxn,
        [555]).AndReturn(issues)
    self.chart_service.StoreIssueSnapshots(self.cnxn, issues, commit=False)
    self.mox.ReplayAll()
    self.features_service.RemoveIssuesFromHotlists(
        self.cnxn, [456, 789], [555], self.issue_service, self.chart_service,
        commit=False)
    self.mox.VerifyAll()

  def testUpdateHotlistItems(self):
    self.SetUpGetHotlists(456)
    self.SetUpUpdateHotlistItems(
        self. cnxn, 456, [], [
            (111, None, None, ''),
            (222, None, None, ''),
            (333, None, None, '')])
    self.mox.ReplayAll()
    self.features_service.UpdateHotlistItems(
        self.cnxn, 456, [],
        [(111, None, None, ''),
         (222, None, None, ''),
         (333, None, None, '')], commit=False)
    self.mox.VerifyAll()

  def SetUpDeleteHotlist(self, cnxn, hotlist_id):
    hotlist_rows = [(hotlist_id, 'hotlist', 'test hotlist',
        'test list', False, '')]
    self.SetUpGetHotlists(678, hotlist_rows=hotlist_rows,
        role_rows=[(hotlist_id, 111, 'owner', )])
    self.features_service.hotlist2issue_tbl.Select(self.cnxn,
        cols=['Issue.project_id'], hotlist_id=hotlist_id, distinct=True,
        left_joins=[('Issue ON issue_id = id', [])]).AndReturn([(1,)])
    self.features_service.hotlist_tbl.Update(cnxn, {'is_deleted': True},
        commit=False, id=hotlist_id)

  def testDeleteHotlist(self):
    self.SetUpDeleteHotlist(self.cnxn, 678)
    self.mox.ReplayAll()
    self.features_service.DeleteHotlist(self.cnxn, 678, commit=False)
    self.mox.VerifyAll()

  def testExpungeHotlists(self):
    hotliststar_tbl = mock.Mock()
    star_service = star_svc.AbstractStarService(
        self.cache_manager, hotliststar_tbl, 'hotlist_id', 'user_id', 'hotlist')
    hotliststar_tbl.Delete = mock.Mock()
    user_service = user_svc.UserService(self.cache_manager)
    user_service.hotlistvisithistory_tbl.Delete = mock.Mock()
    chart_service = chart_svc.ChartService(self.config_service)
    self.cnxn.Execute = mock.Mock()

    hotlist1 = fake.Hotlist(hotlist_name='unique', hotlist_id=678,
                            owner_ids=[111], editor_ids=[222, 333])
    hotlist2 = fake.Hotlist(hotlist_name='unique2', hotlist_id=679,
                            owner_ids=[111])
    hotlists_by_id = {hotlist1.hotlist_id: hotlist1,
                      hotlist2.hotlist_id: hotlist2}
    self.features_service.GetHotlists = mock.Mock(return_value=hotlists_by_id)
    self.features_service.hotlist2user_tbl.Delete = mock.Mock()
    self.features_service.hotlist2issue_tbl.Delete = mock.Mock()
    self.features_service.hotlist_tbl.Delete = mock.Mock()
    # cache invalidation mocks
    self.features_service.hotlist_2lc.InvalidateKeys = mock.Mock()
    self.features_service.hotlist_id_2lc.InvalidateKeys = mock.Mock()
    self.features_service.hotlist_user_to_ids.InvalidateKeys = mock.Mock()
    self.config_service.InvalidateMemcacheForEntireProject = mock.Mock()

    hotlists_project_id = 787
    self.features_service.GetProjectIDsFromHotlist = mock.Mock(
        return_value=[hotlists_project_id])

    hotlist_ids = hotlists_by_id.keys()
    commit = True  # commit in ExpungeHotlists should be True by default.
    self.features_service.ExpungeHotlists(
        self.cnxn, hotlist_ids, star_service, user_service, chart_service)

    star_calls = [
        mock.call(
            self.cnxn, commit=commit, limit=None, hotlist_id=hotlist_ids[0]),
        mock.call(
            self.cnxn, commit=commit, limit=None, hotlist_id=hotlist_ids[1])]
    hotliststar_tbl.Delete.assert_has_calls(star_calls)

    self.cnxn.Execute.assert_called_once_with(
        'DELETE FROM IssueSnapshot2Hotlist WHERE hotlist_id IN (%s,%s)',
        [678, 679], commit=commit)
    user_service.hotlistvisithistory_tbl.Delete.assert_called_once_with(
        self.cnxn, commit=commit, hotlist_id=hotlist_ids)

    self.features_service.hotlist2user_tbl.Delete.assert_called_once_with(
        self.cnxn, hotlist_id=hotlist_ids, commit=commit)
    self.features_service.hotlist2issue_tbl.Delete.assert_called_once_with(
        self.cnxn, hotlist_id=hotlist_ids, commit=commit)
    self.features_service.hotlist_tbl.Delete.assert_called_once_with(
        self.cnxn, id=hotlist_ids, commit=commit)
    # cache invalidation checks
    self.features_service.hotlist_2lc.InvalidateKeys.assert_called_once_with(
        self.cnxn, hotlist_ids)
    invalidate_owner_calls = [
        mock.call(self.cnxn, [(hotlist1.name, hotlist1.owner_ids[0])]),
        mock.call(self.cnxn, [(hotlist2.name, hotlist2.owner_ids[0])])]
    self.features_service.hotlist_id_2lc.InvalidateKeys.assert_has_calls(
      invalidate_owner_calls)
    self.features_service.hotlist_user_to_ids.InvalidateKeys.\
assert_called_once_with(
        self.cnxn, [333, 222, 111])
    self.config_service.InvalidateMemcacheForEntireProject.\
assert_called_once_with(hotlists_project_id)

  def testExpungeUsersInHotlists(self):
    hotliststar_tbl = mock.Mock()
    star_service = star_svc.AbstractStarService(
        self.cache_manager, hotliststar_tbl, 'hotlist_id', 'user_id', 'hotlist')
    user_service = user_svc.UserService(self.cache_manager)
    chart_service = chart_svc.ChartService(self.config_service)
    user_ids = [111, 222]

    # hotlist1 will get transferred to 333
    hotlist1 = fake.Hotlist(hotlist_name='unique', hotlist_id=123,
                            owner_ids=[111], editor_ids=[222, 333])
    # hotlist2 will get deleted
    hotlist2 = fake.Hotlist(hotlist_name='name', hotlist_id=223,
                            owner_ids=[222], editor_ids=[111, 333])
    delete_hotlists = [hotlist2.hotlist_id]
    delete_hotlist_project_id = 788
    self.features_service.GetProjectIDsFromHotlist = mock.Mock(
        return_value=[delete_hotlist_project_id])
    self.config_service.InvalidateMemcacheForEntireProject = mock.Mock()
    hotlists_by_user_id = {
        111: [hotlist1.hotlist_id, hotlist2.hotlist_id],
        222: [hotlist1.hotlist_id, hotlist2.hotlist_id],
        333: [hotlist1.hotlist_id, hotlist2.hotlist_id]}
    self.features_service.LookupUserHotlists = mock.Mock(
        return_value=hotlists_by_user_id)
    hotlists_by_id = {hotlist1.hotlist_id: hotlist1,
                      hotlist2.hotlist_id: hotlist2}
    self.features_service.GetHotlistsByID = mock.Mock(
        return_value=(hotlists_by_id, []))

    # User 333 already has a hotlist named 'name'.
    def side_effect(_cnxn, hotlist_names, owner_ids):
      if 333 in owner_ids and 'name' in hotlist_names:
        return {('name', 333): 567}
      return {}
    self.features_service.LookupHotlistIDs = mock.Mock(
        side_effect=side_effect)
    # Called to transfer hotlist ownership
    self.features_service.UpdateHotlistRoles = mock.Mock()

    # Called to expunge users and hotlists
    self.features_service.hotlist2user_tbl.Delete = mock.Mock()
    self.features_service.hotlist2issue_tbl.Update = mock.Mock()
    user_service.hotlistvisithistory_tbl.Delete = mock.Mock()

    # Called to expunge hotlists
    hotlists_by_id = {hotlist1.hotlist_id: hotlist1,
                      hotlist2.hotlist_id: hotlist2}
    self.features_service.GetHotlists = mock.Mock(
        return_value=hotlists_by_id)
    self.features_service.hotlist2issue_tbl.Delete = mock.Mock()
    self.features_service.hotlist_tbl.Delete = mock.Mock()
    hotliststar_tbl.Delete = mock.Mock()

    self.features_service.ExpungeUsersInHotlists(
        self.cnxn, user_ids, star_service, user_service, chart_service)

    self.features_service.UpdateHotlistRoles.assert_called_once_with(
        self.cnxn, hotlist1.hotlist_id, [333], [222], [], commit=False)

    self.features_service.hotlist2user_tbl.Delete.assert_has_calls(
        [mock.call(self.cnxn, user_id=user_ids, commit=False),
         mock.call(self.cnxn, hotlist_id=delete_hotlists, commit=False)])
    self.features_service.hotlist2issue_tbl.Update.assert_called_once_with(
        self.cnxn, {'adder_id': framework_constants.DELETED_USER_ID},
        adder_id=user_ids, commit=False)
    user_service.hotlistvisithistory_tbl.Delete.assert_has_calls(
        [mock.call(self.cnxn, user_id=user_ids, commit=False),
         mock.call(self.cnxn, hotlist_id=delete_hotlists, commit=False)])

    self.features_service.hotlist2issue_tbl.Delete.assert_called_once_with(
        self.cnxn, hotlist_id=delete_hotlists, commit=False)
    hotliststar_tbl.Delete.assert_called_once_with(
        self.cnxn, commit=False, limit=None, hotlist_id=delete_hotlists[0])
    self.features_service.hotlist_tbl.Delete.assert_called_once_with(
        self.cnxn, id=delete_hotlists, commit=False)


  def testGetProjectIDsFromHotlist(self):
    self.features_service.hotlist2issue_tbl.Select(self.cnxn,
        cols=['Issue.project_id'], hotlist_id=678, distinct=True,
        left_joins=[('Issue ON issue_id = id', [])]).AndReturn(
            [(789,), (787,), (788,)])

    self.mox.ReplayAll()
    project_ids = self.features_service.GetProjectIDsFromHotlist(self.cnxn, 678)
    self.mox.VerifyAll()
    self.assertEqual([789, 787, 788], project_ids)
