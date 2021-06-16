// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {defaultMemoize} from 'reselect';

import {relativeTime}
  from 'elements/chops/chops-timestamp/chops-timestamp-helpers.js';
import {issueNameToRef, issueToName, userNameToId}
  from 'shared/convertersV0.js';
import {DEFAULT_ISSUE_FIELD_LIST} from 'shared/issue-fields.js';

import {store, connectStore} from 'reducers/base.js';
import * as hotlists from 'reducers/hotlists.js';
import * as projectV0 from 'reducers/projectV0.js';
import * as sitewide from 'reducers/sitewide.js';
import * as ui from 'reducers/ui.js';

import 'elements/chops/chops-filter-chips/chops-filter-chips.js';
import 'elements/framework/dialogs/mr-change-columns/mr-change-columns.js';
// eslint-disable-next-line max-len
import 'elements/framework/dialogs/mr-issue-hotlists-action/mr-move-issue-hotlists-dialog.js';
// eslint-disable-next-line max-len
import 'elements/framework/dialogs/mr-issue-hotlists-action/mr-update-issue-hotlists-dialog.js';
import 'elements/framework/mr-button-bar/mr-button-bar.js';
import 'elements/framework/mr-issue-list/mr-issue-list.js';
import 'elements/hotlist/mr-hotlist-header/mr-hotlist-header.js';

const DEFAULT_HOTLIST_FIELDS = Object.freeze([
  ...DEFAULT_ISSUE_FIELD_LIST,
  'Added',
  'Adder',
  'Rank',
]);

/** Hotlist Issues page */
export class _MrHotlistIssuesPage extends LitElement {
  /** @override */
  static get styles() {
    return css`
      :host {
        display: block;
      }
      p, div {
        margin: 16px 24px;
      }
      div {
        align-items: center;
        display: flex;
      }
      chops-filter-chips {
        margin-left: 6px;
      }
      mr-button-bar {
        margin: 16px 24px 8px 24px;
      }
    `;
  }

  /** @override */
  render() {
    return html`
      <mr-hotlist-header selected=0></mr-hotlist-header>
      ${this._hotlist ? this._renderPage() : 'Loading...'}
    `;
  }

  /**
   * @return {TemplateResult}
   */
  _renderPage() {
    // Memoize the issues passed to <mr-issue-list> so that
    // out property updates don't cause it to re-render.
    const items = _filterIssues(this._filter, this._items);

    const allProjectNamesEqual = items.length && items.every(
        (issue) => issue.projectName === items[0].projectName);
    const projectName = allProjectNamesEqual ? items[0].projectName : null;

    /** @type {HotlistV0} */
    // Populates <mr-update-issue-hotlists-dialog>' issueHotlists property.
    const hotlistV0 = {
      ownerRef: {userId: userNameToId(this._hotlist.owner)},
      name: this._hotlist.displayName,
    };

    const MAY_EDIT = this._permissions.includes(hotlists.ADMINISTER) ||
                     this._permissions.includes(hotlists.EDIT);
    // TODO(https://crbug.com/monorail/7776): The UI to allow reranking of
    // Issues should reflect user permissions.

    return html`
      <p>${this._hotlist.summary}</p>

      <div>
        Filter by Status
        <chops-filter-chips
            .options=${['Open', 'Closed']}
            .selected=${this._filter}
            @change=${this._onFilterChange}
        ></chops-filter-chips>
      </div>

      <mr-button-bar .items=${this._buttonBarItems()}></mr-button-bar>

      <mr-issue-list
        .issues=${items}
        .projectName=${projectName}
        .columns=${this._columns}
        .defaultFields=${DEFAULT_HOTLIST_FIELDS}
        .extractFieldValues=${this._extractFieldValues.bind(this)}
        .rerank=${this._rerankItems.bind(this)}
        ?selectionEnabled=${MAY_EDIT}
        @selectionChange=${this._onSelectionChange}
      ></mr-issue-list>

      <mr-change-columns .columns=${this._columns}></mr-change-columns>
      <mr-update-issue-hotlists-dialog
        .issueRefs=${this._selected.map(issueNameToRef)}
        .issueHotlists=${[hotlistV0]}
        @saveSuccess=${this._handleHotlistSaveSuccess}
      ></mr-update-issue-hotlists-dialog>
      <mr-move-issue-hotlists-dialog
        .issueRefs=${this._selected.map(issueNameToRef)}
        @saveSuccess=${this._handleHotlistSaveSuccess}
      ><mr-move-issue-hotlists-dialog>
    `;
  }

