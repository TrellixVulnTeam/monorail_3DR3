// Copyright 2020 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

// This file defines protobufs for features and related business
// objects, e.g., hotlists.

// Code generated by protoc-gen-go. DO NOT EDIT.
// versions:
// 	protoc-gen-go v1.24.0-devel
// 	protoc        v3.6.1
// source: api/v3/api_proto/feature_objects.proto

package monorail_v3

import (
	proto "github.com/golang/protobuf/proto"
	timestamp "github.com/golang/protobuf/ptypes/timestamp"
	_ "google.golang.org/genproto/googleapis/api/annotations"
	protoreflect "google.golang.org/protobuf/reflect/protoreflect"
	protoimpl "google.golang.org/protobuf/runtime/protoimpl"
	reflect "reflect"
	sync "sync"
)

const (
	// Verify that this generated code is sufficiently up-to-date.
	_ = protoimpl.EnforceVersion(20 - protoimpl.MinVersion)
	// Verify that runtime/protoimpl is sufficiently up-to-date.
	_ = protoimpl.EnforceVersion(protoimpl.MaxVersion - 20)
)

// This is a compile-time assertion that a sufficiently up-to-date version
// of the legacy proto package is being used.
const _ = proto.ProtoPackageIsVersion4

// Privacy level of a Hotlist.
// Next available tag: 2
type Hotlist_HotlistPrivacy int32

const (
	// This value is unused.
	Hotlist_HOTLIST_PRIVACY_UNSPECIFIED Hotlist_HotlistPrivacy = 0
	// Only the owner and editors of the hotlist can view the hotlist.
	Hotlist_PRIVATE Hotlist_HotlistPrivacy = 1
	// Anyone on the web can view the hotlist.
	Hotlist_PUBLIC Hotlist_HotlistPrivacy = 2
)

// Enum value maps for Hotlist_HotlistPrivacy.
var (
	Hotlist_HotlistPrivacy_name = map[int32]string{
		0: "HOTLIST_PRIVACY_UNSPECIFIED",
		1: "PRIVATE",
		2: "PUBLIC",
	}
	Hotlist_HotlistPrivacy_value = map[string]int32{
		"HOTLIST_PRIVACY_UNSPECIFIED": 0,
		"PRIVATE":                     1,
		"PUBLIC":                      2,
	}
)

func (x Hotlist_HotlistPrivacy) Enum() *Hotlist_HotlistPrivacy {
	p := new(Hotlist_HotlistPrivacy)
	*p = x
	return p
}

func (x Hotlist_HotlistPrivacy) String() string {
	return protoimpl.X.EnumStringOf(x.Descriptor(), protoreflect.EnumNumber(x))
}

func (Hotlist_HotlistPrivacy) Descriptor() protoreflect.EnumDescriptor {
	return file_api_v3_api_proto_feature_objects_proto_enumTypes[0].Descriptor()
}

func (Hotlist_HotlistPrivacy) Type() protoreflect.EnumType {
	return &file_api_v3_api_proto_feature_objects_proto_enumTypes[0]
}

func (x Hotlist_HotlistPrivacy) Number() protoreflect.EnumNumber {
	return protoreflect.EnumNumber(x)
}

// Deprecated: Use Hotlist_HotlistPrivacy.Descriptor instead.
func (Hotlist_HotlistPrivacy) EnumDescriptor() ([]byte, []int) {
	return file_api_v3_api_proto_feature_objects_proto_rawDescGZIP(), []int{0, 0}
}

