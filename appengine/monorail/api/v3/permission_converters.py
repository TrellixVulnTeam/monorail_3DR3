# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from framework import permissions
from framework import exceptions
from api.v3.api_proto import permission_objects_pb2

# Global dictionaries to map backend permission strings to
# API Permission enum values.

HOTLIST_PERMISSIONS_MAP = {
    permissions.EDIT_HOTLIST:
        permission_objects_pb2.Permission.Value('HOTLIST_EDIT'),
    permissions.ADMINISTER_HOTLIST:
        permission_objects_pb2.Permission.Value('HOTLIST_ADMINISTER')
}

FIELDDEF_PERMISSIONS_MAP = {
    permissions.EDIT_FIELD_DEF:
        permission_objects_pb2.Permission.Value('FIELD_DEF_EDIT'),
    permissions.EDIT_FIELD_DEF_VALUE:
        permission_objects_pb2.Permission.Value('FIELD_DEF_VALUE_EDIT')
}

# TODO(crbug/monorail/7339): Create a common _ConvertPermissions(permissions,
# permissions_map)


def ConvertHotlistPermissions(hotlist_permissions):
  # type: (Sequence[str]) -> Sequence[permission_objects_pb2.Permission]
  """Converts hotlist permission strings into protoc Permission enum values."""
  api_permissions = []
  for permission in hotlist_permissions:
    api_permission = HOTLIST_PERMISSIONS_MAP.get(permission)
    if not api_permission:
      raise exceptions.InputException(
          'Unrecognized hotlist permission: %s' % permission)
    api_permissions.append(api_permission)

  return api_permissions


def ConvertFieldDefPermissions(field_permissions):
  # type: (Sequence[str]) -> Sequence[permission_objects_pb2.Permission]
  """Converts field permission strings into protoc Permission enum values."""
  api_permissions = []
  for permission in field_permissions:
    api_permission = FIELDDEF_PERMISSIONS_MAP.get(permission)
    if not api_permission:
      raise exceptions.InputException(
          'Unrecognized field permission: %s' % permission)
    api_permissions.append(api_permission)

  return api_permissions


# TODO(crbug/monorail/7339): Implement all ConvertFooPermissions methods.
