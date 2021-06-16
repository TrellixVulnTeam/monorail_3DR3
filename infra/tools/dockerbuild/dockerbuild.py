# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import distutils.version
import os
import re
import sys

from . import dockcross
from . import markdown
from . import runtime
from . import source
from . import util
from . import build_platform
from . import wheels

from .builder import PlatformNotSupported


def _filter_platform_specs(selected_platforms, selected_specs):
  filtered_platforms = [
      build_platform.ALL[p] for p in
      (build_platform.NAMES if not selected_platforms else selected_platforms)
  ]
  filtered_specs = (
      wheels.DEFAULT_SPEC_NAMES if not selected_specs else selected_specs)
  return filtered_platforms, filtered_specs


def _main_sources(args, system):
  for src in sorted(source.Source.all()):
    if args.list:
      print 'Source: %s @ %s' % (src.name, src.version)
      continue

    util.LOGGER.info('Source: %s @ %s', src.name, src.version)
    with util.tempdir(system.root, src.tag) as tdir:
      system.repo.ensure(src, tdir)


def _main_docker_mirror(args, system):
  plats = [
      build_platform.ALL[name]
      for name in (args.platform or build_platform.NAMES)
  ]
  builder = dockcross.Builder(system)
  for plat in plats:
    if not plat.dockcross_base:
      util.LOGGER.info('Skipping [%s]: not configured for dockcross.',
                       plat.name)
      continue

    util.LOGGER.info('Mirroring base image for [%s]...', plat.name)
    builder.mirror_base_image(plat, upload=args.upload)


def _main_docker_generate(args, system):
  names = args.platform or build_platform.NAMES
  builder = dockcross.Builder(system)

  for name in names:
    plat = build_platform.ALL[name]
    if not plat.dockcross_base:
      util.LOGGER.info('Skipping [%s]: not configured for dockcross.', name)
      continue

    with util.Timer.run() as timer:
      util.LOGGER.info('Generating Docker image for %r...', name)
      dx = builder.build(plat, rebuild=args.rebuild, upload=args.upload)
      util.LOGGER.info('Generated Docker image [%s]', dx.identifier)

    util.LOGGER.info('Completed building platform [%s] in %s',
        name, timer.delta)


def _main_wheel_build(args, system):
  to_build = set(args.wheel or ())
  if args.wheel_re:
    regex = r'^%s$' % '|'.join('(%s)' % r for r in args.wheel_re)
    wheel_re = re.compile(regex)
    to_build.update(x for x in wheels.SPEC_NAMES if wheel_re.match(x))
    if not to_build:
      util.LOGGER.error("--wheel_re didn't match any wheels: %s", regex)
      return

  # Packages that we've updated this run.  Used to determine which packages
  # need their refs updated.
  updated_packages = set()

  platforms, specs = _filter_platform_specs(args.platform, to_build)

  _, git_revision = system.check_run(
      ['git', 'rev-parse', 'HEAD'],
      cwd=system.root,
  )
  for spec_name in specs:
    build = wheels.SPECS[spec_name]

    seen = set()
    for plat in platforms:
      w = build.wheel(system, plat)
      package = w.cipd_package(git_revision)
      if package in seen:
        continue
      seen.add(package)

      # Figure out the unique version id for this wheel build.
      buildid = build.version_fn(system)
      version_tag = 'version:%s' % (buildid,)
      cipd_exists = system.cipd.exists(package.name, version_tag)
      if cipd_exists and not args.rebuild:
        util.LOGGER.info('Package [%s] with buildid [%s] already exists.',
            package, buildid)
        continue

      util.LOGGER.info('Running wheel build [%s] with buildid [%s] for [%s]',
          spec_name, buildid, plat.name)
      try:
        pkg_path = build.build(w, system, rebuild=args.rebuild)
        if not pkg_path:
          continue
      except PlatformNotSupported:
        util.LOGGER.warning('Not supported on: %s', plat.name)
        continue
      util.LOGGER.info('Finished wheel for package: %s', package.name)

      dryrun = not args.upload or cipd_exists
      if cipd_exists:
        util.LOGGER.info('CIPD package already exists; ignoring --upload.')
      else:
        util.LOGGER.info('Uploading CIPD package for: %s', package)

      # When we register it, we want to attach all tags.
      system.cipd.register_package(pkg_path, package.tags, dryrun=dryrun)

      # Note packages that we've updated so we can update all the refs.
      updated_packages.add(package.name)

  # Now that we've registered all our packages, update all the refs.
  # We first create a reverse mapping for the cipd name to wheels.
  # i.e. We map "pylint-py2_py3" cipd name to all known versions.
  platforms, specs = _filter_platform_specs(args.platform, set())
  package_map = {}
  for spec_name in specs:
    build = wheels.SPECS[spec_name]
    seen = set()
    for plat in platforms:
      w = build.wheel(system, plat)
      package = w.cipd_package(git_revision)
      if package in seen:
        continue
      seen.add(package)

      if package.name in updated_packages:
        buildid = build.version_fn(system)
        package_map.setdefault(package.name, []).append((package, buildid))

  # Now walk the cipd packages to figure refs<->version bindings.
  for package_name, packages in package_map.items():
    util.LOGGER.info('Updating refs for %s', package_name)

    # First build the map of all versions that could satisfy a ref.
    # e.g. This creates {'latest': ['1.0', '2.0'],
    #                    '1.x': ['1.0'],
    #                    '2.x': ['2.0']}.
    ref_candidates = {'latest': []}
    for package, buildid in packages:
      version = distutils.version.LooseVersion(buildid)
      ref_candidates['latest'].append(version)

      # Create some ".x" refs for version series that are generally considered
      # "compatible".  We leave it to the end user to determine when using these
      # make sense as not all upstream packages have good practices (although
      # many do follow semver policies).
      # e.g. This creates:
      #   224     -> <none>
      #   1.9     -> 1.x
      #   1.5.6   -> 1.x 1.5.x
      #   1.8.7.3 -> 1.x 1.8.x 1.8.7.x
      parts = version.version
      for i in range(1, len(parts)):
        # Stop parsing if we hit non-numeric component.
        # e.g. 1.3.0rc1 -> [1, 3, 0, 'rc', 1].
        if not isinstance(parts[i], int):
          break
        series = '.'.join(str(x) for x in parts[0:i] + ['x'])
        ref_candidates.setdefault(series, []).append(version)

    # Then figure out which tags get which refs.  Basically we sort the
    # candidates to find the newest version and then point the ref to it.
    # e.g. This creates {'version:1.2.3': ['1.2.x'],
    #                    'version:1.3.1': ['latest', '1.3.x', '1.x']}.
    version_refs = {}
    for ref, versions in ref_candidates.items():
      version = sorted(versions)[-1]
      version_tag = 'version:%s' % (version.vstring,)
      version_refs.setdefault(version_tag, []).append(ref)

    # Finally set the refs!
    for version_tag, refs in version_refs.items():
      util.LOGGER.info('Setting %s refs %s to point to tag %s',
          package_name, refs, version_tag)
      system.cipd.set_refs(package_name, version_tag, refs, dryrun=dryrun)


