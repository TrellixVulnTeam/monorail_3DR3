// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"os"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/tsmon"
	"golang.org/x/net/context"

	"infra/monitoring/sysmon/android"
	"infra/monitoring/sysmon/cipd"
	"infra/monitoring/sysmon/cros"
	"infra/monitoring/sysmon/docker"
	"infra/monitoring/sysmon/puppet"
	"infra/monitoring/sysmon/system"
)

func main() {
	fs := flag.NewFlagSet("", flag.ExitOnError)

	tsmonFlags := tsmon.NewFlags()
	tsmonFlags.Flush = "auto"
	tsmonFlags.Register(fs)

	loggingConfig := logging.Config{Level: logging.Info}
	loggingConfig.AddFlags(fs)

	fs.Parse(os.Args[1:])

	c := context.Background()
	c = gologger.StdConfig.Use(c)
	c = loggingConfig.Set(c)

	if err := tsmon.InitializeFromFlags(c, &tsmonFlags); err != nil {
		panic(fmt.Sprintf("failed to initialize tsmon: %s", err))
	}

	// Register metric callbacks.
	android.Register()
	cipd.Register()
	cros.Register()
	docker.Register()
	puppet.Register()
	system.Register() // Should be registered last.

	if tsmonFlags.Flush == "auto" {
		// tsmon's auto-flusher goroutine will call the metric callbacks and flush
		// the metrics every minute.
		select {}
	} else {
		// Flush once and exit.
		tsmon.Flush(c)
	}
}
