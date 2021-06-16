// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import page from 'page';
import {connectStore, store} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as sitewide from 'reducers/sitewide.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import 'elements/framework/links/mr-crbug-link/mr-crbug-link.js';
import 'elements/framework/mr-dropdown/mr-dropdown.js';
import 'elements/framework/mr-star-button/mr-star-button.js';
import {constructHref, prepareDataForDownload} from './list-to-csv-helpers.js';
import {
  issueRefToUrl,
  issueRefToString,
  issueStringToRef,
  issueToIssueRef,
  issueToIssueRefString,
  labelRefsToOneWordLabels,
} from 'shared/convertersV0.js';
import {isTextInput, findDeepEventTarget} from 'shared/dom-helpers.js';
import {
  urlWithNewParams,
  pluralize,
  setHasAny,
  objectValuesForKeys,
} from 'shared/helpers.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import {parseColSpec, EMPTY_FIELD_VALUE} from 'shared/issue-fields.js';
import './mr-show-columns-dropdown.js';

/**
 * Column to display name mapping dictionary
 * @type {Object<string, string>}
 */
const COLUMN_DISPLAY_NAMES = Object.freeze({
  'summary': 'Summary + Labels',
});

/** @const {number} Button property value of DOM click event */
const PRIMARY_BUTTON = 0;
/** @const {number} Button property value of DOM auxclick event */
const MIDDLE_BUTTON = 1;

/** @const {string} A short transition to ease movement of list items. */
const EASE_OUT_TRANSITION = 'transform 0.05s cubic-bezier(0, 0, 0.2, 1)';

/**
 * Really high cardinality attributes like ID and Summary are unlikely to be
 * useful if grouped, so it's better to just hide the option.
 * @const {Set<string>}
 */
const UNGROUPABLE_COLUMNS = new Set(['id', 'summary']);

/**
 * Columns that should render as issue links.
 * @const {Set<string>}
 */
const ISSUE_COLUMNS = new Set(['id', 'mergedinto', 'blockedon', 'blocking']);

/**
 * `<mr-issue-list>`
 *
 * A list of issues intended to be used in multiple contexts.
 * @extends {LitElement}
 */
