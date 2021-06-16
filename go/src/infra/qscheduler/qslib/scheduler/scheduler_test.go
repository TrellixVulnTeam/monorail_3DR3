// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package scheduler

import (
	"context"
	"fmt"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
)

// TestReprioritize tests that the scheduler correctly changes the priority
// of running jobs (promote or demote) if the account balance makes that
// necessary.
func TestSchedulerReprioritize(t *testing.T) {
	// Prepare a situation in which one P0 job (out of 2 running) will be
	// demoted, and a separate P2 job will be promoted to P1.
	Convey("Given two running requests with different costs for an account that needs 1 demotion from P0, and supports 1 additional P1 job", t, func() {
		ctx := context.Background()
		tm0 := time.Unix(0, 0)
		s := New(tm0)
		aid := AccountID("a1")
		s.AddAccount(ctx, aid, NewAccountConfig(0, 0, []float32{1.1, 0.9}, false, ""), []float32{2 * DemoteThreshold, 2 * PromoteThreshold, 2 * PromoteThreshold})

		for _, i := range []int{1, 2} {
			rid := RequestID(fmt.Sprintf("r%d", i))
			wid := WorkerID(fmt.Sprintf("w%d", i))
			addRunningRequest(ctx, s, rid, wid, aid, 0, tm0)
		}
		s.state.workers["w2"].runningTask.cost = Balance{1, 0, 0}

		Convey("given both requests running at P0", func() {
			Convey("when scheduling", func() {
				s.RunOnce(ctx, NullEventSink)
				Convey("then the cheaper request should be demoted.", func() {
					So(s.state.workers["w1"].runningTask.priority, ShouldEqual, 1)
					So(s.state.workers["w2"].runningTask.priority, ShouldEqual, 0)
				})
			})
		})

		Convey("given both requests running at P2", func() {
			for _, wid := range []WorkerID{"w1", "w2"} {
				s.state.workers[wid].runningTask.priority = 2
			}
			Convey("when scheduling", func() {

				s.RunOnce(ctx, NullEventSink)
				Convey("then the more expensive should be promoted.", func() {
					So(s.state.workers["w1"].runningTask.priority, ShouldEqual, 2)
					So(s.state.workers["w2"].runningTask.priority, ShouldEqual, 1)
				})
			})
		})
	})
}

// TestPreempt tests that the scheduler correctly preempts lower priority jobs
// running on a worker, when a higher priority job appears to take its place.
func TestSchedulerPreempt(t *testing.T) {
	Convey("Given a state with two running P1 tasks", t, func() {
		ctx := context.Background()
		tm0 := time.Unix(0, 0)
		s := New(tm0)
		s.AddAccount(ctx, "a1", NewAccountConfig(0, 0, []float32{1, 1, 1}, false, ""), []float32{0.5 * PromoteThreshold, 1})
		for _, i := range []int{1, 2} {
			rid := RequestID(fmt.Sprintf("r%d", i))
			wid := WorkerID(fmt.Sprintf("w%d", i))
			s.AddRequest(ctx, NewTaskRequest(rid, "a1", nil, nil, tm0), tm0, nil, NullEventSink)
			s.MarkIdle(ctx, wid, stringset.New(0), tm0, NullEventSink)
			s.state.applyAssignment(&Assignment{RequestID: rid, WorkerID: wid, Type: AssignmentIdleWorker, Priority: 1})
		}
		s.state.workers["w1"].runningTask.cost = Balance{0, 1, 0}
		Convey("given a new P0 request from a different account", func() {
			s.AddAccount(ctx, "a2", NewAccountConfig(0, 0, nil, false, ""), nil)
			s.AddRequest(ctx, NewTaskRequest("r3", "a2", nil, nil, tm0), tm0, nil, NullEventSink)
			Convey("given sufficient balance", func() {
				s.state.balances["a2"] = Balance{1}
				Convey("when scheduling", func() {
					tm1 := time.Unix(1, 0)
					s.UpdateTime(ctx, tm1)
					got := s.RunOnce(ctx, NullEventSink)
					Convey("then the cheaper running job is preempted.", func() {
						want := &Assignment{Type: AssignmentPreemptWorker, Priority: 0, WorkerID: "w2", RequestID: "r3", TaskToAbort: "r2", Time: tm1}
						So(got, ShouldResemble, []*Assignment{want})
					})
				})
			})
			Convey("given insufficient balance", func() {
				Convey("when scheduling", func() {
					got := s.RunOnce(ctx, NullEventSink)
					Convey("then nothing happens.", func() {
						So(got, ShouldBeEmpty)
					})
				})
			})
		})

		Convey("given a new P0 request from the same account", func() {
			s.AddRequest(ctx, NewTaskRequest("r3", "a1", nil, nil, tm0), tm0, nil, NullEventSink)
			Convey("when scheduling", func() {
				got := s.RunOnce(ctx, NullEventSink)
				Convey("then nothing happens.", func() {
					So(got, ShouldBeEmpty)
				})
			})
		})
	})
}

