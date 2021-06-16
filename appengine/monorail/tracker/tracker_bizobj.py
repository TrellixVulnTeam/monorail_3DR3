# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Business objects for the Monorail issue tracker.

These are classes and functions that operate on the objects that
users care about in the issue tracker: e.g., issues, and the issue
tracker configuration.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging
import time

from six import string_types

from features import federated
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import timestr
from framework import urls
from proto import tracker_pb2
from tracker import tracker_constants


def GetOwnerId(issue):
  """Get the owner of an issue, whether it is explicit or derived."""
  return (issue.owner_id or issue.derived_owner_id or
          framework_constants.NO_USER_SPECIFIED)


def GetStatus(issue):
  """Get the status of an issue, whether it is explicit or derived."""
  return issue.status or issue.derived_status or  ''


def GetCcIds(issue):
  """Get the Cc's of an issue, whether they are explicit or derived."""
  return issue.cc_ids + issue.derived_cc_ids


def GetApproverIds(issue):
  """Get the Approvers' ids of an isuses approval_values."""
  approver_ids = []
  for av in issue.approval_values:
    approver_ids.extend(av.approver_ids)

  return list(set(approver_ids))


def GetLabels(issue):
  """Get the labels of an issue, whether explicit or derived."""
  return issue.labels + issue.derived_labels


def MakeProjectIssueConfig(
    project_id, well_known_statuses, statuses_offer_merge, well_known_labels,
    excl_label_prefixes, col_spec):
  """Return a ProjectIssueConfig with the given values."""
  # pylint: disable=multiple-statements
  if not well_known_statuses: well_known_statuses = []
  if not statuses_offer_merge: statuses_offer_merge = []
  if not well_known_labels: well_known_labels = []
  if not excl_label_prefixes: excl_label_prefixes = []
  if not col_spec: col_spec = ' '

  project_config = tracker_pb2.ProjectIssueConfig()
  if project_id:  # There is no ID for harmonized configs.
    project_config.project_id = project_id

  SetConfigStatuses(project_config, well_known_statuses)
  project_config.statuses_offer_merge = statuses_offer_merge
  SetConfigLabels(project_config, well_known_labels)
  project_config.exclusive_label_prefixes = excl_label_prefixes

  # ID 0 means that nothing has been specified, so use hard-coded defaults.
  project_config.default_template_for_developers = 0
  project_config.default_template_for_users = 0

  project_config.default_col_spec = col_spec

  # Note: default project issue config has no filter rules.

  return project_config


def FindFieldDef(field_name, config):
  """Find the specified field, or return None."""
  if not field_name:
    return None
  field_name_lower = field_name.lower()
  for fd in config.field_defs:
    if fd.field_name.lower() == field_name_lower:
      return fd

  return None


def FindFieldDefByID(field_id, config):
  """Find the specified field, or return None."""
  for fd in config.field_defs:
    if fd.field_id == field_id:
      return fd

  return None


def FindApprovalDef(approval_name, config):
  """Find the specified approval, or return None."""
  fd = FindFieldDef(approval_name, config)
  if fd:
    return FindApprovalDefByID(fd.field_id, config)

  return None


def FindApprovalDefByID(approval_id, config):
  """Find the specified approval, or return None."""
  for approval_def in config.approval_defs:
    if approval_def.approval_id == approval_id:
      return approval_def

  return None


def FindApprovalValueByID(approval_id, approval_values):
  """Find the specified approval_value in the given list or return None."""
  for av in approval_values:
    if av.approval_id == approval_id:
      return av

  return None


def FindApprovalsSubfields(approval_ids, config):
  """Return a dict of {approval_ids: approval_subfields}."""
  approval_subfields_dict = collections.defaultdict(list)
  for fd in config.field_defs:
    if fd.approval_id in approval_ids:
      approval_subfields_dict[fd.approval_id].append(fd)

  return approval_subfields_dict


def FindPhaseByID(phase_id, phases):
  """Find the specified phase, or return None"""
  for phase in phases:
    if phase.phase_id == phase_id:
      return phase

  return None


def FindPhase(name, phases):
  """Find the specified phase, or return None"""
  for phase in phases:
    if phase.name.lower() == name.lower():
      return phase

  return None


def GetGrantedPerms(issue, effective_ids, config):
  """Return a set of permissions granted by user-valued fields in an issue."""
  granted_perms = set()
  for field_value in issue.field_values:
    if field_value.user_id in effective_ids:
      field_def = FindFieldDefByID(field_value.field_id, config)
      if field_def and field_def.grants_perm:
        # TODO(jrobbins): allow comma-separated list in grants_perm
        granted_perms.add(field_def.grants_perm.lower())

  return granted_perms


def LabelsByPrefix(labels, lower_field_names):
  """Convert a list of key-value labels into {lower_prefix: [value, ...]}.

  It also handles custom fields with dashes in the field name.
  """
  label_values_by_prefix = collections.defaultdict(list)
  for lab in labels:
    if '-' not in lab:
      continue
    lower_lab = lab.lower()
    for lower_field_name in lower_field_names:
      if lower_lab.startswith(lower_field_name + '-'):
        prefix = lower_field_name
        value = lab[len(lower_field_name)+1:]
        break
    else:  # No field name matched
      prefix, value = lab.split('-', 1)
      prefix = prefix.lower()
    label_values_by_prefix[prefix].append(value)
  return label_values_by_prefix


def LabelIsMaskedByField(label, field_names):
  """If the label should be displayed as a field, return the field name.

  Args:
    label: string label to consider.
    field_names: a list of field names in lowercase.

  Returns:
    If masked, return the lowercase name of the field, otherwise None.  A label
    is masked by a custom field if the field name "Foo" matches the key part of
    a key-value label "Foo-Bar".
  """
  if '-' not in label:
    return None

  for field_name_lower in field_names:
    if label.lower().startswith(field_name_lower + '-'):
      return field_name_lower

  return None


def NonMaskedLabels(labels, field_names):
  """Return only those labels that are not masked by custom fields."""
  return [lab for lab in labels
          if not LabelIsMaskedByField(lab, field_names)]


def ExplicitAndDerivedNonMaskedLabels(labels, derived_labels, config):
  """Return two lists of labels that are not masked by enum custom fields."""
  field_names = [fd.field_name.lower() for fd in config.field_defs
                 if fd.field_type is tracker_pb2.FieldTypes.ENUM_TYPE and
                 not fd.is_deleted]  # TODO(jrobbins): restricts
  labels = [
      lab for lab in labels
      if not LabelIsMaskedByField(lab, field_names)]
  derived_labels = [
    lab for lab in derived_labels
    if not LabelIsMaskedByField(lab, field_names)]
  return labels, derived_labels


def MakeApprovalValue(approval_id, approver_ids=None, status=None,
                      setter_id=None, set_on=None, phase_id=None):
  """Return an ApprovalValue PB with the given field values."""
  av = tracker_pb2.ApprovalValue(
      approval_id=approval_id, status=status,
      setter_id=setter_id, set_on=set_on, phase_id=phase_id)
  if approver_ids is not None:
    av.approver_ids = approver_ids
  return av


