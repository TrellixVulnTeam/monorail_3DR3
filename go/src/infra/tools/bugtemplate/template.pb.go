// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/tools/bugtemplate/template.proto

package main

import (
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
	math "math"
)

// Reference imports to suppress errors if they are not otherwise used.
var _ = proto.Marshal
var _ = fmt.Errorf
var _ = math.Inf

// This is a compile-time assertion to ensure that this generated file
// is compatible with the proto package it is being compiled against.
// A compilation error at this line likely means your copy of the
// proto package needs to be updated.
const _ = proto.ProtoPackageIsVersion3 // please upgrade the proto package

type Priority int32

const (
	Priority_PriUnset Priority = 0
	Priority_P0       Priority = 1
	Priority_P1       Priority = 2
	Priority_P2       Priority = 3
	Priority_P3       Priority = 4
)

var Priority_name = map[int32]string{
	0: "PriUnset",
	1: "P0",
	2: "P1",
	3: "P2",
	4: "P3",
}

var Priority_value = map[string]int32{
	"PriUnset": 0,
	"P0":       1,
	"P1":       2,
	"P2":       3,
	"P3":       4,
}

func (x Priority) String() string {
	return proto.EnumName(Priority_name, int32(x))
}

func (Priority) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_f970d99fe2dcc709, []int{0}
}

type Type int32

const (
	Type_TypeUnset Type = 0
	Type_Bug       Type = 1
	Type_Feature   Type = 2
	Type_Task      Type = 3
)

var Type_name = map[int32]string{
	0: "TypeUnset",
	1: "Bug",
	2: "Feature",
	3: "Task",
}

var Type_value = map[string]int32{
	"TypeUnset": 0,
	"Bug":       1,
	"Feature":   2,
	"Task":      3,
}

func (x Type) String() string {
	return proto.EnumName(Type_name, int32(x))
}

func (Type) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_f970d99fe2dcc709, []int{1}
}

