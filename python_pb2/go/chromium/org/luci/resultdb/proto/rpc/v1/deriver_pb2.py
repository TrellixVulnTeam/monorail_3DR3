# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: go.chromium.org/luci/resultdb/proto/rpc/v1/deriver.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.api import field_behavior_pb2 as google_dot_api_dot_field__behavior__pb2
from go.chromium.org.luci.resultdb.proto.rpc.v1 import invocation_pb2 as go_dot_chromium_dot_org_dot_luci_dot_resultdb_dot_proto_dot_rpc_dot_v1_dot_invocation__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='go.chromium.org/luci/resultdb/proto/rpc/v1/deriver.proto',
  package='luci.resultdb.rpc.v1',
  syntax='proto3',
  serialized_options=_b('Z0go.chromium.org/luci/resultdb/proto/rpc/v1;rpcpb'),
  serialized_pb=_b('\n8go.chromium.org/luci/resultdb/proto/rpc/v1/deriver.proto\x12\x14luci.resultdb.rpc.v1\x1a\x1fgoogle/api/field_behavior.proto\x1a;go.chromium.org/luci/resultdb/proto/rpc/v1/invocation.proto\"\xb9\x01\n\x1f\x44\x65riveChromiumInvocationRequest\x12^\n\rswarming_task\x18\x01 \x01(\x0b\x32\x42.luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest.SwarmingTaskB\x03\xe0\x41\x02\x1a\x36\n\x0cSwarmingTask\x12\x15\n\x08hostname\x18\x01 \x01(\tB\x03\xe0\x41\x02\x12\x0f\n\x02id\x18\x02 \x01(\tB\x03\xe0\x41\x02*\x9e\x01\n/DeriveChromiumInvocationPreconditionFailureType\x12\x44\n@DERIVE_CHROMIUM_INVOCATION_PRECONDITION_FAILURE_TYPE_UNSPECIFIED\x10\x00\x12%\n!INCOMPLETE_CHROMIUM_SWARMING_TASK\x10\x01\x32\x80\x01\n\x07\x44\x65river\x12u\n\x18\x44\x65riveChromiumInvocation\x12\x35.luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest\x1a .luci.resultdb.rpc.v1.Invocation\"\x00\x42\x32Z0go.chromium.org/luci/resultdb/proto/rpc/v1;rpcpbb\x06proto3')
  ,
  dependencies=[google_dot_api_dot_field__behavior__pb2.DESCRIPTOR,go_dot_chromium_dot_org_dot_luci_dot_resultdb_dot_proto_dot_rpc_dot_v1_dot_invocation__pb2.DESCRIPTOR,])

_DERIVECHROMIUMINVOCATIONPRECONDITIONFAILURETYPE = _descriptor.EnumDescriptor(
  name='DeriveChromiumInvocationPreconditionFailureType',
  full_name='luci.resultdb.rpc.v1.DeriveChromiumInvocationPreconditionFailureType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='DERIVE_CHROMIUM_INVOCATION_PRECONDITION_FAILURE_TYPE_UNSPECIFIED', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INCOMPLETE_CHROMIUM_SWARMING_TASK', index=1, number=1,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=365,
  serialized_end=523,
)
_sym_db.RegisterEnumDescriptor(_DERIVECHROMIUMINVOCATIONPRECONDITIONFAILURETYPE)

DeriveChromiumInvocationPreconditionFailureType = enum_type_wrapper.EnumTypeWrapper(_DERIVECHROMIUMINVOCATIONPRECONDITIONFAILURETYPE)
DERIVE_CHROMIUM_INVOCATION_PRECONDITION_FAILURE_TYPE_UNSPECIFIED = 0
INCOMPLETE_CHROMIUM_SWARMING_TASK = 1



