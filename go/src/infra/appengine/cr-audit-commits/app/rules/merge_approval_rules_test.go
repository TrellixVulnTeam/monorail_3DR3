// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package rules

import (
	"testing"

	"context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"

	"infra/monorail"
)

func TestMergeApprovalRules(t *testing.T) {

	Convey("Merge Approval rules work", t, func() {
		ctx := memory.Use(context.Background())
		rs := &RepoState{
			RepoURL: "https://a.googlesource.com/a.git/+/master",
		}
		datastore.Put(ctx, rs)
		rc := &RelevantCommit{
			RepoStateKey:  datastore.KeyForObj(ctx, rs),
			CommitHash:    "b07c0de",
			Status:        AuditScheduled,
			CommitMessage: "Making sure changes committed are approved",
		}
		cfg := &RefConfig{
			BaseRepoURL: "https://a.googlesource.com/a.git",
			GerritURL:   "https://a-review.googlesource.com/",
			BranchName:  "3325",
			Metadata:    "MilestoneNumber:65",
		}
		ap := &AuditParams{
			TriggeringAccount: "releasebot@sample.com",
			RepoCfg:           cfg,
		}
		testClients := &Clients{}
		testClients.Monorail = MockMonorailClient{
			Gi: &monorail.Issue{},
			Ii: &monorail.InsertIssueResponse{
				Issue: &monorail.Issue{},
			},
		}
		Convey("Change to commit has a valid bug with merge approval label in comment history", func() {
			testClients.Monorail = MockMonorailClient{
				Gi: &monorail.Issue{
					Id: 123456,
				},
				Cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "benmason@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{
									"-Hotlist-Merge-Review",
									"-Merge-Review-65",
									"Merge-Approved-65",
								},
							},
						},
					},
				},
			}
			rc.CommitMessage = "This change has a valid bug ID with merge approval label in comment history \nBug:123456"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RulePassed)
		})
		Convey("Change to commit has a valid bug prefixed with chromium with merge approval label in comment history", func() {
			testClients.Monorail = MockMonorailClient{
				Gi: &monorail.Issue{
					Id: 123456,
				},
				Cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "benmason@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{
									"-Hotlist-Merge-Review",
									"-Merge-Review-65",
									"Merge-Approved-65",
								},
							},
						},
					},
				},
			}
			rc.CommitMessage = "This change has a valid bug ID with merge approval label in comment history \nBug: chromium:123456"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RulePassed)
		})
		Convey("Change to commit has multiple bugs including an invalid one", func() {
			testClients.Monorail = MockMonorailClient{
				Gi: &monorail.Issue{
					Id: 123456,
				},
				Cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "benmason@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{
									"-Hotlist-Merge-Review",
									"-Merge-Review-65",
									"Merge-Approved-65",
								},
							},
						},
					},
				},
			}
			rc.CommitMessage = "This change to commit has multiple bugs including an invalid one \nBug:123456, 654321"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RulePassed)
		})
		Convey("Change to commit has an invalid bug and a valid one with no merge approval label", func() {
			testClients.Monorail = MockMonorailClient{
				Gi: &monorail.Issue{
					Id:     123456,
					Labels: []string{},
				},
				Cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{
						{
							Author: &monorail.AtomPerson{Name: "benmason@chromium.org"},
							Updates: &monorail.Update{
								Status: "Fixed",
								Labels: []string{},
							},
						},
					},
				},
			}
			rc.CommitMessage = "Change to commit has an invalid bug and a valid one with no merge approval label \nBug: 265485, 123456"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RuleFailed)
		})
		Convey("Change to commit has multiple invalid bugs", func() {
			testClients.Monorail = MockMonorailClient{
				Gi: &monorail.Issue{
					Id:     123456,
					Labels: []string{},
				},
				Cl: &monorail.ListCommentsResponse{
					Items: []*monorail.Comment{},
				},
			}
			rc.CommitMessage = "All bugs listed on this change to commit are all invalid \nBug: 654321, 587469"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RuleFailed)
		})
		Convey("Change to commit is authored by a Chrome TPM", func() {
			rc.CommitMessage = "This change's author is a Chrome TPM"
			rc.AuthorAccount = "benmason@chromium.org"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RulePassed)

		})
		Convey("Change to commit is committed by a Chrome TPM", func() {
			rc.CommitMessage = "This change's committer is a Chrome TPM"
			rc.CommitterAccount = "benmason@chromium.org"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RulePassed)

		})
		Convey("Change to commit is by Chrome release bot", func() {
			rc.CommitMessage = "This change's author is Chrome release bot"
			rc.AuthorAccount = "chrome-release-bot@chromium.org"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RulePassed)

		})
		Convey("Change to commit has no bug ID field", func() {
			rc.CommitMessage = "This change does not have a bug ID field"
			rc.CommitHash = "a1b2c3d4e5f6"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RuleFailed)
			//Check result message
			So(rr.Message, ShouldContainSubstring, rc.CommitHash)

		})
		Convey("Change to commit has an invalid bug ID", func() {
			rc.CommitMessage = "This change has an invalid bug ID \nBug=none"
			rc.CommitHash = "a1b2c3d4e5f6"
			// Run rule
			rr, _ := OnlyMergeApprovedChange{}.Run(ctx, ap, rc, testClients)
			// Check result code
			So(rr.RuleResultStatus, ShouldEqual, RuleFailed)
			//Check result message
			So(rr.Message, ShouldContainSubstring, rc.CommitHash)
		})

	})
}
