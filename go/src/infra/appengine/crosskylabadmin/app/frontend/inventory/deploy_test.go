// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package inventory

import (
	"fmt"
	"reflect"
	"testing"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/deploy"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/libs/skylab/inventory"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/proto"
	"github.com/google/go-cmp/cmp"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
	"golang.org/x/net/context"
)

func mockValidateDeviceconfig(ctx context.Context, ic inventoryClient, nds []*inventory.CommonDeviceSpecs) error {
	return nil
}

func TestDeleteDutsWithSplitInventory(t *testing.T) {
	Convey("With 3 DUTs in the split inventory", t, func() {
		ctx := testingContext()
		ctx = withSplitInventory(ctx)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		setSplitGitilesDuts(tf.C, tf.FakeGitiles, []testInventoryDut{
			{id: "dut1_id", hostname: "jetstream-host", model: "link", pool: "DUT_POOL_SUITES"},
			{id: "dut2_id", hostname: "chromeos6-rack1-row2-host3", model: "link", pool: "DUT_POOL_SUITES"},
			{id: "dut3_id", hostname: "chromeos15-rack1-row2-host3", model: "link", pool: "DUT_POOL_SUITES"},
		})

		Convey("DeleteDuts with no hostnames returns error", func() {
			_, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{})
			So(err, ShouldNotBeNil)
		})

		Convey("DeleteDuts with unknown hostname deletes no duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"unknown_hostname"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(resp.GetIds(), ShouldBeEmpty)
		})

		Convey("DeleteDuts with known hostnames deletes duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"jetstream-host", "chromeos6-rack1-row2-host3"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(stringset.NewFromSlice(resp.GetIds()...), ShouldResemble, stringset.NewFromSlice("dut1_id", "dut2_id"))

			So(tf.FakeGerrit.Changes, ShouldHaveLength, 1)
			change := tf.FakeGerrit.Changes[len(tf.FakeGerrit.Changes)-1]
			So(change.Files, ShouldHaveLength, 2)
			var paths []string
			for p := range change.Files {
				paths = append(paths, p)
			}
			So(stringset.NewFromSlice(paths...), ShouldResemble, stringset.NewFromSlice(
				"data/skylab/chromeos-misc/jetstream-host.textpb",
				"data/skylab/chromeos6/chromeos6-rack1-row2-host3.textpb",
			))
		})
	})
}

