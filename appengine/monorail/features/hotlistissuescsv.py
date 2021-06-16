# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implemention of the hotlist issues list output as a CSV file."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from features import hotlistissues
from framework import framework_views
from framework import csv_helpers
from framework import permissions
from framework import xsrf


# TODO(jojwang): can be refactored even more, see similarities with
# IssueListCsv
class HotlistIssuesCsv(hotlistissues.HotlistIssues):
  """HotlistIssuesCsv provides to the user a list of issues as a CSV document.

  Overrides the standard HotlistIssues servlet but uses a different EZT template
  to provide the same content as the HotlistIssues only as CSV. Adds the HTTP
  header to offer the result as a download.
  """

  _PAGE_TEMPLATE = 'tracker/issue-list-csv.ezt'

  def GatherPageData(self, mr):
    if not mr.auth.user_id:
      raise permissions.PermissionException(
          'Anonymous users are not allowed to download hotlist CSV')

    owner_id = mr.hotlist.owner_ids[0]  # only one owner allowed
    users_by_id = framework_views.MakeAllUserViews(
        mr.cnxn, self.services.user,
        [owner_id])
    owner = users_by_id[owner_id]

    # Try to validate XSRF by either user email or user ID.
    try:
      xsrf.ValidateToken(
          mr.token, mr.auth.user_id,
          '/u/%s/hotlists/%s.do' % (owner.email, mr.hotlist.name))
    except xsrf.TokenIncorrect:
      xsrf.ValidateToken(
          mr.token, mr.auth.user_id,
          '/u/%s/hotlists/%s.do' % (owner.user_id, mr.hotlist.name))

    # Sets headers to allow the response to be downloaded.
    self.content_type = 'text/csv; charset=UTF-8'
    download_filename = 'hotlist_%d-issues.csv' % mr.hotlist_id
    self.response.headers.add(
        'Content-Disposition', 'attachment; filename=%s' % download_filename)
    self.response.headers.add('X-Content-Type-Options', 'nosniff')

    mr.ComputeColSpec(mr.hotlist)
    mr.col_spec = csv_helpers.RewriteColspec(mr.col_spec)
    page_data = hotlistissues.HotlistIssues.GatherPageData(self, mr)
    return csv_helpers.ReformatRowsForCSV(
        mr, page_data, '%d/csv' % mr.hotlist_id)
