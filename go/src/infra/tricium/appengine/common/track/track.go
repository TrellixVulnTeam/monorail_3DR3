// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package track implements shared tracking functionality for the Tricium service modules.
//
// Overview diagram:
//
//    +-----------------+
//    |AnalyzeRequest   |
//    |id=<generated_id>|
//    +---+-------------+
//        |
//        +----------------------+
//        |                      |
//    +---+----------------+ +---+-------+
//    |AnalyzeRequestResult| |WorkflowRun|
//    |id=1                | |id=1       |
//    +---+----------------+ +-----------+
//                               |
//                               +----------------------+
//                               |                      |
//                           +---+-------------+ +---+-------------+
//                           |WorkflowRunResult| |FunctionRun      |
//                           |id=1             | |id=<functionName>|
//                           +-----------------+ +---+-------------+
//                                                   |
//                               +-------------------+
//                               |                   |
//                           +---+-------------+ +---+----------------------+
//                           |FunctionRunResult| |WorkerRun                 |
//                           |id=1             | |id=<functionName_platform>|
//                           +-----------------+ +---+----------------------+
//                                                   |
//                                          +--------+---------+
//                                          |                  |
//                                      +---+-----------+ +----+------------+
//                                      |WorkerRunResult| |Comment          |
//                                      |id=1           | |id=<generated_id>|
//                                      +---------------+ +----+------------+
//                                                             |
//                                          +------------------+
//                                          |                  |
//                                       +--+-------------+ +--+------------+
//                                       |CommentSelection| |CommentFeedback|
//                                       |id=1            | |id=1           |
//                                       +-----------   --+ +---------------+
//
package track

import (
	"bytes"
	"context"
	"strings"
	"time"

	"github.com/golang/protobuf/jsonpb"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"

	tricium "infra/tricium/api/v1"
)

// AnalyzeRequest represents one Tricium Analyze RPC request.
//
// Immutable root entry.
type AnalyzeRequest struct {
	// LUCI datastore ID field with generated value.
	ID int64 `gae:"$id"`
	// Time when the corresponding request was received.
	Received time.Time
	// The name of the project in luci-config that specifies
	// the configuration and project details that are used in
	// this analyze request.
	Project string
	// Files listed in the request, including metadata.
	Files []tricium.Data_File `gae:",noindex"`
	// Paths is retained for backward compatibility but should not be used
	// in new entities. Files is used instead. See crbug.com/934246.
	Paths []string `gae:",noindex"`
	// Full URL of Git repository hosting files in the request.
	GitURL string `gae:",noindex"`
	// Git ref to use in the git repo.
	GitRef string `gae:",noindex"`
	// Gerrit details if applicable.
	// GerritHost and GerritChange can be used to uniquely identify a Gerrit
	// change; these fields are indexed to enable querying for all runs for a
	// particular change.
	GerritHost    string
	GerritProject string `gae:",noindex"`
	// GerritChange includes project, branch, and Change-Id footer.
	GerritChange string
	// Disabled Gerrit reporting means that no progress or result messages
	// are sent to Gerrit.
	GerritReportingDisabled bool `gae:",noindex"`
	// Commit message provided by Gerrit if applicable. This may not be present
	// in older entities, and may be empty for non-Gerrit requests.
	CommitMessage string `gae:",noindex"`
}

// AnalyzeRequestResult tracks the state of a tricium.Analyze request.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to AnalyzeRequest entity) fields.
type AnalyzeRequestResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// State of the Analyze request; running, success, or failure.
	State tricium.State
}

// WorkflowRun declares a request to execute a Tricium workflow.
//
// Immutable root of the complete workflow execution.
// LUCI datastore ID (=1) and parent (=key to AnalyzeRequest entity) fields.
type WorkflowRun struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of analyzers included in this workflow.
	//
	// Included here to allow for direct access without queries.
	Functions []string `gae:",noindex"`
	// Isolate server URL.
	IsolateServerURL string `gae:",noindex"`
	// Swarming server URL.
	SwarmingServerURL string `gae:",noindex"`
	// Buildbucket server hostname.
	BuildbucketServerHost string `gae:",noindex"`
}

// WorkflowRunResult tracks the state of a workflow run.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to WorkflowRun entity) fields.
type WorkflowRunResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// State of the parent request; running, success, or failure.
	//
	// This state is an aggregation of the run state of triggered analyzers.
	State tricium.State
	// Number of comments produced for this analyzer.
	// If results were merged, then this is the merged number of results.
	NumComments int
	// If the results for this analyzer were merged.
	HasMergedResults bool
}