func TestDeployDutWithSplitInventory(t *testing.T) {
	Convey("With no DUTs and one drone in the inventory", t, func() {
		ctx := testingContext()
		ctx = withSplitInventory(ctx)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		err := tf.FakeGitiles.SetSplitInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Infrastructure: inventoryBytesFromServers([]testInventoryServer{
				{
					hostname: "drone-queen-ENVIRONMENT_STAGING",
				},
			}),
		})
		So(err, ShouldBeNil)

		Convey("DeployDut with empty new_spec returns error", func() {
			_, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{})
			So(err, ShouldNotBeNil)
		})

		Convey("DeployDut with invalid new_specs returns error", func() {
			_, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: [][]byte{[]byte("clearly not a protobuf")},
			})
			So(err, ShouldNotBeNil)
		})

		Convey("DeployDut with valid new_specs triggers deploy", func() {
			// Id is a required field, so must be set.
			// But a new ID is assigned on deployment.
			ignoredID := "This ID is ignored"
			dutHostname := "fake-dut"
			specs := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID,
				Hostname: &dutHostname,
			}

			// TODO(pprabhu) Check arguments of this call after testing utilities
			// from ../test_common.go are refactored into a package.
			deployTaskID := "swarming-task"
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).Return(deployTaskID, nil)
			validateDeviceConfigsFunc = mockValidateDeviceconfig
			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(specs),
			})
			So(err, ShouldBeNil)
			deploymentID := resp.DeploymentId
			So(deploymentID, ShouldNotEqual, "")

			oneDutLab, err := getLastChangeForHost(tf.FakeGerrit, "data/skylab/chromeos-misc/fake-dut.textpb")
			So(err, ShouldBeNil)
			dut := oneDutLab.Duts[0]
			common := dut.GetCommon()
			So(common.GetId(), ShouldNotEqual, "")
			So(common.GetId(), ShouldNotEqual, specs.GetId())
			So(common.GetHostname(), ShouldEqual, specs.GetHostname())

			infra, err := getInfrastructureFromLastChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(infra.Servers, ShouldHaveLength, 1)
			server := infra.Servers[0]
			So(server.GetHostname(), ShouldEqual, "drone-queen-ENVIRONMENT_STAGING")
			So(server.DutUids, ShouldHaveLength, 1)
			So(server.DutUids[0], ShouldEqual, common.GetId())

			Convey("then GetDeploymentStatus with wrong ID returns error", func() {
				_, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: "incorrct-id"})
				So(err, ShouldNotBeNil)
			})

			Convey("then GetDeploymentStatus with correct ID returns IN_PROGRESS status", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "RUNNING",
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS)
				So(resp.ChangeUrl, ShouldNotEqual, "")
				So(resp.TaskUrl, ShouldContainSubstring, deploymentID)
			})

			Convey("then GetDeploymentStatus with correct ID returns COMPLETED status on task success", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "COMPLETED",
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_SUCCEEDED)
			})

			Convey("then GetDeploymentStatus with correct ID returns FAILURE status on task failure", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State:   "COMPLETED",
						Failure: true,
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED)
			})
		})

		Convey("DeployDut with multiple valid new_specs triggers deploy", func() {
			ignoredID1 := "fake-id-1"
			dutHostname1 := "fake-dut-1"
			specs1 := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID1,
				Hostname: &dutHostname1,
			}
			ignoredID2 := "fake-id-2"
			dutHostname2 := "chromeos15-rack1-row2-host3"
			specs2 := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID2,
				Hostname: &dutHostname2,
			}

			var byteArr [][]byte
			byteArr = marshalOrPanicMany(specs1, specs2)

			deployTaskID := "swarming-task2"
			// expect two calls to create task (one per new DUT)
			for i := 1; i <= 2; i++ {
				tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).Return(deployTaskID, nil)
			}
			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: byteArr,
			})
			So(err, ShouldBeNil)
			deploymentID := resp.DeploymentId
			So(deploymentID, ShouldNotEqual, "")

			Convey("DeploymentStatus returns IN_PROGRESS", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "RUNNING",
					},
					{
						State: "COMPLETED",
					},
				}, nil)
				depResp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: resp.DeploymentId})
				So(err, ShouldBeNil)
				So(depResp.TaskUrl, ShouldContainSubstring, deploymentID)
				So(depResp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS)
			})

			Convey("DeploymentStatus returns FAILURE", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "COMPLETED",
					},
					{
						State:   "COMPLETED",
						Failure: true,
					},
				}, nil)
				depResp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: resp.DeploymentId})
				So(err, ShouldBeNil)
				So(depResp.TaskUrl, ShouldContainSubstring, deploymentID)
				So(depResp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED)
			})

			Convey("DeploymentStatus returns SUCCESS", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "COMPLETED",
					},
					{
						State: "COMPLETED",
					},
				}, nil)
				depResp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: resp.DeploymentId})
				So(err, ShouldBeNil)
				So(depResp.TaskUrl, ShouldContainSubstring, deploymentID)
				So(depResp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_SUCCEEDED)
			})

			oneDutLab, err := getLastChangeForHost(tf.FakeGerrit, "data/skylab/chromeos-misc/fake-dut-1.textpb")
			So(err, ShouldBeNil)
			dut := oneDutLab.Duts[0]
			common := dut.GetCommon()
			So(common.GetId(), ShouldNotEqual, "")
			So(common.GetId(), ShouldNotEqual, specs1.GetId())
			So(common.GetHostname(), ShouldEqual, specs1.GetHostname())

			oneDutLab, err = getLastChangeForHost(tf.FakeGerrit, "data/skylab/chromeos15/chromeos15-rack1-row2-host3.textpb")
			So(err, ShouldBeNil)
			dut = oneDutLab.Duts[0]
			common = dut.GetCommon()
			So(common.GetId(), ShouldNotEqual, "")
			So(common.GetId(), ShouldNotEqual, specs2.GetId())
			So(common.GetHostname(), ShouldEqual, specs2.GetHostname())

			infra, err := getInfrastructureFromLastChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(infra.Servers, ShouldHaveLength, 1)
			server := infra.Servers[0]
			So(server.GetHostname(), ShouldEqual, "drone-queen-ENVIRONMENT_STAGING")
			So(server.DutUids, ShouldHaveLength, 2)
		})

		Convey("DeployDut assigns servo_port if requested via option", func() {
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes()
			tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{
				{
					State: "RUNNING",
				},
			}, nil)

			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(&inventory.CommonDeviceSpecs{
					Id:       stringPtr("This ID is ignored"),
					Hostname: stringPtr("first-dut"),
					Attributes: []*inventory.KeyValue{
						{Key: stringPtr("servo_host"), Value: stringPtr("my-special-labstation")},
					},
				}),
				Options: &fleet.DutDeploymentOptions{
					AssignServoPortIfMissing: true,
				},
			})
			So(err, ShouldBeNil)
			_, err = tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: resp.DeploymentId})
			So(err, ShouldBeNil)

			oneDutLab, err := getLastChangeForHost(tf.FakeGerrit, "data/skylab/chromeos-misc/first-dut.textpb")
			So(err, ShouldBeNil)
			common := oneDutLab.Duts[0].GetCommon()
			So(common.GetHostname(), ShouldEqual, "first-dut")
			firstPort, found := getAttributeByKey(common, servoPortAttributeKey)
			So(found, ShouldEqual, true)
			// Currently, these test hard-codes the expectation that the first assigned port is 9999.
			// It is very difficult to setup expectations for subsequent
			// DeployDut() calls, so we can not truly validate that the
			// auto-generated ports are arbitrary, but different.
			// See also TestDeployMultipleDuts.
			So(firstPort, ShouldEqual, "9999")
		})

		Convey("DeployDUT should skip deployment if SkipDeployment is provided", func() {
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).MaxTimes(0)
			tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().MaxTimes(0)
			response, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(&inventory.CommonDeviceSpecs{
					Id:       stringPtr("This ID is ignored"),
					Hostname: stringPtr("first-dut"),
					Attributes: []*inventory.KeyValue{
						{Key: stringPtr("servo_host"), Value: stringPtr("my-special-labstation")},
					},
				}),
				Actions: &fleet.DutDeploymentActions{
					SkipDeployment: true,
				},
			})
			So(err, ShouldBeNil)
			So(response, ShouldNotBeNil)
			So(response.DeploymentId, ShouldNotBeNil)
			{
				response, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: response.GetDeploymentId()})
				So(err, ShouldBeNil)
				So(response.ChangeUrl, ShouldNotEqual, "")
				So(response.TaskUrl, ShouldEqual, "")
			}
		})
	})
}

