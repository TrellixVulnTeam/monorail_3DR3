# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/osx_sdk',
  'infra_checkout',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/platform',
  'recipe_engine/properties',
]

PROPERTIES = {
  'GOARCH': Property(
    default=None,
    kind=str,
    help="set GOARCH environment variable for go build+test"),
  'run_integration_tests': Property(
    default=False,
    kind=bool,
    help='Whether to run integration tests',
  ),
}

LUCI_GO_PATH_IN_INFRA = 'infra/go/src/go.chromium.org/luci'


def RunSteps(api, GOARCH, run_integration_tests):
  co = api.infra_checkout.checkout('luci_go', patch_root=LUCI_GO_PATH_IN_INFRA)
  is_presubmit = 'presubmit' in api.buildbucket.builder_name.lower()
  if is_presubmit:
    co.commit_change()
  co.gclient_runhooks()


  env = {}
  if GOARCH is not None:
    env['GOARCH'] = GOARCH
  if run_integration_tests:
    env['INTEGRATION_TESTS'] = '1'

  with api.context(env=env), api.osx_sdk('mac'):
    co.ensure_go_env()
    if is_presubmit:
      co.run_presubmit_in_go_env()
    else:
      co.go_env_step('go', 'build', 'go.chromium.org/luci/...')
      co.go_env_step('go', 'test', 'go.chromium.org/luci/...')
      if not api.platform.is_win:
        # Windows bots do not have gcc installed at the moment.
        co.go_env_step('go', 'test', '-race', 'go.chromium.org/luci/...',
                       name='go test -race')


def GenTests(api):
  for plat in ('linux', 'mac', 'win'):
    yield (
      api.test('luci_go_%s' % plat) +
      api.platform(plat, 64) +
      api.buildbucket.ci_build(
          'infra', 'ci', 'luci-gae-trusty-64',
          git_repo="https://chromium.googlesource.com/infra/infra",
          revision='1'*40) +
      # Sadly, hacks in gclient required to patch non-main git repo in
      # a solution requires revision as a property :(
      api.properties(revision='1'*40)
    )

  yield (
    api.test('presubmit_try_job') +
    api.buildbucket.try_build(
        'infra', 'try', 'Luci-go Presubmit', change_number=607472, patch_set=2,
    ) + api.step_data('presubmit', api.json.output([[]]))
  )

  yield (
    api.test('override_GOARCH') +
    api.platform('linux', 64) +
    api.buildbucket.try_build(
        'infra', 'try', 'luci-go-trusty-64',
        git_repo='https://chromium.googlesource.com/infra/luci/luci-go',
        change_number=607472,
        patch_set=2,
    ) + api.properties(GOARCH='386')
  )

  yield (
    api.test('integration_tests') +
    api.buildbucket.try_build(
        'infra', 'try', 'integration_tests', change_number=607472, patch_set=2,
    ) +
    api.properties(run_integration_tests=True)
  )
