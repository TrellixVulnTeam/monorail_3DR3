# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Helper functions for custom field sevlets."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import itertools
import logging
import re

from features import autolink_constants
from framework import authdata
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import permissions
from framework import timestr
from framework import validate
from proto import tracker_pb2
from services import config_svc
from tracker import tracker_bizobj


INVALID_USER_ID = -1

ParsedFieldDef = collections.namedtuple(
    'ParsedFieldDef',
    'field_name, field_type_str, min_value, max_value, regex, '
    'needs_member, needs_perm, grants_perm, notify_on, is_required, '
    'is_niche, importance, is_multivalued, field_docstring, choices_text, '
    'applicable_type, applicable_predicate, revised_labels, date_action_str, '
    'approvers_str, survey, parent_approval_name, is_phase_field, '
    'is_restricted_field')


def ParseFieldDefRequest(post_data, config):
  """Parse the user's HTML form data to update a field definition."""
  field_name = post_data.get('name', '')
  field_type_str = post_data.get('field_type')
  # TODO(jrobbins): once a min or max is set, it cannot be completely removed.
  min_value_str = post_data.get('min_value')
  try:
    min_value = int(min_value_str)
  except (ValueError, TypeError):
    min_value = None
  max_value_str = post_data.get('max_value')
  try:
    max_value = int(max_value_str)
  except (ValueError, TypeError):
    max_value = None
  regex = post_data.get('regex')
  needs_member = 'needs_member' in post_data
  needs_perm = post_data.get('needs_perm', '').strip()
  grants_perm = post_data.get('grants_perm', '').strip()
  notify_on_str = post_data.get('notify_on')
  if notify_on_str in config_svc.NOTIFY_ON_ENUM:
    notify_on = config_svc.NOTIFY_ON_ENUM.index(notify_on_str)
  else:
    notify_on = 0
  importance = post_data.get('importance')
  is_required = (importance == 'required')
  is_niche = (importance == 'niche')
  is_multivalued = 'is_multivalued' in post_data
  field_docstring = post_data.get('docstring', '')
  choices_text = post_data.get('choices', '')
  applicable_type = post_data.get('applicable_type', '')
  applicable_predicate = ''  # TODO(jrobbins): placeholder for future feature
  revised_labels = _ParseChoicesIntoWellKnownLabels(
      choices_text, field_name, config, field_type_str)
  date_action_str = post_data.get('date_action')
  approvers_str = post_data.get('approver_names', '').strip().rstrip(',')
  survey = post_data.get('survey', '')
  parent_approval_name = post_data.get('parent_approval_name', '')
  # TODO(jojwang): monorail:3774, remove enum_type condition when
  # phases can have labels.
  is_phase_field = ('is_phase_field' in post_data) and (
      field_type_str not in ['approval_type', 'enum_type'])
  is_restricted_field = 'is_restricted_field' in post_data

  return ParsedFieldDef(
      field_name, field_type_str, min_value, max_value, regex, needs_member,
      needs_perm, grants_perm, notify_on, is_required, is_niche, importance,
      is_multivalued, field_docstring, choices_text, applicable_type,
      applicable_predicate, revised_labels, date_action_str, approvers_str,
      survey, parent_approval_name, is_phase_field, is_restricted_field)


def _ParseChoicesIntoWellKnownLabels(
    choices_text, field_name, config, field_type_str):
  """Parse a field's possible choices and integrate them into the config.

  Args:
    choices_text: string with one label and optional docstring per line.
    field_name: string name of the field definition being edited.
    config: ProjectIssueConfig PB of the current project.
    field_type_str: string name of the new field's type. None if an existing
      field is being updated

  Returns:
    A revised list of labels that can be used to update the config.
  """
  fd = tracker_bizobj.FindFieldDef(field_name, config)
  matches = framework_constants.IDENTIFIER_DOCSTRING_RE.findall(choices_text)
  maskingFieldNames = []
  # wkls should only be masked by the field if it is an enum_type.
  if (field_type_str == 'enum_type') or (
      fd and fd.field_type is tracker_pb2.FieldTypes.ENUM_TYPE):
    maskingFieldNames.append(field_name.lower())

  new_labels = [
      ('%s-%s' % (field_name, label), choice_docstring.strip(), False)
      for label, choice_docstring in matches]
  kept_labels = [
      (wkl.label, wkl.label_docstring, wkl.deprecated)
      for wkl in config.well_known_labels
      if not tracker_bizobj.LabelIsMaskedByField(
          wkl.label, maskingFieldNames)]
  revised_labels = kept_labels + new_labels
  return revised_labels


