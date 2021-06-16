package handler

import (
	"fmt"
	"testing"
	"time"

	"golang.org/x/net/context"

	"infra/appengine/sheriff-o-matic/som/analyzer"
	testhelper "infra/appengine/sheriff-o-matic/som/client/test"
	"infra/appengine/sheriff-o-matic/som/model"
	"infra/monitoring/messages"

	"go.chromium.org/gae/impl/dummy"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/appengine/gaetesting"
	bbpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/clock"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/logging/gologger"
)

func newTestContext() context.Context {
	c := gaetesting.TestingContext()
	ta := datastore.GetTestable(c)
	ta.Consistent(true)
	c = gologger.StdConfig.Use(c)
	return c
}

type giMock struct {
	info.RawInterface
	token  string
	expiry time.Time
	err    error
}

func (gi giMock) AccessToken(scopes ...string) (token string, expiry time.Time, err error) {
	return gi.token, gi.expiry, gi.err
}

func setUpGitiles(c context.Context) context.Context {
	return urlfetch.Set(c, &testhelper.MockGitilesTransport{
		Responses: map[string]string{
			gkTreesURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
			gkTreesInternalURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
			gkUnkeptTreesURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
			gkConfigInternalURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,

			gkConfigURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
			gkUnkeptConfigURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
		}})
}

type mockBuildBucket struct {
	builds []*bbpb.Build
	err    error
}

func (b *mockBuildBucket) LatestBuilds(ctx context.Context, builderIDs []*bbpb.BuilderID) ([]*bbpb.Build, error) {
	return b.builds, b.err
}

type mockFindit struct {
	res []*messages.FinditResultV2
	err error
}

func (mf *mockFindit) FinditBuildbucket(ctx context.Context, id int64, stepNames []string) ([]*messages.FinditResultV2, error) {
	return mf.res, mf.err
}

func (mf *mockFindit) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	return nil, fmt.Errorf("don't call this in tests")
}

func TestAttachFinditResults(t *testing.T) {
	Convey("smoke", t, func() {
		c := gaetesting.TestingContext()
		bf := []*messages.BuildFailure{
			{
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "some step",
					},
				},
			},
		}
		fc := &mockFindit{}
		attachFindItResults(c, bf, fc)
		So(len(bf), ShouldEqual, 1)
	})

	Convey("some results", t, func() {
		c := newTestContext()
		bf := []*messages.BuildFailure{
			{
				Builders: []*messages.AlertedBuilder{
					{
						Name: "some builder",
					},
				},
				StepAtFault: &messages.BuildStep{
					Step: &messages.Step{
						Name: "some step",
					},
				},
			},
		}
		fc := &mockFindit{
			res: []*messages.FinditResultV2{{
				StepName: "some step",
				Culprits: []*messages.Culprit{
					{
						Commit: &messages.GitilesCommit{
							Host:           "githost",
							Project:        "proj",
							ID:             "0xdeadbeef",
							CommitPosition: 1234,
						},
					},
				},
				IsFinished:  true,
				IsSupported: true,
			}},
		}
		attachFindItResults(c, bf, fc)
		So(len(bf), ShouldEqual, 1)
		So(len(bf[0].Culprits), ShouldEqual, 1)
		So(bf[0].HasFindings, ShouldEqual, true)
	})
}

func TestStoreAlertsSummary(t *testing.T) {
	Convey("success", t, func() {
		c := gaetesting.TestingContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = setUpGitiles(c)
		a := analyzer.New(5, 100)
		err := storeAlertsSummary(c, a, "some tree", &messages.AlertsSummary{
			Alerts: []*messages.Alert{
				{
					Title: "foo",
					Extension: &messages.BuildFailure{
						RegressionRanges: []*messages.RegressionRange{
							{Repo: "some repo", URL: "about:blank", Positions: []string{}, Revisions: []string{}},
						},
					},
				},
			},
		})
		So(err, ShouldBeNil)
	})
}

type fakeReasonRaw struct {
	signature string
	title     string
}

func (f *fakeReasonRaw) Signature() string {
	if f.signature != "" {
		return f.signature
	}

	return "fakeSignature"
}

func (f *fakeReasonRaw) Kind() string {
	return "fakeKind"
}

func (f *fakeReasonRaw) Title([]*messages.BuildStep) string {
	if f.title == "" {
		return "fakeTitle"
	}
	return f.title
}

func (f *fakeReasonRaw) Severity() messages.Severity {
	return messages.NewFailure
}

type annList []model.Annotation

func (a annList) Len() int {
	return len(a)
}

func (a annList) Less(i, j int) bool {
	return a[i].Key < a[j].Key
}

func (a annList) Swap(i, j int) {
	a[i], a[j] = a[j], a[i]
}
