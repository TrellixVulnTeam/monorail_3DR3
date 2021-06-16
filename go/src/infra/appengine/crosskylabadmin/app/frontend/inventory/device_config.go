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

package inventory

import (
	"bytes"
	"strings"
	"time"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"

	"go.chromium.org/chromiumos/infra/proto/go/device"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/libs/skylab/inventory"
)

// DeviceConfigID includes required info to form a device config ID.
type DeviceConfigID struct {
	PlatformID string
	ModelID    string
	VariantID  string
}

// getDeviceConfigIDStr generates device id for a DUT.
func getDeviceConfigIDStr(ctx context.Context, dcID DeviceConfigID) string {
	return strings.Join([]string{
		strings.ToLower(dcID.PlatformID),
		strings.ToLower(dcID.ModelID),
		strings.ToLower(dcID.VariantID),
	}, ".")
}

func getIDForDeviceConfig(ctx context.Context, dc *device.Config) string {
	return getDeviceConfigIDStr(ctx, DeviceConfigID{
		PlatformID: strings.ToLower(dc.Id.PlatformId.Value),
		ModelID:    strings.ToLower(dc.Id.ModelId.Value),
		VariantID:  strings.ToLower(dc.Id.VariantId.Value),
	})
}

func getIDForInventoryLabels(ctx context.Context, sl *inventory.SchedulableLabels) string {
	return getDeviceConfigIDStr(ctx, DeviceConfigID{
		PlatformID: strings.ToLower(sl.GetBoard()),
		ModelID:    strings.ToLower(sl.GetModel()),
		VariantID:  strings.ToLower(sl.GetSku()),
	})
}

// UpdateLabelsWithDeviceConfig update skylab inventory labels with cached device config.
func UpdateLabelsWithDeviceConfig(ctx context.Context, sl *inventory.SchedulableLabels) error {
	dcID := getIDForInventoryLabels(ctx, sl)
	if dcID == getDeviceConfigIDStr(ctx, DeviceConfigID{}) {
		return errors.Reason("no platform, model, variant are specified in inventory labels").Err()
	}
	dce := &deviceConfigEntity{
		ID: dcID,
	}
	if err := datastore.Get(ctx, dce); err != nil {
		if datastore.IsErrNoSuchEntity(err) {
			logging.Infof(ctx, "cannot find device id %s in datastore, no sync", dcID)
			return nil
		}
		return errors.Annotate(err, "fail to get device config by id %s", dcID).Err()
	}

	var dc device.Config
	if err := proto.Unmarshal(dce.DeviceConfig, &dc); err != nil {
		return errors.Annotate(err, "fail to unmarshal device config for id %s", dce.ID).Err()
	}
	spec := &inventory.CommonDeviceSpecs{
		Labels: &inventory.SchedulableLabels{},
	}
	inventory.ConvertDeviceConfig(&dc, spec)
	logging.Infof(ctx, "successfully convert device config")
	inventory.CopyDCAmongLabels(sl, spec.GetLabels())
	logging.Infof(ctx, "successfully copy device config")
	return nil
}

// GetDeviceConfig fetch device configs from git.
func GetDeviceConfig(ctx context.Context, gitilesC gitiles.GitilesClient) (map[string]*device.Config, error) {
	cfg := config.Get(ctx).Inventory
	gf := gitstore.FilesSpec{
		Project: cfg.DeviceConfigProject,
		Branch:  cfg.DeviceConfigBranch,
		Paths:   []string{cfg.DeviceConfigPath},
	}
	files, err := gitstore.FetchFiles(ctx, gitilesC, gf)
	if err != nil {
		return nil, errors.Annotate(err, "fail to fetch device configs based on %s:%s:%v", gf.Project, gf.Branch, gf.Paths).Err()
	}
	data, ok := files[cfg.DeviceConfigPath]
	if !ok {
		return nil, errors.Reason("no device config in path %s/%s", cfg.DeviceConfigProject, cfg.DeviceConfigPath).Err()
	}

	unmarshaler := jsonpb.Unmarshaler{AllowUnknownFields: true}
	allConfigs := device.AllConfigs{}
	err = unmarshaler.Unmarshal(bytes.NewReader([]byte(data)), &allConfigs)
	if err != nil {
		return nil, errors.Annotate(err, "fail to unmarshal device config").Err()
	}
	deviceConfigs := make(map[string]*device.Config, 0)
	for _, c := range allConfigs.Configs {
		id := getIDForDeviceConfig(ctx, c)
		if _, found := deviceConfigs[id]; found {
			logging.Infof(ctx, "found duplicated id: %s id")
		} else {
			deviceConfigs[id] = c
		}
	}
	return deviceConfigs, nil
}

// SaveDeviceConfig save device configs to datastore for updateDutLabel check.
func SaveDeviceConfig(ctx context.Context, deviceConfigs map[string]*device.Config) error {
	updated := time.Now().UTC()
	dcs := make([]*deviceConfigEntity, 0, len(deviceConfigs))
	for configID, v := range deviceConfigs {
		key := datastore.MakeKey(ctx, DeviceConfigKind, configID)
		res, err := datastore.Exists(ctx, key)
		if err != nil {
			logging.Warningf(ctx, "fail to check if device config id %s exists", configID)
		}
		if err == nil && res.Any() {
			logging.Warningf(ctx, "device config id %s already exists", configID)
		}
		data, err := proto.Marshal(v)
		if err != nil {
			logging.Warningf(ctx, "cannot marshal device config %s (id %s)", v.String(), configID)
			continue
		}
		dcs = append(dcs, &deviceConfigEntity{
			ID:           configID,
			DeviceConfig: data,
			Updated:      updated,
		})
	}
	if err := datastore.Put(ctx, dcs); err != nil {
		return errors.Annotate(err, "save device config").Err()
	}
	return nil
}

const (
	// DeviceConfigKind is the datastore entity kind for device config entities.
	DeviceConfigKind string = "DeviceConfig"
)

type deviceConfigEntity struct {
	_kind string `gae:"$kind,DeviceConfig"`
	ID    string `gae:"$id"`
	// Serialized *device.Config
	DeviceConfig []byte `gae:",noindex"`
	Updated      time.Time
}
