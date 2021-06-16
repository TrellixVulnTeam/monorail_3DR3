# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implements the source version checking and acquisition logic."""

import functools
import operator
import re

from pkg_resources import parse_version

from .run_script import run_script

from PB.recipe_modules.infra.support_3pp.spec import LT, LE, GT, GE, EQ, NE


def _to_versions(raw_ls_remote_lines, version_join, tag_re):
  """Converts raw ls-remote output lines to a sorted (descending)
  list of (Version, v_str) objects.
  """
  ret = []
  for line in raw_ls_remote_lines:
    _hash, ref = line.split('\t')
    if ref.startswith('refs/tags/'):
      tag = ref[len('refs/tags/'):]
      m = tag_re.match(tag)
      if not m:
        continue

      v_str = m.group(1)
      if version_join:
        v_str = '.'.join(v_str.split(version_join))

      ret.append((parse_version(v_str), v_str))
  return sorted(ret, reverse=True)


# Maps the operator OP(a, b) to the reverse function. For example:
#
#    A < B   maps to   B >= A
#
# This will allow us to use functools.partial to pre-fill the value of B.
FILTER_TO_REVERSE_OP = {
  LT: operator.ge,
  LE: operator.gt,
  GT: operator.le,
  GE: operator.lt,

  # EQ and NE are commutative comparisons, so they map directly to their
  # equivalent function in `operator`.
  EQ: operator.eq,
  NE: operator.ne,
}

def _filters_to_func(filters):
  restrictions = [
    functools.partial(FILTER_TO_REVERSE_OP[f.op], parse_version(f.val))
    for f in filters
  ]
  def _apply_filter(candidate_version):
    for restriction in restrictions:
      if not restriction(candidate_version):
        return False
    return True
  return _apply_filter


def _filter_versions(version_strs, filters):
  if not filters:
    return version_strs
  filt_fn = _filters_to_func(filters)
  return [
    (vers, vers_s)
    for vers, vers_s in version_strs
    if filt_fn(vers)
  ]


def resolve_latest(api, spec):
  """Resolves the latest available version given a ResolvedSpec.

  This usually involves doing network operations, depending on the `source`
  type of the ResolvedSpec.

  Args:
    * api - The ThirdPartyPackagesNGApi's `self.m` module collection.
    * spec (ResolvedSpec) - The spec to resolve.

  Returns (str) the symver for the latest version of this package, e.g.
  '1.2.3'. This should always use '.' as the digit separator.
  """
  # TODO(iannucci): when we can put annotations on nest steps, put the 'resolved
  # version' there.

  method_name, source_method_pb = spec.source_method
  if method_name == 'git':
    # We need to transform the tag_pattern (which is a python format-string
    # lookalike with `%s` in it) into a regex which we can use to scan over the
    # repo's tags.
    tag_re = re.escape(
      source_method_pb.tag_pattern if source_method_pb.tag_pattern else '%s')
    tag_re = '^%s$' % (tag_re.replace('\\%s', '(.*)'),)

    step = api.git('ls-remote', '-t', source_method_pb.repo,
                   stdout=api.raw_io.output(),
                   step_test_data=lambda: api.raw_io.test_api.stream_output(
                     '\n'.join([
                       'hash\trefs/tags/unrelated',
                       'hash\trefs/tags/v1.0.0-a2',
                       'hash\trefs/tags/v1.3.0',
                       'hash\trefs/tags/v1.4.0',
                       'hash\trefs/tags/v1.4.1',
                       'hash\trefs/tags/v1.5.0-rc1',
                     ])))

    versions = _to_versions(
        step.stdout.splitlines(),
        source_method_pb.version_join,
        re.compile(tag_re))

    versions = _filter_versions(
        versions, source_method_pb.version_restriction)

    highest_cmp = parse_version('0')
    highest_str = ''
    for vers, v_str in versions:
      if vers > highest_cmp:
        highest_cmp = vers
        highest_str = v_str

    assert highest_str
    version = highest_str
    api.step.active_result.presentation.step_text = (
      'resolved version: %s' % (version,))

  elif method_name == 'script':
    script = spec.host_dir.join(source_method_pb.name[0])
    args = map(str, source_method_pb.name[1:]) + ['latest']
    version = run_script(api,
      script, *args,
      stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output('2.0.0')
    ).stdout.strip()
    api.step.active_result.presentation.step_text = (
      'resolved version: %s' % (version,))

  elif method_name == 'cipd':
    version = source_method_pb.default_version
    # We don't actually run a real step here, so we can't put the 'resolved
    # version' anywhere :(. See TODO at top.

  else: # pragma: no cover
    assert False, '"latest" version resolution not defined for %r' % method_name

  return version