def MakeFieldDef(
    field_id,
    project_id,
    field_name,
    field_type_int,
    applic_type,
    applic_pred,
    is_required,
    is_niche,
    is_multivalued,
    min_value,
    max_value,
    regex,
    needs_member,
    needs_perm,
    grants_perm,
    notify_on,
    date_action,
    docstring,
    is_deleted,
    approval_id=None,
    is_phase_field=False,
    is_restricted_field=False):
  """Make a FieldDef PB for the given FieldDef table row tuple."""
  if isinstance(date_action, string_types):
    date_action = date_action.upper()
  fd = tracker_pb2.FieldDef(
      field_id=field_id,
      project_id=project_id,
      field_name=field_name,
      field_type=field_type_int,
      is_required=bool(is_required),
      is_niche=bool(is_niche),
      is_multivalued=bool(is_multivalued),
      docstring=docstring,
      is_deleted=bool(is_deleted),
      applicable_type=applic_type or '',
      applicable_predicate=applic_pred or '',
      needs_member=bool(needs_member),
      grants_perm=grants_perm or '',
      notify_on=tracker_pb2.NotifyTriggers(notify_on or 0),
      date_action=tracker_pb2.DateAction(date_action or 0),
      is_phase_field=bool(is_phase_field),
      is_restricted_field=bool(is_restricted_field))
  if min_value is not None:
    fd.min_value = min_value
  if max_value is not None:
    fd.max_value = max_value
  if regex is not None:
    fd.regex = regex
  if needs_perm is not None:
    fd.needs_perm = needs_perm
  if approval_id is not None:
    fd.approval_id = approval_id
  return fd


def MakeFieldValue(
    field_id, int_value, str_value, user_id, date_value, url_value, derived,
    phase_id=None):
  """Make a FieldValue based on the given information."""
  fv = tracker_pb2.FieldValue(field_id=field_id, derived=derived)
  if phase_id is not None:
    fv.phase_id = phase_id
  if int_value is not None:
    fv.int_value = int_value
  elif str_value is not None:
    fv.str_value = str_value
  elif user_id is not None:
    fv.user_id = user_id
  elif date_value is not None:
    fv.date_value = date_value
  elif url_value is not None:
    fv.url_value = url_value
  else:
    raise ValueError('Unexpected field value')
  return fv


def GetFieldValueWithRawValue(field_type, field_value, users_by_id, raw_value):
  """Find and return the field value of the specified field type.

  If the specified field_value is None or is empty then the raw_value is
  returned. When the field type is USER_TYPE the raw_value is used as a key to
  lookup users_by_id.

  Args:
    field_type: tracker_pb2.FieldTypes type.
    field_value: tracker_pb2.FieldValue type.
    users_by_id: Dict mapping user_ids to UserViews.
    raw_value: String to use if field_value is not specified.

  Returns:
    Value of the specified field type.
  """
  ret_value = GetFieldValue(field_value, users_by_id)
  if ret_value:
    return ret_value
  # Special case for user types.
  if field_type == tracker_pb2.FieldTypes.USER_TYPE:
    if raw_value in users_by_id:
      return users_by_id[raw_value].email
  return raw_value


def GetFieldValue(fv, users_by_id):
  """Return the value of this field.  Give emails for users in users_by_id."""
  if fv is None:
    return None
  elif fv.int_value is not None:
    return fv.int_value
  elif fv.str_value is not None:
    return fv.str_value
  elif fv.user_id is not None:
    if fv.user_id in users_by_id:
      return users_by_id[fv.user_id].email
    else:
      logging.info('Failed to lookup user %d when getting field', fv.user_id)
      return fv.user_id
  elif fv.date_value is not None:
    return timestr.TimestampToDateWidgetStr(fv.date_value)
  elif fv.url_value is not None:
    return fv.url_value
  else:
    return None


def FindComponentDef(path, config):
  """Find the specified component, or return None."""
  path_lower = path.lower()
  for cd in config.component_defs:
    if cd.path.lower() == path_lower:
      return cd

  return None


def FindMatchingComponentIDs(path, config, exact=True):
  """Return a list of components that match the given path."""
  component_ids = []
  path_lower = path.lower()

  if exact:
    for cd in config.component_defs:
      if cd.path.lower() == path_lower:
        component_ids.append(cd.component_id)
  else:
    path_lower_delim = path.lower() + '>'
    for cd in config.component_defs:
      target_delim = cd.path.lower() + '>'
      if target_delim.startswith(path_lower_delim):
        component_ids.append(cd.component_id)

  return component_ids


def FindComponentDefByID(component_id, config):
  """Find the specified component, or return None."""
  for cd in config.component_defs:
    if cd.component_id == component_id:
      return cd

  return None


def FindAncestorComponents(config, component_def):
  """Return a list of all components the given component is under."""
  path_lower = component_def.path.lower()
  return [cd for cd in config.component_defs
          if path_lower.startswith(cd.path.lower() + '>')]


def GetIssueComponentsAndAncestors(issue, config):
  """Return a list of all the components that an issue is in."""
  result = set()
  for component_id in issue.component_ids:
    cd = FindComponentDefByID(component_id, config)
    if cd is None:
      logging.error('Tried to look up non-existent component %r' % component_id)
      continue
    ancestors = FindAncestorComponents(config, cd)
    result.add(cd)
    result.update(ancestors)

  return sorted(result, key=lambda cd: cd.path)


def FindDescendantComponents(config, component_def):
  """Return a list of all nested components under the given component."""
  path_plus_delim = component_def.path.lower() + '>'
  return [cd for cd in config.component_defs
          if cd.path.lower().startswith(path_plus_delim)]


def MakeComponentDef(
    component_id, project_id, path, docstring, deprecated, admin_ids, cc_ids,
    created, creator_id, modified=None, modifier_id=None, label_ids=None):
  """Make a ComponentDef PB for the given FieldDef table row tuple."""
  cd = tracker_pb2.ComponentDef(
      component_id=component_id, project_id=project_id, path=path,
      docstring=docstring, deprecated=bool(deprecated),
      admin_ids=admin_ids, cc_ids=cc_ids, created=created,
      creator_id=creator_id, modified=modified, modifier_id=modifier_id,
      label_ids=label_ids or [])
  return cd


def MakeSavedQuery(
    query_id, name, base_query_id, query, subscription_mode=None,
    executes_in_project_ids=None):
  """Make SavedQuery PB for the given info."""
  saved_query = tracker_pb2.SavedQuery(
      name=name, base_query_id=base_query_id, query=query)
  if query_id is not None:
    saved_query.query_id = query_id
  if subscription_mode is not None:
    saved_query.subscription_mode = subscription_mode
  if executes_in_project_ids is not None:
    saved_query.executes_in_project_ids = executes_in_project_ids
  return saved_query


def SetConfigStatuses(project_config, well_known_statuses):
  """Internal method to set the well-known statuses of ProjectIssueConfig."""
  project_config.well_known_statuses = []
  for status, docstring, means_open, deprecated in well_known_statuses:
    canonical_status = framework_bizobj.CanonicalizeLabel(status)
    project_config.well_known_statuses.append(tracker_pb2.StatusDef(
        status_docstring=docstring, status=canonical_status,
        means_open=means_open, deprecated=deprecated))


def SetConfigLabels(project_config, well_known_labels):
  """Internal method to set the well-known labels of a ProjectIssueConfig."""
  project_config.well_known_labels = []
  for label, docstring, deprecated in well_known_labels:
    canonical_label = framework_bizobj.CanonicalizeLabel(label)
    project_config.well_known_labels.append(tracker_pb2.LabelDef(
        label=canonical_label, label_docstring=docstring,
        deprecated=deprecated))


def SetConfigApprovals(project_config, approval_def_tuples):
  """Internal method to set up approval defs of a ProjectissueConfig."""
  project_config.approval_defs = []
  for approval_id, approver_ids, survey in approval_def_tuples:
    project_config.approval_defs.append(tracker_pb2.ApprovalDef(
        approval_id=approval_id, approver_ids=approver_ids, survey=survey))


