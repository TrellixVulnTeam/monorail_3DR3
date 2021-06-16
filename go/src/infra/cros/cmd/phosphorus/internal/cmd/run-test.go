// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/maruel/subcommands"
	"github.com/pkg/errors"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/phosphorus"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/proto/google"

	"infra/cros/cmd/phosphorus/internal/autotest/atutil"
)

// RunTest subcommand: Run a test against one or multiple DUTs.
var RunTest = &subcommands.Command{
	UsageLine: "run-test -input_json /path/to/input.json",
	ShortDesc: "Run a test against one or multiple DUTs.",
	LongDesc: `Run a test against one or multiple DUTs.

A wrapper around 'autoserv'.`,
	CommandRun: func() subcommands.CommandRun {
		c := &runTestRun{}
		c.Flags.StringVar(&c.inputPath, "input_json", "", "Path that contains JSON encoded test_platform.phosphorus.RunTestRequest")
		c.Flags.StringVar(&c.outputPath, "output_json", "", "Path to write JSON encoded test_platform.phosphorus.RunTestResponse to")
		return c
	},
}

type runTestRun struct {
	commonRun
}

type autoservResult struct {
	CmdResult  *atutil.Result
	ResultsDir string
}

func (c *runTestRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.validateArgs(); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return 1
	}

	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), err.Error())
		return 1
	}
	return 0
}

func (c *runTestRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	var r phosphorus.RunTestRequest
	if err := readJSONPb(c.inputPath, &r); err != nil {
		return err
	}

	if err := validateRunTestRequest(r); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)

	if d := google.TimeFromProto(r.Deadline); !d.IsZero() {
		var c context.CancelFunc
		log.Printf("Running with deadline %s (current time: %s)", d, time.Now().UTC())
		ctx, c = context.WithDeadline(ctx, d)
		defer c()
	}
	ar, err := runTestStep(ctx, r)
	if err != nil {
		return err
	}
	return writeJSONPb(c.outputPath, runTestResponse(ar))
}

func runTestResponse(r *autoservResult) *phosphorus.RunTestResponse {
	return &phosphorus.RunTestResponse{
		ResultsDir: r.ResultsDir,
		State:      runTestState(r.CmdResult),
	}
}

func runTestState(r *atutil.Result) phosphorus.RunTestResponse_State {
	if r.Success() {
		return phosphorus.RunTestResponse_SUCCEEDED
	}
	if r.RunResult.Aborted {
		return phosphorus.RunTestResponse_ABORTED
	}
	return phosphorus.RunTestResponse_FAILED
}

func validateRunTestRequest(r phosphorus.RunTestRequest) error {
	missingArgs := getCommonMissingArgs(r.Config)

	if len(r.DutHostnames) == 0 {
		missingArgs = append(missingArgs, "DUT hostname(s)")
	}

	if r.GetAutotest().GetName() == "" {
		missingArgs = append(missingArgs, "test name")
	}

	if len(missingArgs) > 0 {
		return fmt.Errorf("no %s provided", strings.Join(missingArgs, ", "))
	}

	return nil
}

// runTestStep runs an individual test. It is a wrapper around autoserv.
func runTestStep(ctx context.Context, r phosphorus.RunTestRequest) (*autoservResult, error) {
	j := getMainJob(r.Config)

	dir := filepath.Join(r.Config.Task.ResultsDir, "autoserv_test")

	t := &atutil.HostTest{
		HostlessTest: atutil.HostlessTest{
			Args:        r.GetAutotest().GetTestArgs(),
			ClientTest:  r.GetAutotest().GetIsClientTest(),
			ControlName: r.GetAutotest().GetName(),
			Keyvals:     r.GetAutotest().GetKeyvals(),
			Name:        r.GetAutotest().GetDisplayName(),
			ResultsDir:  dir,
		},
		Hosts:             r.DutHostnames,
		OffloadDir:        r.Config.GetTask().GetSynchronousOffloadDir(),
		LocalOnlyHostInfo: true,
		RequireSSP:        !r.GetAutotest().GetIsClientTest(),
	}

	ar, err := atutil.RunAutoserv(ctx, j, t, os.Stdout)
	if err != nil {
		return nil, errors.Wrap(err, "run test")
	}
	return &autoservResult{
		CmdResult:  ar,
		ResultsDir: dir,
	}, nil
}
