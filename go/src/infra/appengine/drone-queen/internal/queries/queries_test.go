// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package queries

import (
	"fmt"
	"sort"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/google/go-cmp/cmp"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"golang.org/x/net/context"

	"infra/appengine/drone-queen/api"
	"infra/appengine/drone-queen/internal/config"
	"infra/appengine/drone-queen/internal/entities"
	"infra/appengine/drone-queen/internal/testlogger"
)

func TestCreateNewDrone(t *testing.T) {
	t.Parallel()
	ctx := gaetesting.TestingContextWithAppID("go-test")
	const dur = 1 * time.Minute
	ctx = config.Use(ctx, &config.Config{
		AssignmentDuration: ptypes.DurationProto(dur),
	})
	now := time.Date(2000, 1, 2, 3, 4, 5, 7006, time.UTC)
	id, err := CreateNewDrone(ctx, now)
	if err != nil {
		t.Fatal(err)
	}
	d := entities.Drone{ID: id}
	if err := datastore.Get(ctx, &d); err != nil {
		t.Errorf("Could not get drone entity %v missing: %v", id, err)
	}
	want := entities.Drone{
		ID:         id,
		Expiration: now.Add(dur).Truncate(time.Microsecond),
	}
	if diff := cmp.Diff(want, d); diff != "" {
		t.Errorf("Unexpected drone (-want +got):\n%s", diff)
	}
}

func TestCreateNewDrone_with_generator(t *testing.T) {
	t.Parallel()
	t.Run("retry uuid generation", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		if err := datastore.Put(ctx, &entities.Drone{ID: "drone1"}); err != nil {
			t.Fatal(err)
		}
		i := 0
		generator := func() string {
			i++
			return fmt.Sprintf("drone%d", i)
		}
		id, err := createNewDrone(ctx, time.Time{}, generator)
		if err != nil {
			t.Fatal(err)
		}
		if id != "drone2" {
			t.Errorf("Got drone id %v; expected drone2", id)
		}
		d := entities.Drone{ID: id}
		if err := datastore.Get(ctx, &d); err != nil {
			t.Errorf("Could not get drone entity %v missing: %v", id, err)
		}
	})
	t.Run("retry uuid generation when uuid used by expired drone", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		now := time.Date(2000, 1, 2, 3, 4, 5, 7006, time.UTC)
		d := entities.Drone{
			ID:         "drone1",
			Expiration: now.Add(-time.Minute),
		}
		if err := datastore.Put(ctx, &d); err != nil {
			t.Fatal(err)
		}
		i := 0
		generator := func() string {
			i++
			return fmt.Sprintf("drone%d", i)
		}
		id, err := createNewDrone(ctx, time.Time{}, generator)
		if err != nil {
			t.Fatal(err)
		}
		if id != "drone2" {
			t.Errorf("Got drone id %v; expected drone2", id)
		}
		d = entities.Drone{ID: id}
		if err := datastore.Get(ctx, &d); err != nil {
			t.Errorf("Could not get drone entity %v missing: %v", id, err)
		}
	})
}

func TestGetDroneDUTs(t *testing.T) {
	t.Parallel()
	ctx := gaetesting.TestingContextWithAppID("go-test")
	datastore.GetTestable(ctx).Consistent(true)
	duts := []*entities.DUT{
		{ID: "ionasal", AssignedDrone: "earthes"},
		{ID: "nayaflask", AssignedDrone: "earthes"},
		{ID: "nei", AssignedDrone: "earthes", Draining: true},
		{ID: "casty", AssignedDrone: "delta"},
		{ID: "shurelia"},
	}
	applyGroup(ctx, duts)
	if err := datastore.Put(ctx, duts); err != nil {
		t.Fatal(err)
	}
	got, err := getDroneDUTs(ctx, "earthes")
	if err != nil {
		t.Fatal(err)
	}
	want := []*entities.DUT{
		{ID: "ionasal", AssignedDrone: "earthes"},
		{ID: "nayaflask", AssignedDrone: "earthes"},
		{ID: "nei", AssignedDrone: "earthes", Draining: true},
	}
	applyGroup(ctx, want)
	assertSameDUTs(t, want, got)
}