def ConvertDictToTemplate(template_dict):
  """Construct a Template PB with the values from template_dict.

  Args:
    template_dict: dictionary with fields corresponding to the Template
        PB fields.

  Returns:
    A Template protocol buffer that can be stored in the
    project's ProjectIssueConfig PB.
  """
  return MakeIssueTemplate(
      template_dict.get('name'), template_dict.get('summary'),
      template_dict.get('status'), template_dict.get('owner_id'),
      template_dict.get('content'), template_dict.get('labels'), [], [],
      template_dict.get('components'),
      summary_must_be_edited=template_dict.get('summary_must_be_edited'),
      owner_defaults_to_member=template_dict.get('owner_defaults_to_member'),
      component_required=template_dict.get('component_required'),
      members_only=template_dict.get('members_only'))


def MakeIssueTemplate(
    name,
    summary,
    status,
    owner_id,
    content,
    labels,
    field_values,
    admin_ids,
    component_ids,
    summary_must_be_edited=None,
    owner_defaults_to_member=None,
    component_required=None,
    members_only=None,
    phases=None,
    approval_values=None):
  """Make an issue template PB."""
  template = tracker_pb2.TemplateDef()
  template.name = name
  if summary:
    template.summary = summary
  if status:
    template.status = status
  if owner_id:
    template.owner_id = owner_id
  template.content = content
  template.field_values = field_values
  template.labels = labels or []
  template.admin_ids = admin_ids
  template.component_ids = component_ids or []
  template.approval_values = approval_values or []

  if summary_must_be_edited is not None:
    template.summary_must_be_edited = summary_must_be_edited
  if owner_defaults_to_member is not None:
    template.owner_defaults_to_member = owner_defaults_to_member
  if component_required is not None:
    template.component_required = component_required
  if members_only is not None:
    template.members_only = members_only
  if phases is not None:
    template.phases = phases

  return template


def MakeDefaultProjectIssueConfig(project_id):
  """Return a ProjectIssueConfig with use by projects that don't have one."""
  return MakeProjectIssueConfig(
      project_id,
      tracker_constants.DEFAULT_WELL_KNOWN_STATUSES,
      tracker_constants.DEFAULT_STATUSES_OFFER_MERGE,
      tracker_constants.DEFAULT_WELL_KNOWN_LABELS,
      tracker_constants.DEFAULT_EXCL_LABEL_PREFIXES,
      tracker_constants.DEFAULT_COL_SPEC)


def HarmonizeConfigs(config_list):
  """Combine several ProjectIssueConfigs into one for cross-project sorting.

  Args:
    config_list: a list of ProjectIssueConfig PBs with labels and statuses
        among other fields.

  Returns:
    A new ProjectIssueConfig with just the labels and status values filled
    in to be a logical union of the given configs.  Specifically, the order
    of the combined status and label lists should be maintained.
  """
  if not config_list:
    return MakeDefaultProjectIssueConfig(None)

  harmonized_status_names = _CombineOrderedLists(
      [[stat.status for stat in config.well_known_statuses]
       for config in config_list])
  harmonized_label_names = _CombineOrderedLists(
      [[lab.label for lab in config.well_known_labels]
       for config in config_list])
  harmonized_default_sort_spec = ' '.join(
      config.default_sort_spec for config in config_list)
  harmonized_means_open = {
      status: any([stat.means_open
                   for config in config_list
                   for stat in config.well_known_statuses
                   if stat.status == status])
      for status in harmonized_status_names}

  # This col_spec is probably not what the user wants to view because it is
  # too much information.  We join all the col_specs here so that we are sure
  # to lookup all users needed for sorting, even if it is more than needed.
  # xxx we need to look up users based on colspec rather than sortspec?
  harmonized_default_col_spec = ' '.join(
      config.default_col_spec for config in config_list)

  result_config = tracker_pb2.ProjectIssueConfig()
  # The combined config is only used during sorting, never stored.
  result_config.default_col_spec = harmonized_default_col_spec
  result_config.default_sort_spec = harmonized_default_sort_spec

  for status_name in harmonized_status_names:
    result_config.well_known_statuses.append(tracker_pb2.StatusDef(
        status=status_name, means_open=harmonized_means_open[status_name]))

  for label_name in harmonized_label_names:
    result_config.well_known_labels.append(tracker_pb2.LabelDef(
        label=label_name))

  for config in config_list:
    result_config.field_defs.extend(
      list(fd for fd in config.field_defs if not fd.is_deleted))
    result_config.component_defs.extend(config.component_defs)
    result_config.approval_defs.extend(config.approval_defs)

  return result_config


def HarmonizeLabelOrStatusRows(def_rows):
  """Put the given label defs into a logical global order."""
  ranked_defs_by_project = {}
  oddball_defs = []
  for row in def_rows:
    def_id, project_id, rank, label = row[0], row[1], row[2], row[3]
    if rank is not None:
      ranked_defs_by_project.setdefault(project_id, []).append(
          (def_id, rank, label))
    else:
      oddball_defs.append((def_id, rank, label))

  oddball_defs.sort(reverse=True, key=lambda def_tuple: def_tuple[2].lower())
  # Compose the list-of-lists in a consistent order by project_id.
  list_of_lists = [ranked_defs_by_project[pid]
                   for pid in sorted(ranked_defs_by_project.keys())]
  harmonized_ranked_defs = _CombineOrderedLists(
      list_of_lists, include_duplicate_keys=True,
      key=lambda def_tuple: def_tuple[2])

  return oddball_defs + harmonized_ranked_defs


def _CombineOrderedLists(
    list_of_lists, include_duplicate_keys=False, key=lambda x: x):
  """Combine lists of items while maintaining their desired order.

  Args:
    list_of_lists: a list of lists of strings.
    include_duplicate_keys: Pass True to make the combined list have the
        same total number of elements as the sum of the input lists.
    key: optional function to choose which part of the list items hold the
        string used for comparison.  The result will have the whole items.

  Returns:
    A single list of items containing one copy of each of the items
    in any of the original list, and in an order that maintains the original
    list ordering as much as possible.
  """
  combined_items = []
  combined_keys = []
  seen_keys_set = set()
  for one_list in list_of_lists:
    _AccumulateCombinedList(
        one_list, combined_items, combined_keys, seen_keys_set, key=key,
        include_duplicate_keys=include_duplicate_keys)

  return combined_items


def _AccumulateCombinedList(
    one_list, combined_items, combined_keys, seen_keys_set,
    include_duplicate_keys=False, key=lambda x: x):
  """Accumulate strings into a combined list while its maintaining ordering.

  Args:
    one_list: list of strings in a desired order.
    combined_items: accumulated list of items in the desired order.
    combined_keys: accumulated list of key strings in the desired order.
    seen_keys_set: set of strings that are already in combined_list.
    include_duplicate_keys: Pass True to make the combined list have the
        same total number of elements as the sum of the input lists.
    key: optional function to choose which part of the list items hold the
        string used for comparison.  The result will have the whole items.

  Returns:
    Nothing.  But, combined_items is modified to mix in all the items of
    one_list at appropriate points such that nothing in combined_items
    is reordered, and the ordering of items from one_list is maintained
    as much as possible.  Also, seen_keys_set is modified to add any keys
    for items that were added to combined_items.

  Also, any strings that begin with "#" are compared regardless of the "#".
  The purpose of such strings is to guide the final ordering.
  """
  insert_idx = 0
  for item in one_list:
    s = key(item).lower()
    if s in seen_keys_set:
      item_idx = combined_keys.index(s)  # Need parallel list of keys
      insert_idx = max(insert_idx, item_idx + 1)

    if s not in seen_keys_set or include_duplicate_keys:
      combined_items.insert(insert_idx, item)
      combined_keys.insert(insert_idx, s)
      insert_idx += 1

    seen_keys_set.add(s)