// FunctionRun declares a request to execute an analyzer.
//
// Immutable entity.
// LUCI datastore ID (="FunctionName") and parent (=key to WorkflowRun entity) fields.
type FunctionRun struct {
	ID     string  `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of workers launched for this function.
	//
	// Included here to allow for direct access without queries.
	Workers []string `gae:",noindex"`
	// Owner email and monorail component for this function.
	//
	// Included here for convenience so that this information can
	// later be used to populate a bug filing template.

	// Cached here from the Function instance so this information can
	// later be used to populate a bug filing template, even if the
	// Function instance changed in the meantime.
	Owner             string `gae:",noindex"`
	MonorailComponent string `gae:",noindex"`
}

// FunctionRunResult tracks the state of an analyzer run.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to FunctionRun entity) fields.
type FunctionRunResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of analyzer.
	//
	// Added here in addition to in the parent key for indexing.
	Name string
	// State of the parent analyzer run; running, success, or failure.
	//
	// This state is an aggregation of the run state of triggered analyzer workers.
	State tricium.State

	// Number of comments produced for this analyzer.
	//
	// If results were merged, then this is the merged number of results.
	NumComments int

	// If the results for this analyzer were merged.
	HasMergedResults bool
}

// WorkerRun declare a request to execute an analyzer worker.
//
// Immutable entity.
// LUCI datastore ID (="WorkerName") and parent (=key to FunctionRun entity) fields.
type WorkerRun struct {
	ID     string  `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Platform this worker is producing results for.
	Platform tricium.Platform_Name
	// Names of workers succeeding this worker in the workflow.
	Next []string `gae:",noindex"`
}

// WorkerRunResult tracks the state of a worker run.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to WorkerRun entity) fields.
type WorkerRunResult struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Name of worker.
	//
	// Stored here, in addition to in the parent ID, for indexing
	// and convenience.
	Name string
	// Name of the function for this worker run.
	//
	// Stored here, in addition to in the ID of ancestors, for indexing
	// and convenience.
	Function string
	// Platform this worker is running on.
	Platform tricium.Platform_Name
	// State of the parent worker run; running, success, or failure.
	State tricium.State
	// Hash to the isolated input provided to the corresponding swarming task.
	IsolatedInput string `gae:",noindex"`

	// Outputs: IsolatedOutput or BuildbucketOutput
	// One and only one of these two fields should be populated by the appropriate
	// service.

	// Hash to the isolated output collected from the corresponding swarming task,
	// if applicable.
	IsolatedOutput string `gae:",noindex"`
	// Output as collected from the corresponding buildbucket run, if applicable.
	BuildbucketOutput  string `gae:",noindex"`
	SwarmingTaskID     string `gae:",noindex"`
	BuildbucketBuildID int64  `gae:",noindex"`
	// Number of comments produced by this worker.
	NumComments int `gae:",noindex"`
	// Tricium result encoded as JSON.
	Result string `gae:",noindex"`
}

// Comment tracks a comment generated by a worker.
//
// Immutable entity.
// LUCI datastore ID (=generated) and parent (=key to WorkerRun entity) fields.
type Comment struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Comment UUID.
	//
	// This is the external ID for the comment and the ID used in any external
	// communication about the comment by the service. For instance,
	// this is the ID used to report feedback for a comment.
	UUID string
	// Comment creation time.
	//
	// Comment creation time in terms of when it is tracked in the service not
	// when it is created by the analyzer. This timestamp allows for filtering
	// on time when summarizing analyzer feedback.
	CreationTime time.Time
	// Comment encoded as JSON.
	//
	// The comment must be an encoded tricium.Data_Comment JSON message
	Comment []byte `gae:",noindex"`
	// Analyzer function name.
	//
	// This field allows for filtering on analyzer name.
	Analyzer string
	// Comment category with subcategories.
	//
	// This includes the analyzer name, e.g., "ClangTidy/llvm-header-guard".
	Category string
	// Platforms this comment applies to.
	//
	// This is a int64 bit map using the tricium.Platform_Name number
	// values for platforms.
	Platforms int64
}

// UnpackComment returns the proto encoded Comment.
func (c *Comment) UnpackComment(ctx context.Context, out *tricium.Data_Comment) error {
	if c.Comment == nil {
		return errors.New("missing comment.Comment")
	}
	if err := jsonpb.Unmarshal(bytes.NewReader(c.Comment), out); err != nil {
		return errors.Annotate(err, "failed to unpack proto tricium.Data_Comment").Err()
	}
	return nil
}

// CommentSelection tracks selection of comments.
//
// When an analyzer has several workers running the analyzer using different
// configurations the resulting comments are merged to avoid duplication of
// results for users.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to Comment entity) fields.
type CommentSelection struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Whether this comments was included in the overall result of the
	// enclosing request.
	//
	// All comments are included by default, but comments may need to be
	// merged in the case when comments for a category are produced for
	// multiple platforms.
	Included bool
}

// CommentFeedback tracks 'not useful' user feedback for a comment.
//
// Mutable entity.
// LUCI datastore ID (=1) and parent (=key to Comment entity) fields.
type CommentFeedback struct {
	ID     int64   `gae:"$id"`
	Parent *ds.Key `gae:"$parent"`
	// Number of 'not useful' clicks.
	// TODO(qyearsley): Store information to prevent multiple clicks by the
	// same user.
	NotUsefulReports int
}

const workerSeparator = "_"

// ExtractFunctionPlatform extracts the analyzer and platform name from a
// worker name.
//
// The worker name must be on the form 'FunctionName_PLATFORM'.
func ExtractFunctionPlatform(workerName string) (string, string, error) {
	parts := strings.SplitN(workerName, workerSeparator, 2)
	if len(parts) != 2 {
		return "", "", errors.Reason("malformed worker name: %s", workerName).Err()
	}
	return parts[0], parts[1], nil

}
