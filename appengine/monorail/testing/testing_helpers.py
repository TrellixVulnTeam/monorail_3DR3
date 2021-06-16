# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helpers for testing."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import email

from framework import emailfmt
from framework import framework_bizobj
from proto import user_pb2
from services import service_manager
from services import template_svc
from testing import fake
from tracker import tracker_constants
import webapp2

DEFAULT_HOST = '127.0.0.1'

MINIMAL_HEADER_LINES = [
    ('From', 'user@example.com'),
    ('To', 'proj@monorail.example.com'),
    ('Cc', 'ningerso@chromium.org'),
    ('Subject', 'Issue 123 in proj: broken link'),
]

# Add one more (long) line for In-Reply-To
HEADER_LINES = MINIMAL_HEADER_LINES + [
    ('In-Reply-To', '<0=969704940193871313=13442892928193434663='
     'proj@monorail.example.com>'),
]

AlertEmailHeader = emailfmt.AlertEmailHeader
ALERT_EMAIL_HEADER_LINES = HEADER_LINES + [
    (AlertEmailHeader.INCIDENT_ID, '1234567890123456789'),
    (AlertEmailHeader.OWNER, 'owner@example.com'),
    (AlertEmailHeader.CC, 'cc1@example.com,cc2@example.com'),
    (AlertEmailHeader.PRIORITY, '0'),
    (AlertEmailHeader.STATUS, 'Unconfirmed'),
    (AlertEmailHeader.COMPONENT, 'Component'),
    (AlertEmailHeader.TYPE, 'Bug'),
    (AlertEmailHeader.OS, 'Android,Windows'),
    (AlertEmailHeader.LABEL, ''),
]


# TODO(crbug/monorail/7238): this should be moved to framework_bizobj
# as this is no longer only used for testing.
def ObscuredEmail(address):
  (_username, _domain, _obs_username,
   obs_email) = framework_bizobj.ParseAndObscureAddress(address)
  return obs_email

def MakeMessage(header_list, body):
  """Convenience function to make an email.message.Message."""
  msg = email.message.Message()
  for key, value in header_list:
    msg[key] = value
  msg.set_payload(body)
  return msg


def MakeMonorailRequest(*args, **kwargs):
  """Get just the monorailrequest.MonorailRequest() from GetRequestObjects."""
  _request, mr = GetRequestObjects(*args, **kwargs)
  return mr


def GetRequestObjects(
    headers=None, path='/', params=None, payload=None, user_info=None,
    project=None, method='GET', perms=None, services=None, hotlist=None):
  """Make fake request and MonorailRequest objects for testing.

  Host param will override the 'Host' header, and has a default value of
  '127.0.0.1'.

  Args:
    headers: Dict of HTTP header strings.
    path: Path part of the URL in the request.
    params: Dict of query-string parameters.
    user_info: Dict of user attributes to set on a MonorailRequest object.
        For example, "user_id: 5" causes self.auth.user_id=5.
    project: optional Project object for the current request.
    method: 'GET' or 'POST'.
    perms: PermissionSet to use for this request.
    services: Connections to backends.
    hotlist: optional Hotlist object for the current request

  Returns:
    A tuple of (http Request, monorailrequest.MonorailRequest()).
  """
  headers = headers or {}
  params = params or {}

  headers.setdefault('Host', DEFAULT_HOST)
  post_items=None
  if method == 'POST' and payload:
    post_items = payload
  elif method == 'POST' and params:
    post_items = params

  if not services:
    services = service_manager.Services(
        project=fake.ProjectService(),
        user=fake.UserService(),
        usergroup=fake.UserGroupService(),
        features=fake.FeaturesService())
    services.project.TestAddProject('proj')
    services.features.TestAddHotlist('hotlist')

  request = webapp2.Request.blank(path, headers=headers, POST=post_items)
  mr = fake.MonorailRequest(
      services, user_info=user_info, project=project, perms=perms,
      params=params, hotlist=hotlist)
  mr.ParseRequest(
      request, services, do_user_lookups=False)
  mr.auth.user_pb = user_pb2.MakeUser(0)
  return request, mr


class Blank(object):
  """Simple class that assigns all named args to attributes.

  Tip: supply a lambda to define a method.
  """

  def __init__(self, **kwargs):
    vars(self).update(kwargs)

  def __repr__(self):
    return '%s(%s)' % (self.__class__.__name__, str(vars(self)))

  def __eq__(self, other):
    if other is None:
      return False
    return vars(self) == vars(other)


def DefaultTemplateRows():
  return [(
    None,
    789,
    template_dict['name'],
    template_dict['content'],
    template_dict['summary'],
    template_dict.get('summary_must_be_edited'),
    None,
    template_dict['status'],
    template_dict.get('members_only', False),
    template_dict.get('owner_defaults_to_member', True),
    template_dict.get('component_required', False),
    ) for template_dict in tracker_constants.DEFAULT_TEMPLATES]


def DefaultTemplates():
  return [template_svc.UnpackTemplate(t) for t in DefaultTemplateRows()]
