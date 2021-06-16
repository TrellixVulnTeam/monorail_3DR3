# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
import urllib

from libs.http.interceptor import LoggingInterceptor


class RetryHttpClient(object):
  """Represents a http client to send http/https request to a remote server.

  Subclasses should implement abstract functions below.
  """

  def __init__(self,
               no_error_logging_statuses=None,
               interceptor=LoggingInterceptor()):
    # If an http request results in the given statuses, the subclasses should
    # not log an error.
    self.interceptor = interceptor
    if isinstance(self.interceptor, LoggingInterceptor):
      no_error_logging_statuses = no_error_logging_statuses or []
      self.interceptor.no_error_logging_statuses = no_error_logging_statuses

  def _Get(self, url, timeout_seconds, headers):  # pylint: disable=W0613, R0201
    """Sends the actual HTTP GET request.

    Returns:
      (status_code, content, response_headers)
      status_code: the HTTP status code of the response.
      content: the content of the response.
      response_headers (dict): str => str map containing response headers.
    """
    raise NotImplementedError(
        '_Get() should be implemented in the child class')  # pragma: no cover

  def _Post(self, url, data, timeout_seconds, headers):  # pylint: disable=W0613, R0201
    """Sends the actual HTTP POST request.

    Returns:
      (status_code, content, response_headers)
    """
    raise NotImplementedError(
        '_Post() should be implemented in the child class')  # pragma: no cover

  def _Put(self, url, data, timeout_seconds, headers):  # pylint: disable=W0613, R0201
    """Sends the actual HTTP PUT request.

    Returns:
      (status_code, content, response_headers)
    """
    raise NotImplementedError(
        '_Put() should be implemented in the child class')  # pragma: no cover

  def GetBackoff(self, retry_backoff, tries):
    """Returns how many seconds to wait before next retry.

    When ``retry_backoff`` is more than 1, return an exponential backoff;
    otherwise we keep it the same.

    Params:
      retry_backoff (float): The base backoff in seconds.
      tries (int): Indicates how many tries have been done.
    """
    if retry_backoff > 1:
      return retry_backoff * (2**(tries - 1))
    else:
      return retry_backoff

  def _Retry(self,
             url,
             method,
             data=None,
             params=None,
             timeout_seconds=60,
             max_retries=5,
             retry_backoff=1.5,
             headers=None):
    if params and method == 'GET':
      url = '%s?%s' % (url, urllib.urlencode(params))

    if self.interceptor:
      request = {'url': url, 'headers': headers or {}}
      request = self.interceptor.OnRequest(request)

      url = request.get('url')
      headers = request.get('headers')

      # Inject auth-headers.
      headers.update(self.interceptor.GetAuthenticationHeaders(request))

    # Default values in case retries are exhausted with retriable exception.
    status_code = 0
    content = ""
    response_headers = {}

    tries = 0
    while tries < max_retries:
      tries += 1

      try:
        if method == 'POST':
          status_code, content, response_headers = self._Post(
              url, data, timeout_seconds, headers)
        elif method == 'PUT':
          status_code, content, response_headers = self._Put(
              url, data, timeout_seconds, headers)
        else:
          status_code, content, response_headers = self._Get(
              url, timeout_seconds, headers)

        retry = False
        if self.interceptor:
          response, retry = self.interceptor.OnResponse(
              request, {
                  'status_code': status_code,
                  'content': content,
                  'headers': response_headers
              })
          status_code, content, response_headers = response.get(
              'status_code'), response.get('content'), response.get('headers')

        if not retry:
          break
      except Exception as e:
        if self.interceptor:
          e = self.interceptor.OnException(
              request, e, can_retry=tries < max_retries)
        if e is not None:
          raise e

      time.sleep(self.GetBackoff(retry_backoff, tries))

    return status_code, content, response_headers

  def Get(self,
          url,
          params=None,
          timeout_seconds=60,
          max_retries=5,
          retry_backoff=1.5,
          headers=None):
    """Sends a GET request to the url with the given parameters and headers.

    Params:
      url (str): The raw url to send request to. If ``params`` is specified, the
          url should not include any parameter in it.
      params (dict): A key-value dict of parameters to send in the request.
      timeout_seconds (int): The timeout for read/write of the http request.
      max_retries (int): The maxmium times of retries for the request when the
          returning http status code is not in 200, 302, 401, 403, 404, or 501.
      retry_backoff (float): The base backoff in seconds for retry.

    Returns:
      (status_code, content, response_headers)
    """
    return self._Retry(
        url,
        method='GET',
        data=None,
        params=params,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        headers=headers)

  def Post(self,
           url,
           data,
           timeout_seconds=60,
           max_retries=5,
           retry_backoff=1.5,
           headers=None):
    """Sends a POST request to the url with the given parameters and headers.

    Params:
      url (str): The raw url to send request to. If ``params`` is specified, the
          url should not include any parameter in it.
      data (dict): The data to send for post request.
      timeout_seconds (int): The timeout for read/write of the http request.
      max_retries (int): The maximum times of retries for the request when the
          returning http status code is not in 200, 302, 401, 403, 404, or 501.
      retry_backoff (float): The base backoff in seconds for retry.

    Returns:
      (status_code, content, response_headers)
    """
    return self._Retry(
        url,
        method='POST',
        data=data,
        params=None,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        headers=headers)

  def Put(self,
          url,
          data,
          timeout_seconds=60,
          max_retries=5,
          retry_backoff=1.5,
          headers=None):
    """Sends a PUT request to the url with the given parameters and headers.

    Params:
      url (str): The raw url to send request to. If ``params`` is specified, the
          url should not include any parameter in it.
      data (dict): The data to send for post request.
      timeout_seconds (int): The timeout for read/write of the http request.
      max_retries (int): The maximum times of retries for the request when the
          returning http status code is not in 200, 302, 401, 403, 404, or 501.
      retry_backoff (float): The base backoff in seconds for retry.

    Returns:
      (status_code, content, response_headers)
    """
    return self._Retry(
        url,
        method='PUT',
        data=data,
        params=None,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        headers=headers)
