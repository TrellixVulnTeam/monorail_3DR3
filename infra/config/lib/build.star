# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions and constants related to build.git used by all modules."""

load('//lib/infra.star', 'infra')


def poller():
  """Defines a gitiles poller polling build.git repo."""
  return luci.gitiles_poller(
      name = 'build-gitiles-trigger',
      bucket = 'ci',
      repo = 'https://chromium.googlesource.com/chromium/tools/build',
  )


def recipe(name, use_bbagent=True):
  """Defines a recipe hosted in the build.git recipe bundle."""
  recipe = name
  if use_bbagent:
    name += "-bbagent"
  else:
    name += "-kitchen"

  return luci.recipe(
      name = name,
      recipe = recipe,
      cipd_package = 'infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build',
      use_bbagent = use_bbagent,
  )


def presubmit(
      *,

      name,
      cq_group,
      repo_name,  # e.g. 'infra' or 'luci_py', as expected by the recipe
      run_hooks=True,
      timeout_s=480,

      os=None,
      experiment_percentage=None
  ):
  """Defines a try builder that runs 'run_presubmit' recipe."""
  props = {
      'repo_name': repo_name,
      '$depot_tools/presubmit': {
          'runhooks': run_hooks,
          'timeout_s': timeout_s,
      }
  }
  luci.builder(
      name = name,
      bucket = 'try',
      executable = build.recipe('presubmit'),
      properties = props,
      service_account = infra.SERVICE_ACCOUNT_TRY,
      dimensions = {
          'os': os or 'Ubuntu-16.04',
          'cpu': 'x86-64',
          'pool': 'luci.flex.try',
      },
      task_template_canary_percentage = 30,
  )
  luci.cq_tryjob_verifier(
      builder = name,
      cq_group = cq_group,
      disable_reuse = True,
      experiment_percentage = experiment_percentage,
  )


build = struct(
    poller = poller,
    recipe = recipe,
    presubmit = presubmit,
)
