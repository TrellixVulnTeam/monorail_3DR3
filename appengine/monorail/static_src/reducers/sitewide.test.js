// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import {assert} from 'chai';

import {store, stateUpdated, resetState} from 'reducers/base.js';
import {prpcClient} from 'prpc-client-instance.js';
import * as sitewide from './sitewide.js';

let prpcCall;

describe('sitewide selectors', () => {
  beforeEach(() => {
    store.dispatch(resetState());
  });
  it('queryParams', () => {
    assert.deepEqual(sitewide.queryParams({}), {});
    assert.deepEqual(sitewide.queryParams({sitewide: {}}), {});
    assert.deepEqual(sitewide.queryParams({sitewide: {queryParams:
      {q: 'owner:me'}}}), {q: 'owner:me'});
  });

  describe('pageTitle', () => {
    it('defaults to Monorail when no data', () => {
      assert.equal(sitewide.pageTitle({}), 'Monorail');
      assert.equal(sitewide.pageTitle({sitewide: {}}), 'Monorail');
    });

    it('uses local page title when one exists', () => {
      assert.equal(sitewide.pageTitle(
          {sitewide: {pageTitle: 'Issue Detail'}}), 'Issue Detail');
    });

    it('shows name of viewed project', () => {
      assert.equal(sitewide.pageTitle({
        sitewide: {pageTitle: 'Page'},
        projectV0: {
          name: 'chromium',
          configs: {chromium: {projectName: 'chromium'}},
        },
      }), 'Page - chromium');
    });
  });

  describe('currentColumns', () => {
    it('returns null no configuration', () => {
      assert.deepEqual(sitewide.currentColumns({}), null);
      assert.deepEqual(sitewide.currentColumns({projectV0: {}}), null);
      const state = {projectV0: {presentationConfig: {}}};
      assert.deepEqual(sitewide.currentColumns(state), null);
    });

    it('gets columns from URL query params', () => {
      const state = {sitewide: {
        queryParams: {colspec: 'ID+Summary+ColumnName+Priority'},
      }};
      const expected = ['ID', 'Summary', 'ColumnName', 'Priority'];
      assert.deepEqual(sitewide.currentColumns(state), expected);
    });
  });

  describe('currentCan', () => {
    it('uses sitewide default can by default', () => {
      assert.deepEqual(sitewide.currentCan({}), '2');
    });

    it('URL params override default can', () => {
      assert.deepEqual(sitewide.currentCan({
        sitewide: {
          queryParams: {can: '3'},
        },
      }), '3');
    });

    it('undefined query param does not override default can', () => {
      assert.deepEqual(sitewide.currentCan({
        sitewide: {
          queryParams: {can: undefined},
        },
      }), '2');
    });
  });

  describe('currentQuery', () => {
    it('defaults to empty', () => {
      assert.deepEqual(sitewide.currentQuery({}), '');
      assert.deepEqual(sitewide.currentQuery({projectV0: {}}), '');
    });

    it('uses project default when no params', () => {
      assert.deepEqual(sitewide.currentQuery({projectV0: {
        name: 'chromium',
        presentationConfigs: {
          chromium: {defaultQuery: 'owner:me'},
        },
      }}), 'owner:me');
    });

    it('URL query params override default query', () => {
      assert.deepEqual(sitewide.currentQuery({
        projectV0: {
          name: 'chromium',
          presentationConfigs: {
            chromium: {defaultQuery: 'owner:me'},
          },
        },
        sitewide: {
          queryParams: {q: 'component:Infra'},
        },
      }), 'component:Infra');
    });

    it('empty string in param overrides default project query', () => {
      assert.deepEqual(sitewide.currentQuery({
        projectV0: {
          name: 'chromium',
          presentationConfigs: {
            chromium: {defaultQuery: 'owner:me'},
          },
        },
        sitewide: {
          queryParams: {q: ''},
        },
      }), '');
    });

    it('undefined query param does not override default search', () => {
      assert.deepEqual(sitewide.currentQuery({
        projectV0: {
          name: 'chromium',
          presentationConfigs: {
            chromium: {defaultQuery: 'owner:me'},
          },
        },
        sitewide: {
          queryParams: {q: undefined},
        },
      }), 'owner:me');
    });
  });
});


describe('sitewide action creators', () => {
  beforeEach(() => {
    prpcCall = sinon.stub(prpcClient, 'call');
  });

  afterEach(() => {
    prpcClient.call.restore();
  });

  it('setQueryParams updates queryParams', async () => {
    store.dispatch(sitewide.setQueryParams({test: 'param'}));

    await stateUpdated;

    assert.deepEqual(sitewide.queryParams(store.getState()), {test: 'param'});
  });

  describe('getServerStatus', () => {
    it('gets server status', async () => {
      prpcCall.callsFake(() => {
        return {
          bannerMessage: 'Message',
          bannerTime: 1234,
          readOnly: true,
        };
      });

      store.dispatch(sitewide.getServerStatus());

      await stateUpdated;
      const state = store.getState();

      assert.deepEqual(sitewide.bannerMessage(state), 'Message');
      assert.deepEqual(sitewide.bannerTime(state), 1234);
      assert.isTrue(sitewide.readOnly(state));

      assert.deepEqual(sitewide.requests(state), {
        serverStatus: {
          error: null,
          requesting: false,
        },
      });
    });

    it('gets empty status', async () => {
      prpcCall.callsFake(() => {
        return {};
      });

      store.dispatch(sitewide.getServerStatus());

      await stateUpdated;
      const state = store.getState();

      assert.deepEqual(sitewide.bannerMessage(state), '');
      assert.deepEqual(sitewide.bannerTime(state), 0);
      assert.isFalse(sitewide.readOnly(state));

      assert.deepEqual(sitewide.requests(state), {
        serverStatus: {
          error: null,
          requesting: false,
        },
      });
    });

    it('fails', async () => {
      const error = new Error('error');
      prpcCall.callsFake(() => {
        throw error;
      });

      store.dispatch(sitewide.getServerStatus());

      await stateUpdated;
      const state = store.getState();

      assert.deepEqual(sitewide.bannerMessage(state), '');
      assert.deepEqual(sitewide.bannerTime(state), 0);
      assert.isFalse(sitewide.readOnly(state));

      assert.deepEqual(sitewide.requests(state), {
        serverStatus: {
          error: error,
          requesting: false,
        },
      });
    });
  });
});
