// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handler

import (
	"bytes"
	"crypto/sha1"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"google.golang.org/appengine"

	"infra/appengine/sheriff-o-matic/config"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/model"
	"infra/monorail"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/xsrf"
	"go.chromium.org/luci/server/router"
)

const (
	annotationsCacheKey = "annotation-metadata"
	// annotations will expire after this amount of time
	annotationExpiration = time.Hour * 24 * 10
	// maxMonorailQuerySize is the maximum number of bugs per monorail query.
	maxMonorailQuerySize = 100
)

// AnnotationHandler handles annotation-related requests.
type AnnotationHandler struct {
	Bqh *BugQueueHandler
}

// AnnotationResponse ... The Annotation object extended with cached bug data.
type AnnotationResponse struct {
	model.Annotation
	BugData map[string]monorail.Issue `json:"bug_data"`
}

func convertAnnotationsNonGroupingToAnnotations(annotationsNonGrouping []*model.AnnotationNonGrouping, annotations *[]*model.Annotation) {
	*annotations = make([]*model.Annotation, len(annotationsNonGrouping))
	for i, annotationNonGrouping := range annotationsNonGrouping {
		tmp := model.Annotation(*annotationNonGrouping)
		(*annotations)[i] = &tmp
	}
}

func convertAnnotationsToAnnotationsNonGrouping(annotations []*model.Annotation) []*model.AnnotationNonGrouping {
	annotationsNonGrouping := make([]*model.AnnotationNonGrouping, len(annotations))
	for i, annotation := range annotations {
		tmp := model.AnnotationNonGrouping(*annotation)
		annotationsNonGrouping[i] = &tmp
	}
	return annotationsNonGrouping
}

func datastoreGetAnnotation(c context.Context, annotation *model.Annotation) error {
	if config.EnableAutoGrouping {
		return datastore.Get(c, annotation)
	}
	annotationNonGrouping := model.AnnotationNonGrouping(*annotation)
	err := datastore.Get(c, &annotationNonGrouping)
	if err != nil {
		return err
	}
	*annotation = model.Annotation(annotationNonGrouping)
	return nil
}

func datastorePutAnnotation(c context.Context, annotation *model.Annotation) error {
	annotations := []*model.Annotation{annotation}
	return datastorePutAnnotations(c, annotations)
}

func datastorePutAnnotations(c context.Context, annotations []*model.Annotation) error {
	if config.EnableAutoGrouping {
		return datastore.Put(c, annotations)
	}
	annotationsNonGrouping := convertAnnotationsToAnnotationsNonGrouping(annotations)
	return datastore.Put(c, annotationsNonGrouping)
}

func datastoreCreateAnnotationQuery() *datastore.Query {
	if config.EnableAutoGrouping {
		return datastore.NewQuery("Annotation")
	}
	return datastore.NewQuery("AnnotationNonGrouping")
}

func datastoreGetAnnotationsByQuery(c context.Context, annotations *[]*model.Annotation, q *datastore.Query) error {
	if config.EnableAutoGrouping {
		return datastore.GetAll(c, q, annotations)
	}
	annotationsNonGrouping := []*model.AnnotationNonGrouping{}
	err := datastore.GetAll(c, q, &annotationsNonGrouping)
	if err != nil {
		return err
	}
	convertAnnotationsNonGroupingToAnnotations(annotationsNonGrouping, annotations)
	return nil
}

func datastoreDeleteAnnotations(c context.Context, annotations []*model.Annotation) error {
	if config.EnableAutoGrouping {
		return datastore.Delete(c, annotations)
	}
	annotationsNonGrouping := convertAnnotationsToAnnotationsNonGrouping(annotations)
	return datastore.Delete(c, annotationsNonGrouping)
}

