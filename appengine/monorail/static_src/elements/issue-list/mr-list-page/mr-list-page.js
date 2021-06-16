// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import qs from 'qs';
import {store, connectStore} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as projectV0 from 'reducers/projectV0.js';
import * as userV0 from 'reducers/userV0.js';
import * as sitewide from 'reducers/sitewide.js';
import * as ui from 'reducers/ui.js';
import {prpcClient} from 'prpc-client-instance.js';
import {DEFAULT_ISSUE_FIELD_LIST, parseColSpec} from 'shared/issue-fields.js';
import {
  shouldWaitForDefaultQuery,
  urlWithNewParams,
  userIsMember,
} from 'shared/helpers.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import 'elements/framework/dialogs/mr-change-columns/mr-change-columns.js';
// eslint-disable-next-line max-len
import 'elements/framework/dialogs/mr-issue-hotlists-action/mr-update-issue-hotlists-dialog.js';
import 'elements/framework/mr-button-bar/mr-button-bar.js';
import 'elements/framework/mr-dropdown/mr-dropdown.js';
import 'elements/framework/mr-issue-list/mr-issue-list.js';
import '../mr-mode-selector/mr-mode-selector.js';

export const DEFAULT_ISSUES_PER_PAGE = 100;
const PARAMS_THAT_TRIGGER_REFRESH = ['sort', 'groupby', 'num',
  'start'];
const SNACKBAR_LOADING = 'Loading issues...';

/**
 * `<mr-list-page>`
 *
 * Container page for the list view
 */
