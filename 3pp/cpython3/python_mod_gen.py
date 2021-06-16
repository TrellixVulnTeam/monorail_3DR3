#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This script generates a Python build "Setup.local" file that describes a fully-
static Python module layout.

It does this by:
  - Probing the local Python installation for all of the modules that it is
    configured to emit.
  - Transforming the extension objects into Setup.local file.
  - Augmenting that file based on external instructions to complete the linking.

This script is intended to be run by the Python build interpreter. If it is
run by a system Python, make sure that Python uses "-s" and "-S" flags to
remove the influence of the local system's site configuration.
"""

import argparse
import contextlib
import glob
import logging
import os
import sys


@contextlib.contextmanager
def _temp_sys_argv(v):
  orig = sys.argv
  try:
    sys.argv = v
    yield
  finally:
    sys.argv = orig


@contextlib.contextmanager
def _temp_sys_builtins(*v):
  orig = sys.builtin_module_names
  try:
    sys.builtin_module_names = list(v)
    yield
  finally:
    sys.builtin_module_names = orig


@contextlib.contextmanager
def _temp_sys_path(root, pybuilddir):
  extra_paths = [
    os.path.join(root),  # to import `setup`
    os.path.join(root, pybuilddir),
    os.path.join(root, 'Lib'),
  ]
  old_path = sys.path
  try:
    sys.path = extra_paths
    yield
  finally:
    sys.path = old_path


def _get_extensions(root, pybuilddir):
  # Enter a "setup.py" expected library pathing, and tell distutil we want to
  # build extensions.
  with \
      _temp_sys_path(root, pybuilddir), \
      _temp_sys_builtins(), \
      _temp_sys_argv(['python', 'build_ext']):

    import distutils
    import distutils.core
    import distutils.command.build_ext

    import sysconfig
    sysconfig.get_config_vars()['MODBUILT_NAMES'] = ''

    # Tells distutils main() function to stop after parsing the command line,
    # but before actually trying to build stuff.
    distutils.core._setup_stop_after = "commandline"

    # Causes the actual 'build stuff' part to be a small explosion.
    class StopBeforeBuilding(Exception):
      pass
    def PreventBuild(*_):
      raise StopBeforeBuilding('boom')
    distutils.command.build_ext.build_ext.build_extensions = PreventBuild
    distutils.command.build_ext.build_ext.build_extension = PreventBuild

    # Have cpython's setup function actually invoke distutils to do
    # everything.
    import setup
    setup.main()

    # We stopped before running any commands. We then pull the 'build_ext'
    # command out of the distribution (which core nicely caches for us at
    # distutils.core), and then finish finalizing it and then 'run' it.
    ext_builder = (
        distutils.core._setup_distribution.get_command_obj('build_ext'))
    ext_builder.ensure_finalized()

    # This does a bunch of additional setup (like setting Command.compiler), and
    # then ultimately invokes setup.PyBuildExt.build_extensions(). This function
    # analyzes the current Modules/Setup.local, and then saves an Extension for
    # every module which should be dynamically built.
    #
    # It then calls through to the base `build_extensions` function, which we
    # earlier stubbed to raise an exception, and then finally prints some
    # summary information to stdout. Since we don't care to see the extra info
    # on # stdout, we catch the exception, then look at the .extensions member.
    try:
      ext_builder.run()
    except StopBeforeBuilding:
      pass

    # Finally, we get all the extensions which should be built for this
    # platform!
    for ext in ext_builder.extensions:
      assert isinstance(ext, distutils.extension.Extension)
      # some extensions are special and don't get fully configured until the
      # build process starts for them.
      try:
        ext_builder.build_extension(ext)
      except StopBeforeBuilding:
        pass
  return ext_builder.extensions


def _escape(v):
  v = v.replace(r'"', r'\\"')
  return v


def _root_abspath(root, root_macro, v):
  if os.path.isabs(v):
    return v

  # Try appending root to the source name.
  av = os.path.join(root, v)
  if not os.path.isfile(av):
    # When sources other than "Modules/**" are referenced, the path does not
    # include the "Modules/" prefix.
    if os.path.join(root, 'Modules', v):
      return os.path.join(root_macro, 'Modules', v)

  # The Modules version doesn't exist, so this could be a to-be-created path.
  return os.path.join(root_macro, v)

def _define_macro(d):
  k, v = map(str, d)
  if not v:
    return '-D%s' % (k,)

  # Escape quotes in "v", since this will appear in a Makefile we have to
  # double-escape it.
  return "'-D%s=%s'" % (k, _escape(str(v)))


def _flag_dirs(root, root_macro, flag, dirs):
  for d in dirs:
    d = _root_abspath(root, root_macro, d)
    yield '-%s%s' % (flag, d)


def _replace_suffix(root, root_macro, l, old_suffix, new_suffix):
  for v in l:
    if v.endswith(old_suffix):
      v = v[:-len(old_suffix)] + new_suffix
    yield _root_abspath(root, root_macro, v)


def set_envvar_from_makefile(root, varname):
  with open(os.path.join(root, 'Makefile')) as f:
    for line in f:
      if line.startswith(varname):
        val = line.split('=')[-1].strip()
        if not val:
          print('%s has empty value, not setting in environ.' % (varname,))
          return
        print('setting %s=%s' % (varname, val))
        os.environ[varname] = val
        return
  assert False, 'failed to find %s in Makefile' % varname


def set_sysconfigdata_from_pybuilddir(root, pybuilddir):
  candidates = glob.glob(os.path.join(root, pybuilddir, '_sysconfigdata_*.py'))
  assert len(candidates) == 1
  val = os.path.basename(candidates[0]).rstrip('.py')
  print('Found sysconfigdata: %s' % (val,))
  os.environ['_PYTHON_SYSCONFIGDATA_NAME'] = val


def main(argv):
  def _arg_mod_augmentation(v):
    parts = v.split('::', 1)
    if len(parts) == 1:
      return (None, v)
    return parts

  parser = argparse.ArgumentParser()
  parser.add_argument('--pybuilddir', required=True,
      help='The current python build directory we are targetting.')
  parser.add_argument('--output', required=True,
      help='Path to the output Setup file.')
  parser.add_argument('--skip', default=[], action='append',
      help='Name of a Python module to skip when translating.')
  parser.add_argument('--attach',
      action='append', default=[], type=_arg_mod_augmentation,
      help='Series of [MOD::]VALUE pairs of text to attach to the end of a '
           'given module definition. If no MOD is supplied, VALUE will be '
           'attached to all lines.')
  args = parser.parse_args(argv)
  args.skip = set(args.skip)

  # Our root directory is our current working directory.
  root = os.path.abspath(os.getcwd())

  # These are used by "sysconfig" to override information about the python
  # interpreter that we 'built' in order to run setup.py. When cross
  # compiling we rely on a build-platform compatible interpreter in $PATH,
  # and these envvars are enough to clue in the 'sysconfig' module to load
  # the correct data from the checkout.
  #
  # See PYTHON_FOR_BUILD in the Makefile.
  os.environ['_PYTHON_PROJECT_BASE'] = root
  set_envvar_from_makefile(root, '_PYTHON_HOST_PLATFORM')
  set_sysconfigdata_from_pybuilddir(root, args.pybuilddir)

  # We need to clear the existing "Setup.local", as it can influence module
  # probing.
  setup_local_path = os.path.join(root, 'Modules', 'Setup.local')
  logging.info('Clearing existing Setup.local: %r', setup_local_path)
  with open(setup_local_path, 'w+') as fd:
    pass

  logging.info('Loading base extension definitions...')
  exts = _get_extensions(root, args.pybuilddir)

  # Compile our attachments into a dict.
  attachments = {}
  for mod, app in args.attach:
    attachments.setdefault(mod, []).append(app)

  # Generate our output file with this information.
  with open(args.output, 'w') as fd:
    def w(line):
      fd.write(line)
      fd.write('\n')

    # Use this macro to make things more human-readable.
    root_macro_name = 'srcroot'
    root_macro = '$(%s)' % (root_macro_name,)

    # Include a banner.
    w('# This file was AUTO-GENERATED by Chrome Operations.')
    w('# Its contents are derived from the extension script defined in')
    w('# "setup.py" by processing it and extracting its extension definitions.')
    w('# The results are then fed back through "setup.py" with a header ')
    w('# telling it to compile them statically.')
    w('')
    w('*static*')
    w('')
    w('%s=%s' % (root_macro_name, root))

    # While it's more correct to have every module line list the static
    # libraries that we need to link against, Python will blindly aggregate
    # them in its linking command, duplicates and all, resulting a pretty
    # horrendous command. Avoid this by only emitting static library
    # dependencies once and relying on Python's "Setup.local" parsing and
    # integration to properly propagate these to the actual linking command.
    common_macros = [
        ('MOD_COMMON_ATTACH', attachments.get(None, ())),
    ]

    for ext in exts:
      if ext.name in args.skip:
        logging.info('Skipping module: %r', ext.name)
        continue

      logging.info('Emitting module: %r', ext.name)

      # Define statements don't parse properly if they have equals signs in
      # them. Rather than care about this too much, we'll just define a special
      # Makefile variable for each module with the defined values in it.
      macros = []
      def add_macro(base, v):
        # pylint: disable=cell-var-from-loop
        v = v or ()
        name = 'MOD_%s__%s' % (base, ext.name)
        macros.append((name, v))

      add_macro('DEFINES', [_define_macro(d) for d in ext.define_macros])
      add_macro('INCLUDES',
          _flag_dirs(root, root_macro, 'I', ext.include_dirs))
      add_macro('EXTRA_COMPILE', ext.extra_compile_args)
      add_macro('EXTRA_LINK', ext.extra_link_args)
      add_macro('ATTACHMENTS', attachments.get(ext.name))

      # First time, emit common macros.
      if common_macros:
        macros += common_macros
        common_macros = None

      entry = [
          ext.name,
      ]
      entry += [_root_abspath(root, root_macro, s) for s in ext.sources]
      entry += _replace_suffix(
          root, root_macro, ext.extra_objects or (), '.o', '.c')
      entry += _flag_dirs(root, root_macro, 'L', ext.library_dirs)
      for name, ents in macros:
        if not ents:
          continue
        w('%s=%s' % (name, ' '.join(ents)))
        entry.append('$(%s)' % (name,))

      w(' '.join(entry))
      w('')


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  sys.exit(main(sys.argv[1:]))
