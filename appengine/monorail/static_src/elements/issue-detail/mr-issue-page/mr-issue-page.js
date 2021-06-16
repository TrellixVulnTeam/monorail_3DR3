// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import page from 'page';
import {LitElement, html, css} from 'lit-element';

import 'elements/chops/chops-button/chops-button.js';
import './mr-issue-header.js';
import './mr-restriction-indicator';
import '../mr-issue-details/mr-issue-details.js';
import '../metadata/mr-metadata/mr-issue-metadata.js';
import '../mr-launch-overview/mr-launch-overview.js';
import {store, connectStore} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as projectV0 from 'reducers/projectV0.js';
import * as userV0 from 'reducers/userV0.js';
import * as sitewide from 'reducers/sitewide.js';

import {SHARED_STYLES} from 'shared/shared-styles.js';
import {ISSUE_DELETE_PERMISSION} from 'shared/permissions.js';

// eslint-disable-next-line max-len
import 'elements/framework/dialogs/mr-issue-hotlists-action/mr-update-issue-hotlists-dialog.js';
import '../dialogs/mr-edit-description/mr-edit-description.js';
import '../dialogs/mr-move-copy-issue/mr-move-copy-issue.js';
import '../dialogs/mr-convert-issue/mr-convert-issue.js';
import '../dialogs/mr-related-issues/mr-related-issues.js';
import '../../help/mr-click-throughs/mr-click-throughs.js';
import {prpcClient} from 'prpc-client-instance.js';

const APPROVAL_COMMENT_COUNT = 5;
const DETAIL_COMMENT_COUNT = 100;

/**
 * `<mr-issue-page>`
 *
 * The main entry point for a Monorail issue detail page.
 *
 */
