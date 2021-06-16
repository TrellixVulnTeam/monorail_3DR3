// Copyright 2020 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// package main implements the App Engine based HTTP server to handle request
// to Rotation Proxy
package main

import (
	"context"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/server"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/gaeemulation"
	"go.chromium.org/luci/server/module"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	rpb "infra/appengine/rotation-proxy/proto"
)

func checkAPIAccess(ctx context.Context, methodName string, req proto.Message) (context.Context, error) {
	// TODO(crbug.com/1081112): Remove the if condition when I figure out a way to authenticate from borg.
	if methodName == "BatchUpdateRotations" {
		return ctx, nil
	}
	hasAccess, err := auth.IsMember(ctx, "rotation-proxy-access")
	if err != nil {
		return nil, err
	}
	if !hasAccess {
		return nil, status.Errorf(codes.PermissionDenied, "%s does not have access to method %s of Rotation Proxy", auth.CurrentIdentity(ctx), methodName)
	}
	return ctx, nil
}

func main() {
	modules := []module.Module{
		gaeemulation.NewModuleFromFlags(),
	}

	server.Main(nil, modules, func(srv *server.Server) error {
		// Install regular http service
		srv.Routes.GET("/current/:name", router.MiddlewareChain{}, func(c *router.Context) {
			GetCurrentShiftHandler(c)
		})

		// Install PRPC service
		rpb.RegisterRotationProxyServiceServer(srv.PRPC, &rpb.DecoratedRotationProxyService{
			Service: &RotationProxyServer{},
			Prelude: checkAPIAccess,
		})
		return nil
	})
}