// TODO(xixuan): remove this after per-file inventory is landed and tested.
func TestDeleteDuts(t *testing.T) {
	Convey("With 3 DUTs in the inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut_id_1", "dut_hostname_1", "link", "DUT_POOL_SUITES"},
				{"dut_id_2", "dut_hostname_2", "link", "DUT_POOL_SUITES"},
				{"dut_id_3", "dut_hostname_3", "link", "DUT_POOL_SUITES"},
			}),
		})
		So(err, ShouldBeNil)

		Convey("DeleteDuts with no hostnames returns error", func() {
			_, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{})
			So(err, ShouldNotBeNil)
		})

		Convey("DeleteDuts with unknown hostname deletes no duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"unknown_hostname"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(resp.GetIds(), ShouldBeEmpty)
		})

		Convey("DeleteDuts with known hostnames deletes duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"dut_hostname_1", "dut_hostname_2"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(stringset.NewFromSlice(resp.GetIds()...), ShouldResemble, stringset.NewFromSlice("dut_id_1", "dut_id_2"))
		})
	})

	Convey("With 2 DUTs with the same hostname", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut_id_1", "dut_hostname", "link", "DUT_POOL_SUITES"},
				{"dut_id_2", "dut_hostname", "link", "DUT_POOL_SUITES"},
			}),
		})
		So(err, ShouldBeNil)

		Convey("DeleteDuts with known hostname deletes both duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"dut_hostname"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(stringset.NewFromSlice(resp.GetIds()...), ShouldResemble, stringset.NewFromSlice("dut_id_1", "dut_id_2"))
		})
	})
}

