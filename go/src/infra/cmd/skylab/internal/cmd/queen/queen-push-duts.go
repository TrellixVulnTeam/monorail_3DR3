// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package queen

import (
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/drone-queen/api"
	skycmdlib "infra/cmd/skylab/internal/cmd/cmdlib"
	"infra/cmd/skylab/internal/site"
	"infra/cmdsupport/cmdlib"
)

// PushDuts subcommand: Inspect drone queen DUT info.
var PushDuts = &subcommands.Command{
	UsageLine: "queen-push-duts",
	ShortDesc: "Push drone queen DUTs",
	LongDesc: `Push drone queen DUTs.

This command is for pushing drone queen assigned DUTs while the
Latchkey pause blocks crosskylabadmin pushes, to push the automated
pushing cron job.
Do not use this command as part of scripts or pipelines.
This command is unstable.

You must be in the inventory providers group to use this.`,
	CommandRun: func() subcommands.CommandRun {
		c := &pushDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type pushDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  skycmdlib.EnvFlags
}

func (c *pushDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		cmdlib.PrintError(a, errors.Annotate(err, "queen-push-duts").Err())
		return 1
	}
	return 0
}

func (c *pushDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(a, c, env)
	hc, err := cmdlib.NewHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	e := c.envFlags.Env()

	ac := fleet.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})
	req := &fleet.GetDroneConfigRequest{Hostname: e.QueenDroneHostname}
	res, err := ac.GetDroneConfig(ctx, req)
	if err != nil {
		return err
	}
	duts := make([]string, len(res.GetDuts()))
	for i, d := range res.GetDuts() {
		duts[i] = d.GetHostname()
	}

	qc := api.NewInventoryProviderPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.QueenService,
		Options: site.DefaultPRPCOptions,
	})
	_, err = qc.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
	if err != nil {
		return err
	}
	return nil
}
