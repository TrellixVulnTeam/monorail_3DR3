# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import json
import os
import pickle
import subprocess
import sys
import threading
import traceback
import zlib

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
_ROOT_DIR = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), os.path.pardir)
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)
from local_libs import script_util
script_util.SetUpSystemPaths(_ROOT_DIR)

from local_libs.local_cache import LocalCache

from analysis.type_enums import CrashClient
from app.common.crash_pipeline import PredatorForClientID
from app.common.model import crash_analysis
from app.common.model.crash_config import CrashConfig
from libs.cache_decorator import Cached
from local_libs import remote_api
from local_libs.git_checkout.local_git_repository import LocalGitRepository
from scripts import setup

# TODO(crbug.com/662540): Add unittests.


_TOP_N_FRAMES = 7

try:
  os.makedirs(setup.PREDATOR_RESULTS_DIRECTORY)
except Exception:  # pragma: no cover.
  pass

_CHROMIUM_REPO_DEPS_TEMPLATE = (
    'https://chromium.googlesource.com/chromium/src.git/+/%s/DEPS')

_LOCAL_CHROMIUM_REPO = os.path.join(
    os.path.expanduser('~'),
    '.local_checkouts/chromium.googlesource.com/chromium/src.git')


def StoreResults(crash, client_id, app_id, id_to_culprits, lock, config,
                 max_retry=3, verbose=False):  # pragma: no cover.
  """Stores predator result of crash into id_to_culprits dict."""
  crash_id = crash.key.urlsafe()
  feedback_url = crash_analysis._FEEDBACK_URL_TEMPLATE % (
      app_id + '.appspot.com', client_id, crash_id)
  retry = 0
  while retry < max_retry:
    try:
      predator = PredatorForClientID(client_id, LocalGitRepository, config)
      crash.ReInitialize(predator)
      culprit = predator.FindCulprit(crash)
      with lock:
        id_to_culprits[crash_id] = culprit
        if verbose:
          print '\n\nCrash:', feedback_url
          print json.dumps(culprit.ToDicts()[0]
                           if culprit else {'found': False},
                           indent=4, sort_keys=True)

      break
    except Exception:
      with lock:
        id_to_culprits[crash_id] = None
        print '\n\nCrash:', feedback_url
        print traceback.format_exc()

      retry += 1


def GetCulprits(crashes, client_id, app_id, verbose=False):  # pragma: no cover.
  """Run ``CrashAnalysis`` entities in parallel and returns culprits.

  Args:
    crashes (list): A list of ``CrashAnalysis`` entities to run Predator on and
      get culprit results.
    client_id (CrashClient): One of CrashClient.FRACAS, CrashClient.CRACAS and
      CrashClient.CLUSTERFUZZ.
    app_id (str): Project id of app engine app.
    verbose (boolean): Whether to print every culprit results or not.

  Returns:
    A dict mapping crash id (urlsafe of entity key for Cracas/Fracas, testcase
    id for Cluterfuzz) to culprit results (dict version of ``Culprit``.)
  """
  # Enable remote access to app engine services.
  remote_api.EnableRemoteApi(app_id)

  tasks = []
  lock = threading.Lock()
  config = CrashConfig.Get()
  id_to_culprits = {}
  for crash in crashes.itervalues():
    tasks.append({
        'function': StoreResults,
        'args': [crash, client_id, app_id, id_to_culprits, lock, config],
        'kwargs': {'verbose': verbose}
    })
  script_util.RunTasks(tasks)

  return id_to_culprits


def GetCulpritsOnRevisionKeyGenerator(
    func, args, kwargs,  # pylint: disable=W0613
    namespace=None):  # pragma: no cover.

  crashes = args[0]
  git_hash = args[1]
  crash_keys = [crash.key.urlsafe() for crash in crashes.itervalues()]
  prefix = namespace or '%s.%s' % (func.__module__, func.__name__)
  return '%s-%s' % (
      prefix, hashlib.md5(pickle.dumps({'crash_keys': crash_keys,
                                        'git_hash': git_hash})).hexdigest())


@Cached(LocalCache(), namespace='Predator-Results-On-Revision',
        expire_time=3*60*60*24, key_generator=GetCulpritsOnRevisionKeyGenerator)
def GetCulpritsOnRevision(crashes, git_hash, client_id, app_id,
                          verbose=False):  # pragma: no cover.
  """Runs Predator in subprocess on a revision and returns culprits.

  Args:
    crashes (list): A list of ``CrashAnalysis`` entities to run Predator on and
      get culprit results.
    client_id (CrashClient): One of CrashClient.FRACAS, CrashClient.CRACAS and
      CrashClient.CLUSTERFUZZ.
    app_id (str): Project id of app engine app.
    verbose (boolean): Whether to print every culprit results or not.

  Returns:
    A dict mapping crash id (urlsafe of entity key for Cracas/Fracas, testcase
    id for Cluterfuzz) to culprit results (dict version of ``Culprit``.)
  """
  print '***************************'
  print 'Switching to git %s' % git_hash
  print '***************************'
  with open(os.devnull, 'w') as null_handle:
    subprocess.check_call(
        'cd %s; git checkout %s' % (_SCRIPT_DIR, git_hash),
        stdout=null_handle,
        stderr=null_handle,
        shell=True)

  input_path = os.path.join(setup.PREDATOR_RESULTS_DIRECTORY, 'input')
  output_path = os.path.join(setup.PREDATOR_RESULTS_DIRECTORY, 'output')
  with open(input_path, 'wb') as f:
    f.write(zlib.compress(pickle.dumps(crashes)))

  run_predator_path = os.path.join(_SCRIPT_DIR, 'run-predator.py')
  args = ['python', run_predator_path, '--input-path', input_path,
          '--result-path', output_path, '--client', client_id, '--app', app_id]
  if verbose:
    args.append('--verbose')

  try:
    subprocess.check_call(args)
    # Read culprit results from ``output_path``, which is computed by
    # sub-routine ``run-predator``.
    with open(output_path) as f:
      return pickle.load(f)
  except subprocess.CalledProcessError as e:
    print '\nError running run-predator in child process'
    raise
  except Exception as e:
    print '\nError loading culprit results running sub routine %s: %s' % (
        git_hash, str(e))
    raise
