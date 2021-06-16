// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Logic for dealing with federated issue references.
 */

import loadGapi, {fetchGapiEmail} from './gapi-loader.js';

const GOOGLE_ISSUE_TRACKER_REGEX = /^b\/\d+$/;

const GOOGLE_ISSUE_TRACKER_API_ROOT = 'https://issuetracker.corp.googleapis.com';
const GOOGLE_ISSUE_TRACKER_DISCOVERY_PATH = '/$discovery/rest';
const GOOGLE_ISSUE_TRACKER_API_VERSION = 'v3';

// Returns if shortlink is valid for any federated tracker.
export function isShortlinkValid(shortlink) {
  return FEDERATED_TRACKERS.some((TrackerClass) => {
    try {
      return new TrackerClass(shortlink);
    } catch (e) {
      if (e instanceof FederatedIssueError) {
        return false;
      } else {
        throw e;
      }
    }
  });
}

// Returns a issue instance for the first matching tracker.
export function fromShortlink(shortlink) {
  for (const key in FEDERATED_TRACKERS) {
    if (FEDERATED_TRACKERS.hasOwnProperty(key)) {
      const TrackerClass = FEDERATED_TRACKERS[key];
      try {
        return new TrackerClass(shortlink);
      } catch (e) {
        if (e instanceof FederatedIssueError) {
          continue;
        } else {
          throw e;
        }
      }
    }
  }
  return null;
}

// FederatedIssue is an abstract class for representing one federated issue.
// Each supported tracker should subclass this class.
class FederatedIssue {
  constructor(shortlink) {
    if (!this.isShortlinkValid(shortlink)) {
      throw new FederatedIssueError(`Invalid tracker shortlink: ${shortlink}`);
    }
    this.shortlink = shortlink;
  }

  // isShortlinkValid returns whether a given shortlink is valid.
  isShortlinkValid(shortlink) {
    if (!(typeof shortlink === 'string')) {
      throw new FederatedIssueError('shortlink argument must be a string.');
    }
    return Boolean(shortlink.match(this.shortlinkRe()));
  }

  // shortlinkRe returns the regex used to validate shortlinks.
  shortlinkRe() {
    throw new Error('Not implemented.');
  }

  // toURL returns the URL to this issue.
  toURL() {
    throw new Error('Not implemented.');
  }

  // toIssueRef converts the FedRef's information into an object having the
  // IssueRef format everywhere on the front-end expects.
  toIssueRef() {
    return {
      extIdentifier: this.shortlink,
    };
  }

  // trackerName should return the name of the bug tracker.
  get trackerName() {
    throw new Error('Not implemented.');
  }

  // isOpen returns a Promise that resolves either true or false.
  async isOpen() {
    throw new Error('Not implemented.');
  }
}

// Class for Google Issue Tracker (Buganizer) logic.
export class GoogleIssueTrackerIssue extends FederatedIssue {
  constructor(shortlink) {
    super(shortlink);
    this.issueID = Number(shortlink.substr(2));
    this._federatedDetails = null;
  }

  shortlinkRe() {
    return GOOGLE_ISSUE_TRACKER_REGEX;
  }

  toURL() {
    return `https://issuetracker.google.com/issues/${this.issueID}`;
  }

  get trackerName() {
    return 'Buganizer';
  }

  async getFederatedDetails() {
    // Prevent fetching details more than once.
    if (this._federatedDetails) {
      return this._federatedDetails;
    }

    await loadGapi();
    const email = await fetchGapiEmail();
    if (!email) {
      // Fail open.
      return true;
    }
    const res = await this._loadGoogleIssueTrackerIssue(this.issueID);
    if (!res || !res.result) {
      // Fail open.
      return null;
    }

    this._federatedDetails = res.result;
    return this._federatedDetails;
  }

  // isOpen assumes getFederatedDetails has already been called, otherwise
  // it will fail open (returning that the issue is open).
  get isOpen() {
    if (!this._federatedDetails) {
      // Fail open.
      return true;
    }

    // Open issues will not have a `resolvedTime`.
    return !Boolean(this._federatedDetails.resolvedTime);
  }

  // summary assumes getFederatedDetails has already been called.
  get summary() {
    if (this._federatedDetails &&
        this._federatedDetails.issueState &&
        this._federatedDetails.issueState.title) {
      return this._federatedDetails.issueState.title;
    }
    return null;
  }

  toIssueRef() {
    return {
      extIdentifier: this.shortlink,
      summary: this.summary,
      statusRef: {meansOpen: this.isOpen},
    };
  }

  get _APIURL() {
    return GOOGLE_ISSUE_TRACKER_API_ROOT + GOOGLE_ISSUE_TRACKER_DISCOVERY_PATH;
  }

  _loadGoogleIssueTrackerIssue(bugID) {
    return new Promise((resolve, reject) => {
      const version = GOOGLE_ISSUE_TRACKER_API_VERSION;
      gapi.client.load(this._APIURL, version, () => {
        const request = gapi.client.corp_issuetracker.issues.get({
          'issueId': bugID,
        });
        request.execute((response) => {
          resolve(response);
        });
      });
    });
  }
}

class FederatedIssueError extends Error {}

// A list of supported tracker classes.
const FEDERATED_TRACKERS = [
  GoogleIssueTrackerIssue,
];
