// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

// TestDefaultGitRetryRegexps test expected strings against the resulting regexp
// to ensure that they match.
func TestDefaultGitRetryRegexps(t *testing.T) {
	t.Parallel()

	Convey(`Default Git retry regexps match expected lines`, t, func() {
		for _, line := range []string{
			`!   [remote rejected] (error in hook) $TRAILING_CONTENT`,
			`!   [remote rejected] (failed to lock) $TRAILING_CONTENT`,
			`!   [remote rejected] (error in Gerrit backend) $TRAILING_CONTENT`,
			`remote error: Internal Server Error`,
			`fatal: Couldn't find remote ref $TRAILING_CONTENT`,
			`git fetch_pack: expected ACK/NAK, got $TRAILING_CONTENT`,
			`protocol error: bad pack header`,
			`The remote end hung up unexpectedly`,
			`fatal: The remote end hung up upon initial contact`,
			`TLS packet with unexpected length was received`,
			`RPC failed; result=12345, HTTP code = 500`,
			`Connection timed out`,
			`repository cannot accept new pushes; contact support`,
			`Service Temporarily Unavailable`,
			`Connection refused`,
			`connection refused`, // Ignore case.
			`The requested URL returned error: 598`,
			`Connection reset by peer`,
			`Unable to look up $TRAILING_CONTENT`,
			`Couldn't resolve host`,
			`unable to access 'URL': Operation too slow. Less than 1000 bytes/sec transferred the last 300 seconds`,
			`Unknown SSL protocol error in connection to foo.example.com:443`,
			`Revision 2c6a80dd54ea51f704934f620f934f6f3a25207d of patch set 1 does not match refs/changes/02/1094702/1 for change`,
			`fatal: remote error: Git repository not found`,
			`Couldn't connect to server`,
			`transfer closed with outstanding read data remaining`,
			`fatal: remote error: Access denied to $TRAILING_CONTENT`,
			`The requested URL returned error: 429`,
			`fatal: expected wanted-ref, got '0176ERR RESOURCE_EXHAUSTED: Resource has been exhausted (e.g. check quota).'`,
		} {
			Convey(fmt.Sprintf(`Matches line: %q`, line), func() {
				So(DefaultGitRetryRegexp.MatchString(line), ShouldBeTrue)
			})
		}
	})
}
