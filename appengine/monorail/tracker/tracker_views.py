# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""View objects to help display tracker business objects in templates."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging
import re
import time
import urllib

from google.appengine.api import app_identity
from third_party import ezt

from features import federated
from framework import exceptions
from framework import filecontent
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import gcs_helpers
from framework import permissions
from framework import template_helpers
from framework import timestr
from framework import urls
from proto import tracker_pb2
from tracker import attachment_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


class IssueView(template_helpers.PBProxy):
  """Wrapper class that makes it easier to display an Issue via EZT."""

  def __init__(self, issue, users_by_id, config):
    """Store relevant values for later display by EZT.

    Args:
      issue: An Issue protocol buffer.
      users_by_id: dict {user_id: UserViews} for all users mentioned in issue.
      config: ProjectIssueConfig for this issue.
    """
    super(IssueView, self).__init__(issue)

    # The users involved in this issue must be present in users_by_id if
    # this IssueView is to be used on the issue detail or peek pages. But,
    # they can be absent from users_by_id if the IssueView is used as a
    # tile in the grid view.
    self.owner = users_by_id.get(issue.owner_id)
    self.derived_owner = users_by_id.get(issue.derived_owner_id)
    self.cc = [users_by_id.get(cc_id) for cc_id in issue.cc_ids
               if cc_id]
    self.derived_cc = [users_by_id.get(cc_id)
                       for cc_id in issue.derived_cc_ids
                       if cc_id]
    self.status = framework_views.StatusView(issue.status, config)
    self.derived_status = framework_views.StatusView(
        issue.derived_status, config)
    # If we don't have a config available, we don't need to access is_open, so
    # let it be True.
    self.is_open = ezt.boolean(
        not config or
        tracker_helpers.MeansOpenInProject(
            tracker_bizobj.GetStatus(issue), config))

    self.components = sorted(
        [ComponentValueView(component_id, config, False)
         for component_id in issue.component_ids
         if tracker_bizobj.FindComponentDefByID(component_id, config)] +
        [ComponentValueView(component_id, config, True)
         for component_id in issue.derived_component_ids
         if tracker_bizobj.FindComponentDefByID(component_id, config)],
        key=lambda cvv: cvv.path)

    self.fields = MakeAllFieldValueViews(
        config, issue.labels, issue.derived_labels, issue.field_values,
        users_by_id)

    labels, derived_labels = tracker_bizobj.ExplicitAndDerivedNonMaskedLabels(
        issue.labels, issue.derived_labels, config)
    self.labels = [
        framework_views.LabelView(label, config)
        for label in labels]
    self.derived_labels = [
        framework_views.LabelView(label, config)
        for label in derived_labels]
    self.restrictions = _RestrictionsView(issue)

    # TODO(jrobbins): sort by order of labels in project config

    self.short_summary = issue.summary[:tracker_constants.SHORT_SUMMARY_LENGTH]

    if issue.closed_timestamp:
      self.closed = timestr.FormatAbsoluteDate(issue.closed_timestamp)
    else:
      self.closed = ''

    self.blocked_on = []
    self.has_dangling = ezt.boolean(self.dangling_blocked_on_refs)
    self.blocking = []

    self.detail_relative_url = tracker_helpers.FormatRelativeIssueURL(
        issue.project_name, urls.ISSUE_DETAIL, id=issue.local_id)
    self.crbug_url = tracker_helpers.FormatCrBugURL(
        issue.project_name, issue.local_id)


