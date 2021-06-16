// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package dynamicsuite provides a library to create control.cros_test_platform
// suite requests that inject arbitrary arguments into
// autotest.dynamic_suite.reimage_and_run(...). This is used as an entry point
// for cros_test_platform when launching legacy autotest suites.
package dynamicsuite

import (
	"encoding/json"
	"infra/libs/skylab/autotest/proxy"
	"time"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
)

const suiteName = "cros_test_platform"
const argsKey = "args_dict_json"

// Args encapsulates arguments for forming a request.
type Args struct {
	Board           string
	Build           string
	FirmwareROBuild string
	FirmwareRWBuild string
	Model           string
	Pool            string
	Priority        int
	AfeHost         string
	Timeout         time.Duration
	// ReimageAndRunArgs specifies arguments to be passed into
	// autotest.dynamic_suite.reimage_and_run. This object must be
	// json-encodable.
	ReimageAndRunArgs interface{}
	// If specified, ignore ReimageAndRunArgs and just run this named
	// autotest suite.
	LegacySuite string
}

// NewRequest creates a new swarming request for the given entry point
// arguments.
func NewRequest(args Args) (*swarming.SwarmingRpcsNewTaskRequest, error) {
	encodedArgs, err := json.Marshal(args.ReimageAndRunArgs)
	if err != nil {
		return nil, errors.Annotate(err, "new dynamicsuite request").Err()
	}
	s := suiteName
	suiteArgs := map[string]interface{}{
		argsKey: string(encodedArgs),
	}
	if args.LegacySuite != "" {
		suiteArgs = map[string]interface{}{}
		s = args.LegacySuite
	}

	req, err := proxy.NewRunSuite(
		proxy.RunSuiteArgs{
			Board:           args.Board,
			Build:           args.Build,
			FirmwareROBuild: args.FirmwareROBuild,
			FirmwareRWBuild: args.FirmwareRWBuild,
			Model:           args.Model,
			Pool:            args.Pool,
			Priority:        args.Priority,
			AfeHost:         args.AfeHost,
			Timeout:         args.Timeout,
			SuiteName:       s,
			SuiteArgs:       suiteArgs,
		})
	if err != nil {
		return nil, errors.Annotate(err, "new dynamicsuite request").Err()
	}
	return req, nil
}