// Convert data from model.Annotation type to AnnotationResponse type by populating monorail data.
func makeAnnotationResponse(annotations *model.Annotation, meta map[string]monorail.Issue) *AnnotationResponse {
	bugs := make(map[string]monorail.Issue)
	for _, b := range annotations.Bugs {
		if bugData, ok := meta[b.BugID]; ok {
			bugs[b.BugID] = bugData
		}
	}
	return &AnnotationResponse{*annotations, bugs}
}

func filterAnnotations(annotations []*model.Annotation, activeKeys map[string]interface{}) []*model.Annotation {
	ret := []*model.Annotation{}
	groups := map[string]interface{}{}

	// Process annotations not belonging to a group
	for _, a := range annotations {
		if _, ok := activeKeys[a.Key]; ok {
			ret = append(ret, a)
			if a.GroupID != "" {
				groups[a.GroupID] = nil
			}
		}
	}

	// Process annotations belonging to a group
	for _, a := range annotations {
		if _, ok := groups[a.Key]; ok {
			ret = append(ret, a)
		}
	}
	return ret
}

// GetAnnotationsHandler retrieves a set of annotations.
func (ah *AnnotationHandler) GetAnnotationsHandler(ctx *router.Context, activeKeys map[string]interface{}) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	q := datastoreCreateAnnotationQuery()

	if tree != "" {
		q = q.Ancestor(datastore.MakeKey(c, "Tree", tree))
	}

	annotations := []*model.Annotation{}
	datastoreGetAnnotationsByQuery(c, &annotations, q)

	annotations = filterAnnotations(annotations, activeKeys)

	meta, err := ah.getAnnotationsMetaData(ctx)

	if err != nil {
		logging.Errorf(c, "while fetching annotation metadata")
	}

	response := make([]*AnnotationResponse, len(annotations))
	for i, a := range annotations {
		response[i] = makeAnnotationResponse(a, meta)
	}

	data, err := json.Marshal(response)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

func (ah *AnnotationHandler) getAnnotationsMetaData(ctx *router.Context) (map[string]monorail.Issue, error) {
	c := ctx.Context
	item, err := memcache.GetKey(c, annotationsCacheKey)
	val := make(map[string]monorail.Issue)

	if err == memcache.ErrCacheMiss {
		logging.Warningf(c, "No annotation metadata in memcache, refreshing...")
		val, err = ah.refreshAnnotations(ctx, nil)

		if err != nil {
			return nil, err
		}
	} else {
		if err = json.Unmarshal(item.Value(), &val); err != nil {
			logging.Errorf(c, "while unmarshaling metadata in getAnnotationsMetaData")
			return nil, err
		}
	}
	return val, nil
}

// RefreshAnnotationsHandler refreshes the set of annotations.
func (ah *AnnotationHandler) RefreshAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	bugMap, err := ah.refreshAnnotations(ctx, nil)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	data, err := json.Marshal(bugMap)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

// Builds a map keyed by projectId (i.e "chromium", "fuchsia"), value contains
// the monorail query string.
// Monorail only returns a maximum of 100 bugs at a time, so we need to break queries into chunks.
func constructQueryFromBugList(bugs []model.MonorailBug, chunkSize int) map[string][]string {
	projectIDToBugIDMap := make(map[string][]string)
	for _, bug := range bugs {
		if bugList, ok := projectIDToBugIDMap[bug.ProjectID]; ok {
			projectIDToBugIDMap[bug.ProjectID] = append(bugList, bug.BugID)
		} else {
			projectIDToBugIDMap[bug.ProjectID] = []string{bug.BugID}
		}
	}
	queries := make(map[string][]string)
	for projectID, bugIDs := range projectIDToBugIDMap {
		queries[projectID] = []string{}
		bugChunks := breakToChunks(bugIDs, chunkSize)
		for _, chunk := range bugChunks {
			str := "id:" + strings.Join(chunk, ",")
			queries[projectID] = append(queries[projectID], str)
		}
	}
	return queries
}

func breakToChunks(bugIDs []string, chunkSize int) [][]string {
	var result [][]string
	for i := 0; i < len(bugIDs); i += chunkSize {
		end := i + chunkSize
		if end > len(bugIDs) {
			end = len(bugIDs)
		}
		result = append(result, bugIDs[i:end])
	}
	return result
}

