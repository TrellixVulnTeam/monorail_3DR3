// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"fmt"
	"strconv"
	"strings"

	"infra/libs/skylab/inventory"

	"go.chromium.org/chromiumos/infra/proto/go/lab"
)

func init() {
	converters = append(converters, boolPeripheralsConverter)
	converters = append(converters, otherPeripheralsConverter)

	reverters = append(reverters, boolPeripheralsReverter)
	reverters = append(reverters, otherPeripheralsReverter)
}

func boolPeripheralsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	p := ls.GetPeripherals()
	if p.GetAudioBoard() {
		labels = append(labels, "audio_board")
	}
	if p.GetAudioBox() {
		labels = append(labels, "audio_box")
	}
	if p.GetAudioLoopbackDongle() {
		labels = append(labels, "audio_loopback_dongle")
	}
	if p.GetCamerabox() {
		labels = append(labels, "camerabox")
	}
	if p.GetChameleon() {
		labels = append(labels, "chameleon")
	}
	if p.GetConductive() {
		// Special case
		labels = append(labels, "conductive:True")
	}
	if p.GetHuddly() {
		labels = append(labels, "huddly")
	}
	if p.GetMimo() {
		labels = append(labels, "mimo")
	}
	if p.GetServo() {
		labels = append(labels, "servo")
	}
	if p.GetSmartUsbhub() {
		labels = append(labels, "smart_usbhub")
	}
	if p.GetStylus() {
		labels = append(labels, "stylus")
	}
	if p.GetWificell() {
		labels = append(labels, "wificell")
	}
	if p.GetRouter_802_11Ax() {
		labels = append(labels, "router_802_11ax")
	}
	return labels
}

func otherPeripheralsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	p := ls.GetPeripherals()

	for _, v := range p.GetChameleonType() {
		const plen = 15 // len("CHAMELEON_TYPE_")
		lv := "chameleon:" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	if invSState := p.GetServoState(); invSState != inventory.PeripheralState_UNKNOWN {
		if labSState, ok := lab.PeripheralState_name[int32(invSState)]; ok {
			lv := "servo_state:" + labSState
			labels = append(labels, lv)
		}
	}

	if servoType := p.GetServoType(); servoType != "" {
		labels = append(labels, fmt.Sprintf("servo_type:%s", servoType))
	}

	if servoUSBState := p.GetServoUsbState(); servoUSBState != inventory.HardwareState_HARDWARE_UNKNOWN {
		if labState, ok := lab.HardwareState_name[int32(p.GetServoUsbState())]; ok {
			name := labState[len("HARDWARE_"):]
			labels = append(labels, "servo_usb_state:"+name)
		}
	}

	if storageState := p.GetStorageState(); storageState != inventory.HardwareState_HARDWARE_UNKNOWN {
		if labState, ok := lab.HardwareState_name[int32(storageState)]; ok {
			name := labState[len("HARDWARE_"):]
			labels = append(labels, "storage_state:"+name)
		}
	}

	if n := p.GetWorkingBluetoothBtpeer(); n > 0 {
		labels = append(labels, fmt.Sprintf("working_bluetooth_btpeer:%d", n))
	}

	if facing := p.GetCameraboxFacing(); facing != inventory.Peripherals_CAMERABOX_FACING_UNKNOWN {
		const plen = 17 // len("CAMERABOX_FACING_")
		lv := "camerabox_facing:" + strings.ToLower(facing.String()[plen:])
		labels = append(labels, lv)
	}

	return labels
}

func boolPeripheralsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	p := ls.GetPeripherals()
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "audio_board":
			*p.AudioBoard = true
		case "audio_box":
			*p.AudioBox = true
		case "audio_loopback_dongle":
			*p.AudioLoopbackDongle = true
		case "camerabox":
			*p.Camerabox = true
		case "chameleon":
			if v != "" {
				continue
			}
			*p.Chameleon = true
		case "conductive":
			// Special case
			if v == "True" {
				*p.Conductive = true
			}
		case "huddly":
			*p.Huddly = true
		case "mimo":
			*p.Mimo = true
		case "servo":
			*p.Servo = true
		case "smart_usbhub":
			*p.SmartUsbhub = true
		case "stylus":
			*p.Stylus = true
		case "wificell":
			*p.Wificell = true
		case "router_802_11ax":
			*p.Router_802_11Ax = true
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}

func otherPeripheralsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	p := ls.GetPeripherals()
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "chameleon":
			if v == "" {
				continue
			}
			vn := "CHAMELEON_TYPE_" + strings.ToUpper(v)
			type t = inventory.Peripherals_ChameleonType
			vals := inventory.Peripherals_ChameleonType_value
			p.ChameleonType = append(p.ChameleonType, t(vals[vn]))
		case "servo_state":
			if v == "" {
				continue
			}
			if labSStateVal, ok := lab.PeripheralState_value[strings.ToUpper(v)]; ok {
				servoState := inventory.PeripheralState(labSStateVal)
				p.ServoState = &servoState
			}
		case "storage_state":
			if labSStateVal, ok := lab.HardwareState_value["HARDWARE_"+strings.ToUpper(v)]; ok {
				state := inventory.HardwareState(labSStateVal)
				p.StorageState = &state
			}
		case "servo_usb_state":
			if labSStateVal, ok := lab.HardwareState_value["HARDWARE_"+strings.ToUpper(v)]; ok {
				state := inventory.HardwareState(labSStateVal)
				p.ServoUsbState = &state
			}
		case "servo_type":
			p.ServoType = &v
		case "working_bluetooth_btpeer":
			i, err := strconv.Atoi(v)
			if err != nil {
				*p.WorkingBluetoothBtpeer = 0
			}
			*p.WorkingBluetoothBtpeer = int32(i)
		case "camerabox_facing":
			vn := "CAMERABOX_FACING_" + strings.ToUpper(v)
			if index, ok := inventory.Peripherals_CameraboxFacing_value[vn]; ok {
				facing := inventory.Peripherals_CameraboxFacing(index)
				p.CameraboxFacing = &facing
			}
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}
