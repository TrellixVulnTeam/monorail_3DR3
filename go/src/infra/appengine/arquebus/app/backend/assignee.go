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

package backend

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/rotang/proto/rotangapi"
	"infra/appengine/rotation-proxy/proto"
	"infra/monorailv2/api/api_proto"
)

var (
	// maxShiftCacheDuration is the maximum cache duration for shifts.
	//
	// This is to have caches updated even before the shift ends, just in
	// case the shift has been modified.
	maxShiftCacheDuration = 5 * time.Minute
)

type oncallShift struct {
	Primary     string   `json:"primary"`
	Secondaries []string `json:"secondaries"`
	Started     int64    `json:"update_unix_timestamp"`
}

func findAssigneeAndCCs(c context.Context, assigner *model.Assigner, task *model.Task) (*monorail.UserRef, []*monorail.UserRef, error) {
	assigneeSrcs, err := assigner.Assignees()
	if err != nil {
		return nil, nil, err
	}
	ccSrcs, err := assigner.CCs()
	if err != nil {
		return nil, nil, err
	}

	// resolve the user sources to find the assignee and ccs.
	ccs, err := resolveUserSources(c, task, ccSrcs)
	if err != nil {
		return nil, nil, err
	}
	assignees, err := resolveUserSources(c, task, assigneeSrcs)
	if err != nil {
		return nil, nil, err
	}
	if len(assignees) == 0 {
		return nil, ccs, nil
	}
	return assignees[0], ccs, nil
}

func resolveUserSources(c context.Context, task *model.Task, sources []config.UserSource) (users []*monorail.UserRef, err error) {
	for _, source := range sources {
		if rotation := source.GetRotation(); rotation != nil {
			userRefs, err := findOncallers(c, task, rotation, true)
			if err != nil {
				return nil, err
			}
			users = append(users, userRefs...)
		} else if oncall := source.GetOncall(); oncall != nil {
			userRefs, err := findOncallers(c, task, oncall, false)
			if err != nil {
				return nil, err
			}
			users = append(users, userRefs...)
		} else if email := source.GetEmail(); email != "" {
			task.WriteLog(c, "Found Monorail User %s", email)
			users = append(users, &monorail.UserRef{DisplayName: email})
		}
	}
	return users, err
}

func getCachedShift(c context.Context, key string, shift *oncallShift) error {
	item, err := memcache.GetKey(c, key)
	if err != nil {
		return err
	}
	return json.Unmarshal(item.Value(), shift)
}

func setShiftCache(c context.Context, key string, shift *oncallShift) error {
	item := memcache.NewItem(c, key)
	bytes, err := json.Marshal(shift)
	if err != nil {
		return err
	}
	// TODO(crbug/967523), if RotaNG provides an RPC to return
	// the end timestamp of a shift, update this logic to maximise the cache
	// duration, based on the shift end timestamp.
	item.SetValue(bytes).SetExpiration(maxShiftCacheDuration)
	return memcache.Set(c, item)
}

func fetchOncallFromRotaNg(c context.Context, rotation string, oc *oncallShift) error {
	rota := getRotaNGClient(c)
	resp, err := rota.Oncall(c, &rotangapi.OncallRequest{Name: rotation})
	if err != nil {
		return err
	}

	if shift := resp.GetShift(); shift != nil {
		nOncallers := len(shift.Oncallers)
		if nOncallers > 0 {
			oc.Primary = shift.Oncallers[0].Email
		}
		if nOncallers > 1 {
			for _, oncaller := range shift.Oncallers[1:] {
				oc.Secondaries = append(oc.Secondaries, oncaller.Email)
			}
		}
		started, _ := ptypes.Timestamp(shift.Start)
		oc.Started = started.Unix()
	}

	return nil
}

func shiftIsCurrent(shift *rotationproxy.Shift) bool {
	now := time.Now()
	if startTime, err := ptypes.Timestamp(shift.StartTime); err != nil || startTime.After(now) {
		return false
	}
	// There might be no end time, in which case this shift extends to
	// infinity (so it should be treated as current).
	if endTime, err := ptypes.Timestamp(shift.EndTime); err == nil && endTime.Before(now) {
		return false
	}
	return true
}

func fetchOncallFromRotationProxy(c context.Context, rotation string, oc *oncallShift) error {
	rotationProxy := getRotationProxyClient(c)
	resp, err := rotationProxy.GetRotation(c, &rotationproxy.GetRotationRequest{Name: rotation})
	if err != nil {
		return err
	}

	if shifts := resp.GetShifts(); len(shifts) > 0 {
		// The first shift will contain either the current or next oncall.
		// We only want to use it if the shift is actually current.
		shift := shifts[0]
		if !shiftIsCurrent(shift) {
			return nil
		}
		nOncallers := len(shift.Oncalls)
		if nOncallers > 0 {
			oc.Primary = shift.Oncalls[0].Email
		}
		if nOncallers > 1 {
			for _, oncaller := range shift.Oncalls[1:] {
				oc.Secondaries = append(oc.Secondaries, oncaller.Email)
			}
		}
		started, _ := ptypes.Timestamp(shift.StartTime)
		oc.Started = started.Unix()
	}

	return nil
}

func findShift(c context.Context, task *model.Task, rotation string, useRotationProxy bool) (*oncallShift, error) {
	var oc oncallShift
	if err := getCachedShift(c, rotation, &oc); err == nil {
		return &oc, nil
	} else if err != memcache.ErrCacheMiss {
		task.WriteLog(c, "Shift cache lookup failed: %s", err.Error())
	}

	if useRotationProxy {
		if err := fetchOncallFromRotationProxy(c, rotation, &oc); err != nil {
			return nil, err
		}
	} else {
		if err := fetchOncallFromRotaNg(c, rotation, &oc); err != nil {
			return nil, err
		}
	}

	if err := setShiftCache(c, rotation, &oc); err != nil {
		// ignore cache save failures, but log the error.
		msg := fmt.Sprintf("Failed to cache the shift; %s", err.Error())
		task.WriteLog(c, msg)
		logging.Errorf(c, msg)
	}

	return &oc, nil
}

func findOncallers(c context.Context, task *model.Task, oncall *config.Oncall, useRotationProxy bool) ([]*monorail.UserRef, error) {
	shift, err := findShift(c, task, oncall.Rotation, useRotationProxy)
	if err != nil {
		return nil, err
	}

	var oncallers []*monorail.UserRef
	switch oncall.GetPosition() {
	case config.Oncall_PRIMARY:
		if shift.Primary != "" {
			oncallers = append(oncallers, &monorail.UserRef{
				DisplayName: shift.Primary},
			)
			task.WriteLog(
				c, "Found primary oncaller %s of %s",
				shift.Primary, oncall.Rotation,
			)
		}
	case config.Oncall_SECONDARY:
		for _, secondary := range shift.Secondaries {
			oncallers = append(oncallers, &monorail.UserRef{
				DisplayName: secondary},
			)
			task.WriteLog(
				c, "Found secondary oncaller %s of %s",
				secondary, oncall.Rotation,
			)
		}
	}
	return oncallers, nil
}
