// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"context"
	"io/ioutil"
	"testing"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes/duration"
	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
	"go.chromium.org/luci/config/validation"

	"infra/appengine/arquebus/app/util"
)

func createConfig(id string) *Config {
	// returns an assigner with a given ID and all required fields.
	var cfg Assigner
	So(proto.UnmarshalText(util.SampleValidAssignerCfg, &cfg), ShouldBeNil)
	cfg.Id = id

	return &Config{
		AccessGroup:      "trooper",
		MonorailHostname: "example.com",
		RotangHostname:   "example.net",
		Assigners:        []*Assigner{&cfg},
	}
}

func createOncallSource(rotation string) *UserSource_Oncall {
	return &UserSource_Oncall{
		Oncall: &Oncall{Rotation: rotation, Position: Oncall_PRIMARY},
	}
}

func createRotationSource(rotation string) *UserSource_Rotation {
	return &UserSource_Rotation{
		Rotation: &Oncall{Rotation: rotation, Position: Oncall_PRIMARY},
	}
}

func TestConfigValidator(t *testing.T) {
	t.Parallel()

	rules := validation.NewRuleSet()
	rules.Vars.Register("appid", func(context.Context) (string, error) {
		return "my_app", nil
	})
	SetupValidation(rules)

	validate := func(cfg *Config) error {
		c := validation.Context{Context: context.Background()}
		err := rules.ValidateConfig(
			&c, "services/my_app", configFile, []byte(cfg.String()),
		)
		So(err, ShouldBeNil)
		return c.Finalize()
	}

	Convey("devcfg template is valid", t, func() {
		content, err := ioutil.ReadFile(
			"../devcfg/services/dev/config-template.cfg",
		)
		So(err, ShouldBeNil)
		cfg := &Config{}
		So(proto.UnmarshalText(string(content), cfg), ShouldBeNil)
		So(validate(cfg), ShouldBeNil)
	})

	Convey("empty monorail_hostname is not valid", t, func() {
		cfg := createConfig("my-assigner")
		cfg.MonorailHostname = ""
		So(validate(cfg), ShouldErrLike, "empty value is not allowed")
	})

	Convey("empty rotang_hostname is not valid", t, func() {
		cfg := createConfig("my-assigner")
		cfg.RotangHostname = ""
		So(validate(cfg), ShouldErrLike, "empty value is not allowed")
	})

	Convey("validateConfig catches errors", t, func() {
		Convey("For duplicate IDs", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners = append(cfg.Assigners, cfg.Assigners[0])
			So(validate(cfg), ShouldErrLike, "duplicate id")
		})

		Convey("for invalid IDs", func() {
			msg := "invalid id"
			So(validate(createConfig("a-")), ShouldErrLike, msg)
			So(validate(createConfig("a-")), ShouldErrLike, msg)
			So(validate(createConfig("-a")), ShouldErrLike, msg)
			So(validate(createConfig("-")), ShouldErrLike, msg)
			So(validate(createConfig("a--b")), ShouldErrLike, msg)
			So(validate(createConfig("a@!3")), ShouldErrLike, msg)
			So(validate(createConfig("12=56")), ShouldErrLike, msg)
			So(validate(createConfig("A-cfg")), ShouldErrLike, msg)
		})

		Convey("for invalid owners", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Owners = []string{"example.com"}
			So(validate(cfg), ShouldErrLike, "invalid email address")
		})

		Convey("for missing interval", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = nil
			So(validate(cfg), ShouldErrLike, "missing interval")
		})

		Convey("for an interval shoter than 1 minute", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Interval = &duration.Duration{Seconds: 59}
			So(validate(cfg), ShouldErrLike, "interval should be at least one minute")
		})

		Convey("for missing assignees", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Assignees = []*UserSource{}
			Convey("with ccs", func() {
				// If ccs[] is given, assignees[] can be omitted.
				So(cfg.Assigners[0].Ccs, ShouldNotBeNil)
				So(validate(cfg), ShouldBeNil)
			})

			Convey("Without ccs", func() {
				cfg.Assigners[0].Ccs = []*UserSource{}
				So(validate(cfg), ShouldErrLike, "at least one of assignees or ccs must be given.")
			})
		})

		Convey("for missing ccs", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].Ccs = []*UserSource{}
			Convey("with assignees", func() {
				// If assignees[] is given, ccs[] can be omitted.
				So(cfg.Assigners[0].Ccs, ShouldNotBeNil)
				So(validate(cfg), ShouldBeNil)
			})

			Convey("Without assignees", func() {
				cfg.Assigners[0].Assignees = []*UserSource{}
				So(validate(cfg), ShouldErrLike, "at least one of assignees or ccs must be given.")
			})
		})

		Convey("for missing issue_query", func() {
			cfg := createConfig("my-assigner")
			cfg.Assigners[0].IssueQuery = nil
			So(validate(cfg), ShouldErrLike, "missing issue_query")
			cfg.Assigners[0].IssueQuery = &IssueQuery{ProjectNames: []string{}}
			So(validate(cfg), ShouldErrLike, "missing q")
			cfg.Assigners[0].IssueQuery = &IssueQuery{Q: "text"}
			So(validate(cfg), ShouldErrLike, "missing project_names")
		})

		Convey("for valid UserResource", func() {
			cfg := createConfig("my-assigner")
			assigner := cfg.Assigners[0]
			source := &UserSource{}
			assigner.Assignees[0] = source

			Convey("with valid rotation names", func() {
				source.From = createOncallSource("rotation")
				So(validate(cfg), ShouldBeNil)
				source.From = createOncallSource("r")
				So(validate(cfg), ShouldBeNil)
				source.From = createOncallSource("rotation-1")
				So(validate(cfg), ShouldBeNil)
				source.From = createOncallSource("My Oncall Rotation-2")
				So(validate(cfg), ShouldBeNil)
				source.From = createRotationSource("oncallator:foo-bar")
				So(validate(cfg), ShouldBeNil)
				source.From = createRotationSource("grotation:foo-bar")
				So(validate(cfg), ShouldBeNil)
			})
		})

		Convey("for invalid UserResource", func() {
			cfg := createConfig("my-assigner")
			assigner := cfg.Assigners[0]
			source := &UserSource{}
			assigner.Assignees[0] = source

			Convey("with missing value", func() {
				source.Reset()
				So(validate(cfg), ShouldErrLike, "missing or unknown user source")
			})

			Convey("with invalid rotation names", func() {
				invalidID := "invalid id"
				source.From = createOncallSource(" rotation")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createOncallSource("rotation ")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createOncallSource("r@otation")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createOncallSource("ro#tation")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createOncallSource(" ")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createOncallSource("")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createRotationSource("")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createRotationSource("foo-bar")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createRotationSource("oncallator: foo-bar")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createRotationSource("oncallator:foo:bar")
				So(validate(cfg), ShouldErrLike, invalidID)
				source.From = createRotationSource("oncallator:[foo-bar]")
				So(validate(cfg), ShouldErrLike, invalidID)
			})

			Convey("with invalid user", func() {
				source.From = &UserSource_Email{Email: "example"}
				So(validate(cfg), ShouldErrLike, "invalid email")
				source.From = &UserSource_Email{Email: "example.org"}
				So(validate(cfg), ShouldErrLike, "invalid email")
				source.From = &UserSource_Email{Email: "http://foo@example.org"}
				So(validate(cfg), ShouldErrLike, "invalid email")
			})
		})
	})
}
