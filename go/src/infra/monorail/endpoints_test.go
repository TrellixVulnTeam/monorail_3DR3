// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/retry/transient"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestEndpointsInsertIssue(t *testing.T) {
	t.Parallel()

	Convey("Endpoints client: InsertIssue", t, func() {
		ctx := context.Background()

		Convey("Insert issue request succeeds", func(c C) {
			req := &InsertIssueRequest{
				Issue: &Issue{
					Summary:     "Write tests for monorail client",
					Author:      &AtomPerson{Name: "seanmccullough@chromium.org"},
					Owner:       &AtomPerson{Name: "nodir@chromium.org"},
					Status:      StatusStarted,
					Cc:          []*AtomPerson{{Name: "agable@chromium.org"}},
					Description: "We should keep our code coverage high, so write tests",
					Components:  []string{"Infra"},
					Labels:      []string{"M-53"},
					ProjectId:   "chromium",
				},
			}

			res := &InsertIssueResponse{
				Issue: &Issue{},
			}
			*res.Issue = *req.Issue
			res.Issue.Id = 1

			var insertIssueServer *httptest.Server
			insertIssueServer = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				c.So(r.URL.String(), ShouldEqual, "/projects/chromium/issues?sendEmail=false")

				actualReq := &Issue{}
				err := json.NewDecoder(r.Body).Decode(actualReq)
				c.So(err, ShouldBeNil)
				c.So(actualReq, ShouldResemble, req.Issue)

				err = json.NewEncoder(w).Encode(res.Issue)
				c.So(err, ShouldBeNil)
			}))
			defer insertIssueServer.Close()

			httpClient := &http.Client{Timeout: time.Second}
			client := NewEndpointsClient(httpClient, insertIssueServer.URL)
			actualRes, err := client.InsertIssue(ctx, req)
			So(err, ShouldBeNil)
			So(actualRes, ShouldResemble, res)
		})

		Convey("Insert issue with invalid request", func(c C) {
			req := &InsertIssueRequest{
				Issue: &Issue{
					Summary: "Write tests for monorail client",
					Author:  &AtomPerson{Name: "seanmccullough@chromium.org"},
					Owner:   &AtomPerson{Name: "nodir@chromium.org"},
					Status:  StatusStarted,
				},
			}

			httpClient := &http.Client{Timeout: time.Second}
			client := NewEndpointsClient(httpClient, "https://example.com")
			_, err := client.InsertIssue(ctx, req)
			So(err, ShouldErrLike, "no projectId")
		})

		Convey("Insert comment request", func(c C) {
			req := &InsertCommentRequest{
				Issue: &IssueRef{
					ProjectId: "chromium",
					IssueId:   1,
				},
				Comment: &InsertCommentRequest_Comment{
					Content: "Done",
					Updates: &Update{
						Status: StatusFixed,
					},
				},
			}

			var handler http.HandlerFunc
			var server *httptest.Server
			actualURL := ""
			server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				actualURL = r.URL.String()
				handler(w, r)
			}))
			defer server.Close()

			client := NewEndpointsClient(nil, server.URL)

			Convey("Succeeds", func() {
				handler = func(w http.ResponseWriter, r *http.Request) {
					actualReq := &InsertCommentRequest_Comment{}
					err := json.NewDecoder(r.Body).Decode(actualReq)
					c.So(err, ShouldBeNil)
					c.So(actualReq, ShouldResemble, req.Comment)

					fmt.Fprint(w, "{}")
				}

				_, err := client.InsertComment(ctx, req)
				So(err, ShouldBeNil)
				c.So(actualURL, ShouldEqual, "/projects/chromium/issues/1/comments?")
			})

			Convey("SendEmail", func() {
				req.SendEmail = true
				handler = func(w http.ResponseWriter, r *http.Request) {
					fmt.Fprint(w, "{}")
				}

				_, err := client.InsertComment(ctx, req)
				So(err, ShouldBeNil)
				c.So(actualURL, ShouldEqual, "/projects/chromium/issues/1/comments?sendEmail=true")
			})

			Convey("Transient error", func(c C) {
				test := func(status int) {
					handler = func(w http.ResponseWriter, r *http.Request) {
						w.WriteHeader(status)
					}

					_, err := client.InsertComment(ctx, req)
					So(err, ShouldNotBeNil)
					So(transient.Tag.In(err), ShouldBeTrue)
				}
				Convey("With HTTP 404", func() {
					test(404)
				})
				Convey("With HTTP 503", func() {
					test(503)
				})
			})
		})
	})
}

func TestEndpointsListComments(t *testing.T) {
	t.Parallel()

	Convey("Endpoints client: ListComments", t, func() {
		ctx := context.Background()

		Convey("succeeds", func(c C) {
			req := &ListCommentsRequest{Issue: &IssueRef{IssueId: 859707, ProjectId: "chromium"}}

			var srv *httptest.Server
			srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				c.So(r.URL.String(), ShouldEqual, "/projects/chromium/issues/859707/comments?startIndex=0")
				_, err := w.Write([]byte(`{
					"items": [
						{
						 "canDelete": false,
						 "author": { "kind": "monorail#issuePerson", "name": "a@example.com" },
						 "is_description": true,
						 "content": "Actually, this is description\n",
						 "published": "2018-07-02T23:12:47",
						 "id": 0
						},
						{
						 "canDelete": false,
						 "author": { "kind": "monorail#issuePerson", "name": "b@example.com" },
						 "is_description": false,
						 "content": "lol",
						 "updates": {
							"status": "Started",
							"kind": "monorail#issueCommentUpdate",
							"labels": [
							 "-Type-Task",
							 "Type-Feature"
							]
						 },
						 "published": "2018-07-02T23:14:59",
						 "id": 1
						}
					 ] ,
					 "kind": "monorail#issueCommentList",
					 "totalResults": 2,
					 "etag": "\"se1Lh8IyiCDwsGaF9fqPeVscq_I/rYRAvt40qdVXvtOjNLeqW1ZMUjA\""
				}`))
				c.So(err, ShouldBeNil)
			}))
			defer srv.Close()

			client := NewEndpointsClient(&http.Client{Timeout: time.Second}, srv.URL)
			res, err := client.ListComments(ctx, req)
			So(err, ShouldBeNil)
			So(res, ShouldResembleProto, &ListCommentsResponse{
				TotalResults: 2,
				Items: []*Comment{
					{
						Author:        &AtomPerson{Name: "a@example.com"},
						IsDescription: true,
						Content:       "Actually, this is description\n",
						Published:     "2018-07-02T23:12:47",
						Id:            0,
					},
					{
						Author:        &AtomPerson{Name: "b@example.com"},
						IsDescription: false,
						Content:       "lol",
						Published:     "2018-07-02T23:14:59",
						Id:            1,
						Updates: &Update{
							Status: "Started",
							Labels: []string{"-Type-Task", "Type-Feature"},
						},
					},
				},
			})
		})
	})
}
