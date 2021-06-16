// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"strings"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/errors"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/tools/kitchen/build"
)

var logConfig = log.Config{
	Level: log.Info,
}

var application = cli.Application{
	Name:  "kitchen",
	Title: "Kitchen. It can run a recipe.",
	Context: func(ctx context.Context) context.Context {
		cfg := gologger.LoggerConfig{
			Out:    os.Stderr,
			Format: "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}",
		}
		ctx = cfg.Use(ctx)
		ctx = logConfig.Set(ctx)
		return handleInterruption(ctx)
	},
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,
		cmdCook,
	},
}

func main() {
	mathrand.SeedRandomly()

	logConfig.AddFlags(flag.CommandLine)
	flag.Parse()

	os.Exit(subcommands.Run(&application, flag.Args()))
}

// handleInterruption cancels the context on first SIGTERM and
// exits the process on a second SIGTERM.
func handleInterruption(ctx context.Context) context.Context {
	ctx, cancel := context.WithCancel(ctx)
	signalC := make(chan os.Signal)
	signal.Notify(signalC, os.Interrupt)
	go func() {
		<-signalC
		cancel()
		<-signalC
		os.Exit(1)
	}()
	return ctx
}

// logAnnotatedErr logs the full stack trace from an annotated error to the
// installed logger at error level.
func logAnnotatedErr(ctx context.Context, err error) {
	if err == nil {
		return
	}

	log.Errorf(ctx, "Annotated error stack:\n%s",
		strings.Join(errors.RenderStack(err), "\n"))
}

// infraFailure converts an error to a build.InfraFailure protobuf message.
// TODO(nodir): delete this function.
func infraFailure(err error) *build.InfraFailure {
	failure := &build.InfraFailure{
		Text: err.Error(),
	}
	if errors.Unwrap(err) == context.Canceled {
		failure.Type = build.InfraFailure_CANCELED
	} else {
		failure.Type = build.InfraFailure_BOOTSTRAPPER_ERROR
		failure.BootstrapperCallStack = errors.RenderStack(err)
	}

	return failure
}
