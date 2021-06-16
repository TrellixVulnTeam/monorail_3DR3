// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import qs from 'qs';


/**
 * With lists a and b, get the elements that are in a but not in b.
 * result = a - b
 * @param {Array} listA
 * @param {Array} listB
 * @param {function} equals
 * @return {Array}
 */
export function arrayDifference(listA, listB, equals) {
  if (!equals) {
    equals = (a, b) => (a === b);
  }
  listA = listA || [];
  listB = listB || [];
  return listA.filter((a) => {
    return !listB.find((b) => (equals(a, b)));
  });
}

/**
 * Check to see if a Set contains any of a list of values.
 *
 * @param {Set} set the Set to check for values in.
 * @param {Iterable} values checks if any of these values are included.
 * @return {boolean} whether the Set has any of the values or not.
 */
export function setHasAny(set, values) {
  for (const value of values) {
    if (set.has(value)) {
      return true;
    }
  }
  return false;
}

/**
 * Capitalize the first letter of a given string.
 * @param {string} str
 * @return {string}
 */
export function capitalizeFirst(str) {
  return `${str.charAt(0).toUpperCase()}${str.substring(1)}`;
}

/**
 * Check if a string has a prefix, ignoring case.
 * @param {string} str
 * @param {string} prefix
 * @return {boolean}
 */
export function hasPrefix(str, prefix) {
  return str.toLowerCase().startsWith(prefix.toLowerCase());
}

/**
 * Returns a string without specified prefix
 * @param {string} str
 * @param {string} prefix
 * @return {string}
 */
export function removePrefix(str, prefix) {
  return str.substr(prefix.length);
}

// TODO(zhangtiff): Make this more grammatically correct for
// more than two items.
export function arrayToEnglish(arr) {
  if (!arr) return '';
  return arr.join(' and ');
}

export function pluralize(count, singular, pluralArg) {
  const plural = pluralArg || singular + 's';
  return count === 1 ? singular : plural;
}

export function objectToMap(obj = {}) {
  const map = new Map();
  Object.keys(obj).forEach((key) => {
    map.set(key, obj[key]);
  });
  return map;
}

/**
 * Given an Object, extract a list of values from it, based on some
 * specified keys.
 *
 * @param {Object} obj the Object to read values from.
 * @param {Array} keys the Object keys to fetch values for.
 * @return {Array} Object values matching the given keys.
 */
export function objectValuesForKeys(obj, keys = []) {
  return keys.map((key) => ((key in obj) ? obj[key] : undefined));
}

/**
 * Checks to see if object has no keys
 * @param {Object} obj
 * @return {boolean}
 */
export function isEmptyObject(obj) {
  return Object.keys(obj).length === 0;
}

/**
 * Checks if two strings are equal, case-insensitive
 * @param {string} a
 * @param {string} b
 * @return {boolean}
 */
export function equalsIgnoreCase(a, b) {
  if (a == b) return true;
  if (!a || !b) return false;
  return a.toLowerCase() === b.toLowerCase();
}

export function immutableSplice(arr, index, count, ...addedItems) {
  if (!arr) return '';

  return [...arr.slice(0, index), ...addedItems, ...arr.slice(index + count)];
}

/**
 * Computes a new URL for a page based on an exiting path and set of query
 * params.
 *
 * @param {string} baseUrl the base URL without query params.
 * @param {Object} oldParams original query params before changes.
 * @param {Object} newParams query parameters to override existing ones.
 * @param {Array} deletedParams list of keys to be cleared.
 * @return {string} the new URL with the updated params.
 */
export function urlWithNewParams(baseUrl = '',
    oldParams = {}, newParams = {}, deletedParams = []) {
  const params = {...oldParams, ...newParams};
  deletedParams.forEach((name) => {
    delete params[name];
  });

  const queryString = qs.stringify(params);

  return `${baseUrl}${queryString ? '?' : ''}${queryString}`;
}

/**
 * Finds out whether a user is a member of a given project based on
 * project membership info.
 *
 * @param {Object} userRef reference to a given user. Expects an id.
 * @param {string} projectName name of the project being searched for.
 * @param {Map} usersProjects all known user project memberships where
 *  keys are userId and values are Objects with expected values
 *  for {ownerOf, memberOf, contributorTo}.
 * @return {boolean} whether the user is a member of the project or not.
 */
export function userIsMember(userRef, projectName, usersProjects = new Map()) {
  // TODO(crbug.com/monorail/5968): Find a better place to place this function
  if (!userRef || !userRef.userId || !projectName) return false;
  const userProjects = usersProjects.get(userRef.userId);
  if (!userProjects) return false;
  const {ownerOf = [], memberOf = [], contributorTo = []} = userProjects;
  return ownerOf.includes(projectName) ||
    memberOf.includes(projectName) ||
    contributorTo.includes(projectName);
}

/**
 * Creates a function that checks two objects are not equal
 * based on a set of property keys
 *
 * @param {Set<string>} props
 * @return {function(): boolean}
 */
export function createObjectComparisonFunc(props) {
  /**
   * Computes whether set of properties have changed
   * @param {Object<string, string>} newVal
   * @param {Object<string, string>} oldVal
   * @return {boolean}
   */
  return function(newVal, oldVal) {
    if (oldVal === undefined && newVal === undefined) {
      return false;
    } else if (oldVal === undefined || newVal === undefined) {
      return true;
    } else if (oldVal === null && newVal === null) {
      return false;
    } else if (oldVal === null || newVal === null) {
      return true;
    }

    return Array.from(props)
        .some((propName) => newVal[propName] !== oldVal[propName]);
  };
}

/**
 * Calculates whether to wait for memberDefaultQuery to exist prior
 * to fetching IssueList. Logged in users may use a default query.
 * @param {Object} queryParams
 * @return {boolean}
 */
export const shouldWaitForDefaultQuery = (queryParams) => {
  return !queryParams.hasOwnProperty('q');
};
