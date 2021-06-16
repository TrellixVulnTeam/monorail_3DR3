# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import apiclient.discovery
import mock
import unittest

from infra.services.bugdroid import monorail_client


class MonorailClientTest(unittest.TestCase):

  def setUp(self):
    self.mock_api_client = mock.Mock()
    self.client = monorail_client.MonorailClient(
        '', client=self.mock_api_client)

    # Alias these to make shorter lines below.
    self.get = self.mock_api_client.issues.return_value.get
    self.insert = (
        self.mock_api_client.issues.return_value.comments.return_value.insert)

  def test_get_issue(self):
    self.get.return_value.execute.return_value = {
      'id': 123,
      'labels': ['one', 'two'],
    }

    ret = self.client.get_issue('foo', 123)
    self.assertIsInstance(ret, monorail_client.Issue)
    self.assertEquals(123, ret.id)
    self.assertEquals(['one', 'two'], ret.labels)

    self.get.assert_called_once_with(projectId='foo', issueId=123)

  def test_get_issue_missing_labels(self):
    self.get.return_value.execute.return_value = {'id': 123}

    ret = self.client.get_issue('foo', 123)
    self.assertEquals([], ret.labels)

  def test_update_not_dirty_issue(self):
    issue = monorail_client.Issue(123, [])
    self.client.update_issue('foo', issue)
    self.assertFalse(self.insert.called)

  def test_update_issue_comment(self):
    issue = monorail_client.Issue(123, [])
    issue.set_comment('hello')
    self.client.update_issue('foo', issue)

    self.insert.assert_called_once_with(
        projectId='foo',
        issueId=123,
        sendEmail=True,
        body={
            'id': 123,
            'updates': {},
            'content': 'hello',
        })

  def test_update_issue_add_label(self):
    issue = monorail_client.Issue(123, [])
    issue.add_label('one')
    self.client.update_issue('foo', issue)

    self.insert.assert_called_once_with(
        projectId='foo',
        issueId=123,
        sendEmail=True,
        body={
            'id': 123,
            'updates': {'labels': ['one']},
        })

  def test_update_issue_add_existing_label(self):
    issue = monorail_client.Issue(123, ['one'])
    issue.add_label('one')
    self.client.update_issue('foo', issue)

    self.assertFalse(self.insert.called)

  def test_update_issue_remove_label(self):
    issue = monorail_client.Issue(123, ['one', 'two'])
    issue.remove_label('two')
    self.assertFalse(issue.has_label('two'))
    self.client.update_issue('foo', issue)

    self.insert.assert_called_once_with(
        projectId='foo',
        issueId=123,
        sendEmail=True,
        body={
            'id': 123,
            'updates': {'labels': ['-two']},
        })

  def test_update_issue_remove_non_existing_label(self):
    issue = monorail_client.Issue(123, ['one', 'two'])
    issue.remove_label('three')
    self.client.update_issue('foo', issue)

    self.assertFalse(self.insert.called)

  def test_update_issue_fixed(self):
    issue = monorail_client.Issue(123, [])
    issue.mark_fixed()
    self.client.update_issue('foo', issue)

    self.insert.assert_called_once_with(
        projectId='foo',
        issueId=123,
        sendEmail=True,
        body={
            'id': 123,
            'updates': {'status': 'Fixed'},
        })

  @mock.patch('logging.debug')
  def test_unicode_decode_error(self, mock_debug):
    http = self.insert.return_value
    http.postproc.side_effect = UnicodeDecodeError('', '', 1, 2, '')

    # The real Http.execute calls postproc.  Postproc calls str.decode which
    # sometimes raises a UnicodeDecodeError.  We make our postproc raise that
    # UnicodeDecodeError by setting the side_effect above.
    # monorail_client monkey-patches the postproc method to catch that exception
    # and log it.
    def fake_execute(*_args, **_kwargs):
      # This calls the wrapped function, which calls the original one we set
      # the side_effect on above.
      http.postproc({'foo': 'bar'}, 'blah blah')
    http.execute.side_effect = fake_execute

    issue = monorail_client.Issue(123, [])
    issue.set_comment('hello')

    with self.assertRaises(UnicodeDecodeError):
      self.client.update_issue('foo', issue)

    mock_debug.assert_called_once_with(
        'Error decoding UTF-8 HTTP response.  Response headers:\n%r\n'
        'Response body:\n%r', {'foo': 'bar'}, 'blah blah')
