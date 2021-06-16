# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import collections
import json
import os
import sys
import urlparse

from infra.libs import git2
from infra.libs.service_utils import outer_loop
from infra.services.gsubtreed import gsubtreed
from infra_libs import logs
from infra_libs import ts_mon


# Return value of parse_args.
Options = collections.namedtuple('Options',
                                 'repo loop_opts json_output dry_run')

commits_counter = ts_mon.CounterMetric('gsubtreed/commit_count',
    'Number of commits processed by gsubtreed',
    [ts_mon.StringField('path')])


def parse_args(args):  # pragma: no cover
  def check_url(s):
    parsed = urlparse.urlparse(s)
    if parsed.scheme not in ('https', 'git', 'file'):
      raise argparse.ArgumentTypeError(
          'Repo URL must use https, git or file protocol.')
    if not parsed.path.strip('/'):
      raise argparse.ArgumentTypeError('URL is missing a path?')
    return git2.Repo(s)

  parser = argparse.ArgumentParser('./run.py %s' % __package__)
  parser.add_argument('--dry_run', action='store_true',
                      help='Do not actually push anything.')
  parser.add_argument('--repo_dir', metavar='DIR', default='gsubtreed_repos',
                      help=('The directory to use for git clones '
                            '(default: %(default)s)'))
  parser.add_argument('--json_output', metavar='PATH',
                      help='Path to write JSON with results of the run to')
  parser.add_argument('repo', nargs=1, help='The url of the repo to act on.',
                      type=check_url)
  logs.add_argparse_options(parser)
  ts_mon.add_argparse_options(parser)
  outer_loop.add_argparse_options(parser)

  parser.set_defaults(
      ts_mon_target_type='task',
      ts_mon_task_service_name='gsubtreed',
  )

  opts = parser.parse_args(args)

  repo = opts.repo[0]
  repo.repos_dir = os.path.abspath(opts.repo_dir)

  if not opts.ts_mon_task_job_name:
    parsed_repo_url = urlparse.urlparse(repo.url)
    opts.ts_mon_task_job_name = '%s%s' % (
        parsed_repo_url.netloc, parsed_repo_url.path)

  logs.process_argparse_options(opts)
  ts_mon.process_argparse_options(opts)
  loop_opts = outer_loop.process_argparse_options(opts)

  return Options(repo, loop_opts, opts.json_output, opts.dry_run)


def main(args):  # pragma: no cover
  opts = parse_args(args)
  try:
    return run(opts)
  finally:
    # Always flush metrics before exit.
    failure_message = 'Failed to flush ts_mon data, potentially losing data'
    try:
      if not ts_mon.flush():
        logging.error(failure_message)
    except Exception:
      logging.exception(failure_message)


def run(opts):
  cref = gsubtreed.GsubtreedConfigRef(opts.repo)
  opts.repo.reify()

  summary = collections.defaultdict(int)
  def outer_loop_iteration():
    success, paths_counts = gsubtreed.inner_loop(opts.repo, cref, opts.dry_run)
    for path, count in paths_counts.iteritems():
      summary[path] += count
      commits_counter.increment_by(count, fields={'path': path})
    return success

  loop_results = outer_loop.loop(
      task=outer_loop_iteration,
      sleep_timeout=lambda: cref['interval'],
      **opts.loop_opts)

  if opts.json_output:
    with open(opts.json_output, 'w') as f:
      json.dump({
        'error_count': loop_results.error_count,
        'summary': summary,
      }, f)

  return 0 if loop_results.success else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
