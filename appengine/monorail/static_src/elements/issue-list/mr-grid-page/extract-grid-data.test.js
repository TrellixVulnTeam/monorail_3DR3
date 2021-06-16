// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {extractGridData} from './extract-grid-data.js';
import {extractFieldValuesFromIssue as fieldExtractor,
  extractTypeForFieldName as typeExtractor} from 'reducers/projectV0.js';

const extractFieldValuesFromIssue = fieldExtractor({});
const extractTypeForFieldName = typeExtractor({});


describe('extract headings from x and y attributes', () => {
  it('no attributes set', () => {
    const issues = [
      {'localId': 1, 'projectName': 'test'},
      {'localId': 2, 'projectName': 'test'},
    ];

    const data = extractGridData({
      issues,
      extractFieldValuesFromIssue,
    });

    const expectedIssues = new Map([
      ['All + All', [
        {'localId': 1, 'projectName': 'test'},
        {'localId': 2, 'projectName': 'test'},
      ]],
    ]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from Attachments attribute', () => {
    const issues = [
      {'attachmentCount': 1}, {'attachmentCount': 0},
      {'attachmentCount': 1},
    ];

    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: 'Attachments'});

    const expectedIssues = new Map([
      ['0 + All', [{'attachmentCount': 0}]],
      ['1 + All', [{'attachmentCount': 1}, {'attachmentCount': 1}]],
    ]);

    assert.deepEqual(data.xHeadings, ['0', '1']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from Blocked attribute', () => {
    const issues = [
      {'blockedOnIssueRefs': [{'localId': 21}]},
      {'otherIssueProperty': 'issueProperty'},
    ];
    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: 'Blocked', yFieldName: ''});

    const expectedIssues = new Map();
    expectedIssues.set('Yes + All',
        [{'blockedOnIssueRefs': [{'localId': 21}]}]);
    expectedIssues.set('No + All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['No', 'Yes']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from BlockedOn attribute', () => {
    const issues = [
      {'otherIssueProperty': 'issueProperty'},
      {'blockedOnIssueRefs': [
        {'localId': 3, 'projectName': 'test-projectB'}]},
      {'blockedOnIssueRefs': [
        {'localId': 3, 'projectName': 'test-projectA'}]},
      {'blockedOnIssueRefs': [
        {'localId': 3, 'projectName': 'test-projectA'}]},
      {'blockedOnIssueRefs': [
        {'localId': 1, 'projectName': 'test-projectA'}]},
    ];

    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: 'BlockedOn', yFieldName: ''});

    const expectedIssues = new Map();
    expectedIssues.set('test-projectB:3 + All', [{'blockedOnIssueRefs':
      [{'localId': 3, 'projectName': 'test-projectB'}]}]);
    expectedIssues.set('test-projectA:3 + All', [{'blockedOnIssueRefs':
      [{'localId': 3, 'projectName': 'test-projectA'}]},
    {'blockedOnIssueRefs':
      [{'localId': 3, 'projectName': 'test-projectA'}]}]);
    expectedIssues.set('test-projectA:1 + All', [{'blockedOnIssueRefs':
      [{'localId': 1, 'projectName': 'test-projectA'}]}]);
    expectedIssues.set('---- + All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['----', 'test-projectA:1',
      'test-projectA:3', 'test-projectB:3']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from Blocking attribute', () => {
    const issues = [
      {'otherIssueProperty': 'issueProperty'},
      {'blockingIssueRefs': [
        {'localId': 1, 'projectName': 'test-projectA'}]},
      {'blockingIssueRefs': [
        {'localId': 1, 'projectName': 'test-projectA'}]},
      {'blockingIssueRefs': [
        {'localId': 3, 'projectName': 'test-projectA'}]},
      {'blockingIssueRefs': [
        {'localId': 3, 'projectName': 'test-projectB'}]},
    ];
    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: 'Blocking', yFieldName: ''});

    const expectedIssues = new Map();
    expectedIssues.set('test-projectA:1 + All', [{'blockingIssueRefs':
      [{'localId': 1, 'projectName': 'test-projectA'}]},
    {'blockingIssueRefs':
      [{'localId': 1, 'projectName': 'test-projectA'}]}]);
    expectedIssues.set('test-projectA:3 + All', [{'blockingIssueRefs':
      [{'localId': 3, 'projectName': 'test-projectA'}]}]);
    expectedIssues.set('test-projectB:3 + All', [{'blockingIssueRefs':
      [{'localId': 3, 'projectName': 'test-projectB'}]}]);
    expectedIssues.set('---- + All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['----', 'test-projectA:1',
      'test-projectA:3', 'test-projectB:3']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from Component attribute', () => {
    const issues = [
      {'otherIssueProperty': 'issueProperty'},
      {'componentRefs': [{'path': 'UI'}]},
      {'componentRefs': [{'path': 'API'}]},
      {'componentRefs': [{'path': 'UI'}]},
    ];
    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: 'Component', yFieldName: ''});

    const expectedIssues = new Map();
    expectedIssues.set('UI + All', [{'componentRefs': [{'path': 'UI'}]},
      {'componentRefs': [{'path': 'UI'}]}]);
    expectedIssues.set('API + All', [{'componentRefs': [{'path': 'API'}]}]);
    expectedIssues.set('---- + All', [{'otherIssueProperty': 'issueProperty'}]);

    assert.deepEqual(data.xHeadings, ['----', 'API', 'UI']);
    assert.deepEqual(data.yHeadings, ['All']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from Reporter attribute', () => {
    const issues = [
      {'reporterRef': {'displayName': 'testA@google.com'}},
      {'reporterRef': {'displayName': 'testB@google.com'}},
    ];
    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: '', yFieldName: 'Reporter'});

    const expectedIssues = new Map();
    expectedIssues.set('All + testA@google.com',
        [{'reporterRef': {'displayName': 'testA@google.com'}}]);
    expectedIssues.set('All + testB@google.com',
        [{'reporterRef': {'displayName': 'testB@google.com'}}]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['testA@google.com', 'testB@google.com']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from Stars attribute', () => {
    const issues = [
      {'starCount': 1}, {'starCount': 6}, {'starCount': 1},
    ];
    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: '', yFieldName: 'Stars'});

    const expectedIssues = new Map();
    expectedIssues.set('All + 1', [{'starCount': 1}, {'starCount': 1}]);
    expectedIssues.set('All + 6', [{'starCount': 6}]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['1', '6']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from Status in order of statusDefs provided', () => {
    const issues = [
      {'statusRef': {'status': 'New'}},
      {'statusRef': {'status': '1Unknown'}},
      {'statusRef': {'status': 'Accepted'}},
      {'statusRef': {'status': 'New'}},
      {'statusRef': {'status': 'UltraNew'}},
    ];
    const statusDefs = [
      {status: 'UltraNew'}, {status: 'New'}, {status: 'Unused'},
      {status: 'Accepted'},
    ];

    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {yFieldName: 'Status', extractTypeForFieldName, statusDefs});

    const expectedIssues = new Map();
    expectedIssues.set(
        'All + Accepted', [{'statusRef': {'status': 'Accepted'}}]);
    expectedIssues.set(
        'All + New',
        [{'statusRef': {'status': 'New'}}, {'statusRef': {'status': 'New'}}]);
    expectedIssues.set(
        'All + UltraNew', [{'statusRef': {'status': 'UltraNew'}}]);
    expectedIssues.set(
        'All + 1Unknown', [{'statusRef': {'status': '1Unknown'}}]);
    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(
        data.yHeadings, ['UltraNew', 'New', 'Accepted', '1Unknown']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('extract headings from the Type attribute', () => {
    const issues = [
      {'labelRefs': [{'label': 'Pri-2'}, {'label': 'Milestone-2000Q1'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Enhancement'}]},
    ];
    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {yFieldName: 'Type'});

    const expectedIssues = new Map();
    expectedIssues.set('All + Defect', [
      {'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]},
    ]);
    expectedIssues.set('All + Enhancement', [{'labelRefs':
      [{'label': 'Type-Enhancement'}]}]);
    expectedIssues.set('All + ----', [{'labelRefs':
      [{'label': 'Pri-2'}, {'label': 'Milestone-2000Q1'}]}]);

    assert.deepEqual(data.xHeadings, ['All']);
    assert.deepEqual(data.yHeadings, ['----', 'Defect', 'Enhancement']);
    assert.deepEqual(data.groupedIssues, expectedIssues);
  });

  it('puts predefined labels ahead of ad hoc labels', () => {
    const issues = [
      {'labelRefs': [{'label': 'Pri-2'}, {'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Enhancement'}]},
      {'labelRefs': [{'label': 'Type-AAA'}]},
    ];
    const labelPrefixValueMap = new Map([
      ['Pri', new Set(['2'])],
      ['Type', new Set(['Defect', 'Enhancement'])],
    ]);

    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: 'Type', yFieldName: 'Pri', labelPrefixValueMap});

    assert.deepEqual(data.xHeadings, ['Defect', 'Enhancement', 'AAA']);
    assert.deepEqual(data.yHeadings, ['----', '2']);
  });

  it('has priority order of predefined, empty, then ad hoc labels', () => {
    const issues = [
      {'labelRefs': [{'label': 'Pri-2'}, {'label': 'Milestone-2000Q1'}]},
      {'labelRefs': [{'label': 'Type-Defect'}]},
      {'labelRefs': [{'label': 'Type-Enhancement'}]},
      {'labelRefs': [{'label': 'Type-AAA'}]},
    ];
    const labelPrefixValueMap = new Map([
      ['Pri', new Set(['2'])],
      ['Type', new Set(['Defect', 'Enhancement'])],
    ]);

    const data = extractGridData({issues, extractFieldValuesFromIssue},
        {xFieldName: 'Type', yFieldName: 'Pri', labelPrefixValueMap});

    assert.deepEqual(data.xHeadings, ['Defect', 'Enhancement', '----', 'AAA']);
  });
});
