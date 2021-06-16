// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"fmt"
	"regexp"
	"strconv"
	"sync"
	"time"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	structpb "github.com/golang/protobuf/ptypes/struct"
	"google.golang.org/genproto/protobuf/field_mask"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"go.chromium.org/luci/buildbucket"
	"go.chromium.org/luci/buildbucket/deprecated"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/milo"
	"go.chromium.org/luci/logdog/common/types"
	"go.chromium.org/luci/lucictx"
)

// buildUpdater implements an annotee callback for updated annotations
// and makes buildbucket.v2.Builds.UpdateBuild RPCs accordingly.
type buildUpdater struct {
	annAddr    *types.StreamAddr
	buildID    int64
	buildToken string
	client     buildbucketpb.BuildsClient

	// annotations contains latest state of the build in the form of
	// binary serialized milo.Step.
	// Must not be closed.
	annotations chan []byte
}

// Run calls client.UpdateBuild on new b.annotations.
// Logs transient errors and returns a fatal error, if any.
// Stops when done is closed or ctx is done.
func (b *buildUpdater) Run(ctx context.Context, done <-chan struct{}) error {
	return b.run(ctx, done, b.updateBuildBytes)
}

func (b *buildUpdater) run(
	ctx context.Context,
	done <-chan struct{},
	update func(ctx context.Context, annBytes []byte) error,
) error {
	cond := sync.NewCond(&sync.Mutex{})
	// protected by cond.L
	var state struct {
		latest    []byte
		latestVer int
		done      bool
	}

	// Listen to new requests.
	go func() {
		locked := func(f func()) {
			cond.L.Lock()
			f()
			cond.L.Unlock()
			cond.Signal()
		}

		for {
			select {
			case ann := <-b.annotations:
				locked(func() {
					state.latest = ann
					state.latestVer++
				})

			case <-ctx.Done():
				locked(func() { state.done = true })
			case <-done:
				locked(func() { state.done = true })
			}
		}
	}()

	// Send requests.

	var sentVer int
	// how long did we wait after most recent update call
	var errSleep time.Duration
	var lastRequestTime time.Time
	for {
		// Ensure at least 1s between calls.
		if !lastRequestTime.IsZero() {
			ellapsed := clock.Since(ctx, lastRequestTime)
			if d := time.Second - ellapsed; d > 0 {
				clock.Sleep(clock.Tag(ctx, "update-build-distance"), d)
			}
		}

		// Wait for news.
		cond.L.Lock()
		if sentVer == state.latestVer && !state.done {
			cond.Wait()
		}
		local := state
		cond.L.Unlock()

		var err error
		if sentVer != local.latestVer {
			lastRequestTime = clock.Now(ctx)

			err = update(ctx, local.latest)
			switch status.Code(errors.Unwrap(err)) {
			case codes.OK:
				errSleep = 0
				sentVer = local.latestVer

			case codes.InvalidArgument:
				// This is fatal.
				return err

			default:
				// Hope another future request will succeed.
				// There is another final UpdateBuild call anyway.
				logging.Errorf(ctx, "failed to update build: %s", err)

				// Sleep.
				if errSleep == 0 {
					errSleep = time.Second
				} else if errSleep < 16*time.Second {
					errSleep *= 2
				}
				logging.Debugf(ctx, "will sleep for %s", errSleep)

				clock.Sleep(clock.Tag(ctx, "update-build-error"), errSleep)
			}
		}

		if local.done {
			return err
		}
	}
}

// updateBuildBytes is a version of updateBuild that accepts raw annotation
// bytes.
func (b *buildUpdater) updateBuildBytes(ctx context.Context, annBytes []byte) error {
	ann := &milo.Step{}
	if err := proto.Unmarshal(annBytes, ann); err != nil {
		return errors.Annotate(err, "failed to parse annotation proto").Err()
	}
	req, err := b.ParseAnnotations(ctx, ann)
	if err != nil {
		return errors.Annotate(err, "failed to parse UpdateBuild request").Err()
	}

	req.Build.Status = buildbucketpb.Status_STARTED
	req.UpdateMask.Paths = append(req.UpdateMask.Paths, "build.status")

	return b.UpdateBuild(ctx, req)
}

