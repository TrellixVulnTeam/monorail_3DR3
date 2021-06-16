# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import hashlib
import json
import os
import pickle
import re
import subprocess
import zlib

from google.appengine.ext import ndb

from scripts import crash_iterator
from scripts.delta_test import delta_util
from scripts.run_predator import GetCulpritsOnRevision
from libs.cache_decorator import Cached
from local_libs.local_cache import LocalCache  # pylint: disable=W


_CRASH_URL_PATTERN = re.compile(r'.*result-feedback\?key=(\w*)')
# TODO(crbug.com/662540): Add unittests.


class Delta(object):  # pragma: no cover.
  """Stands for delta between two results.

  Note, the 2 results should be the same kind and have the same structure.
  """

  def __init__(self, result1, result2):
    self._result1 = result1
    self._result2 = result2
    self._delta_dict = None
    self._delta_dict_str = None

  @property
  def delta_dict(self):
    """Dict representation of delta.

    Returns:
    A dict. For example, for Culprit result, the delta dict is like below:
    {
        'suspected_project': ('chromium', 'chromium-v8'),
        'suspected_components': (['Blink>API'], ['Internal']),
        'regression_range': (['52.0.1200.1', '52.0.1200.3'], None)
    }
    """
    if self._delta_dict:
      return self._delta_dict

    self._delta_dict = {}
    result1 = self._result1.ToDicts()[0] if self._result1 else {'found': False}
    result2 = self._result2.ToDicts()[0] if self._result2 else {'found': False}
    keys = (set(result1.keys()) if result1 else set() |
            set(result2.keys()) if result2 else set())
    for key in keys:
      value1 = result1.get(key)
      value2 = result2.get(key)
      if key == 'suspected_cls':
        for value in [value1, value2]:
          if not value:
            continue

          for cl in value:
            cl['confidence'] = round(cl['confidence'], 2)

        url_list1 = [suspect['url'] for suspect in value1 or []]
        url_list2 = [suspect['url'] for suspect in value2 or []]
        if url_list1 != url_list2:
          self._delta_dict[key] = (value1, value2)
      elif value1 != value2:
        self._delta_dict[key] = (value1, value2)

    return self._delta_dict

  def ToDict(self):
    return self.delta_dict

  def __str__(self):
    return json.dumps(self.delta_dict, indent=2, sort_keys=True)

  def __bool__(self):
    return bool(self.delta_dict)

  def __nonzero__(self):
    return self.__bool__()


def GetDeltaForTwoSetsOfResults(set1, set2):  # pragma: no cover.
  """Gets delta from two sets of results.

  Set1 and set2 are dicts mapping id to result.
  Results are a list of (message, matches, component_name, cr_label)
  Returns a list of delta results (results1, results2).
  """
  if set1 is None or set2 is None:
    return {}

  deltas = {}
  for result_id, result1 in set1.iteritems():
    # Even when the command are exactly the same, it's possible that one set is
    # loaded from local result file, another is just queried from database,
    # sometimes some crash results would get deleted.
    if result_id not in set2:
      continue

    result2 = set2[result_id]
    if not result1 and not result2:
      continue

    delta = Delta(result1, result2)
    if delta:
      deltas[result_id] = delta

  return deltas


def GetDeltaForCrashes(crashes, git_hash1, git_hash2, client_id, app_id,
                       verbose=False):  # pragma: no cover.
  head_branch_name = subprocess.check_output(
      ['git', 'rev-parse', '--abbrev-ref', 'HEAD']).replace('\n', '')
  try:
    result1 = GetCulpritsOnRevision(crashes, git_hash1, client_id,
                                    app_id, verbose=verbose)
    result2 = GetCulpritsOnRevision(crashes, git_hash2, client_id,
                                    app_id, verbose=verbose)
  finally:
    # Switch back to the original revision.
    with open(os.devnull, 'w') as null_handle:
      subprocess.check_call(['git', 'checkout', head_branch_name],
                            stdout=null_handle, stderr=null_handle)

  # Compute delta between 2 versions of culprit results for this batch.
  return GetDeltaForTwoSetsOfResults(result1, result2)


def GetTriageResultsFromCrashes(crashes):  # pragma: no cover.
  """Check those triaged crash in ``crashes`` and return the triaged culprits.

  Args:
    crashes (dict): A dict mapping ``crash_id`` to ``CrashAnalysis`` entities.

  Returns:
    A dict mapping from ``crash_id`` to its culprit results, like culprit_cls,
    culprit_regression_range or culprit_components.
  """
  triage_results = {}
  for crash_id, crash in crashes.iteritems():
    triage_result = {}
    if crash.culprit_cls:
      triage_result['culprit_cls'] = crash.culprit_cls
    if crash.culprit_regression_range:
      triage_result[
          'culprit_regression_range'] = crash.culprit_regression_range
    if crash.culprit_components:
      triage_result['culprit_components'] = crash.culprit_components

    triage_results[crash_id] = triage_result

  return triage_results