  /**
   * @return {Array<MenuItem>}
   */
  _buttonBarItems() {
    if (this._selected.length) {
      return [
        {
          icon: 'remove_circle_outline',
          text: 'Remove',
          handler: this._removeItems.bind(this)},
        {
          icon: 'edit',
          text: 'Update',
          handler: this._openUpdateIssuesHotlistsDialog.bind(this),
        },
        {
          icon: 'forward',
          text: 'Move to...',
          handler: this._openMoveToHotlistDialog.bind(this),
        },
      ];
    } else {
      return [
        // TODO(dtu): Implement this action.
        // {icon: 'add', text: 'Add issues'},
        {
          icon: 'table_chart',
          text: 'Change columns',
          handler: this._openColumnsDialog.bind(this),
        },
      ];
    }
  }

  /** @override */
  static get properties() {
    return {
      // Populated from Redux.
      _hotlist: {type: Object},
      _permissions: {type: Array},
      _items: {type: Array},
      _columns: {type: Array},
      _issue: {type: Object},
      _extractFieldValuesFromIssue: {type: Object},

      // Populated from events.
      _filter: {type: Object},
      _selected: {type: Array},
    };
  };

  /** @override */
  constructor() {
    super();

    /** @type {?Hotlist} */
    this._hotlist = null;
    /** @type {Array<Permission>} */
    this._permissions = [];
    /** @type {Array<HotlistIssue>} */
    this._items = [];
    /** @type {Array<string>} */
    this._columns = [];
    /**
     * @param {Issue} _issue
     * @param {string} _fieldName
     * @return {Array<string>}
     */
    this._extractFieldValuesFromIssue = (_issue, _fieldName) => [];

    /** @type {Object<string, boolean>} */
    this._filter = {Open: true};

    /**
     * An array of selected Issue Names.
     * TODO(https://crbug.com/monorail/7440): Update typedef.
     * @type {Array<string>}
     */
    this._selected = [];
  }

  /**
   * @param {HotlistIssue} hotlistIssue
   * @param {string} fieldName
   * @return {Array<string>}
   */
  _extractFieldValues(hotlistIssue, fieldName) {
    switch (fieldName) {
      case 'Added':
        return [relativeTime(new Date(hotlistIssue.createTime))];
      case 'Adder':
        return [hotlistIssue.adder.displayName];
      case 'Rank':
        return [String(hotlistIssue.rank + 1)];
      default:
        return this._extractFieldValuesFromIssue(hotlistIssue, fieldName);
    }
  }

  /**
   * @param {Event} e A change event fired by <chops-filter-chips>.
   */
  _onFilterChange(e) {
    this._filter = e.target.selected;
  }

  /**
   * @param {CustomEvent} e A selectionChange event fired by <mr-issue-list>.
   */
  _onSelectionChange(e) {
    this._selected = e.target.selectedIssues.map(issueToName);
  }

  /** Opens a dialog to change the columns shown in the issue list. */
  _openColumnsDialog() {
    this.shadowRoot.querySelector('mr-change-columns').open();
  }

  /** Handles successfully saved Hotlist changes. */
  async _handleHotlistSaveSuccess() {}

  /** Removes items from the hotlist, dispatching an action to Redux. */
  async _removeItems() {}

