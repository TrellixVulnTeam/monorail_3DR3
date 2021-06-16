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

/*
Package scheduler provides Scheduler, which is an implementation of the
quotascheduler algorithm. The algorithm priorities and matches requests to workers,
tracks account balances, and ensures consistency between the scheduler's estimate
of Request and Worker states and the client-supplied authoritative state.

scheduler.Scheduler is an implementation of the reconciler.Scheduler interface.

See the provided example in this packages godoc or doc_test.go for usage.
*/
package scheduler

import (
	"context"
	"fmt"
	"time"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"

	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/protos/metrics"
)

// Scheduler encapsulates the state and configuration of a running
// quotascheduler for a single pool, and its methods provide an implementation
// of the quotascheduler algorithm.
type Scheduler struct {
	state  *state
	config *Config
}

// AccountID (a string) identifies an account.
type AccountID string

// WorkerID (a string) identifies a worker.
type WorkerID string

// RequestID (a string) identifies a request.
type RequestID string

// AssignmentType is an enum of scheduler assignment types.
type AssignmentType int

// Priority is a qscheduler priority level.
type Priority int

const (
	// AssignmentIdleWorker indicates assigning a task to a currently idle worker.
	AssignmentIdleWorker AssignmentType = iota

	// AssignmentPreemptWorker indicates preempting a running task on a worker with a new task.
	AssignmentPreemptWorker
)

// An Assignment represents a scheduler decision to assign a task to a worker.
type Assignment struct {
	// Type describes which kind of assignment this represents.
	Type AssignmentType

	// WorkerID of the worker to assign a new task to (and to preempt the previous
	// task of, if this is a AssignmentPreemptWorker mutator).
	WorkerID WorkerID

	// RequestID of the task to assign to that worker.
	RequestID RequestID

	// TaskToAbort is relevant only for the AssignmentPreemptWorker type.
	// It is the request ID of the task that should be preempted.
	TaskToAbort RequestID

	// Priority at which the task will run.
	Priority Priority

	// Time is the time at which this Assignment was determined.
	Time time.Time
}

// New returns a newly initialized Scheduler.
func New(t time.Time) *Scheduler {
	return NewWithConfig(t, NewConfig())
}

// NewWithConfig returns a newly initialized Scheduler.
func NewWithConfig(t time.Time, c *Config) *Scheduler {
	return &Scheduler{
		state:  newState(t),
		config: c,
	}
}

// NewFromProto returns a new Scheduler from proto representation.
func NewFromProto(s *protos.Scheduler) *Scheduler {
	return &Scheduler{newStateFromProto(s.State), NewConfigFromProto(s.Config)}
}

// ToProto returns a proto representation of the state and configuration of Scheduler.
func (s *Scheduler) ToProto() *protos.Scheduler {
	return &protos.Scheduler{
		State:  s.state.toProto(),
		Config: s.config.ToProto(),
	}
}

// ToSnapshot returns the snapshot of the pool's scheduler state.
func (s *Scheduler) ToSnapshot(poolID string) *Snapshot {
	return s.state.snapshot(poolID)
}

// AddAccount creates a new account with the given id, config, and initialBalance
// (or zero balance if nil).
//
// If an account with that id already exists, then it is overwritten.
func (s *Scheduler) AddAccount(ctx context.Context, id AccountID, config *AccountConfig, initialBalance []float32) {
	if len(initialBalance) > NumPriorities {
		panic("too many values supplied in initialBalance")
	}
	s.config.AccountConfigs[id] = config
	bal := Balance{}
	copy(bal[:], initialBalance)
	s.state.balances[id] = bal
}

// AddRequest enqueues a new task request.
func (s *Scheduler) AddRequest(ctx context.Context, request *TaskRequest, t time.Time, tags []string, e EventSink) {
	if request.ID == "" {
		panic("empty request id")
	}
	s.state.addRequest(ctx, request, t, tags, e)
}

// IsAssigned returns whether the given request is currently assigned to the
// given worker. It is provided for a consistency checks.
func (s *Scheduler) IsAssigned(requestID RequestID, workerID WorkerID) bool {
	if w, ok := s.state.workers[workerID]; ok {
		if !w.IsIdle() {
			return w.runningTask.request.ID == requestID
		}
	}
	return false
}

// UpdateTime updates the current time for a quotascheduler, and
// updates quota account balances accordingly, based on running jobs,
// account policies, and the time elapsed since the last update.
//
// If the provided time is earlier than that last update, this does nothing.
func (s *Scheduler) UpdateTime(ctx context.Context, t time.Time) {
	state := s.state
	config := s.config
	t0 := state.lastUpdateTime

	if t.Before(t0) {
		return
	}

	elapsedSecs := float32(t.Sub(t0).Seconds())

	// Count the number of running tasks per priority bucket for each
	//
	// Since we are iterating over all running tasks, also use this
	// opportunity to update the accumulate cost of running tasks.
	jobsPerAcct := make(map[AccountID][]int)

	for _, w := range state.workers {
		if !w.IsIdle() {
			id := w.runningTask.request.AccountID
			c := jobsPerAcct[id]
			if c == nil {
				c = make([]int, NumPriorities)
				jobsPerAcct[id] = c
			}
			rt := w.runningTask
			p := rt.priority
			// Count running tasks unless they are in the FreeBucket (p = NumPriorities).
			if p < NumPriorities {
				c[w.runningTask.priority]++
				rt.cost[p] += elapsedSecs
			}
		}
	}

	// Determine the new account balance for each account.

	// Null out balances with no corresponding config.
	for aid := range s.state.balances {
		if _, ok := config.AccountConfigs[aid]; !ok {
			delete(s.state.balances, aid)
		}
	}

	// Update account balances.
	for id, acct := range config.AccountConfigs {
		accountID := AccountID(id)
		runningJobs := jobsPerAcct[accountID]
		if runningJobs == nil {
			runningJobs = make([]int, NumPriorities)
		}
		state.balances[accountID] = nextBalance(state.balances[accountID], acct, elapsedSecs, runningJobs)
	}

	state.lastUpdateTime = t

	s.expireWorkers()
}

