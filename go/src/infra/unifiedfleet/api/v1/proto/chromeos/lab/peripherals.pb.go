// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/unifiedfleet/api/v1/proto/chromeos/lab/peripherals.proto

package ufspb

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

// Next Tag: 3
type CameraType int32

const (
	CameraType_CAMERA_INVALID CameraType = 0
	// camera Huddly GO
	CameraType_CAMERA_HUDDLY CameraType = 1
	// camera Logitech PTZ Pro 2
	CameraType_CAMERA_PTZPRO2 CameraType = 2
)

var CameraType_name = map[int32]string{
	0: "CAMERA_INVALID",
	1: "CAMERA_HUDDLY",
	2: "CAMERA_PTZPRO2",
}

var CameraType_value = map[string]int32{
	"CAMERA_INVALID": 0,
	"CAMERA_HUDDLY":  1,
	"CAMERA_PTZPRO2": 2,
}

func (x CameraType) String() string {
	return proto.EnumName(CameraType_name, int32(x))
}

func (CameraType) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{0}
}

type CableType int32

const (
	CableType_CABLE_INVALID     CableType = 0
	CableType_CABLE_AUDIOJACK   CableType = 1
	CableType_CABLE_USBAUDIO    CableType = 2
	CableType_CABLE_USBPRINTING CableType = 3
	CableType_CABLE_HDMIAUDIO   CableType = 4
)

var CableType_name = map[int32]string{
	0: "CABLE_INVALID",
	1: "CABLE_AUDIOJACK",
	2: "CABLE_USBAUDIO",
	3: "CABLE_USBPRINTING",
	4: "CABLE_HDMIAUDIO",
}

var CableType_value = map[string]int32{
	"CABLE_INVALID":     0,
	"CABLE_AUDIOJACK":   1,
	"CABLE_USBAUDIO":    2,
	"CABLE_USBPRINTING": 3,
	"CABLE_HDMIAUDIO":   4,
}

func (x CableType) String() string {
	return proto.EnumName(CableType_name, int32(x))
}

func (CableType) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{1}
}

// DUT's WiFi antenna's connection.
// Next Tag: 3
type Wifi_AntennaConnection int32

const (
	Wifi_CONN_UNKNOWN Wifi_AntennaConnection = 0
	// WIFI antenna is connected conductively.
	Wifi_CONN_CONDUCTIVE Wifi_AntennaConnection = 1
	// WIFI antenna is connected over-the-air.
	Wifi_CONN_OTA Wifi_AntennaConnection = 2
)

var Wifi_AntennaConnection_name = map[int32]string{
	0: "CONN_UNKNOWN",
	1: "CONN_CONDUCTIVE",
	2: "CONN_OTA",
}

var Wifi_AntennaConnection_value = map[string]int32{
	"CONN_UNKNOWN":    0,
	"CONN_CONDUCTIVE": 1,
	"CONN_OTA":        2,
}

func (x Wifi_AntennaConnection) String() string {
	return proto.EnumName(Wifi_AntennaConnection_name, int32(x))
}

func (Wifi_AntennaConnection) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{5, 0}
}

type Wifi_Router int32

const (
	Wifi_ROUTER_UNSPECIFIED Wifi_Router = 0
	Wifi_ROUTER_802_11AX    Wifi_Router = 1
)

var Wifi_Router_name = map[int32]string{
	0: "ROUTER_UNSPECIFIED",
	1: "ROUTER_802_11AX",
}

var Wifi_Router_value = map[string]int32{
	"ROUTER_UNSPECIFIED": 0,
	"ROUTER_802_11AX":    1,
}

func (x Wifi_Router) String() string {
	return proto.EnumName(Wifi_Router_name, int32(x))
}

func (Wifi_Router) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{5, 1}
}

// Facing of DUT's camera to be tested whose FOV should cover chart tablet's screen.
// Next Tag: 3
type Camerabox_Facing int32

const (
	Camerabox_FACING_UNKNOWN Camerabox_Facing = 0
	// DUT's back camera is facing to chart tablet.
	Camerabox_FACING_BACK Camerabox_Facing = 1
	// DUT's front camera is facing to chart tablet.
	Camerabox_FACING_FRONT Camerabox_Facing = 2
)