def fetch_source(api, workdir, spec, version, spec_lookup, ensure_built):
  """Prepares a checkout in `workdir` to build `spec` at `version`.

  Args:
    * api - The ThirdPartyPackagesNGApi's `self.m` module collection.
    * workdir (Workdir) - The working directory object we're going to build the
      spec in. This function will create the checkout in `workdir.checkout`.
    * spec (ResolvedSpec) - The package we want to build.
    * version (str) - The symver of the package we want to build (e.g. '1.2.0').
    * spec_lookup ((package_name, platform) -> ResolvedSpec) - A function to
      lookup (possibly cached) ResolvedSpec's for things like dependencies and
      tools.
    * ensure_built ((ResolvedSpec, version) -> CIPDSpec) - A function to ensure
      that a given ResolvedSpec is actually fully built and return a CIPDSpec to
      retrieve it's output package.
  """
  def _ensure_installed(root, cipd_pkgs):
    # TODO(iannucci): once `cipd ensure` supports local package installation,
    # use that.
    for pkg in cipd_pkgs:
      pkg.deploy(root)

  if spec.create_pb.build.tool:
    with api.step.nest('installing tools'):
      # ensure all our dependencies are built (should be handled by
      # ensure_uploaded, but just in case).
      _ensure_installed(workdir.tools_prefix, [
        ensure_built(tool, 'latest')
        for tool in spec.unpinned_tools
      ] + [
        spec_lookup(tool, spec.tool_platform).cipd_spec(tool_version)
        for tool, tool_version in spec.pinned_tool_info
      ])

  if spec.create_pb.build.dep:
    with api.step.nest('installing deps'):
      _ensure_installed(workdir.deps_prefix, [
        ensure_built(dep, 'latest')
        for dep in spec.all_possible_deps
      ])

  _do_checkout(api, workdir, spec, version)

  # Iff we are going to do the 'build' operation, copy all the package
  # definition scripts into the checkout. If no build message is provided, then
  # we're planning to directly package the result of the checkout, and we don't
  # want to include these scripts.
  if spec.create_pb.HasField("build"):
    # Copy all package definition stuff into the checkout
    api.file.copytree(
      'copy package definition',
      spec.base_path,
      workdir.script_dir_base)


#### Private stuff


def _do_checkout(api, workdir, spec, version):
  method_name, source_method_pb = spec.source_method
  source_pb = spec.create_pb.source

  checkout_dir = workdir.checkout
  if source_pb.subdir:
    checkout_dir = checkout_dir.join(*(source_pb.subdir.split('/')))

  api.file.ensure_directory(
    'mkdir -p [workdir]/checkout/%s' % (str(source_pb.subdir),), checkout_dir)

  if method_name == 'git':
    tag_pattern = source_method_pb.tag_pattern or '%s'
    version_join = (source_method_pb.version_join or '.')
    tag_name = tag_pattern % (version_join.join(version.split('.')),)
    tag = 'refs/tags/%s' % (tag_name,)
    api.git.checkout(source_method_pb.repo, tag, checkout_dir)

  elif method_name == 'cipd':
    api.cipd.ensure(
      checkout_dir,
      api.cipd.EnsureFile().
      add_package(str(source_method_pb.pkg), 'version:'+str(version)))

  elif method_name == 'script':
    # version is already in env as $_3PP_VERSION
    script = spec.host_dir.join(source_method_pb.name[0])
    args = map(str, source_method_pb.name[1:]) + ['checkout', checkout_dir]
    run_script(api, script, *args)

  else: # pragma: no cover
    assert False, 'Unknown source type %r' % (method_name,)

  if source_pb.unpack_archive:
    with api.step.nest('unpack_archive'):
      paths = api.file.glob_paths(
        'find archive to unpack', checkout_dir, '*.*')
      assert len(paths) == 1, (
        'unpack_archive==true - expected single archive file, '
        'but %s are extracted' % (paths,))

      archive = paths[0]
      archive_name = archive.pieces[-1]
      api.step.active_result.presentation.step_text = (
        'found %r' % (archive_name,))

      tmpdir = api.path.mkdtemp()
      # Use copy instead of move because archive might be a symlink (e.g. when
      # using a "cipd" source mode).
      #
      # TODO(iannucci): Have a way for `cipd pkg-deploy` to always deploy in
      # copy mode and change this to a move.
      api.file.copy('cp %r [tmpdir]' % archive_name,
                    archive, tmpdir.join(archive_name))

      # blow away any other files (e.g. .git)
      api.file.rmtree('rm -rf [checkout_dir]', checkout_dir)

      api.archive.extract('extracting [tmpdir]/%s' % archive_name,
                          tmpdir.join(archive_name),
                          checkout_dir)

      if not source_pb.no_archive_prune:
        api.file.flatten_single_directories(
          'prune archive subdirs', checkout_dir)

  if source_pb.patch_dir:
    patches = []
    for patch_dir in source_pb.patch_dir:
      patch_dir = str(patch_dir)
      patches.extend(api.file.glob_paths(
        'find patches in %s' % patch_dir,
        spec.host_dir.join(*(patch_dir.split('/'))), '*'))
    with api.context(cwd=checkout_dir):
      api.git('apply', '-v', *patches)
