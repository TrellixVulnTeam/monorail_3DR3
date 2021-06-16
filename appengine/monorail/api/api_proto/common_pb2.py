# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: api/api_proto/common.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='api/api_proto/common.proto',
  package='monorail',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n\x1a\x61pi/api_proto/common.proto\x12\x08monorail\"0\n\x0c\x43omponentRef\x12\x0c\n\x04path\x18\x01 \x01(\t\x12\x12\n\nis_derived\x18\x02 \x01(\x08\"j\n\x08\x46ieldRef\x12\x10\n\x08\x66ield_id\x18\x01 \x01(\x04\x12\x12\n\nfield_name\x18\x02 \x01(\t\x12!\n\x04type\x18\x03 \x01(\x0e\x32\x13.monorail.FieldType\x12\x15\n\rapproval_name\x18\x04 \x01(\t\"-\n\x08LabelRef\x12\r\n\x05label\x18\x01 \x01(\t\x12\x12\n\nis_derived\x18\x02 \x01(\x08\"C\n\tStatusRef\x12\x0e\n\x06status\x18\x01 \x01(\t\x12\x12\n\nmeans_open\x18\x02 \x01(\x08\x12\x12\n\nis_derived\x18\x03 \x01(\x08\"J\n\x08IssueRef\x12\x14\n\x0cproject_name\x18\x01 \x01(\t\x12\x10\n\x08local_id\x18\x02 \x01(\r\x12\x16\n\x0e\x65xt_identifier\x18\x03 \x01(\t\"D\n\x07UserRef\x12\x0f\n\x07user_id\x18\x01 \x01(\x04\x12\x14\n\x0c\x64isplay_name\x18\x02 \x01(\t\x12\x12\n\nis_derived\x18\x03 \x01(\x08\"P\n\nHotlistRef\x12\x12\n\nhotlist_id\x18\x01 \x01(\x04\x12\x0c\n\x04name\x18\x02 \x01(\t\x12 \n\x05owner\x18\x03 \x01(\x0b\x32\x11.monorail.UserRef\")\n\x0bValueAndWhy\x12\r\n\x05value\x18\x01 \x01(\t\x12\x0b\n\x03why\x18\x02 \x01(\t\".\n\nPagination\x12\x11\n\tmax_items\x18\x01 \x01(\r\x12\r\n\x05start\x18\x02 \x01(\r\"R\n\nSavedQuery\x12\x10\n\x08query_id\x18\x01 \x01(\x04\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\r\n\x05query\x18\x03 \x01(\t\x12\x15\n\rproject_names\x18\x04 \x03(\t*\x91\x01\n\tFieldType\x12\x0b\n\x07NO_TYPE\x10\x00\x12\r\n\tENUM_TYPE\x10\x01\x12\x0c\n\x08INT_TYPE\x10\x02\x12\x0c\n\x08STR_TYPE\x10\x03\x12\r\n\tUSER_TYPE\x10\x04\x12\r\n\tDATE_TYPE\x10\x05\x12\r\n\tBOOL_TYPE\x10\x06\x12\x0c\n\x08URL_TYPE\x10\x07\x12\x11\n\rAPPROVAL_TYPE\x10\x08\x62\x06proto3')
)

_FIELDTYPE = _descriptor.EnumDescriptor(
  name='FieldType',
  full_name='monorail.FieldType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='NO_TYPE', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ENUM_TYPE', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INT_TYPE', index=2, number=2,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='STR_TYPE', index=3, number=3,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='USER_TYPE', index=4, number=4,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DATE_TYPE', index=5, number=5,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BOOL_TYPE', index=6, number=6,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='URL_TYPE', index=7, number=7,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='APPROVAL_TYPE', index=8, number=8,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=718,
  serialized_end=863,
)
_sym_db.RegisterEnumDescriptor(_FIELDTYPE)

