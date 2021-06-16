// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';

import 'elements/framework/links/mr-user-link/mr-user-link.js';
import {fieldTypes, EMPTY_FIELD_VALUE} from 'shared/issue-fields.js';
import {displayNameToUserRef} from 'shared/convertersV0.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';

/**
 * `<mr-field-values>`
 *
 * Takes in a list of field values and a single fieldDef and displays them
 * according to their type.
 *
 */
export class MrFieldValues extends LitElement {
  /** @override */
  static get styles() {
    return SHARED_STYLES;
  }

  /** @override */
  render() {
    if (!this.values || !this.values.length) {
      return html`${EMPTY_FIELD_VALUE}`;
    }
    switch (this.type) {
      case fieldTypes.URL_TYPE:
        return html`${this.values.map((value) => html`
          <a href=${value} target="_blank" rel="nofollow">${value}</a>
        `)}`;
      case fieldTypes.USER_TYPE:
        return html`${this.values.map((value) => html`
          <mr-user-link .userRef=${displayNameToUserRef(value)}></mr-user-link>
        `)}`;
      default:
        return html`${this.values.map((value, i) => html`
          <a href="/p/${this.projectName}/issues/list?q=${this.name}=&quot;${value}&quot;">
            ${value}</a>${this.values.length - 1 > i ? ', ' : ''}
        `)}`;
    }
  }

  /** @override */
  static get properties() {
    return {
      name: {type: String},
      type: {type: Object},
      projectName: {type: String},
      values: {type: Array},
    };
  }
}

customElements.define('mr-field-values', MrFieldValues);