  /** Opens a dialog to update attached Hotlists for selected Issues. */
  _openUpdateIssuesHotlistsDialog() {
    this.shadowRoot.querySelector('mr-update-issue-hotlists-dialog').open();
  }

  /** Opens a dialog to move selected Issues to desired Hotlist. */
  _openMoveToHotlistDialog() {
    this.shadowRoot.querySelector('mr-move-issue-hotlists-dialog').open();
  }
  /**
   * Reranks items in the hotlist, dispatching an action to Redux.
   * @param {Array<String>} items The names of the HotlistItems to move.
   * @param {number} index The index to insert the moved items.
   * @return {Promise<void>}
   */
  async _rerankItems(items, index) {}
};

/** Redux-connected version of _MrHotlistIssuesPage. */
export class MrHotlistIssuesPage extends connectStore(_MrHotlistIssuesPage) {
  /** @override */
  stateChanged(state) {
    this._hotlist = hotlists.viewedHotlist(state);
    this._permissions = hotlists.viewedHotlistPermissions(state);
    this._items = hotlists.viewedHotlistIssues(state);

    const hotlistColumns =
        this._hotlist && this._hotlist.defaultColumns.map((col) => col.column);
    this._columns = sitewide.currentColumns(state) || hotlistColumns;

    this._extractFieldValuesFromIssue =
      projectV0.extractFieldValuesFromIssue(state);
  }

  /** @override */
  updated(changedProperties) {
    if (changedProperties.has('_hotlist') && this._hotlist) {
      const pageTitle = `Issues - ${this._hotlist.displayName}`;
      store.dispatch(sitewide.setPageTitle(pageTitle));
      const headerTitle = `Hotlist ${this._hotlist.displayName}`;
      store.dispatch(sitewide.setHeaderTitle(headerTitle));
    }
  }

  /** @override */
  async _handleHotlistSaveSuccess() {
    const action = hotlists.fetchItems(this._hotlist.name);
    await store.dispatch(action);
    store.dispatch(ui.showSnackbar(ui.snackbarNames.UPDATE_HOTLISTS_SUCCESS,
        'Hotlists updated.'));
  }

  /** @override */
  async _removeItems() {
    const action = hotlists.removeItems(this._hotlist.name, this._selected);
    await store.dispatch(action);
  }

  /** @override */
  async _rerankItems(items, index) {
    // The index given from <mr-issue-list> includes only the items shown in
    // the list and excludes the items that are being moved. So, we need to
    // count the hidden items.
    let shownItems = 0;
    let hiddenItems = 0;
    for (let i = 0; shownItems < index && i < this._items.length; ++i) {
      const item = this._items[i];
      const isShown = _isShown(this._filter, item);
      if (!isShown) ++hiddenItems;
      if (isShown && !items.includes(item.name)) ++shownItems;
    }

    await store.dispatch(hotlists.rerankItems(
        this._hotlist.name, items, index + hiddenItems));
  }
};

const _filterIssues = defaultMemoize(
    /**
     * Filters an array of HotlistIssues based on a filter condition. Memoized.
     * @param {Object<string, boolean>} filter The types of issues to show.
     * @param {Array<HotlistIssue>} items A HotlistIssue to check.
     * @return {Array<HotlistIssue>}
     */
    (filter, items) => items.filter((item) => _isShown(filter, item)));

/**
 * Returns true iff the current filter includes the given HotlistIssue.
 * @param {Object<string, boolean>} filter The types of issues to show.
 * @param {HotlistIssue} item A HotlistIssue to check.
 * @return {boolean}
 */
function _isShown(filter, item) {
  return filter.Open && item.statusRef.meansOpen ||
      filter.Closed && !item.statusRef.meansOpen;
}

customElements.define('mr-hotlist-issues-page-base', _MrHotlistIssuesPage);
customElements.define('mr-hotlist-issues-page', MrHotlistIssuesPage);
