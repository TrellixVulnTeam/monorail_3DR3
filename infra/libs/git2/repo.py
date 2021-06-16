# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import errno
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urlparse

from infra.libs.git2.commit import Commit
from infra.libs.git2.ref import Ref
from infra.libs.git2.util import CalledProcessError, INVALID

LOGGER = logging.getLogger(__name__)


class Repo(object):
  """Represents a remote git repo.

  Manages the (bare) on-disk mirror of the remote repo.
  """
  MAX_CACHE_SIZE = 1024

  DEFAULT_REFS = (
    'refs/*config',        # e.g. refs/meta/config, refs/infra/config
    'refs/*config/main',   # e.g. refs/gsubtreed-config/main
    'refs/branch-heads/*',
    'refs/heads/*',
    'refs/notes/*',
    'refs/tags/*',
  )

  def __init__(self, url, whitelist_refs=DEFAULT_REFS):
    """Creates a new Repo for the given git repo `url`.

    Args:
      url (str) - The URL of the repo to manage. Can be any URL scheme that git
        supports (including `file://`).
      whitelist_refs (iterable[str]) - The refs to include in this mirror. By
        default this includes known config refs, heads, branch-heads, notes and
        tags. This list excludes gerrit CL metadata which has on the order of a
        ~million extra refs (as of 2018Q3). Unfortunately there's no simple way
        to BLACKLIST refs as of git 2.18.
    """
    self.dry_run = False
    self.repos_dir = None
    self.netrc_file = None

    self._url = url
    self._repo_path = None
    self._commit_cache = collections.OrderedDict()
    self._log = LOGGER.getChild('Repo')
    self._queued_refs = {}
    self._whitelist_refs = sorted(whitelist_refs)

  def __hash__(self):
    return hash((self._url, self._repo_path))

  def __getitem__(self, ref):
    """Get a Ref attached to this Repo."""
    return Ref(self, ref)

  # Accessors
  # pylint: disable=W0212
  url = property(lambda self: self._url)
  repo_path = property(lambda self: self._repo_path)

  def reify(self, share_from=None, timeout=None, partial_clone=False):
    """Ensures the local mirror of this Repo exists.

    Args:
      share_from - Either a Repo, or a path to a git repo (on disk). This will
                   cause objects/info/alternates to be set up to point to the
                   other repo for objects.
      timeout - How long to wait for fetch operation to finish before killing
                it, sec.
      partial_clone - if True, only history will be fetched, but no file
                objects. See also https://git-scm.com/docs/partial-clone
                Can not be used with share_from.
                Default: False.
    """
    assert self.repos_dir is not None
    assert not partial_clone or share_from is None, (
        'partial_clone can\'t be used with share_from')

    if not os.path.exists(self.repos_dir):
      try:
        self._log.info('making repos dir: %s', self.repos_dir)
        os.makedirs(self.repos_dir)
      except OSError as e:  # pragma: no cover
        if e.errno != errno.EEXIST:
          raise

    parsed = urlparse.urlparse(self.url)
    norm_url = parsed.netloc + parsed.path
    if norm_url.endswith('.git'):
      norm_url = norm_url[:-len('.git')]
    folder = norm_url.replace('-', '--').replace('/', '-').lower()

    rpath = os.path.abspath(os.path.join(self.repos_dir, folder))

    share_objects = None
    if share_from:
      if isinstance(share_from, Repo):
        assert share_from.repo_path, 'share_from target must be reify()\'d'
        share_from = share_from.repo_path
      share_objects = os.path.join(share_from, 'objects')

    def ensure_config(path):
      if self.netrc_file:
        home = os.path.expanduser('~')
        fake_home = os.path.join(path, 'fake_home')
        try:
          os.makedirs(fake_home)
        except OSError as e:  # pragma: no cover
          if e.errno != errno.EEXIST:
            raise
        if os.path.exists(os.path.join(home, '.gitconfig')):
          shutil.copy(
              os.path.join(home, '.gitconfig'),
              os.path.join(fake_home, '.gitconfig'))
        shutil.copy(self.netrc_file, os.path.join(fake_home, '.netrc'))
        os.chmod(os.path.join(fake_home, '.netrc'), 0600)

      if share_objects:
        altfile = os.path.join(path, 'objects', 'info', 'alternates')
        try:
          os.makedirs(os.path.dirname(altfile))
        except OSError as e:
          if e.errno != errno.EEXIST:
            raise  # pragma: no cover

        add_entry = not os.path.exists(altfile)
        if not add_entry:
          with open(altfile, 'r') as f:
            add_entry = share_objects in f.readlines()
        if add_entry:
          with open(altfile, 'a') as f:
            print >> f, share_objects

      # First config resets all fetch refs
      first = True
      for pattern in self._whitelist_refs:
        self.run(*[
          'config',
          '--replace-all' if first else '--add',
          'remote.origin.fetch', '+%s:%s' % (pattern, pattern)
        ], cwd=path)
        first = False

    if not os.path.isdir(rpath):
      self._log.debug('initializing %r -> %r', self, rpath)
      tmp_path = tempfile.mkdtemp(dir=self.repos_dir)
      self.run('init', '--bare', os.path.basename(tmp_path), cwd=self.repos_dir)
      self.run(
          'remote', 'add', '--mirror=fetch', 'origin', self.url, cwd=tmp_path)
      ensure_config(tmp_path)
      if partial_clone:
        self.run('config', 'extensions.partialclone', 'origin', cwd=tmp_path)
        self.run('config', 'core.repositoryformatversion', '1', cwd=tmp_path)
        self.run('config', 'core.partialclonefilter', 'blob:none', cwd=tmp_path)
      self.run(
          'fetch', stdout=sys.stdout, stderr=sys.stderr,
          cwd=tmp_path, silent=True, timeout=timeout)
      os.rename(tmp_path, os.path.join(self.repos_dir, folder))
    else:
      ensure_config(rpath)
      self._log.debug('%r already initialized', self)

    self._repo_path = rpath

  # Representation
  def __repr__(self):
    return 'Repo({_url!r})'.format(**self.__dict__)

  # Methods
  def get_commit(self, hsh):
    """Creates a new ``Commit`` object for this ``Repo``.

    Uses a very basic LRU cache for commit objects, keeping up to
    ``MAX_CACHE_SIZE`` before eviction. This cuts down on the number of
    redundant git commands by > 50%, and allows expensive cached_property's to
    remain for the life of the process.

    If the ``Commit`` does not exist in this ``Repo``, return INVALID and do
    not cache the result.
    """
    if hsh in self._commit_cache:
      self._log.debug('Hit %s', hsh)
      r = self._commit_cache.pop(hsh)
    else:
      self._log.debug('Miss %s', hsh)
      if len(self._commit_cache) >= self.MAX_CACHE_SIZE:
        self._commit_cache.popitem(last=False)
      r = Commit(self, hsh)
      if r.data is INVALID:
        return INVALID

    self._commit_cache[hsh] = r
    return r

  def refglob(self, *globstrings):
    """Yield every Ref in this repo which matches a ``globstring`` according to
    the rules of git-for-each-ref.

    Defaults to all refs.
    """
    refs = self.run('for-each-ref', '--format=%(refname)', *globstrings)
    for ref in refs.splitlines():
      yield self[ref]

  def run(self, *args, **kwargs):
    """Yet-another-git-subprocess-wrapper.

    Args:
      args (list): argv tokens. 'git' is always argv[0]

    Keyword Args:
      indata (str): data to feed to communicate()
      ok_ret (set): valid return codes. Defaults to {0}.
      timeout (number): How long to wait for process to finish before killing
        it, sec.
      kwargs: passed through to subprocess.Popen()
    """
    assert args, args
    if args[0] == 'push' and self.dry_run:
      self._log.warn('DRY-RUN: Would have pushed %r', args[1:])
      return

    silent = kwargs.pop('silent', False)
    if args[0] in ('fetch', 'push') and not silent:
      log_func = self._log.info
    else:
      log_func = self._log.debug

    if 'cwd' not in kwargs:
      assert self._repo_path is not None
      kwargs.setdefault('cwd', self._repo_path)

    kwargs.setdefault('stderr', subprocess.PIPE)
    kwargs.setdefault('stdout', subprocess.PIPE)
    indata = kwargs.pop('indata', None)
    if indata:
      assert 'stdin' not in kwargs
      kwargs['stdin'] = subprocess.PIPE

    # Point git to a fake HOME with custom .netrc. An alternative is to use
    # credential.helper == 'store --file=...', but git always tries to use
    # HOME/.netrc before credential helper. So faking home is necessary anyway.
    if self.netrc_file:
      fake_home = os.path.abspath(os.path.join(kwargs['cwd'], 'fake_home'))
      if os.path.exists(fake_home):
        env = kwargs.get('env', os.environ).copy()
        env['HOME'] = fake_home
        kwargs['env'] = env

    # Git spawns subprocesses, we want to be able to kill them all.
    assert 'preexec_fn' not in kwargs
    if sys.platform != 'win32':  # pragma: no cover
      kwargs['preexec_fn'] = os.setpgrp

    ok_ret = kwargs.pop('ok_ret', {0})
    timeout = kwargs.pop('timeout', None)
    cmd = ('git',) + args

    log_func('Running %r', cmd)
    started = time.time()
    process = subprocess.Popen(cmd, **kwargs)
    def kill_proc():
      LOGGER.warning(
          'Terminating stuck process %d, %d sec timeout exceeded',
          process.pid, timeout)
      try:
        if sys.platform == 'win32':  # pragma: no cover
          process.terminate()
        else:
          assert os.getpgid(process.pid) == process.pid
          os.killpg(process.pid, signal.SIGTERM)
      except OSError as e:  # pragma: no cover
        if e.errno != errno.ESRCH:
          LOGGER.exception('Unexpected exception')
      except Exception:  # pragma: no cover
        LOGGER.exception('Unexpected exception')
    killer = threading.Timer(timeout, kill_proc) if timeout else None
    try:
      if killer:
        killer.start()
      output, errout = process.communicate(indata)
      retcode = process.poll()
    finally:
      if killer:
        killer.cancel()

    dt = time.time() - started
    if dt > 1:  # pragma: no cover
      log_func('Finished in %.1f sec', dt)
    if retcode not in ok_ret:
      raise CalledProcessError(retcode, cmd, output, errout)

    if errout:
      sys.stderr.write(errout)
    return output

  def intern(self, data, typ='blob'):
    return self.run(
        'hash-object', '-w', '-t', typ, '--stdin', indata=str(data)).strip()

  def fetch(self, timeout=None):
    """Update all local repo state to match remote.

    Clears queue_fast_forward entries.
    Args:
      timeout (number): kill the process after this many seconds.
    """
    self._queued_refs = {}
    LOGGER.debug('fetching %r', self)
    self.run('fetch', stdout=sys.stdout, stderr=sys.stderr, timeout=timeout)

  def fast_forward_push(self, refs_and_commits,
                        include_err=False, timeout=None):
    """Push commits to refs on the remote, and also update refs' local copies.

    Refs names are specified as refs on remote, i.e. push to
    ``Ref('refs/heads/master')`` would update 'refs/heads/master' on remote
    (and on local repo mirror), no ref name translation is happening.

    Optionally captures the stderror output of the push command and returns
    it as a string.

    Returns the stdout of the push command, or the stdout+stderr of the push
    command if ``include_err`` is specified.

    Args:
      refs_and_commits: dict {Ref object -> Commit to push to the ref}.
      include_err: a boolean indicating to capture and return the push output.
      timeout: how long to wait for push to complete before aborting, in sec.
    """
    if not refs_and_commits:
      return
    refspec = self.make_refspec(refs_and_commits)
    kwargs = {'stderr': sys.stdout} if include_err else {}
    kwargs['timeout'] = timeout
    output = self.run('push', 'origin', *refspec, **kwargs)
    for r, c in refs_and_commits.iteritems():
      r.fast_forward(c)
    return output

  def make_refspec(self, refs_and_commits):
    """Returns the rendered list of refspec entries for a git-push command line.

    Args:
      refs_and_commits: dict {Ref object -> Commit to push to the ref}.
    """
    assert all(r.repo is self for r in refs_and_commits)
    return [
      '%s:%s' % (c.hsh, r.ref)
      for r, c in sorted(
          refs_and_commits.iteritems(), key=lambda pair: pair[0].ref)
    ]

  def queue_fast_forward(self, refs_and_commits):
    """Update local refs, and keep track of which refs are updated.

    Push all queued refs to remote when push_queued_fast_forwards() is called.

    Refs names are specified the same as fast_forward_push()

    Args:
      refs_and_commits: dict {Ref object -> Commit to push to the ref}.
    """
    if not refs_and_commits:
      return
    assert all(r.repo is self for r in refs_and_commits)
    for r, c in refs_and_commits.iteritems():
      LOGGER.debug('Queuing %r -> %r', r.ref, c.hsh)
      r.fast_forward(c)
      self._queued_refs[r] = c

  def push_queued_fast_forwards(self, include_err=False, timeout=None):
    """Push refs->commits enqueued with queue_fast_forward."""
    queued = self._queued_refs
    self._queued_refs = {}
    return self.fast_forward_push(
        queued, include_err=include_err, timeout=timeout)

  def notes(self, obj, ref=None):
    """Get git-notes content for this object.

    See also: ``Commit.notes``.

    Args:
      obj (str|Ref): the hash of some object or a Ref.
      ref (str|Ref): a string ref for git-notes or a Ref.

    Returns:
    The notes content as a string, or None if there was no note for this object.
    """
    obj = obj.ref if isinstance(obj, Ref) else obj
    ref = ref.ref if isinstance(ref, Ref) else ref
    try:
      args = ['notes'] + (['--ref', ref] if ref else []) + ['show', obj]
      return self.run(*args)
    except CalledProcessError:
      return None
