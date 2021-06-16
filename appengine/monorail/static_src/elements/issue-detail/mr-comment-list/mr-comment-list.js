// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {cache} from 'lit-html/directives/cache.js';
import {LitElement, html, css} from 'lit-element';

import '../../chops/chops-button/chops-button.js';
import './mr-comment.js';
import {connectStore} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as userV0 from 'reducers/userV0.js';
import * as ui from 'reducers/ui.js';
import {userIsMember} from 'shared/helpers.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';

const ADD_ISSUE_COMMENT_PERMISSION = 'addissuecomment';

/**
 * `<mr-comment-list>`
 *
 * Display a list of Monorail comments.
 *
 */
export class MrCommentList extends connectStore(LitElement) {
  /** @override */
  constructor() {
    super();

    this.commentsShownCount = 2;
    this.comments = [];
    this.headingLevel = 4;

    this.issuePermissions = [];
    this.focusId = null;

    this.usersProjects = new Map();

    this._hideComments = true;
  }

  /** @override */
  static get properties() {
    return {
      commentsShownCount: {type: Number},
      comments: {type: Array},
      headingLevel: {type: Number},

      issuePermissions: {type: Array},
      focusId: {type: String},

      usersProjects: {type: Object},

      _hideComments: {type: Boolean},
    };
  }

  /** @override */
  stateChanged(state) {
    this.issuePermissions = issueV0.permissions(state);
    this.focusId = ui.focusId(state);
    this.usersProjects = userV0.projectsPerUser(state);
  }

  /** @override */
  updated(changedProperties) {
    super.updated(changedProperties);

    if (!this._hideComments) return;

    // If any hidden comment is focused, show all hidden comments.
    const hiddenCount =
      _hiddenCount(this.comments.length, this.commentsShownCount);
    const hiddenComments = this.comments.slice(0, hiddenCount);
    for (const comment of hiddenComments) {
      if ('c' + comment.sequenceNum === this.focusId) {
        this._hideComments = false;
        break;
      }
    };
  }

  /** @override */
  static get styles() {
    return [SHARED_STYLES, css`
      button.toggle {
        background: none;
        color: var(--chops-link-color);
        border: 0;
        border-bottom: var(--chops-normal-border);
        border-top: var(--chops-normal-border);
        width: 100%;
        padding: 0.5em 8px;
        text-align: left;
        font-size: var(--chops-main-font-size);
      }
      button.toggle:hover {
        cursor: pointer;
        text-decoration: underline;
      }
      button.toggle[hidden] {
        display: none;
      }
      .edit-slot {
        margin-top: 3em;
      }
    `];
  }

  /** @override */
  render() {
    const hiddenCount =
      _hiddenCount(this.comments.length, this.commentsShownCount);
    return html`
      <button @click=${this._toggleHide}
          class="toggle"
          ?hidden=${hiddenCount <= 0}>
        ${this._hideComments ? 'Show' : 'Hide'}
        ${hiddenCount}
        older
        ${hiddenCount == 1 ? 'comment' : 'comments'}
      </button>
      ${cache(this._hideComments ? '' :
    html`${this.comments.slice(0, hiddenCount).map(
        this.renderComment.bind(this))}`)}
      ${this.comments.slice(hiddenCount).map(this.renderComment.bind(this))}
      <div class="edit-slot"
          ?hidden=${!_canAddComment(this.issuePermissions)}>
        <slot></slot>
      </div>
    `;
  }

  /**
   * Helper to render a single comment.
   * @param {Comment} comment
   * @return {TemplateResult}
   */
  renderComment(comment) {
    const commenterIsMember = userIsMember(
        comment.commenter, comment.projectName, this.usersProjects);
    return html`
      <mr-comment
          .comment=${comment}
          headingLevel=${this.headingLevel}
          ?highlighted=${'c' + comment.sequenceNum === this.focusId}
          ?commenterIsMember=${commenterIsMember}
      ></mr-comment>`;
  }

  /**
   * Hides or unhides comments that are hidden by default. For example,
   * if an issue has 200 comments, the first 100 comments are shown initially,
   * then the last 100 can be toggled to be shown.
   * @private
   */
  _toggleHide() {
    this._hideComments = !this._hideComments;
  }
}

/**
 * Computes how many comments the user is able to expand.
 * @param {number} commentCount Total comments.
 * @param {number} commentsShownCount The number of comments shown.
 * @return {number} The number of hidden comments.
 * @private
 */
function _hiddenCount(commentCount, commentsShownCount) {
  return Math.max(commentCount - commentsShownCount, 0);
}

/**
 * @param {Array<string>} issuePermissions
 * @return {boolean} Whether the user has permission to add a comment or not.
 * @private
 */
function _canAddComment(issuePermissions) {
  return (issuePermissions || []).includes(ADD_ISSUE_COMMENT_PERMISSION);
}

customElements.define('mr-comment-list', MrCommentList);
