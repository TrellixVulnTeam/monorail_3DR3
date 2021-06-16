// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


// Prevent triggering input change handlers on key events that don't
// edit forms.
export const NON_EDITING_KEY_EVENTS = new Set(['Enter', 'Tab', 'Escape',
  'ArrowUp', 'ArrowLeft', 'ArrowRight', 'ArrowDown']);
const INPUT_TYPES_WITHOUT_TEXT_INPUT = [
  'checkbox',
  'radio',
  'file',
  'submit',
  'button',
  'image',
];

// TODO: Add a method to watch for property changes in one of a subset of
// element properties.
// Via: https://crrev.com/c/infra/infra/+/1762911/7/appengine/monorail/static_src/elements/help/mr-cue/mr-cue.js

/**
 * Function to check if a keyboard event should be disabled if
 * the user is typing.
 *
 * @param {HTMLElement} element is a dom node to run checks against.
 * @return {boolean} Whether the dom node is an element that accepts key input.
 */
export function isTextInput(element) {
  const tagName = element.tagName && element.tagName.toUpperCase();
  if (tagName === 'INPUT') {
    const type = element.type.toLowerCase();
    if (INPUT_TYPES_WITHOUT_TEXT_INPUT.includes(type)) {
      return false;
    }
    return true;
  }
  return tagName === 'SELECT' || tagName === 'TEXTAREA' ||
    element.isContentEditable;
}

/**
 * Helper to find the EventTarget that an Event originated from, even if that
 * EventTarget is buried until multiple layers of ShadowDOM.
 *
 * @param {Event} event
 * @return {EventTarget} The DOM node that the event came from. For example,
 *   if the input was a keypress, this might be the input element the user was
 *   typing into.
 */
export function findDeepEventTarget(event) {
  /**
   * Event.target finds the element the event came from, but only
   * finds events that come from the highest ShadowDOM level. For
   * example, an Event listener attached to "window" will have all
   * Events originating from the SPA set to a target of <mr-app>.
   */
  const path = event.composedPath();
  return path ? path[0] : event.target;
}
