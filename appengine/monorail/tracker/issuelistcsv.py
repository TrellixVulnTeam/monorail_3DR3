# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implemention of the issue list output as a CSV file."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import types

import settings

from framework import csv_helpers
from framework import permissions
from framework import urls
from framework import xsrf
from tracker import issuelist
from tracker import tablecell


class IssueListCsv(issuelist.IssueList):
  """IssueListCsv provides to the user a list of issues as a CSV document.

  Overrides the standard IssueList servlet but uses a different EZT template
  to provide the same content as the IssueList only as CSV.  Adds the HTTP
  header to offer the result as a download.
  """

  _PAGE_TEMPLATE = 'tracker/issue-list-csv.ezt'

  def GatherPageData(self, mr):
    if not mr.auth.user_id:
      raise permissions.PermissionException(
          'Anonymous users are not allowed to download issue list CSV')

    xsrf.ValidateToken(
        mr.token, mr.auth.user_id,
        '/p/%s%s.do' % (mr.project_name, urls.ISSUE_LIST_OLD))

    # Sets headers to allow the response to be downloaded.
    self.content_type = 'text/csv; charset=UTF-8'
    download_filename = '%s-issues.csv' % mr.project_name
    self.response.headers.add(
        'Content-Disposition', 'attachment; filename=%s' % download_filename)
    self.response.headers.add('X-Content-Type-Options', 'nosniff')

    # Rewrite the colspec to add some extra columns that make the CSV
    # file more complete.
    with mr.profiler.Phase('finishing config work'):
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)

    mr.ComputeColSpec(config)
    mr.col_spec = csv_helpers.RewriteColspec(mr.col_spec)
    page_data = issuelist.IssueList.GatherPageData(self, mr)
    return  csv_helpers.ReformatRowsForCSV(mr, page_data, urls.ISSUE_LIST_CSV)

  def GetCellFactories(self):
    return tablecell.CSV_CELL_FACTORIES
