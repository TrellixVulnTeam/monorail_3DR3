// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

package main

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/functions/shellcheck/runner"
)

const (
	testInputDir       = "testdata"
	triciumResultsPath = "tricium/data/results.json"
)

func TestRun(t *testing.T) {
	r := &runner.Runner{
		Path:   findShellCheckBin(),
		Dir:    testInputDir,
		Logger: runnerLogger,
		Enable: "require-variable-braces",
	}
	version, err := r.Version()
	if err != nil {
		t.Skip("no valid shellcheck bin found; skipping test")
	}
	if !strings.HasPrefix(version, "0.7.") {
		t.Skipf("got shellcheck version %q want 0.7.x; skipping test", version)
	}

	outputDir, err := ioutil.TempDir("", "tricium-shellcheck-test")
	if err != nil {
		panic(err)
	}
	defer os.RemoveAll(outputDir)

	run(r, testInputDir, outputDir, "*.other,*.sh")

	resultsData, err := ioutil.ReadFile(filepath.Join(outputDir, triciumResultsPath))
	if err != nil {
		panic(err)
	}

	var results map[string][]map[string]interface{}

	if err := json.Unmarshal(resultsData, &results); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	comments, ok := results["comments"]
	Convey("Results should be properly formatted", t, func() {
		Convey("Results should have comments", func() {
			So(ok, ShouldBeTrue)
		})

		Convey("There should be multiple comments", func() {
			So(len(comments), ShouldEqual, 5)
		})

		Convey("Comments should have specific contents", func() {
			So(comments, ShouldResemble, []map[string]interface{}{
				{
					"category":  "ShellCheck/SC2034",
					"message":   "warning: FLAGS_flag appears unused. Verify use (or export if used externally).\n\nhttps://github.com/koalaman/shellcheck/wiki/SC2034",
					"path":      "bad.sh",
					"startLine": float64(3),
					"endLine":   float64(3),
					"startChar": float64(15),
					"endChar":   float64(19),
				},
				{
					"category":  "ShellCheck/SC2034",
					"message":   "warning: unused appears unused. Verify use (or export if used externally).\n\nhttps://github.com/koalaman/shellcheck/wiki/SC2034",
					"path":      "bad.sh",
					"startLine": float64(5),
					"endLine":   float64(5),
					"startChar": float64(1),
					"endChar":   float64(7),
				},
				{
					"category":  "ShellCheck/SC1037",
					"message":   "error: Braces are required for positionals over 9, e.g. ${10}.\n\nhttps://github.com/koalaman/shellcheck/wiki/SC1037",
					"path":      "bad.sh",
					"startLine": float64(6),
					"endLine":   float64(6),
					"startChar": float64(6),
					"endChar":   float64(6),
				},
				{
					"category":  "ShellCheck/SC2086",
					"message":   "info: Double quote to prevent globbing and word splitting.\n\nhttps://github.com/koalaman/shellcheck/wiki/SC2086",
					"path":      "bad.sh",
					"startLine": float64(8),
					"endLine":   float64(8),
					"startChar": float64(5),
					"endChar":   float64(9),
				},
				{
					"category":  "ShellCheck/SC2250",
					"message":   "style: Prefer putting braces around variable references even when not strictly required.\n\nhttps://github.com/koalaman/shellcheck/wiki/SC2250",
					"path":      "bad.sh",
					"startLine": float64(8),
					"endLine":   float64(8),
					"startChar": float64(5),
					"endChar":   float64(9),
				},
			})
		})
	})
}

func assertMapKeyEqual(t *testing.T, m map[string]interface{}, k string, want interface{}) {
	t.Helper()
	got, _ := m[k]
	if !reflect.DeepEqual(got, want) {
		t.Errorf("key %q got %v want %v", k, got, want)
	}
}