func filterDuplicateBugs(bugs []model.MonorailBug) []model.MonorailBug {
	bugIds := map[string]interface{}{}
	filteredBugs := []model.MonorailBug{}
	for _, bug := range bugs {
		if _, exist := bugIds[bug.BugID]; !exist {
			bugIds[bug.BugID] = nil
			filteredBugs = append(filteredBugs, bug)
		}
	}
	return filteredBugs
}

// Update the cache for annotation bug data.
func (ah *AnnotationHandler) refreshAnnotations(ctx *router.Context, a *model.Annotation) (map[string]monorail.Issue, error) {
	c := ctx.Context
	q := datastoreCreateAnnotationQuery()
	results := []*model.Annotation{}
	datastoreGetAnnotationsByQuery(c, &results, q)

	// Monorail takes queries of the format id:1,2,3 (gets bugs with those ids).
	if a != nil {
		results = append(results, a)
	}

	allBugs := []model.MonorailBug{}
	for _, annotation := range results {
		for _, b := range annotation.Bugs {
			allBugs = append(allBugs, b)
		}
	}

	allBugs = filterDuplicateBugs(allBugs)

	queries := constructQueryFromBugList(allBugs, maxMonorailQuerySize)
	m := make(map[string]monorail.Issue)
	for project, queriesForProj := range queries {
		for _, query := range queriesForProj {
			issues, err := ah.Bqh.getBugsFromMonorail(c, query, project, monorail.IssuesListRequest_ALL)
			if err != nil {
				logging.Errorf(c, "error getting bugs from monorail: %v", err)
				return nil, err
			}
			for _, b := range issues.Items {
				key := fmt.Sprintf("%d", b.Id)
				m[key] = *b
			}
		}
	}

	bytes, err := json.Marshal(m)
	if err != nil {
		return nil, err
	}

	item := memcache.NewItem(c, annotationsCacheKey).SetValue(bytes)

	err = memcache.Set(c, item)

	if err != nil {
		return nil, err
	}

	return m, nil
}

type postRequest struct {
	XSRFToken string           `json:"xsrf_token"`
	Data      *json.RawMessage `json:"data"`
}

// PostAnnotationsHandler handles updates to annotations.
func (ah *AnnotationHandler) PostAnnotationsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")
	action := p.ByName("action")
	if action != "add" && action != "remove" {
		errStatus(c, w, http.StatusBadRequest, "unrecognized annotation action")
		return
	}

	req := &postRequest{}
	err := json.NewDecoder(r.Body).Decode(req)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("while decoding request: %s", err))
		return
	}

	if err = xsrf.Check(c, req.XSRFToken); err != nil {
		errStatus(c, w, http.StatusForbidden, err.Error())
		return
	}

	// Extract the annotation key from the otherwise unparsed body.
	rawJSON := struct{ Key string }{}
	if err = json.Unmarshal([]byte(*req.Data), &rawJSON); err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("while decoding request: %s", err))
	}

	key := rawJSON.Key

	annotation := &model.Annotation{
		Tree:      datastore.MakeKey(c, "Tree", tree),
		KeyDigest: fmt.Sprintf("%x", sha1.Sum([]byte(key))),
		Key:       key,
	}

	err = datastoreGetAnnotation(c, annotation)
	if action == "remove" && err != nil {
		logging.Errorf(c, "while getting %s: %s", key, err)
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("Annotation %s not found", key))
		return
	}

	needRefresh := false
	if info.AppID(c) != "" && info.AppID(c) != "app" {
		c = appengine.WithContext(c, r)
	}
	// The annotation probably doesn't exist if we're adding something.
	data := bytes.NewReader([]byte(*req.Data))
	if action == "add" {
		needRefresh, err = annotation.Add(c, data)
	} else if action == "remove" {
		needRefresh, err = annotation.Remove(c, data)
	}

	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	err = r.Body.Close()
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	err = datastorePutAnnotation(c, annotation)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	var m map[string]monorail.Issue
	// Refresh the annotation cache on a write. Note that we want the rest of the
	// code to still run even if this fails.
	if needRefresh {
		logging.Infof(c, "Refreshing annotation metadata, due to a stateful modification.")
		m, err = ah.refreshAnnotations(ctx, annotation)
		if err != nil {
			logging.Errorf(c, "while refreshing annotation cache on post: %s", err)
		}
	} else {
		m, err = ah.getAnnotationsMetaData(ctx)
		if err != nil {
			logging.Errorf(c, "while getting annotation metadata: %s", err)
		}

	}

	resp, err := json.Marshal(makeAnnotationResponse(annotation, m))
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
}