class _RestrictionsView(object):
  """An EZT object for the restrictions associated with an issue."""

  # Restrict label fragments that correspond to known permissions.
  _VIEW = permissions.VIEW.lower()
  _EDIT = permissions.EDIT_ISSUE.lower()
  _ADD_COMMENT = permissions.ADD_ISSUE_COMMENT.lower()
  _KNOWN_ACTION_KINDS = {_VIEW, _EDIT, _ADD_COMMENT}

  def __init__(self, issue):
    # List of restrictions that don't map to a known action kind.
    self.other = []

    restrictions_by_action = collections.defaultdict(list)
    # We can't use GetRestrictions here, as we prefer to preserve
    # the case of the label when showing restrictions in the UI.
    for label in tracker_bizobj.GetLabels(issue):
      if permissions.IsRestrictLabel(label):
        _kw, action_kind, needed_perm = label.split('-', 2)
        action_kind = action_kind.lower()
        if action_kind in self._KNOWN_ACTION_KINDS:
          restrictions_by_action[action_kind].append(needed_perm)
        else:
          self.other.append(label)

    self.view = ' and '.join(restrictions_by_action[self._VIEW])
    self.add_comment = ' and '.join(restrictions_by_action[self._ADD_COMMENT])
    self.edit = ' and '.join(restrictions_by_action[self._EDIT])

    self.has_restrictions = ezt.boolean(
        self.view or self.add_comment or self.edit or self.other)


class IssueCommentView(template_helpers.PBProxy):
  """Wrapper class that makes it easier to display an IssueComment via EZT."""

  def __init__(
      self, project_name, comment_pb, users_by_id, autolink,
      all_referenced_artifacts, mr, issue, effective_ids=None):
    """Get IssueComment PB and make its fields available as attrs.

    Args:
      project_name: Name of the project this issue belongs to.
      comment_pb: Comment protocol buffer.
      users_by_id: dict mapping user_ids to UserViews, including
          the user that entered the comment, and any changed participants.
      autolink: utility object for automatically linking to other
        issues, git revisions, etc.
      all_referenced_artifacts: opaque object with details of referenced
        artifacts that is needed by autolink.
      mr: common information parsed from the HTTP request.
      issue: Issue PB for the issue that this comment is part of.
      effective_ids: optional set of int user IDs for the comment author.
    """
    super(IssueCommentView, self).__init__(comment_pb)

    self.id = comment_pb.id
    self.creator = users_by_id[comment_pb.user_id]

    # TODO(jrobbins): this should be based on the issue project, not the
    # request project for non-project views and cross-project.
    if mr.project:
      self.creator_role = framework_helpers.GetRoleName(
          effective_ids or {self.creator.user_id}, mr.project)
    else:
      self.creator_role = None

    time_tuple = time.localtime(comment_pb.timestamp)
    self.date_string = timestr.FormatAbsoluteDate(
        comment_pb.timestamp, old_format=timestr.MONTH_DAY_YEAR_FMT)
    self.date_relative = timestr.FormatRelativeDate(comment_pb.timestamp)
    self.date_tooltip = time.asctime(time_tuple)
    self.date_yyyymmdd = timestr.FormatAbsoluteDate(
        comment_pb.timestamp, recent_format=timestr.MONTH_DAY_YEAR_FMT,
        old_format=timestr.MONTH_DAY_YEAR_FMT)
    self.text_runs = _ParseTextRuns(comment_pb.content)
    if autolink and not comment_pb.deleted_by:
      self.text_runs = autolink.MarkupAutolinks(
          mr, self.text_runs, all_referenced_artifacts)

    self.attachments = [AttachmentView(attachment, project_name)
                        for attachment in comment_pb.attachments]
    self.amendments = sorted([
        AmendmentView(amendment, users_by_id, mr.project_name)
        for amendment in comment_pb.amendments],
        key=lambda amendment: amendment.field_name.lower())
    # Treat comments from banned users as being deleted.
    self.is_deleted = (comment_pb.deleted_by or
                       (self.creator and self.creator.banned))
    self.can_delete = False

    # TODO(jrobbins): pass through config to get granted permissions.
    perms = permissions.UpdateIssuePermissions(
        mr.perms, mr.project, issue, mr.auth.effective_ids)
    if mr.auth.user_id and mr.project:
      self.can_delete = permissions.CanDeleteComment(
          comment_pb, self.creator, mr.auth.user_id, perms)

    self.visible = permissions.CanViewComment(
        comment_pb, self.creator, mr.auth.user_id, perms)


