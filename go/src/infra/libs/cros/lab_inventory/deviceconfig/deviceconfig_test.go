// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package deviceconfig

import (
	"testing"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/chromiumos/infra/proto/go/device"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/proto/gitiles"
)

var deviceConfigJSON = `
{
	"configs": [
		{
			"unkonwnField": "hahaha",
			"id": {
				"platformId": {
					"value": "Arcada"
				},
				"modelId": {
					"value": "arcada"
				},
				"variantId": {}
			},
			"hardwareFeatures": [
				"HARDWARE_FEATURE_BLUETOOTH",
				"HARDWARE_FEATURE_TOUCHSCREEN"
			],
			"power": "POWER_SUPPLY_BATTERY",
			"storage": "STORAGE_NVME",
			"videoAccelerationSupports": [
				"VIDEO_ACCELERATION_H264",
				"VIDEO_ACCELERATION_ENC_MJPG"
			],
			"soc": "SOC_WHISKEY_LAKE_U"
		},
		{
			"id": {
				"platformId": {
					"value": "Arcada"
				},
				"modelId": {
					"value": "arcada"
				},
				"variantId": {
					"value": "2"
				}
			},
			"hardwareFeatures": [
				"HARDWARE_FEATURE_TOUCHPAD",
				"HARDWARE_FEATURE_TOUCHSCREEN"
			],
			"power": "POWER_SUPPLY_BATTERY",
			"storage": "STORAGE_NVME",
			"videoAccelerationSupports": [
				"VIDEO_ACCELERATION_MJPG",
				"VIDEO_ACCELERATION_ENC_MJPG"
			],
			"soc": "SOC_WHISKEY_LAKE_U"
		}
	]
}
`

func TestUpdateDatastore(t *testing.T) {
	Convey("Test update device config cache", t, func() {
		ctx := gaetesting.TestingContextWithAppID("go-test")
		ctl := gomock.NewController(t)
		defer ctl.Finish()

		gitilesMock := gitiles.NewMockGitilesClient(ctl)
		gitilesMock.EXPECT().DownloadFile(gomock.Any(), gomock.Any()).Return(
			&gitiles.DownloadFileResponse{
				Contents: deviceConfigJSON,
			},
			nil,
		)
		Convey("Happy path", func() {
			err := UpdateDatastore(ctx, gitilesMock, "", "", "")
			So(err, ShouldBeNil)
			// There should be 2 entities created in datastore.
			var cfgs []*devcfgEntity
			datastore.GetTestable(ctx).Consistent(true)
			err = datastore.GetAll(ctx, datastore.NewQuery(entityKind), &cfgs)
			So(err, ShouldBeNil)
			So(cfgs, ShouldHaveLength, 2)
		})
	})
}

func TestGetCachedDeviceConfig(t *testing.T) {
	ctx := gaetesting.TestingContextWithAppID("go-test")

	Convey("Test get device config from datastore", t, func() {
		err := datastore.Put(ctx, []devcfgEntity{
			{ID: "platform.model.variant1"},
			{ID: "platform.model.variant2"},
			{
				ID:        "platform.model.variant3",
				DevConfig: []byte("bad data"),
			},
		})
		So(err, ShouldBeNil)

		Convey("Happy path", func() {
			devcfg, err := GetCachedConfig(ctx, []*device.ConfigId{
				{
					PlatformId: &device.PlatformId{Value: "platform"},
					ModelId:    &device.ModelId{Value: "model"},
					VariantId:  &device.VariantId{Value: "variant1"},
					BrandId:    &device.BrandId{Value: "brand1"},
				},
				{
					PlatformId: &device.PlatformId{Value: "platform"},
					ModelId:    &device.ModelId{Value: "model"},
					VariantId:  &device.VariantId{Value: "variant2"},
					BrandId:    &device.BrandId{Value: "brand2"},
				},
			})
			So(err, ShouldBeNil)
			So(devcfg, ShouldHaveLength, 2)
		})

		Convey("Device id is case insensitive", func() {
			devcfg, err := GetCachedConfig(ctx, []*device.ConfigId{
				{
					PlatformId: &device.PlatformId{Value: "PLATFORM"},
					ModelId:    &device.ModelId{Value: "model"},
					VariantId:  &device.VariantId{Value: "variant1"},
					BrandId:    &device.BrandId{Value: "brand1"},
				},
			})
			So(err, ShouldBeNil)
			So(devcfg, ShouldHaveLength, 1)
		})

		Convey("Data unmarshal error", func() {
			_, err := GetCachedConfig(ctx, []*device.ConfigId{
				{
					PlatformId: &device.PlatformId{Value: "platform"},
					ModelId:    &device.ModelId{Value: "model"},
					VariantId:  &device.VariantId{Value: "variant3"},
					BrandId:    &device.BrandId{Value: "brand3"},
				},
			})
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "unmarshal config data")
		})

		Convey("Get nonexisting data", func() {
			_, err := GetCachedConfig(ctx, []*device.ConfigId{
				{
					PlatformId: &device.PlatformId{Value: "platform"},
					ModelId:    &device.ModelId{Value: "model"},
					VariantId:  &device.VariantId{Value: "variant-nonexisting"},
					BrandId:    &device.BrandId{Value: "nonexisting"},
				},
			})
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "no such entity")
		})
	})
}

