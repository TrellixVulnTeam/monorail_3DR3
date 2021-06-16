package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
)

func TestHandleMember(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		email      string
		memberPool []rotang.Member
	}{{
		name: "Canceled context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/memberjson", nil),
		},
	}, {
		name: "Not logged in",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/memberjson", nil),
		},
	}, {
		name: "Member does not exist",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/memberjson", nil),
		},
		email: "test@user.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "not-test@user.com",
			},
		},
	}, {
		name: "Method not supported",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("UPDATE", "/memberjson", nil),
		},
		email: "test@user.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
			},
		},
	}, {
		name: "POST fail",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/memberjson", nil),
		},
		email: "test@user.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
			},
		},
	}, {
		name: "GET fail",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/memberjson", nil),
		},
		email: "test@user.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
			},
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}

			if tst.email != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.email),
				})
			}

			h.HandleMember(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleMember(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
		})
	}

}

func TestMemberGET(t *testing.T) {
	ctx := newTestContext()

	ausLoc, err := time.LoadLocation("Australia/Sydney")
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", "Australia/Sydney", err)
	}

	tests := []struct {
		name       string
		isAdmin    bool
		fail       bool
		ctx        *router.Context
		rota       string
		member     *rotang.Member
		memberPool []rotang.Member
		cfgs       []rotang.Configuration
		shifts     []rotang.ShiftEntry
		want       MemberInfo
	}{{
		name:    "Success",
		isAdmin: false,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/memberjson", nil),
		},
		rota: "Test Rota",
		member: &rotang.Member{
			Name:  "Test Member",
			Email: "test@member.com",
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Member",
				Email: "test@member.com",
			},
		},
		cfgs: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Shifts: []rotang.Shift{
							{
								Name:     "Test All Day",
								Duration: fullDay,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "test@member.com",
						ShiftName: "Test All Day",
					},
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "Test All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "test@member.com",
						ShiftName: "Test All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(72 * time.Hour),
			},
		},
		want: MemberInfo{
			Member: JSONMember{
				Member: rotang.Member{
					Name:  "Test Member",
					Email: "test@member.com",
				},
			},
			Shifts: []RotaShift{
				{
					Name: "Test Rota",
					Entries: []rotang.ShiftEntry{
						{
							Name: "Test All Day",
							OnCall: []rotang.ShiftMember{
								{
									Email:     "test@member.com",
									ShiftName: "Test All Day",
								},
							},
							StartTime: midnight,
							EndTime:   midnight.Add(72 * time.Hour),
						},
					},
				},
			},
		},
	}, {
		name:    "No shifts",
		isAdmin: false,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/memberjson", nil),
		},
		rota: "Test Rota",
		member: &rotang.Member{
			Name:  "Test Member",
			Email: "test@member.com",
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Member",
				Email: "test@member.com",
			},
		},
		cfgs: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Shifts: []rotang.Shift{
							{
								Name:     "Test All Day",
								Duration: fullDay,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "test@member.com",
						ShiftName: "Test All Day",
					},
				},
			},
		},
		want: MemberInfo{
			Member: JSONMember{
				Member: rotang.Member{
					Name:  "Test Member",
					Email: "test@member.com",
				},
			},
		},
	}, {
		name:    "Member with TZ info",
		isAdmin: false,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/memberjson", nil),
		},
		rota: "Test Rota",
		member: &rotang.Member{
			Name:  "Test Member",
			Email: "test@member.com",
			TZ:    *ausLoc,
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Member",
				Email: "test@member.com",
			},
		},
		cfgs: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name: "Test Rota",
					Shifts: rotang.ShiftConfig{
						Shifts: []rotang.Shift{
							{
								Name:     "Test All Day",
								Duration: fullDay,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "test@member.com",
						ShiftName: "Test All Day",
					},
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "Test All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "test@member.com",
						ShiftName: "Test All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(72 * time.Hour),
			},
		},
		want: MemberInfo{
			Member: JSONMember{
				Member: rotang.Member{
					Name:  "Test Member",
					Email: "test@member.com",
				},
				TZString: "Australia/Sydney",
			},
			Shifts: []RotaShift{
				{
					Name: "Test Rota",
					Entries: []rotang.ShiftEntry{
						{
							Name: "Test All Day",
							OnCall: []rotang.ShiftMember{
								{
									Email:     "test@member.com",
									ShiftName: "Test All Day",
								},
							},
							StartTime: midnight,
							EndTime:   midnight.Add(72 * time.Hour),
						},
					},
				},
			},
		},
	},
		{
			name:    "Admin user",
			isAdmin: true,
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: httptest.NewRequest("GET", "/memberjson?email=user@example.com", nil),
			},
			rota: "Test Rota",
			member: &rotang.Member{
				Name:  "Test Member",
				Email: "test@member.com",
			},
			memberPool: []rotang.Member{
				{
					Name:  "Example user",
					Email: "user@example.com",
				},
				{
					Name:  "Test Member",
					Email: "test@member.com",
				},
			},
			cfgs: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "Test Rota",
						Shifts: rotang.ShiftConfig{
							Shifts: []rotang.Shift{
								{
									Name:     "Test All Day",
									Duration: fullDay,
								},
							},
						},
					},
					Members: []rotang.ShiftMember{
						{
							Email:     "user@example.com",
							ShiftName: "Test All Day",
						},
					},
				},
			},
			shifts: []rotang.ShiftEntry{
				{
					Name: "Test All Day",
					OnCall: []rotang.ShiftMember{
						{
							Email:     "user@example.com",
							ShiftName: "Test All Day",
						},
					},
					StartTime: midnight,
					EndTime:   midnight.Add(72 * time.Hour),
				},
			},
			want: MemberInfo{
				Member: JSONMember{
					Member: rotang.Member{
						Name:  "Example user",
						Email: "user@example.com",
					},
					TZString: "UTC",
				},
				Shifts: []RotaShift{
					{
						Name: "Test Rota",
						Entries: []rotang.ShiftEntry{
							{
								Name: "Test All Day",
								OnCall: []rotang.ShiftMember{
									{
										Email:     "user@example.com",
										ShiftName: "Test All Day",
									},
								},
								StartTime: midnight,
								EndTime:   midnight.Add(72 * time.Hour),
							},
						},
					},
				},
			},
		}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			setAdminForTest(tst.isAdmin)
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, cfg := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			if err := h.shiftStore(ctx).AddShifts(ctx, tst.rota, tst.shifts); err != nil {
				t.Fatalf("%s: AddShifts(ctx, %q, _) failed: %v", tst.name, tst.rota, err)
			}
			defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.rota)

			tst.ctx.Context = clock.Set(tst.ctx.Context, testclock.New(midnight))

			err := h.memberGET(tst.ctx, tst.member)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)

			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: memberGet(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}

			var got MemberInfo
			if err := json.NewDecoder(recorder.Body).Decode(&got); err != nil {
				t.Fatalf("%s: Decode() failed: %v", tst.name, err)
			}
			if diff := prettyConfig.Compare(tst.want, got); diff != "" {
				t.Fatalf("%s: memberGet(ctx, _) differ -want +got, \n%s", tst.name, diff)
			}
		})
	}
}

