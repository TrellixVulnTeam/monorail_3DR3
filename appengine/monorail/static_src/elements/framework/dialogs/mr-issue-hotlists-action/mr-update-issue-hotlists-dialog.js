// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {html, css} from 'lit-element';
import deepEqual from 'deep-equal';

import 'elements/chops/chops-checkbox/chops-checkbox.js';
import {store} from 'reducers/base.js';
import * as issueV0 from 'reducers/issueV0.js';
import * as userV0 from 'reducers/userV0.js';
import {prpcClient} from 'prpc-client-instance.js';
import {MrIssueHotlistsDialog} from './mr-issue-hotlists-dialog';

/**
 * `<mr-update-issue-hotlists-dialog>`
 *
 * Displays a dialog with the current hotlists's issues allowing the user to
 * update which hotlists the issues are a member of.
 */
export class MrUpdateIssueDialog extends MrIssueHotlistsDialog {
  /** @override */
  static get styles() {
    return [
      ...super.styles,
      css`
        input[type="checkbox"] {
          width: auto;
          height: auto;
        }
        button.toggle {
          background: none;
          color: hsl(240, 100%, 40%);
          border: 0;
          width: 100%;
          padding: 0.25em 0;
          text-align: left;
        }
        button.toggle:hover {
          cursor: pointer;
          text-decoration: underline;
        }
        label, chops-checkbox {
          display: flex;
          line-height: 200%;
          align-items: center;
          width: 100%;
          text-align: left;
          font-weight: normal;
          padding: 0.25em 8px;
          box-sizing: border-box;
        }
        label input[type="checkbox"] {
          margin-right: 8px;
        }
        .discard-button {
          margin-right: 16px;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
        .input-grid {
          align-items: center;
        }
        .input-grid > input {
          width: 200px;
          max-width: 100%;
        }
      `,
    ];
  }

  /** @override */
  renderHeader() {
    return html`
      <h3 class="medium-heading">Add issue to hotlists</h3>
    `;
  }

  /** @override */
  renderContent() {
    return html`
      ${this.renderFilter()}
      <form id="issueHotlistsForm">
        ${this.renderHotlists()}
        <h3 class="medium-heading">Create new hotlist</h3>
        <div class="input-grid">
          <label for="newHotlistName">New hotlist name:</label>
          <input type="text" name="newHotlistName">
        </div>
        ${this.renderError()}
        <div class="edit-actions">
          <chops-button
            class="de-emphasized discard-button"
            ?disabled=${this.disabled}
            @click=${this.discard}
          >
            Discard
          </chops-button>
          <chops-button
            class="emphasized"
            ?disabled=${this.disabled}
            @click=${this.save}
          >
            Save changes
          </chops-button>
        </div>
      </form>
    `;
  }

  /** @override */
  renderFilteredHotlist(hotlist) {
    return html`
      <chops-checkbox
        class="hotlist"
        title=${this._checkboxTitle(hotlist, this.issueHotlists)}
        data-hotlist-name="${hotlist.name}"
        ?checked=${this.hotlistsToAdd.has(hotlist.name)}
        @checked-change=${this._targetHotlistChecked}
      >
        ${hotlist.name}
      </chops-checkbox>`;
  }

  /** @override */
  static get properties() {
    return {
      ...super.properties,
      viewedIssueRef: {type: Object},
      issueHotlists: {type: Array},
      user: {type: Object},
      hotlistsToAdd: {
        type: Object,
        hasChanged(newVal, oldVal) {
          return !deepEqual(newVal, oldVal);
        },
      },
    };
  }

  /** @override */
  stateChanged(state) {
    super.stateChanged(state);
    this.viewedIssueRef = issueV0.viewedIssueRef(state);
    this.user = userV0.currentUser(state);
  }

  /** @override */
  constructor() {
    super();

    /** The list of Hotlists attached to the issueRefs. */
    this.issueHotlists = [];

    /** The Set of Hotlist names that the Issues will be added to. */
    this.hotlistsToAdd = this._initializeHotlistsToAdd();
  }

  /** @override */
  reset() {
    const form = this.shadowRoot.querySelector('#issueHotlistsForm');
    form.reset();
    // LitElement's hasChanged needs an assignment to verify Set objects.
    // https://lit-element.polymer-project.org/guide/properties#haschanged
    this.hotlistsToAdd = this._initializeHotlistsToAdd();
    super.reset();
  }

  /**
   * An alias to the close method.
   */
  discard() {
    this.close();
  }