def ShiftEnumFieldsIntoLabels(
    labels, labels_remove, field_val_strs, field_val_strs_remove, config):
  """Look at the custom field values and treat enum fields as labels.

  Args:
    labels: list of labels to add/set on the issue.
    labels_remove: list of labels to remove from the issue.
    field_val_strs: {field_id: [val_str, ...]} of custom fields to add/set.
    field_val_strs_remove: {field_id: [val_str, ...]} of custom fields to
        remove.
    config: ProjectIssueConfig PB including custom field definitions.

  SIDE-EFFECT: the labels and labels_remove lists will be extended with
  key-value labels corresponding to the enum field values.  Those field
  entries will be removed from field_vals and field_vals_remove.
  """
  for fd in config.field_defs:
    if fd.field_type != tracker_pb2.FieldTypes.ENUM_TYPE:
      continue

    if fd.field_id in field_val_strs:
      labels.extend(
          '%s-%s' % (fd.field_name, val)
          for val in field_val_strs[fd.field_id]
          if val and val != '--')
      del field_val_strs[fd.field_id]

    if fd.field_id in field_val_strs_remove:
      labels_remove.extend(
          '%s-%s' % (fd.field_name, val)
          for val in field_val_strs_remove[fd.field_id]
          if val and val != '--')
      del field_val_strs_remove[fd.field_id]


def ReviseApprovals(approval_id, approver_ids, survey, config):
  revised_approvals = [(
      approval.approval_id, approval.approver_ids, approval.survey) for
                       approval in config.approval_defs if
                       approval.approval_id != approval_id]
  revised_approvals.append((approval_id, approver_ids, survey))
  return revised_approvals


def ParseOneFieldValue(cnxn, user_service, fd, val_str):
  """Make one FieldValue PB from the given user-supplied string."""
  if fd.field_type == tracker_pb2.FieldTypes.INT_TYPE:
    try:
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, int(val_str), None, None, None, None, False)
    except ValueError:
      return None  # TODO(jrobbins): should bounce

  elif fd.field_type == tracker_pb2.FieldTypes.STR_TYPE:
    return tracker_bizobj.MakeFieldValue(
        fd.field_id, None, val_str, None, None, None, False)

  elif fd.field_type == tracker_pb2.FieldTypes.USER_TYPE:
    if val_str:
      try:
        user_id = user_service.LookupUserID(cnxn, val_str, autocreate=False)
      except exceptions.NoSuchUserException:
        # Set to invalid user ID to display error during the validation step.
        user_id = INVALID_USER_ID
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, None, None, user_id, None, None, False)
    else:
      return None

  elif fd.field_type == tracker_pb2.FieldTypes.DATE_TYPE:
    try:
      timestamp = timestr.DateWidgetStrToTimestamp(val_str)
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, None, None, None, timestamp, None, False)
    except ValueError:
      return None  # TODO(jrobbins): should bounce

  elif fd.field_type == tracker_pb2.FieldTypes.URL_TYPE:
    val_str = FormatUrlFieldValue(val_str)
    try:
      return tracker_bizobj.MakeFieldValue(
          fd.field_id, None, None, None, None, val_str, False)
    except ValueError:
      return None # TODO(jojwang): should bounce

  else:
    logging.error('Cant parse field with unexpected type %r', fd.field_type)
    return None


def ParseOnePhaseFieldValue(cnxn, user_service, fd, val_str, phase_ids):
  """Return a list containing a FieldValue PB for each phase."""
  phase_fvs = []
  for phase_id in phase_ids:
    # TODO(jojwang): monorail:3970, create the FieldValue once and find some
    # proto2 CopyFrom() method to create a new one for each phase.
    fv = ParseOneFieldValue(cnxn, user_service, fd, val_str)
    if fv:
      fv.phase_id = phase_id
      phase_fvs.append(fv)

  return phase_fvs


def ParseFieldValues(cnxn, user_service, field_val_strs, phase_field_val_strs,
                     config, phase_ids_by_name=None):
  """Return a list of FieldValue PBs based on the given dict of strings."""
  field_values = []
  for fd in config.field_defs:
    if fd.is_phase_field and (
        fd.field_id in phase_field_val_strs) and phase_ids_by_name:
      fvs_by_phase_name = phase_field_val_strs.get(fd.field_id, {})
      for phase_name, val_strs in fvs_by_phase_name.items():
        phase_ids = phase_ids_by_name.get(phase_name)
        if not phase_ids:
          continue
        for val_str in val_strs:
          field_values.extend(
              ParseOnePhaseFieldValue(
                  cnxn, user_service, fd, val_str, phase_ids=phase_ids))
    # We do not save phase fields when there are no phases.
    elif not fd.is_phase_field and (fd.field_id in field_val_strs):
      for val_str in field_val_strs[fd.field_id]:
        fv = ParseOneFieldValue(cnxn, user_service, fd, val_str)
        if fv:
          field_values.append(fv)

  return field_values


