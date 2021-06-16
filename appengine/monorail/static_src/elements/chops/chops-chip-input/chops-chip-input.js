// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import deepEqual from 'deep-equal';
import 'elements/chops/chops-chip/chops-chip.js';
import {immutableSplice} from 'shared/helpers.js';

const DELIMITER_REGEX = /[,;\s]+/;

/**
 * `<chops-chip-input>`
 *
 * A chip input.
 *
 */
export class ChopsChipInput extends LitElement {
  /** @override */
  static get styles() {
    return css`
      :host {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: flex-start;
        border-bottom: var(--chops-accessible-border);
        margin-botton: 2px;
      }
      :host([hidden]) {
        display: none;
      }
      :host([focused]) {
        border-bottom: 1px solid var(--chops-primary-accent-color);
      }
      .immutable {
        font-style: italic;
      }
      chops-chip {
        flex-grow: 0;
        flex-shrink: 0;
        margin: 4px 0;
        margin-right: 4px;
      }
      chops-chip[focusable] {
        cursor: pointer;
      }
      input {
        flex-grow: 1;
        border: 0;
        outline: none;
        /* Give inputs the same vertical sizing styles as chips. */
        padding: 0.1em 4px;
        line-height: 140%;
        margin: 0 2px;
        font-size: var(--chops-main-font-size);
      }
    `;
  }

  /** @override */
  render() {
    return html`
      ${this.immutableValues.map((value) => html`
        <chops-chip class="immutable" title="Derived: ${value}">
          ${value}
        </chops-chip>
      `)}
      ${this.values.map((value, i) => html`
        <input
          ?hidden=${i !== this.collapsedChipIndex}
          class="edit-value edit-value-${i}"
          part="edit-field"
          placeholder=${this.placeholder}
          data-ac-type=${this.acType}
          data-index=${i}
          aria-label="${this.name} input #${i}"
          autocomplete=${this.autocomplete}
          .value=${value}
          @keyup=${this._createChipsWhileTyping}
          @blur=${this._stopEditingChip}
          @focus=${this._changeFocus}
        />
        <chops-chip
          ?hidden=${i === this.collapsedChipIndex}
          class="chip-${i}"
          data-index=${i}
          aria-label="${this.name} value #${i} ${value}"
          role="button"
          buttonIcon="close"
          .buttonLabel="Remove ${this.name}"
          @click-button=${this._removeValue}
          @dblclick=${this._editChip}
          @keydown=${this._interactWithChips}
          @blur=${this._changeFocus}
          @focus=${this._changeFocus}
          focusable>${value}</chops-chip>
      `)}
      <input
        class="add-value"
        part="edit-field"
        placeholder=${this.placeholder}
        data-ac-type=${this.acType}
        data-index=${this.values.length}
        aria-label="${this.name} input #${this.values.length + 1}"
        autocomplete=${this.autocomplete}
        @keydown=${this._navigateByKeyboard}
        @keyup=${this._createChipsWhileTyping}
        @blur=${this._onBlur}
        @focus=${this._focusAddValue}
      />
    `;
  }

  /** @override */
  static get properties() {
    return {
      name: {type: String},
      immutableValues: {type: Array},
      initialValues: {
        type: Array,
        hasChanged(newVal, oldVal) {
          // Prevent extra recomputations of the same initial value cause
          // values to be reset.
          return !deepEqual(newVal, oldVal);
        },
      },
      values: {type: Array},
      // TODO(zhangtiff): Change autocomplete binding once Monorail's
      // autocomplete is rewritten.
      acType: {type: String},
      autocomplete: {type: String},
      placeholder: {type: String},
      focused: {
        type: Boolean,
        reflect: true,
      },
      collapsedChipIndex: {type: Number},
      delimiterRegex: {type: Object},
      undoStack: {type: Array},
      undoLimit: {type: Number},
      _addValueInput: {type: Object},
      _boundKeyDown: {type: Object},
    };
  }

  /** @override */
  constructor() {
    super();

    this.values = [];
    this.initialValues = [];
    this.immutableValues = [];

    this.delimiterRegex = DELIMITER_REGEX;
    this.collapsedChipIndex = -1;
    this.placeholder = 'Add value...';

    this.undoStack = [];
    this.undoLimit = 50;

    this._boundKeyDown = this._onKeyDown.bind(this);
  }

  /** @override */
  connectedCallback() {
    super.connectedCallback();

    window.addEventListener('keydown', this._boundKeyDown);
  }

  /** @override */
  disconnectedCallback() {
    super.disconnectedCallback();

    window.removeEventListener('keydown', this._boundKeyDown);
  }

  /** @override */
  firstUpdated() {
    this._addValueInput = this.shadowRoot.querySelector('.add-value');
  }

