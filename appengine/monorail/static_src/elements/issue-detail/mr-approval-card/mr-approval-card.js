// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/chops/chops-dialog/chops-dialog.js';
import 'elements/chops/chops-collapse/chops-collapse.js';
import {store, connectStore} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as projectV0 from 'reducers/projectV0.js';
import * as userV0 from 'reducers/userV0.js';
import * as ui from 'reducers/ui.js';
import {fieldTypes} from 'shared/issue-fields.js';
import 'elements/framework/mr-comment-content/mr-description.js';
import '../mr-comment-list/mr-comment-list.js';
import 'elements/issue-detail/metadata/mr-edit-metadata/mr-edit-metadata.js';
import 'elements/issue-detail/metadata/mr-metadata/mr-metadata.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import {APPROVER_RESTRICTED_STATUSES, STATUS_ENUM_TO_TEXT, TEXT_TO_STATUS_ENUM,
  STATUS_CLASS_MAP, CLASS_ICON_MAP, APPROVAL_STATUSES,
} from 'shared/approval-consts.js';
import {commentListToDescriptionList} from 'shared/convertersV0.js';
import {cueNames, cueNameToSpec} from 'elements/help/mr-cue/cue-helpers.js';


/**
 * @type {Array<string>} The list of built in metadata fields to show on
 *   issue approvals.
 */
const APPROVAL_METADATA_FIELDS = ['ApprovalStatus', 'Approvers', 'Setter',
  cueNameToSpec(cueNames.AVAILABILITY_MSGS)];

/**
 * `<mr-approval-card>`
 *
 * This element shows a card for a single approval.
 *
 */
export class MrApprovalCard extends connectStore(LitElement) {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          width: 100%;
          background-color: var(--chops-white);
          font-size: var(--chops-main-font-size);
          border-bottom: var(--chops-normal-border);
          box-sizing: border-box;
          display: block;
          border-left: 4px solid var(--approval-bg-color);