// UpdateBuild updates a build on the buildbucket server.
// Includes a build token in the request.
func (b *buildUpdater) UpdateBuild(ctx context.Context, req *buildbucketpb.UpdateBuildRequest) error {
	ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs(buildbucket.BuildTokenHeader, b.buildToken))
	_, err := b.client.UpdateBuild(ctx, req)
	return err
}

// ParseAnnotations converts an annotation proto to a UpdateBuildRequest that
// updates steps, output properties and output gitiles commit.
func (b *buildUpdater) ParseAnnotations(ctx context.Context, ann *milo.Step) (*buildbucketpb.UpdateBuildRequest, error) {
	updatePaths := []string{"build.steps", "build.output.properties"}
	prefix, _ := b.annAddr.Path.Split()
	fullPrefix := fmt.Sprintf("%s/%s", b.annAddr.Project, prefix)
	steps, err := deprecated.ConvertBuildSteps(ctx, ann.Substep, b.annAddr.Host, fullPrefix)
	if err != nil {
		return nil, errors.Annotate(err, "failed to parse steps from an annotation proto").Err()
	}

	props, err := milo.ExtractProperties(ann)
	if err != nil {
		return nil, errors.Annotate(err, "failed to extract properties from an annotation proto").Err()
	}

	delete(props.Fields, "buildbucket")
	delete(props.Fields, "$recipe_engine/buildbucket")

	// Extract output commit
	// The other side: https://cs.chromium.org/chromium/infra/recipes-py/recipe_modules/buildbucket/api.py?q=set_output_gitiles_commit
	var outputCommit *buildbucketpb.GitilesCommit
	const outputCommitProp = "$recipe_engine/buildbucket/output_gitiles_commit"
	if f, ok := props.Fields[outputCommitProp]; ok {
		dict := f.GetStructValue().GetFields()
		outputCommit = &buildbucketpb.GitilesCommit{
			Host:     dict["host"].GetStringValue(),
			Project:  dict["project"].GetStringValue(),
			Ref:      dict["ref"].GetStringValue(),
			Id:       dict["id"].GetStringValue(),
			Position: uint32(dict["position"].GetNumberValue()),
		}
		delete(props.Fields, outputCommitProp)
	}
	if outputCommit == nil {
		if outputCommit, err = outputCommitFromLegacyProperties(props); err != nil {
			logging.Warningf(ctx, "failed to parse output commit from legacy properties: %s", err)
		}
	}
	if outputCommit != nil {
		updatePaths = append(updatePaths, "build.output.gitiles_commit")
	}

	tags := parseAdditionalTags(props)
	if len(tags) > 0 {
		updatePaths = append(updatePaths, "build.tags")
	}

	return &buildbucketpb.UpdateBuildRequest{
		Build: &buildbucketpb.Build{
			Id:    b.buildID,
			Steps: steps,
			Output: &buildbucketpb.Build_Output{
				Properties:    props,
				GitilesCommit: outputCommit,
			},
			Tags: tags,
		},
		UpdateMask: &field_mask.FieldMask{Paths: updatePaths},
	}, nil
}

// regular expressions for outputCommitFromLegacyProperties.
var (
	commitPositionRe = regexp.MustCompile(`^(refs/[^@]+)@{#(\d+)}$`)
	sha1HexRe        = regexp.MustCompile(`^[0-9a-f]{40}$`)
	refRe            = regexp.MustCompile(`^refs/`)
)

