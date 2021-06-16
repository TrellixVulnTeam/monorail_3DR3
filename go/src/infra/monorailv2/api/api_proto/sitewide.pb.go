// Code generated by protoc-gen-go. DO NOT EDIT.
// source: api/api_proto/sitewide.proto

package monorail

import prpc "go.chromium.org/luci/grpc/prpc"

import (
	context "context"
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
	grpc "google.golang.org/grpc"
	codes "google.golang.org/grpc/codes"
	status "google.golang.org/grpc/status"
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

// Next available tag: 4
type RefreshTokenRequest struct {
	Token                string   `protobuf:"bytes,2,opt,name=token,proto3" json:"token,omitempty"`
	TokenPath            string   `protobuf:"bytes,3,opt,name=token_path,json=tokenPath,proto3" json:"token_path,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *RefreshTokenRequest) Reset()         { *m = RefreshTokenRequest{} }
func (m *RefreshTokenRequest) String() string { return proto.CompactTextString(m) }
func (*RefreshTokenRequest) ProtoMessage()    {}
func (*RefreshTokenRequest) Descriptor() ([]byte, []int) {
	return fileDescriptor_03599899b30de215, []int{0}
}

func (m *RefreshTokenRequest) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_RefreshTokenRequest.Unmarshal(m, b)
}
func (m *RefreshTokenRequest) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_RefreshTokenRequest.Marshal(b, m, deterministic)
}
func (m *RefreshTokenRequest) XXX_Merge(src proto.Message) {
	xxx_messageInfo_RefreshTokenRequest.Merge(m, src)
}
func (m *RefreshTokenRequest) XXX_Size() int {
	return xxx_messageInfo_RefreshTokenRequest.Size(m)
}
func (m *RefreshTokenRequest) XXX_DiscardUnknown() {
	xxx_messageInfo_RefreshTokenRequest.DiscardUnknown(m)
}

var xxx_messageInfo_RefreshTokenRequest proto.InternalMessageInfo

func (m *RefreshTokenRequest) GetToken() string {
	if m != nil {
		return m.Token
	}
	return ""
}

func (m *RefreshTokenRequest) GetTokenPath() string {
	if m != nil {
		return m.TokenPath
	}
	return ""
}

// Next available tag: 3
type RefreshTokenResponse struct {
	Token                string   `protobuf:"bytes,1,opt,name=token,proto3" json:"token,omitempty"`
	TokenExpiresSec      uint32   `protobuf:"varint,2,opt,name=token_expires_sec,json=tokenExpiresSec,proto3" json:"token_expires_sec,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *RefreshTokenResponse) Reset()         { *m = RefreshTokenResponse{} }
func (m *RefreshTokenResponse) String() string { return proto.CompactTextString(m) }
func (*RefreshTokenResponse) ProtoMessage()    {}
func (*RefreshTokenResponse) Descriptor() ([]byte, []int) {
	return fileDescriptor_03599899b30de215, []int{1}
}

func (m *RefreshTokenResponse) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_RefreshTokenResponse.Unmarshal(m, b)
}
func (m *RefreshTokenResponse) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_RefreshTokenResponse.Marshal(b, m, deterministic)
}
func (m *RefreshTokenResponse) XXX_Merge(src proto.Message) {
	xxx_messageInfo_RefreshTokenResponse.Merge(m, src)
}
func (m *RefreshTokenResponse) XXX_Size() int {
	return xxx_messageInfo_RefreshTokenResponse.Size(m)
}
func (m *RefreshTokenResponse) XXX_DiscardUnknown() {
	xxx_messageInfo_RefreshTokenResponse.DiscardUnknown(m)
}

var xxx_messageInfo_RefreshTokenResponse proto.InternalMessageInfo

func (m *RefreshTokenResponse) GetToken() string {
	if m != nil {
		return m.Token
	}
	return ""
}

func (m *RefreshTokenResponse) GetTokenExpiresSec() uint32 {
	if m != nil {
		return m.TokenExpiresSec
	}
	return 0
}

// Next available tag: 1
type GetServerStatusRequest struct {
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *GetServerStatusRequest) Reset()         { *m = GetServerStatusRequest{} }
func (m *GetServerStatusRequest) String() string { return proto.CompactTextString(m) }
func (*GetServerStatusRequest) ProtoMessage()    {}
func (*GetServerStatusRequest) Descriptor() ([]byte, []int) {
	return fileDescriptor_03599899b30de215, []int{2}
}