def GetBuiltInQuery(query_id):
  """If the given query ID is for a built-in query, return that string."""
  return tracker_constants.DEFAULT_CANNED_QUERY_CONDS.get(query_id, '')


def UsersInvolvedInAmendments(amendments):
  """Return a set of all user IDs mentioned in the given Amendments."""
  user_id_set = set()
  for amendment in amendments:
    user_id_set.update(amendment.added_user_ids)
    user_id_set.update(amendment.removed_user_ids)

  return user_id_set


def _AccumulateUsersInvolvedInComment(comment, user_id_set):
  """Build up a set of all users involved in an IssueComment.

  Args:
    comment: an IssueComment PB.
    user_id_set: a set of user IDs to build up.

  Returns:
    The same set, but modified to have the user IDs of user who
    entered the comment, and all the users mentioned in any amendments.
  """
  user_id_set.add(comment.user_id)
  user_id_set.update(UsersInvolvedInAmendments(comment.amendments))

  return user_id_set


def UsersInvolvedInComment(comment):
  """Return a set of all users involved in an IssueComment.

  Args:
    comment: an IssueComment PB.

  Returns:
    A set with the user IDs of user who entered the comment, and all the
    users mentioned in any amendments.
  """
  return _AccumulateUsersInvolvedInComment(comment, set())


def UsersInvolvedInCommentList(comments):
  """Return a set of all users involved in a list of IssueComments.

  Args:
    comments: a list of IssueComment PBs.

  Returns:
    A set with the user IDs of user who entered the comment, and all the
    users mentioned in any amendments.
  """
  result = set()
  for c in comments:
    _AccumulateUsersInvolvedInComment(c, result)

  return result


def UsersInvolvedInIssues(issues):
  """Return a set of all user IDs referenced in the issues' metadata."""
  result = set()
  for issue in issues:
    result.update([issue.reporter_id, issue.owner_id, issue.derived_owner_id])
    result.update(issue.cc_ids)
    result.update(issue.derived_cc_ids)
    result.update(fv.user_id for fv in issue.field_values if fv.user_id)
    for av in issue.approval_values:
      result.update(approver_id for approver_id in av.approver_ids)
      if av.setter_id:
        result.update([av.setter_id])

  return result


def UsersInvolvedInTemplate(template):
  """Return a set of all user IDs referenced in the template."""
  result = set(
    template.admin_ids +
    [fv.user_id for fv in template.field_values if fv.user_id])
  if template.owner_id:
    result.add(template.owner_id)
  for av in template.approval_values:
    result.update(set(av.approver_ids))
    if av.setter_id:
      result.add(av.setter_id)
  return result


def UsersInvolvedInTemplates(templates):
  """Return a set of all user IDs referenced in the given templates."""
  result = set()
  for template in templates:
    result.update(UsersInvolvedInTemplate(template))
  return result


def UsersInvolvedInComponents(component_defs):
  """Return a set of user IDs referenced in the given components."""
  result = set()
  for cd in component_defs:
    result.update(cd.admin_ids)
    result.update(cd.cc_ids)
    if cd.creator_id:
      result.add(cd.creator_id)
    if cd.modifier_id:
      result.add(cd.modifier_id)

  return result


def UsersInvolvedInApprovalDefs(approval_defs, matching_fds):
  # type: (Sequence[proto.tracker_pb2.ApprovalDef],
  #     Sequence[proto.tracker_pb2.FieldDef]) -> Collection[int]
  """Return a set of user IDs referenced in the approval_defs and field defs"""
  result = set()
  for ad in approval_defs:
    result.update(ad.approver_ids)
  for fd in matching_fds:
    result.update(fd.admin_ids)
  return result


def UsersInvolvedInConfig(config):
  """Return a set of all user IDs referenced in the config."""
  result = set()
  for ad in config.approval_defs:
    result.update(ad.approver_ids)
  for fd in config.field_defs:
    result.update(fd.admin_ids)
  result.update(UsersInvolvedInComponents(config.component_defs))
  return result


def LabelIDsInvolvedInConfig(config):
  """Return a set of all label IDs referenced in the config."""
  result = set()
  for cd in config.component_defs:
    result.update(cd.label_ids)
  return result


def MakeApprovalDelta(
    status, setter_id, approver_ids_add, approver_ids_remove,
    subfield_vals_add, subfield_vals_remove, subfields_clear, labels_add,
    labels_remove, set_on=None):
  approval_delta = tracker_pb2.ApprovalDelta(
      approver_ids_add=approver_ids_add,
      approver_ids_remove=approver_ids_remove,
      subfield_vals_add=subfield_vals_add,
      subfield_vals_remove=subfield_vals_remove,
      subfields_clear=subfields_clear,
      labels_add=labels_add,
      labels_remove=labels_remove
  )
  if status is not None:
    approval_delta.status = status
    approval_delta.set_on = set_on or int(time.time())
    approval_delta.setter_id = setter_id

  return approval_delta


def MakeIssueDelta(
    status, owner_id, cc_ids_add, cc_ids_remove, comp_ids_add, comp_ids_remove,
    labels_add, labels_remove, field_vals_add, field_vals_remove, fields_clear,
    blocked_on_add, blocked_on_remove, blocking_add, blocking_remove,
    merged_into, summary, ext_blocked_on_add=None, ext_blocked_on_remove=None,
    ext_blocking_add=None, ext_blocking_remove=None, merged_into_external=None):
  """Construct an IssueDelta object with the given fields, iff non-None."""
  delta = tracker_pb2.IssueDelta(
      cc_ids_add=cc_ids_add, cc_ids_remove=cc_ids_remove,
      comp_ids_add=comp_ids_add, comp_ids_remove=comp_ids_remove,
      labels_add=labels_add, labels_remove=labels_remove,
      field_vals_add=field_vals_add, field_vals_remove=field_vals_remove,
      fields_clear=fields_clear,
      blocked_on_add=blocked_on_add, blocked_on_remove=blocked_on_remove,
      blocking_add=blocking_add, blocking_remove=blocking_remove)
  if status is not None:
    delta.status = status
  if owner_id is not None:
    delta.owner_id = owner_id
  if merged_into is not None:
    delta.merged_into = merged_into
  if merged_into_external is not None:
    delta.merged_into_external = merged_into_external
  if summary is not None:
    delta.summary = summary
  if ext_blocked_on_add is not None:
    delta.ext_blocked_on_add = ext_blocked_on_add
  if ext_blocked_on_remove is not None:
    delta.ext_blocked_on_remove = ext_blocked_on_remove
  if ext_blocking_add is not None:
    delta.ext_blocking_add = ext_blocking_add
  if ext_blocking_remove is not None:
    delta.ext_blocking_remove = ext_blocking_remove

  return delta


def ApplyLabelChanges(issue, config, labels_add, labels_remove):
  """Updates the PB issue's labels and returns the amendment or None."""
  canon_labels_add = [framework_bizobj.CanonicalizeLabel(l)
                      for l in labels_add]
  labels_add = [l for l in canon_labels_add if l]
  canon_labels_remove = [framework_bizobj.CanonicalizeLabel(l)
                         for l in labels_remove]
  labels_remove = [l for l in canon_labels_remove if l]

  (labels, update_labels_add,
   update_labels_remove) = framework_bizobj.MergeLabels(
       issue.labels, labels_add, labels_remove, config)

  if update_labels_add or update_labels_remove:
    issue.labels = labels
    return MakeLabelsAmendment(
          update_labels_add, update_labels_remove)
  return None


