// Code generated by protoc-gen-go. DO NOT EDIT.
// source: common.proto

package inventory

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

// NEXT TAG: 4
type Environment int32

const (
	Environment_ENVIRONMENT_INVALID Environment = 0
	Environment_ENVIRONMENT_PROD    Environment = 1
	Environment_ENVIRONMENT_STAGING Environment = 2
	Environment_ENVIRONMENT_SKYLAB  Environment = 3 // Deprecated: Do not use.
)

var Environment_name = map[int32]string{
	0: "ENVIRONMENT_INVALID",
	1: "ENVIRONMENT_PROD",
	2: "ENVIRONMENT_STAGING",
	3: "ENVIRONMENT_SKYLAB",
}

var Environment_value = map[string]int32{
	"ENVIRONMENT_INVALID": 0,
	"ENVIRONMENT_PROD":    1,
	"ENVIRONMENT_STAGING": 2,
	"ENVIRONMENT_SKYLAB":  3,
}

func (x Environment) Enum() *Environment {
	p := new(Environment)
	*p = x
	return p
}

func (x Environment) String() string {
	return proto.EnumName(Environment_name, int32(x))
}

func (x *Environment) UnmarshalJSON(data []byte) error {
	value, err := proto.UnmarshalJSONEnum(Environment_value, data, "Environment")
	if err != nil {
		return err
	}
	*x = Environment(value)
	return nil
}

func (Environment) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_555bd8c177793206, []int{0}
}

type Timestamp struct {
	Seconds              *int64   `protobuf:"varint,1,opt,name=seconds" json:"seconds,omitempty"`
	Nanos                *int32   `protobuf:"varint,2,opt,name=nanos" json:"nanos,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Timestamp) Reset()         { *m = Timestamp{} }
func (m *Timestamp) String() string { return proto.CompactTextString(m) }
func (*Timestamp) ProtoMessage()    {}
func (*Timestamp) Descriptor() ([]byte, []int) {
	return fileDescriptor_555bd8c177793206, []int{0}
}

func (m *Timestamp) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Timestamp.Unmarshal(m, b)
}
func (m *Timestamp) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Timestamp.Marshal(b, m, deterministic)
}
func (m *Timestamp) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Timestamp.Merge(m, src)
}
func (m *Timestamp) XXX_Size() int {
	return xxx_messageInfo_Timestamp.Size(m)
}
func (m *Timestamp) XXX_DiscardUnknown() {
	xxx_messageInfo_Timestamp.DiscardUnknown(m)
}

var xxx_messageInfo_Timestamp proto.InternalMessageInfo

func (m *Timestamp) GetSeconds() int64 {
	if m != nil && m.Seconds != nil {
		return *m.Seconds
	}
	return 0
}

func (m *Timestamp) GetNanos() int32 {
	if m != nil && m.Nanos != nil {
		return *m.Nanos
	}
	return 0
}

func init() {
	proto.RegisterEnum("chrome.chromeos_infra.skylab.proto.inventory.Environment", Environment_name, Environment_value)
	proto.RegisterType((*Timestamp)(nil), "chrome.chromeos_infra.skylab.proto.inventory.Timestamp")
}

func init() {
	proto.RegisterFile("common.proto", fileDescriptor_555bd8c177793206)
}

var fileDescriptor_555bd8c177793206 = []byte{
	// 213 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0xe2, 0xe2, 0x49, 0xce, 0xcf, 0xcd,
	0xcd, 0xcf, 0xd3, 0x2b, 0x28, 0xca, 0x2f, 0xc9, 0x17, 0xd2, 0x49, 0xce, 0x28, 0xca, 0xcf, 0x4d,
	0xd5, 0x83, 0x50, 0xf9, 0xc5, 0xf1, 0x99, 0x79, 0x69, 0x45, 0x89, 0x7a, 0xc5, 0xd9, 0x95, 0x39,
	0x89, 0x49, 0x10, 0x35, 0x7a, 0x99, 0x79, 0x65, 0xa9, 0x79, 0x25, 0xf9, 0x45, 0x95, 0x4a, 0xd6,
	0x5c, 0x9c, 0x21, 0x99, 0xb9, 0xa9, 0xc5, 0x25, 0x89, 0xb9, 0x05, 0x42, 0x12, 0x5c, 0xec, 0xc5,
	0xa9, 0xc9, 0xf9, 0x79, 0x29, 0xc5, 0x12, 0x8c, 0x0a, 0x8c, 0x1a, 0xcc, 0x41, 0x30, 0xae, 0x90,
	0x08, 0x17, 0x6b, 0x5e, 0x62, 0x5e, 0x7e, 0xb1, 0x04, 0x93, 0x02, 0xa3, 0x06, 0x6b, 0x10, 0x84,
	0xa3, 0x55, 0xc8, 0xc5, 0xed, 0x9a, 0x57, 0x96, 0x59, 0x94, 0x9f, 0x97, 0x9b, 0x9a, 0x57, 0x22,
	0x24, 0xce, 0x25, 0xec, 0xea, 0x17, 0xe6, 0x19, 0xe4, 0xef, 0xe7, 0xeb, 0xea, 0x17, 0x12, 0xef,
	0xe9, 0x17, 0xe6, 0xe8, 0xe3, 0xe9, 0x22, 0xc0, 0x20, 0x24, 0xc2, 0x25, 0x80, 0x2c, 0x11, 0x10,
	0xe4, 0xef, 0x22, 0xc0, 0x88, 0xae, 0x3c, 0x38, 0xc4, 0xd1, 0xdd, 0xd3, 0xcf, 0x5d, 0x80, 0x49,
	0x48, 0x8a, 0x4b, 0x08, 0x45, 0xc2, 0x3b, 0xd2, 0xc7, 0xd1, 0x49, 0x80, 0x59, 0x8a, 0x89, 0x83,
	0xd1, 0x89, 0x3b, 0x8a, 0x13, 0xee, 0x78, 0x40, 0x00, 0x00, 0x00, 0xff, 0xff, 0xea, 0xf9, 0x8e,
	0xd3, 0xf9, 0x00, 0x00, 0x00,
}