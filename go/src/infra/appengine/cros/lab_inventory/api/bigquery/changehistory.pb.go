// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/appengine/cros/lab_inventory/api/bigquery/changehistory.proto

package apibq

import (
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
	timestamp "github.com/golang/protobuf/ptypes/timestamp"
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

type ChangeHistory struct {
	Id                   string               `protobuf:"bytes,1,opt,name=id,proto3" json:"id,omitempty"`
	Hostname             string               `protobuf:"bytes,2,opt,name=hostname,proto3" json:"hostname,omitempty"`
	Label                string               `protobuf:"bytes,3,opt,name=label,proto3" json:"label,omitempty"`
	OldValue             string               `protobuf:"bytes,4,opt,name=old_value,json=oldValue,proto3" json:"old_value,omitempty"`
	NewValue             string               `protobuf:"bytes,5,opt,name=new_value,json=newValue,proto3" json:"new_value,omitempty"`
	UpdatedTime          *timestamp.Timestamp `protobuf:"bytes,6,opt,name=updated_time,json=updatedTime,proto3" json:"updated_time,omitempty"`
	ByWhom               *ChangeHistory_User  `protobuf:"bytes,7,opt,name=by_whom,json=byWhom,proto3" json:"by_whom,omitempty"`
	Comment              string               `protobuf:"bytes,8,opt,name=comment,proto3" json:"comment,omitempty"`
	XXX_NoUnkeyedLiteral struct{}             `json:"-"`
	XXX_unrecognized     []byte               `json:"-"`
	XXX_sizecache        int32                `json:"-"`
}

func (m *ChangeHistory) Reset()         { *m = ChangeHistory{} }
func (m *ChangeHistory) String() string { return proto.CompactTextString(m) }
func (*ChangeHistory) ProtoMessage()    {}
func (*ChangeHistory) Descriptor() ([]byte, []int) {
	return fileDescriptor_534ece429dd22f13, []int{0}
}

func (m *ChangeHistory) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ChangeHistory.Unmarshal(m, b)
}
func (m *ChangeHistory) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ChangeHistory.Marshal(b, m, deterministic)
}
func (m *ChangeHistory) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ChangeHistory.Merge(m, src)
}
func (m *ChangeHistory) XXX_Size() int {
	return xxx_messageInfo_ChangeHistory.Size(m)
}
func (m *ChangeHistory) XXX_DiscardUnknown() {
	xxx_messageInfo_ChangeHistory.DiscardUnknown(m)
}

var xxx_messageInfo_ChangeHistory proto.InternalMessageInfo

func (m *ChangeHistory) GetId() string {
	if m != nil {
		return m.Id
	}
	return ""
}

func (m *ChangeHistory) GetHostname() string {
	if m != nil {
		return m.Hostname
	}
	return ""
}

func (m *ChangeHistory) GetLabel() string {
	if m != nil {
		return m.Label
	}
	return ""
}

func (m *ChangeHistory) GetOldValue() string {
	if m != nil {
		return m.OldValue
	}
	return ""
}

func (m *ChangeHistory) GetNewValue() string {
	if m != nil {
		return m.NewValue
	}
	return ""
}

func (m *ChangeHistory) GetUpdatedTime() *timestamp.Timestamp {
	if m != nil {
		return m.UpdatedTime
	}
	return nil
}

func (m *ChangeHistory) GetByWhom() *ChangeHistory_User {
	if m != nil {
		return m.ByWhom
	}
	return nil
}

func (m *ChangeHistory) GetComment() string {
	if m != nil {
		return m.Comment
	}
	return ""
}

