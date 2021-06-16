// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cros

import (
	"os/user"
	"path/filepath"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"
	"golang.org/x/net/context"
)

var (
	availMem = metric.NewInt("dev/cros/mem/available",
		"Available memory of DUT.",
		&types.MetricMetadata{Units: types.Kibibytes},
		field.String("container_hostname"))
	battCharge = metric.NewFloat("dev/cros/battery/charge",
		"Percentage charge of battery.",
		nil,
		field.String("container_hostname"))
	crosVersion = metric.NewString("dev/cros/version",
		"CrOS version.",
		nil,
		field.String("container_hostname"))
	dutStatus = metric.NewString("dev/cros/status",
		"DUT status (Online|Offline).",
		nil,
		field.String("container_hostname"))
	procCount = metric.NewInt("dev/cros/proc_count",
		"Number of running processes.",
		nil,
		field.String("container_hostname"))
	temperature = metric.NewFloat("dev/cros/temperature",
		"Temperature in °C",
		&types.MetricMetadata{Units: types.DegreeCelsiusUnit},
		field.String("container_hostname"), field.String("zone"))
	totalMem = metric.NewInt("dev/cros/mem/total",
		"Total memory of DUT.",
		&types.MetricMetadata{Units: types.Kibibytes},
		field.String("container_hostname"))
	uptime = metric.NewFloat("dev/cros/uptime",
		"Uptime of DUT in seconds",
		&types.MetricMetadata{Units: types.Seconds},
		field.String("container_hostname"))

	allMetrics = []types.Metric{
		availMem,
		battCharge,
		crosVersion,
		dutStatus,
		procCount,
		temperature,
		totalMem,
		uptime,
	}
)

// Register adds tsmon callbacks to set metrics
func Register() {
	tsmon.RegisterGlobalCallback(func(c context.Context) {
		usr, err := user.Current()
		if err != nil {
			logging.Errorf(c, "Failed to get current user: %s",
				err)
		} else if err = update(c, usr.HomeDir); err != nil {
			logging.Errorf(c, "Error updating DUT metrics: %s",
				err)
		}
	}, allMetrics...)
}

func update(c context.Context, usrHome string) (err error) {
	allFiles, err := filepath.Glob(
		filepath.Join(usrHome, fileGlob))
	if err != nil {
		return
	}
	if len(allFiles) == 0 {
		// This is usual case in most machines. So don't log an error
		// message.
		return
	}
	var lastErr error
	for _, filePath := range allFiles {
		statusFile, err := loadfile(c, filePath)
		if err != nil {
			logging.Errorf(c, "Failed to load file %s. %s",
				filePath, err)
			lastErr = err
		} else {
			updateMetrics(c, statusFile)
		}
	}
	err = lastErr
	return
}

func updateMetrics(c context.Context, deviceFile deviceStatusFile) {
	if deviceFile.Status != "" {
		dutStatus.Set(c, deviceFile.Status, deviceFile.ContainerHostname)
	} else {
		logging.Warningf(c, "Device status unknown")
	}
	if deviceFile.OSVersion != "" {
		crosVersion.Set(c, deviceFile.OSVersion,
			deviceFile.ContainerHostname)
	} else {
		logging.Warningf(c, "CrOS version unknown")
	}
	if &(deviceFile.Battery) != nil {
		battCharge.Set(c, deviceFile.Battery.Charge,
			deviceFile.ContainerHostname)
	} else {
		logging.Warningf(c, "Battery info unknown")
	}
	if len(deviceFile.Temperature) > 0 {
		for zone, temp := range deviceFile.Temperature {
			// Reporting average temperature per zone. Usually
			// a single temperature is reported per zone. If a DUT
			// reports multiple temperatures per zone, we are
			// probably not interested.
			avgTemp := 0.0
			for _, tempInst := range temp {
				avgTemp += tempInst
			}
			avgTemp = avgTemp / float64(len(temp))
			temperature.Set(c, avgTemp, deviceFile.ContainerHostname, zone)
		}
	} else {
		logging.Warningf(c, "Temperature info unknown")
	}
	if &(deviceFile.Memory) != nil {
		totalMem.Set(c, deviceFile.Memory.Total, deviceFile.ContainerHostname)
		availMem.Set(c, deviceFile.Memory.Avail, deviceFile.ContainerHostname)
	} else {
		logging.Warningf(c, "Memory info unknown")
	}
	if deviceFile.Uptime != 0.0 {
		uptime.Set(c, deviceFile.Uptime, deviceFile.ContainerHostname)
	}
	if deviceFile.ProcCount != 0 {
		procCount.Set(c, deviceFile.ProcCount, deviceFile.ContainerHostname)
	}
}
