# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions.

Has "bb" prefix to avoid confusion with components.utils.
"""

from google.protobuf import json_format
from google.protobuf import struct_pb2

from go.chromium.org.luci.buildbucket.proto import common_pb2

TRINARY_TO_BOOLISH = {
    common_pb2.UNSET: None,
    common_pb2.YES: True,
    common_pb2.NO: False,
}
BOOLISH_TO_TRINARY = {v: k for k, v in TRINARY_TO_BOOLISH.iteritems()}


def dict_to_struct(d):  # pragma: no cover
  """Converts a dict to google.protobuf.Struct."""
  s = struct_pb2.Struct()
  s.update(d)
  return s


def struct_to_dict(s):  # pragma: no cover
  """Converts a google.protobuf.Struct to dict."""
  return json_format.MessageToDict(s)


def update_struct(dest, src):  # pragma: no cover
  """Updates dest struct with values from src.

  Like dict.update, but for google.protobuf.Struct.
  """
  for key, value in src.fields.iteritems():
    # This will create a new struct_pb2.Value if one does not exist.
    dest.fields[key].CopyFrom(value)