func TestGetUnassignedDUTs(t *testing.T) {
	t.Parallel()
	t.Run("n is larger than total", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		duts := []*entities.DUT{
			{ID: "ionasal"},
			{ID: "nayaflask"},
			{ID: "casty"},
			{ID: "shurelia"},
		}
		applyGroup(ctx, duts)
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		got, err := getUnassignedDUTs(ctx, 10)
		if err != nil {
			t.Fatal(err)
		}
		want := []*entities.DUT{
			{ID: "ionasal"},
			{ID: "nayaflask"},
			{ID: "casty"},
			{ID: "shurelia"},
		}
		applyGroup(ctx, want)
		assertSameDUTs(t, want, got)
	})
	t.Run("n is smaller than total", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		duts := []*entities.DUT{
			{ID: "ionasal"},
			{ID: "nayaflask"},
			{ID: "casty"},
			{ID: "shurelia"},
		}
		applyGroup(ctx, duts)
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		got, err := getUnassignedDUTs(ctx, 3)
		if err != nil {
			t.Fatal(err)
		}
		assertSubsetDUTs(t, duts, got)
	})
	t.Run("zero n", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		duts := []*entities.DUT{
			{ID: "ionasal"},
			{ID: "nayaflask"},
		}
		applyGroup(ctx, duts)
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		got, err := getUnassignedDUTs(ctx, 0)
		if err != nil {
			t.Fatal(err)
		}
		if len(got) != 0 {
			t.Errorf("Expected no DUTs, got %s", entities.FormatDUTs(got))
		}
	})
	t.Run("negative n", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		duts := []*entities.DUT{
			{ID: "ionasal"},
			{ID: "nayaflask"},
		}
		applyGroup(ctx, duts)
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		got, err := getUnassignedDUTs(ctx, -1)
		if err != nil {
			t.Fatal(err)
		}
		if len(got) != 0 {
			t.Errorf("Expected no DUTs, got %s", entities.FormatDUTs(got))
		}
	})
	t.Run("ignore draining DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		duts := []*entities.DUT{
			{ID: "ionasal"},
			{ID: "nayaflask"},
			{ID: "nei", Draining: true},
			{ID: "casty"},
			{ID: "shurelia"},
		}
		applyGroup(ctx, duts)
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		got, err := getUnassignedDUTs(ctx, 10)
		if err != nil {
			t.Fatal(err)
		}
		want := []*entities.DUT{
			{ID: "ionasal"},
			{ID: "nayaflask"},
			{ID: "casty"},
			{ID: "shurelia"},
		}
		applyGroup(ctx, want)
		assertSameDUTs(t, want, got)
	})
	t.Run("ignore assigned DUTs", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("go-test")
		datastore.GetTestable(ctx).Consistent(true)
		duts := []*entities.DUT{
			{ID: "ionasal", AssignedDrone: "earthes"},
			{ID: "nayaflask"},
		}
		applyGroup(ctx, duts)
		if err := datastore.Put(ctx, duts); err != nil {
			t.Fatal(err)
		}
		got, err := getUnassignedDUTs(ctx, 1)
		if err != nil {
			t.Fatal(err)
		}
		want := []*entities.DUT{
			{ID: "nayaflask"},
		}
		applyGroup(ctx, want)
		assertSameDUTs(t, want, got)
	})
}

