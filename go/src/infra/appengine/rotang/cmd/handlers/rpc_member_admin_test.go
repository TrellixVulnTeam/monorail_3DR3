package handlers

import (
	"context"
	"infra/appengine/rotang"
	"sort"
	"testing"
	"time"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"

	apb "infra/appengine/rotang/proto/rotangapi"
)

func TestRPCAllMembersOwners(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		in      string
		cfgs    []*rotang.Configuration
		user    string
		rota    string
		members []rotang.Member
		want    []string
	}{{
		name: "Success",
		in: `
			name: "Test Rota",
		`,
		ctx:  ctx,
		user: "owner@owner.com",
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name:   "Test Rota",
					Owners: []string{"another@owner.com", "owner@owner.com"},
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			},
		},
		want: []string{"owner@owner.com", "mtv1@oncall.com", "mtv2@oncall.com"},
	}, {
		name: "No rotation name",
		ctx:  ctx,
		fail: true,
	}, {
		name: "Rotation not found",
		ctx:  ctx,
		fail: true,
		in: `
			name: "Not exist",
		`,
	}, {
		name: "Not owner",
		ctx:  ctx,
		user: "not_owner@owner.com",
		fail: true,
		in: `
			name: "Test Rota",
		`,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name:   "Test Rota",
					Owners: []string{"owner@owner.com"},
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			},
		},
	}, {
		name: "No members",
		ctx:  ctx,
		user: "owner@owner.com",
		in: `
			name: "Test Rota",
		`,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name:   "Test Rota",
					Owners: []string{"owner@owner.com"},
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
			},
		},
		want: []string{"owner@owner.com"},
	}, {
		name: "Owner in list only once",
		in: `
			name: "Test Rota",
		`,
		ctx:  ctx,
		user: "owner@owner.com",
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name:   "Test Rota",
					Owners: []string{"owner@owner.com"},
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "owner@owner.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "owner@owner.com",
				Name:  "Le Owner",
				TZ:    *time.UTC,
			},
		},
		want: []string{"owner@owner.com", "mtv1@oncall.com", "mtv2@oncall.com"},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.members {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, c := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, c); err != nil {
					t.Fatalf("%s: CreateRotaconfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
			}

			var inPB apb.MakeAllMembersOwnersRequest
			if err := proto.UnmarshalText(tst.in, &inPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			if tst.user != "" {
				tst.ctx = auth.WithState(tst.ctx, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			_, err := h.MakeAllMembersOwners(tst.ctx, &inPB)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.AllMembersOwners(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}

			if err != nil {
				return
			}

			cfg, err := h.configStore(ctx).RotaConfig(ctx, tst.rota)
			if err != nil {
				t.Fatalf("%s: RotaConfig(ctx, %q) failed: %v", tst.name, tst.rota, err)
			}

			sort.Strings(cfg[0].Config.Owners)
			sort.Strings(tst.want)

			if diff := prettyConfigIgnoreUnexported.Compare(tst.want, cfg[0].Config.Owners); diff != "" {
				t.Fatalf("%s: MakeAllMembersOwners(ctx, %q) differ -want +got: %s", tst.name, tst.rota, diff)
			}
		})
	}
}

func TestRPCRotationMembers(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name    string
		fail    bool
		ctx     context.Context
		in      string
		cfgs    []*rotang.Configuration
		members []rotang.Member
		shifts  []rotang.ShiftEntry
		want    string
	}{{
		name: "Success",
		in: `
			name: "Test Rota"
		`,
		ctx: ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
				OOO: []rotang.OOO{
					{
						Start:    midnight.Add(12 * fullDay),
						Duration: 2 * fullDay,
						Comment:  "Test comment",
					},
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(-1 * fullDay),
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		want: `
			rotation: "Test Rota"
			members: <
				member: <
					email: "mtv1@oncall.com"
					name: "Mtv1 Mtvsson"
					tz: "UTC"
				>
				oncall_shifts: <
					name: "MTV All Day"
					oncallers: <
						email: "mtv1@oncall.com"
						name: "Mtv1 Mtvsson"
						tz: "UTC"
					>
					start: <
						seconds: 1143849600
					>
					end: <
						seconds: 1144022400
					>
				>
			>
			members: <
				member: <
					email: "mtv2@oncall.com"
					name: "Mtv2 Mtvsson"
					tz: "UTC"
				>
				ooo: <
					start: <
						seconds: 1144972800
					>
					end: <
						seconds: 1145145600
					>
					comment: "Test comment"
				>
			>
		`,
	}, {
		name: "No rota name",
		fail: true,
		ctx:  ctx,
	}, {
		name: "No shifts",
		in: `
			name: "Test Rota"
		`,
		ctx: ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		members: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
				Name:  "Mtv1 Mtvsson",
				TZ:    *time.UTC,
			}, {
				Email: "mtv2@oncall.com",
				Name:  "Mtv2 Mtvsson",
				TZ:    *time.UTC,
				OOO: []rotang.OOO{
					{
						Start:    midnight.Add(12 * fullDay),
						Duration: 2 * fullDay,
						Comment:  "Test comment",
					},
				},
			},
		},
		want: `
			rotation: "Test Rota"
			members: <
				member: <
					email: "mtv1@oncall.com"
					name: "Mtv1 Mtvsson"
					tz: "UTC"
				>
			>
			members: <
				member: <
					email: "mtv2@oncall.com"
					name: "Mtv2 Mtvsson"
					tz: "UTC"
				>
				ooo: <
					start: <
						seconds: 1144972800
					>
					end: <
						seconds: 1145145600
					>
					comment: "Test comment"
				>
			>
		`,
	}, {
		name: "No Members",
		in: `
			name: "Test Rota"
		`,
		ctx: ctx,
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name: "MTV All Day",
							},
						},
					},
				},
			},
		},
		want: `
			rotation: "Test Rota"
		`,
	}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.members {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, c := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, c); err != nil {
					t.Fatalf("%s: CreateRotaconfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
				if err := h.shiftStore(ctx).AddShifts(ctx, c.Config.Name, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, %q, _) failed: %v", tst.name, c.Config.Name, err)
				}
				defer h.shiftStore(ctx).DeleteAllShifts(ctx, c.Config.Name)
			}

			var inPB apb.RotationMembersRequest
			if err := proto.UnmarshalText(tst.in, &inPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			var wantPB apb.RotationMembersResponse
			if err := proto.UnmarshalText(tst.want, &wantPB); err != nil {
				t.Fatalf("%s: proto.UnmarshalText(_, _) failed: %v", tst.name, err)
			}

			res, err := h.RotationMembers(tst.ctx, &inPB)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.RotationMembers(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}

			if err != nil {
				return
			}

			if diff := prettyConfigIgnoreUnexported.Compare(wantPB, res); diff != "" {
				t.Fatalf("%s: h.RotationMembers(ctx, _) differ -want +got: %s", tst.name, diff)
			}
		})
	}
}