export class MrIssueList extends connectStore(LitElement) {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: table;
          width: 100%;
          font-size: var(--chops-main-font-size);
        }
        .edit-widget-container {
          display: flex;
          flex-wrap: no-wrap;
          align-items: center;
        }
        mr-star-button {
          --mr-star-button-size: 18px;
          margin-bottom: 1px;
          margin-left: 4px;
        }
        input[type="checkbox"] {
          cursor: pointer;
          margin: 0 4px;
          width: 16px;
          height: 16px;
          border-radius: 2px;
          box-sizing: border-box;
          appearance: none;
          -webkit-appearance: none;
          border: 2px solid var(--chops-gray-400);
          position: relative;
          background: var(--chops-white);
        }
        th input[type="checkbox"] {
          border-color: var(--chops-gray-500);
        }
        input[type="checkbox"]:checked {
          background: var(--chops-primary-accent-color);
          border-color: var(--chops-primary-accent-color);
        }
        input[type="checkbox"]:checked::after {
          left: 1px;
          top: 2px;
          position: absolute;
          content: "";
          width: 8px;
          height: 4px;
          border: 2px solid white;
          border-right: none;
          border-top: none;
          transform: rotate(-45deg);
        }
        td, th.group-header {
          padding: 4px 8px;
          text-overflow: ellipsis;
          border-bottom: var(--chops-normal-border);
          cursor: pointer;
          font-weight: normal;
        }
        .group-header-content {
          height: 100%;
          width: 100%;
          align-items: center;
          display: flex;
        }
        th.group-header i.material-icons {
          font-size: var(--chops-icon-font-size);
          color: var(--chops-primary-icon-color);
          margin-right: 4px;
        }
        td.ignore-navigation {
          cursor: default;
        }
        th {
          background: var(--chops-table-header-bg);
          white-space: nowrap;
          text-align: left;
          z-index: 10;
          border-bottom: var(--chops-normal-border);
        }
        th.selection-header {
          padding: 3px 8px;
        }
        th > mr-dropdown, th > mr-show-columns-dropdown {
          font-weight: normal;
          color: var(--chops-link-color);
          --mr-dropdown-icon-color: var(--chops-link-color);
          --mr-dropdown-anchor-padding: 3px 8px;
          --mr-dropdown-anchor-font-weight: bold;
          --mr-dropdown-menu-min-width: 150px;
        }
        tr {
          padding: 0 8px;
        }
        tr[selected] {
          background: var(--chops-selected-bg);
        }
        td:first-child, th:first-child {
          border-left: 4px solid transparent;
        }
        tr[cursored] > td:first-child {
          border-left: 4px solid var(--chops-blue-700);
        }
        mr-crbug-link {
          /* We need the shortlink to be hidden but still accessible.
          * The opacity attribute visually hides a link while still
          * keeping it in the DOM.opacity. */
          --mr-crbug-link-opacity: 0;
          --mr-crbug-link-opacity-focused: 1;
        }
        td:hover > mr-crbug-link {
          --mr-crbug-link-opacity: 1;
        }
        .col-summary, .header-summary {
          /* Setting a table cell to 100% width makes it take up
          * all remaining space in the table, not the full width of
          * the table. */
          width: 100%;
        }
        .summary-label {
          display: inline-block;
          margin: 0 2px;
          color: var(--chops-green-800);
          text-decoration: none;
          font-size: 90%;
        }
        .summary-label:hover {
          text-decoration: underline;
        }
        td.draggable i {
          opacity: 0;
        }
        td.draggable {
          color: var(--chops-primary-icon-color);
          cursor: grab;
          padding-left: 0;
          padding-right: 0;
        }
        tr.dragged {
          opacity: 0.74;
        }
        tr:hover td.draggable i {
          opacity: 1;
        }
        .csv-download-container {
          border-bottom: none;
          text-align: end;
          cursor: default;
        }
        #hidden-data-link {
          display: none;
        }
        @media (min-width: 1024px) {
          .first-row th {
            position: sticky;
            top: var(--monorail-header-height);
          }
        }
      `,
    ];
  }

  /** @override */
  render() {
    const selectAllChecked = this._selectedIssues.size > 0;
    const checkboxLabel = `Select ${selectAllChecked ? 'None' : 'All'}`;

    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <thead>
        <tr class="first-row">
          ${this.rerank ? html`<th></th>` : ''}
          <th class="selection-header">
            <div class="edit-widget-container">
              ${this.selectionEnabled ? html`
                <input
                  class="select-all"
                  .checked=${selectAllChecked}
                  type="checkbox"
                  aria-label=${checkboxLabel}
                  title=${checkboxLabel}
                  @change=${this._selectAll}
                />
              ` : ''}
            </div>
          </th>
          ${this.columns.map((column, i) => this._renderHeader(column, i))}
          <th style="z-index: ${this.highestZIndex};">
            <mr-show-columns-dropdown
              title="Show columns"
              menuAlignment="right"
              .columns=${this.columns}
              .issues=${this.issues}
              .defaultFields=${this.defaultFields}
            ></mr-show-columns-dropdown>
          </th>
        </tr>
      </thead>
      <tbody>
        ${this._renderIssues()}
      </tbody>
      ${this.userDisplayName && html`
        <tfoot><tr><td colspan=999 class="csv-download-container">
          <a id="download-link" aria-label="Download page as CSV"
              @click=${this._downloadCsv} href>CSV</a>
          <a id="hidden-data-link" download="${this.projectName}-issues.csv"
            href=${this._csvDataHref}></a>
        </td></tr></tfoot>
      `}
    `;
  }

  /**
   * @param {string} column
   * @param {number} i The index of the column in the table.
   * @return {TemplateResult} html for header for the i-th column.
   * @private
   */
  _renderHeader(column, i) {
    // zIndex is used to render the z-index property in descending order
    const zIndex = this.highestZIndex - i;
    const colKey = column.toLowerCase();
    const name = colKey in COLUMN_DISPLAY_NAMES ? COLUMN_DISPLAY_NAMES[colKey] :
      column;
    return html`
      <th style="z-index: ${zIndex};" class="header-${colKey}">
        <mr-dropdown
          class="dropdown-${colKey}"
          .text=${name}
          .items=${this._headerActions(column, i)}
          menuAlignment="left"
        ></mr-dropdown>
      </th>`;
  }

  /**
   * @param {string} column
   * @param {number} i The index of the column in the table.
   * @return {Array<Object>} Available actions for the column.
   * @private
   */
  _headerActions(column, i) {
    const columnKey = column.toLowerCase();

    const isGroupable = this.sortingAndGroupingEnabled &&
        !UNGROUPABLE_COLUMNS.has(columnKey);

    let showOnly = [];
    if (isGroupable) {
      const values = [...this._uniqueValuesByColumn.get(columnKey)];
      if (values.length) {
        showOnly = [{
          text: 'Show only',
          items: values.map((v) => ({
            text: v,
            handler: () => this.showOnly(column, v),
          })),
        }];
      }
    }
    const sortingActions = this.sortingAndGroupingEnabled ? [
      {
        text: 'Sort up',
        handler: () => this.updateSortSpec(column),
      },
      {
        text: 'Sort down',
        handler: () => this.updateSortSpec(column, true),
      },
    ] : [];
    const actions = [
      ...sortingActions,
      ...showOnly,
      {
        text: 'Hide column',
        handler: () => this.removeColumn(i),
      },
    ];
    if (isGroupable) {
      actions.push({
        text: 'Group rows',
        handler: () => this.addGroupBy(i),
      });
    }
    return actions;
  }

  /**
   * @return {TemplateResult}
   */
  _renderIssues() {
    // Keep track of all the groups that we've seen so far to create
    // group headers as needed.
    const {issues, groupedIssues} = this;

    if (groupedIssues) {
      // Make sure issues in groups are rendered with unique indices across
      // groups to make sure hot keys and the like still work.
      let indexOffset = 0;
      return html`${groupedIssues.map(({groupName, issues}) => {
        const template = html`
          ${this._renderGroup(groupName, issues, indexOffset)}
        `;
        indexOffset += issues.length;
        return template;
      })}`;
    }

    return html`
      ${issues.map((issue, i) => this._renderRow(issue, i))}
    `;
  }

  /**
   * @param {string} groupName
   * @param {Array<Issue>} issues
   * @param {number} iOffset
   * @return {TemplateResult}
   * @private
   */
  _renderGroup(groupName, issues, iOffset) {
    if (!this.groups.length) return html``;

    const count = issues.length;
    const groupKey = groupName.toLowerCase();
    const isHidden = this._hiddenGroups.has(groupKey);

    return html`
      <tr>
        <th
          class="group-header"
          colspan="${this.numColumns}"
          @click=${() => this._toggleGroup(groupKey)}
          aria-expanded=${(!isHidden).toString()}
        >
          <div class="group-header-content">
            <i
              class="material-icons"
              title=${isHidden ? 'Show' : 'Hide'}
            >${isHidden ? 'add' : 'remove'}</i>
            ${count} ${pluralize(count, 'issue')}: ${groupName}
          </div>
        </th>
      </tr>
      ${issues.map((issue, i) => this._renderRow(issue, iOffset + i, isHidden))}
    `;
  }

  /**
   * @param {string} groupKey Lowercase group key.
   * @private
   */
  _toggleGroup(groupKey) {
    if (this._hiddenGroups.has(groupKey)) {
      this._hiddenGroups.delete(groupKey);
    } else {
      this._hiddenGroups.add(groupKey);
    }

    // Lit-element's default hasChanged check does not notice when Sets mutate.
    this.requestUpdate('_hiddenGroups');
  }

  /**
   * @param {Issue} issue
   * @param {number} i Index within the list of issues
   * @param {boolean=} isHidden
   * @return {TemplateResult}
   */
  _renderRow(issue, i, isHidden = false) {
    const rowSelected = this._selectedIssues.has(issueRefToString(issue));
    const id = issueRefToString(issue);
    const cursorId = issueRefToString(this.cursor);
    const hasCursor = cursorId === id;
    const dragged = this._dragging && rowSelected;

    return html`
      <tr
        class="row-${i} list-row ${dragged ? 'dragged' : ''}"
        ?selected=${rowSelected}
        ?cursored=${hasCursor}
        ?hidden=${isHidden}
        data-issue-ref=${id}
        data-index=${i}
        data-name=${issue.name}
        @focus=${this._setRowAsCursorOnFocus}
        @click=${this._clickIssueRow}
        @auxclick=${this._clickIssueRow}
        @keydown=${this._keydownIssueRow}
        tabindex="0"
      >
        ${this.rerank ? html`
          <td class="draggable ignore-navigation"
              @mousedown=${this._onMouseDown}>
            <i class="material-icons" title="Drag issue">drag_indicator</i>
          </td>
        ` : ''}
        <td class="ignore-navigation">
          <div class="edit-widget-container">
            ${this.selectionEnabled ? html`
              <input
                class="issue-checkbox"
                .value=${id}
                .checked=${rowSelected}
                type="checkbox"
                data-index=${i}
                aria-label="Select Issue ${issue.localId}"
                @change=${this._selectIssue}
                @click=${this._selectIssueRange}
              />
            ` : ''}
            ${this.starringEnabled ? html`
              <mr-star-button
                .issueRef=${issueToIssueRef(issue)}
              ></mr-star-button>
            ` : ''}
          </div>
        </td>

        ${this.columns.map((column) => html`
          <td class="col-${column.toLowerCase()}">
            ${this._renderCell(column, issue)}
          </td>
        `)}

        <td>
          <mr-crbug-link .issue=${issue}></mr-crbug-link>
        </td>
      </tr>
    `;
  }

  /**
   * @param {string} column
   * @param {Issue} issue
   * @return {TemplateResult} Html for the given column for the given issue.
   * @private
   */
  _renderCell(column, issue) {
    const columnName = column.toLowerCase();
    if (columnName === 'summary') {
      return html`
        ${issue.summary}
        ${labelRefsToOneWordLabels(issue.labelRefs).map(({label}) => html`
          <a
            class="summary-label"
            href="${this._baseUrl()}?q=label%3A${label}"
          >${label}</a>
        `)}
      `;
    }
    const values = this.extractFieldValues(issue, column);

    if (!values.length) return EMPTY_FIELD_VALUE;

    // TODO(zhangtiff): Make this based on the "ISSUE" field type rather than a
    // hardcoded list of issue fields.
    if (ISSUE_COLUMNS.has(columnName)) {
      return values.map((issueRefString, i) => {
        const issue = this._issueForRefString(issueRefString, this.projectName);
        return html`
          <mr-issue-link
            .projectName=${this.projectName}
            .issue=${issue}
            .queryParams=${this._queryParams}
            short
          ></mr-issue-link>${values.length - 1 > i ? ', ' : ''}
        `;
      });
    }
    return values.join(', ');
  }

  /** @override */
  static get properties() {
    return {
      /**
       * Array of columns to display.
       */
      columns: {type: Array},
      /**
       * Array of built in fields that are available outside of project
       * configuration.
       */
      defaultFields: {type: Array},
      /**
       * A function that takes in an issue and a field name and returns the
       * value for that field in the issue. This function accepts custom fields,
       * built in fields, and ad hoc fields computed from label prefixes.
       */
      extractFieldValues: {type: Object},
      /**
       * Array of columns that are used as groups for issues.
       */
      groups: {type: Array},
      /**
       * List of issues to display.
       */
      issues: {type: Array},
      /**
       * A Redux action creator that calls the API to rerank the issues
       * in the list. If set, reranking is enabled for this issue list.
       */
      rerank: {type: Object},
      /**
       * Whether issues should be selectable or not.
       */
      selectionEnabled: {type: Boolean},
      /**
       * Whether issues should be sortable and groupable or not. This will
       * change how column headers will be displayed. The ability to sort and
       * group are currently coupled.
       */
      sortingAndGroupingEnabled: {type: Boolean},
      /**
       * Whether to show issue starring or not.
       */
      starringEnabled: {type: Boolean},
      /**
       * Attribute set to make host element into a table for accessibility.
       * Do not override.
       */
      role: {
        type: String,
        reflect: true,
      },
      /**
       * A query representing the current set of matching issues in the issue
       * list. Does not necessarily match queryParams.q since queryParams.q can
       * be empty while currentQuery is set to a default project query.
       */
      currentQuery: {type: String},
      /**
       * Object containing URL parameters to be preserved when issue links are
       * clicked. This Object is only used for the purpose of preserving query
       * parameters across links, not for the purpose of evaluating the query
       * parameters themselves to get values like columns, sort, or q. This
       * separation is important because we don't want to tightly couple this
       * list component with a specific URL system.
       * @private
       */
      _queryParams: {type: Object},
      /**
       * The initial cursor that a list view uses. This attribute allows users
       * of the list component to specify and control the cursor. When the
       * initialCursor attribute updates, the list focuses the element specified
       * by the cursor.
       */
      initialCursor: {type: String},
      /**
       * Logged in user's display name
       */
      userDisplayName: {type: String},
      /**
       * IssueRef Object specifying which issue the user is currently focusing.
       */
      _localCursor: {type: Object},
      /**
       * Set of group keys that are currently hidden.
       */
      _hiddenGroups: {type: Object},
      /**
       * Set of all selected issues where each entry is an issue ref string.
       */
      _selectedIssues: {type: Object},
      /**
       * List of unique phase names for all phases in issues.
       */
      _phaseNames: {type: Array},
      /**
       * True iff the user is dragging issues.
       */
      _dragging: {type: Boolean},
      /**
       * CSV data in data HREF format, used to download csv
       */
      _csvDataHref: {type: String},
      /**
       * Function to get a full Issue object for a given ref string.
       */
      _issueForRefString: {type: Object},
    };
  };

  /** @override */
  constructor() {
    super();
    /** @type {Array<Issue>} */
    this.issues = [];
    // TODO(jojwang): monorail:6336#c8, when ezt listissues page is fully
    // deprecated, remove phaseNames from mr-issue-list.
    this._phaseNames = [];
    /** @type {IssueRef} */
    this._localCursor;
    /** @type {IssueRefString} */
    this.initialCursor;
    /** @type {Set<IssueRefString>} */
    this._selectedIssues = new Set();
    /** @type {string} */
    this.projectName;
    /** @type {Object} */
    this._queryParams = {};
    /** @type {string} */
    this.currentQuery = '';
    /**
     * @param {Array<String>} items
     * @param {number} index
     * @return {Promise<void>}
     */
    this.rerank = null;
    /** @type {boolean} */
    this.selectionEnabled = false;
    /** @type {boolean} */
    this.sortingAndGroupingEnabled = false;
    /** @type {boolean} */
    this.starringEnabled = false;
    /** @type {Array} */
    this.columns = ['ID', 'Summary'];
    /** @type {Array<string>} */
    this.defaultFields = [];
    /** @type {Array} */
    this.groups = [];
    this.userDisplayName = '';
    /**
     * @type {string}
     * Role attribute set for accessibility. Do not override.
     */
    this.role = 'table';

    /** @type {function(KeyboardEvent): void} */
    this._boundRunListHotKeys = this._runListHotKeys.bind(this);
    /** @type {function(MouseEvent): void} */
    this._boundOnMouseMove = this._onMouseMove.bind(this);
    /** @type {function(MouseEvent): void} */
    this._boundOnMouseUp = this._onMouseUp.bind(this);

    /**
     * @param {Issue} _issue
     * @param {string} _fieldName
     * @return {Array<string>}
     */
    this.extractFieldValues = (_issue, _fieldName) => [];

    /**
     * @param {IssueRefString} _issueRefString
     * @param {string} projectName The currently viewed project.
     * @return {Issue}
     */
    this._issueForRefString = (_issueRefString, projectName) =>
      issueStringToRef(_issueRefString, projectName);

    this._hiddenGroups = new Set();

    this._starredIssues = new Set();
    this._fetchingStarredIssues = false;
    this._starringIssues = new Map();

    this._uniqueValuesByColumn = new Map();

    this._dragging = false;
    this._mouseX = null;
    this._mouseY = null;

    /** @type {number} */
    this._lastSelectedCheckbox = -1;

    // Expose page.js for stubbing.
    this._page = page;
    /** @type {string} page data in csv format as data href */
    this._csvDataHref = '';
  };

  /** @override */
  stateChanged(state) {
    this._starredIssues = issueV0.starredIssues(state);
    this._fetchingStarredIssues =
        issueV0.requests(state).fetchStarredIssues.requesting;
    this._starringIssues = issueV0.starringIssues(state);

    this._phaseNames = (issueV0.issueListPhaseNames(state) || []);
    this._queryParams = sitewide.queryParams(state);

    this._issueForRefString = issueV0.issueForRefString(state);
  }

  /** @override */
  firstUpdated() {
    // Only attach an event listener once the DOM has rendered.
    window.addEventListener('keydown', this._boundRunListHotKeys);
    this._dataLink = this.shadowRoot.querySelector('#hidden-data-link');
  }

  /** @override */
  disconnectedCallback() {
    super.disconnectedCallback();

    window.removeEventListener('keydown', this._boundRunListHotKeys);
  }

  /**
   * @override
   * @fires CustomEvent#selectionChange
   */
  update(changedProperties) {
    if (changedProperties.has('issues')) {
      // Clear selected issues to avoid an ever-growing Set size. In the future,
      // we may want to consider saving selections across issue reloads, though,
      // such as in the case or list refreshing.
      this._selectedIssues = new Set();
      this.dispatchEvent(new CustomEvent('selectionChange'));

      // Clear group toggle state when the list of issues changes to prevent an
      // ever-growing Set size.
      this._hiddenGroups = new Set();

      this._lastSelectedCheckbox = -1;
    }

    const valuesByColumnArgs = ['issues', 'columns', 'extractFieldValues'];
    if (setHasAny(changedProperties, valuesByColumnArgs)) {
      this._uniqueValuesByColumn = this._computeUniqueValuesByColumn(
          ...objectValuesForKeys(this, valuesByColumnArgs));
    }

    super.update(changedProperties);
  }

  /** @override */
  updated(changedProperties) {
    if (changedProperties.has('initialCursor')) {
      const ref = issueStringToRef(this.initialCursor, this.projectName);
      const row = this._getRowFromIssueRef(ref);
      if (row) {
        row.focus();
      }
    }
  }

  /**
   * Iterates through all issues in a list to sort unique values
   * across columns, for use in the "Show only" feature.
   * @param {Array} issues
   * @param {Array} columns
   * @param {function(Issue, string): Array<string>} fieldExtractor
   * @return {Map} Map where each entry has a String key for the
   *   lowercase column name and a Set value, continuing all values for
   *   that column.
   */
  _computeUniqueValuesByColumn(issues, columns, fieldExtractor) {
    const valueMap = new Map(
        columns.map((col) => [col.toLowerCase(), new Set()]));

    issues.forEach((issue) => {
      columns.forEach((col) => {
        const key = col.toLowerCase();
        const valueSet = valueMap.get(key);

        const values = fieldExtractor(issue, col);
        // Note: This allows multiple casings of the same values to be added
        // to the Set.
        values.forEach((v) => valueSet.add(v));
      });
    });
    return valueMap;
  }

  /**
   * Used for dynamically computing z-index to ensure column dropdowns overlap
   * properly.
   */
  get highestZIndex() {
    return this.columns.length + 10;
  }

  /**
   * The number of columns displayed in the table. This is the count of
   * customized columns + number of built in columns.
   */
  get numColumns() {
    return this.columns.length + 2;
  }

  /**
   * Sort issues into groups if groups are defined. The grouping feature is used
   * when the "groupby" URL parameter is set in the list view.
   */
  get groupedIssues() {
    if (!this.groups || !this.groups.length) return;

    const issuesByGroup = new Map();

    this.issues.forEach((issue) => {
      const groupName = this._groupNameForIssue(issue);
      const groupKey = groupName.toLowerCase();

      if (!issuesByGroup.has(groupKey)) {
        issuesByGroup.set(groupKey, {groupName, issues: [issue]});
      } else {
        const entry = issuesByGroup.get(groupKey);
        entry.issues.push(issue);
      }
    });
    return [...issuesByGroup.values()];
  }

  /**
   * The currently selected issue, with _localCursor overriding initialCursor.
   *
   * @return {IssueRef} The currently selected issue.
   */
  get cursor() {
    if (this._localCursor) {
      return this._localCursor;
    }
    if (this.initialCursor) {
      return issueStringToRef(this.initialCursor, this.projectName);
    }
    return {};
  }

  /**
   * Computes the name of the group that an issue belongs to. Issues are grouped
   * by fields that the user specifies and group names are generated using a
   * combination of an issue's field values for all specified groups.
   *
   * @param {Issue} issue
   * @return {string}
   */
  _groupNameForIssue(issue) {
    const groups = this.groups;
    const keyPieces = [];

    groups.forEach((group) => {
      const values = this.extractFieldValues(issue, group);
      if (!values.length) {
        keyPieces.push(`-has:${group}`);
      } else {
        values.forEach((v) => {
          keyPieces.push(`${group}=${v}`);
        });
      }
    });

    return keyPieces.join(' ');
  }

  /**
   * @return {Array<Issue>} Selected issues in the order they appear.
   */
  get selectedIssues() {
    return this.issues.filter((issue) =>
      this._selectedIssues.has(issueToIssueRefString(issue)));
  }

  /**
   * Update the search query to filter values matching a specific one.
   *
   * @param {string} column name of the column being filtered.
   * @param {string} value value of the field to filter by.
   */
  showOnly(column, value) {
    column = column.toLowerCase();

    // TODO(zhangtiff): Handle edge cases where column names are not
    // mapped directly to field names. For example, "AllLabels", should
    // query for "Labels".
    const querySegment = `${column}=${value}`;

    let query = this.currentQuery.trim();

    if (!query.includes(querySegment)) {
      query += ' ' + querySegment;

      this._updateQueryParams({q: query.trim()}, ['start']);
    }
  }

  /**
   * Update sort parameter in the URL based on user input.
   *
   * @param {string} column name of the column to be sorted.
   * @param {boolean} descending descending or ascending order.
   */
  updateSortSpec(column, descending = false) {
    column = column.toLowerCase();
    const oldSpec = this._queryParams.sort || '';
    const columns = parseColSpec(oldSpec.toLowerCase());

    // Remove any old instances of the same sort spec.
    const newSpec = columns.filter(
        (c) => c && c !== column && c !== `-${column}`);

    newSpec.unshift(`${descending ? '-' : ''}${column}`);

    this._updateQueryParams({sort: newSpec.join(' ')}, ['start']);
  }

  /**
   * Updates the groupby URL parameter to include a new column to group.
   *
   * @param {number} i index of the column to be grouped.
   */
  addGroupBy(i) {
    const groups = [...this.groups];
    const columns = [...this.columns];
    const groupedColumn = columns[i];
    columns.splice(i, 1);

    groups.unshift(groupedColumn);

    this._updateQueryParams({
      groupby: groups.join(' '),
      colspec: columns.join('+'),
    }, ['start']);
  }

  /**
   * Removes the column at a particular index.
   *
   * @param {number} i the issue column to be removed.
   */
  removeColumn(i) {
    const columns = [...this.columns];
    columns.splice(i, 1);
    this.reloadColspec(columns);
  }

  /**
   * Adds a new column to a particular index.
   *
   * @param {string} name of the new column added.
   */
  addColumn(name) {
    this.reloadColspec([...this.columns, name]);
  }

  /**
   * Reflects changes to the columns of an issue list to the URL, through
   * frontend routing.
   *
   * @param {Array} newColumns the new colspec to set in the URL.
   */
  reloadColspec(newColumns) {
    this._updateQueryParams({colspec: newColumns.join('+')});
  }

  /**
   * Navigates to the same URL as the current page, but with query
   * params updated.
   *
   * @param {Object} newParams keys and values of the queryParams
   * Object to be updated.
   * @param {Array} deletedParams keys to be cleared from queryParams.
   */
  _updateQueryParams(newParams = {}, deletedParams = []) {
    const url = urlWithNewParams(this._baseUrl(), this._queryParams, newParams,
        deletedParams);
    this._page(url);
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

  /**
   * Run issue list hot keys. This event handler needs to be bound globally
   * because a list cursor can be defined even when no element in the list is
   * focused.
   * @param {KeyboardEvent} e
   */
  _runListHotKeys(e) {
    if (!this.issues || !this.issues.length) return;
    const target = findDeepEventTarget(e);
    if (!target || isTextInput(target)) return;

    const key = e.key;

    const activeRow = this._getCursorElement();

    let i = -1;
    if (activeRow) {
      i = Number.parseInt(activeRow.dataset.index);

      const issue = this.issues[i];

      switch (key) {
        case 's': // Star focused issue.
          this._starIssue(issueToIssueRef(issue));
          return;
        case 'x': // Toggle selection of focused issue.
          const issueRefString = issueToIssueRefString(issue);
          this._updateSelectedIssues([issueRefString],
              !this._selectedIssues.has(issueRefString));
          return;
        case 'o': // Open current issue.
        case 'O': // Open current issue in new tab.
          this._navigateToIssue(issue, e.shiftKey);
          return;
      }
    }

    // Move up and down the issue list.
    // 'j' moves 'down'.
    // 'k' moves 'up'.
    if (key === 'j' || key === 'k') {
      if (key === 'j') { // Navigate down the list.
        i += 1;
        if (i >= this.issues.length) {
          i = 0;
        }
      } else if (key === 'k') { // Navigate up the list.
        i -= 1;
        if (i < 0) {
          i = this.issues.length - 1;
        }
      }

      const nextRow = this.shadowRoot.querySelector(`.row-${i}`);
      this._setRowAsCursor(nextRow);
    }
  }

  /**
   * @return {HTMLTableRowElement}
   */
  _getCursorElement() {
    const cursor = this.cursor;
    if (cursor) {
      // If there's a cursor set, use that instead of focus.
      return this._getRowFromIssueRef(cursor);
    }
    return;
  }

  /**
   * @param {FocusEvent} e
   */
  _setRowAsCursorOnFocus(e) {
    this._setRowAsCursor(/** @type {HTMLTableRowElement} */ (e.target));
  }

  /**
   *
   * @param {HTMLTableRowElement} row
   */
  _setRowAsCursor(row) {
    this._localCursor = issueStringToRef(row.dataset.issueRef,
        this.projectName);
    row.focus();
  }

  /**
   * @param {IssueRef} ref The issueRef to query for.
   * @return {HTMLTableRowElement}
   */
  _getRowFromIssueRef(ref) {
    return this.shadowRoot.querySelector(
        `.list-row[data-issue-ref="${issueRefToString(ref)}"]`);
  }

  /**
   * Returns an Array containing every <tr> in the list, excluding the header.
   * @return {Array<HTMLTableRowElement>}
   */
  _getRows() {
    return Array.from(this.shadowRoot.querySelectorAll('.list-row'));
  }

  /**
   * Returns an Array containing every selected <tr> in the list.
   * @return {Array<HTMLTableRowElement>}
   */
  _getSelectedRows() {
    return this._getRows().filter((row) => {
      return this._selectedIssues.has(row.dataset.issueRef);
    });
  }

  /**
   * @param {IssueRef} issueRef Issue to star
   */
  _starIssue(issueRef) {
    if (!this.starringEnabled) return;
    const issueKey = issueRefToString(issueRef);

    // TODO(zhangtiff): Find way to share star disabling logic more.
    const isStarring = this._starringIssues.has(issueKey) &&
      this._starringIssues.get(issueKey).requesting;
    const starEnabled = !this._fetchingStarredIssues && !isStarring;
    if (starEnabled) {
      const newIsStarred = !this._starredIssues.has(issueKey);
      this._starIssueInternal(issueRef, newIsStarred);
    }
  }

  /**
   * Wrap store.dispatch and issue.star, for testing.
   *
   * @param {IssueRef} issueRef the issue being starred.
   * @param {boolean} newIsStarred whether to star or unstar the issue.
   * @private
   */
  _starIssueInternal(issueRef, newIsStarred) {
    store.dispatch(issueV0.star(issueRef, newIsStarred));
  }
  /**
   * @param {Event} e
   * @fires CustomEvent#open-dialog
   * @private
   */
  _selectAll(e) {
    const checkbox = /** @type {HTMLInputElement} */ (e.target);

    if (checkbox.checked) {
      this._selectedIssues = new Set(this.issues.map(issueRefToString));
    } else {
      this._selectedIssues = new Set();
    }
    this.dispatchEvent(new CustomEvent('selectionChange'));
  }

  // TODO(zhangtiff): Implement Shift+Click to select a range of checkboxes
  // for the 'x' hot key.
  /**
   * @param {MouseEvent} e
   * @private
   */
  _selectIssueRange(e) {
    if (!this.selectionEnabled) return;

    const checkbox = /** @type {HTMLInputElement} */ (e.target);

    const index = Number.parseInt(checkbox.dataset.index);
    if (Number.isNaN(index)) {
      console.error('Issue checkbox has invalid data-index attribute.');
      return;
    }

    const lastIndex = this._lastSelectedCheckbox;
    if (e.shiftKey && lastIndex >= 0) {
      const newCheckedState = checkbox.checked;

      const start = Math.min(lastIndex, index);
      const end = Math.max(lastIndex, index) + 1;

      const updatedIssueKeys = this.issues.slice(start, end).map(
          issueToIssueRefString);
      this._updateSelectedIssues(updatedIssueKeys, newCheckedState);
    }

    this._lastSelectedCheckbox = index;
  }

  /**
   * @param {Event} e
   * @private
   */
  _selectIssue(e) {
    if (!this.selectionEnabled) return;

    const checkbox = /** @type {HTMLInputElement} */ (e.target);
    const issueKey = checkbox.value;

    this._updateSelectedIssues([issueKey], checkbox.checked);
  }

  /**
   * @param {Array<IssueRefString>} issueKeys Stringified issue refs.
   * @param {boolean} selected
   * @fires CustomEvent#selectionChange
   * @private
   */
  _updateSelectedIssues(issueKeys, selected) {
    let hasChanges = false;

    issueKeys.forEach((issueKey) => {
      const oldSelection = this._selectedIssues.has(issueKey);

      if (selected) {
        this._selectedIssues.add(issueKey);
      } else if (this._selectedIssues.has(issueKey)) {
        this._selectedIssues.delete(issueKey);
      }

      const newSelection = this._selectedIssues.has(issueKey);

      hasChanges = hasChanges || newSelection !== oldSelection;
    });


    if (hasChanges) {
      this.requestUpdate('_selectedIssues');
      this.dispatchEvent(new CustomEvent('selectionChange'));
    }
  }

  /**
   * Handles 'Enter' being pressed when a row is focused.
   * Note we install the 'Enter' listener on the row rather than the window so
   * 'Enter' behaves as expected when the focus is on other elements.
   *
   * @param {KeyboardEvent} e
   * @private
   */
  _keydownIssueRow(e) {
    if (e.key === 'Enter') {
      this._maybeOpenIssueRow(e);
    }
  }

  /**
   * Handles mouseDown to start drag events.
   * @param {MouseEvent} event
   * @private
   */
  _onMouseDown(event) {
    event.cancelable && event.preventDefault();

    this._mouseX = event.clientX;
    this._mouseY = event.clientY;

    this._setRowAsCursor(event.currentTarget.parentNode);
    this._startDrag();

    // We add the event listeners to window because the mouse can go out of the
    // bounds of the target element. window.mouseUp still triggers even if the
    // mouse is outside the browser window.
    window.addEventListener('mousemove', this._boundOnMouseMove);
    window.addEventListener('mouseup', this._boundOnMouseUp);
  }

  /**
   * Handles mouseMove to continue drag events.
   * @param {MouseEvent} event
   * @private
   */
  _onMouseMove(event) {
    event.cancelable && event.preventDefault();

    const x = event.clientX - this._mouseX;
    const y = event.clientY - this._mouseY;
    this._continueDrag(x, y);
  }

  /**
   * Handles mouseUp to end drag events.
   * @param {MouseEvent} event
   * @private
   */
  _onMouseUp(event) {
    event.cancelable && event.preventDefault();

    window.removeEventListener('mousemove', this._boundOnMouseMove);
    window.removeEventListener('mouseup', this._boundOnMouseUp);

    this._endDrag(event.clientY - this._mouseY);
  }

  /**
   * Gives a visual indicator that we've started dragging an issue row.
   * @private
   */
  _startDrag() {
    this._dragging = true;

    // If the dragged row is not selected, select it.
    // TODO(dtu): Allow dragging an existing selection for multi-drag.
    const issueRefString = issueRefToString(this.cursor);
    this._selectedIssues = new Set();
    this._updateSelectedIssues([issueRefString], true);
  }

  /**
   * @param {number} x The x-distance the cursor has moved since mouseDown.
   * @param {number} y The y-distance the cursor has moved since mouseDown.
   * @private
   */
  _continueDrag(x, y) {
    // Unselected rows: Transition them to their new positions.
    const [rows, initialIndex, finalIndex] = this._computeRerank(y);
    this._translateRows(rows, initialIndex, finalIndex);

    // Selected rows: Stick them to the cursor. No transition.
    for (const row of this._getSelectedRows()) {
      row.style.transform = `translate(${x}px, ${y}px`;
    };
  }

  /**
   * @param {number} y The y-distance the cursor has moved since mouseDown.
   * @private
   */
  async _endDrag(y) {
    this._dragging = false;

    // Unselected rows: Transition them to their new positions.
    const [rows, initialIndex, finalIndex] = this._computeRerank(y);
    const targetTranslation =
        this._translateRows(rows, initialIndex, finalIndex);

    // Selected rows: Transition them to their final positions
    // and reset their opacity.
    const selectedRows = this._getSelectedRows();
    for (const row of selectedRows) {
      row.style.transition = EASE_OUT_TRANSITION;
      row.style.transform = `translate(0px, ${targetTranslation}px)`;
    };

    // Submit the change.
    const items = selectedRows.map((row) => row.dataset.name);
    await this.rerank(items, finalIndex);

    // Reset the transforms.
    for (const row of this._getRows()) {
      row.style.transition = '';
      row.style.transform = '';
    };

    // Set the cursor to the new row.
    // In order to focus the correct element, we need the DOM to be in sync
    // with the issue list. We modified this.issues, so wait for a re-render.
    await this.updateComplete;
    const selector = `.list-row[data-index="${finalIndex}"]`;
    this.shadowRoot.querySelector(selector).focus();
  }

  /**
   * Computes the starting and ending indices of the cursor row,
   * given how far the mouse has been dragged in the y-direction.
   * The indices assume the cursor row has been removed from the list.
   * @param {number} y The y-distance the cursor has moved since mouseDown.
   * @return {[Array<HTMLTableRowElement>, number, number]} A tuple containing:
   *     An Array of table rows with the cursor row removed.
   *     The initial index of the cursor row.
   *     The final index of the cursor row.
   * @private
   */
  _computeRerank(y) {
    const row = this._getCursorElement();
    const rows = this._getRows();
    const listTop = row.parentNode.offsetTop;

    // Find the initial index of the cursor row.
    // TODO(dtu): If we support multi-drag, this should be the adjusted index of
    // the first selected row after collapsing spaces in the selected group.
    const initialIndex = rows.indexOf(row);
    rows.splice(initialIndex, 1);

    // Compute the initial and final y-positions of the top
    // of the cursor row relative to the top of the list.
    const initialY = row.offsetTop - listTop;
    const finalY = initialY + y;

    // Compute the final index of the cursor row.
    // The break points are the halfway marks of each row.
    let finalIndex = 0;
    for (finalIndex = 0; finalIndex < rows.length; ++finalIndex) {
      const rowTop = rows[finalIndex].offsetTop - listTop -
          (finalIndex >= initialIndex ? row.scrollHeight : 0);
      const breakpoint = rowTop + rows[finalIndex].scrollHeight / 2;
      if (breakpoint > finalY) {
        break;
      }
    }

    return [rows, initialIndex, finalIndex];
  }

  /**
   * @param {Array<HTMLTableRowElement>} rows Array of table rows with the
   *    cursor row removed.
   * @param {number} initialIndex The initial index of the cursor row.
   * @param {number} finalIndex The final index of the cursor row.
   * @return {number} The number of pixels the cursor row moved.
   * @private
   */
  _translateRows(rows, initialIndex, finalIndex) {
    const firstIndex = Math.min(initialIndex, finalIndex);
    const lastIndex = Math.max(initialIndex, finalIndex);

    const rowHeight = this._getCursorElement().scrollHeight;
    const translation = initialIndex < finalIndex ? -rowHeight : rowHeight;

    let targetTranslation = 0;
    for (let i = 0; i < rows.length; ++i) {
      rows[i].style.transition = EASE_OUT_TRANSITION;
      if (i >= firstIndex && i < lastIndex) {
        rows[i].style.transform = `translate(0px, ${translation}px)`;
        targetTranslation += rows[i].scrollHeight;
      } else {
        rows[i].style.transform = '';
      }
    }

    return initialIndex < finalIndex ? targetTranslation : -targetTranslation;
  }

  /**
   * Handle click and auxclick on issue row.
   * @param {MouseEvent} event
   * @private
   */
  _clickIssueRow(event) {
    if (event.button === PRIMARY_BUTTON || event.button === MIDDLE_BUTTON) {
      this._maybeOpenIssueRow(
          event, /* openNewTab= */ event.button === MIDDLE_BUTTON);
    }
  }

  /**
   * Checks that the given event should not be ignored, then navigates to the
   * issue associated with the row.
   *
   * @param {MouseEvent|KeyboardEvent} rowEvent A click or 'enter' on a row.
   * @param {boolean=} openNewTab Forces opening in a new tab
   * @private
   */
  _maybeOpenIssueRow(rowEvent, openNewTab = false) {
    const path = rowEvent.composedPath();
    const containsIgnoredElement = path.find(
        (node) => (node.tagName || '').toUpperCase() === 'A' ||
        (node.classList && node.classList.contains('ignore-navigation')));
    if (containsIgnoredElement) return;

    const row = /** @type {HTMLTableRowElement} */ (rowEvent.currentTarget);

    const i = Number.parseInt(row.dataset.index);

    if (i >= 0 && i < this.issues.length) {
      this._navigateToIssue(this.issues[i], openNewTab || rowEvent.metaKey ||
          rowEvent.ctrlKey);
    }
  }

  /**
   * @param {Issue} issue
   * @param {boolean} newTab
   * @private
   */
  _navigateToIssue(issue, newTab) {
    const link = issueRefToUrl(issueToIssueRef(issue),
        this._queryParams);

    if (newTab) {
      // Whether the link opens in a new tab or window is based on the
      // user's browser preferences.
      window.open(link, '_blank', 'noopener');
    } else {
      this._page(link);
    }
  }

  /**
   * Convert an issue's data into an array of strings, where the columns
   * match this.columns. Extracting data like _renderCell.
   * @param {Issue} issue
   * @return {Array<string>}
   * @private
   */
  _convertIssueToPlaintextArray(issue) {
    return this.columns.map((column) => {
      return this.extractFieldValues(issue, column).join(', ');
    });
  }

  /**
   * Convert each Issue into array of strings, where the columns
   * match this.columns.
   * @return {Array<Array<string>>}
   * @private
   */
  _convertIssuesToPlaintextArrays() {
    return this.issues.map(this._convertIssueToPlaintextArray.bind(this));
  }

  /**
   * Download content as csv. Conversion to CSV only on button click
   * instead of on data change because CSV download is not often used.
   * @param {MouseEvent} event
   * @private
   */
  async _downloadCsv(event) {
    event.preventDefault();

    if (this.userDisplayName) {
      // convert issues to array of arrays of strings
      const issueData = this._convertIssuesToPlaintextArrays();

      // convert the data into csv formatted string.
      const csvDataString = prepareDataForDownload(issueData, this.columns);

      // construct data href
      const href = constructHref(csvDataString);

      // modify a tag's href
      this._csvDataHref = href;
      await this.requestUpdate('_csvDataHref');

      // click to trigger download
      this._dataLink.click();

      // reset dataHref
      this._csvDataHref = '';
    }
  }
};

customElements.define('mr-issue-list', MrIssueList);
