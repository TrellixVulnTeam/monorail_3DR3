// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import sinon from 'sinon';
import * as projectV0 from 'reducers/projectV0.js';
import {stringValuesForIssueField} from 'shared/issue-fields.js';
import {MrIssueList} from './mr-issue-list.js';

let element;

const listRowIsFocused = (element, i) => {
  const focused = element.shadowRoot.activeElement;
  assert.equal(focused.tagName.toUpperCase(), 'TR');
  assert.equal(focused.dataset.index, `${i}`);
};

describe('mr-issue-list', () => {
  beforeEach(() => {
    element = document.createElement('mr-issue-list');
    element.extractFieldValues = projectV0.extractFieldValuesFromIssue({});
    document.body.appendChild(element);

    sinon.stub(element, '_baseUrl').returns('/p/chromium/issues/list');
    sinon.stub(element, '_page');
    sinon.stub(window, 'open');
  });

  afterEach(() => {
    document.body.removeChild(element);
    window.open.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrIssueList);
  });

  it('issue summaries render', async () => {
    element.issues = [
      {summary: 'test issue'},
      {summary: 'I have a summary'},
    ];
    element.columns = ['Summary'];

    await element.updateComplete;

    const summaries = element.shadowRoot.querySelectorAll('.col-summary');

    assert.equal(summaries.length, 2);

    assert.equal(summaries[0].textContent.trim(), 'test issue');
    assert.equal(summaries[1].textContent.trim(), 'I have a summary');
  });

  it('one word labels render in summary column', async () => {
    element.issues = [
      {
        projectName: 'test',
        localId: 1,
        summary: 'test issue',
        labelRefs: [
          {label: 'ignore-multi-word-labels'},
          {label: 'Security'},
          {label: 'A11y'},
        ],
      },
    ];
    element.columns = ['Summary'];

    await element.updateComplete;

    const summary = element.shadowRoot.querySelector('.col-summary');
    const labels = summary.querySelectorAll('.summary-label');

    assert.equal(labels.length, 2);

    assert.equal(labels[0].textContent.trim(), 'Security');
    assert.include(labels[0].href,
        '/p/chromium/issues/list?q=label%3ASecurity');
    assert.equal(labels[1].textContent.trim(), 'A11y');
    assert.include(labels[1].href,
        '/p/chromium/issues/list?q=label%3AA11y');
  });

  it('blocking column renders issue links', async () => {
    element.issues = [
      {
        projectName: 'test',
        localId: 1,
        blockingIssueRefs: [
          {projectName: 'test', localId: 2},
          {projectName: 'test', localId: 3},
        ],
      },
    ];
    element.columns = ['Blocking'];

    await element.updateComplete;

    const blocking = element.shadowRoot.querySelector('.col-blocking');
    const link = blocking.querySelector('mr-issue-link');
    assert.equal(link.href, '/p/test/issues/detail?id=2');
  });

  it('blockedOn column renders issue links', async () => {
    element.issues = [
      {
        projectName: 'test',
        localId: 1,
        blockedOnIssueRefs: [{projectName: 'test', localId: 2}],
      },
    ];
    element.columns = ['BlockedOn'];

    await element.updateComplete;

    const blocking = element.shadowRoot.querySelector('.col-blockedon');
    const link = blocking.querySelector('mr-issue-link');
    assert.equal(link.href, '/p/test/issues/detail?id=2');
  });

  it('mergedInto column renders issue link', async () => {
    element.issues = [
      {
        projectName: 'test',
        localId: 1,
        mergedIntoIssueRef: {projectName: 'test', localId: 2},
      },
    ];
    element.columns = ['MergedInto'];

    await element.updateComplete;

    const blocking = element.shadowRoot.querySelector('.col-mergedinto');
    const link = blocking.querySelector('mr-issue-link');
    assert.equal(link.href, '/p/test/issues/detail?id=2');
  });

  it('clicking issue link does not trigger _navigateToIssue', async () => {
    sinon.stub(element, '_navigateToIssue');

    // Prevent the page from actually navigating on the link click.
    const clickIntercepter = sinon.spy((e) => {
      e.preventDefault();
    });
    window.addEventListener('click', clickIntercepter);

    element.issues = [
      {projectName: 'test', localId: 1, summary: 'test issue'},
      {projectName: 'test', localId: 2, summary: 'I have a summary'},
    ];
    element.columns = ['ID'];

    await element.updateComplete;

    const idLink = element.shadowRoot.querySelector('.col-id > mr-issue-link');

    idLink.click();

    sinon.assert.calledOnce(clickIntercepter);
    sinon.assert.notCalled(element._navigateToIssue);

    window.removeEventListener('click', clickIntercepter);
  });

  it('clicking issue row opens issue', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 22,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.click();

    sinon.assert.calledWith(element._page, '/p/chromium/issues/detail?id=22');
    sinon.assert.notCalled(window.open);
  });

  it('ctrl+click on row opens issue in new tab', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 24,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.dispatchEvent(new MouseEvent('click',
        {ctrlKey: true, bubbles: true}));

    sinon.assert.calledWith(window.open,
        '/p/chromium/issues/detail?id=24', '_blank', 'noopener');
  });

  it('meta+click on row opens issue in new tab', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 24,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.dispatchEvent(new MouseEvent('click',
        {metaKey: true, bubbles: true}));

    sinon.assert.calledWith(window.open,
        '/p/chromium/issues/detail?id=24', '_blank', 'noopener');
  });

  it('mouse wheel click on row opens issue in new tab', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 24,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.dispatchEvent(new MouseEvent('auxclick',
        {button: 1, bubbles: true}));

    sinon.assert.calledWith(window.open,
        '/p/chromium/issues/detail?id=24', '_blank', 'noopener');
  });

  it('right click on row does not navigate', async () => {
    element.issues = [{
      summary: 'click me',
      localId: 24,
      projectName: 'chromium',
    }];
    element.columns = ['Summary'];

    await element.updateComplete;

    const rowChild = element.shadowRoot.querySelector('.col-summary');
    rowChild.dispatchEvent(new MouseEvent('auxclick',
        {button: 2, bubbles: true}));

    sinon.assert.notCalled(window.open);
  });

  it('AllLabels column renders', async () => {
    element.issues = [
      {labelRefs: [{label: 'test'}, {label: 'hello-world'}]},
      {labelRefs: [{label: 'one-label'}]},
    ];

    element.columns = ['AllLabels'];

    await element.updateComplete;

    const labels = element.shadowRoot.querySelectorAll('.col-alllabels');

    assert.equal(labels.length, 2);

    assert.equal(labels[0].textContent.trim(), 'test, hello-world');
    assert.equal(labels[1].textContent.trim(), 'one-label');
  });

  it('issues sorted into groups when groups defined', async () => {
    element.issues = [
      {ownerRef: {displayName: 'test@example.com'}},
      {ownerRef: {displayName: 'test@example.com'}},
      {ownerRef: {displayName: 'other.user@example.com'}},
      {},
    ];

    element.columns = ['Owner'];
    element.groups = ['Owner'];

    await element.updateComplete;

    const owners = element.shadowRoot.querySelectorAll('.col-owner');
    assert.equal(owners.length, 4);

    const groupHeaders = element.shadowRoot.querySelectorAll(
        '.group-header');
    assert.equal(groupHeaders.length, 3);

    assert.include(groupHeaders[0].textContent,
        '2 issues: Owner=test@example.com');
    assert.include(groupHeaders[1].textContent,
        '1 issue: Owner=other.user@example.com');
    assert.include(groupHeaders[2].textContent, '1 issue: -has:Owner');
  });

  it('toggling group hides members', async () => {
    element.issues = [
      {ownerRef: {displayName: 'group1@example.com'}},
      {ownerRef: {displayName: 'group2@example.com'}},
    ];

    element.columns = ['Owner'];
    element.groups = ['Owner'];

    await element.updateComplete;

    const issueRows = element.shadowRoot.querySelectorAll('.list-row');
    assert.equal(issueRows.length, 2);

    assert.isFalse(issueRows[0].hidden);
    assert.isFalse(issueRows[1].hidden);

    const groupHeaders = element.shadowRoot.querySelectorAll(
        '.group-header');
    assert.equal(groupHeaders.length, 2);

    // Toggle first group hidden.
    groupHeaders[0].click();
    await element.updateComplete;

    assert.isTrue(issueRows[0].hidden);
    assert.isFalse(issueRows[1].hidden);
  });

  it('reloadColspec navigates to page with new colspec', () => {
    element.columns = ['ID', 'Summary'];
    element._queryParams = {};

    element.reloadColspec(['Summary', 'AllLabels']);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?colspec=Summary%2BAllLabels');
  });

  it('updateSortSpec navigates to page with new sort option', async () => {
    element.columns = ['ID', 'Summary'];
    element._queryParams = {};

    await element.updateComplete;

    element.updateSortSpec('Summary', true);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?sort=-summary');
  });

  it('updateSortSpec navigates to first page when on later page', async () => {
    element.columns = ['ID', 'Summary'];
    element._queryParams = {start: '100', q: 'owner:me'};

    await element.updateComplete;

    element.updateSortSpec('Summary', true);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?q=owner%3Ame&sort=-summary');
  });

  it('updateSortSpec prepends new option to existing sort', async () => {
    element.columns = ['ID', 'Summary', 'Owner'];
    element._queryParams = {sort: '-summary+owner'};

    await element.updateComplete;

    element.updateSortSpec('ID');

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?sort=id%20-summary%20owner');
  });

  it('updateSortSpec removes existing instances of sorted column', async () => {
    element.columns = ['ID', 'Summary', 'Owner'];
    element._queryParams = {sort: '-summary+owner+owner'};

    await element.updateComplete;

    element.updateSortSpec('Owner', true);

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?sort=-owner%20-summary');
  });

  it('_uniqueValuesByColumn re-computed when columns update', async () => {
    element.issues = [
      {id: 1, projectName: 'chromium'},
      {id: 2, projectName: 'chromium'},
      {id: 3, projectName: 'chrOmiUm'},
      {id: 1, projectName: 'other'},
    ];
    element.columns = [];
    await element.updateComplete;

    assert.deepEqual(element._uniqueValuesByColumn, new Map());

    element.columns = ['project'];
    await element.updateComplete;

    assert.deepEqual(element._uniqueValuesByColumn,
        new Map([['project', new Set(['chromium', 'chrOmiUm', 'other'])]]));
  });

  it('showOnly adds new search term to query', async () => {
    element.currentQuery = 'owner:me';
    element._queryParams = {};

    await element.updateComplete;

    element.showOnly('Priority', 'High');

    sinon.assert.calledWith(element._page,
        '/p/chromium/issues/list?q=owner%3Ame%20priority%3DHigh');
  });

  it('addColumn adds a column', () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'reloadColspec');

    element.addColumn('AllLabels');

    sinon.assert.calledWith(element.reloadColspec,
        ['ID', 'Summary', 'AllLabels']);
  });

  it('removeColumn removes a column', () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'reloadColspec');

    element.removeColumn(0);

    sinon.assert.calledWith(element.reloadColspec, ['Summary']);
  });

  it('clicking hide column in column header removes column', async () => {
    element.columns = ['ID', 'Summary'];

    sinon.stub(element, 'removeColumn');

    await element.updateComplete;

    const dropdown = element.shadowRoot.querySelector('.dropdown-summary');

    dropdown.clickItem(0); // Hide column.

    sinon.assert.calledWith(element.removeColumn, 1);
  });

  it('starring disabled when starringEnabled is false', async () => {
    element.starringEnabled = false;
    element.issues = [
      {projectName: 'test', localId: 1, summary: 'test issue'},
      {projectName: 'test', localId: 2, summary: 'I have a summary'},
    ];

    await element.updateComplete;

    let stars = element.shadowRoot.querySelectorAll('mr-star-button');
    assert.equal(stars.length, 0);

    element.starringEnabled = true;
    await element.updateComplete;

    stars = element.shadowRoot.querySelectorAll('mr-star-button');
    assert.equal(stars.length, 2);
  });

  describe('issue sorting and grouping enabled', () => {
    beforeEach(() => {
      element.sortingAndGroupingEnabled = true;
    });

    it('clicking sort up column header sets sort spec', async () => {
      element.columns = ['ID', 'Summary'];

      sinon.stub(element, 'updateSortSpec');

      await element.updateComplete;

      const dropdown = element.shadowRoot.querySelector('.dropdown-summary');

      dropdown.clickItem(0); // Sort up.

      sinon.assert.calledWith(element.updateSortSpec, 'Summary');
    });

    it('clicking sort down column header sets sort spec', async () => {
      element.columns = ['ID', 'Summary'];

      sinon.stub(element, 'updateSortSpec');

      await element.updateComplete;

      const dropdown = element.shadowRoot.querySelector('.dropdown-summary');

      dropdown.clickItem(1); // Sort down.

      sinon.assert.calledWith(element.updateSortSpec, 'Summary', true);
    });

    it('clicking group rows column header groups rows', async () => {
      element.columns = ['Owner', 'Priority'];
      element.groups = ['Status'];

      sinon.spy(element, 'addGroupBy');

      await element.updateComplete;

      const dropdown = element.shadowRoot.querySelector('.dropdown-owner');
      dropdown.clickItem(3); // Group rows.

      sinon.assert.calledWith(element.addGroupBy, 0);

      sinon.assert.calledWith(element._page,
          '/p/chromium/issues/list?groupby=Owner%20Status&colspec=Priority');
    });
  });

  describe('issue selection', () => {
    beforeEach(() => {
      element.selectionEnabled = true;
    });

    it('selections disabled when selectionEnabled is false', async () => {
      element.selectionEnabled = false;
      element.issues = [
        {projectName: 'test', localId: 1, summary: 'test issue'},
        {projectName: 'test', localId: 2, summary: 'I have a summary'},
      ];

      await element.updateComplete;

      let checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');
      assert.equal(checkboxes.length, 0);

      element.selectionEnabled = true;
      await element.updateComplete;

      checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');
      assert.equal(checkboxes.length, 2);
    });

    it('selected issues render selected attribute', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'another issue', localId: 2, projectName: 'proj'},
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ];
      element.columns = ['Summary'];

      await element.updateComplete;

      element._selectedIssues = new Set(['proj:1']);

      await element.updateComplete;

      const issues = element.shadowRoot.querySelectorAll('tr[selected]');

      assert.equal(issues.length, 1);
      assert.equal(issues[0].dataset.index, '0');
      assert.include(issues[0].textContent, 'issue 1');
    });

    it('select all / none conditionally shows tooltip', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ];

      await element.updateComplete;
      assert.deepEqual(element.selectedIssues, []);

      const selectAll = element.shadowRoot.querySelector('.select-all');

      // No issues selected, offer "Select All".
      assert.equal(selectAll.title, 'Select All');
      assert.equal(selectAll.getAttribute('aria-label'), 'Select All');

      selectAll.click();

      await element.updateComplete;

      // Some issues selected, offer "Select None".
      assert.equal(selectAll.title, 'Select None');
      assert.equal(selectAll.getAttribute('aria-label'), 'Select None');
    });

    it('clicking select all selects all issues', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ];

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, []);

      const selectAll = element.shadowRoot.querySelector('.select-all');
      selectAll.click();

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ]);
    });

    it('when checked select all deselects all issues', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ];

      await element.updateComplete;

      element._selectedIssues = new Set(['proj:1', 'proj:2']);

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 2, projectName: 'proj'},
      ]);

      const selectAll = element.shadowRoot.querySelector('.select-all');
      selectAll.click();

      assert.deepEqual(element.selectedIssues, []);
    });

    it('selected issues added when issues checked', async () => {
      element.issues = [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'another issue', localId: 2, projectName: 'proj'},
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ];

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, []);

      const checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');

      assert.equal(checkboxes.length, 3);

      checkboxes[2].dispatchEvent(new MouseEvent('click'));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ]);

      checkboxes[0].dispatchEvent(new MouseEvent('click'));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {summary: 'issue 1', localId: 1, projectName: 'proj'},
        {summary: 'issue 2', localId: 3, projectName: 'proj'},
      ]);
    });

    it('shift+click selects issues in a range', async () => {
      element.issues = [
        {localId: 1, projectName: 'proj'},
        {localId: 2, projectName: 'proj'},
        {localId: 3, projectName: 'proj'},
        {localId: 4, projectName: 'proj'},
        {localId: 5, projectName: 'proj'},
      ];

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, []);

      const checkboxes = element.shadowRoot.querySelectorAll('.issue-checkbox');

      // First click.
      checkboxes[0].dispatchEvent(new MouseEvent('click'));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 1, projectName: 'proj'},
      ]);

      // Second click.
      checkboxes[3].dispatchEvent(new MouseEvent('click', {shiftKey: true}));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 1, projectName: 'proj'},
        {localId: 2, projectName: 'proj'},
        {localId: 3, projectName: 'proj'},
        {localId: 4, projectName: 'proj'},
      ]);

      // It's possible to chain Shift+Click operations.
      checkboxes[2].dispatchEvent(new MouseEvent('click', {shiftKey: true}));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 1, projectName: 'proj'},
        {localId: 2, projectName: 'proj'},
      ]);
    });

    it('fires selectionChange events', async () => {
      const listener = sinon.stub();
      element.addEventListener('selectionChange', listener);

      // Changing the issue list clears the selection and fires an event.
      element.issues = [{localId: 1, projectName: 'proj'}];
      await element.updateComplete;
      // Selecting all/deselecting all fires an event.
      element.shadowRoot.querySelector('.select-all').click();
      await element.updateComplete;
      // Selecting an individual issue fires an event.
      element.shadowRoot.querySelectorAll('.issue-checkbox')[0].click();

      sinon.assert.calledThrice(listener);
    });
  });

  describe('cursor', () => {
    beforeEach(() => {
      element.issues = [
        {localId: 1, projectName: 'chromium'},
        {localId: 2, projectName: 'chromium'},
      ];
    });

    it('empty when no initialCursor', () => {
      assert.deepEqual(element.cursor, {});

      element.initialCursor = '';
      assert.deepEqual(element.cursor, {});
    });

    it('parses initialCursor value', () => {
      element.initialCursor = '1';
      element.projectName = 'chromium';

      assert.deepEqual(element.cursor, {projectName: 'chromium', localId: 1});

      element.initialCursor = 'chromium:1';
      assert.deepEqual(element.cursor, {projectName: 'chromium', localId: 1});
    });

    it('overrides initialCursor with _localCursor', () => {
      element.initialCursor = 'chromium:1';
      element._localCursor = {projectName: 'gerrit', localId: 2};

      assert.deepEqual(element.cursor, {projectName: 'gerrit', localId: 2});
    });

    it('initialCursor renders cursor and focuses element', async () => {
      element.initialCursor = 'chromium:1';

      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-0');
      assert.isTrue(row.hasAttribute('cursored'));
      listRowIsFocused(element, 0);
    });

    it('cursor value updated when row is focused', async () => {
      element.initialCursor = 'chromium:1';

      await element.updateComplete;

      // HTMLElement.focus() seems to cause a timing related flake here.
      element.shadowRoot.querySelector('.row-1').dispatchEvent(
          new Event('focus'));

      assert.deepEqual(element.cursor, {projectName: 'chromium', localId: 2});
    });
  });

  describe('hot keys', () => {
    beforeEach(() => {
      element.issues = [
        {localId: 1, projectName: 'chromium'},
        {localId: 2, projectName: 'chromium'},
        {localId: 3, projectName: 'chromium'},
      ];

      element.selectionEnabled = true;

      sinon.stub(element, '_navigateToIssue');
    });

    afterEach(() => {
      element._navigateToIssue.restore();
    });

    it('global keydown listener removed on disconnect', async () => {
      sinon.stub(element, '_boundRunListHotKeys');

      await element.updateComplete;

      window.dispatchEvent(new Event('keydown'));
      sinon.assert.calledOnce(element._boundRunListHotKeys);

      document.body.removeChild(element);

      window.dispatchEvent(new Event('keydown'));
      sinon.assert.calledOnce(element._boundRunListHotKeys);

      document.body.appendChild(element);
    });

    it('pressing j defaults to first issue', async () => {
      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 0);
    });

    it('pressing j focuses next issue', async () => {
      element.initialCursor = 'chromium:1';

      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 1);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 2);
    });

    it('pressing j at the end of the list loops around', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-2').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));

      listRowIsFocused(element, 0);
    });


    it('pressing k defaults to last issue', async () => {
      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 2);
    });

    it('pressing k focuses previous issue', async () => {
      element.initialCursor = 'chromium:3';

      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 1);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 0);
    });

    it('pressing k at the start of the list loops around', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-0').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));

      listRowIsFocused(element, 2);
    });

    it('j and k keys treat row as focused if child is focused', async () => {
      await element.updateComplete;

      element.shadowRoot.querySelector('.row-1').querySelector(
          'mr-issue-link').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      listRowIsFocused(element, 2);

      element.shadowRoot.querySelector('.row-1').querySelector(
          'mr-issue-link').focus();

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      listRowIsFocused(element, 0);
    });

    it('j and k keys stay on one element when one issue', async () => {
      element.issues = [{localId: 2, projectName: 'chromium'}];
      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      listRowIsFocused(element, 0);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      listRowIsFocused(element, 0);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      listRowIsFocused(element, 0);

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      listRowIsFocused(element, 0);
    });

    it('j and k no-op when event is from input', async () => {
      const input = document.createElement('input');
      document.body.appendChild(input);

      await element.updateComplete;

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      assert.isNull(element.shadowRoot.activeElement);

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      assert.isNull(element.shadowRoot.activeElement);

      document.body.removeChild(input);
    });

    it('j and k no-op when event is from shadowDOM input', async () => {
      const input = document.createElement('input');
      const root = document.createElement('div');

      root.attachShadow({mode: 'open'});
      root.shadowRoot.appendChild(input);

      document.body.appendChild(root);

      await element.updateComplete;

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'j'}));
      assert.isNull(element.shadowRoot.activeElement);

      input.dispatchEvent(new KeyboardEvent('keydown', {key: 'k'}));
      assert.isNull(element.shadowRoot.activeElement);

      document.body.removeChild(root);
    });

    describe('starring issue', () => {
      beforeEach(() => {
        element.starringEnabled = true;
        element.initialCursor = 'chromium:2';
      });

      it('pressing s stars focused issue', async () => {
        sinon.stub(element, '_starIssue');
        await element.updateComplete;

        window.dispatchEvent(new KeyboardEvent('keydown', {key: 's'}));

        sinon.assert.calledWith(element._starIssue,
            {localId: 2, projectName: 'chromium'});
      });

      it('starIssue does not star issue while stars are fetched', () => {
        sinon.stub(element, '_starIssueInternal');
        element._fetchingStarredIssues = true;

        element._starIssue({localId: 2, projectName: 'chromium'});

        sinon.assert.notCalled(element._starIssueInternal);
      });

      it('starIssue does not star when issue is being starred', () => {
        sinon.stub(element, '_starIssueInternal');
        element._starringIssues = new Map([['chromium:2', {requesting: true}]]);

        element._starIssue({localId: 2, projectName: 'chromium'});

        sinon.assert.notCalled(element._starIssueInternal);
      });

      it('starIssue stars issue when issue is not being starred', () => {
        sinon.stub(element, '_starIssueInternal');
        element._starringIssues = new Map([
          ['chromium:2', {requesting: false}],
        ]);

        element._starIssue({localId: 2, projectName: 'chromium'});

        sinon.assert.calledWith(element._starIssueInternal,
            {localId: 2, projectName: 'chromium'}, true);
      });

      it('starIssue unstars issue when issue is already starred', () => {
        sinon.stub(element, '_starIssueInternal');
        element._starredIssues = new Set(['chromium:2']);

        element._starIssue({localId: 2, projectName: 'chromium'});

        sinon.assert.calledWith(element._starIssueInternal,
            {localId: 2, projectName: 'chromium'}, false);
      });
    });

    it('pressing x selects focused issue', async () => {
      element.initialCursor = 'chromium:2';

      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'x'}));

      await element.updateComplete;

      assert.deepEqual(element.selectedIssues, [
        {localId: 2, projectName: 'chromium'},
      ]);
    });

    it('pressing o navigates to focused issue', async () => {
      element.initialCursor = 'chromium:2';

      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'o'}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(element._navigateToIssue,
          {localId: 2, projectName: 'chromium'}, false);
    });

    it('pressing shift+o opens focused issue in new tab', async () => {
      element.initialCursor = 'chromium:2';

      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown',
          {key: 'O', shiftKey: true}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(element._navigateToIssue,
          {localId: 2, projectName: 'chromium'}, true);
    });

    it('enter keydown on row navigates to issue', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');

      row.dispatchEvent(
          new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(
          element._navigateToIssue, {localId: 2, projectName: 'chromium'},
          false);
    });

    it('ctrl+enter keydown on row navigates to issue in new tab', async () => {
      await element.updateComplete;

      const row = element.shadowRoot.querySelector('.row-1');

      // Note: metaKey would also work, but this is covered by click tests.
      row.dispatchEvent(new KeyboardEvent(
          'keydown', {key: 'Enter', ctrlKey: true, bubbles: true}));

      await element.updateComplete;

      sinon.assert.calledOnce(element._navigateToIssue);
      sinon.assert.calledWith(element._navigateToIssue,
          {localId: 2, projectName: 'chromium'}, true);
    });

    it('enter keypress outside row is ignored', async () => {
      await element.updateComplete;

      window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));

      await element.updateComplete;

      sinon.assert.notCalled(element._navigateToIssue);
    });
  });

  describe('_convertIssueToPlaintextArray', () => {
    it('returns an array with as many entries as this.columns.length', () => {
      element.columns = ['summary'];
      const result = element._convertIssueToPlaintextArray({
        summary: 'test issue',
      });
      assert.equal(element.columns.length, result.length);
    });

    it('for column id uses issueRefToString', async () => {
      const projectName = 'some_project_name';
      const otherProjectName = 'some_other_project';
      const localId = '123';
      element.columns = ['ID'];
      element.projectName = projectName;

      element.extractFieldValues = (issue, fieldName) =>
        stringValuesForIssueField(issue, fieldName, projectName);

      let result;
      result = element._convertIssueToPlaintextArray({
        localId,
        projectName,
      });
      assert.equal(localId, result[0]);

      result = element._convertIssueToPlaintextArray({
        localId,
        projectName: otherProjectName,
      });
      assert.equal(`${otherProjectName}:${localId}`, result[0]);
    });

    it('uses extractFieldValues', () => {
      element.columns = ['summary', 'notsummary', 'anotherColumn'];
      element.extractFieldValues = sinon.fake.returns(['a', 'b']);

      element._convertIssueToPlaintextArray({summary: 'test issue'});
      sinon.assert.callCount(element.extractFieldValues,
          element.columns.length);
    });

    it('joins the result of extractFieldValues with ", "', () => {
      element.columns = ['notSummary'];
      element.extractFieldValues = sinon.fake.returns(['a', 'b']);

      const result = element._convertIssueToPlaintextArray({
        summary: 'test issue',
      });
      assert.deepEqual(result, ['a, b']);
    });
  });

  describe('_convertIssuesToPlaintextArrays', () => {
    it('maps this.issues with this._convertIssueToPlaintextArray', () => {
      element._convertIssueToPlaintextArray = sinon.fake.returns(['foobar']);

      element.columns = ['summary'];
      element.issues = [
        {summary: 'test issue'},
        {summary: 'I have a summary'},
      ];
      const result = element._convertIssuesToPlaintextArrays();

      assert.deepEqual([['foobar'], ['foobar']], result);
      sinon.assert.callCount(element._convertIssueToPlaintextArray,
          element.issues.length);
    });
  });

  it('drag-and-drop', async () => {
    element.rerank = () => {};
    element.issues = [
      {projectName: 'project', localId: 123, summary: 'test issue'},
      {projectName: 'project', localId: 456, summary: 'I have a summary'},
      {projectName: 'project', localId: 789, summary: 'third issue'},
    ];
    await element.updateComplete;

    const rows = element._getRows();

    // Mouse down on the middle element!
    const secondRow = rows[1];
    const dragHandle = secondRow.firstElementChild;
    const mouseDown = new MouseEvent('mousedown', {clientX: 0, clientY: 0});
    dragHandle.dispatchEvent(mouseDown);

    assert.deepEqual(element._dragging, true);
    assert.deepEqual(element.cursor, {projectName: 'project', localId: 456});
    assert.deepEqual(element.selectedIssues, [element.issues[1]]);

    // Drag the middle element to the end!
    const mouseMove = new MouseEvent('mousemove', {clientX: 0, clientY: 100});
    window.dispatchEvent(mouseMove);

    assert.deepEqual(rows[0].style['transform'], '');
    assert.deepEqual(rows[1].style['transform'], 'translate(0px, 100px)');
    assert.match(rows[2].style['transform'], /^translate\(0px, -\d+px\)$/);

    // Mouse up!
    const mouseUp = new MouseEvent('mouseup', {clientX: 0, clientY: 100});
    window.dispatchEvent(mouseUp);

    assert.deepEqual(element._dragging, false);
    assert.match(rows[1].style['transform'], /^translate\(0px, \d+px\)$/);
  });

  describe('CSV download', () => {
    let _downloadCsvSpy;
    let convertStub;

    beforeEach(() => {
      element.userDisplayName = 'notempty';
      _downloadCsvSpy = sinon.spy(element, '_downloadCsv');
      convertStub = sinon
          .stub(element, '_convertIssuesToPlaintextArrays')
          .returns([['']]);
    });

    afterEach(() => {
      _downloadCsvSpy.restore();
      convertStub.restore();
    });

    it('hides download link for anonymous users', async () => {
      element.userDisplayName = '';
      await element.updateComplete;
      const downloadLink = element.shadowRoot.querySelector('#download-link');
      assert.isNull(downloadLink);
    });

    it('renders a #download-link', async () => {
      await element.updateComplete;
      const downloadLink = element.shadowRoot.querySelector('#download-link');
      assert.isNotNull(downloadLink);
      assert.equal('inline', window.getComputedStyle(downloadLink).display);
    });

    it('renders a #hidden-data-link', async () => {
      await element.updateComplete;
      assert.isNotNull(element._dataLink);
      const expected = element.shadowRoot.querySelector('#hidden-data-link');
      assert.equal(expected, element._dataLink);
    });

    it('hides #hidden-data-link', async () => {
      await element.updateComplete;
      const _dataLink = element.shadowRoot.querySelector('#hidden-data-link');
      assert.equal('none', window.getComputedStyle(_dataLink).display);
    });

    it('calls _downloadCsv on click', async () => {
      await element.updateComplete;
      sinon.stub(element._dataLink, 'click');

      const downloadLink = element.shadowRoot.querySelector('#download-link');
      downloadLink.click();
      await element.requestUpdate('_csvDataHref');

      sinon.assert.calledOnce(_downloadCsvSpy);
      element._dataLink.click.restore();
    });

    it('converts issues into arrays of plaintext data', async () => {
      await element.updateComplete;
      sinon.stub(element._dataLink, 'click');

      const downloadLink = element.shadowRoot.querySelector('#download-link');
      downloadLink.click();
      await element.requestUpdate('_csvDataHref');

      sinon.assert.calledOnce(convertStub);
      element._dataLink.click.restore();
    });

    it('triggers _dataLink click after #downloadLink click', async () => {
      await element.updateComplete;
      const dataLinkStub = sinon.stub(element._dataLink, 'click');

      const downloadLink = element.shadowRoot.querySelector('#download-link');

      downloadLink.click();

      await element.requestUpdate('_csvDataHref');
      sinon.assert.calledOnce(dataLinkStub);

      element._dataLink.click.restore();
    });

    it('triggers _csvDataHref update and _dataLink click', async () => {
      await element.updateComplete;
      assert.equal('', element._csvDataHref);
      const downloadStub = sinon.stub(element._dataLink, 'click');

      const downloadLink = element.shadowRoot.querySelector('#download-link');

      downloadLink.click();
      assert.notEqual('', element._csvDataHref);
      await element.requestUpdate('_csvDataHref');
      sinon.assert.calledOnce(downloadStub);

      element._dataLink.click.restore();
    });

    it('resets _csvDataHref', async () => {
      await element.updateComplete;
      assert.equal('', element._csvDataHref);

      sinon.stub(element._dataLink, 'click');
      const downloadLink = element.shadowRoot.querySelector('#download-link');
      downloadLink.click();
      assert.notEqual('', element._csvDataHref);

      await element.requestUpdate('_csvDataHref');
      assert.equal('', element._csvDataHref);
      element._dataLink.click.restore();
    });

    it('does nothing for anonymous users', async () => {
      await element.updateComplete;

      element.userDisplayName = '';

      const downloadStub = sinon.stub(element._dataLink, 'click');

      const downloadLink = element.shadowRoot.querySelector('#download-link');

      downloadLink.click();
      await element.requestUpdate('_csvDataHref');
      sinon.assert.notCalled(downloadStub);

      element._dataLink.click.restore();
    });
  });
});
