// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {connectStore} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as userV0 from 'reducers/userV0.js';
import {arrayToEnglish} from 'shared/helpers.js';


/**
 * `<mr-restriction-indicator>`
 *
 * Display for showing whether an issue is restricted.
 *
 */
export class MrRestrictionIndicator extends connectStore(LitElement) {
  /** @override */
  static get styles() {
    return css`
      :host {
        width: 100%;
        margin-top: 0;
        background-color: var(--monorail-metadata-toggled-bg);
        border-bottom: var(--chops-normal-border);
        font-size: var(--chops-main-font-size);
        padding: 0.25em 8px;
        box-sizing: border-box;
        display: flex;
        flex-direction: row;
        justify-content: flex-start;
        align-items: center;
      }
      :host([showWarning]) {
        background-color: var(--chops-red-700);
        color: var(--chops-white);
        font-weight: bold;
      }
      :host([showWarning]) i {
        color: var(--chops-white);
      }
      :host([hidden]) {
        display: none;
      }
      i.material-icons {
        color: var(--chops-primary-icon-color);
        font-size: var(--chops-icon-font-size);
      }
      .lock-icon {
        margin-right: 4px;
      }
      i.warning-icon {
        margin-right: 4px;
      }
      i[hidden] {
        display: none;
      }
    `;
  }

  /** @override */
  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <i
        class="lock-icon material-icons"
        icon="lock"
        ?hidden=${!this._restrictionText}
        title=${this._restrictionText}
      >
        lock
      </i>
      <i
        class="warning-icon material-icons"
        icon="warning"
        ?hidden=${!this.showWarning}
        title=${this._warningText}
      >
        warning
      </i>
      ${this._combinedText}
    `;
  }

  /** @override */
  static get properties() {
    return {
      restrictions: Object,
      prefs: Object,
      hidden: {
        type: Boolean,
        reflect: true,
      },
      showWarning: {
        type: Boolean,
        reflect: true,
      },
    };
  }

  /** @override */
  constructor() {
    super();

    this.hidden = true;
    this.showWarning = false;
    this.prefs = {};
  }

  /** @override */
  stateChanged(state) {
    this.restrictions = issueV0.restrictions(state);
    this.prefs = userV0.prefs(state);
  }

  /** @override */
  update(changedProperties) {
    if (changedProperties.has('prefs') ||
        changedProperties.has('restrictions')) {
      this.hidden = !this._combinedText;

      this.showWarning = !!this._warningText;
    }

    super.update(changedProperties);
  }

  get _warningText() {
    const {restrictions, prefs} = this;
    if (!prefs) return '';
    if (!restrictions) return '';
    if ('view' in restrictions && restrictions['view'].length) return '';
    if (prefs.get('public_issue_notice') === 'true') {
      return 'Public issue: Please do not post confidential information.';
    }
    return '';
  }

  get _combinedText() {
    if (this._warningText) return this._warningText;
    return this._restrictionText;
  }

  get _restrictionText() {
    const {restrictions} = this;
    if (!restrictions) return;
    if ('view' in restrictions && restrictions['view'].length) {
      return `Only users with ${arrayToEnglish(restrictions['view'])
      } permission or issue reporter may view.`;
    } else if ('edit' in restrictions && restrictions['edit'].length) {
      return `Only users with ${arrayToEnglish(restrictions['edit'])
      } permission may edit.`;
    } else if ('comment' in restrictions && restrictions['comment'].length) {
      return `Only users with ${arrayToEnglish(restrictions['comment'])
      } permission or issue reporter may comment.`;
    }
    return '';
  }
}

customElements.define('mr-restriction-indicator', MrRestrictionIndicator);