def ValidateCustomFieldValue(mr, project, services, field_def, field_val):
  """Validate one custom field value and return an error string or None."""
  if field_def.field_type == tracker_pb2.FieldTypes.INT_TYPE:
    if (field_def.min_value is not None and
        field_val.int_value < field_def.min_value):
      return 'Value must be >= %d' % field_def.min_value
    if (field_def.max_value is not None and
        field_val.int_value > field_def.max_value):
      return 'Value must be <= %d' % field_def.max_value

  elif field_def.field_type == tracker_pb2.FieldTypes.STR_TYPE:
    if field_def.regex and field_val.str_value:
      try:
        regex = re.compile(field_def.regex)
        if not regex.match(field_val.str_value):
          return 'Value must match regular expression: %s' % field_def.regex
      except re.error:
        logging.info('Failed to process regex %r with value %r. Allowing.',
                     field_def.regex, field_val.str_value)
        return None

  elif field_def.field_type == tracker_pb2.FieldTypes.USER_TYPE:
    field_val_user = services.user.GetUser(mr.cnxn, field_val.user_id)
    auth = authdata.AuthData.FromUser(mr.cnxn, field_val_user, services)
    if auth.user_pb.user_id == INVALID_USER_ID:
      return 'User not found'
    if field_def.needs_member:
      user_value_in_project = framework_bizobj.UserIsInProject(
          project, auth.effective_ids)
      if not user_value_in_project:
        return 'User must be a member of the project'
      if field_def.needs_perm:
        user_perms = permissions.GetPermissions(
            auth.user_pb, auth.effective_ids, project)
        has_perm = user_perms.CanUsePerm(
            field_def.needs_perm, auth.effective_ids, project, [])
        if not has_perm:
          return 'User must have permission "%s"' % field_def.needs_perm
    return None

  elif field_def.field_type == tracker_pb2.FieldTypes.DATE_TYPE:
    # TODO(jrobbins): date validation
    pass

  elif field_def.field_type == tracker_pb2.FieldTypes.URL_TYPE:
    if field_val.url_value:
      if not (validate.IsValidURL(field_val.url_value)
              or autolink_constants.IS_A_SHORT_LINK_RE.match(
                  field_val.url_value)
              or autolink_constants.IS_A_NUMERIC_SHORT_LINK_RE.match(
                  field_val.url_value)
              or autolink_constants.IS_IMPLIED_LINK_RE.match(
                  field_val.url_value)):
        return 'Value must be a valid url'

  return None


def ValidateCustomFields(mr, services, field_values, config, errors):
  """Validate each of the given fields and report problems in errors object."""
  fds_by_id = {fd.field_id: fd for fd in config.field_defs}
  for fv in field_values:
    fd = fds_by_id.get(fv.field_id)
    if fd:
      err_msg = ValidateCustomFieldValue(mr, mr.project, services, fd, fv)
      if err_msg:
        errors.SetCustomFieldError(fv.field_id, err_msg)


def AssertCustomFieldsEditPerms(
    mr, config, field_vals, field_vals_remove, fields_clear, labels,
    labels_remove):
  """Check permissions for any kind of custom field edition attempt."""
  # TODO: When clearing phase_fields is possible, include it in this method.
  field_ids = set()

  for fv in field_vals:
    field_ids.add(fv.field_id)
  for fvr in field_vals_remove:
    field_ids.add(fvr.field_id)
  for fd_id in fields_clear:
    field_ids.add(fd_id)

  enum_fds_by_name = {
      fd.field_name.lower(): fd.field_id
      for fd in config.field_defs
      if fd.field_type is tracker_pb2.FieldTypes.ENUM_TYPE and not fd.is_deleted
  }
  for label in itertools.chain(labels, labels_remove):
    enum_field_name = tracker_bizobj.LabelIsMaskedByField(
        label, enum_fds_by_name.keys())
    if enum_field_name:
      field_ids.add(enum_fds_by_name.get(enum_field_name))

  fds_by_id = {fd.field_id: fd for fd in config.field_defs}
  for field_id in field_ids:
    fd = fds_by_id.get(field_id)
    if fd:
      assert permissions.CanEditValueForFieldDef(
          mr.auth.effective_ids, mr.perms, mr.project,
          fd), 'No permission to edit certain fields.'


