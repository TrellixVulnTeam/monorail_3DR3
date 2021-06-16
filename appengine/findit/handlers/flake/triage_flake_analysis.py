# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to handle manual triage of a suspected flake result.

This handler will mark the suspected flake result as correct or incorrect.
"""

from google.appengine.ext import ndb
from google.appengine.api import users

from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from libs import analysis_status


def _UpdateSuspectedFlakeAnalysis(key_urlsafe, triage_result, user_name):
  master_flake_analysis = ndb.Key(urlsafe=key_urlsafe).get()

  assert master_flake_analysis
  assert master_flake_analysis.status == analysis_status.COMPLETED
  assert master_flake_analysis.suspected_flake_build_number is not None

  if master_flake_analysis.culprit_urlsafe_key:
    culprit = ndb.Key(urlsafe=master_flake_analysis.culprit_urlsafe_key).get()
    assert culprit

    suspect_info = {
        'culprit_revision': culprit.revision,
        'culprit_commit_position': culprit.commit_position,
        'culprit_url': culprit.url,
    }
  else:
    suspect_info = {
        'build_number': master_flake_analysis.suspected_flake_build_number
    }

  master_flake_analysis.UpdateTriageResult(triage_result, suspect_info,
                                           user_name,
                                           master_flake_analysis.version_number)
  master_flake_analysis.put()
  return True


class TriageFlakeAnalysis(BaseHandler):
  PERMISSION_LEVEL = Permission.CORP_USER

  @token.VerifyXSRFToken()
  def HandlePost(self):
    """Sets the manual triage result for the suspected flake analysis."""
    key_urlsafe = self.request.get('key').strip()
    triage_result = self.request.get('triage_result')

    if not key_urlsafe or triage_result is None:
      return {'data': {'success': False}}

    # As the permission level is CORP_USER, we could assume the current user
    # already logged in.
    user_name = users.get_current_user().email().split('@')[0]

    success = _UpdateSuspectedFlakeAnalysis(key_urlsafe,
                                            int(triage_result), user_name)

    return {'data': {'success': success}}