// A user-owned list of Issues.
// Next available tag: 9
type Hotlist struct {
	state         protoimpl.MessageState
	sizeCache     protoimpl.SizeCache
	unknownFields protoimpl.UnknownFields

	// Resource name of the hotlist.
	Name string `protobuf:"bytes,1,opt,name=name,proto3" json:"name,omitempty"`
	// `display_name` must follow pattern found at `framework_bizobj.RE_HOTLIST_NAME_PATTERN`.
	DisplayName string `protobuf:"bytes,2,opt,name=display_name,json=displayName,proto3" json:"display_name,omitempty"`
	// Resource name of the hotlist owner.
	// Owners can update hotlist settings, editors, owner, and HotlistItems.
	// TODO(monorail:7023): field_behavior may be changed in the future.
	Owner string `protobuf:"bytes,3,opt,name=owner,proto3" json:"owner,omitempty"`
	// Resource names of the hotlist editors.
	// Editors can update hotlist HotlistItems.
	Editors []string `protobuf:"bytes,4,rep,name=editors,proto3" json:"editors,omitempty"`
	// Summary of the hotlist.
	Summary string `protobuf:"bytes,5,opt,name=summary,proto3" json:"summary,omitempty"`
	// More detailed description of the purpose of the hotlist.
	Description string `protobuf:"bytes,6,opt,name=description,proto3" json:"description,omitempty"`
	// Ordered list of default columns shown on hotlist's issues list view.
	DefaultColumns []*IssuesListColumn    `protobuf:"bytes,7,rep,name=default_columns,json=defaultColumns,proto3" json:"default_columns,omitempty"`
	HotlistPrivacy Hotlist_HotlistPrivacy `protobuf:"varint,8,opt,name=hotlist_privacy,json=hotlistPrivacy,proto3,enum=monorail.v3.Hotlist_HotlistPrivacy" json:"hotlist_privacy,omitempty"`
}

func (x *Hotlist) Reset() {
	*x = Hotlist{}
	if protoimpl.UnsafeEnabled {
		mi := &file_api_v3_api_proto_feature_objects_proto_msgTypes[0]
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		ms.StoreMessageInfo(mi)
	}
}

func (x *Hotlist) String() string {
	return protoimpl.X.MessageStringOf(x)
}

func (*Hotlist) ProtoMessage() {}

func (x *Hotlist) ProtoReflect() protoreflect.Message {
	mi := &file_api_v3_api_proto_feature_objects_proto_msgTypes[0]
	if protoimpl.UnsafeEnabled && x != nil {
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		if ms.LoadMessageInfo() == nil {
			ms.StoreMessageInfo(mi)
		}
		return ms
	}
	return mi.MessageOf(x)
}

// Deprecated: Use Hotlist.ProtoReflect.Descriptor instead.
func (*Hotlist) Descriptor() ([]byte, []int) {
	return file_api_v3_api_proto_feature_objects_proto_rawDescGZIP(), []int{0}
}

func (x *Hotlist) GetName() string {
	if x != nil {
		return x.Name
	}
	return ""
}

func (x *Hotlist) GetDisplayName() string {
	if x != nil {
		return x.DisplayName
	}
	return ""
}

func (x *Hotlist) GetOwner() string {
	if x != nil {
		return x.Owner
	}
	return ""
}

func (x *Hotlist) GetEditors() []string {
	if x != nil {
		return x.Editors
	}
	return nil
}

func (x *Hotlist) GetSummary() string {
	if x != nil {
		return x.Summary
	}
	return ""
}

func (x *Hotlist) GetDescription() string {
	if x != nil {
		return x.Description
	}
	return ""
}

func (x *Hotlist) GetDefaultColumns() []*IssuesListColumn {
	if x != nil {
		return x.DefaultColumns
	}
	return nil
}

func (x *Hotlist) GetHotlistPrivacy() Hotlist_HotlistPrivacy {
	if x != nil {
		return x.HotlistPrivacy
	}
	return Hotlist_HOTLIST_PRIVACY_UNSPECIFIED
}

// Represents the the position of an Issue in a Hotlist.
// Next available tag: 7
type HotlistItem struct {
	state         protoimpl.MessageState
	sizeCache     protoimpl.SizeCache
	unknownFields protoimpl.UnknownFields

	// Resource name of the HotlistItem.
	Name string `protobuf:"bytes,1,opt,name=name,proto3" json:"name,omitempty"`
	// The Issue associated with this item.
	Issue string `protobuf:"bytes,2,opt,name=issue,proto3" json:"issue,omitempty"`
	// Represents the item's position in the Hotlist in decreasing priority order.
	// Values will be from 1 to N (the size of the hotlist), each item having a unique rank.
	// Changes to rank must be made in `RerankHotlistItems`.
	Rank uint32 `protobuf:"varint,3,opt,name=rank,proto3" json:"rank,omitempty"`
	// Resource name of the adder of HotlistItem.
	Adder string `protobuf:"bytes,4,opt,name=adder,proto3" json:"adder,omitempty"`
	// The time this HotlistItem was added to the hotlist.
	CreateTime *timestamp.Timestamp `protobuf:"bytes,5,opt,name=create_time,json=createTime,proto3" json:"create_time,omitempty"`
	// User-provided additional details about this item.
	Note string `protobuf:"bytes,6,opt,name=note,proto3" json:"note,omitempty"`
}

