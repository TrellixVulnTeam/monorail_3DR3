# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/git',
  'depot_tools/git_cl',
  'depot_tools/gsutil',

  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/python',
  'recipe_engine/random',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'recipe_engine/time',
]


# TODO(phajdan.jr): provide coverage (http://crbug.com/693058).
DISABLE_STRICT_COVERAGE = True
