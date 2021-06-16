// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/server/auth"
	gr "golang.org/x/build/gerrit"
	"google.golang.org/appengine"

	admin "infra/tricium/api/admin/v1"
	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	"infra/tricium/appengine/common/config"
	gc "infra/tricium/appengine/common/gerrit"
)

var (
	// Commit message footer values that tell Tricium to skip.
	skipValues = stringset.NewFromSlice("disable", "skip", "no", "none", "false")
	// Strings that won't be treated as footer keys.
	footerKeyBlacklist = stringset.NewFromSlice("Http", "Https")
	paragraphBreak     = regexp.MustCompile(`\n\s*\n`)
	// Pattern for a commit message footer: A key which can have dashes but not
	// spaces, colon and optional space, and a value.
	footerPattern = regexp.MustCompile(`^\s*([\w-]+): *(.*)$`)
)

// Datastore schema diagram for tracked Gerrit projects and CLs:
//
//    +------------------+
//    |GerritProject     |
//    |id=<host:project> |
//    +---+--------------+
//        |
//    +---+-----------+
//    |Change         |
//    |id=<change ID> |
//    +---------------+

// Project represents one Gerrit project, which corresponds to one repo.
//
// Mutable entity. This is used to track the last poll time.
// The kind is "GerritProject"; this is not to be confused with
// `GerritProject` from the Tricium config schema.
type Project struct {
	ID       string `gae:"$id"`
	Instance string
	Project  string
	// Timestamp of last successful poll.
	LastPoll time.Time
}

// Change represents one CL (one Gerrit change).
//
// Mutable entity. This is used to track the latest patchset.
// It's assumed that entities for inactive changes are cleaned up.
type Change struct {
	ID           string  `gae:"$id"`
	Parent       *ds.Key `gae:"$parent"`
	LastRevision string
}

// byUpdateTime sorts changes based on update timestamps.
type byUpdatedTime []gr.ChangeInfo

func (c byUpdatedTime) Len() int           { return len(c) }
func (c byUpdatedTime) Swap(i, j int)      { c[i], c[j] = c[j], c[i] }
func (c byUpdatedTime) Less(i, j int) bool { return c[i].Updated.Time().Before(c[i].Updated.Time()) }

// poll adds a task to poll Gerrit for each project.
func poll(c context.Context, cp config.ProviderAPI) error {
	projects, err := cp.GetAllProjectConfigs(c)
	if err != nil {
		return errors.Annotate(err, "failed to get all service configs").Err()
	}

	// Sort the names so that they are processed in a deterministic order.
	names := make([]string, 0, len(projects))
	for name := range projects {
		names = append(names, name)
	}
	sort.Strings(names)

	var tasks []*tq.Task
	for _, name := range names {
		logging.Debugf(c, "Adding poll-project task for %q.", name)
		task := tq.NewPOSTTask("/gerrit/internal/poll-project", nil)
		bytes, err := proto.Marshal(&admin.PollProjectRequest{Project: name})
		if err != nil {
			return errors.Annotate(err, "failed to marshal PollProjectRequest").Err()
		}
		task.Payload = bytes
		tasks = append(tasks, task)
	}
	if err := tq.Add(c, common.PollProjectQueue, tasks...); err != nil {
		return errors.Annotate(err, "failed to enqueue poll project requests").Err()
	}
	return nil
}

// pollProject polls for new changes for all repos in one LUCI project.
func pollProject(c context.Context, name string, gerrit gc.API, cp config.ProviderAPI) error {
	// Separate repos in one project can be processed in parallel in one request.
	pc, err := cp.GetProjectConfig(c, name)
	if err != nil {
		return errors.Annotate(err, "failed to get project config for %q", name).Err()
	}
	return parallel.FanOutIn(func(taskC chan<- func() error) {
		for _, repo := range pc.Repos {
			repo := repo // Make a separate variable for use in the closure below.
			if repo.GetGerritProject() != nil {
				taskC <- func() error {
					return pollGerritProject(c, name, repo, gerrit)
				}
			}
		}
	})
}

