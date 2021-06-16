package handler

import (
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/golang/protobuf/ptypes"
	"golang.org/x/net/context"
	"google.golang.org/appengine"

	"infra/appengine/sheriff-o-matic/config"
	"infra/appengine/sheriff-o-matic/som/analyzer"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/model"
	"infra/appengine/sheriff-o-matic/som/model/gen"
	"infra/monitoring/messages"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/bq"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/server/router"

	"cloud.google.com/go/bigquery"
)

const (
	logdiffQueue = "logdiff"

	// groupingPoolSize controls the number of goroutines used to creating
	// groupings when post processing the generated alerts. Has not been tuned.
	groupingPoolSize = 2

	bqDatasetID = "events"
	bqTableID   = "alerts"
)

var (
	alertCount = metric.NewInt("sheriff_o_matic/analyzer/alert_count",
		"Number of alerts generated.",
		nil,
		field.String("tree"),
		field.String("category")) // "consistent", "new" etc

	alertGroupCount = metric.NewInt("sheriff_o_matic/analyzer/alert_group_count",
		"Number of alert groups active.",
		nil,
		field.String("tree"),
		field.String("category")) // "consistent", "new" etc
)

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

type bySeverity []*messages.Alert

func (a bySeverity) Len() int      { return len(a) }
func (a bySeverity) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a bySeverity) Less(i, j int) bool {
	return a[i].Severity < a[j].Severity
}

type ctxKeyType string

var analyzerCtxKey = ctxKeyType("analyzer")

// WithAnalyzer returns a context with a attached as a context value.
func WithAnalyzer(ctx context.Context, a *analyzer.Analyzer) context.Context {
	return context.WithValue(ctx, analyzerCtxKey, a)
}

// GetAnalyzeHandler enqueues a request to run an analysis on a particular tree.
// This is usually hit by appengine cron rather than manually.
func GetAnalyzeHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")
	a, ok := c.Value(analyzerCtxKey).(*analyzer.Analyzer)
	if !ok {
		errStatus(c, w, http.StatusInternalServerError, "no analyzer set in Context")
		return
	}
	var alertsSummary *messages.AlertsSummary
	var err error
	c = appengine.WithContext(c, r)

	alertsSummary, err = generateBigQueryAlerts(c, a, tree)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	alertsSummary.Timestamp = messages.TimeToEpochTime(time.Now())
	if err := putAlertsBigQuery(c, tree, alertsSummary); err != nil {
		logging.Errorf(c, "error sending alerts to bigquery: %v", err)
		// Not fatal, just log and continue.
	}

	w.Write([]byte("ok"))
}

func generateBigQueryAlerts(c context.Context, a *analyzer.Analyzer, tree string) (*messages.AlertsSummary, error) {
	gkRules, err := getGatekeeperRules(c)
	if err != nil {
		logging.Errorf(c, "error getting gatekeeper rules: %v", err)
		return nil, err
	}

	builderAlerts, err := analyzer.GetBigQueryAlerts(c, tree)
	if err != nil {
		return nil, err
	}

	// Filter out ignored builders/steps.
	filteredBuilderAlerts := []*messages.BuildFailure{}
	for _, ba := range builderAlerts {
		builders := []*messages.AlertedBuilder{}
		for _, b := range ba.Builders {
			masterURL, err := url.Parse(fmt.Sprintf("https://build.chromium.org/p/%s", b.Master))
			if err != nil {
				return nil, err
			}
			master := &messages.MasterLocation{
				URL: *masterURL,
			}

			// The chromium.clang tree specifically wants all of the failures.
			// Some other trees, who also reference chromium.clang builders do *not* want all of them.
			// This extra tree == "chromium.clang" condition works around this shortcoming of the gatekeeper
			// tree config format.
			if tree == "chromium.clang" || !gkRules.ExcludeFailure(c, tree, master, b.Name, ba.StepAtFault.Step.Name) {
				builders = append(builders, b)
			}
		}
		if len(builders) > 0 {
			ba.Builders = builders
			filteredBuilderAlerts = append(filteredBuilderAlerts, ba)
		}
	}
	logging.Infof(c, "filtered alerts, before: %d after: %d", len(builderAlerts), len(filteredBuilderAlerts))
	attachFindItResults(c, filteredBuilderAlerts, a.FindIt)

	alerts := []*messages.Alert{}
	for _, ba := range filteredBuilderAlerts {
		title := fmt.Sprintf("Step %q failing on %d builder(s)", ba.StepAtFault.Step.Name, len(ba.Builders))
		// TODO(crbug.com/1043371): Remove the if condition after we disable automatic grouping.
		if len(ba.Builders) == 1 {
			title = fmt.Sprintf("Step %q failing on builder %q", ba.StepAtFault.Step.Name, ba.Builders[0].Name)
		}
		startTime := messages.TimeToEpochTime(time.Now())
		severity := messages.NewFailure
		for _, b := range ba.Builders {
			if b.StartTime > 0 && b.StartTime < startTime {
				startTime = b.StartTime
			}
			if b.LatestFailure-b.FirstFailure != 0 {
				severity = messages.ReliableFailure
			}
		}

		alert := &messages.Alert{
			Key:       getKeyForAlert(c, ba, tree),
			Title:     title,
			Extension: ba,
			StartTime: startTime,
			Severity:  severity,
		}

		switch ba.Reason.Kind() {
		case "test":
			alert.Type = messages.AlertTestFailure
		default:
			alert.Type = messages.AlertBuildFailure
		}

		alerts = append(alerts, alert)
	}

	logging.Infof(c, "%d alerts generated for tree %q", len(alerts), tree)

	alertsSummary := &messages.AlertsSummary{
		Timestamp:         messages.TimeToEpochTime(time.Now()),
		RevisionSummaries: map[string]*messages.RevisionSummary{},
		Alerts:            alerts,
	}

	if err := storeAlertsSummary(c, a, tree, alertsSummary); err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		return nil, err
	}

	return alertsSummary, nil
}

