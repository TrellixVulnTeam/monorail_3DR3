// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rules

import (
	"bufio"
	"fmt"
	"io/ioutil"
	"net/http"
	"regexp"
	"sort"
	"strings"

	"context"

	"google.golang.org/genproto/protobuf/field_mask"

	ds "go.chromium.org/gae/service/datastore"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
	"go.chromium.org/luci/common/logging"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"infra/appengine/cr-audit-commits/buildstatus"
	"infra/monorail"
)

const (
	// TODO(robertocn): Move this to the gitiles library.

	// GerritScope is a link of Gerrit authorization.
	GerritScope = "https://www.googleapis.com/auth/gerritcodereview"
	// EmailScope is a link of Google email authorization.
	EmailScope = "https://www.googleapis.com/auth/userinfo.email"
	// FailedBuildPrefix is a prefix that is followed by some failed builds in
	// commit messages.
	FailedBuildPrefix = "Sample Failed Build:"
	// FailedStepPrefix is a prefix that is followed by some failed steps in
	// commit messages.
	FailedStepPrefix = "Sample Failed Step:"
	// FlakyTestPrefix is a prefix that is followed by some flaky tests in
	// commit messages.
	FlakyTestPrefix     = "Sample Flaky Test:"
	bugIDRegex          = "^(?:Bug:|BUG=|Fixed:)(((\\s*)(chromium:|b:)?(\\s*)(\\d+),)*(\\s*)(chromium:|b:)?(\\s*)(\\d+))$"
	buganizerBugRegex   = "b([/:])(\\s*)([\\d]+)"
	prodBuildbucketHost = "cr-buildbucket.appspot.com"
)

type gerritClientInterface interface {
	ChangeDetails(context.Context, string, gerrit.ChangeDetailsParams) (*gerrit.Change, error)
	ChangeQuery(context.Context, gerrit.ChangeQueryParams) ([]*gerrit.Change, bool, error)
	IsChangePureRevert(context.Context, string) (bool, error)
	SetReview(context.Context, string, string, *gerrit.ReviewInput) (*gerrit.ReviewResult, error)
}

// TODO(robertocn): move this into a dedicated file for authentication, and
// accept a list of scopes to make this function usable for communicating for
// different systems.

// GetAuthenticatedHTTPClient gets http clients from given scopes.
func GetAuthenticatedHTTPClient(ctx context.Context, scopes ...string) (*http.Client, error) {
	var t http.RoundTripper
	var err error
	if len(scopes) > 0 {
		t, err = auth.GetRPCTransport(ctx, auth.AsSelf, auth.WithScopes(scopes...))
	} else {
		t, err = auth.GetRPCTransport(ctx, auth.AsSelf)
	}

	if err != nil {
		return nil, err
	}

	return &http.Client{Transport: t}, nil
}

func findPrefixLine(m string, prefix string) (string, error) {
	s := bufio.NewScanner(strings.NewReader(m))
	for s.Scan() {
		line := s.Text()
		if strings.HasPrefix(line, prefix) {
			return strings.TrimSpace(strings.TrimPrefix(line, prefix)), nil
		}
	}
	return "", fmt.Errorf("commit message does not contain line prefixed with %q", prefix)
}
func failedBuildFromCommitMessage(m string) (string, error) {
	return findPrefixLine(m, FailedBuildPrefix)
}

func failedStepFromCommitMessage(m string) (string, error) {
	return findPrefixLine(m, FailedStepPrefix)
}

// isFlakeRevert determines if a commit is a revert due to flake by the contents
// of the given commit message.
func isFlakeRevert(m string) bool {
	_, err := findPrefixLine(m, FlakyTestPrefix)
	return err == nil
}