// TODO(xixuan): remove this after per-file inventory is landed and tested.
func TestDeployDut(t *testing.T) {
	Convey("With no DUTs and one drone in the inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Infrastructure: inventoryBytesFromServers([]testInventoryServer{
				{
					hostname: "drone-queen-ENVIRONMENT_STAGING",
				},
			}),
		})
		So(err, ShouldBeNil)

		Convey("DeployDut with empty new_spec returns error", func() {
			_, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{})
			So(err, ShouldNotBeNil)
		})

		Convey("DeployDut with invalid new_specs returns error", func() {
			_, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: [][]byte{[]byte("clearly not a protobuf")},
			})
			So(err, ShouldNotBeNil)
		})

		Convey("DeployDut rejects deployment of labsations with wrong os_type", func() {
			ignoredID := "This ID is ignored"
			dutHostname := "my-labstation123"
			specs := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID,
				Hostname: &dutHostname,
			}
			_, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(specs),
			})
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "OS_TYPE_LABSTATION")
		})

		Convey("DeployDut with valid new_specs triggers deploy", func() {
			// Id is a required field, so must be set.
			// But a new ID is assigned on deployment.
			ignoredID := "This ID is ignored"
			dutHostname := "fake-dut"
			specs := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID,
				Hostname: &dutHostname,
			}

			// TODO(pprabhu) Check arguments of this call after testing utilities
			// from ../test_common.go are refactored into a package.
			deployTaskID := "swarming-task"
			validateDeviceConfigsFunc = mockValidateDeviceconfig
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).Return(deployTaskID, nil)
			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(specs),
			})
			So(err, ShouldBeNil)
			deploymentID := resp.DeploymentId
			So(deploymentID, ShouldNotEqual, "")

			lab, err := getLabFromLastChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(lab.Duts, ShouldHaveLength, 1)
			dut := lab.Duts[0]
			common := dut.GetCommon()
			So(common.GetId(), ShouldNotEqual, "")
			So(common.GetId(), ShouldNotEqual, specs.GetId())
			So(common.GetHostname(), ShouldEqual, specs.GetHostname())

			infra, err := getInfrastructureFromLastChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(infra.Servers, ShouldHaveLength, 1)
			server := infra.Servers[0]
			So(server.GetHostname(), ShouldEqual, "drone-queen-ENVIRONMENT_STAGING")
			So(server.DutUids, ShouldHaveLength, 1)
			So(server.DutUids[0], ShouldEqual, common.GetId())

			Convey("then GetDeploymentStatus with wrong ID returns error", func() {
				_, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: "incorrct-id"})
				So(err, ShouldNotBeNil)
			})

			Convey("then GetDeploymentStatus with correct ID returns IN_PROGRESS status", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "RUNNING",
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS)
				So(resp.ChangeUrl, ShouldNotEqual, "")
				So(resp.TaskUrl, ShouldContainSubstring, deploymentID)
			})

			Convey("then GetDeploymentStatus with correct ID returns COMPLETED status on task success", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "COMPLETED",
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_SUCCEEDED)
			})

			Convey("then GetDeploymentStatus with correct ID returns FAILURE status on task failure", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State:   "COMPLETED",
						Failure: true,
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED)
			})
		})

		Convey("DeployDut with multiple valid new_specs triggers deploy", func() {
			ignoredID1 := "fake-id-1"
			dutHostname1 := "fake-dut-1"
			specs1 := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID1,
				Hostname: &dutHostname1,
			}
			ignoredID2 := "fake-id-2"
			dutHostname2 := "fale-dut-2"
			specs2 := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID2,
				Hostname: &dutHostname2,
			}

			var byteArr [][]byte
			byteArr = marshalOrPanicMany(specs1, specs2)

			deployTaskID := "swarming-task2"
			// expect two calls to create task (one per new DUT)
			for i := 1; i <= 2; i++ {
				tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).Return(deployTaskID, nil)
			}
			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: byteArr,
			})
			So(err, ShouldBeNil)
			deploymentID := resp.DeploymentId
			So(deploymentID, ShouldNotEqual, "")
		})

		Convey("DeployDut assigns servo_port if requested via option", func() {
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes()
			tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{
				{
					State: "RUNNING",
				},
			}, nil)

			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(&inventory.CommonDeviceSpecs{
					Id:       stringPtr("This ID is ignored"),
					Hostname: stringPtr("first-dut"),
					Attributes: []*inventory.KeyValue{
						{Key: stringPtr("servo_host"), Value: stringPtr("my-special-labstation")},
					},
				}),
				Options: &fleet.DutDeploymentOptions{
					AssignServoPortIfMissing: true,
				},
			})
			So(err, ShouldBeNil)
			_, err = tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: resp.DeploymentId})
			So(err, ShouldBeNil)

			lab, err := getLabFromLastChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(lab.Duts, ShouldHaveLength, 1)
			dut := lab.Duts[0]
			common := dut.GetCommon()
			So(common.GetHostname(), ShouldEqual, "first-dut")
			firstPort, found := getAttributeByKey(common, servoPortAttributeKey)
			So(found, ShouldEqual, true)
			// Currently, these test hard-codes the expectation that the first assigned port is 9999.
			// It is very difficult to setup expectations for subsequent
			// DeployDut() calls, so we can not truly validate that the
			// auto-generated ports are arbitrary, but different.
			// See also TestDeployMultipleDuts.
			So(firstPort, ShouldEqual, "9999")
		})

		Convey("DeployDUT should skip deployment if SkipDeployment is provided", func() {
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).MaxTimes(0)
			tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().MaxTimes(0)
			response, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(&inventory.CommonDeviceSpecs{
					Id:       stringPtr("This ID is ignored"),
					Hostname: stringPtr("first-dut"),
					Attributes: []*inventory.KeyValue{
						{Key: stringPtr("servo_host"), Value: stringPtr("my-special-labstation")},
					},
				}),
				Actions: &fleet.DutDeploymentActions{
					SkipDeployment: true,
				},
			})
			So(err, ShouldBeNil)
			So(response, ShouldNotBeNil)
			So(response.DeploymentId, ShouldNotBeNil)
			{
				response, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: response.GetDeploymentId()})
				So(err, ShouldBeNil)
				So(response.ChangeUrl, ShouldNotEqual, "")
				So(response.TaskUrl, ShouldEqual, "")
			}
		})
	})
}