def ApplyFieldValueChanges(issue, config, fvs_add, fvs_remove, fields_clear):
  """Updates the PB issue's field_values and returns an amendments list."""
  phase_names_dict = {phase.phase_id: phase.name for phase in issue.phases}
  phase_ids = list(phase_names_dict.keys())
  (field_vals, added_fvs_by_id,
   removed_fvs_by_id) = _MergeFields(
       issue.field_values,
       [fv for fv in fvs_add if not fv.phase_id or fv.phase_id in phase_ids],
       [fv for fv in fvs_remove if not fv.phase_id or fv.phase_id in phase_ids],
       config.field_defs)
  amendments = []
  if added_fvs_by_id or removed_fvs_by_id:
    issue.field_values = field_vals
    for fd in config.field_defs:
      fd_added_values_by_phase = collections.defaultdict(list)
      fd_removed_values_by_phase = collections.defaultdict(list)
      # Split fd's added/removed fvs by the phase they belong to.
      # non-phase fds will result in {None: [added_fvs]}
      for fv in added_fvs_by_id.get(fd.field_id, []):
        fd_added_values_by_phase[fv.phase_id].append(fv)
      for fv in removed_fvs_by_id.get(fd.field_id, []):
        fd_removed_values_by_phase[fv.phase_id].append(fv)
      # Use all_fv_phase_ids to create Amendments, so no empty amendments
      # are created for issue phases that had no field value changes.
      all_fv_phase_ids = set(
          fd_removed_values_by_phase.keys() + fd_added_values_by_phase.keys())
      for phase_id in all_fv_phase_ids:
        new_values = [GetFieldValue(fv, {}) for fv
                      in fd_added_values_by_phase.get(phase_id, [])]
        old_values = [GetFieldValue(fv, {}) for fv
                      in fd_removed_values_by_phase.get(phase_id, [])]
        amendments.append(MakeFieldAmendment(
              fd.field_id, config, new_values, old_values=old_values,
              phase_name=phase_names_dict.get(phase_id)))

  # Note: Clearing fields is used with bulk-editing and phase fields do
  # not appear there and cannot be bulk-edited.
  if fields_clear:
    field_clear_set = set(fields_clear)
    revised_fields = []
    for fd in config.field_defs:
      if fd.field_id not in field_clear_set:
        revised_fields.extend(
            fv for fv in issue.field_values if fv.field_id == fd.field_id)
      else:
        amendments.append(
            MakeFieldClearedAmendment(fd.field_id, config))
        if fd.field_type == tracker_pb2.FieldTypes.ENUM_TYPE:
          prefix = fd.field_name.lower() + '-'
          filtered_labels = [
              lab for lab in issue.labels
              if not lab.lower().startswith(prefix)]
          issue.labels = filtered_labels

    issue.field_values = revised_fields
  return amendments


def ApplyIssueDelta(cnxn, issue_service, issue, delta, config):
  """Apply an issue delta to an issue in RAM.

  Args:
    cnxn: connection to SQL database.
    issue_service: object to access issue-related data in the database.
    issue: Issue to be updated.
    delta: IssueDelta object with new values for everything being changed.
    config: ProjectIssueConfig object for the project containing the issue.

  Returns:
    A pair (amendments, impacted_iids) where amendments is a list of Amendment
    protos to describe what changed, and impacted_iids is a set of other IIDs
    for issues that are modified because they are related to the given issue.
  """
  amendments = []
  impacted_iids = set()
  if (delta.status is not None and delta.status != issue.status):
    status = framework_bizobj.CanonicalizeLabel(delta.status)
    amendments.append(MakeStatusAmendment(status, issue.status))
    issue.status = status
  if (delta.owner_id is not None and delta.owner_id != issue.owner_id):
    amendments.append(MakeOwnerAmendment(delta.owner_id, issue.owner_id))
    issue.owner_id = delta.owner_id

  # compute the set of cc'd users added and removed
  cc_add = [cc for cc in delta.cc_ids_add if cc not in issue.cc_ids]
  cc_remove = [cc for cc in delta.cc_ids_remove if cc in issue.cc_ids]
  if cc_add or cc_remove:
    cc_ids = [cc for cc in list(issue.cc_ids) + cc_add
              if cc not in cc_remove]
    issue.cc_ids = cc_ids
    amendments.append(MakeCcAmendment(cc_add, cc_remove))

  # compute the set of components added and removed
  comp_ids_add = [
      c for c in delta.comp_ids_add if c not in issue.component_ids]
  comp_ids_remove = [
      c for c in delta.comp_ids_remove if c in issue.component_ids]
  if comp_ids_add or comp_ids_remove:
    comp_ids = [cid for cid in list(issue.component_ids) + comp_ids_add
                if cid not in comp_ids_remove]
    issue.component_ids = comp_ids
    amendments.append(MakeComponentsAmendment(
        comp_ids_add, comp_ids_remove, config))

  # compute the set of labels added and removed
  label_amendment = ApplyLabelChanges(
      issue, config, delta.labels_add, delta.labels_remove)
  if label_amendment:
    amendments.append(label_amendment)

  # compute the set of custom fields added and removed
  fv_amendments = ApplyFieldValueChanges(
      issue, config, delta.field_vals_add, delta.field_vals_remove,
      delta.fields_clear)
  amendments.extend(fv_amendments)

  if delta.blocked_on_add or delta.blocked_on_remove:
    old_blocked_on = issue.blocked_on_iids
    blocked_on_add = [iid for iid in delta.blocked_on_add
                      if iid not in old_blocked_on]
    add_refs = [
        (ref_issue.project_name, ref_issue.local_id)
        for ref_issue in issue_service.GetIssues(cnxn, delta.blocked_on_add)]
    blocked_on_rm = [iid for iid in delta.blocked_on_remove
                     if iid in old_blocked_on]
    remove_refs = [
        (ref_issue.project_name, ref_issue.local_id)
        for ref_issue in issue_service.GetIssues(cnxn, blocked_on_rm)]
    amendments.append(MakeBlockedOnAmendment(
        add_refs, remove_refs, default_project_name=issue.project_name))
    blocked_on = [iid for iid in old_blocked_on + blocked_on_add
                  if iid not in delta.blocked_on_remove]
    (issue.blocked_on_iids, issue.blocked_on_ranks
     ) = issue_service.SortBlockedOn(cnxn, issue, blocked_on)
    impacted_iids.update(blocked_on_add + blocked_on_rm)

  if delta.blocking_add or delta.blocking_remove:
    old_blocking = issue.blocking_iids
    blocking_add = [iid for iid in delta.blocking_add
                    if iid not in old_blocking]
    add_refs = [(ref_issue.project_name, ref_issue.local_id)
                for ref_issue in issue_service.GetIssues(cnxn, blocking_add)]
    blocking_remove = [iid for iid in delta.blocking_remove
                       if iid in old_blocking]
    remove_refs = [
        (ref_issue.project_name, ref_issue.local_id)
        for ref_issue in issue_service.GetIssues(cnxn, blocking_remove)]
    amendments.append(MakeBlockingAmendment(
        add_refs, remove_refs, default_project_name=issue.project_name))
    blocking_refs = [iid for iid in old_blocking + blocking_add
                     if iid not in blocking_remove]
    issue.blocking_iids = blocking_refs
    impacted_iids.update(blocking_add + blocking_remove)

  # Update external issue references.
  if delta.ext_blocked_on_add or delta.ext_blocked_on_remove:
    add_refs = [
        tracker_pb2.DanglingIssueRef(ext_issue_identifier=ext_id)
        for ext_id in delta.ext_blocked_on_add
        if federated.IsShortlinkValid(ext_id)]
    remove_refs = [
        tracker_pb2.DanglingIssueRef(ext_issue_identifier=ext_id)
        for ext_id in delta.ext_blocked_on_remove
        if federated.IsShortlinkValid(ext_id)]
    amendments.append(MakeBlockedOnAmendment(add_refs, remove_refs))
    issue.dangling_blocked_on_refs = [
        ref for ref in issue.dangling_blocked_on_refs + add_refs
        if ref.ext_issue_identifier not in delta.ext_blocked_on_remove]

  # Update external issue references.
  if delta.ext_blocking_add or delta.ext_blocking_remove:
    add_refs = [
        tracker_pb2.DanglingIssueRef(ext_issue_identifier=ext_id)
        for ext_id in delta.ext_blocking_add
        if federated.IsShortlinkValid(ext_id)]
    remove_refs = [
        tracker_pb2.DanglingIssueRef(ext_issue_identifier=ext_id)
        for ext_id in delta.ext_blocking_remove
        if federated.IsShortlinkValid(ext_id)]
    amendments.append(MakeBlockingAmendment(add_refs, remove_refs))
    issue.dangling_blocking_refs = [
        ref for ref in issue.dangling_blocking_refs + add_refs
        if ref.ext_issue_identifier not in delta.ext_blocking_remove]

  if delta.merged_into and delta.merged_into_external:
    raise ValueError(('Cannot update merged_into and merged_into_external'
      ' fields at the same time.'))

  if (delta.merged_into is not None and
      delta.merged_into != 0 and
      delta.merged_into != issue.merged_into):
    merged_remove = issue.merged_into
    merged_add = delta.merged_into
    issue.merged_into = delta.merged_into
    try:
      remove_issue = issue_service.GetIssue(cnxn, merged_remove)
      remove_ref = remove_issue.project_name, remove_issue.local_id
      impacted_iids.add(merged_remove)
    except exceptions.NoSuchIssueException:
      remove_ref = None

    # Handle going from external->internal mergedinto.
    if issue.merged_into_external:
      remove_ref = tracker_pb2.DanglingIssueRef(
          ext_issue_identifier=issue.merged_into_external)
      issue.merged_into_external = None

    try:
      add_issue = issue_service.GetIssue(cnxn, merged_add)
      add_ref = add_issue.project_name, add_issue.local_id
      impacted_iids.add(merged_add)
    except exceptions.NoSuchIssueException:
      add_ref = None

    amendments.append(MakeMergedIntoAmendment(
        add_ref, remove_ref, default_project_name=issue.project_name))

  if (delta.merged_into_external is not None and
      delta.merged_into_external != issue.merged_into_external and
      federated.IsShortlinkValid(delta.merged_into_external)):

    remove_ref = None
    if issue.merged_into_external:
      remove_ref = tracker_pb2.DanglingIssueRef(
          ext_issue_identifier=issue.merged_into_external)
    elif issue.merged_into:
      # Handle moving from internal->external mergedinto.
      try:
        remove_issue = issue_service.GetIssue(cnxn, issue.merged_into)
        remove_ref = remove_issue.project_name, remove_issue.local_id
        impacted_iids.add(issue.merged_into)
      except exceptions.NoSuchIssueException:
        pass

    if federated.IsShortlinkValid(delta.merged_into_external):
      add_ref = tracker_pb2.DanglingIssueRef(
          ext_issue_identifier=delta.merged_into_external)
    else:
      add_ref = None

    issue.merged_into = 0
    issue.merged_into_external = delta.merged_into_external
    amendments.append(MakeMergedIntoAmendment(add_ref, remove_ref,
        default_project_name=issue.project_name))

  if delta.summary and delta.summary != issue.summary:
    amendments.append(MakeSummaryAmendment(delta.summary, issue.summary))
    issue.summary = delta.summary

  return amendments, impacted_iids


