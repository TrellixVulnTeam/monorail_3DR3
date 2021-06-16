// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import sinon from 'sinon';
import {assert} from 'chai';
import {prpcClient} from 'prpc-client-instance.js';
import {MrListPage, DEFAULT_ISSUES_PER_PAGE} from './mr-list-page.js';
import {store, resetState} from 'reducers/base.js';

let element;

describe('mr-list-page', () => {
  beforeEach(() => {
    store.dispatch(resetState());
    element = document.createElement('mr-list-page');
    document.body.appendChild(element);
    sinon.stub(prpcClient, 'call');
  });

  afterEach(() => {
    document.body.removeChild(element);
    prpcClient.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrListPage);
  });

  it('shows loading page when issues not loaded yet', async () => {
    element._issueListLoaded = false;

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.equal(loading.textContent.trim(), 'Loading...');
    assert.isNull(noIssues);
    assert.isNull(issueList);
  });

  it('does not clear existing issue list when loading new issues', async () => {
    element._fetchingIssueList = true;
    element._issueListLoaded = true;

    element.totalIssues = 1;
    element.issues = [{localId: 1, projectName: 'chromium'}];

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.isNull(loading);
    assert.isNull(noIssues);
    assert.isNotNull(issueList);
    // TODO(crbug.com/monorail/6560): We intend for the snackbar to be shown,
    // but it is hidden because the store thinks we have 0 total issues.
  });

  it('shows list when done loading', async () => {
    element._fetchingIssueList = false;
    element._issueListLoaded = true;

    element.totalIssues = 100;

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.isNull(loading);
    assert.isNull(noIssues);
    assert.isNotNull(issueList);
  });

  describe('issue loading snackbar', () => {
    beforeEach(() => {
      sinon.spy(store, 'dispatch');
    });

    afterEach(() => {
      store.dispatch.restore();
    });

    it('shows snackbar when loading new list of issues', async () => {
      sinon.stub(element, 'stateChanged');
      sinon.stub(element, '_showIssueLoadingSnackbar');

      element._fetchingIssueList = true;
      element.totalIssues = 1;
      element.issues = [{localId: 1, projectName: 'chromium'}];

      await element.updateComplete;

      sinon.assert.calledOnce(element._showIssueLoadingSnackbar);
    });

    it('hides snackbar when issues are done loading', async () => {
      element._fetchingIssueList = true;
      element.totalIssues = 1;
      element.issues = [{localId: 1, projectName: 'chromium'}];

      await element.updateComplete;

      sinon.assert.neverCalledWith(store.dispatch,
          {type: 'HIDE_SNACKBAR', id: 'FETCH_ISSUE_LIST'});

      element._fetchingIssueList = false;

      await element.updateComplete;

      sinon.assert.calledWith(store.dispatch,
          {type: 'HIDE_SNACKBAR', id: 'FETCH_ISSUE_LIST'});
    });

    it('hides snackbar when <mr-list-page> disconnects', async () => {
      document.body.removeChild(element);

      sinon.assert.calledWith(store.dispatch,
          {type: 'HIDE_SNACKBAR', id: 'FETCH_ISSUE_LIST'});

      document.body.appendChild(element);
    });

    it('shows snackbar on issue loading error', async () => {
      sinon.stub(element, 'stateChanged');
      sinon.stub(element, '_showIssueErrorSnackbar');

      element._fetchIssueListError = 'Something went wrong';

      await element.updateComplete;

      sinon.assert.calledWith(element._showIssueErrorSnackbar,
          'Something went wrong');
    });
  });

  it('shows no issues when no search results', async () => {
    element._fetchingIssueList = false;
    element._issueListLoaded = true;

    element.totalIssues = 0;
    element._queryParams = {q: 'owner:me'};

    await element.updateComplete;

    const loading = element.shadowRoot.querySelector('.container-loading');
    const noIssues = element.shadowRoot.querySelector('.container-no-issues');
    const issueList = element.shadowRoot.querySelector('mr-issue-list');

    assert.isNull(loading);
    assert.isNotNull(noIssues);
    assert.isNull(issueList);

    assert.equal(noIssues.querySelector('strong').textContent.trim(),
        'owner:me');
  });

  it('offers consider closed issues when no open results', async () => {
    element._fetchingIssueList = false;
    element._issueListLoaded = true;

    element.totalIssues = 0;
    element._queryParams = {q: 'owner:me', can: '2'};

    await element.updateComplete;

    const considerClosed = element.shadowRoot.querySelector('.consider-closed');

    assert.isFalse(considerClosed.hidden);

    element._queryParams = {q: 'owner:me', can: '1'};
    element._fetchingIssueList = false;
    element._issueListLoaded = true;

    await element.updateComplete;

    assert.isTrue(considerClosed.hidden);
  });

  it('refreshes when _queryParams.sort changes', async () => {
    sinon.stub(element, 'refresh');

    element._queryParams = {q: ''};
    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 1);

    element._queryParams = {q: '', colspec: 'Summary+ID'};

    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 1);

    element._queryParams = {q: '', sort: '-Summary'};
    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 2);

    element.refresh.restore();
  });

  it('refreshes when currentQuery changes', async () => {
    sinon.stub(element, 'refresh');

    element._queryParams = {q: ''};
    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 1);

    element.currentQuery = 'some query term';

    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 2);

    element.refresh.restore();
  });

  it('does not refresh when presentation config not fetched', async () => {
    sinon.stub(element, 'refresh');

    element._presentationConfigLoaded = false;
    element.currentQuery = 'some query term';

    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 0);

    element.refresh.restore();
  });

  it('refreshes if presentation config fetch finishes last', async () => {
    sinon.stub(element, 'refresh');

    element._presentationConfigLoaded = false;

    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 0);

    element._presentationConfigLoaded = true;
    element.currentQuery = 'some query term';

    await element.updateComplete;
    sinon.assert.callCount(element.refresh, 1);

    element.refresh.restore();
  });

  it('startIndex parses _queryParams for value', () => {
    // Default value.
    element._queryParams = {};
    assert.equal(element.startIndex, 0);

    // Int.
    element._queryParams = {start: 2};
    assert.equal(element.startIndex, 2);

    // String.
    element._queryParams = {start: '5'};
    assert.equal(element.startIndex, 5);

    // Negative value.
    element._queryParams = {start: -5};
    assert.equal(element.startIndex, 0);

    // NaN
    element._queryParams = {start: 'lol'};
    assert.equal(element.startIndex, 0);
  });

  it('maxItems parses _queryParams for value', () => {
    // Default value.
    element._queryParams = {};
    assert.equal(element.maxItems, DEFAULT_ISSUES_PER_PAGE);

    // Int.
    element._queryParams = {num: 50};
    assert.equal(element.maxItems, 50);

    // String.
    element._queryParams = {num: '33'};
    assert.equal(element.maxItems, 33);

    // NaN
    element._queryParams = {num: 'lol'};
    assert.equal(element.maxItems, DEFAULT_ISSUES_PER_PAGE);
  });

  it('parses groupby parameter correctly', () => {
    element._queryParams = {groupby: 'Priority+Status'};

    assert.deepEqual(element.groups,
        ['Priority', 'Status']);
  });

  it('groupby parsing preserves dashed parameters', () => {
    element._queryParams = {groupby: 'Priority+Custom-Status'};

    assert.deepEqual(element.groups,
        ['Priority', 'Custom-Status']);
  });

  describe('pagination', () => {
    beforeEach(() => {
      // Stop Redux from overriding values being tested.
      sinon.stub(element, 'stateChanged');
    });

    it('issue count hidden when no issues', async () => {
      element._queryParams = {num: 10, start: 0};
      element.totalIssues = 0;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.isTrue(count.hidden);
    });

    it('issue count renders on first page', async () => {
      element._queryParams = {num: 10, start: 0};
      element.totalIssues = 100;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '1 - 10 of 100');
    });

    it('issue count renders on middle page', async () => {
      element._queryParams = {num: 10, start: 50};
      element.totalIssues = 100;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '51 - 60 of 100');
    });

    it('issue count renders on last page', async () => {
      element._queryParams = {num: 10, start: 95};
      element.totalIssues = 100;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '96 - 100 of 100');
    });

    it('issue count renders on single page', async () => {
      element._queryParams = {num: 100, start: 0};
      element.totalIssues = 33;

      await element.updateComplete;

      const count = element.shadowRoot.querySelector('.issue-count');

      assert.equal(count.textContent.trim(), '1 - 33 of 33');
    });

    it('next and prev hidden on single page', async () => {
      element._queryParams = {num: 500, start: 0};
      element.totalIssues = 10;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNull(next);
      assert.isNull(prev);
    });

    it('prev hidden on first page', async () => {
      element._queryParams = {num: 10, start: 0};
      element.totalIssues = 30;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNotNull(next);
      assert.isNull(prev);
    });

    it('next hidden on last page', async () => {
      element._queryParams = {num: 10, start: 9};
      element.totalIssues = 5;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNull(next);
      assert.isNotNull(prev);
    });

    it('next and prev shown on middle page', async () => {
      element._queryParams = {num: 10, start: 50};
      element.totalIssues = 100;

      await element.updateComplete;

      const next = element.shadowRoot.querySelector('.next-link');
      const prev = element.shadowRoot.querySelector('.prev-link');

      assert.isNotNull(next);
      assert.isNotNull(prev);
    });
  });

  describe('edit actions', () => {
    beforeEach(() => {
      sinon.stub(window, 'alert');

      // Give the test user edit privileges.
      element._isLoggedIn = true;
      element._currentUser = {isSiteAdmin: true};
    });

    afterEach(() => {
      window.alert.restore();
    });

    it('edit actions hidden when user is logged out', async () => {
      element._isLoggedIn = false;

      await element.updateComplete;

      assert.isNull(element.shadowRoot.querySelector('mr-button-bar'));
    });

    it('edit actions hidden when user is not a project member', async () => {
      element._isLoggedIn = true;
      element._currentUser = {displayName: 'regular@user.com'};

      await element.updateComplete;

      assert.isNull(element.shadowRoot.querySelector('mr-button-bar'));
    });

    it('edit actions shown when user is a project member', async () => {
      element.projectName = 'chromium';
      element._isLoggedIn = true;
      element._currentUser = {isSiteAdmin: false, userId: '123'};
      element._usersProjects = new Map([['123', {ownerOf: ['chromium']}]]);

      await element.updateComplete;

      assert.isNotNull(element.shadowRoot.querySelector('mr-button-bar'));

      element.projectName = 'nonmember-project';
      await element.updateComplete;

      assert.isNull(element.shadowRoot.querySelector('mr-button-bar'));
    });

    it('edit actions shown when user is a site admin', async () => {
      element._isLoggedIn = true;
      element._currentUser = {isSiteAdmin: true};

      await element.updateComplete;

      assert.isNotNull(element.shadowRoot.querySelector('mr-button-bar'));
    });

    it('bulk edit stops when no issues selected', () => {
      element.selectedIssues = [];
      element.projectName = 'test';

      element.bulkEdit();

      sinon.assert.calledWith(window.alert,
          'Please select some issues to edit.');
    });

    it('bulk edit redirects to bulk edit page', () => {
      element.page = sinon.stub();
      element.selectedIssues = [
        {localId: 1},
        {localId: 2},
      ];
      element.projectName = 'test';

      element.bulkEdit();

      sinon.assert.calledWith(element.page,
          '/p/test/issues/bulkedit?ids=1%2C2');
    });

    it('flag issue as spam stops when no issues selected', () => {
      element.selectedIssues = [];

      element._flagIssues(true);

      sinon.assert.calledWith(window.alert,
          'Please select some issues to flag as spam.');
    });

    it('un-flag issue as spam stops when no issues selected', () => {
      element.selectedIssues = [];

      element._flagIssues(false);

      sinon.assert.calledWith(window.alert,
          'Please select some issues to un-flag as spam.');
    });

    it('flagging issues as spam sends pRPC request', async () => {
      element.page = sinon.stub();
      element.selectedIssues = [
        {localId: 1, projectName: 'test'},
        {localId: 2, projectName: 'test'},
      ];

      await element._flagIssues(true);

      sinon.assert.calledWith(prpcClient.call, 'monorail.Issues',
          'FlagIssues', {
            issueRefs: [
              {localId: 1, projectName: 'test'},
              {localId: 2, projectName: 'test'},
            ],
            flag: true,
          });
    });

    it('un-flagging issues as spam sends pRPC request', async () => {
      element.page = sinon.stub();
      element.selectedIssues = [
        {localId: 1, projectName: 'test'},
        {localId: 2, projectName: 'test'},
      ];

      await element._flagIssues(false);

      sinon.assert.calledWith(prpcClient.call, 'monorail.Issues',
          'FlagIssues', {
            issueRefs: [
              {localId: 1, projectName: 'test'},
              {localId: 2, projectName: 'test'},
            ],
            flag: false,
          });
    });

    it('clicking change columns opens dialog', async () => {
      await element.updateComplete;
      const dialog = element.shadowRoot.querySelector('mr-change-columns');
      sinon.stub(dialog, 'open');

      element.openColumnsDialog();

      sinon.assert.calledOnce(dialog.open);
    });

    it('add to hotlist stops when no issues selected', () => {
      element.selectedIssues = [];
      element.projectName = 'test';

      element.addToHotlist();

      sinon.assert.calledWith(window.alert,
          'Please select some issues to add to hotlists.');
    });

    it('add to hotlist dialog opens', async () => {
      element.selectedIssues = [
        {localId: 1, projectName: 'test'},
        {localId: 2, projectName: 'test'},
      ];
      element.projectName = 'test';

      await element.updateComplete;

      const dialog = element.shadowRoot.querySelector(
          'mr-update-issue-hotlists-dialog');

      sinon.stub(dialog, 'open');

      element.addToHotlist();

      sinon.assert.calledOnce(dialog.open);
    });

    it('hotlist update triggers snackbar', async () => {
      element.selectedIssues = [
        {localId: 1, projectName: 'test'},
        {localId: 2, projectName: 'test'},
      ];
      element.projectName = 'test';
      sinon.stub(element, '_showHotlistSaveSnackbar');

      await element.updateComplete;

      const dialog = element.shadowRoot.querySelector(
          'mr-update-issue-hotlists-dialog');

      element.addToHotlist();
      dialog.dispatchEvent(new Event('saveSuccess'));

      sinon.assert.calledOnce(element._showHotlistSaveSnackbar);
    });
  });
});