func TestDeployMultipleDuts(t *testing.T) {
	// This test is separate because lack of a proper fake gitstore.GitStore makes writing this test a lot harder.
	// Once a fake gitstore implementation is available, this can be merged with TestDeployDut
	Convey("With one DUT and one drone in the inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		lab, err := inventory.WriteLabToString(&inventory.Lab{
			Duts: []*inventory.DeviceUnderTest{
				{
					Common: &inventory.CommonDeviceSpecs{
						Hostname: stringPtr("host1"),
						Id:       stringPtr("host1-id"),
						Attributes: []*inventory.KeyValue{
							{Key: stringPtr("servo_host"), Value: stringPtr("my-special-labstation")},
							// Currently, these test hard-codes the expectation that the first assigned port is 9999.
							// It is very difficult to setup expectations for subsequent
							// DeployDut() calls, so we can not truly validate that the
							// auto-generated ports are arbitrary, but different.
							//
							// Together with TestDeploy, this ensures that the first port
							// assigned is 9999, and the next port assigned is different.
							{Key: stringPtr("servo_port"), Value: stringPtr("9999")},
						},
					},
				},
			},
		})
		So(err, ShouldBeNil)

		err = tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Infrastructure: inventoryBytesFromServers([]testInventoryServer{
				{
					hostname: "drone-queen-ENVIRONMENT_STAGING",
				},
			}),
			Lab: []byte(lab),
		})
		So(err, ShouldBeNil)

		Convey("DeployDut with duplicated hostname", func() {
			ignoredID := "This ID is ignored"
			specs := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID,
				Hostname: stringPtr("host1"),
				Attributes: []*inventory.KeyValue{
					{Key: stringPtr("servo_host"), Value: stringPtr("my-special-labstation")},
					{Key: stringPtr("servo_port"), Value: stringPtr("8888")},
				},
			}
			validateDeviceConfigsFunc = mockValidateDeviceconfig
			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(specs),
			})
			So(err, ShouldBeNil)
			deploymentID := resp.DeploymentId
			So(deploymentID, ShouldNotEqual, "")

			resp2, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
			So(err, ShouldBeNil)
			So(resp2.TaskUrl, ShouldEqual, "")

			store := gitstore.NewInventoryStore(tf.FakeGerrit, tf.FakeGitiles)
			err = store.Refresh(tf.C)
			So(err, ShouldBeNil)
			So(store.GetDuts(), ShouldHaveLength, 1)

			duts := mapHostnameToDUTs(store.GetDuts())
			So(duts, ShouldContainKey, "host1")
			dut := duts["host1"]
			firstPort, found := getAttributeByKey(dut.GetCommon(), servoPortAttributeKey)
			So(found, ShouldEqual, true)
			So(firstPort, ShouldEqual, "9999")
		})

		Convey("DeployDut assigns non-conflicting servo_port if requested via option", func() {
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes()
			tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).AnyTimes().Return([]*swarming.SwarmingRpcsTaskResult{
				{
					State: "RUNNING",
				},
			}, nil)

			validateDeviceConfigsFunc = mockValidateDeviceconfig
			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: marshalOrPanicMany(&inventory.CommonDeviceSpecs{
					Id:       stringPtr("This ID is ignored"),
					Hostname: stringPtr("new-dut"),
					Attributes: []*inventory.KeyValue{
						{Key: stringPtr("servo_host"), Value: stringPtr("my-special-labstation")},
					},
				}),
				Options: &fleet.DutDeploymentOptions{
					AssignServoPortIfMissing: true,
				},
			})
			So(err, ShouldBeNil)
			_, err = tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: resp.DeploymentId})
			So(err, ShouldBeNil)

			lab, err := getLabFromLastChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(lab.Duts, ShouldHaveLength, 2)

			duts := mapHostnameToDUTs(lab.Duts)
			So(duts, ShouldContainKey, "new-dut")
			dut := duts["new-dut"]
			firstPort, found := getAttributeByKey(dut.GetCommon(), servoPortAttributeKey)
			So(found, ShouldEqual, true)
			So(firstPort, ShouldNotEqual, "9999")
		})
	})

}

