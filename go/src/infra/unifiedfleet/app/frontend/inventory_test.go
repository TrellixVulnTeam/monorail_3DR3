// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"strconv"
	"testing"

	proto "infra/unifiedfleet/api/v1/proto"
	api "infra/unifiedfleet/api/v1/rpc"
	"infra/unifiedfleet/app/model/configuration"
	. "infra/unifiedfleet/app/model/datastore"
	"infra/unifiedfleet/app/model/inventory"
	"infra/unifiedfleet/app/util"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
	code "google.golang.org/genproto/googleapis/rpc/code"
)

func mockMachineLSE(id string) *proto.MachineLSE {
	return &proto.MachineLSE{
		Name: util.AddPrefix(util.MachineLSECollection, id),
	}
}

func mockRackLSE(id string) *proto.RackLSE {
	return &proto.RackLSE{
		Name: util.AddPrefix(util.RackLSECollection, id),
	}
}

func TestCreateMachineLSE(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	machineLSE1 := mockMachineLSE("machineLSE-1")
	machineLSE2 := mockMachineLSE("machineLSE-2")
	Convey("CreateMachineLSEs", t, func() {
		Convey("Create new machineLSE with machineLSE_id", func() {
			req := &api.CreateMachineLSERequest{
				MachineLSE:   machineLSE1,
				MachineLSEId: "machineLSE-1",
			}
			resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, machineLSE1)
		})

		Convey("Create existing machineLSEs", func() {
			req := &api.CreateMachineLSERequest{
				MachineLSE:   machineLSE1,
				MachineLSEId: "machineLSE-1",
			}
			resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new machineLSE - Invalid input nil", func() {
			req := &api.CreateMachineLSERequest{
				MachineLSE: nil,
			}
			resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new machineLSE - Invalid input empty ID", func() {
			req := &api.CreateMachineLSERequest{
				MachineLSE:   machineLSE2,
				MachineLSEId: "",
			}
			resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new machineLSE - Invalid input invalid characters", func() {
			req := &api.CreateMachineLSERequest{
				MachineLSE:   machineLSE2,
				MachineLSEId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateMachineLSE(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	machineLSE1 := mockMachineLSE("machineLSE-1")
	machineLSE2 := mockMachineLSE("machineLSE-1")
	machineLSE2.Hostname = "Linux Server"
	machineLSE3 := mockMachineLSE("machineLSE-3")
	machineLSE4 := mockMachineLSE("")
	machineLSE5 := mockMachineLSE("a.b)7&")
	Convey("UpdateMachineLSEs", t, func() {
		Convey("Update existing machineLSEs", func() {
			req := &api.CreateMachineLSERequest{
				MachineLSE:   machineLSE1,
				MachineLSEId: "machineLSE-1",
			}
			resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, machineLSE1)
			ureq := &api.UpdateMachineLSERequest{
				MachineLSE: machineLSE2,
			}
			resp, err = tf.Fleet.UpdateMachineLSE(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, machineLSE2)
		})

		Convey("Update non-existing machineLSEs", func() {
			ureq := &api.UpdateMachineLSERequest{
				MachineLSE: machineLSE3,
			}
			resp, err := tf.Fleet.UpdateMachineLSE(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update machineLSE - Invalid input nil", func() {
			req := &api.UpdateMachineLSERequest{
				MachineLSE: nil,
			}
			resp, err := tf.Fleet.UpdateMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update machineLSE - Invalid input empty name", func() {
			machineLSE4.Name = ""
			req := &api.UpdateMachineLSERequest{
				MachineLSE: machineLSE4,
			}
			resp, err := tf.Fleet.UpdateMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update machineLSE - Invalid input invalid characters", func() {
			req := &api.UpdateMachineLSERequest{
				MachineLSE: machineLSE5,
			}
			resp, err := tf.Fleet.UpdateMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetMachineLSE(t *testing.T) {
	t.Parallel()
	Convey("GetMachineLSE", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		machineLSE1 := mockMachineLSE("machineLSE-1")
		req := &api.CreateMachineLSERequest{
			MachineLSE:   machineLSE1,
			MachineLSEId: "machineLSE-1",
		}
		resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, machineLSE1)
		Convey("Get machineLSE by existing ID", func() {
			req := &api.GetMachineLSERequest{
				Name: util.AddPrefix(util.MachineLSECollection, "machineLSE-1"),
			}
			resp, err := tf.Fleet.GetMachineLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, machineLSE1)
		})
		Convey("Get machineLSE by non-existing ID", func() {
			req := &api.GetMachineLSERequest{
				Name: util.AddPrefix(util.MachineLSECollection, "machineLSE-2"),
			}
			resp, err := tf.Fleet.GetMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get machineLSE - Invalid input empty name", func() {
			req := &api.GetMachineLSERequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get machineLSE - Invalid input invalid characters", func() {
			req := &api.GetMachineLSERequest{
				Name: util.AddPrefix(util.MachineLSECollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListMachineLSEs(t *testing.T) {
	t.Parallel()
	Convey("ListMachineLSEs", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		machineLSEs := make([]*proto.MachineLSE, 0, 4)
		for i := 0; i < 4; i++ {
			machineLSE1 := mockMachineLSE("machineLSE-1")
			req := &api.CreateMachineLSERequest{
				MachineLSE:   machineLSE1,
				MachineLSEId: fmt.Sprintf("machineLSE-%d", i),
			}
			resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, machineLSE1)
			machineLSEs = append(machineLSEs, resp)
		}

		Convey("ListMachineLSEs - page_size negative", func() {
			req := &api.ListMachineLSEsRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListMachineLSEs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListMachineLSEs - page_token invalid", func() {
			req := &api.ListMachineLSEsRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListMachineLSEs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListMachineLSEs - Full listing Max PageSize", func() {
			req := &api.ListMachineLSEsRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListMachineLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.MachineLSEs, ShouldResembleProto, machineLSEs)
		})

		Convey("ListMachineLSEs - Full listing with no pagination", func() {
			req := &api.ListMachineLSEsRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListMachineLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.MachineLSEs, ShouldResembleProto, machineLSEs)
		})

		Convey("ListMachineLSEs - listing with pagination", func() {
			req := &api.ListMachineLSEsRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListMachineLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.MachineLSEs, ShouldResembleProto, machineLSEs[:3])

			req = &api.ListMachineLSEsRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListMachineLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.MachineLSEs, ShouldResembleProto, machineLSEs[3:])
		})
	})
}

func TestDeleteMachineLSE(t *testing.T) {
	t.Parallel()
	Convey("DeleteMachineLSE", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		machineLSE1 := mockMachineLSE("")
		req := &api.CreateMachineLSERequest{
			MachineLSE:   machineLSE1,
			MachineLSEId: "machineLSE-1",
		}
		resp, err := tf.Fleet.CreateMachineLSE(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, machineLSE1)
		Convey("Delete machineLSE by existing ID", func() {
			req := &api.DeleteMachineLSERequest{
				Name: util.AddPrefix(util.MachineLSECollection, "machineLSE-1"),
			}
			_, err := tf.Fleet.DeleteMachineLSE(tf.C, req)
			So(err, ShouldBeNil)
			greq := &api.GetMachineLSERequest{
				Name: util.AddPrefix(util.MachineLSECollection, "machineLSE-1"),
			}
			res, err := tf.Fleet.GetMachineLSE(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete machineLSE by non-existing ID", func() {
			req := &api.DeleteMachineLSERequest{
				Name: util.AddPrefix(util.MachineLSECollection, "machineLSE-2"),
			}
			_, err := tf.Fleet.DeleteMachineLSE(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete machineLSE - Invalid input empty name", func() {
			req := &api.DeleteMachineLSERequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Delete machineLSE - Invalid input invalid characters", func() {
			req := &api.DeleteMachineLSERequest{
				Name: util.AddPrefix(util.MachineLSECollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteMachineLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestCreateRackLSE(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	rackLSE1 := mockRackLSE("rackLSE-1")
	rackLSE2 := mockRackLSE("rackLSE-2")
	Convey("CreateRackLSEs", t, func() {
		Convey("Create new rackLSE with rackLSE_id", func() {
			req := &api.CreateRackLSERequest{
				RackLSE:   rackLSE1,
				RackLSEId: "rackLSE-1",
			}
			resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rackLSE1)
		})

		Convey("Create existing rackLSEs", func() {
			req := &api.CreateRackLSERequest{
				RackLSE:   rackLSE1,
				RackLSEId: "rackLSE-1",
			}
			resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, AlreadyExists)
		})

		Convey("Create new rackLSE - Invalid input nil", func() {
			req := &api.CreateRackLSERequest{
				RackLSE: nil,
			}
			resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Create new rackLSE - Invalid input empty ID", func() {
			req := &api.CreateRackLSERequest{
				RackLSE:   rackLSE2,
				RackLSEId: "",
			}
			resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyID)
		})

		Convey("Create new rackLSE - Invalid input invalid characters", func() {
			req := &api.CreateRackLSERequest{
				RackLSE:   rackLSE2,
				RackLSEId: "a.b)7&",
			}
			resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestUpdateRackLSE(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	rackLSE1 := mockRackLSE("rackLSE-1")
	rackLSE2 := mockRackLSE("rackLSE-1")
	rackLSE3 := mockRackLSE("rackLSE-3")
	rackLSE4 := mockRackLSE("")
	rackLSE5 := mockRackLSE("a.b)7&")
	Convey("UpdateRackLSEs", t, func() {
		Convey("Update existing rackLSEs", func() {
			req := &api.CreateRackLSERequest{
				RackLSE:   rackLSE1,
				RackLSEId: "rackLSE-1",
			}
			resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rackLSE1)
			ureq := &api.UpdateRackLSERequest{
				RackLSE: rackLSE2,
			}
			resp, err = tf.Fleet.UpdateRackLSE(tf.C, ureq)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rackLSE2)
		})

		Convey("Update non-existing rackLSEs", func() {
			ureq := &api.UpdateRackLSERequest{
				RackLSE: rackLSE3,
			}
			resp, err := tf.Fleet.UpdateRackLSE(tf.C, ureq)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})

		Convey("Update rackLSE - Invalid input nil", func() {
			req := &api.UpdateRackLSERequest{
				RackLSE: nil,
			}
			resp, err := tf.Fleet.UpdateRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.NilEntity)
		})

		Convey("Update rackLSE - Invalid input empty name", func() {
			rackLSE4.Name = ""
			req := &api.UpdateRackLSERequest{
				RackLSE: rackLSE4,
			}
			resp, err := tf.Fleet.UpdateRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})

		Convey("Update rackLSE - Invalid input invalid characters", func() {
			req := &api.UpdateRackLSERequest{
				RackLSE: rackLSE5,
			}
			resp, err := tf.Fleet.UpdateRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestGetRackLSE(t *testing.T) {
	t.Parallel()
	Convey("GetRackLSE", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		rackLSE1 := mockRackLSE("rackLSE-1")
		req := &api.CreateRackLSERequest{
			RackLSE:   rackLSE1,
			RackLSEId: "rackLSE-1",
		}
		resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, rackLSE1)
		Convey("Get rackLSE by existing ID", func() {
			req := &api.GetRackLSERequest{
				Name: util.AddPrefix(util.RackLSECollection, "rackLSE-1"),
			}
			resp, err := tf.Fleet.GetRackLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rackLSE1)
		})
		Convey("Get rackLSE by non-existing ID", func() {
			req := &api.GetRackLSERequest{
				Name: util.AddPrefix(util.RackLSECollection, "rackLSE-2"),
			}
			resp, err := tf.Fleet.GetRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Get rackLSE - Invalid input empty name", func() {
			req := &api.GetRackLSERequest{
				Name: "",
			}
			resp, err := tf.Fleet.GetRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Get rackLSE - Invalid input invalid characters", func() {
			req := &api.GetRackLSERequest{
				Name: util.AddPrefix(util.RackLSECollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.GetRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestListRackLSEs(t *testing.T) {
	t.Parallel()
	Convey("ListRackLSEs", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		rackLSEs := make([]*proto.RackLSE, 0, 4)
		for i := 0; i < 4; i++ {
			rackLSE1 := mockRackLSE("rackLSE-1")
			req := &api.CreateRackLSERequest{
				RackLSE:   rackLSE1,
				RackLSEId: fmt.Sprintf("rackLSE-%d", i),
			}
			resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldResembleProto, rackLSE1)
			rackLSEs = append(rackLSEs, resp)
		}

		Convey("ListRackLSEs - page_size negative", func() {
			req := &api.ListRackLSEsRequest{
				PageSize: -5,
			}
			resp, err := tf.Fleet.ListRackLSEs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidPageSize)
		})

		Convey("ListRackLSEs - page_token invalid", func() {
			req := &api.ListRackLSEsRequest{
				PageSize:  5,
				PageToken: "abc",
			}
			resp, err := tf.Fleet.ListRackLSEs(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, InvalidPageToken)
		})

		Convey("ListRackLSEs - Full listing Max PageSize", func() {
			req := &api.ListRackLSEsRequest{
				PageSize: 2000,
			}
			resp, err := tf.Fleet.ListRackLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RackLSEs, ShouldResembleProto, rackLSEs)
		})

		Convey("ListRackLSEs - Full listing with no pagination", func() {
			req := &api.ListRackLSEsRequest{
				PageSize: 0,
			}
			resp, err := tf.Fleet.ListRackLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RackLSEs, ShouldResembleProto, rackLSEs)
		})

		Convey("ListRackLSEs - listing with pagination", func() {
			req := &api.ListRackLSEsRequest{
				PageSize: 3,
			}
			resp, err := tf.Fleet.ListRackLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RackLSEs, ShouldResembleProto, rackLSEs[:3])

			req = &api.ListRackLSEsRequest{
				PageSize:  3,
				PageToken: resp.NextPageToken,
			}
			resp, err = tf.Fleet.ListRackLSEs(tf.C, req)
			So(resp, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(resp.RackLSEs, ShouldResembleProto, rackLSEs[3:])
		})
	})
}

func TestDeleteRackLSE(t *testing.T) {
	t.Parallel()
	Convey("DeleteRackLSE", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		rackLSE1 := mockRackLSE("")
		req := &api.CreateRackLSERequest{
			RackLSE:   rackLSE1,
			RackLSEId: "rackLSE-1",
		}
		resp, err := tf.Fleet.CreateRackLSE(tf.C, req)
		So(err, ShouldBeNil)
		So(resp, ShouldResembleProto, rackLSE1)
		Convey("Delete rackLSE by existing ID", func() {
			req := &api.DeleteRackLSERequest{
				Name: util.AddPrefix(util.RackLSECollection, "rackLSE-1"),
			}
			_, err := tf.Fleet.DeleteRackLSE(tf.C, req)
			So(err, ShouldBeNil)
			greq := &api.GetRackLSERequest{
				Name: util.AddPrefix(util.RackLSECollection, "rackLSE-1"),
			}
			res, err := tf.Fleet.GetRackLSE(tf.C, greq)
			So(res, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete rackLSE by non-existing ID", func() {
			req := &api.DeleteRackLSERequest{
				Name: util.AddPrefix(util.RackLSECollection, "rackLSE-2"),
			}
			_, err := tf.Fleet.DeleteRackLSE(tf.C, req)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, NotFound)
		})
		Convey("Delete rackLSE - Invalid input empty name", func() {
			req := &api.DeleteRackLSERequest{
				Name: "",
			}
			resp, err := tf.Fleet.DeleteRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.EmptyName)
		})
		Convey("Delete rackLSE - Invalid input invalid characters", func() {
			req := &api.DeleteRackLSERequest{
				Name: util.AddPrefix(util.RackLSECollection, "a.b)7&"),
			}
			resp, err := tf.Fleet.DeleteRackLSE(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, api.InvalidCharacters)
		})
	})
}

func TestImportMachineLSEs(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	Convey("Import machine lses", t, func() {
		Convey("happy path", func() {
			req := &api.ImportMachineLSEsRequest{
				Source: &api.ImportMachineLSEsRequest_MachineDbSource{
					MachineDbSource: &api.MachineDBSource{
						Host: "fake_host",
					},
				},
			}
			tf.Fleet.importPageSize = 25
			res, err := tf.Fleet.ImportMachineLSEs(ctx, req)
			So(err, ShouldBeNil)
			So(res.Code, ShouldEqual, code.Code_OK)

			// Verify machine lse prototypes
			lps, _, err := configuration.ListMachineLSEPrototypes(ctx, 100, "")
			So(err, ShouldBeNil)
			So(parseAssets(lps, "Name"), ShouldResemble, []string{"browser-lab:no-vm", "browser-lab:vm"})

			// Verify machine lses
			machineLSEs, _, err := inventory.ListMachineLSEs(ctx, 100, "")
			So(err, ShouldBeNil)
			So(parseAssets(machineLSEs, "Name"), ShouldResemble, []string{"esx-8", "web"})
			lse, err := inventory.QueryMachineLSEByPropertyName(ctx, "machine_ids", "machine1", false)
			So(err, ShouldBeNil)
			So(lse, ShouldHaveLength, 1)
			So(lse[0].GetMachineLsePrototype(), ShouldEqual, "browser-lab:vm")
			So(lse[0].GetHostname(), ShouldEqual, "esx-8")
			So(lse[0].GetChromeBrowserMachineLse().GetVms(), ShouldHaveLength, 1)
			So(lse[0].GetChromeBrowserMachineLse().GetVms()[0].GetHostname(), ShouldEqual, "esx-8:vm578-m4")

			// Verify DHCPs
			dhcp, err := configuration.GetDHCPConfig(ctx, lse[0].GetHostname())
			So(err, ShouldBeNil)
			So(dhcp.GetIp(), ShouldEqual, "192.168.40.60")
			So(dhcp.GetMacAddress(), ShouldEqual, "00:3e:e1:c8:57:f9")

			// Verify IPs
			ipv4, err := util.ParseIPv4(dhcp.GetIp())
			So(err, ShouldBeNil)
			ips, err := configuration.QueryIPByPropertyName(ctx, "ipv4", strconv.FormatUint(uint64(ipv4), 10))
			So(err, ShouldBeNil)
			So(ips, ShouldHaveLength, 1)
			So(ips[0].GetOccupied(), ShouldBeTrue)
			So(ips[0].GetVlan(), ShouldEqual, util.GetBrowserLabVlanName(40))
		})
	})
}
