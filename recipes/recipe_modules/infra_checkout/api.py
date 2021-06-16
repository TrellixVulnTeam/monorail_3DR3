# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib

from recipe_engine import recipe_api

class InfraCheckoutApi(recipe_api.RecipeApi):
  """Stateless API for using public infra gclient checkout."""

  # Named cache shared across builders using public infra gclient checkout.
  PUBLIC_NAMED_CACHE = 'infra_gclient_with_go'
  # Ditto but for builders which use internal gclient checkout.
  INTERNAL_NAMED_CACHE = 'infra_internal_gclient_with_go'

  def checkout(self, gclient_config_name,
               patch_root=None,
               path=None,
               internal=False,
               named_cache=None,
               **kwargs):
    """Fetches infra gclient checkout into a given path OR named_cache.

    Arguments:
      * gclient_config_name (string) - name of gclient config.
      * patch_root (path or string) - path **inside** infra checkout to git repo
        in which to apply the patch. For example, 'infra/luci' for luci-py repo.
        If None (default), no patches will be applied.
      * path (path or string) - path to where to create/update infra checkout.
        If None (default) - path is cache with customizable name (see below).
      * internal (bool) - by default, False, meaning infra gclient checkout
          layout is assumed, else infra_internal.
          This has an effect on named_cache default and inside which repo's
          go corner the ./go/env.py command is run.
      * named_cache - if path is None, this allows to customize the name of the
        cache. Defaults to PUBLIC_NAMED_CACHE or INTERNAL_NAMED_CACHE, depending
        on `internal` argument value.
        Note: your cr-buildbucket.cfg should specify named_cache for swarming to
          prioritize bots which actually have this cache populated by prior
          runs. Otherwise, using named cache isn't particularly useful, unless
          your pool of builders is very small.
      * kwargs - passed as is to bot_update.ensure_checkout.

    Returns:
      a Checkout object with commands for common actions on infra checkout.
    """
    assert gclient_config_name, gclient_config_name
    if named_cache is None:
      named_cache = (self.INTERNAL_NAMED_CACHE if internal else
                     self.PUBLIC_NAMED_CACHE)
    path = path or self.m.path['cache'].join(named_cache)
    self.m.file.ensure_directory('ensure builder dir', path)

    with self.m.context(cwd=path):
      self.m.gclient.set_config(gclient_config_name)
      bot_update_step = self.m.bot_update.ensure_checkout(
          patch_root=patch_root, **kwargs)

    class Checkout(object):
      def __init__(self, m):
        self.m = m
        self._go_env = None
        self._go_env_prefixes = None

      @property
      def path(self):
        return path

      @property
      def bot_update_step(self):
        return bot_update_step

      @property
      def patch_root_path(self):
        assert patch_root
        return path.join(patch_root)

      @staticmethod
      def commit_change():
        assert patch_root
        with self.m.context(cwd=path.join(patch_root)):
          self.m.git(
              '-c', 'user.email=commit-bot@chromium.org',
              '-c', 'user.name=The Commit Bot',
              'commit', '-a', '-m', 'Committed patch',
              name='commit git patch')

      @staticmethod
      def get_changed_files():
        assert patch_root
        # Grab a list of changed files.
        with self.m.context(cwd=path.join(patch_root)):
          result = self.m.git(
              'diff', '--name-only', 'HEAD', 'HEAD~',
              name='get change list',
              stdout=self.m.raw_io.output())
        files = result.stdout.splitlines()
        if len(files) < 50:
          result.presentation.logs['change list'] = sorted(files)
        else:
          result.presentation.logs['change list is too long'] = (
              '%d files' % len(files))
        return set(files)

      @staticmethod
      def gclient_runhooks():
        with self.m.context(cwd=path):
          self.m.gclient.runhooks()

      @contextlib.contextmanager
      def go_env(self):
        self.ensure_go_env()
        with self.m.context(
            cwd=self.path,
            env=self._go_env,
            env_prefixes=self._go_env_prefixes):
          yield

      def ensure_go_env(self):
        if self._go_env is not None:
          return  # already did this

        with self.m.context(cwd=self.path):
          where = 'infra_internal' if internal else 'infra'
          step = self.m.python(
              'init infra go env',
              path.join(where, 'go', 'bootstrap.py'),
              [self.m.json.output()],
              venv=True,
              infra_step=True,
              step_test_data=lambda: self.m.json.test_api.output({
                  'go_version': '1.66.6',
                  'env': {
                      'GOROOT': str(path.join('golang', 'go')),
                      'GOPATH': str(path.join(where, 'go')),
                  },
                  'env_prefixes': {
                      'PATH': [
                          str(path.join('golang', 'go')),
                          str(path.join(where, 'go', 'bin')),
                      ],
                  },
              }))

        out = step.json.output
        step.presentation.step_text += 'Using go %s' % (out.get('go_version'),)

        self._go_env = out['env']
        self._go_env_prefixes = out['env_prefixes']

      # TODO(vadimsh): Get rid of this in favor of using `with go_env()`.
      @staticmethod
      def go_env_step(*args, **kwargs):
        # name lazily defaults to first two args, like "go test".
        name = kwargs.pop('name', None) or ' '.join(map(str, args[:2]))
        with self.m.context(cwd=path):
          where = 'infra_internal' if internal else 'infra'
          return self.m.python(name, path.join(where, 'go', 'env.py'),
                               args, venv=True, **kwargs)

      # TODO(vadimsh): Get rid of this in favor of using `with go_env()`.
      @staticmethod
      def run_presubmit_in_go_env():
        assert patch_root
        assert self.m.runtime.is_luci
        revs = self.m.bot_update.get_project_revision_properties(patch_root)
        upstream = bot_update_step.json.output['properties'].get(revs[0])
        gerrit_change = self.m.buildbucket.build.input.gerrit_changes[0]
        # The presubmit must be run with proper Go environment.
        presubmit_cmd = [
          'vpython',
          self.m.presubmit.presubmit_support_path,
          '--root', path.join(patch_root),
          '--commit',
          '--verbose', '--verbose',
          '--issue', gerrit_change.change,
          '--patchset', gerrit_change.patchset,
          '--gerrit_url', 'https://' + gerrit_change.host,
          '--gerrit_fetch',
          '--upstream', upstream,

          '--skip_canned', 'CheckTreeIsOpen',
          '--skip_canned', 'CheckBuildbotPendingBuilds',
        ]
        with self.m.context(env={'PRESUBMIT_BUILDER': '1'}):
          Checkout.go_env_step(*presubmit_cmd, name='presubmit')

    return Checkout(self.m)
