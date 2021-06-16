# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class that provides persistence for Monorail's additional features.

Business objects are described in tracker_pb2.py, features_pb2.py, and
tracker_bizobj.py.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging
import re
import time

import settings

from features import features_constants
from features import filterrules_helpers
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import sql
from proto import features_pb2
from services import caches
from services import config_svc
from tracker import tracker_bizobj
from tracker import tracker_constants

QUICKEDITHISTORY_TABLE_NAME = 'QuickEditHistory'
QUICKEDITMOSTRECENT_TABLE_NAME = 'QuickEditMostRecent'
SAVEDQUERY_TABLE_NAME = 'SavedQuery'
PROJECT2SAVEDQUERY_TABLE_NAME = 'Project2SavedQuery'
SAVEDQUERYEXECUTESINPROJECT_TABLE_NAME = 'SavedQueryExecutesInProject'
USER2SAVEDQUERY_TABLE_NAME = 'User2SavedQuery'
FILTERRULE_TABLE_NAME = 'FilterRule'
HOTLIST_TABLE_NAME = 'Hotlist'
HOTLIST2ISSUE_TABLE_NAME = 'Hotlist2Issue'
HOTLIST2USER_TABLE_NAME = 'Hotlist2User'


QUICKEDITHISTORY_COLS = [
    'user_id', 'project_id', 'slot_num', 'command', 'comment']
QUICKEDITMOSTRECENT_COLS = ['user_id', 'project_id', 'slot_num']
SAVEDQUERY_COLS = ['id', 'name', 'base_query_id', 'query']
PROJECT2SAVEDQUERY_COLS = ['project_id', 'rank', 'query_id']
SAVEDQUERYEXECUTESINPROJECT_COLS = ['query_id', 'project_id']
USER2SAVEDQUERY_COLS = ['user_id', 'rank', 'query_id', 'subscription_mode']
FILTERRULE_COLS = ['project_id', 'rank', 'predicate', 'consequence']
HOTLIST_COLS = [
    'id', 'name', 'summary', 'description', 'is_private', 'default_col_spec']
HOTLIST_ABBR_COLS = ['id', 'name', 'summary', 'is_private']
HOTLIST2ISSUE_COLS = [
    'hotlist_id', 'issue_id', 'rank', 'adder_id', 'added', 'note']
HOTLIST2USER_COLS = ['hotlist_id', 'user_id', 'role_name']


# Regex for parsing one action in the filter rule consequence storage syntax.
CONSEQUENCE_RE = re.compile(
    r'(default_status:(?P<default_status>[-.\w]+))|'
    r'(default_owner_id:(?P<default_owner_id>\d+))|'
    r'(add_cc_id:(?P<add_cc_id>\d+))|'
    r'(add_label:(?P<add_label>[-.\w]+))|'
    r'(add_notify:(?P<add_notify>[-.@\w]+))|'
    r'(warning:(?P<warning>.+))|'  # Warnings consume the rest of the string.
    r'(error:(?P<error>.+))'  # Errors consume the rest of the string.
    )

class HotlistTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage both RAM and memcache for Hotlist PBs."""

  def __init__(self, cachemanager, features_service):
    super(HotlistTwoLevelCache, self).__init__(
        cachemanager, 'hotlist', 'hotlist:', features_pb2.Hotlist)
    self.features_service = features_service

  def _DeserializeHotlists(
      self, hotlist_rows, issue_rows, role_rows):
    """Convert database rows into a dictionary of Hotlist PB keyed by ID.

    Args:
      hotlist_rows: a list of hotlist rows from HOTLIST_TABLE_NAME.
      issue_rows: a list of issue rows from HOTLIST2ISSUE_TABLE_NAME,
        ordered by rank DESC, issue_id.
      role_rows: a list of role rows from HOTLIST2USER_TABLE_NAME.

    Returns:
      a dict mapping hotlist_id to hotlist PB"""
    hotlist_dict = {}

    for hotlist_row in hotlist_rows:
      (hotlist_id, hotlist_name, summary, description, is_private,
       default_col_spec) = hotlist_row
      hotlist = features_pb2.MakeHotlist(
          hotlist_name, hotlist_id=hotlist_id, summary=summary,
          description=description, is_private=bool(is_private),
          default_col_spec=default_col_spec)
      hotlist_dict[hotlist_id] = hotlist

    for (hotlist_id, issue_id, rank, adder_id, added, note) in issue_rows:
      hotlist = hotlist_dict.get(hotlist_id)
      if hotlist:
        hotlist.items.append(
            features_pb2.MakeHotlistItem(issue_id=issue_id, rank=rank,
                                         adder_id=adder_id , date_added=added,
                                         note=note))
      else:
        logging.warn('hotlist %d not found', hotlist_id)

    for (hotlist_id, user_id, role_name) in role_rows:
      hotlist = hotlist_dict.get(hotlist_id)
      if not hotlist:
        logging.warn('hotlist %d not found', hotlist_id)
      elif role_name == 'owner':
        hotlist.owner_ids.append(user_id)
      elif role_name == 'editor':
        hotlist.editor_ids.append(user_id)
      elif role_name == 'follower':
        hotlist.follower_ids.append(user_id)
      else:
        logging.info('unknown role name %s', role_name)

    return hotlist_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database to get missing hotlists."""
    hotlist_rows = self.features_service.hotlist_tbl.Select(
        cnxn, cols=HOTLIST_COLS, is_deleted=False, id=keys)
    issue_rows = self.features_service.hotlist2issue_tbl.Select(
        cnxn, cols=HOTLIST2ISSUE_COLS, hotlist_id=keys,
        order_by=[('rank DESC', []), ('issue_id', [])])
    role_rows = self.features_service.hotlist2user_tbl.Select(
        cnxn, cols=HOTLIST2USER_COLS, hotlist_id=keys)
    retrieved_dict = self._DeserializeHotlists(
        hotlist_rows, issue_rows, role_rows)
    return retrieved_dict


class HotlistIDTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage both RAM and memcache for hotlist_ids.

     Keys for this cache are tuples (hotlist_name.lower(), owner_id).
     This cache should be used to fetch hotlist_ids owned by users or
     to check if a user owns a hotlist with a certain name, so the
     hotlist_names in keys will always be in lowercase.
  """

  def __init__(self, cachemanager, features_service):
    super(HotlistIDTwoLevelCache, self).__init__(
        cachemanager, 'hotlist_id', 'hotlist_id:', int,
        max_size=settings.issue_cache_max_size)
    self.features_service = features_service

  def _MakeCache(self, cache_manager, kind, max_size=None):
    """Override normal RamCache creation with ValueCentricRamCache."""
    return caches.ValueCentricRamCache(cache_manager, kind, max_size=max_size)

  def _KeyToStr(self, key):
    """This cache uses pairs of (str, int) as keys. Convert them to strings."""
    return '%s,%d' % key

  def _StrToKey(self, key_str):
    """This cache uses pairs of (str, int) as keys.
       Convert them from strings.
    """
    hotlist_name_str, owner_id_str = key_str.split(',')
    return (hotlist_name_str, int(owner_id_str))

  def _DeserializeHotlistIDs(
      self, hotlist_rows, owner_rows, wanted_names_for_owners):
    """Convert database rows into a dictionary of hotlist_ids keyed by (
       hotlist_name, owner_id).

    Args:
      hotlist_rows: a list of hotlist rows [id, name] from HOTLIST for
        with names we are interested in.
      owner_rows: a list of role rows [hotlist_id, uwer_id] from HOTLIST2USER
        for owners that we are interested in that own hotlists with names that
        we are interested in.
      wanted_names_for_owners: a dict of
        {owner_id: [hotlist_name.lower(), ...], ...}
        so we know which (hotlist_name, owner_id) keys to return.

    Returns:
      A dict mapping (hotlist_name.lower(), owner_id) keys to hotlist_id values.
    """
    hotlist_ids_dict = {}
    if not hotlist_rows or not owner_rows:
      return hotlist_ids_dict

    hotlist_to_owner_id = {}

    # Note: owner_rows contains hotlist owners that we are interested in, but
    # may not own hotlists with names we are interested in.
    for (hotlist_id, user_id) in owner_rows:
      found_owner_id = hotlist_to_owner_id.get(hotlist_id)
      if found_owner_id:
        logging.warn(
            'hotlist %d has more than one owner: %d, %d',
            hotlist_id, user_id, found_owner_id)
      hotlist_to_owner_id[hotlist_id] = user_id

    # Note: hotlist_rows hotlists found in the owner_rows that have names
    # we're interested in.
    # We use wanted_names_for_owners to filter out hotlists in hotlist_rows
    # that have a (hotlist_name, owner_id) pair we are not interested in.
    for (hotlist_id, hotlist_name) in hotlist_rows:
      owner_id = hotlist_to_owner_id.get(hotlist_id)
      if owner_id:
        if hotlist_name.lower() in wanted_names_for_owners.get(owner_id, []):
          hotlist_ids_dict[(hotlist_name.lower(), owner_id)] = hotlist_id

    return hotlist_ids_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database."""
    hotlist_names, _owner_ids = zip(*keys)
    # Keys may contain [(name1, user1), (name1, user2)] so we cast this to
    # a set to make sure 'name1' is not repeated.
    hotlist_names_set = set(hotlist_names)
    # Pass this dict to _DeserializeHotlistIDs so it knows what hotlist names
    # we're interested in for each owner.
    wanted_names_for_owner = collections.defaultdict(list)
    for hotlist_name, owner_id in keys:
      wanted_names_for_owner[owner_id].append(hotlist_name.lower())

    role_rows = self.features_service.hotlist2user_tbl.Select(
        cnxn, cols=['hotlist_id', 'user_id'],
        user_id=wanted_names_for_owner.keys(), role_name='owner')

    hotlist_ids = [row[0] for row in role_rows]
    hotlist_rows = self.features_service.hotlist_tbl.Select(
        cnxn, cols=['id', 'name'], id=hotlist_ids, is_deleted=False,
        where=[('LOWER(name) IN (%s)' % sql.PlaceHolders(hotlist_names_set),
                [name.lower() for name in hotlist_names_set])])

    return self._DeserializeHotlistIDs(
        hotlist_rows, role_rows, wanted_names_for_owner)


