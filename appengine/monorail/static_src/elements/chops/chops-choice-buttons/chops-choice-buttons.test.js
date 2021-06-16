// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {assert} from 'chai';
import sinon from 'sinon';
import {ChopsChoiceButtons} from './chops-choice-buttons';

let element;

describe('chops-choice-buttons', () => {
  beforeEach(() => {
    element = document.createElement('chops-choice-buttons');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsChoiceButtons);
  });

  it('clicking option fires change event', async () => {
    element.options = [{value: 'test', text: 'click me'}];
    element.value = '';

    await element.updateComplete;

    const changeStub = sinon.stub();
    element.addEventListener('change', changeStub);

    const option = element.shadowRoot.querySelector('button');
    option.click();

    sinon.assert.calledOnce(changeStub);
  });

  it('clicking selected value does not fire change event', async () => {
    element.options = [{value: 'test', text: 'click me'}];
    element.value = 'test';

    await element.updateComplete;

    const changeStub = sinon.stub();
    element.addEventListener('change', changeStub);

    const option = element.shadowRoot.querySelector('button');
    option.click();

    sinon.assert.notCalled(changeStub);
  });

  it('selected value highlighted and has aria-current="true"', async () => {
    element.options = [
      {value: 'test', text: 'test'},
      {value: 'selected', text: 'highlighted!'},
    ];
    element.value = 'selected';

    await element.updateComplete;

    const options = element.shadowRoot.querySelectorAll('button');

    assert.isFalse(options[0].hasAttribute('selected'));
    assert.isTrue(options[1].hasAttribute('selected'));

    assert.equal(options[0].getAttribute('aria-current'), 'false');
    assert.equal(options[1].getAttribute('aria-current'), 'true');
  });

  it('renders <a> tags when url set', async () => {
    element.options = [
      {value: 'test', text: 'test', url: 'http://google.com/'},
    ];

    await element.updateComplete;

    const options = element.shadowRoot.querySelectorAll('a');

    assert.equal(options[0].textContent.trim(), 'test');
    assert.equal(options[0].href, 'http://google.com/');
  });

  it('selected value highlighted for <a> tags', async () => {
    element.options = [
      {value: 'test', text: 'test', url: 'http://google.com/'},
      {value: 'selected', text: 'highlighted!', url: 'http://localhost/'},
    ];
    element.value = 'selected';

    await element.updateComplete;

    const options = element.shadowRoot.querySelectorAll('a');

    assert.isFalse(options[0].hasAttribute('selected'));
    assert.isTrue(options[1].hasAttribute('selected'));
  });
});
