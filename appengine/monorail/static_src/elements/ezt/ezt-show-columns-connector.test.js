// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {EztShowColumnsConnector} from './ezt-show-columns-connector.js';


let element;

describe('ezt-show-columns-connector', () => {
  beforeEach(() => {
    element = document.createElement('ezt-show-columns-connector');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, EztShowColumnsConnector);
  });

  it('initialColumns parses colspec', () => {
    element.colspec = 'Summary ID Owner';
    assert.deepEqual(element.initialColumns, ['Summary', 'ID', 'Owner']);
  });

  it('filters columns based on column mask', () => {
    sinon.stub(element, 'initialColumns').get(() => ['ID', 'Summary']);
    element.hiddenColumns = new Set([1]);

    assert.deepEqual(element.columns, ['ID']);
  });

  it('phaseNames parses phasespec', () => {
    element.phasespec = 'stable beta stable-exp';
    assert.deepEqual(element.phaseNames, ['stable', 'beta', 'stable-exp']);
  });
});