func (m *GetServerStatusRequest) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_GetServerStatusRequest.Unmarshal(m, b)
}
func (m *GetServerStatusRequest) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_GetServerStatusRequest.Marshal(b, m, deterministic)
}
func (m *GetServerStatusRequest) XXX_Merge(src proto.Message) {
	xxx_messageInfo_GetServerStatusRequest.Merge(m, src)
}
func (m *GetServerStatusRequest) XXX_Size() int {
	return xxx_messageInfo_GetServerStatusRequest.Size(m)
}
func (m *GetServerStatusRequest) XXX_DiscardUnknown() {
	xxx_messageInfo_GetServerStatusRequest.DiscardUnknown(m)
}

var xxx_messageInfo_GetServerStatusRequest proto.InternalMessageInfo

// Next available tag: 4
type GetServerStatusResponse struct {
	BannerMessage        string   `protobuf:"bytes,1,opt,name=banner_message,json=bannerMessage,proto3" json:"banner_message,omitempty"`
	BannerTime           uint32   `protobuf:"fixed32,2,opt,name=banner_time,json=bannerTime,proto3" json:"banner_time,omitempty"`
	ReadOnly             bool     `protobuf:"varint,3,opt,name=read_only,json=readOnly,proto3" json:"read_only,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *GetServerStatusResponse) Reset()         { *m = GetServerStatusResponse{} }
func (m *GetServerStatusResponse) String() string { return proto.CompactTextString(m) }
func (*GetServerStatusResponse) ProtoMessage()    {}
func (*GetServerStatusResponse) Descriptor() ([]byte, []int) {
	return fileDescriptor_03599899b30de215, []int{3}
}

func (m *GetServerStatusResponse) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_GetServerStatusResponse.Unmarshal(m, b)
}
func (m *GetServerStatusResponse) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_GetServerStatusResponse.Marshal(b, m, deterministic)
}
func (m *GetServerStatusResponse) XXX_Merge(src proto.Message) {
	xxx_messageInfo_GetServerStatusResponse.Merge(m, src)
}
func (m *GetServerStatusResponse) XXX_Size() int {
	return xxx_messageInfo_GetServerStatusResponse.Size(m)
}
func (m *GetServerStatusResponse) XXX_DiscardUnknown() {
	xxx_messageInfo_GetServerStatusResponse.DiscardUnknown(m)
}

var xxx_messageInfo_GetServerStatusResponse proto.InternalMessageInfo

func (m *GetServerStatusResponse) GetBannerMessage() string {
	if m != nil {
		return m.BannerMessage
	}
	return ""
}

func (m *GetServerStatusResponse) GetBannerTime() uint32 {
	if m != nil {
		return m.BannerTime
	}
	return 0
}

func (m *GetServerStatusResponse) GetReadOnly() bool {
	if m != nil {
		return m.ReadOnly
	}
	return false
}

func init() {
	proto.RegisterType((*RefreshTokenRequest)(nil), "monorail.RefreshTokenRequest")
	proto.RegisterType((*RefreshTokenResponse)(nil), "monorail.RefreshTokenResponse")
	proto.RegisterType((*GetServerStatusRequest)(nil), "monorail.GetServerStatusRequest")
	proto.RegisterType((*GetServerStatusResponse)(nil), "monorail.GetServerStatusResponse")
}

func init() {
	proto.RegisterFile("api/api_proto/sitewide.proto", fileDescriptor_03599899b30de215)
}

var fileDescriptor_03599899b30de215 = []byte{
	// 312 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x7c, 0x92, 0xd1, 0x4a, 0xfb, 0x30,
	0x14, 0xc6, 0xff, 0xfb, 0x8b, 0xda, 0x1e, 0x9d, 0xc3, 0x38, 0xb4, 0x4c, 0xa7, 0xb3, 0x20, 0x88,
	0x17, 0x1d, 0xe8, 0x33, 0x88, 0x20, 0xc8, 0x24, 0xdd, 0xc5, 0xee, 0x4a, 0xb6, 0x1d, 0x6d, 0xb0,
	0x4d, 0x62, 0x92, 0xa9, 0xbb, 0xf1, 0xad, 0x7c, 0x3f, 0x59, 0xd2, 0xb1, 0xa9, 0xd3, 0xbb, 0x9e,
	0xdf, 0x77, 0xfa, 0x9d, 0x73, 0x3e, 0x02, 0x47, 0x4c, 0xf1, 0x2e, 0x53, 0x3c, 0x53, 0x5a, 0x5a,
	0xd9, 0x35, 0xdc, 0xe2, 0x2b, 0x1f, 0x63, 0xe2, 0x4a, 0x12, 0x94, 0x52, 0x48, 0xcd, 0x78, 0x11,
	0xdf, 0xc2, 0x1e, 0xc5, 0x07, 0x8d, 0x26, 0xef, 0xcb, 0x27, 0x14, 0x14, 0x9f, 0x27, 0x68, 0x2c,
	0x69, 0xc2, 0xba, 0x9d, 0xd5, 0xd1, 0xff, 0x4e, 0xed, 0x3c, 0xa4, 0xbe, 0x20, 0x6d, 0x00, 0xf7,
	0x91, 0x29, 0x66, 0xf3, 0x68, 0xcd, 0x49, 0xa1, 0x23, 0xf7, 0xcc, 0xe6, 0xf1, 0x00, 0x9a, 0x5f,
	0xbd, 0x8c, 0x92, 0xc2, 0xe0, 0xc2, 0xac, 0xb6, 0x6c, 0x76, 0x01, 0xbb, 0xde, 0x0c, 0xdf, 0x14,
	0xd7, 0x68, 0x32, 0x83, 0x23, 0x37, 0xae, 0x4e, 0x1b, 0x4e, 0xb8, 0xf6, 0x3c, 0xc5, 0x51, 0x1c,
	0xc1, 0xfe, 0x0d, 0xda, 0x14, 0xf5, 0x0b, 0xea, 0xd4, 0x32, 0x3b, 0x31, 0xd5, 0xa2, 0xf1, 0x3b,
	0x1c, 0xfc, 0x50, 0xaa, 0xb1, 0x67, 0xb0, 0x33, 0x64, 0x42, 0xa0, 0xce, 0x4a, 0x34, 0x86, 0x3d,
	0x62, 0x35, 0xbf, 0xee, 0xe9, 0x9d, 0x87, 0xe4, 0x04, 0xb6, 0xaa, 0x36, 0xcb, 0x4b, 0x74, 0x1b,
	0x6c, 0x52, 0xf0, 0xa8, 0xcf, 0x4b, 0x24, 0x87, 0x10, 0x6a, 0x64, 0xe3, 0x4c, 0x8a, 0x62, 0xea,
	0x8e, 0x0e, 0x68, 0x30, 0x03, 0x3d, 0x51, 0x4c, 0x2f, 0x3f, 0x6a, 0x10, 0xa4, 0x55, 0xb8, 0xa4,
	0x07, 0xdb, 0xcb, 0x01, 0x90, 0x76, 0x32, 0xcf, 0x39, 0x59, 0x11, 0x72, 0xeb, 0xf8, 0x37, 0xd9,
	0x1f, 0x10, 0xff, 0x23, 0x03, 0x68, 0x7c, 0xbb, 0x8e, 0x74, 0x16, 0x3f, 0xad, 0x8e, 0xa4, 0x75,
	0xfa, 0x47, 0xc7, 0xdc, 0x79, 0xb8, 0xe1, 0x1e, 0xc2, 0xd5, 0x67, 0x00, 0x00, 0x00, 0xff, 0xff,
	0x80, 0x29, 0xfd, 0xe1, 0x28, 0x02, 0x00, 0x00,
}

// Reference imports to suppress errors if they are not otherwise used.
var _ context.Context
var _ grpc.ClientConnInterface

// This is a compile-time assertion to ensure that this generated file
// is compatible with the grpc package it is being compiled against.
const _ = grpc.SupportPackageIsVersion6

// SitewideClient is the client API for Sitewide service.
//
// For semantics around ctx use and closing/ending streaming RPCs, please refer to https://godoc.org/google.golang.org/grpc#ClientConn.NewStream.
type SitewideClient interface {
	RefreshToken(ctx context.Context, in *RefreshTokenRequest, opts ...grpc.CallOption) (*RefreshTokenResponse, error)
	GetServerStatus(ctx context.Context, in *GetServerStatusRequest, opts ...grpc.CallOption) (*GetServerStatusResponse, error)
}
type sitewidePRPCClient struct {
	client *prpc.Client
}

func NewSitewidePRPCClient(client *prpc.Client) SitewideClient {
	return &sitewidePRPCClient{client}
}

func (c *sitewidePRPCClient) RefreshToken(ctx context.Context, in *RefreshTokenRequest, opts ...grpc.CallOption) (*RefreshTokenResponse, error) {
	out := new(RefreshTokenResponse)
	err := c.client.Call(ctx, "monorail.Sitewide", "RefreshToken", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}

func (c *sitewidePRPCClient) GetServerStatus(ctx context.Context, in *GetServerStatusRequest, opts ...grpc.CallOption) (*GetServerStatusResponse, error) {
	out := new(GetServerStatusResponse)
	err := c.client.Call(ctx, "monorail.Sitewide", "GetServerStatus", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}

type sitewideClient struct {
	cc grpc.ClientConnInterface
}

func NewSitewideClient(cc grpc.ClientConnInterface) SitewideClient {
	return &sitewideClient{cc}
}

func (c *sitewideClient) RefreshToken(ctx context.Context, in *RefreshTokenRequest, opts ...grpc.CallOption) (*RefreshTokenResponse, error) {
	out := new(RefreshTokenResponse)
	err := c.cc.Invoke(ctx, "/monorail.Sitewide/RefreshToken", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}

func (c *sitewideClient) GetServerStatus(ctx context.Context, in *GetServerStatusRequest, opts ...grpc.CallOption) (*GetServerStatusResponse, error) {
	out := new(GetServerStatusResponse)
	err := c.cc.Invoke(ctx, "/monorail.Sitewide/GetServerStatus", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}

// SitewideServer is the server API for Sitewide service.
type SitewideServer interface {
	RefreshToken(context.Context, *RefreshTokenRequest) (*RefreshTokenResponse, error)
	GetServerStatus(context.Context, *GetServerStatusRequest) (*GetServerStatusResponse, error)
}

// UnimplementedSitewideServer can be embedded to have forward compatible implementations.
type UnimplementedSitewideServer struct {
}

func (*UnimplementedSitewideServer) RefreshToken(ctx context.Context, req *RefreshTokenRequest) (*RefreshTokenResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "method RefreshToken not implemented")
}
func (*UnimplementedSitewideServer) GetServerStatus(ctx context.Context, req *GetServerStatusRequest) (*GetServerStatusResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "method GetServerStatus not implemented")
}

func RegisterSitewideServer(s prpc.Registrar, srv SitewideServer) {
	s.RegisterService(&_Sitewide_serviceDesc, srv)
}

func _Sitewide_RefreshToken_Handler(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	in := new(RefreshTokenRequest)
	if err := dec(in); err != nil {
		return nil, err
	}
	if interceptor == nil {
		return srv.(SitewideServer).RefreshToken(ctx, in)
	}
	info := &grpc.UnaryServerInfo{
		Server:     srv,
		FullMethod: "/monorail.Sitewide/RefreshToken",
	}
	handler := func(ctx context.Context, req interface{}) (interface{}, error) {
		return srv.(SitewideServer).RefreshToken(ctx, req.(*RefreshTokenRequest))
	}
	return interceptor(ctx, in, info, handler)
}

func _Sitewide_GetServerStatus_Handler(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	in := new(GetServerStatusRequest)
	if err := dec(in); err != nil {
		return nil, err
	}
	if interceptor == nil {
		return srv.(SitewideServer).GetServerStatus(ctx, in)
	}
	info := &grpc.UnaryServerInfo{
		Server:     srv,
		FullMethod: "/monorail.Sitewide/GetServerStatus",
	}
	handler := func(ctx context.Context, req interface{}) (interface{}, error) {
		return srv.(SitewideServer).GetServerStatus(ctx, req.(*GetServerStatusRequest))
	}
	return interceptor(ctx, in, info, handler)
}

var _Sitewide_serviceDesc = grpc.ServiceDesc{
	ServiceName: "monorail.Sitewide",
	HandlerType: (*SitewideServer)(nil),
	Methods: []grpc.MethodDesc{
		{
			MethodName: "RefreshToken",
			Handler:    _Sitewide_RefreshToken_Handler,
		},
		{
			MethodName: "GetServerStatus",
			Handler:    _Sitewide_GetServerStatus_Handler,
		},
	},
	Streams:  []grpc.StreamDesc{},
	Metadata: "api/api_proto/sitewide.proto",
}
