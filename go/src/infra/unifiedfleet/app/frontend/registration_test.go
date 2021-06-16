// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"math"
	"reflect"
	"strconv"
	"strings"
	"testing"

	proto "infra/unifiedfleet/api/v1/proto"
	api "infra/unifiedfleet/api/v1/rpc"
	"infra/unifiedfleet/app/model/configuration"
	. "infra/unifiedfleet/app/model/datastore"
	"infra/unifiedfleet/app/model/inventory"
	"infra/unifiedfleet/app/model/registration"
	"infra/unifiedfleet/app/util"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
	code "google.golang.org/genproto/googleapis/rpc/code"
	"google.golang.org/grpc/status"
)

func mockChromeOSMachine(id, lab, board string) *proto.Machine {
	return &proto.Machine{
		Name: util.AddPrefix(util.MachineCollection, id),
		Device: &proto.Machine_ChromeosMachine{
			ChromeosMachine: &proto.ChromeOSMachine{
				ReferenceBoard: board,
			},
		},
	}
}

func mockChromeBrowserMachine(id, lab, name string) *proto.Machine {
	return &proto.Machine{
		Name: util.AddPrefix(util.MachineCollection, id),
		Device: &proto.Machine_ChromeBrowserMachine{
			ChromeBrowserMachine: &proto.ChromeBrowserMachine{
				Description: name,
			},
		},
	}
}

func assertMachineEqual(a *proto.Machine, b *proto.Machine) {
	So(a.GetName(), ShouldEqual, b.GetName())
	So(a.GetChromeBrowserMachine().GetDescription(), ShouldEqual,
		b.GetChromeBrowserMachine().GetDescription())
	So(a.GetChromeosMachine().GetReferenceBoard(), ShouldEqual,
		b.GetChromeosMachine().GetReferenceBoard())
}

func mockRack(id string, rackCapactiy int32) *proto.Rack {
	return &proto.Rack{
		Name:       util.AddPrefix(util.RackCollection, id),
		CapacityRu: rackCapactiy,
	}
}

func mockNic(id string) *proto.Nic {
	return &proto.Nic{
		Name: util.AddPrefix(util.NicCollection, id),
	}
}

func mockKVM(id string) *proto.KVM {
	return &proto.KVM{
		Name: util.AddPrefix(util.KVMCollection, id),
	}
}

func mockRPM(id string) *proto.RPM {
	return &proto.RPM{
		Name: util.AddPrefix(util.RPMCollection, id),
	}
}

func mockDrac(id string) *proto.Drac {
	return &proto.Drac{
		Name: util.AddPrefix(util.DracCollection, id),
	}
}

func mockSwitch(id string) *proto.Switch {
	return &proto.Switch{
		Name: util.AddPrefix(util.SwitchCollection, id),
	}
}

