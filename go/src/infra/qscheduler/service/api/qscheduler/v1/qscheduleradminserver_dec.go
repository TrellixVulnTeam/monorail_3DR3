// Code generated by svcdec; DO NOT EDIT.

package qscheduler

import (
	"context"

	proto "github.com/golang/protobuf/proto"
)

type DecoratedQSchedulerAdmin struct {
	// Service is the service to decorate.
	Service QSchedulerAdminServer
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

func (s *DecoratedQSchedulerAdmin) CreateSchedulerPool(ctx context.Context, req *CreateSchedulerPoolRequest) (rsp *CreateSchedulerPoolResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "CreateSchedulerPool", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.CreateSchedulerPool(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "CreateSchedulerPool", rsp, err)
	}
	return
}

func (s *DecoratedQSchedulerAdmin) CreateAccount(ctx context.Context, req *CreateAccountRequest) (rsp *CreateAccountResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "CreateAccount", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.CreateAccount(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "CreateAccount", rsp, err)
	}
	return
}

func (s *DecoratedQSchedulerAdmin) Wipe(ctx context.Context, req *WipeRequest) (rsp *WipeResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "Wipe", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.Wipe(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "Wipe", rsp, err)
	}
	return
}

func (s *DecoratedQSchedulerAdmin) ModAccount(ctx context.Context, req *ModAccountRequest) (rsp *ModAccountResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "ModAccount", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.ModAccount(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "ModAccount", rsp, err)
	}
	return
}

func (s *DecoratedQSchedulerAdmin) ModSchedulerPool(ctx context.Context, req *ModSchedulerPoolRequest) (rsp *ModSchedulerPoolResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "ModSchedulerPool", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.ModSchedulerPool(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "ModSchedulerPool", rsp, err)
	}
	return
}

func (s *DecoratedQSchedulerAdmin) DeleteAccount(ctx context.Context, req *DeleteAccountRequest) (rsp *DeleteAccountResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "DeleteAccount", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.DeleteAccount(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "DeleteAccount", rsp, err)
	}
	return
}

func (s *DecoratedQSchedulerAdmin) DeleteSchedulerPool(ctx context.Context, req *DeleteSchedulerPoolRequest) (rsp *DeleteSchedulerPoolResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(ctx, "DeleteSchedulerPool", req)
		if err == nil {
			ctx = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.DeleteSchedulerPool(ctx, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(ctx, "DeleteSchedulerPool", rsp, err)
	}
	return
}
