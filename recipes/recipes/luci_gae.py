# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'infra_checkout',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/platform',
  'recipe_engine/properties',
]

LUCI_GAE_PATH_IN_INFRA = 'infra/go/src/go.chromium.org/gae'


def RunSteps(api):
  co = api.infra_checkout.checkout('luci_gae',
                                   patch_root=LUCI_GAE_PATH_IN_INFRA)
  is_presubmit = 'presubmit' in api.buildbucket.builder_name.lower()
  if is_presubmit:
    co.commit_change()
  co.gclient_runhooks()

  co.ensure_go_env()
  if is_presubmit:
    co.run_presubmit_in_go_env()
  else:
    co.go_env_step('go', 'build', 'go.chromium.org/gae/...')
    co.go_env_step('go', 'test', 'go.chromium.org/gae/...')
    if not api.platform.is_win:
      # Windows bots do not have gcc installed at the moment.
      co.go_env_step('go', 'test', '-race', 'go.chromium.org/gae/...',
                     name='go test -race')


def GenTests(api):
  yield (
    api.test('luci_gae') +
    api.buildbucket.ci_build(
        'infra', 'ci', 'luci-gae-linux64',
        git_repo="https://chromium.googlesource.com/infra/infra",
        revision='1'*40) +
    # Sadly, hacks in gclient required to patch non-main git repo in a solution
    # requires revsion as a property :(
    api.properties(revision='1'*40)
  )
  yield (
    api.test('presubmit_try_job') +
    api.buildbucket.try_build(
        'infra', 'try', 'Luci-GAE Presubmit',
        git_repo='https://chromium.googlesource.com/infra/luci/gae',
        change_number=607472,
        patch_set=2,
    ) + api.step_data('presubmit', api.json.output([[]]))
  )