// TestDisableFreeTasks tests that the DisableFreeTasks account config behaves
// as expected.
func TestDisableFreeTasks(t *testing.T) {
	Convey("Given a state", t, func() {
		ctx := context.Background()
		tm0 := time.Unix(0, 0)
		s := New(tm0)
		Convey("with an idle bot, and a task for an account", func() {
			aid := AccountID("a1")
			s.AddRequest(ctx, NewTaskRequest("rid", aid, nil, nil, tm0), tm0, nil, NullEventSink)
			s.MarkIdle(ctx, "worker", nil, tm0, NullEventSink)
			Convey("when free tasks are enabled", func() {
				config := NewAccountConfig(0, 0, nil, false, "")
				s.AddAccount(ctx, aid, config, nil)
				Convey("then when the scheduler runs, the task is assigned.", func() {
					assignments := s.RunOnce(ctx, NullEventSink)
					So(assignments, ShouldHaveLength, 1)
				})
			})
			Convey("when free tasks are disabled", func() {
				config := NewAccountConfig(0, 0, nil, true, "")
				s.AddAccount(ctx, aid, config, nil)
				Convey("then when the scheduler runs, no task is assigned.", func() {
					assignments := s.RunOnce(ctx, NullEventSink)
					So(assignments, ShouldHaveLength, 0)
				})
			})
		})
	})
}

// TestUpdateBalance tests that UpdateBalance makes the correct modifications
// to account balances and task run costs.
func TestUpdateBalance(t *testing.T) {
	t0 := time.Unix(0, 0)
	aID := AccountID("accountID")
	Convey("Given a scheduler with an added account config", t, func() {
		ctx := context.Background()
		s := New(t0)
		var maxTime float32 = 2.0
		s.AddAccount(ctx, aID, NewAccountConfig(0, maxTime, []float32{1, 2, 3}, false, ""), nil)

		Convey("then a zeroed balance for that account exists", func() {
			So(s.state.balances, ShouldContainKey, aID)
			So(s.state.balances[aID], ShouldResemble, Balance{})
		})

		Convey("when updating time forward", func() {
			t1 := t0.Add(time.Second)
			s.UpdateTime(ctx, t1)
			Convey("then account balance should be increased according to charge rate", func() {
				So(s.state.balances[aID], ShouldResemble, Balance{1, 2, 3})
			})
		})

		Convey("when updating time forward beyond the account's max charge time", func() {
			t1 := t0.Add(10 * time.Second)
			s.UpdateTime(ctx, t1)
			Convey("then account balance saturates at the maximum charge.", func() {
				So(s.state.balances[aID], ShouldResemble, Balance{2, 4, 6})
			})
		})

		Convey("when account config is removed", func() {
			delete(s.config.AccountConfigs, aID)
			Convey("when updating time forward", func() {
				t1 := t0.Add(time.Second)
				s.UpdateTime(ctx, t1)
				Convey("then account balance is absent.", func() {
					So(s.state.balances, ShouldNotContainKey, aID)
				})
			})
		})

		Convey("when 2 tasks for the account are running", func() {
			r1 := RequestID("request 1")
			r2 := RequestID("request 2")
			s.AddRequest(ctx, NewTaskRequest(r1, aID, nil, nil, t0), t0, nil, NullEventSink)
			s.AddRequest(ctx, NewTaskRequest(r2, aID, nil, nil, t0), t0, nil, NullEventSink)
			s.MarkIdle(ctx, "w1", nil, t0, NullEventSink)
			s.MarkIdle(ctx, "w2", nil, t0, NullEventSink)
			s.state.applyAssignment(&Assignment{Priority: 0, RequestID: r1, WorkerID: "w1", Type: AssignmentIdleWorker})
			s.state.applyAssignment(&Assignment{Priority: 0, RequestID: r2, WorkerID: "w2", Type: AssignmentIdleWorker})
			So(s.state.queuedRequests, ShouldBeEmpty)
			So(s.state.workers, ShouldHaveLength, 2)
			Convey("when updating time forward", func() {
				t1 := t0.Add(time.Second)
				s.UpdateTime(ctx, t1)
				Convey("then account balance reflects charges for running tasks.", func() {
					So(s.state.balances[aID], ShouldResemble, Balance{-1, 2, 3})
				})
			})
		})
	})
}

