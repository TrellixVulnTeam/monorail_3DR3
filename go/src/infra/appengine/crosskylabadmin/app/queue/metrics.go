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

package queue

import (
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
)

var (
	runRepairTick = metric.NewCounter(
		"chromeos/crosskylabadmin/queue/run_repair",
		"runRepair attempt",
		nil,
		field.Bool("success"),
	)
	runResetTick = metric.NewCounter(
		"chromeos/crosskylabadmin/queue/run_set",
		"runReset attempt",
		nil,
		field.Bool("success"),
	)
	runAuditTick = metric.NewCounter(
		"chromeos/crosskylabadmin/queue/run_audit",
		"runAudit attempt",
		nil,
		field.Bool("success"),
	)
)
