// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package worker implements a constructor for skylab_swarming_worker
// commands.  This package is intended to be used by package that need
// to construct a command line for running skylab_swarming_worker.
package worker

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// DefaultPath is the default path for skylab_swarming_worker.
const DefaultPath = "/opt/infra-tools/skylab_swarming_worker"

// isolateOutdirMagicVal is a magic cmd argument that gets replaced by
// Swarming with the path to the isolated output directory inside the
// Swarming bot. Anything written by the worker to the isolated output
// directory is automatically uploaded to the Isolate server.
const isolatedOutdirMagicVal = "${ISOLATED_OUTDIR}"

// Command is a constructor for skylab_swarming_worker commands.
type Command struct {
	Actions    string
	ClientTest bool
	Deadline   time.Time
	ForceFresh bool
	Keyvals    map[string]string
	// LogDogAnnotationURL can be set automatically with Env.
	LogDogAnnotationURL string
	// If true, pass the magic var ${ISOLATED_OUTDIR} to the worker.
	OutputToIsolate bool
	// Path to skylab_swarming_worker.  The default is DefaultPath.
	Path            string
	ProvisionLabels []string
	// TaskName is required.
	TaskName string
	TestArgs string
}

// Args returns the arg strings for running the command.
func (c *Command) Args() []string {
	var args []string
	if c.Path != "" {
		args = append(args, c.Path)
	} else {
		args = append(args, DefaultPath)
	}

	if c.Actions != "" {
		args = append(args, "-actions", c.Actions)
	}
	if c.ClientTest {
		args = append(args, "-client-test")
	}
	if !c.Deadline.IsZero() {
		args = append(args, "-deadline", stiptime(c.Deadline))
	}
	if c.ForceFresh {
		args = append(args, "-force-fresh")
	}
	if c.Keyvals != nil {
		b, err := json.Marshal(c.Keyvals)
		// Marshal map[string]string should never error.
		if err != nil {
			panic(err)
		}
		args = append(args, "-keyvals", string(b))
	}
	if c.LogDogAnnotationURL != "" {
		args = append(args, "-logdog-annotation-url", c.LogDogAnnotationURL)
	}
	if c.OutputToIsolate {
		args = append(args, "-isolated-outdir", isolatedOutdirMagicVal)
	}
	if len(c.ProvisionLabels) > 0 {
		args = append(args, "-provision-labels", strings.Join(c.ProvisionLabels, ","))
	}
	if c.TaskName != "" {
		args = append(args, "-task-name", c.TaskName)
	}
	if c.TestArgs != "" {
		args = append(args, "-test-args", c.TestArgs)
	}
	return args
}

// Config configures the command with the given options.
func (c *Command) Config(e Environment) {
	c.LogDogAnnotationURL = GenerateLogDogURL(e)
}

// Environment defines a Skylab environment (e.g., dev vs prod) for
// configuring a worker command.
type Environment interface {
	LUCIProject() string
	LogDogHost() string
	GenerateLogPrefix() string
}

// GenerateLogDogURL generates a LogDog annotation URL that is
// suitable for a worker command.
func GenerateLogDogURL(e Environment) string {
	u := logDogURL{
		Host:    e.LogDogHost(),
		Project: e.LUCIProject(),
		Prefix:  e.GenerateLogPrefix(),
	}
	return u.String()
}

// logDogURL is a constructor for LogDog annotation URLs.
type logDogURL struct {
	Host    string
	Project string
	Prefix  string
}

func (u logDogURL) String() string {
	return fmt.Sprintf("logdog://%s/%s/%s/+/annotations", u.Host, u.Project, u.Prefix)
}

const stipLayout = "2006-01-02T15:04:05.99Z0700"

func stiptime(t time.Time) string {
	return t.In(time.UTC).Format(stipLayout)
}