// TestDefaultProtoTimes tests that worker.modifiedTime and request.examinedTime
// deserialize correctly from proto, including default values when they are
// not defined in proto.
func TestDefaultProtoTimes(t *testing.T) {
	Convey("Given a state proto with workers and requests, some with undefined examinedTime or modifiedTime", t, func() {
		t1 := tutils.TimestampProto(time.Unix(100, 0))
		t2 := tutils.TimestampProto(time.Unix(200, 0))
		stateProto := &protos.SchedulerState{
			LastUpdateTime: t2,
			QueuedRequests: map[string]*protos.TaskRequest{
				"r1": {ConfirmedTime: t1, EnqueueTime: t1},
				"r2": {ConfirmedTime: t1, EnqueueTime: t1, ExaminedTime: t1},
			},
			Workers: map[string]*protos.Worker{
				"w1": {ConfirmedTime: t1},
				"w2": {ConfirmedTime: t1, ModifiedTime: t1},
			},
		}

		Convey("then the deserialized state has correct timestamps.", func() {
			state := newStateFromProto(stateProto)
			So(state.queuedRequests["r1"].examinedTime, ShouldEqual, time.Unix(0, 0))
			So(state.queuedRequests["r2"].examinedTime, ShouldEqual, time.Unix(100, 0))
			So(state.workers["w1"].modifiedTime, ShouldEqual, time.Unix(200, 0))
			So(state.workers["w2"].modifiedTime, ShouldEqual, time.Unix(100, 0))
		})
	})
}

// TestWorkerModifiedTime tests that worker.modifiedTime is updated under the
// right circumstances (when its labels change, or when it becomes idle).
func TestWorkerModifiedTime(t *testing.T) {
	Convey("Given a state with a newly added worker", t, func() {
		ctx := context.Background()
		t0 := time.Unix(100, 0)
		s := New(t0)
		s.MarkIdle(ctx, "w1", nil, time.Unix(0, 0), NullEventSink)
		Convey("the worker starts with modification time equal to scheduler's last update time.", func() {
			So(s.state.workers["w1"].modifiedTime, ShouldEqual, t0)
		})

		t1 := t0.Add(10 * time.Second)
		s.UpdateTime(ctx, t1)
		Convey("when scheduler time is updated, worker modificate time is unchanged.", func() {
			So(s.state.workers["w1"].modifiedTime, ShouldEqual, t0)
		})

		s.MarkIdle(ctx, "w1", nil, time.Unix(100, 0), NullEventSink)
		Convey("when worker is marked idle with same labels as before, modification time is unchanged.", func() {
			So(s.state.workers["w1"].modifiedTime, ShouldEqual, t0)
		})

		s.MarkIdle(ctx, "w1", stringset.NewFromSlice("foo"), time.Unix(0, 0), NullEventSink)
		Convey("when worker has an ignored update (timestamp before previous update), modification time is unchanged.", func() {
			So(s.state.workers["w1"].modifiedTime, ShouldEqual, t0)
		})

		s.MarkIdle(ctx, "w1", stringset.NewFromSlice("foo"), time.Unix(200, 0), NullEventSink)
		Convey("when worker has a forward in time update with label change, modification time becomes the scheduler's last update time.", func() {
			So(s.state.workers["w1"].modifiedTime, ShouldEqual, t1)
		})
	})

	Convey("Given a state with a running worker", t, func() {
		ctx := context.Background()
		t0 := time.Unix(100, 0)
		s := New(t0)
		s.MarkIdle(ctx, "w1", nil, time.Unix(0, 0), NullEventSink)
		s.AddRequest(ctx, NewTaskRequest("r1", "", nil, nil, t0), t0, nil, NullEventSink)
		s.RunOnce(ctx, NullEventSink)
		So(s.state.workers["w1"].IsIdle(), ShouldBeFalse)
		So(s.state.workers["w1"].modifiedTime, ShouldEqual, t0)
		Convey("when the worker becomes idle, it's modification time becomes scheduler's latest update time.", func() {
			t1 := t0.Add(10 * time.Second)
			s.UpdateTime(ctx, t1)
			s.MarkIdle(ctx, "w1", nil, t1, NullEventSink)
			So(s.state.workers["w1"].IsIdle(), ShouldBeTrue)
			So(s.state.workers["w1"].modifiedTime, ShouldEqual, t1)
		})
	})
}