func TestGetAllCachedConfig(t *testing.T) {
	Convey("Test get all device config cache", t, func() {
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		err := datastore.Put(ctx, []devcfgEntity{
			{ID: "platform.model.variant1"},
			{ID: "platform.model.variant2"},
			{
				ID:        "platform.model.variant3",
				DevConfig: []byte("bad data"),
			},
		})
		So(err, ShouldBeNil)

		devConfigs, err := GetAllCachedConfig(ctx)
		So(err, ShouldBeNil)
		So(devConfigs, ShouldHaveLength, 2)
		for dc := range devConfigs {
			So(dc.GetId(), ShouldBeNil)
		}
	})
}

func TestDeviceConfigsExists(t *testing.T) {
	ctx := gaetesting.TestingContextWithAppID("go-test")

	Convey("Test exists device config in datastore", t, func() {
		err := datastore.Put(ctx, []devcfgEntity{
			{ID: "kunimitsu.lars.variant1"},
			{ID: "arcada.arcada.variant2"},
			{
				ID:        "platform.model.variant3",
				DevConfig: []byte("bad data"),
			},
		})
		So(err, ShouldBeNil)

		Convey("Happy path", func() {
			exists, err := DeviceConfigsExists(ctx, []*device.ConfigId{
				{
					PlatformId: &device.PlatformId{Value: "kunimitsu"},
					ModelId:    &device.ModelId{Value: "lars"},
					VariantId:  &device.VariantId{Value: "variant1"},
				},
				{
					PlatformId: &device.PlatformId{Value: "arcada"},
					ModelId:    &device.ModelId{Value: "arcada"},
					VariantId:  &device.VariantId{Value: "variant2"},
				},
			})
			So(err, ShouldBeNil)
			So(exists[0], ShouldBeTrue)
			So(exists[1], ShouldBeTrue)
		})

		Convey("check for nonexisting data", func() {
			exists, err := DeviceConfigsExists(ctx, []*device.ConfigId{
				{
					PlatformId: &device.PlatformId{Value: "platform"},
					ModelId:    &device.ModelId{Value: "model"},
					VariantId:  &device.VariantId{Value: "variant-nonexisting"},
					BrandId:    &device.BrandId{Value: "nonexisting"},
				},
			})
			So(err, ShouldBeNil)
			So(exists[0], ShouldBeFalse)
		})

		Convey("check for existing and nonexisting data", func() {
			exists, err := DeviceConfigsExists(ctx, []*device.ConfigId{
				{
					PlatformId: &device.PlatformId{Value: "platform"},
					ModelId:    &device.ModelId{Value: "model"},
					VariantId:  &device.VariantId{Value: "variant-nonexisting"},
				},
				{
					PlatformId: &device.PlatformId{Value: "arcada"},
					ModelId:    &device.ModelId{Value: "arcada"},
					VariantId:  &device.VariantId{Value: "variant2"},
				},
			})
			So(err, ShouldBeNil)
			So(exists[0], ShouldBeFalse)
			So(exists[1], ShouldBeTrue)
		})
	})
}