func (x *HotlistItem) Reset() {
	*x = HotlistItem{}
	if protoimpl.UnsafeEnabled {
		mi := &file_api_v3_api_proto_feature_objects_proto_msgTypes[1]
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		ms.StoreMessageInfo(mi)
	}
}

func (x *HotlistItem) String() string {
	return protoimpl.X.MessageStringOf(x)
}

func (*HotlistItem) ProtoMessage() {}

func (x *HotlistItem) ProtoReflect() protoreflect.Message {
	mi := &file_api_v3_api_proto_feature_objects_proto_msgTypes[1]
	if protoimpl.UnsafeEnabled && x != nil {
		ms := protoimpl.X.MessageStateOf(protoimpl.Pointer(x))
		if ms.LoadMessageInfo() == nil {
			ms.StoreMessageInfo(mi)
		}
		return ms
	}
	return mi.MessageOf(x)
}

// Deprecated: Use HotlistItem.ProtoReflect.Descriptor instead.
func (*HotlistItem) Descriptor() ([]byte, []int) {
	return file_api_v3_api_proto_feature_objects_proto_rawDescGZIP(), []int{1}
}

func (x *HotlistItem) GetName() string {
	if x != nil {
		return x.Name
	}
	return ""
}

func (x *HotlistItem) GetIssue() string {
	if x != nil {
		return x.Issue
	}
	return ""
}

func (x *HotlistItem) GetRank() uint32 {
	if x != nil {
		return x.Rank
	}
	return 0
}

func (x *HotlistItem) GetAdder() string {
	if x != nil {
		return x.Adder
	}
	return ""
}

func (x *HotlistItem) GetCreateTime() *timestamp.Timestamp {
	if x != nil {
		return x.CreateTime
	}
	return nil
}

func (x *HotlistItem) GetNote() string {
	if x != nil {
		return x.Note
	}
	return ""
}

var File_api_v3_api_proto_feature_objects_proto protoreflect.FileDescriptor