// pollGerritProject polls for changes for one Gerrit project.
//
// One Gerrit project corresponds to one repo; however one LUCI project
// (with one Tricium project config) may include multiple Gerrit projects.
//
// This function could be run concurrently and two parallel runs may query
// Gerrit using the same last poll time. This scenario would lead to duplicate
// analyze tasks. This is OK because the analyze task queue handler will check
// for existing active runs for a change before moving tasks further along the
// pipeline.
//
// Each poll to a Gerrit host and project is logged with a timestamp and last
// seen revisions (within the same second). The timestamp of the most recent
// change in the last poll is used in the next poll, as the value of "after"
// in the query string. If no previous poll has been logged, then a time
// corresponding to zero is used (time.Time{}).
func pollGerritProject(c context.Context, luciProject string, repo *tricium.RepoDetails, gerrit gc.API) error {
	gerritProject := repo.GetGerritProject()
	logging.Debugf(c, "Starting poll-project for project %q.", luciProject)

	// Get last poll data for the given host/project.
	p := &Project{ID: gerritProjectID(gerritProject.Host, gerritProject.Project)}
	if err := ds.Get(c, p); err != nil {
		if err != ds.ErrNoSuchEntity {
			return errors.Annotate(err, "failed to get Project entity").Err()
		}
		logging.Fields{
			"gerritProject": p.ID,
		}.Infof(c, "Found no previous poll for gerrit project.")
		err = nil
		p.Instance = gerritProject.Host
		p.Project = gerritProject.Project
	}

	// If there is no previous poll, store current time and return.
	if p.LastPoll.IsZero() {
		logging.Infof(c, "No previous poll for %s/%s. Storing current timestamp and stopping.",
			gerritProject.Host, gerritProject.Project)
		p.ID = gerritProjectID(gerritProject.Host, gerritProject.Project)
		p.Instance = gerritProject.Host
		p.Project = gerritProject.Project
		p.LastPoll = clock.Now(c).UTC()
		logging.Debugf(c, "Storing project data: %+v", p)
		if err := ds.Put(c, p); err != nil {
			return errors.Annotate(err, "failed to store Project entity").Err()
		}
		return nil
	}

	logging.Debugf(c, "Last poll for %q: %s", p.ID, p.LastPoll)

	// Query for changes updated since last poll. Even though Gerrit supports
	// pagination, we only make one request for a list of changes to avoid using
	// too much memory and time. During super-busy times, this may occasionally
	// mean that some revisions are skipped.
	// TODO(crbug.com/915842): We could add another task to the task queue to poll
	// for the next page, to avoid skipping revisions.
	changes, more, err := gerrit.QueryChanges(c, p.Instance, p.Project, p.LastPoll)
	if err != nil {
		return errors.Annotate(err, "failed to query for change").Err()
	}
	if more {
		logging.Warningf(c, "There were changes beyond the limit %d. Some will be skipped.", gc.MaxChanges)
	}

	// No changes found.
	if len(changes) == 0 {
		logging.Infof(c, "Poll done for %q. No changes found.", luciProject)
		return nil
	}

	// Make sure changes are sorted (most recent change first).
	// This is used to move the poll pointer forward and avoid polling for
	// the same changes more than once. There may still be an overlap but
	// the tracking of change state should be update between polls (and is
	// also guarded by a transaction).
	sort.Sort(sort.Reverse(byUpdatedTime(changes)))

	// Extract updates.
	diff, uchanges, dchanges, err := extractUpdates(c, p, changes)
	if err != nil {
		return errors.Annotate(err, "failed to extract updates").Err()
	}

	// Store updated tracking data.
	if err := ds.RunInTransaction(c, func(c context.Context) error {
		return parallel.FanOutIn(func(taskC chan<- func() error) {
			// Update existing changes and add new ones.
			taskC <- func() error {
				if len(uchanges) == 0 {
					return nil
				}
				return ds.Put(c, uchanges)
			}

			// Delete removed changes.
			taskC <- func() error {
				if len(dchanges) == 0 {
					return nil
				}
				if err := ds.Delete(c, dchanges); err != nil {
					if me, ok := err.(appengine.MultiError); ok {
						for _, merr := range me {
							if merr != ds.ErrNoSuchEntity {
								// Some error other than entity not found, report.
								return err
							}
						}
					} else {
						return err
					}
				}
				return nil
			}

			// Update poll timestamp.
			taskC <- func() error {
				p.LastPoll = changes[0].Updated.Time()
				if err := ds.Put(c, p); err != nil {
					return errors.Annotate(err, "failed to update last poll timestamp").Err()
				}
				return nil
			}
		})
	}, nil); err != nil {
		return err
	}
	logging.Infof(c, "Poll done for %q. Processed %d change(s).", luciProject, len(changes))

	// Filter out the changes that we don't actually want to process.
	diff = filterChanges(c, repo, diff)

	// Convert diff to Analyze requests.
	//
	// Running after the transaction because each seen change will result in one
	// enqueued task and there is a limit on the number of action in a transaction.
	return enqueueAnalyzeRequests(c, luciProject, repo, diff)
}

