# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Represents status of the analysis result of a Chromium waterfall compile/test
# failure or a Chrome crash.
UNSPECIFIED = -1
FOUND_CORRECT = 0
FOUND_INCORRECT = 10
NOT_FOUND_INCORRECT = 20
FOUND_UNTRIAGED = 30
NOT_FOUND_UNTRIAGED = 40
NOT_FOUND_CORRECT = 50
PARTIALLY_CORRECT_FOUND = 60
FLAKY = 70
UNSUPPORTED = 80
FOUND_CORRECT_DUPLICATE = 1000
FOUND_INCORRECT_DUPLICATE = 1010

RESULT_STATUS_TO_DESCRIPTION = {
    FOUND_CORRECT: 'Correct - Found',
    FOUND_INCORRECT: 'Incorrect - Found',
    NOT_FOUND_INCORRECT: 'Incorrect - Not Found',
    FOUND_UNTRIAGED: 'Untriaged - Found',
    NOT_FOUND_UNTRIAGED: 'Untriaged - Not Found',
    NOT_FOUND_CORRECT: 'Correct - Not Found',
    PARTIALLY_CORRECT_FOUND: 'Partially Correct - Found',
    FLAKY: 'Flaky',
    UNSUPPORTED: 'Unsupported',
    FOUND_CORRECT_DUPLICATE: 'Correct(duplicate) - Found',
    FOUND_INCORRECT_DUPLICATE: 'Incorrect(duplicate) - Found'
}
