// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"crypto/sha1"
	"fmt"
	"strings"
	"testing"
	"time"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"
)

var _ = fmt.Printf

func TestAnnotation(t *testing.T) {
	t.Parallel()

	Convey("Annotation", t, func() {
		c := gaetesting.TestingContext()
		cl := testclock.New(testclock.TestTimeUTC)
		c = clock.Set(c, cl)

		ann := &Annotation{
			Key:              "foobar",
			KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
			ModificationTime: cl.Now(),
		}
		cl.Add(time.Hour)

		Convey("allows weird keys", func() {
			ann.Key = "hihih\"///////%20     lol"
			ann.KeyDigest = fmt.Sprintf("%x", sha1.Sum([]byte(ann.Key)))
			So(datastore.Put(c, ann), ShouldBeNil)
		})

		Convey("allows long keys", func() {
			// App engine key size limit is 500 characters
			ann.Key = strings.Repeat("annnn", 200)
			ann.KeyDigest = fmt.Sprintf("%x", sha1.Sum([]byte(ann.Key)))
			So(datastore.Put(c, ann), ShouldBeNil)
		})

		Convey("with mocked checkAndGetBug", func() {
			Convey("add", func() {
				Convey("time", func() {
					changeS := `{"snoozeTime":123123}`
					needRefresh, err := ann.Add(c, strings.NewReader(changeS))

					So(err, ShouldBeNil)
					So(needRefresh, ShouldBeFalse)
					So(ann.SnoozeTime, ShouldEqual, 123123)
					So(ann.Bugs, ShouldBeNil)
					So(ann.Comments, ShouldBeNil)
					So(ann.ModificationTime, ShouldResemble, cl.Now())
				})

				Convey("bugs", func() {
					changeString := `{"bugs":[{"id": "123123", "projectId": "chromium"}]}`
					Convey("basic", func() {
						needRefresh, err := ann.Add(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeTrue)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldResemble, []MonorailBug{{BugID: "123123", ProjectID: "chromium"}})
						So(ann.ModificationTime, ShouldResemble, cl.Now())

						Convey("duplicate bugs", func() {
							cl.Add(time.Hour)
							needRefresh, err = ann.Add(c, strings.NewReader(changeString))
							So(err, ShouldBeNil)
							So(needRefresh, ShouldBeFalse)

							So(ann.SnoozeTime, ShouldEqual, 0)
							So(ann.Bugs, ShouldResemble, []MonorailBug{{BugID: "123123", ProjectID: "chromium"}})
							So(ann.Comments, ShouldBeNil)
							// We aren't changing the annotation, so the modification time shouldn't update.
							So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
						})
					})

					Convey("bug error", func() {
						needRefresh, err := ann.Add(c, strings.NewReader("hi"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldBeNil)
						So(ann.Comments, ShouldBeNil)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})

				Convey("comments", func() {
					changeString := `{"comments":["woah", "man", "comments"]}`
					Convey("basic", func() {
						needRefresh, err := ann.Add(c, strings.NewReader(changeString))
						t := cl.Now()

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldBeNil)

						So(ann.Comments, ShouldResemble, []Comment{{"woah", "", t}, {"man", "", t}, {"comments", "", t}})
						So(ann.ModificationTime, ShouldResemble, t)
					})

					Convey("comments error", func() {
						needRefresh, err := ann.Add(c, strings.NewReader("plz don't add me"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldBeNil)
						So(ann.Comments, ShouldBeNil)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})
			})

			Convey("remove", func() {
				t := cl.Now()
				fakeComments := []Comment{{"hello", "", t}, {"world", "", t}, {"hehe", "", t}}
				fakeBugs := []MonorailBug{{BugID: "123123", ProjectID: "chromium"}, {BugID: "bug2", ProjectID: "fuchsia"}}
				ann.SnoozeTime = 100
				ann.Bugs = fakeBugs
				ann.Comments = fakeComments

				Convey("time", func() {
					changeS := `{"snoozeTime":true}`
					needRefresh, err := ann.Remove(c, strings.NewReader(changeS))

					So(err, ShouldBeNil)
					So(needRefresh, ShouldBeFalse)
					So(ann.SnoozeTime, ShouldEqual, 0)
					So(ann.Bugs, ShouldResemble, fakeBugs)
					So(ann.Comments, ShouldResemble, fakeComments)
					So(ann.ModificationTime, ShouldResemble, cl.Now())
				})

				Convey("bugs", func() {
					changeString := `{"bugs":[{"id": "123123", "projectId": "chromium"}]}`
					Convey("basic", func() {
						needRefresh, err := ann.Remove(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Comments, ShouldResemble, fakeComments)
						So(ann.Bugs, ShouldResemble, []MonorailBug{{BugID: "bug2", ProjectID: "fuchsia"}})
						So(ann.ModificationTime, ShouldResemble, cl.Now())
					})

					Convey("bug error", func() {
						needRefresh, err := ann.Remove(c, strings.NewReader("badbugzman"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, fakeBugs)
						So(ann.Comments, ShouldResemble, fakeComments)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})

				Convey("comments", func() {
					Convey("basic", func() {
						changeString := `{"comments":[1]}`
						needRefresh, err := ann.Remove(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, fakeBugs)
						So(ann.Comments, ShouldResemble, []Comment{{"hello", "", t}, {"hehe", "", t}})
						So(ann.ModificationTime, ShouldResemble, cl.Now())
					})

					Convey("bad format", func() {
						needRefresh, err := ann.Remove(c, strings.NewReader("don't do this"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, fakeBugs)
						So(ann.Comments, ShouldResemble, fakeComments)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})

					Convey("invalid index", func() {
						changeString := `{"comments":[3]}`
						needRefresh, err := ann.Remove(c, strings.NewReader(changeString))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, fakeBugs)
						So(ann.Comments, ShouldResemble, fakeComments)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})

			})
		})
	})
}

func TestAlertJSONNonGroupingGetStepName(t *testing.T) {
	Convey("valid ID", t, func() {
		ann := &AlertJSONNonGrouping{
			ID: "tree$!project$!bucket$!builder$!step$!0",
		}
		stepName, err := ann.GetStepName()
		So(err, ShouldBeNil)
		So(stepName, ShouldEqual, "step")
	})
	Convey("invalid ID", t, func() {
		ann := &AlertJSONNonGrouping{
			ID: "my key",
		}
		_, err := ann.GetStepName()
		So(err, ShouldNotBeNil)
	})
	Convey("invalid ID 1", t, func() {
		ann := &AlertJSONNonGrouping{
			ID: "1$!2$!3$!4$!5$!6$!7",
		}
		_, err := ann.GetStepName()
		So(err, ShouldNotBeNil)
	})
}

func TestAnnotationGetStepName(t *testing.T) {
	c := gaetesting.TestingContext()
	Convey("Get step name valid", t, func() {
		ann := &Annotation{
			Tree: datastore.MakeKey(c, "Tree", "chromium"),
			Key:  "chromium.step_name",
		}
		stepName, err := ann.GetStepName()
		So(err, ShouldBeNil)
		So(stepName, ShouldEqual, "step_name")
	})
	Convey("Get step name when tree name containing dot", t, func() {
		ann := &Annotation{
			Tree: datastore.MakeKey(c, "Tree", "chromium.clang"),
			Key:  "chromium.clang.step_name",
		}
		stepName, err := ann.GetStepName()
		So(err, ShouldBeNil)
		So(stepName, ShouldEqual, "step_name")
	})
	Convey("Get step name invalid", t, func() {
		ann := &Annotation{
			Tree: datastore.MakeKey(c, "Tree", "chromium"),
			Key:  "step_name",
		}
		_, err := ann.GetStepName()
		So(err, ShouldNotBeNil)
	})
}

func TestIsGroupAnnotation(t *testing.T) {
	Convey("is group annotation returns true", t, func() {
		ann := &Annotation{
			Key: "e2d935ac-c623-4c10-b1e3-73bb54584f8f",
		}
		So(ann.IsGroupAnnotation(), ShouldBeTrue)
	})
	Convey("is group annotation returns false", t, func() {
		ann := &Annotation{
			Key: "abcd",
		}
		So(ann.IsGroupAnnotation(), ShouldBeFalse)
	})
}
