// Code generated by protoc-gen-go. DO NOT EDIT.
// source: infra/tricium/api/admin/v1/workflow.proto

package admin

import (
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
	v1 "infra/tricium/api/v1"
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

// Tricium workflow configuration.
//
// A Workflow is generated from a merged service and project config,
// and contains information required for one workflow run.
type Workflow struct {
	// TODO(qyearsley): remove service_account if it is unused.
	ServiceAccount string    `protobuf:"bytes,1,opt,name=service_account,json=serviceAccount,proto3" json:"service_account,omitempty"`
	Workers        []*Worker `protobuf:"bytes,2,rep,name=workers,proto3" json:"workers,omitempty"`
	SwarmingServer string    `protobuf:"bytes,3,opt,name=swarming_server,json=swarmingServer,proto3" json:"swarming_server,omitempty"`
	IsolateServer  string    `protobuf:"bytes,4,opt,name=isolate_server,json=isolateServer,proto3" json:"isolate_server,omitempty"`
	// Function definitions used for this workflow; these contain the function
	// owner and component, to be used when filling out a bug filing template.
	Functions             []*v1.Function `protobuf:"bytes,5,rep,name=functions,proto3" json:"functions,omitempty"`
	BuildbucketServerHost string         `protobuf:"bytes,6,opt,name=buildbucket_server_host,json=buildbucketServerHost,proto3" json:"buildbucket_server_host,omitempty"`
	XXX_NoUnkeyedLiteral  struct{}       `json:"-"`
	XXX_unrecognized      []byte         `json:"-"`
	XXX_sizecache         int32          `json:"-"`
}

func (m *Workflow) Reset()         { *m = Workflow{} }
func (m *Workflow) String() string { return proto.CompactTextString(m) }
func (*Workflow) ProtoMessage()    {}
func (*Workflow) Descriptor() ([]byte, []int) {
	return fileDescriptor_7764f5c4faf0fbd9, []int{0}
}

func (m *Workflow) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Workflow.Unmarshal(m, b)
}
func (m *Workflow) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Workflow.Marshal(b, m, deterministic)
}
func (m *Workflow) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Workflow.Merge(m, src)
}
func (m *Workflow) XXX_Size() int {
	return xxx_messageInfo_Workflow.Size(m)
}
func (m *Workflow) XXX_DiscardUnknown() {
	xxx_messageInfo_Workflow.DiscardUnknown(m)
}

var xxx_messageInfo_Workflow proto.InternalMessageInfo

func (m *Workflow) GetServiceAccount() string {
	if m != nil {
		return m.ServiceAccount
	}
	return ""
}

func (m *Workflow) GetWorkers() []*Worker {
	if m != nil {
		return m.Workers
	}
	return nil
}

func (m *Workflow) GetSwarmingServer() string {
	if m != nil {
		return m.SwarmingServer
	}
	return ""
}

func (m *Workflow) GetIsolateServer() string {
	if m != nil {
		return m.IsolateServer
	}
	return ""
}

func (m *Workflow) GetFunctions() []*v1.Function {
	if m != nil {
		return m.Functions
	}
	return nil
}

func (m *Workflow) GetBuildbucketServerHost() string {
	if m != nil {
		return m.BuildbucketServerHost
	}
	return ""
}

