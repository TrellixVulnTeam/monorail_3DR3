// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {arrayDifference, setHasAny, capitalizeFirst, hasPrefix, objectToMap,
  objectValuesForKeys, equalsIgnoreCase, immutableSplice, userIsMember,
  urlWithNewParams, createObjectComparisonFunc} from './helpers.js';


describe('arrayDifference', () => {
  it('empty array stays empty', () => {
    assert.deepEqual(arrayDifference([], []), []);
    assert.deepEqual(arrayDifference([], undefined), []);
    assert.deepEqual(arrayDifference([], ['a']), []);
  });

  it('subtracting empty array does nothing', () => {
    assert.deepEqual(arrayDifference(['a'], []), ['a']);
    assert.deepEqual(arrayDifference([1, 2, 3], []), [1, 2, 3]);
    assert.deepEqual(arrayDifference([1, 2, 'test'], []), [1, 2, 'test']);
    assert.deepEqual(arrayDifference([1, 2, 'test'], undefined),
        [1, 2, 'test']);
  });

  it('subtracts elements from array', () => {
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['b', 'c']), ['a']);
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['a']), ['b', 'c']);
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['b']), ['a', 'c']);
    assert.deepEqual(arrayDifference([1, 2, 3], [2]), [1, 3]);
  });

  it('does not subtract missing elements from array', () => {
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['d']), ['a', 'b', 'c']);
    assert.deepEqual(arrayDifference([1, 2, 3], [5]), [1, 2, 3]);
    assert.deepEqual(arrayDifference([1, 2, 3], [-1, 2]), [1, 3]);
  });

  it('custom equals function', () => {
    assert.deepEqual(arrayDifference(['a', 'b'], ['A']), ['a', 'b']);
    assert.deepEqual(arrayDifference(['a', 'b'], ['A'], equalsIgnoreCase),
        ['b']);
  });
});

describe('setHasAny', () => {
  it('empty set never has any values', () => {
    assert.isFalse(setHasAny(new Set(), []));
    assert.isFalse(setHasAny(new Set(), ['test']));
    assert.isFalse(setHasAny(new Set(), ['nope', 'yup', 'no']));
  });

  it('false when no values found', () => {
    assert.isFalse(setHasAny(new Set(['hello', 'world']), []));
    assert.isFalse(setHasAny(new Set(['hello', 'world']), ['wor']));
    assert.isFalse(setHasAny(new Set(['test']), ['other', 'values']));
    assert.isFalse(setHasAny(new Set([1, 2, 3]), [4, 5, 6]));
  });

  it('true when values found', () => {
    assert.isTrue(setHasAny(new Set(['hello', 'world']), ['world']));
    assert.isTrue(setHasAny(new Set([1, 2, 3]), [3, 4, 5]));
    assert.isTrue(setHasAny(new Set([1, 2, 3]), [1, 3]));
  });
});

describe('capitalizeFirst', () => {
  it('empty string', () => {
    assert.equal(capitalizeFirst(''), '');
  });

  it('ignores non-letters', () => {
    assert.equal(capitalizeFirst('8fcsdf'), '8fcsdf');
  });

  it('preserves existing caps', () => {
    assert.equal(capitalizeFirst('HELLO world'), 'HELLO world');
  });

  it('capitalizes lowercase', () => {
    assert.equal(capitalizeFirst('hello world'), 'Hello world');
  });
});

describe('hasPrefix', () => {
  it('only true when has prefix', () => {
    assert.isFalse(hasPrefix('teststring', 'test-'));
    assert.isFalse(hasPrefix('stringtest-', 'test-'));
    assert.isFalse(hasPrefix('^test-$', 'test-'));
    assert.isTrue(hasPrefix('test-', 'test-'));
    assert.isTrue(hasPrefix('test-fsdfsdf', 'test-'));
  });

  it('ignores case when checking prefix', () => {
    assert.isTrue(hasPrefix('TEST-string', 'test-'));
    assert.isTrue(hasPrefix('test-string', 'test-'));
    assert.isTrue(hasPrefix('tEsT-string', 'test-'));
  });
});

describe('objectToMap', () => {
  it('converts Object to Map with the same keys', () => {
    assert.deepEqual(objectToMap({}), new Map());
    assert.deepEqual(objectToMap({test: 'value'}),
        new Map([['test', 'value']]));
    assert.deepEqual(objectToMap({['weird:key']: 'value',
      ['what is this key']: 'v2'}), new Map([['weird:key', 'value'],
      ['what is this key', 'v2']]));
  });
});