var Camerabox_Facing_name = map[int32]string{
	0: "FACING_UNKNOWN",
	1: "FACING_BACK",
	2: "FACING_FRONT",
}

var Camerabox_Facing_value = map[string]int32{
	"FACING_UNKNOWN": 0,
	"FACING_BACK":    1,
	"FACING_FRONT":   2,
}

func (x Camerabox_Facing) String() string {
	return proto.EnumName(Camerabox_Facing_name, int32(x))
}

func (Camerabox_Facing) EnumDescriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{7, 0}
}

// Peripherals of device. Next Tag: 13
type Peripherals struct {
	Servo     *Servo     `protobuf:"bytes,1,opt,name=servo,proto3" json:"servo,omitempty"`
	Chameleon *Chameleon `protobuf:"bytes,2,opt,name=chameleon,proto3" json:"chameleon,omitempty"`
	Rpm       *RPM       `protobuf:"bytes,3,opt,name=rpm,proto3" json:"rpm,omitempty"`
	// refer to cameras that connected to the device.
	ConnectedCamera []*Camera `protobuf:"bytes,4,rep,name=connected_camera,json=connectedCamera,proto3" json:"connected_camera,omitempty"`
	Audio           *Audio    `protobuf:"bytes,5,opt,name=audio,proto3" json:"audio,omitempty"`
	Wifi            *Wifi     `protobuf:"bytes,6,opt,name=wifi,proto3" json:"wifi,omitempty"`
	Touch           *Touch    `protobuf:"bytes,7,opt,name=touch,proto3" json:"touch,omitempty"`
	// e.g: "att", "verizon",.. It's a manual label set by lab, varies dut by dut.
	Carrier string `protobuf:"bytes,8,opt,name=carrier,proto3" json:"carrier,omitempty"`
	// Indicate if the device is setup in a steady and controllable camera box environment for camera test automation.
	// http://go/cros-camera-box
	Camerabox bool `protobuf:"varint,9,opt,name=camerabox,proto3" json:"camerabox,omitempty"`
	// Indicate if the device is setup in a chaos environment. It's a special settings for running wifi interop tests.
	Chaos bool `protobuf:"varint,10,opt,name=chaos,proto3" json:"chaos,omitempty"`
	// Indicate the cables that connect audio, printer to the device in ACS lab.
	Cable []*Cable `protobuf:"bytes,11,rep,name=cable,proto3" json:"cable,omitempty"`
	// Incompatible upgraded type from bool camerabox=9.
	CameraboxInfo        *Camerabox `protobuf:"bytes,12,opt,name=camerabox_info,json=cameraboxInfo,proto3" json:"camerabox_info,omitempty"`
	XXX_NoUnkeyedLiteral struct{}   `json:"-"`
	XXX_unrecognized     []byte     `json:"-"`
	XXX_sizecache        int32      `json:"-"`
}

func (m *Peripherals) Reset()         { *m = Peripherals{} }
func (m *Peripherals) String() string { return proto.CompactTextString(m) }
func (*Peripherals) ProtoMessage()    {}
func (*Peripherals) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{0}
}

func (m *Peripherals) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Peripherals.Unmarshal(m, b)
}
func (m *Peripherals) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Peripherals.Marshal(b, m, deterministic)
}
func (m *Peripherals) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Peripherals.Merge(m, src)
}
func (m *Peripherals) XXX_Size() int {
	return xxx_messageInfo_Peripherals.Size(m)
}
func (m *Peripherals) XXX_DiscardUnknown() {
	xxx_messageInfo_Peripherals.DiscardUnknown(m)
}

var xxx_messageInfo_Peripherals proto.InternalMessageInfo

func (m *Peripherals) GetServo() *Servo {
	if m != nil {
		return m.Servo
	}
	return nil
}

func (m *Peripherals) GetChameleon() *Chameleon {
	if m != nil {
		return m.Chameleon
	}
	return nil
}

func (m *Peripherals) GetRpm() *RPM {
	if m != nil {
		return m.Rpm
	}
	return nil
}

