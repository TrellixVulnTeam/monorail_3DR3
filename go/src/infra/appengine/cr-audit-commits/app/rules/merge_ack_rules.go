// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rules

import (
	"context"
	"go.chromium.org/luci/common/logging"
)

// AcknowledgeMerge is a Rule that acknowledges any merge into a release branch.
type AcknowledgeMerge struct{}

// GetName returns the name of the rule.
func (rule AcknowledgeMerge) GetName() string {
	return "AcknowledgeMerge"
}

// Run executes the rule.
func (rule AcknowledgeMerge) Run(ctx context.Context, ap *AuditParams, rc *RelevantCommit, cs *Clients) (*RuleResult, error) {
	result := &RuleResult{}
	result.RuleResultStatus = RuleSkipped
	bugID, err := bugIDFromCommitMessage(rc.CommitMessage)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Found no bug on relevant commit %s", rc.CommitHash)
		return result, nil
	}
	result.RuleResultStatus = NotificationRequired
	result.MetaData, _ = SetToken(ctx, "BugNumbers", bugID, result.MetaData)
	return result, nil
}