def _ReadCrashesFromTestset(testset_path, separator):  # pragma: no cover.
  """Reads crashes from csv/tsv/etc. testset file.

  Args:
    testset_path (str): file path to read the testset file.
    separator (str): the separator used in the file, e.g. tab for .tsv files.

  Returns:
    A dict mapping crash_id(urlsafe encoding of a CrashAnalysis model) to
    its *CrashAnalysis model.
  """
  crashes = {}
  with open(testset_path) as f:
    for line in f.readlines():
      if not line:
        continue

      line_parts = line.split(separator)
      match = _CRASH_URL_PATTERN.match(line_parts[0])
      if match:
        crash_id = match.group(1)
        crash = ndb.Key(urlsafe=crash_id).get()
        if crash:
          crashes[crash_id] = crash

  return crashes


def ReadCrashesFromTsvTestset(testset_path):  # pragma: no cover.
  """Read crashes from tsv testset file."""
  return _ReadCrashesFromTestset(testset_path, '\t')


def ReadCrashesFromCsvTestset(testset_path):  # pragma: no cover.
  """Reads crashes from csv testset file."""
  return _ReadCrashesFromTestset(testset_path, ',')


def DeltaKeyGenerator(func, args, kwargs, namespace=None):  # pragma: no cover.
  kwargs_copy = copy.deepcopy(kwargs)
  if 'verbose' in kwargs_copy:
    del kwargs_copy['verbose']

  encoded_params = hashlib.md5(pickle.dumps([args, kwargs_copy])).hexdigest()
  prefix = namespace or '%s.%s' % (func.__module__, func.__name__)
  return '%s-%s' % (prefix, encoded_params)


@Cached(LocalCache(), namespace='Delta-Results', expire_time=10*60*60*24,
        key_generator=DeltaKeyGenerator)
def EvaluateDelta(git_hash1, git_hash2,
                  client_id, app_id,
                  start_date, end_date, batch_size, max_n,
                  property_values=None, verbose=False):  # pragma: no cover.
  """Evaluates delta between git_hash1 and git_hash2 on query results.

  Args:
    git_hash1 (str): A git hash of predator repository.
    git_hash2 (str): A git hash of predator repository.
    start_date (str): Run delta test on testcases after (including)
      the start_date, format should be '%Y-%m-%d'.
    end_date (str): Run delta test on testcases before (not including)
      the end_date, format should be '%Y-%m-%d'.
    client_id (CrashClient): Possible values are 'fracas', 'cracas',
      'cluterfuzz'.
    app_id (str): Appengine app id to query.
    batch_size (int): Size of a batch that can be queried at one time.
    max_n: (int): Maximum total number of crashes.
    property_values (dict): Property values to query.
    batch_size (int): The size of crashes that can be queried at one time.
    verbose (bool): If True, print all the predator results.

  Return:
    (deltas, triage_results, crash_count).
    deltas (dict): Mappings id to delta for each culprit value.
    triage_results (dict): Dict mapping crash_id to its triaged results.
    crash_count (int): Total count of all the crashes.
  """
  deltas = {}
  triage_results = {}

  batch_size = min(batch_size, max_n)
  crash_count = 0
  # Iterate batches of crash informations.
  for crashes in crash_iterator.CachedCrashIterator(
      client_id, app_id, property_values=property_values,
      start_date=start_date, end_date=end_date,
      batch_size=batch_size, batch_run=True):
    # Truncate crashes and make it contain at most max_n crashes.
    crashes = {crash.key.urlsafe(): crash for crash in crashes}
    if crash_count + len(crashes) > max_n:
      crashes = {crash_id: crashes[crash_id]
                 for crash_id in crashes.keys()[:(max_n - crash_count)]}

    crash_count += len(crashes)
    batch_delta = GetDeltaForCrashes(crashes, git_hash1, git_hash2,
                                     client_id, app_id, verbose=verbose)
    # Print the deltas of the current batch.
    print '========= Delta of this batch ========='
    delta_util.PrintDelta(batch_delta, len(crashes), client_id, app_id)
    deltas.update(batch_delta)
    triage_results.update(GetTriageResultsFromCrashes(crashes))

    if crash_count >= max_n:
      break

  return deltas, triage_results, crash_count


def EvaluateDeltaOnTestSet(git_hash1, git_hash2,
                           client_id, app_id,
                           testset_path, verbose=False):  # pragma: no cover
  """Evaluates delta between git_hash1 and git_hash2 on a set of Testcases.

  Args:
    git_hash1 (str): A git hash of predator repository.
    git_hash2 (str): A git hash of predator repository.
    client_id (CrashClient): Possible values are 'fracas', 'cracas',
      'cluterfuzz'.
    app_id (str): Appengine app id to query.
    testset_path (str): file path to read the tsv testset file.
    verbose (bool): If True, print all the predator results.

  Return:
    (deltas, triage_results, crash_count).
    deltas (dict): Mappings id to delta for each culprit value.
    triage_results (dict): Dict mapping crash_id to its triaged results.
    crash_count (int): Total count of all the crashes.
  """
  crashes = ReadCrashesFromTsvTestset(testset_path)
  delta = GetDeltaForCrashes(crashes, git_hash1, git_hash2,
                             client_id, app_id, verbose=verbose)

  # Print delta of the current batch.
  print '========= Delta of the test set ========='
  delta_util.PrintDelta(delta, len(crashes), client_id, app_id)

  return delta, GetTriageResultsFromCrashes(crashes), len(crashes)