func bugIDFromCommitMessage(m string) (string, error) {
	s := bufio.NewScanner(strings.NewReader(m))
	for s.Scan() {
		line := s.Text()
		re := regexp.MustCompile(bugIDRegex)
		matches := re.FindAllStringSubmatch(line, -1)
		if len(matches) != 0 {
			rawBugList := strings.Split(string(matches[0][1]), ",")
			bugList := []string{}
			buganizerRe := regexp.MustCompile(buganizerBugRegex)

			for _, bugID := range rawBugList {
				// Remove buganizer bugs
				if buganizerRe.MatchString(bugID) {
					continue
				}

				// Remove space and "chromium:" prefix
				bugID = strings.Replace(bugID, " ", "", -1)
				bugID = strings.Replace(bugID, "chromium:", "", -1)

				// Add into bugList
				bugList = append(bugList, bugID)
			}

			if len(bugList) != 0 {
				return strings.Join(bugList, ","), nil
			}
		}
	}
	return "", fmt.Errorf("commit message does not contain any bug id")
}

func getIssueBySummaryAndAccount(ctx context.Context, cfg *RefConfig, s, a string, cs *Clients) (*monorail.Issue, error) {
	q := fmt.Sprintf("summary:\"%s\" reporter:\"%s\"", s, a)
	req := &monorail.IssuesListRequest{
		ProjectId: cfg.MonorailProject,
		Can:       monorail.IssuesListRequest_ALL,
		Q:         q,
	}
	resp, err := cs.Monorail.IssuesList(ctx, req)
	if err != nil {
		return nil, err
	}
	for _, iss := range resp.Items {
		if iss.Summary == s {
			return iss, nil
		}
	}
	return nil, nil
}

func postComment(ctx context.Context, cfg *RefConfig, iID int32, c string, cs *Clients, labels []string) error {
	req := &monorail.InsertCommentRequest{
		Comment: &monorail.InsertCommentRequest_Comment{
			Content: c,
			Updates: &monorail.Update{
				Labels: labels,
			},
		},
		Issue: &monorail.IssueRef{
			IssueId:   iID,
			ProjectId: cfg.MonorailProject,
		},
	}
	_, err := cs.Monorail.InsertComment(ctx, req)
	return err
}

// PostIssue will create an issue based on the given parameters.
func PostIssue(ctx context.Context, cfg *RefConfig, s, d string, cs *Clients, components, labels []string) (int32, error) {
	// The components for the issue will be the additional components
	// depending on which rules were violated, and the component defined
	// for the repo(if any).
	iss := &monorail.Issue{
		Description: d,
		Components:  components,
		Labels:      labels,
		Status:      monorail.StatusUntriaged,
		Summary:     s,
		ProjectId:   cfg.MonorailProject,
	}

	req := &monorail.InsertIssueRequest{
		Issue:     iss,
		SendEmail: true,
	}

	resp, err := cs.Monorail.InsertIssue(ctx, req)
	if err != nil {
		return 0, err
	}
	return resp.Issue.Id, nil
}

func issueFromID(ctx context.Context, cfg *RefConfig, ID int32, cs *Clients) (*monorail.Issue, error) {
	req := &monorail.GetIssueRequest{
		Issue: &monorail.IssueRef{
			IssueId:   ID,
			ProjectId: cfg.MonorailProject,
		},
	}
	return cs.Monorail.GetIssue(ctx, req)
}