func getKeyForAlert(ctx context.Context, bf *messages.BuildFailure, tree string) string {
	if config.EnableAutoGrouping {
		return fmt.Sprintf("%s.%v", tree, bf.Reason.Signature())
	}
	step := bf.StepAtFault.Step.Name
	project := bf.Builders[0].Project
	bucket := bf.Builders[0].Bucket
	builder := bf.Builders[0].Name
	firstFailure := bf.Builders[0].FirstFailure
	strs := []string{tree, project, bucket, builder, step, strconv.FormatInt(firstFailure, 10)}
	return strings.Join(strs, model.AlertKeySeparator)
}

func attachFindItResults(ctx context.Context, failures []*messages.BuildFailure, finditClient client.FindIt) {
	for _, bf := range failures {
		stepName := bf.StepAtFault.Step.Name
		for _, someBuilder := range bf.Builders {
			results, err := finditClient.FinditBuildbucket(ctx, someBuilder.LatestFailure, []string{stepName})
			if err != nil {
				logging.Errorf(ctx, "error getting findit results: %v", err)
			}

			for _, result := range results {
				if result.StepName != bf.StepAtFault.Step.Name {
					continue
				}

				bf.Culprits = append(bf.Culprits, result.Culprits...)
				bf.HasFindings = bf.HasFindings || len(result.Culprits) > 0
				bf.IsFinished = bf.IsFinished || result.IsFinished
				bf.IsSupported = bf.IsSupported || result.IsSupported
			}
		}
	}
}

func alertCategory(a *messages.Alert) string {
	cat := "other"
	if a.Severity == messages.NewFailure {
		cat = "new"
	} else if a.Severity == messages.ReliableFailure {
		cat = "consistent"
	}
	return cat
}

// groupCounts maps alert category to a map of group IDs to counts of alerts
// in that category and group.
type groupCounts map[string]map[string]int

func storeAlertsSummary(c context.Context, a *analyzer.Analyzer, tree string, alertsSummary *messages.AlertsSummary) error {
	sort.Sort(messages.Alerts(alertsSummary.Alerts))
	sort.Stable(bySeverity(alertsSummary.Alerts))

	// Make sure we have summaries for each revision implicated in a builder failure.
	for _, alert := range alertsSummary.Alerts {
		if bf, ok := alert.Extension.(messages.BuildFailure); ok {
			for _, r := range bf.RegressionRanges {
				revs, err := a.GetRevisionSummaries(r.Revisions)
				if err != nil {
					return err
				}
				for _, rev := range revs {
					alertsSummary.RevisionSummaries[rev.GitHash] = rev
				}
			}
		}
	}
	alertsSummary.Timestamp = messages.TimeToEpochTime(time.Now())

	return putAlertsDatastore(c, tree, alertsSummary, true)
}

func putAlertsBigQuery(c context.Context, tree string, alertsSummary *messages.AlertsSummary) error {
	client, err := bigquery.NewClient(c, info.AppID(c))
	if err != nil {
		return err
	}
	up := bq.NewUploader(c, client, bqDatasetID, bqTableID)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true

	ts, err := ptypes.TimestampProto(alertsSummary.Timestamp.Time())
	if err != nil {
		return err
	}

	row := &gen.SOMAlertsEvent{
		Timestamp: ts,
		Tree:      tree,
		RequestId: appengine.RequestID(c),
	}

	for _, a := range alertsSummary.Alerts {
		alertEvt := &gen.SOMAlertsEvent_Alert{
			Key:   a.Key,
			Title: a.Title,
			Body:  a.Body,
			Type:  alertEventType(a.Type),
		}

		if bf, ok := a.Extension.(messages.BuildFailure); ok {
			for _, builder := range bf.Builders {
				newBF := &gen.SOMAlertsEvent_Alert_BuildbotFailure{
					Master:        builder.Master,
					Builder:       builder.Name,
					Step:          bf.StepAtFault.Step.Name,
					FirstFailure:  builder.FirstFailure,
					LatestFailure: builder.LatestFailure,
					LatestPassing: builder.LatestPassing,
				}
				alertEvt.BuildbotFailures = append(alertEvt.BuildbotFailures, newBF)
			}
		}

		row.Alerts = append(row.Alerts, alertEvt)
	}

	return up.Put(c, row)
}

var (
	alertToEventType = map[messages.AlertType]gen.SOMAlertsEvent_Alert_AlertType{
		messages.AlertStaleMaster:    gen.SOMAlertsEvent_Alert_STALE_MASTER,
		messages.AlertHungBuilder:    gen.SOMAlertsEvent_Alert_HUNG_BUILDER,
		messages.AlertOfflineBuilder: gen.SOMAlertsEvent_Alert_OFFLINE_BUILDER,
		messages.AlertIdleBuilder:    gen.SOMAlertsEvent_Alert_IDLE_BUILDER,
		messages.AlertInfraFailure:   gen.SOMAlertsEvent_Alert_INFRA_FAILURE,
		messages.AlertBuildFailure:   gen.SOMAlertsEvent_Alert_BUILD_FAILURE,
		messages.AlertTestFailure:    gen.SOMAlertsEvent_Alert_TEST_FAILURE,
	}
)

func alertEventType(t messages.AlertType) gen.SOMAlertsEvent_Alert_AlertType {
	if val, ok := alertToEventType[t]; ok {
		return val
	}
	panic("unknown alert type: " + string(t))
}