func TestRedeployDut(t *testing.T) {
	Convey("With one DUT in the inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		env := inventory.Environment_ENVIRONMENT_STAGING
		oldSpecs := &inventory.CommonDeviceSpecs{
			Environment: &env,
			Hostname:    stringPtr("dut_hostname_1"),
			Id:          stringPtr("dut_id_1"),
			Labels: &inventory.SchedulableLabels{
				Model:         stringPtr("link"),
				CriticalPools: []inventory.SchedulableLabels_DUTPool{inventory.SchedulableLabels_DUT_POOL_SUITES},
			},
		}

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut_id_1", "dut_hostname_1", "link", "DUT_POOL_SUITES"},
			}),
			Infrastructure: inventoryBytesFromServers([]testInventoryServer{
				{
					hostname:    "fake-drone.google.com",
					environment: inventory.Environment_ENVIRONMENT_STAGING,
					dutIDs:      []string{"dut_id_1"},
				},
			}),
		})
		So(err, ShouldBeNil)

		Convey("Update DUT with empty old specs returns error", func() {
			_, err = tf.Inventory.RedeployDut(tf.C, &fleet.RedeployDutRequest{
				NewSpecs: marshalOrPanicOne(oldSpecs),
			})
			So(err, ShouldNotBeNil)
		})

		Convey("Update DUT with empty new specs returns error", func() {
			_, err = tf.Inventory.RedeployDut(tf.C, &fleet.RedeployDutRequest{
				OldSpecs: marshalOrPanicOne(oldSpecs),
			})
			So(err, ShouldNotBeNil)
		})

		Convey("Update DUT with different DUT ID across specs returns error", func() {
			newSpecs := &inventory.CommonDeviceSpecs{}
			proto.Merge(newSpecs, oldSpecs)
			newSpecs.Id = stringPtr("changed_id")
			So(err, ShouldBeNil)
			_, err = tf.Inventory.RedeployDut(tf.C, &fleet.RedeployDutRequest{
				OldSpecs: marshalOrPanicOne(oldSpecs),
				NewSpecs: marshalOrPanicOne(newSpecs),
			})
			So(err, ShouldNotBeNil)
		})

		Convey("Update DUT with same old and new specs triggers deploy task", func() {
			// TODO(pprabhu) Check arguments of this call after testing utilities
			// from ../test_common.go are refactored into a package.
			deployTaskID := "swarming-task"
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).Return(deployTaskID, nil)

			resp, err := tf.Inventory.RedeployDut(tf.C, &fleet.RedeployDutRequest{
				OldSpecs: marshalOrPanicOne(oldSpecs),
				NewSpecs: marshalOrPanicOne(oldSpecs),
			})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			deploymentID := resp.GetDeploymentId()
			So(deploymentID, ShouldNotEqual, "")

			// There were no DUT specs update, so there should be no inventory chanage.
			So(tf.FakeGerrit.Changes, ShouldHaveLength, 0)

			Convey("then GetDeploymentStatus with correct ID returns IN_PROGRESS status", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "RUNNING",
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS)
				// There were no DUT specs update, so there should be no inventory chanage.
				So(resp.ChangeUrl, ShouldEqual, "")
				So(resp.TaskUrl, ShouldContainSubstring, deploymentID)
			})
		})

		Convey("Update DUT with different old and new specs updates inventory and triggers deploy task", func() {
			newSpecs := &inventory.CommonDeviceSpecs{}
			proto.Merge(newSpecs, oldSpecs)
			newSpecs.Hostname = stringPtr("updated_hostname")

			// TODO(pprabhu) Check arguments of this call after testing utilities
			// from ../test_common.go are refactored into a package.
			deployTaskID := "swarming-task"
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).Return(deployTaskID, nil)

			resp, err := tf.Inventory.RedeployDut(tf.C, &fleet.RedeployDutRequest{
				OldSpecs: marshalOrPanicOne(oldSpecs),
				NewSpecs: marshalOrPanicOne(newSpecs),
			})

			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			deploymentID := resp.GetDeploymentId()
			So(deploymentID, ShouldNotEqual, "")

			lab, err := getLabFromLastChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(lab.Duts, ShouldHaveLength, 1)
			dut := lab.Duts[0]
			common := dut.GetCommon()
			So(common.GetId(), ShouldEqual, newSpecs.GetId())
			// Verify hostname was updated.
			So(common.GetHostname(), ShouldEqual, newSpecs.GetHostname())

			Convey("then GetDeploymentStatus with correct ID returns IN_PROGRESS status", func() {
				tf.MockSwarming.EXPECT().ListRecentTasks(gomock.Any(), gomock.Any(), gomock.Any(), gomock.Any()).Return([]*swarming.SwarmingRpcsTaskResult{
					{
						State: "RUNNING",
					},
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS)
				So(resp.ChangeUrl, ShouldNotEqual, "")
				So(resp.TaskUrl, ShouldContainSubstring, deploymentID)
			})

		})
	})
}