def MakeAmendment(
    field, new_value, added_ids, removed_ids, custom_field_name=None,
    old_value=None):
  """Utility function to populate an Amendment PB.

  Args:
    field: enum for the field being updated.
    new_value: new string value of that field.
    added_ids: list of user IDs being added.
    removed_ids: list of user IDs being removed.
    custom_field_name: optional name of a custom field.
    old_value: old string value of that field.

  Returns:
    An instance of Amendment.
  """
  amendment = tracker_pb2.Amendment()
  amendment.field = field
  amendment.newvalue = new_value
  amendment.added_user_ids.extend(added_ids)
  amendment.removed_user_ids.extend(removed_ids)

  if old_value is not None:
    amendment.oldvalue = old_value

  if custom_field_name is not None:
    amendment.custom_field_name = custom_field_name

  return amendment


def _PlusMinusString(added_items, removed_items):
  """Return a concatenation of the items, with a minus on removed items.

  Args:
    added_items: list of string items added.
    removed_items: list of string items removed.

  Returns:
    A unicode string with all the removed items first (preceeded by minus
    signs) and then the added items.
  """
  assert all(isinstance(item, string_types)
             for item in added_items + removed_items)
  # TODO(jrobbins): this is not good when values can be negative ints.
  return ' '.join(
      ['-%s' % item.strip()
       for item in removed_items if item] +
      ['%s' % item for item in added_items if item])


def _PlusMinusAmendment(
    field, added_items, removed_items, custom_field_name=None):
  """Make an Amendment PB with the given added/removed items."""
  return MakeAmendment(
      field, _PlusMinusString(added_items, removed_items), [], [],
      custom_field_name=custom_field_name)


def _PlusMinusRefsAmendment(
    field, added_refs, removed_refs, default_project_name=None):
  """Make an Amendment PB with the given added/removed refs."""
  return _PlusMinusAmendment(
      field,
      [FormatIssueRef(r, default_project_name=default_project_name)
       for r in added_refs if r],
      [FormatIssueRef(r, default_project_name=default_project_name)
       for r in removed_refs if r])


def MakeSummaryAmendment(new_summary, old_summary):
  """Make an Amendment PB for a change to the summary."""
  return MakeAmendment(
      tracker_pb2.FieldID.SUMMARY, new_summary, [], [], old_value=old_summary)


def MakeStatusAmendment(new_status, old_status):
  """Make an Amendment PB for a change to the status."""
  return MakeAmendment(
      tracker_pb2.FieldID.STATUS, new_status, [], [], old_value=old_status)


def MakeOwnerAmendment(new_owner_id, old_owner_id):
  """Make an Amendment PB for a change to the owner."""
  return MakeAmendment(
      tracker_pb2.FieldID.OWNER, '', [new_owner_id], [old_owner_id])


def MakeCcAmendment(added_cc_ids, removed_cc_ids):
  """Make an Amendment PB for a change to the Cc list."""
  return MakeAmendment(
      tracker_pb2.FieldID.CC, '', added_cc_ids, removed_cc_ids)


def MakeLabelsAmendment(added_labels, removed_labels):
  """Make an Amendment PB for a change to the labels."""
  return _PlusMinusAmendment(
      tracker_pb2.FieldID.LABELS, added_labels, removed_labels)


def DiffValueLists(new_list, old_list):
  """Give an old list and a new list, return the added and removed items."""
  if not old_list:
    return new_list, []
  if not new_list:
    return [], old_list

  added = []
  removed = old_list[:]  # Assume everything was removed, then narrow that down
  for val in new_list:
    if val in removed:
      removed.remove(val)
    else:
      added.append(val)

  return added, removed


