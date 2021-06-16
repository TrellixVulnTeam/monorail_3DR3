// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import qs from 'qs';
import {connectStore} from 'reducers/base.js';
import * as sitewide from 'reducers/sitewide.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';

/**
 * Class for displaying a single flipper.
 * @extends {LitElement}
 */
export default class MrFlipper extends connectStore(LitElement) {
  /** @override */
  static get properties() {
    return {
      currentIndex: {type: Number},
      totalCount: {type: Number},
      prevUrl: {type: String},
      nextUrl: {type: String},
      listUrl: {type: String},
      queryParams: {type: Object},
    };
  }

  /** @override */
  constructor() {
    super();
    this.currentIndex = null;
    this.totalCount = null;
    this.prevUrl = null;
    this.nextUrl = null;
    this.listUrl = null;

    this.queryParams = {};
  }

  /** @override */
  stateChanged(state) {
    this.queryParams = sitewide.queryParams(state);
  }

  /** @override */
  updated(changedProperties) {
    if (changedProperties.has('queryParams')) {
      this.fetchFlipperData(qs.stringify(this.queryParams));
    }
  }

  // Eventually this should be replaced with pRPC.
  fetchFlipperData(query) {
    const options = {
      credentials: 'include',
      method: 'GET',
    };
    fetch(`detail/flipper?${query}`, options).then(
        (response) => response.text(),
    ).then(
        (responseBody) => {
          let responseData;
          try {
          // Strip XSSI prefix from response.
            responseData = JSON.parse(responseBody.substr(5));
          } catch (e) {
            console.error(`Error parsing JSON response for flipper: ${e}`);
            return;
          }
          this._populateResponseData(responseData);
        },
    );
  }

  _populateResponseData(data) {
    this.totalCount = data.total_count;
    this.currentIndex = data.cur_index;
    this.prevUrl = data.prev_url;
    this.nextUrl = data.next_url;
    this.listUrl = data.list_url;
  }

  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: flex;
          justify-content: center;
          flex-direction: column;
        }
        /* Use visibility instead of display:hidden for hiding in order to
        * avoid popping when elements are made visible. */
        .row a[hidden], .counts[hidden] {
          visibility: hidden;
        }
        .counts[hidden] {
          display: block;
        }
        .row a {
          display: block;
          padding: 0.25em 0;
        }
        .row a, .row div {
          flex: 1;
          white-space: nowrap;
          padding: 0 2px;
        }
        .row .counts {
          padding: 0 16px;
        }
        .row {
          display: flex;
          align-items: baseline;
          text-align: center;
          flex-direction: row;
        }
        @media (max-width: 960px) {
          :host {
            display: inline-block;
          }
        }
      `,
    ];
  }

  /** @override */
  render() {
    return html`
      <div class="row">
        <a href="${this.prevUrl}" ?hidden="${!this.prevUrl}" title="Prev" class="prev-url">
          &lsaquo; Prev
        </a>
        <div class="counts" ?hidden=${!this.totalCount}>
          ${this.currentIndex + 1} of ${this.totalCount}
        </div>
        <a href="${this.nextUrl}" ?hidden="${!this.nextUrl}" title="Next" class="next-url">
          Next &rsaquo;
        </a>
      </div>
      <div class="row">
        <a href="${this.listUrl}" ?hidden="${!this.listUrl}" title="Back to list" class="list-url">
          Back to list
        </a>
      </div>
    `;
  }
}

window.customElements.define('mr-flipper', MrFlipper);
