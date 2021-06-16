# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from api import monorail_servicer
from api import converters
from api.api_proto import common_pb2
from api.api_proto import features_pb2
from api.api_proto import features_prpc_pb2
from businesslogic import work_env
from features import component_helpers
from features import features_bizobj
from framework import exceptions
from framework import framework_bizobj
from framework import framework_views
from framework import paginate
from framework import permissions
from services import features_svc
from tracker import tracker_bizobj


class FeaturesServicer(monorail_servicer.MonorailServicer):
  """Handle API requests related to Features objects.

  Each API request is implemented with a method as defined in the .proto
  file that does any request-specific validation, uses work_env to
  safely operate on business objects, and returns a response proto.
  """

  DESCRIPTION = features_prpc_pb2.FeaturesServiceDescription

  @monorail_servicer.PRPCMethod
  def ListHotlistsByUser(self, mc, request):
    """Return the hotlists for the given user."""
    user_id = converters.IngestUserRef(
        mc.cnxn, request.user, self.services.user)

    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      hotlists = we.ListHotlistsByUser(user_id)

    with mc.profiler.Phase('making user views'):
      users_involved = features_bizobj.UsersInvolvedInHotlists(hotlists)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    converted_hotlists = [
        converters.ConvertHotlist(hotlist, users_by_id)
        for hotlist in hotlists]

    result = features_pb2.ListHotlistsByUserResponse(
        hotlists=converted_hotlists)

    return result

  @monorail_servicer.PRPCMethod
  def ListHotlistsByIssue(self, mc, request):
    """Return the hotlists the given issue is part of."""
    issue_id = converters.IngestIssueRefs(
        mc.cnxn, [request.issue], self.services)[0]

    with work_env.WorkEnv(mc, self.services) as we:
      project = we.GetProjectByName(request.issue.project_name)
      mc.LookupLoggedInUserPerms(project)
      hotlists = we.ListHotlistsByIssue(issue_id)

    with mc.profiler.Phase('making user views'):
      users_involved = features_bizobj.UsersInvolvedInHotlists(hotlists)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    converted_hotlists = [
        converters.ConvertHotlist(hotlist, users_by_id)
        for hotlist in hotlists]

    result = features_pb2.ListHotlistsByIssueResponse(
        hotlists=converted_hotlists)

    return result

  @monorail_servicer.PRPCMethod
  def ListRecentlyVisitedHotlists(self, mc, _request):
    """Return the recently visited hotlists for the logged in user."""
    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      hotlists = we.ListRecentlyVisitedHotlists()

    with mc.profiler.Phase('making user views'):
      users_involved = features_bizobj.UsersInvolvedInHotlists(hotlists)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    converted_hotlists = [
        converters.ConvertHotlist(hotlist, users_by_id)
        for hotlist in hotlists]

    result = features_pb2.ListRecentlyVisitedHotlistsResponse(
        hotlists=converted_hotlists)

    return result

  @monorail_servicer.PRPCMethod
  def ListStarredHotlists(self, mc, _request):
    """Return the starred hotlists for the logged in user."""
    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      hotlists = we.ListStarredHotlists()

    with mc.profiler.Phase('maknig user views'):
      users_involved = features_bizobj.UsersInvolvedInHotlists(hotlists)
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    converted_hotlists = [
        converters.ConvertHotlist(hotlist, users_by_id)
        for hotlist in hotlists]

    result = features_pb2.ListStarredHotlistsResponse(
        hotlists=converted_hotlists)

    return result

  @monorail_servicer.PRPCMethod
  def GetHotlistStarCount(self, mc, request):
    """Get the star count for the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      star_count = we.GetHotlistStarCount(hotlist_id)

    result = features_pb2.GetHotlistStarCountResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def StarHotlist(self, mc, request):
    """Star the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      we.StarHotlist(hotlist_id, request.starred)
      star_count = we.GetHotlistStarCount(hotlist_id)

    result = features_pb2.StarHotlistResponse(star_count=star_count)
    return result

  @monorail_servicer.PRPCMethod
  def GetHotlist(self, mc, request):
    """Get the Hotlist metadata for the specified hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      hotlist = we.GetHotlist(hotlist_id)

    with mc.profiler.Phase('making user views'):
      users_involved = features_bizobj.UsersInvolvedInHotlists([hotlist])
      users_by_id = framework_views.MakeAllUserViews(
          mc.cnxn, self.services.user, users_involved)
      framework_views.RevealAllEmailsToMembers(mc.auth, None, users_by_id)

    converted_hotlist = converters.ConvertHotlist(hotlist, users_by_id)
    return features_pb2.GetHotlistResponse(hotlist=converted_hotlist)

  @monorail_servicer.PRPCMethod
  def CreateHotlist(self, mc, request):
    """Create a new hotlist."""
    editor_ids = converters.IngestUserRefs(
        mc.cnxn, request.editor_refs, self.services.user)
    issue_ids = converters.IngestIssueRefs(
        mc.cnxn, request.issue_refs, self.services)

    with work_env.WorkEnv(mc, self.services) as we:
      we.CreateHotlist(
          request.name, request.summary, request.description, editor_ids,
          issue_ids, request.is_private, '')

    result = features_pb2.CreateHotlistResponse()
    return result

  @monorail_servicer.PRPCMethod
  def CheckHotlistName(self, mc, request):
    """Check that a hotlist name is valid and not already in use."""
    with work_env.WorkEnv(mc, self.services) as we:
      error = we.CheckHotlistName(request.name)
    result = features_pb2.CheckHotlistNameResponse(error=error)
    return result

  @monorail_servicer.PRPCMethod
  def RemoveIssuesFromHotlists(self, mc, request):
    """Remove the given issues from the given hotlists."""
    hotlist_ids = converters.IngestHotlistRefs(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_refs)
    issue_ids = converters.IngestIssueRefs(
        mc.cnxn, request.issue_refs, self.services)

    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      we.RemoveIssuesFromHotlists(hotlist_ids, issue_ids)

    result = features_pb2.RemoveIssuesFromHotlistsResponse()
    return result

  @monorail_servicer.PRPCMethod
  def AddIssuesToHotlists(self, mc, request):
    """Add the given issues to the given hotlists."""
    hotlist_ids = converters.IngestHotlistRefs(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_refs)
    issue_ids = converters.IngestIssueRefs(
        mc.cnxn, request.issue_refs, self.services)

    with work_env.WorkEnv(mc, self.services) as we:
      mc.LookupLoggedInUserPerms(None)
      we.AddIssuesToHotlists(hotlist_ids, issue_ids, request.note)

    result = features_pb2.AddIssuesToHotlistsResponse()
    return result

  @monorail_servicer.PRPCMethod
  def RerankHotlistIssues(self, mc, request):
    """Rerank issues in the given hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)
    moved_issue_ids = converters.IngestIssueRefs(
        mc.cnxn, request.moved_refs, self.services)
    [target_issue_id] = converters.IngestIssueRefs(
        mc.cnxn, [request.target_ref], self.services)

    with work_env.WorkEnv(mc, self.services) as we:
      we.RerankHotlistIssues(
          hotlist_id, moved_issue_ids, target_issue_id, request.split_above)

    # TODO(jojwang): return updated hotlist items.
    with mc.profiler.Phase('converting to response objects'):
      result = features_pb2.RerankHotlistIssuesResponse()

    return result

  @monorail_servicer.PRPCMethod
  def UpdateHotlistIssueNote(self, mc, request):
    """Update the note for the given issue in the given hotlist."""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)
    issue_id = converters.IngestIssueRefs(
        mc.cnxn, [request.issue_ref], self.services)[0]

    with work_env.WorkEnv(mc, self.services) as we:
      project = we.GetProjectByName(request.issue_ref.project_name)
      mc.LookupLoggedInUserPerms(project)
      we.UpdateHotlistIssueNote(hotlist_id, issue_id, request.note)

    result = features_pb2.UpdateHotlistIssueNoteResponse()
    return result

  @monorail_servicer.PRPCMethod
  def DeleteHotlist(self, mc, request):
    """Delete the given hotlist"""
    hotlist_id = converters.IngestHotlistRef(
        mc.cnxn, self.services.user, self.services.features,
        request.hotlist_ref)

    with work_env.WorkEnv(mc, self.services) as we:
      we.DeleteHotlist(hotlist_id)

    return features_pb2.DeleteHotlistResponse()

  @monorail_servicer.PRPCMethod
  def PredictComponent(self, mc, request):
    """Predict the component of an issue based on the given text."""
    with work_env.WorkEnv(mc, self.services) as we:
      project = we.GetProjectByName(request.project_name)
      config = we.GetProjectConfig(project.project_id)

    component_ref = None
    component_id = component_helpers.PredictComponent(request.text, config)

    if component_id:
      component_ref = converters.ConvertComponentRef(component_id, config)

    result = features_pb2.PredictComponentResponse(component_ref=component_ref)
    return result
