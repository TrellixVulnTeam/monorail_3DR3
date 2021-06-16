# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that help display pagination widgets for result sets."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import base64
import logging
import hmac

from third_party import ezt
from google.protobuf import message

import settings
from framework import exceptions
from framework import framework_helpers
from services import secrets_svc
from proto import secrets_pb2

# TODO(crbug/monorail/6988):Create Paginator class in API level to keep
# code separate and simple.

def GeneratePageToken(request_contents, start):
  # type: (secrets_pb2.ListRequestContents, int) -> str
  """Encrypts a List requests's contents and generates a next page token.

  Args:
    request_contents: ListRequestContents object that holds data given by the
      request.
    start: int start index that should be used for the subsequent request.

  Returns:
    String next_page_token that is a serialized PageTokenContents object.
  """
  digester = hmac.new(secrets_svc.GetPaginationKey())
  digester.update(request_contents.SerializeToString())
  token_contents = secrets_pb2.PageTokenContents(
      start=start,
      encrypted_list_request_contents=digester.digest())
  serialized_token = token_contents.SerializeToString()
  # Page tokens must be URL-safe strings (see aip.dev/158)
  # and proto string fields must be utf-8 strings while
  # `SerializeToString()` returns binary bytes contained in a str type.
  # So we must encode with web-safe base64 format.
  return base64.b64encode(serialized_token)


def ValidateAndParsePageToken(token, request_contents):
  # type: (str, secrets_pb2.ListRequestContents) -> int
  """Returns the start index of the page if the token is valid.

  Args:
    token: String token given in a ListFoo API request.
    request_contents: ListRequestContents object that holds data given by the
      request.

  Returns:
    The start index that should be used when getting the requested page.

  Raises:
    PageTokenException: if the token is invalid or incorrect for the given
      request_contents.
  """
  token_contents = secrets_pb2.PageTokenContents()
  try:
    decoded_serialized_token = base64.b64decode(token)
    token_contents.ParseFromString(decoded_serialized_token)
  except (message.DecodeError, TypeError):
    raise exceptions.PageTokenException('Invalid page token.')

  start = token_contents.start
  expected_token = GeneratePageToken(request_contents, start)
  if hmac.compare_digest(token, expected_token):
    return start
  raise exceptions.PageTokenException('Incorrect page token.')


# If extracting items_per_page and start values from a MonorailRequest object,
# keep in mind that mr.num and mr.GetPositiveIntParam may return different
# values. mr.num is the result of calling mr.GetPositiveIntParam with a default
# value.
class VirtualPagination(object):
  """Class to calc Prev and Next pagination links based on result counts."""

  def __init__(self, total_count, items_per_page, start, list_page_url=None,
               count_up=True, start_param_name='start', num_param_name='num',
               max_num=None, url_params=None, project_name=None):
    """Given 'num' and 'start' params, determine Prev and Next links.

    Args:
      total_count: total number of artifacts that satisfy the query.
      items_per_page: number of items to display on each page, e.g., 25.
      start: the start index of the pagination page.
      list_page_url: URL of the web application page that is displaying
        the list of artifacts.  Used to build the Prev and Next URLs.
        If None, no URLs will be built.
      count_up: if False, count down from total_count.
      start_param_name: query string parameter name for the start value
        of the pagination page.
      num_param: query string parameter name for the number of items
        to show on a pagination page.
      max_num: optional limit on the value of the num param.  If not given,
        settings.max_artifact_search_results_per_page is used.
      url_params: list of (param_name, param_value) we want to keep
        in any new urls.
      project_name: the name of the project we are operating in.
    """
    self.total_count = total_count
    self.prev_url = ''
    self.reload_url = ''
    self.next_url = ''

    if max_num is None:
      max_num = settings.max_artifact_search_results_per_page

    self.num = items_per_page
    self.num = min(self.num, max_num)

    if count_up:
      self.start = start or 0
      self.last = min(self.total_count, self.start + self.num)
      prev_start = max(0, self.start - self.num)
      next_start = self.start + self.num
    else:
      self.start = start or self.total_count
      self.last = max(0, self.start - self.num)
      prev_start = min(self.total_count, self.start + self.num)
      next_start = self.start - self.num

    if list_page_url:
      if project_name:
        list_servlet_rel_url = '/p/%s%s' % (
            project_name, list_page_url)
      else:
        list_servlet_rel_url = list_page_url

      self.reload_url = framework_helpers.FormatURL(
          url_params, list_servlet_rel_url,
          **{start_param_name: self.start, num_param_name: self.num})

      if prev_start != self.start:
        self.prev_url = framework_helpers.FormatURL(
             url_params, list_servlet_rel_url,
            **{start_param_name: prev_start, num_param_name: self.num})
      if ((count_up and next_start < self.total_count) or
          (not count_up and next_start >= 1)):
        self.next_url = framework_helpers.FormatURL(
           url_params, list_servlet_rel_url,
            **{start_param_name: next_start, num_param_name: self.num})

    self.visible = ezt.boolean(self.last != self.start)

    # Adjust indices to one-based values for display to users.
    if count_up:
      self.start += 1
    else:
      self.last += 1

  def DebugString(self):
    """Return a string that is useful in on-page debugging."""
    return '%s - %s of %s; prev_url:%s; next_url:%s' % (
        self.start, self.last, self.total_count, self.prev_url, self.next_url)


class ArtifactPagination(VirtualPagination):
  """Class to calc Prev and Next pagination links based on a results list."""

  def __init__(
      self, results, items_per_page, start, project_name, list_page_url,
      total_count=None, limit_reached=False, skipped=0, url_params=None):
    """Given 'num' and 'start' params, determine Prev and Next links.

    Args:
      results: a list of artifact ids that satisfy the query.
      items_per_page: number of items to display on each page, e.g., 25.
      start: the start index of the pagination page.
      project_name: the name of the project we are operating in.
      list_page_url: URL of the web application page that is displaying
        the list of artifacts.  Used to build the Prev and Next URLs.
      total_count: specify total result count rather than the length of results
      limit_reached: optional boolean that indicates that more results could
        not be fetched because a limit was reached.
      skipped: optional int number of items that were skipped and left off the
        front of results.
      url_params: list of (param_name, param_value) we want to keep
        in any new urls.
    """
    if total_count is None:
      total_count = skipped + len(results)
    super(ArtifactPagination, self).__init__(
        total_count, items_per_page, start, list_page_url=list_page_url,
        project_name=project_name, url_params=url_params)

    self.limit_reached = ezt.boolean(limit_reached)
    # Determine which of those results should be visible on the current page.
    range_start = self.start - 1 - skipped
    range_end = range_start + self.num
    assert 0 <= range_start <= range_end
    self.visible_results = results[range_start:range_end]
