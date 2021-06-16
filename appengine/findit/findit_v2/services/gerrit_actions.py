# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra_api_clients.codereview import gerrit
from services import git


class GerritActions(object):
  """Houses functions for interacting with Gerrit for auto-actions in findit_v2.
  """

  def __init__(self, project_api):
    self.project_api = project_api

  def ChangeInfoAndClientFromCommit(self, commit):
    """Gets a commit's code review information and a configured client."""
    repo_url = git.GetRepoUrlFromCommit(commit)
    change_info = git.GetCodeReviewInfoForACommit(commit.gitiles_id, repo_url,
                                                  commit.gitiles_ref)
    assert change_info, 'Missing CL info for %s' % commit.key.id()
    return change_info, gerrit.Gerrit(change_info['review_server_host'])

  def NotifyCulprit(self, culprit, message, silent_notification=True):
    """Post comment on culprit's CL about Findit's findings.

    This is intended for Findit to notify the culprit's author/reviewers that
    change was identified by Findit as causing certain CI failures.
    Args:
      culprit (findit_v2.model.gitiles_commit.Culprit), the culprit to notify.
      message(str): A message explaining the findings, and providing an example
          of a failed build caused by the change. This will be posted in the CL
          as a comment.
      silent_notification(bool): If true, make the comment posting not send
          email to the reviewers. For example, when the culprit is already being
          reverted by a human, such as the sheriff or the author.
    Returns:
      sent: A boolean indicating whether the notification was sent successfully.
    """
    change_info, gerrit_client = self.ChangeInfoAndClientFromCommit(culprit)
    return gerrit_client.PostMessage(
        change_info['review_change_id'],
        message,
        should_email=not silent_notification)

  def CreateRevert(self, culprit, reason):
    """Create a revert of a culprit.

    If a commit is identified as the root cause of a CI failure, Findit may
    choose to create a revert if the project is so configured. This revert may
    then be landed automatically by Findit or manually by Sheriffs or other
    group in charge of the CI waterfall, again depending on how the project is
    configured.

    Args:
      culrpit (findit_v2.model.gitiles_commit.Culprit) The culprit to revert.
      reason(str): A message explaining the reason for the revert, this will
          be included in the commit description of the revert.
    Returns:
      revert_info:
      A dictionary as returned by Gerrit. E.g.:
      {
        "id": "myProject~master~I8473b95934b5732ac55d26311a706c9c2bde9940",
        "project": "myProject",
        "branch": "master",
        "change_id": "I8473b95934b5732ac55d26311a706c9c2bde9940",
        "subject": "Revert \"Implementing Feature X\"",
        "status": "NEW",
        "created": "2013-02-01 09:59:32.126000000",
        "updated": "2013-02-21 11:16:36.775000000",
        "mergeable": true,
        "insertions": 6,
        "deletions": 4,
        "_number": 3965,
        "owner": {
          "name": "John Doe"
        }
      }
    """
    change_info, gerrit_client = self.ChangeInfoAndClientFromCommit(culprit)
    revert_info = gerrit_client.CreateRevert(
        reason, change_info['review_change_id'], full_change_info=True)
    revert_info['client'] = gerrit_client
    return revert_info

  def RequestReview(self, revert_info, message):
    """Add appropriate reviewers to revert for manual submission.

    In case the project is not configured to automatically land reverts, or the
    configured limit of auto-submitted reverts has been reached, this method may
    be called to add the appropriate reviewers and post a message requesting
    that they manually land the revert if they agree with Findit's findings.
    Args:
      revert_info (dict): A dictionary identifying the revert to be reviewed
          as generated by CreateRevert()
      message(str): A message explaining that Findit will not commit the revert
          automatically, instructions about how to land it and where to report a
          false positive. This will be added to the CL as a comment.
    """
    client = revert_info['client']
    return bool(
        client.AddReviewers(
            revert_info['review_change_id'],
            self.project_api.GetAutoRevertReviewers(),
            message=message))

  def CommitRevert(self, revert_info, request_confirmation_message):
    """Attempt to submit a revert created by Findit.

    Once a revert has been created, Findit may land it if the project is
    configured to allow it. It will also add the Sheriffs on rotation as
    reviewers of the revert and post a message with the justification for
    landing the revert, as well as informing the reviewers on how to report a
    false positive.

    Args:
      revert_info (dict): A dictionary identifying the revert to be committed
          as generated by CreateRevert()
      request_confirmation_message(str): A message explaining that Findit
          committed the change automatically and where to report a false
          positive. This will be added to the CL as a comment.
    Returns:
      A boolean indicating whether the revert was landed successfully.
    """
    client = revert_info['client']
    submitted = client.SubmitRevert(revert_info['review_change_id'])
    if submitted:
      return self.RequestReview(revert_info, request_confirmation_message)
    return False