// extractUpdates extracts change updates, which determines what to analyze.
//
// Compares stored tracked changes with those found in the poll. Takes as
// input the list of changes found in the poll.
//
// Returns the Gerrit changes to analyze, as well as the Change entities
// to update (re-put) and remove.
func extractUpdates(c context.Context, p *Project, pollChanges []gr.ChangeInfo) ([]gr.ChangeInfo, []*Change, []*Change, error) {
	var diff []gr.ChangeInfo
	var uchanges []*Change
	var dchanges []*Change

	// Get list of tracked changes.
	pkey := ds.NewKey(c, "GerritProject", p.ID, 0, nil)
	var trackedChanges []*Change
	for _, change := range pollChanges {
		trackedChanges = append(trackedChanges, &Change{ID: change.ID, Parent: pkey})
	}
	if err := ds.Get(c, trackedChanges); err != nil {
		if me, ok := err.(errors.MultiError); ok {
			for _, merr := range me {
				if merr != nil && merr != ds.ErrNoSuchEntity {
					return diff, uchanges, dchanges, err
				}
			}
		} else if err != ds.ErrNoSuchEntity {
			logging.WithError(err).Errorf(c, "Getting tracked changes failed.")
			return diff, uchanges, dchanges, err
		}
	}

	// Create a map of tracked changes stored in the datastore,
	// so that tracked changes can be looked up by ID when iterating
	// through changes from the poll.
	t := map[string]Change{}
	for _, change := range trackedChanges {
		if change != nil {
			t[change.ID] = *change
		}
	}

	// Compare polled changes to tracked changes, update tracking and add to the
	// diff list when there is an updated revision change.
	for _, change := range pollChanges {
		tc, ok := t[change.ID]
		switch {
		// Untracked open change; start tracking and add to diff list.
		case !ok && isOpen(change):
			logging.Debugf(c, "Found untracked %s change (%s); tracking.", change.Status, change.ID)
			tc.ID = change.ID
			tc.LastRevision = change.CurrentRevision
			uchanges = append(uchanges, &tc)
			diff = append(diff, change)
		// Untracked closed change; move on to the next change.
		case !ok:
			logging.Debugf(c, "Found untracked %s change (%s); leaving untracked.", change.Status, change.ID)
		// Tracked closed change; stop tracking (clean up).
		case !isOpen(change):
			logging.Debugf(c, "Found tracked %s change (%s); removing.", change.Status, change.ID)
			// Because we are only adding keys found by the query,
			// we should not get any NoSuchEntity errors.
			dchanges = append(dchanges, &tc)
		// Open tracked changes with a new revision: update tracking and add
		// to diff list.
		case tc.LastRevision != change.CurrentRevision:
			logging.Debugf(c, "Found tracked %s change (%s) with new revision; updating.", change.Status, change.ID)
			tc.LastRevision = change.CurrentRevision
			uchanges = append(uchanges, &tc)
			diff = append(diff, change)
		// Open tracked change with no new revision: Leave as is.
		default:
			logging.Debugf(c, "Found tracked %s change (%s) with no update; leaving as is.", change.Status, change.ID)
		}
	}
	return diff, uchanges, dchanges, nil
}

// isOpen checks whether a Gerrit CL is considered open.
//
// Status is one of "NEW", "MERGED", or "ABANDONED", where "NEW" indicates
// any open change. ChangeInfo schema: https://goo.gl/M8Csu6
func isOpen(change gr.ChangeInfo) bool {
	return change.Status == "NEW"
}

