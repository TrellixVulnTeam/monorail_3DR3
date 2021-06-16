// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Package queue implements handlers for taskqueue jobs in this app.
//
// All actual logic are implemented in tasker layer.
package queue

import (
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"

	"infra/appengine/crosskylabadmin/app/frontend"
)

// InstallHandlers installs handlers for queue jobs that are part of this app.
//
// All handlers serve paths under /internal/queue/*
func InstallHandlers(r *router.Router, mwBase router.MiddlewareChain) {
	r.POST(
		"/internal/task/cros_repair/*ignored",
		mwBase.Extend(gaemiddleware.RequireTaskQueue("repair-bots")),
		logAndSetHTTPErr(runRepairQueueHandler),
	)
	r.POST(
		"/internal/task/labstation_repair/*ignored",
		mwBase.Extend(gaemiddleware.RequireTaskQueue("repair-labstations")),
		logAndSetHTTPErr(runRepairQueueHandler),
	)
	r.POST(
		"/internal/task/reset/*ignored",
		mwBase.Extend(gaemiddleware.RequireTaskQueue("reset-bots")),
		logAndSetHTTPErr(runResetQueueHandler),
	)
	r.POST(
		"/internal/task/audit/*ignored",
		mwBase.Extend(gaemiddleware.RequireTaskQueue("audit-bots")),
		logAndSetHTTPErr(runAuditQueueHandler),
	)
}

func runRepairQueueHandler(c *router.Context) (err error) {
	defer func() {
		runRepairTick.Add(c.Context, 1, err == nil)
	}()

	botID := c.Request.FormValue("botID")
	taskURL, err := frontend.CreateRepairTask(c.Context, botID)
	if err != nil {
		logging.Infof(c.Context, "fail to run repair job in queue for %s: %s", botID, err.Error())
		return err
	}

	logging.Infof(c.Context, "Successfully run repair job for %s: %s", botID, taskURL)
	return nil
}

func runResetQueueHandler(c *router.Context) (err error) {
	defer func() {
		runResetTick.Add(c.Context, 1, err == nil)
	}()

	botID := c.Request.FormValue("botID")
	taskURL, err := frontend.CreateResetTask(c.Context, botID)
	if err != nil {
		return err
	}
	logging.Infof(c.Context, "Successfully run reset job for %s: %s", botID, taskURL)
	return nil
}

func runAuditQueueHandler(c *router.Context) (err error) {
	defer func() {
		runAuditTick.Add(c.Context, 1, err == nil)
	}()

	botID := c.Request.FormValue("botID")
	taskURL, err := frontend.CreateAuditTask(c.Context, botID)
	if err != nil {
		return err
	}
	logging.Infof(c.Context, "Successfully run audit job for %s: %s", botID, taskURL)
	return nil
}

func logAndSetHTTPErr(f func(c *router.Context) error) func(*router.Context) {
	return func(c *router.Context) {
		if err := f(c); err != nil {
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}
