# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: my_target.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='my_target.proto',
  package='ts_mon.common.test',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x0fmy_target.proto\x12\x12ts_mon.common.test\"+\n\x08MyTarget\x12\t\n\x01\x62\x18\x01 \x01(\x08\x12\t\n\x01i\x18\x02 \x01(\x03\x12\t\n\x01s\x18\x03 \x01(\tb\x06proto3')
)




_MYTARGET = _descriptor.Descriptor(
  name='MyTarget',
  full_name='ts_mon.common.test.MyTarget',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='b', full_name='ts_mon.common.test.MyTarget.b', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='i', full_name='ts_mon.common.test.MyTarget.i', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='s', full_name='ts_mon.common.test.MyTarget.s', index=2,
      number=3, type=9, cpp_type=9, label=1,
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
  serialized_start=39,
  serialized_end=82,
)

DESCRIPTOR.message_types_by_name['MyTarget'] = _MYTARGET
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

MyTarget = _reflection.GeneratedProtocolMessageType('MyTarget', (_message.Message,), dict(
  DESCRIPTOR = _MYTARGET,
  __module__ = 'my_target_pb2'
  # @@protoc_insertion_point(class_scope:ts_mon.common.test.MyTarget)
  ))
_sym_db.RegisterMessage(MyTarget)


# @@protoc_insertion_point(module_scope)