// A Tricium worker includes the details needed to execute a function on a
// specific platform as swarming task.
type Worker struct {
	// Name of worker is combination of the function and platform name
	// for which results are provided, e.g "GitFileIsolator_LINUX".
	Name string `protobuf:"bytes,1,opt,name=name,proto3" json:"name,omitempty"`
	// Includes data dependencies for runtime type checking.
	// Platform-specific details are provided when required by the corresponding
	// data type.
	Needs               v1.Data_Type     `protobuf:"varint,2,opt,name=needs,proto3,enum=tricium.Data_Type" json:"needs,omitempty"`
	NeedsForPlatform    v1.Platform_Name `protobuf:"varint,3,opt,name=needs_for_platform,json=needsForPlatform,proto3,enum=tricium.Platform_Name" json:"needs_for_platform,omitempty"`
	Provides            v1.Data_Type     `protobuf:"varint,4,opt,name=provides,proto3,enum=tricium.Data_Type" json:"provides,omitempty"`
	ProvidesForPlatform v1.Platform_Name `protobuf:"varint,5,opt,name=provides_for_platform,json=providesForPlatform,proto3,enum=tricium.Platform_Name" json:"provides_for_platform,omitempty"`
	// Workers to run after this one.
	Next []string `protobuf:"bytes,6,rep,name=next,proto3" json:"next,omitempty"`
	// Name of the runtime platform configuration.
	RuntimePlatform v1.Platform_Name `protobuf:"varint,7,opt,name=runtime_platform,json=runtimePlatform,proto3,enum=tricium.Platform_Name" json:"runtime_platform,omitempty"`
	// Swarming dimensions for execution of the worker. These should be on the
	// form "key:value", using keys and values known to the swarming service.
	Dimensions []string `protobuf:"bytes,8,rep,name=dimensions,proto3" json:"dimensions,omitempty"`
	// List of cipd packages needed for the swarming task used to execute the
	// worker.
	CipdPackages []*v1.CipdPackage `protobuf:"bytes,9,rep,name=cipd_packages,json=cipdPackages,proto3" json:"cipd_packages,omitempty"`
	// Types that are valid to be assigned to Impl:
	//	*Worker_Cmd
	//	*Worker_Recipe
	Impl isWorker_Impl `protobuf_oneof:"impl"`
	// Deadline for execution of the worker in minutes. Note that this time
	// should include the overhead of triggering the corresponding swarming task
	// collecting result from it.
	Deadline             int32    `protobuf:"varint,11,opt,name=deadline,proto3" json:"deadline,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Worker) Reset()         { *m = Worker{} }
func (m *Worker) String() string { return proto.CompactTextString(m) }
func (*Worker) ProtoMessage()    {}
func (*Worker) Descriptor() ([]byte, []int) {
	return fileDescriptor_7764f5c4faf0fbd9, []int{1}
}

func (m *Worker) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Worker.Unmarshal(m, b)
}
func (m *Worker) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Worker.Marshal(b, m, deterministic)
}
func (m *Worker) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Worker.Merge(m, src)
}
func (m *Worker) XXX_Size() int {
	return xxx_messageInfo_Worker.Size(m)
}
func (m *Worker) XXX_DiscardUnknown() {
	xxx_messageInfo_Worker.DiscardUnknown(m)
}

var xxx_messageInfo_Worker proto.InternalMessageInfo

func (m *Worker) GetName() string {
	if m != nil {
		return m.Name
	}
	return ""
}

func (m *Worker) GetNeeds() v1.Data_Type {
	if m != nil {
		return m.Needs
	}
	return v1.Data_NONE
}

func (m *Worker) GetNeedsForPlatform() v1.Platform_Name {
	if m != nil {
		return m.NeedsForPlatform
	}
	return v1.Platform_ANY
}

func (m *Worker) GetProvides() v1.Data_Type {
	if m != nil {
		return m.Provides
	}
	return v1.Data_NONE
}

func (m *Worker) GetProvidesForPlatform() v1.Platform_Name {
	if m != nil {
		return m.ProvidesForPlatform
	}
	return v1.Platform_ANY
}

func (m *Worker) GetNext() []string {
	if m != nil {
		return m.Next
	}
	return nil
}

func (m *Worker) GetRuntimePlatform() v1.Platform_Name {
	if m != nil {
		return m.RuntimePlatform
	}
	return v1.Platform_ANY
}

func (m *Worker) GetDimensions() []string {
	if m != nil {
		return m.Dimensions
	}
	return nil
}

func (m *Worker) GetCipdPackages() []*v1.CipdPackage {
	if m != nil {
		return m.CipdPackages
	}
	return nil
}

type isWorker_Impl interface {
	isWorker_Impl()
}

type Worker_Cmd struct {
	Cmd *v1.Cmd `protobuf:"bytes,10,opt,name=cmd,proto3,oneof"`
}

type Worker_Recipe struct {
	Recipe *v1.Recipe `protobuf:"bytes,12,opt,name=recipe,proto3,oneof"`
}

func (*Worker_Cmd) isWorker_Impl() {}

func (*Worker_Recipe) isWorker_Impl() {}

func (m *Worker) GetImpl() isWorker_Impl {
	if m != nil {
		return m.Impl
	}
	return nil
}

func (m *Worker) GetCmd() *v1.Cmd {
	if x, ok := m.GetImpl().(*Worker_Cmd); ok {
		return x.Cmd
	}
	return nil
}

func (m *Worker) GetRecipe() *v1.Recipe {
	if x, ok := m.GetImpl().(*Worker_Recipe); ok {
		return x.Recipe
	}
	return nil
}

func (m *Worker) GetDeadline() int32 {
	if m != nil {
		return m.Deadline
	}
	return 0
}

// XXX_OneofWrappers is for the internal use of the proto package.
func (*Worker) XXX_OneofWrappers() []interface{} {
	return []interface{}{
		(*Worker_Cmd)(nil),
		(*Worker_Recipe)(nil),
	}
}

func init() {
	proto.RegisterType((*Workflow)(nil), "admin.Workflow")
	proto.RegisterType((*Worker)(nil), "admin.Worker")
}

func init() {
	proto.RegisterFile("infra/tricium/api/admin/v1/workflow.proto", fileDescriptor_7764f5c4faf0fbd9)
}

var fileDescriptor_7764f5c4faf0fbd9 = []byte{
	// 512 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x7c, 0x93, 0xdd, 0x6e, 0xd3, 0x30,
	0x14, 0xc7, 0xd7, 0xf5, 0x63, 0xed, 0xe9, 0xd7, 0x30, 0x0c, 0xa2, 0x5e, 0x40, 0x35, 0x84, 0x96,
	0xdd, 0x24, 0x5a, 0x91, 0x90, 0xb8, 0x1c, 0x4c, 0x53, 0xc5, 0x05, 0x9a, 0x02, 0xd2, 0x2e, 0x23,
	0xd7, 0x76, 0x86, 0xd5, 0xd8, 0x8e, 0x1c, 0xa7, 0x1d, 0x0f, 0xc2, 0x53, 0xf0, 0x92, 0x28, 0x8e,
	0x93, 0x16, 0x6d, 0xea, 0x9d, 0xf3, 0x3f, 0xbf, 0xf3, 0x3f, 0x5f, 0x0a, 0x5c, 0x72, 0x99, 0x68,
	0x1c, 0x1a, 0xcd, 0x09, 0x2f, 0x44, 0x88, 0x33, 0x1e, 0x62, 0x2a, 0xb8, 0x0c, 0x37, 0x57, 0xe1,
	0x56, 0xe9, 0x75, 0x92, 0xaa, 0x6d, 0x90, 0x69, 0x65, 0x14, 0xea, 0xda, 0xc0, 0xec, 0xdd, 0xd3,
	0x8c, 0xcd, 0x55, 0x48, 0xb1, 0xc1, 0x15, 0x37, 0x7b, 0xff, 0x2c, 0x90, 0x14, 0x92, 0x18, 0xae,
	0xe4, 0x41, 0x28, 0x4b, 0xb1, 0x49, 0x94, 0x16, 0x15, 0x74, 0xfe, 0xe7, 0x18, 0xfa, 0xf7, 0xae,
	0x09, 0x74, 0x01, 0xd3, 0x9c, 0xe9, 0x0d, 0x27, 0x2c, 0xc6, 0x84, 0xa8, 0x42, 0x1a, 0xaf, 0x35,
	0x6f, 0xf9, 0x83, 0x68, 0xe2, 0xe4, 0xeb, 0x4a, 0x45, 0x17, 0x70, 0x52, 0x76, 0xce, 0x74, 0xee,
	0x1d, 0xcf, 0xdb, 0xfe, 0x70, 0x31, 0x0e, 0x6c, 0xe7, 0xc1, 0xbd, 0x55, 0xa3, 0x3a, 0x6a, 0x1d,
	0xb7, 0x58, 0x0b, 0x2e, 0x1f, 0xe2, 0xd2, 0x83, 0x69, 0xaf, 0xed, 0x1c, 0x9d, 0xfc, 0xc3, 0xaa,
	0xe8, 0x03, 0x4c, 0x78, 0xae, 0x52, 0x6c, 0x58, 0xcd, 0x75, 0x2c, 0x37, 0x76, 0xaa, 0xc3, 0x42,
	0x18, 0xd4, 0x53, 0xe6, 0x5e, 0xd7, 0x96, 0x7e, 0x11, 0xb8, 0x09, 0x83, 0x5b, 0x17, 0x89, 0x76,
	0x0c, 0xfa, 0x04, 0x6f, 0x56, 0x05, 0x4f, 0xe9, 0xaa, 0x20, 0x6b, 0x66, 0x9c, 0x77, 0xfc, 0x4b,
	0xe5, 0xc6, 0xeb, 0xd9, 0x02, 0x67, 0x7b, 0xe1, 0xaa, 0xc8, 0x52, 0xe5, 0xe6, 0xfc, 0x6f, 0x07,
	0x7a, 0xd5, 0x30, 0x08, 0x41, 0x47, 0x62, 0xc1, 0xdc, 0x2a, 0xec, 0x1b, 0xf9, 0xd0, 0x95, 0x8c,
	0xd1, 0x72, 0xfc, 0x96, 0x3f, 0x59, 0xa0, 0xa6, 0x87, 0x9b, 0xf2, 0x48, 0x3f, 0x7f, 0x67, 0x2c,
	0xaa, 0x00, 0x74, 0x03, 0xc8, 0x3e, 0xe2, 0x44, 0xe9, 0xb8, 0x5e, 0xbe, 0x5d, 0xc2, 0x64, 0xf1,
	0xba, 0x49, 0xbb, 0xab, 0xaf, 0xf2, 0x1d, 0x0b, 0x16, 0x9d, 0xda, 0x8c, 0x5b, 0xa5, 0x6b, 0x19,
	0x05, 0xd0, 0xcf, 0xb4, 0xda, 0x70, 0xca, 0x72, 0xbb, 0x98, 0xe7, 0x4b, 0x36, 0x0c, 0xfa, 0x06,
	0x67, 0xf5, 0xfb, 0xff, 0xc2, 0xdd, 0x83, 0x85, 0x5f, 0xd6, 0x49, 0xfb, 0xb5, 0xcb, 0xf9, 0xd9,
	0x63, 0xb9, 0xaf, 0xb6, 0x9d, 0x9f, 0x3d, 0x1a, 0x74, 0x0d, 0xa7, 0xba, 0x90, 0x86, 0x0b, 0xb6,
	0xb3, 0x3e, 0x39, 0x68, 0x3d, 0x75, 0x7c, 0x63, 0xfb, 0x16, 0x80, 0x72, 0xc1, 0x64, 0x6e, 0x6f,
	0xd9, 0xb7, 0xe6, 0x7b, 0x0a, 0xfa, 0x0c, 0x63, 0xc2, 0x33, 0x1a, 0x67, 0x98, 0xac, 0xf1, 0x03,
	0xcb, 0xbd, 0x81, 0x3d, 0xf7, 0xab, 0xc6, 0xff, 0x2b, 0xcf, 0xe8, 0x5d, 0x15, 0x8c, 0x46, 0x64,
	0xf7, 0x91, 0xa3, 0x39, 0xb4, 0x89, 0xa0, 0x1e, 0xcc, 0x5b, 0xfe, 0x70, 0x31, 0xda, 0x25, 0x08,
	0xba, 0x3c, 0x8a, 0xca, 0x10, 0xba, 0x84, 0x9e, 0x66, 0x84, 0x67, 0xcc, 0x1b, 0x59, 0x68, 0xda,
	0x40, 0x91, 0x95, 0x97, 0x47, 0x91, 0x03, 0xd0, 0x0c, 0xfa, 0x94, 0x61, 0x9a, 0x72, 0xc9, 0xbc,
	0xe1, 0xbc, 0xe5, 0x77, 0xa3, 0xe6, 0xfb, 0x4b, 0x0f, 0x3a, 0x5c, 0x64, 0xe9, 0xaa, 0x67, 0x7f,
	0xa6, 0x8f, 0xff, 0x02, 0x00, 0x00, 0xff, 0xff, 0xb6, 0x41, 0x52, 0x45, 0xeb, 0x03, 0x00, 0x00,
}