// filterChanges filters out changes that shouldn't be processed,
// and furthermore filters out files from changes that shouldn't be processed.
//
// Changes that shouldn't be analyzed include:
//   - changes by owners that aren't whitelisted
//   - changes with a "Tricium: no" CL description flag
//   - "Trivial" revisions with no code change
//
// Changes with only deleted files are also filtered out below
// in enqueueAnalyzeRequests, where the list of files is also
// transformed.
func filterChanges(c context.Context, repo *tricium.RepoDetails, changes []gr.ChangeInfo) []gr.ChangeInfo {
	var toProcess []gr.ChangeInfo
	for _, change := range changes {
		curRev := change.Revisions[change.CurrentRevision]
		if hasSkipCommand(&curRev) {
			logging.Fields{
				"changeID": change.ID,
			}.Infof(c, "Skipping change with skip footer.")
			continue
		}
		if curRev.Kind != "REWORK" {
			// REWORK is the revision kind that involves code change.
			// For other possible values of Kind, see:
			// https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#revision-info
			logging.Fields{
				"changeID": change.ID,
				"revision": change.CurrentRevision,
				"kind":     curRev.Kind,
			}.Infof(c, "Skipping revision with no code change.")
			continue
		}
		if !isAuthorAllowed(c, change, repo.WhitelistedGroup) {
			logging.Fields{
				"changeID": change.ID,
			}.Infof(c, "Skipping change with non-whitelisted author.")
			continue
		}
		toProcess = append(toProcess, change)
	}
	return toProcess
}

// enqueueAnalyzeRequests enqueues Analyze requests for the provided Gerrit changes.
func enqueueAnalyzeRequests(c context.Context, luciProject string, repo *tricium.RepoDetails, changes []gr.ChangeInfo) error {
	if len(changes) == 0 {
		return nil
	}
	logging.Infof(c, "Preparing to enqueue Analyze requests for %d changes for project %q.",
		len(changes), luciProject)
	gerritProject := repo.GetGerritProject()

	var tasks []*tq.Task
	for _, change := range changes {
		curRev := change.Revisions[change.CurrentRevision]
		files := triciumFiles(c, curRev.Files)
		if len(files) == 0 {
			logging.Fields{
				"changeID": change.ID,
			}.Infof(c, "Skipping change with no files.")
			continue
		}
		commitMessage := ""
		if curRev.Commit != nil {
			commitMessage = curRev.Commit.Message
		}
		req := &tricium.AnalyzeRequest{
			Project: luciProject,
			Files:   files,
			Source: &tricium.AnalyzeRequest_GerritRevision{
				GerritRevision: &tricium.GerritRevision{
					Host:          gerritProject.Host,
					Project:       gerritProject.Project,
					Change:        change.ID,
					GitRef:        curRev.Ref,
					GitUrl:        gerritProject.GitUrl,
					CommitMessage: commitMessage,
				},
			},
		}
		b, err := proto.Marshal(req)
		if err != nil {
			return errors.Annotate(err, "failed to marshal Analyze request").Err()
		}
		t := tq.NewPOSTTask("/internal/analyze", nil)
		t.Payload = b
		logging.Debugf(c, "Created AnalyzeRequest: %v", req)
		tasks = append(tasks, t)
	}
	if err := tq.Add(c, common.AnalyzeQueue, tasks...); err != nil {
		return errors.Annotate(err, "failed to enqueue Analyze request").Err()
	}
	return nil
}

// triciumFiles returns the list of tricium.Data_File to analyze for
// a change given the list of files from Gerrit.
func triciumFiles(c context.Context, grFiles map[string]*gr.FileInfo) []*tricium.Data_File {
	var files []*tricium.Data_File
	for k, v := range grFiles {
		status := statusFromCode(c, v.Status)
		if status == tricium.Data_DELETED {
			continue // Never consider deleted files; they don't exist after the patch.
		}
		files = append(files, &tricium.Data_File{
			Path:     k,
			Status:   status,
			IsBinary: v.Binary,
		})
	}
	// Sorting files according to their paths to account for random
	// enumeration in go maps. This is to get consistent behavior for the
	// same input.
	sort.Slice(files, func(i, j int) bool {
		return files[i].Path < files[j].Path
	})
	return files
}