_DERIVECHROMIUMINVOCATIONREQUEST_SWARMINGTASK = _descriptor.Descriptor(
  name='SwarmingTask',
  full_name='luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest.SwarmingTask',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='hostname', full_name='luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest.SwarmingTask.hostname', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\340A\002'), file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='id', full_name='luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest.SwarmingTask.id', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\340A\002'), file=DESCRIPTOR),
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
  serialized_start=308,
  serialized_end=362,
)

_DERIVECHROMIUMINVOCATIONREQUEST = _descriptor.Descriptor(
  name='DeriveChromiumInvocationRequest',
  full_name='luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='swarming_task', full_name='luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest.swarming_task', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=_b('\340A\002'), file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[_DERIVECHROMIUMINVOCATIONREQUEST_SWARMINGTASK, ],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=177,
  serialized_end=362,
)

_DERIVECHROMIUMINVOCATIONREQUEST_SWARMINGTASK.containing_type = _DERIVECHROMIUMINVOCATIONREQUEST
_DERIVECHROMIUMINVOCATIONREQUEST.fields_by_name['swarming_task'].message_type = _DERIVECHROMIUMINVOCATIONREQUEST_SWARMINGTASK
DESCRIPTOR.message_types_by_name['DeriveChromiumInvocationRequest'] = _DERIVECHROMIUMINVOCATIONREQUEST
DESCRIPTOR.enum_types_by_name['DeriveChromiumInvocationPreconditionFailureType'] = _DERIVECHROMIUMINVOCATIONPRECONDITIONFAILURETYPE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

DeriveChromiumInvocationRequest = _reflection.GeneratedProtocolMessageType('DeriveChromiumInvocationRequest', (_message.Message,), dict(

  SwarmingTask = _reflection.GeneratedProtocolMessageType('SwarmingTask', (_message.Message,), dict(
    DESCRIPTOR = _DERIVECHROMIUMINVOCATIONREQUEST_SWARMINGTASK,
    __module__ = 'go.chromium.org.luci.resultdb.proto.rpc.v1.deriver_pb2'
    # @@protoc_insertion_point(class_scope:luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest.SwarmingTask)
    ))
  ,
  DESCRIPTOR = _DERIVECHROMIUMINVOCATIONREQUEST,
  __module__ = 'go.chromium.org.luci.resultdb.proto.rpc.v1.deriver_pb2'
  # @@protoc_insertion_point(class_scope:luci.resultdb.rpc.v1.DeriveChromiumInvocationRequest)
  ))
_sym_db.RegisterMessage(DeriveChromiumInvocationRequest)
_sym_db.RegisterMessage(DeriveChromiumInvocationRequest.SwarmingTask)


DESCRIPTOR._options = None
_DERIVECHROMIUMINVOCATIONREQUEST_SWARMINGTASK.fields_by_name['hostname']._options = None
_DERIVECHROMIUMINVOCATIONREQUEST_SWARMINGTASK.fields_by_name['id']._options = None
_DERIVECHROMIUMINVOCATIONREQUEST.fields_by_name['swarming_task']._options = None

_DERIVER = _descriptor.ServiceDescriptor(
  name='Deriver',
  full_name='luci.resultdb.rpc.v1.Deriver',
  file=DESCRIPTOR,
  index=0,
  serialized_options=None,
  serialized_start=526,
  serialized_end=654,
  methods=[
  _descriptor.MethodDescriptor(
    name='DeriveChromiumInvocation',
    full_name='luci.resultdb.rpc.v1.Deriver.DeriveChromiumInvocation',
    index=0,
    containing_service=None,
    input_type=_DERIVECHROMIUMINVOCATIONREQUEST,
    output_type=go_dot_chromium_dot_org_dot_luci_dot_resultdb_dot_proto_dot_rpc_dot_v1_dot_invocation__pb2._INVOCATION,
    serialized_options=None,
  ),
])
_sym_db.RegisterServiceDescriptor(_DERIVER)

DESCRIPTOR.services_by_name['Deriver'] = _DERIVER

# @@protoc_insertion_point(module_scope)