func TestCreateMachine(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	chromeOSMachine1 := mockChromeOSMachine("", "chromeoslab1", "samus1")
	chromeOSMachine2 := mockChromeOSMachine("", "chromeoslab2", "samus2")
	chromeOSMachine3 := mockChromeOSMachine("", "chromeoslab3", "samus3")
	chromeOSMachine4 := mockChromeOSMachine("", "chromeoslab1", "samus1")
	Convey("CreateMachines", t, func() {
		Convey("Create new machine with machine_id", func() {
			req := &api.CreateMachineRequest{
				Machine:   chromeOSMachine1,
				MachineId: "Chromeos-asset-1",
			}
			resp, err := tf.Fleet.CreateMachine(tf.C, req)
			So(err, ShouldBeNil)
			assertMachineEqual(resp, chromeOSMachine1)
		})

		Convey("Create existing machines", func() {
			req := &api.CreateMachineRequest{
				Machine:   chromeOSMachine4,
				MachineId: "Chromeos-asset-1",
			}
			resp, err := tf.Fleet.CreateMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new machine - Invalid input nil", func() {
			req := &api.CreateMachineRequest{
				Machine: nil,
			}
			resp, err := tf.Fleet.CreateMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new machine - Invalid input empty ID", func() {
			req := &api.CreateMachineRequest{
				Machine:   chromeOSMachine2,
				MachineId: "",
			}
			resp, err := tf.Fleet.CreateMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new machine - Invalid input invalid characters", func() {
			req := &api.CreateMachineRequest{
				Machine:   chromeOSMachine3,
				MachineId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateMachine(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	chromeOSMachine1 := mockChromeOSMachine("", "chromeoslab1", "samus1")
	chromeOSMachine2 := mockChromeOSMachine("chromeos-asset-1", "chromeoslab", "veyron")
	chromeBrowserMachine1 := mockChromeBrowserMachine("chrome-asset-1", "chromelab", "machine-1")
	chromeOSMachine3 := mockChromeOSMachine("", "chromeoslab", "samus")
	chromeOSMachine4 := mockChromeOSMachine("a.b)7&", "chromeoslab", "samus")
	Convey("UpdateMachines", t, func() {
		Convey("Update existing machines", func() {
			req := &api.CreateMachineRequest{
				Machine:   chromeOSMachine1,
				MachineId: "chromeos-asset-1",
			}
			resp, err := tf.Fleet.CreateMachine(tf.C, req)
			So(err, ShouldBeNil)
			assertMachineEqual(resp, chromeOSMachine1)
			ureq := &api.UpdateMachineRequest{
				Machine: chromeOSMachine2,
			}
			resp, err = tf.Fleet.UpdateMachine(tf.C, ureq)
			So(err, ShouldBeNil)
			assertMachineEqual(resp, chromeOSMachine2)
		})

		Convey("Update non-existing machines", func() {
			ureq := &api.UpdateMachineRequest{
				Machine: chromeBrowserMachine1,
			}
			resp, err := tf.Fleet.UpdateMachine(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update machine - Invalid input nil", func() {
			req := &api.UpdateMachineRequest{
				Machine: nil,
			}
			resp, err := tf.Fleet.UpdateMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update machine - Invalid input empty name", func() {
			chromeOSMachine3.Name = ""
			req := &api.UpdateMachineRequest{
				Machine: chromeOSMachine3,
			}
			resp, err := tf.Fleet.UpdateMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update machine - Invalid input invalid characters", func() {
			req := &api.UpdateMachineRequest{
				Machine: chromeOSMachine4,
			}
			resp, err := tf.Fleet.UpdateMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetMachine(t *testing.T) {
	t.Parallel()
	Convey("GetMachine", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		chromeOSMachine1 := mockChromeOSMachine("chromeos-asset-1", "chromeoslab", "samus")
		req := &api.CreateMachineRequest{
			Machine:   chromeOSMachine1,
			MachineId: "chromeos-asset-1",
		}
		resp, err := tf.Fleet.CreateMachine(tf.C, req)
		So(err, ShouldBeNil)
		assertMachineEqual(resp, chromeOSMachine1)
		Convey("Get machine by existing ID", func() {
			req := &api.GetMachineRequest{
				Name: util.AddPrefix(util.MachineCollection, "chromeos-asset-1"),
			}
			resp, err := tf.Fleet.GetMachine(tf.C, req)
			So(err, ShouldBeNil)
			assertMachineEqual(resp, chromeOSMachine1)
		})
		Convey("Get machine by non-existing ID", func() {
			req := &api.GetMachineRequest{
				Name: util.AddPrefix(util.MachineCollection, "chrome-asset-1"),
			}
			resp, err := tf.Fleet.GetMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get machine - Invalid input empty name", func() {
			req := &api.GetMachineRequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get machine - Invalid input invalid characters", func() {
			req := &api.GetMachineRequest{
				Name: util.AddPrefix(util.MachineCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListMachines(t *testing.T) {
	t.Parallel()
	Convey("ListMachines", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		machines := make([]*proto.Machine, 0, 4)
		for i := 0; i < 4; i++ {
			chromeOSMachine1 := mockChromeOSMachine("", "chromeoslab", "samus")
			req := &api.CreateMachineRequest{
				Machine:   chromeOSMachine1,
				MachineId: fmt.Sprintf("chromeos-asset-%d", i),
			}
			resp, err := tf.Fleet.CreateMachine(tf.C, req)
			So(err, ShouldBeNil)
			assertMachineEqual(resp, chromeOSMachine1)
			machines = append(machines, resp)
		}

		Convey("ListMachines - page_size negative", func() {
			req := &api.ListMachinesRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListMachines(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListMachines - page_token invalid", func() {
			req := &api.ListMachinesRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListMachines(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListMachines - Full listing Max PageSize", func() {
			req := &api.ListMachinesRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListMachines(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Machines, ShouldResembleProto, machines)
		})

		Convey("ListMachines - Full listing with no pagination", func() {
			req := &api.ListMachinesRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListMachines(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Machines, ShouldResembleProto, machines)
		})

		Convey("ListMachines - listing with pagination", func() {
			req := &api.ListMachinesRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListMachines(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Machines, ShouldResembleProto, machines[:3])

			req = &api.ListMachinesRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListMachines(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Machines, ShouldResembleProto, machines[3:])
		})
	})
}

func TestDeleteMachine(t *testing.T) {
	t.Parallel()
	Convey("DeleteMachine", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		chromeOSMachine1 := mockChromeOSMachine("chromeos-asset-1", "chromeoslab", "samus")
		req := &api.CreateMachineRequest{
			Machine:   chromeOSMachine1,
			MachineId: "chromeos-asset-1",
		}
		resp, err := tf.Fleet.CreateMachine(tf.C, req)
		So(err, ShouldBeNil)
		assertMachineEqual(resp, chromeOSMachine1)
		Convey("Delete machine by existing ID", func() {
			req := &api.DeleteMachineRequest{
				Name: util.AddPrefix(util.MachineCollection, "chromeos-asset-1"),
			}
			_, err := tf.Fleet.DeleteMachine(tf.C, req)
			So(err, ShouldBeNil)
			greq := &api.GetMachineRequest{
				Name: util.AddPrefix(util.MachineCollection, "chromeos-asset-1"),
			}
			res, err := tf.Fleet.GetMachine(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete machine by non-existing ID", func() {
			req := &api.DeleteMachineRequest{
				Name: util.AddPrefix(util.MachineCollection, "chrome-asset-1"),
			}
			_, err := tf.Fleet.DeleteMachine(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete machine - Invalid input empty name", func() {
			req := &api.DeleteMachineRequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Delete machine - Invalid input invalid characters", func() {
			req := &api.DeleteMachineRequest{
				Name: util.AddPrefix(util.MachineCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteMachine(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestImportMachines(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	Convey("Import browser machines", t, func() {
		Convey("happy path", func() {
			req := &api.ImportMachinesRequest{
				Source: &api.ImportMachinesRequest_MachineDbSource{
					MachineDbSource: &api.MachineDBSource{
						Host: "fake_host",
					},
				},
			}
			res, err := tf.Fleet.ImportMachines(ctx, req)
			So(err, ShouldBeNil)
			So(res.Code, ShouldEqual, code.Code_OK)
			machines, _, err := registration.ListMachines(ctx, 100, "")
			So(err, ShouldBeNil)
			So(machines, ShouldHaveLength, 3)
			So(parseAssets(machines, "Name"), ShouldResemble, []string{"machine1", "machine2", "machine3"})
			browserMachines := make([]*proto.ChromeBrowserMachine, len(machines))
			switches := make([]*proto.SwitchInterface, len(machines))
			for i, m := range machines {
				browserMachines[i] = m.GetChromeBrowserMachine()
				switches[i] = m.GetChromeBrowserMachine().GetNetworkDeviceInterface()
			}
			So(parseAssets(browserMachines, "Nic"), ShouldResemble, []string{"machine1-eth0", "machine2-eth0", "machine3-eth0"})
			So(parseAssets(browserMachines, "Drac"), ShouldResemble, []string{"machine1-drac"})
			So(switches, ShouldResembleProto, []*proto.SwitchInterface{
				{
					Switch: "eq017.atl97",
					Port:   2,
				},
				{
					Switch: "eq017.atl97",
					Port:   3,
				},
				{
					Switch: "eq041.atl97",
					Port:   1,
				},
			})
		})
		Convey("import browser machines with empty machineDB host", func() {
			req := &api.ImportMachinesRequest{
				Source: &api.ImportMachinesRequest_MachineDbSource{
					MachineDbSource: &api.MachineDBSource{
						Host: "",
					},
				},
			}
			_, err := tf.Fleet.ImportMachines(ctx, req)
			So(err, ShouldNotBeNil)
			s, ok := status.FromError(err)
			So(ok, ShouldBeTrue)
			So(s.Code(), ShouldEqual, code.Code_INVALID_ARGUMENT)
		})
		Convey("import browser machines with empty machineDB source", func() {
			req := &api.ImportMachinesRequest{
				Source: &api.ImportMachinesRequest_MachineDbSource{},
			}
			_, err := tf.Fleet.ImportMachines(ctx, req)
			So(err, ShouldNotBeNil)
			s, ok := status.FromError(err)
			So(ok, ShouldBeTrue)
			So(s.Code(), ShouldEqual, code.Code_INVALID_ARGUMENT)
		})
	})
}

func TestCreateRack(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	rack1 := mockRack("", 5)
	rack2 := mockRack("", 4)
	rack3 := mockRack("", 2)
	Convey("CreateRack", t, func() {
		Convey("Create new rack with rack_id", func() {
			req := &api.CreateRackRequest{
				Rack:   rack1,
				RackId: "Rack-1",
			}
			resp, err := tf.Fleet.CreateRack(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rack1)
		})

		Convey("Create existing rack", func() {
			req := &api.CreateRackRequest{
				Rack:   rack3,
				RackId: "Rack-1",
			}
			resp, err := tf.Fleet.CreateRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new rack - Invalid input nil", func() {
			req := &api.CreateRackRequest{
				Rack: nil,
			}
			resp, err := tf.Fleet.CreateRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new rack - Invalid input empty ID", func() {
			req := &api.CreateRackRequest{
				Rack:   rack2,
				RackId: "",
			}
			resp, err := tf.Fleet.CreateRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new rack - Invalid input invalid characters", func() {
			req := &api.CreateRackRequest{
				Rack:   rack2,
				RackId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateRack(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	rack1 := mockRack("", 5)
	rack2 := mockRack("rack-1", 10)
	rack3 := mockRack("rack-3", 6)
	rack4 := mockRack("a.b)7&", 6)
	Convey("UpdateRack", t, func() {
		Convey("Update existing rack", func() {
			req := &api.CreateRackRequest{
				Rack:   rack1,
				RackId: "rack-1",
			}
			resp, err := tf.Fleet.CreateRack(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rack1)
			ureq := &api.UpdateRackRequest{
				Rack: rack2,
			}
			resp, err = tf.Fleet.UpdateRack(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rack2)
		})

		Convey("Update non-existing rack", func() {
			ureq := &api.UpdateRackRequest{
				Rack: rack3,
			}
			resp, err := tf.Fleet.UpdateRack(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update rack - Invalid input nil", func() {
			req := &api.UpdateRackRequest{
				Rack: nil,
			}
			resp, err := tf.Fleet.UpdateRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update rack - Invalid input empty name", func() {
			rack3.Name = ""
			req := &api.UpdateRackRequest{
				Rack: rack3,
			}
			resp, err := tf.Fleet.UpdateRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update rack - Invalid input invalid characters", func() {
			req := &api.UpdateRackRequest{
				Rack: rack4,
			}
			resp, err := tf.Fleet.UpdateRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetRack(t *testing.T) {
	t.Parallel()
	Convey("GetRack", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		rack1 := mockRack("rack-1", 10)
		req := &api.CreateRackRequest{
			Rack:   rack1,
			RackId: "rack-1",
		}
		resp, err := tf.Fleet.CreateRack(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, rack1)
		Convey("Get rack by existing ID", func() {
			req := &api.GetRackRequest{
				Name: util.AddPrefix(util.RackCollection, "rack-1"),
			}
			resp, err := tf.Fleet.GetRack(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rack1)
		})
		Convey("Get rack by non-existing ID", func() {
			req := &api.GetRackRequest{
				Name: util.AddPrefix(util.RackCollection, "rack-2"),
			}
			resp, err := tf.Fleet.GetRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get rack - Invalid input empty name", func() {
			req := &api.GetRackRequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get rack - Invalid input invalid characters", func() {
			req := &api.GetRackRequest{
				Name: util.AddPrefix(util.RackCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListRacks(t *testing.T) {
	t.Parallel()
	Convey("ListRacks", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		racks := make([]*proto.Rack, 0, 4)
		for i := 0; i < 4; i++ {
			rack1 := mockRack("", 10)
			req := &api.CreateRackRequest{
				Rack:   rack1,
				RackId: fmt.Sprintf("rack-%d", i),
			}
			resp, err := tf.Fleet.CreateRack(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rack1)
			racks = append(racks, resp)
		}

		Convey("ListRacks - page_size negative", func() {
			req := &api.ListRacksRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListRacks(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListRacks - page_token invalid", func() {
			req := &api.ListRacksRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListRacks(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListRacks - Full listing Max PageSize", func() {
			req := &api.ListRacksRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListRacks(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Racks, ShouldResembleProto, racks)
		})

		Convey("ListRacks - Full listing with no pagination", func() {
			req := &api.ListRacksRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListRacks(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Racks, ShouldResembleProto, racks)
		})

		Convey("ListRacks - listing with pagination", func() {
			req := &api.ListRacksRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListRacks(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Racks, ShouldResembleProto, racks[:3])

			req = &api.ListRacksRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListRacks(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Racks, ShouldResembleProto, racks[3:])
		})
	})
}

func TestDeleteRack(t *testing.T) {
	t.Parallel()
	Convey("DeleteRack", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		rack1 := mockRack("", 10)
		req := &api.CreateRackRequest{
			Rack:   rack1,
			RackId: "rack-1",
		}
		resp, err := tf.Fleet.CreateRack(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, rack1)
		Convey("Delete rack by existing ID", func() {
			req := &api.DeleteRackRequest{
				Name: util.AddPrefix(util.RackCollection, "rack-1"),
			}
			_, err := tf.Fleet.DeleteRack(tf.C, req)
			So(err, ShouldBeNil)
			greq := &api.GetRackRequest{
				Name: util.AddPrefix(util.RackCollection, "rack-1"),
			}
			res, err := tf.Fleet.GetRack(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete rack by non-existing ID", func() {
			req := &api.DeleteRackRequest{
				Name: util.AddPrefix(util.RackCollection, "rack-2"),
			}
			_, err := tf.Fleet.DeleteRack(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete rack - Invalid input empty name", func() {
			req := &api.DeleteRackRequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Delete rack - Invalid input invalid characters", func() {
			req := &api.DeleteRackRequest{
				Name: util.AddPrefix(util.RackCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteRack(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestCreateNic(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	nic1 := mockNic("")
	nic2 := mockNic("")
	nic3 := mockNic("")
	Convey("CreateNic", t, func() {
		Convey("Create new nic with nic_id", func() {
			req := &api.CreateNicRequest{
				Nic:   nic1,
				NicId: "Nic-1",
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, nic1)
		})

		Convey("Create existing nic", func() {
			req := &api.CreateNicRequest{
				Nic:   nic3,
				NicId: "Nic-1",
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new nic - Invalid input nil", func() {
			req := &api.CreateNicRequest{
				Nic: nil,
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new nic - Invalid input empty ID", func() {
			req := &api.CreateNicRequest{
				Nic:   nic2,
				NicId: "",
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new nic - Invalid input invalid characters", func() {
			req := &api.CreateNicRequest{
				Nic:   nic2,
				NicId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateNic(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	nic1 := mockNic("")
	nic2 := mockNic("nic-1")
	nic3 := mockNic("nic-3")
	nic4 := mockNic("a.b)7&")
	Convey("UpdateNic", t, func() {
		Convey("Update existing nic", func() {
			req := &api.CreateNicRequest{
				Nic:   nic1,
				NicId: "nic-1",
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, nic1)
			ureq := &api.UpdateNicRequest{
				Nic: nic2,
			}
			resp, err = tf.Fleet.UpdateNic(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, nic2)
		})

		Convey("Update non-existing nic", func() {
			ureq := &api.UpdateNicRequest{
				Nic: nic3,
			}
			resp, err := tf.Fleet.UpdateNic(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update nic - Invalid input nil", func() {
			req := &api.UpdateNicRequest{
				Nic: nil,
			}
			resp, err := tf.Fleet.UpdateNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update nic - Invalid input empty name", func() {
			nic3.Name = ""
			req := &api.UpdateNicRequest{
				Nic: nic3,
			}
			resp, err := tf.Fleet.UpdateNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update nic - Invalid input invalid characters", func() {
			req := &api.UpdateNicRequest{
				Nic: nic4,
			}
			resp, err := tf.Fleet.UpdateNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetNic(t *testing.T) {
	t.Parallel()
	Convey("GetNic", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		nic1 := mockNic("nic-1")
		req := &api.CreateNicRequest{
			Nic:   nic1,
			NicId: "nic-1",
		}
		resp, err := tf.Fleet.CreateNic(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, nic1)
		Convey("Get nic by existing ID", func() {
			req := &api.GetNicRequest{
				Name: util.AddPrefix(util.NicCollection, "nic-1"),
			}
			resp, err := tf.Fleet.GetNic(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, nic1)
		})
		Convey("Get nic by non-existing ID", func() {
			req := &api.GetNicRequest{
				Name: util.AddPrefix(util.NicCollection, "nic-2"),
			}
			resp, err := tf.Fleet.GetNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get nic - Invalid input empty name", func() {
			req := &api.GetNicRequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get nic - Invalid input invalid characters", func() {
			req := &api.GetNicRequest{
				Name: util.AddPrefix(util.NicCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListNics(t *testing.T) {
	t.Parallel()
	Convey("ListNics", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		nics := make([]*proto.Nic, 0, 4)
		for i := 0; i < 4; i++ {
			nic1 := mockNic("")
			req := &api.CreateNicRequest{
				Nic:   nic1,
				NicId: fmt.Sprintf("nic-%d", i),
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, nic1)
			nics = append(nics, resp)
		}

		Convey("ListNics - page_size negative", func() {
			req := &api.ListNicsRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListNics(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListNics - page_token invalid", func() {
			req := &api.ListNicsRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListNics(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListNics - Full listing Max PageSize", func() {
			req := &api.ListNicsRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListNics(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Nics, ShouldResembleProto, nics)
		})

		Convey("ListNics - Full listing with no pagination", func() {
			req := &api.ListNicsRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListNics(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Nics, ShouldResembleProto, nics)
		})

		Convey("ListNics - listing with pagination", func() {
			req := &api.ListNicsRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListNics(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Nics, ShouldResembleProto, nics[:3])

			req = &api.ListNicsRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListNics(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Nics, ShouldResembleProto, nics[3:])
		})
	})
}

func TestDeleteNic(t *testing.T) {
	t.Parallel()
	Convey("DeleteNic", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		Convey("Delete nic by existing ID with machine reference", func() {
			nic1 := mockNic("")
			req := &api.CreateNicRequest{
				Nic:   nic1,
				NicId: "nic-1",
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, nic1)

			chromeBrowserMachine1 := &proto.Machine{
				Name: util.AddPrefix(util.MachineCollection, "machine-1"),
				Device: &proto.Machine_ChromeBrowserMachine{
					ChromeBrowserMachine: &proto.ChromeBrowserMachine{
						Nic: "nic-1",
					},
				},
			}
			mreq := &api.CreateMachineRequest{
				Machine:   chromeBrowserMachine1,
				MachineId: "machine-1",
			}
			mresp, merr := tf.Fleet.CreateMachine(tf.C, mreq)
			So(merr, ShouldBeNil)
			So(mresp, ShouldResembleProto, chromeBrowserMachine1)

			dreq := &api.DeleteNicRequest{
				Name: util.AddPrefix(util.NicCollection, "nic-1"),
			}
			_, err = tf.Fleet.DeleteNic(tf.C, dreq)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, CannotDelete)

			greq := &api.GetNicRequest{
				Name: util.AddPrefix(util.NicCollection, "nic-1"),
			}
			res, err := tf.Fleet.GetNic(tf.C, greq)
			So(res, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(res, ShouldResembleProto, nic1)
		})

		Convey("Delete nic by existing ID without references", func() {
			nic2 := mockNic("")
			req := &api.CreateNicRequest{
				Nic:   nic2,
				NicId: "nic-2",
			}
			resp, err := tf.Fleet.CreateNic(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, nic2)

			dreq := &api.DeleteNicRequest{
				Name: util.AddPrefix(util.NicCollection, "nic-2"),
			}
			_, err = tf.Fleet.DeleteNic(tf.C, dreq)
			So(err, ShouldBeNil)

			greq := &api.GetNicRequest{
				Name: util.AddPrefix(util.NicCollection, "nic-2"),
			}
			res, err := tf.Fleet.GetNic(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete nic by non-existing ID", func() {
			req := &api.DeleteNicRequest{
				Name: util.AddPrefix(util.NicCollection, "nic-2"),
			}
			_, err := tf.Fleet.DeleteNic(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete nic - Invalid input empty name", func() {
			req := &api.DeleteNicRequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Delete nic - Invalid input invalid characters", func() {
			req := &api.DeleteNicRequest{
				Name: util.AddPrefix(util.NicCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteNic(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestImportNics(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	Convey("Import nics", t, func() {
		Convey("happy path", func() {
			req := &api.ImportNicsRequest{
				Source: &api.ImportNicsRequest_MachineDbSource{
					MachineDbSource: &api.MachineDBSource{
						Host: "fake_host",
					},
				},
			}
			res, err := tf.Fleet.ImportNics(ctx, req)
			So(err, ShouldBeNil)
			So(res.Code, ShouldEqual, code.Code_OK)
			nics, _, err := registration.ListNics(ctx, 100, "")
			So(err, ShouldBeNil)
			So(parseAssets(nics, "Name"), ShouldResemble, []string{"machine1-eth0", "machine2-eth0", "machine3-eth0"})
			dracs, _, err := registration.ListDracs(ctx, 100, "")
			So(err, ShouldBeNil)
			So(parseAssets(dracs, "Name"), ShouldResemble, []string{"machine1-drac"})
			dhcps, _, err := configuration.ListDHCPConfigs(ctx, 100, "")
			So(err, ShouldBeNil)
			So(parseAssets(dhcps, "Ip"), ShouldResemble, []string{"ip1.1", "ip1.2", "ip2", "ip3"})
		})
		// Invalid & Empty machines DB hosts are tested in TestImportMachines
		// Skip testing here
	})
}

func TestImportDatacenters(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	Convey("Import datacenters", t, func() {
		Convey("happy path", func() {
			req := &api.ImportDatacentersRequest{
				Source: &api.ImportDatacentersRequest_ConfigSource{
					ConfigSource: &api.ConfigSource{
						ConfigServiceName: "fake-service",
						FileName:          "fakeDatacenter.cfg",
					},
				},
			}
			res, err := tf.Fleet.ImportDatacenters(ctx, req)
			So(err, ShouldBeNil)
			So(res.Code, ShouldEqual, code.Code_OK)
			dhcps, _, err := configuration.ListDHCPConfigs(ctx, 100, "")
			So(err, ShouldBeNil)
			So(dhcps, ShouldHaveLength, 3)
			racks, _, err := registration.ListRacks(ctx, 100, "")
			So(err, ShouldBeNil)
			So(racks, ShouldHaveLength, 2)
			So(parseAssets(racks, "Name"), ShouldResemble, []string{"cr20", "cr22"})
			kvms, _, err := registration.ListKVMs(ctx, 100, "")
			So(err, ShouldBeNil)
			So(kvms, ShouldHaveLength, 3)
			So(parseAssets(kvms, "Name"), ShouldResemble, []string{"cr20-kvm1", "cr22-kvm1", "cr22-kvm2"})
			switches, _, err := registration.ListSwitches(ctx, 100, "")
			So(err, ShouldBeNil)
			So(switches, ShouldHaveLength, 4)
			So(parseAssets(switches, "Name"), ShouldResemble, []string{"eq017.atl97", "eq041.atl97", "eq050.atl97", "eq113.atl97"})
			rackLSEs, _, err := inventory.ListRackLSEs(ctx, 100, "")
			So(err, ShouldBeNil)
			So(rackLSEs, ShouldHaveLength, 2)
			rlse, err := inventory.QueryRackLSEByPropertyName(ctx, "rack_ids", "cr20", false)
			So(err, ShouldBeNil)
			So(rlse, ShouldHaveLength, 1)
			So(rlse[0].GetRackLsePrototype(), ShouldEqual, "browser-lab:normal")
			So(rlse[0].GetChromeBrowserRackLse().GetKvms(), ShouldResemble, []string{"cr20-kvm1"})
			So(rlse[0].GetChromeBrowserRackLse().GetSwitches(), ShouldResemble, []string{"eq017.atl97"})
		})
	})
}

func TestImportDatacenterConfigs(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	Convey("Import datacenter configs", t, func() {
		Convey("happy path", func() {
			dcs, err := tf.Fleet.ImportDatacenterConfigs(ctx)
			So(err, ShouldBeNil)
			So(dcs, ShouldResemble, []string{"dc1", "dc2", "dc3"})
		})
	})
}

func TestCreateKVM(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	KVM1 := mockKVM("")
	KVM2 := mockKVM("")
	KVM3 := mockKVM("")
	Convey("CreateKVM", t, func() {
		Convey("Create new KVM with KVM_id", func() {
			req := &api.CreateKVMRequest{
				KVM:   KVM1,
				KVMId: "KVM-1",
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, KVM1)
		})

		Convey("Create existing KVM", func() {
			req := &api.CreateKVMRequest{
				KVM:   KVM3,
				KVMId: "KVM-1",
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new KVM - Invalid input nil", func() {
			req := &api.CreateKVMRequest{
				KVM: nil,
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new KVM - Invalid input empty ID", func() {
			req := &api.CreateKVMRequest{
				KVM:   KVM2,
				KVMId: "",
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new KVM - Invalid input invalid characters", func() {
			req := &api.CreateKVMRequest{
				KVM:   KVM2,
				KVMId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateKVM(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	KVM1 := mockKVM("")
	KVM2 := mockKVM("KVM-1")
	KVM3 := mockKVM("KVM-3")
	KVM4 := mockKVM("a.b)7&")
	Convey("UpdateKVM", t, func() {
		Convey("Update existing KVM", func() {
			req := &api.CreateKVMRequest{
				KVM:   KVM1,
				KVMId: "KVM-1",
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, KVM1)
			ureq := &api.UpdateKVMRequest{
				KVM: KVM2,
			}
			resp, err = tf.Fleet.UpdateKVM(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, KVM2)
		})

		Convey("Update non-existing KVM", func() {
			ureq := &api.UpdateKVMRequest{
				KVM: KVM3,
			}
			resp, err := tf.Fleet.UpdateKVM(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update KVM - Invalid input nil", func() {
			req := &api.UpdateKVMRequest{
				KVM: nil,
			}
			resp, err := tf.Fleet.UpdateKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update KVM - Invalid input empty name", func() {
			KVM3.Name = ""
			req := &api.UpdateKVMRequest{
				KVM: KVM3,
			}
			resp, err := tf.Fleet.UpdateKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update KVM - Invalid input invalid characters", func() {
			req := &api.UpdateKVMRequest{
				KVM: KVM4,
			}
			resp, err := tf.Fleet.UpdateKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetKVM(t *testing.T) {
	t.Parallel()
	Convey("GetKVM", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		KVM1 := mockKVM("KVM-1")
		req := &api.CreateKVMRequest{
			KVM:   KVM1,
			KVMId: "KVM-1",
		}
		resp, err := tf.Fleet.CreateKVM(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, KVM1)
		Convey("Get KVM by existing ID", func() {
			req := &api.GetKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "KVM-1"),
			}
			resp, err := tf.Fleet.GetKVM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, KVM1)
		})
		Convey("Get KVM by non-existing ID", func() {
			req := &api.GetKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "KVM-2"),
			}
			resp, err := tf.Fleet.GetKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get KVM - Invalid input empty name", func() {
			req := &api.GetKVMRequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get KVM - Invalid input invalid characters", func() {
			req := &api.GetKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListKVMs(t *testing.T) {
	t.Parallel()
	Convey("ListKVMs", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		KVMs := make([]*proto.KVM, 0, 4)
		for i := 0; i < 4; i++ {
			KVM1 := mockKVM("")
			req := &api.CreateKVMRequest{
				KVM:   KVM1,
				KVMId: fmt.Sprintf("KVM-%d", i),
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, KVM1)
			KVMs = append(KVMs, resp)
		}

		Convey("ListKVMs - page_size negative", func() {
			req := &api.ListKVMsRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListKVMs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListKVMs - page_token invalid", func() {
			req := &api.ListKVMsRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListKVMs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListKVMs - Full listing Max PageSize", func() {
			req := &api.ListKVMsRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListKVMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.KVMs, ShouldResembleProto, KVMs)
		})

		Convey("ListKVMs - Full listing with no pagination", func() {
			req := &api.ListKVMsRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListKVMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.KVMs, ShouldResembleProto, KVMs)
		})

		Convey("ListKVMs - listing with pagination", func() {
			req := &api.ListKVMsRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListKVMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.KVMs, ShouldResembleProto, KVMs[:3])

			req = &api.ListKVMsRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListKVMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.KVMs, ShouldResembleProto, KVMs[3:])
		})
	})
}

func TestDeleteKVM(t *testing.T) {
	t.Parallel()
	Convey("DeleteKVM", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		Convey("Delete KVM by existing ID with machine reference", func() {
			KVM1 := mockKVM("")
			req := &api.CreateKVMRequest{
				KVM:   KVM1,
				KVMId: "KVM-1",
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, KVM1)

			chromeBrowserMachine1 := &proto.Machine{
				Name: util.AddPrefix(util.MachineCollection, "machine-1"),
				Device: &proto.Machine_ChromeBrowserMachine{
					ChromeBrowserMachine: &proto.ChromeBrowserMachine{
						KvmInterface: &proto.KVMInterface{
							Kvm: "KVM-1",
						},
					},
				},
			}
			mreq := &api.CreateMachineRequest{
				Machine:   chromeBrowserMachine1,
				MachineId: "machine-1",
			}
			mresp, merr := tf.Fleet.CreateMachine(tf.C, mreq)
			So(merr, ShouldBeNil)
			So(mresp, ShouldResembleProto, chromeBrowserMachine1)

			dreq := &api.DeleteKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "KVM-1"),
			}
			_, err = tf.Fleet.DeleteKVM(tf.C, dreq)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, CannotDelete)

			greq := &api.GetKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "KVM-1"),
			}
			res, err := tf.Fleet.GetKVM(tf.C, greq)
			So(res, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(res, ShouldResembleProto, KVM1)
		})

		Convey("Delete KVM by existing ID without references", func() {
			KVM2 := mockKVM("")
			req := &api.CreateKVMRequest{
				KVM:   KVM2,
				KVMId: "KVM-2",
			}
			resp, err := tf.Fleet.CreateKVM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, KVM2)

			dreq := &api.DeleteKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "KVM-2"),
			}
			_, err = tf.Fleet.DeleteKVM(tf.C, dreq)
			So(err, ShouldBeNil)

			greq := &api.GetKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "KVM-2"),
			}
			res, err := tf.Fleet.GetKVM(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete KVM by non-existing ID", func() {
			req := &api.DeleteKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "KVM-2"),
			}
			_, err := tf.Fleet.DeleteKVM(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete KVM - Invalid input empty name", func() {
			req := &api.DeleteKVMRequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Delete KVM - Invalid input invalid characters", func() {
			req := &api.DeleteKVMRequest{
				Name: util.AddPrefix(util.KVMCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteKVM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestCreateRPM(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	RPM1 := mockRPM("")
	RPM2 := mockRPM("")
	RPM3 := mockRPM("")
	Convey("CreateRPM", t, func() {
		Convey("Create new RPM with RPM_id", func() {
			req := &api.CreateRPMRequest{
				RPM:   RPM1,
				RPMId: "RPM-1",
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, RPM1)
		})

		Convey("Create existing RPM", func() {
			req := &api.CreateRPMRequest{
				RPM:   RPM3,
				RPMId: "RPM-1",
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new RPM - Invalid input nil", func() {
			req := &api.CreateRPMRequest{
				RPM: nil,
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new RPM - Invalid input empty ID", func() {
			req := &api.CreateRPMRequest{
				RPM:   RPM2,
				RPMId: "",
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new RPM - Invalid input invalid characters", func() {
			req := &api.CreateRPMRequest{
				RPM:   RPM2,
				RPMId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateRPM(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	RPM1 := mockRPM("")
	RPM2 := mockRPM("RPM-1")
	RPM3 := mockRPM("RPM-3")
	RPM4 := mockRPM("a.b)7&")
	Convey("UpdateRPM", t, func() {
		Convey("Update existing RPM", func() {
			req := &api.CreateRPMRequest{
				RPM:   RPM1,
				RPMId: "RPM-1",
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, RPM1)
			ureq := &api.UpdateRPMRequest{
				RPM: RPM2,
			}
			resp, err = tf.Fleet.UpdateRPM(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, RPM2)
		})

		Convey("Update non-existing RPM", func() {
			ureq := &api.UpdateRPMRequest{
				RPM: RPM3,
			}
			resp, err := tf.Fleet.UpdateRPM(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update RPM - Invalid input nil", func() {
			req := &api.UpdateRPMRequest{
				RPM: nil,
			}
			resp, err := tf.Fleet.UpdateRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update RPM - Invalid input empty name", func() {
			RPM3.Name = ""
			req := &api.UpdateRPMRequest{
				RPM: RPM3,
			}
			resp, err := tf.Fleet.UpdateRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update RPM - Invalid input invalid characters", func() {
			req := &api.UpdateRPMRequest{
				RPM: RPM4,
			}
			resp, err := tf.Fleet.UpdateRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetRPM(t *testing.T) {
	t.Parallel()
	Convey("GetRPM", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		RPM1 := mockRPM("RPM-1")
		req := &api.CreateRPMRequest{
			RPM:   RPM1,
			RPMId: "RPM-1",
		}
		resp, err := tf.Fleet.CreateRPM(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, RPM1)
		Convey("Get RPM by existing ID", func() {
			req := &api.GetRPMRequest{
				Name: util.AddPrefix(util.RPMCollection, "RPM-1"),
			}
			resp, err := tf.Fleet.GetRPM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, RPM1)
		})
		Convey("Get RPM by non-existing ID", func() {
			req := &api.GetRPMRequest{
				Name: util.AddPrefix(util.RPMCollection, "RPM-2"),
			}
			resp, err := tf.Fleet.GetRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get RPM - Invalid input empty name", func() {
			req := &api.GetRPMRequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get RPM - Invalid input invalid characters", func() {
			req := &api.GetRPMRequest{
				Name: util.AddPrefix(util.RPMCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListRPMs(t *testing.T) {
	t.Parallel()
	Convey("ListRPMs", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		RPMs := make([]*proto.RPM, 0, 4)
		for i := 0; i < 4; i++ {
			RPM1 := mockRPM("")
			req := &api.CreateRPMRequest{
				RPM:   RPM1,
				RPMId: fmt.Sprintf("RPM-%d", i),
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, RPM1)
			RPMs = append(RPMs, resp)
		}

		Convey("ListRPMs - page_size negative", func() {
			req := &api.ListRPMsRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListRPMs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListRPMs - page_token invalid", func() {
			req := &api.ListRPMsRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListRPMs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListRPMs - Full listing Max PageSize", func() {
			req := &api.ListRPMsRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListRPMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RPMs, ShouldResembleProto, RPMs)
		})

		Convey("ListRPMs - Full listing with no pagination", func() {
			req := &api.ListRPMsRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListRPMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RPMs, ShouldResembleProto, RPMs)
		})

		Convey("ListRPMs - listing with pagination", func() {
			req := &api.ListRPMsRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListRPMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RPMs, ShouldResembleProto, RPMs[:3])

			req = &api.ListRPMsRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListRPMs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RPMs, ShouldResembleProto, RPMs[3:])
		})
	})
}

func TestDeleteRPM(t *testing.T) {
	t.Parallel()
	Convey("DeleteRPM", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		Convey("Delete RPM by existing ID", func() {
			RPM2 := mockRPM("")
			req := &api.CreateRPMRequest{
				RPM:   RPM2,
				RPMId: "RPM-2",
			}
			resp, err := tf.Fleet.CreateRPM(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, RPM2)

			dreq := &api.DeleteRPMRequest{
				Name: util.AddPrefix(util.RPMCollection, "RPM-2"),
			}
			_, err = tf.Fleet.DeleteRPM(tf.C, dreq)
			So(err, ShouldBeNil)

			greq := &api.GetRPMRequest{
				Name: util.AddPrefix(util.RPMCollection, "RPM-2"),
			}
			res, err := tf.Fleet.GetRPM(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete RPM by non-existing ID", func() {
			req := &api.DeleteRPMRequest{
				Name: util.AddPrefix(util.RPMCollection, "RPM-2"),
			}
			_, err := tf.Fleet.DeleteRPM(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete RPM - Invalid input empty name", func() {
			req := &api.DeleteRPMRequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Delete RPM - Invalid input invalid characters", func() {
			req := &api.DeleteRPMRequest{
				Name: util.AddPrefix(util.RPMCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteRPM(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestCreateDrac(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	drac1 := mockDrac("")
	drac2 := mockDrac("")
	drac3 := mockDrac("")
	Convey("CreateDrac", t, func() {
		Convey("Create new drac with drac_id", func() {
			req := &api.CreateDracRequest{
				Drac:   drac1,
				DracId: "Drac-1",
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, drac1)
		})

		Convey("Create existing drac", func() {
			req := &api.CreateDracRequest{
				Drac:   drac3,
				DracId: "Drac-1",
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new drac - Invalid input nil", func() {
			req := &api.CreateDracRequest{
				Drac: nil,
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new drac - Invalid input empty ID", func() {
			req := &api.CreateDracRequest{
				Drac:   drac2,
				DracId: "",
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new drac - Invalid input invalid characters", func() {
			req := &api.CreateDracRequest{
				Drac:   drac2,
				DracId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateDrac(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	drac1 := mockDrac("")
	drac2 := mockDrac("drac-1")
	drac3 := mockDrac("drac-3")
	drac4 := mockDrac("a.b)7&")
	Convey("UpdateDrac", t, func() {
		Convey("Update existing drac", func() {
			req := &api.CreateDracRequest{
				Drac:   drac1,
				DracId: "drac-1",
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, drac1)
			ureq := &api.UpdateDracRequest{
				Drac: drac2,
			}
			resp, err = tf.Fleet.UpdateDrac(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, drac2)
		})

		Convey("Update non-existing drac", func() {
			ureq := &api.UpdateDracRequest{
				Drac: drac3,
			}
			resp, err := tf.Fleet.UpdateDrac(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update drac - Invalid input nil", func() {
			req := &api.UpdateDracRequest{
				Drac: nil,
			}
			resp, err := tf.Fleet.UpdateDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update drac - Invalid input empty name", func() {
			drac3.Name = ""
			req := &api.UpdateDracRequest{
				Drac: drac3,
			}
			resp, err := tf.Fleet.UpdateDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update drac - Invalid input invalid characters", func() {
			req := &api.UpdateDracRequest{
				Drac: drac4,
			}
			resp, err := tf.Fleet.UpdateDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetDrac(t *testing.T) {
	t.Parallel()
	Convey("GetDrac", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		drac1 := mockDrac("drac-1")
		req := &api.CreateDracRequest{
			Drac:   drac1,
			DracId: "drac-1",
		}
		resp, err := tf.Fleet.CreateDrac(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, drac1)
		Convey("Get drac by existing ID", func() {
			req := &api.GetDracRequest{
				Name: util.AddPrefix(util.DracCollection, "drac-1"),
			}
			resp, err := tf.Fleet.GetDrac(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, drac1)
		})
		Convey("Get drac by non-existing ID", func() {
			req := &api.GetDracRequest{
				Name: util.AddPrefix(util.DracCollection, "drac-2"),
			}
			resp, err := tf.Fleet.GetDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get drac - Invalid input empty name", func() {
			req := &api.GetDracRequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get drac - Invalid input invalid characters", func() {
			req := &api.GetDracRequest{
				Name: util.AddPrefix(util.DracCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListDracs(t *testing.T) {
	t.Parallel()
	Convey("ListDracs", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		dracs := make([]*proto.Drac, 0, 4)
		for i := 0; i < 4; i++ {
			drac1 := mockDrac("")
			req := &api.CreateDracRequest{
				Drac:   drac1,
				DracId: fmt.Sprintf("drac-%d", i),
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, drac1)
			dracs = append(dracs, resp)
		}

		Convey("ListDracs - page_size negative", func() {
			req := &api.ListDracsRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListDracs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListDracs - page_token invalid", func() {
			req := &api.ListDracsRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListDracs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListDracs - Full listing Max PageSize", func() {
			req := &api.ListDracsRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListDracs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Dracs, ShouldResembleProto, dracs)
		})

		Convey("ListDracs - Full listing with no pagination", func() {
			req := &api.ListDracsRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListDracs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Dracs, ShouldResembleProto, dracs)
		})

		Convey("ListDracs - listing with pagination", func() {
			req := &api.ListDracsRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListDracs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Dracs, ShouldResembleProto, dracs[:3])

			req = &api.ListDracsRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListDracs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Dracs, ShouldResembleProto, dracs[3:])
		})
	})
}

func TestDeleteDrac(t *testing.T) {
	t.Parallel()
	Convey("DeleteDrac", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		Convey("Delete drac by existing ID with machine reference", func() {
			drac1 := mockDrac("")
			req := &api.CreateDracRequest{
				Drac:   drac1,
				DracId: "drac-1",
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, drac1)

			chromeBrowserMachine1 := &proto.Machine{
				Name: util.AddPrefix(util.MachineCollection, "machine-1"),
				Device: &proto.Machine_ChromeBrowserMachine{
					ChromeBrowserMachine: &proto.ChromeBrowserMachine{
						Drac: "drac-1",
					},
				},
			}
			mreq := &api.CreateMachineRequest{
				Machine:   chromeBrowserMachine1,
				MachineId: "machine-1",
			}
			mresp, merr := tf.Fleet.CreateMachine(tf.C, mreq)
			So(merr, ShouldBeNil)
			So(mresp, ShouldResembleProto, chromeBrowserMachine1)

			dreq := &api.DeleteDracRequest{
				Name: util.AddPrefix(util.DracCollection, "drac-1"),
			}
			_, err = tf.Fleet.DeleteDrac(tf.C, dreq)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, CannotDelete)

			greq := &api.GetDracRequest{
				Name: util.AddPrefix(util.DracCollection, "drac-1"),
			}
			res, err := tf.Fleet.GetDrac(tf.C, greq)
			So(res, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(res, ShouldResembleProto, drac1)
		})

		Convey("Delete drac by existing ID without references", func() {
			drac2 := mockDrac("")
			req := &api.CreateDracRequest{
				Drac:   drac2,
				DracId: "drac-2",
			}
			resp, err := tf.Fleet.CreateDrac(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, drac2)

			dreq := &api.DeleteDracRequest{
				Name: util.AddPrefix(util.DracCollection, "drac-2"),
			}
			_, err = tf.Fleet.DeleteDrac(tf.C, dreq)
			So(err, ShouldBeNil)

			greq := &api.GetDracRequest{
				Name: util.AddPrefix(util.DracCollection, "drac-2"),
			}
			res, err := tf.Fleet.GetDrac(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete drac by non-existing ID", func() {
			req := &api.DeleteDracRequest{
				Name: util.AddPrefix(util.DracCollection, "drac-2"),
			}
			_, err := tf.Fleet.DeleteDrac(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete drac - Invalid input empty name", func() {
			req := &api.DeleteDracRequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Delete drac - Invalid input invalid characters", func() {
			req := &api.DeleteDracRequest{
				Name: util.AddPrefix(util.DracCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteDrac(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestCreateSwitch(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	switch1 := mockSwitch("")
	switch2 := mockSwitch("")
	switch3 := mockSwitch("")
	Convey("CreateSwitch", t, func() {
		Convey("Create new switch with switch_id", func() {
			req := &api.CreateSwitchRequest{
				Switch:   switch1,
				SwitchId: "Switch-1",
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, switch1)
		})

		Convey("Create existing switch", func() {
			req := &api.CreateSwitchRequest{
				Switch:   switch3,
				SwitchId: "Switch-1",
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new switch - Invalid input nil", func() {
			req := &api.CreateSwitchRequest{
				Switch: nil,
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new switch - Invalid input empty ID", func() {
			req := &api.CreateSwitchRequest{
				Switch:   switch2,
				SwitchId: "",
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new switch - Invalid input invalid characters", func() {
			req := &api.CreateSwitchRequest{
				Switch:   switch2,
				SwitchId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateSwitch(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	switch1 := mockSwitch("")
	switch2 := mockSwitch("switch-1")
	switch3 := mockSwitch("switch-3")
	switch4 := mockSwitch("a.b)7&")
	Convey("UpdateSwitch", t, func() {
		Convey("Update existing switch", func() {
			req := &api.CreateSwitchRequest{
				Switch:   switch1,
				SwitchId: "switch-1",
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, switch1)
			ureq := &api.UpdateSwitchRequest{
				Switch: switch2,
			}
			resp, err = tf.Fleet.UpdateSwitch(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, switch2)
		})

		Convey("Update non-existing switch", func() {
			ureq := &api.UpdateSwitchRequest{
				Switch: switch3,
			}
			resp, err := tf.Fleet.UpdateSwitch(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update switch - Invalid input nil", func() {
			req := &api.UpdateSwitchRequest{
				Switch: nil,
			}
			resp, err := tf.Fleet.UpdateSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update switch - Invalid input empty name", func() {
			switch3.Name = ""
			req := &api.UpdateSwitchRequest{
				Switch: switch3,
			}
			resp, err := tf.Fleet.UpdateSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update switch - Invalid input invalid characters", func() {
			req := &api.UpdateSwitchRequest{
				Switch: switch4,
			}
			resp, err := tf.Fleet.UpdateSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetSwitch(t *testing.T) {
	t.Parallel()
	Convey("GetSwitch", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		switch1 := mockSwitch("switch-1")
		req := &api.CreateSwitchRequest{
			Switch:   switch1,
			SwitchId: "switch-1",
		}
		resp, err := tf.Fleet.CreateSwitch(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, switch1)
		Convey("Get switch by existing ID", func() {
			req := &api.GetSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "switch-1"),
			}
			resp, err := tf.Fleet.GetSwitch(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, switch1)
		})
		Convey("Get switch by non-existing ID", func() {
			req := &api.GetSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "switch-2"),
			}
			resp, err := tf.Fleet.GetSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get switch - Invalid input empty name", func() {
			req := &api.GetSwitchRequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get switch - Invalid input invalid characters", func() {
			req := &api.GetSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListSwitches(t *testing.T) {
	t.Parallel()
	Convey("ListSwitches", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		switches := make([]*proto.Switch, 0, 4)
		for i := 0; i < 4; i++ {
			switch1 := mockSwitch("")
			req := &api.CreateSwitchRequest{
				Switch:   switch1,
				SwitchId: fmt.Sprintf("switch-%d", i),
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, switch1)
			switches = append(switches, resp)
		}

		Convey("ListSwitches - page_size negative", func() {
			req := &api.ListSwitchesRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListSwitches(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListSwitches - page_token invalid", func() {
			req := &api.ListSwitchesRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListSwitches(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListSwitches - Full listing Max PageSize", func() {
			req := &api.ListSwitchesRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListSwitches(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Switches, ShouldResembleProto, switches)
		})

		Convey("ListSwitches - Full listing with no pagination", func() {
			req := &api.ListSwitchesRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListSwitches(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Switches, ShouldResembleProto, switches)
		})

		Convey("ListSwitches - listing with pagination", func() {
			req := &api.ListSwitchesRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListSwitches(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Switches, ShouldResembleProto, switches[:3])

			req = &api.ListSwitchesRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListSwitches(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.Switches, ShouldResembleProto, switches[3:])
		})
	})
}

func TestDeleteSwitch(t *testing.T) {
	t.Parallel()
	Convey("DeleteSwitch", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		Convey("Delete switch by existing ID with machine reference", func() {
			switch1 := mockSwitch("")
			req := &api.CreateSwitchRequest{
				Switch:   switch1,
				SwitchId: "switch-1",
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, switch1)

			chromeBrowserMachine1 := &proto.Machine{
				Name: "machine-1",
				Device: &proto.Machine_ChromeBrowserMachine{
					ChromeBrowserMachine: &proto.ChromeBrowserMachine{
						NetworkDeviceInterface: &proto.SwitchInterface{
							Switch: "switch-1",
						},
					},
				},
			}
			mreq := &api.CreateMachineRequest{
				Machine:   chromeBrowserMachine1,
				MachineId: "machine-1",
			}
			mresp, merr := tf.Fleet.CreateMachine(tf.C, mreq)
			So(merr, ShouldBeNil)
			So(mresp, ShouldResembleProto, chromeBrowserMachine1)

			dreq := &api.DeleteSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "switch-1"),
			}
			_, err = tf.Fleet.DeleteSwitch(tf.C, dreq)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, CannotDelete)

			greq := &api.GetSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "switch-1"),
			}
			res, err := tf.Fleet.GetSwitch(tf.C, greq)
			So(res, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(res, ShouldResembleProto, switch1)
		})

		Convey("Delete switch by existing ID without references", func() {
			switch2 := mockSwitch("")
			req := &api.CreateSwitchRequest{
				Switch:   switch2,
				SwitchId: "switch-2",
			}
			resp, err := tf.Fleet.CreateSwitch(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, switch2)

			dreq := &api.DeleteSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "switch-2"),
			}
			_, err = tf.Fleet.DeleteSwitch(tf.C, dreq)
			So(err, ShouldBeNil)

			greq := &api.GetSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "switch-2"),
			}
			res, err := tf.Fleet.GetSwitch(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete switch by non-existing ID", func() {
			req := &api.DeleteSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "switch-2"),
			}
			_, err := tf.Fleet.DeleteSwitch(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Delete switch - Invalid input empty name", func() {
			req := &api.DeleteSwitchRequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Delete switch - Invalid input invalid characters", func() {
			req := &api.DeleteSwitchRequest{
				Name: util.AddPrefix(util.SwitchCollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteSwitch(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func parseAssets(args interface{}, k string) []string {
	names := make([]string, 0)
	v := reflect.ValueOf(args)
	switch v.Kind() {
	case reflect.Ptr:
		names = append(names, parse(v.Elem(), k))
	case reflect.Slice:
		for i := 0; i < v.Len(); i++ {
			n := parse(v.Index(i).Elem(), k)
			if n != "" {
				names = append(names, n)
			}
		}
	}
	return names
}

func parse(v reflect.Value, k string) string {
	typeOfT := v.Type()
	for i := 0; i < v.NumField(); i++ {
		f := v.Field(i)
		if typeOfT.Field(i).Name == k {
			return f.Interface().(string)
		}
	}
	return ""
}

func getCapacity(cidr string) float64 {
	cover := strings.Split(cidr, "/")[1]
	coverN, err := strconv.Atoi(cover)
	if err != nil {
		return 0
	}
	return math.Exp2(32 - float64(coverN))
}