_TEMPLATE_TEXT_RE = re.compile('^(<b>[^<]+</b>)', re.MULTILINE)


def _ParseTextRuns(content):
  """Convert the user's comment to a list of TextRun objects."""
  chunks = _TEMPLATE_TEXT_RE.split(content.strip())
  runs = [_ChunkToRun(chunk) for chunk in chunks]
  return runs


def _ChunkToRun(chunk):
  """Convert a substring of the user's comment to a TextRun object."""
  if chunk.startswith('<b>') and chunk.endswith('</b>'):
    return template_helpers.TextRun(chunk[3:-4], tag='b')
  else:
    return template_helpers.TextRun(chunk)


class LogoView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display project logos via EZT."""

  def __init__(self, project_pb):
    super(LogoView, self).__init__(None)
    if (not project_pb or
        not project_pb.logo_gcs_id or
        not project_pb.logo_file_name):
      self.thumbnail_url = ''
      self.viewurl = ''
      return

    bucket_name = app_identity.get_default_gcs_bucket_name()
    gcs_object = project_pb.logo_gcs_id
    self.filename = project_pb.logo_file_name
    self.mimetype = filecontent.GuessContentTypeFromFilename(self.filename)

    self.thumbnail_url = gcs_helpers.SignUrl(bucket_name,
        gcs_object + '-thumbnail')
    self.viewurl = (
        gcs_helpers.SignUrl(bucket_name, gcs_object) + '&' + urllib.urlencode(
            {'response-content-displacement':
                ('attachment; filename=%s' % self.filename)}))


class AttachmentView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display issue attachments via EZT."""

  def __init__(self, attach_pb, project_name):
    """Get IssueAttachmentContent PB and make its fields available as attrs.

    Args:
      attach_pb: Attachment part of IssueComment protocol buffer.
      project_name: string Name of the current project.
    """
    super(AttachmentView, self).__init__(attach_pb)
    self.filesizestr = template_helpers.BytesKbOrMb(attach_pb.filesize)
    self.downloadurl = attachment_helpers.GetDownloadURL(
        attach_pb.attachment_id)
    self.url = attachment_helpers.GetViewURL(
        attach_pb, self.downloadurl, project_name)
    self.thumbnail_url = attachment_helpers.GetThumbnailURL(
        attach_pb, self.downloadurl)
    self.video_url = attachment_helpers.GetVideoURL(
        attach_pb, self.downloadurl)

    self.iconurl = '/images/paperclip.png'


class AmendmentView(object):
  """Wrapper class that makes it easier to display an Amendment via EZT."""

  def __init__(self, amendment, users_by_id, project_name):
    """Get the info from the PB and put it into easily accessible attrs.

    Args:
      amendment: Amendment part of an IssueComment protocol buffer.
      users_by_id: dict mapping user_ids to UserViews.
      project_name: Name of the project the issue/comment/amendment is in.
    """
    # TODO(jrobbins): take field-level restrictions into account.
    # Including the case where user is not allowed to see any amendments.
    self.field_name = tracker_bizobj.GetAmendmentFieldName(amendment)
    self.newvalue = tracker_bizobj.AmendmentString(amendment, users_by_id)
    self.values = tracker_bizobj.AmendmentLinks(
        amendment, users_by_id, project_name)