// MarkIdle marks the given worker as idle, and with the given provisionable,
// labels, as of the given time. If this call is contradicted by newer knowledge
// of state, then it does nothing.
//
// Note: calls to MarkIdle come from bot reap calls from swarming.
func (s *Scheduler) MarkIdle(ctx context.Context, workerID WorkerID, labels stringset.Set, t time.Time, e EventSink) {
	s.state.markIdle(workerID, labels, t, e)
}

// NotifyTaskRunning informs the scheduler authoritatively that the given task
// was running on the given worker at the given time.
//
// Supplied requestID and workerID must not be "".
func (s *Scheduler) NotifyTaskRunning(ctx context.Context, requestID RequestID, workerID WorkerID, t time.Time, e EventSink) {
	s.state.notifyTaskRunning(ctx, requestID, workerID, t, e)
}

// NotifyTaskAbsent informs the scheduler authoritatively that the given request
// is stopped (not running on a worker, and not in the queue) at the given time.
//
// Supplied requestID must not be "".
func (s *Scheduler) NotifyTaskAbsent(ctx context.Context, requestID RequestID, t time.Time, e EventSink) {
	s.state.notifyTaskAbsent(ctx, requestID, t, e)
}

// Unassign moves a request that was previously assigned to a worker back to the queue.
//
// This is intended for internal use by reconciler, to heal scheduler state in cases
// where a worker was assigned a task but never successfully reaped it.
func (s *Scheduler) Unassign(ctx context.Context, requestID RequestID, workerID WorkerID, t time.Time, e EventSink) error {
	if !s.IsAssigned(requestID, workerID) {
		return fmt.Errorf("unassign: request %s not on worker %s", requestID, workerID)
	}

	worker := s.state.workers[workerID]
	request := worker.runningTask.request
	e.AddEvent(eventUnassigned(request, worker, s.state, t, &metrics.TaskEvent_UnassignedDetails{}))
	s.state.deleteWorker(workerID)
	// Drop the tasks exceeding the max timeout.
	if isBeyondMaximalTimeout(request) {
		logging.Debugf(ctx, "unassign: request %s has expired", request.ID)
		return nil
	}
	s.state.queuedRequests[request.ID] = request
	return nil
}

// RunOnce performs a single round of the quota scheduler algorithm
// on a given state and config, and returns a slice of state mutations.
func (s *Scheduler) RunOnce(ctx context.Context, e EventSink) []*Assignment {
	pass := s.newRun()
	return pass.Run(e)
}

// GetRequest returns the (waiting or running) request for a given ID.
func (s *Scheduler) GetRequest(rid RequestID) (req *TaskRequest, ok bool) {
	return s.state.getRequest(rid)
}

// GetWorkers returns the known workers.
func (s *Scheduler) GetWorkers() map[WorkerID]*Worker {
	return s.state.workers
}

// GetWaitingRequests returns the waiting requests.
func (s *Scheduler) GetWaitingRequests() map[RequestID]*TaskRequest {
	return s.state.queuedRequests
}

// GetBalances returns the account balances.
func (s *Scheduler) GetBalances() map[AccountID]Balance {
	return s.state.balances
}

// ResetBalance resets the given account's balance to 0, if it exists.
func (s *Scheduler) ResetBalance(aid AccountID) {
	if _, ok := s.state.balances[aid]; ok {
		s.state.balances[aid] = Balance{}
	}
}

// RunningRequests gets the number of running task requests.
func (s *Scheduler) RunningRequests() int {
	return len(s.state.runningRequestsCache)
}

// DeleteAccount deletes the given account.
func (s *Scheduler) DeleteAccount(aid AccountID) {
	delete(s.config.AccountConfigs, aid)
	delete(s.state.balances, aid)
}

// Config returns the scheduler's config.
func (s *Scheduler) Config() *Config {
	return s.config
}

// expireWorkers deletes idle workers that haven't been heard from recently.
func (s *Scheduler) expireWorkers() {
	expiry := 300 * time.Second
	if s.config.BotExpiration != 0 {
		expiry = s.config.BotExpiration
	}

	for wid, w := range s.state.workers {
		if !w.IsIdle() {
			continue
		}
		elapsed := s.state.lastUpdateTime.Sub(w.ConfirmedTime())
		if elapsed > expiry {
			delete(s.state.workers, wid)
		}
	}
}

// isBeyondMaximalTimeout checks if the task exceeded the maximal possible timeout.
func isBeyondMaximalTimeout(r *TaskRequest) bool {
	maxQueueingHours := 46.0
	now := time.Now()
	return now.Sub(r.EnqueueTime).Hours() > maxQueueingHours
}