// outputCommitFromLegacyProperties synthesizes an output commit from
// legacy got_revision and got_revision_cp properties.
func outputCommitFromLegacyProperties(props *structpb.Struct) (*buildbucketpb.GitilesCommit, error) {
	gotRevision := props.Fields["got_revision"].GetStringValue()
	if gotRevision == "" {
		return nil, nil
	}

	// Retrieve gitiles host and project from build input, using buildbucket
	// internal property.
	buildStruct := props.Fields["$recipe_engine/buildbucket"].GetStructValue().GetFields()["build"].GetStructValue()
	if buildStruct == nil {
		return nil, fmt.Errorf("no buildbucket build property")
	}
	build := &buildbucketpb.Build{}
	if err := structToMessage(buildStruct, build); err != nil {
		return nil, err
	}
	ret := &buildbucketpb.GitilesCommit{}
	switch {
	case build.GetInput().GetGitilesCommit() != nil:
		ic := build.GetInput().GetGitilesCommit()
		ret.Host = ic.Host
		ret.Project = ic.Project
		ret.Ref = ic.Ref
	case len(build.GetInput().GetGerritChanges()) == 1:
		cl := build.GetInput().GetGerritChanges()[0]
		ret.Host = cl.Host
		ret.Project = cl.Project
	}
	if ret.Host == "" || ret.Project == "" {
		return nil, fmt.Errorf("failed to determine gitiles host or project")
	}
	if ret.Ref == "" {
		ret.Ref = "refs/heads/master"
	}

	cp := props.Fields["got_revision_cp"].GetStringValue()

	// Parse got_revision.
	switch {
	case sha1HexRe.MatchString(gotRevision):
		ret.Id = gotRevision

	case refRe.MatchString(gotRevision):
		if cp != "" {
			return nil, errors.Reason("got_revision is a ref and got_revision_cp is provided; this is unexpected").Err()
		}
		ret.Ref = gotRevision
		return ret, nil

	default:
		return nil, errors.Reason("unrecognized got_revision format: %q", gotRevision).Err()
	}

	// Parse commit position.
	if cp != "" {
		m := commitPositionRe.FindStringSubmatch(cp)
		if m == nil {
			return nil, errors.Reason("unexpected got_revision_cp format: %q", cp).Err()
		}
		ret.Ref = m[1]
		pos, err := strconv.ParseUint(m[2], 10, 32)
		if err != nil {
			return nil, errors.Annotate(err, "malformed uint32 in got_revision_cp").Err()
		}
		ret.Position = uint32(pos)
	}

	return ret, nil
}

// structToMessage converts the struct to msg via JSONPB format.
// This is inefficient.
func structToMessage(s *structpb.Struct, msg proto.Message) error {
	buf := &bytes.Buffer{}
	if err := (&jsonpb.Marshaler{}).Marshal(buf, s); err != nil {
		return err
	}
	return (&jsonpb.Unmarshaler{AllowUnknownFields: true}).Unmarshal(buf, msg)
}

// AnnotationUpdated is an annotee.Options.AnnotationUpdated callback
// that enqueues an UpdateBuild RPC.
// Assumes annBytes will stay unchanged.
func (b *buildUpdater) AnnotationUpdated(annBytes []byte) {
	b.annotations <- annBytes
}

// readBuildSecrets populates c.buildSecrets from swarming secret bytes, if any.
func readBuildSecrets(ctx context.Context) (*buildbucketpb.BuildSecrets, error) {
	secrets := &buildbucketpb.BuildSecrets{}
	swarming := lucictx.GetSwarming(ctx)
	if swarming != nil {
		if err := proto.Unmarshal(swarming.SecretBytes, secrets); err != nil {
			return nil, err
		}
	}

	return secrets, nil
}

// parseAdditionalTags parses tags from output properties.
// The other side: https://cs.chromium.org/chromium/infra/recipes-py/recipe_modules/buildbucket/api.py?q=add_tags_to_current_build
func parseAdditionalTags(props *structpb.Struct) []*buildbucketpb.StringPair {
	tags := []*buildbucketpb.StringPair{}
	tagsProp := "$recipe_engine/buildbucket/runtime-tags"
	v, ok := props.Fields[tagsProp]
	if !ok {
		return tags
	}

	dict := v.GetStructValue().GetFields()
	for key, values := range dict {
		for _, value := range values.GetListValue().GetValues() {
			tags = append(tags, &buildbucketpb.StringPair{
				Key:   key,
				Value: value.GetStringValue(),
			})
		}
	}
	delete(props.Fields, tagsProp)
	return tags
}