class ComponentDefView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display component definitions."""

  def __init__(self, cnxn, services, component_def, users_by_id):
    super(ComponentDefView, self).__init__(component_def)

    c_path = component_def.path
    if '>' in c_path:
      self.parent_path = c_path[:c_path.rindex('>')]
      self.leaf_name = c_path[c_path.rindex('>') + 1:]
    else:
      self.parent_path = ''
      self.leaf_name = c_path

    self.docstring_short = template_helpers.FitUnsafeText(
        component_def.docstring, 200)

    self.admins = [users_by_id.get(admin_id)
                   for admin_id in component_def.admin_ids]
    self.cc = [users_by_id.get(cc_id) for cc_id in component_def.cc_ids]
    self.labels = [
        services.config.LookupLabel(cnxn, component_def.project_id, label_id)
        for label_id in component_def.label_ids]
    self.classes = 'all '
    if self.parent_path == '':
      self.classes += 'toplevel '
    self.classes += 'deprecated ' if component_def.deprecated else 'active '


class ComponentValueView(object):
  """Wrapper class that makes it easier to display a component value."""

  def __init__(self, component_id, config, derived):
    """Make the component name and docstring available as attrs.

    Args:
      component_id: int component_id to look up in the config
      config: ProjectIssueConfig PB for the issue's project.
      derived: True if this component was derived.
    """
    cd = tracker_bizobj.FindComponentDefByID(component_id, config)
    self.path = cd.path
    self.docstring = cd.docstring
    self.docstring_short = template_helpers.FitUnsafeText(cd.docstring, 60)
    self.derived = ezt.boolean(derived)


class FieldValueView(object):
  """Wrapper class that makes it easier to display a custom field value."""

  def __init__(
      self, fd, config, values, derived_values, issue_types, applicable=None,
      phase_name=None):
    """Make several values related to this field available as attrs.

    Args:
      fd: field definition to be displayed (or not, if no value).
      config: ProjectIssueConfig PB for the issue's project.
      values: list of explicit field values.
      derived_values: list of derived field values.
      issue_types: set of lowered string values from issues' "Type-*" labels.
      applicable: optional boolean that overrides the rule that determines
          when a field is applicable.
      phase_name: name of the phase this field value belongs to.
    """
    self.field_def = FieldDefView(fd, config)
    self.field_id = fd.field_id
    self.field_name = fd.field_name
    self.field_docstring = fd.docstring
    self.field_docstring_short = template_helpers.FitUnsafeText(
        fd.docstring, 60)
    self.phase_name = phase_name or ""

    self.values = values
    self.derived_values = derived_values

    self.applicable_type = fd.applicable_type
    if applicable is not None:
      self.applicable = ezt.boolean(applicable)
    else:
      # Note: We don't show approval types, approval sub fields, or
      # phase fields in ezt issue pages.
      if (fd.field_type == tracker_pb2.FieldTypes.APPROVAL_TYPE or
          fd.approval_id or fd.is_phase_field):
        self.applicable = ezt.boolean(False)
      else:
        # A field is applicable to a given issue if it (a) applies to all,
        # issues or (b) already has a value on this issue, or (c) says that
        # it applies to issues with this type (or a prefix of it).
        applicable_type_lower = self.applicable_type.lower()
        self.applicable = ezt.boolean(
            not self.applicable_type or values or
            any(type_label.startswith(applicable_type_lower)
                for type_label in issue_types))
      # TODO(jrobbins): also evaluate applicable_predicate

    self.display = ezt.boolean(   # or fd.show_empty
        self.values or self.derived_values or
        (self.applicable and not fd.is_niche))

    #FieldValueView does not handle determining if it's editable
    #by the logged-in user. This can be determined by using
    #permission.CanEditValueForFieldDef.
    self.is_editable = ezt.boolean(True)


def _PrecomputeInfoForValueViews(labels, derived_labels, field_values, config,
                                 phases):
  """Organize issue values into datastructures used to make FieldValueViews."""
  field_values_by_id = collections.defaultdict(list)
  for fv in field_values:
    field_values_by_id[fv.field_id].append(fv)
  lower_enum_field_names = [
      fd.field_name.lower() for fd in config.field_defs
      if fd.field_type == tracker_pb2.FieldTypes.ENUM_TYPE]
  labels_by_prefix = tracker_bizobj.LabelsByPrefix(
      labels, lower_enum_field_names)
  der_labels_by_prefix = tracker_bizobj.LabelsByPrefix(
      derived_labels, lower_enum_field_names)
  label_docs = {wkl.label.lower(): wkl.label_docstring
                for wkl in config.well_known_labels}
  phases_by_name = collections.defaultdict(list)
  # group issue phases by name
  for phase in phases:
    phases_by_name[phase.name.lower()].append(phase)
  return (labels_by_prefix, der_labels_by_prefix, field_values_by_id,
          label_docs, phases_by_name)


def MakeAllFieldValueViews(
    config, labels, derived_labels, field_values, users_by_id,
    parent_approval_ids=None, phases=None):
  """Return a list of FieldValues, each containing values from the issue.
     A phase field value view will be created for each unique phase name found
     in the given list a phases. Phase field value views will not be created
     if the phases list is empty.
  """
  parent_approval_ids = parent_approval_ids or []
  precomp_view_info = _PrecomputeInfoForValueViews(
      labels, derived_labels, field_values, config, phases or [])
  def GetApplicable(fd):
    if fd.approval_id and fd.approval_id in parent_approval_ids:
      return True
    return None
  field_value_views = [
      _MakeFieldValueView(fd, config, precomp_view_info, users_by_id,
                          applicable=GetApplicable(fd))
      # TODO(jrobbins): field-level view restrictions, display options
      for fd in config.field_defs
      if not fd.is_deleted and not fd.is_phase_field]

  # Make a phase field's view for each unique phase_name found in phases.
  (_, _, _, _, phases_by_name) = precomp_view_info
  for phase_name in phases_by_name.keys():
    field_value_views.extend([
        _MakeFieldValueView(
            fd, config, precomp_view_info, users_by_id, phase_name=phase_name)
        for fd in config.field_defs if fd.is_phase_field])

  field_value_views = sorted(
      field_value_views, key=lambda f: (f.applicable_type, f.field_name))
  return field_value_views


def _MakeFieldValueView(
    fd, config, precomp_view_info, users_by_id, applicable=None,
    phase_name=None):
  """Return a FieldValueView with all values from the issue for that field."""
  (labels_by_prefix, der_labels_by_prefix, field_values_by_id,
   label_docs, phases_by_name) = precomp_view_info

  field_name_lower = fd.field_name.lower()
  values = []
  derived_values = []

  if fd.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
    values = _ConvertLabelsToFieldValues(
        labels_by_prefix.get(field_name_lower, []),
        field_name_lower, label_docs)
    derived_values = _ConvertLabelsToFieldValues(
        der_labels_by_prefix.get(field_name_lower, []),
        field_name_lower, label_docs)
  else:
    # Phases with the same name may have different phase_ids. Phases
    # are defined during template creation and updating a template structure
    # may result in new phase rows to be created while existing issues
    # are referencing older phase rows.
    phase_ids_for_phase_name = [
        phase.phase_id for phase in phases_by_name.get(phase_name, [])]
    # If a phase_name is given, we must filter field_values_by_id fvs to those
    # that belong to the given phase. This is not done for labels
    # because monorail does not support phase enum_type field values.
    values = _MakeFieldValueItems(
        [fv for fv in field_values_by_id.get(fd.field_id, [])
         if not fv.derived and
         (not phase_name or (fv.phase_id in phase_ids_for_phase_name))],
        users_by_id)
    derived_values = _MakeFieldValueItems(
        [fv for fv in field_values_by_id.get(fd.field_id, [])
         if fv.derived and
         (not phase_name or (fv.phase_id in phase_ids_for_phase_name))],
        users_by_id)

  issue_types = (labels_by_prefix.get('type', []) +
                 der_labels_by_prefix.get('type', []))
  issue_types_lower = [it.lower() for it in issue_types]

  return FieldValueView(fd, config, values, derived_values, issue_types_lower,
                        applicable=applicable, phase_name=phase_name)


def _MakeFieldValueItems(field_values, users_by_id):
  """Make appropriate int, string, or user values in the given fields."""
  result = []
  for fv in field_values:
    val = tracker_bizobj.GetFieldValue(fv, users_by_id)
    result.append(template_helpers.EZTItem(
        val=val, docstring=val, idx=len(result)))

  return result


def MakeBounceFieldValueViews(field_vals, phase_field_vals, config):
  """Return a list of field values to display on a validation bounce page."""
  field_value_views = []
  for fd in config.field_defs:
    if fd.field_id in field_vals:
      # TODO(jrobbins): also bounce derived values.
      val_items = [
          template_helpers.EZTItem(val=v, docstring='', idx=idx)
          for idx, v in enumerate(field_vals[fd.field_id])]
      field_value_views.append(FieldValueView(
          fd, config, val_items, [], None, applicable=True))
    elif fd.field_id in phase_field_vals:
      vals_by_phase_name = phase_field_vals.get(fd.field_id)
      for phase_name, values in vals_by_phase_name.items():
        val_items = [
            template_helpers.EZTItem(val=v, docstring='', idx=idx)
            for idx, v in enumerate(values)]
        field_value_views.append(FieldValueView(
            fd, config, val_items, [], None, applicable=False,
            phase_name=phase_name))

  return field_value_views


def _ConvertLabelsToFieldValues(label_values, field_name_lower, label_docs):
  """Iterate through the given labels and pull out values for the field.

  Args:
    label_values: a list of label strings for the given field.
    field_name_lower: lowercase string name of the custom field.
    label_docs: {lower_label: docstring} for well-known labels in the project.

  Returns:
    A list of EZT items with val and docstring fields.  One item is included
    for each label that matches the given field name.
  """
  values = []
  for idx, lab_val in enumerate(label_values):
    full_label_lower = '%s-%s' % (field_name_lower, lab_val.lower())
    values.append(template_helpers.EZTItem(
        val=lab_val, docstring=label_docs.get(full_label_lower, ''), idx=idx))

  return values


class FieldDefView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display field definitions via EZT."""

  def __init__(self, field_def, config, user_views=None, approval_def=None):
    super(FieldDefView, self).__init__(field_def)

    self.type_name = str(field_def.field_type)
    self.field_def = field_def

    self.choices = []
    if field_def.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
      self.choices = tracker_helpers.LabelsMaskedByFields(
          config, [field_def.field_name], trim_prefix=True)

    self.approvers = []
    self.survey = ''
    self.survey_questions = []
    if (approval_def and
        field_def.field_type == tracker_pb2.FieldTypes.APPROVAL_TYPE):
      self.approvers = [user_views.get(approver_id) for
                             approver_id in approval_def.approver_ids]
      if approval_def.survey:
        self.survey = approval_def.survey
        self.survey_questions = self.survey.split('\n')


    self.docstring_short = template_helpers.FitUnsafeText(
        field_def.docstring, 200)
    self.validate_help = None

    if field_def.is_required:
      self.importance = 'required'
    elif field_def.is_niche:
      self.importance = 'niche'
    else:
      self.importance = 'normal'

    if field_def.min_value is not None:
      self.min_value = field_def.min_value
      self.validate_help = 'Value must be >= %d' % field_def.min_value
    else:
      self.min_value = None  # Otherwise it would default to 0

    if field_def.max_value is not None:
      self.max_value = field_def.max_value
      self.validate_help = 'Value must be <= %d' % field_def.max_value
    else:
      self.max_value = None  # Otherwise it would default to 0

    if field_def.min_value is not None and field_def.max_value is not None:
      self.validate_help = 'Value must be between %d and %d' % (
          field_def.min_value, field_def.max_value)

    if field_def.regex:
      self.validate_help = 'Value must match regex: %s' % field_def.regex

    if field_def.needs_member:
      self.validate_help = 'Value must be a project member'

    if field_def.needs_perm:
      self.validate_help = (
          'Value must be a project member with permission %s' %
          field_def.needs_perm)

    self.date_action_str = str(field_def.date_action or 'no_action').lower()

    self.admins = []
    if user_views:
      self.admins = [user_views.get(admin_id)
                     for admin_id in field_def.admin_ids]

    self.editors = []
    if user_views:
      self.editors = [
          user_views.get(editor_id) for editor_id in field_def.editor_ids
      ]

    if field_def.approval_id:
      self.is_approval_subfield = ezt.boolean(True)
      self.parent_approval_name = tracker_bizobj.FindFieldDefByID(
          field_def.approval_id, config).field_name
    else:
      self.is_approval_subfield = ezt.boolean(False)

    self.is_phase_field = ezt.boolean(field_def.is_phase_field)
    self.is_restricted_field = ezt.boolean(field_def.is_restricted_field)


