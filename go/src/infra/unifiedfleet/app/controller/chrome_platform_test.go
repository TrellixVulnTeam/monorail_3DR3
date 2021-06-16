// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package controller

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
	fleet "infra/unifiedfleet/api/v1/proto"
	"infra/unifiedfleet/app/model/configuration"
	. "infra/unifiedfleet/app/model/datastore"
	"infra/unifiedfleet/app/model/registration"
)

func mockChromePlatform(id, desc string) *fleet.ChromePlatform {
	return &fleet.ChromePlatform{
		Name:        id,
		Description: desc,
	}
}

func TestDeleteChromePlatform(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	chromePlatform1 := mockChromePlatform("chromePlatform-1", "Camera")
	chromePlatform2 := mockChromePlatform("chromePlatform-2", "Camera")
	chromePlatform3 := mockChromePlatform("chromePlatform-3", "Sensor")
	Convey("DeleteChromePlatform", t, func() {
		Convey("Delete chromePlatform by existing ID with machine reference", func() {
			resp, cerr := configuration.CreateChromePlatform(ctx, chromePlatform1)
			So(cerr, ShouldBeNil)
			So(resp, ShouldResembleProto, chromePlatform1)

			chromeBrowserMachine1 := &fleet.Machine{
				Name: "machine-1",
				Device: &fleet.Machine_ChromeBrowserMachine{
					ChromeBrowserMachine: &fleet.ChromeBrowserMachine{
						ChromePlatform: "chromePlatform-1",
					},
				},
			}
			mresp, merr := registration.CreateMachine(ctx, chromeBrowserMachine1)
			So(merr, ShouldBeNil)
			So(mresp, ShouldResembleProto, chromeBrowserMachine1)

			err := DeleteChromePlatform(ctx, "chromePlatform-1")
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, CannotDelete)

			resp, cerr = configuration.GetChromePlatform(ctx, "chromePlatform-1")
			So(resp, ShouldNotBeNil)
			So(cerr, ShouldBeNil)
			So(resp, ShouldResembleProto, chromePlatform1)
		})
		Convey("Delete chromePlatform by existing ID with KVM reference", func() {
			resp, cerr := configuration.CreateChromePlatform(ctx, chromePlatform3)
			So(cerr, ShouldBeNil)
			So(resp, ShouldResembleProto, chromePlatform3)

			kvm1 := &fleet.KVM{
				Name:           "kvm-1",
				ChromePlatform: "chromePlatform-3",
			}
			kresp, kerr := registration.CreateKVM(ctx, kvm1)
			So(kerr, ShouldBeNil)
			So(kresp, ShouldResembleProto, kvm1)

			err := DeleteChromePlatform(ctx, "chromePlatform-3")
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, CannotDelete)

			resp, cerr = configuration.GetChromePlatform(ctx, "chromePlatform-3")
			So(resp, ShouldNotBeNil)
			So(cerr, ShouldBeNil)
			So(resp, ShouldResembleProto, chromePlatform3)
		})
		Convey("Delete chromePlatform successfully by existing ID without references", func() {
			resp, cerr := configuration.CreateChromePlatform(ctx, chromePlatform2)
			So(cerr, ShouldBeNil)
			So(resp, ShouldResembleProto, chromePlatform2)

			err := DeleteChromePlatform(ctx, "chromePlatform-2")
			So(err, ShouldBeNil)

			resp, cerr = configuration.GetChromePlatform(ctx, "chromePlatform-2")
			So(resp, ShouldBeNil)
			So(cerr, ShouldNotBeNil)
			So(cerr.Error(), ShouldContainSubstring, NotFound)
		})
	})
}
