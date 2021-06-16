# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the tracker helpers module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

import settings

from framework import framework_constants
from framework import framework_helpers
from framework import permissions
from framework import template_helpers
from framework import urls
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers

TEST_ID_MAP = {
    'a@example.com': 1,
    'b@example.com': 2,
    'c@example.com': 3,
    'd@example.com': 4,
    }


def _Issue(project_name, local_id, summary, status):
  issue = tracker_pb2.Issue()
  issue.project_name = project_name
  issue.project_id = 789
  issue.local_id = local_id
  issue.issue_id = 100000 + local_id
  issue.summary = summary
  issue.status = status
  return issue


def _MakeConfig():
  config = tracker_pb2.ProjectIssueConfig()
  config.well_known_statuses.append(tracker_pb2.StatusDef(
      means_open=True, status='New', deprecated=False))
  config.well_known_statuses.append(tracker_pb2.StatusDef(
      status='Old', means_open=False, deprecated=False))
  config.well_known_statuses.append(tracker_pb2.StatusDef(
      status='StatusThatWeDontUseAnymore', means_open=False, deprecated=True))

  return config


class HelpersTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService())

    for email, user_id in TEST_ID_MAP.items():
      self.services.user.TestAddUser(email, user_id)

    self.services.project.TestAddProject('testproj', project_id=789)
    self.issue1 = fake.MakeTestIssue(789, 1, 'one', 'New', 111)
    self.issue1.project_name = 'testproj'
    self.services.issue.TestAddIssue(self.issue1)
    self.issue2 = fake.MakeTestIssue(789, 2, 'two', 'New', 111)
    self.issue2.project_name = 'testproj'
    self.services.issue.TestAddIssue(self.issue2)
    self.issue3 = fake.MakeTestIssue(789, 3, 'three', 'New', 111)
    self.issue3.project_name = 'testproj'
    self.services.issue.TestAddIssue(self.issue3)
    self.cnxn = 'fake connextion'
    self.errors = template_helpers.EZTError()
    self.default_colspec_param = 'colspec=%s' % (
        tracker_constants.DEFAULT_COL_SPEC.replace(' ', '%20'))
    self.services.usergroup.TestAddGroupSettings(999, 'group@example.com')

  def testParseIssueRequest_Empty(self):
    post_data = fake.PostData()
    errors = template_helpers.EZTError()
    parsed = tracker_helpers.ParseIssueRequest(
        'fake cnxn', post_data, self.services, errors, 'proj')
    self.assertEqual('', parsed.summary)
    self.assertEqual('', parsed.comment)
    self.assertEqual('', parsed.status)
    self.assertEqual('', parsed.users.owner_username)
    self.assertEqual(0, parsed.users.owner_id)
    self.assertEqual([], parsed.users.cc_usernames)
    self.assertEqual([], parsed.users.cc_usernames_remove)
    self.assertEqual([], parsed.users.cc_ids)
    self.assertEqual([], parsed.users.cc_ids_remove)
    self.assertEqual('', parsed.template_name)
    self.assertEqual([], parsed.labels)
    self.assertEqual([], parsed.labels_remove)
    self.assertEqual({}, parsed.fields.vals)
    self.assertEqual({}, parsed.fields.vals_remove)
    self.assertEqual([], parsed.fields.fields_clear)
    self.assertEqual('', parsed.blocked_on.entered_str)
    self.assertEqual([], parsed.blocked_on.iids)

  def testParseIssueRequest_Normal(self):
    post_data = fake.PostData({
        'summary': ['some summary'],
        'comment': ['some comment'],
        'status': ['SomeStatus'],
        'template_name': ['some template'],
        'label': ['lab1', '-lab2'],
        'custom_123': ['field1123a', 'field1123b'],
        })
    errors = template_helpers.EZTError()
    parsed = tracker_helpers.ParseIssueRequest(
        'fake cnxn', post_data, self.services, errors, 'proj')
    self.assertEqual('some summary', parsed.summary)
    self.assertEqual('some comment', parsed.comment)
    self.assertEqual('SomeStatus', parsed.status)
    self.assertEqual('', parsed.users.owner_username)
    self.assertEqual(0, parsed.users.owner_id)
    self.assertEqual([], parsed.users.cc_usernames)
    self.assertEqual([], parsed.users.cc_usernames_remove)
    self.assertEqual([], parsed.users.cc_ids)
    self.assertEqual([], parsed.users.cc_ids_remove)
    self.assertEqual('some template', parsed.template_name)
    self.assertEqual(['lab1'], parsed.labels)
    self.assertEqual(['lab2'], parsed.labels_remove)
    self.assertEqual({123: ['field1123a', 'field1123b']}, parsed.fields.vals)
    self.assertEqual({}, parsed.fields.vals_remove)
    self.assertEqual([], parsed.fields.fields_clear)

  def testMarkupDescriptionOnInput(self):
    content = 'What?\nthat\nWhy?\nidk\nWhere?\n'
    tmpl_txt = 'What?\nWhy?\nWhere?\nWhen?'
    desc = '<b>What?</b>\nthat\n<b>Why?</b>\nidk\n<b>Where?</b>\n'
    self.assertEqual(tracker_helpers.MarkupDescriptionOnInput(
        content, tmpl_txt), desc)

  def testMarkupDescriptionLineOnInput(self):
    line = 'What happened??'
    tmpl_lines = ['What happened??','Why?']
    self.assertEqual(tracker_helpers._MarkupDescriptionLineOnInput(
        line, tmpl_lines), '<b>What happened??</b>')

    line = 'Something terrible!!!'
    self.assertEqual(tracker_helpers._MarkupDescriptionLineOnInput(
        line, tmpl_lines), 'Something terrible!!!')

  def testClassifyPlusMinusItems(self):
    add, remove = tracker_helpers._ClassifyPlusMinusItems([])
    self.assertEqual([], add)
    self.assertEqual([], remove)

    add, remove = tracker_helpers._ClassifyPlusMinusItems(
        ['', ' ', '  \t', '-'])
    self.assertItemsEqual([], add)
    self.assertItemsEqual([], remove)

    add, remove = tracker_helpers._ClassifyPlusMinusItems(
        ['a', 'b', 'c'])
    self.assertItemsEqual(['a', 'b', 'c'], add)
    self.assertItemsEqual([], remove)

    add, remove = tracker_helpers._ClassifyPlusMinusItems(
        ['a-a-a', 'b-b', 'c-'])
    self.assertItemsEqual(['a-a-a', 'b-b', 'c-'], add)
    self.assertItemsEqual([], remove)

    add, remove = tracker_helpers._ClassifyPlusMinusItems(
        ['-a'])
    self.assertItemsEqual([], add)
    self.assertItemsEqual(['a'], remove)

    add, remove = tracker_helpers._ClassifyPlusMinusItems(
        ['-a', 'b', 'c-c'])
    self.assertItemsEqual(['b', 'c-c'], add)
    self.assertItemsEqual(['a'], remove)

    add, remove = tracker_helpers._ClassifyPlusMinusItems(
        ['-a', '-b-b', '-c-'])
    self.assertItemsEqual([], add)
    self.assertItemsEqual(['a', 'b-b', 'c-'], remove)

    # We dedup, but we don't cancel out items that are both added and removed.
    add, remove = tracker_helpers._ClassifyPlusMinusItems(
        ['a', 'a', '-a'])
    self.assertItemsEqual(['a'], add)
    self.assertItemsEqual(['a'], remove)

  def testParseIssueRequestFields(self):
    parsed_fields = tracker_helpers._ParseIssueRequestFields(fake.PostData({
        'custom_1': ['https://hello.com'],
        'custom_12': ['https://blah.com'],
        'custom_14': ['https://remove.com'],
        'custom_15_goats': ['2', '3'],
        'custom_15_sheep': ['3', '5'],
        'custom_16_sheep': ['yarn'],
        'op_custom_14': ['remove'],
        'op_custom_12': ['clear'],
        'op_custom_16_sheep': ['remove'],
        'ignore': 'no matter',}))
    self.assertEqual(
        parsed_fields,
        tracker_helpers.ParsedFields(
            {
                1: ['https://hello.com'],
                12: ['https://blah.com']
            }, {14: ['https://remove.com']}, [12],
            {15: {
                'goats': ['2', '3'],
                'sheep': ['3', '5']
            }}, {16: {
                'sheep': ['yarn']
            }}))

  def testParseIssueRequestAttachments(self):
    file1 = testing_helpers.Blank(
        filename='hello.c',
        value='hello world')

    file2 = testing_helpers.Blank(
        filename='README',
        value='Welcome to our project')

    file3 = testing_helpers.Blank(
        filename='c:\\dir\\subdir\\FILENAME.EXT',
        value='Abort, Retry, or Fail?')

    # Browsers send this if FILE field was not filled in.
    file4 = testing_helpers.Blank(
        filename='',
        value='')

    attachments = tracker_helpers._ParseIssueRequestAttachments({})
    self.assertEqual([], attachments)

    attachments = tracker_helpers._ParseIssueRequestAttachments(fake.PostData({
        'file1': [file1],
        }))
    self.assertEqual(
        [('hello.c', 'hello world', 'text/plain')],
        attachments)

    attachments = tracker_helpers._ParseIssueRequestAttachments(fake.PostData({
        'file1': [file1],
        'file2': [file2],
        }))
    self.assertEqual(
        [('hello.c', 'hello world', 'text/plain'),
         ('README', 'Welcome to our project', 'text/plain')],
        attachments)

    attachments = tracker_helpers._ParseIssueRequestAttachments(fake.PostData({
        'file3': [file3],
        }))
    self.assertEqual(
        [('FILENAME.EXT', 'Abort, Retry, or Fail?',
          'application/octet-stream')],
        attachments)

    attachments = tracker_helpers._ParseIssueRequestAttachments(fake.PostData({
        'file1': [file4],  # Does not appear in result
        'file3': [file3],
        'file4': [file4],  # Does not appear in result
        }))
    self.assertEqual(
        [('FILENAME.EXT', 'Abort, Retry, or Fail?',
          'application/octet-stream')],
        attachments)

  def testParseIssueRequestKeptAttachments(self):
    pass  # TODO(jrobbins): Write this test.

  def testParseIssueRequestUsers(self):
    post_data = {}
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('', parsed_users.owner_username)
    self.assertEqual(
        framework_constants.NO_USER_SPECIFIED, parsed_users.owner_id)
    self.assertEqual([], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertEqual([], parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'owner': [''],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('', parsed_users.owner_username)
    self.assertEqual(
        framework_constants.NO_USER_SPECIFIED, parsed_users.owner_id)
    self.assertEqual([], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertEqual([], parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'owner': [' \t'],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('', parsed_users.owner_username)
    self.assertEqual(
        framework_constants.NO_USER_SPECIFIED, parsed_users.owner_id)
    self.assertEqual([], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertEqual([], parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'owner': ['b@example.com'],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('b@example.com', parsed_users.owner_username)
    self.assertEqual(TEST_ID_MAP['b@example.com'], parsed_users.owner_id)
    self.assertEqual([], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertEqual([], parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'owner': ['b@example.com'],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('b@example.com', parsed_users.owner_username)
    self.assertEqual(TEST_ID_MAP['b@example.com'], parsed_users.owner_id)
    self.assertEqual([], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertEqual([], parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'cc': ['b@example.com'],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('', parsed_users.owner_username)
    self.assertEqual(
        framework_constants.NO_USER_SPECIFIED, parsed_users.owner_id)
    self.assertEqual(['b@example.com'], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertEqual([TEST_ID_MAP['b@example.com']], parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'cc': ['-b@example.com, c@example.com,,'
               'a@example.com,'],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('', parsed_users.owner_username)
    self.assertEqual(
        framework_constants.NO_USER_SPECIFIED, parsed_users.owner_id)
    self.assertItemsEqual(['c@example.com', 'a@example.com'],
                          parsed_users.cc_usernames)
    self.assertEqual(['b@example.com'], parsed_users.cc_usernames_remove)
    self.assertItemsEqual([TEST_ID_MAP['c@example.com'],
                           TEST_ID_MAP['a@example.com']],
                          parsed_users.cc_ids)
    self.assertEqual([TEST_ID_MAP['b@example.com']],
                      parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'owner': ['fuhqwhgads@example.com'],
        'cc': ['c@example.com, fuhqwhgads@example.com'],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertEqual('fuhqwhgads@example.com', parsed_users.owner_username)
    gen_uid = framework_helpers.MurmurHash3_x86_32(parsed_users.owner_username)
    self.assertEqual(gen_uid, parsed_users.owner_id)  # autocreated user
    self.assertItemsEqual(
        ['c@example.com', 'fuhqwhgads@example.com'], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertItemsEqual(
       [TEST_ID_MAP['c@example.com'], gen_uid], parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

    post_data = fake.PostData({
        'cc': ['C@example.com, b@exAmple.cOm'],
        })
    parsed_users = tracker_helpers._ParseIssueRequestUsers(
        'fake connection', post_data, self.services)
    self.assertItemsEqual(
        ['c@example.com', 'b@example.com'], parsed_users.cc_usernames)
    self.assertEqual([], parsed_users.cc_usernames_remove)
    self.assertItemsEqual(
       [TEST_ID_MAP['c@example.com'], TEST_ID_MAP['b@example.com']],
       parsed_users.cc_ids)
    self.assertEqual([], parsed_users.cc_ids_remove)

  def testParseBlockers_BlockedOnNothing(self):
    """Was blocked on nothing, still nothing."""
    post_data = {tracker_helpers.BLOCKED_ON: ''}
    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKED_ON)

    self.assertEqual('', parsed_blockers.entered_str)
    self.assertEqual([], parsed_blockers.iids)
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKING))

  def testParseBlockers_BlockedOnAdded(self):
    """Was blocked on nothing; now 1, 2, 3."""
    post_data = {tracker_helpers.BLOCKED_ON: '1, 2, 3'}
    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKED_ON)

    self.assertEqual('1, 2, 3', parsed_blockers.entered_str)
    self.assertEqual([100001, 100002, 100003], parsed_blockers.iids)
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKING))

  def testParseBlockers_BlockedOnDuplicateRef(self):
    """Was blocked on nothing; now just 2, but repeated in input."""
    post_data = {tracker_helpers.BLOCKED_ON: '2, 2, 2'}
    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKED_ON)

    self.assertEqual('2, 2, 2', parsed_blockers.entered_str)
    self.assertEqual([100002], parsed_blockers.iids)
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKING))

  def testParseBlockers_Missing(self):
    """Parsing an input field that was not in the POST."""
    post_data = {}
    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKED_ON)

    self.assertEqual('', parsed_blockers.entered_str)
    self.assertEqual([], parsed_blockers.iids)
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKING))

  def testParseBlockers_SameIssueNoProject(self):
    """Adding same issue as blocker should modify the errors object."""
    post_data = {'id': '2', tracker_helpers.BLOCKING: '2, 3'}

    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKING)
    self.assertEqual('2, 3', parsed_blockers.entered_str)
    self.assertEqual([], parsed_blockers.iids)
    self.assertEqual(
        getattr(self.errors, tracker_helpers.BLOCKING),
        'Cannot be blocking the same issue')
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))

  def testParseBlockers_SameIssueSameProject(self):
    """Adding same issue as blocker should modify the errors object."""
    post_data = {'id': '2', tracker_helpers.BLOCKING: 'testproj:2, 3'}

    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKING)
    self.assertEqual('testproj:2, 3', parsed_blockers.entered_str)
    self.assertEqual([], parsed_blockers.iids)
    self.assertEqual(
        getattr(self.errors, tracker_helpers.BLOCKING),
        'Cannot be blocking the same issue')
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))

  def testParseBlockers_SameIssueDifferentProject(self):
    """Adding different blocker issue should not modify the errors object."""
    post_data = {'id': '2', tracker_helpers.BLOCKING: 'testproj:2'}

    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testprojB',
        tracker_helpers.BLOCKING)
    self.assertEqual('testproj:2', parsed_blockers.entered_str)
    self.assertEqual([100002], parsed_blockers.iids)
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKING))
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))

  def testParseBlockers_Invalid(self):
    """Input fields with invalid values should modify the errors object."""
    post_data = {tracker_helpers.BLOCKING: '2, foo',
                 tracker_helpers.BLOCKED_ON: '3, bar'}

    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKING)
    self.assertEqual('2, foo', parsed_blockers.entered_str)
    self.assertEqual([100002], parsed_blockers.iids)
    self.assertEqual(
        getattr(self.errors, tracker_helpers.BLOCKING), 'Invalid issue ID foo')
    self.assertIsNone(getattr(self.errors, tracker_helpers.BLOCKED_ON))

    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKED_ON)
    self.assertEqual('3, bar', parsed_blockers.entered_str)
    self.assertEqual([100003], parsed_blockers.iids)
    self.assertEqual(
        getattr(self.errors, tracker_helpers.BLOCKED_ON),
        'Invalid issue ID bar')

  def testParseBlockers_Dangling(self):
    """A ref to a sanctioned projected should be allowed."""
    post_data = {'id': '2', tracker_helpers.BLOCKING: 'otherproj:2'}
    real_codesite_projects = settings.recognized_codesite_projects
    settings.recognized_codesite_projects = ['otherproj']
    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKING)
    self.assertEqual('otherproj:2', parsed_blockers.entered_str)
    self.assertEqual([('otherproj', 2)], parsed_blockers.dangling_refs)
    settings.recognized_codesite_projects = real_codesite_projects

  def testParseBlockers_FederatedReferences(self):
    """Should parse and return FedRefs."""
    post_data = {'id': '9', tracker_helpers.BLOCKING: '2, b/123, 3, b/789'}
    parsed_blockers = tracker_helpers._ParseBlockers(
        self.cnxn, post_data, self.services, self.errors, 'testproj',
        tracker_helpers.BLOCKING)
    self.assertEqual('2, b/123, 3, b/789', parsed_blockers.entered_str)
    self.assertEqual([100002, 100003], parsed_blockers.iids)
    self.assertEqual(['b/123', 'b/789'], parsed_blockers.federated_ref_strings)

  def testIsValidIssueOwner(self):
    project = project_pb2.Project()
    project.owner_ids.extend([1, 2])
    project.committer_ids.extend([3])
    project.contributor_ids.extend([4, 999])

    valid, _ = tracker_helpers.IsValidIssueOwner(
        'fake cnxn', project, framework_constants.NO_USER_SPECIFIED,
        self.services)
    self.assertTrue(valid)

    valid, _ = tracker_helpers.IsValidIssueOwner(
        'fake cnxn', project, 1,
        self.services)
    self.assertTrue(valid)
    valid, _ = tracker_helpers.IsValidIssueOwner(
        'fake cnxn', project, 2,
        self.services)
    self.assertTrue(valid)
    valid, _ = tracker_helpers.IsValidIssueOwner(
        'fake cnxn', project, 3,
        self.services)
    self.assertTrue(valid)
    valid, _ = tracker_helpers.IsValidIssueOwner(
        'fake cnxn', project, 4,
        self.services)
    self.assertTrue(valid)

    valid, _ = tracker_helpers.IsValidIssueOwner(
        'fake cnxn', project, 7,
        self.services)
    self.assertFalse(valid)

    valid, _ = tracker_helpers.IsValidIssueOwner(
        'fake cnxn', project, 999,
        self.services)
    self.assertFalse(valid)

  # MakeViewsForUsersInIssuesTest is tested in MakeViewsForUsersInIssuesTest.

  def testGetAllowedOpenedAndClosedIssues(self):
    pass  # TOOD(jrobbins): Write this test.

  def testFormatIssueListURL_JumpedToIssue(self):
    """If we jumped to issue 123, the list is can=1&q=id-123."""
    config = tracker_pb2.ProjectIssueConfig()
    path = '/p/proj/issues/detail?id=123&q=123'
    mr = testing_helpers.MakeMonorailRequest(
        path=path, headers={'Host': 'code.google.com'})
    mr.ComputeColSpec(config)

    absolute_base_url = 'http://code.google.com'

    url_1 = tracker_helpers.FormatIssueListURL(mr, config)
    self.assertEqual(
        '%s/p/proj/issues/list?can=1&%s&q=id%%3D123' % (
            absolute_base_url, self.default_colspec_param),
        url_1)

  def testFormatIssueListURL_NoCurrentState(self):
    config = tracker_pb2.ProjectIssueConfig()
    path = '/p/proj/issues/detail?id=123'
    mr = testing_helpers.MakeMonorailRequest(
        path=path, headers={'Host': 'code.google.com'})
    mr.ComputeColSpec(config)

    absolute_base_url = 'http://code.google.com'

    url_1 = tracker_helpers.FormatIssueListURL(mr, config)
    self.assertEqual(
        '%s/p/proj/issues/list?%s&q=' % (
            absolute_base_url, self.default_colspec_param),
        url_1)

    url_2 = tracker_helpers.FormatIssueListURL(
        mr, config, foo=123)
    self.assertEqual(
        '%s/p/proj/issues/list?%s&foo=123&q=' % (
            absolute_base_url, self.default_colspec_param),
        url_2)

    url_3 = tracker_helpers.FormatIssueListURL(
        mr, config, foo=123, bar='abc')
    self.assertEqual(
        '%s/p/proj/issues/list?bar=abc&%s&foo=123&q=' % (
            absolute_base_url, self.default_colspec_param),
        url_3)

    url_4 = tracker_helpers.FormatIssueListURL(
        mr, config, baz='escaped+encoded&and100% "safe"')
    self.assertEqual(
        '%s/p/proj/issues/list?'
        'baz=escaped%%2Bencoded%%26and100%%25%%20%%22safe%%22&%s&q=' % (
            absolute_base_url, self.default_colspec_param),
        url_4)

  def testFormatIssueListURL_KeepCurrentState(self):
    config = tracker_pb2.ProjectIssueConfig()
    path = '/p/proj/issues/detail?id=123&sort=aa&colspec=a b c&groupby=d'
    mr = testing_helpers.MakeMonorailRequest(
        path=path, headers={'Host': 'localhost:8080'})
    mr.ComputeColSpec(config)

    absolute_base_url = 'http://localhost:8080'

    url_1 = tracker_helpers.FormatIssueListURL(mr, config)
    self.assertEqual(
        '%s/p/proj/issues/list?colspec=a%%20b%%20c'
        '&groupby=d&q=&sort=aa' % absolute_base_url,
        url_1)

    url_2 = tracker_helpers.FormatIssueListURL(
        mr, config, foo=123)
    self.assertEqual(
        '%s/p/proj/issues/list?'
        'colspec=a%%20b%%20c&foo=123&groupby=d&q=&sort=aa' % absolute_base_url,
        url_2)

    url_3 = tracker_helpers.FormatIssueListURL(
        mr, config, colspec='X Y Z')
    self.assertEqual(
        '%s/p/proj/issues/list?colspec=a%%20b%%20c'
        '&groupby=d&q=&sort=aa' % absolute_base_url,
        url_3)

  def testFormatRelativeIssueURL(self):
    self.assertEqual(
        '/p/proj/issues/attachment',
        tracker_helpers.FormatRelativeIssueURL(
            'proj', urls.ISSUE_ATTACHMENT))

    self.assertEqual(
        '/p/proj/issues/detail?id=123',
        tracker_helpers.FormatRelativeIssueURL(
            'proj', urls.ISSUE_DETAIL, id=123))

  @mock.patch('google.appengine.api.app_identity.get_application_id')
  def testFormatCrBugURL_Prod(self, mock_get_app_id):
    mock_get_app_id.return_value = 'monorail-prod'
    self.assertEqual(
        'https://crbug.com/proj/123',
        tracker_helpers.FormatCrBugURL('proj', 123))
    self.assertEqual(
        'https://crbug.com/123456',
        tracker_helpers.FormatCrBugURL('chromium', 123456))

  @mock.patch('google.appengine.api.app_identity.get_application_id')
  def testFormatCrBugURL_NonProd(self, mock_get_app_id):
    mock_get_app_id.return_value = 'monorail-staging'
    self.assertEqual(
        '/p/proj/issues/detail?id=123',
        tracker_helpers.FormatCrBugURL('proj', 123))
    self.assertEqual(
        '/p/chromium/issues/detail?id=123456',
        tracker_helpers.FormatCrBugURL('chromium', 123456))

  def testComputeNewQuotaBytesUsed(self):
    pass  # TODO(jrobbins): Write this test.

  def testIsUnderSoftAttachmentQuota(self):
    pass  # TODO(jrobbins): Write this test.

  # GetAllIssueProjects is tested in GetAllIssueProjectsTest.

  def testGetPermissionsInAllProjects(self):
    pass  # TODO(jrobbins): Write this test.

  # FilterOutNonViewableIssues is tested in FilterOutNonViewableIssuesTest.

  def testMeansOpenInProject(self):
    config = _MakeConfig()

    # ensure open means open
    self.assertTrue(tracker_helpers.MeansOpenInProject('New', config))
    self.assertTrue(tracker_helpers.MeansOpenInProject('new', config))

    # ensure an unrecognized status means open
    self.assertTrue(tracker_helpers.MeansOpenInProject(
        '_undefined_status_', config))

    # ensure closed means closed
    self.assertFalse(tracker_helpers.MeansOpenInProject('Old', config))
    self.assertFalse(tracker_helpers.MeansOpenInProject('old', config))
    self.assertFalse(tracker_helpers.MeansOpenInProject(
        'StatusThatWeDontUseAnymore', config))

  def testIsNoisy(self):
    self.assertTrue(tracker_helpers.IsNoisy(778, 320))
    self.assertFalse(tracker_helpers.IsNoisy(20, 500))
    self.assertFalse(tracker_helpers.IsNoisy(500, 20))
    self.assertFalse(tracker_helpers.IsNoisy(1, 1))

  def testMergeCCsAndAddComment(self):
    target_issue = fake.MakeTestIssue(
        789, 10, 'Target issue', 'New', 111)
    source_issue = fake.MakeTestIssue(
        789, 100, 'Source issue', 'New', 222)
    source_issue.cc_ids.append(111)
    # Issue without owner
    source_issue_2 = fake.MakeTestIssue(
        789, 101, 'Source issue 2', 'New', 0)

    self.services.issue.TestAddIssue(target_issue)
    self.services.issue.TestAddIssue(source_issue)
    self.services.issue.TestAddIssue(source_issue_2)

    # We copy this list so that it isn't updated by the test framework
    initial_issue_comments = (
        self.services.issue.GetCommentsForIssue(
            'fake cnxn', target_issue.issue_id)[:])
    mr = testing_helpers.MakeMonorailRequest(user_info={'user_id': 111})

    # Merging source into target should create a comment.
    self.assertIsNotNone(
        tracker_helpers.MergeCCsAndAddComment(
            self.services, mr, source_issue, target_issue))
    updated_issue_comments = self.services.issue.GetCommentsForIssue(
        'fake cnxn', target_issue.issue_id)
    for comment in initial_issue_comments:
      self.assertIn(comment, updated_issue_comments)
      self.assertEqual(
          len(initial_issue_comments) + 1, len(updated_issue_comments))

    # Merging source into target should add source's owner to target's CCs.
    updated_target_issue = self.services.issue.GetIssueByLocalID(
        'fake cnxn', 789, 10)
    self.assertIn(111, updated_target_issue.cc_ids)
    self.assertIn(222, updated_target_issue.cc_ids)

    # Merging source 2 into target should make a comment, but not update CCs.
    self.assertIsNotNone(
        tracker_helpers.MergeCCsAndAddComment(
            self.services, mr, source_issue_2, updated_target_issue))
    updated_target_issue = self.services.issue.GetIssueByLocalID(
        'fake cnxn', 789, 10)
    self.assertNotIn(0, updated_target_issue.cc_ids)

  def testMergeCCsAndAddComment_RestrictedSourceIssue(self):
    target_issue = fake.MakeTestIssue(
        789, 10, 'Target issue', 'New', 222)
    target_issue_2 = fake.MakeTestIssue(
        789, 11, 'Target issue 2', 'New', 222)
    source_issue = fake.MakeTestIssue(
        789, 100, 'Source issue', 'New', 111)
    source_issue.cc_ids.append(111)
    source_issue.labels.append('Restrict-View-Commit')
    target_issue_2.labels.append('Restrict-View-Commit')

    self.services.issue.TestAddIssue(source_issue)
    self.services.issue.TestAddIssue(target_issue)
    self.services.issue.TestAddIssue(target_issue_2)

    # We copy this list so that it isn't updated by the test framework
    initial_issue_comments = self.services.issue.GetCommentsForIssue(
        'fake cnxn', target_issue.issue_id)[:]
    mr = testing_helpers.MakeMonorailRequest(user_info={'user_id': 111})
    self.assertIsNotNone(
        tracker_helpers.MergeCCsAndAddComment(
            self.services, mr, source_issue, target_issue))

    # When the source is restricted, we update the target comments...
    updated_issue_comments = self.services.issue.GetCommentsForIssue(
        'fake cnxn', target_issue.issue_id)
    for comment in initial_issue_comments:
      self.assertIn(comment, updated_issue_comments)
      self.assertEqual(
          len(initial_issue_comments) + 1, len(updated_issue_comments))
    # ...but not the target CCs...
    updated_target_issue = self.services.issue.GetIssueByLocalID(
        'fake cnxn', 789, 10)
    self.assertNotIn(111, updated_target_issue.cc_ids)
    # ...unless both issues have the same restrictions.
    self.assertIsNotNone(
        tracker_helpers.MergeCCsAndAddComment(
            self.services, mr, source_issue, target_issue_2))
    updated_target_issue_2 = self.services.issue.GetIssueByLocalID(
        'fake cnxn', 789, 11)
    self.assertIn(111, updated_target_issue_2.cc_ids)

  def testMergeCCsAndAddCommentMultipleIssues(self):
    pass  # TODO(jrobbins): Write this test.

  def testGetAttachmentIfAllowed(self):
    pass  # TODO(jrobbins): Write this test.

  def testLabelsMaskedByFields(self):
    pass  # TODO(jrobbins): Write this test.

  def testLabelsNotMaskedByFields(self):
    pass  # TODO(jrobbins): Write this test.

  def testLookupComponentIDs(self):
    pass  # TODO(jrobbins): Write this test.

  def testParsePostDataUsers(self):
    pd_users = 'a@example.com, b@example.com'

    pd_users_ids, pd_users_str = tracker_helpers.ParsePostDataUsers(
        self.cnxn, pd_users, self.services.user)

    self.assertEqual([1, 2], sorted(pd_users_ids))
    self.assertEqual('a@example.com, b@example.com', pd_users_str)

  def testParsePostDataUsers_Empty(self):
    pd_users = ''

    pd_users_ids, pd_users_str = tracker_helpers.ParsePostDataUsers(
        self.cnxn, pd_users, self.services.user)

    self.assertEqual([], sorted(pd_users_ids))
    self.assertEqual('', pd_users_str)

  def testFilterIssueTypes(self):
    pass  # TODO(jrobbins): Write this test.

  # ParseMergeFields is tested in IssueMergeTest.
  # AddIssueStarrers is tested in IssueMergeTest.testMergeIssueStars().
  # IsMergeAllowed is tested in IssueMergeTest.

  def testPairDerivedValuesWithRuleExplanations_Nothing(self):
    """Test we return nothing for an issue with no derived values."""
    proposed_issue = tracker_pb2.Issue()  # No derived values.
    traces = {}
    derived_users_by_id = {}
    actual = tracker_helpers.PairDerivedValuesWithRuleExplanations(
        proposed_issue, traces, derived_users_by_id)
    (derived_labels_and_why, derived_owner_and_why,
     derived_cc_and_why, warnings_and_why, errors_and_why) = actual
    self.assertEqual([], derived_labels_and_why)
    self.assertEqual([], derived_owner_and_why)
    self.assertEqual([], derived_cc_and_why)
    self.assertEqual([], warnings_and_why)
    self.assertEqual([], errors_and_why)

  def testPairDerivedValuesWithRuleExplanations_SomeValues(self):
    """Test we return derived values and explanations for an issue."""
    proposed_issue = tracker_pb2.Issue(
        derived_owner_id=111, derived_cc_ids=[222, 333],
        derived_labels=['aaa', 'zzz'],
        derived_warnings=['Watch out'],
        derived_errors=['Status Assigned requires an owner'])
    traces = {
        (tracker_pb2.FieldID.OWNER, 111): 'explain 1',
        (tracker_pb2.FieldID.CC, 222): 'explain 2',
        (tracker_pb2.FieldID.CC, 333): 'explain 3',
        (tracker_pb2.FieldID.LABELS, 'aaa'): 'explain 4',
        (tracker_pb2.FieldID.WARNING, 'Watch out'): 'explain 6',
        (tracker_pb2.FieldID.ERROR,
         'Status Assigned requires an owner'): 'explain 7',
        # There can be extra traces that are not used.
        (tracker_pb2.FieldID.LABELS, 'bbb'): 'explain 5',
        # If there is no trace for some derived value, why is None.
        }
    derived_users_by_id = {
      111: testing_helpers.Blank(display_name='one@example.com'),
      222: testing_helpers.Blank(display_name='two@example.com'),
      333: testing_helpers.Blank(display_name='three@example.com'),
      }
    actual = tracker_helpers.PairDerivedValuesWithRuleExplanations(
        proposed_issue, traces, derived_users_by_id)
    (derived_labels_and_why, derived_owner_and_why,
     derived_cc_and_why, warnings_and_why, errors_and_why) = actual
    self.assertEqual([
        {'value': 'aaa', 'why': 'explain 4'},
        {'value': 'zzz', 'why': None},
        ], derived_labels_and_why)
    self.assertEqual([
        {'value': 'one@example.com', 'why': 'explain 1'},
        ], derived_owner_and_why)
    self.assertEqual([
        {'value': 'two@example.com', 'why': 'explain 2'},
        {'value': 'three@example.com', 'why': 'explain 3'},
        ], derived_cc_and_why)
    self.assertEqual([
        {'value': 'Watch out', 'why': 'explain 6'},
        ], warnings_and_why)
    self.assertEqual([
        {'value': 'Status Assigned requires an owner', 'why': 'explain 7'},
        ], errors_and_why)