func TestGetDeploymentStatus(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	id, err := deploy.PutStatus(ctx, &deploy.Status{
		IsFinal: true,
		Status:  fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED,
		Reason:  "something went wrong",
	})
	if err != nil {
		t.Fatal(err)
	}

	tf, validate := newTestFixture(t)
	defer validate()
	got, err := tf.Inventory.GetDeploymentStatus(ctx, &fleet.GetDeploymentStatusRequest{
		DeploymentId: id,
	})
	if err != nil {
		t.Fatal(err)
	}
	want := &fleet.GetDeploymentStatusResponse{
		Status:  fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED,
		Message: "something went wrong",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("GetDeploymentStatus() = %#v; want %#v", got, want)
	}
}

func TestDeployActionArgs(t *testing.T) {
	t.Parallel()
	testCases := []struct {
		test string
		in   *fleet.DutDeploymentActions
		out  string
	}{
		{
			"empty",
			&fleet.DutDeploymentActions{},
			"",
		},
		{
			"StageImageToUsb",
			&fleet.DutDeploymentActions{
				StageImageToUsb: true,
			},
			"stage-usb",
		},
		{
			"InstallFirmware",
			&fleet.DutDeploymentActions{
				InstallFirmware: true,
			},
			"install-firmware,verify-recovery-mode",
		},
		{
			"InstallTestImage",
			&fleet.DutDeploymentActions{
				InstallTestImage: true,
			},
			"install-test-image,update-label",
		},
		{
			"SkipDeployment",
			&fleet.DutDeploymentActions{
				SkipDeployment: true,
			},
			"",
		},
		{
			"SetupLabstation",
			&fleet.DutDeploymentActions{
				SetupLabstation: true,
			},
			"setup-labstation,update-label",
		},
		{
			"RunPreDeployVerification",
			&fleet.DutDeploymentActions{
				RunPreDeployVerification: true,
			},
			"run-pre-deploy-verification",
		},
		{
			"All",
			&fleet.DutDeploymentActions{
				StageImageToUsb:          true,
				InstallFirmware:          true,
				InstallTestImage:         true,
				SkipDeployment:           true,
				SetupLabstation:          true,
				RunPreDeployVerification: true,
			},
			"stage-usb,install-test-image,update-label,install-firmware,verify-recovery-mode,setup-labstation,update-label,run-pre-deploy-verification",
		},
	}
	for _, tc := range testCases {
		t.Run("Test case "+tc.test, func(t *testing.T) {
			got := deployActionArgs(tc.in)
			if diff := cmp.Diff(tc.out, got); diff != "" {
				t.Errorf(
					"Convert actions %#v got labels differ -want +got, %s",
					tc.test,
					diff)
			}
		})
	}
}

