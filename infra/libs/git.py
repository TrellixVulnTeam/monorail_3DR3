# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility for dealing with Git repositories."""

import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time

from types import MethodType


LOGGER = logging.getLogger(__name__)


class GitException(UserWarning):
  """Indicate that an error occured in the infra.libs.git module."""
  pass


class Git(object):
  """Wrapper class to abstract git operations against a single repository.

  Args:
    path (str): The absolute or relative path to the repository on disk.
  """

  def __init__(self, path):  # pragma: no cover
    self.path = os.path.abspath(path)

  def __call__(self, *args, **kwargs):  # pragma: no cover
    """Run a git command and returns its combined stdout and stderr.

    Args:
       args (list): passed as argument to the 'git' command.
       kwargs (dict): passed to subprocess.check_output

    Returns:
       output (str): combined stdout and stderr.
    """
    cmd = ['git'] + [str(arg) for arg in args]
    kwargs.setdefault('cwd', self.path)
    LOGGER.debug('Running `%s` with %s', ' '.join(cmd), kwargs)
    out = subprocess.check_output(
        cmd, stderr=subprocess.STDOUT, **kwargs)
    return out

  @property
  def bare(self):  # pragma: no cover
    """True if the repository is bare (is just the .git directory)."""
    return self('config', '--get', 'core.bare').strip() == 'true'

  def show(self, ref, path, *args):  # pragma: no cover
    """Get the contents of a Git object (blob, tree, tag, or commit).

    Args:
      ref (string): The ref at which to show the object.
        Can be an empty string.
      path (string): The path to the blob or tree, relative to repository root.

    Returns:
      content (str): the requested object.
    """
    treeish = ref + (':%s' % path if path else '')
    cmd = ['show', treeish] + list(args)
    return self(*cmd)

  def number(self, *refs):  # pragma: no cover
    """Get the commit position of each input ref.

    Args:
      refs (tuple of refishes): refishes to number.

    Returns:
      positions (list of [str|None]): respective numbers.
    """
    positions = []
    for ref in refs:
      cmd = ['show', '-s', '--format=%B', ref]
      out = self(*cmd)
      found = False
      for line in reversed(out.splitlines()):
        if line.startswith('Cr-Commit-Position: '):
          positions.append(line.split()[-1].strip())
          found = True
          break
      if not found:
        positions.append(None)
    return positions


def NewGit(url, path, bare=False):  # pragma: no cover
  """Factory function to create a Git object against a remote url.

  Ensures the given path exists. If a git repository is already present
  ensures that it points at the given url; otherwise, creates a git repository
  from the given url.

  Args:
    url (str): The url of the remote repository.
    path (str): The path to the local version of the repository.
    bare (str, optional): Whether or not the local repo should be a bare clone.

  Returns:
    repo (:class:`Git`): object representing the local git repository.

  Raises:
    GitException
  """
  # If the directory doesn't exist, create it.
  if not os.path.isdir(path):
    os.makedirs(path)

  git = Git(path)

  # If the directory has nothing in it, clone into it.
  if not os.listdir(path):
    b = ['--bare'] if bare else []
    clone_cmd = ['clone'] + b + [url, '.']
    git(*clone_cmd)
    return git

  # If the directory is already correctly configured for this repo, fetch.
  try:
    curr_url = git('config', '--get', 'remote.origin.url').strip()
    if curr_url != url:
      msg = ('A Git repo at %s exists, '
             'but has %s configured as remote origin url.' % (path, curr_url))
      LOGGER.error(msg)
      raise GitException(msg)
    if git.bare != bare:
      msg = ('A Git repo at %s exists, but is %sbare.' %
             (path, 'not ' if not git.bare else ''))
      LOGGER.error(msg)
      raise GitException(msg)
  except subprocess.CalledProcessError:
    msg = 'There appears to already be something else at %s.' % path
    LOGGER.error(msg)
    raise GitException(msg)

  try:
    git('fetch', 'origin')
  except subprocess.CalledProcessError:
    LOGGER.error('Failed to fetch origin.')
  return git


def TmpGit(url, bare=False):  # pragma: no cover
  """Factory function to create a temporary Git object against a remote url.

  Creates a temporary directory, clones the repository into that directory,
  and returns a Git object pointing at that temporary directory. The instance
  will clean up after itself by deleting the temporary directory.

  Args:
    url (str): The url of the remote repository.
    bare (bool): Whether or not the local repo should be a bare clone.

  Returns:
    git_repo (:class:`Git`): the local temporary git clone.
  """
  path = tempfile.mkdtemp()
  git = NewGit(url, path, bare)

  def __del__(git_obj):
    """Destroy the temporary directory."""
    def rm_on_error(_func, _path, _exc):
      """Error handling function to enforce removal of readonly files."""
      if sys.platform.startswith('win'):
        # On windows, we'll just fall back to using cmd.exe's rd.
        for _ in xrange(3):
          exitcode = subprocess.call(['cmd.exe', '/c', 'rd', '/q', '/s', path])
          if exitcode == 0:
            return
          else:
            LOGGER.warn('rd exited with code %d', exitcode)
          time.sleep(3)
        LOGGER.fatal('Failed to remove path %s', path)
      else:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 777
        shutil.rmtree(path, ignore_errors=False, onerror=rm_on_error)

    shutil.rmtree(git_obj.path, ignore_errors=False, onerror=rm_on_error)

  git.__del__ = MethodType(__del__, git, Git)  # pylint: disable=W0201

  return git