class MakeViewsForUsersInIssuesTest(unittest.TestCase):

  def setUp(self):
    self.issue1 = _Issue('proj', 1, 'summary 1', 'New')
    self.issue1.owner_id = 1001
    self.issue1.reporter_id = 1002

    self.issue2 = _Issue('proj', 2, 'summary 2', 'New')
    self.issue2.owner_id = 2001
    self.issue2.reporter_id = 2002
    self.issue2.cc_ids.extend([1, 1001, 1002, 1003])

    self.issue3 = _Issue('proj', 3, 'summary 3', 'New')
    self.issue3.owner_id = 1001
    self.issue3.reporter_id = 3002

    self.user = fake.UserService()
    for user_id in [1, 1001, 1002, 1003, 2001, 2002, 3002]:
      self.user.TestAddUser(
          'test%d' % user_id, user_id, add_user=True)

  def testMakeViewsForUsersInIssues(self):
    issue_list = [self.issue1, self.issue2, self.issue3]
    users_by_id = tracker_helpers.MakeViewsForUsersInIssues(
        'fake cnxn', issue_list, self.user)
    self.assertItemsEqual([0, 1, 1001, 1002, 1003, 2001, 2002, 3002],
                          list(users_by_id.keys()))
    for user_id in [1001, 1002, 1003, 2001]:
      self.assertEqual(users_by_id[user_id].user_id, user_id)

  def testMakeViewsForUsersInIssuesOmittingSome(self):
    issue_list = [self.issue1, self.issue2, self.issue3]
    users_by_id = tracker_helpers.MakeViewsForUsersInIssues(
        'fake cnxn', issue_list, self.user, omit_ids=[1001, 1003])
    self.assertItemsEqual([0, 1, 1002, 2001, 2002, 3002],
        list(users_by_id.keys()))
    for user_id in [1002, 2001, 2002, 3002]:
      self.assertEqual(users_by_id[user_id].user_id, user_id)

  def testMakeViewsForUsersInIssuesEmpty(self):
    issue_list = []
    users_by_id = tracker_helpers.MakeViewsForUsersInIssues(
        'fake cnxn', issue_list, self.user)
    self.assertItemsEqual([], list(users_by_id.keys()))