def MakeFieldAmendment(
    field_id, config, new_values, old_values=None, phase_name=None):
  """Return an amendment showing how an issue's field changed.

  Args:
    field_id: int field ID of a built-in or custom issue field.
    config: config info for the current project, including field_defs.
    new_values: list of strings representing new values of field.
    old_values: list of strings representing old values of field.
    phase_name: name of the phase that owned the field that was changed.

  Returns:
    A new Amemdnent object.

  Raises:
    ValueError: if the specified field was not found.
  """
  fd = FindFieldDefByID(field_id, config)

  if fd is None:
    raise ValueError('field %r vanished mid-request', field_id)

  field_name = fd.field_name if not phase_name else '%s-%s' % (
      phase_name, fd.field_name)
  if fd.is_multivalued:
    old_values = old_values or []
    added, removed = DiffValueLists(new_values, old_values)
    if fd.field_type == tracker_pb2.FieldTypes.USER_TYPE:
      return MakeAmendment(
          tracker_pb2.FieldID.CUSTOM, '', added, removed,
          custom_field_name=field_name)
    else:
      return _PlusMinusAmendment(
          tracker_pb2.FieldID.CUSTOM,
          ['%s' % item for item in added],
          ['%s' % item for item in removed],
          custom_field_name=field_name)

  else:
    if fd.field_type == tracker_pb2.FieldTypes.USER_TYPE:
      return MakeAmendment(
          tracker_pb2.FieldID.CUSTOM, '', new_values, [],
          custom_field_name=field_name)

    if new_values:
      new_str = ', '.join('%s' % item for item in new_values)
    else:
      new_str = '----'

    return MakeAmendment(
        tracker_pb2.FieldID.CUSTOM, new_str, [], [],
        custom_field_name=field_name)


def MakeFieldClearedAmendment(field_id, config):
  fd = FindFieldDefByID(field_id, config)

  if fd is None:
    raise ValueError('field %r vanished mid-request', field_id)

  return MakeAmendment(
      tracker_pb2.FieldID.CUSTOM, '----', [], [],
      custom_field_name=fd.field_name)


def MakeApprovalStructureAmendment(new_approvals, old_approvals):
  """Return an Amendment showing an issue's approval structure changed.

  Args:
    new_approvals: the new list of approvals.
    old_approvals: the old list of approvals.

  Returns:
    A new Amendment object.
  """

  approvals_added, approvals_removed = DiffValueLists(
      new_approvals, old_approvals)
  return MakeAmendment(
      tracker_pb2.FieldID.CUSTOM, _PlusMinusString(
          approvals_added, approvals_removed),
      [], [], custom_field_name='Approvals')


def MakeApprovalStatusAmendment(new_status):
  """Return an Amendment showing an issue approval's status changed.

  Args:
    new_status: ApprovalStatus representing the new approval status.

  Returns:
    A new Amemdnent object.
  """
  return MakeAmendment(
      tracker_pb2.FieldID.CUSTOM, new_status.name.lower(), [], [],
      custom_field_name='Status')


def MakeApprovalApproversAmendment(approvers_add, approvers_remove):
  """Return an Amendment showing an issue approval's approvers changed.

  Args:
    approvers_add: list of approver user_ids being added.
    approvers_remove: list of approver user_ids being removed.

  Returns:
    A new Amendment object.
  """
  return MakeAmendment(
      tracker_pb2.FieldID.CUSTOM, '', approvers_add, approvers_remove,
      custom_field_name='Approvers')


def MakeComponentsAmendment(added_comp_ids, removed_comp_ids, config):
  """Make an Amendment PB for a change to the components."""
  # TODO(jrobbins): record component IDs as ints and display them with
  # lookups (and maybe permission checks in the future).  But, what
  # about history that references deleleted components?
  added_comp_paths = []
  for comp_id in added_comp_ids:
    cd = FindComponentDefByID(comp_id, config)
    if cd:
      added_comp_paths.append(cd.path)

  removed_comp_paths = []
  for comp_id in removed_comp_ids:
    cd = FindComponentDefByID(comp_id, config)
    if cd:
      removed_comp_paths.append(cd.path)

  return _PlusMinusAmendment(
      tracker_pb2.FieldID.COMPONENTS,
      added_comp_paths, removed_comp_paths)


def MakeBlockedOnAmendment(
    added_refs, removed_refs, default_project_name=None):
  """Make an Amendment PB for a change to the blocked on issues."""
  return _PlusMinusRefsAmendment(
      tracker_pb2.FieldID.BLOCKEDON, added_refs, removed_refs,
      default_project_name=default_project_name)


def MakeBlockingAmendment(added_refs, removed_refs, default_project_name=None):
  """Make an Amendment PB for a change to the blocking issues."""
  return _PlusMinusRefsAmendment(
      tracker_pb2.FieldID.BLOCKING, added_refs, removed_refs,
      default_project_name=default_project_name)


def MakeMergedIntoAmendment(added_ref, removed_ref, default_project_name=None):
  """Make an Amendment PB for a change to the merged-into issue."""
  return _PlusMinusRefsAmendment(
      tracker_pb2.FieldID.MERGEDINTO, [added_ref], [removed_ref],
      default_project_name=default_project_name)


def MakeProjectAmendment(new_project_name):
  """Make an Amendment PB for a change to an issue's project."""
  return MakeAmendment(
      tracker_pb2.FieldID.PROJECT, new_project_name, [], [])


def AmendmentString_New(amendment, user_display_names):
  # type: (tracker_pb2.Amendment, Mapping[int, str]) -> str
  """Produce a displayable string for an Amendment PB.

  Args:
    amendment: Amendment PB to display.
    user_display_names: dict {user_id: display_name, ...} including all users
        mentioned in amendment.

  Returns:
    A string that could be displayed on a web page or sent in email.
  """
  if amendment.newvalue:
    return amendment.newvalue

  # Display new owner only
  if amendment.field == tracker_pb2.FieldID.OWNER:
    if amendment.added_user_ids and amendment.added_user_ids[0]:
      uid = amendment.added_user_ids[0]
      result = user_display_names[uid]
    else:
      result = framework_constants.NO_USER_NAME
  else:
    added = [
        user_display_names[uid]
        for uid in amendment.added_user_ids
        if uid in user_display_names
    ]
    removed = [
        user_display_names[uid]
        for uid in amendment.removed_user_ids
        if uid in user_display_names
    ]
    result = _PlusMinusString(added, removed)

  return result


def AmendmentString(amendment, user_views_by_id):
  """Produce a displayable string for an Amendment PB.

  TODO(crbug.com/monorail/7571): Delete this function in favor of _New.

  Args:
    amendment: Amendment PB to display.
    user_views_by_id: dict {user_id: user_view, ...} including all users
        mentioned in amendment.

  Returns:
    A string that could be displayed on a web page or sent in email.
  """
  if amendment.newvalue:
    return amendment.newvalue

  # Display new owner only
  if amendment.field == tracker_pb2.FieldID.OWNER:
    if amendment.added_user_ids and amendment.added_user_ids[0]:
      uid = amendment.added_user_ids[0]
      result = user_views_by_id[uid].display_name
    else:
      result = framework_constants.NO_USER_NAME
  else:
    result = _PlusMinusString(
        [user_views_by_id[uid].display_name for uid in amendment.added_user_ids
         if uid in user_views_by_id],
        [user_views_by_id[uid].display_name
         for uid in amendment.removed_user_ids if uid in user_views_by_id])

  return result