// A monorail issue template.
type Template struct {
	// A one line description of the issue.
	Summary string `protobuf:"bytes,1,opt,name=summary,proto3" json:"summary,omitempty"`
	// The text body of the issue.
	Description string `protobuf:"bytes,2,opt,name=description,proto3" json:"description,omitempty"`
	// Emails of people participating in the issue discussion.
	Cc []string `protobuf:"bytes,3,rep,name=cc,proto3" json:"cc,omitempty"`
	// Monorail components for this issue.
	Components []string `protobuf:"bytes,4,rep,name=components,proto3" json:"components,omitempty"`
	// Issue priority.
	Pri Priority `protobuf:"varint,5,opt,name=pri,proto3,enum=bugtemplate.Priority" json:"pri,omitempty"`
	// Issue type.
	Type Type `protobuf:"varint,6,opt,name=type,proto3,enum=bugtemplate.Type" json:"type,omitempty"`
	// Bug labels.
	Labels []string `protobuf:"bytes,7,rep,name=labels,proto3" json:"labels,omitempty"`
	// Bugs which should be blocked on the one being filed.
	// Supports "project:number" notation.
	Blocking             []string `protobuf:"bytes,8,rep,name=blocking,proto3" json:"blocking,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Template) Reset()         { *m = Template{} }
func (m *Template) String() string { return proto.CompactTextString(m) }
func (*Template) ProtoMessage()    {}
func (*Template) Descriptor() ([]byte, []int) {
	return fileDescriptor_f970d99fe2dcc709, []int{0}
}

func (m *Template) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Template.Unmarshal(m, b)
}
func (m *Template) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Template.Marshal(b, m, deterministic)
}
func (m *Template) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Template.Merge(m, src)
}
func (m *Template) XXX_Size() int {
	return xxx_messageInfo_Template.Size(m)
}
func (m *Template) XXX_DiscardUnknown() {
	xxx_messageInfo_Template.DiscardUnknown(m)
}

var xxx_messageInfo_Template proto.InternalMessageInfo

func (m *Template) GetSummary() string {
	if m != nil {
		return m.Summary
	}
	return ""
}

func (m *Template) GetDescription() string {
	if m != nil {
		return m.Description
	}
	return ""
}

func (m *Template) GetCc() []string {
	if m != nil {
		return m.Cc
	}
	return nil
}

func (m *Template) GetComponents() []string {
	if m != nil {
		return m.Components
	}
	return nil
}

func (m *Template) GetPri() Priority {
	if m != nil {
		return m.Pri
	}
	return Priority_PriUnset
}

func (m *Template) GetType() Type {
	if m != nil {
		return m.Type
	}
	return Type_TypeUnset
}

func (m *Template) GetLabels() []string {
	if m != nil {
		return m.Labels
	}
	return nil
}

func (m *Template) GetBlocking() []string {
	if m != nil {
		return m.Blocking
	}
	return nil
}

func init() {
	proto.RegisterEnum("bugtemplate.Priority", Priority_name, Priority_value)
	proto.RegisterEnum("bugtemplate.Type", Type_name, Type_value)
	proto.RegisterType((*Template)(nil), "bugtemplate.Template")
}

func init() {
	proto.RegisterFile("infra/tools/bugtemplate/template.proto", fileDescriptor_f970d99fe2dcc709)
}

var fileDescriptor_f970d99fe2dcc709 = []byte{
	// 301 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x54, 0x51, 0xcd, 0x4b, 0xf3, 0x30,
	0x18, 0x7f, 0xfb, 0xf1, 0xb6, 0xdd, 0xb3, 0xf7, 0x1d, 0xf1, 0x01, 0x25, 0x78, 0x90, 0x22, 0xa8,
	0x63, 0x87, 0x4d, 0x37, 0x04, 0xcf, 0x3b, 0x78, 0x1e, 0x65, 0x5e, 0xbc, 0xa5, 0x31, 0x8e, 0xb0,
	0x36, 0x09, 0x49, 0x7a, 0xe8, 0xbf, 0xee, 0x49, 0x16, 0x56, 0xa9, 0xa7, 0xdf, 0x67, 0xf8, 0x05,
	0x1e, 0xb8, 0x97, 0xea, 0xd3, 0xb2, 0x95, 0xd7, 0xba, 0x71, 0xab, 0xba, 0x3b, 0x78, 0xd1, 0x9a,
	0x86, 0x79, 0xb1, 0x1a, 0xc8, 0xd2, 0x58, 0xed, 0x35, 0x4e, 0x47, 0xd9, 0xed, 0x57, 0x04, 0xc5,
	0xfe, 0x2c, 0x90, 0x42, 0xee, 0xba, 0xb6, 0x65, 0xb6, 0xa7, 0x51, 0x19, 0xcd, 0x27, 0xd5, 0x20,
	0xb1, 0x84, 0xe9, 0x87, 0x70, 0xdc, 0x4a, 0xe3, 0xa5, 0x56, 0x34, 0x0e, 0xe9, 0xd8, 0xc2, 0x19,
	0xc4, 0x9c, 0xd3, 0xa4, 0x4c, 0xe6, 0x93, 0x2a, 0xe6, 0x1c, 0x6f, 0x00, 0xb8, 0x6e, 0x8d, 0x56,
	0x42, 0x79, 0x47, 0xd3, 0xe0, 0x8f, 0x1c, 0x7c, 0x80, 0xc4, 0x58, 0x49, 0xff, 0x96, 0xd1, 0x7c,
	0xb6, 0xbe, 0x5c, 0x8e, 0xfe, 0xb4, 0xdc, 0x59, 0xa9, 0xad, 0xf4, 0x7d, 0x75, 0x6a, 0xe0, 0x1d,
	0xa4, 0xbe, 0x37, 0x82, 0x66, 0xa1, 0x79, 0xf1, 0xab, 0xb9, 0xef, 0x8d, 0xa8, 0x42, 0x8c, 0x57,
	0x90, 0x35, 0xac, 0x16, 0x8d, 0xa3, 0x79, 0xd8, 0x3a, 0x2b, 0xbc, 0x86, 0xa2, 0x6e, 0x34, 0x3f,
	0x4a, 0x75, 0xa0, 0x45, 0x48, 0x7e, 0xf4, 0xe2, 0x05, 0x8a, 0x61, 0x0b, 0xff, 0x05, 0xfe, 0xa6,
	0x9c, 0xf0, 0xe4, 0x0f, 0x66, 0x10, 0xef, 0x1e, 0x49, 0x14, 0xf0, 0x89, 0xc4, 0x01, 0xd7, 0x24,
	0x09, 0xb8, 0x21, 0xe9, 0xe2, 0x19, 0xd2, 0xd3, 0x36, 0xfe, 0x87, 0xc9, 0x09, 0x87, 0x67, 0x39,
	0x24, 0xdb, 0xee, 0x40, 0x22, 0x9c, 0x42, 0xfe, 0x2a, 0x98, 0xef, 0xac, 0x20, 0x31, 0x16, 0x90,
	0xee, 0x99, 0x3b, 0x92, 0x64, 0x9b, 0xbd, 0xa7, 0x2d, 0x93, 0xaa, 0xce, 0xc2, 0x25, 0x36, 0xdf,
	0x01, 0x00, 0x00, 0xff, 0xff, 0xcf, 0xc1, 0xf0, 0x27, 0xb3, 0x01, 0x00, 0x00,
}