func TestMemberPOST(t *testing.T) {
	ctx := newTestContext()

	testTime, err := time.Parse(time.RFC3339, "2018-11-06T08:00:00Z")
	if err != nil {
		t.Fatalf("time.Parse() failed: %v", err)
	}

	limaLoc, err := time.LoadLocation("America/Lima")
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", "Australia/Sydney", err)
	}

	tests := []struct {
		name       string
		isAdmin    bool
		fail       bool
		ctx        *router.Context
		member     *JSONMember
		want       *rotang.Member
		memberPool []rotang.Member
	}{{
		name:    "Success",
		isAdmin: false,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/memberjson", bytes.NewBufferString(`
				{ "full_name":"Test Testson",
					"email_address":"test@user.com",
					"TZ":{},
					"OOO":[{
						"Start":"2018-11-06T08:00:00Z",
						"Duration":259200000000000,
						"Comment":"Off to the circus"
					}],
					"Preferences":null
				}`)),
		},
		member: &JSONMember{
			Member: rotang.Member{
				Name:  "Test Testson",
				Email: "test@user.com",
				OOO: []rotang.OOO{{
					Start:    midnight,
					Duration: time.Hour * 72,
					Comment:  "Out and about",
				},
				},
			},
		},
		want: &rotang.Member{
			Name:  "Test Testson",
			Email: "test@user.com",
			TZ:    *time.UTC,
			OOO: []rotang.OOO{{
				Start:    testTime,
				Duration: time.Hour * 72,
				Comment:  "Off to the circus",
			},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
			},
		},
	}, {
		name:    "Changing other member",
		isAdmin: false,
		fail:    true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/memberjson", bytes.NewBufferString(`
				{ "full_name":"Test Testson",
					"email_address":"test2@user.com",
					"TZ":{},
					"OOO":[{
						"Start":"2018-11-06T08:00:00Z",
						"Duration":259200000000000,
						"Comment":"Off to the circus"
					}],
					"Preferences":null
				}`)),
		},
		member: &JSONMember{
			Member: rotang.Member{
				Name:  "Test Testson",
				Email: "test@user.com",
				OOO: []rotang.OOO{{
					Start:    midnight,
					Duration: time.Hour * 72,
					Comment:  "Out and about",
				},
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
			},
			{
				Name:  "Test Testson",
				Email: "test2@user.com",
			},
		},
	}, {
		name:    "Admin changing user TZ",
		isAdmin: true,
		fail:    false,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/memberjson", bytes.NewBufferString(`
				{ "full_name":"Test Testson",
					"email_address":"user@user.com",
					"TZString":"America/Lima",
					"Preferences":null
				}`)),
		},
		member: &JSONMember{
			Member: rotang.Member{
				Name:  "Test Testson",
				Email: "admin@user.com",
				OOO: []rotang.OOO{{
					Start:    midnight,
					Duration: time.Hour * 72,
					Comment:  "Out and about",
				},
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "admin@user.com",
			},
			{
				Name:  "Test Testson",
				Email: "user@user.com",
			},
		},
		want: &rotang.Member{
			Name:  "Test Testson",
			Email: "user@user.com",
			TZ:    *limaLoc,
		},
	}, {
		name:    "Broken JSON",
		isAdmin: false,
		fail:    true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/memberjson", bytes.NewBufferString(`
				{ "full_name":"Test Testson",
					"email_address":"test@user.com",
					"TZ":{},
					"OOO":[{
						"Start":"2018-11-06T08:00:00Z",
						"Duration":259200000000000,
						"Comment":"Off to the circus"
					}],
					"Preferences":null,
				}`)),
		},
		member: &JSONMember{
			Member: rotang.Member{
				Name:  "Test Testson",
				Email: "test@user.com",
				OOO: []rotang.OOO{{
					Start:    midnight,
					Duration: time.Hour * 72,
					Comment:  "Out and about",
				},
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
			},
		},
	}, {
		name:    "Comment missing",
		isAdmin: false,
		fail:    true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/memberjson", bytes.NewBufferString(`
				{ "full_name":"Test Testson",
					"email_address":"test@user.com",
					"TZ":{},
					"OOO":[{
						"Start":"2018-11-06T08:00:00Z",
						"Duration":259200000000000
					}],
					"Preferences":null
				}`)),
		},
		member: &JSONMember{
			Member: rotang.Member{
				Name:  "Test Testson",
				Email: "test@user.com",
				OOO: []rotang.OOO{{
					Start:    midnight,
					Duration: time.Hour * 72,
					Comment:  "Out and about",
				},
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
			},
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			setAdminForTest(tst.isAdmin)
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			err := h.memberPOST(tst.ctx, tst.member)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: h.memberPOST(ctx, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}

			var jsonMember JSONMember
			if err := json.NewDecoder(tst.ctx.Request.Body).Decode(&jsonMember); err != nil {
				return
			}

			member, err := h.memberStore(ctx).Member(ctx, jsonMember.Email)
			if err != nil {
				t.Fatalf("%s: Member(ctx, %q) failed: %v", tst.name, jsonMember.Email, err)
			}
			if diff := prettyConfig.Compare(tst.want, member); diff != "" {
				t.Fatalf("%s: h.memberPOST(ctx, _) differ -want +got, \n%s", tst.name, diff)
			}
		})
	}
}