class IssueTemplateView(template_helpers.PBProxy):
  """Wrapper class to make it easier to display an issue template via EZT."""

  def __init__(self, mr, template, user_service, config):
    super(IssueTemplateView, self).__init__(template)

    self.ownername = ''
    try:
      self.owner_view = framework_views.MakeUserView(
          mr.cnxn, user_service, template.owner_id)
    except exceptions.NoSuchUserException:
      self.owner_view = None
    if self.owner_view:
      self.ownername = self.owner_view.email

    self.admin_views = list(framework_views.MakeAllUserViews(
        mr.cnxn, user_service, template.admin_ids).values())
    self.admin_names = ', '.join(sorted([
        admin_view.email for admin_view in self.admin_views]))

    self.summary_must_be_edited = ezt.boolean(template.summary_must_be_edited)
    self.members_only = ezt.boolean(template.members_only)
    self.owner_defaults_to_member = ezt.boolean(
        template.owner_defaults_to_member)
    self.component_required = ezt.boolean(template.component_required)

    component_paths = []
    for component_id in template.component_ids:
      component_paths.append(
          tracker_bizobj.FindComponentDefByID(component_id, config).path)
    self.components = ', '.join(component_paths)

    self.can_view = ezt.boolean(permissions.CanViewTemplate(
        mr.auth.effective_ids, mr.perms, mr.project, template))
    self.can_edit = ezt.boolean(permissions.CanEditTemplate(
        mr.auth.effective_ids, mr.perms, mr.project, template))

    field_name_set = {fd.field_name.lower() for fd in config.field_defs
                      if fd.field_type is tracker_pb2.FieldTypes.ENUM_TYPE and
                      not fd.is_deleted}  # TODO(jrobbins): restrictions
    non_masked_labels = [
        lab for lab in template.labels
        if not tracker_bizobj.LabelIsMaskedByField(lab, field_name_set)]

    for i, label in enumerate(non_masked_labels):
      setattr(self, 'label%d' % i, label)
    for i in range(len(non_masked_labels), framework_constants.MAX_LABELS):
      setattr(self, 'label%d' % i, '')

    field_user_views = MakeFieldUserViews(mr.cnxn, template, user_service)

    self.field_values = []
    for fv in template.field_values:
      self.field_values.append(template_helpers.EZTItem(
          field_id=fv.field_id,
          val=tracker_bizobj.GetFieldValue(fv, field_user_views),
          idx=len(self.field_values)))

    self.complete_field_values = MakeAllFieldValueViews(
        config, template.labels, [], template.field_values, field_user_views)

    # Templates only display and edit the first value of multi-valued fields, so
    # expose a single value, if any.
    # TODO(jrobbins): Fully support multi-valued fields in templates.
    for idx, field_value_view in enumerate(self.complete_field_values):
      field_value_view.idx = idx
      if field_value_view.values:
        field_value_view.val = field_value_view.values[0].val
      else:
        field_value_view.val = None


