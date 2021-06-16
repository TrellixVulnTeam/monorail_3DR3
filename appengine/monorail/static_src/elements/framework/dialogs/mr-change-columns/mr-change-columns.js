// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import qs from 'qs';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import {parseColSpec} from 'shared/issue-fields.js';

/**
 * `<mr-change-columns>`
 *
 * Dialog where the user can change columns on the list view.
 *
 */
export class MrChangeColumns extends LitElement {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        .edit-actions {
          margin: 0.5em 0;
          text-align: right;
        }
        .input-grid {
          align-items: center;
          width: 800px;
          max-width: 100%;
        }
        input {
          box-sizing: border-box;
          padding: 0.25em 4px;
        }
      `,
    ];
  }

  /** @override */
  render() {
    return html`
      <chops-dialog closeOnOutsideClick>
        <h3 class="medium-heading">Change list columns</h3>
        <form id="changeColumns" @submit=${this._save}>
          <div class="input-grid">
            <label for="columnsInput">Columns: </label>
            <input
              id="columnsInput"
              placeholder="Edit columns..."
              value=${this.columns.join(' ')}
            />
          </div>
          <div class="edit-actions">
            <chops-button
              @click=${this.close}
              class="de-emphasized discard-button"
            >
              Discard
            </chops-button>
            <chops-button
              @click=${this._save}
              class="emphasized"
            >
              Update columns
            </chops-button>
          </div>
        </form>
      </chops-dialog>
    `;
  }

  /** @override */
  static get properties() {
    return {
      /**
       * Array of the currently configured issue columns, used to set
       * the default value.
       */
      columns: {type: Array},
      /**
       * Parsed query params for the current page, to be used in
       * navigation.
       */
      queryParams: {type: Object},
    };
  }

  /** @override */
  constructor() {
    super();

    this.columns = [];
    this.queryParams = {};

    this._page = page;
  }

  /**
   * Abstract out the computation of the current page. Useful for testing.
   */
  get _currentPage() {
    return window.location.pathname;
  }

  /** Updates the URL query params with the new columns. */
  save() {
    const input = this.shadowRoot.querySelector('#columnsInput');
    const newColumns = parseColSpec(input.value);

    const params = {...this.queryParams};
    params.colspec = newColumns.join('+');

    // TODO(zhangtiff): Create a shared function to change only
    // query params in a URL.
    this._page(`${this._currentPage}?${qs.stringify(params)}`);

    this.close();
  }

  /**
   * Handles form submit events.
   * @param {Event} e A click or submit event.
   */
  _save(e) {
    e.preventDefault();
    this.save();
  }

  /** Opens and resets this dialog. */
  open() {
    this.reset();
    const dialog = this.shadowRoot.querySelector('chops-dialog');
    dialog.open();
  }

  /** Closes this dialog. */
  close() {
    const dialog = this.shadowRoot.querySelector('chops-dialog');
    dialog.close();
  }

  /** Resets the form in this dialog. */
  reset() {
    this.shadowRoot.querySelector('form').reset();
  }
}

customElements.define('mr-change-columns', MrChangeColumns);