// TestExaminedTime tests that request.examineTime is updated correctly.
func TestExaminedTime(t *testing.T) {
	Convey("Given a state with a new accountless request", t, func() {
		ctx := context.Background()
		t0 := time.Unix(100, 0)
		s := New(t0)
		s.AddRequest(ctx, NewTaskRequest("r1", "", nil, nil, t0), t0, nil, NullEventSink)
		Convey("it starts with examinedTime = 0.", func() {
			So(s.state.queuedRequests["r1"].examinedTime, ShouldEqual, time.Unix(0, 0))
		})

		s.RunOnce(ctx, NullEventSink)
		Convey("after a scheduler run in which it is not assigned, its examinedTime gets updated to scheduler's time.", func() {
			So(s.state.queuedRequests["r1"].examinedTime, ShouldEqual, t0)
		})
	})

	Convey("Given two requests with an account with fanout limit, and with free tasks disabled", t, func() {
		ctx := context.Background()
		t0 := time.Unix(100, 0).UTC()
		s := New(t0)
		accountConfig := NewAccountConfig(1, 10, []float32{100}, false, "")
		accountConfig.DisableFreeTasks = true
		s.AddAccount(ctx, "a1", accountConfig, []float32{100})

		s.AddRequest(ctx, NewTaskRequest("r1", "a1", nil, nil, t0), t0, nil, NullEventSink)
		s.AddRequest(ctx, NewTaskRequest("r2", "a1", nil, nil, t0), t0, nil, NullEventSink)

		s.RunOnce(ctx, NullEventSink)
		Convey("after a scheduler run in which neither is assigned, their examined times are updated to scheduler's time.", func() {
			So(s.state.queuedRequests, ShouldHaveLength, 2)
			for _, r := range s.state.queuedRequests {
				So(r.examinedTime, ShouldEqual, t0)
			}
		})

		t1 := t0.Add(10 * time.Second)
		s.MarkIdle(ctx, "w1", nil, t1, NullEventSink)
		s.UpdateTime(ctx, t1)
		s.RunOnce(ctx, NullEventSink)
		Convey("after a idle worker is added and a scheduler run in which one request is assigned, the other request's examined time is not updated (due to throttling, with an account with free tasks disabled).", func() {
			So(s.state.queuedRequests, ShouldHaveLength, 1)
			for _, r := range s.state.queuedRequests {
				So(r.examinedTime, ShouldEqual, t0)
			}
		})

		accountConfig.MaxFanout = 10
		s.state.balances["a1"] = Balance{}
		s.RunOnce(ctx, NullEventSink)
		Convey("if the request is not throttled due to fanout, but it is still unable to match due to the account being out of quota, its examined time is not updated.", func() {
			So(s.state.queuedRequests, ShouldHaveLength, 1)
			for _, r := range s.state.queuedRequests {
				So(r.examinedTime, ShouldEqual, t0)
			}
		})

		s.config.AccountConfigs["a1"].DisableFreeTasks = false
		t2 := t1.Add(10 * time.Second)
		s.UpdateTime(ctx, t2)
		s.RunOnce(ctx, NullEventSink)
		Convey("when free tasks are enabled, then after a scheduler run the queued request's examined time is updated.", func() {
			So(s.state.queuedRequests, ShouldHaveLength, 1)
			for _, r := range s.state.queuedRequests {
				So(r.examinedTime, ShouldEqual, t2)
			}
		})
	})
}

// addRunningRequest is a test helper to add a new request to a scheduler and
// immediately start it running on a new worker.
func addRunningRequest(ctx context.Context, s *Scheduler, rid RequestID, wid WorkerID, aid AccountID, pri Priority, tm time.Time) {
	s.AddRequest(ctx, NewTaskRequest(rid, aid, nil, nil, tm), tm, nil, NullEventSink)
	s.MarkIdle(ctx, wid, stringset.New(0), tm, NullEventSink)
	s.state.applyAssignment(&Assignment{Priority: pri, RequestID: rid, WorkerID: wid, Type: AssignmentIdleWorker})
}
