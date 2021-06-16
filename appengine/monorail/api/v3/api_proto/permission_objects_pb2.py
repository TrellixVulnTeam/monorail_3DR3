# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: api/v3/api_proto/permission_objects.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google_proto.google.api import field_behavior_pb2 as google__proto_dot_google_dot_api_dot_field__behavior__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='api/v3/api_proto/permission_objects.proto',
  package='monorail.v3',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n)api/v3/api_proto/permission_objects.proto\x12\x0bmonorail.v3\x1a,google_proto/google/api/field_behavior.proto\"O\n\rPermissionSet\x12\x10\n\x08resource\x18\x01 \x01(\t\x12,\n\x0bpermissions\x18\x02 \x03(\x0e\x32\x17.monorail.v3.Permission*\x90\x01\n\nPermission\x12\x1a\n\x16PERMISSION_UNSPECIFIED\x10\x00\x12\x10\n\x0cHOTLIST_EDIT\x10\x01\x12\x16\n\x12HOTLIST_ADMINISTER\x10\x02\x12\x0e\n\nISSUE_EDIT\x10\x03\x12\x12\n\x0e\x46IELD_DEF_EDIT\x10\x04\x12\x18\n\x14\x46IELD_DEF_VALUE_EDIT\x10\x05\x62\x06proto3')
  ,
  dependencies=[google__proto_dot_google_dot_api_dot_field__behavior__pb2.DESCRIPTOR,])

_PERMISSION = _descriptor.EnumDescriptor(
  name='Permission',
  full_name='monorail.v3.Permission',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='PERMISSION_UNSPECIFIED', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='HOTLIST_EDIT', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='HOTLIST_ADMINISTER', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ISSUE_EDIT', index=3, number=3,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FIELD_DEF_EDIT', index=4, number=4,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FIELD_DEF_VALUE_EDIT', index=5, number=5,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=186,
  serialized_end=330,
)
_sym_db.RegisterEnumDescriptor(_PERMISSION)

Permission = enum_type_wrapper.EnumTypeWrapper(_PERMISSION)
PERMISSION_UNSPECIFIED = 0
HOTLIST_EDIT = 1
HOTLIST_ADMINISTER = 2
ISSUE_EDIT = 3
FIELD_DEF_EDIT = 4
FIELD_DEF_VALUE_EDIT = 5



_PERMISSIONSET = _descriptor.Descriptor(
  name='PermissionSet',
  full_name='monorail.v3.PermissionSet',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='resource', full_name='monorail.v3.PermissionSet.resource', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='permissions', full_name='monorail.v3.PermissionSet.permissions', index=1,
      number=2, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=104,
  serialized_end=183,
)

_PERMISSIONSET.fields_by_name['permissions'].enum_type = _PERMISSION
DESCRIPTOR.message_types_by_name['PermissionSet'] = _PERMISSIONSET
DESCRIPTOR.enum_types_by_name['Permission'] = _PERMISSION
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

PermissionSet = _reflection.GeneratedProtocolMessageType('PermissionSet', (_message.Message,), dict(
  DESCRIPTOR = _PERMISSIONSET,
  __module__ = 'api.v3.api_proto.permission_objects_pb2'
  # @@protoc_insertion_point(class_scope:monorail.v3.PermissionSet)
  ))
_sym_db.RegisterMessage(PermissionSet)


# @@protoc_insertion_point(module_scope)
