// Code generated by protoc-gen-go. DO NOT EDIT.
// source: chromeos_config.proto

package _go

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

type ChromeOSDeviceType int32

const (
	ChromeOSDeviceType_DEVICE_INVALID    ChromeOSDeviceType = 0
	ChromeOSDeviceType_DEVICE_CHROMEBOOK ChromeOSDeviceType = 1
	ChromeOSDeviceType_DEVICE_LABSTATION ChromeOSDeviceType = 2
	ChromeOSDeviceType_DEVICE_SERVO      ChromeOSDeviceType = 3
)

var ChromeOSDeviceType_name = map[int32]string{
	0: "DEVICE_INVALID",
	1: "DEVICE_CHROMEBOOK",
	2: "DEVICE_LABSTATION",
	3: "DEVICE_SERVO",
}

var ChromeOSDeviceType_value = map[string]int32{
	"DEVICE_INVALID":    0,
	"DEVICE_CHROMEBOOK": 1,
	"DEVICE_LABSTATION": 2,
	"DEVICE_SERVO":      3,
}

func (x ChromeOSDeviceType) String() string {
	return proto.EnumName(ChromeOSDeviceType_name, int32(x))
}

func (ChromeOSDeviceType) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_423e98b76c637751, []int{0}
}

func init() {
	proto.RegisterEnum("fleet.ChromeOSDeviceType", ChromeOSDeviceType_name, ChromeOSDeviceType_value)
}

func init() { proto.RegisterFile("chromeos_config.proto", fileDescriptor_423e98b76c637751) }

var fileDescriptor_423e98b76c637751 = []byte{
	// 167 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0xe2, 0x12, 0x4d, 0xce, 0x28, 0xca,
	0xcf, 0x4d, 0xcd, 0x2f, 0x8e, 0x4f, 0xce, 0xcf, 0x4b, 0xcb, 0x4c, 0xd7, 0x2b, 0x28, 0xca, 0x2f,
	0xc9, 0x17, 0x62, 0x4d, 0xcb, 0x49, 0x4d, 0x2d, 0xd1, 0xca, 0xe0, 0x12, 0x72, 0x06, 0xcb, 0xfb,
	0x07, 0xbb, 0xa4, 0x96, 0x65, 0x26, 0xa7, 0x86, 0x54, 0x16, 0xa4, 0x0a, 0x09, 0x71, 0xf1, 0xb9,
	0xb8, 0x86, 0x79, 0x3a, 0xbb, 0xc6, 0x7b, 0xfa, 0x85, 0x39, 0xfa, 0x78, 0xba, 0x08, 0x30, 0x08,
	0x89, 0x72, 0x09, 0x42, 0xc5, 0x9c, 0x3d, 0x82, 0xfc, 0x7d, 0x5d, 0x9d, 0xfc, 0xfd, 0xbd, 0x05,
	0x18, 0x91, 0x84, 0x7d, 0x1c, 0x9d, 0x82, 0x43, 0x1c, 0x43, 0x3c, 0xfd, 0xfd, 0x04, 0x98, 0x84,
	0x04, 0xb8, 0x78, 0xa0, 0xc2, 0xc1, 0xae, 0x41, 0x61, 0xfe, 0x02, 0xcc, 0x4e, 0x32, 0x51, 0x52,
	0x99, 0x79, 0x69, 0x45, 0x89, 0xfa, 0x39, 0x99, 0x49, 0xc5, 0xfa, 0x60, 0xdb, 0xf5, 0xc1, 0x4e,
	0x29, 0xd6, 0x4f, 0xcf, 0x4f, 0x62, 0x03, 0x33, 0x8d, 0x01, 0x01, 0x00, 0x00, 0xff, 0xff, 0x26,
	0xe3, 0x30, 0xa7, 0xae, 0x00, 0x00, 0x00,
}