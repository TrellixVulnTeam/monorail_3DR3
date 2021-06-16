// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package docker

import (
	"bytes"
	"io"
	"testing"
	"time"

	"golang.org/x/net/context"

	dockerTypes "github.com/docker/docker/api/types"
	dockerContainerTypes "github.com/docker/docker/api/types/container"

	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/tsmon"

	. "github.com/smartystreets/goconvey/convey"
)

type noOpCloser struct {
	io.Reader
}

func (noOpCloser) Close() (err error) {
	return nil
}

func TestMetrics(t *testing.T) {
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC) // Unix timestamp 946782245
	nowMinus10s := now.Add(-10 * time.Second)
	c := context.Background()
	c, _ = testclock.UseTime(c, now)
	c, _ = tsmon.WithDummyInMemory(c)

	container := dockerTypes.Container{
		Names: []string{"/container_name"},
		State: "running",
	}
	containerState := dockerTypes.ContainerState{
		StartedAt: nowMinus10s.Format(time.RFC3339Nano),
	}
	containerConfig := dockerContainerTypes.Config{
		Hostname: "hostname123",
	}
	containerInfoBase := dockerTypes.ContainerJSONBase{
		State: &containerState,
	}
	containerInfo := dockerTypes.ContainerJSON{
		Config:            &containerConfig,
		ContainerJSONBase: &containerInfoBase,
	}
	containerStatsJSON := dockerTypes.ContainerStats{
		Body: noOpCloser{bytes.NewReader([]byte(`{` +
			`"name": "container1", ` +
			`"memory_stats": {"usage": 1111, "limit": 9999}, ` +
			`"networks": {"eth0": {"rx_bytes": 987, "tx_bytes": 123}}}`))},
	}

	Convey("Test All Metrics", t, func() {
		err := updateContainerMetrics(c, container, containerInfo,
			containerStatsJSON)
		So(err, ShouldBeNil)

		So(statusMetric.Get(c, "container_name", "hostname123"), ShouldEqual, "running")
		So(uptimeMetric.Get(c, "container_name"), ShouldEqual, 10)
		So(memUsedMetric.Get(c, "container_name"), ShouldEqual, 1111)
		So(memTotalMetric.Get(c, "container_name"), ShouldEqual, 9999)
		So(netUpMetric.Get(c, "container_name"), ShouldEqual, 123)
		So(netDownMetric.Get(c, "container_name"), ShouldEqual, 987)
	})

	Convey("Test Broken JSON", t, func() {
		bodyJSON := "omg this isn't json"
		reader := bytes.NewReader([]byte(bodyJSON))
		readCloser := noOpCloser{reader}
		containerStatsJSON.Body = readCloser

		err := updateContainerMetrics(c, container, containerInfo,
			containerStatsJSON)
		So(err, ShouldNotBeNil)
	})

	Convey("Test Broken Time Format", t, func() {
		containerState = dockerTypes.ContainerState{StartedAt: "omg this isn't a timestamp"}

		err := updateContainerMetrics(c, container, containerInfo,
			containerStatsJSON)
		So(err, ShouldNotBeNil)
	})
}
