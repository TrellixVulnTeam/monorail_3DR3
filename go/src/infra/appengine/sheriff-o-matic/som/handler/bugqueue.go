// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"infra/appengine/sheriff-o-matic/som/model"
	"infra/monorail"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

const (
	bugQueueCacheFormat = "bugqueue-%s"
)

var (
	bugQueueLength = metric.NewInt("bug_queue_length", "Number of bugs in queue.",
		nil, field.String("label"))
)

// BugQueueHandler handles bug queue-related requests.
type BugQueueHandler struct {
	Monorail               monorail.MonorailClient
	DefaultMonorailProject string
}

// A bit of a hack to let us mock getBugsFromMonorail.
func (bqh *BugQueueHandler) getBugsFromMonorail(c context.Context, q string, projectID string,
	can monorail.IssuesListRequest_CannedQuery) (*monorail.IssuesListResponse, error) {
	// TODO(martiniss): make this look up request info based on Tree datastore
	// object
	req := &monorail.IssuesListRequest{
		ProjectId: projectID,
		Q:         q,
	}

	req.Can = can

	before := clock.Now(c)

	res, err := bqh.Monorail.IssuesList(c, req)
	if err != nil {
		logging.Errorf(c, "error getting issuelist: %v", err)
		return nil, err
	}

	logging.Debugf(c, "Fetch to monorail took %v. Got %d bugs.", clock.Now(c).Sub(before), res.TotalResults)
	return res, nil
}

// Switches chromium.org emails for google.com emails and vice versa.
// Note that chromium.org emails may be different from google.com emails.
func getAlternateEmail(email string) string {
	s := strings.Split(email, "@")
	if len(s) != 2 {
		return email
	}

	user, domain := s[0], s[1]
	if domain == "chromium.org" {
		return fmt.Sprintf("%s@google.com", user)
	}
	return fmt.Sprintf("%s@chromium.org", user)
}

// GetBugQueueHandler returns a set of bugs for the current user and tree.
func (bqh *BugQueueHandler) GetBugQueueHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	label := p.ByName("label")
	key := fmt.Sprintf(bugQueueCacheFormat, label)

	item, err := memcache.GetKey(c, key)

	if err == memcache.ErrCacheMiss {
		logging.Debugf(c, "No bug queue data for %s in memcache, refreshing...", label)
		item, err = bqh.refreshBugQueue(c, label, bqh.GetMonorailProjectNameFromLabel(c, label))
	}

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	result := item.Value()

	w.Header().Set("Content-Type", "application/json")
	w.Write(result)
}

// GetUncachedBugsHandler bypasses the cache to return the bug queue for current user and tree.
func (bqh *BugQueueHandler) GetUncachedBugsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	label := p.ByName("label")

	user := auth.CurrentIdentity(c)
	email := getAlternateEmail(user.Email())
	q := fmt.Sprintf("label:%[1]s -has:owner OR label:%[1]s owner:%s OR owner:%s label:%[1]s",
		label, user.Email(), email)

	bugs, err := bqh.getBugsFromMonorail(c, q, bqh.GetMonorailProjectNameFromLabel(c, label), monorail.IssuesListRequest_OPEN)
	if err != nil && bugs != nil {
		bugQueueLength.Set(c, int64(bugs.TotalResults), label)
	}

	out, err := json.Marshal(bugs)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(out)
}

// Makes a request to Monorail for bugs in a label and caches the results.
func (bqh *BugQueueHandler) refreshBugQueue(c context.Context, label string, projectID string) (memcache.Item, error) {
	q := fmt.Sprintf("label=%s", label)
	res, err := bqh.getBugsFromMonorail(c, q, projectID, monorail.IssuesListRequest_OPEN)

	if err != nil {
		return nil, err
	}

	bytes, err := json.Marshal(res)
	if err != nil {
		return nil, err
	}

	item := memcache.NewItem(c, fmt.Sprintf(bugQueueCacheFormat, label)).SetValue(bytes)

	if err = memcache.Set(c, item); err != nil {
		return nil, err
	}

	return item, nil
}

// RefreshBugQueueHandler updates the cached bug queue for current tree.
func (bqh *BugQueueHandler) RefreshBugQueueHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params
	label := p.ByName("label")
	item, err := bqh.refreshBugQueue(c, label, bqh.GetMonorailProjectNameFromLabel(c, label))

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(item.Value())
}

// GetMonorailProjectNameFromLabel returns the default monorail project name
// configured in project settings by comparing the bugqueue label.
func (bqh *BugQueueHandler) GetMonorailProjectNameFromLabel(c context.Context, label string) string {

	if bqh.DefaultMonorailProject == "" {
		bqh.DefaultMonorailProject = bqh.queryTreeForLabel(c, label)
	}

	return bqh.DefaultMonorailProject
}

func (bqh *BugQueueHandler) queryTreeForLabel(c context.Context, label string) string {
	q := datastore.NewQuery("Tree")
	trees := []*model.Tree{}
	if err := datastore.GetAll(c, q, &trees); err == nil {
		for _, tree := range trees {
			if tree.BugQueueLabel == label && tree.DefaultMonorailProjectName != "" {
				return tree.DefaultMonorailProjectName
			}
		}
	}
	return "chromium"
}
