# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for the ast2select module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import time
import unittest

from framework import sql
from proto import ast_pb2
from proto import tracker_pb2
from search import ast2select
from search import query2ast
from tracker import tracker_bizobj


BUILTIN_ISSUE_FIELDS = query2ast.BUILTIN_ISSUE_FIELDS
ANY_FIELD = query2ast.BUILTIN_ISSUE_FIELDS['any_field']


class AST2SelectTest(unittest.TestCase):

  def setUp(self):
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(789)

  def testBuildSQLQuery_EmptyAST(self):
    ast = ast_pb2.QueryAST(conjunctions=[ast_pb2.Conjunction()])  # No conds
    left_joins, where, unsupported = ast2select.BuildSQLQuery(ast)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([], unsupported)

  def testBuildSQLQuery_Normal(self):
    owner_field = BUILTIN_ISSUE_FIELDS['owner']
    reporter_id_field = BUILTIN_ISSUE_FIELDS['reporter_id']
    conds = [
        ast_pb2.MakeCond(
            ast_pb2.QueryOp.TEXT_HAS, [owner_field], ['example.com'], []),
        ast_pb2.MakeCond(
            ast_pb2.QueryOp.EQ, [reporter_id_field], [], [111])]
    ast = ast_pb2.QueryAST(conjunctions=[ast_pb2.Conjunction(conds=conds)])
    left_joins, where, unsupported = ast2select.BuildSQLQuery(ast)
    self.assertEqual(
        [('User AS Cond0 ON (Issue.owner_id = Cond0.user_id '
          'OR Issue.derived_owner_id = Cond0.user_id)', [])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('(LOWER(Cond0.email) LIKE %s)', ['%example.com%']),
         ('Issue.reporter_id = %s', [111])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockingIDCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
          'Cond1.kind = %s AND Cond1.issue_id = %s',
          ['blockedon', 1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.dst_issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockingIDCond_NegatedSingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
          'Cond1.kind = %s AND Cond1.issue_id = %s',
          ['blockedon', 1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.dst_issue_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockingIDCond_MultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1, 2, 3])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
          'Cond1.kind = %s AND Cond1.issue_id IN (%s,%s,%s)',
          ['blockedon', 1, 2, 3])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.dst_issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockingIDCond_NegatedMultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1, 2, 3])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
          'Cond1.kind = %s AND Cond1.issue_id IN (%s,%s,%s)',
          ['blockedon', 1, 2, 3])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.dst_issue_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockingIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['b/1'], [])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        txt_cond, 'Cond1', 'Issue1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([txt_cond], unsupported)

  def testBlockingIDCond_ExtIssues(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    ne_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], ['b/1', 'b/2'], [])
    eq_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['b/1', 'b/2'], [])

    for cond, where_str in [(eq_cond, 'DIR.issue_id IS NOT NULL'),
      (ne_cond, 'DIR.issue_id IS NULL')]:
      left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
          cond, 'DIR', 'Issue1', snapshot_mode=False)
      self.assertEqual(
          [('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
            'DIR.kind = %s AND DIR.ext_issue_identifier IN (%s,%s)',
            ['blocking', 'b/1', 'b/2'])],
          left_joins)
      self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
      self.assertEqual(
          [(where_str, [])],
          where)
      self.assertTrue(sql._IsValidWhereCond(where[0][0]))
      self.assertEqual([], unsupported)

  def testBlockingIDCond_CombinedIssues(self):
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['b/1', 'b/2'], [1, 2])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        ('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
          'Cond1.kind = %s AND Cond1.issue_id IN (%s,%s)',
          ['blockedon', 1, 2]), left_joins[0])
    self.assertEqual(
         ('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
          'DIR.kind = %s AND DIR.ext_issue_identifier IN (%s,%s)',
          ['blocking', 'b/1', 'b/2']), left_joins[1])
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertTrue(sql._IsValidJoin(left_joins[1][0]))
    self.assertEqual(
        [('Cond1.dst_issue_id IS NOT NULL', []),
        ('DIR.issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertTrue(sql._IsValidWhereCond(where[1][0]))
    self.assertEqual([], unsupported)

  def testBlockedOnIDCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1])

    left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.kind = %s AND Cond1.dst_issue_id = %s',
          ['blockedon', 1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockedOnIDCond_NegatedSingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1])

    left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.kind = %s AND Cond1.dst_issue_id = %s',
          ['blockedon', 1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.issue_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockedOnIDCond_MultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1, 2, 3])

    left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.kind = %s AND Cond1.dst_issue_id IN (%s,%s,%s)',
          ['blockedon', 1, 2, 3])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockedOnIDCond_NegatedMultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1, 2, 3])

    left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.kind = %s AND Cond1.dst_issue_id IN (%s,%s,%s)',
          ['blockedon', 1, 2, 3])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.issue_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testBlockedOnIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['b/1'], [])

    left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
        txt_cond, 'Cond1', 'Issue1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([txt_cond], unsupported)

  def testBlockedOnIDCond_ExtIssues(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    eq_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['b/1', 'b/2'], [])
    ne_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], ['b/1', 'b/2'], [])

    for cond, where_str in [(eq_cond, 'DIR.issue_id IS NOT NULL'),
      (ne_cond, 'DIR.issue_id IS NULL')]:
      left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
          cond, 'DIR', 'Issue1', snapshot_mode=False)
      self.assertEqual(
          [('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
            'DIR.kind = %s AND DIR.ext_issue_identifier IN (%s,%s)',
            ['blockedon', 'b/1', 'b/2'])],
          left_joins)
      self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
      self.assertEqual(
          [(where_str, [])],
          where)
      self.assertTrue(sql._IsValidWhereCond(where[0][0]))
      self.assertEqual([], unsupported)

  def testBlockedOnIDCond_CombinedIssues(self):
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['b/1', 'b/2'], [1, 2])

    left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        ('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.kind = %s AND Cond1.dst_issue_id IN (%s,%s)',
          ['blockedon', 1, 2]), left_joins[0])
    self.assertEqual(
         ('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
          'DIR.kind = %s AND DIR.ext_issue_identifier IN (%s,%s)',
          ['blockedon', 'b/1', 'b/2']), left_joins[1])
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertTrue(sql._IsValidJoin(left_joins[1][0]))
    self.assertEqual(
        [('Cond1.issue_id IS NOT NULL', []),
        ('DIR.issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertTrue(sql._IsValidWhereCond(where[1][0]))
    self.assertEqual([], unsupported)

  def testMergedIntoIDCond_MultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['mergedinto_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1, 2, 3])

    left_joins, where, unsupported = ast2select._ProcessMergedIntoIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.kind = %s AND Cond1.dst_issue_id IN (%s,%s,%s)',
          ['mergedinto', 1, 2, 3])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testMergedIntoIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['mergedinto_id']
    txt_cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['b/1', 'b/2', 'b/3'], [])

    left_joins, where, unsupported = ast2select._ProcessMergedIntoIDCond(
        txt_cond, 'Cond1', 'Issue1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([txt_cond], unsupported)

  def testMergedIntoIDCond_ExtIssues(self):
    fd = BUILTIN_ISSUE_FIELDS['mergedinto_id']
    eq_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['b/1', 'b/2'], [])
    ne_cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], ['b/1', 'b/2'], [])

    for cond, expected in [(eq_cond, ['b/1', 'b/2']),
      (ne_cond, ['b/1', 'b/2'])]:
      left_joins, where, unsupported = ast2select._ProcessMergedIntoIDCond(
          cond, 'Cond1', 'Issue1', snapshot_mode=False)
      self.assertEqual(
          [('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
            'DIR.kind = %s AND DIR.ext_issue_identifier IN (%s,%s)',
            ['mergedinto'] + expected)],
          left_joins)
      self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
      self.assertTrue(sql._IsValidWhereCond(where[0][0]))
      self.assertEqual([], unsupported)

  def testMergedIntoIDCond_CombinedIssues(self):
    fd = BUILTIN_ISSUE_FIELDS['mergedinto_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['b/1', 'b/2'], [1, 2])

    left_joins, where, unsupported = ast2select._ProcessMergedIntoIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=False)
    self.assertEqual(
        [('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.kind = %s AND Cond1.dst_issue_id IN (%s,%s)',
          ['mergedinto', 1, 2]),
         ('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
          'DIR.kind = %s AND DIR.ext_issue_identifier IN (%s,%s)',
          ['mergedinto', 'b/1', 'b/2'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.issue_id IS NOT NULL', []),
        ('DIR.issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testHasBlockedCond(self):
    for op, expected in ((ast_pb2.QueryOp.IS_DEFINED, 'IS NOT NULL'),
                         (ast_pb2.QueryOp.IS_NOT_DEFINED, 'IS NULL')):
      fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
      cond = ast_pb2.MakeCond(op, [fd], [], [])

      left_joins, where, unsupported = ast2select._ProcessBlockedOnIDCond(
          cond, 'Cond1', None, snapshot_mode=False)
      self.assertEqual(
          ('IssueRelation AS Cond1 ON Issue.id = Cond1.issue_id AND '
            'Cond1.kind = %s', ['blockedon']),
          left_joins[0])
      self.assertEqual(
          ('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
            'DIR.kind = %s', ['blockedon']),
          left_joins[1])
      self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
      self.assertTrue(sql._IsValidJoin(left_joins[1][0]))
      self.assertEqual([('(Cond1.issue_id %s OR DIR.issue_id %s)'
          % (expected, expected), [])], where)
      self.assertTrue(sql._IsValidWhereCond(where[0][0]))
      self.assertEqual([], unsupported)

  def testHasBlockedCond_SnapshotMode(self):
    op = ast_pb2.QueryOp.IS_DEFINED
    fd = BUILTIN_ISSUE_FIELDS['blockedon_id']
    cond = ast_pb2.MakeCond(op, [fd], [], [])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testHasBlockingCond(self):
    for op, expected in ((ast_pb2.QueryOp.IS_DEFINED, 'IS NOT NULL'),
                         (ast_pb2.QueryOp.IS_NOT_DEFINED, 'IS NULL')):
      fd = BUILTIN_ISSUE_FIELDS['blocking_id']
      cond = ast_pb2.MakeCond(op, [fd], [], [])

      left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(cond,
          'Cond1', None, snapshot_mode=False)
      self.assertEqual(
          ('IssueRelation AS Cond1 ON Issue.id = Cond1.dst_issue_id AND '
            'Cond1.kind = %s', ['blockedon']),
          left_joins[0])
      self.assertEqual(
          ('DanglingIssueRelation AS DIR ON Issue.id = DIR.issue_id AND '
            'DIR.kind = %s', ['blocking']),
          left_joins[1])
      self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
      self.assertTrue(sql._IsValidJoin(left_joins[1][0]))
      self.assertEqual([('(Cond1.dst_issue_id %s OR DIR.issue_id %s)'
          % (expected, expected), [])], where)
      self.assertTrue(sql._IsValidWhereCond(where[0][0]))
      self.assertEqual([], unsupported)

  def testHasBlockingCond_SnapshotMode(self):
    op = ast_pb2.QueryOp.IS_DEFINED
    fd = BUILTIN_ISSUE_FIELDS['blocking_id']
    cond = ast_pb2.MakeCond(op, [fd], [], [])

    left_joins, where, unsupported = ast2select._ProcessBlockingIDCond(
        cond, 'Cond1', 'Issue1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessOwnerCond(self):
    fd = BUILTIN_ISSUE_FIELDS['owner']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessOwnerCond(cond, 'Cond1',
        'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('User AS Cond1 ON (Issue.owner_id = Cond1.user_id '
          'OR Issue.derived_owner_id = Cond1.user_id)', [])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('(LOWER(Cond1.email) LIKE %s)', ['%example.com%'])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessOwnerCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['owner']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessOwnerCond(cond, 'Cond1',
        'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('User AS Cond1 ON IssueSnapshot.owner_id = Cond1.user_id', [])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('(LOWER(Cond1.email) LIKE %s)', ['%example.com%'])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessOwnerIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['owner_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessOwnerIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.owner_id = %s OR Issue.derived_owner_id = %s)',
          [111, 111])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessOwnerIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['owner_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessOwnerIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([('IssueSnapshot.owner_id = %s', [111])], where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessOwnerLastVisitCond(self):
    fd = BUILTIN_ISSUE_FIELDS['ownerlastvisit']
    NOW = 1234567890
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.LT, [fd], [], [NOW])
    left_joins, where, unsupported = ast2select._ProcessOwnerLastVisitCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('User AS Cond1 ON (Issue.owner_id = Cond1.user_id OR '
          'Issue.derived_owner_id = Cond1.user_id)',
          [])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.last_visit_timestamp < %s',
          [NOW])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessOwnerLastVisitCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['ownerlastvisit']
    NOW = 1234567890
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.LT, [fd], [], [NOW])
    left_joins, where, unsupported = ast2select._ProcessOwnerLastVisitCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessIsOwnerBouncing(self):
    fd = BUILTIN_ISSUE_FIELDS['ownerbouncing']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [])
    left_joins, where, unsupported = ast2select._ProcessIsOwnerBouncing(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('User AS Cond1 ON (Issue.owner_id = Cond1.user_id OR '
          'Issue.derived_owner_id = Cond1.user_id)',
          [])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('(Cond1.email_bounce_timestamp IS NOT NULL AND'
          ' Cond1.email_bounce_timestamp != %s)',
          [0])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessIsOwnerBouncing_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['ownerbouncing']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [])
    left_joins, where, unsupported = ast2select._ProcessIsOwnerBouncing(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessReporterCond(self):
    fd = BUILTIN_ISSUE_FIELDS['reporter']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessReporterCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('User AS Cond1 ON Issue.reporter_id = Cond1.user_id', [])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('(LOWER(Cond1.email) LIKE %s)', ['%example.com%'])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessReporterCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['reporter']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessReporterCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('User AS Cond1 ON IssueSnapshot.reporter_id = Cond1.user_id', [])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('(LOWER(Cond1.email) LIKE %s)', ['%example.com%'])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessReporterIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['reporter_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessReporterIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('Issue.reporter_id = %s', [111])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessReporterIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['reporter_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessReporterIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('IssueSnapshot.reporter_id = %s', [111])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_SinglePositive(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND (LOWER(Spare1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%example.com%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_SinglePositive_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('(IssueSnapshot2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND (LOWER(Spare1.email) LIKE %s)) '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id',
          ['%example.com%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_MultiplePositive(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['.com', '.org'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND '
          '(LOWER(Spare1.email) LIKE %s OR LOWER(Spare1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%.com%', '%.org%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_MultiplePositive_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['.com', '.org'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('(IssueSnapshot2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND '
          '(LOWER(Spare1.email) LIKE %s OR LOWER(Spare1.email) LIKE %s)) '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id',
          ['%.com%', '%.org%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_SingleNegative(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND (LOWER(Spare1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%example.com%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_SingleNegative_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('(IssueSnapshot2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND (LOWER(Spare1.email) LIKE %s)) '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id',
          ['%example.com%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_Multiplenegative(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [fd], ['.com', '.org'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('(Issue2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND '
          '(LOWER(Spare1.email) LIKE %s OR LOWER(Spare1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Issue.shard = Cond1.issue_shard',
          ['%.com%', '%.org%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcCond_Multiplenegative_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['cc']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [fd], ['.com', '.org'], [])
    left_joins, where, unsupported = ast2select._ProcessCcCond(cond, 'Cond1',
        'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('(IssueSnapshot2Cc AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.cc_id = Spare1.user_id AND '
          '(LOWER(Spare1.email) LIKE %s OR LOWER(Spare1.email) LIKE %s)) '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id',
          ['%.com%', '%.org%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['cc_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessCcIDCond(cond, 'Cond1',
        'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2Cc AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.cc_id = %s',
         [111])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.cc_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCcIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['cc_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessCcIDCond(cond, 'Cond1',
        'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('IssueSnapshot2Cc AS Cond1 '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id '
          'AND Cond1.cc_id = %s',
         [111])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.cc_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessStarredByCond(self):
    fd = BUILTIN_ISSUE_FIELDS['starredby']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessStarredByCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('(IssueStar AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.user_id = Spare1.user_id AND '
          '(LOWER(Spare1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id', ['%example.com%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessStarredByCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['starredby']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessStarredByCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessStarredByIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['starredby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessStarredByIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('IssueStar AS Cond1 ON Issue.id = Cond1.issue_id '
          'AND Cond1.user_id = %s', [111])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.user_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessStarredByIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['starredby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessStarredByIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessCommentByCond(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessCommentByCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('(Comment AS Cond1 JOIN User AS Spare1 '
          'ON Cond1.commenter_id = Spare1.user_id '
          'AND (LOWER(Spare1.email) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id AND Cond1.deleted_by IS NULL',
          ['%example.com%'])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Spare1.email IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCommentByCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.TEXT_HAS, [fd], ['example.com'], [])
    left_joins, where, unsupported = ast2select._ProcessCommentByCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessCommentByIDCond_EqualsUserID(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessCommentByIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Comment AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.commenter_id = %s AND Cond1.deleted_by IS NULL',
          [111])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.commenter_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCommentByIDCond_EqualsUserID_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessCommentByIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessCommentByIDCond_QuickOr(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [111, 222])
    left_joins, where, unsupported = ast2select._ProcessCommentByIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Comment AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.commenter_id IN (%s,%s) '
          'AND Cond1.deleted_by IS NULL',
          [111, 222])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.commenter_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCommentByIDCond_NotEqualsUserID(self):
    fd = BUILTIN_ISSUE_FIELDS['commentby_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [111])
    left_joins, where, unsupported = ast2select._ProcessCommentByIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Comment AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.commenter_id = %s AND Cond1.deleted_by IS NULL',
          [111])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.commenter_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessStatusIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['status_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [2])
    left_joins, where, unsupported = ast2select._ProcessStatusIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.status_id = %s OR Issue.derived_status_id = %s)', [2, 2])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessStatusIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['status_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [2])
    left_joins, where, unsupported = ast2select._ProcessStatusIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([('IssueSnapshot.status_id = %s', [2])], where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessSummaryCond(self):
    fd = BUILTIN_ISSUE_FIELDS['summary']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['sum'], [])
    left_joins, where, unsupported = ast2select._ProcessSummaryCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('IssueSummary AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.summary = %s', ['sum'])],
        left_joins)
    self.assertEqual(
        [('Cond1.issue_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessSummaryCond_SnapshotMode(self):
    """Issue summary is not currently included in issue snapshot, so ignore."""
    fd = BUILTIN_ISSUE_FIELDS['summary']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['sum'], [])
    left_joins, where, unsupported = ast2select._ProcessSummaryCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessLabelIDCond_NoValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [])
    with self.assertRaises(ast2select.NoPossibleResults):
      ast2select._ProcessLabelIDCond(cond, 'Cond1', 'Spare1',
          snapshot_mode=False)

  def testProcessLabelIDCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1])
    left_joins, where, unsupported = ast2select._ProcessLabelIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id = %s', [1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.label_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessLabelIDCond_SingleValue_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1])
    left_joins, where, unsupported = ast2select._ProcessLabelIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('IssueSnapshot2Label AS Cond1 '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id AND '
          'Cond1.label_id = %s', [1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.label_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessLabelIDCond_MultipleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1, 2])
    left_joins, where, unsupported = ast2select._ProcessLabelIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.label_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessLabelIDCond_NegatedNoValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [])
    left_joins, where, unsupported = ast2select._ProcessLabelIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([], unsupported)

  def testProcessLabelIDCond_NegatedSingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1])
    left_joins, where, unsupported = ast2select._ProcessLabelIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id = %s', [1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.label_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessLabelIDCond_NegatedSingleValue_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1])
    left_joins, where, unsupported = ast2select._ProcessLabelIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('IssueSnapshot2Label AS Cond1 '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id AND '
          'Cond1.label_id = %s', [1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.label_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessLabelIDCond_NegatedMultipleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['label_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1, 2])
    left_joins, where, unsupported = ast2select._ProcessLabelIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2Label AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.label_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.label_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessComponentIDCond(self):
    fd = BUILTIN_ISSUE_FIELDS['component_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [101])
    left_joins, where, unsupported = ast2select._ProcessComponentIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2Component AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.component_id = %s', [101])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.component_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessComponentIDCond_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['component_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [101])
    left_joins, where, unsupported = ast2select._ProcessComponentIDCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('IssueSnapshot2Component AS Cond1 '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id AND '
          'Cond1.component_id = %s', [101])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.component_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessApprovalFieldCond_Status(self):
    approval_fd = tracker_pb2.FieldDef(
        field_id=1, field_name='UXReview',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [approval_fd], ['Approved'], [],
        key_suffix=query2ast.STATUS_SUFFIX)
    left_joins, where, _unsupported = ast2select._ProcessApprovalFieldCond(
        cond, 'Cond1', 'Spare1', False)
    self.assertEqual(
        [('Issue2ApprovalValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.approval_id = %s AND LOWER(Cond1.status) = %s',
          [1, 'approved'])],
        left_joins)
    self.assertEqual(
        [('Cond1.approval_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))

  def testProcessApprovalFieldCond_SetOn(self):
    approval_fd = tracker_pb2.FieldDef(
        field_id=1, field_name='UXReview',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    int_time = int(time.mktime(datetime.datetime(2016, 10, 5).timetuple()))
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [approval_fd], [], [int_time],
        key_suffix=query2ast.SET_ON_SUFFIX)
    left_joins, where, _unsupported = ast2select._ProcessApprovalFieldCond(
        cond, 'Cond1', 'Spare1', False)
    self.assertEqual(
        [('Issue2ApprovalValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.approval_id = %s AND Cond1.set_on = %s',
          [1, int_time])],
        left_joins)
    self.assertEqual(
        [('Cond1.approval_id IS NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))

  def testProcessApprovalFieldCond_SetBy(self):
    approval_fd = tracker_pb2.FieldDef(
        field_id=1, field_name='UXReview',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [approval_fd], ['user2@email.com'], [],
        key_suffix=query2ast.SET_BY_SUFFIX)
    left_joins, where, _unsupported = ast2select._ProcessApprovalFieldCond(
        cond, 'Cond1', 'Spare1', False)
    self.assertEqual(
        [('User AS Spare1 ON LOWER(Spare1.email) = %s', ['user2@email.com']),
         ('Issue2ApprovalValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.approval_id = %s AND Cond1.setter_id = Spare1.user_id',
          [1])],
        left_joins)
    self.assertEqual(
        [('Cond1.approval_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))

  def testProcessApprovalFieldCond_ApproverID(self):
    approval_fd = tracker_pb2.FieldDef(
        field_id=1, field_name='UXReview',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [approval_fd], [], [111],
        key_suffix=query2ast.APPROVER_SUFFIX)
    left_joins, where, _unsupported = ast2select._ProcessApprovalFieldCond(
        cond, 'Cond1', 'Spare1', False)
    self.assertEqual(
        [('IssueApproval2Approver AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.approval_id = %s AND Cond1.approver_id = %s',
          [1, 111])], left_joins)
    self.assertEqual(
        [('Cond1.approval_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))


  def testProcessApprovalFieldCond_IsDefined(self):
    approval_fd = tracker_pb2.FieldDef(
        field_id=1, field_name='UXReview',
        field_type=tracker_pb2.FieldTypes.APPROVAL_TYPE)
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.IS_DEFINED, [approval_fd], [], [])
    left_joins, where, _unsupported = ast2select._ProcessApprovalFieldCond(
        cond, 'Cond1', 'Spare1', False)
    self.assertEqual(
        [('Issue2ApprovalValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.approval_id = %s',
          [1])], left_joins)
    self.assertEqual(
        [('Cond1.approval_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))

  def testProcessCustomFieldCond_IntType(self):
    fd = tracker_pb2.FieldDef(
      field_id=1, project_id=789, field_name='EstDays',
      field_type=tracker_pb2.FieldTypes.INT_TYPE)
    val = 42
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [val])
    left_joins, where, unsupported = ast2select._ProcessCustomFieldCond(
        cond, 'Cond1', 'Spare1', 'Phase', snapshot_mode=False)
    self.assertEqual(
        [('Issue2FieldValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.field_id = %s AND '
          'Cond1.int_value = %s', [1, val])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.field_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCustomFieldCond_StrType(self):
    fd = tracker_pb2.FieldDef(
      field_id=1, project_id=789, field_name='Nickname',
      field_type=tracker_pb2.FieldTypes.STR_TYPE)
    val = 'Fuzzy'
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [val], [])
    left_joins, where, unsupported = ast2select._ProcessCustomFieldCond(
        cond, 'Cond1', 'Spare1','Phase1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2FieldValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.field_id = %s AND '
          'Cond1.str_value = %s', [1, val])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.field_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCustomFieldCond_StrType_SnapshotMode(self):
    fd = tracker_pb2.FieldDef(
      field_id=1, project_id=789, field_name='Nickname',
      field_type=tracker_pb2.FieldTypes.STR_TYPE)
    val = 'Fuzzy'
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [val], [])
    left_joins, where, unsupported = ast2select._ProcessCustomFieldCond(
        cond, 'Cond1', 'Spare1', 'Phase1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessCustomFieldCond_UserType_ByID(self):
    fd = tracker_pb2.FieldDef(
      field_id=1, project_id=789, field_name='ExecutiveProducer',
      field_type=tracker_pb2.FieldTypes.USER_TYPE)
    val = 111
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [val])
    left_joins, where, unsupported = ast2select._ProcessCustomFieldCond(
        cond, 'Cond1', 'Spare1', 'Phase1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2FieldValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.field_id = %s AND '
          'Cond1.user_id = %s', [1, val])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.field_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCustomFieldCond_UserType_ByEmail(self):
    fd = tracker_pb2.FieldDef(
      field_id=1, project_id=789, field_name='ExecutiveProducer',
      field_type=tracker_pb2.FieldTypes.USER_TYPE)
    val = 'exec@example.com'
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [val], [])
    left_joins, where, unsupported = ast2select._ProcessCustomFieldCond(
        cond, 'Cond1', 'Spare1', 'Phase1',  snapshot_mode=False)
    self.assertEqual(
        [('User AS Spare1 ON '
          'LOWER(Spare1.email) = %s', [val]),
         ('Issue2FieldValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.field_id = %s AND '
          'Cond1.user_id = Spare1.user_id', [1])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertTrue(sql._IsValidJoin(left_joins[1][0]))
    self.assertEqual(
        [('Cond1.field_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCustomFieldCond_DateType(self):
    fd = tracker_pb2.FieldDef(
      field_id=1, project_id=789, field_name='Deadline',
      field_type=tracker_pb2.FieldTypes.DATE_TYPE)
    val = int(time.mktime(datetime.datetime(2016, 10, 5).timetuple()))
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [val])
    left_joins, where, unsupported = ast2select._ProcessCustomFieldCond(
        cond, 'Cond1', 'Spare1', 'Phase1', snapshot_mode=False)
    self.assertEqual(
        [('Issue2FieldValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Issue.shard = Cond1.issue_shard AND '
          'Cond1.field_id = %s AND '
          'Cond1.date_value = %s', [1, val])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('Cond1.field_id IS NOT NULL', [])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessCustomFieldCond_PhaseName(self):
    fd = tracker_pb2.FieldDef(
      field_id=1, project_id=789, field_name='Milestone',
      field_type=tracker_pb2.FieldTypes.INT_TYPE)
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [72],
                            phase_name='Canary')
    left_joins, where, unsupported = ast2select._ProcessCustomFieldCond(
        cond, 'Cond1', 'User1', 'Phase1', snapshot_mode=False)
    self.assertEqual(
        [('IssuePhaseDef AS Phase1 ON LOWER(Phase1.name) = %s', ['Canary']),
        ('Issue2FieldValue AS Cond1 ON Issue.id = Cond1.issue_id AND '
         'Issue.shard = Cond1.issue_shard AND '
         'Cond1.field_id = %s AND Cond1.int_value = %s AND '
         'Cond1.phase_id = Phase1.id', [1, 72])],
        left_joins)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessAttachmentCond_HasAttachment(self):
    fd = BUILTIN_ISSUE_FIELDS['attachment']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.IS_DEFINED, [fd], [], [])
    left_joins, where, unsupported = ast2select._ProcessAttachmentCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.attachment_count IS NOT NULL AND '
          'Issue.attachment_count != %s)',
          [0])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))

    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.IS_NOT_DEFINED, [fd], [], [])
    left_joins, where, unsupported = ast2select._ProcessAttachmentCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual([], left_joins)
    self.assertEqual(
        [('(Issue.attachment_count IS NULL OR '
          'Issue.attachment_count = %s)',
          [0])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessAttachmentCond_HasAttachment_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['attachment']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.IS_DEFINED, [fd], [], [])
    left_joins, where, unsupported = ast2select._ProcessAttachmentCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual([], left_joins)
    self.assertEqual([], where)
    self.assertEqual([cond], unsupported)

  def testProcessAttachmentCond_TextHas(self):
    fd = BUILTIN_ISSUE_FIELDS['attachment']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.TEXT_HAS, [fd], ['jpg'], [])
    left_joins, where, unsupported = ast2select._ProcessAttachmentCond(
        cond, 'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Attachment AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.deleted = %s',
          [False])],
        left_joins)
    self.assertTrue(sql._IsValidJoin(left_joins[0][0]))
    self.assertEqual(
        [('(Cond1.filename LIKE %s)', ['%jpg%'])],
        where)
    self.assertTrue(sql._IsValidWhereCond(where[0][0]))
    self.assertEqual([], unsupported)

  def testProcessHotlistIDCond_MultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1, 2])
    left_joins, where, unsupported = ast2select._ProcessHotlistIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Hotlist2Issue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.hotlist_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertEqual(
        [('Cond1.hotlist_id IS NOT NULL', [])],
        where)
    self.assertEqual([], unsupported)

  def testProcessHotlistIDCond_MultiValue_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1, 2])
    left_joins, where, unsupported = ast2select._ProcessHotlistIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('IssueSnapshot2Hotlist AS Cond1 '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id AND '
          'Cond1.hotlist_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertEqual(
        [('Cond1.hotlist_id IS NOT NULL', [])],
        where)
    self.assertEqual([], unsupported)

  def testProcessHotlistIDCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], [], [1])
    left_joins, where, unsupported = ast2select._ProcessHotlistIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Hotlist2Issue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.hotlist_id = %s', [1])],
        left_joins)
    self.assertEqual(
        [('Cond1.hotlist_id IS NOT NULL', [])],
        where)
    self.assertEqual([], unsupported)

  def testProcessHotlistIDCond_NegatedMultiValue(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1, 2])
    left_joins, where, unsupported = ast2select._ProcessHotlistIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Hotlist2Issue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.hotlist_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertEqual(
        [('Cond1.hotlist_id IS NULL', [])],
        where)
    self.assertEqual([], unsupported)

  def testProcessHotlistIDCond_NegatedMultiValue_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1, 2])
    left_joins, where, unsupported = ast2select._ProcessHotlistIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('IssueSnapshot2Hotlist AS Cond1 '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id AND '
          'Cond1.hotlist_id IN (%s,%s)', [1, 2])],
        left_joins)
    self.assertEqual(
        [('Cond1.hotlist_id IS NULL', [])],
        where)
    self.assertEqual([], unsupported)

  def testProcessHotlistIDCond_NegatedSingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1])
    left_joins, where, unsupported = ast2select._ProcessHotlistIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
        [('Hotlist2Issue AS Cond1 ON Issue.id = Cond1.issue_id AND '
          'Cond1.hotlist_id = %s', [1])],
        left_joins)
    self.assertEqual(
        [('Cond1.hotlist_id IS NULL', [])],
        where)
    self.assertEqual([], unsupported)

  def testProcessHotlistIDCond_NegatedSingleValue_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist_id']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], [], [1])
    left_joins, where, unsupported = ast2select._ProcessHotlistIDCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
        [('IssueSnapshot2Hotlist AS Cond1 '
          'ON IssueSnapshot.id = Cond1.issuesnapshot_id AND '
          'Cond1.hotlist_id = %s', [1])],
        left_joins)
    self.assertEqual(
        [('Cond1.hotlist_id IS NULL', [])],
        where)
    self.assertEqual([], unsupported)

  def testProcessHotlistCond_SingleValue(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['invalid:spa'], [])
    left_joins, where, unsupported = ast2select._ProcessHotlistCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
      [('(Hotlist2Issue JOIN Hotlist AS Cond1 ON '
        'Hotlist2Issue.hotlist_id = Cond1.id AND (LOWER(Cond1.name) LIKE %s))'
        ' ON Issue.id = Hotlist2Issue.issue_id', ['%spa%'])],
      left_joins)
    self.assertEqual([('Cond1.name IS NOT NULL', [])], where)
    self.assertEqual([], unsupported)

  def testProcessHotlistCond_SingleValue_SnapshotMode(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd], ['invalid:spa'], [])
    left_joins, where, unsupported = ast2select._ProcessHotlistCond(cond,
        'Cond1', 'Spare1', snapshot_mode=True)
    self.assertEqual(
      [('(IssueSnapshot2Hotlist JOIN Hotlist AS Cond1 ON '
        'IssueSnapshot2Hotlist.hotlist_id = Cond1.id '
        'AND (LOWER(Cond1.name) LIKE %s)) '
        'ON IssueSnapshot.id = IssueSnapshot2Hotlist.issuesnapshot_id',
        ['%spa%'])],
      left_joins)
    self.assertEqual([('Cond1.name IS NOT NULL', [])], where)
    self.assertEqual([], unsupported)

  def testProcessHotlistCond_SingleValue2(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.EQ, [fd],
                            ['invalid:spa', 'port', 'invalid2:barc'], [])
    left_joins, where, unsupported = ast2select._ProcessHotlistCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
      [('(Hotlist2Issue JOIN Hotlist AS Cond1 ON '
        'Hotlist2Issue.hotlist_id = Cond1.id AND (LOWER(Cond1.name) LIKE %s OR '
        'LOWER(Cond1.name) LIKE %s OR LOWER(Cond1.name) LIKE %s)) ON '
        'Issue.id = Hotlist2Issue.issue_id', ['%spa%', '%port%', '%barc%'])],
      left_joins)
    self.assertEqual([('Cond1.name IS NOT NULL', [])], where)
    self.assertEqual([], unsupported)

  def testProcessHotlistCond_SingleValue3(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NE, [fd], ['invalid:spa'], [])
    left_joins, where, unsupported = ast2select._ProcessHotlistCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
      [('(Hotlist2Issue JOIN Hotlist AS Cond1 ON '
        'Hotlist2Issue.hotlist_id = Cond1.id AND (LOWER(Cond1.name) LIKE %s))'
        ' ON Issue.id = Hotlist2Issue.issue_id', ['%spa%'])],
      left_joins)
    self.assertEqual([('Cond1.name IS NULL', [])], where)
    self.assertEqual([], unsupported)

  def testProcessHotlistCond_SingleValue4(self):
    fd = BUILTIN_ISSUE_FIELDS['hotlist']
    cond = ast_pb2.MakeCond(ast_pb2.QueryOp.NOT_TEXT_HAS, [fd],
                            ['invalid:spa', 'port', 'invalid2:barc'], [])
    left_joins, where, unsupported = ast2select._ProcessHotlistCond(cond,
        'Cond1', 'Spare1', snapshot_mode=False)
    self.assertEqual(
      [('(Hotlist2Issue JOIN Hotlist AS Cond1 ON '
        'Hotlist2Issue.hotlist_id = Cond1.id AND (LOWER(Cond1.name) LIKE %s OR '
        'LOWER(Cond1.name) LIKE %s OR LOWER(Cond1.name) LIKE %s)) ON '
        'Issue.id = Hotlist2Issue.issue_id', ['%spa%', '%port%', '%barc%'])],
      left_joins)
    self.assertEqual([('Cond1.name IS NULL', [])], where)
    self.assertEqual([], unsupported)

  def testProcessPhaseCond_HasGateEQ(self):
    fd = BUILTIN_ISSUE_FIELDS['gate']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.EQ, [fd], ['canary', 'stable'], [])
    left_joins, where, unsupported = ast2select._ProcessPhaseCond(
        cond, 'Cond1', 'Phase1', False)
    self.assertEqual(
        [('(Issue2ApprovalValue AS Cond1 JOIN IssuePhaseDef AS Phase1 '
          'ON Cond1.phase_id = Phase1.id AND '
          'LOWER(Phase1.name) IN (%s,%s)) '
          'ON Issue.id = Cond1.issue_id', ['canary', 'stable'])],
        left_joins)
    self.assertEqual([('Phase1.name IS NOT NULL', [])], where)
    self.assertEqual([], unsupported)

  def testProcessPhaseCond_NoGateTEXT(self):
    fd = BUILTIN_ISSUE_FIELDS['gate']
    cond = ast_pb2.MakeCond(
        ast_pb2.QueryOp.NOT_TEXT_HAS, [fd], ['canary', 'stable'], [])
    left_joins, where, unsupported = ast2select._ProcessPhaseCond(
        cond, 'Cond1', 'Phase1', False)
    self.assertEqual(
        [('(Issue2ApprovalValue AS Cond1 JOIN IssuePhaseDef AS Phase1 '
          'ON Cond1.phase_id = Phase1.id AND '
          '(LOWER(Phase1.name) LIKE %s '
          'OR LOWER(Phase1.name) LIKE %s)) '
          'ON Issue.id = Cond1.issue_id', ['%canary%', '%stable%'])],
        left_joins)
    self.assertEqual([('Phase1.name IS NULL', [])], where)
    self.assertEqual([], unsupported)

  def testCompare_IntTypes(self):
    val_type = tracker_pb2.FieldTypes.INT_TYPE
    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.IS_DEFINED, val_type, 'col', [1, 2])
    self.assertEqual('(Alias.col IS NOT NULL AND Alias.col != %s)', cond_str)
    self.assertEqual([0], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', [1])
    self.assertEqual('Alias.col = %s', cond_str)
    self.assertEqual([1], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', [1, 2])
    self.assertEqual('Alias.col IN (%s,%s)', cond_str)
    self.assertEqual([1, 2], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [])
    self.assertEqual('TRUE', cond_str)
    self.assertEqual([], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [1])
    self.assertEqual('(Alias.col IS NULL OR Alias.col != %s)', cond_str)
    self.assertEqual([1], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [1, 2])
    self.assertEqual('(Alias.col IS NULL OR Alias.col NOT IN (%s,%s))',
                     cond_str)
    self.assertEqual([1, 2], cond_args)

  def testCompare_STRTypes(self):
    val_type = tracker_pb2.FieldTypes.STR_TYPE
    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.IS_DEFINED, val_type, 'col', ['a', 'b'])
    self.assertEqual('(Alias.col IS NOT NULL AND Alias.col != %s)', cond_str)
    self.assertEqual([''], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', ['a'])
    self.assertEqual('Alias.col = %s', cond_str)
    self.assertEqual(['a'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.EQ, val_type, 'col', ['a', 'b'])
    self.assertEqual('Alias.col IN (%s,%s)', cond_str)
    self.assertEqual(['a', 'b'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', [])
    self.assertEqual('TRUE', cond_str)
    self.assertEqual([], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', ['a'])
    self.assertEqual('(Alias.col IS NULL OR Alias.col != %s)', cond_str)
    self.assertEqual(['a'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NE, val_type, 'col', ['a', 'b'])
    self.assertEqual('(Alias.col IS NULL OR Alias.col NOT IN (%s,%s))',
                     cond_str)
    self.assertEqual(['a', 'b'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.TEXT_HAS, val_type, 'col', ['a'])
    self.assertEqual('(Alias.col LIKE %s)', cond_str)
    self.assertEqual(['%a%'], cond_args)

    cond_str, cond_args = ast2select._Compare(
        'Alias', ast_pb2.QueryOp.NOT_TEXT_HAS, val_type, 'col', ['a'])
    self.assertEqual('(Alias.col IS NULL OR Alias.col NOT LIKE %s)', cond_str)
    self.assertEqual(['%a%'], cond_args)

  def testCompareAlreadyJoined(self):
    cond_str, cond_args = ast2select._CompareAlreadyJoined(
        'Alias', ast_pb2.QueryOp.EQ, 'col')
    self.assertEqual('Alias.col IS NOT NULL', cond_str)
    self.assertEqual([], cond_args)

    cond_str, cond_args = ast2select._CompareAlreadyJoined(
        'Alias', ast_pb2.QueryOp.NE, 'col')
    self.assertEqual('Alias.col IS NULL', cond_str)
    self.assertEqual([], cond_args)
