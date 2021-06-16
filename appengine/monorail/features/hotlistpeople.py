# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to implement the hotlistpeople page and related forms."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import time

from third_party import ezt

from features import hotlist_helpers
from features import hotlist_views
from framework import framework_helpers
from framework import framework_views
from framework import paginate
from framework import permissions
from framework import servlet
from framework import urls
from project import project_helpers

MEMBERS_PER_PAGE = 50


class HotlistPeopleList(servlet.Servlet):
  _PAGE_TEMPLATE = 'project/people-list-page.ezt'
  # Note: using the project's peoplelist page template. minor edits were
  # to make it compatible with HotlistPeopleList
  _MAIN_TAB_MODE = servlet.Servlet.HOTLIST_TAB_PEOPLE

  def AssertBasePermission(self, mr):
    super(HotlistPeopleList, self).AssertBasePermission(mr)
    if not permissions.CanViewHotlist(
        mr.auth.effective_ids, mr.perms, mr.hotlist):
      raise permissions.PermissionException(
          'User is now allowed to view the hotlist people list')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    if mr.auth.user_id:
      self.services.user.AddVisitedHotlist(
          mr.cnxn, mr.auth.user_id, mr.hotlist_id)

    all_members = (mr.hotlist.owner_ids +
                   mr.hotlist.editor_ids + mr.hotlist.follower_ids)

    hotlist_url = hotlist_helpers.GetURLOfHotlist(
        mr.cnxn, mr.hotlist, self.services.user)

    with mr.profiler.Phase('gathering members on this page'):
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user, all_members)
      framework_views.RevealAllEmailsToMembers(mr.auth, mr.project, users_by_id)

    untrusted_user_group_proxies = []
    # TODO(jojwang): implement FindUntrustedGroups()

    with mr.profiler.Phase('making member views'):
      owner_views = self._MakeMemberViews(mr, mr.hotlist.owner_ids, users_by_id)
      editor_views = self._MakeMemberViews(mr, mr.hotlist.editor_ids,
                                           users_by_id)
      follower_views = self._MakeMemberViews(mr, mr.hotlist.follower_ids,
                                             users_by_id)
      all_member_views = owner_views + editor_views + follower_views

    url_params = [(name, mr.GetParam(name)) for name in
                  framework_helpers.RECOGNIZED_PARAMS]
    # We are passing in None for the project_name because we are not operating
    # under any project.
    pagination = paginate.ArtifactPagination(
        all_member_views, mr.GetPositiveIntParam('num', MEMBERS_PER_PAGE),
        mr.GetPositiveIntParam('start'), None,
        '%s%s' % (hotlist_url, urls.HOTLIST_PEOPLE), url_params=url_params)

    offer_membership_editing = permissions.CanAdministerHotlist(
        mr.auth.effective_ids, mr.perms, mr.hotlist)

    offer_remove_self = (
        not offer_membership_editing and
        mr.auth.user_id and
        mr.auth.user_id in mr.hotlist.editor_ids)

    newly_added_views = [mv for mv in all_member_views
                         if str(mv.user.user_id) in mr.GetParam('new', [])]

    return {
        'is_hotlist': ezt.boolean(True),
        'untrusted_user_groups': untrusted_user_group_proxies,
        'pagination': pagination,
        'initial_add_members': '',
        'subtab_mode': None,
        'initially_expand_form': ezt.boolean(False),
        'newly_added_views': newly_added_views,
        'offer_membership_editing': ezt.boolean(offer_membership_editing),
        'offer_remove_self': ezt.boolean(offer_remove_self),
        'total_num_owners': len(mr.hotlist.owner_ids),
        'check_abandonment': ezt.boolean(True),
        'initial_new_owner_username': '',
        'placeholder': 'new-owner-username',
        'open_dialog': ezt.boolean(False),
        'viewing_user_page': ezt.boolean(True),
        'new_ui_url': '%s/%s/people' % (urls.HOTLISTS, mr.hotlist_id),
    }

  def ProcessFormData(self, mr, post_data):
    """Process the posted form."""
    permit_edit = permissions.CanAdministerHotlist(
        mr.auth.effective_ids, mr.perms, mr.hotlist)
    can_remove_self = (
        not permit_edit and
        mr.auth.user_id and
        mr.auth.user_id in mr.hotlist.editor_ids)
    if not can_remove_self and not permit_edit:
      raise permissions.PermissionException(
          'User is not permitted to edit hotlist membership')
    hotlist_url = hotlist_helpers.GetURLOfHotlist(
        mr.cnxn, mr.hotlist, self.services.user)
    if permit_edit:
      if 'addbtn' in post_data:
        return self.ProcessAddMembers(mr, post_data, hotlist_url)
      elif 'removebtn' in post_data:
        return self.ProcessRemoveMembers(mr, post_data, hotlist_url)
      elif 'changeowners' in post_data:
        return self.ProcessChangeOwnership(mr, post_data)
    if can_remove_self:
      if 'removeself' in post_data:
        return self.ProcessRemoveSelf(mr, hotlist_url)

  def _MakeMemberViews(self, mr, member_ids, users_by_id):
    """Return a sorted list of MemberViews for display by EZT."""
    member_views = [hotlist_views.MemberView(
        mr.auth.user_id, member_id, users_by_id[member_id],
        mr.hotlist) for member_id in member_ids]
    member_views.sort(key=lambda mv: mv.user.email)
    return member_views

  def ProcessChangeOwnership(self, mr, post_data):
    new_owner_id_set = project_helpers.ParseUsernames(
        mr.cnxn, self.services.user, post_data.get('changeowners'))
    remain_as_editor = post_data.get('becomeeditor') == 'on'
    if len(new_owner_id_set) != 1:
      mr.errors.transfer_ownership = (
          'Please add one valid user email.')
    else:
      new_owner_id = new_owner_id_set.pop()
      if self.services.features.LookupHotlistIDs(
          mr.cnxn, [mr.hotlist.name], [new_owner_id]):
        mr.errors.transfer_ownership = (
            'This user already owns a hotlist with the same name')

    if mr.errors.AnyErrors():
      self.PleaseCorrect(
          mr, initial_new_owner_username=post_data.get('changeowners'),
          open_dialog=ezt.boolean(True))
    else:
      old_and_new_owner_ids = [new_owner_id] + mr.hotlist.owner_ids
      (_, editor_ids, follower_ids) = hotlist_helpers.MembersWithoutGivenIDs(
          mr.hotlist, old_and_new_owner_ids)
      if remain_as_editor and mr.hotlist.owner_ids:
        editor_ids.append(mr.hotlist.owner_ids[0])

      self.services.features.UpdateHotlistRoles(
          mr.cnxn, mr.hotlist_id, [new_owner_id], editor_ids, follower_ids)

      hotlist = self.services.features.GetHotlist(mr.cnxn, mr.hotlist_id)
      hotlist_url = hotlist_helpers.GetURLOfHotlist(
        mr.cnxn, hotlist, self.services.user)
      return framework_helpers.FormatAbsoluteURL(
          mr,'%s%s' % (hotlist_url, urls.HOTLIST_PEOPLE),
          saved=1, ts=int(time.time()),
          include_project=False)

  def ProcessAddMembers(self, mr, post_data, hotlist_url):
    """Process the user's request to add members.

    Args:
      mr: common information parsed from the HTTP request.
      post_data: dictionary of form data
      hotlist_url: hotlist_url to return to after data has been processed.

    Returns:
      String URL to redirect the user to after processing
    """
    # NOTE: using project_helpers function
    new_member_ids = project_helpers.ParseUsernames(
        mr.cnxn, self.services.user, post_data.get('addmembers'))
    if not new_member_ids or not post_data.get('addmembers'):
      mr.errors.incorrect_email_input = (
          'Please give full emails seperated by commas.')
    role = post_data['role']

    (owner_ids, editor_ids, follower_ids) = hotlist_helpers.MembersWithGivenIDs(
        mr.hotlist, new_member_ids, role)
    # TODO(jojwang): implement MAX_HOTLIST_PEOPLE

    if not owner_ids:
      mr.errors.addmembers = (
          'Cannot have a hotlist without an owner; please leave at least one.')

    if mr.errors.AnyErrors():
      add_members_str = post_data.get('addmembers', '')
      self.PleaseCorrect(
          mr, initial_add_members=add_members_str, initially_expand_form=True)
    else:
      self.services.features.UpdateHotlistRoles(
          mr.cnxn, mr.hotlist_id, owner_ids, editor_ids, follower_ids)
      return framework_helpers.FormatAbsoluteURL(
          mr, '%s%s' % (
              hotlist_url, urls.HOTLIST_PEOPLE),
          saved=1, ts=int(time.time()),
          new=','.join([str(u) for u in new_member_ids]),
          include_project=False)

  def ProcessRemoveMembers(self, mr, post_data, hotlist_url):
    """Process the user's request to remove members."""
    remove_strs = post_data.getall('remove')
    logging.info('remove_strs = %r', remove_strs)
    remove_ids = set(
        self.services.user.LookupUserIDs(mr.cnxn, remove_strs).values())
    (owner_ids, editor_ids,
     follower_ids) = hotlist_helpers.MembersWithoutGivenIDs(
         mr.hotlist, remove_ids)

    self.services.features.UpdateHotlistRoles(
        mr.cnxn, mr.hotlist_id, owner_ids, editor_ids, follower_ids)

    return framework_helpers.FormatAbsoluteURL(
        mr, '%s%s' % (
              hotlist_url, urls.HOTLIST_PEOPLE),
          saved=1, ts=int(time.time()), include_project=False)

  def ProcessRemoveSelf(self, mr, hotlist_url):
    """Process the request to remove the logged-in user."""
    remove_ids = [mr.auth.user_id]

    # This function does no permission checking; that's done by the caller.
    (owner_ids, editor_ids,
        follower_ids) = hotlist_helpers.MembersWithoutGivenIDs(
            mr.hotlist, remove_ids)

    self.services.features.UpdateHotlistRoles(
        mr.cnxn, mr.hotlist_id, owner_ids, editor_ids, follower_ids)

    return framework_helpers.FormatAbsoluteURL(
        mr, '%s%s' % (
              hotlist_url, urls.HOTLIST_PEOPLE),
          saved=1, ts=int(time.time()), include_project=False)
