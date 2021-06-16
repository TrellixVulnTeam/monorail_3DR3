// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/issue-detail/mr-flipper/mr-flipper.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import 'elements/chops/chops-timestamp/chops-timestamp.js';
import {store, connectStore} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as userV0 from 'reducers/userV0.js';
import * as projectV0 from 'reducers/projectV0.js';
import {userIsMember} from 'shared/helpers.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import 'elements/framework/links/mr-user-link/mr-user-link.js';
import 'elements/framework/links/mr-crbug-link/mr-crbug-link.js';
import 'elements/framework/mr-code-font-toggle/mr-code-font-toggle.js';
import 'elements/framework/mr-dropdown/mr-dropdown.js';
import {ISSUE_EDIT_PERMISSION, ISSUE_DELETE_PERMISSION,
  ISSUE_FLAGSPAM_PERMISSION} from 'shared/permissions.js';
import {issueToIssueRef} from 'shared/convertersV0.js';
import {prpcClient} from 'prpc-client-instance.js';

const DELETE_ISSUE_CONFIRMATION_NOTICE = `\
Normally, you would just close issues by setting their status to a closed value.
Are you sure you want to delete this issue?`;


/**
 * `<mr-issue-header>`
 *
 * The header for a given launch issue.
 *
 */
export class MrIssueHeader extends connectStore(LitElement) {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          width: 100%;
          margin-top: 0;
          font-size: var(--chops-large-font-size);
          background-color: var(--monorail-metadata-toggled-bg);
          border-bottom: var(--chops-normal-border);
          padding: 0.25em 8px;
          box-sizing: border-box;
          display: flex;
          flex-direction: row;
          justify-content: space-between;
          align-items: center;
        }
        h1 {
          font-size: 100%;
          line-height: 140%;
          font-weight: bolder;
          padding: 0;
          margin: 0;
        }
        mr-flipper {
          border-left: var(--chops-normal-border);
          padding-left: 8px;
          margin-left: 4px;
          font-size: var(--chops-main-font-size);
        }
        .issue-actions {
          min-width: fit-content;
          display: flex;
          flex-direction: row;
          align-items: center;
          font-size: var(--chops-main-font-size);
        }
        .issue-actions div {
          min-width: 70px;
          display: flex;
          justify-content: space-between;
        }
        .spam-notice {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 1px 6px;
          border-radius: 3px;
          background: #F44336;
          color: var(--chops-white);
          font-weight: bold;
          font-size: var(--chops-main-font-size);
          margin-right: 4px;
        }
        .byline {
          display: block;
          font-size: var(--chops-main-font-size);
          width: 100%;
          line-height: 140%;
          color: var(--chops-primary-font-color);
        }
        .role-label {
          background-color: var(--chops-gray-600);
          border-radius: 3px;
          color: var(--chops-white);
          display: inline-block;
          padding: 2px 4px;
          font-size: 75%;
          font-weight: bold;
          line-height: 14px;
          vertical-align: text-bottom;
          margin-left: 16px;
        }
        .main-text-outer {
          flex-basis: 100%;
          display: flex;
          justify-content: flex-start;
          flex-direction: row;
          align-items: center;
        }
        .main-text {
          flex-basis: 100%;
        }
        @media (max-width: 840px) {
          :host {
            flex-wrap: wrap;
            justify-content: center;
          }
          .main-text {
            width: 100%;
            margin-bottom: 0.5em;
          }
        }
      `,
    ];
  }

  /** @override */
  render() {
    const reporterIsMember = userIsMember(
        this.issue.reporterRef, this.issue.projectName, this.usersProjects);
    return html`
      <div class="main-text-outer">
        <div class="main-text">
          <h1>
            ${this.issue.isSpam ? html`
              <span class="spam-notice">Spam</span>
            `: ''}
            Issue ${this.issue.localId}: ${this.issue.summary}
          </h1>
          <small class="byline">
            Reported by
            <mr-user-link
              .userRef=${this.issue.reporterRef}
              aria-label="issue reporter"
            ></mr-user-link>
            on <chops-timestamp .timestamp=${this.issue.openedTimestamp}></chops-timestamp>
            ${reporterIsMember ? html`
              <span class="role-label">Project Member</span>` : ''}
          </small>
        </div>
      </div>
      <div class="issue-actions">
        <div>
          <mr-crbug-link .issue=${this.issue}></mr-crbug-link>
          <mr-code-font-toggle
            .userDisplayName=${this.userDisplayName}
          ></mr-code-font-toggle>
        </div>
        ${this._issueOptions.length ? html`
          <mr-dropdown
            .items=${this._issueOptions}
            icon="more_vert"
            label="Issue options"
          ></mr-dropdown>
        ` : ''}
        <mr-flipper></mr-flipper>
      </div>
    `;
  }

  /** @override */
  static get properties() {
    return {
      userDisplayName: {type: String},
      issue: {type: Object},
      issuePermissions: {type: Object},
      isRestricted: {type: Boolean},
      projectTemplates: {type: Array},
      usersProjects: {type: Object},
      _action: {type: String},
      _targetProjectError: {type: String},
    };
  }

  /** @override */
  constructor() {
    super();
    this.issuePermissions = [];
    this.projectTemplates = [];
    this.issue = {};
    this.usersProjects = new Map();
    this.isRestricted = false;
  }

  /** @override */
  stateChanged(state) {
    this.issue = issueV0.viewedIssue(state);
    this.issuePermissions = issueV0.permissions(state);
    this.projectTemplates = projectV0.viewedTemplates(state);
    this.usersProjects = userV0.projectsPerUser(state);

    const restrictions = issueV0.restrictions(state);
    this.isRestricted = restrictions && Object.keys(restrictions).length;
  }

  /**
   * @return {Array<MenuItem>} Actions the user can take on the issue.
   * @private
   */
  get _issueOptions() {
    // We create two edit Arrays for the top and bottom half of the menu,
    // to be separated by a separator in the UI.
    const editOptions = [];
    const riskyOptions = [];
    const isSpam = this.issue.isSpam;
    const isRestricted = this.isRestricted;

    const permissions = this.issuePermissions;
    const templates = this.projectTemplates;


    if (permissions.includes(ISSUE_EDIT_PERMISSION)) {
      editOptions.push({
        text: 'Edit issue description',
        handler: this._openEditDescription.bind(this),
      });
      if (templates.length) {
        riskyOptions.push({
          text: 'Convert issue template',
          handler: this._openConvertIssue.bind(this),
        });
      }
    }

    if (permissions.includes(ISSUE_DELETE_PERMISSION)) {
      riskyOptions.push({
        text: 'Delete issue',
        handler: this._deleteIssue.bind(this),
      });
      if (!isRestricted) {
        editOptions.push({
          text: 'Move issue',
          handler: this._openMoveCopyIssue.bind(this, 'Move'),
        });
        editOptions.push({
          text: 'Copy issue',
          handler: this._openMoveCopyIssue.bind(this, 'Copy'),
        });
      }
    }

    if (permissions.includes(ISSUE_FLAGSPAM_PERMISSION)) {
      const text = (isSpam ? 'Un-flag' : 'Flag') + ' issue as spam';
      riskyOptions.push({
        text,
        handler: this._markIssue.bind(this),
      });
    }

    if (editOptions.length && riskyOptions.length) {
      editOptions.push({separator: true});
    }
    return editOptions.concat(riskyOptions);
  }

  /**
   * Marks an issue as either spam or not spam based on whether the issue
   * was spam.
   */
  _markIssue() {
    prpcClient.call('monorail.Issues', 'FlagIssues', {
      issueRefs: [{
        projectName: this.issue.projectName,
        localId: this.issue.localId,
      }],
      flag: !this.issue.isSpam,
    }).then(() => {
      store.dispatch(issueV0.fetch({
        projectName: this.issue.projectName,
        localId: this.issue.localId,
      }));
    });
  }

  /**
   * Deletes an issue.
   */
  _deleteIssue() {
    const ok = confirm(DELETE_ISSUE_CONFIRMATION_NOTICE);
    if (ok) {
      const issueRef = issueToIssueRef(this.issue);
      // TODO(crbug.com/monorail/7374): Delete for the v0 -> v3 migration.
      prpcClient.call('monorail.Issues', 'DeleteIssue', {
        issueRef,
        delete: true,
      }).then(() => {
        store.dispatch(issueV0.fetch(issueRef));
      });
    }
  }

  /**
   * Launches the dialog to edit an issue's description.
   * @fires CustomEvent#open-dialog
   * @private
   */
  _openEditDescription() {
    this.dispatchEvent(new CustomEvent('open-dialog', {
      bubbles: true,
      composed: true,
      detail: {
        dialogId: 'edit-description',
        fieldName: '',
      },
    }));
  }

  /**
   * Opens dialog to either move or copy an issue.
   * @param {"move"|"copy"} action
   * @fires CustomEvent#open-dialog
   * @private
   */
  _openMoveCopyIssue(action) {
    this.dispatchEvent(new CustomEvent('open-dialog', {
      bubbles: true,
      composed: true,
      detail: {
        dialogId: 'move-copy-issue',
        action,
      },
    }));
  }

  /**
   * Opens dialog for converting an issue.
   * @fires CustomEvent#open-dialog
   * @private
   */
  _openConvertIssue() {
    this.dispatchEvent(new CustomEvent('open-dialog', {
      bubbles: true,
      composed: true,
      detail: {
        dialogId: 'convert-issue',
      },
    }));
  }
}

customElements.define('mr-issue-header', MrIssueHeader);