type ChangeHistory_User struct {
	Name                 string   `protobuf:"bytes,1,opt,name=name,proto3" json:"name,omitempty"`
	Email                string   `protobuf:"bytes,2,opt,name=email,proto3" json:"email,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *ChangeHistory_User) Reset()         { *m = ChangeHistory_User{} }
func (m *ChangeHistory_User) String() string { return proto.CompactTextString(m) }
func (*ChangeHistory_User) ProtoMessage()    {}
func (*ChangeHistory_User) Descriptor() ([]byte, []int) {
	return fileDescriptor_534ece429dd22f13, []int{0, 0}
}

func (m *ChangeHistory_User) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ChangeHistory_User.Unmarshal(m, b)
}
func (m *ChangeHistory_User) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ChangeHistory_User.Marshal(b, m, deterministic)
}
func (m *ChangeHistory_User) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ChangeHistory_User.Merge(m, src)
}
func (m *ChangeHistory_User) XXX_Size() int {
	return xxx_messageInfo_ChangeHistory_User.Size(m)
}
func (m *ChangeHistory_User) XXX_DiscardUnknown() {
	xxx_messageInfo_ChangeHistory_User.DiscardUnknown(m)
}

var xxx_messageInfo_ChangeHistory_User proto.InternalMessageInfo

func (m *ChangeHistory_User) GetName() string {
	if m != nil {
		return m.Name
	}
	return ""
}

func (m *ChangeHistory_User) GetEmail() string {
	if m != nil {
		return m.Email
	}
	return ""
}

func init() {
	proto.RegisterType((*ChangeHistory)(nil), "apibq.ChangeHistory")
	proto.RegisterType((*ChangeHistory_User)(nil), "apibq.ChangeHistory.User")
}

func init() {
	proto.RegisterFile("infra/appengine/cros/lab_inventory/api/bigquery/changehistory.proto", fileDescriptor_534ece429dd22f13)
}

var fileDescriptor_534ece429dd22f13 = []byte{
	// 309 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x54, 0x90, 0x3b, 0x4f, 0xf3, 0x30,
	0x14, 0x86, 0xd5, 0x7c, 0xe9, 0xcd, 0xfd, 0x60, 0xb0, 0x18, 0x4c, 0x18, 0xa8, 0x98, 0x3a, 0xd9,
	0xa8, 0xcc, 0x4c, 0x5d, 0x98, 0x2b, 0x2e, 0x63, 0x64, 0x37, 0xa7, 0x89, 0x25, 0xdf, 0x9a, 0x38,
	0xad, 0xf2, 0x17, 0xf9, 0x55, 0xc8, 0x76, 0x83, 0xc4, 0xf8, 0x9e, 0xe7, 0xbc, 0xd2, 0x79, 0x0e,
	0xda, 0x49, 0x73, 0x6c, 0x39, 0xe3, 0xce, 0x81, 0xa9, 0xa5, 0x01, 0x76, 0x68, 0x6d, 0xc7, 0x14,
	0x17, 0xa5, 0x34, 0x67, 0x30, 0xde, 0xb6, 0x03, 0xe3, 0x4e, 0x32, 0x21, 0xeb, 0x53, 0x0f, 0xed,
	0xc0, 0x0e, 0x0d, 0x37, 0x35, 0x34, 0xb2, 0x0b, 0x88, 0xba, 0xd6, 0x7a, 0x8b, 0xa7, 0xdc, 0x49,
	0x71, 0x2a, 0x1e, 0x6b, 0x6b, 0x6b, 0x05, 0x2c, 0x0e, 0x45, 0x7f, 0x64, 0x5e, 0x6a, 0xe8, 0x3c,
	0xd7, 0x2e, 0xed, 0x3d, 0x7d, 0x67, 0xe8, 0x66, 0x17, 0xfb, 0x6f, 0xa9, 0x8f, 0x6f, 0x51, 0x26,
	0x2b, 0x32, 0x59, 0x4f, 0x36, 0xcb, 0x7d, 0x26, 0x2b, 0x5c, 0xa0, 0x45, 0x63, 0x3b, 0x6f, 0xb8,
	0x06, 0x92, 0xc5, 0xe9, 0x6f, 0xc6, 0x77, 0x68, 0xaa, 0xb8, 0x00, 0x45, 0xfe, 0x45, 0x90, 0x02,
	0x7e, 0x40, 0x4b, 0xab, 0xaa, 0xf2, 0xcc, 0x55, 0x0f, 0x24, 0x4f, 0x15, 0xab, 0xaa, 0xcf, 0x90,
	0x03, 0x34, 0x70, 0xb9, 0xc2, 0x69, 0x82, 0x06, 0x2e, 0x09, 0xbe, 0xa2, 0xff, 0xbd, 0xab, 0xb8,
	0x87, 0xaa, 0x0c, 0x87, 0x92, 0xd9, 0x7a, 0xb2, 0x59, 0x6d, 0x0b, 0x9a, 0x2c, 0xe8, 0x68, 0x41,
	0xdf, 0x47, 0x8b, 0xfd, 0xea, 0xba, 0x1f, 0x26, 0x78, 0x8b, 0xe6, 0x62, 0x28, 0x2f, 0x8d, 0xd5,
	0x64, 0x1e, 0x9b, 0xf7, 0x34, 0xbe, 0x81, 0xfe, 0x31, 0xa4, 0x1f, 0x1d, 0xb4, 0xfb, 0x99, 0x18,
	0xbe, 0x1a, 0xab, 0x31, 0x41, 0xf3, 0x83, 0xd5, 0x1a, 0x8c, 0x27, 0x8b, 0x78, 0xcd, 0x18, 0x8b,
	0x67, 0x94, 0x87, 0x4d, 0x8c, 0x51, 0x1e, 0xe5, 0xd3, 0x4b, 0xf2, 0x51, 0x1c, 0x34, 0x97, 0xea,
	0xfa, 0x91, 0x14, 0xc4, 0x2c, 0x1e, 0xf8, 0xf2, 0x13, 0x00, 0x00, 0xff, 0xff, 0xae, 0x71, 0x55,
	0xe5, 0xc2, 0x01, 0x00, 0x00,
}