describe('objectValuesForKeys', () => {
  it('no values when no matching keys', () => {
    assert.deepEqual(objectValuesForKeys({}, []), []);
    assert.deepEqual(objectValuesForKeys({}, []), []);
    assert.deepEqual(objectValuesForKeys({key: 'value'}, []), []);
  });

  it('returns values when keys match', () => {
    assert.deepEqual(objectValuesForKeys({a: 1, b: 2, c: 3}, ['a', 'b']),
        [1, 2]);
    assert.deepEqual(objectValuesForKeys({a: 1, b: 2, c: 3}, ['b', 'c']),
        [2, 3]);
    assert.deepEqual(objectValuesForKeys({['weird:key']: {nested: 'obj'}},
        ['weird:key']), [{nested: 'obj'}]);
  });

  it('sets non-matching keys to undefined', () => {
    assert.deepEqual(objectValuesForKeys({a: 1, b: 2, c: 3}, ['c', 'd', 'e']),
        [3, undefined, undefined]);
    assert.deepEqual(objectValuesForKeys({a: 1, b: 2, c: 3}, [1, 2, 3]),
        [undefined, undefined, undefined]);
  });
});

describe('equalsIgnoreCase', () => {
  it('matches same case strings', () => {
    assert.isTrue(equalsIgnoreCase('', ''));
    assert.isTrue(equalsIgnoreCase('HelloWorld', 'HelloWorld'));
    assert.isTrue(equalsIgnoreCase('hmm', 'hmm'));
    assert.isTrue(equalsIgnoreCase('TEST', 'TEST'));
  });

  it('matches different case strings', () => {
    assert.isTrue(equalsIgnoreCase('a', 'A'));
    assert.isTrue(equalsIgnoreCase('HelloWorld', 'helloworld'));
    assert.isTrue(equalsIgnoreCase('hmm', 'HMM'));
    assert.isTrue(equalsIgnoreCase('TEST', 'teSt'));
  });

  it('does not match different strings', () => {
    assert.isFalse(equalsIgnoreCase('hello', 'hello '));
    assert.isFalse(equalsIgnoreCase('superstring', 'string'));
    assert.isFalse(equalsIgnoreCase('aaa', 'aa'));
  });
});

describe('immutableSplice', () => {
  it('does not edit original array', () => {
    const arr = ['apples', 'pears', 'oranges'];

    assert.deepEqual(immutableSplice(arr, 1, 1),
        ['apples', 'oranges']);

    assert.deepEqual(arr, ['apples', 'pears', 'oranges']);
  });

  it('removes multiple items', () => {
    const arr = [1, 2, 3, 4, 5, 6];

    assert.deepEqual(immutableSplice(arr, 1, 0), [1, 2, 3, 4, 5, 6]);
    assert.deepEqual(immutableSplice(arr, 1, 4), [1, 6]);
    assert.deepEqual(immutableSplice(arr, 0, 6), []);
  });

  it('adds items', () => {
    const arr = [1, 2, 3];

    assert.deepEqual(immutableSplice(arr, 1, 1, 4, 5, 6), [1, 4, 5, 6, 3]);
    assert.deepEqual(immutableSplice(arr, 2, 1, 4, 5, 6), [1, 2, 4, 5, 6]);
    assert.deepEqual(immutableSplice(arr, 0, 0, -3, -2, -1, 0),
        [-3, -2, -1, 0, 1, 2, 3]);
  });
});

describe('urlWithNewParams', () => {
  it('empty', () => {
    assert.equal(urlWithNewParams(), '');
    assert.equal(urlWithNewParams(''), '');
    assert.equal(urlWithNewParams('', {}), '');
    assert.equal(urlWithNewParams('', {}, {}), '');
    assert.equal(urlWithNewParams('', {}, {}, []), '');
  });

  it('preserves existing URL without changes', () => {
    assert.equal(urlWithNewParams('/p/chromium/issues/list'),
        '/p/chromium/issues/list');
    assert.equal(urlWithNewParams('/p/chromium/issues/list', {q: 'owner:me'}),
        '/p/chromium/issues/list?q=owner%3Ame');
    assert.equal(
        urlWithNewParams('/p/chromium/issues/list', {q: 'owner:me', can: '1'}),
        '/p/chromium/issues/list?q=owner%3Ame&can=1');
  });

  it('adds new params', () => {
    assert.equal(
        urlWithNewParams('/p/chromium/issues/list', {}, {q: 'owner:me'}),
        '/p/chromium/issues/list?q=owner%3Ame');
    assert.equal(
        urlWithNewParams('/p/chromium/issues/list',
            {can: '1'}, {q: 'owner:me'}),
        '/p/chromium/issues/list?can=1&q=owner%3Ame');

    // Override existing params.
    assert.equal(
        urlWithNewParams('/p/chromium/issues/list',
            {can: '1', q: 'owner:me'}, {q: 'test'}),
        '/p/chromium/issues/list?can=1&q=test');
  });

  it('clears existing params', () => {
    assert.equal(
        urlWithNewParams('/p/chromium/issues/list', {q: 'owner:me'}, {}, ['q']),
        '/p/chromium/issues/list');
    assert.equal(
        urlWithNewParams('/p/chromium/issues/list',
            {can: '1'}, {q: 'owner:me'}, ['can']),
        '/p/chromium/issues/list?q=owner%3Ame');
    assert.equal(
        urlWithNewParams('/p/chromium/issues/list', {q: 'owner:me'}, {can: '2'},
            ['q', 'can', 'fakeparam']),
        '/p/chromium/issues/list');
  });
});