  /**
   * Saves all changes that were found in the dialog and issues async requests
   * to update the issues.
   * @fires Event#saveSuccess
   */
  async save() {
    const changes = this.changes;
    const issueRefs = this.issueRefs;
    const viewedRef = this.viewedIssueRef;

    if (!issueRefs || !changes) return;

    // TODO(https://crbug.com/monorail/7778): Use action creators.
    const promises = [];
    if (changes.added && changes.added.length) {
      promises.push(prpcClient.call(
          'monorail.Features', 'AddIssuesToHotlists', {
            hotlistRefs: changes.added,
            issueRefs,
          },
      ));
    }
    if (changes.removed && changes.removed.length) {
      promises.push(prpcClient.call(
          'monorail.Features', 'RemoveIssuesFromHotlists', {
            hotlistRefs: changes.removed,
            issueRefs,
          },
      ));
    }
    if (changes.created) {
      promises.push(prpcClient.call(
          'monorail.Features', 'CreateHotlist', {
            name: changes.created.name,
            summary: changes.created.summary,
            issueRefs,
          },
      ));
    }

    try {
      await Promise.all(promises);

      // Refresh the viewed issue's hotlists only if there is a viewed issue.
      if (viewedRef) {
        const viewedIssueWasUpdated = issueRefs.find((ref) =>
          ref.projectName === viewedRef.projectName &&
          ref.localId === viewedRef.localId);
        if (viewedIssueWasUpdated) {
          store.dispatch(issueV0.fetchHotlists(viewedRef));
        }
      }
      store.dispatch(userV0.fetchHotlists({userId: this.user.userId}));
      this.dispatchEvent(new Event('saveSuccess'));
      this.close();
    } catch (error) {
      this.error = error.description;
    }
  }

  /**
   * Returns whether a given hotlist matches any of the given issue's hotlists.
   * @param {Hotlist} hotlist Hotlist to look for.
   * @param {Array<Hotlist>} issueHotlists Issue's hotlists to compare to.
   * @return {boolean}
   */
  _issueInHotlist(hotlist, issueHotlists) {
    return issueHotlists.some((issueHotlist) => {
      // TODO(https://crbug.com/monorail/7451): use `===`.
      return (hotlist.ownerRef.userId == issueHotlist.ownerRef.userId &&
        hotlist.name === issueHotlist.name);
    });
  }

  /**
   * Get a Set of Hotlists to add the Issues to based on the
   * Get the initial Set of Hotlists that Issues will be added to. Calculated
   * using userHotlists and issueHotlists.
   * @return {!Set<string>}
   */
  _initializeHotlistsToAdd() {
    const userHotlistsInIssueHotlists = this.userHotlists.reduce(
        (acc, hotlist) => {
          if (this._issueInHotlist(hotlist, this.issueHotlists)) {
            acc.push(hotlist.name);
          }
          return acc;
        }, []);
    return new Set(userHotlistsInIssueHotlists);
  }

  /**
   * Gets the checkbox title, depending on the checked state.
   * @param {boolean} isChecked Whether the input is checked.
   * @return {string}
   */
  _getCheckboxTitle(isChecked) {
    return (isChecked ? 'Remove issue from' : 'Add issue to') + ' this hotlist';
  }

  /**
   * The checkbox title for the issue, shown on hover and for a11y.
   * @param {Hotlist} hotlist Hotlist to look for.
   * @param {Array<Hotlist>} issueHotlists Issue's hotlists to compare to.
   * @return {string}
   */
  _checkboxTitle(hotlist, issueHotlists) {
    return this._getCheckboxTitle(this._issueInHotlist(hotlist, issueHotlists));
  }

  /**
   * Handles when the target Hotlist chops-checkbox has been checked.
   * @param {Event} e
   */
  _targetHotlistChecked(e) {
    const hotlistName = e.target.dataset.hotlistName;
    const currentHotlistsToAdd = new Set(this.hotlistsToAdd);
    if (hotlistName && e.detail.checked) {
      currentHotlistsToAdd.add(hotlistName);
    } else {
      currentHotlistsToAdd.delete(hotlistName);
    }
    // LitElement's hasChanged needs an assignment to verify Set objects.
    // https://lit-element.polymer-project.org/guide/properties#haschanged
    this.hotlistsToAdd = currentHotlistsToAdd;
    e.target.title = this._getCheckboxTitle(e.target.checked);
  }

  /**
   * Gets the changes between the added, removed, and created hotlists .
   */
  get changes() {
    const changes = {
      added: [],
      removed: [],
    };
    const form = this.shadowRoot.querySelector('#issueHotlistsForm');
    this.userHotlists.forEach((hotlist) => {
      const issueInHotlist = this._issueInHotlist(hotlist, this.issueHotlists);
      if (issueInHotlist && !this.hotlistsToAdd.has(hotlist.name)) {
        changes.removed.push({
          name: hotlist.name,
          owner: hotlist.ownerRef,
        });
      } else if (!issueInHotlist && this.hotlistsToAdd.has(hotlist.name)) {
        changes.added.push({
          name: hotlist.name,
          owner: hotlist.ownerRef,
        });
      }
    });
    if (form.newHotlistName.value) {
      changes.created = {
        name: form.newHotlistName.value,
        summary: 'Hotlist created from issue.',
      };
    }
    return changes;
  }
}

customElements.define('mr-update-issue-hotlists-dialog', MrUpdateIssueDialog);
