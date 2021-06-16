// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package backend

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"
	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/tq"
	"go.chromium.org/luci/appengine/tq/tqtesting"
	"go.chromium.org/luci/common/clock/testclock"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
	"infra/appengine/rotang/proto/rotangapi"
	"infra/appengine/rotation-proxy/proto"
	"infra/monorailv2/api/api_proto"
)

var (
	testStart, _    = ptypes.TimestampProto(testclock.TestRecentTimeUTC)
	testEnd, _      = ptypes.TimestampProto(testclock.TestRecentTimeUTC)
	yesterday, _    = ptypes.TimestampProto(time.Now().AddDate(0, 0, -1))
	tomorrow, _     = ptypes.TimestampProto(time.Now().AddDate(0, 0, 1))
	dayAfterNext, _ = ptypes.TimestampProto(time.Now().AddDate(0, 0, 2))

	// sample output from RotaNG.
	sampleOncallShifts = map[string]*rotangapi.ShiftEntry{
		"Rotation 1": {
			Start: testStart,
			End:   testEnd,
			Oncallers: []*rotangapi.OnCaller{
				{Email: "r1pri@example.com"},
				{Email: "r1sec1@example.com"},
				{Email: "r1sec2@example.com"},
			},
		},
		"Rotation 2": {
			Start: testStart,
			End:   testEnd,
			Oncallers: []*rotangapi.OnCaller{
				{Email: "r2pri@example.com"},
				{Email: "r2sec1@example.com"},
				{Email: "r2sec2@example.com"},
			},
		},
		"Rotation 3": {
			Start: testStart,
			End:   testEnd,
			Oncallers: []*rotangapi.OnCaller{
				{Email: "r3pri@example.com"},
				{Email: "r3sec1@example.com"},
				{Email: "r3sec2@example.com"},
			},
		},
	}

	// sample output from rotation-proxy.
	sampleRotationProxyRotations = map[string]*rotationproxy.Rotation{
		"Rotation 1": {
			Name: "Rotation 1",
			Shifts: []*rotationproxy.Shift{
				{
					Oncalls: []*rotationproxy.OncallPerson{
						{Email: "r1pri@example.com"},
						{Email: "r1sec1@example.com"},
						{Email: "r1sec2@example.com"},
					},
					StartTime: yesterday,
					EndTime:   tomorrow,
				},
			},
		},
		"Rotation 2": {
			Name: "Rotation 2",
			Shifts: []*rotationproxy.Shift{
				{
					Oncalls: []*rotationproxy.OncallPerson{
						{Email: "r2pri@example.com"},
						{Email: "r2sec1@example.com"},
						{Email: "r2sec2@example.com"},
					},
					StartTime: yesterday,
				},
			},
		},
		"Rotation 3": {
			Name: "Rotation 3",
			Shifts: []*rotationproxy.Shift{
				{
					Oncalls: []*rotationproxy.OncallPerson{
						{Email: "r3pri@example.com"},
						{Email: "r3sec1@example.com"},
						{Email: "r3sec2@example.com"},
					},
					StartTime: tomorrow,
					EndTime:   dayAfterNext,
				},
			},
		},
	}
)

// createTestContextWithTQ creates a test context with testable a TaskQueue.
func createTestContextWithTQ() context.Context {
	// create a context with config first.
	c := util.CreateTestContext()
	c = config.SetConfig(c, &config.Config{
		AccessGroup:      "engineers",
		MonorailHostname: "example.org",
		RotangHostname:   "example.net",

		Assigners: []*config.Assigner{},
	})

	// install TQ handlers
	d := &tq.Dispatcher{}
	registerTaskHandlers(d)
	tq := tqtesting.GetTestable(c, d)
	tq.CreateQueues()
	c = util.SetDispatcher(c, d)

	// install mocked pRPC clients.
	c = setMonorailClient(c, newTestIssueClient())
	c = setRotaNGClient(c, newTestOncallInfoClient())
	c = setRotationProxyClient(c, newTestRotationProxyServiceClient())

	// set sample rotation shifts for Rota-NG
	for rotation, shift := range sampleOncallShifts {
		mockOncall(c, rotation, shift)
	}

	// set sample rotation shifts for rotation-proxy
	for name, rotation := range sampleRotationProxyRotations {
		mockRotation(c, name, rotation)
	}
	return c
}

