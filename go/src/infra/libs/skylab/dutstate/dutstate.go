// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package dutstate provides utils related to the DUT state cache file
// and the autotest host info file.
package dutstate

import (
	"path/filepath"
)

const (
	hostInfoSubDir     = "host_info_store"
	hostInfoFileSuffix = ".store"
	dutStateSubDir     = "swarming_state"
	dutStateFileSuffix = ".json"
)

// HostInfoFilePath constructs the path to the autotest host info store.
func HostInfoFilePath(resultsDir string, dutName string) string {
	return filepath.Join(resultsDir, hostInfoSubDir, dutName+hostInfoFileSuffix)
}

// CacheFilePath constructs the path to the state cache file.
func CacheFilePath(autotestDir string, dutID string) string {
	return filepath.Join(autotestDir, dutStateSubDir, dutID+dutStateFileSuffix)
}
