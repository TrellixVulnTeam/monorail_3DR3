// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//go:generate cproto

package tabledef

import (
	"github.com/golang/protobuf/proto"
)

var _ = proto.Marshal