  /** @override */
  update(changedProperties) {
    if (changedProperties.has('initialValues')) {
      this.reset();
    }

    super.update(changedProperties);
  }

  /**
   * @override
   * @fires Event#change
   */
  updated(changedProperties) {
    if (changedProperties.has('values')) {
      this.dispatchEvent(new Event('change'));
    }
  }

  /**
   * Resets chips to default input values.
   */
  reset() {
    this.setValues(this.initialValues);
    this.undoStack = [];
  }

  /**
   * Focuses the chip input.
   */
  focus() {
    this._addValueInput.focus();
  }

  /**
   * Undos the last edit the user made.
   */
  undo() {
    if (!this.undoStack.length) return;

    const prevValues = this.undoStack.pop();

    // TODO(zhangtiff): Make undo work for values that aren't
    // chips yet as well.
    this.values = prevValues;
  }

  /**
   * Handles hot keys for chip inputs.
   * @param {KeyboardEvent} e
   * @private
   */
  _onKeyDown(e) {
    if (!this.focused) return;
    if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
      this.undo();
      e.preventDefault();
    }
  }

  /**
   * @return {Array<string>} All values in the chip input, including chips
   *   and non-chips.
   */
  getValues() {
    // Make sure to include any values that haven't yet been chipified as well.
    const newValues = this._readCollapsedValues(this._addValueInput);
    return this.values.concat(newValues);
  }

  /**
   * Updates the chip input with specified values.
   * @param {Array<string>} values
   */
  setValues(values) {
    this._saveValues(values);

    if (this._addValueInput) {
      this._addValueInput.value = '';
    }
  }

  /**
   * Helper function to handle updating the chip input's internal value store.
   * @param {Array<string>} values Values to save.
   * @private
   */
  _saveValues(values) {
    this.undoStack.push(this.values);

    if (this.undoStack.length > this.undoLimit) {
      this.undoStack.shift();
    }

    this.values = [...values];
  }

  /**
   * Event handler that fires when the user edits chips.
   * @param {Event} e
   * @private
   */
  async _editChip(e) {
    const target = e.target;
    const index = this._indexFromTarget(target);
    if (index < 0 || index >= this.values.length) return;

    this.collapsedChipIndex = index;

    await this.updateComplete;

    const input = this.shadowRoot.querySelector(`.edit-value-${index}`);

    const value = this.values[index];
    input.value = value;

    input.focus();
    input.select();

    this._triggerLegacyAutocomplete({target: input});
  }

  /**
   * Removes a chip, such as when the user clicks the "x" button
   * or types "Backspace".
   * @param {Event} e
   * @private
   */
  _removeValue(e) {
    const target = e.target;
    const index = Number.parseInt(target.dataset.index);
    if (index < 0 || index >= this.values.length) return;

    this._saveValues(immutableSplice(this.values, index, 1));
  }

  /**
   * Converts collapsed values back into chips once the user finishes editing.
   * @param {Event} e
   * @private
   */
  _stopEditingChip(e) {
    if (this.collapsedChipIndex < 0) return;
    const input = e.target;
    this._convertNewValuesToChips(input);
    this.collapsedChipIndex = -1;

    this._changeFocus();
  }

  /**
   * When the user leaves the chip input, update virtual focus and convert
   * collapsed values into chips.
   * @param {Event} e
   * @private
   */
  _onBlur(e) {
    this._convertNewValuesToChips(e.target);
    this._changeFocus();
  }

  /**
   * Turn collapsed values into chips as the user types given delimiters.
   * For example, if the user types a space, then a chip should be created
   * with any values from before that space.
   * @param {Event} e
   * @private
   */
  async _createChipsWhileTyping(e) {
    const input = e.target;
    if (input.value.match(this.delimiterRegex)) {
      this._convertNewValuesToChips(input);

      await this.updateComplete;
      if (!input.hidden) {
        this._triggerLegacyAutocomplete({target: input});
      }
    }
  }

  /**
   * Helper to turn collapsed input values into chips.
   * @param {HTMLInputElement} input
   * @private
   */
  async _convertNewValuesToChips(input) {
    const index = this._indexFromTarget(input);
    const values = this._readCollapsedValues(input);
    if (values.length) {
      this._saveValues(immutableSplice(
          this.values, index, 1, ...values));

      if (this.collapsedChipIndex === index) {
        this.collapsedChipIndex = -1;

        await this.updateComplete;

        const chip = this._getChipElement(index);

        if (chip) {
          chip.focus();
        }
      } else {
        input.value = '';
      }
    }
  }

  /**
   * Handles keeping virtual chip focus in sync as individual elements get
   * focused and unfocused. <chops-chip-input> maintains its own abstracted
   * out focus layer on top of native browser focus because we want to treat
   * the entire chip input as focused if any one input inside of
   * <chops-chip-input> is focused.
   * @fires CustomEvent#focus Event for when the user focuses the chip input.
   * @fires CustomEvent#blur Event for when the user stops focusing the
   *   chip inputs.
   * @private
   */
  _changeFocus() {
    // Check if any element in this shadowRoot is focused.
    const active = this.shadowRoot.activeElement;
    if (active) {
      this.focused = true;
      this.dispatchEvent(new CustomEvent('focus'));
    } else {
      this.focused = false;
      this.dispatchEvent(new CustomEvent('blur'));
    }
  }

  /**
   * Handles various keyboard shortcuts for chips.
   * @param {KeyboardEvent} e
   * @private
   */
  _interactWithChips(e) {
    const chip = e.target;
    const index = Number.parseInt(chip.dataset.index);
    if (index < 0 || index >= this.values.length) return;
    const input = this._addValueInput;

    if (e.key === 'Backspace') {
      // Delete the current chip then focus the one before it.
      this._saveValues(immutableSplice(this.values, index, 1));

      if (this.values.length > 0) {
        const chipBefore = this._getChipElement(Math.max(0, index - 1));
        chipBefore.focus();
      } else {
        // Move to the input if there are no chips left.
        input.focus();
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      const prevChip = this._getChipElement(index - 1);
      prevChip.focus();
    } else if (e.key === 'ArrowRight') {
      if (index >= this.values.length - 1) {
        // Move to the input if there are no chips to the right.
        input.focus();
      } else {
        const nextChip = this._getChipElement(index + 1);
        nextChip.focus();
      }
    } else if (e.key === 'Enter' || e.code === 'Space') {
      this._editChip(e);
      e.preventDefault();
    }
  }

  /**
   * Changes the user's location within the chip input based on keyboard
   * input. For example, the user can use the left and right arrow keys to
   * navigate between chips.
   * @param {KeyboardEvent} e
   * @private
   */
  _navigateByKeyboard(e) {
    // TODO(zhangtiff): Make keyboard navigation work for collapsed chips.
    const input = e.target;
    const atStartOfInput = input.selectionEnd === input.selectionStart
        && input.selectionStart === 0;
    const index = this._indexFromTarget(input);
    if (atStartOfInput) {
      if (e.key === 'Backspace') {
        // Delete the chip before this input.
        this._saveValues(immutableSplice(this.values,
            index - 1, 1));

        // Prevent autocomplete menu from opening.
        // TODO(zhangtiff): Remove this when reworking autocomplete as a
        // web component.
        e.stopPropagation();
      } else if (e.key === 'ArrowLeft' && index > 0) {
        const chipBefore = this._getChipElement(index - 1);
        chipBefore.focus();

        // Prevent autocomplete menu from opening.
        // TODO(zhangtiff): Remove this when reworking autocomplete as a
        // web component.
        e.stopPropagation();
      }
    }
  }

  /**
   * Helper to get the chip index of the element an event fired from.
   * @param {HTMLElement} target
   * @return {number}
   * @private
   */
  _indexFromTarget(target) {
    const index = Number.parseInt(target.dataset.index);
    return Number.isNaN(index) ? this.values.length : index;
  }

  /**
   * Gets the values a user has typed into an input,
   * delimited into chip values.
   * @param {HTMLInputElement} input
   * @return {Array<string>}
   * @private
   */
  _readCollapsedValues(input) {
    const values = input.value.split(this.delimiterRegex);

    // Filter out empty strings.
    const pieces = values.filter(Boolean);
    return pieces;
  }

  /**
   * Gets the HTML chip present at a given index.
   * @param {number} index
   * @return {HTMLElement}
   * @private
   */
  _getChipElement(index) {
    return this.shadowRoot.querySelector(`.chip-${index}`);
  }

  /**
   * Event handler for when the user focuses on the "add value" form.
   * @param {Event} e
   * @private
   */
  _focusAddValue(e) {
    this._triggerLegacyAutocomplete(e);
    this._changeFocus();
  }

  // TODO(zhangtiff): Delete this code once deprecating legacy autocomplete.
  // See: http://crbug.com/monorail/5301
  /**
   * Glue code for working with legacy autocomplete.
   * @param {Event} e
   */
  _triggerLegacyAutocomplete(e) {
    e.avoidValues = this.values.filter((val, i) =>
      i !== this.collapsedChipIndex);
    if (window.ac_keyevent_) {
      ac_keyevent_(e);
    }
  }
}

customElements.define('chops-chip-input', ChopsChipInput);
