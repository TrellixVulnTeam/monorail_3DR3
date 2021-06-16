# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A servlet for project owners to create a new field def."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re
import time

from third_party import ezt

from framework import exceptions
from framework import framework_helpers
from framework import jsonfeed
from framework import permissions
from framework import servlet
from framework import urls
from proto import tracker_pb2
from tracker import field_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


class FieldCreate(servlet.Servlet):
  """Servlet allowing project owners to create a custom field."""

  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_PROCESS
  _PAGE_TEMPLATE = 'tracker/field-create-page.ezt'

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(FieldCreate, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'You are not allowed to administer this project')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    well_known_issue_types = tracker_helpers.FilterIssueTypes(config)
    approval_names = [fd.field_name for fd in config.field_defs if
                      fd.field_type is tracker_pb2.FieldTypes.APPROVAL_TYPE and
                      not fd.is_deleted]

    return {
        'admin_tab_mode': servlet.Servlet.PROCESS_TAB_LABELS,
        'initial_field_name': '',
        'initial_field_docstring': '',
        'initial_importance': 'normal',
        'initial_is_multivalued': ezt.boolean(False),
        'initial_parent_approval_name': '',
        'initial_choices': '',
        'initial_admins': '',
        'initial_editors': '',
        'initial_type': 'enum_type',
        'initial_applicable_type': '',  # That means any issue type
        'initial_applicable_predicate': '',
        'initial_needs_member': ezt.boolean(False),
        'initial_needs_perm': '',
        'initial_grants_perm': '',
        'initial_notify_on': 0,
        'initial_date_action': 'no_action',
        'well_known_issue_types': well_known_issue_types,
        'initial_approvers': '',
        'initial_survey': '',
        'approval_names': approval_names,
        'initial_is_phase_field': ezt.boolean(False),
        'initial_is_restricted_field': ezt.boolean(False),
    }

  def ProcessFormData(self, mr, post_data):
    """Validate and store the contents of the issues tracker admin page.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    parsed = field_helpers.ParseFieldDefRequest(post_data, config)

    if not tracker_constants.FIELD_NAME_RE.match(parsed.field_name):
      mr.errors.field_name = 'Invalid field name'

    field_name_error_msg = FieldNameErrorMessage(parsed.field_name, config)
    if field_name_error_msg:
      mr.errors.field_name = field_name_error_msg

    admin_ids, admin_str = tracker_helpers.ParsePostDataUsers(
        mr.cnxn, post_data['admin_names'], self.services.user)
    editor_ids, editor_str = tracker_helpers.ParsePostDataUsers(
        mr.cnxn, post_data.get('editor_names', ''), self.services.user)

    field_helpers.ParsedFieldDefAssertions(mr, parsed)

    if not (parsed.is_restricted_field):
      assert not editor_ids, 'Editors are only for restricted fields.'

    # TODO(crbug/monorail/7275): This condition could potentially be
    # included in the field_helpers.ParsedFieldDefAssertions method,
    # just remember that it should be compatible with its usage in
    # fielddetail.py where there is a very similar condition.
    if parsed.field_type_str == 'approval_type':
      assert not (
          parsed.is_restricted_field), 'Approval fields cannot be restricted.'
      if parsed.approvers_str:
        approver_ids_dict = self.services.user.LookupUserIDs(
            mr.cnxn, re.split('[,;\s]+', parsed.approvers_str),
            autocreate=True)
        approver_ids = list(set(approver_ids_dict.values()))
      else:
        mr.errors.approvers = 'Please provide at least one default approver.'

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr,
          initial_field_name=parsed.field_name,
          initial_type=parsed.field_type_str,
          initial_parent_approval_name=parsed.parent_approval_name,
          initial_field_docstring=parsed.field_docstring,
          initial_applicable_type=parsed.applicable_type,
          initial_applicable_predicate=parsed.applicable_predicate,
          initial_needs_member=ezt.boolean(parsed.needs_member),
          initial_needs_perm=parsed.needs_perm,
          initial_importance=parsed.importance,
          initial_is_multivalued=ezt.boolean(parsed.is_multivalued),
          initial_grants_perm=parsed.grants_perm,
          initial_notify_on=parsed.notify_on,
          initial_date_action=parsed.date_action_str,
          initial_choices=parsed.choices_text,
          initial_approvers=parsed.approvers_str,
          initial_survey=parsed.survey,
          initial_is_phase_field=parsed.is_phase_field,
          initial_admins=admin_str,
          initial_editors=editor_str,
          initial_is_restricted_field=parsed.is_restricted_field)
      return

    approval_id = None
    if parsed.parent_approval_name and (
        parsed.field_type_str != 'approval_type'):
      approval_fd = tracker_bizobj.FindFieldDef(
          parsed.parent_approval_name, config)
      if approval_fd:
        approval_id = approval_fd.field_id
    field_id = self.services.config.CreateFieldDef(
        mr.cnxn,
        mr.project_id,
        parsed.field_name,
        parsed.field_type_str,
        parsed.applicable_type,
        parsed.applicable_predicate,
        parsed.is_required,
        parsed.is_niche,
        parsed.is_multivalued,
        parsed.min_value,
        parsed.max_value,
        parsed.regex,
        parsed.needs_member,
        parsed.needs_perm,
        parsed.grants_perm,
        parsed.notify_on,
        parsed.date_action_str,
        parsed.field_docstring,
        admin_ids,
        editor_ids,
        approval_id,
        parsed.is_phase_field,
        is_restricted_field=parsed.is_restricted_field)
    if parsed.field_type_str == 'approval_type':
      revised_approvals = field_helpers.ReviseApprovals(
          field_id, approver_ids, parsed.survey, config)
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project, approval_defs=revised_approvals)
    if parsed.field_type_str == 'enum_type':
      self.services.config.UpdateConfig(
          mr.cnxn, mr.project, well_known_labels=parsed.revised_labels)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ADMIN_LABELS, saved=1, ts=int(time.time()))


def FieldNameErrorMessage(field_name, config):
  """Return an error message for the given field name, or None."""
  field_name_lower = field_name.lower()
  if field_name_lower in tracker_constants.RESERVED_PREFIXES:
    return 'That name is reserved.'
  if field_name_lower.endswith(
      tuple(tracker_constants.RESERVED_COL_NAME_SUFFIXES)):
    return 'That suffix is reserved.'

  for fd in config.field_defs:
    fn_lower = fd.field_name.lower()
    if field_name_lower == fn_lower:
      return 'That name is already in use.'
    if field_name_lower.startswith(fn_lower + '-'):
      return 'An existing field name is a prefix of that name.'
    if fn_lower.startswith(field_name_lower + '-'):
      return 'That name is a prefix of an existing field name.'

  return None
