// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

/**
 * `<chops-collapse>` displays a collapsible element.
 *
 */
export class ChopsCollapse extends LitElement {
  /** @override */
  static get properties() {
    return {
      opened: {
        type: Boolean,
        reflect: true,
      },
      ariaHidden: {
        attribute: 'aria-hidden',
        type: Boolean,
        reflect: true,
      },
    };
  }

  /** @override */
  static get styles() {
    return css`
      :host, :host([hidden]) {
        display: none;
      }
      :host([opened]) {
        display: block;
      }
    `;
  }

  /** @override */
  render() {
    return html`
      <slot></slot>
    `;
  }

  /** @override */
  constructor() {
    super();

    this.opened = false;
    this.ariaHidden = true;
  }

  /** @override */
  update(changedProperties) {
    if (changedProperties.has('opened')) {
      this.ariaHidden = !this.opened;
    }
    super.update(changedProperties);
  }
}
customElements.define('chops-collapse', ChopsCollapse);