class GetAllIssueProjectsTest(unittest.TestCase):
  issue_x_1 = tracker_pb2.Issue()
  issue_x_1.project_id = 789
  issue_x_1.local_id = 1
  issue_x_1.reporter_id = 1002

  issue_x_2 = tracker_pb2.Issue()
  issue_x_2.project_id = 789
  issue_x_2.local_id = 2
  issue_x_2.reporter_id = 2002

  issue_y_1 = tracker_pb2.Issue()
  issue_y_1.project_id = 678
  issue_y_1.local_id = 1
  issue_y_1.reporter_id = 2002

  def setUp(self):
    self.project_service = fake.ProjectService()
    self.project_service.TestAddProject('proj-x', project_id=789)
    self.project_service.TestAddProject('proj-y', project_id=678)
    self.cnxn = 'fake connection'

  def testGetAllIssueProjects_Empty(self):
    self.assertEqual(
        {}, tracker_helpers.GetAllIssueProjects(
            self.cnxn, [], self.project_service))

  def testGetAllIssueProjects_Normal(self):
    self.assertEqual(
        {789: self.project_service.GetProjectByName(self.cnxn, 'proj-x')},
        tracker_helpers.GetAllIssueProjects(
            self.cnxn, [self.issue_x_1, self.issue_x_2], self.project_service))
    self.assertEqual(
        {789: self.project_service.GetProjectByName(self.cnxn, 'proj-x'),
         678: self.project_service.GetProjectByName(self.cnxn, 'proj-y')},
        tracker_helpers.GetAllIssueProjects(
            self.cnxn, [self.issue_x_1, self.issue_x_2, self.issue_y_1],
            self.project_service))


