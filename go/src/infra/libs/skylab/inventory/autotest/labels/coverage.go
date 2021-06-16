// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolTestCoverageHintsConverter)

	reverters = append(reverters, boolTestCoverageHintsReverter)
}

func boolTestCoverageHintsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	h := ls.GetTestCoverageHints()
	if h.GetChaosDut() {
		labels = append(labels, "chaos_dut")
	}
	if h.GetChaosNightly() {
		labels = append(labels, "chaos_nightly")
	}
	if h.GetChromesign() {
		labels = append(labels, "chromesign")
	}
	if h.GetHangoutApp() {
		labels = append(labels, "hangout_app")
	}
	if h.GetMeetApp() {
		labels = append(labels, "meet_app")
	}
	if h.GetRecoveryTest() {
		labels = append(labels, "recovery_test")
	}
	if h.GetTestAudiojack() {
		labels = append(labels, "test_audiojack")
	}
	if h.GetTestHdmiaudio() {
		labels = append(labels, "test_hdmiaudio")
	}
	if h.GetTestUsbaudio() {
		labels = append(labels, "test_usbaudio")
	}
	if h.GetTestUsbprinting() {
		labels = append(labels, "test_usbprinting")
	}
	if h.GetUsbDetect() {
		labels = append(labels, "usb_detect")
	}
	if h.GetUseLid() {
		labels = append(labels, "use_lid")
	}
	return labels
}

func boolTestCoverageHintsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	h := ls.GetTestCoverageHints()
	for i := 0; i < len(labels); i++ {
		v := labels[i]
		switch v {
		case "chaos_dut":
			*h.ChaosDut = true
		case "chaos_nightly":
			*h.ChaosNightly = true
		case "chromesign":
			*h.Chromesign = true
		case "hangout_app":
			*h.HangoutApp = true
		case "meet_app":
			*h.MeetApp = true
		case "recovery_test":
			*h.RecoveryTest = true
		case "test_audiojack":
			*h.TestAudiojack = true
		case "test_hdmiaudio":
			*h.TestHdmiaudio = true
		case "test_usbaudio":
			*h.TestUsbaudio = true
		case "test_usbprinting":
			*h.TestUsbprinting = true
		case "usb_detect":
			*h.UsbDetect = true
		case "use_lid":
			*h.UseLid = true
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}