func listCommentsFromIssueID(ctx context.Context, cfg *RefConfig, ID int32, cs *Clients) ([]*monorail.Comment, error) {
	req := &monorail.ListCommentsRequest{
		Issue: &monorail.IssueRef{
			IssueId:   ID,
			ProjectId: cfg.MonorailProject,
		},
	}
	resp, err := cs.Monorail.ListComments(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp.Items, nil
}

func resultText(cfg *RefConfig, rc *RelevantCommit, issueExists bool) string {
	sort.Slice(rc.Result, func(i, j int) bool {
		if rc.Result[i].RuleResultStatus == rc.Result[j].RuleResultStatus {
			return rc.Result[i].RuleName < rc.Result[j].RuleName
		}
		return rc.Result[i].RuleResultStatus < rc.Result[j].RuleResultStatus
	})
	rows := []string{}
	for _, rr := range rc.Result {
		rows = append(rows, fmt.Sprintf(" - %s: %s -- %s", rr.RuleName, rr.RuleResultStatus.ToString(), rr.Message))
	}

	results := fmt.Sprintf("Here's a summary of the rules that were executed: \n%s",
		strings.Join(rows, "\n"))

	if issueExists {
		return results
	}

	description := "An audit of the git commit at %q found at least one violation. \n" +
		" The commit was created by %s and committed by %s.\n\n%s"

	return fmt.Sprintf(description, cfg.LinkToCommit(rc.CommitHash), rc.AuthorAccount, rc.CommitterAccount, results)

}

func getBuildByURL(ctx context.Context, buildURL string, cs *Clients, fm *field_mask.FieldMask) (*buildbucketpb.Build, error) {
	buildID, err := buildstatus.ParseBuildURL(buildURL)
	if err != nil {
		return nil, err
	}
	return getBuild(ctx, buildID, cs, fm)
}

func getPreviousBuildByURL(ctx context.Context, buildURL string, cs *Clients, fm *field_mask.FieldMask) (*buildbucketpb.Build, error) {
	buildID, err := buildstatus.ParseBuildURL(buildURL)
	if err != nil {
		return nil, err
	}
	return getPrevBuild(ctx, buildID, cs, fm)
}

func getBuild(ctx context.Context, buildID int64, cs *Clients, fm *field_mask.FieldMask) (*buildbucketpb.Build, error) {
	req := &buildbucketpb.GetBuildRequest{
		Id: buildID,
	}
	if fm != nil {
		req.Fields = fm
	}
	bb := cs.NewBuildbucketClient()
	build, err := bb.GetBuild(ctx, req)
	if err != nil {
		return nil, err
	}
	return build, nil
}

func getPrevBuild(ctx context.Context, buildID int64, cs *Clients, fm *field_mask.FieldMask) (*buildbucketpb.Build, error) {
	build, err := getBuild(ctx, buildID, cs, fm)
	if err != nil {
		return nil, err
	}
	req := &buildbucketpb.GetBuildRequest{
		Builder:     build.Builder,
		BuildNumber: build.Number - 1,
	}
	if fm != nil {
		req.Fields = fm
	}
	bb := cs.NewBuildbucketClient()
	prevBuild, err := bb.GetBuild(ctx, req)
	if err != nil {
		return nil, err
	}
	return prevBuild, nil
}

// Clients exposes clients for external services shared throughout one request.
type Clients struct {

	// Instead of actual clients, use interfaces so that tests
	// can inject mock clients as needed.
	gerrit     gerritClientInterface
	httpClient *http.Client

	// This is already an interface so we use it as exported.
	Monorail           monorail.MonorailClient
	GitilesFactory     GitilesClientFactory
	buildbucketFactory BuildbucketClientFactory
}

// BuildbucketClientFactory is function type for generating new Buildbucket
// clients, both the production client factory and any mock factories are
// expected to implement it.
type BuildbucketClientFactory func(httpClient *http.Client) buildbucketpb.BuildsClient

// ProdBuildbucketClientFactory is a BuildbucketClientFactory used to create production
// buildbucket PRPC clients.
func ProdBuildbucketClientFactory(httpClient *http.Client) buildbucketpb.BuildsClient {
	return buildbucketpb.NewBuildsPRPCClient(&prpc.Client{
		C:    httpClient,
		Host: prodBuildbucketHost,
	})
}

// NewBuildbucketClient uses a factory set in the Clients object and its httpClient
// to create a new buildbucket client.
func (c *Clients) NewBuildbucketClient() buildbucketpb.BuildsClient {
	return c.buildbucketFactory(c.httpClient)
}

// GitilesClientFactory is function type for generating new gitiles clients,
// both the production client factory and any mock factories are expected to
// implement it.
type GitilesClientFactory func(host string, httpClient *http.Client) (gitilespb.GitilesClient, error)

// ProdGitilesClientFactory is a GitilesClientFactory used to create production
// gitiles REST clients.
func ProdGitilesClientFactory(host string, httpClient *http.Client) (gitilespb.GitilesClient, error) {
	gc, err := gitiles.NewRESTClient(httpClient, host, true)
	if err != nil {
		return nil, err
	}
	return gc, nil
}

// NewGitilesClient uses a factory set in the Clients object and its httpClient
// to create a new gitiles client.
func (c *Clients) NewGitilesClient(host string) (gitilespb.GitilesClient, error) {
	gc, err := c.GitilesFactory(host, c.httpClient)
	if err != nil {
		return nil, err
	}
	return gc, nil
}

// ConnectAll creates the clients so the rules can use them, also sets
// necessary values in the context for the clients to talk to production.
func (c *Clients) ConnectAll(ctx context.Context, cfg *RefConfig, client *http.Client) error {
	var err error
	c.httpClient = client

	c.gerrit, err = gerrit.NewClient(c.httpClient, cfg.GerritURL)
	if err != nil {
		return err
	}

	c.Monorail = monorail.NewEndpointsClient(c.httpClient, cfg.MonorailAPIURL)
	c.GitilesFactory = ProdGitilesClientFactory
	c.buildbucketFactory = ProdBuildbucketClientFactory
	return nil
}

// LoadConfigFromContext finds the repo config and repo state matching the git
// ref given as the "refUrl" parameter in the http request bound to the router
// context.
//
// If the given ref matches a configuration set to dynamic refs, this function
// calls the config's method to populate the concrete ref parameters and returns
// the result of that method.
func LoadConfigFromContext(rc *router.Context) (*RefConfig, *RepoState, error) {
	ctx, req := rc.Context, rc.Request
	refURL := req.FormValue("refUrl")
	return LoadConfig(ctx, refURL)
}

// LoadConfig returns both repository status and config based on given refURL.
func LoadConfig(ctx context.Context, refURL string) (*RefConfig, *RepoState, error) {
	rs := &RepoState{RepoURL: refURL}
	err := ds.Get(ctx, rs)
	if err != nil {
		return nil, nil, err
	}

	cfg, ok := RuleMap[rs.ConfigName]
	if !ok {
		return nil, nil, fmt.Errorf("Unknown or missing config %s", rs.ConfigName)
	}
	return cfg.SetConcreteRef(ctx, rs), rs, nil
}

// InitializeClients returns clients that connects to given repositories.
func InitializeClients(ctx context.Context, cfg *RefConfig, client *http.Client) (*Clients, error) {
	cs := &Clients{}
	err := cs.ConnectAll(ctx, cfg, client)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Could not create external clients")
		return nil, fmt.Errorf("Could not create external clients")
	}
	return cs, nil
}

