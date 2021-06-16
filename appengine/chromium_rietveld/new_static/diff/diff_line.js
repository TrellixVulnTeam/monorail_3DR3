// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DiffLine(type)
{
    this.type = type;
    this.beforeNumber = 0;
    this.afterNumber = 0;
    this.contextLinesStart = 0;
    this.contextLinesEnd = 0;
    this.context = false;
    this.text = "";
    Object.preventExtensions(this);
}

DiffLine.BLANK_LINE = new DiffLine("blank");