func TestAssignNewDUTs(t *testing.T) {
	t.Parallel()
	type loadIndicators = api.ReportDroneRequest_LoadIndicators
	cases := []struct {
		desc    string
		initial []*entities.DUT
		li      loadIndicators
		want    []*entities.DUT
	}{
		{
			desc: "assign some DUTs to drone without DUTs",
			initial: []*entities.DUT{
				{ID: "ionasal"},
				{ID: "nayaflask"},
			},
			li: loadIndicators{DutCapacity: 2},
			want: []*entities.DUT{
				{ID: "ionasal", AssignedDrone: "earthes"},
				{ID: "nayaflask", AssignedDrone: "earthes"},
			},
		},
		{
			desc: "don't assign draining DUTs",
			initial: []*entities.DUT{
				{ID: "ionasal"},
				{ID: "nei", Draining: true},
			},
			li: loadIndicators{DutCapacity: 2},
			want: []*entities.DUT{
				{ID: "ionasal", AssignedDrone: "earthes"},
			},
		},
		{
			desc: "assign to drone with DUTs",
			initial: []*entities.DUT{
				{ID: "ionasal", AssignedDrone: "earthes"},
				{ID: "nei"},
			},
			li: loadIndicators{DutCapacity: 2},
			want: []*entities.DUT{
				{ID: "ionasal", AssignedDrone: "earthes"},
				{ID: "nei", AssignedDrone: "earthes"},
			},
		},
		{
			desc: "don't assign to overloaded drone",
			initial: []*entities.DUT{
				{ID: "ionasal", AssignedDrone: "earthes"},
				{ID: "nei", AssignedDrone: "earthes"},
				{ID: "casty"},
			},
			li: loadIndicators{DutCapacity: 1},
			want: []*entities.DUT{
				{ID: "ionasal", AssignedDrone: "earthes"},
				{ID: "nei", AssignedDrone: "earthes"},
			},
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			ctx := gaetesting.TestingContextWithAppID("go-test")
			datastore.GetTestable(ctx).Consistent(true)
			ctx = testlogger.Use(ctx, t)
			applyGroup(ctx, c.initial)
			if err := datastore.Put(ctx, c.initial); err != nil {
				t.Fatal(err)
			}
			var got []*entities.DUT
			f := func(ctx context.Context) error {
				var err error
				got, err = AssignNewDUTs(ctx, "earthes", &c.li)
				return err
			}
			if err := datastore.RunInTransaction(ctx, f, nil); err != nil {
				t.Fatal(err)
			}
			applyGroup(ctx, c.want)
			t.Run("returned DUTs", func(t *testing.T) {
				assertSameDUTs(t, c.want, got)
			})
			t.Run("DUTs in datastore", func(t *testing.T) {
				q := datastore.NewQuery(entities.DUTKind).Eq(entities.AssignedDroneField, "earthes")
				var duts []*entities.DUT
				if err := datastore.GetAll(ctx, q, &duts); err != nil {
					t.Fatal(err)
				}
				assertSameDUTs(t, c.want, got)
			})
		})
	}
}

func TestFreeInvalidDUTs(t *testing.T) {
	t.Parallel()
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	dr := []*entities.Drone{
		{ID: "shurelia", Expiration: now.Add(-time.Minute)},
		{ID: "harvestasha", Expiration: now.Add(time.Minute)},
	}
	cases := []struct {
		desc string
		dut  entities.DUT
		want entities.DUT
	}{
		{
			desc: "unassigned DUT",
			dut:  entities.DUT{ID: "jakuri"},
			want: entities.DUT{ID: "jakuri"},
		},
		{
			desc: "DUT assigned to expired drone",
			dut:  entities.DUT{ID: "jakuri", AssignedDrone: "shurelia"},
			want: entities.DUT{ID: "jakuri"},
		},
		{
			desc: "DUT assigned to valid drone",
			dut:  entities.DUT{ID: "jakuri", AssignedDrone: "harvestasha"},
			want: entities.DUT{ID: "jakuri", AssignedDrone: "harvestasha"},
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			ctx := gaetesting.TestingContextWithAppID("go-test")
			datastore.GetTestable(ctx).Consistent(true)
			if err := datastore.Put(ctx, dr); err != nil {
				t.Fatal(err)
			}
			dut := c.dut
			dut.Group = entities.DUTGroupKey(ctx)
			if err := datastore.Put(ctx, &dut); err != nil {
				t.Fatal(err)
			}
			if err := FreeInvalidDUTs(ctx, now); err != nil {
				t.Fatal(err)
			}
			if err := datastore.Get(ctx, &dut); err != nil {
				t.Fatal(err)
			}
			want := c.want
			want.Group = entities.DUTGroupKey(ctx)
			if diff := cmp.Diff(want, dut); diff != "" {
				t.Errorf("Unexpected DUT (-want +got):\n%s", diff)
			}
		})
	}
}

func TestGetValidDrones(t *testing.T) {
	t.Parallel()
	ctx := gaetesting.TestingContextWithAppID("go-test")
	datastore.GetTestable(ctx).Consistent(true)
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	d := []*entities.Drone{
		{ID: "shurelia", Expiration: now.Add(-time.Minute)},
		{ID: "harvestasha", Expiration: now.Add(time.Minute)},
	}
	if err := datastore.Put(ctx, d); err != nil {
		t.Fatal(err)
	}

	got, err := getValidDrones(ctx, now)
	if err != nil {
		t.Fatal(err)
	}
	want := map[entities.DroneID]bool{
		"harvestasha": true,
	}
	if diff := cmp.Diff(want, got); diff != "" {
		t.Errorf("map mismatch (-want +got):\n%s", diff)
	}
}