export class MrIssuePage extends connectStore(LitElement) {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          --mr-issue-page-horizontal-padding: 12px;
          --mr-toggled-font-family: inherit;
          --monorail-metadata-toggled-bg: var(--monorail-metadata-open-bg);
        }
        :host([issueClosed]) {
          --monorail-metadata-toggled-bg: var(--monorail-metadata-closed-bg);
        }
        :host([codeFont]) {
          --mr-toggled-font-family: Monospace;
        }
        .container-issue {
          width: 100%;
          flex-direction: column;
          align-items: stretch;
          justify-content: flex-start;
          z-index: 200;
        }
        .container-issue-content {
          padding: 0;
          flex-grow: 1;
          display: flex;
          align-items: stretch;
          justify-content: space-between;
          flex-direction: row;
          flex-wrap: nowrap;
          box-sizing: border-box;
          padding-top: 0.5em;
        }
        .container-outside {
          box-sizing: border-box;
          width: 100%;
          max-width: 100%;
          margin: auto;
          padding: 0;
          display: flex;
          align-items: stretch;
          justify-content: space-between;
          flex-direction: row;
          flex-wrap: no-wrap;
        }
        .container-no-issue {
          padding: 0.5em 16px;
          font-size: var(--chops-large-font-size);
        }
        .metadata-container {
          font-size: var(--chops-main-font-size);
          background: var(--monorail-metadata-toggled-bg);
          border-right: var(--chops-normal-border);
          border-bottom: var(--chops-normal-border);
          width: 24em;
          min-width: 256px;
          flex-grow: 0;
          flex-shrink: 0;
          box-sizing: border-box;
          z-index: 100;
        }
        .issue-header-container {
          z-index: 10;
          position: sticky;
          top: var(--monorail-header-height);
          margin-bottom: 0.25em;
          width: 100%;
        }
        mr-issue-details {
          min-width: 50%;
          max-width: 1000px;
          flex-grow: 1;
          box-sizing: border-box;
          min-height: 100%;
          padding-left: var(--mr-issue-page-horizontal-padding);
          padding-right: var(--mr-issue-page-horizontal-padding);
        }
        mr-issue-metadata {
          position: sticky;
          overflow-y: auto;
          top: var(--monorail-header-height);
          height: calc(100vh - var(--monorail-header-height));
        }
        mr-launch-overview {
          border-left: var(--chops-normal-border);
          padding-left: var(--mr-issue-page-horizontal-padding);
          padding-right: var(--mr-issue-page-horizontal-padding);
          flex-grow: 0;
          flex-shrink: 0;
          width: 50%;
          box-sizing: border-box;
          min-height: 100%;
        }
        @media (max-width: 1126px) {
          .container-issue-content {
            flex-direction: column;
            padding: 0 var(--mr-issue-page-horizontal-padding);
          }
          mr-issue-details, mr-launch-overview {
            width: 100%;
            padding: 0;
            border: 0;
          }
        }
        @media (max-width: 840px) {
          .container-outside {
            flex-direction: column;
          }
          .metadata-container {
            width: 100%;
            height: auto;
            border: 0;
            border-bottom: var(--chops-normal-border);
          }
          mr-issue-metadata {
            min-width: auto;
            max-width: auto;
            width: 100%;
            padding: 0;
            min-height: 0;
            border: 0;
          }
          mr-issue-metadata, .issue-header-container {
            position: static;
          }
        }
      `,
    ];
  }

  /** @override */
  render() {
    return html`
      <mr-click-throughs
         .userDisplayName=${this.userDisplayName}></mr-click-throughs>
      ${this._renderIssue()}
    `;
  }

  /**
   * Render the issue.
   * @return {TemplateResult}
   */
  _renderIssue() {
    const issueIsEmpty = !this.issue || !this.issue.localId;
    const movedToRef = this.issue.movedToRef;
    const commentShown = this.issue.approvalValues ? APPROVAL_COMMENT_COUNT :
      DETAIL_COMMENT_COUNT;

    if (this.fetchIssueError) {
      return html`
        <div class="container-no-issue" id="fetch-error">
          ${this.fetchIssueError.description}
        </div>
      `;
    }

    if (this.fetchingIssue && issueIsEmpty) {
      return html`
        <div class="container-no-issue" id="loading">
          Loading...
        </div>
      `;
    }

    if (this.issue.isDeleted) {
      return html`
        <div class="container-no-issue" id="deleted">
          <p>Issue ${this.issueRef.localId} has been deleted.</p>
          ${this.issuePermissions.includes(ISSUE_DELETE_PERMISSION) ? html`
            <chops-button
              @click=${this._undeleteIssue}
              class="undelete emphasized"
            >
              Undelete Issue
            </chops-button>
          `: ''}
        </div>
      `;
    }

    if (movedToRef && movedToRef.localId) {
      return html`
        <div class="container-no-issue" id="moved">
          <h2>Issue has moved.</h2>
          <p>
            This issue was moved to ${movedToRef.projectName}.
            <a
              class="new-location"
              href="/p/${movedToRef.projectName}/issues/detail?id=${movedToRef.localId}"
            >
              Go to issue</a>.
          </p>
        </div>
      `;
    }

    if (!issueIsEmpty) {
      return html`
        <div
          class="container-outside"
          @open-dialog=${this._openDialog}
          id="issue"
        >
          <aside class="metadata-container">
            <mr-issue-metadata></mr-issue-metadata>
          </aside>
          <div class="container-issue">
            <div class="issue-header-container">
              <mr-issue-header
                .userDisplayName=${this.userDisplayName}
              ></mr-issue-header>
              <mr-restriction-indicator></mr-restriction-indicator>
            </div>
            <div class="container-issue-content">
              <mr-issue-details
                class="main-item"
                .commentsShownCount=${commentShown}
              ></mr-issue-details>
              <mr-launch-overview class="main-item"></mr-launch-overview>
            </div>
          </div>
        </div>
        <mr-edit-description id="edit-description"></mr-edit-description>
        <mr-move-copy-issue id="move-copy-issue"></mr-move-copy-issue>
        <mr-convert-issue id="convert-issue"></mr-convert-issue>
        <mr-related-issues id="reorder-related-issues"></mr-related-issues>
        <mr-update-issue-hotlists-dialog
          id="update-issue-hotlists"
          .issueRefs=${[this.issueRef]}
          .issueHotlists=${this.issueHotlists}
        ></mr-update-issue-hotlists-dialog>
      `;
    }

    return '';
  }

  /** @override */
  static get properties() {
    return {
      userDisplayName: {type: String},
      // Redux state.
      fetchIssueError: {type: String},
      fetchingIssue: {type: Boolean},
      fetchingProjectConfig: {type: Boolean},
      issue: {type: Object},
      issueHotlists: {type: Array},
      issueClosed: {
        type: Boolean,
        reflect: true,
      },
      codeFont: {
        type: Boolean,
        reflect: true,
      },
      issuePermissions: {type: Object},
      issueRef: {type: Object},
      prefs: {type: Object},
      loginUrl: {type: String},
    };
  }

  /** @override */
  constructor() {
    super();
    this.issue = {};
    this.issueRef = {};
    this.issuePermissions = [];
    this.pref = {};
    this.codeFont = false;
  }

  /** @override */
  stateChanged(state) {
    this.projectName = projectV0.viewedProjectName(state);
    this.issue = issueV0.viewedIssue(state);
    this.issueHotlists = issueV0.hotlists(state);
    this.issueRef = issueV0.viewedIssueRef(state);
    this.fetchIssueError = issueV0.requests(state).fetch.error;
    this.fetchingIssue = issueV0.requests(state).fetch.requesting;
    this.fetchingProjectConfig = projectV0.fetchingConfig(state);
    this.issueClosed = !issueV0.isOpen(state);
    this.issuePermissions = issueV0.permissions(state);
    this.prefs = userV0.prefs(state);
  }

  /** @override */
  update(changedProperties) {
    if (changedProperties.has('prefs')) {
      this.codeFont = this.prefs.get('code_font') === 'true';
    }
    if (changedProperties.has('fetchIssueError') &&
      !this.userDisplayName && this.fetchIssueError &&
      this.fetchIssueError.codeName === 'PERMISSION_DENIED') {
      page(this.loginUrl);
    }
    super.update(changedProperties);
  }

  /** @override */
  updated(changedProperties) {
    if (changedProperties.has('issueRef') || changedProperties.has('issue')) {
      const title = this._pageTitle(this.issueRef, this.issue);
      store.dispatch(sitewide.setPageTitle(title));
    }
  }

  /**
   * Generates a title for the currently viewed page based on issue data.
   * @param {IssueRef} issueRef
   * @param {Issue} issue
   * @return {string}
   */
  _pageTitle(issueRef, issue) {
    const titlePieces = [];
    if (issueRef.localId) {
      titlePieces.push(issueRef.localId);
    }
    if (!issue || !issue.localId) {
      // Issue is not loaded.
      titlePieces.push('Loading issue...');
    } else {
      if (issue.isDeleted) {
        titlePieces.push('Deleted issue');
      } else if (issue.summary) {
        titlePieces.push(issue.summary);
      }
    }
    return titlePieces.join(' - ');
  }

  /**
   * Opens a dialog with a specific ID based on an Event.
   * @param {CustomEvent} e
   */
  _openDialog(e) {
    this.shadowRoot.querySelector('#' + e.detail.dialogId).open(e);
  }

  /**
   * Undeletes the current issue.
   */
  _undeleteIssue() {
    prpcClient.call('monorail.Issues', 'DeleteIssue', {
      issueRef: this.issueRef,
      delete: false,
    }).then(() => {
      store.dispatch(issueV0.fetchIssuePageData(this.issueRef));
    });
  }
}

customElements.define('mr-issue-page', MrIssuePage);
