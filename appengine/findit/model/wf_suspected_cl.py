# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model.base_suspected_cl import BaseSuspectedCL
from waterfall import buildbot


class WfSuspectedCL(BaseSuspectedCL):
  """Represents suspected cl that causes failures on Chromium waterfall builds.

  'Wf' is short for waterfall.
  """

  # The dict of builds in which the suspected CL caused some breakage.
  # The dict will look like:
  # {
  #     'm1/b1/123': {
  #         'failure_type': 'compile',
  #         'failures': None,
  #         'status': CORRECT,
  #         'approaches': [HEURISTIC, TRY_JOB],
  #         'top_score': 5
  #     },
  #     'm2/b2/234': {
  #         'failure_type': 'test',
  #         'failures': {
  #             's1': ['t1', 't2']
  #         },
  #         'status': CORRECT,
  #         'approachES': [HEURISTIC, TRY_JOB],
  #         'top_score': None
  #     },
  #     {
  #         'failure_type': 'test',
  #         'failures': {
  #             's1': ['t3']
  #         },
  #         'status': INCORRECT,
  #         'approaches': [HEURISTIC],
  #         'top_score': 2
  #     },
  #     {
  #         'failure_type': 'test',
  #         'failures': {
  #             's2': []
  #         },
  #         'status': INCORRECT,
  #         'approaches': [HEURISTIC],
  #         'top_score': 1
  #     }
  # }
  builds = ndb.JsonProperty(indexed=False, compressed=True)

  # Is the suspected CL the culprit or not.
  # If not triaged, the status would be None.
  # Other possible status are: suspected_cl_status.CORRECT,
  # suspected_cl_status.INCORRECT, suspected_cl_status.PARTIALLY_CORRECT and
  # suspected_cl_status.PARTIALLY_TRIAGED.
  status = ndb.IntegerProperty(indexed=True, default=None)

  # From which approach do we get this suspected CL:
  # analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB or both.
  approaches = ndb.IntegerProperty(indexed=True, repeated=True)

  # Failure type: failure_type.COMPILE, failure_type.TEST,
  # and if a CL caused a compile failure and another test failure,
  # the failure_type would be both.
  failure_type = ndb.IntegerProperty(indexed=True, repeated=True)

  @classmethod
  def Create(cls, repo_name, revision, commit_position):  # pragma: no cover
    instance = cls(key=cls._CreateKey(repo_name, revision))
    instance.repo_name = repo_name
    instance.revision = revision
    instance.commit_position = commit_position
    instance.builds = {}
    return instance

  def GetBuildInfo(self, master_name, builder_name, build_number):
    build_key = BaseBuildModel.CreateBuildKey(master_name, builder_name,
                                              build_number)
    return self.builds.get(build_key)

  def GetCulpritLink(self):
    return ('https://analysis.chromium.org/waterfall/culprit?key=%s' %
            self.key.urlsafe())

  def GenerateRevertReason(self,
                           build_id,
                           commit_position,
                           revision,
                           sample_step_name=None):
    sample_build = build_id.split('/')
    sample_build_url = buildbot.CreateBuildbucketUrl(*sample_build)
    return textwrap.dedent("""
          Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
          culprit for failures in the build cycles as shown on:
          https://analysis.chromium.org/waterfall/culprit?key=%s\n
          Sample Failed Build: %s\n
          Sample Failed Step: %s""") % (commit_position or revision,
                                        self.key.urlsafe(), sample_build_url,
                                        sample_step_name)
