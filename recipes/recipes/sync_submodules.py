# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'sync_submodules',
  'recipe_engine/properties',
  'recipe_engine/runtime',
]


DEFAULT_SOURCE_REPO = 'https://chromium.googlesource.com/chromium/src'

PROPERTIES = {
  'disable_path_prefix': Property(default=False),
}

def RunSteps(api, disable_path_prefix):
  source_repo = api.properties.get('source_repo', DEFAULT_SOURCE_REPO)
  source_repo_checkout_name = api.properties.get('source_repo_checkout_name',
                                                 None)
  dest_repo = api.properties.get('dest_repo', source_repo + '/codesearch')
  extra_submodules = [
      x for x in api.properties.get('extra_submodules', '').split(',') if x]
  deps_path_prefix = api.properties.get('deps_path_prefix', None)
  api.sync_submodules(source_repo, source_repo_checkout_name,
                      dest_repo, extra_submodules=extra_submodules,
                      deps_path_prefix=deps_path_prefix,
                      disable_path_prefix=disable_path_prefix)


def GenTests(api):
  yield api.test('basic') + api.properties(buildername='foo_builder')
  yield (
      api.test('basic_experimental') +
      api.properties(buildername='foo_builder') +
      api.step_data('git diff-index', retcode=1) +
      api.runtime(is_luci=True, is_experimental=True))
  yield (
      api.test('basic_with_diff') +
      api.properties(buildername='foo_builder') +
      api.step_data('git diff-index', retcode=1) +
      api.runtime(is_luci=True, is_experimental=False))
  yield (
      api.test('basic_with_diff_failure') +
      api.properties(buildername='foo_builder') +
      api.step_data('git diff-index', retcode=2) +
      api.runtime(is_luci=True, is_experimental=False))
  yield (
      api.test('with_one_extra_submodule') +
      api.properties(
          buildername='foo_builder',
          extra_submodules='src/out=https://www.example.com') +
      api.runtime(is_luci=True, is_experimental=False))
  yield (
      api.test('with_two_extra_submodules') +
      api.properties(
          buildername='foo_builder',
          extra_submodules=(
              'src/foo=https://www.foo.com,src/bar=http://www.bar.com')) +
      api.runtime(is_luci=True, is_experimental=False))
  yield (
      api.test('basic_with_prefix') +
      api.properties(
          source='https://chromium.googlesource.com/external/webrtc',
          buildername='foo_builder',
          deps_path_prefix='src/') +
      api.runtime(is_luci=True, is_experimental=False))
  yield (
      api.test('basic_with_prefix_disabled') +
      api.properties(
          source='https://chromium.googlesource.com/external/webrtc',
          buildername='foo_builder',
          deps_path_prefix='src/',
          disable_path_prefix=True) +
      api.runtime(is_luci=True, is_experimental=False))
  yield (
      api.test('with_source_repo_checkout_name') +
      api.properties(
          source_repo='https://chromium.googlesource.com/foo_remote_name',
          source_repo_checkout_name='foo_local_name',
          buildername='foo_builder') +
      api.runtime(is_luci=True, is_experimental=False))