// FlushOldAnnotationsHandler culls obsolete annotations from the datastore.
// TODO (crbug.com/1079068): Perhaps we want to revisit flush annotation logic.
func FlushOldAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	numDeleted, err := flushOldAnnotations(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	s := fmt.Sprintf("deleted %d annotations", numDeleted)
	logging.Debugf(c, s)
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(s))
}

func flushOldAnnotations(c context.Context) (int, error) {
	q := datastoreCreateAnnotationQuery()
	q = q.Lt("ModificationTime", clock.Get(c).Now().Add(-annotationExpiration))
	q = q.KeysOnly(true)

	results := []*model.Annotation{}
	err := datastoreGetAnnotationsByQuery(c, &results, q)
	if err != nil {
		return 0, fmt.Errorf("while fetching annotations to delete: %s", err)
	}

	for _, ann := range results {
		logging.Debugf(c, "Deleting %#v\n", ann)
	}

	err = datastoreDeleteAnnotations(c, results)
	if err != nil {
		return 0, fmt.Errorf("while deleting annotations: %s", err)
	}

	return len(results), nil
}

// FileBugHandler files a new bug in monorail.
func FileBugHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request

	req := &postRequest{}
	err := json.NewDecoder(r.Body).Decode(req)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("while decoding request: %s", err))
		return
	}

	if err = xsrf.Check(c, req.XSRFToken); err != nil {
		errStatus(c, w, http.StatusForbidden, err.Error())
		return
	}

	rawJSON := struct {
		Summary     string
		Description string
		ProjectID   string
		Cc          []string
		Priority    string
		Labels      []string
	}{}
	if err = json.Unmarshal([]byte(*req.Data), &rawJSON); err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("while decoding request: %s", err))
	}

	ccList := make([]*monorail.AtomPerson, len(rawJSON.Cc))
	for i, cc := range rawJSON.Cc {
		ccList[i] = &monorail.AtomPerson{Name: cc}
	}

	sa, err := info.ServiceAccount(c)
	if err != nil {
		logging.Errorf(c, "failed to get service account: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	user := auth.CurrentIdentity(c)
	description := fmt.Sprintf("Filed by %s on behalf of %s\n\n%s", sa, user.Email(),
		rawJSON.Description)

	fileBugReq := &monorail.InsertIssueRequest{
		Issue: &monorail.Issue{
			ProjectId:   rawJSON.ProjectID,
			Cc:          ccList,
			Summary:     rawJSON.Summary,
			Description: description,
			Status:      "Untriaged",
			Labels:      rawJSON.Labels,
		},
	}

	var mr monorail.MonorailClient

	if info.AppID(c) == "sheriff-o-matic" {
		mr = client.NewMonorail(c, "https://monorail-prod.appspot.com")
	} else {
		mr = client.NewMonorail(c, "https://monorail-staging.appspot.com")
	}

	res, err := mr.InsertIssue(c, fileBugReq)
	if err != nil {
		logging.Errorf(c, "error inserting new Issue: %v", err)
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}
	out, err := json.Marshal(res)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logging.Infof(c, "%v", out)
	w.Header().Set("Content-Type", "applications/json")
	w.Write(out)
}
