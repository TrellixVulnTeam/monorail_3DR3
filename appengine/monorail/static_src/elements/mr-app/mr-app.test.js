// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {MrApp} from './mr-app.js';
import {store, resetState} from 'reducers/base.js';
import {select} from 'reducers/projectV0.js';

let element;
let next;

window.CS_env = {
  token: 'foo-token',
};

describe('mr-app', () => {
  beforeEach(() => {
    global.ga = sinon.spy();
    store.dispatch(resetState());
    element = document.createElement('mr-app');
    document.body.appendChild(element);
    element.formsToCheck = [];

    next = sinon.stub();
  });

  afterEach(() => {
    global.ga.resetHistory();
    document.body.removeChild(element);
    next.reset();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrApp);
  });

  describe('snackbar handling', () => {
    beforeEach(() => {
      sinon.spy(store, 'dispatch');
    });

    afterEach(() => {
      store.dispatch.restore();
    });

    it('renders no snackbars', async () => {
      element._snackbars = [];

      await element.updateComplete;

      const snackbars =
        element.shadowRoot.querySelectorAll('chops-snackbar');

      assert.equal(snackbars.length, 0);
    });

    it('renders multiple snackbars', async () => {
      element._snackbars = [
        {text: 'Snackbar one', id: 'one'},
        {text: 'Snackbar two', id: 'two'},
        {text: 'Snackbar three', id: 'thre'},
      ];

      await element.updateComplete;

      const snackbars =
        element.shadowRoot.querySelectorAll('chops-snackbar');

      assert.equal(snackbars.length, 3);

      assert.include(snackbars[0].textContent, 'Snackbar one');
      assert.include(snackbars[1].textContent, 'Snackbar two');
      assert.include(snackbars[2].textContent, 'Snackbar three');
    });

    it('closing snackbar hides snackbar', async () => {
      element._snackbars = [
        {text: 'Snackbar', id: 'one'},
      ];

      await element.updateComplete;

      const snackbar = element.shadowRoot.querySelector('chops-snackbar');

      snackbar.close();

      sinon.assert.calledWith(store.dispatch,
          {type: 'HIDE_SNACKBAR', id: 'one'});
    });
  });

  it('_preRouteHandler calls next()', () => {
    const ctx = {};

    element._preRouteHandler(ctx, next);

    sinon.assert.calledOnce(next);
  });

  it('_preRouteHandler does not call next() on same page nav', () => {
    element._lastContext = {path: '123'};
    const ctx = {path: '123'};

    element._preRouteHandler(ctx, next);

    assert.isFalse(ctx.handled);
    sinon.assert.notCalled(next);
  });

  it('_preRouteHandler parses queryParams', () => {
    const ctx = {querystring: 'q=owner:me&colspec=Summary'};
    element._preRouteHandler(ctx, next);

    assert.deepEqual(ctx.queryParams, {q: 'owner:me', colspec: 'Summary'});
  });

  it('_preRouteHandler ignores case for queryParams keys', () => {
    const ctx = {querystring: 'Q=owner:me&ColSpeC=Summary&x=owner'};
    element._preRouteHandler(ctx, next);

    assert.deepEqual(ctx.queryParams, {q: 'owner:me', colspec: 'Summary',
      x: 'owner'});
  });

  it('_preRouteHandler ignores case for queryParams keys', () => {
    const ctx = {querystring: 'Q=owner:me&ColSpeC=Summary&x=owner'};
    element._preRouteHandler(ctx, next);

    assert.deepEqual(ctx.queryParams, {q: 'owner:me', colspec: 'Summary',
      x: 'owner'});
  });

  it('_postRouteHandler saves ctx.queryParams to Redux', () => {
    const ctx = {queryParams: {q: '1234'}};
    element._postRouteHandler(ctx, next);

    assert.deepEqual(element.queryParams, {q: '1234'});
  });

  it('_postRouteHandler saves ctx to this._lastContext', () => {
    const ctx = {path: '1234'};
    element._postRouteHandler(ctx, next);

    assert.deepEqual(element._lastContext, {path: '1234'});
  });

  describe('scroll to the top on page changes', () => {
    beforeEach(() => {
      sinon.stub(window, 'scrollTo');
    });

    afterEach(() => {
      window.scrollTo.restore();
    });

    it('scrolls page to top on initial load', () => {
      element._lastContext = null;
      const ctx = {path: '1234'};
      element._postRouteHandler(ctx, next);

      sinon.assert.calledWith(window.scrollTo, 0, 0);
    });

    it('scrolls page to top on parh change', () => {
      element._lastContext = {pathname: '/list', path: '/list?q=123',
        querystring: '?q=123', queryParams: {q: '123'}};
      const ctx = {pathname: '/other', path: '/other?q=123',
        querystring: '?q=123', queryParams: {q: '123'}};

      element._postRouteHandler(ctx, next);

      sinon.assert.calledWith(window.scrollTo, 0, 0);
    });

    it('does not scroll to top when on the same path', () => {
      element._lastContext = {pathname: '/list', path: '/list?q=123',
        querystring: '?a=123', queryParams: {a: '123'}};
      const ctx = {pathname: '/list', path: '/list?q=456',
        querystring: '?a=456', queryParams: {a: '456'}};

      element._postRouteHandler(ctx, next);

      sinon.assert.notCalled(window.scrollTo);
    });

    it('scrolls to the top on same path when q param changes', () => {
      element._lastContext = {pathname: '/list', path: '/list?q=123',
        querystring: '?q=123', queryParams: {q: '123'}};
      const ctx = {pathname: '/list', path: '/list?q=456',
        querystring: '?q=456', queryParams: {q: '456'}};

      element._postRouteHandler(ctx, next);

      sinon.assert.calledWith(window.scrollTo, 0, 0);
    });
  });


  it('_postRouteHandler does not call next', () => {
    const ctx = {path: '1234'};
    element._postRouteHandler(ctx, next);

    sinon.assert.notCalled(next);
  });

  it('_loadIssuePage loads issue page', async () => {
    await element._loadIssuePage({
      queryParams: {id: '234'},
      params: {project: 'chromium'},
    }, next);
    await element.updateComplete;

    // Check that only one page element is rendering at a time.
    const main = element.shadowRoot.querySelector('main');
    assert.equal(main.children.length, 1);

    const issuePage = element.shadowRoot.querySelector('mr-issue-page');
    assert.isDefined(issuePage, 'issue page is defined');
    assert.equal(issuePage.issueRef.projectName, 'chromium');
    assert.equal(issuePage.issueRef.localId, 234);
  });

  it('_loadListPage loads list page', async () => {
    await element._loadListPage({
      params: {project: 'chromium'},
    }, next);
    await element.updateComplete;

    // Check that only one page element is rendering at a time.
    const main = element.shadowRoot.querySelector('main');
    assert.equal(main.children.length, 1);

    const listPage = element.shadowRoot.querySelector('mr-list-page');
    assert.isDefined(listPage, 'list page is defined');
  });

  it('_loadListPage loads grid page', async () => {
    element.queryParams = {mode: 'grid'};
    await element._loadListPage({
      params: {project: 'chromium'},
    }, next);
    await element.updateComplete;

    // Check that only one page element is rendering at a time.
    const main = element.shadowRoot.querySelector('main');
    assert.equal(main.children.length, 1);

    const gridPage = element.shadowRoot.querySelector('mr-grid-page');
    assert.isDefined(gridPage, 'grid page is defined');
  });

  describe('_selectProject', () => {
    beforeEach(() => {
      sinon.spy(store, 'dispatch');
    });

    afterEach(() => {
      store.dispatch.restore();
    });

    it('selects and fetches project', () => {
      const projectName = 'chromium';
      assert.notEqual(store.getState().projectV0.name, projectName);

      element._selectProject(
          {params: {project: projectName}},
          next);

      sinon.assert.calledTwice(store.dispatch);
    });

    it('skips selecting and fetching when project isn\'t changing', () => {
      const projectName = 'chromium';

      store.dispatch.restore();
      store.dispatch(select(projectName));
      sinon.spy(store, 'dispatch');

      assert.equal(store.getState().projectV0.name, projectName);

      element._selectProject(
          {params: {project: projectName}},
          next);

      sinon.assert.notCalled(store.dispatch);
    });
  });
});
