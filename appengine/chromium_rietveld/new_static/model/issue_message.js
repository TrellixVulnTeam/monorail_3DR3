// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function IssueMessage(issue, sequence)
{
    MessageBase.call(this);
    this.issue = issue || null; // Issue
    this.recipients = []; // Array<User>
    this.disapproval = false;
    this.approval = false;
    this.sequence = sequence || 0;
    this.generated = false;
    this.preview = "";
    this.active = false;
    this.issueWasClosed = false;
    Object.preventExtensions(this);
}
IssueMessage.extends(MessageBase);

IssueMessage.REPLY_HEADER = /^On \d+\/\d+\/\d+ (at )?\d+:\d+:\d+, .*? wrote:$/;
IssueMessage.FILE_HEADER = /^https:\/\/codereview.chromium.org\/\d+\/diff\/\d+\/.*$/;
IssueMessage.MAX_PREVIEW_LENGTH = 300;

IssueMessage.createMessagePreview = function(text) {
    var lines = text.split("\n");
    var i = 0;

    while (i < text.length) {
        if (lines[i] === "") {
            ++i;
        } if (IssueMessage.REPLY_HEADER.test(lines[i])) {
            ++i;
        } else if (IssueMessage.FILE_HEADER.test(lines[i])) {
            i += 5;
        } else if (lines[i] && lines[i].startsWith(">")) {
            ++i;
        } else {
            break;
        }
    }

    // If we hit the end then it's not clear what's in this reply so
    // just show it all.
    if (i >= text.length)
        return text;

    return lines
        .slice(i)
        .join("\n")
        .substr(0, IssueMessage.MAX_PREVIEW_LENGTH);
};

IssueMessage.prototype.parseData = function(data)
{
    this.author = User.forMailingListEmail(data.sender);
    this.recipients = (data.recipients || []).map(function(email) {
        return User.forMailingListEmail(email);
    });
    this.recipients.sort(User.compare);
    this.text = data.text || "";
    this.preview = IssueMessage.createMessagePreview(this.text);
    this.disapproval = data.disapproval || false;
    this.date = Date.utc.create(data.date);
    this.approval = data.approval || false;
    this.generated = data.auto_generated || false;
    this.issueWasClosed = data.issue_was_closed || false;
};
