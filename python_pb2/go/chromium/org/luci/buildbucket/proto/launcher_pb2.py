# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: go.chromium.org/luci/buildbucket/proto/launcher.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from go.chromium.org.luci.buildbucket.proto import build_pb2 as go_dot_chromium_dot_org_dot_luci_dot_buildbucket_dot_proto_dot_build__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='go.chromium.org/luci/buildbucket/proto/launcher.proto',
  package='buildbucket.v2',
  syntax='proto3',
  serialized_options=_b('Z4go.chromium.org/luci/buildbucket/proto;buildbucketpb'),
  serialized_pb=_b('\n5go.chromium.org/luci/buildbucket/proto/launcher.proto\x12\x0e\x62uildbucket.v2\x1a\x32go.chromium.org/luci/buildbucket/proto/build.proto\"M\n\x0c\x42uildSecrets\x12\x13\n\x0b\x62uild_token\x18\x01 \x01(\t\x12(\n resultdb_invocation_update_token\x18\x02 \x01(\t\"\x98\x01\n\x0b\x42\x42\x41gentArgs\x12\x17\n\x0f\x65xecutable_path\x18\x01 \x01(\t\x12\x14\n\x0cpayload_path\x18\x05 \x01(\t\x12\x11\n\tcache_dir\x18\x02 \x01(\t\x12!\n\x19known_public_gerrit_hosts\x18\x03 \x03(\t\x12$\n\x05\x62uild\x18\x04 \x01(\x0b\x32\x15.buildbucket.v2.BuildB6Z4go.chromium.org/luci/buildbucket/proto;buildbucketpbb\x06proto3')
  ,
  dependencies=[go_dot_chromium_dot_org_dot_luci_dot_buildbucket_dot_proto_dot_build__pb2.DESCRIPTOR,])




_BUILDSECRETS = _descriptor.Descriptor(
  name='BuildSecrets',
  full_name='buildbucket.v2.BuildSecrets',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='build_token', full_name='buildbucket.v2.BuildSecrets.build_token', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='resultdb_invocation_update_token', full_name='buildbucket.v2.BuildSecrets.resultdb_invocation_update_token', index=1,
      number=2, type=9, cpp_type=9, label=1,
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
  serialized_start=125,
  serialized_end=202,
)


_BBAGENTARGS = _descriptor.Descriptor(
  name='BBAgentArgs',
  full_name='buildbucket.v2.BBAgentArgs',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='executable_path', full_name='buildbucket.v2.BBAgentArgs.executable_path', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='payload_path', full_name='buildbucket.v2.BBAgentArgs.payload_path', index=1,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='cache_dir', full_name='buildbucket.v2.BBAgentArgs.cache_dir', index=2,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='known_public_gerrit_hosts', full_name='buildbucket.v2.BBAgentArgs.known_public_gerrit_hosts', index=3,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='build', full_name='buildbucket.v2.BBAgentArgs.build', index=4,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
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
  serialized_start=205,
  serialized_end=357,
)

_BBAGENTARGS.fields_by_name['build'].message_type = go_dot_chromium_dot_org_dot_luci_dot_buildbucket_dot_proto_dot_build__pb2._BUILD
DESCRIPTOR.message_types_by_name['BuildSecrets'] = _BUILDSECRETS
DESCRIPTOR.message_types_by_name['BBAgentArgs'] = _BBAGENTARGS
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

BuildSecrets = _reflection.GeneratedProtocolMessageType('BuildSecrets', (_message.Message,), dict(
  DESCRIPTOR = _BUILDSECRETS,
  __module__ = 'go.chromium.org.luci.buildbucket.proto.launcher_pb2'
  # @@protoc_insertion_point(class_scope:buildbucket.v2.BuildSecrets)
  ))
_sym_db.RegisterMessage(BuildSecrets)

BBAgentArgs = _reflection.GeneratedProtocolMessageType('BBAgentArgs', (_message.Message,), dict(
  DESCRIPTOR = _BBAGENTARGS,
  __module__ = 'go.chromium.org.luci.buildbucket.proto.launcher_pb2'
  # @@protoc_insertion_point(class_scope:buildbucket.v2.BBAgentArgs)
  ))
_sym_db.RegisterMessage(BBAgentArgs)


DESCRIPTOR._options = None
# @@protoc_insertion_point(module_scope)