// isAuthorAllowed checks whether the author of the CL is whitelisted.
//
// A CL is analyzed if the owner (author) of the CL is in at least one of the
// the whitelist groups for this repo as specified in the project config.
// If there are no whitelisted groups, then there is no filtering.
//
// If there is an error, this function logs an error and returns false.
func isAuthorAllowed(c context.Context, change gr.ChangeInfo, whitelist []string) bool {
	if len(whitelist) == 0 {
		return true
	}
	// The auth DB should be set in state by middleware.
	state := auth.GetState(c)
	if state == nil {
		logging.Errorf(c, "failed to check auth, no State in context.")
		return false
	}
	authDB := state.DB()
	if authDB == nil {
		logging.Errorf(c, "Failed to check auth, nil auth DB in State.")
		return false
	}
	email := change.Owner.Email
	// If we fail to check the whitelist for a user, we'll
	// log an error and consider the owner to be not whitelisted.
	ident, err := identity.MakeIdentity("user:" + email)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to create identity for %q.", email)
		return false
	}
	authOK, err := authDB.IsMember(c, ident, whitelist)
	if err != nil {
		logging.WithError(err).Errorf(c, "Failed to check auth for %q.", email)
		return false
	}
	return authOK
}

// hasSkipCommand checks whether the CL description contains a footer flag that
// indicates that this change should be skipped.
func hasSkipCommand(rev *gr.RevisionInfo) bool {
	if rev.Commit == nil {
		return false
	}
	flags := extractFooterFlags(rev.Commit.Message)
	triciumValue, ok := flags["Tricium"]
	if !ok {
		return false
	}
	return skipValues.Has(strings.ToLower(triciumValue))
}

// extractFooterFlags extracts the key: value footers from the commit message.
//
// The behavior is supposed to match (roughly) the footer parsing behavior in
// https://cs.chromium.org/chromium/tools/depot_tools/git_footers.py
//
// Specifically: Footer flags only appear in the last paragraph of the commit
// message; if there's only one paragraph then there are no footers. The last
// paragraph may also contain lines with no footer flags. Footer flag lines
// consist of a key (which has no spaces but can have dashes) followed by
// colon, optional whitespace, and a value which goes to the end of the line.
//
// The return value is a map of flag keys to values where the key is converted
// to title case. If a flag key appears multiple times, the value from the
// latest line is used.
func extractFooterFlags(message string) map[string]string {
	flags := map[string]string{}
	// Note, the commit message generally has a trailing newline, but it's
	// also possible for it to have multiple trailing newlines or lines with
	// only whitespace, which should be ignored.
	message = strings.TrimSpace(message)
	paragraphs := paragraphBreak.Split(message, -1)
	if len(paragraphs) == 1 {
		// There is only one paragraph, so there are no footers.
		return flags
	}

	lastParagraph := paragraphs[len(paragraphs)-1]
	for _, line := range strings.Split(lastParagraph, "\n") {
		matches := footerPattern.FindStringSubmatch(line)
		if len(matches) != 3 {
			continue
		}
		key := strings.Title(strings.ToLower(matches[1]))
		if footerKeyBlacklist.Has(key) {
			continue
		}
		flags[key] = matches[2]
	}
	return flags
}

// gerritProjectID constructs the ID used to store information about
// a Gerrit host and project.
func gerritProjectID(host, project string) string {
	return fmt.Sprintf("%s:%s", host, project)
}

// statusFromCode returns a file status given a one character code.
//
// The input is one of the valid values for the status field in
// Gerrit FileInfo; see https://goo.gl/ABFHDg.
func statusFromCode(c context.Context, status string) tricium.Data_Status {
	switch status {
	case "", "M":
		// An empty or missing Status field indicates "MODIFIED".
		// Gerrit uses an empty status field for modified files.
		return tricium.Data_MODIFIED
	case "A":
		return tricium.Data_ADDED
	case "D":
		return tricium.Data_DELETED
	case "R":
		return tricium.Data_RENAMED
	case "C":
		return tricium.Data_COPIED
	case "W":
		return tricium.Data_REWRITTEN
	default:
		logging.Warningf(c, "Received unrecognized status %q.", status)
		return tricium.Data_MODIFIED
	}
}
