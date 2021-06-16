# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Represents the type of approach.
HEURISTIC = 0x01
TRY_JOB = 0x02
PRE_ANALYSIS = 0x03
SWARMING = 0x04

STATUS_TO_DESCRIPTION = {
    HEURISTIC: 'Heuristic',
    TRY_JOB: 'Try Job',
    PRE_ANALYSIS: 'Pre-Analysis',
    SWARMING: 'Swarming'
}
