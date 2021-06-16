# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import urlparse

_NO_RETRY_CODES = [200, 302, 401, 403, 404, 409, 501]
_RETRIABLE_EXCEPTIONS = []


class HttpInterceptorBase(object):
  """A modifying interceptor for http clients.

  This is a base class for interceptors that can intercept and modify:
    - A request before it is made
    - A response before it is returned to the caller
    - An exception before it is raised to the caller

  It is expected that the caller will use the returned values for each of these
  methods instead of the ones originally sent to them.
  """

  def __init__(self, no_retry_codes=None, retriable_exceptions=None):
    self.no_retry_codes = no_retry_codes or _NO_RETRY_CODES
    self._retriable_exceptions = tuple(retriable_exceptions or
                                       _RETRIABLE_EXCEPTIONS)

  def GetAuthenticationHeaders(self, request):
    """An interceptor can override this method to produce auth headers.

    The http client is expected to call this function for every request and
    update the request's headers with the ones this function provides.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers'
    Returns: a dict containing headers to be set to the request before sending.
    """
    _ = request
    return {}

  def OnRequest(self, request):
    """Override this method to examine and/or tweak requests before sending.

    The http client is expected to call this method on every request and use its
    return value instead.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers'
    Returns: A request dict with possibly modified values.
    """
    return request

  def OnResponse(self, request, response):
    """Override to check and/or tweak status/body before returning to caller.

    Also, decide whether the request should be retried.

    The http client is expected to call this method after a response is received
    and before any retry logic is applied. The client is expected to return to
    the caller the return value of this method, modulo any retry logic that the
    client may implement.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers' for the request that was sent to obtain the response.
      - response(dict): A dict with 'status_code' and 'content' fields.
    Returns: A response dict with the same values (or possibly modified ones) as
      the 'response' arg, **and a boolean indicating whether to retry**
    """
    _ = request
    return response, response.get('status_code') not in self.no_retry_codes

  def OnException(self, request, exception, can_retry):
    """Override to check and/or tweak an exception raised when sending request.

    The http client is expected to call this method with any exception raised
    when sending the request, if this method returns an exception, the client
    will raise it to the caller; if None is returned, the client may retry.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers' for the request that was sent to obtain the response.
      - exception(Exception): The exception raised by the underlying call.
      - can_retry(bool): Whether the caller will retry if the interceptor
        swallows the exception. Useful to take action on persistent exceptions
        and not on transient ones.
    Retruns: An exception to be raised to the caller or None.
    """
    _ = request
    if can_retry and isinstance(exception, self._retriable_exceptions):
      # Only swallow a known exception when can_retry is true.
      return None
    return exception

  @staticmethod
  def GetHost(url):
    """Standarized way for interceptors to get the host from the requested urls.

    The point of having this here instead of making each interceptor parse the
    url, is that we may have a single point to use special-casing for some hosts
    and/or paths.

    Args:
      - url(str): A string containing the requested url.
    Returns:
      The hostname part of the url(str), None if url is empty or None.
    """
    host = None
    if url:
      host = urlparse.urlparse(url).hostname
    return host


class LoggingInterceptor(HttpInterceptorBase):
  """A minimal interceptor that logs status code and url."""

  def __init__(self, *args, **kwargs):
    self.no_error_logging_statuses = kwargs.pop('no_error_logging_statuses', [])
    super(LoggingInterceptor, self).__init__(*args, **kwargs)

  def OnResponse(self, request, response):
    if response.get('status_code') == 200:
      logging.info('got response status 200 for url %s', request.get('url'))
    elif response.get('status_code') not in self.no_error_logging_statuses:
      logging.info('request to %s responded with %d http status and headers %s',
                   request.get('url'), response.get('status_code', 0),
                   json.dumps(response.get('headers', {}).items()))

    # Call the base's OnResponse to keep the retry functionality.
    return super(LoggingInterceptor, self).OnResponse(request, response)

  def OnException(self, request, exception, can_retry):
    if can_retry:
      logging.warning('got exception %s("%s") for url %s', type(exception),
                      exception.message, request.get('url'))
    else:
      logging.exception('got exception %s("%s") for url %s', type(exception),
                        exception.message, request.get('url'))
    return super(LoggingInterceptor, self).OnException(request, exception,
                                                       can_retry)