var file_api_v3_api_proto_feature_objects_proto_rawDesc = []byte{
	0x0a, 0x26, 0x61, 0x70, 0x69, 0x2f, 0x76, 0x33, 0x2f, 0x61, 0x70, 0x69, 0x5f, 0x70, 0x72, 0x6f,
	0x74, 0x6f, 0x2f, 0x66, 0x65, 0x61, 0x74, 0x75, 0x72, 0x65, 0x5f, 0x6f, 0x62, 0x6a, 0x65, 0x63,
	0x74, 0x73, 0x2e, 0x70, 0x72, 0x6f, 0x74, 0x6f, 0x12, 0x0b, 0x6d, 0x6f, 0x6e, 0x6f, 0x72, 0x61,
	0x69, 0x6c, 0x2e, 0x76, 0x33, 0x1a, 0x2c, 0x67, 0x6f, 0x6f, 0x67, 0x6c, 0x65, 0x5f, 0x70, 0x72,
	0x6f, 0x74, 0x6f, 0x2f, 0x67, 0x6f, 0x6f, 0x67, 0x6c, 0x65, 0x2f, 0x61, 0x70, 0x69, 0x2f, 0x66,
	0x69, 0x65, 0x6c, 0x64, 0x5f, 0x62, 0x65, 0x68, 0x61, 0x76, 0x69, 0x6f, 0x72, 0x2e, 0x70, 0x72,
	0x6f, 0x74, 0x6f, 0x1a, 0x26, 0x67, 0x6f, 0x6f, 0x67, 0x6c, 0x65, 0x5f, 0x70, 0x72, 0x6f, 0x74,
	0x6f, 0x2f, 0x67, 0x6f, 0x6f, 0x67, 0x6c, 0x65, 0x2f, 0x61, 0x70, 0x69, 0x2f, 0x72, 0x65, 0x73,
	0x6f, 0x75, 0x72, 0x63, 0x65, 0x2e, 0x70, 0x72, 0x6f, 0x74, 0x6f, 0x1a, 0x1f, 0x67, 0x6f, 0x6f,
	0x67, 0x6c, 0x65, 0x2f, 0x70, 0x72, 0x6f, 0x74, 0x6f, 0x62, 0x75, 0x66, 0x2f, 0x74, 0x69, 0x6d,
	0x65, 0x73, 0x74, 0x61, 0x6d, 0x70, 0x2e, 0x70, 0x72, 0x6f, 0x74, 0x6f, 0x1a, 0x24, 0x61, 0x70,
	0x69, 0x2f, 0x76, 0x33, 0x2f, 0x61, 0x70, 0x69, 0x5f, 0x70, 0x72, 0x6f, 0x74, 0x6f, 0x2f, 0x69,
	0x73, 0x73, 0x75, 0x65, 0x5f, 0x6f, 0x62, 0x6a, 0x65, 0x63, 0x74, 0x73, 0x2e, 0x70, 0x72, 0x6f,
	0x74, 0x6f, 0x22, 0x85, 0x04, 0x0a, 0x07, 0x48, 0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x12, 0x12,
	0x0a, 0x04, 0x6e, 0x61, 0x6d, 0x65, 0x18, 0x01, 0x20, 0x01, 0x28, 0x09, 0x52, 0x04, 0x6e, 0x61,
	0x6d, 0x65, 0x12, 0x26, 0x0a, 0x0c, 0x64, 0x69, 0x73, 0x70, 0x6c, 0x61, 0x79, 0x5f, 0x6e, 0x61,
	0x6d, 0x65, 0x18, 0x02, 0x20, 0x01, 0x28, 0x09, 0x42, 0x03, 0xe0, 0x41, 0x02, 0x52, 0x0b, 0x64,
	0x69, 0x73, 0x70, 0x6c, 0x61, 0x79, 0x4e, 0x61, 0x6d, 0x65, 0x12, 0x30, 0x0a, 0x05, 0x6f, 0x77,
	0x6e, 0x65, 0x72, 0x18, 0x03, 0x20, 0x01, 0x28, 0x09, 0x42, 0x1a, 0xfa, 0x41, 0x14, 0x0a, 0x12,
	0x61, 0x70, 0x69, 0x2e, 0x63, 0x72, 0x62, 0x75, 0x67, 0x2e, 0x63, 0x6f, 0x6d, 0x2f, 0x55, 0x73,
	0x65, 0x72, 0xe0, 0x41, 0x02, 0x52, 0x05, 0x6f, 0x77, 0x6e, 0x65, 0x72, 0x12, 0x31, 0x0a, 0x07,
	0x65, 0x64, 0x69, 0x74, 0x6f, 0x72, 0x73, 0x18, 0x04, 0x20, 0x03, 0x28, 0x09, 0x42, 0x17, 0xfa,
	0x41, 0x14, 0x0a, 0x12, 0x61, 0x70, 0x69, 0x2e, 0x63, 0x72, 0x62, 0x75, 0x67, 0x2e, 0x63, 0x6f,
	0x6d, 0x2f, 0x55, 0x73, 0x65, 0x72, 0x52, 0x07, 0x65, 0x64, 0x69, 0x74, 0x6f, 0x72, 0x73, 0x12,
	0x1d, 0x0a, 0x07, 0x73, 0x75, 0x6d, 0x6d, 0x61, 0x72, 0x79, 0x18, 0x05, 0x20, 0x01, 0x28, 0x09,
	0x42, 0x03, 0xe0, 0x41, 0x02, 0x52, 0x07, 0x73, 0x75, 0x6d, 0x6d, 0x61, 0x72, 0x79, 0x12, 0x25,
	0x0a, 0x0b, 0x64, 0x65, 0x73, 0x63, 0x72, 0x69, 0x70, 0x74, 0x69, 0x6f, 0x6e, 0x18, 0x06, 0x20,
	0x01, 0x28, 0x09, 0x42, 0x03, 0xe0, 0x41, 0x02, 0x52, 0x0b, 0x64, 0x65, 0x73, 0x63, 0x72, 0x69,
	0x70, 0x74, 0x69, 0x6f, 0x6e, 0x12, 0x46, 0x0a, 0x0f, 0x64, 0x65, 0x66, 0x61, 0x75, 0x6c, 0x74,
	0x5f, 0x63, 0x6f, 0x6c, 0x75, 0x6d, 0x6e, 0x73, 0x18, 0x07, 0x20, 0x03, 0x28, 0x0b, 0x32, 0x1d,
	0x2e, 0x6d, 0x6f, 0x6e, 0x6f, 0x72, 0x61, 0x69, 0x6c, 0x2e, 0x76, 0x33, 0x2e, 0x49, 0x73, 0x73,
	0x75, 0x65, 0x73, 0x4c, 0x69, 0x73, 0x74, 0x43, 0x6f, 0x6c, 0x75, 0x6d, 0x6e, 0x52, 0x0e, 0x64,
	0x65, 0x66, 0x61, 0x75, 0x6c, 0x74, 0x43, 0x6f, 0x6c, 0x75, 0x6d, 0x6e, 0x73, 0x12, 0x4c, 0x0a,
	0x0f, 0x68, 0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x5f, 0x70, 0x72, 0x69, 0x76, 0x61, 0x63, 0x79,
	0x18, 0x08, 0x20, 0x01, 0x28, 0x0e, 0x32, 0x23, 0x2e, 0x6d, 0x6f, 0x6e, 0x6f, 0x72, 0x61, 0x69,
	0x6c, 0x2e, 0x76, 0x33, 0x2e, 0x48, 0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x2e, 0x48, 0x6f, 0x74,
	0x6c, 0x69, 0x73, 0x74, 0x50, 0x72, 0x69, 0x76, 0x61, 0x63, 0x79, 0x52, 0x0e, 0x68, 0x6f, 0x74,
	0x6c, 0x69, 0x73, 0x74, 0x50, 0x72, 0x69, 0x76, 0x61, 0x63, 0x79, 0x22, 0x4a, 0x0a, 0x0e, 0x48,
	0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x50, 0x72, 0x69, 0x76, 0x61, 0x63, 0x79, 0x12, 0x1f, 0x0a,
	0x1b, 0x48, 0x4f, 0x54, 0x4c, 0x49, 0x53, 0x54, 0x5f, 0x50, 0x52, 0x49, 0x56, 0x41, 0x43, 0x59,
	0x5f, 0x55, 0x4e, 0x53, 0x50, 0x45, 0x43, 0x49, 0x46, 0x49, 0x45, 0x44, 0x10, 0x00, 0x12, 0x0b,
	0x0a, 0x07, 0x50, 0x52, 0x49, 0x56, 0x41, 0x54, 0x45, 0x10, 0x01, 0x12, 0x0a, 0x0a, 0x06, 0x50,
	0x55, 0x42, 0x4c, 0x49, 0x43, 0x10, 0x02, 0x3a, 0x31, 0xea, 0x41, 0x2e, 0x0a, 0x15, 0x61, 0x70,
	0x69, 0x2e, 0x63, 0x72, 0x62, 0x75, 0x67, 0x2e, 0x63, 0x6f, 0x6d, 0x2f, 0x48, 0x6f, 0x74, 0x6c,
	0x69, 0x73, 0x74, 0x12, 0x15, 0x68, 0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x73, 0x2f, 0x7b, 0x68,
	0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x5f, 0x69, 0x64, 0x7d, 0x22, 0xbc, 0x02, 0x0a, 0x0b, 0x48,
	0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x49, 0x74, 0x65, 0x6d, 0x12, 0x12, 0x0a, 0x04, 0x6e, 0x61,
	0x6d, 0x65, 0x18, 0x01, 0x20, 0x01, 0x28, 0x09, 0x52, 0x04, 0x6e, 0x61, 0x6d, 0x65, 0x12, 0x31,
	0x0a, 0x05, 0x69, 0x73, 0x73, 0x75, 0x65, 0x18, 0x02, 0x20, 0x01, 0x28, 0x09, 0x42, 0x1b, 0xfa,
	0x41, 0x15, 0x0a, 0x13, 0x61, 0x70, 0x69, 0x2e, 0x63, 0x72, 0x62, 0x75, 0x67, 0x2e, 0x63, 0x6f,
	0x6d, 0x2f, 0x49, 0x73, 0x73, 0x75, 0x65, 0xe0, 0x41, 0x05, 0x52, 0x05, 0x69, 0x73, 0x73, 0x75,
	0x65, 0x12, 0x17, 0x0a, 0x04, 0x72, 0x61, 0x6e, 0x6b, 0x18, 0x03, 0x20, 0x01, 0x28, 0x0d, 0x42,
	0x03, 0xe0, 0x41, 0x03, 0x52, 0x04, 0x72, 0x61, 0x6e, 0x6b, 0x12, 0x30, 0x0a, 0x05, 0x61, 0x64,
	0x64, 0x65, 0x72, 0x18, 0x04, 0x20, 0x01, 0x28, 0x09, 0x42, 0x1a, 0xfa, 0x41, 0x14, 0x0a, 0x12,
	0x61, 0x70, 0x69, 0x2e, 0x63, 0x72, 0x62, 0x75, 0x67, 0x2e, 0x63, 0x6f, 0x6d, 0x2f, 0x55, 0x73,
	0x65, 0x72, 0xe0, 0x41, 0x03, 0x52, 0x05, 0x61, 0x64, 0x64, 0x65, 0x72, 0x12, 0x40, 0x0a, 0x0b,
	0x63, 0x72, 0x65, 0x61, 0x74, 0x65, 0x5f, 0x74, 0x69, 0x6d, 0x65, 0x18, 0x05, 0x20, 0x01, 0x28,
	0x0b, 0x32, 0x1a, 0x2e, 0x67, 0x6f, 0x6f, 0x67, 0x6c, 0x65, 0x2e, 0x70, 0x72, 0x6f, 0x74, 0x6f,
	0x62, 0x75, 0x66, 0x2e, 0x54, 0x69, 0x6d, 0x65, 0x73, 0x74, 0x61, 0x6d, 0x70, 0x42, 0x03, 0xe0,
	0x41, 0x03, 0x52, 0x0a, 0x63, 0x72, 0x65, 0x61, 0x74, 0x65, 0x54, 0x69, 0x6d, 0x65, 0x12, 0x12,
	0x0a, 0x04, 0x6e, 0x6f, 0x74, 0x65, 0x18, 0x06, 0x20, 0x01, 0x28, 0x09, 0x52, 0x04, 0x6e, 0x6f,
	0x74, 0x65, 0x3a, 0x45, 0xea, 0x41, 0x42, 0x0a, 0x19, 0x61, 0x70, 0x69, 0x2e, 0x63, 0x72, 0x62,
	0x75, 0x67, 0x2e, 0x63, 0x6f, 0x6d, 0x2f, 0x48, 0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x49, 0x74,
	0x65, 0x6d, 0x12, 0x25, 0x68, 0x6f, 0x74, 0x6c, 0x69, 0x73, 0x74, 0x73, 0x2f, 0x7b, 0x68, 0x6f,
	0x74, 0x6c, 0x69, 0x73, 0x74, 0x5f, 0x69, 0x64, 0x7d, 0x2f, 0x69, 0x74, 0x65, 0x6d, 0x73, 0x2f,
	0x7b, 0x69, 0x74, 0x65, 0x6d, 0x5f, 0x69, 0x64, 0x7d, 0x62, 0x06, 0x70, 0x72, 0x6f, 0x74, 0x6f,
	0x33,
}

