// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {css} from 'lit-element';
import {MrDropdown} from 'elements/framework/mr-dropdown/mr-dropdown.js';
import page from 'page';
import qs from 'qs';
import {connectStore} from 'reducers/base.js';
import * as projectV0 from 'reducers/projectV0.js';
import * as sitewide from 'reducers/sitewide.js';
import {fieldTypes, fieldsForIssue} from 'shared/issue-fields.js';


/**
 * `<mr-show-columns-dropdown>`
 *
 * Issue list column options dropdown.
 *
 */
export class MrShowColumnsDropdown extends connectStore(MrDropdown) {
  /** @override */
  static get styles() {
    return [
      ...MrDropdown.styles,
      css`
        :host {
          font-weight: normal;
          color: var(--chops-link-color);
          --mr-dropdown-icon-color: var(--chops-link-color);
          --mr-dropdown-anchor-padding: 3px 8px;
          --mr-dropdown-anchor-font-weight: bold;
          --mr-dropdown-menu-min-width: 150px;
          --mr-dropdown-menu-font-size: var(--chops-main-font-size);
          --mr-dropdown-menu-icon-size: var(--chops-main-font-size);
          /* Because we're using a sticky header, we need to make sure the
           * dropdown cannot be taller than the screen. */
          --mr-dropdown-menu-max-height: 80vh;
          --mr-dropdown-menu-overflow: auto;
        }
      `,
    ];
  }
  /** @override */
  static get properties() {
    return {
      ...MrDropdown.properties,
      /**
       * Array of displayed columns.
       */
      columns: {type: Array},
      /**
       * Array of displayed issues.
       */
      issues: {type: Array},
      /**
       * Array of unique phase names to prepend to phase field columns.
       */
      // TODO(dtu): Delete after removing EZT hotlist issue list.
      phaseNames: {type: Array},
      /**
       * Array of built in fields that are available outside of project
       * configuration.
       */
      defaultFields: {type: Array},
      _fieldDefs: {type: Array},
      _labelPrefixFields: {type: Array},
      // TODO(zhangtiff): Delete this legacy integration after removing
      // the EZT issue list view.
      onHideColumn: {type: Object},
      onShowColumn: {type: Object},
    };
  }

  /** @override */
  constructor() {
    super();

    // Inherited from MrDropdown.
    this.label = 'Show columns';
    this.icon = 'more_horiz';

    this.columns = [];
    /** @type {Array<Issue>} */
    this.issues = [];
    this.phaseNames = [];
    this.defaultFields = [];

    // TODO(dtu): Delete after removing EZT hotlist issue list.
    this._fieldDefs = [];
    this._labelPrefixFields = [];

    this._queryParams = {};
    this._page = page;

    // TODO(zhangtiff): Delete this legacy integration after removing
    // the EZT issue list view.
    this.onHideColumn = null;
    this.onShowColumn = null;
  }

  /** @override */
  stateChanged(state) {
    this._fieldDefs = projectV0.fieldDefs(state) || [];
    this._labelPrefixFields = projectV0.labelPrefixFields(state) || [];
    this._queryParams = sitewide.queryParams(state);
  }

  /** @override */
  update(changedProperties) {
    if (this.issues.length) {
      this.items = this.columnOptions();
    } else {
      // TODO(dtu): Delete after removing EZT hotlist issue list.
      this.items = this.columnOptionsEzt(
          this.defaultFields, this._fieldDefs, this._labelPrefixFields,
          this.columns, this.phaseNames);
    }

    super.update(changedProperties);
  }

  /**
   * Computes the column options available in the list view based on Issues.
   * @return {Array<MenuItem>}
   */
  columnOptions() {
    const availableFields = new Set(this.defaultFields);
    this.issues.forEach((issue) => {
      fieldsForIssue(issue).forEach((field) => {
        availableFields.add(field);
      });
    });

    // Remove selected columns from available fields.
    this.columns.forEach((field) => availableFields.delete(field));
    const sortedFields = [...availableFields].sort();

    return [
      // Show selected options first.
      ...this.columns.map((field, i) => ({
        icon: 'check',
        text: field,
        handler: () => this._removeColumn(i),
      })),
      // Unselected options come next.
      ...sortedFields.map((field) => ({
        icon: '',
        text: field,
        handler: () => this._addColumn(field),
      })),
    ];
  }

