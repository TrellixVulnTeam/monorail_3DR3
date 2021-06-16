# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: go.chromium.org/luci/server/auth/delegation/messages/delegation.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='go.chromium.org/luci/server/auth/delegation/messages/delegation.proto',
  package='messages',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\nEgo.chromium.org/luci/server/auth/delegation/messages/delegation.proto\x12\x08messages\"y\n\x0f\x44\x65legationToken\x12\x11\n\tsigner_id\x18\x02 \x01(\t\x12\x16\n\x0esigning_key_id\x18\x03 \x01(\t\x12\x18\n\x10pkcs1_sha256_sig\x18\x04 \x01(\x0c\x12\x1b\n\x13serialized_subtoken\x18\x05 \x01(\x0cJ\x04\x08\x01\x10\x02\"\x99\x02\n\x08Subtoken\x12%\n\x04kind\x18\x08 \x01(\x0e\x32\x17.messages.Subtoken.Kind\x12\x13\n\x0bsubtoken_id\x18\x04 \x01(\x03\x12\x1a\n\x12\x64\x65legated_identity\x18\x01 \x01(\t\x12\x1a\n\x12requestor_identity\x18\x07 \x01(\t\x12\x15\n\rcreation_time\x18\x02 \x01(\x03\x12\x19\n\x11validity_duration\x18\x03 \x01(\x05\x12\x10\n\x08\x61udience\x18\x05 \x03(\t\x12\x10\n\x08services\x18\x06 \x03(\t\x12\x0c\n\x04tags\x18\t \x03(\t\"5\n\x04Kind\x12\x10\n\x0cUNKNOWN_KIND\x10\x00\x12\x1b\n\x17\x42\x45\x41RER_DELEGATION_TOKEN\x10\x01\x62\x06proto3')
)



_SUBTOKEN_KIND = _descriptor.EnumDescriptor(
  name='Kind',
  full_name='messages.Subtoken.Kind',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='UNKNOWN_KIND', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BEARER_DELEGATION_TOKEN', index=1, number=1,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=435,
  serialized_end=488,
)
_sym_db.RegisterEnumDescriptor(_SUBTOKEN_KIND)


_DELEGATIONTOKEN = _descriptor.Descriptor(
  name='DelegationToken',
  full_name='messages.DelegationToken',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='signer_id', full_name='messages.DelegationToken.signer_id', index=0,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='signing_key_id', full_name='messages.DelegationToken.signing_key_id', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='pkcs1_sha256_sig', full_name='messages.DelegationToken.pkcs1_sha256_sig', index=2,
      number=4, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='serialized_subtoken', full_name='messages.DelegationToken.serialized_subtoken', index=3,
      number=5, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
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
  serialized_start=83,
  serialized_end=204,
)


_SUBTOKEN = _descriptor.Descriptor(
  name='Subtoken',
  full_name='messages.Subtoken',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='kind', full_name='messages.Subtoken.kind', index=0,
      number=8, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='subtoken_id', full_name='messages.Subtoken.subtoken_id', index=1,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='delegated_identity', full_name='messages.Subtoken.delegated_identity', index=2,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='requestor_identity', full_name='messages.Subtoken.requestor_identity', index=3,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='creation_time', full_name='messages.Subtoken.creation_time', index=4,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='validity_duration', full_name='messages.Subtoken.validity_duration', index=5,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='audience', full_name='messages.Subtoken.audience', index=6,
      number=5, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='services', full_name='messages.Subtoken.services', index=7,
      number=6, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='tags', full_name='messages.Subtoken.tags', index=8,
      number=9, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _SUBTOKEN_KIND,
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=207,
  serialized_end=488,
)

_SUBTOKEN.fields_by_name['kind'].enum_type = _SUBTOKEN_KIND
_SUBTOKEN_KIND.containing_type = _SUBTOKEN
DESCRIPTOR.message_types_by_name['DelegationToken'] = _DELEGATIONTOKEN
DESCRIPTOR.message_types_by_name['Subtoken'] = _SUBTOKEN
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

DelegationToken = _reflection.GeneratedProtocolMessageType('DelegationToken', (_message.Message,), dict(
  DESCRIPTOR = _DELEGATIONTOKEN,
  __module__ = 'go.chromium.org.luci.server.auth.delegation.messages.delegation_pb2'
  # @@protoc_insertion_point(class_scope:messages.DelegationToken)
  ))
_sym_db.RegisterMessage(DelegationToken)

Subtoken = _reflection.GeneratedProtocolMessageType('Subtoken', (_message.Message,), dict(
  DESCRIPTOR = _SUBTOKEN,
  __module__ = 'go.chromium.org.luci.server.auth.delegation.messages.delegation_pb2'
  # @@protoc_insertion_point(class_scope:messages.Subtoken)
  ))
_sym_db.RegisterMessage(Subtoken)


# @@protoc_insertion_point(module_scope)
