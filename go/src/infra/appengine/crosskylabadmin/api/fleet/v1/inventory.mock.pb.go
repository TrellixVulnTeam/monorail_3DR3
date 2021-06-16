// Code generated by MockGen. DO NOT EDIT.
// Source: inventory.pb.go

// Package fleet is a generated GoMock package.
package fleet

import (
	context "context"
	gomock "github.com/golang/mock/gomock"
	grpc "google.golang.org/grpc"
	reflect "reflect"
)

// MockInventoryClient is a mock of InventoryClient interface.
type MockInventoryClient struct {
	ctrl     *gomock.Controller
	recorder *MockInventoryClientMockRecorder
}

// MockInventoryClientMockRecorder is the mock recorder for MockInventoryClient.
type MockInventoryClientMockRecorder struct {
	mock *MockInventoryClient
}

// NewMockInventoryClient creates a new mock instance.
func NewMockInventoryClient(ctrl *gomock.Controller) *MockInventoryClient {
	mock := &MockInventoryClient{ctrl: ctrl}
	mock.recorder = &MockInventoryClientMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *MockInventoryClient) EXPECT() *MockInventoryClientMockRecorder {
	return m.recorder
}

// DeployDut mocks base method.
func (m *MockInventoryClient) DeployDut(ctx context.Context, in *DeployDutRequest, opts ...grpc.CallOption) (*DeployDutResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "DeployDut", varargs...)
	ret0, _ := ret[0].(*DeployDutResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// DeployDut indicates an expected call of DeployDut.
func (mr *MockInventoryClientMockRecorder) DeployDut(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "DeployDut", reflect.TypeOf((*MockInventoryClient)(nil).DeployDut), varargs...)
}

// RedeployDut mocks base method.
func (m *MockInventoryClient) RedeployDut(ctx context.Context, in *RedeployDutRequest, opts ...grpc.CallOption) (*RedeployDutResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "RedeployDut", varargs...)
	ret0, _ := ret[0].(*RedeployDutResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// RedeployDut indicates an expected call of RedeployDut.
func (mr *MockInventoryClientMockRecorder) RedeployDut(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "RedeployDut", reflect.TypeOf((*MockInventoryClient)(nil).RedeployDut), varargs...)
}

