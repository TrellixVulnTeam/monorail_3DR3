#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

./configure --enable-static --disable-shared \
  --prefix "$PREFIX" \
  --host "$CROSS_TRIPLE" \
  --disable-all-programs \
  --enable-libuuid \
  --enable-libuuid-force-uuidd
make -j $(nproc)
make install -j $(nproc)
