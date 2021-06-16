# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

components_ereporter2_RECIPIENTS_AUTH_GROUP = 'buildbucket-ereporter2-reports'
components_ereporter2_VIEWERS_AUTH_GROUP = 'buildbucket-ereporter2-viewers'

components_auth_USE_PROJECT_IDENTITIES = True

from components import utils
utils.fix_protobuf_package()
