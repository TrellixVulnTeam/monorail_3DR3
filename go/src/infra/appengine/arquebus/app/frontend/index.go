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

package frontend

import (
	"net/http"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/arquebus/app/backend"
	"infra/appengine/arquebus/app/util"
)

func indexPage(c *router.Context) {
	assigners, err := backend.GetAllAssigners(c.Context)
	if err != nil {
		logging.Errorf(c.Context, "%s", err)
		util.ErrStatus(c, http.StatusInternalServerError, "Internal error.")
		return
	}
	templates.MustRender(
		c.Context,
		c.Writer,
		"pages/index.html",
		map[string]interface{}{
			"Assigners": assigners,
		},
	)
}