          /* Default styles are for the NotSet/NeedsReview case. */
          --approval-bg-color: var(--chops-purple-50);
          --approval-accent-color: var(--chops-purple-700);
        }
        :host(.status-na) {
          --approval-bg-color: hsl(227, 20%, 92%);
          --approval-accent-color: hsl(227, 80%, 40%);
        }
        :host(.status-approved) {
          --approval-bg-color: hsl(78, 55%, 90%);
          --approval-accent-color: hsl(78, 100%, 30%);
        }
        :host(.status-pending) {
          --approval-bg-color: hsl(40, 75%, 90%);
          --approval-accent-color: hsl(33, 100%, 39%);
        }
        :host(.status-rejected) {
          --approval-bg-color: hsl(5, 60%, 92%);
          --approval-accent-color: hsl(357, 100%, 39%);
        }
        chops-button {
          border: var(--chops-normal-border);
          margin: 0;
        }
        h3 {
          margin: 0;
          padding: 0;
          display: inline;
          font-weight: inherit;
          font-size: inherit;
          line-height: inherit;
        }
        mr-description {
          display: block;
          margin-bottom: 0.5em;
        }
        .approver-notice {
          padding: 0.25em 0;
          width: 100%;
          display: flex;
          flex-direction: row;
          align-items: baseline;
          justify-content: space-between;
          border-bottom: 1px dotted hsl(0, 0%, 83%);
        }
        .card-content {
          box-sizing: border-box;
          padding: 0.5em 16px;
          padding-bottom: 1em;
        }
        .expand-icon {
          display: block;
          margin-right: 8px;
          color: hsl(0, 0%, 45%);
        }
        .header {
          margin: 0;
          width: 100%;
          border: 0;
          font-size: var(--chops-large-font-size);
          font-weight: normal;
          box-sizing: border-box;
          display: flex;
          align-items: center;
          flex-direction: row;
          padding: 0.5em 8px;
          background-color: var(--approval-bg-color);
          cursor: pointer;
        }
        .status {
          font-size: var(--chops-main-font-size);
          color: var(--approval-accent-color);
          display: inline-flex;
          align-items: center;
          margin-left: 32px;
        }
        .survey {
          padding: 0.5em 0;
          max-height: 500px;
          overflow-y: auto;
          max-width: 100%;
          box-sizing: border-box;
        }
        [role="heading"] {
          display: flex;
          flex-direction: row;
          justify-content: space-between;
          align-items: flex-end;
        }
      `,
    ];
  }

  /** @override */
  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <button
        class="header"
        @click=${this.toggleCard}
        aria-expanded=${(this.opened || false).toString()}
      >
        <i class="material-icons expand-icon">
          ${this.opened ? 'expand_less' : 'expand_more'}
        </i>
        <h3>${this.fieldName}</h3>
        <span class="status">
          <i class="material-icons status-icon" role="presentation">
            ${CLASS_ICON_MAP[this._statusClass]}
          </i>
          ${this._status}
        </span>
      </button>
      <chops-collapse class="card-content" ?opened=${this.opened}>
        <div class="approver-notice">
          ${this._isApprover ? html`
            You are an approver for this bit.
          `: ''}
          ${this.user && this.user.isSiteAdmin ? html`
            Your site admin privileges give you full access to edit this approval.
          `: ''}
        </div>
        <mr-metadata
          aria-label="${this.fieldName} Approval Metadata"
          .approvalStatus=${this._status}
          .approvers=${this.approvers}
          .setter=${this.setter}
          .fieldDefs=${this.fieldDefs}
          .builtInFieldSpec=${APPROVAL_METADATA_FIELDS}
          isApproval
        ></mr-metadata>
        <h4
          class="medium-heading"
          role="heading"
        >
          ${this.fieldName} Survey
          <chops-button @click=${this._openSurveyEditor}>
            Edit responses
          </chops-button>
        </h4>
        <mr-description
          class="survey"
          .descriptionList=${this._allSurveys}
        ></mr-description>
        <mr-comment-list
          headingLevel=4
          .comments=${this.comments}
        >
          <h4 id="edit${this.fieldName}" class="medium-heading">
            Editing approval: ${this.phaseName} &gt; ${this.fieldName}
          </h4>
          <mr-edit-metadata
            .formName="${this.phaseName} > ${this.fieldName}"
            .approvers=${this.approvers}
            .fieldDefs=${this.fieldDefs}
            .statuses=${this._availableStatuses}
            .status=${this._status}
            .error=${this.updateError && (this.updateError.description || this.updateError.message)}
            ?saving=${this.updatingApproval}
            ?hasApproverPrivileges=${this._hasApproverPrivileges}
            isApproval
            @save=${this.save}
            @discard=${this.reset}
          ></mr-edit-metadata>
        </mr-comment-list>
      </chops-collapse>
    `;
  }

  /** @override */
  static get properties() {
    return {
      fieldName: {type: String},
      approvers: {type: Array},
      phaseName: {type: String},
      setter: {type: Object},
      fieldDefs: {type: Array},
      focusId: {type: String},
      user: {type: Object},
      issue: {type: Object},
      issueRef: {type: Object},
      projectConfig: {type: Object},
      comments: {type: String},
      opened: {
        type: Boolean,
        reflect: true,
      },
      statusEnum: {type: String},
      updatingApproval: {type: Boolean},
      updateError: {type: Object},
      _allSurveys: {type: Array},
    };
  }

  /** @override */
  constructor() {
    super();
    this.opened = false;
    this.comments = [];
    this.fieldDefs = [];
    this._allSurveys = [];
  }

  /** @override */
  stateChanged(state) {
    const fieldDefsByApproval = projectV0.fieldDefsByApprovalName(state);
    if (fieldDefsByApproval && this.fieldName &&
        fieldDefsByApproval.has(this.fieldName)) {
      this.fieldDefs = fieldDefsByApproval.get(this.fieldName);
    }
    const commentsByApproval = issueV0.commentsByApprovalName(state);
    if (commentsByApproval && this.fieldName &&
        commentsByApproval.has(this.fieldName)) {
      const comments = commentsByApproval.get(this.fieldName);
      this.comments = comments.slice(1);
      this._allSurveys = commentListToDescriptionList(comments);
    }
    this.focusId = ui.focusId(state);
    this.user = userV0.currentUser(state);
    this.issue = issueV0.viewedIssue(state);
    this.issueRef = issueV0.viewedIssueRef(state);
    this.projectConfig = projectV0.viewedConfig(state);
    this.updatingApproval = issueV0.requests(state).updateApproval.requesting;
    this.updateError = issueV0.requests(state).updateApproval.error;
  }

  /** @override */
  update(changedProperties) {
    if ((changedProperties.has('comments') ||
        changedProperties.has('focusId')) && this.comments) {
      const focused = this.comments.find(
          (comment) => `c${comment.sequenceNum}` === this.focusId);
      if (focused) {
        // Make sure to open the card when a comment is focused.
        this.opened = true;
      }
    }
    if (changedProperties.has('statusEnum')) {
      this.setAttribute('class', this._statusClass);
    }
    if (changedProperties.has('user') || changedProperties.has('approvers')) {
      if (this._isApprover) {
        // Open the card by default if the user is an approver.
        this.opened = true;
      }
    }
    super.update(changedProperties);
  }

  /** @override */
  updated(changedProperties) {
    if (changedProperties.has('issue')) {
      this.reset();
    }
  }

  /**
   * Resets the approval edit form.
   */
  reset() {
    const form = this.shadowRoot.querySelector('mr-edit-metadata');
    if (!form) return;
    form.reset();
  }

  /**
   * Saves the user's changes in the approval update form.
   */
  async save() {
    const form = this.shadowRoot.querySelector('mr-edit-metadata');
    const delta = form.delta;

    if (delta.status) {
      delta.status = TEXT_TO_STATUS_ENUM[delta.status];
    }

    // TODO(ehmaldonado): Show snackbar on change, and prevent starring issues
    // to resetting the form.

    const message = {
      issueRef: this.issueRef,
      fieldRef: {
        type: fieldTypes.APPROVAL_TYPE,
        fieldName: this.fieldName,
      },
      approvalDelta: delta,
      commentContent: form.getCommentContent(),
      sendEmail: form.sendEmail,
    };

    // Add files to message.
    const uploads = await form.getAttachments();

    if (uploads && uploads.length) {
      message.uploads = uploads;
    }

    if (message.commentContent || message.approvalDelta || message.uploads) {
      store.dispatch(issueV0.updateApproval(message));
    }
  }

  /**
   * Opens and closes the approval card.
   */
  toggleCard() {
    this.opened = !this.opened;
  }

  /**
   * @return {string} The CSS class used to style the approval card,
   *   given its status.
   * @private
   */
  get _statusClass() {
    return STATUS_CLASS_MAP[this._status];
  }

  /**
   * @return {string} The human readable value of an approval status.
   * @private
   */
  get _status() {
    return STATUS_ENUM_TO_TEXT[this.statusEnum || ''];
  }

  /**
   * @return {boolean} Whether the user is an approver or not.
   * @private
   */
  get _isApprover() {
    // Assumption: Since a user who is an approver should always be a project
    // member, displayNames should be visible to them if they are an approver.
    if (!this.approvers || !this.user || !this.user.displayName) return false;
    const userGroups = this.user.groups || [];
    return !!this.approvers.find((a) => {
      return a.displayName === this.user.displayName || userGroups.find(
          (group) => group.displayName === a.displayName,
      );
    });
  }

  /**
   * @return {boolean} Whether the user can approver the approval or not.
   *   Not the same as _isApprover because site admins can approve approvals
   *   even if they are not approvers.
   * @private
   */
  get _hasApproverPrivileges() {
    return (this.user && this.user.isSiteAdmin) || this._isApprover;
  }

  /**
   * @return {Array<StatusDef>}
   * @private
   */
  get _availableStatuses() {
    return APPROVAL_STATUSES.filter((s) => {
      if (s.status === this._status) {
        // The current status should always appear as an option.
        return true;
      }

      if (!this._hasApproverPrivileges &&
          APPROVER_RESTRICTED_STATUSES.has(s.status)) {
        // If you are not an approver and and this status is restricted,
        // you can't change to this status.
        return false;
      }

      // No one can set statuses to NotSet, not even approvers.
      return s.status !== 'NotSet';
    });
  }

  /**
   * Launches the description editing dialog for the survey.
   * @fires CustomEvent#open-dialog
   * @private
   */
  _openSurveyEditor() {
    this.dispatchEvent(new CustomEvent('open-dialog', {
      bubbles: true,
      composed: true,
      detail: {
        dialogId: 'edit-description',
        fieldName: this.fieldName,
      },
    }));
  }
}

customElements.define('mr-approval-card', MrApprovalCard);
