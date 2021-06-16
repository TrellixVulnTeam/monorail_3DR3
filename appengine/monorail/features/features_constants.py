# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Some constants used in Monorail hotlist pages."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from tracker import tracker_constants
from project import project_constants

DEFAULT_COL_SPEC = 'Rank Project Status Type ID Stars Owner Summary Modified'
DEFAULT_RESULTS_PER_PAGE = 100
OTHER_BUILT_IN_COLS = (
    tracker_constants.OTHER_BUILT_IN_COLS + ['Adder', 'Added', 'Note'])
# pylint: disable=line-too-long
ISSUE_INPUT_REGEX = '%s:\d+(([,]|\s)+%s:\d+)*' % (
    project_constants.PROJECT_NAME_PATTERN,
    project_constants.PROJECT_NAME_PATTERN)
FIELD_DEF_NAME_PATTERN = '[a-zA-Z]([_-]?[a-zA-Z0-9])*'

QUEUE_NOTIFICATIONS = 'notifications'
QUEUE_OUTBOUND_EMAIL = 'outboundemail'
QUEUE_PUBSUB = 'pubsub-issueupdates'

KNOWN_CUES = (
    'privacy_click_through',
    'code_of_conduct',
    'how_to_join_project',
    'search_for_numbers',
    'dit_keystrokes',
    'italics_mean_derived',
    'availability_msgs',
    'stale_fulltext',
    'document_team_duties',
    'showing_ids_instead_of_tiles',
    'issue_timestamps',
    'you_are_on_vacation',
    'your_email_bounced',
    'explain_hotlist_starring',
)
