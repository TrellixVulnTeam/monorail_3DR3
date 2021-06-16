# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from protorpc import messages


class FlakeType(messages.Enum):
  """Enumerates types of flakes for FlakeOccurrence."""

  # A flaky test that caused a CL to be incorrectly rejected by CQ.
  CQ_FALSE_REJECTION = 1

  # A flaky test that failed in the (with patch) steps, but passed in retry
  # steps such as (retry with patch) or (retry shards with patch).
  # this type name remains to be RETRY_WITH_PATCH because it's used in
  # FlakeOccurrence keys.
  RETRY_WITH_PATCH = 2

  # A flaky test that failed some test runs then pass.
  CQ_HIDDEN_FLAKE = 3

  # A flaky test that caused failed test steps in CI builds.
  CI_FAILED_STEP = 4


FLAKE_TYPE_DESCRIPTIONS = {
    FlakeType.CQ_FALSE_REJECTION: 'cq false rejection',
    FlakeType.RETRY_WITH_PATCH: 'cq step level retry',
    FlakeType.CQ_HIDDEN_FLAKE: 'cq hidden flake',
    FlakeType.CI_FAILED_STEP: 'ci failed step',
}

DESCRIPTION_TO_FLAKE_TYPE = {
    'cq false rejection': FlakeType.CQ_FALSE_REJECTION,
    'cq step level retry': FlakeType.RETRY_WITH_PATCH,
    'cq hidden flake': FlakeType.CQ_HIDDEN_FLAKE,
    'ci failed step': FlakeType.CI_FAILED_STEP
}

# Weights for each type of flakes.
# The weights are picked by intuitive, after comparing with other candidates.
# See goo.gl/y5awC5 for the comparison.
FLAKE_TYPE_WEIGHT = {
    FlakeType.CQ_FALSE_REJECTION: 100,
    FlakeType.RETRY_WITH_PATCH: 10,
    FlakeType.CQ_HIDDEN_FLAKE: 1,
    FlakeType.CI_FAILED_STEP: 10
}
