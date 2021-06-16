// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {expect, assert} from 'chai';
import {ChopsDialog} from './chops-dialog.js';

let element;

describe('chops-dialog', () => {
  beforeEach(() => {
    element = document.createElement('chops-dialog');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsDialog);
  });

  it('chops-dialog is visible when open', async () => {
    element.opened = false;

    await element.updateComplete;

    expect(element).not.to.be.visible;

    element.opened = true;

    await element.updateComplete;

    expect(element).to.be.visible;
  });
});