FieldType = enum_type_wrapper.EnumTypeWrapper(_FIELDTYPE)
NO_TYPE = 0
ENUM_TYPE = 1
INT_TYPE = 2
STR_TYPE = 3
USER_TYPE = 4
DATE_TYPE = 5
BOOL_TYPE = 6
URL_TYPE = 7
APPROVAL_TYPE = 8



_COMPONENTREF = _descriptor.Descriptor(
  name='ComponentRef',
  full_name='monorail.ComponentRef',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='path', full_name='monorail.ComponentRef.path', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='is_derived', full_name='monorail.ComponentRef.is_derived', index=1,
      number=2, type=8, cpp_type=7, label=1,
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
  serialized_start=40,
  serialized_end=88,
)


_FIELDREF = _descriptor.Descriptor(
  name='FieldRef',
  full_name='monorail.FieldRef',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='field_id', full_name='monorail.FieldRef.field_id', index=0,
      number=1, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='field_name', full_name='monorail.FieldRef.field_name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='type', full_name='monorail.FieldRef.type', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='approval_name', full_name='monorail.FieldRef.approval_name', index=3,
      number=4, type=9, cpp_type=9, label=1,
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
  serialized_start=90,
  serialized_end=196,
)


_LABELREF = _descriptor.Descriptor(
  name='LabelRef',
  full_name='monorail.LabelRef',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='label', full_name='monorail.LabelRef.label', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='is_derived', full_name='monorail.LabelRef.is_derived', index=1,
      number=2, type=8, cpp_type=7, label=1,
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
  serialized_start=198,
  serialized_end=243,
)


_STATUSREF = _descriptor.Descriptor(
  name='StatusRef',
  full_name='monorail.StatusRef',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='status', full_name='monorail.StatusRef.status', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='means_open', full_name='monorail.StatusRef.means_open', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='is_derived', full_name='monorail.StatusRef.is_derived', index=2,
      number=3, type=8, cpp_type=7, label=1,
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
  serialized_start=245,
  serialized_end=312,
)


_ISSUEREF = _descriptor.Descriptor(
  name='IssueRef',
  full_name='monorail.IssueRef',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='project_name', full_name='monorail.IssueRef.project_name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='local_id', full_name='monorail.IssueRef.local_id', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='ext_identifier', full_name='monorail.IssueRef.ext_identifier', index=2,
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
  serialized_start=314,
  serialized_end=388,
)


_USERREF = _descriptor.Descriptor(
  name='UserRef',
  full_name='monorail.UserRef',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='user_id', full_name='monorail.UserRef.user_id', index=0,
      number=1, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='display_name', full_name='monorail.UserRef.display_name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='is_derived', full_name='monorail.UserRef.is_derived', index=2,
      number=3, type=8, cpp_type=7, label=1,
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
  serialized_start=390,
  serialized_end=458,
)


_HOTLISTREF = _descriptor.Descriptor(
  name='HotlistRef',
  full_name='monorail.HotlistRef',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='hotlist_id', full_name='monorail.HotlistRef.hotlist_id', index=0,
      number=1, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='monorail.HotlistRef.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='owner', full_name='monorail.HotlistRef.owner', index=2,
      number=3, type=11, cpp_type=10, label=1,
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
  serialized_start=460,
  serialized_end=540,
)


_VALUEANDWHY = _descriptor.Descriptor(
  name='ValueAndWhy',
  full_name='monorail.ValueAndWhy',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='value', full_name='monorail.ValueAndWhy.value', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='why', full_name='monorail.ValueAndWhy.why', index=1,
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
  serialized_start=542,
  serialized_end=583,
)


_PAGINATION = _descriptor.Descriptor(
  name='Pagination',
  full_name='monorail.Pagination',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='max_items', full_name='monorail.Pagination.max_items', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='start', full_name='monorail.Pagination.start', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
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
  serialized_start=585,
  serialized_end=631,
)


_SAVEDQUERY = _descriptor.Descriptor(
  name='SavedQuery',
  full_name='monorail.SavedQuery',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='query_id', full_name='monorail.SavedQuery.query_id', index=0,
      number=1, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='name', full_name='monorail.SavedQuery.name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='query', full_name='monorail.SavedQuery.query', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='project_names', full_name='monorail.SavedQuery.project_names', index=3,
      number=4, type=9, cpp_type=9, label=3,
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
  serialized_start=633,
  serialized_end=715,
)