func (m *Peripherals) GetConnectedCamera() []*Camera {
	if m != nil {
		return m.ConnectedCamera
	}
	return nil
}

func (m *Peripherals) GetAudio() *Audio {
	if m != nil {
		return m.Audio
	}
	return nil
}

func (m *Peripherals) GetWifi() *Wifi {
	if m != nil {
		return m.Wifi
	}
	return nil
}

func (m *Peripherals) GetTouch() *Touch {
	if m != nil {
		return m.Touch
	}
	return nil
}

func (m *Peripherals) GetCarrier() string {
	if m != nil {
		return m.Carrier
	}
	return ""
}

func (m *Peripherals) GetCamerabox() bool {
	if m != nil {
		return m.Camerabox
	}
	return false
}

func (m *Peripherals) GetChaos() bool {
	if m != nil {
		return m.Chaos
	}
	return false
}

func (m *Peripherals) GetCable() []*Cable {
	if m != nil {
		return m.Cable
	}
	return nil
}

func (m *Peripherals) GetCameraboxInfo() *Camerabox {
	if m != nil {
		return m.CameraboxInfo
	}
	return nil
}

// Remote power management info.
// Next Tag: 3
type RPM struct {
	PowerunitName        string   `protobuf:"bytes,1,opt,name=powerunit_name,json=powerunitName,proto3" json:"powerunit_name,omitempty"`
	PowerunitOutlet      string   `protobuf:"bytes,2,opt,name=powerunit_outlet,json=powerunitOutlet,proto3" json:"powerunit_outlet,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *RPM) Reset()         { *m = RPM{} }
func (m *RPM) String() string { return proto.CompactTextString(m) }
func (*RPM) ProtoMessage()    {}
func (*RPM) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{1}
}

func (m *RPM) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_RPM.Unmarshal(m, b)
}
func (m *RPM) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_RPM.Marshal(b, m, deterministic)
}
func (m *RPM) XXX_Merge(src proto.Message) {
	xxx_messageInfo_RPM.Merge(m, src)
}
func (m *RPM) XXX_Size() int {
	return xxx_messageInfo_RPM.Size(m)
}
func (m *RPM) XXX_DiscardUnknown() {
	xxx_messageInfo_RPM.DiscardUnknown(m)
}

var xxx_messageInfo_RPM proto.InternalMessageInfo

func (m *RPM) GetPowerunitName() string {
	if m != nil {
		return m.PowerunitName
	}
	return ""
}

func (m *RPM) GetPowerunitOutlet() string {
	if m != nil {
		return m.PowerunitOutlet
	}
	return ""
}

// Next Tag: 2
type Camera struct {
	CameraType           CameraType `protobuf:"varint,1,opt,name=camera_type,json=cameraType,proto3,enum=unifiedfleet.api.v1.proto.chromeos.lab.CameraType" json:"camera_type,omitempty"`
	XXX_NoUnkeyedLiteral struct{}   `json:"-"`
	XXX_unrecognized     []byte     `json:"-"`
	XXX_sizecache        int32      `json:"-"`
}

func (m *Camera) Reset()         { *m = Camera{} }
func (m *Camera) String() string { return proto.CompactTextString(m) }
func (*Camera) ProtoMessage()    {}
func (*Camera) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{2}
}

func (m *Camera) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Camera.Unmarshal(m, b)
}
func (m *Camera) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Camera.Marshal(b, m, deterministic)
}
func (m *Camera) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Camera.Merge(m, src)
}
func (m *Camera) XXX_Size() int {
	return xxx_messageInfo_Camera.Size(m)
}
func (m *Camera) XXX_DiscardUnknown() {
	xxx_messageInfo_Camera.DiscardUnknown(m)
}

var xxx_messageInfo_Camera proto.InternalMessageInfo

func (m *Camera) GetCameraType() CameraType {
	if m != nil {
		return m.CameraType
	}
	return CameraType_CAMERA_INVALID
}

type Cable struct {
	Type                 CableType `protobuf:"varint,1,opt,name=type,proto3,enum=unifiedfleet.api.v1.proto.chromeos.lab.CableType" json:"type,omitempty"`
	XXX_NoUnkeyedLiteral struct{}  `json:"-"`
	XXX_unrecognized     []byte    `json:"-"`
	XXX_sizecache        int32     `json:"-"`
}

func (m *Cable) Reset()         { *m = Cable{} }
func (m *Cable) String() string { return proto.CompactTextString(m) }
func (*Cable) ProtoMessage()    {}
func (*Cable) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{3}
}

func (m *Cable) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Cable.Unmarshal(m, b)
}
func (m *Cable) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Cable.Marshal(b, m, deterministic)
}
func (m *Cable) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Cable.Merge(m, src)
}
func (m *Cable) XXX_Size() int {
	return xxx_messageInfo_Cable.Size(m)
}
func (m *Cable) XXX_DiscardUnknown() {
	xxx_messageInfo_Cable.DiscardUnknown(m)
}

var xxx_messageInfo_Cable proto.InternalMessageInfo

func (m *Cable) GetType() CableType {
	if m != nil {
		return m.Type
	}
	return CableType_CABLE_INVALID
}

// Next Tag: 3
type Audio struct {
	// Indicate if the DUT is housed in an audio box to record / replay audio
	// for audio testing.
	AudioBox bool `protobuf:"varint,1,opt,name=audio_box,json=audioBox,proto3" json:"audio_box,omitempty"`
	// Indicate if the DUT is connected to Atrus speakermic
	Atrus                bool     `protobuf:"varint,2,opt,name=atrus,proto3" json:"atrus,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Audio) Reset()         { *m = Audio{} }
func (m *Audio) String() string { return proto.CompactTextString(m) }
func (*Audio) ProtoMessage()    {}
func (*Audio) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{4}
}

