// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package utilization

import (
	"context"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/tsmon"

	"infra/libs/skylab/inventory"
)

func TestReportMetrics(t *testing.T) {
	Convey("with fake tsmon context", t, func() {
		ctx := context.Background()
		ctx, _ = tsmon.WithDummyInMemory(ctx)

		Convey("ReportMetric for single bot should report 0 for unknown statuses", func() {
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{
				{State: "", Dimensions: []*swarming.SwarmingRpcsStringListPair{}},
			})
			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "[None]", false), ShouldEqual, 1)

			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "NeedsRepair", false), ShouldEqual, 0)
			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "Running", false), ShouldEqual, 0)
			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "RepairFailed", false), ShouldEqual, 0)
			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "Ready", false), ShouldEqual, 0)
			So(dutmonMetric.Get(ctx, "[None]", "[None]", "[None]", "NeedsReset", false), ShouldEqual, 0)
		})

		Convey("ReportMetric for multiple bots with same fields should count up", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "IDLE", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"ready"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"some_random_pool"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi, bi, bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "some_random_pool", "Ready", false), ShouldEqual, 3)
		})

		Convey("ReportMetric should report dut_state as Running when dut_state is ready and task id is not null", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "BUSY", TaskId: "foobar", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"ready"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"some_random_pool"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi, bi, bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "some_random_pool", "Running", false), ShouldEqual, 3)
		})

		Convey("ReportMetric with managed pool should report pool correctly", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "IDLE", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"ready"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"DUT_POOL_CQ"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "managed:DUT_POOL_CQ", "Ready", false), ShouldEqual, 1)
			So(dutmonMetric.Get(ctx, "reef", "electro", "DUT_POOL_CQ", "Ready", false), ShouldEqual, 0)
		})

		Convey("Multiple calls to ReportMetric keep metric unchanged", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "IDLE", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"ready"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"some_random_pool"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi, bi, bi})
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi, bi, bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "some_random_pool", "Ready", false), ShouldEqual, 3)
		})

		Convey("ReportMetric should stop counting bots that disappear", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "IDLE", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"ready"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"some_random_pool"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi, bi, bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "some_random_pool", "Ready", false), ShouldEqual, 3)
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "some_random_pool", "Ready", false), ShouldEqual, 1)
		})

		Convey("ReportMetric should report repair_failed bots as RepairFailed", func() {
			bi := &swarming.SwarmingRpcsBotInfo{State: "IDLE", Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{Key: "dut_state", Value: []string{"repair_failed"}},
				{Key: "label-board", Value: []string{"reef"}},
				{Key: "label-model", Value: []string{"electro"}},
				{Key: "label-pool", Value: []string{"some_random_pool"}},
			}}
			ReportMetrics(ctx, []*swarming.SwarmingRpcsBotInfo{bi})
			So(dutmonMetric.Get(ctx, "reef", "electro", "some_random_pool", "RepairFailed", false), ShouldEqual, 1)
		})

	})
}

func TestReportServerMetrics(t *testing.T) {
	Convey("with fake tsmon context", t, func() {
		ctx := context.Background()
		ctx, _ = tsmon.WithDummyInMemory(ctx)

		Convey("Happy path", func() {
			ReportServerMetrics(ctx, []*inventory.Server{
				{
					Hostname:    strPtr("devserver1"),
					Environment: inventory.Environment_ENVIRONMENT_PROD.Enum(),
					Roles:       []inventory.Server_Role{inventory.Server_ROLE_DEVSERVER, inventory.Server_ROLE_SKYLAB_DRONE},
					Status:      inventory.Server_STATUS_PRIMARY.Enum(),
				},
				{
					Hostname:    strPtr("devserver2"),
					Environment: inventory.Environment_ENVIRONMENT_PROD.Enum(),
					Roles:       []inventory.Server_Role{inventory.Server_ROLE_DEVSERVER},
					Status:      inventory.Server_STATUS_PRIMARY.Enum(),
				},
				{
					Hostname:    strPtr("skylab_drone1"),
					Environment: inventory.Environment_ENVIRONMENT_PROD.Enum(),
					Roles:       []inventory.Server_Role{inventory.Server_ROLE_SKYLAB_DRONE},
					Status:      inventory.Server_STATUS_PRIMARY.Enum(),
				},
			})

			So(serverMetric.Get(ctx, "devserver1", "ENVIRONMENT_PROD", "[Multiple]", "STATUS_PRIMARY"), ShouldEqual, 1)
			So(serverMetric.Get(ctx, "devserver2", "ENVIRONMENT_PROD", "ROLE_DEVSERVER", "STATUS_PRIMARY"), ShouldEqual, 1)
			So(serverMetric.Get(ctx, "skylab_drone1", "ENVIRONMENT_PROD", "ROLE_SKYLAB_DRONE", "STATUS_PRIMARY"), ShouldEqual, 1)
		})
	})
}

func strPtr(s string) *string { return &s }
