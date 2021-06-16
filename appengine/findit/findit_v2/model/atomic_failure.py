# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from findit_v2.model.gitiles_commit import Culprit
from findit_v2.model.gitiles_commit import Suspect
from findit_v2.model.luci_build import LuciFailedBuild


class FileInFailureLog(ndb.Model):
  """Class for a file mentioned in failure log."""

  # normalized file path.
  path = ndb.StringProperty(indexed=False)

  # Mentioned line numbers of the file in failure log.
  line_numbers = ndb.IntegerProperty(repeated=True, indexed=False)


class AtomicFailure(ndb.Model):
  """Base Class for an atom failure.

  Atom failure means failures that cannot be further divided.
  - In compile failure atom failure is a failed compile target.
  - In test failure atom failure is a failed test.

  Key to an AtomicFailure entity is
  Key(LuciFailedBuild, <build_id>,
      <AtomicFailure>, 'step_ui_name@atomic_failure').
  """
  # Id of the build in which this atom failure occurred the first time in
  # a sequence of consecutive failed builds.
  # For example, if a test passed in build 100, and failed in builds 101 - 105,
  # then for atom failures of builds 101 - 105, their first_failed_build_id
  # will all be id of build 101.
  # First_failed_build_id can also be used to find the analysis on the
  # failure: analysis only runs for the first time failures, so using the
  # first_failed_build_id can get to the analysis.
  first_failed_build_id = ndb.IntegerProperty()

  # Id of the build in which this atom run (targets or test) was a pass and
  # since the next build, it kept not passing (can failed, not run, or end
  # with other status).
  last_passed_build_id = ndb.IntegerProperty()

  # Id of the first build forming the group.
  # Whether or how to group failures differs from project to project.
  # So this value could be empty.
  failure_group_build_id = ndb.IntegerProperty()

  # Key to the culprit commit found by rerun based analysis.
  # There should be only one culprit for each failure.
  culprit_commit_key = ndb.KeyProperty(Culprit)
  # Key to the suspected commit found by heuristic analysis.
  # There could be multiple suspects found for each failure.
  suspect_commit_key = ndb.KeyProperty(Suspect, repeated=True)

  # Optional information for heuristic analysis.
  # Mentioned files in failure log for the failure.
  files = ndb.LocalStructuredProperty(FileInFailureLog, repeated=True)

  # Arbitrary properties of the failure.
  properties = ndb.JsonProperty(compressed=True)

  @property
  def build_id(self):
    """Gets the id of the build that this failure belongs to."""
    return self.key.parent().id()

  @property
  def step_ui_name(self):
    """Full step name of the failure."""
    entity_id = self.key.id()
    id_parts = entity_id.split('@', 1)
    assert len(id_parts) == 2, 'Atomic Failure ID is in wrong format: %s' % (
        entity_id)
    return id_parts[0]

  @classmethod
  def Create(cls,
             failed_build_key,
             failure_id,
             first_failed_build_id=None,
             last_passed_build_id=None,
             failure_group_build_id=None,
             files=None,
             properties=None):  # pragma: no cover
    instance = cls(
        parent=failed_build_key,
        id=failure_id,
        first_failed_build_id=first_failed_build_id,
        last_passed_build_id=last_passed_build_id,
        failure_group_build_id=failure_group_build_id,
        properties=properties)

    files_objs = []
    if files:
      for path, line_numbers in files.iteritems():
        files_objs.append(
            FileInFailureLog(path=path, line_numbers=line_numbers))
    instance.files = files_objs
    return instance

  @classmethod
  def GetMergedFailureKey(cls, failure_entities, referred_build_id,
                          step_ui_name, atomic_failures):
    """Gets an existing failure key for a new failure to merge into.

     Looks for a failure which is the same as the new failure and has actually
     been analyzed.

     Args:
       failure_entities (dict): map of build_ids to failures of that build.
       referred_build_id (int): Id of a build which likely has a failure for the
         new failure to merge into.
       step_ui_name (str): Step name of the new failure.
       atomic_failures (frozenset): Identifier of the new failure. To find the
         failure to merge into, that failure should have the same step name and
         failure identifier as this new failure.
     """

    def get_failures_by_build_id(build_id):
      """Gets failure entities by build id."""
      build_key = ndb.Key(LuciFailedBuild, build_id)
      return cls.query(ancestor=build_key).fetch()

    assert referred_build_id, (
        'Missing referred_build_id when looking for merged failure key.')
    assert isinstance(
        atomic_failures,
        (type(None), frozenset)), ('Unexpected atomic_failures type: {}'.format(
            type(atomic_failures)))

    if referred_build_id not in failure_entities:
      failure_entities[referred_build_id] = (
          get_failures_by_build_id(referred_build_id))

    for failure in failure_entities[referred_build_id]:
      if (failure.step_ui_name == step_ui_name and
          failure.GetFailureIdentifier() == atomic_failures):
        # Found the same failure in the referred build.
        if (failure.build_id == failure.first_failed_build_id and
            failure.build_id == failure.failure_group_build_id):
          # This failure is the first failure on its builder and is not merged
          # into another failure on other builders either. This failure should
          # have been actually analyzed.
          return failure.key
        return failure.merged_failure_key
    return None

  def GetFailureIdentifier(self):
    """Returns the identifier for the failure within its step.

    Returns:
    (frozenset): information to identify a failure.
      - For compile failures, it'll be the output_targets.
      - For test failures, it'll be the frozenset([test_name]).

    """
    raise NotImplementedError