describe('userIsMember', () => {
  it('false when no user', () => {
    assert.isFalse(userIsMember(undefined));
    assert.isFalse(userIsMember({}));
    assert.isFalse(userIsMember({}, 'chromium',
        new Map([['123', {ownerOf: ['chromium']}]])));
  });

  it('true when user is member of project', () => {
    assert.isTrue(userIsMember({userId: '123'}, 'chromium',
        new Map([['123', {contributorTo: ['chromium']}]])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium',
        new Map([['123', {ownerOf: ['chromium']}]])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium',
        new Map([['123', {memberOf: ['chromium']}]])));
  });

  it('true when user is member of multiple projects', () => {
    assert.isTrue(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {contributorTo: ['test', 'chromium', 'fakeproject']}],
    ])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {ownerOf: ['test', 'chromium', 'fakeproject']}],
    ])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {memberOf: ['test', 'chromium', 'fakeproject']}],
    ])));
  });

  it('false when user is member of different project', () => {
    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {contributorTo: ['test', 'fakeproject']}],
    ])));

    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {ownerOf: ['test', 'fakeproject']}],
    ])));

    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {memberOf: ['test', 'fakeproject']}],
    ])));
  });

  it('false when no project data for user', () => {
    assert.isFalse(userIsMember({userId: '123'}, 'chromium'));
    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map()));
    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['543', {ownerOf: ['chromium']}],
    ])));
  });
});

describe('createObjectComparisonFunc', () => {
  it('returns a function', () => {
    const result = createObjectComparisonFunc(new Set());
    assert.instanceOf(result, Function);
  });

  describe('returned function', () => {
    it('returns false if both inputs are undefined', () => {
      const comparableProps = new Set(['a', 'b', 'c']);
      const func = createObjectComparisonFunc(comparableProps);
      const result = func(undefined, undefined);

      assert.isFalse(result);
    });

    it('returns true if only one inputs is undefined', () => {
      const comparableProps = new Set(['a', 'b', 'c']);
      const func = createObjectComparisonFunc(comparableProps);
      const result = func({}, undefined);

      assert.isTrue(result);
    });

    it('returns false if both inputs are null', () => {
      const comparableProps = new Set(['a', 'b', 'c']);
      const func = createObjectComparisonFunc(comparableProps);
      const result = func(null, null);

      assert.isFalse(result);
    });

    it('returns true if only one inputs is null', () => {
      const comparableProps = new Set(['a', 'b', 'c']);
      const func = createObjectComparisonFunc(comparableProps);
      const result = func({}, null);

      assert.isTrue(result);
    });

    it('returns true if any comparable property is different', () => {
      const comparableProps = new Set(['a', 'b', 'c']);
      const func = createObjectComparisonFunc(comparableProps);
      const a = {a: 1, b: 2, c: 3};
      const b = {a: 1, b: 2, c: '3'};
      const result = func(a, b);

      assert.isTrue(result);
    });

    it('returns false if all comparable properties are the same', () => {
      const comparableProps = new Set(['a', 'b', 'c']);
      const func = createObjectComparisonFunc(comparableProps);
      const a = {a: 1, b: 2, c: 3};
      const b = {a: 1, b: 2, c: 3};
      const result = func(a, b);

      assert.isFalse(result);
    });

    it('ignores non-comparable properties', () => {
      const comparableProps = new Set(['a', 'b', 'c']);
      const func = createObjectComparisonFunc(comparableProps);
      const a = {a: 1, b: 2, c: 3, d: 4};
      const b = {a: 1, b: 2, c: 3, d: 'not four', e: 'exists'};
      const result = func(a, b);

      assert.isFalse(result);
    });
  });
});
