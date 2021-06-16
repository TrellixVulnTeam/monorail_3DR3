// Code generated by svcdec; DO NOT EDIT.

package qscheduler

import (
	"context"

	proto "github.com/golang/protobuf/proto"
)

type DecoratedQSchedulerView struct {
	// Service is the service to decorate.
	Service QSchedulerViewServer
	// Prelude is called for each method before forwarding the call to Service.
	// If Prelude returns an error, then the call is skipped and the error is
	// processed via the Postlude (if one is defined), or it is returned directly.
	Prelude func(ctx context.Context, methodName string, req proto.Message) (context.Context, error)
	// Postlude is called for each method after Service has processed the call, or
	// after the Prelude has returned an error. This takes the the Service's
	// response proto (which may be nil) and/or any error. The decorated
	// service will return the response (possibly mutated) and error that Postlude
	// returns.
	Postlude func(ctx context.Context, methodName string, rsp proto.Message, err error) error
}

func (s *DecoratedQSchedulerView) ListAccounts(ctx context.Context, req *ListAccountsRequest) (rsp *ListAccountsResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "ListAccounts", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.ListAccounts(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "ListAccounts", rsp, err)
	}
	return
}

func (s *DecoratedQSchedulerView) InspectPool(ctx context.Context, req *InspectPoolRequest) (rsp *InspectPoolResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "InspectPool", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.InspectPool(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "InspectPool", rsp, err)
	}
	return
}