func (m *Audio) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Audio.Unmarshal(m, b)
}
func (m *Audio) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Audio.Marshal(b, m, deterministic)
}
func (m *Audio) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Audio.Merge(m, src)
}
func (m *Audio) XXX_Size() int {
	return xxx_messageInfo_Audio.Size(m)
}
func (m *Audio) XXX_DiscardUnknown() {
	xxx_messageInfo_Audio.DiscardUnknown(m)
}

var xxx_messageInfo_Audio proto.InternalMessageInfo

func (m *Audio) GetAudioBox() bool {
	if m != nil {
		return m.AudioBox
	}
	return false
}

func (m *Audio) GetAtrus() bool {
	if m != nil {
		return m.Atrus
	}
	return false
}

// Next Tag: 4
type Wifi struct {
	// Indicate if the device is inside a hermetic wifi cell.
	Wificell    bool                   `protobuf:"varint,1,opt,name=wificell,proto3" json:"wificell,omitempty"`
	AntennaConn Wifi_AntennaConnection `protobuf:"varint,2,opt,name=antenna_conn,json=antennaConn,proto3,enum=unifiedfleet.api.v1.proto.chromeos.lab.Wifi_AntennaConnection" json:"antenna_conn,omitempty"`
	// Indicate if the device is in a pre-setup environment with 802.11ax routers.
	// crbug.com/1044786
	Router               Wifi_Router `protobuf:"varint,3,opt,name=router,proto3,enum=unifiedfleet.api.v1.proto.chromeos.lab.Wifi_Router" json:"router,omitempty"`
	XXX_NoUnkeyedLiteral struct{}    `json:"-"`
	XXX_unrecognized     []byte      `json:"-"`
	XXX_sizecache        int32       `json:"-"`
}

func (m *Wifi) Reset()         { *m = Wifi{} }
func (m *Wifi) String() string { return proto.CompactTextString(m) }
func (*Wifi) ProtoMessage()    {}
func (*Wifi) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{5}
}

func (m *Wifi) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Wifi.Unmarshal(m, b)
}
func (m *Wifi) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Wifi.Marshal(b, m, deterministic)
}
func (m *Wifi) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Wifi.Merge(m, src)
}
func (m *Wifi) XXX_Size() int {
	return xxx_messageInfo_Wifi.Size(m)
}
func (m *Wifi) XXX_DiscardUnknown() {
	xxx_messageInfo_Wifi.DiscardUnknown(m)
}