def ApplyRestrictedDefaultValues(
    mr, config, field_vals, labels, template_field_vals, template_labels):
  """Add default values of template fields that the user cannot edit.

     This method can be called by servlets where restricted field values that
     a user cannot edit are displayed but do not get returned when the user
     submits the form (and also assumes that previous assertions ensure these
     conditions). These missing default values still need to be passed to the
     services layer when a 'write' is done so that these default values do
     not get removed.

     Args:
       mr: MonorailRequest Object to hold info about the request and the user.
       config: ProjectIssueConfig Object for the project.
       field_vals: list of FieldValues that the user wants to save.
       labels: list of labels that the user wants to save.
       template_field_vals: list of FieldValues belonging to the template.
       template_labels: list of labels belonging to the template.

     Side Effect:
       The default values of a template that the user cannot edit are added
       to 'field_vals' and 'labels'.
  """

  fds_by_id = {fd.field_id: fd for fd in config.field_defs}
  for fv in template_field_vals:
    fd = fds_by_id.get(fv.field_id)
    if fd and not permissions.CanEditValueForFieldDef(mr.auth.effective_ids,
                                                      mr.perms, mr.project, fd):
      field_vals.append(fv)

  fds_by_name = {
      fd.field_name.lower(): fd
      for fd in config.field_defs
      if fd.field_type is tracker_pb2.FieldTypes.ENUM_TYPE and not fd.is_deleted
  }
  for label in template_labels:
    enum_field_name = tracker_bizobj.LabelIsMaskedByField(
        label, fds_by_name.keys())
    if enum_field_name:
      fd = fds_by_name.get(enum_field_name)
      if fd and not permissions.CanEditValueForFieldDef(
          mr.auth.effective_ids, mr.perms, mr.project, fd):
        labels.append(label)


def FormatUrlFieldValue(url_str):
  """Check for and add 'https://' to a url string"""
  if not url_str.startswith('http'):
    return 'http://' + url_str
  return url_str


def ReviseFieldDefFromParsed(parsed, old_fd):
  """Creates new FieldDef based on an original FieldDef and parsed FieldDef"""
  if parsed.date_action_str in config_svc.DATE_ACTION_ENUM:
    date_action = config_svc.DATE_ACTION_ENUM.index(parsed.date_action_str)
  else:
    date_action = 0
  return tracker_bizobj.MakeFieldDef(
      old_fd.field_id, old_fd.project_id, old_fd.field_name, old_fd.field_type,
      parsed.applicable_type, parsed.applicable_predicate, parsed.is_required,
      parsed.is_niche, parsed.is_multivalued, parsed.min_value,
      parsed.max_value, parsed.regex, parsed.needs_member, parsed.needs_perm,
      parsed.grants_perm, parsed.notify_on, date_action, parsed.field_docstring,
      False, approval_id=old_fd.approval_id or None,
      is_phase_field=old_fd.is_phase_field)


def ParsedFieldDefAssertions(mr, parsed):
  """Checks if new/updated FieldDef is not violating basic assertions.
      If the assertions are violated, the errors
      will be included in the mr.errors.

    Args:
      mr: MonorailRequest object used to hold
          commonly info parsed from the request.
      parsed: ParsedFieldDef object used to contain parsed info,
          in this case regarding a custom field definition.
    """
  # TODO(crbug/monorail/7275): This method is meant to eventually
  # do all assertion checkings (shared by create/update fieldDef)
  # and assign all mr.errors values.
  if (parsed.is_required and parsed.is_niche):
    mr.errors.is_niche = 'A field cannot be both required and niche.'
  if parsed.date_action_str is not None and (
      parsed.date_action_str not in config_svc.DATE_ACTION_ENUM):
    mr.errors.date_action = 'The date action should be either: ' + ', '.join(
        config_svc.DATE_ACTION_ENUM) + '.'
  if (parsed.min_value is not None and parsed.max_value is not None and
      parsed.min_value > parsed.max_value):
    mr.errors.min_value = 'Minimum value must be less than maximum.'
  if parsed.regex:
    try:
      re.compile(parsed.regex)
    except re.error:
      mr.errors.regex = 'Invalid regular expression.'
