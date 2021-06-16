// Copyright 2019 The LUCI Authors.
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

package frontend

import (
	"context"
	"math/rand"
	"sync"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"go.chromium.org/luci/grpc/grpcutil"
	swarming "go.chromium.org/luci/swarming/proto/api"

	"infra/qscheduler/service/app/state"
	"infra/qscheduler/service/app/state/nodestore"
)

// BatchedQSchedulerServer implements the QSchedulerServer interface.
//
// This implementation batches concurrent read-write requests for a given
// scheduler.
type BatchedQSchedulerServer struct {
	// batchers is a map from scheduler id to batcher.
	batchers map[string]*state.BatchRunner

	// batchersLock governs access to batchers.
	batchersLock sync.RWMutex
}

// NewBatchedServer initializes a new BatchedQSchedulerServer
func NewBatchedServer() *BatchedQSchedulerServer {
	return &BatchedQSchedulerServer{
		batchers: make(map[string]*state.BatchRunner),
	}
}

// getOrCreateBatcher creates or returns the batcher for the given scheduler.
//
// Concurrency-safe.
func (s *BatchedQSchedulerServer) getOrCreateBatcher(schedulerID string) *state.BatchRunner {
	batcher, ok := s.getBatcher(schedulerID)
	if ok {
		return batcher
	}

	s.batchersLock.Lock()
	defer s.batchersLock.Unlock()

	batcher, ok = s.batchers[schedulerID]
	if ok {
		return batcher
	}
	batcher = state.NewBatcher(schedulerID)
	store := nodestore.For(schedulerID)
	batcher.Start(store)
	s.batchers[schedulerID] = batcher
	return batcher
}

// getBatcher returns the batcher for the given scheduler, if it exists.
//
// Concurrency-safe.
func (s *BatchedQSchedulerServer) getBatcher(schedulerID string) (*state.BatchRunner, bool) {
	s.batchersLock.RLock()
	defer s.batchersLock.RUnlock()

	batcher, ok := s.batchers[schedulerID]
	return batcher, ok
}

// AssignTasks implements QSchedulerServer.
func (s *BatchedQSchedulerServer) AssignTasks(ctx context.Context, r *swarming.AssignTasksRequest) (resp *swarming.AssignTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err := r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	dur := getHandlerTimeout(ctx)
	var cancel context.CancelFunc
	if dur != 0 {
		ctx, cancel = context.WithTimeout(ctx, dur)
		defer cancel()
	}

	batcher := s.getOrCreateBatcher(r.SchedulerId)
	return batcher.Assign(ctx, r)
}

// GetCancellations implements QSchedulerServer.
func (s *BatchedQSchedulerServer) GetCancellations(ctx context.Context, r *swarming.GetCancellationsRequest) (resp *swarming.GetCancellationsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	store := nodestore.For(r.SchedulerId)
	sp, err := store.Get(ctx)
	if err != nil {
		return nil, err
	}

	c := sp.Reconciler.Cancellations(ctx)
	rc := make([]*swarming.GetCancellationsResponse_Cancellation, len(c))
	for i, v := range c {
		rc[i] = &swarming.GetCancellationsResponse_Cancellation{BotId: v.WorkerID, TaskId: v.RequestID}
	}
	return &swarming.GetCancellationsResponse{Cancellations: rc}, nil
}

// NotifyTasks implements QSchedulerServer.
func (s *BatchedQSchedulerServer) NotifyTasks(ctx context.Context, r *swarming.NotifyTasksRequest) (resp *swarming.NotifyTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err := r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	dur := getHandlerTimeout(ctx)
	var cancel context.CancelFunc
	if dur != 0 {
		ctx, cancel = context.WithTimeout(ctx, dur)
		defer cancel()
	}

	batcher := s.getOrCreateBatcher(r.SchedulerId)
	return batcher.Notify(ctx, r)
}

// GetCallbacks implements QSchedulerServer.
func (s *BatchedQSchedulerServer) GetCallbacks(ctx context.Context, r *swarming.GetCallbacksRequest) (resp *swarming.GetCallbacksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.For(r.SchedulerId)
	sp, err := store.Get(ctx)
	if err != nil {
		return nil, err
	}

	var requestIDs []string

	// Note: This implementation returns 1% (uniformly random) waiting requests,
	// and 5% (uniformly random) running requests. It would be better to select
	// the N% most stale items instead.

	for rid := range sp.Scheduler.GetWaitingRequests() {
		if rand.Int31n(100) == 0 {
			requestIDs = append(requestIDs, string(rid))
		}
	}
	for _, w := range sp.Scheduler.GetWorkers() {
		if !w.IsIdle() {
			if rand.Int31n(100) <= 4 {
				requestIDs = append(requestIDs, string(w.RunningRequest().ID))
			}
		}
	}

	resp = &swarming.GetCallbacksResponse{
		TaskIds: requestIDs,
	}

	return resp, nil
}