def MakeFieldUserViews(cnxn, template, user_service):
  """Return {user_id: user_view} for users in template field values."""
  field_user_ids = [
      fv.user_id for fv in template.field_values
      if fv.user_id]
  field_user_views = framework_views.MakeAllUserViews(
      cnxn, user_service, field_user_ids)
  return field_user_views


class ConfigView(template_helpers.PBProxy):
  """Make it easy to display most fields of a ProjectIssueConfig in EZT."""

  def __init__(self, mr, services, config, template=None,
               load_all_templates=False):
    """Gather data for the issue section of a project admin page.

    Args:
      mr: MonorailRequest, including a database connection, the current
          project, and authenticated user IDs.
      services: Persist services with ProjectService, ConfigService,
          TemplateService and UserService included.
      config: ProjectIssueConfig for the current project..
      template (TemplateDef, optional): the current template.
      load_all_templates (boolean): default False. If true loads self.templates.

    Returns:
      Project info in a dict suitable for EZT.
    """
    super(ConfigView, self).__init__(config)
    self.open_statuses = []
    self.closed_statuses = []
    for wks in config.well_known_statuses:
      item = template_helpers.EZTItem(
          name=wks.status,
          name_padded=wks.status.ljust(20),
          commented='#' if wks.deprecated else '',
          docstring=wks.status_docstring)
      if tracker_helpers.MeansOpenInProject(wks.status, config):
        self.open_statuses.append(item)
      else:
        self.closed_statuses.append(item)

    is_member = framework_bizobj.UserIsInProject(
        mr.project, mr.auth.effective_ids)
    template_set = services.template.GetTemplateSetForProject(mr.cnxn,
        config.project_id)

    # Filter non-viewable templates
    self.template_names = []
    for _, template_name, members_only in template_set:
      if members_only and not is_member:
        continue
      self.template_names.append(template_name)

    if load_all_templates:
      templates = services.template.GetProjectTemplates(mr.cnxn,
          config.project_id)
      self.templates = [
          IssueTemplateView(mr, tmpl, services.user, config)
          for tmpl in templates]
      for index, template_view in enumerate(self.templates):
        template_view.index = index

    if template:
      self.template_view = IssueTemplateView(mr, template, services.user,
          config)

    self.field_names = [  # TODO(jrobbins): field-level controls
        fd.field_name for fd in config.field_defs if
        fd.field_type is tracker_pb2.FieldTypes.ENUM_TYPE and
        not fd.is_deleted]
    self.issue_labels = tracker_helpers.LabelsNotMaskedByFields(
        config, self.field_names)
    self.excl_prefixes = [
        prefix.lower() for prefix in config.exclusive_label_prefixes]
    self.restrict_to_known = ezt.boolean(config.restrict_to_known)

    self.default_col_spec = (
        config.default_col_spec or tracker_constants.DEFAULT_COL_SPEC)