_FIELDREF.fields_by_name['type'].enum_type = _FIELDTYPE
_HOTLISTREF.fields_by_name['owner'].message_type = _USERREF
DESCRIPTOR.message_types_by_name['ComponentRef'] = _COMPONENTREF
DESCRIPTOR.message_types_by_name['FieldRef'] = _FIELDREF
DESCRIPTOR.message_types_by_name['LabelRef'] = _LABELREF
DESCRIPTOR.message_types_by_name['StatusRef'] = _STATUSREF
DESCRIPTOR.message_types_by_name['IssueRef'] = _ISSUEREF
DESCRIPTOR.message_types_by_name['UserRef'] = _USERREF
DESCRIPTOR.message_types_by_name['HotlistRef'] = _HOTLISTREF
DESCRIPTOR.message_types_by_name['ValueAndWhy'] = _VALUEANDWHY
DESCRIPTOR.message_types_by_name['Pagination'] = _PAGINATION
DESCRIPTOR.message_types_by_name['SavedQuery'] = _SAVEDQUERY
DESCRIPTOR.enum_types_by_name['FieldType'] = _FIELDTYPE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

ComponentRef = _reflection.GeneratedProtocolMessageType('ComponentRef', (_message.Message,), dict(
  DESCRIPTOR = _COMPONENTREF,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.ComponentRef)
  ))
_sym_db.RegisterMessage(ComponentRef)

FieldRef = _reflection.GeneratedProtocolMessageType('FieldRef', (_message.Message,), dict(
  DESCRIPTOR = _FIELDREF,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.FieldRef)
  ))
_sym_db.RegisterMessage(FieldRef)

LabelRef = _reflection.GeneratedProtocolMessageType('LabelRef', (_message.Message,), dict(
  DESCRIPTOR = _LABELREF,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.LabelRef)
  ))
_sym_db.RegisterMessage(LabelRef)

StatusRef = _reflection.GeneratedProtocolMessageType('StatusRef', (_message.Message,), dict(
  DESCRIPTOR = _STATUSREF,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.StatusRef)
  ))
_sym_db.RegisterMessage(StatusRef)

IssueRef = _reflection.GeneratedProtocolMessageType('IssueRef', (_message.Message,), dict(
  DESCRIPTOR = _ISSUEREF,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.IssueRef)
  ))
_sym_db.RegisterMessage(IssueRef)

UserRef = _reflection.GeneratedProtocolMessageType('UserRef', (_message.Message,), dict(
  DESCRIPTOR = _USERREF,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.UserRef)
  ))
_sym_db.RegisterMessage(UserRef)

HotlistRef = _reflection.GeneratedProtocolMessageType('HotlistRef', (_message.Message,), dict(
  DESCRIPTOR = _HOTLISTREF,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.HotlistRef)
  ))
_sym_db.RegisterMessage(HotlistRef)

ValueAndWhy = _reflection.GeneratedProtocolMessageType('ValueAndWhy', (_message.Message,), dict(
  DESCRIPTOR = _VALUEANDWHY,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.ValueAndWhy)
  ))
_sym_db.RegisterMessage(ValueAndWhy)

Pagination = _reflection.GeneratedProtocolMessageType('Pagination', (_message.Message,), dict(
  DESCRIPTOR = _PAGINATION,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.Pagination)
  ))
_sym_db.RegisterMessage(Pagination)

SavedQuery = _reflection.GeneratedProtocolMessageType('SavedQuery', (_message.Message,), dict(
  DESCRIPTOR = _SAVEDQUERY,
  __module__ = 'api.api_proto.common_pb2'
  # @@protoc_insertion_point(class_scope:monorail.SavedQuery)
  ))
_sym_db.RegisterMessage(SavedQuery)


# @@protoc_insertion_point(module_scope)
