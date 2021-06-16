# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: api/api_proto/features_objects.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from api.api_proto import common_pb2 as api_dot_api__proto_dot_common__pb2
from api.api_proto import issue_objects_pb2 as api_dot_api__proto_dot_issue__objects__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='api/api_proto/features_objects.proto',
  package='monorail',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n$api/api_proto/features_objects.proto\x12\x08monorail\x1a\x1a\x61pi/api_proto/common.proto\x1a!api/api_proto/issue_objects.proto\"\xe3\x01\n\x07Hotlist\x12$\n\towner_ref\x18\x01 \x01(\x0b\x32\x11.monorail.UserRef\x12&\n\x0b\x65\x64itor_refs\x18\x05 \x03(\x0b\x32\x11.monorail.UserRef\x12(\n\rfollower_refs\x18\x06 \x03(\x0b\x32\x11.monorail.UserRef\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x0f\n\x07summary\x18\x03 \x01(\t\x12\x13\n\x0b\x64\x65scription\x18\x04 \x01(\t\x12\x18\n\x10\x64\x65\x66\x61ult_col_spec\x18\x07 \x01(\t\x12\x12\n\nis_private\x18\x08 \x01(\x08\"\x88\x01\n\x0bHotlistItem\x12\x1e\n\x05issue\x18\x01 \x01(\x0b\x32\x0f.monorail.Issue\x12\x0c\n\x04rank\x18\x02 \x01(\r\x12$\n\tadder_ref\x18\x03 \x01(\x0b\x32\x11.monorail.UserRef\x12\x17\n\x0f\x61\x64\x64\x65\x64_timestamp\x18\x04 \x01(\r\x12\x0c\n\x04note\x18\x05 \x01(\t\"\xc5\x01\n\x12HotlistPeopleDelta\x12(\n\rnew_owner_ref\x18\x01 \x01(\x0b\x32\x11.monorail.UserRef\x12*\n\x0f\x61\x64\x64_editor_refs\x18\x02 \x03(\x0b\x32\x11.monorail.UserRef\x12,\n\x11\x61\x64\x64_follower_refs\x18\x03 \x03(\x0b\x32\x11.monorail.UserRef\x12+\n\x10remove_user_refs\x18\x04 \x03(\x0b\x32\x11.monorail.UserRefb\x06proto3')
  ,
  dependencies=[api_dot_api__proto_dot_common__pb2.DESCRIPTOR,api_dot_api__proto_dot_issue__objects__pb2.DESCRIPTOR,])




_HOTLIST = _descriptor.Descriptor(
  name='Hotlist',
  full_name='monorail.Hotlist',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='owner_ref', full_name='monorail.Hotlist.owner_ref', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='editor_refs', full_name='monorail.Hotlist.editor_refs', index=1,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='follower_refs', full_name='monorail.Hotlist.follower_refs', index=2,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='monorail.Hotlist.name', index=3,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='summary', full_name='monorail.Hotlist.summary', index=4,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='description', full_name='monorail.Hotlist.description', index=5,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='default_col_spec', full_name='monorail.Hotlist.default_col_spec', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='is_private', full_name='monorail.Hotlist.is_private', index=7,
      number=8, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
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
  serialized_start=114,
  serialized_end=341,
)


_HOTLISTITEM = _descriptor.Descriptor(
  name='HotlistItem',
  full_name='monorail.HotlistItem',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='issue', full_name='monorail.HotlistItem.issue', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='rank', full_name='monorail.HotlistItem.rank', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='adder_ref', full_name='monorail.HotlistItem.adder_ref', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='added_timestamp', full_name='monorail.HotlistItem.added_timestamp', index=3,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='note', full_name='monorail.HotlistItem.note', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
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
  serialized_start=344,
  serialized_end=480,
)


_HOTLISTPEOPLEDELTA = _descriptor.Descriptor(
  name='HotlistPeopleDelta',
  full_name='monorail.HotlistPeopleDelta',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='new_owner_ref', full_name='monorail.HotlistPeopleDelta.new_owner_ref', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='add_editor_refs', full_name='monorail.HotlistPeopleDelta.add_editor_refs', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='add_follower_refs', full_name='monorail.HotlistPeopleDelta.add_follower_refs', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='remove_user_refs', full_name='monorail.HotlistPeopleDelta.remove_user_refs', index=3,
      number=4, type=11, cpp_type=10, label=3,
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
  serialized_start=483,
  serialized_end=680,
)

_HOTLIST.fields_by_name['owner_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_HOTLIST.fields_by_name['editor_refs'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_HOTLIST.fields_by_name['follower_refs'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_HOTLISTITEM.fields_by_name['issue'].message_type = api_dot_api__proto_dot_issue__objects__pb2._ISSUE
_HOTLISTITEM.fields_by_name['adder_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_HOTLISTPEOPLEDELTA.fields_by_name['new_owner_ref'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_HOTLISTPEOPLEDELTA.fields_by_name['add_editor_refs'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_HOTLISTPEOPLEDELTA.fields_by_name['add_follower_refs'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
_HOTLISTPEOPLEDELTA.fields_by_name['remove_user_refs'].message_type = api_dot_api__proto_dot_common__pb2._USERREF
DESCRIPTOR.message_types_by_name['Hotlist'] = _HOTLIST
DESCRIPTOR.message_types_by_name['HotlistItem'] = _HOTLISTITEM
DESCRIPTOR.message_types_by_name['HotlistPeopleDelta'] = _HOTLISTPEOPLEDELTA
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Hotlist = _reflection.GeneratedProtocolMessageType('Hotlist', (_message.Message,), dict(
  DESCRIPTOR = _HOTLIST,
  __module__ = 'api.api_proto.features_objects_pb2'
  # @@protoc_insertion_point(class_scope:monorail.Hotlist)
  ))
_sym_db.RegisterMessage(Hotlist)

HotlistItem = _reflection.GeneratedProtocolMessageType('HotlistItem', (_message.Message,), dict(
  DESCRIPTOR = _HOTLISTITEM,
  __module__ = 'api.api_proto.features_objects_pb2'
  # @@protoc_insertion_point(class_scope:monorail.HotlistItem)
  ))
_sym_db.RegisterMessage(HotlistItem)

HotlistPeopleDelta = _reflection.GeneratedProtocolMessageType('HotlistPeopleDelta', (_message.Message,), dict(
  DESCRIPTOR = _HOTLISTPEOPLEDELTA,
  __module__ = 'api.api_proto.features_objects_pb2'
  # @@protoc_insertion_point(class_scope:monorail.HotlistPeopleDelta)
  ))
_sym_db.RegisterMessage(HotlistPeopleDelta)


# @@protoc_insertion_point(module_scope)