func escapeToken(t string) string {
	return strings.Replace(
		strings.Replace(
			strings.Replace(
				t, "\\", "\\\\", -1),
			"\n", "\\n", -1),
		":", "\\c", -1)

}
func unescapeToken(t string) string {
	// Hack needed due to golang's lack of positive lookbehind in regexp.

	// Only replace \n for newline if preceded by an even number of
	// backslashes.
	// e.g:  (in the example below (0x0a) represents whatever "\n" means to go)
	//   \\n -> \n, \\\n -> \(0x0a), \\\n -> \\n, \\\\\n -> \\(0x0a)
	re := regexp.MustCompile("\\\\+n") // One or more slashes followed by n.
	t = re.ReplaceAllStringFunc(t, func(s string) string {
		if len(s)%2 != 0 {
			return s
		}
		return strings.Replace(s, "\\n", "\n", 1)
	})

	// Same for colons.
	re = regexp.MustCompile("\\\\+c") // One or more slashes followed by c.
	t = re.ReplaceAllStringFunc(t, func(s string) string {
		if len(s)%2 != 0 {
			return s
		}
		return strings.Replace(s, "\\c", ":", 1)
	})

	return strings.Replace(t, "\\\\", "\\", -1)
}

// GetToken returns the value of a token, and a boolean indicating if the token
// exists (as opposed to the token being the empty string).
func GetToken(ctx context.Context, tokenName, packedTokens string) (string, bool) {
	tokenName = escapeToken(tokenName)
	pairs := strings.Split(packedTokens, "\n")
	for _, v := range pairs {
		parts := strings.SplitN(v, ":", 2)
		if len(parts) != 2 {
			logging.Debugf(ctx, "Missing ':' separator in key:value token %s in RuleResult.MetaData", v)
			continue
		}
		if parts[0] != tokenName {
			continue
		}
		return unescapeToken(parts[1]), true
	}
	return "", false
}