// createAssigner creates a sample Assigner entity.
func createAssigner(c context.Context, id string) *model.Assigner {
	var cfg config.Assigner
	So(proto.UnmarshalText(util.SampleValidAssignerCfg, &cfg), ShouldBeNil)
	cfg.Id = id

	So(UpdateAssigners(c, []*config.Assigner{&cfg}, "rev-1"), ShouldBeNil)
	datastore.GetTestable(c).CatchupIndexes()
	assigner, err := GetAssigner(c, id)
	So(assigner.ID, ShouldEqual, id)
	So(err, ShouldBeNil)
	So(assigner, ShouldNotBeNil)

	return assigner
}

func triggerScheduleTaskHandler(c context.Context, id string) []*model.Task {
	req := &ScheduleAssignerTask{AssignerId: id}
	So(scheduleAssignerTaskHandler(c, req), ShouldBeNil)
	_, tasks, err := GetAssignerWithTasks(c, id, 99999, true)
	So(err, ShouldBeNil)
	return tasks
}

func triggerRunTaskHandler(c context.Context, assignerID string, taskID int64) *model.Task {
	req := &RunAssignerTask{AssignerId: assignerID, TaskId: taskID}
	So(runAssignerTaskHandler(c, req), ShouldBeNil)
	assigner, task, err := GetTask(c, assignerID, taskID)
	So(assigner.ID, ShouldEqual, assignerID)
	So(err, ShouldBeNil)
	So(task, ShouldNotBeNil)
	return task
}

func createRawUserSources(sources ...*config.UserSource) [][]byte {
	raw := make([][]byte, len(sources))
	for i, source := range sources {
		raw[i], _ = proto.Marshal(source)
	}
	return raw
}

func monorailUser(email string) *monorail.UserRef {
	return &monorail.UserRef{DisplayName: email}
}

func emailUserSource(email string) *config.UserSource {
	return &config.UserSource{From: &config.UserSource_Email{Email: email}}
}

func oncallUserSource(rotation string, position config.Oncall_Position) *config.UserSource {
	return &config.UserSource{
		From: &config.UserSource_Oncall{Oncall: &config.Oncall{
			Rotation: rotation, Position: position,
		}},
	}
}

func rotationUserSource(rotation string, position config.Oncall_Position) *config.UserSource {
	return &config.UserSource{
		From: &config.UserSource_Rotation{Rotation: &config.Oncall{
			Rotation: rotation, Position: position,
		}},
	}
}

func findPrimaryOncall(shift *rotangapi.ShiftEntry) *monorail.UserRef {
	if len(shift.Oncallers) == 0 {
		return nil
	}
	return monorailUser(shift.Oncallers[0].Email)
}

func findSecondaryOncalls(shift *rotangapi.ShiftEntry) []*monorail.UserRef {
	var oncalls []*monorail.UserRef
	if len(shift.Oncallers) < 2 {
		return oncalls
	}
	for _, oc := range shift.Oncallers[1:] {
		oncalls = append(oncalls, monorailUser(oc.Email))
	}
	return oncalls
}

// ----------------------------------
// test Monorail Issue Client

type testIssueClientStorage struct {
	listIssuesRequest  *monorail.ListIssuesRequest
	listIssuesResponse []*monorail.Issue
	getIssueResponse   map[string]*monorail.Issue

	updateIssueRequestLock sync.Mutex
	updateIssueRequest     map[string]*monorail.UpdateIssueRequest
}

type testIssueClient struct {
	monorail.IssuesClient
	storage *testIssueClientStorage
}

func newTestIssueClient() testIssueClient {
	return testIssueClient{
		storage: &testIssueClientStorage{
			updateIssueRequest: map[string]*monorail.UpdateIssueRequest{},
			getIssueResponse:   map[string]*monorail.Issue{},
		},
	}
}

func (client testIssueClient) UpdateIssue(c context.Context, in *monorail.UpdateIssueRequest, opts ...grpc.CallOption) (*monorail.IssueResponse, error) {
	client.storage.updateIssueRequestLock.Lock()
	defer client.storage.updateIssueRequestLock.Unlock()
	client.storage.updateIssueRequest[genIssueKey(
		in.IssueRef.ProjectName, in.IssueRef.LocalId,
	)] = in
	return &monorail.IssueResponse{}, nil
}