export class MrListPage extends connectStore(LitElement) {
  /** @override */
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: block;
          box-sizing: border-box;
          width: 100%;
          padding: 0.5em 8px;
        }
        .container-loading,
        .container-no-issues {
          width: 100%;
          box-sizing: border-box;
          padding: 0 8px;
          font-size: var(--chops-main-font-size);
        }
        .container-no-issues {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
        }
        .container-no-issues p {
          margin: 0.5em;
        }
        .no-issues-block {
          display: block;
          padding: 1em 16px;
          margin-top: 1em;
          flex-grow: 1;
          width: 300px;
          max-width: 100%;
          text-align: center;
          background: var(--chops-primary-accent-bg);
          border-radius: 8px;
          border-bottom: var(--chops-normal-border);
        }
        .no-issues-block[hidden] {
          display: none;
        }
        .list-controls {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          padding: 0.5em 0;
        }
        .right-controls {
          flex-grow: 0;
          display: flex;
          align-items: center;
          justify-content: flex-end;
        }
        .next-link, .prev-link {
          display: inline-block;
          margin: 0 8px;
        }
        mr-mode-selector {
          margin-left: 8px;
        }
      `,
    ];
  }

  /** @override */
  render() {
    const selectedRefs = this.selectedIssues.map(
        ({localId, projectName}) => ({localId, projectName}));

    return html`
      ${this._renderControls()}
      ${this._renderListBody()}
      <mr-update-issue-hotlists-dialog
        .issueRefs=${selectedRefs}
        @saveSuccess=${this._showHotlistSaveSnackbar}
      ></mr-update-issue-hotlists-dialog>
      <mr-change-columns
        .columns=${this.columns}
        .queryParams=${this._queryParams}
      ></mr-change-columns>
    `;
  }

  /**
   * @return {TemplateResult}
   */
  _renderListBody() {
    if (!this._issueListLoaded) {
      return html`
        <div class="container-loading">
          Loading...
        </div>
      `;
    } else if (!this.totalIssues) {
      return html`
        <div class="container-no-issues">
          <p>
            The search query:
          </p>
          <strong>${this._queryParams.q}</strong>
          <p>
            did not generate any results.
          </p>
          <div class="no-issues-block">
            Type a new query in the search box above
          </div>
          <a
            href=${this._urlWithNewParams({can: 2, q: ''})}
            class="no-issues-block view-all-open"
          >
            View all open issues
          </a>
          <a
            href=${this._urlWithNewParams({can: 1})}
            class="no-issues-block consider-closed"
            ?hidden=${this._queryParams.can === '1'}
          >
            Consider closed issues
          </a>
        </div>
      `;
    }

    return html`
      <mr-issue-list
        .issues=${this.issues}
        .projectName=${this.projectName}
        .queryParams=${this._queryParams}
        .initialCursor=${this._queryParams.cursor}
        .currentQuery=${this.currentQuery}
        .currentCan=${this.currentCan}
        .columns=${this.columns}
        .defaultFields=${DEFAULT_ISSUE_FIELD_LIST}
        .extractFieldValues=${this._extractFieldValues}
        .groups=${this.groups}
        .userDisplayName=${this.userDisplayName}
        ?selectionEnabled=${this.editingEnabled}
        ?sortingAndGroupingEnabled=${true}
        ?starringEnabled=${this.starringEnabled}
        @selectionChange=${this._setSelectedIssues}
      ></mr-issue-list>
    `;
  }

  /**
   * @return {TemplateResult}
   */
  _renderControls() {
    const maxItems = this.maxItems;
    const startIndex = this.startIndex;
    const end = Math.min(startIndex + maxItems, this.totalIssues);
    const hasNext = end < this.totalIssues;
    const hasPrev = startIndex > 0;

    return html`
      <div class="list-controls">
        <div>
          ${this.editingEnabled ? html`
            <mr-button-bar .items=${this._actions}></mr-button-bar>
          ` : ''}
        </div>

        <div class="right-controls">
          ${hasPrev ? html`
            <a
              href=${this._urlWithNewParams({start: startIndex - maxItems})}
              class="prev-link"
            >
              &lsaquo; Prev
            </a>
          ` : ''}
          <div class="issue-count" ?hidden=${!this.totalIssues}>
            ${startIndex + 1} - ${end} of ${this.totalIssues}
          </div>
          ${hasNext ? html`
            <a
              href=${this._urlWithNewParams({start: startIndex + maxItems})}
              class="next-link"
            >
              Next &rsaquo;
            </a>
          ` : ''}
          <mr-mode-selector
            .projectName=${this.projectName}
            .queryParams=${this._queryParams}
            value="list"
          ></mr-mode-selector>
        </div>
      </div>
    `;
  }

  /** @override */
  static get properties() {
    return {
      issues: {type: Array},
      totalIssues: {type: Number},
      /** @private {Object} */
      _queryParams: {type: Object},
      projectName: {type: String},
      _fetchingIssueList: {type: Boolean},
      _issueListLoaded: {type: Boolean},
      selectedIssues: {type: Array},
      columns: {type: Array},
      userDisplayName: {type: String},
      /**
       * The current search string the user is querying for.
       */
      currentQuery: {type: String},
      /**
       * The current canned query the user is searching for.
       */
      currentCan: {type: String},
      /**
       * A function that takes in an issue and a field name and returns the
       * value for that field in the issue. This function accepts custom fields,
       * built in fields, and ad hoc fields computed from label prefixes.
       */
      _extractFieldValues: {type: Object},
      _isLoggedIn: {type: Boolean},
      _currentUser: {type: Object},
      _usersProjects: {type: Object},
      _fetchIssueListError: {type: String},
      _presentationConfigLoaded: {type: Boolean},
    };
  };

  /** @override */
  constructor() {
    super();
    this.issues = [];
    this._fetchingIssueList = false;
    this._issueListLoaded = false;
    this.selectedIssues = [];
    this._queryParams = {};
    this.columns = [];
    this._usersProjects = new Map();
    this._presentationConfigLoaded = false;

    this._boundRefresh = this.refresh.bind(this);

    this._actions = [
      {icon: 'edit', text: 'Bulk edit', handler: this.bulkEdit.bind(this)},
      {
        icon: 'add', text: 'Add to hotlist',
        handler: this.addToHotlist.bind(this),
      },
      {
        icon: 'table_chart', text: 'Change columns',
        handler: this.openColumnsDialog.bind(this),
      },
      {icon: 'more_vert', text: 'More actions...', items: [
        {text: 'Flag as spam', handler: () => this._flagIssues(true)},
        {text: 'Un-flag as spam', handler: () => this._flagIssues(false)},
      ]},
    ];

    /**
     * @param {Issue} _issue
     * @param {string} _fieldName
     * @return {Array<string>}
     */
    this._extractFieldValues = (_issue, _fieldName) => [];

    // Expose page.js for test stubbing.
    this.page = page;
  };

  /** @override */
  connectedCallback() {
    super.connectedCallback();

    window.addEventListener('refreshList', this._boundRefresh);

    // TODO(zhangtiff): Consider if we can make this page title more useful for
    // the list view.
    store.dispatch(sitewide.setPageTitle('Issues'));
  }

  /** @override */
  disconnectedCallback() {
    super.disconnectedCallback();

    window.removeEventListener('refreshList', this._boundRefresh);

    this._hideIssueLoadingSnackbar();
  }

  /** @override */
  updated(changedProperties) {
    if (changedProperties.has('_fetchingIssueList')) {
      const wasFetching = changedProperties.get('_fetchingIssueList');
      const isFetching = this._fetchingIssueList;
      // Show a snackbar if waiting for issues to load but only when there's
      // already a different, non-empty issue list loaded. This approach avoids
      // clearing the issue list for a loading screen.
      if (isFetching && this.totalIssues > 0) {
        this._showIssueLoadingSnackbar();
      }
      if (wasFetching && !isFetching) {
        this._hideIssueLoadingSnackbar();
      }
    }

    if (changedProperties.has('userDisplayName')) {
      store.dispatch(issueV0.fetchStarredIssues());
    }

    if (changedProperties.has('_fetchIssueListError') &&
        this._fetchIssueListError) {
      this._showIssueErrorSnackbar(this._fetchIssueListError);
    }

    const shouldRefresh = this._shouldRefresh(changedProperties);
    if (shouldRefresh) this.refresh();
  }

  /**
   * Considers if list-page should fetch ListIssues
   * @param {Map} changedProperties
   * @return {boolean}
   */
  _shouldRefresh(changedProperties) {
    const wait = shouldWaitForDefaultQuery(this._queryParams);
    if (wait && !this._presentationConfigLoaded) {
      return false;
    } else if (wait && this._presentationConfigLoaded &&
        changedProperties.has('_presentationConfigLoaded')) {
      return true;
    } else if (changedProperties.has('projectName') ||
          changedProperties.has('currentQuery') ||
          changedProperties.has('currentCan')) {
      return true;
    } else if (changedProperties.has('_queryParams')) {
      const oldParams = changedProperties.get('_queryParams') || {};

      const shouldRefresh = PARAMS_THAT_TRIGGER_REFRESH.some((param) => {
        const oldValue = oldParams[param];
        const newValue = this._queryParams[param];
        return oldValue !== newValue;
      });
      return shouldRefresh;
    }
    return false;
  }

  // TODO(crbug.com/monorail/6933): Remove the need for this wrapper.
  /** Dispatches a Redux action to show an issues loading snackbar.  */
  _showIssueLoadingSnackbar() {
    store.dispatch(ui.showSnackbar(ui.snackbarNames.FETCH_ISSUE_LIST,
        SNACKBAR_LOADING, 0));
  }

  /** Dispatches a Redux action to hide the issue loading snackbar.  */
  _hideIssueLoadingSnackbar() {
    store.dispatch(ui.hideSnackbar(ui.snackbarNames.FETCH_ISSUE_LIST));
  }

  /**
   * Shows a snackbar telling the user their issue loading failed.
   * @param {string} error The error to display.
   */
  _showIssueErrorSnackbar(error) {
    store.dispatch(ui.showSnackbar(ui.snackbarNames.FETCH_ISSUE_LIST_ERROR,
        error));
  }

  /**
   * Refreshes the list of issues show.
   */
  refresh() {
    store.dispatch(issueV0.fetchIssueList(this.projectName, {
      ...this._queryParams,
      q: this.currentQuery,
      can: this.currentCan,
      maxItems: this.maxItems,
      start: this.startIndex,
    }));
  }

  /** @override */
  stateChanged(state) {
    this.projectName = projectV0.viewedProjectName(state);
    this._isLoggedIn = userV0.isLoggedIn(state);
    this._currentUser = userV0.currentUser(state);
    this._usersProjects = userV0.projectsPerUser(state);

    this.issues = issueV0.issueList(state) || [];
    this.totalIssues = issueV0.totalIssues(state) || 0;
    this._fetchingIssueList = issueV0.requests(state).fetchIssueList.requesting;
    this._issueListLoaded = issueV0.issueListLoaded(state);

    const error = issueV0.requests(state).fetchIssueList.error;
    this._fetchIssueListError = error ? error.message : '';

    this.currentQuery = sitewide.currentQuery(state);
    this.currentCan = sitewide.currentCan(state);
    this.columns =
        sitewide.currentColumns(state) || projectV0.defaultColumns(state);

    this._queryParams = sitewide.queryParams(state);

    this._extractFieldValues = projectV0.extractFieldValuesFromIssue(state);
    this._presentationConfigLoaded =
      projectV0.viewedPresentationConfigLoaded(state);
  }

  /**
   * @return {boolean} Whether the user is able to star the issues in the list.
   */
  get starringEnabled() {
    return this._isLoggedIn;
  }

  /**
   * @return {boolean} Whether the user has permissions to edit the issues in
   *   the list.
   */
  get editingEnabled() {
    return this._isLoggedIn && (userIsMember(this._currentUser,
        this.projectName, this._usersProjects) ||
        this._currentUser.isSiteAdmin);
  }

  /**
   * @return {Array<string>} Array of columns to group by.
   */
  get groups() {
    return parseColSpec(this._queryParams.groupby);
  }

  /**
   * @return {number} Maximum number of issues to load for this query.
   */
  get maxItems() {
    return Number.parseInt(this._queryParams.num) || DEFAULT_ISSUES_PER_PAGE;
  }

  /**
   * @return {number} Number of issues to offset by, based on pagination.
   */
  get startIndex() {
    const num = Number.parseInt(this._queryParams.start) || 0;
    return Math.max(0, num);
  }

  /**
   * Computes the current URL of the page with updated queryParams.
   *
   * @param {Object} newParams keys and values to override existing parameters.
   * @return {string} the new URL.
   */
  _urlWithNewParams(newParams) {
    const baseUrl = `/p/${this.projectName}/issues/list`;
    return urlWithNewParams(baseUrl, this._queryParams, newParams);
  }

  /**
   * Shows the user an alert telling them their action won't work.
   * @param {string} action Text describing what you're trying to do.
   */
  noneSelectedAlert(action) {
    // TODO(zhangtiff): Replace this with a modal for a more modern feel.
    alert(`Please select some issues to ${action}.`);
  }

  /**
   * Opens the the column selector.
   */
  openColumnsDialog() {
    this.shadowRoot.querySelector('mr-change-columns').open();
  }

  /**
   * Opens a modal to add the selected issues to a hotlist.
   */
  addToHotlist() {
    const issues = this.selectedIssues;
    if (!issues || !issues.length) {
      this.noneSelectedAlert('add to hotlists');
      return;
    }
    this.shadowRoot.querySelector('mr-update-issue-hotlists-dialog').open();
  }

  /**
   * Redirects the user to the bulk edit page for the issues they've selected.
   */
  bulkEdit() {
    const issues = this.selectedIssues;
    if (!issues || !issues.length) {
      this.noneSelectedAlert('edit');
      return;
    }
    const params = {
      ids: issues.map((issue) => issue.localId).join(','),
      q: this._queryParams && this._queryParams.q,
    };
    this.page(`/p/${this.projectName}/issues/bulkedit?${qs.stringify(params)}`);
  }

  /** Shows user confirmation that their hotlist changes were saved. */
  _showHotlistSaveSnackbar() {
    store.dispatch(ui.showSnackbar(ui.snackbarNames.UPDATE_HOTLISTS_SUCCESS,
        'Hotlists updated.'));
  }

  /**
   * Flags the selected issues as spam.
   * @param {boolean} flagAsSpam If true, flag as spam. If false, unflag
   *   as spam.
   */
  async _flagIssues(flagAsSpam = true) {
    const issues = this.selectedIssues;
    if (!issues || !issues.length) {
      return this.noneSelectedAlert(
          `${flagAsSpam ? 'flag' : 'un-flag'} as spam`);
    }
    const refs = issues.map((issue) => ({
      localId: issue.localId,
      projectName: issue.projectName,
    }));

    // TODO(zhangtiff): Refactor this into a shared action creator and
    // display the error on the frontend.
    try {
      await prpcClient.call('monorail.Issues', 'FlagIssues', {
        issueRefs: refs,
        flag: flagAsSpam,
      });
      this.refresh();
    } catch (e) {
      console.error(e);
    }
  }

  /**
   * Syncs this component's selected issues with the child component's selected
   * issues.
   */
  _setSelectedIssues() {
    const issueListRef = this.shadowRoot.querySelector('mr-issue-list');
    if (!issueListRef) return;

    this.selectedIssues = issueListRef.selectedIssues;
  }
};
customElements.define('mr-list-page', MrListPage);