class FeaturesService(object):
  """The persistence layer for servlets in the features directory."""

  def __init__(self, cache_manager, config_service):
    """Initialize this object so that it is ready to use.

    Args:
      cache_manager: local cache with distributed invalidation.
      config_service: an instance of ConfigService.
    """
    self.quickedithistory_tbl = sql.SQLTableManager(QUICKEDITHISTORY_TABLE_NAME)
    self.quickeditmostrecent_tbl = sql.SQLTableManager(
        QUICKEDITMOSTRECENT_TABLE_NAME)

    self.savedquery_tbl = sql.SQLTableManager(SAVEDQUERY_TABLE_NAME)
    self.project2savedquery_tbl = sql.SQLTableManager(
        PROJECT2SAVEDQUERY_TABLE_NAME)
    self.savedqueryexecutesinproject_tbl = sql.SQLTableManager(
        SAVEDQUERYEXECUTESINPROJECT_TABLE_NAME)
    self.user2savedquery_tbl = sql.SQLTableManager(USER2SAVEDQUERY_TABLE_NAME)

    self.filterrule_tbl = sql.SQLTableManager(FILTERRULE_TABLE_NAME)

    self.hotlist_tbl = sql.SQLTableManager(HOTLIST_TABLE_NAME)
    self.hotlist2issue_tbl = sql.SQLTableManager(HOTLIST2ISSUE_TABLE_NAME)
    self.hotlist2user_tbl = sql.SQLTableManager(HOTLIST2USER_TABLE_NAME)

    self.saved_query_cache = caches.RamCache(
        cache_manager, 'user', max_size=1000)
    self.canned_query_cache = caches.RamCache(
        cache_manager, 'project', max_size=1000)

    self.hotlist_2lc = HotlistTwoLevelCache(cache_manager, self)
    self.hotlist_id_2lc = HotlistIDTwoLevelCache(cache_manager, self)
    self.hotlist_user_to_ids = caches.RamCache(cache_manager, 'hotlist')

    self.config_service = config_service

  ### QuickEdit command history

  def GetRecentCommands(self, cnxn, user_id, project_id):
    """Return recent command items for the "Redo" menu.

    Args:
      cnxn: Connection to SQL database.
      user_id: int ID of the current user.
      project_id: int ID of the current project.

    Returns:
      A pair (cmd_slots, recent_slot_num).  cmd_slots is a list of
      3-tuples that can be used to populate the "Redo" menu of the
      quick-edit dialog.  recent_slot_num indicates which of those
      slots should initially populate the command and comment fields.
    """
    # Always start with the standard 5 commands.
    history = tracker_constants.DEFAULT_RECENT_COMMANDS[:]
    # If the user has modified any, then overwrite some standard ones.
    history_rows = self.quickedithistory_tbl.Select(
        cnxn, cols=['slot_num', 'command', 'comment'],
        user_id=user_id, project_id=project_id)
    for slot_num, command, comment in history_rows:
      if slot_num < len(history):
        history[slot_num - 1] = (command, comment)

    slots = []
    for idx, (command, comment) in enumerate(history):
      slots.append((idx + 1, command, comment))

    recent_slot_num = self.quickeditmostrecent_tbl.SelectValue(
        cnxn, 'slot_num', default=1, user_id=user_id, project_id=project_id)

    return slots, recent_slot_num

  def StoreRecentCommand(
      self, cnxn, user_id, project_id, slot_num, command, comment):
    """Store the given command and comment in the user's command history."""
    self.quickedithistory_tbl.InsertRow(
        cnxn, replace=True, user_id=user_id, project_id=project_id,
        slot_num=slot_num, command=command, comment=comment)
    self.quickeditmostrecent_tbl.InsertRow(
        cnxn, replace=True, user_id=user_id, project_id=project_id,
        slot_num=slot_num)

  def ExpungeQuickEditHistory(self, cnxn, project_id):
    """Completely delete every users' quick edit history for this project."""
    self.quickeditmostrecent_tbl.Delete(cnxn, project_id=project_id)
    self.quickedithistory_tbl.Delete(cnxn, project_id=project_id)

  def ExpungeQuickEditsByUsers(self, cnxn, user_ids, limit=None):
    """Completely delete every given users' quick edits.

    This method will not commit the operations. This method will
    not make changes to in-memory data.
    """
    commit = False
    self.quickeditmostrecent_tbl.Delete(
        cnxn, user_id=user_ids, commit=commit, limit=limit)
    self.quickedithistory_tbl.Delete(
        cnxn, user_id=user_ids, commit=commit, limit=limit)

  ### Saved User and Project Queries

  def GetSavedQueries(self, cnxn, query_ids):
    """Retrieve the specified SaveQuery PBs."""
    # TODO(jrobbins): RAM cache
    saved_queries = {}
    savedquery_rows = self.savedquery_tbl.Select(
        cnxn, cols=SAVEDQUERY_COLS, id=query_ids)
    for saved_query_tuple in savedquery_rows:
      qid, name, base_id, query = saved_query_tuple
      saved_queries[qid] = tracker_bizobj.MakeSavedQuery(
          qid, name, base_id, query)

    sqeip_rows = self.savedqueryexecutesinproject_tbl.Select(
        cnxn, cols=SAVEDQUERYEXECUTESINPROJECT_COLS,
        query_id=query_ids)
    for query_id, project_id in sqeip_rows:
      saved_queries[query_id].executes_in_project_ids.append(project_id)

    return saved_queries

  def GetSavedQuery(self, cnxn, query_id):
    """Retrieve the specified SaveQuery PB."""
    saved_queries = self.GetSavedQueries(cnxn, [query_id])
    return saved_queries.get(query_id)

  def _GetUsersSavedQueriesDict(self, cnxn, user_ids):
    """Return a dict of all SavedQuery PBs for the specified users."""
    results_dict, missed_uids = self.saved_query_cache.GetAll(user_ids)

    if missed_uids:
      savedquery_rows = self.user2savedquery_tbl.Select(
          cnxn, cols=SAVEDQUERY_COLS + ['user_id', 'subscription_mode'],
          left_joins=[('SavedQuery ON query_id = id', [])],
          order_by=[('rank', [])], user_id=missed_uids)
      sqeip_rows = self.savedqueryexecutesinproject_tbl.Select(
          cnxn, cols=SAVEDQUERYEXECUTESINPROJECT_COLS,
          query_id={row[0] for row in savedquery_rows})
      sqeip_dict = {}
      for qid, pid in sqeip_rows:
        sqeip_dict.setdefault(qid, []).append(pid)

      for saved_query_tuple in savedquery_rows:
        query_id, name, base_id, query, uid, sub_mode = saved_query_tuple
        sq = tracker_bizobj.MakeSavedQuery(
            query_id, name, base_id, query, subscription_mode=sub_mode,
            executes_in_project_ids=sqeip_dict.get(query_id, []))
        results_dict.setdefault(uid, []).append(sq)

    self.saved_query_cache.CacheAll(results_dict)
    return results_dict

  # TODO(jrobbins): change this termonology to "canned query" rather than
  # "saved" throughout the application.
  def GetSavedQueriesByUserID(self, cnxn, user_id):
    """Return a list of SavedQuery PBs for the specified user."""
    saved_queries_dict = self._GetUsersSavedQueriesDict(cnxn, [user_id])
    saved_queries = saved_queries_dict.get(user_id, [])
    return saved_queries[:]

  def GetCannedQueriesForProjects(self, cnxn, project_ids):
    """Return a dict {project_id: [saved_query]} for the specified projects."""
    results_dict, missed_pids = self.canned_query_cache.GetAll(project_ids)

    if missed_pids:
      cannedquery_rows = self.project2savedquery_tbl.Select(
          cnxn, cols=['project_id'] + SAVEDQUERY_COLS,
          left_joins=[('SavedQuery ON query_id = id', [])],
          order_by=[('rank', [])], project_id=project_ids)

      for cq_row in cannedquery_rows:
        project_id = cq_row[0]
        canned_query_tuple = cq_row[1:]
        results_dict.setdefault(project_id ,[]).append(
            tracker_bizobj.MakeSavedQuery(*canned_query_tuple))

    self.canned_query_cache.CacheAll(results_dict)
    return results_dict

  def GetCannedQueriesByProjectID(self, cnxn, project_id):
    """Return the list of SavedQueries for the specified project."""
    project_ids_to_canned_queries = self.GetCannedQueriesForProjects(
        cnxn, [project_id])
    return project_ids_to_canned_queries.get(project_id, [])

  def _UpdateSavedQueries(self, cnxn, saved_queries, commit=True):
    """Store the given SavedQueries to the DB."""
    savedquery_rows = [
        (sq.query_id or None, sq.name, sq.base_query_id, sq.query)
        for sq in saved_queries]
    existing_query_ids = [sq.query_id for sq in saved_queries if sq.query_id]
    if existing_query_ids:
      self.savedquery_tbl.Delete(cnxn, id=existing_query_ids, commit=commit)

    generated_ids = self.savedquery_tbl.InsertRows(
        cnxn, SAVEDQUERY_COLS, savedquery_rows, commit=commit,
        return_generated_ids=True)
    if generated_ids:
      logging.info('generated_ids are %r', generated_ids)
      for sq in saved_queries:
        generated_id = generated_ids.pop(0)
        if not sq.query_id:
          sq.query_id = generated_id

  def UpdateCannedQueries(self, cnxn, project_id, canned_queries):
    """Update the canned queries for a project.

    Args:
      cnxn: connection to SQL database.
      project_id: int project ID of the project that contains these queries.
      canned_queries: list of SavedQuery PBs to update.
    """
    self.project2savedquery_tbl.Delete(
        cnxn, project_id=project_id, commit=False)
    self._UpdateSavedQueries(cnxn, canned_queries, commit=False)
    project2savedquery_rows = [
        (project_id, rank, sq.query_id)
        for rank, sq in enumerate(canned_queries)]
    self.project2savedquery_tbl.InsertRows(
        cnxn, PROJECT2SAVEDQUERY_COLS, project2savedquery_rows,
        commit=False)
    cnxn.Commit()

    self.canned_query_cache.Invalidate(cnxn, project_id)

  def UpdateUserSavedQueries(self, cnxn, user_id, saved_queries):
    """Store the given saved_queries for the given user."""
    saved_query_ids = [sq.query_id for sq in saved_queries if sq.query_id]
    self.savedqueryexecutesinproject_tbl.Delete(
        cnxn, query_id=saved_query_ids, commit=False)
    self.user2savedquery_tbl.Delete(cnxn, user_id=user_id, commit=False)

    self._UpdateSavedQueries(cnxn, saved_queries, commit=False)
    user2savedquery_rows = []
    for rank, sq in enumerate(saved_queries):
      user2savedquery_rows.append(
          (user_id, rank, sq.query_id, sq.subscription_mode or 'noemail'))

    self.user2savedquery_tbl.InsertRows(
        cnxn, USER2SAVEDQUERY_COLS, user2savedquery_rows, commit=False)

    sqeip_rows = []
    for sq in saved_queries:
      for pid in sq.executes_in_project_ids:
        sqeip_rows.append((sq.query_id, pid))

    self.savedqueryexecutesinproject_tbl.InsertRows(
        cnxn, SAVEDQUERYEXECUTESINPROJECT_COLS, sqeip_rows, commit=False)
    cnxn.Commit()

    self.saved_query_cache.Invalidate(cnxn, user_id)

  ### Subscriptions

  def GetSubscriptionsInProjects(self, cnxn, project_ids):
    """Return all saved queries for users that have any subscription there.

    Args:
      cnxn: Connection to SQL database.
      project_ids: list of int project IDs that contain the modified issues.

    Returns:
      A dict {user_id: all_saved_queries, ...} for all users that have any
      subscription in any of the specified projects.
    """
    sqeip_join_str = (
        'SavedQueryExecutesInProject ON '
        'SavedQueryExecutesInProject.query_id = User2SavedQuery.query_id')
    user_join_str = (
        'User ON '
        'User.user_id = User2SavedQuery.user_id')
    now = int(time.time())
    absence_threshold = now - settings.subscription_timeout_secs
    where = [
        ('(User.banned IS NULL OR User.banned = %s)', ['']),
        ('User.last_visit_timestamp >= %s', [absence_threshold]),
        ('(User.email_bounce_timestamp IS NULL OR '
         'User.email_bounce_timestamp = %s)', [0]),
        ]
    # TODO(jrobbins): cache this since it rarely changes.
    subscriber_rows = self.user2savedquery_tbl.Select(
        cnxn, cols=['User2SavedQuery.user_id'], distinct=True,
        joins=[(sqeip_join_str, []), (user_join_str, [])],
        subscription_mode='immediate', project_id=project_ids,
        where=where)
    subscriber_ids = [row[0] for row in subscriber_rows]
    logging.info('subscribers relevant to projects %r are %r',
                 project_ids, subscriber_ids)
    user_ids_to_saved_queries = self._GetUsersSavedQueriesDict(
        cnxn, subscriber_ids)
    return user_ids_to_saved_queries

  def ExpungeSavedQueriesExecuteInProject(self, cnxn, project_id):
    """Remove any references from saved queries to projects in the database."""
    self.savedqueryexecutesinproject_tbl.Delete(cnxn, project_id=project_id)

    savedquery_rows = self.project2savedquery_tbl.Select(
        cnxn, cols=['query_id'], project_id=project_id)
    savedquery_ids = [row[0] for row in savedquery_rows]
    self.project2savedquery_tbl.Delete(cnxn, project_id=project_id)
    self.savedquery_tbl.Delete(cnxn, id=savedquery_ids)

  def ExpungeSavedQueriesByUsers(self, cnxn, user_ids, limit=None):
    """Completely delete every given users' saved queries.

    This method will not commit the operations. This method will
    not make changes to in-memory data.
    """
    commit = False
    savedquery_rows = self.user2savedquery_tbl.Select(
        cnxn, cols=['query_id'], user_id=user_ids, limit=limit)
    savedquery_ids = [row[0] for row in savedquery_rows]
    self.user2savedquery_tbl.Delete(
        cnxn, query_id=savedquery_ids, commit=commit)
    self.savedqueryexecutesinproject_tbl.Delete(
        cnxn, query_id=savedquery_ids, commit=commit)
    self.savedquery_tbl.Delete(cnxn, id=savedquery_ids, commit=commit)


  ### Filter rules

  def _DeserializeFilterRules(self, filterrule_rows):
    """Convert the given DB row tuples into PBs."""
    result_dict = collections.defaultdict(list)

    for filterrule_row in sorted(filterrule_rows):
      project_id, _rank, predicate, consequence = filterrule_row
      (default_status, default_owner_id, add_cc_ids, add_labels,
       add_notify, warning, error) = self._DeserializeRuleConsequence(
          consequence)
      rule = filterrules_helpers.MakeRule(
          predicate, default_status=default_status,
          default_owner_id=default_owner_id, add_cc_ids=add_cc_ids,
          add_labels=add_labels, add_notify=add_notify, warning=warning,
          error=error)
      result_dict[project_id].append(rule)

    return result_dict

  def _DeserializeRuleConsequence(self, consequence):
    """Decode the THEN-part of a filter rule."""
    (default_status, default_owner_id, add_cc_ids, add_labels,
     add_notify, warning, error) = None, None, [], [], [], None, None
    for match in CONSEQUENCE_RE.finditer(consequence):
      if match.group('default_status'):
        default_status = match.group('default_status')
      elif match.group('default_owner_id'):
        default_owner_id = int(match.group('default_owner_id'))
      elif match.group('add_cc_id'):
        add_cc_ids.append(int(match.group('add_cc_id')))
      elif match.group('add_label'):
        add_labels.append(match.group('add_label'))
      elif match.group('add_notify'):
        add_notify.append(match.group('add_notify'))
      elif match.group('warning'):
        warning = match.group('warning')
      elif match.group('error'):
        error = match.group('error')

    return (default_status, default_owner_id, add_cc_ids, add_labels,
            add_notify, warning, error)

  def _GetFilterRulesByProjectIDs(self, cnxn, project_ids):
    """Return {project_id: [FilterRule, ...]} for the specified projects."""
    # TODO(jrobbins): caching
    filterrule_rows = self.filterrule_tbl.Select(
        cnxn, cols=FILTERRULE_COLS, project_id=project_ids)
    return self._DeserializeFilterRules(filterrule_rows)

  def GetFilterRules(self, cnxn, project_id):
    """Return a list of FilterRule PBs for the specified project."""
    rules_by_project_id = self._GetFilterRulesByProjectIDs(cnxn, [project_id])
    return rules_by_project_id[project_id]

  def _SerializeRuleConsequence(self, rule):
    """Put all actions of a filter rule into one string."""
    assignments = []
    for add_lab in rule.add_labels:
      assignments.append('add_label:%s' % add_lab)
    if rule.default_status:
      assignments.append('default_status:%s' % rule.default_status)
    if rule.default_owner_id:
      assignments.append('default_owner_id:%d' % rule.default_owner_id)
    for add_cc_id in rule.add_cc_ids:
      assignments.append('add_cc_id:%d' % add_cc_id)
    for add_notify in rule.add_notify_addrs:
      assignments.append('add_notify:%s' % add_notify)
    if rule.warning:
      assignments.append('warning:%s' % rule.warning)
    if rule.error:
      assignments.append('error:%s' % rule.error)

    return ' '.join(assignments)

  def UpdateFilterRules(self, cnxn, project_id, rules):
    """Update the filter rules part of a project's issue configuration.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      rules: a list of FilterRule PBs.
    """
    rows = []
    for rank, rule in enumerate(rules):
      predicate = rule.predicate
      consequence = self._SerializeRuleConsequence(rule)
      if predicate and consequence:
        rows.append((project_id, rank, predicate, consequence))

    self.filterrule_tbl.Delete(cnxn, project_id=project_id)
    self.filterrule_tbl.InsertRows(cnxn, FILTERRULE_COLS, rows)

  def ExpungeFilterRules(self, cnxn, project_id):
    """Completely destroy filter rule info for the specified project."""
    self.filterrule_tbl.Delete(cnxn, project_id=project_id)

  def ExpungeFilterRulesByUser(self, cnxn, user_ids_by_email):
    """Wipes any Filter Rules containing the given users.

    This method will not commit the operation. This method will not make
    changes to in-memory data.
    Args:
      cnxn: connection to SQL database.
      user_ids_by_email: dict of {email: user_id ..} of all users we want to
        expunge

    Returns:
      Dictionary of {project_id: [(predicate, consequence), ..]} for Filter
      Rules that will be deleted for containing the given emails.
    """
    deleted_project_rules_dict = collections.defaultdict(list)
    if user_ids_by_email:
      deleted_rows = []
      emails = user_ids_by_email.keys()
      all_rules_rows = self.filterrule_tbl.Select(cnxn, FILTERRULE_COLS)
      logging.info('Fetched all filter rules: %s' % (all_rules_rows,))
      for rule_row in all_rules_rows:
        project_id, _rank, predicate, consequence = rule_row
        if any(email in predicate for email in emails):
          deleted_rows.append(rule_row)
          continue
        if any(
            (('add_notify:%s' % email) in consequence or
             ('add_cc_id:%s' % user_id) in consequence or
             ('default_owner_id:%s' % user_id) in consequence)
            for email, user_id in user_ids_by_email.iteritems()):
          deleted_rows.append(rule_row)
          continue

      for deleted_row in deleted_rows:
        project_id, rank, predicate, consequence = deleted_row
        self.filterrule_tbl.Delete(
            cnxn, project_id=project_id, rank=rank, predicate=predicate,
            consequence=consequence, commit=False)
      deleted_project_rules_dict = self._DeserializeFilterRules(deleted_rows)

    return deleted_project_rules_dict

  ### Creating hotlists

  def CreateHotlist(
      self, cnxn, name, summary, description, owner_ids, editor_ids,
      issue_ids=None, is_private=None, default_col_spec=None, ts=None):
    # type: (MonorailConnection, string, string, string, Collection[int],
    #     Optional[Collection[int]], Optional[Boolean], Optional[string],
    #     Optional[int] -> int
    """Create and store a Hotlist with the given attributes.

    Args:
      cnxn: connection to SQL database.
      name: a valid hotlist name.
      summary: one-line explanation of the hotlist.
      description: one-page explanation of the hotlist.
      owner_ids: a list of user IDs for the hotlist owners.
      editor_ids: a list of user IDs for the hotlist editors.
      issue_ids: a list of issue IDs for the hotlist issues.
      is_private: True if the hotlist can only be viewed by owners and editors.
      default_col_spec: the default columns that show in list view.
      ts: a timestamp for when this hotlist was created.

    Returns:
      The int id of the new hotlist.

    Raises:
      InputException: if the hotlist name is invalid.
      HotlistAlreadyExists: if any of the owners already own a hotlist with
        the same name.
      UnownedHotlistException: if owner_ids is empty.
    """
    # TODO(crbug.com/monorail/7677): These checks should be done in the
    # the business layer.
    # Remove when calls from non-business layer code are removed.
    if not owner_ids:  # Should never happen.
      logging.error('Attempt to create unowned Hotlist: name:%r', name)
      raise UnownedHotlistException()
    if not framework_bizobj.IsValidHotlistName(name):
      raise exceptions.InputException(
          '%s is not a valid name for a Hotlist' % name)
    if self.LookupHotlistIDs(cnxn, [name], owner_ids):
      raise HotlistAlreadyExists()
    # TODO(crbug.com/monorail/7677): We are not setting a
    # default default_col_spec in v3.
    if default_col_spec is None:
      default_col_spec = features_constants.DEFAULT_COL_SPEC

    hotlist_item_fields = [
        (issue_id, rank*100, owner_ids[0], ts, '') for
        rank, issue_id in enumerate(issue_ids or [])]
    hotlist = features_pb2.MakeHotlist(
        name, hotlist_item_fields=hotlist_item_fields, summary=summary,
        description=description, is_private=is_private, owner_ids=owner_ids,
        editor_ids=editor_ids, default_col_spec=default_col_spec)
    hotlist.hotlist_id = self._InsertHotlist(cnxn, hotlist)
    return hotlist

  def UpdateHotlist(
      self, cnxn, hotlist_id, name=None, summary=None, description=None,
      is_private=None, default_col_spec=None, owner_id=None,
      add_editor_ids=None):
    """Update the DB with the given hotlist information."""
    # Note: If something is None, it does not get changed to None,
    # it just does not get updated.
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    delta = {}
    if name is not None:
      delta['name'] = name
    if summary is not None:
      delta['summary'] = summary
    if description is not None:
      delta['description'] = description
    if is_private is not None:
      delta['is_private'] = is_private
    if default_col_spec is not None:
      delta['default_col_spec'] = default_col_spec

    self.hotlist_tbl.Update(cnxn, delta, id=hotlist_id, commit=False)
    insert_rows = []
    if owner_id is not None:
      insert_rows.append((hotlist_id, owner_id, 'owner'))
      self.hotlist2user_tbl.Delete(
          cnxn, hotlist_id=hotlist_id, role='owner', commit=False)
    if add_editor_ids:
      insert_rows.extend(
          [(hotlist_id, user_id, 'editor') for user_id in add_editor_ids])
    if insert_rows:
      self.hotlist2user_tbl.InsertRows(
          cnxn, HOTLIST2USER_COLS, insert_rows, commit=False)

    cnxn.Commit()

    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])
    if not hotlist.owner_ids:  # Should never happen.
      logging.warn('Modifying unowned Hotlist: id:%r, name:%r',
        hotlist_id, hotlist.name)
    elif hotlist.name:
      self.hotlist_id_2lc.InvalidateKeys(
          cnxn, [(hotlist.name.lower(), owner_id) for
                 owner_id in hotlist.owner_ids])

    # Update the hotlist PB in RAM
    if name is not None:
      hotlist.name = name
    if summary is not None:
      hotlist.summary = summary
    if description is not None:
      hotlist.description = description
    if is_private is not None:
      hotlist.is_private = is_private
    if default_col_spec is not None:
      hotlist.default_col_spec = default_col_spec
    if owner_id is not None:
      hotlist.owner_ids = [owner_id]
    if add_editor_ids:
      hotlist.editor_ids.extend(add_editor_ids)

  def RemoveHotlistEditors(self, cnxn, hotlist_id, remove_editor_ids):
    # type: MonorailConnection, int, Collection[int]
    """Remove given editors from the specified hotlist.

    Args:
      cnxn: MonorailConnection object.
      hotlist_id: int ID of the Hotlist we want to update.
      remove_editor_ids: collection of existing hotlist editor User IDs
        that we want to remove from the hotlist.

    Raises:
      NoSuchHotlistException: if the hotlist is not found.
      InputException: if there are not editors to remove.
    """
    if not remove_editor_ids:
      raise exceptions.InputException
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    self.hotlist2user_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, user_id=remove_editor_ids)
    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])

    # Update in-memory data
    for remove_id in remove_editor_ids:
      hotlist.editor_ids.remove(remove_id)

  def UpdateHotlistIssues(
      self,
      cnxn,  # type: sql.MonorailConnection
      hotlist_id,  # type: int
      updated_items,  # type: Collection[features_pb2.HotlistItem]
      remove_issue_ids,  # type: Collection[int]
      issue_svc,  # type: issue_svc.IssueService
      chart_svc,  # type: chart_svc.ChartService
      commit=True  # type: Optional[bool]
  ):
    # type: (...) -> None
    """Update the Issues in a Hotlist.
       This method removes the given remove_issue_ids from a Hotlist then
       updates or adds the HotlistItems found in updated_items. HotlistItems
       in updated_items may exist in the hotlist and just need to be updated
       or they may be new items that should be added to the Hotlist.

    Args:
      cnxn: MonorailConnection object.
      hotlist_id: int ID of the Hotlist to update.
      updated_items: Collection of HotlistItems that either already exist in
        the hotlist and need to be updated or needed to be added to the hotlist.
      remove_issue_ids: Collection of Issue IDs that should be removed from the
        hotlist.
      issue_svc: IssueService object.
      chart_svc: ChartService object.

    Raises:
      NoSuchHotlistException if a hotlist with the given ID is not found.
      InputException if no changes were given.
    """
    if not updated_items and not remove_issue_ids:
      raise exceptions.InputException('No changes to make')

    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    # Used to hold the updated Hotlist.items to use when updating
    # the in-memory hotlist.
    all_hotlist_items = list(hotlist.items)

    # Used to hold ids of issues affected by this change for storing
    # Issue Snapshots.
    affected_issue_ids = set()

    if remove_issue_ids:
      affected_issue_ids.update(remove_issue_ids)
      self.hotlist2issue_tbl.Delete(
          cnxn, hotlist_id=hotlist_id, issue_id=remove_issue_ids, commit=False)
      all_hotlist_items = filter(
          lambda item: item.issue_id not in remove_issue_ids, all_hotlist_items)

    if updated_items:
      updated_issue_ids = [item.issue_id for item in updated_items]
      affected_issue_ids.update(updated_issue_ids)
      self.hotlist2issue_tbl.Delete(
          cnxn, hotlist_id=hotlist_id, issue_id=updated_issue_ids, commit=False)
      insert_rows = []
      for item in updated_items:
        insert_rows.append(
            (
                hotlist_id, item.issue_id, item.rank, item.adder_id,
                item.date_added, item.note))
      self.hotlist2issue_tbl.InsertRows(
          cnxn, cols=HOTLIST2ISSUE_COLS, row_values=insert_rows, commit=False)
      all_hotlist_items = filter(
          lambda item: item.issue_id not in updated_issue_ids,
          all_hotlist_items)
      all_hotlist_items.extend(updated_items)

    if commit:
      cnxn.Commit()
    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])

    # Update in-memory hotlist items.
    hotlist.items = sorted(all_hotlist_items, key=lambda item: item.rank)

    issues = issue_svc.GetIssues(cnxn, list(affected_issue_ids))
    chart_svc.StoreIssueSnapshots(cnxn, issues, commit=commit)

  # TODO(crbug/monorail/7104): {Add|Remove}IssuesToHotlists both call
  # UpdateHotlistItems to add/remove issues from a hotlist.
  # UpdateHotlistItemsFields is called by methods for reranking existing issues
  # and updating HotlistItem notes.
  # (1) We are removing notes from HotlistItems. crbug/monorail/####
  # (2) our v3 AddHotlistItems will allow for inserting new issues to
  # non-last ranks of a hotlist. So there could be some shared code
  # for the reranking path and the adding issues path.
  # UpdateHotlistIssues will be handling adding, removing, and reranking issues.
  # {Add|Remove}IssueToHotlists, UpdateHotlistItems, UpdateHotlistItemFields
  # should be removed, once all methods are updated to call UpdateHotlistIssues.

  def AddIssueToHotlists(self, cnxn, hotlist_ids, issue_tuple, issue_svc,
                         chart_svc, commit=True):
    """Add a single issue, specified in the issue_tuple, to the given hotlists.

    Args:
      cnxn: connection to SQL database.
      hotlist_ids: a list of hotlist_ids to add the issues to.
      issue_tuple: (issue_id, user_id, ts, note) of the issue to be added.
      issue_svc: an instance of IssueService.
      chart_svc: an instance of ChartService.
    """
    self.AddIssuesToHotlists(cnxn, hotlist_ids, [issue_tuple], issue_svc,
        chart_svc, commit=commit)

  def AddIssuesToHotlists(self, cnxn, hotlist_ids, added_tuples, issue_svc,
                          chart_svc, commit=True):
    """Add the issues given in the added_tuples list to the given hotlists.

    Args:
      cnxn: connection to SQL database.
      hotlist_ids: a list of hotlist_ids to add the issues to.
      added_tuples: a list of (issue_id, user_id, ts, note)
        for issues to be added.
      issue_svc: an instance of IssueService.
      chart_svc: an instance of ChartService.
    """
    for hotlist_id in hotlist_ids:
      self.UpdateHotlistItems(cnxn, hotlist_id, [], added_tuples, commit=commit)

    issues = issue_svc.GetIssues(cnxn,
        [added_tuple[0] for added_tuple in added_tuples])
    chart_svc.StoreIssueSnapshots(cnxn, issues, commit=commit)

  def RemoveIssuesFromHotlists(self, cnxn, hotlist_ids, issue_ids, issue_svc,
                               chart_svc, commit=True):
    """Remove the issues given in issue_ids from the given hotlists.

    Args:
      cnxn: connection to SQL database.
      hotlist_ids: a list of hotlist ids to remove the issues from.
      issue_ids: a list of issue_ids to be removed.
      issue_svc: an instance of IssueService.
      chart_svc: an instance of ChartService.
    """
    for hotlist_id in hotlist_ids:
      self.UpdateHotlistItems(cnxn, hotlist_id, issue_ids, [], commit=commit)

    issues = issue_svc.GetIssues(cnxn, issue_ids)
    chart_svc.StoreIssueSnapshots(cnxn, issues, commit=commit)

  def UpdateHotlistItems(
      self, cnxn, hotlist_id, remove, added_tuples, commit=True):
    """Updates a hotlist's list of hotlistissues.

    Args:
      cnxn: connection to SQL database.
      hotlist_id: the ID of the hotlist to update.
      remove: a list of issue_ids for be removed.
      added_tuples: a list of (issue_id, user_id, ts, note)
        for issues to be added.
    """
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    # adding new Hotlistissues, ignoring pairs where issue_id is already in
    # hotlist's iid_rank_pairs
    current_issues_ids = {
        item.issue_id for item in hotlist.items}

    self.hotlist2issue_tbl.Delete(
        cnxn, hotlist_id=hotlist_id,
        issue_id=[remove_id for remove_id in remove
                  if remove_id in current_issues_ids],
        commit=False)
    if hotlist.items:
      items_sorted = sorted(hotlist.items, key=lambda item: item.rank)
      rank_base = items_sorted[-1].rank + 10
    else:
      rank_base = 1
    insert_rows = [
        (hotlist_id, issue_id, rank*10 + rank_base, user_id, ts, note)
        for (rank, (issue_id, user_id, ts, note)) in enumerate(added_tuples)
        if issue_id not in current_issues_ids]
    self.hotlist2issue_tbl.InsertRows(
        cnxn, cols=HOTLIST2ISSUE_COLS, row_values=insert_rows, commit=commit)
    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])

    # removing an issue that was never in the hotlist would not cause any
    # problems.
    items = [
        item for item in hotlist.items if
        item.issue_id not in remove]

    new_hotlist_items = [
        features_pb2.MakeHotlistItem(issue_id, rank, user_id, ts, note)
        for (_hid, issue_id, rank, user_id, ts, note) in insert_rows]
    items.extend(new_hotlist_items)
    hotlist.items = items

  def UpdateHotlistItemsFields(
      self, cnxn, hotlist_id, new_ranks=None, new_notes=None, commit=True):
    """Updates rankings or notes of hotlistissues.

    Args:
      cnxn: connection to SQL database.
      hotlist_id: the ID of the hotlist to update.
      new_ranks : This should be a dictionary of {issue_id: rank}.
      new_notes: This should be a diciontary of {issue_id: note}.
      commit: set to False to skip the DB commit and do it in the caller.
    """
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()
    if new_ranks is None:
      new_ranks = {}
    if new_notes is None:
      new_notes = {}
    issue_ids = []
    insert_rows = []

    # Update the hotlist PB in RAM
    for hotlist_item in hotlist.items:
      item_updated = False
      if hotlist_item.issue_id in new_ranks:
        # Update rank before adding it to insert_rows
        hotlist_item.rank = new_ranks[hotlist_item.issue_id]
        item_updated = True
      if hotlist_item.issue_id in new_notes:
        # Update note before adding it to insert_rows
        hotlist_item.note = new_notes[hotlist_item.issue_id]
        item_updated = True
      if item_updated:
        issue_ids.append(hotlist_item.issue_id)
        insert_rows.append((
            hotlist_id, hotlist_item.issue_id, hotlist_item.rank,
            hotlist_item.adder_id, hotlist_item.date_added, hotlist_item.note))
    hotlist.items = sorted(hotlist.items, key=lambda item: item.rank)
    self.hotlist2issue_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, issue_id=issue_ids, commit=False)

    self.hotlist2issue_tbl.InsertRows(
        cnxn, cols=HOTLIST2ISSUE_COLS , row_values=insert_rows, commit=commit)
    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])

  def _InsertHotlist(self, cnxn, hotlist):
    """Insert the given hotlist into the database."""
    hotlist_id = self.hotlist_tbl.InsertRow(
        cnxn, name=hotlist.name, summary=hotlist.summary,
        description=hotlist.description, is_private=hotlist.is_private,
        default_col_spec=hotlist.default_col_spec)
    logging.info('stored hotlist was given id %d', hotlist_id)

    self.hotlist2issue_tbl.InsertRows(
        cnxn, HOTLIST2ISSUE_COLS,
        [(hotlist_id, issue.issue_id, issue.rank,
          issue.adder_id, issue.date_added, issue.note)
         for issue in hotlist.items],
        commit=False)
    self.hotlist2user_tbl.InsertRows(
        cnxn, HOTLIST2USER_COLS,
        [(hotlist_id, user_id, 'owner')
         for user_id in hotlist.owner_ids] +
        [(hotlist_id, user_id, 'editor')
         for user_id in hotlist.editor_ids] +
        [(hotlist_id, user_id, 'follower')
         for user_id in hotlist.follower_ids])

    self.hotlist_user_to_ids.InvalidateKeys(cnxn, hotlist.owner_ids)

    return hotlist_id

  def TransferHotlistOwnership(
      self, cnxn, hotlist, new_owner_id, remain_editor, commit=True):
    """Transfers ownership of a hotlist to a new owner."""
    new_editor_ids = hotlist.editor_ids
    if remain_editor:
      new_editor_ids.extend(hotlist.owner_ids)
    if new_owner_id in new_editor_ids:
      new_editor_ids.remove(new_owner_id)
    new_follower_ids = hotlist.follower_ids
    if new_owner_id in new_follower_ids:
      new_follower_ids.remove(new_owner_id)
    self.UpdateHotlistRoles(
        cnxn, hotlist.hotlist_id, [new_owner_id], new_editor_ids,
        new_follower_ids, commit=commit)

  ### Lookup hotlist IDs

  def LookupHotlistIDs(self, cnxn, hotlist_names, owner_ids):
    """Return a dict of (name, owner_id) mapped to hotlist_id for all hotlists
    with one of the given names and any of the given owners. Hotlists that
    match multiple owners will be in the dict multiple times."""
    id_dict, _missed_keys = self.hotlist_id_2lc.GetAll(
        cnxn, [(name.lower(), owner_id)
               for name in hotlist_names for owner_id in owner_ids])
    return id_dict

  def LookupUserHotlists(self, cnxn, user_ids):
    """Return a dict of {user_id: [hotlist_id,...]} for all user_ids."""
    id_dict, missed_ids = self.hotlist_user_to_ids.GetAll(user_ids)
    if missed_ids:
      retrieved_dict = {user_id: [] for user_id in missed_ids}
      id_rows = self.hotlist2user_tbl.Select(
          cnxn, cols=['user_id', 'hotlist_id'], user_id=user_ids,
          left_joins=[('Hotlist ON hotlist_id = id', [])],
          where=[('Hotlist.is_deleted = %s', [False])])
      for (user_id, hotlist_id) in id_rows:
        retrieved_dict[user_id].append(hotlist_id)
      self.hotlist_user_to_ids.CacheAll(retrieved_dict)
      id_dict.update(retrieved_dict)

    return id_dict

  def LookupIssueHotlists(self, cnxn, issue_ids):
    """Return a dict of {issue_id: [hotlist_id,...]} for all issue_ids."""
    # TODO(jojwang): create hotlist_issue_to_ids cache
    retrieved_dict = {issue_id: [] for issue_id in issue_ids}
    id_rows = self.hotlist2issue_tbl.Select(
        cnxn, cols=['hotlist_id', 'issue_id'], issue_id=issue_ids,
        left_joins=[('Hotlist ON hotlist_id = id', [])],
        where=[('Hotlist.is_deleted = %s', [False])])
    for hotlist_id, issue_id in id_rows:
      retrieved_dict[issue_id].append(hotlist_id)
    return retrieved_dict

  def GetProjectIDsFromHotlist(self, cnxn, hotlist_id):
    project_id_rows = self.hotlist2issue_tbl.Select(cnxn,
        cols=['Issue.project_id'], hotlist_id=hotlist_id, distinct=True,
        left_joins=[('Issue ON issue_id = id', [])])
    return [row[0] for row in project_id_rows]

  ### Get hotlists
  def GetHotlists(self, cnxn, hotlist_ids, use_cache=True):
    """Returns dict of {hotlist_id: hotlist PB}."""
    hotlists_dict, missed_ids = self.hotlist_2lc.GetAll(
        cnxn, hotlist_ids, use_cache=use_cache)

    if missed_ids:
      raise NoSuchHotlistException()

    return hotlists_dict

  def GetHotlistsByUserID(self, cnxn, user_id, use_cache=True):
    """Get a list of hotlist PBs for a given user."""
    hotlist_id_dict = self.LookupUserHotlists(cnxn, [user_id])
    hotlists = self.GetHotlists(
        cnxn, hotlist_id_dict.get(user_id, []), use_cache=use_cache)
    return list(hotlists.values())

  def GetHotlistsByIssueID(self, cnxn, issue_id, use_cache=True):
    """Get a list of hotlist PBs for a given issue."""
    hotlist_id_dict = self.LookupIssueHotlists(cnxn, [issue_id])
    hotlists = self.GetHotlists(
        cnxn, hotlist_id_dict.get(issue_id, []), use_cache=use_cache)
    return list(hotlists.values())

  def GetHotlist(self, cnxn, hotlist_id, use_cache=True):
    """Returns hotlist PB."""
    hotlist_dict = self.GetHotlists(cnxn, [hotlist_id], use_cache=use_cache)
    return hotlist_dict[hotlist_id]

  def GetHotlistsByID(self, cnxn, hotlist_ids, use_cache=True):
    """Load all the Hotlist PBs for the given hotlists.

    Args:
      cnxn: connection to SQL database.
      hotlist_ids: list of hotlist ids.
      use_cache: specifiy False to force database query.

    Returns:
      A dict mapping ids to the corresponding Hotlist protocol buffers and
      a list of any hotlist_ids that were not found.
    """
    hotlists_dict, missed_ids = self.hotlist_2lc.GetAll(
        cnxn, hotlist_ids, use_cache=use_cache)
    return hotlists_dict, missed_ids

  def GetHotlistByID(self, cnxn, hotlist_id, use_cache=True):
    """Load the specified hotlist from the database, None if does not exist."""
    hotlist_dict, _ = self.GetHotlistsByID(
        cnxn, [hotlist_id], use_cache=use_cache)
    return hotlist_dict.get(hotlist_id)

  def UpdateHotlistRoles(
      self, cnxn, hotlist_id, owner_ids, editor_ids, follower_ids, commit=True):
    """"Store the hotlist's roles in the DB."""
    # This will be a newly contructed object, not from the cache and not
    # shared with any other thread.
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    self.hotlist2user_tbl.Delete(
        cnxn, hotlist_id=hotlist_id, commit=False)

    insert_rows = [(hotlist_id, user_id, 'owner') for user_id in owner_ids]
    insert_rows.extend(
        [(hotlist_id, user_id, 'editor') for user_id in editor_ids])
    insert_rows.extend(
        [(hotlist_id, user_id, 'follower') for user_id in follower_ids])
    self.hotlist2user_tbl.InsertRows(
        cnxn, HOTLIST2USER_COLS, insert_rows, commit=False)

    if commit:
      cnxn.Commit()
    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])
    self.hotlist_user_to_ids.InvalidateKeys(cnxn, hotlist.owner_ids)
    hotlist.owner_ids = owner_ids
    hotlist.editor_ids = editor_ids
    hotlist.follower_ids = follower_ids

  def DeleteHotlist(self, cnxn, hotlist_id, commit=True):
    hotlist = self.GetHotlist(cnxn, hotlist_id, use_cache=False)
    if not hotlist:
      raise NoSuchHotlistException()

    # Fetch all associated project IDs in order to invalidate their cache.
    project_ids = self.GetProjectIDsFromHotlist(cnxn, hotlist_id)

    delta = {'is_deleted': True}
    self.hotlist_tbl.Update(cnxn, delta, id=hotlist_id, commit=commit)

    self.hotlist_2lc.InvalidateKeys(cnxn, [hotlist_id])
    self.hotlist_user_to_ids.InvalidateKeys(cnxn, hotlist.owner_ids)
    self.hotlist_user_to_ids.InvalidateKeys(cnxn, hotlist.editor_ids)
    if not hotlist.owner_ids:  # Should never happen.
      logging.warn('Soft-deleting unowned Hotlist: id:%r, name:%r',
        hotlist_id, hotlist.name)
    elif hotlist.name:
      self.hotlist_id_2lc.InvalidateKeys(
          cnxn, [(hotlist.name.lower(), owner_id) for
                 owner_id in hotlist.owner_ids])

    for project_id in project_ids:
      self.config_service.InvalidateMemcacheForEntireProject(project_id)

  def ExpungeHotlists(
      self, cnxn, hotlist_ids, star_svc, user_svc, chart_svc, commit=True):
    """Wipes the given hotlists from the DB tables.

    This method will only do cache invalidation if commit is set to True.

    Args:
      cnxn: connection to SQL database.
      hotlist_ids: the ID of the hotlists to Expunge.
      star_svc: an instance of a HotlistStarService.
      user_svc: an instance of a UserService.
      chart_svc: an instance of a ChartService.
      commit: set to False to skip the DB commit and do it in the caller.
    """

    hotlists_by_id = self.GetHotlists(cnxn, hotlist_ids)

    for hotlist_id in hotlist_ids:
      star_svc.ExpungeStars(cnxn, hotlist_id, commit=commit)
    chart_svc.ExpungeHotlistsFromIssueSnapshots(
        cnxn, hotlist_ids, commit=commit)
    user_svc.ExpungeHotlistsFromHistory(cnxn, hotlist_ids, commit=commit)
    self.hotlist2user_tbl.Delete(cnxn, hotlist_id=hotlist_ids, commit=commit)
    self.hotlist2issue_tbl.Delete(cnxn, hotlist_id=hotlist_ids, commit=commit)
    self.hotlist_tbl.Delete(cnxn, id=hotlist_ids, commit=commit)

    # Invalidate cache for deleted hotlists.
    self.hotlist_2lc.InvalidateKeys(cnxn, hotlist_ids)
    users_to_invalidate = set()
    for hotlist in hotlists_by_id.values():
      users_to_invalidate.update(
          hotlist.owner_ids + hotlist.editor_ids + hotlist.follower_ids)
      self.hotlist_id_2lc.InvalidateKeys(
          cnxn, [(hotlist.name, owner_id) for owner_id in hotlist.owner_ids])
    self.hotlist_user_to_ids.InvalidateKeys(cnxn, list(users_to_invalidate))
    hotlist_project_ids = set()
    for hotlist_id in hotlist_ids:
      hotlist_project_ids.update(self.GetProjectIDsFromHotlist(
          cnxn, hotlist_id))
    for project_id in hotlist_project_ids:
      self.config_service.InvalidateMemcacheForEntireProject(project_id)

  def ExpungeUsersInHotlists(
      self, cnxn, user_ids, star_svc, user_svc, chart_svc):
    """Wipes the given users and any hotlists they owned from the
       hotlists system.

    This method will not commit the operation. This method will not make
    changes to in-memory data.
    """
    # Transfer hotlist ownership to editors, if possible.
    hotlist_ids_by_user_id = self.LookupUserHotlists(cnxn, user_ids)
    hotlist_ids = [hotlist_id for hotlist_ids in hotlist_ids_by_user_id.values()
                   for hotlist_id in hotlist_ids]
    hotlists_by_id, missed = self.GetHotlistsByID(
        cnxn, list(set(hotlist_ids)), use_cache=False)
    logging.info('Missed hotlists: %s', missed)

    hotlists_to_delete = []
    for hotlist_id, hotlist in hotlists_by_id.items():
      # One of the users to be deleted is an owner of hotlist.
      if not set(hotlist.owner_ids).isdisjoint(user_ids):
        hotlists_to_delete.append(hotlist_id)
        candidate_new_owners = [user_id for user_id in hotlist.editor_ids
                                if user_id not in user_ids]
        for candidate_id in candidate_new_owners:
          if not self.LookupHotlistIDs(cnxn, [hotlist.name], [candidate_id]):
            self.TransferHotlistOwnership(
                cnxn, hotlist, candidate_id, False, commit=False)
            # Hotlist transferred successfully. No need to delete it.
            hotlists_to_delete.remove(hotlist_id)
            break

    # Delete users
    self.hotlist2user_tbl.Delete(cnxn, user_id=user_ids, commit=False)
    self.hotlist2issue_tbl.Update(
        cnxn, {'adder_id': framework_constants.DELETED_USER_ID},
        adder_id=user_ids, commit=False)
    user_svc.ExpungeUsersHotlistsHistory(cnxn, user_ids, commit=False)
    # Delete hotlists
    if hotlists_to_delete:
      self.ExpungeHotlists(
          cnxn, hotlists_to_delete, star_svc, user_svc, chart_svc, commit=False)


class HotlistAlreadyExists(Exception):
  """Tried to create a hotlist with the same name as another hotlist
  with the same owner."""
  pass


class NoSuchHotlistException(Exception):
  """The requested hotlist was not found."""
  pass


class UnownedHotlistException(Exception):
  """Tried to create a hotlist with no owner."""
  pass