// getLastChangeForHost gets the latest change for a given path of one host in gerrit for per-file inventory.
func getLastChangeForHost(fg *fakes.GerritClient, path string) (*inventory.Lab, error) {
	if len(fg.Changes) == 0 {
		return nil, errors.Reason("found no gerrit changes").Err()
	}

	change := fg.Changes[len(fg.Changes)-1]
	content, ok := change.Files[path]
	if !ok {
		return nil, errors.Reason(fmt.Sprintf("cannot find path %s in %v", path, change.Files)).Err()
	}
	var oneDutLab inventory.Lab
	err := inventory.LoadLabFromString(content, &oneDutLab)
	return &oneDutLab, err
}

// getLabFromLastChange gets the latest inventory.Lab committed to
// fakes.GerritClient
func getLabFromLastChange(fg *fakes.GerritClient) (*inventory.Lab, error) {
	if len(fg.Changes) == 0 {
		return nil, errors.Reason("found no gerrit changes").Err()
	}

	change := fg.Changes[len(fg.Changes)-1]
	f, ok := change.Files["data/skylab/lab.textpb"]
	if !ok {
		return nil, errors.Reason("No modification to Lab in gerrit change").Err()
	}
	var lab inventory.Lab
	err := inventory.LoadLabFromString(f, &lab)
	return &lab, err
}

// getInfrastructureFromLastChange gets the latest inventory.Infrastructure
// committed to fakes.GerritClient
func getInfrastructureFromLastChange(fg *fakes.GerritClient) (*inventory.Infrastructure, error) {
	if len(fg.Changes) == 0 {
		return nil, errors.Reason("found no gerrit changes").Err()
	}

	change := fg.Changes[len(fg.Changes)-1]
	f, ok := change.Files["data/skylab/server_db.textpb"]
	if !ok {
		return nil, errors.Reason("No modification to Infrastructure in gerrit change").Err()
	}
	var infra inventory.Infrastructure
	err := inventory.LoadInfrastructureFromString(f, &infra)
	return &infra, err
}

func stringPtr(s string) *string {
	return &s
}

// marshalOrPanicOne serializes the given proto.Message or panics on failure.
func marshalOrPanicOne(m proto.Message) []byte {
	s, err := proto.Marshal(m)
	if err != nil {
		panic(err)
	}
	return s
}

// call marshalOrPanicOne on multiple arguments
func marshalOrPanicMany(m ...proto.Message) [][]byte {
	out := make([][]byte, 0)
	for _, item := range m {
		out = append(out, marshalOrPanicOne(item))
	}
	return out
}