func (client testIssueClient) ListIssues(c context.Context, in *monorail.ListIssuesRequest, opts ...grpc.CallOption) (*monorail.ListIssuesResponse, error) {
	client.storage.listIssuesRequest = in
	return &monorail.ListIssuesResponse{
		Issues: client.storage.listIssuesResponse,
	}, nil
}

func (client testIssueClient) GetIssue(c context.Context, in *monorail.GetIssueRequest, opts ...grpc.CallOption) (*monorail.IssueResponse, error) {
	response := getMonorailClient(c).(testIssueClient).storage.getIssueResponse
	issue, ok := response[genIssueKey(in.IssueRef.ProjectName, in.IssueRef.LocalId)]
	if !ok {
		return nil, status.Errorf(codes.NotFound, "The issue does not exist.")
	}
	return &monorail.IssueResponse{Issue: issue}, nil
}

func mockGetAndListIssues(c context.Context, issues ...*monorail.Issue) {
	mockGetIssues(c, issues...)
	mockListIssues(c, issues...)
}

func mockListIssues(c context.Context, issues ...*monorail.Issue) {
	getMonorailClient(c).(testIssueClient).storage.listIssuesResponse = issues
}

func mockGetIssues(c context.Context, issues ...*monorail.Issue) {
	response := map[string]*monorail.Issue{}
	for _, issue := range issues {
		response[genIssueKey(issue.ProjectName, issue.LocalId)] = issue
	}
	getMonorailClient(c).(testIssueClient).storage.getIssueResponse = response
}

func getIssueUpdateRequest(c context.Context, projectName string, localID uint32) *monorail.UpdateIssueRequest {
	updateIssueRequest := getMonorailClient(c).(testIssueClient).storage.updateIssueRequest
	return updateIssueRequest[genIssueKey(projectName, localID)]
}

func getListIssuesRequest(c context.Context) *monorail.ListIssuesRequest {
	return getMonorailClient(c).(testIssueClient).storage.listIssuesRequest
}

func genIssueKey(projectName string, localID uint32) string {
	return fmt.Sprintf("%s:%d", projectName, localID)
}

// ----------------------------------
// test RotaNG OncallInfo Client

type testOncallInfoClientStorage struct {
	shiftsByRotation map[string]*rotangapi.ShiftEntry
}

type testOncallInfoClient struct {
	rotangapi.OncallInfoClient
	storage *testOncallInfoClientStorage
}

func newTestOncallInfoClient() testOncallInfoClient {
	return testOncallInfoClient{
		storage: &testOncallInfoClientStorage{
			shiftsByRotation: map[string]*rotangapi.ShiftEntry{},
		},
	}
}

func (client testOncallInfoClient) Oncall(c context.Context, in *rotangapi.OncallRequest, opts ...grpc.CallOption) (*rotangapi.OncallResponse, error) {
	shift, exist := client.storage.shiftsByRotation[in.Name]
	if !exist {
		return nil, status.Errorf(codes.NotFound, `"%s" not found`, in.Name)
	}
	return &rotangapi.OncallResponse{Shift: shift}, nil
}

func mockOncall(c context.Context, rotation string, shift *rotangapi.ShiftEntry) {
	getRotaNGClient(c).(testOncallInfoClient).storage.shiftsByRotation[rotation] = shift
}

// ----------------------------------
// test rotation-proxy RotationProxyService Client

type testRotationProxyServiceClientStorage struct {
	rotationsByName map[string]*rotationproxy.Rotation
}

type testRotationProxyServiceClient struct {
	rotationproxy.RotationProxyServiceClient
	storage *testRotationProxyServiceClientStorage
}

func newTestRotationProxyServiceClient() testRotationProxyServiceClient {
	return testRotationProxyServiceClient{
		storage: &testRotationProxyServiceClientStorage{
			rotationsByName: map[string]*rotationproxy.Rotation{},
		},
	}
}

func (client testRotationProxyServiceClient) GetRotation(c context.Context, req *rotationproxy.GetRotationRequest, opts ...grpc.CallOption) (*rotationproxy.Rotation, error) {
	rotation, exist := client.storage.rotationsByName[req.Name]
	if !exist {
		return nil, status.Errorf(codes.NotFound, `"%s" not found`, req.Name)
	}
	return rotation, nil
}

func mockRotation(c context.Context, name string, rotation *rotationproxy.Rotation) {
	getRotationProxyClient(c).(testRotationProxyServiceClient).storage.rotationsByName[name] = rotation
}