def StatusDefsAsText(config):
  """Return two strings for editing open and closed status definitions."""
  open_lines = []
  closed_lines = []
  for wks in config.well_known_statuses:
    line = '%s%s%s%s' % (
      '#' if wks.deprecated else '',
      wks.status.ljust(20),
      '\t= ' if wks.status_docstring else '',
      wks.status_docstring)

    if tracker_helpers.MeansOpenInProject(wks.status, config):
      open_lines.append(line)
    else:
      closed_lines.append(line)

  open_text = '\n'.join(open_lines)
  closed_text = '\n'.join(closed_lines)
  logging.info('open_text is \n%s', open_text)
  logging.info('closed_text is \n%s', closed_text)
  return open_text, closed_text


def LabelDefsAsText(config):
  """Return a string for editing label definitions."""
  field_names = [fd.field_name for fd in config.field_defs
                 if fd.field_type is tracker_pb2.FieldTypes.ENUM_TYPE
                 and not fd.is_deleted]
  masked_labels = tracker_helpers.LabelsMaskedByFields(config, field_names)
  masked_set = set(masked.name for masked in masked_labels)

  label_def_lines = []
  for wkl in config.well_known_labels:
    if wkl.label in masked_set:
      continue
    line = '%s%s%s%s' % (
      '#' if wkl.deprecated else '',
      wkl.label.ljust(20),
      '\t= ' if wkl.label_docstring else '',
      wkl.label_docstring)
    label_def_lines.append(line)

  labels_text = '\n'.join(label_def_lines)
  logging.info('labels_text is \n%s', labels_text)
  return labels_text
