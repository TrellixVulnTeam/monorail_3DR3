package handlers

import (
	"context"
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"go.chromium.org/gae/service/mail"
	"go.chromium.org/luci/server/router"
)

func TestJobEventUpdate(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		cfgs       []*rotang.Configuration
		time       time.Time
		memberPool []rotang.Member
	}{{
		name: "Canceled context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "No configurations",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name:             "Test Rota",
					Enabled:          true,
					Expiration:       2,
					ShiftsToSchedule: 2,
					Shifts: rotang.ShiftConfig{
						StartTime:    midnight,
						Length:       5,
						Skip:         2,
						Generator:    "Fair",
						ShiftMembers: 1,
						Shifts: []rotang.Shift{
							{
								Name:     "MTV All Day",
								Duration: fullDay,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
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
			for _, cfg := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}

			h.JobEventUpdate(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: JobEventUpdate(ctx) = %d want: %d", tst.name, recorder.Code, http.StatusOK)
			}
		})
	}
}

func TestEventUpdate(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		changeID   bool
		ctx        *router.Context
		cfg        *rotang.Configuration
		time       time.Time
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		events     []rotang.ShiftEntry
		want       []rotang.ShiftEntry
		email      []mail.Message
	}{{
		name: "Config not enabled",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:       "Test Rota",
				Enabled:    false,
				Expiration: 4,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(-weekDuration),
				EndTime:   midnight.Add(-weekDuration + 5*fullDay),
				EvtID:     "before 1",
			}, {
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "before 2",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(-weekDuration),
				EndTime:   midnight.Add(-weekDuration + 5*fullDay),
				EvtID:     "before 1",
			}, {
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "before 2",
			},
		},
	}, {
		name: "No shifts in config",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
	}, {
		name: "Don't consider already ended shifts",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       1,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(-weekDuration),
				EndTime:   midnight.Add(-weekDuration + 5*fullDay),
				EvtID:     "before 1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "before 2",
			},
		},
		events: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(-weekDuration),
				EndTime:   midnight.Add(-weekDuration + 5*fullDay),
				EvtID:     "before 1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "before 2",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(-weekDuration),
				EndTime:   midnight.Add(-weekDuration + 5*fullDay),
				EvtID:     "before 1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "before 2",
			},
		},
	}, {
		name: "Success update shifts",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "Before1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
				EvtID:     "Before2",
			},
		},
		events: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "Before1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
				EvtID:     "Before2",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "Before1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
				EvtID:     "Before2",
			},
		},
	}, {
		name:     "Success update changed shifts",
		changeID: true,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Owners:           []string{"owner1@owner.com", "owner2@owner.com"},
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller3@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller4@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller5@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller6@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
			{
				Email: "oncaller3@oncall.com",
			},
			{
				Email: "oncaller4@oncall.com",
			},
			{
				Email: "oncaller5@oncall.com",
			},
			{
				Email: "oncaller6@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "Before1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller3@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "oncaller4@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
				EvtID:     "Before2",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller5@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "oncaller6@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
				EvtID:     "Before3",
			},
		},
		events: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "Before1",
			},
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller4@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
				EvtID:     "Before2",
			}, {
				Name:      "MTV All Day",
				OnCall:    []rotang.ShiftMember{},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
				EvtID:     "Before3",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "0",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller4@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
				EvtID:     "1",
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
				EvtID:     "2",
			},
		},
		email: []mail.Message{
			{
				Sender:  "admin@example.com",
				To:      []string{"oncaller2@oncall.com"},
				Subject: "TestSubject",
				Body:    "TestBody",
			}, {
				Sender:  "admin@example.com",
				To:      []string{"owner1@owner.com", "owner2@owner.com"},
				Subject: "TestSubject",
				Body:    "TestBody",
			}, {
				Sender:  "admin@example.com",
				To:      []string{"oncaller3@oncall.com"},
				Subject: "TestSubject",
				Body:    "TestBody",
			}, {
				Sender:  "admin@example.com",
				To:      []string{"owner1@owner.com", "owner2@owner.com"},
				Subject: "TestSubject",
				Body:    "TestBody",
			}, {
				Sender:  "admin@example.com",
				To:      []string{"oncaller5@oncall.com", "oncaller6@oncall.com"},
				Subject: "TestSubject",
				Body:    "TestBody",
			}, {
				Sender:  "admin@example.com",
				To:      []string{"owner1@owner.com", "owner2@owner.com"},
				Subject: "TestSubject",
				Body:    "TestBody",
			},
		},
	}, {
		name:     "Split shifts",
		changeID: true,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 8 * time.Hour,
						}, {
							Name:     "SYD Shift",
							Duration: 8 * time.Hour,
						}, {
							Name:     "EU Shift",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv1@oncall.com",
					ShiftName: "MTV Shift",
				}, {
					Email:     "mtv2@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd1@oncall.com",
					ShiftName: "SYD Shift",
				}, {
					Email:     "syd2@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "eu1@oncall.com",
					ShiftName: "EU Shift",
				}, {
					Email:     "eu2@oncall.com",
					ShiftName: "EU Shift",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "syd1@oncall.com",
			},
			{
				Email: "syd2@oncall.com",
			},
			{
				Email: "eu1@oncall.com",
			},
			{
				Email: "eu2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour),
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd1@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour),
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu1@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16 * time.Hour),
				EndTime:   midnight.Add(5 * fullDay),
			},
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour + weekDuration),
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd2@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8*time.Hour + weekDuration),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour + weekDuration),
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu2@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16*time.Hour + weekDuration),
				EndTime:   midnight.Add(5*fullDay + weekDuration),
			},
		},
		events: []rotang.ShiftEntry{
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour),
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd1@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour),
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu1@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16 * time.Hour),
				EndTime:   midnight.Add(5 * fullDay),
			},
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour + weekDuration),
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd2@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8*time.Hour + weekDuration),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour + weekDuration),
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu2@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16*time.Hour + weekDuration),
				EndTime:   midnight.Add(5*fullDay + weekDuration),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour),
				EvtID:     "0",
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd1@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour),
				EvtID:     "1",
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu1@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16 * time.Hour),
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "2",
			},
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour + weekDuration),
				EvtID:     "3",
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd2@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8*time.Hour + weekDuration),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour + weekDuration),
				EvtID:     "4",
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu2@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16*time.Hour + weekDuration),
				EndTime:   midnight.Add(5*fullDay + weekDuration),
				EvtID:     "5",
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
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.cfg.Config.Name)

			if err := h.shiftStore(ctx).AddShifts(ctx, tst.cfg.Config.Name, tst.shifts); err != nil {
				t.Fatalf("%s: AddShifts(ctx, _) failed: %v", tst.name, err)
			}

			h.calendar.(*fakeCal).events = make(map[time.Time]rotang.ShiftEntry)
			for i := range tst.events {
				sp := tst.events[i]
				h.calendar.(*fakeCal).events[sp.StartTime] = sp
			}
			defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.cfg.Config.Name)

			h.calendar.(*fakeCal).Set(nil, false, tst.changeID, 0)

			testMail := mail.GetTestable(tst.ctx.Context)
			testMail.Reset()

			err := h.eventUpdate(tst.ctx, tst.cfg, midnight)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: eventUpdate(ctx, _, %v) = %t want: %t, err: %v", tst.name, midnight, got, want, err)
			}
			if err != nil {
				return
			}

			got, err := h.shiftStore(ctx).AllShifts(ctx, tst.cfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: AllShifts(ctx, %q) failed: %v", tst.name, tst.cfg.Config.Name, err)
			}

			if diff := prettyConfig.Compare(tst.want, got); diff != "" {
				t.Fatalf("%s: scheduleShifts(ctx, _, %v) differ -want +got, %s", tst.name, midnight, diff)
			}

			var gotMsg []mail.Message
			for _, m := range testMail.SentMessages() {
				gotMsg = append(gotMsg, m.Message)
			}

			if diff := prettyConfig.Compare(tst.email, gotMsg); diff != "" {
				t.Fatalf("%s: JobEventUpdate(ctx) differ -want =got, \n%s", tst.name, diff)
			}
		})
	}
}