var xxx_messageInfo_Wifi proto.InternalMessageInfo

func (m *Wifi) GetWificell() bool {
	if m != nil {
		return m.Wificell
	}
	return false
}

func (m *Wifi) GetAntennaConn() Wifi_AntennaConnection {
	if m != nil {
		return m.AntennaConn
	}
	return Wifi_CONN_UNKNOWN
}

func (m *Wifi) GetRouter() Wifi_Router {
	if m != nil {
		return m.Router
	}
	return Wifi_ROUTER_UNSPECIFIED
}

// Next Tag: 2
type Touch struct {
	// Has touch monitor mimo.
	Mimo                 bool     `protobuf:"varint,1,opt,name=mimo,proto3" json:"mimo,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Touch) Reset()         { *m = Touch{} }
func (m *Touch) String() string { return proto.CompactTextString(m) }
func (*Touch) ProtoMessage()    {}
func (*Touch) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{6}
}

func (m *Touch) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Touch.Unmarshal(m, b)
}
func (m *Touch) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Touch.Marshal(b, m, deterministic)
}
func (m *Touch) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Touch.Merge(m, src)
}
func (m *Touch) XXX_Size() int {
	return xxx_messageInfo_Touch.Size(m)
}
func (m *Touch) XXX_DiscardUnknown() {
	xxx_messageInfo_Touch.DiscardUnknown(m)
}

var xxx_messageInfo_Touch proto.InternalMessageInfo

func (m *Touch) GetMimo() bool {
	if m != nil {
		return m.Mimo
	}
	return false
}

// Next Tag: 2
type Camerabox struct {
	Facing               Camerabox_Facing `protobuf:"varint,1,opt,name=facing,proto3,enum=unifiedfleet.api.v1.proto.chromeos.lab.Camerabox_Facing" json:"facing,omitempty"`
	XXX_NoUnkeyedLiteral struct{}         `json:"-"`
	XXX_unrecognized     []byte           `json:"-"`
	XXX_sizecache        int32            `json:"-"`
}

func (m *Camerabox) Reset()         { *m = Camerabox{} }
func (m *Camerabox) String() string { return proto.CompactTextString(m) }
func (*Camerabox) ProtoMessage()    {}
func (*Camerabox) Descriptor() ([]byte, []int) {
	return fileDescriptor_8e286d38e250f484, []int{7}
}

func (m *Camerabox) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Camerabox.Unmarshal(m, b)
}
func (m *Camerabox) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Camerabox.Marshal(b, m, deterministic)
}
func (m *Camerabox) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Camerabox.Merge(m, src)
}
func (m *Camerabox) XXX_Size() int {
	return xxx_messageInfo_Camerabox.Size(m)
}
func (m *Camerabox) XXX_DiscardUnknown() {
	xxx_messageInfo_Camerabox.DiscardUnknown(m)
}

var xxx_messageInfo_Camerabox proto.InternalMessageInfo

func (m *Camerabox) GetFacing() Camerabox_Facing {
	if m != nil {
		return m.Facing
	}
	return Camerabox_FACING_UNKNOWN
}

func init() {
	proto.RegisterEnum("unifiedfleet.api.v1.proto.chromeos.lab.CameraType", CameraType_name, CameraType_value)
	proto.RegisterEnum("unifiedfleet.api.v1.proto.chromeos.lab.CableType", CableType_name, CableType_value)
	proto.RegisterEnum("unifiedfleet.api.v1.proto.chromeos.lab.Wifi_AntennaConnection", Wifi_AntennaConnection_name, Wifi_AntennaConnection_value)
	proto.RegisterEnum("unifiedfleet.api.v1.proto.chromeos.lab.Wifi_Router", Wifi_Router_name, Wifi_Router_value)
	proto.RegisterEnum("unifiedfleet.api.v1.proto.chromeos.lab.Camerabox_Facing", Camerabox_Facing_name, Camerabox_Facing_value)
	proto.RegisterType((*Peripherals)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.Peripherals")
	proto.RegisterType((*RPM)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.RPM")
	proto.RegisterType((*Camera)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.Camera")
	proto.RegisterType((*Cable)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.Cable")
	proto.RegisterType((*Audio)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.Audio")
	proto.RegisterType((*Wifi)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.Wifi")
	proto.RegisterType((*Touch)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.Touch")
	proto.RegisterType((*Camerabox)(nil), "unifiedfleet.api.v1.proto.chromeos.lab.Camerabox")
}

func init() {
	proto.RegisterFile("infra/unifiedfleet/api/v1/proto/chromeos/lab/peripherals.proto", fileDescriptor_8e286d38e250f484)
}

var fileDescriptor_8e286d38e250f484 = []byte{
	// 848 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x94, 0x95, 0xdd, 0x6e, 0xdb, 0x36,
	0x18, 0x86, 0x27, 0xff, 0xd5, 0xfe, 0x9c, 0x38, 0x0a, 0xf7, 0x03, 0x21, 0xdd, 0x41, 0x20, 0x60,
	0x43, 0xd6, 0xad, 0xf2, 0xac, 0x6e, 0x40, 0xb0, 0x9f, 0x6e, 0xb2, 0xec, 0x24, 0x5a, 0x12, 0xc9,
	0x60, 0xec, 0xa6, 0x2d, 0x30, 0x08, 0xb4, 0x42, 0xcd, 0x02, 0x64, 0x51, 0x90, 0xe5, 0x74, 0xb9,
	0x99, 0xdd, 0xd4, 0xee, 0x65, 0xc7, 0x03, 0x49, 0x59, 0x36, 0xd0, 0x13, 0xeb, 0x4c, 0x7c, 0xc9,
	0xf7, 0xe1, 0xc7, 0x8f, 0x2f, 0x6d, 0x78, 0x1d, 0x25, 0x61, 0x46, 0xfa, 0xeb, 0x24, 0x0a, 0x23,
	0xfa, 0x10, 0xc6, 0x94, 0xe6, 0x7d, 0x92, 0x46, 0xfd, 0xc7, 0x41, 0x3f, 0xcd, 0x58, 0xce, 0xfa,
	0xc1, 0x22, 0x63, 0x4b, 0xca, 0x56, 0xfd, 0x98, 0xcc, 0xfb, 0x29, 0xcd, 0xa2, 0x74, 0x41, 0x33,
	0x12, 0xaf, 0x0c, 0x31, 0x8d, 0xbe, 0xde, 0x75, 0x1a, 0x24, 0x8d, 0x8c, 0xc7, 0x81, 0x9c, 0x32,
	0x36, 0x4e, 0x23, 0x26, 0xf3, 0x93, 0x5f, 0x2a, 0xed, 0x13, 0x2c, 0xc8, 0x92, 0xc6, 0x94, 0x25,
	0x12, 0x75, 0x72, 0x5e, 0xc9, 0xbd, 0xa2, 0xd9, 0x23, 0x93, 0x4e, 0xfd, 0xbf, 0x26, 0x74, 0x27,
	0xdb, 0xaa, 0x91, 0x0d, 0x4d, 0x31, 0xad, 0x29, 0xa7, 0xca, 0x59, 0xd7, 0x7c, 0x69, 0xec, 0x57,
	0xbf, 0x71, 0xc7, 0x4d, 0x58, 0x7a, 0x91, 0x07, 0x9d, 0xb2, 0x42, 0xad, 0x26, 0x40, 0x83, 0x7d,
	0x41, 0xf6, 0xc6, 0x88, 0xb7, 0x0c, 0xf4, 0x2b, 0xd4, 0xb3, 0x74, 0xa9, 0xd5, 0x05, 0xea, 0xdb,
	0x7d, 0x51, 0x78, 0x72, 0x8b, 0xb9, 0x0f, 0xbd, 0x03, 0x35, 0x60, 0x49, 0x42, 0x83, 0x9c, 0x3e,
	0xf8, 0x01, 0x59, 0xd2, 0x8c, 0x68, 0x8d, 0xd3, 0xfa, 0x59, 0xd7, 0x34, 0xf6, 0x2e, 0x4b, 0xb8,
	0xf0, 0x51, 0xc9, 0x91, 0x02, 0xef, 0x17, 0x59, 0x3f, 0x44, 0x4c, 0x6b, 0x56, 0xeb, 0x97, 0xc5,
	0x4d, 0x58, 0x7a, 0xd1, 0xef, 0xd0, 0xf8, 0x10, 0x85, 0x91, 0xd6, 0x12, 0x8c, 0xef, 0xf6, 0x65,
	0xdc, 0x47, 0x61, 0x84, 0x85, 0x93, 0x97, 0x91, 0xb3, 0x75, 0xb0, 0xd0, 0x9e, 0x55, 0x2b, 0x63,
	0xca, 0x4d, 0x58, 0x7a, 0x91, 0x06, 0xcf, 0x02, 0x92, 0x65, 0x11, 0xcd, 0xb4, 0xf6, 0xa9, 0x72,
	0xd6, 0xc1, 0x9b, 0x21, 0xfa, 0x12, 0x3a, 0xb2, 0x6d, 0x73, 0xf6, 0xb7, 0xd6, 0x39, 0x55, 0xce,
	0xda, 0x78, 0x2b, 0xa0, 0xcf, 0xa0, 0x19, 0x2c, 0x08, 0x5b, 0x69, 0x20, 0x66, 0xe4, 0x80, 0x97,
	0x14, 0x90, 0x79, 0x4c, 0xb5, 0xae, 0xe8, 0xf4, 0xcb, 0xfd, 0x3b, 0x3d, 0x8f, 0x29, 0x96, 0x5e,
	0xf4, 0x16, 0x7a, 0xe5, 0x3e, 0x7e, 0x94, 0x84, 0x4c, 0x3b, 0xa8, 0x18, 0xa7, 0x8d, 0x1b, 0x1f,
	0x96, 0x20, 0x27, 0x09, 0x99, 0x7e, 0x0f, 0x75, 0x3c, 0xb9, 0x45, 0x5f, 0x41, 0x2f, 0x65, 0x1f,
	0x68, 0xb6, 0x4e, 0xa2, 0xdc, 0x4f, 0xc8, 0x92, 0x8a, 0xe0, 0x77, 0xf0, 0x61, 0xa9, 0xba, 0x64,
	0x49, 0xd1, 0x37, 0xa0, 0x6e, 0x97, 0xb1, 0x75, 0x1e, 0xd3, 0x5c, 0x04, 0xbb, 0x83, 0x8f, 0x4a,
	0xdd, 0x13, 0xb2, 0xfe, 0x27, 0xb4, 0x8a, 0x6c, 0xdc, 0x41, 0x57, 0xee, 0xe9, 0xe7, 0x4f, 0xa9,
	0x04, 0xf7, 0x4c, 0xb3, 0x5a, 0xe5, 0xd3, 0xa7, 0x94, 0x62, 0x08, 0xca, 0x6f, 0xdd, 0x85, 0xa6,
	0xe8, 0x10, 0x1a, 0x43, 0x63, 0x07, 0x3b, 0xa8, 0xd4, 0x5e, 0x41, 0x15, 0x76, 0xfd, 0x27, 0x68,
	0x8a, 0x2c, 0xa2, 0xe7, 0xd0, 0x11, 0x69, 0xf4, 0xf9, 0x1d, 0x2b, 0xe2, 0x26, 0xdb, 0x42, 0x18,
	0xca, 0x2b, 0x26, 0x79, 0xb6, 0x5e, 0x89, 0x43, 0xb7, 0xb1, 0x1c, 0xe8, 0xff, 0xd6, 0xa0, 0xc1,
	0x43, 0x88, 0x4e, 0xa0, 0xcd, 0x63, 0x18, 0xd0, 0x38, 0xde, 0x58, 0x37, 0x63, 0x44, 0xe0, 0x80,
	0x24, 0x39, 0x4d, 0x12, 0xe2, 0xf3, 0xc7, 0x23, 0x08, 0x3d, 0xf3, 0x75, 0x95, 0x90, 0x1b, 0x96,
	0x04, 0xd8, 0xf2, 0xf1, 0x45, 0x2c, 0xc1, 0x5d, 0xb2, 0x95, 0xd0, 0x35, 0xb4, 0x32, 0xb6, 0xce,
	0x69, 0x26, 0x7e, 0x21, 0x7a, 0xe6, 0xab, 0x4a, 0x70, 0x2c, 0xac, 0xb8, 0x40, 0xe8, 0x57, 0x70,
	0xfc, 0xd1, 0x76, 0x48, 0x85, 0x03, 0xdb, 0x73, 0x5d, 0x7f, 0xe6, 0x5e, 0xbb, 0xde, 0xbd, 0xab,
	0x7e, 0x82, 0x3e, 0x85, 0x23, 0xa1, 0xd8, 0x9e, 0x3b, 0x9a, 0xd9, 0x53, 0xe7, 0xcd, 0x58, 0x55,
	0xd0, 0x01, 0xb4, 0x85, 0xe8, 0x4d, 0x2d, 0xb5, 0xa6, 0xff, 0x08, 0x2d, 0xc9, 0x46, 0x5f, 0x00,
	0xc2, 0xde, 0x6c, 0x3a, 0xc6, 0xfe, 0xcc, 0xbd, 0x9b, 0x8c, 0x6d, 0xe7, 0xc2, 0x19, 0x8f, 0x24,
	0xa4, 0xd0, 0xcf, 0xbf, 0x37, 0xfd, 0xc1, 0xc0, 0x7a, 0xab, 0x2a, 0xfa, 0x73, 0x68, 0x8a, 0x67,
	0x89, 0x10, 0x34, 0x96, 0xd1, 0x92, 0x15, 0x1d, 0x15, 0xdf, 0xfa, 0x3f, 0x0a, 0x74, 0xca, 0x4c,
	0xa3, 0x09, 0xb4, 0x42, 0x12, 0x44, 0xc9, 0x5f, 0x45, 0x0a, 0xce, 0x2b, 0x3f, 0x0b, 0xe3, 0x42,
	0xf8, 0x71, 0xc1, 0xd1, 0x7f, 0x83, 0x96, 0x54, 0x10, 0x82, 0xde, 0x85, 0x65, 0x3b, 0xee, 0xe5,
	0xce, 0xa1, 0x8f, 0xa0, 0x5b, 0x68, 0x43, 0xcb, 0xbe, 0x56, 0x15, 0xde, 0x97, 0x42, 0xb8, 0xc0,
	0x9e, 0x3b, 0x55, 0x6b, 0x2f, 0x2e, 0x01, 0xb6, 0xc9, 0xe5, 0x10, 0xdb, 0xba, 0x1d, 0x63, 0xcb,
	0x77, 0xdc, 0x37, 0xd6, 0x8d, 0xc3, 0x0f, 0x7d, 0x0c, 0x87, 0x85, 0x76, 0x35, 0x1b, 0x8d, 0x6e,
	0xde, 0xa9, 0xca, 0xce, 0xb2, 0xc9, 0xf4, 0xfd, 0x04, 0x7b, 0xa6, 0x5a, 0x7b, 0xb1, 0xe2, 0x07,
	0x2d, 0xb2, 0x2a, 0x3d, 0xc3, 0x9b, 0xf1, 0x0e, 0x86, 0x5f, 0x80, 0x90, 0xac, 0xd9, 0xc8, 0xf1,
	0xfe, 0x90, 0xf5, 0x08, 0x10, 0x17, 0x67, 0x77, 0x43, 0xa1, 0xab, 0x35, 0xf4, 0x39, 0x1c, 0x97,
	0xda, 0x04, 0x3b, 0xee, 0xd4, 0x71, 0x2f, 0xd5, 0xfa, 0xd6, 0x7f, 0x35, 0xba, 0x75, 0xe4, 0xda,
	0xc6, 0xf0, 0x87, 0xf7, 0x66, 0x95, 0xbf, 0xd2, 0x9f, 0xd7, 0xe1, 0x2a, 0x9d, 0xcf, 0x5b, 0x62,
	0xe6, 0xd5, 0xff, 0x01, 0x00, 0x00, 0xff, 0xff, 0x08, 0x82, 0xc4, 0xef, 0x2d, 0x08, 0x00, 0x00,
}