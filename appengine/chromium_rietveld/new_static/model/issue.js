// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

// https://codereview.chromium.org/api/148223004/?messages=true
function Issue(id)
{
    this.description = "";
    this.cc = []; // Array<User>
    this.reviewers = []; // Array<User>
    this.requiredReviewers = []; // Array<String>
    this.messages = []; // Array<IssueMessage>
    this.messageCount = 0;
    this.draftCount = 0;
    this.owner = null; // User
    this.editAllowed = false;
    this.offer_cq = true;
    this.private = false;
    this.project = "";
    this.targetRef = "";
    this.subject = "";
    this.created = ""; // Date
    this.patchsets = []; // Array<PatchSet>
    this.draftPatchsets = []; // Array<DraftPatchSet>
    this.lastModified = ""; // Date
    this.closed = false;
    this.commit = false;
    this.cqDryRun = false;
    this.id = id || 0;
    this.scores = {}; // Map<email, (-1, 1)>
    this.approvalCount = 0;
    this.disapprovalCount = 0;
    this.recentActivity = false;
    this.landed_days_ago = "unknown";
    Object.preventExtensions(this);
}

Issue.DETAIL_URL = "/api/{1}?messages=true";
Issue.DELETE_DRAFTS_URL = "/{1}/delete_drafts";

Issue.prototype.getDetailUrl = function()
{
    return Issue.DETAIL_URL.assign(encodeURIComponent(this.id));
};

Issue.prototype.getDiscardAllDraftsUrl = function()
{
    return Issue.DELETE_DRAFTS_URL.assign(encodeURIComponent(this.id));
};

Issue.prototype.reviewerEmails = function()
{
    var issue = this;
    return this.reviewers.map(function(user) {
        if (issue.requiredReviewers.find(user.email))
            return "*" + user.email;
        return user.email;
    }).join(", ");
};

Issue.prototype.ccEmails = function()
{
    return this.cc.map(function(user) {
        return user.email;
    }).join(", ");
};

Issue.prototype.loadDetails = function()
{
    var issue = this;
    return loadJSON(this.getDetailUrl()).then(function(data) {
        issue.parseData(data);
    });
};

Issue.prototype.parseData = function(data)
{
    var issue = this;
    if (this.id !== data.issue)
        throw new Error("Incorrect issue loaded " + this.id + " != " + data.issue);
    this.project = data.project || "";
    this.targetRef = data.target_ref || "";
    this.closed = data.closed || false;
    this.commit = data.commit || false;
    this.editAllowed = data.is_editor || false;
    this.cqDryRun = data.cq_dry_run || false;
    this.created = Date.utc.create(data.created);
    this.description = data.description || "";
    this.lastModified = Date.utc.create(data.modified);
    this.offer_cq = data.offer_cq;
    this.landed_days_ago = data.landed_days_ago;
    this.owner = User.forName(data.owner, data.owner_email);
    this.private = data.private;
    this.subject = data.subject || "";
    this.cc = (data.cc || []).map(function(email) {
        return User.forMailingListEmail(email);
    });
    this.reviewers = (data.reviewers || []).map(function(email) {
        return User.forMailingListEmail(email);
    });
    this.requiredReviewers = data.required_reviewers || [];
    this.patchsets = (data.patchsets || []).map(function(patchsetId, i) {
        return new PatchSet(issue, patchsetId, i + 1);
    });
    this.messages = (data.messages || []).map(function(messageData, i) {
        var message = new IssueMessage(issue, i + 1);
        message.parseData(messageData);
        return message;
    });
    this.updateScores();
    this.reviewers.sort(User.compare);
    this.cc.sort(User.compare);
    if (this.patchsets.length) {
        var last = this.patchsets.last();
        last.commit = this.commit;
        last.cqDryRun = this.cqDryRun;
        last.mostRecent = true;
        last.active = true;
    }
    // Overwrite the count in case they differ (ex. new comments were added since
    // the summary list was loaded).
    this.messageCount = this.messages.length;
};

Issue.prototype.parseInboxData = function(data)
{
    this.subject = data.subject;
    this.recentActivity = data.has_updates;
    this.lastModified = Date.utc.create(data.modified);
    this.owner = User.forMailingListEmail(data.owner_email);
    this.reviewers = Object.keys(data.reviewer_scores).map(function(email) {
        return User.forMailingListEmail(email);
    }).sort(User.compare);
    // Reset computed fields since we may call parseInboxData twice, once with
    // cached values and then again when the server comes back with new data.
    this.approvalCount = 0;
    this.disapprovalCount = 0;
    this.scores = {};
    for (var i = 0; i < this.reviewers.length; ++i) {
        var reviewer = this.reviewers[i];
        var score = data.reviewer_scores[reviewer.email];
        // TODO(esprehn): This isn't right, it should use email instead but the
        // UI wants to show short names in the inbox.
        this.scores[reviewer.name] = score;
        if (score == 1)
            this.approvalCount++;
        else if (score == -1)
            this.disapprovalCount++;
    }
};

Issue.prototype.updateScores = function() {
    var issue = this;
    var reviewerEmails = {};
    this.reviewers.forEach(function(user) {
        reviewerEmails[user.email] = true;
    });
    this.messages.forEach(function(message) {
        if (!message.approval && !message.disapproval)
            return;
        var email = message.author.email;
        if (message.approval) {
            issue.scores[email] = 1;
            issue.approvalCount++;
        } else if (message.disapproval) {
            issue.scores[email] = -1;
            issue.disapprovalCount++;
        }
        // Rietveld allows removing reviewers even if they lgtm or not lgtm a patch,
        // but still treats them as a reviewer even though the JSON API won't return
        // that user anymore. We add them back here to compensate for the JSON API
        // not having the right users.
        if (!reviewerEmails[email]) {
            reviewerEmails[email] = true;
            issue.reviewers.push(User.forMailingListEmail(email));
        }
    });
};

Issue.prototype.getDrafts = function()
{
    var drafts = [];
    this.draftPatchsets.forEach(function(draftPatchset) {
        draftPatchset.files.forEach(function(file) {
            file.drafts.forEach(function(draft) {
                drafts.push(draft);
            });
        });
    });
    return drafts;
};

Issue.prototype.updateDraftFiles = function()
{
    var draftPatchsets = {};
    this.draftPatchsets.forEach(function(draftPatchset) {
        if (draftPatchset.patchset.draftCount)
            draftPatchsets[draftPatchset.sequence] = draftPatchset;
    });
    this.draftPatchsets = [];
    this.patchsets.forEach(function(patchset) {
        if (!patchset.draftCount)
            return;
        var draftPatchset = draftPatchsets[patchset.sequence] || new DraftPatchSet(patchset);
        draftPatchset.updateFiles();
        this.draftPatchsets.push(draftPatchset);
    }, this);
};

Issue.prototype.hasBeenSent = function()
{
    return this.messages.any(function (message) {
        return !message.generated;
    });
};
