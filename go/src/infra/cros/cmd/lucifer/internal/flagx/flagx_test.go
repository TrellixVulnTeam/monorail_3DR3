// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"flag"
	"io/ioutil"
	"reflect"
	"testing"

	"infra/cros/cmd/lucifer/internal/autotest/atutil"
	"infra/cros/cmd/lucifer/internal/autotest/dutprep"
)

// Check that not passing the flag keeps the default nil value, which
// works like an empty slice.
func TestCommaListParseWithDefaultNil(t *testing.T) {
	t.Parallel()
	fs := testFlagSet()
	var s []string
	fs.Var(CommaList(&s), "list", "Some list")
	if err := fs.Parse([]string{}); err != nil {
		t.Fatalf("Parse returned error: %s", err)
	}
	if len(s) != 0 {
		t.Errorf("Comma list value is not empty: %v", s)
	}
}

// Check that passing a single item parses to a corresponding one
// length slice.
func TestCommaListParseWithSingleItem(t *testing.T) {
	t.Parallel()
	fs := testFlagSet()
	var s []string
	fs.Var(CommaList(&s), "list", "Some list")
	if err := fs.Parse([]string{"-list", "foo"}); err != nil {
		t.Fatalf("Parse returned error: %s", err)
	}
	exp := []string{"foo"}
	if !reflect.DeepEqual(s, exp) {
		t.Errorf("Unexpected Comma list value: got %#v, expected %#v", s, exp)
	}
}

// Check that passing a string with commas parses to a corresponding
// slice with more than one item.
func TestCommaListParseWithManyItems(t *testing.T) {
	t.Parallel()
	fs := testFlagSet()
	var s []string
	fs.Var(CommaList(&s), "list", "Some list.")
	if err := fs.Parse([]string{"-list", "foo,bar,spam"}); err != nil {
		t.Fatalf("Parse returned error: %s", err)
	}
	exp := []string{"foo", "bar", "spam"}
	if !reflect.DeepEqual(s, exp) {
		t.Errorf("Unexpected Comma list value: got %#v, expected %#v", s, exp)
	}
}

// Check that task strings get parsed to the correct AdminTaskType.
func TestTaskTypeParse(t *testing.T) {
	t.Parallel()
	cases := []struct {
		arg      string
		expected atutil.AdminTaskType
	}{
		{"", atutil.NoTask},
		{"cleanup", atutil.Cleanup},
		{"repair", atutil.Repair},
		{"reset", atutil.Reset},
		{"verify", atutil.Verify},
	}
	for _, c := range cases {
		var tt atutil.AdminTaskType
		fs := testFlagSet()
		fs.Var(TaskType(&tt, 0), "task", "Task name")
		if err := fs.Parse([]string{"-task", c.arg}); err != nil {
			t.Errorf("Parse returned an error for %s: %s", c.arg, err)
			continue
		}
		if tt != c.expected {
			t.Errorf("Parsing %s, got %s, expected %s", c.arg, tt, c.expected)
		}
	}
}

// Check that passing an invalid TaskType string causes an error.
func TestTaskTypeParseError(t *testing.T) {
	t.Parallel()
	cases := []struct {
		arg string
		c   TaskTypeConfig
	}{
		{"blah", 0},
		{"spam", 0},
		{"", RejectNoTask},
		{"repair", RejectRepair},
	}
	for _, c := range cases {
		var tt atutil.AdminTaskType
		fs := testFlagSet()
		fs.Var(TaskType(&tt, c.c), "task", "Task name")
		if err := fs.Parse([]string{"-task", c.arg}); err == nil {
			t.Errorf("Parse did not return error for %s with config %d", c.arg, c.c)
		}
	}
}

// Check that a JSON object string gets parsed correctly using JSONMap.
func TestParseJSONMap(t *testing.T) {
	t.Parallel()
	cases := []struct {
		arg      string
		expected map[string]string
	}{
		{`{"foo": "bar"}`, map[string]string{"foo": "bar"}},
	}
	for _, c := range cases {
		var m map[string]string
		fs := testFlagSet()
		fs.Var(JSONMap(&m), "map", "Some map")
		if err := fs.Parse([]string{"-map", c.arg}); err != nil {
			t.Errorf("Parse returned an error for %s: %s", c.arg, err)
			continue
		}
		if !reflect.DeepEqual(m, c.expected) {
			t.Errorf("Parsing %s, got %#v, expected %#v", c.arg, m, c.expected)
		}
	}
}

// Check that passing action arguments with commas parses to a corresponding
// action slice with more than one item.
func TestDeployActionListParseWithManyItems(t *testing.T) {
	t.Parallel()
	fs := testFlagSet()
	var a []dutprep.Action
	fs.Var(DeployActionList(&a), "actions", "Some action list.")
	if err := fs.Parse([]string{"-actions", "stage-usb,install-test-image"}); err != nil {
		t.Fatalf("Parse returned error: %s", err)
	}
	exp := []dutprep.Action{dutprep.StageUSB, dutprep.InstallTestImage}
	if !reflect.DeepEqual(a, exp) {
		t.Errorf("Unexpected action list value: got %s, expected %s", a, exp)
	}
}

func testFlagSet() *flag.FlagSet {
	fs := flag.NewFlagSet("test", flag.ContinueOnError)
	fs.Usage = func() {}
	fs.SetOutput(ioutil.Discard)
	return fs
}
