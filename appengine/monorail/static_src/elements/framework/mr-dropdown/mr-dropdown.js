// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {ifDefined} from 'lit-html/directives/if-defined';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import 'shared/typedef.js';

export const SCREENREADER_ATTRIBUTE_ERROR = `For screenreader support,
  mr-dropdown must always have either a label or a text property defined.`;

/**
 * `<mr-dropdown>`
 *
 * Dropdown menu for Monorail.
 *
 */
export class MrDropdown extends LitElement {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          position: relative;
          display: inline-block;
          height: 100%;
          font-size: inherit;
          font-family: var(--chops-font-family);
          --mr-dropdown-icon-color: var(--chops-primary-icon-color);
          --mr-dropdown-icon-font-size: var(--chops-icon-font-size);
          --mr-dropdown-anchor-font-weight: var(--chops-link-font-weight);
          --mr-dropdown-anchor-padding: 4px 0.25em;
          --mr-dropdown-anchor-justify-content: center;
          --mr-dropdown-menu-max-height: initial;
          --mr-dropdown-menu-overflow: initial;
          --mr-dropdown-menu-min-width: 120%;
          --mr-dropdown-menu-font-size: var(--chops-large-font-size);
          --mr-dropdown-menu-icon-size: var(--chops-icon-font-size);
        }
        :host([hidden]) {
          display: none;
          visibility: hidden;
        }
        :host(:not([opened])) .menu {
          display: none;
          visibility: hidden;
        }
        strong {
          font-size: var(--chops-large-font-size);
        }
        i.material-icons {
          font-size: var(--mr-dropdown-icon-font-size);
          display: inline-block;
          color: var(--mr-dropdown-icon-color);
          padding: 0 2px;
          box-sizing: border-box;
        }
        i.material-icons[hidden],
        .menu-item > i.material-icons[hidden] {
          display: none;
        }
        .menu-item > i.material-icons {
          display: block;
          font-size: var(--mr-dropdown-menu-icon-size);
          width: var(--mr-dropdown-menu-icon-size);
          height: var(--mr-dropdown-menu-icon-size);
          margin-right: 8px;
        }
        .anchor:disabled {
          color: var(--chops-button-disabled-color);
        }
        button.anchor {
          box-sizing: border-box;
          background: none;
          border: none;
          font-size: inherit;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: var(--mr-dropdown-anchor-justify-content);
          cursor: pointer;
          padding: var(--mr-dropdown-anchor-padding);
          color: var(--chops-link-color);
          font-weight: var(--mr-dropdown-anchor-font-weight);
          font-family: inherit;
        }
        /* menuAlignment options: right, left, side. */
        .menu.right {
          right: 0px;
        }
        .menu.left {
          left: 0px;
        }
        .menu.side {
          left: 100%;
          top: 0;
        }
        .menu {
          font-size: var(--mr-dropdown-menu-font-size);
          position: absolute;
          min-width: var(--mr-dropdown-menu-min-width);
          max-height: var(--mr-dropdown-menu-max-height);
          overflow: var(--mr-dropdown-menu-overflow);
          top: 90%;
          display: block;
          background: var(--chops-white);
          border: var(--chops-accessible-border);
          z-index: 990;
          box-shadow: 2px 3px 8px 0px hsla(0, 0%, 0%, 0.3);
          font-family: inherit;
        }
        .menu-item {
          background: none;
          margin: 0;
          border: 0;
          box-sizing: border-box;
          text-decoration: none;
          white-space: nowrap;
          display: flex;
          align-items: center;
          justify-content: left;
          width: 100%;
          padding: 0.25em 8px;
          transition: 0.2s background ease-in-out;

        }
        .menu-item[hidden] {
          display: none;
        }
        mr-dropdown.menu-item {
          width: 100%;
          padding: 0;
          --mr-dropdown-anchor-padding: 0.25em 8px;
          --mr-dropdown-anchor-justify-content: space-between;
        }
        .menu hr {
          width: 96%;
          margin: 0 2%;
          border: 0;
          height: 1px;
          background: hsl(0, 0%, 80%);
        }
        .menu a {
          cursor: pointer;
          color: var(--chops-link-color);
        }
        .menu a:hover, .menu a:focus {
          background: var(--chops-active-choice-bg);
        }
      `,
    ];
  }

  /** @override */
  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <button class="anchor"
        @click=${this.toggle}
        @keydown=${this._exitMenuOnEsc}
        ?disabled=${this.disabled}
        title=${this.title || this.label}
        aria-label=${this.label}
        aria-expanded=${this.opened}
      >
        ${this.text}
        <i class="material-icons" aria-hidden="true">${this.icon}</i>
      </button>
      <div class="menu ${this.menuAlignment}">
        ${this.items.map((item, index) => this._renderItem(item, index))}
        <slot></slot>
      </div>
    `;
  }

  /**
   * Render a single dropdown menu item.
   * @param {MenuItem} item
   * @param {number} index The item's position in the list of items.
   * @return {TemplateResult}
   */
  _renderItem(item, index) {
    if (item.separator) {
      // The menu item is a no-op divider between sections.
      return html`
        <strong ?hidden=${!item.text} class="menu-item">
          ${item.text}
        </strong>
        <hr />
      `;
    }
    if (item.items && item.items.length) {
      // The menu contains a sub-menu.
      return html`
        <mr-dropdown
          .text=${item.text}
          .items=${item.items}
          menuAlignment="side"
          icon="arrow_right"
          data-idx=${index}
          class="menu-item"
        ></mr-dropdown>
      `;
    }

    return html`
      <a
        href=${ifDefined(item.url)}
        @click=${this._runItemHandler}
        @keydown=${this._onItemKeydown}
        data-idx=${index}
        tabindex="0"
        class="menu-item"
      >
        <i
          class="material-icons"
          ?hidden=${item.icon === undefined}
        >${item.icon}</i>
        ${item.text}
      </a>
    `;
  }

  /** @override */
  constructor() {
    super();

    this.label = '';
    this.text = '';
    this.items = [];
    this.icon = 'arrow_drop_down';
    this.menuAlignment = 'right';
    this.opened = false;
    this.disabled = false;

    this._boundCloseOnOutsideClick = this._closeOnOutsideClick.bind(this);
  }

  /** @override */
  static get properties() {
    return {
      title: {type: String},
      label: {type: String},
      text: {type: String},
      items: {type: Array},
      icon: {type: String},
      menuAlignment: {type: String},
      opened: {type: Boolean, reflect: true},
      disabled: {type: Boolean},
    };
  }

  /**
   * Either runs the click handler attached to the clicked item and closes the
   * menu.
   * @param {MouseEvent|KeyboardEvent} e
   */
  _runItemHandler(e) {
    if (e instanceof MouseEvent || e.code === 'Enter') {
      const idx = e.target.dataset.idx;
      if (idx !== undefined && this.items[idx].handler) {
        this.items[idx].handler();
      }
      this.close();
    }
  }

  /**
   * Runs multiple event handlers when a user types a key while
   * focusing a menu item.
   * @param {KeyboardEvent} e
   */
  _onItemKeydown(e) {
    this._runItemHandler(e);
    this._exitMenuOnEsc(e);
  }

  /**
   * If the user types Esc while focusing any dropdown item, then
   * exit the dropdown.
   * @param {KeyboardEvent} e
   */
  _exitMenuOnEsc(e) {
    if (e.key === 'Escape') {
      this.close();

      // Return focus to the anchor of the dropdown on closing, so that
      // users don't lose their overall focus position within the page.
      const anchor = this.shadowRoot.querySelector('.anchor');
      anchor.focus();
    }
  }

  /** @override */
  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('click', this._boundCloseOnOutsideClick, true);
  }

  /** @override */
  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('click', this._boundCloseOnOutsideClick, true);
  }

  /** @override */
  updated(changedProperties) {
    if (changedProperties.has('label') || changedProperties.has('text')) {
      if (!this.label && !this.text) {
        console.error(SCREENREADER_ATTRIBUTE_ERROR);
      }
    }
  }

  /**
   * Closes and opens the dropdown menu.
   */
  toggle() {
    this.opened = !this.opened;
  }

  /**
   * Opens the dropdown menu.
   */
  open() {
    this.opened = true;
  }

  /**
   * Closes the dropdown menu.
   */
  close() {
    this.opened = false;
  }

  /**
   * Click a specific item in mr-dropdown, using JavaScript. Useful for testing.
   *
   * @param {number} i index of the item to click.
   */
  clickItem(i) {
    const items = this.shadowRoot.querySelectorAll('.menu-item');
    items[i].click();
  }

  /**
   * @param {MouseEvent} evt
   * @private
   */
  _closeOnOutsideClick(evt) {
    if (!this.opened) return;

    const hasMenu = evt.composedPath().find(
        (node) => {
          return node === this;
        },
    );
    if (hasMenu) return;

    this.close();
  }
}

customElements.define('mr-dropdown', MrDropdown);
