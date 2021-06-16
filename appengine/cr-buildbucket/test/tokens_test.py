# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

import tokens


class BuildTokenTests(testing.AppengineTestCase):

  def test_roundtrip_simple(self):
    build_id = 1234567890
    token = tokens.generate_build_token(build_id)
    tokens.validate_build_token(token, build_id)
