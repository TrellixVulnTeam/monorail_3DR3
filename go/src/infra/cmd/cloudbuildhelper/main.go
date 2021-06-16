// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Binary cloudbuildhelper is used internally by Infra CI pipeline to build
// docker images.
package main

import (
	"context"
	"os"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/client/versioncli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/flag/fixflagpos"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/hardcoded/chromeinfra"
)

const (
	// Version is the version of cloudbuildhelper tool.
	Version = "1.1.3"
	// UserAgent is used in HTTP headers of requests from cloudbuildhelper.
	UserAgent = "cloudbuildhelper v" + Version
)

func getApplication() *cli.Application {
	return &cli.Application{
		Name:  "cloudbuildhelper",
		Title: "Helper for building docker images (" + UserAgent + ")",

		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},

		Commands: []*subcommands.Command{
			subcommands.CmdHelp,
			versioncli.CmdVersion(UserAgent),

			subcommands.Section(""),
			cmdBuild,
			cmdLocalBuild,
			cmdStage,
			cmdUpload,

			subcommands.Section(""),
			cmdPinsAdd,
			cmdPinsUpdate,

			subcommands.Section(""),
			authcli.SubcommandLogin(authOptions(), "login", false),
			authcli.SubcommandLogout(authOptions(), "logout", false),
			authcli.SubcommandInfo(authOptions(), "whoami", false),
		},
	}
}

func authOptions() auth.Options {
	opts := chromeinfra.DefaultAuthOptions()
	opts.Scopes = []string{
		// For calling GCR, GCS and Cloud Build.
		"https://www.googleapis.com/auth/cloud-platform",
		// For calling LUCI and for displaying the email.
		"https://www.googleapis.com/auth/userinfo.email",
	}
	return opts
}

func main() {
	mathrand.SeedRandomly()
	os.Exit(subcommands.Run(getApplication(), fixflagpos.FixSubcommands(os.Args[1:])))
}
