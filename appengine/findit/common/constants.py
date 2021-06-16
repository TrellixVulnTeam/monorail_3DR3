# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Includes all the constants of module names, queue names, url paths, etc."""

import os
import re

# OAuth2 client_id of the "API Explorer" web app.
API_EXPLORER_CLIENT_ID = '292824132082.apps.googleusercontent.com'

# Names of all modules.
WATERFALL_BACKEND = 'waterfall-backend'
FLAKE_DETECTION_BACKEND = 'flake-detection-backend'
DISABLED_TEST_DETECTION_BACKEND = 'disabled-test-detection-backend'
AUTO_ACTION_BACKEND = 'auto-action-backend'

# Names of all queues.
DEFAULT_QUEUE = 'default'
WATERFALL_ANALYSIS_QUEUE = 'waterfall-analysis-queue'
WATERFALL_TRY_JOB_QUEUE = 'waterfall-try-job-queue'
WATERFALL_FAILURE_ANALYSIS_REQUEST_QUEUE = 'waterfall-failure-analysis-request'
WATERFALL_FLAKE_ANALYSIS_REQUEST_QUEUE = 'waterfall-flake-analysis-request'
RERUN_TRYJOB_QUEUE = 'rerun-tryjob'
AUTO_ACTION_QUEUE = 'auto-action-queue'
FLAKE_DETECTION_MULTITASK_QUEUE = 'flake-detection-multitask-queue'
DISABLED_TEST_DETECTION_QUEUE = 'disabled-test-detection-queue'

# Waterfall-related.
WATERFALL_PROCESS_FAILURE_ANALYSIS_REQUESTS_URL = (
    '/waterfall/task/process-failure-analysis-requests')
WATERFALL_PROCESS_FLAKE_ANALYSIS_REQUEST_URL = (
    '/waterfall/task/process-flake-analysis-request')
WATERFALL_ALERTS_URL = 'https://sheriff-o-matic.appspot.com/alerts'
COMPILE_STEP_NAME = 'compile'

# TODO: move this to config.
# Whitelisted prod app ids for authorized access to Findit prod.
WHITELISTED_APP_ACCOUNTS = [
    'findit-for-me@appspot.gserviceaccount.com',
    'sheriff-o-matic@appspot.gserviceaccount.com',
]

# Whitelisted staging app ids for authorized access to Findit staging.
WHITELISTED_STAGING_APP_ACCOUNTS = [
    'findit-for-me-staging@appspot.gserviceaccount.com',
    'sheriff-o-matic-staging@appspot.gserviceaccount.com',
]

# Whitelisted client ids for authorized access to Findit prod and staging.
WHITELISTED_CLIENT_IDS = [
    API_EXPLORER_CLIENT_ID,
]

# Directory of html templates.
HTML_TEMPLATE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), os.path.pardir, 'templates'))

DEFAULT_SERVICE_ACCOUNT = 'findit-for-me@appspot.gserviceaccount.com'

# TODO(chanli@): Move emails to config or other locations and avoid hard coding.
# List of accounts whose changes should never be flagged as culprits.
NO_BLAME_ACTION_ACCOUNTS = ['chrome-release-bot@chromium.org']

# List of accounts like DEPS rollers that auto-commit code.
NO_AUTO_COMMIT_REVERT_ACCOUNTS = [  # yapf: disable
    'blink-w3c-test-autoroller@chromium.org',
    'chromeos-commit-bot@chromium.org',
    'ios-autoroll@chromium.org',
    'v8-autoroll@chromium.org',
    'v8-ci-autoroll-builder@chops-service-accounts.iam.gserviceaccount.com',
] + NO_BLAME_ACTION_ACCOUNTS

AUTO_ROLLER_ACCOUNT_PATTERN = re.compile(
    r'.*chromium.*-autoroll@skia-(corp|public|buildbots)(\.google\.com)?\.iam\.'
    r'gserviceaccount\.com')

# TODO(crbug.com/1050188): remove webkit_layout_tests.
SUPPORTED_ISOLATED_SCRIPT_TESTS = ['webkit_layout_tests', 'blink_web_tests']