func TestPruneExpiredDrones(t *testing.T) {
	t.Parallel()
	ctx := gaetesting.TestingContextWithAppID("go-test")
	datastore.GetTestable(ctx).Consistent(true)
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	d := []*entities.Drone{
		{ID: "shurelia", Expiration: now.Add(-time.Minute)},
		{ID: "jakuri", Expiration: now},
		{ID: "harvestasha", Expiration: now.Add(time.Minute)},
	}
	if err := datastore.Put(ctx, d); err != nil {
		t.Fatal(err)
	}
	if err := PruneExpiredDrones(ctx, now); err != nil {
		t.Fatal(err)
	}
	d = nil
	if err := datastore.GetAll(ctx, datastore.NewQuery(entities.DroneKind), &d); err != nil {
		t.Fatal(err)
	}
	want := []*entities.Drone{
		{ID: "harvestasha", Expiration: now.Add(time.Minute)},
	}
	assertSameDrones(t, want, d)
}

func TestPruneDrainedDUTs(t *testing.T) {
	t.Parallel()
	cases := []struct {
		desc    string
		initial []*entities.DUT
		want    []*entities.DUT
	}{
		{
			desc:    "prune draining and unassigned",
			initial: []*entities.DUT{{ID: "ionasal", Draining: true}},
			want:    nil,
		},
		{
			desc:    "ignore draining and assigned",
			initial: []*entities.DUT{{ID: "ionasal", Draining: true, AssignedDrone: "earthes"}},
			want:    []*entities.DUT{{ID: "ionasal", Draining: true, AssignedDrone: "earthes"}},
		},
		{
			desc:    "ignore not draining and unassigned",
			initial: []*entities.DUT{{ID: "ionasal"}},
			want:    []*entities.DUT{{ID: "ionasal"}},
		},
		{
			desc:    "ignore not draining and assigned",
			initial: []*entities.DUT{{ID: "ionasal", AssignedDrone: "earthes"}},
			want:    []*entities.DUT{{ID: "ionasal", AssignedDrone: "earthes"}},
		},
	}
	for _, c := range cases {
		c := c
		t.Run(c.desc, func(t *testing.T) {
			t.Parallel()
			ctx := gaetesting.TestingContextWithAppID("go-test")
			datastore.GetTestable(ctx).Consistent(true)
			applyGroup(ctx, c.initial)
			if err := datastore.Put(ctx, c.initial); err != nil {
				t.Fatal(err)
			}
			if err := PruneDrainedDUTs(ctx); err != nil {
				t.Fatal(err)
			}
			var duts []*entities.DUT
			q := datastore.NewQuery(entities.DUTKind)
			q = q.Ancestor(entities.DUTGroupKey(ctx))
			if err := datastore.GetAll(ctx, q, &duts); err != nil {
				t.Fatal(err)
			}
			applyGroup(ctx, c.want)
			assertSameDUTs(t, c.want, duts)
		})
	}
}

func applyGroup(ctx context.Context, d []*entities.DUT) {
	k := entities.DUTGroupKey(ctx)
	for _, d := range d {
		d.Group = k
	}
}

func assertSubsetDUTs(t *testing.T, all, got []*entities.DUT) {
	t.Helper()
	duts := make(map[entities.DUTID]*entities.DUT)
	for _, d := range all {
		duts[d.ID] = d
	}
	for _, d := range got {
		if !d.Equal(*duts[d.ID]) {
			t.Errorf("Got DUT %v not in expected set %v", d, entities.FormatDUTs(all))
		}
	}
}

func assertSameDrones(t *testing.T, want, got []*entities.Drone) {
	t.Helper()
	sortDrones(want)
	sortDrones(got)
	if diff := cmp.Diff(want, got); diff != "" {
		t.Errorf("Unexpected DUTs (-want +got):\n%s", diff)
	}
}

func sortDrones(d []*entities.Drone) {
	sort.Slice(d, func(i, j int) bool { return d[i].ID < d[j].ID })
}

func assertSameDUTs(t *testing.T, want, got []*entities.DUT) {
	t.Helper()
	sortDUTs(want)
	sortDUTs(got)
	if diff := cmp.Diff(want, got); diff != "" {
		t.Errorf("Unexpected DUTs (-want +got):\n%s", diff)
	}
}

func sortDUTs(d []*entities.DUT) {
	sort.Slice(d, func(i, j int) bool { return d[i].ID < d[j].ID })
}