// SetToken modifies the value of the token if it exists, or adds it if not.
func SetToken(ctx context.Context, tokenName, tokenValue, packedTokens string) (string, error) {
	tokenValue = escapeToken(tokenValue)
	tokenName = escapeToken(tokenName)
	modified := false
	newVal := fmt.Sprintf("%s:%s", tokenName, tokenValue)
	pairs := strings.Split(packedTokens, "\n")
	for i, v := range pairs {
		if strings.HasPrefix(v, tokenName+":") {
			pairs[i] = newVal
			modified = true
			break
		}
	}
	if !modified {
		pairs = append(pairs, newVal)
	}
	return strings.Join(pairs, "\n"), nil
}

// GetToken is a convenience method to get tokens from a RuleResult's MetaData.
// exists (as opposed to the token being the empty string).
// Assumes rr.MetaData is a \n separated list of "key:value" strings, used by
// rules to specify details of the notification not conveyed in the .Message
// field.
func (rr *RuleResult) GetToken(ctx context.Context, tokenName string) (string, bool) {
	return GetToken(ctx, tokenName, rr.MetaData)
}

// SetToken is a convenience method to set tokens on a RuleResult's MetaData.
// Assumes rr.MetaData is a \n separated list of "key:value" strings, used by
// rules to specify details of the notification not conveyed in the .Message
// field.
func (rr *RuleResult) SetToken(ctx context.Context, tokenName, tokenValue string) error {
	var err error
	rr.MetaData, err = SetToken(ctx, tokenName, tokenValue, rr.MetaData)
	return err
}

func getURLAsString(ctx context.Context, url string) (string, error) {
	httpClient, err := GetAuthenticatedHTTPClient(ctx, GerritScope, EmailScope)
	response, err := httpClient.Get(url)
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	contents, err := ioutil.ReadAll(response.Body)
	if err != nil {
		return "", err
	}
	return string(contents), nil
}

// getBlamelist computes the list of commits in a build and not included in its previous build.
func getBlamelist(ctx context.Context, buildURL string, cs *Clients) ([]string, error) {
	currBuild, err := getBuildByURL(ctx, buildURL, cs, nil)
	if err != nil {
		return nil, err
	}

	prevBuild, err := getPreviousBuildByURL(ctx, buildURL, cs, nil)
	if err != nil {
		return nil, err
	}

	gc, err := cs.GitilesFactory(currBuild.Input.GitilesCommit.Host, cs.httpClient)
	if err != nil {
		return nil, err
	}

	logReq := &gitilespb.LogRequest{
		Project:            currBuild.Input.GitilesCommit.Project,
		ExcludeAncestorsOf: prevBuild.Input.GitilesCommit.Id,
		Committish:         currBuild.Input.GitilesCommit.Id,
	}
	logResp, err := gc.Log(ctx, logReq)
	result := make([]string, 0, 10)
	if err != nil {
		return nil, err
	}
	for _, commit := range logResp.Log {
		result = append(result, commit.Id)
	}
	for logResp.NextPageToken != "" {
		logReq.PageToken = logResp.NextPageToken
		logResp, err = gc.Log(ctx, logReq)
		if err != nil {
			return nil, err
		}
		for _, commit := range logResp.Log {
			result = append(result, commit.Id)
		}
	}
	return result, nil
}
