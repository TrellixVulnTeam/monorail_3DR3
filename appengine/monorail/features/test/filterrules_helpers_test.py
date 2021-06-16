# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for filterrules_helpers feature."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mox

from google.appengine.api import taskqueue

import settings
from features import filterrules_helpers
from framework import framework_constants
from framework import template_helpers
from framework import urls
from proto import ast_pb2
from proto import tracker_pb2
from search import query2ast
from services import service_manager
from testing import fake
from tracker import tracker_bizobj


ORIG_SUMMARY = 'this is the orginal summary'
ORIG_LABELS = ['one', 'two']

# Fake user id mapping
TEST_ID_MAP = {
    'mike.j.parent': 1,
    'jrobbins': 2,
    'ningerso': 3,
    'ui@example.com': 4,
    'db@example.com': 5,
    'ui-db@example.com': 6,
    }

TEST_LABEL_IDS = {
  'i18n': 1,
  'l10n': 2,
  'Priority-High': 3,
  'Priority-Medium': 4,
  }


class MockTaskQueue(object):
  def __init__(self):
    self.work_items = []

  def add(self, **kwargs):
    self.work_items.append(kwargs)


class RecomputeAllDerivedFieldsTest(unittest.TestCase):

  BLOCK = filterrules_helpers.BLOCK

  def setUp(self):
    self.features = fake.FeaturesService()
    self.user = fake.UserService()
    self.services = service_manager.Services(
        features=self.features,
        user=self.user,
        issue=fake.IssueService())
    self.project = fake.Project(project_name='proj')
    self.config = 'fake config'
    self.cnxn = 'fake cnxn'
    self.mox = mox.Mox()
    self.mock_task_queue = MockTaskQueue()
    self.mox.StubOutWithMock(taskqueue, 'add')

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testRecomputeDerivedFields_Disabled(self):
    """Servlet should just call RecomputeAllDerivedFieldsNow with no bounds."""
    saved_flag = settings.recompute_derived_fields_in_worker
    settings.recompute_derived_fields_in_worker = False
    self.mox.ReplayAll()

    filterrules_helpers.RecomputeAllDerivedFields(
        self.cnxn, self.services, self.project, self.config)
    self.assertTrue(self.services.issue.get_all_issues_in_project_called)
    self.assertTrue(self.services.issue.update_issues_called)
    self.assertTrue(self.services.issue.enqueue_issues_called)

    self.mox.VerifyAll()
    settings.recompute_derived_fields_in_worker = saved_flag

  def testRecomputeDerivedFields_DisabledNextIDSet(self):
    """Servlet should just call RecomputeAllDerivedFields with no bounds."""
    saved_flag = settings.recompute_derived_fields_in_worker
    settings.recompute_derived_fields_in_worker = False
    self.services.issue.next_id = 1234
    self.mox.ReplayAll()

    filterrules_helpers.RecomputeAllDerivedFields(
        self.cnxn, self.services, self.project, self.config)
    self.assertTrue(self.services.issue.get_all_issues_in_project_called)
    self.assertTrue(self.services.issue.enqueue_issues_called)

    self.mox.VerifyAll()
    settings.recompute_derived_fields_in_worker = saved_flag

  def testRecomputeDerivedFields_NoIssues(self):
    """Servlet should not call because there is no work to do."""
    saved_flag = settings.recompute_derived_fields_in_worker
    settings.recompute_derived_fields_in_worker = True
    self.mox.ReplayAll()

    filterrules_helpers.RecomputeAllDerivedFields(
        self.cnxn, self.services, self.project, self.config)
    self.assertFalse(self.services.issue.get_all_issues_in_project_called)
    self.assertFalse(self.services.issue.update_issues_called)
    self.assertFalse(self.services.issue.enqueue_issues_called)

    self.mox.VerifyAll()
    settings.recompute_derived_fields_in_worker = saved_flag

  def testRecomputeDerivedFields_SomeIssues(self):
    """Servlet should enqueue one work item rather than call directly."""
    saved_flag = settings.recompute_derived_fields_in_worker
    settings.recompute_derived_fields_in_worker = True
    self.services.issue.next_id = 1234
    num_calls = (self.services.issue.next_id // self.BLOCK + 1)
    for _ in range(num_calls):
      taskqueue.add(
          params=mox.IsA(dict),
          url='/_task/recomputeDerivedFields.do').WithSideEffects(
              self.mock_task_queue.add)
    self.mox.ReplayAll()

    filterrules_helpers.RecomputeAllDerivedFields(
        self.cnxn, self.services, self.project, self.config)
    self.assertFalse(self.services.issue.get_all_issues_in_project_called)
    self.assertFalse(self.services.issue.update_issues_called)
    self.assertFalse(self.services.issue.enqueue_issues_called)
    work_items = self.mock_task_queue.work_items
    self.assertEqual(num_calls, len(work_items))

    self.mox.VerifyAll()
    settings.recompute_derived_fields_in_worker = saved_flag

  def testRecomputeDerivedFields_LotsOfIssues(self):
    """Servlet should enqueue multiple work items."""
    saved_flag = settings.recompute_derived_fields_in_worker
    settings.recompute_derived_fields_in_worker = True
    self.services.issue.next_id = 12345
    num_calls = (self.services.issue.next_id // self.BLOCK + 1)
    for _ in range(num_calls):
      taskqueue.add(
          params=mox.IsA(dict),
          url='/_task/recomputeDerivedFields.do').WithSideEffects(
              self.mock_task_queue.add)
    self.mox.ReplayAll()

    filterrules_helpers.RecomputeAllDerivedFields(
        self.cnxn, self.services, self.project, self.config)
    self.assertFalse(self.services.issue.get_all_issues_in_project_called)
    self.assertFalse(self.services.issue.update_issues_called)
    self.assertFalse(self.services.issue.enqueue_issues_called)

    work_items = self.mock_task_queue.work_items
    self.assertEqual(num_calls, len(work_items))
    url, params = work_items[0]['url'], work_items[0]['params']
    self.assertEqual(urls.RECOMPUTE_DERIVED_FIELDS_TASK + '.do', url)
    self.assertEqual(self.project.project_id, params['project_id'])
    self.assertEqual(12345 // self.BLOCK * self.BLOCK + 1,
                     params['lower_bound'])
    self.assertEqual(12345, params['upper_bound'])

    url, params = work_items[-1]['url'], work_items[-1]['params']
    self.assertEqual(urls.RECOMPUTE_DERIVED_FIELDS_TASK + '.do', url)
    self.assertEqual(self.project.project_id, params['project_id'])
    self.assertEqual(1, params['lower_bound'])
    self.assertEqual(self.BLOCK + 1, params['upper_bound'])

    self.mox.VerifyAll()
    settings.recompute_derived_fields_in_worker = saved_flag

  def testRecomputeAllDerivedFieldsNow(self):
    """Servlet should reapply all filter rules to project's issues."""
    self.services.issue.next_id = 12345
    test_issue_1 = fake.MakeTestIssue(
        project_id=self.project.project_id, local_id=1, issue_id=1001,
        summary='sum1', owner_id=100, status='New')
    test_issue_1.assume_stale = False  # We will store this issue.
    test_issue_2 = fake.MakeTestIssue(
        project_id=self.project.project_id, local_id=2, issue_id=1002,
        summary='sum2', owner_id=100, status='New')
    test_issue_2.assume_stale = False  # We will store this issue.
    test_issues = [test_issue_1, test_issue_2]
    self.services.issue.TestAddIssue(test_issue_1)
    self.services.issue.TestAddIssue(test_issue_2)

    self.mox.StubOutWithMock(filterrules_helpers, 'ApplyGivenRules')
    for test_issue in test_issues:
      filterrules_helpers.ApplyGivenRules(
          self.cnxn, self.services, test_issue, self.config,
          [], []).AndReturn((True, {}))
    self.mox.ReplayAll()

    filterrules_helpers.RecomputeAllDerivedFieldsNow(
        self.cnxn, self.services, self.project, self.config)

    self.assertTrue(self.services.issue.get_all_issues_in_project_called)
    self.assertTrue(self.services.issue.update_issues_called)
    self.assertTrue(self.services.issue.enqueue_issues_called)
    self.assertEqual(test_issues, self.services.issue.updated_issues)
    self.assertEqual([issue.issue_id for issue in test_issues],
                     self.services.issue.enqueued_issues)
    self.mox.VerifyAll()


class FilterRulesHelpersTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue=fake.IssueService(),
        config=fake.ConfigService())
    self.project = self.services.project.TestAddProject('proj', project_id=789)
    self.other_project = self.services.project.TestAddProject(
        'otherproj', project_id=890)
    for email, user_id in TEST_ID_MAP.items():
      self.services.user.TestAddUser(email, user_id)
    self.services.config.TestAddLabelsDict(TEST_LABEL_IDS)

  def testApplyRule(self):
    cnxn = 'fake sql connection'
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 111, labels=ORIG_LABELS)
    config = tracker_pb2.ProjectIssueConfig(project_id=self.project.project_id)
    # Empty label set cannot satisfy rule looking for labels.
    pred = 'label:a label:b'
    rule = filterrules_helpers.MakeRule(
        pred, default_owner_id=1, default_status='S')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (None, None, [], [], [], None, None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, set(), config))

    pred = 'label:a -label:b'
    rule = filterrules_helpers.MakeRule(
        pred, default_owner_id=1, default_status='S')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (None, None, [], [], [], None, None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, set(), config))

    # Empty label set will satisfy rule looking for missing labels.
    pred = '-label:a -label:b'
    rule = filterrules_helpers.MakeRule(
        pred, default_owner_id=1, default_status='S')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (1, 'S', [], [], [], None, None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, set(), config))

    # Label set has the needed labels.
    pred = 'label:a label:b'
    rule = filterrules_helpers.MakeRule(
        pred, default_owner_id=1, default_status='S')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (1, 'S', [], [], [], None, None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, {'a', 'b'},
            config))

    # Label set has the needed labels with test for unicode.
    pred = 'label:a label:b'
    rule = filterrules_helpers.MakeRule(
        pred, default_owner_id=1, default_status='S')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (1, 'S', [], [], [], None, None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, {u'a', u'b'},
            config))

    # Label set has the needed labels, capitalization irrelevant.
    pred = 'label:A label:B'
    rule = filterrules_helpers.MakeRule(
        pred, default_owner_id=1, default_status='S')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (1, 'S', [], [], [], None, None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, {'a', 'b'},
            config))

    # Label set has a label, the rule negates.
    pred = 'label:a -label:b'
    rule = filterrules_helpers.MakeRule(
        pred, default_owner_id=1, default_status='S')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (None, None, [], [], [], None, None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, {'a', 'b'},
            config))

    # Consequence is to add a warning.
    pred = 'label:a'
    rule = filterrules_helpers.MakeRule(
        pred, warning='Hey look out')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (None, None, [], [], [], 'Hey look out', None),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, {'a', 'b'},
            config))

    # Consequence is to add an error.
    pred = 'label:a'
    rule = filterrules_helpers.MakeRule(
        pred, error='We cannot allow that')
    predicate_ast = query2ast.ParseUserQuery(
        pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
    self.assertEqual(
        (None, None, [], [], [], None, 'We cannot allow that'),
        filterrules_helpers._ApplyRule(
            cnxn, self.services, rule, predicate_ast, issue, {'a', 'b'},
            config))

  def testComputeDerivedFields_Components(self):
    cnxn = 'fake sql connection'
    rules = []
    component_defs = [
      tracker_bizobj.MakeComponentDef(
        10, 789, 'DB', 'database', False, [],
        [TEST_ID_MAP['db@example.com'],
         TEST_ID_MAP['ui-db@example.com']],
        0, 0,
        label_ids=[TEST_LABEL_IDS['i18n'],
                   TEST_LABEL_IDS['Priority-High']]),
      tracker_bizobj.MakeComponentDef(
        20, 789, 'Install', 'installer', False, [],
        [], 0, 0),
      tracker_bizobj.MakeComponentDef(
        30, 789, 'UI', 'doc', False, [],
        [TEST_ID_MAP['ui@example.com'],
         TEST_ID_MAP['ui-db@example.com']],
        0, 0,
        label_ids=[TEST_LABEL_IDS['i18n'],
                   TEST_LABEL_IDS['l10n'],
                   TEST_LABEL_IDS['Priority-Medium']]),
      ]
    excl_prefixes = ['Priority', 'type', 'milestone']
    config = tracker_pb2.ProjectIssueConfig(
        exclusive_label_prefixes=excl_prefixes,
        component_defs=component_defs)
    predicate_asts = filterrules_helpers.ParsePredicateASTs(rules, config, [])

    # No components.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=ORIG_LABELS)
    self.assertEqual(
        (0, '', [], [], [], {}, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # One component, no CCs or labels added
    issue.component_ids = [20]
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=ORIG_LABELS)
    self.assertEqual(
        (0, '', [], [], [], {}, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # One component, some CCs and labels added
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=ORIG_LABELS,
        component_ids=[10])
    traces = {
      (tracker_pb2.FieldID.CC, TEST_ID_MAP['db@example.com']):
          'Added by component DB',
      (tracker_pb2.FieldID.CC, TEST_ID_MAP['ui-db@example.com']):
          'Added by component DB',
      (tracker_pb2.FieldID.LABELS, 'i18n'):
          'Added by component DB',
      (tracker_pb2.FieldID.LABELS, 'Priority-High'):
          'Added by component DB',
      }
    self.assertEqual(
        (
            0, '', [
                TEST_ID_MAP['db@example.com'], TEST_ID_MAP['ui-db@example.com']
            ], ['i18n', 'Priority-High'], [], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # One component, CCs and labels not added because of labels on the issue.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=['Priority-Low', 'i18n'],
        component_ids=[10])
    issue.cc_ids = [TEST_ID_MAP['db@example.com']]
    traces = {
      (tracker_pb2.FieldID.CC, TEST_ID_MAP['ui-db@example.com']):
          'Added by component DB',
      }
    self.assertEqual(
        (0, '', [TEST_ID_MAP['ui-db@example.com']], [], [], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # Multiple components, added CCs treated as a set, exclusive labels in later
    # components take priority over earlier ones.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=ORIG_LABELS,
        component_ids=[10, 30])
    traces = {
      (tracker_pb2.FieldID.CC, TEST_ID_MAP['db@example.com']):
          'Added by component DB',
      (tracker_pb2.FieldID.CC, TEST_ID_MAP['ui-db@example.com']):
          'Added by component DB',
      (tracker_pb2.FieldID.LABELS, 'i18n'):
          'Added by component DB',
      (tracker_pb2.FieldID.LABELS, 'Priority-High'):
          'Added by component DB',
      (tracker_pb2.FieldID.CC, TEST_ID_MAP['ui@example.com']):
          'Added by component UI',
      (tracker_pb2.FieldID.LABELS, 'Priority-Medium'):
          'Added by component UI',
      (tracker_pb2.FieldID.LABELS, 'l10n'):
          'Added by component UI',
      }
    self.assertEqual(
        (
            0, '', [
                TEST_ID_MAP['db@example.com'], TEST_ID_MAP['ui-db@example.com'],
                TEST_ID_MAP['ui@example.com']
            ], ['i18n', 'l10n', 'Priority-Medium'], [], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

  def testComputeDerivedFields_Rules(self):
    cnxn = 'fake sql connection'
    rules = [
        filterrules_helpers.MakeRule(
            'label:HasWorkaround', add_labels=['Priority-Low']),
        filterrules_helpers.MakeRule(
            'label:Security', add_labels=['Private']),
        filterrules_helpers.MakeRule(
            'label:Security', add_labels=['Priority-High'],
            add_notify=['jrobbins@chromium.org']),
        filterrules_helpers.MakeRule(
            'Priority=High label:Regression', add_labels=['Urgent']),
        filterrules_helpers.MakeRule(
            'Size=L', default_owner_id=444),
        filterrules_helpers.MakeRule(
            'Size=XL', warning='It will take too long'),
        filterrules_helpers.MakeRule(
            'Size=XL', warning='It will cost too much'),
        ]
    excl_prefixes = ['Priority', 'type', 'milestone']
    config = tracker_pb2.ProjectIssueConfig(
        exclusive_label_prefixes=excl_prefixes,
        project_id=self.project.project_id)
    predicate_asts = filterrules_helpers.ParsePredicateASTs(rules, config, [])

    # No rules fire.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=ORIG_LABELS)
    self.assertEqual(
        (0, '', [], [], [], {}, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=['foo', 'bar'])
    self.assertEqual(
        (0, '', [], [], [], {}, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # One rule fires.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=['Size-L'])
    traces = {
        (tracker_pb2.FieldID.OWNER, 444):
            'Added by rule: IF Size=L THEN SET DEFAULT OWNER',
        }
    self.assertEqual(
        (444, '', [], [], [], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # One rule fires, but no effect because of explicit fields.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0,
        labels=['HasWorkaround', 'Priority-Critical'])
    traces = {}
    self.assertEqual(
        (0, '', [], [], [], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # One rule fires, another has no effect because of explicit exclusive label.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0,
        labels=['Security', 'Priority-Critical'])
    traces = {
        (tracker_pb2.FieldID.LABELS, 'Private'):
            'Added by rule: IF label:Security THEN ADD LABEL',
        }
    self.assertEqual(
        (0, '', [], ['Private'], ['jrobbins@chromium.org'], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # Multiple rules have cumulative effect.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=['HasWorkaround', 'Size-L'])
    traces = {
        (tracker_pb2.FieldID.LABELS, 'Priority-Low'):
            'Added by rule: IF label:HasWorkaround THEN ADD LABEL',
        (tracker_pb2.FieldID.OWNER, 444):
            'Added by rule: IF Size=L THEN SET DEFAULT OWNER',
        }
    self.assertEqual(
        (444, '', [], ['Priority-Low'], [], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # Multiple rules have cumulative warnings.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=['Size-XL'])
    traces = {
        (tracker_pb2.FieldID.WARNING, 'It will take too long'):
            'Added by rule: IF Size=XL THEN ADD WARNING',
        (tracker_pb2.FieldID.WARNING, 'It will cost too much'):
            'Added by rule: IF Size=XL THEN ADD WARNING',
        }
    self.assertEqual(
        (
            0, '', [], [], [], traces,
            ['It will take too long', 'It will cost too much'], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # Two rules fire, second overwrites the first.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=['HasWorkaround', 'Security'])
    traces = {
        (tracker_pb2.FieldID.LABELS, 'Priority-Low'):
            'Added by rule: IF label:HasWorkaround THEN ADD LABEL',
        (tracker_pb2.FieldID.LABELS, 'Priority-High'):
            'Added by rule: IF label:Security THEN ADD LABEL',
        (tracker_pb2.FieldID.LABELS, 'Private'):
            'Added by rule: IF label:Security THEN ADD LABEL',
        }
    self.assertEqual(
        (
            0, '', [], ['Private', 'Priority-High'], ['jrobbins@chromium.org'],
            traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # Two rules fire, second triggered by the first.
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 0, labels=['Security', 'Regression'])
    traces = {
        (tracker_pb2.FieldID.LABELS, 'Priority-High'):
            'Added by rule: IF label:Security THEN ADD LABEL',
        (tracker_pb2.FieldID.LABELS, 'Urgent'):
            'Added by rule: IF Priority=High label:Regression THEN ADD LABEL',
        (tracker_pb2.FieldID.LABELS, 'Private'):
            'Added by rule: IF label:Security THEN ADD LABEL',
        }
    self.assertEqual(
        (
            0, '', [], ['Private', 'Priority-High', 'Urgent'],
            ['jrobbins@chromium.org'], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

    # Two rules fire, each one wants to add the same CC: only add once.
    rules.append(filterrules_helpers.MakeRule('Watch', add_cc_ids=[111]))
    rules.append(filterrules_helpers.MakeRule('Monitor', add_cc_ids=[111]))
    config = tracker_pb2.ProjectIssueConfig(
        exclusive_label_prefixes=excl_prefixes,
        project_id=self.project.project_id)
    predicate_asts = filterrules_helpers.ParsePredicateASTs(rules, config, [])
    traces = {
        (tracker_pb2.FieldID.CC, 111):
            'Added by rule: IF Watch THEN ADD CC',
        }
    issue = fake.MakeTestIssue(
        789, 1, ORIG_SUMMARY, 'New', 111, labels=['Watch', 'Monitor'])
    self.assertEqual(
        (0, '', [111], [], [], traces, [], []),
        filterrules_helpers._ComputeDerivedFields(
            cnxn, self.services, issue, config, rules, predicate_asts))

  def testCompareComponents_Trivial(self):
    config = tracker_pb2.ProjectIssueConfig()
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.IS_DEFINED, [], [123]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.IS_NOT_DEFINED, [], [123]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.IS_DEFINED, [], []))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.IS_NOT_DEFINED, [], []))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, [123], []))

  def testCompareComponents_Normal(self):
    config = tracker_pb2.ProjectIssueConfig()
    config.component_defs.append(tracker_bizobj.MakeComponentDef(
        100, 789, 'UI', 'doc', False, [], [], 0, 0))
    config.component_defs.append(tracker_bizobj.MakeComponentDef(
        110, 789, 'UI>Help', 'doc', False, [], [], 0, 0))
    config.component_defs.append(tracker_bizobj.MakeComponentDef(
        200, 789, 'Networking', 'doc', False, [], [], 0, 0))

    # Check if the issue is in a specified component or subcomponent.
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI'], [100]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI>Help'], [110]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI'], [100, 110]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI'], []))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI'], [110]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI'], [200]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI>Help'], [100]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['Networking'], [100]))

    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.NE, ['UI'], []))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.NE, ['UI'], [100]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.NE, ['Networking'], [100]))

    # Exact vs non-exact.
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['Help'], [110]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.TEXT_HAS, ['UI'], [110]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.TEXT_HAS, ['Help'], [110]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.NOT_TEXT_HAS, ['UI'], [110]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.NOT_TEXT_HAS, ['Help'], [110]))

    # Multivalued issues and Quick-OR notation
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['Networking'], [200]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['Networking'], [100, 110]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI', 'Networking'], [100]))
    self.assertFalse(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI', 'Networking'], [110]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI', 'Networking'], [200]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI', 'Networking'], [110, 200]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.TEXT_HAS, ['UI', 'Networking'], [110, 200]))
    self.assertTrue(filterrules_helpers._CompareComponents(
        config, ast_pb2.QueryOp.EQ, ['UI>Help', 'Networking'], [110, 200]))

  def testCompareIssueRefs_Trivial(self):
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.IS_DEFINED, [], [123]))
    self.assertFalse(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.IS_NOT_DEFINED, [], [123]))
    self.assertFalse(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.IS_DEFINED, [], []))
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.IS_NOT_DEFINED, [], []))
    self.assertFalse(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.EQ, ['1'], []))

  def testCompareIssueRefs_Normal(self):
    self.services.issue.TestAddIssue(fake.MakeTestIssue(
        789, 1, 'summary', 'New', 0, issue_id=123))
    self.services.issue.TestAddIssue(fake.MakeTestIssue(
        789, 2, 'summary', 'New', 0, issue_id=124))
    self.services.issue.TestAddIssue(fake.MakeTestIssue(
        890, 1, 'other summary', 'New', 0, issue_id=125))

    # EQ and NE, implict references to the current project.
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.EQ, ['1'], [123]))
    self.assertFalse(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.NE, ['1'], [123]))

    # EQ and NE, explicit project references.
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.EQ, ['proj:1'], [123]))
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.EQ, ['otherproj:1'], [125]))

    # Inequalities
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.GE, ['1'], [123]))
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.GE, ['1'], [124]))
    self.assertTrue(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.GE, ['2'], [124]))
    self.assertFalse(filterrules_helpers._CompareIssueRefs(
        self.cnxn, self.services, self.project,
        ast_pb2.QueryOp.GT, ['2'], [124]))

  def testCompareUsers(self):
    pass  # TODO(jrobbins): Add this test.

  def testCompareUserIDs(self):
    pass  # TODO(jrobbins): Add this test.

  def testCompareEmails(self):
    pass  # TODO(jrobbins): Add this test.

  def testCompare(self):
    pass  # TODO(jrobbins): Add this test.

  def testParseOneRuleAddLabels(self):
    cnxn = 'fake SQL connection'
    error_list = []
    rule_pb = filterrules_helpers._ParseOneRule(
        cnxn, 'label:lab1 label:lab2', 'add_labels', 'hot cOld, ', None, 1,
        error_list)
    self.assertEqual('label:lab1 label:lab2', rule_pb.predicate)
    self.assertEqual(error_list, [])
    self.assertEqual(len(rule_pb.add_labels), 2)
    self.assertEqual(rule_pb.add_labels[0], 'hot')
    self.assertEqual(rule_pb.add_labels[1], 'cOld')

    rule_pb = filterrules_helpers._ParseOneRule(
        cnxn, '', 'default_status', 'hot cold', None, 1, error_list)
    self.assertEqual(len(rule_pb.predicate), 0)
    self.assertEqual(error_list, [])

  def testParseOneRuleDefaultOwner(self):
    cnxn = 'fake SQL connection'
    error_list = []
    rule_pb = filterrules_helpers._ParseOneRule(
        cnxn, 'label:lab1, label:lab2 ', 'default_owner', 'jrobbins',
        self.services.user, 1, error_list)
    self.assertEqual(error_list, [])
    self.assertEqual(rule_pb.default_owner_id, TEST_ID_MAP['jrobbins'])

  def testParseOneRuleDefaultStatus(self):
    cnxn = 'fake SQL connection'
    error_list = []
    rule_pb = filterrules_helpers._ParseOneRule(
        cnxn, 'label:lab1', 'default_status', 'InReview',
        None, 1, error_list)
    self.assertEqual(error_list, [])
    self.assertEqual(rule_pb.default_status, 'InReview')

  def testParseOneRuleAddCcs(self):
    cnxn = 'fake SQL connection'
    error_list = []
    rule_pb = filterrules_helpers._ParseOneRule(
        cnxn, 'label:lab1', 'add_ccs', 'jrobbins, mike.j.parent',
        self.services.user, 1, error_list)
    self.assertEqual(error_list, [])
    self.assertEqual(rule_pb.add_cc_ids[0], TEST_ID_MAP['jrobbins'])
    self.assertEqual(rule_pb.add_cc_ids[1], TEST_ID_MAP['mike.j.parent'])
    self.assertEqual(len(rule_pb.add_cc_ids), 2)

  def testParseRulesNone(self):
    cnxn = 'fake SQL connection'
    post_data = {}
    rules = filterrules_helpers.ParseRules(
        cnxn, post_data, None, template_helpers.EZTError())
    self.assertEqual(rules, [])

  def testParseRules(self):
    cnxn = 'fake SQL connection'
    post_data = {
        'predicate1': 'a, b c',
        'action_type1': 'default_status',
        'action_value1': 'Reviewed',
        'predicate2': 'a, b c',
        'action_type2': 'default_owner',
        'action_value2': 'jrobbins',
        'predicate3': 'a, b c',
        'action_type3': 'add_ccs',
        'action_value3': 'jrobbins, mike.j.parent',
        'predicate4': 'a, b c',
        'action_type4': 'add_labels',
        'action_value4': 'hot, cold',
        }
    errors = template_helpers.EZTError()
    rules = filterrules_helpers.ParseRules(
        cnxn, post_data, self.services.user, errors)
    self.assertEqual(rules[0].predicate, 'a, b c')
    self.assertEqual(rules[0].default_status, 'Reviewed')
    self.assertEqual(rules[1].default_owner_id, TEST_ID_MAP['jrobbins'])
    self.assertEqual(rules[2].add_cc_ids[0], TEST_ID_MAP['jrobbins'])
    self.assertEqual(rules[2].add_cc_ids[1], TEST_ID_MAP['mike.j.parent'])
    self.assertEqual(rules[3].add_labels[0], 'hot')
    self.assertEqual(rules[3].add_labels[1], 'cold')
    self.assertEqual(len(rules), 4)
    self.assertFalse(errors.AnyErrors())

  def testOwnerCcsInvolvedInFilterRules(self):
    rules = [
        tracker_pb2.FilterRule(add_cc_ids=[111, 333], default_owner_id=999),
        tracker_pb2.FilterRule(default_owner_id=888),
        tracker_pb2.FilterRule(add_cc_ids=[999, 777]),
        tracker_pb2.FilterRule(),
        ]
    actual_user_ids = filterrules_helpers.OwnerCcsInvolvedInFilterRules(rules)
    self.assertItemsEqual([111, 333, 777, 888, 999], actual_user_ids)

  def testBuildFilterRuleStrings(self):
    rules = [
        tracker_pb2.FilterRule(
            predicate='label:machu', add_cc_ids=[111, 333, 999]),
        tracker_pb2.FilterRule(predicate='label:pichu', default_owner_id=222),
        tracker_pb2.FilterRule(
            predicate='owner:farmer@test.com',
            add_labels=['cows-farting', 'chicken', 'machu-pichu']),
        tracker_pb2.FilterRule(predicate='label:beach', default_status='New'),
        tracker_pb2.FilterRule(
            predicate='label:rainforest',
            add_notify_addrs=['cake@test.com', 'pie@test.com']),
    ]
    emails_by_id = {
        111: 'cow@test.com', 222: 'fox@test.com', 333: 'llama@test.com'}
    rule_strs = filterrules_helpers.BuildFilterRuleStrings(rules, emails_by_id)

    self.assertItemsEqual(
        rule_strs, [
            'if label:machu '
            'then add cc(s): cow@test.com, llama@test.com, user not found',
            'if label:pichu then set default owner: fox@test.com',
            'if owner:farmer@test.com '
            'then add label(s): cows-farting, chicken, machu-pichu',
            'if label:beach then set default status: New',
            'if label:rainforest then notify: cake@test.com, pie@test.com',
        ])

  def testBuildRedactedFilterRuleStrings(self):
    rules_by_project = {
        16: [
            tracker_pb2.FilterRule(
                predicate='label:machu', add_cc_ids=[111, 333, 999]),
            tracker_pb2.FilterRule(
                predicate='label:pichu', default_owner_id=222)],
        19: [
            tracker_pb2.FilterRule(
                predicate='owner:farmer@test.com',
                add_labels=['cows-farting', 'chicken', 'machu-pichu']),
            tracker_pb2.FilterRule(
                predicate='label:rainforest',
                add_notify_addrs=['cake@test.com', 'pie@test.com'])],
        }
    deleted_emails = ['farmer@test.com', 'pie@test.com', 'fox@test.com']
    self.services.user.TestAddUser('cow@test.com', 111)
    self.services.user.TestAddUser('fox@test.com', 222)
    self.services.user.TestAddUser('llama@test.com', 333)
    actual = filterrules_helpers.BuildRedactedFilterRuleStrings(
        self.cnxn, rules_by_project, self.services.user, deleted_emails)

    self.assertItemsEqual(
        actual,
        {16: [
            'if label:machu '
            'then add cc(s): cow@test.com, llama@test.com, user not found',
            'if label:pichu '
            'then set default owner: %s' %
            framework_constants.DELETED_USER_NAME],
         19: [
             'if owner:%s '
             'then add label(s): cows-farting, chicken, machu-pichu' %
             framework_constants.DELETED_USER_NAME,
             'if label:rainforest '
             'then notify: cake@test.com, %s' %
             framework_constants.DELETED_USER_NAME],
        })
