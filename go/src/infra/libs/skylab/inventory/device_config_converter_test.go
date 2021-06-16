// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"bytes"
	"testing"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/kylelemons/godebug/pretty"

	"go.chromium.org/chromiumos/infra/proto/go/device"
)

const fullDeviceConfig = `
{
	"configs": [
		{
			"id": {
				"platformId": {
					"value": "Coral"
				},
				"modelId": {
					"value": "whitetip"
				},
				"variantId": {
					"value": "82"
				},
				"brandId": {
					"value": ""
				}
			},
			"formFactor": "FORM_FACTOR_UNSPECIFIED",
			"gpuFamily": "",
			"graphics": "GRAPHICS_UNSPECIFIED",
			"hardwareFeatures": [
				"HARDWARE_FEATURE_BLUETOOTH",
				"HARDWARE_FEATURE_INTERNAL_DISPLAY",
				"HARDWARE_FEATURE_WEBCAM",
				"HARDWARE_FEATURE_TOUCHPAD",
				"HARDWARE_FEATURE_TOUCHSCREEN",
				"HARDWARE_FEATURE_STYLUS",
				"HARDWARE_FEATURE_DETACHABLE_KEYBOARD",
				"HARDWARE_FEATURE_FINGERPRINT"
			],
			"power": "POWER_SUPPLY_BATTERY",
			"storage": "STORAGE_MMC",
			"videoAccelerationSupports": [
				"VIDEO_ACCELERATION_H264",
				"VIDEO_ACCELERATION_ENC_H264",
				"VIDEO_ACCELERATION_VP8",
				"VIDEO_ACCELERATION_ENC_VP8",
				"VIDEO_ACCELERATION_ENC_VP9"
			],
			"cpu": "ARM64"
		}
	]
}
`

const fullCommonSpec = `
id: "id1"
hostname: "host1"
labels: {
	capabilities: {
		bluetooth: true
		gpu_family: ""
		graphics: ""
		internal_display: true
		power: "battery"
		storage: "mmc"
		touchpad: true
		touchscreen: true
		detachablebase: true
		fingerprint: true
		video_acceleration: 1
		video_acceleration: 2
		video_acceleration: 3
		video_acceleration: 4
		video_acceleration: 6
		webcam: true
	}
	peripherals: {
		stylus: true
	}
	cts_abi: 1
	cts_cpu: 1
}
`

const testCommonSpec = `
id: "id1"
hostname: "host1"
labels: {
	capabilities: {
		bluetooth: false
		internal_display: true
		power: "AC_only"
		storage: "nvme"
		touchpad: true
		touchscreen: true
		video_acceleration: 2
		webcam: false
	}
	peripherals: {
		stylus: false
	}
}
`

var (
	unmarshaler = jsonpb.Unmarshaler{AllowUnknownFields: true}
)

func TestConvertDeviceConfig(t *testing.T) {
	allConfigs := device.AllConfigs{}
	unmarshaler.Unmarshal(bytes.NewReader([]byte(fullDeviceConfig)), &allConfigs)
	var want CommonDeviceSpecs
	if err := proto.UnmarshalText(fullCommonSpec, &want); err != nil {
		t.Fatalf("error unmarshalling example common specs: %s", err.Error())
	}
	var got CommonDeviceSpecs
	if err := proto.UnmarshalText(testCommonSpec, &got); err != nil {
		t.Fatalf("error unmarshalling testing common specs: %s", err.Error())
	}
	ConvertDeviceConfig(allConfigs.Configs[0], &got)
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("device config differ -want +got, %s", diff)
	}
}

func TestCopyDCAmongLabels(t *testing.T) {
	var want CommonDeviceSpecs
	if err := proto.UnmarshalText(fullCommonSpec, &want); err != nil {
		t.Fatalf("error unmarshalling example common specs: %s", err.Error())
	}
	var got CommonDeviceSpecs
	if err := proto.UnmarshalText(testCommonSpec, &got); err != nil {
		t.Fatalf("error unmarshalling testing common specs: %s", err.Error())
	}
	CopyDCAmongLabels(got.Labels, want.Labels)
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("device config differ -want +got, %s", diff)
	}
}

func TestCopyDCAmongEmptyLabels(t *testing.T) {
	var want CommonDeviceSpecs
	if err := proto.UnmarshalText(fullCommonSpec, &want); err != nil {
		t.Fatalf("error unmarshalling example common specs: %s", err.Error())
	}
	var got CommonDeviceSpecs
	if err := proto.UnmarshalText(testCommonSpec, &got); err != nil {
		t.Fatalf("error unmarshalling testing common specs: %s", err.Error())
	}
	got.Labels.Capabilities = nil
	got.Labels.Peripherals = nil
	CopyDCAmongLabels(got.Labels, want.Labels)
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("device config differ -want +got, %s", diff)
	}
}
