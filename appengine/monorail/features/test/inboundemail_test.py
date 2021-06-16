# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.feature.inboundemail."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest
import webapp2
from mock import patch

import mox
import time

from google.appengine.ext.webapp.mail_handlers import BounceNotificationHandler

import settings
from businesslogic import work_env
from features import alert2issue
from features import commitlogcommands
from features import inboundemail
from framework import authdata
from framework import emailfmt
from framework import monorailcontext
from framework import permissions
from proto import project_pb2
from proto import tracker_pb2
from proto import user_pb2
from services import service_manager
from testing import fake
from testing import testing_helpers
from tracker import tracker_helpers


class InboundEmailTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        config=fake.ConfigService(),
        issue=fake.IssueService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        project=fake.ProjectService())
    self.project = self.services.project.TestAddProject(
        'proj', project_id=987, process_inbound_email=True,
        contrib_ids=[111])
    self.project_addr = 'proj@monorail.example.com'

    self.issue = tracker_pb2.Issue()
    self.issue.project_id = 987
    self.issue.local_id = 100
    self.services.issue.TestAddIssue(self.issue)

    self.msg = testing_helpers.MakeMessage(
        testing_helpers.HEADER_LINES, 'awesome!')

    request, _ = testing_helpers.GetRequestObjects()
    self.inbound = inboundemail.InboundEmail(request, None, self.services)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testTemplates(self):
    for name, template_path in self.inbound._templates.items():
      assert(name in inboundemail.MSG_TEMPLATES)
      assert(
          template_path.GetTemplatePath().endswith(
              inboundemail.MSG_TEMPLATES[name]))

  def testProcessMail_MsgTooBig(self):
    self.mox.StubOutWithMock(emailfmt, 'IsBodyTooBigToParse')
    emailfmt.IsBodyTooBigToParse(mox.IgnoreArg()).AndReturn(True)
    self.mox.ReplayAll()

    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEqual(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual('Email body too long', email_task['subject'])

  def testProcessMail_NoProjectOnToLine(self):
    self.mox.StubOutWithMock(emailfmt, 'IsProjectAddressOnToLine')
    emailfmt.IsProjectAddressOnToLine(
        self.project_addr, [self.project_addr]).AndReturn(False)
    self.mox.ReplayAll()

    ret = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessMail_IssueUnidentified(self):
    self.mox.StubOutWithMock(emailfmt, 'IdentifyProjectVerbAndLabel')
    emailfmt.IdentifyProjectVerbAndLabel(self.project_addr).AndReturn(('proj',
        None, None))

    self.mox.StubOutWithMock(emailfmt, 'IdentifyIssue')
    emailfmt.IdentifyIssue('proj', mox.IgnoreArg()).AndReturn((None))

    self.mox.ReplayAll()

    ret = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessMail_ProjectNotLive(self):
    self.services.user.TestAddUser('user@example.com', 111)
    self.project.state = project_pb2.ProjectState.DELETABLE
    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual('Project not found', email_task['subject'])

  def testProcessMail_ProjectInboundEmailDisabled(self):
    self.services.user.TestAddUser('user@example.com', 111)
    self.project.process_inbound_email = False
    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual(
        'Email replies are not enabled in project proj', email_task['subject'])

  def testProcessMail_NoRefHeader(self):
    self.services.user.TestAddUser('user@example.com', 111)
    self.mox.StubOutWithMock(emailfmt, 'ValidateReferencesHeader')
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(False)
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(False)
    self.mox.ReplayAll()

    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEqual(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual(
        'Your message is not a reply to a notification email',
        email_task['subject'])

  def testProcessMail_NoAccount(self):
    # Note: not calling TestAddUser().
    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEqual(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual(
        'Could not determine account of sender', email_task['subject'])

  def testProcessMail_BannedAccount(self):
    user_pb = self.services.user.TestAddUser('user@example.com', 111)
    user_pb.banned = 'banned'

    self.mox.StubOutWithMock(emailfmt, 'ValidateReferencesHeader')
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(True)
    self.mox.ReplayAll()

    email_tasks = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertEqual(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual(
        'You are banned from using this issue tracker', email_task['subject'])

  def testProcessMail_Success(self):
    self.services.user.TestAddUser('user@example.com', 111)

    self.mox.StubOutWithMock(emailfmt, 'ValidateReferencesHeader')
    emailfmt.ValidateReferencesHeader(
        mox.IgnoreArg(), self.project, mox.IgnoreArg(),
        mox.IgnoreArg()).AndReturn(True)

    self.mox.StubOutWithMock(self.inbound, 'ProcessIssueReply')
    self.inbound.ProcessIssueReply(
        mox.IgnoreArg(), self.project, 123, self.project_addr,
        'awesome!')

    self.mox.ReplayAll()

    ret = self.inbound.ProcessMail(self.msg, self.project_addr)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessMail_Success_with_AlertNotification(self):
    """Test ProcessMail with an alert notification message.

    This is a sanity check for alert2issue.ProcessEmailNotification to ensure
    that it can be successfully invoked in ProcessMail. Each function of
    alert2issue module should be tested in aler2issue_test.
    """
    project_name = self.project.project_name
    verb = 'alert'
    trooper_queue = 'my-trooper'
    project_addr = '%s+%s+%s@example.com' % (project_name, verb, trooper_queue)

    self.mox.StubOutWithMock(emailfmt, 'IsProjectAddressOnToLine')
    emailfmt.IsProjectAddressOnToLine(
        project_addr, mox.IgnoreArg()).AndReturn(True)

    class MockAuthData(object):
      def __init__(self):
        self.user_pb = user_pb2.MakeUser(111)
        self.effective_ids = set([1, 2, 3])
        self.user_id = 111
        self.email = 'user@example.com'

    mock_auth_data = MockAuthData()
    self.mox.StubOutWithMock(authdata.AuthData, 'FromEmail')
    authdata.AuthData.FromEmail(
        mox.IgnoreArg(), settings.alert_service_account, self.services,
        autocreate=True).AndReturn(mock_auth_data)

    self.mox.StubOutWithMock(alert2issue, 'ProcessEmailNotification')
    alert2issue.ProcessEmailNotification(
        self.services, mox.IgnoreArg(), self.project, project_addr,
        mox.IgnoreArg(), mock_auth_data, mox.IgnoreArg(), 'awesome!', '',
        self.msg, trooper_queue)

    self.mox.ReplayAll()
    ret = self.inbound.ProcessMail(self.msg, project_addr)
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessIssueReply_NoIssue(self):
    nonexistant_local_id = 200
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    email_tasks = self.inbound.ProcessIssueReply(
        mc, self.project, nonexistant_local_id, self.project_addr,
        'awesome!')
    self.assertEqual(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual(
        'Could not find issue %d in project %s' %
        (nonexistant_local_id, self.project.project_name),
        email_task['subject'])

  def testProcessIssueReply_DeletedIssue(self):
    self.issue.deleted = True
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    mc.LookupLoggedInUserPerms(self.project)

    email_tasks = self.inbound.ProcessIssueReply(
        mc, self.project, self.issue.local_id, self.project_addr,
        'awesome!')
    self.assertEqual(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual(
        'Could not find issue %d in project %s' %
        (self.issue.local_id, self.project.project_name), email_task['subject'])

  def VerifyUserHasNoPerm(self, perms):
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    mc.perms = perms

    email_tasks = self.inbound.ProcessIssueReply(
        mc, self.project, self.issue.local_id, self.project_addr,
        'awesome!')
    self.assertEqual(1, len(email_tasks))
    email_task = email_tasks[0]
    self.assertEqual('user@example.com', email_task['to'])
    self.assertEqual(
        'User does not have permission to add a comment', email_task['subject'])

  def testProcessIssueReply_NoViewPerm(self):
    self.VerifyUserHasNoPerm(permissions.EMPTY_PERMISSIONSET)

  def testProcessIssueReply_CantViewRestrictedIssue(self):
    self.issue.labels.append('Restrict-View-CoreTeam')
    self.VerifyUserHasNoPerm(permissions.USER_PERMISSIONSET)

  def testProcessIssueReply_NoAddIssuePerm(self):
    self.VerifyUserHasNoPerm(permissions.READ_ONLY_PERMISSIONSET)

  def testProcessIssueReply_NoEditIssuePerm(self):
    self.services.user.TestAddUser('user@example.com', 111)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    mc.perms = permissions.USER_PERMISSIONSET
    mock_uia = commitlogcommands.UpdateIssueAction(self.issue.local_id)

    self.mox.StubOutWithMock(commitlogcommands, 'UpdateIssueAction')
    commitlogcommands.UpdateIssueAction(self.issue.local_id).AndReturn(mock_uia)

    self.mox.StubOutWithMock(mock_uia, 'Parse')
    mock_uia.Parse(
        self.cnxn, self.project.project_name, 111, ['awesome!'], self.services,
        strip_quoted_lines=True)
    self.mox.StubOutWithMock(mock_uia, 'Run')
    # mc.perms does not contain permission EDIT_ISSUE.
    mock_uia.Run(mc, self.services)

    self.mox.ReplayAll()
    ret = self.inbound.ProcessIssueReply(
        mc, self.project, self.issue.local_id, self.project_addr,
        'awesome!')
    self.mox.VerifyAll()
    self.assertIsNone(ret)

  def testProcessIssueReply_Success(self):
    self.services.user.TestAddUser('user@example.com', 111)
    mc = monorailcontext.MonorailContext(
        self.services, cnxn=self.cnxn, requester='user@example.com')
    mc.perms = permissions.COMMITTER_ACTIVE_PERMISSIONSET
    mock_uia = commitlogcommands.UpdateIssueAction(self.issue.local_id)

    self.mox.StubOutWithMock(commitlogcommands, 'UpdateIssueAction')
    commitlogcommands.UpdateIssueAction(self.issue.local_id).AndReturn(mock_uia)

    self.mox.StubOutWithMock(mock_uia, 'Parse')
    mock_uia.Parse(
        self.cnxn, self.project.project_name, 111, ['awesome!'], self.services,
        strip_quoted_lines=True)
    self.mox.StubOutWithMock(mock_uia, 'Run')
    mock_uia.Run(mc, self.services)

    self.mox.ReplayAll()
    ret = self.inbound.ProcessIssueReply(
        mc, self.project, self.issue.local_id, self.project_addr,
        'awesome!')
    self.mox.VerifyAll()
    self.assertIsNone(ret)


class BouncedEmailTest(unittest.TestCase):

  def setUp(self):
    self.cnxn = 'fake cnxn'
    self.services = service_manager.Services(
        user=fake.UserService())
    self.user = self.services.user.TestAddUser('user@example.com', 111)

    app = webapp2.WSGIApplication(config={'services': self.services})
    app.set_globals(app=app)

    self.servlet = inboundemail.BouncedEmail()
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testPost_Normal(self):
    """Normally, our post() just calls BounceNotificationHandler post()."""
    self.mox.StubOutWithMock(BounceNotificationHandler, 'post')
    BounceNotificationHandler.post()
    self.mox.ReplayAll()

    self.servlet.post()
    self.mox.VerifyAll()

  def testPost_Exception(self):
    """Our post() method works around an escaping bug."""
    self.servlet.request = webapp2.Request.blank(
        '/', POST={'raw-message': 'this is an email message'})

    self.mox.StubOutWithMock(BounceNotificationHandler, 'post')
    BounceNotificationHandler.post().AndRaise(AttributeError())
    BounceNotificationHandler.post()
    self.mox.ReplayAll()

    self.servlet.post()
    self.mox.VerifyAll()

  def testReceive_Normal(self):
    """Find the user that bounced and set email_bounce_timestamp."""
    self.assertEqual(0, self.user.email_bounce_timestamp)

    bounce_message = testing_helpers.Blank(original={'to': 'user@example.com'})
    self.servlet.receive(bounce_message)

    self.assertNotEqual(0, self.user.email_bounce_timestamp)

  def testReceive_NoSuchUser(self):
    """When not found, log it and ignore without creating a user record."""
    self.servlet.request = webapp2.Request.blank(
        '/', POST={'raw-message': 'this is an email message'})
    bounce_message = testing_helpers.Blank(
        original={'to': 'nope@example.com'},
        notification='notification')
    self.servlet.receive(bounce_message)
    self.assertEqual(1, len(self.services.user.users_by_id))