def AmendmentLinks(amendment, users_by_id, project_name):
  """Produce a list of value/url pairs for an Amendment PB.

  Args:
    amendment: Amendment PB to display.
    users_by_id: dict {user_id: user_view, ...} including all users
      mentioned in amendment.
    project_nme: Name of project the issue/comment/amendment is in.

  Returns:
    A list of dicts with 'value' and 'url' keys. 'url' may be None.
  """
  # Display both old and new summary, status
  if (amendment.field == tracker_pb2.FieldID.SUMMARY or
      amendment.field == tracker_pb2.FieldID.STATUS):
    result = amendment.newvalue
    oldValue = amendment.oldvalue;
    # Old issues have a 'NULL' string as the old value of the summary
    # or status fields. See crbug.com/monorail/3805
    if oldValue and oldValue != 'NULL':
      result += ' (was: %s)' % amendment.oldvalue
    return [{'value': result, 'url': None}]
  # Display new owner only
  elif amendment.field == tracker_pb2.FieldID.OWNER:
    if amendment.added_user_ids and amendment.added_user_ids[0]:
      uid = amendment.added_user_ids[0]
      return [{'value': users_by_id[uid].display_name, 'url': None}]
    return [{'value': framework_constants.NO_USER_NAME, 'url': None}]
  elif amendment.field in (tracker_pb2.FieldID.BLOCKEDON,
                           tracker_pb2.FieldID.BLOCKING,
                           tracker_pb2.FieldID.MERGEDINTO):
    values = amendment.newvalue.split()
    bug_refs = [_SafeParseIssueRef(v.strip()) for v in values]
    issue_urls = [FormatIssueURL(ref, default_project_name=project_name)
                  for ref in bug_refs]
    # TODO(jrobbins): Permission checks on referenced issues to allow
    # showing summary on hover.
    return [{'value': v, 'url': u} for (v, u) in zip(values, issue_urls)]
  elif amendment.newvalue:
    # Catchall for everything except user-valued fields.
    return [{'value': v, 'url': None} for v in amendment.newvalue.split()]
  else:
    # Applies to field==CC or CUSTOM with user type.
    values = _PlusMinusString(
        [users_by_id[uid].display_name for uid in amendment.added_user_ids
         if uid in users_by_id],
        [users_by_id[uid].display_name for uid in amendment.removed_user_ids
         if uid in users_by_id])
    return [{'value': v.strip(), 'url': None} for v in values.split()]


def GetAmendmentFieldName(amendment):
  """Get user-visible name for an amendment to a built-in or custom field."""
  if amendment.custom_field_name:
    return amendment.custom_field_name
  else:
    field_name = str(amendment.field)
    return field_name.capitalize()


def MakeDanglingIssueRef(project_name, issue_id, ext_id=''):
  """Create a DanglingIssueRef pb."""
  ret = tracker_pb2.DanglingIssueRef()
  ret.project = project_name
  ret.issue_id = issue_id
  ret.ext_issue_identifier = ext_id
  return ret


def FormatIssueURL(issue_ref_tuple, default_project_name=None):
  """Format an issue url from an issue ref."""
  if issue_ref_tuple is None:
    return ''
  project_name, local_id = issue_ref_tuple
  project_name = project_name or default_project_name
  url = framework_helpers.FormatURL(
    None, '/p/%s%s' % (project_name, urls.ISSUE_DETAIL), id=local_id)
  return url


def FormatIssueRef(issue_ref_tuple, default_project_name=None):
  """Format an issue reference for users: e.g., 123, or projectname:123."""
  if issue_ref_tuple is None:
    return ''

  # TODO(jeffcarp): Improve method signature to not require isinstance.
  if isinstance(issue_ref_tuple, tracker_pb2.DanglingIssueRef):
    return issue_ref_tuple.ext_issue_identifier or ''

  project_name, local_id = issue_ref_tuple
  if project_name and project_name != default_project_name:
    return '%s:%d' % (project_name, local_id)
  else:
    return str(local_id)


def ParseIssueRef(ref_str):
  """Parse an issue ref string: e.g., 123, or projectname:123 into a tuple.

  Raises ValueError if the ref string exists but can't be parsed.
  """
  if not ref_str.strip():
    return None

  if ':' in ref_str:
    project_name, id_str = ref_str.split(':', 1)
    project_name = project_name.strip().lstrip('-')
  else:
    project_name = None
    id_str = ref_str

  id_str = id_str.lstrip('-')

  return project_name, int(id_str)


def _SafeParseIssueRef(ref_str):
  """Same as ParseIssueRef, but catches ValueError and returns None instead."""
  try:
    return ParseIssueRef(ref_str)
  except ValueError:
    return None


def _MergeFields(field_values, fields_add, fields_remove, field_defs):
  """Merge the fields to add/remove into the current field values.

  Args:
    field_values: list of current FieldValue PBs.
    fields_add: list of FieldValue PBs to add to field_values.  If any of these
        is for a single-valued field, it replaces all previous values for the
        same field_id in field_values.
    fields_remove: list of FieldValues to remove from field_values, if found.
    field_defs: list of FieldDef PBs from the issue's project's config.

  Returns:
    A 3-tuple with the merged list of field values and {field_id: field_values}
    dict for the specific values that are added or removed.  The actual added
    or removed might be fewer than the requested ones if the issue already had
    one of the values-to-add or lacked one of the values-to-remove.
  """
  is_multi = {fd.field_id: fd.is_multivalued for fd in field_defs}
  merged_fvs = list(field_values)
  added_fvs_by_id = collections.defaultdict(list)
  for fv_consider in fields_add:
    consider_value = GetFieldValue(fv_consider, {})
    for old_fv in field_values:
      # Don't add fv_consider if field_values already contains consider_value
      if (fv_consider.field_id == old_fv.field_id and
          GetFieldValue(old_fv, {}) == consider_value and
          fv_consider.phase_id == old_fv.phase_id):
        break
    else:
      # Drop any existing values for non-multi fields.
      if not is_multi.get(fv_consider.field_id):
        if fv_consider.phase_id:
          # Drop existing phase fvs that belong to the same phase
          merged_fvs = [fv for fv in merged_fvs if
                        not (fv.field_id == fv_consider.field_id
                             and fv.phase_id == fv_consider.phase_id)]
        else:
          # Drop existing non-phase fvs
          merged_fvs = [fv for fv in merged_fvs if
                        not fv.field_id == fv_consider.field_id]
      added_fvs_by_id[fv_consider.field_id].append(fv_consider)
      merged_fvs.append(fv_consider)

  removed_fvs_by_id = collections.defaultdict(list)
  for fv_consider in fields_remove:
    consider_value = GetFieldValue(fv_consider, {})
    for old_fv in field_values:
      # Only remove fv_consider if field_values contains consider_value
      if (fv_consider.field_id == old_fv.field_id and
          GetFieldValue(old_fv, {}) == consider_value and
          fv_consider.phase_id == old_fv.phase_id):
        removed_fvs_by_id[fv_consider.field_id].append(fv_consider)
        merged_fvs.remove(old_fv)
  return merged_fvs, added_fvs_by_id, removed_fvs_by_id


def SplitBlockedOnRanks(issue, target_iid, split_above, open_iids):
  """Splits issue relation rankings by some target issue's rank

  Args:
    issue: Issue PB for the issue considered.
    target_iid: the global ID of the issue to split rankings about.
    split_above: False to split below the target issue, True to split above.
    open_iids: a list of global IDs of open and visible issues blocking
      the considered issue.

  Returns:
    A tuple (lower, higher) where both are lists of
    [(blocker_iid, rank),...] of issues in rank order. If split_above is False
    the target issue is included in higher, otherwise it is included in lower
  """
  issue_rank_pairs = [(dst_iid, rank)
      for (dst_iid, rank) in zip(issue.blocked_on_iids, issue.blocked_on_ranks)
      if dst_iid in open_iids]
  # blocked_on_iids is sorted high-to-low, we need low-to-high
  issue_rank_pairs.reverse()
  offset = int(split_above)
  for i, (dst_iid, _) in enumerate(issue_rank_pairs):
    if dst_iid == target_iid:
      return issue_rank_pairs[:i + offset], issue_rank_pairs[i + offset:]

  logging.error('Target issue %r was not found in blocked_on_iids of %r',
                target_iid, issue)
  return issue_rank_pairs, []