var (
	file_api_v3_api_proto_feature_objects_proto_rawDescOnce sync.Once
	file_api_v3_api_proto_feature_objects_proto_rawDescData = file_api_v3_api_proto_feature_objects_proto_rawDesc
)

func file_api_v3_api_proto_feature_objects_proto_rawDescGZIP() []byte {
	file_api_v3_api_proto_feature_objects_proto_rawDescOnce.Do(func() {
		file_api_v3_api_proto_feature_objects_proto_rawDescData = protoimpl.X.CompressGZIP(file_api_v3_api_proto_feature_objects_proto_rawDescData)
	})
	return file_api_v3_api_proto_feature_objects_proto_rawDescData
}

var file_api_v3_api_proto_feature_objects_proto_enumTypes = make([]protoimpl.EnumInfo, 1)
var file_api_v3_api_proto_feature_objects_proto_msgTypes = make([]protoimpl.MessageInfo, 2)
var file_api_v3_api_proto_feature_objects_proto_goTypes = []interface{}{
	(Hotlist_HotlistPrivacy)(0), // 0: monorail.v3.Hotlist.HotlistPrivacy
	(*Hotlist)(nil),             // 1: monorail.v3.Hotlist
	(*HotlistItem)(nil),         // 2: monorail.v3.HotlistItem
	(*IssuesListColumn)(nil),    // 3: monorail.v3.IssuesListColumn
	(*timestamp.Timestamp)(nil), // 4: google.protobuf.Timestamp
}
var file_api_v3_api_proto_feature_objects_proto_depIdxs = []int32{
	3, // 0: monorail.v3.Hotlist.default_columns:type_name -> monorail.v3.IssuesListColumn
	0, // 1: monorail.v3.Hotlist.hotlist_privacy:type_name -> monorail.v3.Hotlist.HotlistPrivacy
	4, // 2: monorail.v3.HotlistItem.create_time:type_name -> google.protobuf.Timestamp
	3, // [3:3] is the sub-list for method output_type
	3, // [3:3] is the sub-list for method input_type
	3, // [3:3] is the sub-list for extension type_name
	3, // [3:3] is the sub-list for extension extendee
	0, // [0:3] is the sub-list for field type_name
}

