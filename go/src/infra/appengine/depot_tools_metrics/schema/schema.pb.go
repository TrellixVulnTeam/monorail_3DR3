// Code generated by protoc-gen-go. DO NOT EDIT.
// source: schema.proto

package schema

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

// HttpRequest stores information on the HTTP requests made by the command.
type HttpRequest struct {
	// The host the request was made to. Must be one of the |knownHTTPHosts| in
	// metrics/constants.go.
	// e.g. chromium-review.googlesource.com
	Host string `protobuf:"bytes,1,opt,name=host,proto3" json:"host,omitempty"`
	// The HTTP method used to make the request (e.g. GET, POST).
	Method string `protobuf:"bytes,2,opt,name=method,proto3" json:"method,omitempty"`
	// The path and URL arguments of the request.
	// The path must be one of the |knownHTTPPaths| and the arguments must be
	// |knownHTTPArguments| as defined in metrics/constants.go.
	//
	// The URL is not recorded since it might contain PII. Similarly, in most
	// cases, only the name of the arguments (and not their values) are recorded.
	// When the possible values for an argument is a fixed set, as is the case for
	// "o-parameters" in Gerrit, they'll be recorded as arguments.
	// Each argument is recorded separately, so as to make it easier to query.
	//
	// e.g. If the request was to
	// '/changes/?q=owner:foo@example.com+is:open&n=3&o=LABELS&o=ALL_REVISIONS'
	// The path will be '/changes' and the arguments will be 'q', 'n', 'o',
	// 'LABELS' and 'ALL_REVISIONS'.
	Path      string   `protobuf:"bytes,3,opt,name=path,proto3" json:"path,omitempty"`
	Arguments []string `protobuf:"bytes,4,rep,name=arguments,proto3" json:"arguments,omitempty"`
	// The HTTP response status.
	Status int64 `protobuf:"varint,5,opt,name=status,proto3" json:"status,omitempty"`
	// The latency of the HTTP request in seconds.
	// TODO(ehmaldonado): Consider converting to google.protobuf.Duration.
	ResponseTime         float64  `protobuf:"fixed64,6,opt,name=response_time,json=responseTime,proto3" json:"response_time,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *HttpRequest) Reset()         { *m = HttpRequest{} }
func (m *HttpRequest) String() string { return proto.CompactTextString(m) }
func (*HttpRequest) ProtoMessage()    {}
func (*HttpRequest) Descriptor() ([]byte, []int) {
	return fileDescriptor_1c5fb4d8cc22d66a, []int{0}
}

func (m *HttpRequest) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_HttpRequest.Unmarshal(m, b)
}
func (m *HttpRequest) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_HttpRequest.Marshal(b, m, deterministic)
}
func (m *HttpRequest) XXX_Merge(src proto.Message) {
	xxx_messageInfo_HttpRequest.Merge(m, src)
}
func (m *HttpRequest) XXX_Size() int {
	return xxx_messageInfo_HttpRequest.Size(m)
}
func (m *HttpRequest) XXX_DiscardUnknown() {
	xxx_messageInfo_HttpRequest.DiscardUnknown(m)
}

var xxx_messageInfo_HttpRequest proto.InternalMessageInfo

func (m *HttpRequest) GetHost() string {
	if m != nil {
		return m.Host
	}
	return ""
}

func (m *HttpRequest) GetMethod() string {
	if m != nil {
		return m.Method
	}
	return ""
}

func (m *HttpRequest) GetPath() string {
	if m != nil {
		return m.Path
	}
	return ""
}

func (m *HttpRequest) GetArguments() []string {
	if m != nil {
		return m.Arguments
	}
	return nil
}

func (m *HttpRequest) GetStatus() int64 {
	if m != nil {
		return m.Status
	}
	return 0
}

func (m *HttpRequest) GetResponseTime() float64 {
	if m != nil {
		return m.ResponseTime
	}
	return 0
}

// SubCommand stores information on the sub-commands executed by the command.
type SubCommand struct {
	// The sub-command that was executed. Must be one of the |knownSubCommands| in
	// metrics/constans.go.
	Command string `protobuf:"bytes,1,opt,name=command,proto3" json:"command,omitempty"`
	// The arguments passed to the sub-command. All arguments must be
	// |knownSubCommandArguments| as defined in metrics/constants.go.
	Arguments []string `protobuf:"bytes,2,rep,name=arguments,proto3" json:"arguments,omitempty"`
	// The runtime of the sub-command runtime in seconds.
	// TODO(ehmaldonado): Consider converting to google.protobuf.Duration.
	ExecutionTime float64 `protobuf:"fixed64,3,opt,name=execution_time,json=executionTime,proto3" json:"execution_time,omitempty"`
	// The exit code of the sub-command.
	ExitCode             int64    `protobuf:"varint,4,opt,name=exit_code,json=exitCode,proto3" json:"exit_code,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *SubCommand) Reset()         { *m = SubCommand{} }
func (m *SubCommand) String() string { return proto.CompactTextString(m) }
func (*SubCommand) ProtoMessage()    {}
func (*SubCommand) Descriptor() ([]byte, []int) {
	return fileDescriptor_1c5fb4d8cc22d66a, []int{1}
}

func (m *SubCommand) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_SubCommand.Unmarshal(m, b)
}
func (m *SubCommand) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_SubCommand.Marshal(b, m, deterministic)
}
func (m *SubCommand) XXX_Merge(src proto.Message) {
	xxx_messageInfo_SubCommand.Merge(m, src)
}
func (m *SubCommand) XXX_Size() int {
	return xxx_messageInfo_SubCommand.Size(m)
}
func (m *SubCommand) XXX_DiscardUnknown() {
	xxx_messageInfo_SubCommand.DiscardUnknown(m)
}

