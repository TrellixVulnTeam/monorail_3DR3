// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {ifDefined} from 'lit-html/directives/if-defined';
import {issueRefToString, issueRefToUrl} from 'shared/convertersV0.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import '../../mr-dropdown/mr-dropdown.js';
import '../../../help/mr-cue/mr-fed-ref-cue.js';

/**
 * `<mr-issue-link>`
 *
 * Displays a link to an issue.
 *
 */
export class MrIssueLink extends LitElement {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        a[is-closed] {
          text-decoration: line-through;
        }
        mr-dropdown {
          width: var(--chops-main-font-size);
          --mr-dropdown-icon-font-size: var(--chops-main-font-size);
          --mr-dropdown-menu-min-width: 100px;
        }
      `,
    ];
  }

  /** @override */
  render() {
    let fedRefInfo;
    if (this.issue && this.issue.extIdentifier) {
      fedRefInfo = html`
        <!-- TODO(jeffcarp): Figure out CSS to enable menuAlignment=left -->
        <mr-dropdown
          label="Federated Reference Info"
          icon="info_outline"
          menuAlignment="right"
        >
          <mr-fed-ref-cue
            cuePrefName="federated_reference"
            fedRefShortlink=${this.issue.extIdentifier}
            nondismissible>
          </mr-fed-ref-cue>
        </mr-dropdown>
      `;
    }
    return html`
      <a
        id="bugLink"
        href=${this.href}
        title=${ifDefined(this.issue && this.issue.summary)}
        ?is-closed=${this.isClosed}
      >${this._linkText}</a>${fedRefInfo}`;
  }

  /** @override */
  static get properties() {
    return {
      // The issue being viewed. Falls back gracefully if this is only a ref.
      issue: {type: Object},
      text: {type: String},
      // The global current project name. NOT the issue's project name.
      projectName: {type: String},
      queryParams: {type: Object},
      short: {type: Boolean},
    };
  }

  /** @override */
  constructor() {
    super();

    this.issue = {};
    this.queryParams = {};
    this.short = false;
  }

  click() {
    const link = this.shadowRoot.querySelector('a');
    if (!link) return;
    link.click();
  }

  /**
   * @return {string} Where this issue links to.
   */
  get href() {
    return issueRefToUrl(this.issue, this.queryParams);
  }

  get isClosed() {
    if (!this.issue || !this.issue.statusRef) return false;

    return this.issue.statusRef.meansOpen === false;
  }

  get _linkText() {
    const {projectName, issue, text, short} = this;
    if (text) return text;

    if (issue && issue.extIdentifier) {
      return issue.extIdentifier;
    }

    const prefix = short ? '' : 'Issue ';

    return prefix + issueRefToString(issue, projectName);
  }
}

customElements.define('mr-issue-link', MrIssueLink);