func init() { file_api_v3_api_proto_feature_objects_proto_init() }
func file_api_v3_api_proto_feature_objects_proto_init() {
	if File_api_v3_api_proto_feature_objects_proto != nil {
		return
	}
	file_api_v3_api_proto_issue_objects_proto_init()
	if !protoimpl.UnsafeEnabled {
		file_api_v3_api_proto_feature_objects_proto_msgTypes[0].Exporter = func(v interface{}, i int) interface{} {
			switch v := v.(*Hotlist); i {
			case 0:
				return &v.state
			case 1:
				return &v.sizeCache
			case 2:
				return &v.unknownFields
			default:
				return nil
			}
		}
		file_api_v3_api_proto_feature_objects_proto_msgTypes[1].Exporter = func(v interface{}, i int) interface{} {
			switch v := v.(*HotlistItem); i {
			case 0:
				return &v.state
			case 1:
				return &v.sizeCache
			case 2:
				return &v.unknownFields
			default:
				return nil
			}
		}
	}
	type x struct{}
	out := protoimpl.TypeBuilder{
		File: protoimpl.DescBuilder{
			GoPackagePath: reflect.TypeOf(x{}).PkgPath(),
			RawDescriptor: file_api_v3_api_proto_feature_objects_proto_rawDesc,
			NumEnums:      1,
			NumMessages:   2,
			NumExtensions: 0,
			NumServices:   0,
		},
		GoTypes:           file_api_v3_api_proto_feature_objects_proto_goTypes,
		DependencyIndexes: file_api_v3_api_proto_feature_objects_proto_depIdxs,
		EnumInfos:         file_api_v3_api_proto_feature_objects_proto_enumTypes,
		MessageInfos:      file_api_v3_api_proto_feature_objects_proto_msgTypes,
	}.Build()
	File_api_v3_api_proto_feature_objects_proto = out.File
	file_api_v3_api_proto_feature_objects_proto_rawDesc = nil
	file_api_v3_api_proto_feature_objects_proto_goTypes = nil
	file_api_v3_api_proto_feature_objects_proto_depIdxs = nil
}