def _main_wheel_dump(args, system):
  try:
    md = markdown.Generator()
    for build in wheels.SPECS.itervalues():
      for plat in build_platform.ALL.itervalues():
        if not build.supported(plat):
          continue
        w = build.wheel(system, plat)
        if w.spec.universal:
          plat = None
        md.add_package(w, plat)

    md.write(args.output)
  finally:
    args.output.close()


def _main_run(args, system):
  plat = build_platform.ALL[args.platform]
  builder = dockcross.Builder(system)

  util.LOGGER.info('Configuring Docker image for %r...', plat.name)
  dx = builder.build(plat)

  dx_args = args.args
  if dx_args and dx_args[0] == '--':
    dx_args = dx_args[1:]

  # abs and ends with slash
  args.workdir = os.path.sep.join([os.path.abspath(args.workdir), ''])
  args.cwd = os.path.sep.join([os.path.abspath(args.cwd), ''])
  assert args.cwd.startswith(args.workdir), (
    'workdir %r does not contain cwd %r' % (args.workdir, args.cwd))

  # Pass through env vars.
  env = {}
  affixes = {}
  for var, value in args.env:
    env['DOCKERBUILD_SET_'+var] = (
      value.replace(args.workdir, '/work/').encode('base64').strip())
  for var, value in args.env_prefix:
    affixes.setdefault('DOCKERBUILD_PREPEND_'+var, []).append(
      value.replace(args.workdir, '/work/'))
  for var, value in args.env_suffix:
    affixes.setdefault('DOCKERBUILD_APPEND_'+var, []).append(
      value.replace(args.workdir, '/work/'))
  for k, vals in affixes.iteritems():
    env[k] = ':'.join(vals).encode('base64').strip()

  retcode, _ = dx.run(args.workdir, dx_args, stdout=sys.stdout,
                      stderr=sys.stderr, cwd=args.cwd, env=env)
  sys.exit(retcode)


