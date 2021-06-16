# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import sys

from glucose import install
from glucose import pack
from glucose import util


def add_argparse_options(parser):
  parser.add_argument('--keep-tmp-directories', action='store_true',
                      help="Do not erase temporary directories created. This is"
                      " intended for debugging Glyco only.")
  parser.add_argument('--quiet', dest='verbose',
                      action='store_false', default=True)
  subparsers = parser.add_subparsers()
  install.add_subparser(subparsers)
  pack.add_subparser(subparsers)


def process_argparse_options(options):
  try:
    return options.command(options)
  except util.GlycoSetupError as err:
    print >> sys.stderr, err.message
    return 2


def main():
  parser = argparse.ArgumentParser(
    description="Glyco is a tool to pack and unpack wheel files.")
  add_argparse_options(parser)

  options = parser.parse_args(sys.argv[1:])

  sys.exit(process_argparse_options(options))
