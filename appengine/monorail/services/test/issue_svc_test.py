# -*- coding: utf-8 -*-
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issue_svc module."""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import logging
import time
import unittest
from mock import patch, Mock, ANY

import mox

from google.appengine.api import search
from google.appengine.ext import testbed

import settings
from framework import exceptions
from framework import framework_constants
from framework import sql
from proto import tracker_pb2
from services import caches
from services import chart_svc
from services import issue_svc
from services import service_manager
from services import spam_svc
from services import tracker_fulltext
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj


class MockIndex(object):

  def delete(self, string_list):
    pass


def MakeIssueService(project_service, config_service, cache_manager,
    chart_service, my_mox):
  issue_service = issue_svc.IssueService(
      project_service, config_service, cache_manager, chart_service)
  for table_var in [
      'issue_tbl', 'issuesummary_tbl', 'issue2label_tbl',
      'issue2component_tbl', 'issue2cc_tbl', 'issue2notify_tbl',
      'issue2fieldvalue_tbl', 'issuerelation_tbl', 'danglingrelation_tbl',
      'issueformerlocations_tbl', 'comment_tbl', 'commentcontent_tbl',
      'issueupdate_tbl', 'attachment_tbl', 'reindexqueue_tbl',
      'localidcounter_tbl', 'issuephasedef_tbl', 'issue2approvalvalue_tbl',
      'issueapproval2approver_tbl', 'issueapproval2comment_tbl',
      'commentimporter_tbl']:
    setattr(issue_service, table_var, my_mox.CreateMock(sql.SQLTableManager))

  return issue_service


class TestableIssueTwoLevelCache(issue_svc.IssueTwoLevelCache):

  def __init__(self, issue_list):
    cache_manager = fake.CacheManager()
    super(TestableIssueTwoLevelCache, self).__init__(
        cache_manager, None, None, None)
    self.cache = caches.RamCache(cache_manager, 'issue')
    self.memcache_prefix = 'issue:'
    self.pb_class = tracker_pb2.Issue

    self.issue_dict = {
      issue.issue_id: issue
      for issue in issue_list}

  def FetchItems(self, cnxn, issue_ids, shard_id=None):
    return {
      issue_id: self.issue_dict[issue_id]
      for issue_id in issue_ids
      if issue_id in self.issue_dict}


class IssueIDTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.project_service = fake.ProjectService()
    self.config_service = fake.ConfigService()
    self.cache_manager = fake.CacheManager()
    self.chart_service = chart_svc.ChartService(self.config_service)
    self.issue_service = MakeIssueService(
        self.project_service, self.config_service, self.cache_manager,
        self.chart_service, self.mox)
    self.issue_id_2lc = self.issue_service.issue_id_2lc
    self.spam_service = fake.SpamService()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testDeserializeIssueIDs_Empty(self):
    issue_id_dict = self.issue_id_2lc._DeserializeIssueIDs([])
    self.assertEqual({}, issue_id_dict)

  def testDeserializeIssueIDs_Normal(self):
    rows = [(789, 1, 78901), (789, 2, 78902), (789, 3, 78903)]
    issue_id_dict = self.issue_id_2lc._DeserializeIssueIDs(rows)
    expected = {
        (789, 1): 78901,
        (789, 2): 78902,
        (789, 3): 78903,
        }
    self.assertEqual(expected, issue_id_dict)

  def SetUpFetchItems(self):
    where = [
        ('(Issue.project_id = %s AND Issue.local_id IN (%s,%s,%s))',
         [789, 1, 2, 3])]
    rows = [(789, 1, 78901), (789, 2, 78902), (789, 3, 78903)]
    self.issue_service.issue_tbl.Select(
        self.cnxn, cols=['project_id', 'local_id', 'id'],
        where=where, or_where_conds=True).AndReturn(rows)

  def testFetchItems(self):
    project_local_ids_list = [(789, 1), (789, 2), (789, 3)]
    issue_ids = [78901, 78902, 78903]
    self.SetUpFetchItems()
    self.mox.ReplayAll()
    issue_dict = self.issue_id_2lc.FetchItems(
        self.cnxn, project_local_ids_list)
    self.mox.VerifyAll()
    self.assertItemsEqual(project_local_ids_list, list(issue_dict.keys()))
    self.assertItemsEqual(issue_ids, list(issue_dict.values()))

  def testKeyToStr(self):
    self.assertEqual('789,1', self.issue_id_2lc._KeyToStr((789, 1)))

  def testStrToKey(self):
    self.assertEqual((789, 1), self.issue_id_2lc._StrToKey('789,1'))


class IssueTwoLevelCacheTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.cnxn = 'fake connection'
    self.project_service = fake.ProjectService()
    self.config_service = fake.ConfigService()
    self.cache_manager = fake.CacheManager()
    self.chart_service = chart_svc.ChartService(self.config_service)
    self.issue_service = MakeIssueService(
        self.project_service, self.config_service, self.cache_manager,
        self.chart_service, self.mox)
    self.issue_2lc = self.issue_service.issue_2lc

    now = int(time.time())
    self.project_service.TestAddProject('proj', project_id=789)
    self.issue_rows = [
        (78901, 789, 1, 1, 111, 222,
         now, now, now, now, now, now,
         0, 0, 0, 1, 0, False)]
    self.summary_rows = [(78901, 'sum')]
    self.label_rows = [(78901, 1, 0)]
    self.component_rows = []
    self.cc_rows = [(78901, 333, 0)]
    self.notify_rows = []
    self.fieldvalue_rows = []
    self.blocked_on_rows = (
        (78901, 78902, 'blockedon', 20), (78903, 78901, 'blockedon', 10))
    self.blocking_rows = ()
    self.merged_rows = ()
    self.relation_rows = (
        self.blocked_on_rows + self.blocking_rows + self.merged_rows)
    self.dangling_relation_rows = [
        (78901, 'codesite', 5001, None, 'blocking'),
        (78901, 'codesite', 5002, None, 'blockedon'),
        (78901, None, None, 'b/1234567', 'blockedon')]
    self.phase_rows = [(1, 'Canary', 1), (2, 'Stable', 11)]
    self.approvalvalue_rows = [(22, 78901, 2, 'not_set', None, None),
                               (21, 78901, 1, 'needs_review', None, None),
                               (23, 78901, 1, 'not_set', None, None)]
    self.av_approver_rows = [
        (21, 111, 78901), (21, 222, 78901), (21, 333, 78901)]

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testUnpackApprovalValue(self):
    row = next(
        row for row in self.approvalvalue_rows if row[3] == 'needs_review')
    av, issue_id = self.issue_2lc._UnpackApprovalValue(row)
    self.assertEqual(av.status, tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    self.assertIsNone(av.setter_id)
    self.assertIsNone(av.set_on)
    self.assertEqual(issue_id, 78901)
    self.assertEqual(av.phase_id, 1)

  def testUnpackApprovalValue_MissingStatus(self):
    av, _issue_id = self.issue_2lc._UnpackApprovalValue(
        (21, 78901, 1, '', None, None))
    self.assertEqual(av.status, tracker_pb2.ApprovalStatus.NOT_SET)

  def testUnpackPhase(self):
    phase = self.issue_2lc._UnpackPhase(
        self.phase_rows[0])
    self.assertEqual(phase.name, 'Canary')
    self.assertEqual(phase.phase_id, 1)
    self.assertEqual(phase.rank, 1)

  def testDeserializeIssues_Empty(self):
    issue_dict = self.issue_2lc._DeserializeIssues(
        self.cnxn, [], [], [], [], [], [], [], [], [], [], [], [])
    self.assertEqual({}, issue_dict)

  def testDeserializeIssues_Normal(self):
    issue_dict = self.issue_2lc._DeserializeIssues(
        self.cnxn, self.issue_rows, self.summary_rows, self.label_rows,
        self.component_rows, self.cc_rows, self.notify_rows,
        self.fieldvalue_rows, self.relation_rows, self.dangling_relation_rows,
        self.phase_rows, self.approvalvalue_rows, self.av_approver_rows)
    self.assertItemsEqual([78901], list(issue_dict.keys()))
    issue = issue_dict[78901]
    self.assertEqual(len(issue.phases), 2)
    self.assertIsNotNone(tracker_bizobj.FindPhaseByID(1, issue.phases))
    av_21 = tracker_bizobj.FindApprovalValueByID(
        21, issue.approval_values)
    self.assertEqual(av_21.phase_id, 1)
    self.assertItemsEqual(av_21.approver_ids, [111, 222, 333])
    self.assertIsNotNone(tracker_bizobj.FindPhaseByID(2, issue.phases))
    self.assertEqual(issue.phases,
                     [tracker_pb2.Phase(rank=1, phase_id=1, name='Canary'),
                      tracker_pb2.Phase(rank=11, phase_id=2, name='Stable')])
    av_22 = tracker_bizobj.FindApprovalValueByID(
        22, issue.approval_values)
    self.assertEqual(av_22.phase_id, 2)
    self.assertEqual([
        tracker_pb2.DanglingIssueRef(
          project=row[1],
          issue_id=row[2],
          ext_issue_identifier=row[3])
          for row in self.dangling_relation_rows
          if row[4] == 'blockedon'
        ], issue.dangling_blocked_on_refs)
    self.assertEqual([
        tracker_pb2.DanglingIssueRef(
          project=row[1],
          issue_id=row[2],
          ext_issue_identifier=row[3])
          for row in self.dangling_relation_rows
          if row[4] == 'blocking'
        ], issue.dangling_blocking_refs)

  def testDeserializeIssues_UnexpectedLabel(self):
    unexpected_label_rows = [
      (78901, 999, 0)
      ]
    self.assertRaises(
      AssertionError,
      self.issue_2lc._DeserializeIssues,
      self.cnxn, self.issue_rows, self.summary_rows, unexpected_label_rows,
      self.component_rows, self.cc_rows, self.notify_rows,
      self.fieldvalue_rows, self.relation_rows, self.dangling_relation_rows,
      self.phase_rows, self.approvalvalue_rows, self.av_approver_rows)

  def testDeserializeIssues_UnexpectedIssueRelation(self):
    unexpected_relation_rows = [
      (78990, 78999, 'blockedon', None)
      ]
    self.assertRaises(
      AssertionError,
      self.issue_2lc._DeserializeIssues,
      self.cnxn, self.issue_rows, self.summary_rows, self.label_rows,
      self.component_rows, self.cc_rows, self.notify_rows,
      self.fieldvalue_rows, unexpected_relation_rows,
      self.dangling_relation_rows, self.phase_rows, self.approvalvalue_rows,
      self.av_approver_rows)

  def testDeserializeIssues_ExternalMergedInto(self):
    """_DeserializeIssues handles external mergedinto refs correctly."""
    dangling_relation_rows = self.dangling_relation_rows + [
        (78901, None, None, 'b/1234567', 'mergedinto')]
    issue_dict = self.issue_2lc._DeserializeIssues(
        self.cnxn, self.issue_rows, self.summary_rows, self.label_rows,
        self.component_rows, self.cc_rows, self.notify_rows,
        self.fieldvalue_rows, self.relation_rows, dangling_relation_rows,
        self.phase_rows, self.approvalvalue_rows, self.av_approver_rows)
    self.assertEqual('b/1234567', issue_dict[78901].merged_into_external)

  def SetUpFetchItems(self, issue_ids):
    shard_id = None
    self.issue_service.issue_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE_COLS, id=issue_ids,
        shard_id=shard_id).AndReturn(self.issue_rows)
    self.issue_service.issuesummary_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUESUMMARY_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.summary_rows)
    self.issue_service.issue2label_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2LABEL_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.label_rows)
    self.issue_service.issue2component_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2COMPONENT_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.component_rows)
    self.issue_service.issue2cc_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2CC_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.cc_rows)
    self.issue_service.issue2notify_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2NOTIFY_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.notify_rows)
    self.issue_service.issue2fieldvalue_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2FIELDVALUE_COLS, shard_id=shard_id,
        issue_id=issue_ids).AndReturn(self.fieldvalue_rows)
    self.issue_service.issuephasedef_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEPHASEDEF_COLS,
        id=[1, 2]).AndReturn(self.phase_rows)
    self.issue_service.issue2approvalvalue_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUE2APPROVALVALUE_COLS,
        issue_id=issue_ids).AndReturn(self.approvalvalue_rows)
    self.issue_service.issueapproval2approver_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2APPROVER_COLS,
        issue_id=issue_ids).AndReturn(self.av_approver_rows)
    self.issue_service.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        issue_id=issue_ids, kind='blockedon',
        order_by=[('issue_id', []), ('rank DESC', []),
                  ('dst_issue_id', [])]).AndReturn(self.blocked_on_rows)
    self.issue_service.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        dst_issue_id=issue_ids, kind='blockedon',
        order_by=[('issue_id', []), ('dst_issue_id', [])]
        ).AndReturn(self.blocking_rows)
    self.issue_service.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        where=[('(issue_id IN (%s) OR dst_issue_id IN (%s))',
                issue_ids + issue_ids),
                ('kind != %s', ['blockedon'])]).AndReturn(self.merged_rows)
    self.issue_service.danglingrelation_tbl.Select(
        self.cnxn, cols=issue_svc.DANGLINGRELATION_COLS,  # Note: no shard
        issue_id=issue_ids).AndReturn(self.dangling_relation_rows)

  def testFetchItems(self):
    issue_ids = [78901]
    self.SetUpFetchItems(issue_ids)
    self.mox.ReplayAll()
    issue_dict = self.issue_2lc.FetchItems(self.cnxn, issue_ids)
    self.mox.VerifyAll()
    self.assertItemsEqual(issue_ids, list(issue_dict.keys()))


class IssueServiceTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    self.mox = mox.Mox()
    self.cnxn = self.mox.CreateMock(sql.MonorailConnection)
    self.services = service_manager.Services()
    self.services.user = fake.UserService()
    self.reporter = self.services.user.TestAddUser('reporter@example.com', 111)
    self.services.usergroup = fake.UserGroupService()
    self.services.project = fake.ProjectService()
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.services.config = fake.ConfigService()
    self.services.features = fake.FeaturesService()
    self.cache_manager = fake.CacheManager()
    self.services.chart = chart_svc.ChartService(self.services.config)
    self.services.issue = MakeIssueService(
        self.services.project, self.services.config, self.cache_manager,
        self.services.chart, self.mox)
    self.services.spam = self.mox.CreateMock(spam_svc.SpamService)
    self.now = int(time.time())
    self.patcher = patch('services.tracker_fulltext.IndexIssues')
    self.patcher.start()
    self.mox.StubOutWithMock(self.services.chart, 'StoreIssueSnapshots')

  def classifierResult(self, score, failed_open=False):
    return {'confidence_is_spam': score,
            'failed_open': failed_open}

  def tearDown(self):
    self.testbed.deactivate()
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    self.patcher.stop()

  ### Issue ID lookups

  def testLookupIssueIDs_Hit(self):
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.issue_id_2lc.CacheItem((789, 2), 78902)
    actual, _misses = self.services.issue.LookupIssueIDs(
        self.cnxn, [(789, 1), (789, 2)])
    self.assertEqual([78901, 78902], actual)

  def testLookupIssueID(self):
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    actual = self.services.issue.LookupIssueID(self.cnxn, 789, 1)
    self.assertEqual(78901, actual)

  def testResolveIssueRefs(self):
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.issue_id_2lc.CacheItem((789, 2), 78902)
    prefetched_projects = {'proj': fake.Project('proj', project_id=789)}
    refs = [('proj', 1), (None, 2)]
    actual, misses = self.services.issue.ResolveIssueRefs(
        self.cnxn, prefetched_projects, 'proj', refs)
    self.assertEqual(misses, [])
    self.assertEqual([78901, 78902], actual)

  def testLookupIssueRefs_Empty(self):
    actual = self.services.issue.LookupIssueRefs(self.cnxn, [])
    self.assertEqual({}, actual)

  def testLookupIssueRefs_Normal(self):
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)
    actual = self.services.issue.LookupIssueRefs(self.cnxn, [78901])
    self.assertEqual(
        {78901: ('proj', 1)},
        actual)

  ### Issue objects

  def CheckCreateIssue(self, is_project_member):
    settings.classifier_spam_thresh = 0.9
    av_23 = tracker_pb2.ApprovalValue(
        approval_id=23, phase_id=1, approver_ids=[111, 222],
        status=tracker_pb2.ApprovalStatus.NEEDS_REVIEW)
    av_24 = tracker_pb2.ApprovalValue(
        approval_id=24, phase_id=1, approver_ids=[111])
    approval_values = [av_23, av_24]
    av_rows = [(23, 78901, 1, 'needs_review', None, None),
               (24, 78901, 1, 'not_set', None, None)]
    approver_rows = [(23, 111, 78901), (23, 222, 78901), (24, 111, 78901)]
    ad_23 = tracker_pb2.ApprovalDef(
        approval_id=23, approver_ids=[111], survey='Question?')
    ad_24 = tracker_pb2.ApprovalDef(
        approval_id=24, approver_ids=[111], survey='Question?')
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    config.approval_defs.extend([ad_23, ad_24])
    self.services.config.StoreConfig(self.cnxn, config)

    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertIssue(av_rows=av_rows, approver_rows=approver_rows)
    self.SetUpInsertComment(7890101, is_description=True)
    self.SetUpInsertComment(7890101, is_description=True, approval_id=23,
        content='<b>Question?</b>')
    self.SetUpInsertComment(7890101, is_description=True, approval_id=24,
        content='<b>Question?</b>')
    self.services.spam.ClassifyIssue(mox.IgnoreArg(),
        mox.IgnoreArg(), self.reporter, is_project_member).AndReturn(
        self.classifierResult(0.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), False, 1.0, False)
    self.SetUpUpdateIssuesModified(set())
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111, [], ['Type-Defect'], [], [], 111, 'content',
        index_now=False, timestamp=self.now, approval_values=approval_values)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def testCreateIssue_NonmemberSpamCheck(self):
    """A non-member must pass a non-member spam check."""
    self.CheckCreateIssue(False)

  def testCreateIssue_DirectMemberSpamCheck(self):
    """A direct member of a project gets a member spam check."""
    self.project.committer_ids.append(self.reporter.user_id)
    self.CheckCreateIssue(True)

  def testCreateIssue_ComputedUsergroupSpamCheck(self):
    """A member of a computed group in project gets a member spam check."""
    group_id = self.services.usergroup.CreateGroup(
        self.cnxn, self.services, 'everyone@example.com', 'ANYONE',
        ext_group_type='COMPUTED')
    self.project.committer_ids.append(group_id)
    self.CheckCreateIssue(True)

  def testCreateIssue_EmptyStringLabels(self):
    settings.classifier_spam_thresh = 0.9
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertIssue(label_rows=[])
    self.SetUpInsertComment(7890101, is_description=True)
    self.services.spam.ClassifyIssue(mox.IgnoreArg(),
        mox.IgnoreArg(), self.reporter, False).AndReturn(
        self.classifierResult(0.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), False, 1.0, False)
    self.SetUpUpdateIssuesModified(set(), modified_timestamp=self.now)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111, [], [',', '', ' ', ', '], [], [], 111, 'content',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def SetUpUpdateIssuesModified(self, iids, modified_timestamp=None):
    self.services.issue.issue_tbl.Update(
        self.cnxn, {'modified': modified_timestamp or self.now},
        id=iids, commit=False)

  def testCreateIssue_SpamPredictionFailed(self):
    settings.classifier_spam_thresh = 0.9
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertSpamIssue()
    self.SetUpInsertComment(7890101, is_description=True)

    self.services.spam.ClassifyIssue(mox.IsA(tracker_pb2.Issue),
        mox.IsA(tracker_pb2.IssueComment), self.reporter, False).AndReturn(
        self.classifierResult(1.0, True))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), True, 1.0, True)
    self.SetUpUpdateIssuesModified(set())
    self.SetUpUpdateIssuesApprovals([])
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111, [], ['Type-Defect'], [], [], 111, 'content',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def testCreateIssue_Spam(self):
    settings.classifier_spam_thresh = 0.9
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertSpamIssue()
    self.SetUpInsertComment(7890101, is_description=True)

    self.services.spam.ClassifyIssue(mox.IsA(tracker_pb2.Issue),
        mox.IsA(tracker_pb2.IssueComment), self.reporter, False).AndReturn(
        self.classifierResult(1.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), True, 1.0, False)
    self.SetUpUpdateIssuesModified(set())
    self.SetUpUpdateIssuesApprovals([])
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    actual_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111, [], ['Type-Defect'], [], [], 111, 'content',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)

  def testCreateIssue_FederatedReferences(self):
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertIssue(dangling_relation_rows=[
        (78901, None, None, 'b/1234', 'blockedon'),
        (78901, None, None, 'b/5678', 'blockedon'),
        (78901, None, None, 'b/9876', 'blocking'),
        (78901, None, None, 'b/5432', 'blocking')])
    self.SetUpInsertComment(7890101, is_description=True)
    self.services.spam.ClassifyIssue(mox.IsA(tracker_pb2.Issue),
        mox.IsA(tracker_pb2.IssueComment), self.reporter, False).AndReturn(
        self.classifierResult(0.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
        mox.IsA(tracker_pb2.Issue), mox.IgnoreArg(), mox.IgnoreArg(),
        mox.IgnoreArg())
    self.SetUpUpdateIssuesModified(set())
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111, [], ['Type-Defect'], [], [], 111, 'content',
        index_now=False, timestamp=self.now,
        dangling_blocked_on=[
          tracker_pb2.DanglingIssueRef(ext_issue_identifier=shortlink)
          for shortlink in ['b/1234', 'b/5678']],
        dangling_blocking=[
          tracker_pb2.DanglingIssueRef(ext_issue_identifier=shortlink)
          for shortlink in ['b/9876', 'b/5432']])
    self.mox.VerifyAll()

  def testCreateIssue_Imported(self):
    settings.classifier_spam_thresh = 0.9
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpInsertIssue(label_rows=[])
    self.SetUpInsertComment(7890101, is_description=True)
    self.services.issue.commentimporter_tbl.InsertRow(
        self.cnxn, comment_id=7890101, importer_id=222)
    self.services.spam.ClassifyIssue(mox.IgnoreArg(),
        mox.IgnoreArg(), self.reporter, False).AndReturn(
        self.classifierResult(0.0))
    self.services.spam.RecordClassifierIssueVerdict(self.cnxn,
       mox.IsA(tracker_pb2.Issue), False, 1.0, False)
    self.SetUpUpdateIssuesModified(set(), modified_timestamp=self.now)
    self.SetUpEnqueueIssuesForIndexing([78901])
    self.mox.ReplayAll()

    actual_local_id, comment = self.services.issue.CreateIssue(
        self.cnxn, self.services, 789, 'sum',
        'New', 111, [], [',', '', ' ', ', '], [], [], 111, 'content',
        index_now=False, timestamp=self.now, importer_id=222)

    self.mox.VerifyAll()
    self.assertEqual(1, actual_local_id)
    self.assertEqual(111, comment.user_id)
    self.assertEqual(222, comment.importer_id)
    self.assertEqual(self.now, comment.timestamp)

  def testGetAllIssuesInProject_NoIssues(self):
    self.SetUpGetHighestLocalID(789, None, None)
    self.mox.ReplayAll()
    issues = self.services.issue.GetAllIssuesInProject(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual([], issues)

  def testGetAnyOnHandIssue(self):
    issue_ids = [78901, 78902, 78903]
    self.SetUpGetIssues()
    issue = self.services.issue.GetAnyOnHandIssue(issue_ids)
    self.assertEqual(78901, issue.issue_id)

  def SetUpGetIssues(self):
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    issue_1.project_name = 'proj'
    issue_2 = fake.MakeTestIssue(
        project_id=789, local_id=2, owner_id=111, summary='sum',
        status='Fixed', issue_id=78902)
    issue_2.project_name = 'proj'
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)
    self.services.issue.issue_2lc.CacheItem(78902, issue_2)
    return issue_1, issue_2

  def testGetIssuesDict(self):
    issue_ids = [78901, 78902]
    issue_1, issue_2 = self.SetUpGetIssues()
    issues_dict = self.services.issue.GetIssuesDict(self.cnxn, issue_ids)
    self.assertEqual(
        {78901: issue_1, 78902: issue_2},
        issues_dict)

  def testGetIssues(self):
    issue_ids = [78901, 78902]
    issue_1, issue_2 = self.SetUpGetIssues()
    issues = self.services.issue.GetIssues(self.cnxn, issue_ids)
    self.assertEqual([issue_1, issue_2], issues)

  def testGetIssue(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    actual_issue = self.services.issue.GetIssue(self.cnxn, 78901)
    self.assertEqual(issue_1, actual_issue)

  def testGetIssuesByLocalIDs(self):
    issue_1, issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.issue_id_2lc.CacheItem((789, 2), 78902)
    actual_issues = self.services.issue.GetIssuesByLocalIDs(
        self.cnxn, 789, [1, 2])
    self.assertEqual([issue_1, issue_2], actual_issues)

  def testGetIssueByLocalID(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    actual_issues = self.services.issue.GetIssueByLocalID(self.cnxn, 789, 1)
    self.assertEqual(issue_1, actual_issues)

  def testGetOpenAndClosedIssues(self):
    issue_1, issue_2 = self.SetUpGetIssues()
    open_issues, closed_issues = self.services.issue.GetOpenAndClosedIssues(
        self.cnxn, [78901, 78902])
    self.assertEqual([issue_1], open_issues)
    self.assertEqual([issue_2], closed_issues)

  def SetUpGetCurrentLocationOfMovedIssue(self, project_id, local_id):
    issue_id = project_id * 100 + local_id
    self.services.issue.issueformerlocations_tbl.SelectValue(
        self.cnxn, 'issue_id', default=0, project_id=project_id,
        local_id=local_id).AndReturn(issue_id)
    self.services.issue.issue_tbl.SelectRow(
        self.cnxn, cols=['project_id', 'local_id'], id=issue_id).AndReturn(
            (project_id + 1, local_id + 1))

  def testGetCurrentLocationOfMovedIssue(self):
    self.SetUpGetCurrentLocationOfMovedIssue(789, 1)
    self.mox.ReplayAll()
    new_project_id, new_local_id = (
        self.services.issue.GetCurrentLocationOfMovedIssue(self.cnxn, 789, 1))
    self.mox.VerifyAll()
    self.assertEqual(789 + 1, new_project_id)
    self.assertEqual(1 + 1, new_local_id)

  def SetUpGetPreviousLocations(self, issue_id, location_rows):
    self.services.issue.issueformerlocations_tbl.Select(
        self.cnxn, cols=['project_id', 'local_id'],
        issue_id=issue_id).AndReturn(location_rows)

  def testGetPreviousLocations(self):
    self.SetUpGetPreviousLocations(78901, [(781, 1), (782, 11), (789, 1)])
    self.mox.ReplayAll()
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    locations = self.services.issue.GetPreviousLocations(self.cnxn, issue)
    self.mox.VerifyAll()
    self.assertEqual(locations, [(781, 1), (782, 11)])

  def SetUpInsertIssue(
      self, label_rows=None, av_rows=None, approver_rows=None,
      dangling_relation_rows=None):
    row = (789, 1, 1, 111, 111,
           self.now, 0, self.now, self.now, self.now, self.now,
           None, 0,
           False, 0, 0, False)
    self.services.issue.issue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE_COLS[1:], [row],
        commit=False, return_generated_ids=True).AndReturn([78901])
    self.cnxn.Commit()
    self.services.issue.issue_tbl.Update(
        self.cnxn, {'shard': 78901 % settings.num_logical_shards},
        id=78901, commit=False)
    self.SetUpUpdateIssuesSummary()
    self.SetUpUpdateIssuesLabels(label_rows=label_rows)
    self.SetUpUpdateIssuesFields()
    self.SetUpUpdateIssuesComponents()
    self.SetUpUpdateIssuesCc()
    self.SetUpUpdateIssuesNotify()
    self.SetUpUpdateIssuesRelation(
        dangling_relation_rows=dangling_relation_rows)
    self.SetUpUpdateIssuesApprovals(
        av_rows=av_rows, approver_rows=approver_rows)
    self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
        commit=False)

  def SetUpInsertSpamIssue(self):
    row = (789, 1, 1, 111, 111,
           self.now, 0, self.now, self.now, self.now, self.now,
           None, 0, False, 0, 0, True)
    self.services.issue.issue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE_COLS[1:], [row],
        commit=False, return_generated_ids=True).AndReturn([78901])
    self.cnxn.Commit()
    self.services.issue.issue_tbl.Update(
        self.cnxn, {'shard': 78901 % settings.num_logical_shards},
        id=78901, commit=False)
    self.SetUpUpdateIssuesSummary()
    self.SetUpUpdateIssuesLabels()
    self.SetUpUpdateIssuesFields()
    self.SetUpUpdateIssuesComponents()
    self.SetUpUpdateIssuesCc()
    self.SetUpUpdateIssuesNotify()
    self.SetUpUpdateIssuesRelation()
    self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
        commit=False)

  def SetUpUpdateIssuesSummary(self):
    self.services.issue.issuesummary_tbl.InsertRows(
        self.cnxn, ['issue_id', 'summary'],
        [(78901, 'sum')], replace=True, commit=False)

  def SetUpUpdateIssuesLabels(self, label_rows=None):
    if label_rows is None:
      label_rows = [(78901, 1, False, 1)]
    self.services.issue.issue2label_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2label_tbl.InsertRows(
        self.cnxn, ['issue_id', 'label_id', 'derived', 'issue_shard'],
        label_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesFields(self, issue2fieldvalue_rows=None):
    issue2fieldvalue_rows = issue2fieldvalue_rows or []
    self.services.issue.issue2fieldvalue_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2fieldvalue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE2FIELDVALUE_COLS + ['issue_shard'],
        issue2fieldvalue_rows, commit=False)

  def SetUpUpdateIssuesComponents(self, issue2component_rows=None):
    issue2component_rows = issue2component_rows or []
    self.services.issue.issue2component_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2component_tbl.InsertRows(
        self.cnxn, ['issue_id', 'component_id', 'derived', 'issue_shard'],
        issue2component_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesCc(self, issue2cc_rows=None):
    issue2cc_rows = issue2cc_rows or []
    self.services.issue.issue2cc_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2cc_tbl.InsertRows(
        self.cnxn, ['issue_id', 'cc_id', 'derived', 'issue_shard'],
        issue2cc_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesNotify(self, notify_rows=None):
    notify_rows = notify_rows or []
    self.services.issue.issue2notify_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2notify_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE2NOTIFY_COLS,
        notify_rows, ignore=True, commit=False)

  def SetUpUpdateIssuesRelation(
    self, relation_rows=None, dangling_relation_rows=None):
    relation_rows = relation_rows or []
    dangling_relation_rows = dangling_relation_rows or []
    self.services.issue.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS[:-1],
        dst_issue_id=[78901], kind='blockedon').AndReturn([])
    self.services.issue.issuerelation_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issuerelation_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUERELATION_COLS, relation_rows,
        ignore=True, commit=False)
    self.services.issue.danglingrelation_tbl.Delete(
        self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.danglingrelation_tbl.InsertRows(
        self.cnxn, issue_svc.DANGLINGRELATION_COLS, dangling_relation_rows,
        ignore=True, commit=False)

  def SetUpUpdateIssuesApprovals(self, av_rows=None, approver_rows=None):
    av_rows = av_rows or []
    approver_rows = approver_rows or []
    self.services.issue.issue2approvalvalue_tbl.Delete(
        self.cnxn, issue_id=78901, commit=False)
    self.services.issue.issue2approvalvalue_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUE2APPROVALVALUE_COLS, av_rows, commit=False)
    self.services.issue.issueapproval2approver_tbl.Delete(
        self.cnxn, issue_id=78901, commit=False)
    self.services.issue.issueapproval2approver_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEAPPROVAL2APPROVER_COLS, approver_rows,
        commit=False)

  def testInsertIssue(self):
    self.SetUpInsertIssue()
    self.mox.ReplayAll()
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, reporter_id=111,
        summary='sum', status='New', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=self.now, modified_timestamp=self.now)
    actual_issue_id = self.services.issue.InsertIssue(self.cnxn, issue)
    self.mox.VerifyAll()
    self.assertEqual(78901, actual_issue_id)

  def SetUpUpdateIssues(self, given_delta=None):
    delta = given_delta or {
        'project_id': 789,
        'local_id': 1,
        'owner_id': 111,
        'status_id': 1,
        'opened': 123456789,
        'closed': 0,
        'modified': 123456789,
        'owner_modified': 123456789,
        'status_modified': 123456789,
        'component_modified': 123456789,
        'derived_owner_id': None,
        'derived_status_id': None,
        'deleted': False,
        'star_count': 12,
        'attachment_count': 0,
        'is_spam': False,
        }
    self.services.issue.issue_tbl.Update(
        self.cnxn, delta, id=78901, commit=False)
    if not given_delta:
      self.SetUpUpdateIssuesLabels()
      self.SetUpUpdateIssuesCc()
      self.SetUpUpdateIssuesFields()
      self.SetUpUpdateIssuesComponents()
      self.SetUpUpdateIssuesNotify()
      self.SetUpUpdateIssuesSummary()
      self.SetUpUpdateIssuesRelation()
      self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
          commit=False)

    if given_delta:
      self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
          commit=False)

    self.cnxn.Commit()

  def testUpdateIssues_Empty(self):
    # Note: no setup because DB should not be called.
    self.mox.ReplayAll()
    self.services.issue.UpdateIssues(self.cnxn, [])
    self.mox.VerifyAll()

  def testUpdateIssues_Normal(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    issue.assume_stale = False
    self.SetUpUpdateIssues()
    self.mox.ReplayAll()
    self.services.issue.UpdateIssues(self.cnxn, [issue])
    self.mox.VerifyAll()

  def testUpdateIssue_Normal(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    issue.assume_stale = False
    self.SetUpUpdateIssues()
    self.mox.ReplayAll()
    self.services.issue.UpdateIssue(self.cnxn, issue)
    self.mox.VerifyAll()

  def testUpdateIssue_Stale(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    # Do not set issue.assume_stale = False
    # Do not call self.SetUpUpdateIssues() because nothing should be updated.
    self.mox.ReplayAll()
    self.assertRaises(
        AssertionError, self.services.issue.UpdateIssue, self.cnxn, issue)
    self.mox.VerifyAll()

  def testUpdateIssuesSummary(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111, summary='sum', status='New',
        project_id=789)
    issue.assume_stale = False
    self.SetUpUpdateIssuesSummary()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesSummary(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesLabels(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111, summary='sum', status='New',
        labels=['Type-Defect'], project_id=789)
    self.SetUpUpdateIssuesLabels()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesLabels(
      self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesFields_Empty(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111, summary='sum', status='New',
        project_id=789)
    self.SetUpUpdateIssuesFields()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesFields(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesFields_Some(self):
    issue = fake.MakeTestIssue(
        local_id=1, issue_id=78901, owner_id=111, summary='sum', status='New',
        project_id=789)
    issue_shard = issue.issue_id % settings.num_logical_shards
    fv1 = tracker_bizobj.MakeFieldValue(345, 679, '', 0, None, None, False)
    issue.field_values.append(fv1)
    fv2 = tracker_bizobj.MakeFieldValue(346, 0, 'Blue', 0, None, None, True)
    issue.field_values.append(fv2)
    fv3 = tracker_bizobj.MakeFieldValue(347, 0, '', 0, 1234567890, None, True)
    issue.field_values.append(fv3)
    fv4 = tracker_bizobj.MakeFieldValue(
        348, 0, '', 0, None, 'www.google.com', True, phase_id=14)
    issue.field_values.append(fv4)
    self.SetUpUpdateIssuesFields(issue2fieldvalue_rows=[
        (issue.issue_id, fv1.field_id, fv1.int_value, fv1.str_value,
         None, fv1.date_value, fv1.url_value, fv1.derived, None,
         issue_shard),
        (issue.issue_id, fv2.field_id, fv2.int_value, fv2.str_value,
         None, fv2.date_value, fv2.url_value, fv2.derived, None,
         issue_shard),
        (issue.issue_id, fv3.field_id, fv3.int_value, fv3.str_value,
         None, fv3.date_value, fv3.url_value, fv3.derived, None,
         issue_shard),
        (issue.issue_id, fv4.field_id, fv4.int_value, fv4.str_value,
         None, fv4.date_value, fv4.url_value, fv4.derived, 14,
         issue_shard),
        ])
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesFields(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesComponents_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesComponents()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesComponents(
        self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesCc_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesCc()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesCc(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesCc_Some(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    issue.cc_ids = [222, 333]
    issue.derived_cc_ids = [888]
    issue_shard = issue.issue_id % settings.num_logical_shards
    self.SetUpUpdateIssuesCc(issue2cc_rows=[
        (issue.issue_id, 222, False, issue_shard),
        (issue.issue_id, 333, False, issue_shard),
        (issue.issue_id, 888, True, issue_shard),
        ])
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesCc(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesNotify_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesNotify()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesNotify(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesRelation_Empty(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    self.SetUpUpdateIssuesRelation()
    self.mox.ReplayAll()
    self.services.issue._UpdateIssuesRelation(self.cnxn, [issue], commit=False)
    self.mox.VerifyAll()

  def testUpdateIssuesRelation_MergedIntoExternal(self):
    self.services.issue.issuerelation_tbl.Select = Mock(return_value=[])
    self.services.issue.issuerelation_tbl.Delete = Mock()
    self.services.issue.issuerelation_tbl.InsertRows = Mock()
    self.services.issue.danglingrelation_tbl.Delete = Mock()
    self.services.issue.danglingrelation_tbl.InsertRows = Mock()

    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, merged_into_external='b/5678')

    self.services.issue._UpdateIssuesRelation(self.cnxn, [issue])

    self.services.issue.danglingrelation_tbl.Delete.assert_called_once_with(
        self.cnxn, commit=False, issue_id=[78901])
    self.services.issue.danglingrelation_tbl.InsertRows\
        .assert_called_once_with(
          self.cnxn, ['issue_id', 'dst_issue_project', 'dst_issue_local_id',
            'ext_issue_identifier', 'kind'],
          [(78901, None, None, 'b/5678', 'mergedinto')],
          ignore=True, commit=True)

  @patch('time.time')
  def testUpdateIssueStructure(self, mockTime):
    mockTime.return_value = self.now
    reporter_id = 111
    comment_content = 'This issue is being converted'
    # Set up config
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    config.approval_defs = [
        tracker_pb2.ApprovalDef(
            approval_id=3, survey='Question3', approver_ids=[222]),
        tracker_pb2.ApprovalDef(
            approval_id=4, survey='Question4', approver_ids=[444]),
        tracker_pb2.ApprovalDef(
            approval_id=7, survey='Question7', approver_ids=[222]),
    ]
    config.field_defs = [
      tracker_pb2.FieldDef(
          field_id=3, project_id=789, field_name='Cow'),
      tracker_pb2.FieldDef(
          field_id=4, project_id=789, field_name='Chicken'),
      tracker_pb2.FieldDef(
          field_id=6, project_id=789, field_name='Llama'),
      tracker_pb2.FieldDef(
          field_id=7, project_id=789, field_name='Roo'),
      tracker_pb2.FieldDef(
          field_id=8, project_id=789, field_name='Salmon'),
      tracker_pb2.FieldDef(
          field_id=9, project_id=789, field_name='Tuna', is_phase_field=True),
      tracker_pb2.FieldDef(
          field_id=10, project_id=789, field_name='Clown', is_phase_field=True),
      tracker_pb2.FieldDef(
          field_id=11, project_id=789, field_name='Dory', is_phase_field=True),
    ]

    # Set up issue
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum', status='Open',
        issue_id=78901, project_name='proj')
    issue.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=3,
            phase_id=4,
            status=tracker_pb2.ApprovalStatus.APPROVED,
            approver_ids=[111],  # trumps approval_def approver_ids
        ),
        tracker_pb2.ApprovalValue(
            approval_id=4,
            phase_id=5,
            approver_ids=[111]),  # trumps approval_def approver_ids
        tracker_pb2.ApprovalValue(approval_id=6)]
    issue.phases = [
        tracker_pb2.Phase(name='Expired', phase_id=4),
        tracker_pb2.Phase(name='canarY', phase_id=3),
        tracker_pb2.Phase(name='Stable', phase_id=2)]
    issue.field_values = [
        tracker_bizobj.MakeFieldValue(8, None, 'Pink', None, None, None, False),
        tracker_bizobj.MakeFieldValue(
            9, None, 'Silver', None, None, None, False, phase_id=3),
        tracker_bizobj.MakeFieldValue(
            10, None, 'Orange', None, None, None, False, phase_id=4),
        tracker_bizobj.MakeFieldValue(
            11, None, 'Flat', None, None, None, False, phase_id=2),
        ]

    # Set up template
    template = testing_helpers.DefaultTemplates()[0]
    template.approval_values = [
        tracker_pb2.ApprovalValue(
            approval_id=3,
            phase_id=6),  # Different phase. Nothing else affected.
        # No phase. Nothing else affected.
        tracker_pb2.ApprovalValue(approval_id=4),
        # New approval not already found in issue.
        tracker_pb2.ApprovalValue(
            approval_id=7,
            phase_id=5),
    ]  # No approval 6
    # TODO(jojwang): monorail:4693, rename 'Stable-Full' after all
    # 'stable-full' gates have been renamed to 'stable'.
    template.phases = [tracker_pb2.Phase(name='Canary', phase_id=5),
                       tracker_pb2.Phase(name='Stable-Full', phase_id=6)]

    self.SetUpInsertComment(
        7890101, is_description=True, approval_id=3,
        content=config.approval_defs[0].survey, commit=False)
    self.SetUpInsertComment(
        7890101, is_description=True, approval_id=4,
        content=config.approval_defs[1].survey, commit=False)
    self.SetUpInsertComment(
        7890101, is_description=True, approval_id=7,
        content=config.approval_defs[2].survey, commit=False)
    amendment_row = (
        78901, 7890101, 'custom', None, '-Llama Roo', None, None, 'Approvals')
    self.SetUpInsertComment(
        7890101, content=comment_content, amendment_rows=[amendment_row],
        commit=False)
    av_rows = [
        (3, 78901, 6, 'approved', None, None),
        (4, 78901, None, 'not_set', None, None),
        (7, 78901, 5, 'not_set', None, None),
    ]
    approver_rows = [(3, 111, 78901), (4, 111, 78901), (7, 222, 78901)]
    self.SetUpUpdateIssuesApprovals(
        av_rows=av_rows, approver_rows=approver_rows)
    issue_shard = issue.issue_id % settings.num_logical_shards
    issue2fieldvalue_rows = [
        (78901, 8, None, 'Pink', None, None, None, False, None, issue_shard),
        (78901, 9, None, 'Silver', None, None, None, False, 5, issue_shard),
        (78901, 11, None, 'Flat', None, None, None, False, 6, issue_shard),
    ]
    self.SetUpUpdateIssuesFields(issue2fieldvalue_rows=issue2fieldvalue_rows)

    self.mox.ReplayAll()
    comment = self.services.issue.UpdateIssueStructure(
        self.cnxn, config, issue, template, reporter_id,
        comment_content=comment_content, commit=False, invalidate=False)
    self.mox.VerifyAll()

    expected_avs = [
        tracker_pb2.ApprovalValue(
            approval_id=3,
            phase_id=6,
            status=tracker_pb2.ApprovalStatus.APPROVED,
            approver_ids=[111],
        ),
        tracker_pb2.ApprovalValue(
            approval_id=4,
            status=tracker_pb2.ApprovalStatus.NOT_SET,
            approver_ids=[111]),
        tracker_pb2.ApprovalValue(
            approval_id=7,
            status=tracker_pb2.ApprovalStatus.NOT_SET,
            phase_id=5,
            approver_ids=[222]),
    ]
    self.assertEqual(issue.approval_values, expected_avs)
    self.assertEqual(issue.phases, template.phases)
    amendment = tracker_bizobj.MakeApprovalStructureAmendment(
        ['Roo', 'Cow', 'Chicken'], ['Cow', 'Chicken', 'Llama'])
    expected_comment = self.services.issue._MakeIssueComment(
        789, reporter_id, content=comment_content, amendments=[amendment])
    expected_comment.issue_id = 78901
    expected_comment.id = 7890101
    self.assertEqual(expected_comment, comment)

  def testDeltaUpdateIssue(self):
    pass  # TODO(jrobbins): write more tests

  def testDeltaUpdateIssue_NoOp(self):
    """If the user didn't provide any content, we don't make an IssueComment."""
    commenter_id = 222
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    delta = tracker_pb2.IssueDelta()

    amendments, comment_pb = self.services.issue.DeltaUpdateIssue(
        self.cnxn, self.services, commenter_id, issue.project_id, config,
        issue, delta, comment='', index_now=False, timestamp=self.now)
    self.assertEqual([], amendments)
    self.assertIsNone(comment_pb)

  def testDeltaUpdateIssue_MergedInto(self):
    commenter_id = 222
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    target_issue = fake.MakeTestIssue(
        project_id=789, local_id=2, owner_id=111, summary='sum sum',
        status='Live', issue_id=78902, project_name='proj')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

    self.mox.StubOutWithMock(self.services.issue, 'GetIssue')
    self.mox.StubOutWithMock(self.services.issue, 'UpdateIssue')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, '_UpdateIssuesModified')

    self.services.issue.GetIssue(
        self.cnxn, 0).AndRaise(exceptions.NoSuchIssueException)
    self.services.issue.GetIssue(
        self.cnxn, target_issue.issue_id).AndReturn(target_issue)
    self.services.issue.UpdateIssue(
        self.cnxn, issue, commit=False, invalidate=False)
    amendments = [
        tracker_bizobj.MakeMergedIntoAmendment(
            ('proj', 2), None, default_project_name='proj')]
    self.services.issue.CreateIssueComment(
        self.cnxn, issue, commenter_id, 'comment text', attachments=None,
        amendments=amendments, commit=False, is_description=False,
        kept_attachments=None, importer_id=None, timestamp=ANY,
        inbound_message=None)
    self.services.issue._UpdateIssuesModified(
        self.cnxn, {issue.issue_id, target_issue.issue_id},
        modified_timestamp=self.now, invalidate=True)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    delta = tracker_pb2.IssueDelta(merged_into=target_issue.issue_id)
    self.services.issue.DeltaUpdateIssue(
        self.cnxn, self.services, commenter_id, issue.project_id, config,
        issue, delta, comment='comment text',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()

  def testDeltaUpdateIssue_BlockedOn(self):
    commenter_id = 222
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    blockedon_issue = fake.MakeTestIssue(
        project_id=789, local_id=2, owner_id=111, summary='sum sum',
        status='Live', issue_id=78902, project_name='proj')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

    self.mox.StubOutWithMock(self.services.issue, 'GetIssue')
    self.mox.StubOutWithMock(self.services.issue, 'GetIssues')
    self.mox.StubOutWithMock(self.services.issue, 'UpdateIssue')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, '_UpdateIssuesModified')
    self.mox.StubOutWithMock(self.services.issue, "SortBlockedOn")

    # Calls in ApplyIssueDelta
    # Call to find added blockedon issues.
    self.services.issue.GetIssues(
        self.cnxn, [blockedon_issue.issue_id]).AndReturn([blockedon_issue])
    # Call to find removed blockedon issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    # Call to sort blockedon issues.
    self.services.issue.SortBlockedOn(
        self.cnxn, issue, [blockedon_issue.issue_id]).AndReturn(([78902], [0]))

    self.services.issue.UpdateIssue(
        self.cnxn, issue, commit=False, invalidate=False)
    amendments = [
        tracker_bizobj.MakeBlockedOnAmendment(
            [('proj', 2)], [], default_project_name='proj')]
    self.services.issue.CreateIssueComment(
        self.cnxn, issue, commenter_id, 'comment text', attachments=None,
        amendments=amendments, commit=False, is_description=False,
        kept_attachments=None, importer_id=None, timestamp=ANY,
        inbound_message=None)
    # Call to find added blockedon issues.
    self.services.issue.GetIssues(
        self.cnxn, [blockedon_issue.issue_id]).AndReturn([blockedon_issue])
    self.services.issue.CreateIssueComment(
        self.cnxn, blockedon_issue, commenter_id, content='',
        amendments=[tracker_bizobj.MakeBlockingAmendment(
            [(issue.project_name, issue.local_id)], [],
            default_project_name='proj')],
        importer_id=None, timestamp=ANY)
    # Call to find removed blockedon issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    # Call to find added blocking issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    # Call to find removed blocking issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])

    self.services.issue._UpdateIssuesModified(
        self.cnxn, {issue.issue_id, blockedon_issue.issue_id},
        modified_timestamp=self.now, invalidate=True)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    delta = tracker_pb2.IssueDelta(blocked_on_add=[blockedon_issue.issue_id])
    self.services.issue.DeltaUpdateIssue(
        self.cnxn, self.services, commenter_id, issue.project_id, config,
        issue, delta, comment='comment text',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()

  def testDeltaUpdateIssue_Blocking(self):
    commenter_id = 222
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    blocking_issue = fake.MakeTestIssue(
        project_id=789, local_id=2, owner_id=111, summary='sum sum',
        status='Live', issue_id=78902, project_name='proj')
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

    self.mox.StubOutWithMock(self.services.issue, 'GetIssue')
    self.mox.StubOutWithMock(self.services.issue, 'GetIssues')
    self.mox.StubOutWithMock(self.services.issue, 'UpdateIssue')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, '_UpdateIssuesModified')
    self.mox.StubOutWithMock(self.services.issue, "SortBlockedOn")

    # Calls in ApplyIssueDelta
    # Call to find added blocking issues.
    self.services.issue.GetIssues(
        self.cnxn, [blocking_issue.issue_id]).AndReturn([blocking_issue])
    # Call to find removed blocking issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])

    self.services.issue.UpdateIssue(
        self.cnxn, issue, commit=False, invalidate=False)
    amendments = [
        tracker_bizobj.MakeBlockingAmendment(
            [('proj', 2)], [], default_project_name='proj')]
    self.services.issue.CreateIssueComment(
        self.cnxn, issue, commenter_id, 'comment text', attachments=None,
        amendments=amendments, commit=False, is_description=False,
        kept_attachments=None, importer_id=None, timestamp=ANY,
        inbound_message=None)
    # Call to find added blockedon issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    # Call to find removed blockedon issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    # Call to find added blocking issues.
    self.services.issue.GetIssues(
        self.cnxn, [blocking_issue.issue_id]).AndReturn([blocking_issue])
    self.services.issue.CreateIssueComment(
        self.cnxn, blocking_issue, commenter_id, content='',
        amendments=[tracker_bizobj.MakeBlockedOnAmendment(
            [(issue.project_name, issue.local_id)], [],
            default_project_name='proj')],
        importer_id=None, timestamp=ANY)
    # Call to find removed blocking issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    self.services.issue._UpdateIssuesModified(
        self.cnxn, {issue.issue_id, blocking_issue.issue_id},
        modified_timestamp=self.now, invalidate=True)
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    delta = tracker_pb2.IssueDelta(blocking_add=[blocking_issue.issue_id])
    self.services.issue.DeltaUpdateIssue(
        self.cnxn, self.services, commenter_id, issue.project_id, config,
        issue, delta, comment='comment text',
        index_now=False, timestamp=self.now)
    self.mox.VerifyAll()

  def testDeltaUpdateIssue_Imported(self):
    """If importer_id is specified, store it."""
    commenter_id = 222
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, project_name='proj')
    issue.assume_stale = False
    config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)
    delta = tracker_pb2.IssueDelta()

    self.mox.StubOutWithMock(self.services.issue, 'GetIssue')
    self.mox.StubOutWithMock(self.services.issue, 'GetIssues')
    self.mox.StubOutWithMock(self.services.issue, 'UpdateIssue')
    self.mox.StubOutWithMock(self.services.issue, 'CreateIssueComment')
    self.mox.StubOutWithMock(self.services.issue, '_UpdateIssuesModified')
    self.mox.StubOutWithMock(self.services.issue, "SortBlockedOn")
    self.services.issue.UpdateIssue(
        self.cnxn, issue, commit=False, invalidate=False)
    # Call to find added blockedon issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    # Call to find removed blockedon issues.
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    self.services.issue.CreateIssueComment(
        self.cnxn, issue, commenter_id, 'a comment', attachments=None,
        amendments=[], commit=False, is_description=False,
        kept_attachments=None, importer_id=333, timestamp=ANY,
        inbound_message=None).AndReturn(
          tracker_pb2.IssueComment(content='a comment', importer_id=333))
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    self.services.issue.GetIssues(self.cnxn, []).AndReturn([])
    self.services.issue._UpdateIssuesModified(
        self.cnxn, {issue.issue_id},
        modified_timestamp=self.now, invalidate=True)
    self.SetUpEnqueueIssuesForIndexing([78901])
    self.mox.ReplayAll()

    amendments, comment_pb = self.services.issue.DeltaUpdateIssue(
        self.cnxn, self.services, commenter_id, issue.project_id, config,
        issue, delta, comment='a comment', index_now=False, timestamp=self.now,
        importer_id=333)

    self.mox.VerifyAll()
    self.assertEqual([], amendments)
    self.assertEqual('a comment', comment_pb.content)
    self.assertEqual(333, comment_pb.importer_id)

  def SetUpMoveIssues_NewProject(self):
    self.services.issue.issueformerlocations_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEFORMERLOCATIONS_COLS, project_id=789,
        issue_id=[78901]).AndReturn([])
    self.SetUpAllocateNextLocalID(789, None, None)
    self.SetUpUpdateIssues()
    self.services.issue.comment_tbl.Update(
        self.cnxn, {'project_id': 789}, issue_id=[78901], commit=False)

    old_location_rows = [(78901, 711, 2)]
    self.services.issue.issueformerlocations_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEFORMERLOCATIONS_COLS, old_location_rows,
        ignore=True, commit=False)
    self.cnxn.Commit()

  def testMoveIssues_NewProject(self):
    """Move project 711 issue 2 to become project 789 issue 1."""
    dest_project = fake.Project(project_id=789)
    issue = fake.MakeTestIssue(
        project_id=711, local_id=2, owner_id=111, summary='sum',
        status='Live', labels=['Type-Defect'], issue_id=78901,
        opened_timestamp=123456789, modified_timestamp=123456789,
        star_count=12)
    issue.assume_stale = False
    self.SetUpMoveIssues_NewProject()
    self.mox.ReplayAll()
    self.services.issue.MoveIssues(
        self.cnxn, dest_project, [issue], self.services.user)
    self.mox.VerifyAll()

  # TODO(jrobbins): case where issue is moved back into former project

  def testExpungeFormerLocations(self):
    self.services.issue.issueformerlocations_tbl.Delete(
      self.cnxn, project_id=789)

    self.mox.ReplayAll()
    self.services.issue.ExpungeFormerLocations(self.cnxn, 789)
    self.mox.VerifyAll()

  def testExpungeIssues(self):
    issue_ids = [1, 2]

    self.mox.StubOutWithMock(search, 'Index')
    search.Index(name=settings.search_index_name_format % 1).AndReturn(
        MockIndex())
    search.Index(name=settings.search_index_name_format % 2).AndReturn(
        MockIndex())

    self.services.issue.issuesummary_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2label_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2component_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2cc_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue2notify_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issueupdate_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.attachment_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.comment_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issuerelation_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issuerelation_tbl.Delete(self.cnxn, dst_issue_id=[1, 2])
    self.services.issue.danglingrelation_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issueformerlocations_tbl.Delete(
        self.cnxn, issue_id=[1, 2])
    self.services.issue.reindexqueue_tbl.Delete(self.cnxn, issue_id=[1, 2])
    self.services.issue.issue_tbl.Delete(self.cnxn, id=[1, 2])

    self.mox.ReplayAll()
    self.services.issue.ExpungeIssues(self.cnxn, issue_ids)
    self.mox.VerifyAll()

  def testSoftDeleteIssue(self):
    project = fake.Project(project_id=789)
    issue_1, issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_2lc = TestableIssueTwoLevelCache(
        [issue_1, issue_2])
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    delta = {'deleted': True}
    self.services.issue.issue_tbl.Update(
        self.cnxn, delta, id=78901, commit=False)

    self.services.chart.StoreIssueSnapshots(self.cnxn, mox.IgnoreArg(),
        commit=False)

    self.cnxn.Commit()
    self.mox.ReplayAll()
    self.services.issue.SoftDeleteIssue(
        self.cnxn, project.project_id, 1, True, self.services.user)
    self.mox.VerifyAll()
    self.assertTrue(issue_1.deleted)

  def SetUpDeleteComponentReferences(self, component_id):
    self.services.issue.issue2component_tbl.Delete(
      self.cnxn, component_id=component_id)

  def testDeleteComponentReferences(self):
    self.SetUpDeleteComponentReferences(123)
    self.mox.ReplayAll()
    self.services.issue.DeleteComponentReferences(self.cnxn, 123)
    self.mox.VerifyAll()

  ### Local ID generation

  def SetUpInitializeLocalID(self, project_id):
    self.services.issue.localidcounter_tbl.InsertRow(
        self.cnxn, project_id=project_id, used_local_id=0, used_spam_id=0)

  def testInitializeLocalID(self):
    self.SetUpInitializeLocalID(789)
    self.mox.ReplayAll()
    self.services.issue.InitializeLocalID(self.cnxn, 789)
    self.mox.VerifyAll()

  def SetUpAllocateNextLocalID(
      self, project_id, highest_in_use, highest_former):
    highest_either = max(highest_in_use or 0, highest_former or 0)
    self.services.issue.localidcounter_tbl.IncrementCounterValue(
        self.cnxn, 'used_local_id', project_id=project_id).AndReturn(
            highest_either + 1)

  def testAllocateNextLocalID_NewProject(self):
    self.SetUpAllocateNextLocalID(789, None, None)
    self.mox.ReplayAll()
    next_local_id = self.services.issue.AllocateNextLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(1, next_local_id)

  def testAllocateNextLocalID_HighestInUse(self):
    self.SetUpAllocateNextLocalID(789, 14, None)
    self.mox.ReplayAll()
    next_local_id = self.services.issue.AllocateNextLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(15, next_local_id)

  def testAllocateNextLocalID_HighestWasMoved(self):
    self.SetUpAllocateNextLocalID(789, 23, 66)
    self.mox.ReplayAll()
    next_local_id = self.services.issue.AllocateNextLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(67, next_local_id)

  def SetUpGetHighestLocalID(self, project_id, highest_in_use, highest_former):
    self.services.issue.issue_tbl.SelectValue(
        self.cnxn, 'MAX(local_id)', project_id=project_id).AndReturn(
            highest_in_use)
    self.services.issue.issueformerlocations_tbl.SelectValue(
        self.cnxn, 'MAX(local_id)', project_id=project_id).AndReturn(
            highest_former)

  def testGetHighestLocalID_OnlyActiveLocalIDs(self):
    self.SetUpGetHighestLocalID(789, 14, None)
    self.mox.ReplayAll()
    highest_id = self.services.issue.GetHighestLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(14, highest_id)

  def testGetHighestLocalID_OnlyFormerIDs(self):
    self.SetUpGetHighestLocalID(789, None, 97)
    self.mox.ReplayAll()
    highest_id = self.services.issue.GetHighestLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(97, highest_id)

  def testGetHighestLocalID_BothActiveAndFormer(self):
    self.SetUpGetHighestLocalID(789, 345, 97)
    self.mox.ReplayAll()
    highest_id = self.services.issue.GetHighestLocalID(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(345, highest_id)

  def testGetAllLocalIDsInProject(self):
    self.SetUpGetHighestLocalID(789, 14, None)
    self.mox.ReplayAll()
    local_id_range = self.services.issue.GetAllLocalIDsInProject(self.cnxn, 789)
    self.mox.VerifyAll()
    self.assertEqual(list(range(1, 15)), local_id_range)

  ### Comments

  def testConsolidateAmendments_Empty(self):
    amendments = []
    actual = self.services.issue._ConsolidateAmendments(amendments)
    self.assertEqual([], actual)

  def testConsolidateAmendments_NoOp(self):
    amendments = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            oldvalue='old sum', newvalue='new sum'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            oldvalue='New', newvalue='Accepted')]
    actual = self.services.issue._ConsolidateAmendments(amendments)
    self.assertEqual(amendments, actual)

  def testConsolidateAmendments_StandardFields(self):
    amendments = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            oldvalue='New'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            newvalue='Accepted'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            oldvalue='old sum'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            newvalue='new sum')]
    actual = self.services.issue._ConsolidateAmendments(amendments)

    expected = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                            oldvalue='old sum', newvalue='new sum'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                            oldvalue='New', newvalue='Accepted')]
    self.assertEqual(expected, actual)

  def testConsolidateAmendments_CustomFields(self):
    amendments = [
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('CUSTOM'),
                            custom_field_name='a', oldvalue='old a'),
      tracker_pb2.Amendment(field=tracker_pb2.FieldID('CUSTOM'),
                            custom_field_name='b', oldvalue='old b')]
    actual = self.services.issue._ConsolidateAmendments(amendments)
    self.assertEqual(amendments, actual)

  def testConsolidateAmendments_SortAmmendments(self):
    amendments = [
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                                oldvalue='New', newvalue='Accepted'),
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                                oldvalue='old sum', newvalue='new sum'),
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('LABELS'),
            oldvalue='Type-Defect', newvalue='-Type-Defect Type-Enhancement'),
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('CC'),
                        oldvalue='a@google.com', newvalue='b@google.com')]
    expected = [
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('SUMMARY'),
                                oldvalue='old sum', newvalue='new sum'),
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('STATUS'),
                                oldvalue='New', newvalue='Accepted'),
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('CC'),
                        oldvalue='a@google.com', newvalue='b@google.com'),
        tracker_pb2.Amendment(field=tracker_pb2.FieldID('LABELS'),
            oldvalue='Type-Defect', newvalue='-Type-Defect Type-Enhancement')]
    actual = self.services.issue._ConsolidateAmendments(amendments)
    self.assertEqual(expected, actual)

  def testDeserializeComments_Empty(self):
    comments = self.services.issue._DeserializeComments([], [], [], [], [], [])
    self.assertEqual([], comments)

  def SetUpCommentRows(self):
    comment_rows = [
        (7890101, 78901, self.now, 789, 111,
         None, False, False, 'unused_commentcontent_id'),
        (7890102, 78901, self.now, 789, 111,
         None, False, False, 'unused_commentcontent_id')]
    commentcontent_rows = [(7890101, 'content', 'msg'),
                           (7890102, 'content2', 'msg')]
    amendment_rows = [
        (1, 78901, 7890101, 'cc', 'old', 'new val', 222, None, None)]
    attachment_rows = []
    approval_rows = [(23, 7890102)]
    importer_rows = []
    return (comment_rows, commentcontent_rows, amendment_rows,
            attachment_rows, approval_rows, importer_rows)

  def testDeserializeComments_Normal(self):
    (comment_rows, commentcontent_rows, amendment_rows,
     attachment_rows, approval_rows, importer_rows) = self.SetUpCommentRows()
    commentcontent_rows = [(7890101, 'content', 'msg')]
    comments = self.services.issue._DeserializeComments(
        comment_rows, commentcontent_rows, amendment_rows, attachment_rows,
        approval_rows, importer_rows)
    self.assertEqual(2, len(comments))

  def testDeserializeComments_Imported(self):
    (comment_rows, commentcontent_rows, amendment_rows,
     attachment_rows, approval_rows, _) = self.SetUpCommentRows()
    importer_rows = [(7890101, 222)]
    commentcontent_rows = [(7890101, 'content', 'msg')]
    comments = self.services.issue._DeserializeComments(
        comment_rows, commentcontent_rows, amendment_rows, attachment_rows,
        approval_rows, importer_rows)
    self.assertEqual(2, len(comments))
    self.assertEqual(222, comments[0].importer_id)

  def MockTheRestOfGetCommentsByID(self, comment_ids):
    self.services.issue.commentcontent_tbl.Select = Mock(
        return_value=[
            (cid + 5000, 'content', None) for cid in comment_ids])
    self.services.issue.issueupdate_tbl.Select = Mock(
        return_value=[])
    self.services.issue.attachment_tbl.Select = Mock(
        return_value=[])
    self.services.issue.issueapproval2comment_tbl.Select = Mock(
        return_value=[])
    self.services.issue.commentimporter_tbl.Select = Mock(
        return_value=[])

  def testGetCommentsByID_Normal(self):
    """We can load comments by comment_ids."""
    comment_ids = [101001, 101002, 101003]
    self.services.issue.comment_tbl.Select = Mock(
        return_value=[
            (cid, cid - cid % 100, self.now, 789, 111,
             None, False, False, cid + 5000)
            for cid in comment_ids])
    self.MockTheRestOfGetCommentsByID(comment_ids)

    comments = self.services.issue.GetCommentsByID(
        self.cnxn, comment_ids, [0, 1, 2])

    self.services.issue.comment_tbl.Select.assert_called_with(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        id=comment_ids, shard_id=ANY)

    self.assertEqual(3, len(comments))

  def testGetCommentsByID_CacheReplicationLag(self):
    self._testGetCommentsByID_ReplicationLag(True)

  def testGetCommentsByID_NoCacheReplicationLag(self):
    self._testGetCommentsByID_ReplicationLag(False)

  def _testGetCommentsByID_ReplicationLag(self, use_cache):
    """If not all comments are on the replica, we try the master."""
    comment_ids = [101001, 101002, 101003]
    replica_comment_ids = comment_ids[:-1]

    return_value_1 = [
      (cid, cid - cid % 100, self.now, 789, 111,
       None, False, False, cid + 5000)
      for cid in replica_comment_ids]
    return_value_2 = [
      (cid, cid - cid % 100, self.now, 789, 111,
       None, False, False, cid + 5000)
      for cid in comment_ids]
    return_values = [return_value_1, return_value_2]
    self.services.issue.comment_tbl.Select = Mock(
        side_effect=lambda *_args, **_kwargs: return_values.pop(0))

    self.MockTheRestOfGetCommentsByID(comment_ids)

    comments = self.services.issue.GetCommentsByID(
        self.cnxn, comment_ids, [0, 1, 2], use_cache=use_cache)

    self.services.issue.comment_tbl.Select.assert_called_with(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        id=comment_ids, shard_id=ANY)
    self.services.issue.comment_tbl.Select.assert_called_with(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        id=comment_ids, shard_id=ANY)
    self.assertEqual(3, len(comments))

  def SetUpGetComments(self, issue_ids):
    # Assumes one comment per issue.
    cids = [issue_id + 1000 for issue_id in issue_ids]
    self.services.issue.comment_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        where=None, issue_id=issue_ids, order_by=[('created', [])],
        shard_id=mox.IsA(int)).AndReturn([
            (issue_id + 1000, issue_id, self.now, 789, 111,
             None, False, False, issue_id + 5000)
            for issue_id in issue_ids])
    self.services.issue.commentcontent_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTCONTENT_COLS,
        id=[issue_id + 5000 for issue_id in issue_ids],
        shard_id=mox.IsA(int)).AndReturn([
        (issue_id + 5000, 'content', None) for issue_id in issue_ids])
    self.services.issue.issueapproval2comment_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
        comment_id=cids).AndReturn([
            (23, cid) for cid in cids])

    # Assume no amendments or attachment for now.
    self.services.issue.issueupdate_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEUPDATE_COLS,
        comment_id=cids, shard_id=mox.IsA(int)).AndReturn([])
    attachment_rows = []
    if issue_ids:
      attachment_rows = [
          (1234, issue_ids[0], cids[0], 'a_filename', 1024, 'text/plain',
           False, None)]

    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS,
        comment_id=cids, shard_id=mox.IsA(int)).AndReturn(attachment_rows)

    self.services.issue.commentimporter_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTIMPORTER_COLS,
        comment_id=cids, shard_id=mox.IsA(int)).AndReturn([])

  def testGetComments_Empty(self):
    self.SetUpGetComments([])
    self.mox.ReplayAll()
    comments = self.services.issue.GetComments(
        self.cnxn, issue_id=[])
    self.mox.VerifyAll()
    self.assertEqual(0, len(comments))

  def testGetComments_Normal(self):
    self.SetUpGetComments([100001, 100002])
    self.mox.ReplayAll()
    comments = self.services.issue.GetComments(
        self.cnxn, issue_id=[100001, 100002])
    self.mox.VerifyAll()
    self.assertEqual(2, len(comments))
    self.assertEqual('content', comments[0].content)
    self.assertEqual('content', comments[1].content)
    self.assertEqual(23, comments[0].approval_id)
    self.assertEqual(23, comments[1].approval_id)

  def SetUpGetComment_Found(self, comment_id):
    # Assumes one comment per issue.
    commentcontent_id = comment_id * 10
    self.services.issue.comment_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        where=None, id=comment_id, order_by=[('created', [])],
        shard_id=mox.IsA(int)).AndReturn([
            (comment_id, int(comment_id // 100), self.now, 789, 111,
             None, False, True, commentcontent_id)])
    self.services.issue.commentcontent_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTCONTENT_COLS,
        id=[commentcontent_id], shard_id=mox.IsA(int)).AndReturn([
            (commentcontent_id, 'content', None)])
    self.services.issue.issueapproval2comment_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
        comment_id=[comment_id]).AndReturn([(23, comment_id)])
    # Assume no amendments or attachment for now.
    self.services.issue.issueupdate_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEUPDATE_COLS,
        comment_id=[comment_id], shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS,
        comment_id=[comment_id], shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.commentimporter_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTIMPORTER_COLS,
        comment_id=[comment_id], shard_id=mox.IsA(int)).AndReturn([])

  def testGetComment_Found(self):
    self.SetUpGetComment_Found(7890101)
    self.mox.ReplayAll()
    comment = self.services.issue.GetComment(self.cnxn, 7890101)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)
    self.assertEqual(23, comment.approval_id)

  def SetUpGetComment_Missing(self, comment_id):
    # Assumes one comment per issue.
    self.services.issue.comment_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENT_COLS,
        where=None, id=comment_id, order_by=[('created', [])],
        shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.commentcontent_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTCONTENT_COLS,
        id=[], shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.issueapproval2comment_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
        comment_id=[]).AndReturn([])
    # Assume no amendments or attachment for now.
    self.services.issue.issueupdate_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUEUPDATE_COLS,
        comment_id=[], shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS, comment_id=[],
        shard_id=mox.IsA(int)).AndReturn([])
    self.services.issue.commentimporter_tbl.Select(
        self.cnxn, cols=issue_svc.COMMENTIMPORTER_COLS,
        comment_id=[], shard_id=mox.IsA(int)).AndReturn([])

  def testGetComment_Missing(self):
    self.SetUpGetComment_Missing(7890101)
    self.mox.ReplayAll()
    self.assertRaises(
        exceptions.NoSuchCommentException,
        self.services.issue.GetComment, self.cnxn, 7890101)
    self.mox.VerifyAll()

  def testGetCommentsForIssue(self):
    issue = fake.MakeTestIssue(789, 1, 'Summary', 'New', 111)
    self.SetUpGetComments([issue.issue_id])
    self.mox.ReplayAll()
    self.services.issue.GetCommentsForIssue(self.cnxn, issue.issue_id)
    self.mox.VerifyAll()

  def testGetCommentsForIssues(self):
    self.SetUpGetComments([100001, 100002])
    self.mox.ReplayAll()
    self.services.issue.GetCommentsForIssues(
        self.cnxn, issue_ids=[100001, 100002])
    self.mox.VerifyAll()

  def SetUpInsertComment(
      self, comment_id, is_spam=False, is_description=False, approval_id=None,
          content=None, amendment_rows=None, commit=True):
    content = content or 'content'
    commentcontent_id = comment_id * 10
    self.services.issue.commentcontent_tbl.InsertRow(
        self.cnxn, content=content,
        inbound_message=None, commit=False).AndReturn(commentcontent_id)
    self.services.issue.comment_tbl.InsertRow(
        self.cnxn, issue_id=78901, created=self.now, project_id=789,
        commenter_id=111, deleted_by=None, is_spam=is_spam,
        is_description=is_description, commentcontent_id=commentcontent_id,
        commit=False).AndReturn(comment_id)

    amendment_rows = amendment_rows or []
    self.services.issue.issueupdate_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEUPDATE_COLS[1:], amendment_rows,
        commit=False)

    attachment_rows = []
    self.services.issue.attachment_tbl.InsertRows(
        self.cnxn, issue_svc.ATTACHMENT_COLS[1:], attachment_rows,
        commit=False)

    if approval_id:
      self.services.issue.issueapproval2comment_tbl.InsertRows(
          self.cnxn, issue_svc.ISSUEAPPROVAL2COMMENT_COLS,
          [(approval_id, comment_id)], commit=False)

    if commit:
      self.cnxn.Commit()

  def testInsertComment(self):
    self.SetUpInsertComment(7890101, approval_id=23)
    self.mox.ReplayAll()
    comment = tracker_pb2.IssueComment(
        issue_id=78901, timestamp=self.now, project_id=789, user_id=111,
        content='content', approval_id=23)
    self.services.issue.InsertComment(self.cnxn, comment, commit=True)
    self.mox.VerifyAll()
    self.assertEqual(7890101, comment.id)

  def SetUpUpdateComment(self, comment_id, delta=None):
    delta = delta or {
        'commenter_id': 111,
        'deleted_by': 222,
        'is_spam': False,
        }
    self.services.issue.comment_tbl.Update(
        self.cnxn, delta, id=comment_id)

  def testUpdateComment(self):
    self.SetUpUpdateComment(7890101)
    self.mox.ReplayAll()
    comment = tracker_pb2.IssueComment(
        id=7890101, issue_id=78901, timestamp=self.now, project_id=789,
        user_id=111, content='new content', deleted_by=222,
        is_spam=False)
    self.services.issue._UpdateComment(self.cnxn, comment)
    self.mox.VerifyAll()

  def testMakeIssueComment(self):
    comment = self.services.issue._MakeIssueComment(
        789, 111, 'content', timestamp=self.now, approval_id=23,
        importer_id=222)
    self.assertEqual('content', comment.content)
    self.assertEqual([], comment.amendments)
    self.assertEqual([], comment.attachments)
    self.assertEqual(comment.approval_id, 23)
    self.assertEqual(222, comment.importer_id)

  def testMakeIssueComment_NonAscii(self):
    _ = self.services.issue._MakeIssueComment(
        789, 111, 'content', timestamp=self.now,
        inbound_message=u'sent by написа')

  def testCreateIssueComment_Normal(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.SetUpInsertComment(7890101, approval_id=24)
    self.mox.ReplayAll()
    comment = self.services.issue.CreateIssueComment(
        self.cnxn, issue_1, 111, 'content', timestamp=self.now, approval_id=24)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)

  def testCreateIssueComment_EditDescription(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.services.issue.attachment_tbl.Select(
        self.cnxn, cols=issue_svc.ATTACHMENT_COLS, id=[123])
    self.SetUpInsertComment(7890101, is_description=True)
    self.mox.ReplayAll()

    comment = self.services.issue.CreateIssueComment(
        self.cnxn, issue_1, 111, 'content', is_description=True,
        kept_attachments=[123], timestamp=self.now)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)

  def testCreateIssueComment_Spam(self):
    issue_1, _issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.SetUpInsertComment(7890101, is_spam=True)
    self.mox.ReplayAll()
    comment = self.services.issue.CreateIssueComment(
        self.cnxn, issue_1, 111, 'content', timestamp=self.now, is_spam=True)
    self.mox.VerifyAll()
    self.assertEqual('content', comment.content)
    self.assertTrue(comment.is_spam)

  def testSoftDeleteComment(self):
    """Deleting a comment with an attachment marks it and updates count."""
    issue_1, issue_2 = self.SetUpGetIssues()
    self.services.issue.issue_2lc = TestableIssueTwoLevelCache(
        [issue_1, issue_2])
    issue_1.attachment_count = 1
    issue_1.assume_stale = False
    comment = tracker_pb2.IssueComment(id=7890101)
    comment.attachments = [tracker_pb2.Attachment()]
    self.services.issue.issue_id_2lc.CacheItem((789, 1), 78901)
    self.SetUpUpdateComment(
        comment.id, delta={'deleted_by': 222, 'is_spam': False})
    self.SetUpUpdateIssues(given_delta={'attachment_count': 0})
    self.SetUpEnqueueIssuesForIndexing([78901])
    self.mox.ReplayAll()
    self.services.issue.SoftDeleteComment(
        self.cnxn, issue_1, comment, 222, self.services.user)
    self.mox.VerifyAll()

  ### Approvals

  def testGetIssueApproval(self):
    av_24 = tracker_pb2.ApprovalValue(approval_id=24)
    av_25 = tracker_pb2.ApprovalValue(approval_id=25)
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901, approval_values=[av_24, av_25])
    issue_1.project_name = 'proj'
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)

    issue, actual_approval_value = self.services.issue.GetIssueApproval(
        self.cnxn, issue_1.issue_id, av_24.approval_id)

    self.assertEqual(av_24, actual_approval_value)
    self.assertEqual(issue, issue_1)

  def testGetIssueApproval_NoSuchApproval(self):
    issue_1 = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    issue_1.project_name = 'proj'
    self.services.issue.issue_2lc.CacheItem(78901, issue_1)
    self.assertRaises(
        exceptions.NoSuchIssueApprovalException,
        self.services.issue.GetIssueApproval,
        self.cnxn, issue_1.issue_id, 24)

  def testDeltaUpdateIssueApproval(self):
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    config.field_defs = [
      tracker_pb2.FieldDef(
        field_id=1, project_id=789, field_name='EstDays',
        field_type=tracker_pb2.FieldTypes.INT_TYPE,
        applicable_type=''),
      tracker_pb2.FieldDef(
        field_id=2, project_id=789, field_name='Tag',
        field_type=tracker_pb2.FieldTypes.STR_TYPE,
        applicable_type=''),
        ]
    self.services.config.StoreConfig(self.cnxn, config)

    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, summary='summary', status='New',
        owner_id=999, issue_id=78901, labels=['noodle-puppies'])
    av = tracker_pb2.ApprovalValue(approval_id=23)
    final_av = tracker_pb2.ApprovalValue(
        approval_id=23, setter_id=111, set_on=1234,
        status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED,
        approver_ids=[222, 444])
    labels_add = ['snakes-are']
    label_id = 1001
    labels_remove = ['noodle-puppies']
    amendments = [
        tracker_bizobj.MakeApprovalStatusAmendment(
            tracker_pb2.ApprovalStatus.REVIEW_REQUESTED),
        tracker_bizobj.MakeApprovalApproversAmendment([222, 444], []),
        tracker_bizobj.MakeFieldAmendment(1, config, [4], []),
        tracker_bizobj.MakeFieldClearedAmendment(2, config),
        tracker_bizobj.MakeLabelsAmendment(labels_add, labels_remove)
    ]
    approval_delta = tracker_pb2.ApprovalDelta(
        status=tracker_pb2.ApprovalStatus.REVIEW_REQUESTED,
        approver_ids_add=[222, 444], set_on=1234,
        subfield_vals_add=[
          tracker_bizobj.MakeFieldValue(1, 4, None, None, None, None, False)
          ],
        labels_add=labels_add,
        labels_remove=labels_remove,
        subfields_clear=[2]
    )

    self.services.issue.issue2approvalvalue_tbl.Update = Mock()
    self.services.issue.issueapproval2approver_tbl.Delete = Mock()
    self.services.issue.issueapproval2approver_tbl.InsertRows = Mock()
    self.services.issue.issue2fieldvalue_tbl.Delete = Mock()
    self.services.issue.issue2fieldvalue_tbl.InsertRows = Mock()
    self.services.issue.issue2label_tbl.Delete = Mock()
    self.services.issue.issue2label_tbl.InsertRows = Mock()
    self.services.issue.CreateIssueComment = Mock()
    self.services.config.LookupLabelID = Mock(return_value=label_id)
    shard = issue.issue_id % settings.num_logical_shards
    fv_rows = [(78901, 1, 4, None, None, None, None, False, None, shard)]
    label_rows = [(78901, label_id, False, shard)]

    self.services.issue.DeltaUpdateIssueApproval(
        self.cnxn, 111, config, issue, av, approval_delta, 'some comment',
        attachments=[], commit=False, kept_attachments=[1, 2, 3])

    self.assertEqual(av, final_av)

    self.services.issue.issue2approvalvalue_tbl.Update.assert_called_once_with(
        self.cnxn,
        {'status': 'review_requested', 'setter_id': 111, 'set_on': 1234},
        approval_id=23, issue_id=78901, commit=False)
    self.services.issue.issueapproval2approver_tbl.\
        Delete.assert_called_once_with(
            self.cnxn, issue_id=78901, approval_id=23, commit=False)
    self.services.issue.issueapproval2approver_tbl.\
        InsertRows.assert_called_once_with(
            self.cnxn, issue_svc.ISSUEAPPROVAL2APPROVER_COLS,
            [(23, 222, 78901), (23, 444, 78901)], commit=False)
    self.services.issue.issue2fieldvalue_tbl.\
        Delete.assert_called_once_with(
            self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2fieldvalue_tbl.\
        InsertRows.assert_called_once_with(
            self.cnxn, issue_svc.ISSUE2FIELDVALUE_COLS + ['issue_shard'],
            fv_rows, commit=False)
    self.services.issue.issue2label_tbl.\
        Delete.assert_called_once_with(
            self.cnxn, issue_id=[78901], commit=False)
    self.services.issue.issue2label_tbl.\
        InsertRows.assert_called_once_with(
            self.cnxn, issue_svc.ISSUE2LABEL_COLS + ['issue_shard'],
            label_rows, ignore=True, commit=False)
    self.services.issue.CreateIssueComment.assert_called_once_with(
        self.cnxn, issue, 111, 'some comment', amendments=amendments,
        approval_id=23, is_description=False, attachments=[], commit=False,
        kept_attachments=[1, 2, 3])

  def testDeltaUpdateIssueApproval_IsDescription(self):
    config = self.services.config.GetProjectConfig(
        self.cnxn, 789)
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, summary='summary', status='New',
        owner_id=999, issue_id=78901)
    av = tracker_pb2.ApprovalValue(approval_id=23)
    approval_delta = tracker_pb2.ApprovalDelta()

    self.services.issue.CreateIssueComment = Mock()

    self.services.issue.DeltaUpdateIssueApproval(
        self.cnxn, 111, config, issue, av, approval_delta, 'better response',
        is_description=True, commit=False)

    self.services.issue.CreateIssueComment.assert_called_once_with(
        self.cnxn, issue, 111, 'better response', amendments=[],
        approval_id=23, is_description=True, attachments=None, commit=False,
        kept_attachments=None)

  def testUpdateIssueApprovalStatus(self):
    av = tracker_pb2.ApprovalValue(approval_id=23, setter_id=111, set_on=1234)

    self.services.issue.issue2approvalvalue_tbl.Update(
        self.cnxn, {'status': 'not_set', 'setter_id': 111, 'set_on': 1234},
        approval_id=23, issue_id=78901, commit=False)

    self.mox.ReplayAll()
    self.services.issue._UpdateIssueApprovalStatus(
        self.cnxn, 78901, av.approval_id, av.status,
        av.setter_id, av.set_on)
    self.mox.VerifyAll()

  def testUpdateIssueApprovalApprovers(self):
    self.services.issue.issueapproval2approver_tbl.Delete(
        self.cnxn, issue_id=78901, approval_id=23, commit=False)
    self.services.issue.issueapproval2approver_tbl.InsertRows(
        self.cnxn, issue_svc.ISSUEAPPROVAL2APPROVER_COLS,
        [(23, 111, 78901), (23, 222, 78901), (23, 444, 78901)], commit=False)

    self.mox.ReplayAll()
    self.services.issue._UpdateIssueApprovalApprovers(
        self.cnxn, 78901, 23, [111, 222, 444])
    self.mox.VerifyAll()

  ### Attachments

  def testGetAttachmentAndContext(self):
    # TODO(jrobbins): re-implemnent to use Google Cloud Storage.
    pass

  def SetUpUpdateAttachment(self, comment_id, attachment_id, delta):
    self.services.issue.attachment_tbl.Update(
        self.cnxn, delta, id=attachment_id)
    self.services.issue.comment_2lc.InvalidateKeys(
        self.cnxn, [comment_id])


  def testUpdateAttachment(self):
    delta = {
        'filename': 'a_filename',
        'filesize': 1024,
        'mimetype': 'text/plain',
        'deleted': False,
        }
    self.SetUpUpdateAttachment(5678, 1234, delta)
    self.mox.ReplayAll()
    attach = tracker_pb2.Attachment(
        attachment_id=1234, filename='a_filename', filesize=1024,
        mimetype='text/plain')
    comment = tracker_pb2.IssueComment(id=5678)
    self.services.issue._UpdateAttachment(self.cnxn, comment, attach)
    self.mox.VerifyAll()

  def testStoreAttachmentBlob(self):
    # TODO(jrobbins): re-implemnent to use Google Cloud Storage.
    pass

  def testSoftDeleteAttachment(self):
    issue = fake.MakeTestIssue(789, 1, 'sum', 'New', 111, issue_id=78901)
    issue.assume_stale = False
    issue.attachment_count = 1

    comment = tracker_pb2.IssueComment(
        project_id=789, content='soon to be deleted', user_id=111,
        issue_id=issue.issue_id)
    attachment = tracker_pb2.Attachment(
        attachment_id=1234)
    comment.attachments.append(attachment)

    self.SetUpUpdateAttachment(179901, 1234, {'deleted': True})
    self.SetUpUpdateIssues(given_delta={'attachment_count': 0})
    self.SetUpEnqueueIssuesForIndexing([78901])

    self.mox.ReplayAll()
    self.services.issue.SoftDeleteAttachment(
        self.cnxn, issue, comment, 1234, self.services.user)
    self.mox.VerifyAll()

  ### Reindex queue

  def SetUpEnqueueIssuesForIndexing(self, issue_ids):
    reindex_rows = [(issue_id,) for issue_id in issue_ids]
    self.services.issue.reindexqueue_tbl.InsertRows(
        self.cnxn, ['issue_id'], reindex_rows, ignore=True)

  def testEnqueueIssuesForIndexing(self):
    self.SetUpEnqueueIssuesForIndexing([78901])
    self.mox.ReplayAll()
    self.services.issue.EnqueueIssuesForIndexing(self.cnxn, [78901])
    self.mox.VerifyAll()

  def SetUpReindexIssues(self, issue_ids):
    self.services.issue.reindexqueue_tbl.Select(
        self.cnxn, order_by=[('created', [])],
        limit=50).AndReturn([(issue_id,) for issue_id in issue_ids])

    if issue_ids:
      _issue_1, _issue_2 = self.SetUpGetIssues()
      self.services.issue.reindexqueue_tbl.Delete(
          self.cnxn, issue_id=issue_ids)

  def testReindexIssues_QueueEmpty(self):
    self.SetUpReindexIssues([])
    self.mox.ReplayAll()
    self.services.issue.ReindexIssues(self.cnxn, 50, self.services.user)
    self.mox.VerifyAll()

  def testReindexIssues_QueueHasTwoIssues(self):
    self.SetUpReindexIssues([78901, 78902])
    self.mox.ReplayAll()
    self.services.issue.ReindexIssues(self.cnxn, 50, self.services.user)
    self.mox.VerifyAll()

  ### Search functions

  def SetUpRunIssueQuery(
      self, rows, limit=settings.search_limit_per_shard):
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, distinct=True, cols=['Issue.id'],
        left_joins=[], where=[('Issue.deleted = %s', [False])], order_by=[],
        limit=limit).AndReturn(rows)

  def testRunIssueQuery_NoResults(self):
    self.SetUpRunIssueQuery([])
    self.mox.ReplayAll()
    result_iids, capped = self.services.issue.RunIssueQuery(
      self.cnxn, [], [], [], shard_id=1)
    self.mox.VerifyAll()
    self.assertEqual([], result_iids)
    self.assertFalse(capped)

  def testRunIssueQuery_Normal(self):
    self.SetUpRunIssueQuery([(1,), (11,), (21,)])
    self.mox.ReplayAll()
    result_iids, capped = self.services.issue.RunIssueQuery(
      self.cnxn, [], [], [], shard_id=1)
    self.mox.VerifyAll()
    self.assertEqual([1, 11, 21], result_iids)
    self.assertFalse(capped)

  def testRunIssueQuery_Capped(self):
    try:
      orig = settings.search_limit_per_shard
      settings.search_limit_per_shard = 3
      self.SetUpRunIssueQuery([(1,), (11,), (21,)], limit=3)
      self.mox.ReplayAll()
      result_iids, capped = self.services.issue.RunIssueQuery(
        self.cnxn, [], [], [], shard_id=1)
      self.mox.VerifyAll()
      self.assertEqual([1, 11, 21], result_iids)
      self.assertTrue(capped)
    finally:
      settings.search_limit_per_shard = orig

  def SetUpGetIIDsByLabelIDs(self):
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        left_joins=[('Issue2Label ON Issue.id = Issue2Label.issue_id', [])],
        label_id=[123, 456], project_id=789,
        where=[('shard = %s', [1])]
        ).AndReturn([(1,), (2,), (3,)])

  def testGetIIDsByLabelIDs(self):
    self.SetUpGetIIDsByLabelIDs()
    self.mox.ReplayAll()
    iids = self.services.issue.GetIIDsByLabelIDs(self.cnxn, [123, 456], 789, 1)
    self.mox.VerifyAll()
    self.assertEqual([1, 2, 3], iids)

  def SetUpGetIIDsByParticipant(self):
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        reporter_id=[111, 888],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789])]
        ).AndReturn([(1,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        owner_id=[111, 888],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789])]
        ).AndReturn([(2,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        derived_owner_id=[111, 888],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789])]
        ).AndReturn([(3,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['id'],
        left_joins=[('Issue2Cc ON Issue2Cc.issue_id = Issue.id', [])],
        cc_id=[111, 888],
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789]),
               ('cc_id IS NOT NULL', [])]
        ).AndReturn([(4,)])
    self.services.issue.issue_tbl.Select(
        self.cnxn, shard_id=1, cols=['Issue.id'],
        left_joins=[
            ('Issue2FieldValue ON Issue.id = Issue2FieldValue.issue_id', []),
            ('FieldDef ON Issue2FieldValue.field_id = FieldDef.id', [])],
        user_id=[111, 888], grants_perm='View',
        where=[('shard = %s', [1]), ('Issue.project_id IN (%s)', [789]),
               ('user_id IS NOT NULL', [])]
        ).AndReturn([(5,)])

  def testGetIIDsByParticipant(self):
    self.SetUpGetIIDsByParticipant()
    self.mox.ReplayAll()
    iids = self.services.issue.GetIIDsByParticipant(
        self.cnxn, [111, 888], [789], 1)
    self.mox.VerifyAll()
    self.assertEqual([1, 2, 3, 4, 5], iids)

  ### Issue Dependency reranking

  def testSortBlockedOn(self):
    issue = self.SetUpSortBlockedOn()
    self.mox.ReplayAll()
    ret = self.services.issue.SortBlockedOn(
        self.cnxn, issue, issue.blocked_on_iids)
    self.mox.VerifyAll()
    self.assertEqual(ret, ([78902, 78903], [20, 10]))

  def SetUpSortBlockedOn(self):
    issue = fake.MakeTestIssue(
        project_id=789, local_id=1, owner_id=111, summary='sum',
        status='Live', issue_id=78901)
    issue.project_name = 'proj'
    issue.blocked_on_iids = [78902, 78903]
    issue.blocked_on_ranks = [20, 10]
    self.services.issue.issue_2lc.CacheItem(78901, issue)
    blocked_on_rows = (
        (78901, 78902, 'blockedon', 20), (78901, 78903, 'blockedon', 10))
    self.services.issue.issuerelation_tbl.Select(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS,
        issue_id=issue.issue_id, dst_issue_id=issue.blocked_on_iids,
        kind='blockedon',
        order_by=[('rank DESC', []), ('dst_issue_id', [])]).AndReturn(
            blocked_on_rows)
    return issue

  def testApplyIssueRerank(self):
    blocker_ids = [78902, 78903]
    relations_to_change = list(zip(blocker_ids, [20, 10]))
    self.services.issue.issuerelation_tbl.Delete(
        self.cnxn, issue_id=78901, dst_issue_id=blocker_ids, commit=False)
    insert_rows = [(78901, blocker_id, 'blockedon', rank)
                   for blocker_id, rank in relations_to_change]
    self.services.issue.issuerelation_tbl.InsertRows(
        self.cnxn, cols=issue_svc.ISSUERELATION_COLS, row_values=insert_rows,
        commit=True)

    self.mox.StubOutWithMock(self.services.issue, "InvalidateIIDs")

    self.services.issue.InvalidateIIDs(self.cnxn, [78901])
    self.mox.ReplayAll()
    self.services.issue.ApplyIssueRerank(self.cnxn, 78901, relations_to_change)
    self.mox.VerifyAll()

  def testExpungeUsersInIssues(self):
    comment_id_rows = [(12, 78901, 112), (13, 78902, 113)]
    comment_ids = [12, 13]
    content_ids = [112, 113]
    self.services.issue.comment_tbl.Select = Mock(
        return_value=comment_id_rows)
    self.services.issue.commentcontent_tbl.Update = Mock()
    self.services.issue.comment_tbl.Update = Mock()

    fv_issue_id_rows = [(78902,), (78903,), (78904,)]
    self.services.issue.issue2fieldvalue_tbl.Select = Mock(
        return_value=fv_issue_id_rows)
    self.services.issue.issue2fieldvalue_tbl.Delete = Mock()
    self.services.issue.issueapproval2approver_tbl.Delete = Mock()
    self.services.issue.issue2approvalvalue_tbl.Update = Mock()

    self.services.issue.issueupdate_tbl.Update = Mock()

    self.services.issue.issue2notify_tbl.Delete = Mock()

    cc_issue_id_rows = [(78904,), (78905,), (78906,)]
    self.services.issue.issue2cc_tbl.Select = Mock(
        return_value=cc_issue_id_rows)
    self.services.issue.issue2cc_tbl.Delete = Mock()
    owner_issue_id_rows = [(78907,), (78908,), (78909,)]
    derived_owner_issue_id_rows = [(78910,), (78911,), (78912,)]
    reporter_issue_id_rows = [(78912,), (78913,)]
    self.services.issue.issue_tbl.Select = Mock(
        side_effect=[owner_issue_id_rows, derived_owner_issue_id_rows,
                     reporter_issue_id_rows])
    self.services.issue.issue_tbl.Update = Mock()

    self.services.issue.issuesnapshot_tbl.Update = Mock()
    self.services.issue.issuesnapshot2cc_tbl.Delete = Mock()

    emails = ['cow@farm.com', 'pig@farm.com', 'chicken@farm.com']
    user_ids = [222, 888, 444]
    user_ids_by_email = {
        email: user_id for user_id, email in zip(user_ids, emails)}
    commit = False
    limit = 50

    affected_user_ids = self.services.issue.ExpungeUsersInIssues(
        self.cnxn, user_ids_by_email, limit=limit)
    self.assertItemsEqual(
        affected_user_ids,
        [78901, 78902, 78903, 78904, 78905, 78906, 78907, 78908, 78909,
         78910, 78911, 78912, 78913])

    self.services.issue.comment_tbl.Select.assert_called_once()
    _cnxn, kwargs = self.services.issue.comment_tbl.Select.call_args
    self.assertEqual(
        kwargs['cols'], ['Comment.id', 'Comment.issue_id', 'commentcontent_id'])
    self.assertItemsEqual(kwargs['commenter_id'], user_ids)
    self.assertEqual(kwargs['limit'], limit)

    # since user_ids are passed to ExpungeUsersInIssues via a dictionary,
    # we cannot know the order of the user_ids list that the method
    # ends up using. To be able to use assert_called_with()
    # rather than extract call_args, we are saving the order of user_ids
    # used by the method after confirming that it has the correct items.
    user_ids = kwargs['commenter_id']

    self.services.issue.commentcontent_tbl.Update.assert_called_once_with(
        self.cnxn, {'inbound_message': None}, id=content_ids, commit=commit)
    self.assertEqual(
        len(self.services.issue.comment_tbl.Update.call_args_list), 2)
    self.services.issue.comment_tbl.Update.assert_any_call(
        self.cnxn, {'commenter_id': framework_constants.DELETED_USER_ID},
        id=comment_ids, commit=False)
    self.services.issue.comment_tbl.Update.assert_any_call(
        self.cnxn, {'deleted_by': framework_constants.DELETED_USER_ID},
        deleted_by=user_ids, commit=False, limit=limit)

    # field values
    self.services.issue.issue2fieldvalue_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['issue_id'], user_id=user_ids, limit=limit)
    self.services.issue.issue2fieldvalue_tbl.Delete.assert_called_once_with(
        self.cnxn, user_id=user_ids, limit=limit, commit=commit)

    # approval values
    self.services.issue.issueapproval2approver_tbl.\
Delete.assert_called_once_with(
        self.cnxn, approver_id=user_ids, commit=commit, limit=limit)
    self.services.issue.issue2approvalvalue_tbl.Update.assert_called_once_with(
        self.cnxn, {'setter_id': framework_constants.DELETED_USER_ID},
        setter_id=user_ids, commit=commit, limit=limit)

    # issue ccs
    self.services.issue.issue2cc_tbl.Select.assert_called_once_with(
        self.cnxn, cols=['issue_id'], cc_id=user_ids, limit=limit)
    self.services.issue.issue2cc_tbl.Delete.assert_called_once_with(
        self.cnxn, cc_id=user_ids, limit=limit, commit=commit)

    # issue owners
    self.services.issue.issue_tbl.Select.assert_any_call(
        self.cnxn, cols=['id'], owner_id=user_ids, limit=limit)
    self.services.issue.issue_tbl.Update.assert_any_call(
        self.cnxn, {'owner_id': None},
        id=[row[0] for row in owner_issue_id_rows], commit=commit)
    self.services.issue.issue_tbl.Select.assert_any_call(
        self.cnxn, cols=['id'], derived_owner_id=user_ids, limit=limit)
    self.services.issue.issue_tbl.Update.assert_any_call(
        self.cnxn, {'derived_owner_id': None},
        id=[row[0] for row in derived_owner_issue_id_rows], commit=commit)

    # issue reporter
    self.services.issue.issue_tbl.Select.assert_any_call(
        self.cnxn, cols=['id'], reporter_id=user_ids, limit=limit)
    self.services.issue.issue_tbl.Update.assert_any_call(
        self.cnxn, {'reporter_id': framework_constants.DELETED_USER_ID},
        id=[row[0] for row in reporter_issue_id_rows], commit=commit)

    self.assertEqual(
        3, len(self.services.issue.issue_tbl.Update.call_args_list))

    # issue updates
    self.services.issue.issueupdate_tbl.Update.assert_any_call(
        self.cnxn, {'added_user_id': framework_constants.DELETED_USER_ID},
        added_user_id=user_ids, commit=commit)
    self.services.issue.issueupdate_tbl.Update.assert_any_call(
        self.cnxn, {'removed_user_id': framework_constants.DELETED_USER_ID},
        removed_user_id=user_ids, commit=commit)
    self.assertEqual(
        2, len(self.services.issue.issueupdate_tbl.Update.call_args_list))

    # issue notify
    call_args_list = self.services.issue.issue2notify_tbl.Delete.call_args_list
    self.assertEqual(1, len(call_args_list))
    _cnxn, kwargs = call_args_list[0]
    self.assertItemsEqual(kwargs['email'], emails)
    self.assertEqual(kwargs['commit'], commit)

    # issue snapshots
    self.services.issue.issuesnapshot_tbl.Update.assert_any_call(
        self.cnxn, {'owner_id': framework_constants.DELETED_USER_ID},
        owner_id=user_ids, commit=commit, limit=limit)
    self.services.issue.issuesnapshot_tbl.Update.assert_any_call(
        self.cnxn, {'reporter_id': framework_constants.DELETED_USER_ID},
        reporter_id=user_ids, commit=commit, limit=limit)
    self.assertEqual(
        2, len(self.services.issue.issuesnapshot_tbl.Update.call_args_list))

    self.services.issue.issuesnapshot2cc_tbl.Delete.assert_called_once_with(
        self.cnxn, cc_id=user_ids, commit=commit, limit=limit)


class IssueServiceFunctionsTest(unittest.TestCase):

  def testUpdateClosedTimestamp(self):
    config = tracker_pb2.ProjectIssueConfig()
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='New', means_open=True))
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='Accepted', means_open=True))
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='Old', means_open=False))
    config.well_known_statuses.append(tracker_pb2.StatusDef(
        status='Closed', means_open=False))

    issue = tracker_pb2.Issue()
    issue.local_id = 1234
    issue.status = 'New'

    # ensure the default value is undef
    self.assertTrue(not issue.closed_timestamp)

    # ensure transitioning to the same and other open states
    # doesn't set the timestamp
    issue.status = 'New'
    issue_svc._UpdateClosedTimestamp(config, issue, 'New')
    self.assertTrue(not issue.closed_timestamp)

    issue.status = 'Accepted'
    issue_svc._UpdateClosedTimestamp(config, issue, 'New')
    self.assertTrue(not issue.closed_timestamp)

    # ensure transitioning from open to closed sets the timestamp
    issue.status = 'Closed'
    issue_svc._UpdateClosedTimestamp(config, issue, 'Accepted')
    self.assertTrue(issue.closed_timestamp)

    # ensure that the timestamp is cleared when transitioning from
    # closed to open
    issue.status = 'New'
    issue_svc._UpdateClosedTimestamp(config, issue, 'Closed')
    self.assertTrue(not issue.closed_timestamp)
