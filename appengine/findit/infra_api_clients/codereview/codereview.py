# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

AUTO_REVERT_OFF_PATTERN = re.compile(r'(NOAUTOREVERT)\s*=\s*true',
                                     re.IGNORECASE)


def IsAutoRevertOff(message):
  match = AUTO_REVERT_OFF_PATTERN.search(message)
  if match:
    flag_name = match.group(1)
    if flag_name.isupper():
      return True
  return False


class CodeReview(object):  # pragma: no cover.
  """Abstract class to interact with code review."""

  def __init__(self, server_hostname):
    """
    Args:
      server_hostname (str): The hostname of the codereview server, eg:
          codereview.chromium.org or chromium-review.googlesource.com.
    """
    self._server_hostname = server_hostname

  def GetCodeReviewUrl(self, change_id):
    """Gets the code review url for a change.

    Args:
      change_id (str or int): The change id of the CL on Gerrit or the issue
        number of the CL on Rietveld.

    Returns:
      The code review url for the change.
    """
    raise NotImplementedError()

  def GetChangeIdFromReviewUrl(self, review_url):
    """Gets the change id from the code review url.

    Args:
      review_url (str): The code review url for the change.

    Returns:
      The change id of the Gerrit Gerrit or the issue number of the Rietveld CL.
    """
    if review_url[-1] == '/':
      review_url = review_url[:-1]
    return review_url.split('/')[-1]

  def PostMessage(self,
                  change_id,
                  message,
                  should_email=True,
                  omit_duplicates=True):
    """Posts the given message to the CL codereview of the given change id.

    Args:
      change_id (str or int): The change id of the CL on Gerrit or the issue
          number of the CL on Rietveld.
      message(str): The message to be posted to the codereview.
      should_email (bool): Should send an email when posting the message or not.
    """
    raise NotImplementedError()

  def CreateRevert(self,
                   reason,
                   change_id,
                   patchset_id=None,
                   footer=None,
                   bug_id=None):
    """Creates a revert CL for the given issue and patchset.

    Args:
      reason (str): A message as the reason for the revert.
      change_id (str or int): The change id on Gerrit or the issue id on
          Rietveld to create the revert for.
      patchset_id (int): The patchset id on Rietveld to create the revert for.
          Optional for Gerrit.

    Returns:
      A dictionary containing at least the 'change_id' key, identifying the
      revert CL created. None if revert creation failed.
    """
    raise NotImplementedError()

  def AddReviewers(self, change_id, reviewers, message=None):
    """Adds a list of users to the CL of the specified url as reviewers.

    Args:
      change_id (str or int): The change id on Gerrit or the issue id on
          Rietveld to add reviewers to.
      reviewers (list of str): The emails of the users to be added as reviewers.
      message(str): (optional) The message to be posted to the codereview.

    Returns:
      A boolean indicating success.
    """
    raise NotImplementedError()

  def GetClDetails(self,
                   change_id,
                   project=None,
                   branch=None,
                   additional_fields=None):
    """Retrieves information about commits and reverts for a given CL.

    Args:
      change_id (str or int): The change id of the CL on Gerrit or the issue
          number of the CL on Rietveld.
      project (str): The project name tracking the CL on the code review server.
      branch (str): The branch name tracking the CL on the code review server.
      additional_fields (list): A list of additional_fields that need to be
        included in response.

    Returns:
      An object that has a `commits` and a `reverts` properties which are lists
      of objects that map a patchset to a revision, and a patchset to a revert
      CL.
    """
    raise NotImplementedError()

  def SubmitRevert(self, change_id):
    """Submits a revert CL.

    Args:
      change_id (str or int): The change id on Gerrit.

    Returns:
      A boolean indicating success.
    """
    raise NotImplementedError()

  def QueryCls(self, query_params, additional_fields=None):
    """Queries changes by provided parameters.

    Args:
      query_params(dict): query parameters.
      additional_fields (list): A list of additional_fields that need to be
        included in response.
    """
    raise NotImplementedError()