class FilterOutNonViewableIssuesTest(unittest.TestCase):
  owner_id = 111
  committer_id = 222
  nonmember_1_id = 1002
  nonmember_2_id = 2002
  nonmember_3_id = 3002

  issue1 = tracker_pb2.Issue()
  issue1.project_name = 'proj'
  issue1.project_id = 789
  issue1.local_id = 1
  issue1.reporter_id = nonmember_1_id

  issue2 = tracker_pb2.Issue()
  issue2.project_name = 'proj'
  issue2.project_id = 789
  issue2.local_id = 2
  issue2.reporter_id = nonmember_2_id
  issue2.labels.extend(['foo', 'bar'])

  issue3 = tracker_pb2.Issue()
  issue3.project_name = 'proj'
  issue3.project_id = 789
  issue3.local_id = 3
  issue3.reporter_id = nonmember_3_id
  issue3.labels.extend(['restrict-view-commit'])

  issue4 = tracker_pb2.Issue()
  issue4.project_name = 'proj'
  issue4.project_id = 789
  issue4.local_id = 4
  issue4.reporter_id = nonmember_3_id
  issue4.labels.extend(['Foo', 'Restrict-View-Commit'])

  def setUp(self):
    self.user = user_pb2.User()
    self.project = self.MakeProject(project_pb2.ProjectState.LIVE)
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(
        self.project.project_id)
    self.project_dict = {self.project.project_id: self.project}
    self.config_dict = {self.config.project_id: self.config}

  def MakeProject(self, state):
    p = project_pb2.Project(
        project_id=789, project_name='proj', state=state,
        owner_ids=[self.owner_id], committer_ids=[self.committer_id])
    return p

  def testFilterOutNonViewableIssues_Member(self):
    # perms will be permissions.COMMITTER_ACTIVE_PERMISSIONSET
    filtered_issues = tracker_helpers.FilterOutNonViewableIssues(
        {self.committer_id}, self.user, self.project_dict,
        self.config_dict,
        [self.issue1, self.issue2, self.issue3, self.issue4])
    self.assertListEqual([1, 2, 3, 4],
                         [issue.local_id for issue in filtered_issues])

  def testFilterOutNonViewableIssues_Owner(self):
    # perms will be permissions.OWNER_ACTIVE_PERMISSIONSET
    filtered_issues = tracker_helpers.FilterOutNonViewableIssues(
        {self.owner_id}, self.user, self.project_dict, self.config_dict,
        [self.issue1, self.issue2, self.issue3, self.issue4])
    self.assertListEqual([1, 2, 3, 4],
                         [issue.local_id for issue in filtered_issues])

  def testFilterOutNonViewableIssues_Empty(self):
    # perms will be permissions.COMMITTER_ACTIVE_PERMISSIONSET
    filtered_issues = tracker_helpers.FilterOutNonViewableIssues(
        {self.committer_id}, self.user, self.project_dict,
        self.config_dict, [])
    self.assertListEqual([], filtered_issues)

  def testFilterOutNonViewableIssues_NonMember(self):
    # perms will be permissions.READ_ONLY_PERMISSIONSET
    filtered_issues = tracker_helpers.FilterOutNonViewableIssues(
        {self.nonmember_1_id}, self.user, self.project_dict,
        self.config_dict, [self.issue1, self.issue2, self.issue3, self.issue4])
    self.assertListEqual([1, 2],
                         [issue.local_id for issue in filtered_issues])

  def testFilterOutNonViewableIssues_Reporter(self):
    # perms will be permissions.READ_ONLY_PERMISSIONSET
    filtered_issues = tracker_helpers.FilterOutNonViewableIssues(
        {self.nonmember_3_id}, self.user, self.project_dict,
        self.config_dict, [self.issue1, self.issue2, self.issue3, self.issue4])
    self.assertListEqual([1, 2, 3, 4],
                         [issue.local_id for issue in filtered_issues])


class IssueMergeTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        project=fake.ProjectService(),
        issue_star=fake.IssueStarService(),
        spam=fake.SpamService()
    )
    self.project = self.services.project.TestAddProject('proj', project_id=987)
    self.config = tracker_bizobj.MakeDefaultProjectIssueConfig(
        self.project.project_id)
    self.project_dict = {self.project.project_id: self.project}
    self.config_dict = {self.config.project_id: self.config}

  def testParseMergeFields_NotSpecified(self):
    issue = fake.MakeTestIssue(987, 1, 'summary', 'New', 111)
    errors = template_helpers.EZTError()
    post_data = {}

    text, merge_into_issue = tracker_helpers.ParseMergeFields(
        self.cnxn, None, 'proj', post_data, 'New', self.config, issue, errors)
    self.assertEqual('', text)
    self.assertEqual(None, merge_into_issue)

    text, merge_into_issue = tracker_helpers.ParseMergeFields(
        self.cnxn, None, 'proj', post_data, 'Duplicate', self.config, issue,
        errors)
    self.assertEqual('', text)
    self.assertTrue(errors.merge_into_id)
    self.assertEqual(None, merge_into_issue)

  def testParseMergeFields_WrongStatus(self):
    issue = fake.MakeTestIssue(987, 1, 'summary', 'New', 111)
    errors = template_helpers.EZTError()
    post_data = {'merge_into': '12'}

    text, merge_into_issue = tracker_helpers.ParseMergeFields(
        self.cnxn, None, 'proj', post_data, 'New', self.config, issue, errors)
    self.assertEqual('', text)
    self.assertEqual(None, merge_into_issue)

  def testParseMergeFields_NoSuchIssue(self):
    issue = fake.MakeTestIssue(987, 1, 'summary', 'New', 111)
    issue.merged_into = 12
    errors = template_helpers.EZTError()
    post_data = {'merge_into': '12'}

    text, merge_into_issue = tracker_helpers.ParseMergeFields(
        self.cnxn, self.services, 'proj', post_data, 'Duplicate',
        self.config, issue, errors)
    self.assertEqual('12', text)
    self.assertEqual(None, merge_into_issue)

  def testParseMergeFields_DontSelfMerge(self):
    issue = fake.MakeTestIssue(987, 1, 'summary', 'New', 111)
    errors = template_helpers.EZTError()
    post_data = {'merge_into': '1'}

    text, merge_into_issue = tracker_helpers.ParseMergeFields(
        self.cnxn, self.services, 'proj', post_data, 'Duplicate', self.config,
        issue, errors)
    self.assertEqual('1', text)
    self.assertEqual(None, merge_into_issue)
    self.assertEqual('Cannot merge issue into itself', errors.merge_into_id)

  def testParseMergeFields_NewIssueToMerge(self):
    merged_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services,
        self.project.project_id, 'unused_summary', 'unused_status', 111,
        [], [], [], [], 111, 'unused_marked_description')
    mergee_local_id, _ = self.services.issue.CreateIssue(
        self.cnxn, self.services,
        self.project.project_id, 'unused_summary', 'unused_status', 111,
        [], [], [], [], 111, 'unused_marked_description')
    merged_issue = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, merged_local_id)
    mergee_issue = self.services.issue.GetIssueByLocalID(
        self.cnxn, self.project.project_id, mergee_local_id)

    errors = template_helpers.EZTError()
    post_data = {'merge_into': str(mergee_issue.local_id)}

    text, merge_into_issue = tracker_helpers.ParseMergeFields(
        self.cnxn, self.services, 'proj', post_data, 'Duplicate', self.config,
        merged_issue, errors)
    self.assertEqual(str(mergee_issue.local_id), text)
    self.assertEqual(mergee_issue, merge_into_issue)

  def testIsMergeAllowed(self):
    mr = testing_helpers.MakeMonorailRequest()
    issue = fake.MakeTestIssue(987, 1, 'summary', 'New', 111)
    issue.project_name = self.project.project_name

    for (perm_set, expected_merge_allowed) in (
            (permissions.READ_ONLY_PERMISSIONSET, False),
            (permissions.COMMITTER_INACTIVE_PERMISSIONSET, False),
            (permissions.COMMITTER_ACTIVE_PERMISSIONSET, True),
            (permissions.OWNER_ACTIVE_PERMISSIONSET, True)):
      mr.perms = perm_set
      merge_allowed = tracker_helpers.IsMergeAllowed(issue, mr, self.services)
      self.assertEqual(expected_merge_allowed, merge_allowed)

  def testMergeIssueStars(self):
    mr = testing_helpers.MakeMonorailRequest()
    mr.project_name = self.project.project_name
    mr.project = self.project

    config = self.services.config.GetProjectConfig(
        self.cnxn, self.project.project_id)
    self.services.issue_star.SetStar(
        self.cnxn, self.services, config, 1, 1, True)
    self.services.issue_star.SetStar(
        self.cnxn, self.services, config, 1, 2, True)
    self.services.issue_star.SetStar(
        self.cnxn, self.services, config, 1, 3, True)
    self.services.issue_star.SetStar(
        self.cnxn, self.services, config, 2, 3, True)
    self.services.issue_star.SetStar(
        self.cnxn, self.services, config, 2, 4, True)
    self.services.issue_star.SetStar(
        self.cnxn, self.services, config, 2, 5, True)

    new_starrers = tracker_helpers.GetNewIssueStarrers(
        self.cnxn, self.services, 1, 2)
    self.assertItemsEqual(new_starrers, [1, 2])
    tracker_helpers.AddIssueStarrers(
        self.cnxn, self.services, mr, 2, self.project, new_starrers)
    issue_2_starrers = self.services.issue_star.LookupItemStarrers(
        self.cnxn, 2)
    # XXX(jrobbins): these tests incorrectly mix local IDs with IIDs.
    self.assertItemsEqual([1, 2, 3, 4, 5], issue_2_starrers)


class MergeLinkedMembersTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        user=fake.UserService())
    self.user1 = self.services.user.TestAddUser('one@example.com', 111)
    self.user2 = self.services.user.TestAddUser('two@example.com', 222)

  def testNoLinkedAccounts(self):
    """When no candidate accounts are linked, they are all returned."""
    actual = tracker_helpers._MergeLinkedMembers(
        self.cnxn, self.services.user, [111, 222])
    self.assertEqual([111, 222], actual)

  def testSomeLinkedButNoMasking(self):
    """If an account has linked accounts, but they are not here, keep it."""
    self.user1.linked_child_ids = [999]
    self.user2.linked_parent_id = 999
    actual = tracker_helpers._MergeLinkedMembers(
        self.cnxn, self.services.user, [111, 222])
    self.assertEqual([111, 222], actual)

  def testParentMasksChild(self):
    """When two accounts linked, only the parent is returned."""
    self.user2.linked_parent_id = 111
    actual = tracker_helpers._MergeLinkedMembers(
        self.cnxn, self.services.user, [111, 222])
    self.assertEqual([111], actual)


class FilterMemberDataTest(unittest.TestCase):

  def setUp(self):
    services = service_manager.Services(
        project=fake.ProjectService(),
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService())
    self.owner_email = 'owner@dom.com'
    self.committer_email = 'commit@dom.com'
    self.contributor_email = 'contrib@dom.com'
    self.indirect_member_email = 'ind@dom.com'
    self.all_emails = [self.owner_email, self.committer_email,
                       self.contributor_email, self.indirect_member_email]
    self.project = services.project.TestAddProject('proj')

  def DoFiltering(self, perms, unsigned_user=False):
    mr = testing_helpers.MakeMonorailRequest(
        project=self.project, perms=perms)
    if not unsigned_user:
      mr.auth.user_id = 111
      mr.auth.user_view = testing_helpers.Blank(domain='jrobbins.org')
    return tracker_helpers._FilterMemberData(
        mr, [self.owner_email], [self.committer_email],
        [self.contributor_email], [self.indirect_member_email], mr.project)

  def testUnsignedUser_NormalProject(self):
    visible_members = self.DoFiltering(
        permissions.READ_ONLY_PERMISSIONSET, unsigned_user=True)
    self.assertItemsEqual(
        [self.owner_email, self.committer_email, self.contributor_email,
         self.indirect_member_email],
        visible_members)

  def testUnsignedUser_RestrictedProject(self):
    self.project.only_owners_see_contributors = True
    visible_members = self.DoFiltering(
        permissions.READ_ONLY_PERMISSIONSET, unsigned_user=True)
    self.assertItemsEqual(
        [self.owner_email, self.committer_email, self.indirect_member_email],
        visible_members)

  def testOwnersAndAdminsCanSeeAll_NormalProject(self):
    visible_members = self.DoFiltering(
        permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.ADMIN_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

  def testOwnersAndAdminsCanSeeAll_HubAndSpoke(self):
    self.project.only_owners_see_contributors = True

    visible_members = self.DoFiltering(
        permissions.OWNER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.ADMIN_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

  def testNonOwnersCanSeeAll_NormalProject(self):
    visible_members = self.DoFiltering(
        permissions.COMMITTER_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

    visible_members = self.DoFiltering(
        permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(self.all_emails, visible_members)

  def testCommittersSeeOnlySameDomain_HubAndSpoke(self):
    self.project.only_owners_see_contributors = True

    visible_members = self.DoFiltering(
        permissions.CONTRIBUTOR_ACTIVE_PERMISSIONSET)
    self.assertItemsEqual(
        [self.owner_email, self.committer_email, self.indirect_member_email],
        visible_members)


class GetLabelOptionsTest(unittest.TestCase):

  @mock.patch('tracker.tracker_helpers.LabelsNotMaskedByFields')
  def testGetLabelOptions(self, mockLabelsNotMaskedByFields):
    mockLabelsNotMaskedByFields.return_value = []
    config = tracker_pb2.ProjectIssueConfig()
    custom_perms = []
    actual = tracker_helpers.GetLabelOptions(config, custom_perms)
    expected = [
      {'doc': 'Only users who can edit the issue may access it',
       'name': 'Restrict-View-EditIssue'},
      {'doc': 'Only users who can edit the issue may add comments',
       'name': 'Restrict-AddIssueComment-EditIssue'},
      {'doc': 'Custom permission CoreTeam is needed to access',
       'name': 'Restrict-View-CoreTeam'}
    ]
    self.assertEqual(expected, actual)

  def testBuildRestrictionChoices(self):
    choices = tracker_helpers._BuildRestrictionChoices([], [], [])
    self.assertEqual([], choices)

    choices = tracker_helpers._BuildRestrictionChoices(
        [], ['Hop', 'Jump'], [])
    self.assertEqual([], choices)

    freq = [('View', 'B', 'You need permission B to do anything'),
            ('A', 'B', 'You need B to use A')]
    choices = tracker_helpers._BuildRestrictionChoices(freq, [], [])
    expected = [dict(name='Restrict-View-B',
                     doc='You need permission B to do anything'),
                dict(name='Restrict-A-B',
                     doc='You need B to use A')]
    self.assertListEqual(expected, choices)

    extra_perms = ['Over18', 'Over21']
    choices = tracker_helpers._BuildRestrictionChoices(
        [], ['Drink', 'Smoke'], extra_perms)
    expected = [dict(name='Restrict-Drink-Over18',
                     doc='Permission Over18 needed to use Drink'),
                dict(name='Restrict-Drink-Over21',
                     doc='Permission Over21 needed to use Drink'),
                dict(name='Restrict-Smoke-Over18',
                     doc='Permission Over18 needed to use Smoke'),
                dict(name='Restrict-Smoke-Over21',
                     doc='Permission Over21 needed to use Smoke')]
    self.assertListEqual(expected, choices)


class FilterKeptAttachmentsTest(unittest.TestCase):
  def testFilterKeptAttachments(self):
    comments = [
        tracker_pb2.IssueComment(
            is_description=True,
            attachments=[tracker_pb2.Attachment(attachment_id=1)]),
        tracker_pb2.IssueComment(),
        tracker_pb2.IssueComment(
            is_description=True,
            attachments=[
                tracker_pb2.Attachment(attachment_id=2),
                tracker_pb2.Attachment(attachment_id=3)]),
        tracker_pb2.IssueComment(),
        tracker_pb2.IssueComment(
            approval_id=24,
            is_description=True,
            attachments=[tracker_pb2.Attachment(attachment_id=4)])]

    filtered = tracker_helpers.FilterKeptAttachments(
        True, [1, 2, 3, 4], comments, None)
    self.assertEqual([2, 3], filtered)

  def testApprovalDescription(self):
    comments = [
        tracker_pb2.IssueComment(
            is_description=True,
            attachments=[tracker_pb2.Attachment(attachment_id=1)]),
        tracker_pb2.IssueComment(),
        tracker_pb2.IssueComment(
            is_description=True,
            attachments=[
                tracker_pb2.Attachment(attachment_id=2),
                tracker_pb2.Attachment(attachment_id=3)]),
        tracker_pb2.IssueComment(),
        tracker_pb2.IssueComment(
            approval_id=24,
            is_description=True,
            attachments=[tracker_pb2.Attachment(attachment_id=4)])]

    filtered = tracker_helpers.FilterKeptAttachments(
        True, [1, 2, 3, 4], comments, 24)
    self.assertEqual([4], filtered)

  def testNotAnIssueDescription(self):
    comments = [
        tracker_pb2.IssueComment(
            is_description=True,
            attachments=[tracker_pb2.Attachment(attachment_id=1)]),
        tracker_pb2.IssueComment(),
        tracker_pb2.IssueComment(
            is_description=True,
            attachments=[
                tracker_pb2.Attachment(attachment_id=2),
                tracker_pb2.Attachment(attachment_id=3)]),
        tracker_pb2.IssueComment(),
        tracker_pb2.IssueComment(
            approval_id=24,
            is_description=True,
            attachments=[tracker_pb2.Attachment(attachment_id=4)])]

    filtered = tracker_helpers.FilterKeptAttachments(
        False, [1, 2, 3, 4], comments, None)
    self.assertIsNone(filtered)

  def testNoDescriptionsInComments(self):
    comments = [
        tracker_pb2.IssueComment(),
        tracker_pb2.IssueComment()]

    filtered = tracker_helpers.FilterKeptAttachments(
        True, [1, 2, 3, 4], comments, None)
    self.assertEqual([], filtered)

  def testNoComments(self):
    filtered = tracker_helpers.FilterKeptAttachments(
        True, [1, 2, 3, 4], [], None)
    self.assertEqual([], filtered)


class EnumFieldHelpersTest(unittest.TestCase):

  def test_GetEnumFieldValuesAndDocstrings(self):
    """We can get all choices for an enum field"""
    fd = tracker_pb2.FieldDef(
        field_id=123,
        project_id=1,
        field_name='yellow',
        field_type=tracker_pb2.FieldTypes.ENUM_TYPE)
    ld_1 = tracker_pb2.LabelDef(
        label='yellow-submarine', label_docstring='ld_1_docstring')
    ld_2 = tracker_pb2.LabelDef(
        label='yellow-tisket', label_docstring='ld_2_docstring')
    ld_3 = tracker_pb2.LabelDef(
        label='yellow-basket', label_docstring='ld_3_docstring')
    ld_4 = tracker_pb2.LabelDef(
        label='yellow', label_docstring='ld_4_docstring')
    ld_5 = tracker_pb2.LabelDef(
        label='not-yellow', label_docstring='ld_5_docstring')
    ld_6 = tracker_pb2.LabelDef(
        label='yellow-tasket',
        label_docstring='ld_6_docstring',
        deprecated=True)
    config = tracker_pb2.ProjectIssueConfig(
        default_template_for_developers=1,
        default_template_for_users=2,
        well_known_labels=[ld_1, ld_2, ld_3, ld_4, ld_5, ld_6])
    actual = tracker_helpers._GetEnumFieldValuesAndDocstrings(fd, config)
    # Expect to omit labels `yellow` and `not-yellow` due to prefix mismatch
    # Also expect to omit label `yellow-tasket` because it's deprecated
    expected = [
        ('submarine', 'ld_1_docstring'), ('tisket', 'ld_2_docstring'),
        ('basket', 'ld_3_docstring')
    ]
    self.assertEqual(expected, actual)
