# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'infra_checkout',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/platform',
    'recipe_engine/python',
    'recipe_engine/runtime',
    'recipe_engine/step',
]


def RunSteps(api):
  co = api.infra_checkout.checkout(gclient_config_name='infra',
                                   patch_root='infra')
  co.gclient_runhooks()
  co.ensure_go_env()
  _ = co.bot_update_step  # coverage...
  if not api.platform.is_win:
    co.go_env_step('echo', '$GOPATH', name='echo')
  with co.go_env():
    api.step('go test', ['go', 'test', 'infra/...'])
  with api.context(cwd=co.patch_root_path):
    api.python('python tests', 'test.py', ['test', 'infra'])
  with api.context(cwd=co.path):
    api.python('dirs', script='''
        import sys, os
        print '\n'.join(os.listdir('./'))
    ''')


def GenTests(api):
  for plat in ('linux', 'mac', 'win'):
    yield (
        api.test(plat) +
        api.platform(plat, 64) +
        api.runtime(is_luci=True, is_experimental=False) +
        api.buildbucket.ci_build(
            project='infra',
            bucket='ci',
            git_repo='https://chromium.googlesource.com/infra/infra',
        )
    )