  // TODO(dtu): Delete after removing EZT hotlist issue list.
  /**
   * Computes the column options available in the list view based on project
   * config data.
   * @param {Array<string>} defaultFields List of built in columns.
   * @param {Array<FieldDef>} fieldDefs List of custom fields configured in the
   *   viewed project.
   * @param {Array<string>} labelPrefixes List of available label prefixes for
   *   the current project config..
   * @param {Array<string>} selectedColumns List of columns the user is
   *   currently viewing.
   * @param {Array<string>} phaseNames All phase namws present in the currently
   *   viewed issue list.
   * @return {Array<MenuItem>}
   */
  columnOptionsEzt(defaultFields, fieldDefs, labelPrefixes, selectedColumns,
      phaseNames) {
    const selectedOptions = new Set(
        selectedColumns.map((col) => col.toLowerCase()));

    const availableFields = new Set();

    // Built-in, hard-coded fields like Owner, Status, and Labels.
    defaultFields.forEach((field) => this._addUnselectedField(
        availableFields, field, selectedOptions));

    // Custom fields.
    fieldDefs.forEach((fd) => {
      const {fieldRef, isPhaseField} = fd;
      const {fieldName, type} = fieldRef;
      if (isPhaseField) {
        // If the custom field belongs to phases, prefix the phase name for
        // each phase.
        phaseNames.forEach((phaseName) => {
          this._addUnselectedField(
              availableFields, `${phaseName}.${fieldName}`, selectedOptions);
        });
        return;
      }

      // TODO(zhangtiff): Prefix custom fields with "approvalName" defined by
      // the approval name after deprecating the old issue list page.

      // Most custom fields can be directly added to the list with no
      // modifications.
      this._addUnselectedField(
          availableFields, fieldName, selectedOptions);

      // If the custom field is type approval, then it also has a built in
      // "Approver" field.
      if (type === fieldTypes.APPROVAL_TYPE) {
        this._addUnselectedField(
            availableFields, `${fieldName}-Approver`, selectedOptions);
      }
    });

    // Fields inferred from label prefixes.
    labelPrefixes.forEach((field) => this._addUnselectedField(
        availableFields, field, selectedOptions));

    const sortedFields = [...availableFields];
    sortedFields.sort();

    return [
      ...selectedColumns.map((field, i) => ({
        icon: 'check',
        text: field,
        handler: () => this._removeColumn(i),
      })),
      ...sortedFields.map((field) => ({
        icon: '',
        text: field,
        handler: () => this._addColumn(field),
      })),
    ];
  }

  /**
   * Helper that mutates a Set of column names in place, adding a given
   * field only if it doesn't already show up in the list of selected
   * fields.
   * @param {Set<string>} availableFields Set of column names to mutate.
   * @param {string} field Name of the field being added to the options.
   * @param {Set<string>} selectedOptions Set of fieldNames that the user
   *   is viewing.
   * @private
   */
  _addUnselectedField(availableFields, field, selectedOptions) {
    if (!selectedOptions.has(field.toLowerCase())) {
      availableFields.add(field);
    }
  }

  /**
   * Removes the column at a particular index.
   *
   * @param {number} i the issue column to be removed.
   */
  _removeColumn(i) {
    if (this.onHideColumn) {
      if (!this.onHideColumn(this.columns[i])) {
        return;
      }
    }
    const columns = [...this.columns];
    columns.splice(i, 1);
    this._reloadColspec(columns);
  }

  /**
   * Adds a new column to a particular index.
   *
   * @param {string} name of the new column added.
   */
  _addColumn(name) {
    if (this.onShowColumn) {
      if (!this.onShowColumn(name)) {
        return;
      }
    }
    this._reloadColspec([...this.columns, name]);
  }

  /**
   * Reflects changes to the columns of an issue list to the URL, through
   * frontend routing.
   *
   * @param {Array} newColumns the new colspec to set in the URL.
   */
  _reloadColspec(newColumns) {
    this._updateQueryParams({colspec: newColumns.join(' ')});
  }

  /**
   * Navigates to the same URL as the current page, but with query
   * params updated.
   *
   * @param {Object} newParams keys and values of the queryParams
   * Object to be updated.
   */
  _updateQueryParams(newParams) {
    const params = {...this._queryParams, ...newParams};
    this._page(`${this._baseUrl()}?${qs.stringify(params)}`);
  }

  /**
   * Get the current URL of the page, without query params. Useful for
   * test stubbing.
   *
   * @return {string} the URL of the list page, without params.
   */
  _baseUrl() {
    return window.location.pathname;
  }
}

customElements.define('mr-show-columns-dropdown', MrShowColumnsDropdown);
