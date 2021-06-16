// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {SHARED_STYLES} from 'shared/shared-styles.js';
import 'elements/chops/chops-button/chops-button.js';
import {store, connectStore} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import {prpcClient} from 'prpc-client-instance.js';

/**
 * `<mr-attachment>`
 *
 * Display attachments for Monorail comments.
 *
 */
export class MrAttachment extends connectStore(LitElement) {
  /** @override */
  static get properties() {
    return {
      attachment: {type: Object},
      projectName: {type: String},
      localId: {type: Number},
      sequenceNum: {type: Number},
      canDelete: {type: Boolean},
    };
  }

  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        .attachment-view,
        .attachment-download {
          margin-left: 8px;
          display: block;
        }
        .attachment-delete {
          margin-left: 16px;
          color: var(--chops-button-color);
          background: var(--chops-button-bg);
          border-color: transparent;
        }
        .comment-attachment {
          min-width: 20%;
          width: fit-content;
          background: var(--chops-card-details-bg);
          padding: 4px;
          margin: 8px;
          overflow: auto;
        }
        .comment-attachment-header {
          display: flex;
          flex-wrap: nowrap;
        }
        .filename {
          margin-left: 8px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .filename-deleted {
          margin-right: 4px;
        }
        .filesize {
          margin-left: 8px;
          white-space: nowrap;
        }
        .preview {
          border: 2px solid #c3d9ff;
          padding: 1px;
          max-width: 98%;
        }
        .preview:hover {
          border: 2px solid blue;
        }
      `];
  }

  /** @override */
  render() {
    return html`
      <div class="comment-attachment">
        <div class="filename">
          ${this.attachment.isDeleted ? html`
            <div class="filename-deleted">[Deleted]</div>
          ` : ''}
          <b>${this.attachment.filename}</b>
          ${this.canDelete ? html`
            <chops-button
              class="attachment-delete"
              @click=${this._deleteAttachment}>
              ${this.attachment.isDeleted ? 'Undelete' : 'Delete'}
            </chops-button>
          ` : ''}
        </div>
        ${!this.attachment.isDeleted ? html`
          <div class="comment-attachment-header">
            <div class="filesize">${_bytesOrKbOrMb(this.attachment.size)}</div>
            ${this.attachment.viewUrl ? html`
              <a
                class="attachment-view"
                href=${this.attachment.viewUrl}
                target="_blank"
              >View</a>
            `: ''}
            ${this.attachment.downloadUrl ? html`
              <a
                class="attachment-download"
                href=${this.attachment.downloadUrl}
                target="_blank"
              >Download</a>
            `: ''}
          </div>
          ${this.attachment.thumbnailUrl ? html`
            <a href=${this.attachment.viewUrl} target="_blank">
              <img
                class="preview" alt="attachment preview"
                src=${this.attachment.thumbnailUrl}>
            </a>
          ` : ''}
          ${_isVideo(this.attachment.contentType) ? html`
            <video
              src=${this.attachment.viewUrl}
              class="preview"
              controls
              width="640"
              preload="metadata"
            ></video>
          ` : ''}
        ` : ''}
      </div>
    `;
  }

  /**
   * Deletes a given attachment in a comment.
   */
  _deleteAttachment() {
    const issueRef = {
      projectName: this.projectName,
      localId: this.localId,
    };

    const promise = prpcClient.call(
        'monorail.Issues', 'DeleteAttachment',
        {
          issueRef,
          sequenceNum: this.sequenceNum,
          attachmentId: this.attachment.attachmentId,
          delete: !this.attachment.isDeleted,
        });

    promise.then(() => {
      store.dispatch(issueV0.fetchComments(issueRef));
    }, (error) => {
      console.log('Failed to (un)delete attachment', error);
    });
  }
}

function _isVideo(contentType) {
  if (!contentType) return;
  return contentType.startsWith('video/');
}

function _bytesOrKbOrMb(numBytes) {
  if (numBytes < 1024) {
    return `${numBytes} bytes`; // e.g., 128 bytes
  } else if (numBytes < 99 * 1024) {
    return `${(numBytes / 1024).toFixed(1)} KB`; // e.g. 23.4 KB
  } else if (numBytes < 1024 * 1024) {
    return `${(numBytes / 1024).toFixed(0)} KB`; // e.g., 219 KB
  } else if (numBytes < 99 * 1024 * 1024) {
    return `${(numBytes / 1024 / 1024).toFixed(1)} MB`; // e.g., 21.9 MB
  } else {
    return `${(numBytes / 1024 / 1024).toFixed(0)} MB`; // e.g., 100 MB
  }
}

customElements.define('mr-attachment', MrAttachment);