// GetDeploymentStatus mocks base method.
func (m *MockInventoryClient) GetDeploymentStatus(ctx context.Context, in *GetDeploymentStatusRequest, opts ...grpc.CallOption) (*GetDeploymentStatusResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "GetDeploymentStatus", varargs...)
	ret0, _ := ret[0].(*GetDeploymentStatusResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetDeploymentStatus indicates an expected call of GetDeploymentStatus.
func (mr *MockInventoryClientMockRecorder) GetDeploymentStatus(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetDeploymentStatus", reflect.TypeOf((*MockInventoryClient)(nil).GetDeploymentStatus), varargs...)
}

// DeleteDuts mocks base method.
func (m *MockInventoryClient) DeleteDuts(ctx context.Context, in *DeleteDutsRequest, opts ...grpc.CallOption) (*DeleteDutsResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "DeleteDuts", varargs...)
	ret0, _ := ret[0].(*DeleteDutsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// DeleteDuts indicates an expected call of DeleteDuts.
func (mr *MockInventoryClientMockRecorder) DeleteDuts(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "DeleteDuts", reflect.TypeOf((*MockInventoryClient)(nil).DeleteDuts), varargs...)
}

// BalancePools mocks base method.
func (m *MockInventoryClient) BalancePools(ctx context.Context, in *BalancePoolsRequest, opts ...grpc.CallOption) (*BalancePoolsResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "BalancePools", varargs...)
	ret0, _ := ret[0].(*BalancePoolsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// BalancePools indicates an expected call of BalancePools.
func (mr *MockInventoryClientMockRecorder) BalancePools(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "BalancePools", reflect.TypeOf((*MockInventoryClient)(nil).BalancePools), varargs...)
}

// ResizePool mocks base method.
func (m *MockInventoryClient) ResizePool(ctx context.Context, in *ResizePoolRequest, opts ...grpc.CallOption) (*ResizePoolResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "ResizePool", varargs...)
	ret0, _ := ret[0].(*ResizePoolResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ResizePool indicates an expected call of ResizePool.
func (mr *MockInventoryClientMockRecorder) ResizePool(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ResizePool", reflect.TypeOf((*MockInventoryClient)(nil).ResizePool), varargs...)
}

// RemoveDutsFromDrones mocks base method.
func (m *MockInventoryClient) RemoveDutsFromDrones(ctx context.Context, in *RemoveDutsFromDronesRequest, opts ...grpc.CallOption) (*RemoveDutsFromDronesResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "RemoveDutsFromDrones", varargs...)
	ret0, _ := ret[0].(*RemoveDutsFromDronesResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// RemoveDutsFromDrones indicates an expected call of RemoveDutsFromDrones.
func (mr *MockInventoryClientMockRecorder) RemoveDutsFromDrones(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "RemoveDutsFromDrones", reflect.TypeOf((*MockInventoryClient)(nil).RemoveDutsFromDrones), varargs...)
}

// AssignDutsToDrones mocks base method.
func (m *MockInventoryClient) AssignDutsToDrones(ctx context.Context, in *AssignDutsToDronesRequest, opts ...grpc.CallOption) (*AssignDutsToDronesResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "AssignDutsToDrones", varargs...)
	ret0, _ := ret[0].(*AssignDutsToDronesResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// AssignDutsToDrones indicates an expected call of AssignDutsToDrones.
func (mr *MockInventoryClientMockRecorder) AssignDutsToDrones(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "AssignDutsToDrones", reflect.TypeOf((*MockInventoryClient)(nil).AssignDutsToDrones), varargs...)
}

// ListServers mocks base method.
func (m *MockInventoryClient) ListServers(ctx context.Context, in *ListServersRequest, opts ...grpc.CallOption) (*ListServersResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "ListServers", varargs...)
	ret0, _ := ret[0].(*ListServersResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ListServers indicates an expected call of ListServers.
func (mr *MockInventoryClientMockRecorder) ListServers(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ListServers", reflect.TypeOf((*MockInventoryClient)(nil).ListServers), varargs...)
}

// GetDutInfo mocks base method.
func (m *MockInventoryClient) GetDutInfo(ctx context.Context, in *GetDutInfoRequest, opts ...grpc.CallOption) (*GetDutInfoResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "GetDutInfo", varargs...)
	ret0, _ := ret[0].(*GetDutInfoResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetDutInfo indicates an expected call of GetDutInfo.
func (mr *MockInventoryClientMockRecorder) GetDutInfo(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetDutInfo", reflect.TypeOf((*MockInventoryClient)(nil).GetDutInfo), varargs...)
}

// GetDroneConfig mocks base method.
func (m *MockInventoryClient) GetDroneConfig(ctx context.Context, in *GetDroneConfigRequest, opts ...grpc.CallOption) (*GetDroneConfigResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "GetDroneConfig", varargs...)
	ret0, _ := ret[0].(*GetDroneConfigResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetDroneConfig indicates an expected call of GetDroneConfig.
func (mr *MockInventoryClientMockRecorder) GetDroneConfig(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetDroneConfig", reflect.TypeOf((*MockInventoryClient)(nil).GetDroneConfig), varargs...)
}

// ListRemovedDuts mocks base method.
func (m *MockInventoryClient) ListRemovedDuts(ctx context.Context, in *ListRemovedDutsRequest, opts ...grpc.CallOption) (*ListRemovedDutsResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "ListRemovedDuts", varargs...)
	ret0, _ := ret[0].(*ListRemovedDutsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ListRemovedDuts indicates an expected call of ListRemovedDuts.
func (mr *MockInventoryClientMockRecorder) ListRemovedDuts(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ListRemovedDuts", reflect.TypeOf((*MockInventoryClient)(nil).ListRemovedDuts), varargs...)
}

// PushInventoryToQueen mocks base method.
func (m *MockInventoryClient) PushInventoryToQueen(ctx context.Context, in *PushInventoryToQueenRequest, opts ...grpc.CallOption) (*PushInventoryToQueenResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "PushInventoryToQueen", varargs...)
	ret0, _ := ret[0].(*PushInventoryToQueenResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// PushInventoryToQueen indicates an expected call of PushInventoryToQueen.
func (mr *MockInventoryClientMockRecorder) PushInventoryToQueen(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "PushInventoryToQueen", reflect.TypeOf((*MockInventoryClient)(nil).PushInventoryToQueen), varargs...)
}

// UpdateDutLabels mocks base method.
func (m *MockInventoryClient) UpdateDutLabels(ctx context.Context, in *UpdateDutLabelsRequest, opts ...grpc.CallOption) (*UpdateDutLabelsResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "UpdateDutLabels", varargs...)
	ret0, _ := ret[0].(*UpdateDutLabelsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateDutLabels indicates an expected call of UpdateDutLabels.
func (mr *MockInventoryClientMockRecorder) UpdateDutLabels(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateDutLabels", reflect.TypeOf((*MockInventoryClient)(nil).UpdateDutLabels), varargs...)
}

// BatchUpdateDuts mocks base method.
func (m *MockInventoryClient) BatchUpdateDuts(ctx context.Context, in *BatchUpdateDutsRequest, opts ...grpc.CallOption) (*BatchUpdateDutsResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "BatchUpdateDuts", varargs...)
	ret0, _ := ret[0].(*BatchUpdateDutsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// BatchUpdateDuts indicates an expected call of BatchUpdateDuts.
func (mr *MockInventoryClientMockRecorder) BatchUpdateDuts(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "BatchUpdateDuts", reflect.TypeOf((*MockInventoryClient)(nil).BatchUpdateDuts), varargs...)
}

// UpdateCachedInventory mocks base method.
func (m *MockInventoryClient) UpdateCachedInventory(ctx context.Context, in *UpdateCachedInventoryRequest, opts ...grpc.CallOption) (*UpdateCachedInventoryResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "UpdateCachedInventory", varargs...)
	ret0, _ := ret[0].(*UpdateCachedInventoryResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateCachedInventory indicates an expected call of UpdateCachedInventory.
func (mr *MockInventoryClientMockRecorder) UpdateCachedInventory(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateCachedInventory", reflect.TypeOf((*MockInventoryClient)(nil).UpdateCachedInventory), varargs...)
}

// UpdateDeviceConfig mocks base method.
func (m *MockInventoryClient) UpdateDeviceConfig(ctx context.Context, in *UpdateDeviceConfigRequest, opts ...grpc.CallOption) (*UpdateDeviceConfigResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "UpdateDeviceConfig", varargs...)
	ret0, _ := ret[0].(*UpdateDeviceConfigResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateDeviceConfig indicates an expected call of UpdateDeviceConfig.
func (mr *MockInventoryClientMockRecorder) UpdateDeviceConfig(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateDeviceConfig", reflect.TypeOf((*MockInventoryClient)(nil).UpdateDeviceConfig), varargs...)
}

// GetStableVersion mocks base method.
func (m *MockInventoryClient) GetStableVersion(ctx context.Context, in *GetStableVersionRequest, opts ...grpc.CallOption) (*GetStableVersionResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "GetStableVersion", varargs...)
	ret0, _ := ret[0].(*GetStableVersionResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetStableVersion indicates an expected call of GetStableVersion.
func (mr *MockInventoryClientMockRecorder) GetStableVersion(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetStableVersion", reflect.TypeOf((*MockInventoryClient)(nil).GetStableVersion), varargs...)
}

// DumpStableVersionToDatastore mocks base method.
func (m *MockInventoryClient) DumpStableVersionToDatastore(ctx context.Context, in *DumpStableVersionToDatastoreRequest, opts ...grpc.CallOption) (*DumpStableVersionToDatastoreResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "DumpStableVersionToDatastore", varargs...)
	ret0, _ := ret[0].(*DumpStableVersionToDatastoreResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// DumpStableVersionToDatastore indicates an expected call of DumpStableVersionToDatastore.
func (mr *MockInventoryClientMockRecorder) DumpStableVersionToDatastore(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "DumpStableVersionToDatastore", reflect.TypeOf((*MockInventoryClient)(nil).DumpStableVersionToDatastore), varargs...)
}

// ReportInventory mocks base method.
func (m *MockInventoryClient) ReportInventory(ctx context.Context, in *ReportInventoryRequest, opts ...grpc.CallOption) (*ReportInventoryResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "ReportInventory", varargs...)
	ret0, _ := ret[0].(*ReportInventoryResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ReportInventory indicates an expected call of ReportInventory.
func (mr *MockInventoryClientMockRecorder) ReportInventory(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ReportInventory", reflect.TypeOf((*MockInventoryClient)(nil).ReportInventory), varargs...)
}

// UpdateManufacturingConfig mocks base method.
func (m *MockInventoryClient) UpdateManufacturingConfig(ctx context.Context, in *UpdateManufacturingConfigRequest, opts ...grpc.CallOption) (*UpdateManufacturingConfigResponse, error) {
	m.ctrl.T.Helper()
	varargs := []interface{}{ctx, in}
	for _, a := range opts {
		varargs = append(varargs, a)
	}
	ret := m.ctrl.Call(m, "UpdateManufacturingConfig", varargs...)
	ret0, _ := ret[0].(*UpdateManufacturingConfigResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateManufacturingConfig indicates an expected call of UpdateManufacturingConfig.
func (mr *MockInventoryClientMockRecorder) UpdateManufacturingConfig(ctx, in interface{}, opts ...interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	varargs := append([]interface{}{ctx, in}, opts...)
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateManufacturingConfig", reflect.TypeOf((*MockInventoryClient)(nil).UpdateManufacturingConfig), varargs...)
}

// MockInventoryServer is a mock of InventoryServer interface.
type MockInventoryServer struct {
	ctrl     *gomock.Controller
	recorder *MockInventoryServerMockRecorder
}

// MockInventoryServerMockRecorder is the mock recorder for MockInventoryServer.
type MockInventoryServerMockRecorder struct {
	mock *MockInventoryServer
}

// NewMockInventoryServer creates a new mock instance.
func NewMockInventoryServer(ctrl *gomock.Controller) *MockInventoryServer {
	mock := &MockInventoryServer{ctrl: ctrl}
	mock.recorder = &MockInventoryServerMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *MockInventoryServer) EXPECT() *MockInventoryServerMockRecorder {
	return m.recorder
}

// DeployDut mocks base method.
func (m *MockInventoryServer) DeployDut(arg0 context.Context, arg1 *DeployDutRequest) (*DeployDutResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "DeployDut", arg0, arg1)
	ret0, _ := ret[0].(*DeployDutResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// DeployDut indicates an expected call of DeployDut.
func (mr *MockInventoryServerMockRecorder) DeployDut(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "DeployDut", reflect.TypeOf((*MockInventoryServer)(nil).DeployDut), arg0, arg1)
}

// RedeployDut mocks base method.
func (m *MockInventoryServer) RedeployDut(arg0 context.Context, arg1 *RedeployDutRequest) (*RedeployDutResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "RedeployDut", arg0, arg1)
	ret0, _ := ret[0].(*RedeployDutResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// RedeployDut indicates an expected call of RedeployDut.
func (mr *MockInventoryServerMockRecorder) RedeployDut(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "RedeployDut", reflect.TypeOf((*MockInventoryServer)(nil).RedeployDut), arg0, arg1)
}

// GetDeploymentStatus mocks base method.
func (m *MockInventoryServer) GetDeploymentStatus(arg0 context.Context, arg1 *GetDeploymentStatusRequest) (*GetDeploymentStatusResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "GetDeploymentStatus", arg0, arg1)
	ret0, _ := ret[0].(*GetDeploymentStatusResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetDeploymentStatus indicates an expected call of GetDeploymentStatus.
func (mr *MockInventoryServerMockRecorder) GetDeploymentStatus(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetDeploymentStatus", reflect.TypeOf((*MockInventoryServer)(nil).GetDeploymentStatus), arg0, arg1)
}

// DeleteDuts mocks base method.
func (m *MockInventoryServer) DeleteDuts(arg0 context.Context, arg1 *DeleteDutsRequest) (*DeleteDutsResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "DeleteDuts", arg0, arg1)
	ret0, _ := ret[0].(*DeleteDutsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// DeleteDuts indicates an expected call of DeleteDuts.
func (mr *MockInventoryServerMockRecorder) DeleteDuts(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "DeleteDuts", reflect.TypeOf((*MockInventoryServer)(nil).DeleteDuts), arg0, arg1)
}

// BalancePools mocks base method.
func (m *MockInventoryServer) BalancePools(arg0 context.Context, arg1 *BalancePoolsRequest) (*BalancePoolsResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "BalancePools", arg0, arg1)
	ret0, _ := ret[0].(*BalancePoolsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// BalancePools indicates an expected call of BalancePools.
func (mr *MockInventoryServerMockRecorder) BalancePools(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "BalancePools", reflect.TypeOf((*MockInventoryServer)(nil).BalancePools), arg0, arg1)
}

// ResizePool mocks base method.
func (m *MockInventoryServer) ResizePool(arg0 context.Context, arg1 *ResizePoolRequest) (*ResizePoolResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "ResizePool", arg0, arg1)
	ret0, _ := ret[0].(*ResizePoolResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ResizePool indicates an expected call of ResizePool.
func (mr *MockInventoryServerMockRecorder) ResizePool(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ResizePool", reflect.TypeOf((*MockInventoryServer)(nil).ResizePool), arg0, arg1)
}

// RemoveDutsFromDrones mocks base method.
func (m *MockInventoryServer) RemoveDutsFromDrones(arg0 context.Context, arg1 *RemoveDutsFromDronesRequest) (*RemoveDutsFromDronesResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "RemoveDutsFromDrones", arg0, arg1)
	ret0, _ := ret[0].(*RemoveDutsFromDronesResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// RemoveDutsFromDrones indicates an expected call of RemoveDutsFromDrones.
func (mr *MockInventoryServerMockRecorder) RemoveDutsFromDrones(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "RemoveDutsFromDrones", reflect.TypeOf((*MockInventoryServer)(nil).RemoveDutsFromDrones), arg0, arg1)
}

// AssignDutsToDrones mocks base method.
func (m *MockInventoryServer) AssignDutsToDrones(arg0 context.Context, arg1 *AssignDutsToDronesRequest) (*AssignDutsToDronesResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "AssignDutsToDrones", arg0, arg1)
	ret0, _ := ret[0].(*AssignDutsToDronesResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// AssignDutsToDrones indicates an expected call of AssignDutsToDrones.
func (mr *MockInventoryServerMockRecorder) AssignDutsToDrones(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "AssignDutsToDrones", reflect.TypeOf((*MockInventoryServer)(nil).AssignDutsToDrones), arg0, arg1)
}

// ListServers mocks base method.
func (m *MockInventoryServer) ListServers(arg0 context.Context, arg1 *ListServersRequest) (*ListServersResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "ListServers", arg0, arg1)
	ret0, _ := ret[0].(*ListServersResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ListServers indicates an expected call of ListServers.
func (mr *MockInventoryServerMockRecorder) ListServers(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ListServers", reflect.TypeOf((*MockInventoryServer)(nil).ListServers), arg0, arg1)
}

// GetDutInfo mocks base method.
func (m *MockInventoryServer) GetDutInfo(arg0 context.Context, arg1 *GetDutInfoRequest) (*GetDutInfoResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "GetDutInfo", arg0, arg1)
	ret0, _ := ret[0].(*GetDutInfoResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetDutInfo indicates an expected call of GetDutInfo.
func (mr *MockInventoryServerMockRecorder) GetDutInfo(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetDutInfo", reflect.TypeOf((*MockInventoryServer)(nil).GetDutInfo), arg0, arg1)
}

// GetDroneConfig mocks base method.
func (m *MockInventoryServer) GetDroneConfig(arg0 context.Context, arg1 *GetDroneConfigRequest) (*GetDroneConfigResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "GetDroneConfig", arg0, arg1)
	ret0, _ := ret[0].(*GetDroneConfigResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetDroneConfig indicates an expected call of GetDroneConfig.
func (mr *MockInventoryServerMockRecorder) GetDroneConfig(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetDroneConfig", reflect.TypeOf((*MockInventoryServer)(nil).GetDroneConfig), arg0, arg1)
}

// ListRemovedDuts mocks base method.
func (m *MockInventoryServer) ListRemovedDuts(arg0 context.Context, arg1 *ListRemovedDutsRequest) (*ListRemovedDutsResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "ListRemovedDuts", arg0, arg1)
	ret0, _ := ret[0].(*ListRemovedDutsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ListRemovedDuts indicates an expected call of ListRemovedDuts.
func (mr *MockInventoryServerMockRecorder) ListRemovedDuts(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ListRemovedDuts", reflect.TypeOf((*MockInventoryServer)(nil).ListRemovedDuts), arg0, arg1)
}

// PushInventoryToQueen mocks base method.
func (m *MockInventoryServer) PushInventoryToQueen(arg0 context.Context, arg1 *PushInventoryToQueenRequest) (*PushInventoryToQueenResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "PushInventoryToQueen", arg0, arg1)
	ret0, _ := ret[0].(*PushInventoryToQueenResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// PushInventoryToQueen indicates an expected call of PushInventoryToQueen.
func (mr *MockInventoryServerMockRecorder) PushInventoryToQueen(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "PushInventoryToQueen", reflect.TypeOf((*MockInventoryServer)(nil).PushInventoryToQueen), arg0, arg1)
}

// UpdateDutLabels mocks base method.
func (m *MockInventoryServer) UpdateDutLabels(arg0 context.Context, arg1 *UpdateDutLabelsRequest) (*UpdateDutLabelsResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "UpdateDutLabels", arg0, arg1)
	ret0, _ := ret[0].(*UpdateDutLabelsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateDutLabels indicates an expected call of UpdateDutLabels.
func (mr *MockInventoryServerMockRecorder) UpdateDutLabels(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateDutLabels", reflect.TypeOf((*MockInventoryServer)(nil).UpdateDutLabels), arg0, arg1)
}

// BatchUpdateDuts mocks base method.
func (m *MockInventoryServer) BatchUpdateDuts(arg0 context.Context, arg1 *BatchUpdateDutsRequest) (*BatchUpdateDutsResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "BatchUpdateDuts", arg0, arg1)
	ret0, _ := ret[0].(*BatchUpdateDutsResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// BatchUpdateDuts indicates an expected call of BatchUpdateDuts.
func (mr *MockInventoryServerMockRecorder) BatchUpdateDuts(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "BatchUpdateDuts", reflect.TypeOf((*MockInventoryServer)(nil).BatchUpdateDuts), arg0, arg1)
}

// UpdateCachedInventory mocks base method.
func (m *MockInventoryServer) UpdateCachedInventory(arg0 context.Context, arg1 *UpdateCachedInventoryRequest) (*UpdateCachedInventoryResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "UpdateCachedInventory", arg0, arg1)
	ret0, _ := ret[0].(*UpdateCachedInventoryResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateCachedInventory indicates an expected call of UpdateCachedInventory.
func (mr *MockInventoryServerMockRecorder) UpdateCachedInventory(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateCachedInventory", reflect.TypeOf((*MockInventoryServer)(nil).UpdateCachedInventory), arg0, arg1)
}

// UpdateDeviceConfig mocks base method.
func (m *MockInventoryServer) UpdateDeviceConfig(arg0 context.Context, arg1 *UpdateDeviceConfigRequest) (*UpdateDeviceConfigResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "UpdateDeviceConfig", arg0, arg1)
	ret0, _ := ret[0].(*UpdateDeviceConfigResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateDeviceConfig indicates an expected call of UpdateDeviceConfig.
func (mr *MockInventoryServerMockRecorder) UpdateDeviceConfig(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateDeviceConfig", reflect.TypeOf((*MockInventoryServer)(nil).UpdateDeviceConfig), arg0, arg1)
}

// GetStableVersion mocks base method.
func (m *MockInventoryServer) GetStableVersion(arg0 context.Context, arg1 *GetStableVersionRequest) (*GetStableVersionResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "GetStableVersion", arg0, arg1)
	ret0, _ := ret[0].(*GetStableVersionResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// GetStableVersion indicates an expected call of GetStableVersion.
func (mr *MockInventoryServerMockRecorder) GetStableVersion(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "GetStableVersion", reflect.TypeOf((*MockInventoryServer)(nil).GetStableVersion), arg0, arg1)
}

// DumpStableVersionToDatastore mocks base method.
func (m *MockInventoryServer) DumpStableVersionToDatastore(arg0 context.Context, arg1 *DumpStableVersionToDatastoreRequest) (*DumpStableVersionToDatastoreResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "DumpStableVersionToDatastore", arg0, arg1)
	ret0, _ := ret[0].(*DumpStableVersionToDatastoreResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// DumpStableVersionToDatastore indicates an expected call of DumpStableVersionToDatastore.
func (mr *MockInventoryServerMockRecorder) DumpStableVersionToDatastore(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "DumpStableVersionToDatastore", reflect.TypeOf((*MockInventoryServer)(nil).DumpStableVersionToDatastore), arg0, arg1)
}

// ReportInventory mocks base method.
func (m *MockInventoryServer) ReportInventory(arg0 context.Context, arg1 *ReportInventoryRequest) (*ReportInventoryResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "ReportInventory", arg0, arg1)
	ret0, _ := ret[0].(*ReportInventoryResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ReportInventory indicates an expected call of ReportInventory.
func (mr *MockInventoryServerMockRecorder) ReportInventory(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ReportInventory", reflect.TypeOf((*MockInventoryServer)(nil).ReportInventory), arg0, arg1)
}

// UpdateManufacturingConfig mocks base method.
func (m *MockInventoryServer) UpdateManufacturingConfig(arg0 context.Context, arg1 *UpdateManufacturingConfigRequest) (*UpdateManufacturingConfigResponse, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "UpdateManufacturingConfig", arg0, arg1)
	ret0, _ := ret[0].(*UpdateManufacturingConfigResponse)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// UpdateManufacturingConfig indicates an expected call of UpdateManufacturingConfig.
func (mr *MockInventoryServerMockRecorder) UpdateManufacturingConfig(arg0, arg1 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UpdateManufacturingConfig", reflect.TypeOf((*MockInventoryServer)(nil).UpdateManufacturingConfig), arg0, arg1)
}