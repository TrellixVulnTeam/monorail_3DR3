// Copyright 2020 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import * as issue from './constants-issueV0.js';
import 'shared/typedef.js';

/** @type {Permission} */
export const PERMISSION_ISSUE_EDIT = 'ISSUE_EDIT';

/** @type {PermissionSet} */
export const PERMISSION_SET_ISSUE = {
  resource: issue.NAME,
  permissions: [PERMISSION_ISSUE_EDIT],
};

/** @type {Object<string, PermissionSet>} */
export const BY_NAME = {
  [issue.NAME]: PERMISSION_SET_ISSUE,
};

/** @type {Array<Permission>} */
export const PERMISSION_HOTLIST_EDIT = ['HOTLIST_EDIT'];
