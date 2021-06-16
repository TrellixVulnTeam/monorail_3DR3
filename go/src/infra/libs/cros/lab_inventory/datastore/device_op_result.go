// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package datastore

import (
	"time"

	"github.com/golang/protobuf/proto"
)

// DeviceOpResult is the common response of all device-related datastore
// functions.
type DeviceOpResult struct {
	Data      proto.Message
	Entity    *DeviceEntity
	Err       error
	Timestamp time.Time // Only used when logging errors.
}

func (d *DeviceOpResult) logError(err error) {
	d.Err = err
	d.Timestamp = time.Now().UTC()
}

// DeviceOpResults is a list of DeviceOpResult.
type DeviceOpResults []DeviceOpResult

func (rs DeviceOpResults) filter(f func(*DeviceOpResult) bool) []DeviceOpResult {
	result := make([]DeviceOpResult, 0, len(rs))
	for _, r := range rs {
		if f(&r) {
			result = append(result, r)
		}
	}
	return result
}

// Passed generates the list of devices passed the operation.
func (rs DeviceOpResults) Passed() []DeviceOpResult {
	return rs.filter(func(result *DeviceOpResult) bool {
		return result.Err == nil
	})
}

// Failed generates the list of devices failed the operation.
func (rs DeviceOpResults) Failed() []DeviceOpResult {
	return rs.filter(func(result *DeviceOpResult) bool {
		return result.Err != nil
	})
}