var xxx_messageInfo_SubCommand proto.InternalMessageInfo

func (m *SubCommand) GetCommand() string {
	if m != nil {
		return m.Command
	}
	return ""
}

func (m *SubCommand) GetArguments() []string {
	if m != nil {
		return m.Arguments
	}
	return nil
}

func (m *SubCommand) GetExecutionTime() float64 {
	if m != nil {
		return m.ExecutionTime
	}
	return 0
}

func (m *SubCommand) GetExitCode() int64 {
	if m != nil {
		return m.ExitCode
	}
	return 0
}

// Metrics stores information for a depot_tools command's execution.
type Metrics struct {
	// The version of the format used to report the metrics.
	MetricsVersion int64 `protobuf:"varint,1,opt,name=metrics_version,json=metricsVersion,proto3" json:"metrics_version,omitempty"`
	// A UNIX timestamp for the time when the command was executed.
	// TODO(ehmaldonado): Consider converting to google.protobuf.Timestamp.
	Timestamp int64 `protobuf:"varint,2,opt,name=timestamp,proto3" json:"timestamp,omitempty"`
	// The command that was executed. Must be one of the |knownCommands| defined
	// in metrics/constants.go.
	Command string `protobuf:"bytes,3,opt,name=command,proto3" json:"command,omitempty"`
	// The arguments passed to the command. All arguments must be |knownArguments|
	// as defined in metrics/constants.go.
	Arguments []string `protobuf:"bytes,4,rep,name=arguments,proto3" json:"arguments,omitempty"`
	// The runtime of the command in seconds.
	// TODO(ehmaldonado): Consider converting to google.protobuf.Duration.
	ExecutionTime float64 `protobuf:"fixed64,5,opt,name=execution_time,json=executionTime,proto3" json:"execution_time,omitempty"`
	// The exit code of the command.
	ExitCode int64 `protobuf:"varint,6,opt,name=exit_code,json=exitCode,proto3" json:"exit_code,omitempty"`
	// Information on the sub-commands executed by this command.
	SubCommands []*SubCommand `protobuf:"bytes,7,rep,name=sub_commands,json=subCommands,proto3" json:"sub_commands,omitempty"`
	// Information on the HTTP requests made by this command.
	HttpRequests []*HttpRequest `protobuf:"bytes,8,rep,name=http_requests,json=httpRequests,proto3" json:"http_requests,omitempty"`
	// The URLs of the current project(s).
	// e.g. The project to which git-cl uploads a change; the projects gclient is
	// configured to manage; etc.
	// Must be one of the |knownProjectURLs| as defined in metrics/constants.go.
	ProjectUrls []string `protobuf:"bytes,9,rep,name=project_urls,json=projectUrls,proto3" json:"project_urls,omitempty"`
	// A UNIX timestamp for the time depot_tools was last modified.
	// TODO(ehmaldonado): Consider converting to google.protobuf.Timestamp.
	DepotToolsAge float64 `protobuf:"fixed64,10,opt,name=depot_tools_age,json=depotToolsAge,proto3" json:"depot_tools_age,omitempty"`
	// The arch the command was executed on. Must be one of the |knownHostArchs|
	// as defined in metrics/constants.go.
	// e.g. x86, arm
	HostArch string `protobuf:"bytes,11,opt,name=host_arch,json=hostArch,proto3" json:"host_arch,omitempty"`
	// The OS the command was executed on. Must be one of the |knownOSs| as
	// defined in metrics/constants.go.
	HostOs string `protobuf:"bytes,12,opt,name=host_os,json=hostOs,proto3" json:"host_os,omitempty"`
	// The python version the command was executed with. Must match the
	// |pythonVersionRegex| defined in metrics/constants.go.
	PythonVersion string `protobuf:"bytes,13,opt,name=python_version,json=pythonVersion,proto3" json:"python_version,omitempty"`
	// The git version the command used. Must match the |gitVersionRegex| defined
	// in metrics/constants.go.
	GitVersion           string   `protobuf:"bytes,14,opt,name=git_version,json=gitVersion,proto3" json:"git_version,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Metrics) Reset()         { *m = Metrics{} }
func (m *Metrics) String() string { return proto.CompactTextString(m) }
func (*Metrics) ProtoMessage()    {}
func (*Metrics) Descriptor() ([]byte, []int) {
	return fileDescriptor_1c5fb4d8cc22d66a, []int{2}
}

func (m *Metrics) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Metrics.Unmarshal(m, b)
}
func (m *Metrics) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Metrics.Marshal(b, m, deterministic)
}
func (m *Metrics) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Metrics.Merge(m, src)
}
func (m *Metrics) XXX_Size() int {
	return xxx_messageInfo_Metrics.Size(m)
}
func (m *Metrics) XXX_DiscardUnknown() {
	xxx_messageInfo_Metrics.DiscardUnknown(m)
}

var xxx_messageInfo_Metrics proto.InternalMessageInfo

func (m *Metrics) GetMetricsVersion() int64 {
	if m != nil {
		return m.MetricsVersion
	}
	return 0
}

func (m *Metrics) GetTimestamp() int64 {
	if m != nil {
		return m.Timestamp
	}
	return 0
}

func (m *Metrics) GetCommand() string {
	if m != nil {
		return m.Command
	}
	return ""
}

func (m *Metrics) GetArguments() []string {
	if m != nil {
		return m.Arguments
	}
	return nil
}

func (m *Metrics) GetExecutionTime() float64 {
	if m != nil {
		return m.ExecutionTime
	}
	return 0
}

func (m *Metrics) GetExitCode() int64 {
	if m != nil {
		return m.ExitCode
	}
	return 0
}

func (m *Metrics) GetSubCommands() []*SubCommand {
	if m != nil {
		return m.SubCommands
	}
	return nil
}

func (m *Metrics) GetHttpRequests() []*HttpRequest {
	if m != nil {
		return m.HttpRequests
	}
	return nil
}

func (m *Metrics) GetProjectUrls() []string {
	if m != nil {
		return m.ProjectUrls
	}
	return nil
}

func (m *Metrics) GetDepotToolsAge() float64 {
	if m != nil {
		return m.DepotToolsAge
	}
	return 0
}

func (m *Metrics) GetHostArch() string {
	if m != nil {
		return m.HostArch
	}
	return ""
}

func (m *Metrics) GetHostOs() string {
	if m != nil {
		return m.HostOs
	}
	return ""
}

func (m *Metrics) GetPythonVersion() string {
	if m != nil {
		return m.PythonVersion
	}
	return ""
}

func (m *Metrics) GetGitVersion() string {
	if m != nil {
		return m.GitVersion
	}
	return ""
}

func init() {
	proto.RegisterType((*HttpRequest)(nil), "schema.HttpRequest")
	proto.RegisterType((*SubCommand)(nil), "schema.SubCommand")
	proto.RegisterType((*Metrics)(nil), "schema.Metrics")
}

func init() { proto.RegisterFile("schema.proto", fileDescriptor_1c5fb4d8cc22d66a) }

var fileDescriptor_1c5fb4d8cc22d66a = []byte{
	// 458 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x84, 0x93, 0xc1, 0x8e, 0x94, 0x4c,
	0x10, 0xc7, 0xc3, 0xc2, 0x32, 0x43, 0x01, 0xb3, 0x49, 0x7f, 0xc9, 0x67, 0x27, 0x9a, 0x88, 0x63,
	0x54, 0x4e, 0x7b, 0xd0, 0x98, 0x78, 0xdd, 0xec, 0xc5, 0x8b, 0x31, 0xc1, 0xd5, 0x2b, 0x61, 0xa0,
	0x02, 0x98, 0x81, 0xc6, 0xae, 0xc2, 0xac, 0x2f, 0x60, 0x7c, 0x14, 0x1f, 0xd3, 0x74, 0x37, 0x33,
	0xb3, 0xeb, 0xc1, 0xbd, 0x55, 0xfd, 0xba, 0x9a, 0xfa, 0xff, 0xab, 0x0b, 0x48, 0xa8, 0xee, 0x70,
	0xa8, 0x2e, 0x27, 0xad, 0x58, 0x89, 0xd0, 0x65, 0xdb, 0xdf, 0x1e, 0xc4, 0xef, 0x99, 0xa7, 0x02,
	0xbf, 0xcd, 0x48, 0x2c, 0x04, 0x04, 0x9d, 0x22, 0x96, 0x5e, 0xe6, 0xe5, 0x51, 0x61, 0x63, 0xf1,
	0x3f, 0x84, 0x03, 0x72, 0xa7, 0x1a, 0x79, 0x66, 0xe9, 0x92, 0x99, 0xda, 0xa9, 0xe2, 0x4e, 0xfa,
	0xae, 0xd6, 0xc4, 0xe2, 0x09, 0x44, 0x95, 0x6e, 0xe7, 0x01, 0x47, 0x26, 0x19, 0x64, 0x7e, 0x1e,
	0x15, 0x27, 0x60, 0xbe, 0x44, 0x5c, 0xf1, 0x4c, 0xf2, 0x3c, 0xf3, 0x72, 0xbf, 0x58, 0x32, 0xf1,
	0x1c, 0x52, 0x8d, 0x34, 0xa9, 0x91, 0xb0, 0xe4, 0x7e, 0x40, 0x19, 0x66, 0x5e, 0xee, 0x15, 0xc9,
	0x01, 0xde, 0xf4, 0x03, 0x6e, 0x7f, 0x79, 0x00, 0x9f, 0xe6, 0xdd, 0xb5, 0x1a, 0x86, 0x6a, 0x6c,
	0x84, 0x84, 0x55, 0xed, 0xc2, 0x45, 0xec, 0x21, 0xbd, 0xaf, 0xe1, 0xec, 0x6f, 0x0d, 0x2f, 0x60,
	0x83, 0xb7, 0x58, 0xcf, 0xdc, 0xab, 0xd1, 0x35, 0xf3, 0x6d, 0xb3, 0xf4, 0x48, 0x4d, 0x37, 0xf1,
	0x18, 0x22, 0xbc, 0xed, 0xb9, 0xac, 0x55, 0x83, 0x32, 0xb0, 0x6a, 0xd7, 0x06, 0x5c, 0xab, 0x06,
	0xb7, 0x3f, 0x03, 0x58, 0x7d, 0x40, 0xd6, 0x7d, 0x4d, 0xe2, 0x15, 0x5c, 0x0c, 0x2e, 0x2c, 0xbf,
	0xa3, 0xa6, 0x5e, 0x8d, 0x56, 0x8f, 0x5f, 0x6c, 0x16, 0xfc, 0xc5, 0x51, 0x23, 0xcb, 0xb4, 0x23,
	0xae, 0x86, 0xc9, 0x4e, 0xd2, 0x2f, 0x4e, 0xe0, 0xae, 0x1d, 0xff, 0x1f, 0x76, 0x82, 0x87, 0xed,
	0x9c, 0x3f, 0x68, 0x27, 0xbc, 0x6f, 0x47, 0xbc, 0x85, 0x84, 0xe6, 0x5d, 0xb9, 0x34, 0x24, 0xb9,
	0xca, 0xfc, 0x3c, 0x7e, 0x2d, 0x2e, 0x97, 0x8d, 0x39, 0x0d, 0xbd, 0x88, 0xe9, 0x18, 0x93, 0x78,
	0x07, 0x69, 0xc7, 0x3c, 0x95, 0xda, 0xed, 0x0e, 0xc9, 0xb5, 0xbd, 0xf7, 0xdf, 0xe1, 0xde, 0x9d,
	0xbd, 0x2a, 0x92, 0xee, 0x94, 0x90, 0x78, 0x06, 0xc9, 0xa4, 0xd5, 0x57, 0xac, 0xb9, 0x9c, 0xf5,
	0x9e, 0x64, 0x64, 0x5d, 0xc5, 0x0b, 0xfb, 0xac, 0xf7, 0x24, 0x5e, 0xc2, 0x45, 0x83, 0x93, 0xe2,
	0x92, 0x95, 0xda, 0x53, 0x59, 0xb5, 0x28, 0xc1, 0x19, 0xb3, 0xf8, 0xc6, 0xd0, 0xab, 0xd6, 0x1a,
	0x33, 0x4b, 0x5a, 0x56, 0xba, 0xee, 0x64, 0x6c, 0x27, 0xb7, 0x36, 0xe0, 0x4a, 0xd7, 0x9d, 0x78,
	0x04, 0x2b, 0x7b, 0xa8, 0x48, 0x26, 0x6e, 0x75, 0x4d, 0xfa, 0xd1, 0x4e, 0x6d, 0xfa, 0xc1, 0x9d,
	0x1a, 0x8f, 0x6f, 0x96, 0xda, 0xf3, 0xd4, 0xd1, 0xc3, 0x93, 0x3d, 0x85, 0xb8, 0xed, 0xf9, 0x58,
	0xb3, 0xb1, 0x35, 0xd0, 0xf6, 0xbc, 0x14, 0xec, 0x42, 0xfb, 0x37, 0xbd, 0xf9, 0x13, 0x00, 0x00,
	0xff, 0xff, 0x78, 0xb3, 0x60, 0xa7, 0x5d, 0x03, 0x00, 0x00,
}