def add_argparse_options(parser):
  cwd = os.getcwd()

  parser.add_argument('--root',
      default=os.path.join(cwd, '.dockerbuild'),
      help='Root directory for checkouts and builds.')
  parser.add_argument('--leak', action='store_true',
      help='Leak temporary files instead of deleting them.')
  parser.add_argument('--native-python', action='store', default=sys.executable,
      help='Path to the Python interpreter to use for native invocations. '
           'If empty, use the current interpreter.')

  group = parser.add_argument_group('sources')
  group.add_argument('--upload-sources', action='store_true',
      help='Enable uploading of generated source CIPD packages.')
  group.add_argument('--force-source-download', action='store_true',
      help='Force download of sources even if a packaged version already '
           'exists in CIPD.')

  subparsers = parser.add_subparsers()

  # Subcommand: sources
  subparser = subparsers.add_parser('sources',
      help='Ensure that all registered source files can be downloaded.')
  subparser.add_argument('--list', action='store_true',
      help='Rather than processing sources, just list and exit.')
  subparser.set_defaults(func=_main_sources)

  # Subcommand: docker-mirror
  subparser = subparsers.add_parser('docker-mirror',
      help='Mirror public Docker base images to our internal repository.')
  subparser.add_argument('--upload', action='store_true',
      help='Upload the tagged images to the internal repository.')
  subparser.add_argument(
      '--platform',
      action='append',
      choices=build_platform.NAMES,
      help='If provided, only mirror images for the named platforms.')
  subparser.set_defaults(func=_main_docker_mirror)

  # Subcommand: docker-generate
  subparser = subparsers.add_parser('docker-generate',
      help='Generate and install the base "dockcross" build environment.')
  subparser.add_argument('--rebuild', action='store_true',
      help='Force rebuild of the image, even if one already exists.')
  subparser.add_argument(
      '--platform',
      action='append',
      choices=build_platform.NAMES,
      help='If provided, only generate the named environment.')
  subparser.add_argument('--upload', action='store_true',
      help='Upload any generated Docker images.')
  subparser.set_defaults(func=_main_docker_generate)

  # Subcommand: wheel-build
  subparser = subparsers.add_parser('wheel-build',
      help='Generate the named wheel.')
  subparser.add_argument(
      '--platform',
      action='append',
      choices=build_platform.NAMES,
      help='Only build packages for the specified platform.')
  subparser.add_argument(
      '--wheel',
      action='append',
      choices=wheels.SPEC_NAMES,
      help='Only build packages for the specified wheel(s).')
  subparser.add_argument('--wheel_re', action='append', default=[],
      metavar='REGEX',
      help='Only build packages for the wheels matching these regexes.')
  subparser.add_argument('--rebuild', action='store_true',
      help='Force rebuild of package even if it is already built.')
  subparser.add_argument('--upload', action='store_true',
      help='Upload any missing CIPD packages.')
  subparser.set_defaults(func=_main_wheel_build)

  # Subcommand: wheel-dump
  subparser = subparsers.add_parser('wheel-dump',
      help='Dumps a markdown-compatible set of generated wheels.')
  subparser.add_argument('--output',
      type=argparse.FileType('w'), default=markdown.DEFAULT_PATH,
      help='Path to write the markdown file.')
  subparser.set_defaults(func=_main_wheel_dump)

  # Subcommand: run
  subparser = subparsers.add_parser('run',
      help='Run the supplied subcommand in a "dockcross" container.')
  subparser.add_argument(
      '--platform',
      required=True,
      choices=build_platform.NAMES,
      help='Run in the container for the specified platform.')
  subparser.add_argument('--workdir', default=cwd,
      help=('Mount this directory as "/work". Must be equal to, or a parent '
            'of, $PWD. The command will be run from the translated $PWD under '
            '"/work". So if $PWD is "/some/path/to/dir", and --workdir is '
            '"/some/path", then "/some/path" will be mounted as "/work", and '
            'the command will run from "/work/to/dir".'))
  subparser.add_argument('--env', nargs=2, action='append', default=[],
      help=('Set this envvar in the container. '
            'If the value contains the workdir, it will be replaced with '
            '"/work".'))
  subparser.add_argument('--env-prefix', nargs=2, action='append', default=[],
      help=('Add path envvar at the beginning of the container\'s value. '
            'If the value contains the workdir, it will be replaced with '
            '"/work".'))
  subparser.add_argument('--env-suffix', nargs=2, action='append', default=[],
      help=('Add path envvar at the end of the container\'s value. '
            'If the value contains the workdir, it will be replaced with '
            '"/work".'))
  subparser.add_argument('args', nargs=argparse.REMAINDER,
      help='Command-line arguments to pass.')
  subparser.set_defaults(func=_main_run, cwd=cwd)


def run(args):
  system = runtime.System.initialize(
      args.root,
      leak=args.leak,
      native_python=args.native_python,
      upload_sources=args.upload_sources,
      force_source_download=args.force_source_download)

  rc = args.func(args, system)
  if system.repo.missing_sources:
    util.LOGGER.warning('Some missing sources were identified. Please upload '
                        'them to CIPD to ensure a reproducible build with '
                        '--upload-sources.')
  return rc
