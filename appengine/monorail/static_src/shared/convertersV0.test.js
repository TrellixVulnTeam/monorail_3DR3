// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {UserInputError} from 'shared/errors.js';
import * as exampleUsers from 'shared/test/constants-users.js';
import {displayNameToUserRef, userIdOrDisplayNameToUserRef,
  userNameToId, userV3ToRef, labelStringToRef,
  labelRefToString, labelRefsToStrings, labelRefsToOneWordLabels,
  isOneWordLabel, _makeRestrictionLabel, restrictionLabelsForPermissions,
  fieldDefToName, statusRefToString, statusRefsToStrings,
  componentStringToRef, componentRefToString, componentRefsToStrings,
  issueStringToRef, issueStringToBlockingRef, issueRefToString,
  issueRefToUrl, fieldNameToLabelPrefix, labelNameToLabelPrefixes,
  labelNameToLabelValue, commentListToDescriptionList, valueToFieldValue,
  issueToIssueRef, issueNameToRef, issueNameToRefString, issueToName,
} from './convertersV0.js';

describe('displayNameToUserRef', () => {
  it('converts displayName', () => {
    assert.deepEqual(
        displayNameToUserRef('foo@bar.com'),
        {displayName: 'foo@bar.com'});
  });

  it('throws on invalid email', () => {
    assert.throws(() => displayNameToUserRef('foo'), UserInputError);
  });
});

describe('userIdOrDisplayNameToUserRef', () => {
  it('converts userId', () => {
    assert.throws(() => displayNameToUserRef('foo'));
    assert.deepEqual(
        userIdOrDisplayNameToUserRef('12345678'),
        {userId: 12345678});
  });

  it('converts displayName', () => {
    assert.deepEqual(
        userIdOrDisplayNameToUserRef('foo@bar.com'),
        {displayName: 'foo@bar.com'});
  });

  it('throws if not an email or numeric id', () => {
    assert.throws(() => userIdOrDisplayNameToUserRef('foo'), UserInputError);
  });
});

it('userNameToId', () => {
  assert.deepEqual(userNameToId(exampleUsers.NAME), exampleUsers.ID);
});

it('userV3ToRef', () => {
  assert.deepEqual(userV3ToRef(exampleUsers.USER), exampleUsers.USER_REF);
});

describe('labelStringToRef', () => {
  it('converts label', () => {
    assert.deepEqual(labelStringToRef('foo'), {label: 'foo'});
  });
});

describe('labelRefToString', () => {
  it('converts labelRef', () => {
    assert.deepEqual(labelRefToString({label: 'foo'}), 'foo');
  });
});

describe('labelRefsToStrings', () => {
  it('converts labelRefs', () => {
    assert.deepEqual(labelRefsToStrings([{label: 'foo'}, {label: 'test'}]),
        ['foo', 'test']);
  });
});

describe('labelRefsToOneWordLabels', () => {
  it('empty', () => {
    assert.deepEqual(labelRefsToOneWordLabels(), []);
    assert.deepEqual(labelRefsToOneWordLabels([]), []);
  });

  it('filters multi-word labels', () => {
    assert.deepEqual(labelRefsToOneWordLabels([
      {label: 'hello'},
      {label: 'filter-me'},
      {label: 'hello-world'},
      {label: 'world'},
      {label: 'this-label-has-so-many-words'},
    ]), [
      {label: 'hello'},
      {label: 'world'},
    ]);
  });
});

describe('isOneWordLabel', () => {
  it('true only for one word labels', () => {
    assert.isTrue(isOneWordLabel('test'));
    assert.isTrue(isOneWordLabel('LABEL'));
    assert.isTrue(isOneWordLabel('Security'));

    assert.isFalse(isOneWordLabel('Restrict-View-EditIssue'));
    assert.isFalse(isOneWordLabel('Type-Feature'));
  });
});

describe('_makeRestrictionLabel', () => {
  it('creates label', () => {
    assert.deepEqual(_makeRestrictionLabel('View', 'Google'), {
      label: `Restrict-View-Google`,
      docstring: `Permission Google needed to use View`,
    });
  });

  it('capitalizes permission name', () => {
    assert.deepEqual(_makeRestrictionLabel('EditIssue', 'security'), {
      label: `Restrict-EditIssue-Security`,
      docstring: `Permission Security needed to use EditIssue`,
    });
  });
});

describe('restrictionLabelsForPermissions', () => {
  it('creates labels for permissions and actions', () => {
    assert.deepEqual(restrictionLabelsForPermissions(['google', 'security'],
        ['View', 'EditIssue'], []), [
      {
        label: 'Restrict-View-Google',
        docstring: 'Permission Google needed to use View',
      }, {
        label: 'Restrict-View-Security',
        docstring: 'Permission Security needed to use View',
      }, {
        label: 'Restrict-EditIssue-Google',
        docstring: 'Permission Google needed to use EditIssue',
      }, {
        label: 'Restrict-EditIssue-Security',
        docstring: 'Permission Security needed to use EditIssue',
      },
    ]);
  });

  it('appends default labels when specified', () => {
    assert.deepEqual(restrictionLabelsForPermissions(['Google'], ['View'], [
      {label: 'Restrict-Hello-World', docstring: 'description of label'},
    ]), [
      {
        label: 'Restrict-View-Google',
        docstring: 'Permission Google needed to use View',
      },
      {label: 'Restrict-Hello-World', docstring: 'description of label'},
    ]);
  });
});

describe('fieldNameToLabelPrefix', () => {
  it('converts fieldName', () => {
    assert.deepEqual(fieldNameToLabelPrefix('test'), 'test-');
    assert.deepEqual(fieldNameToLabelPrefix('test-hello'), 'test-hello-');
    assert.deepEqual(fieldNameToLabelPrefix('WHATEVER'), 'whatever-');
  });
});

describe('labelNameToLabelPrefixes', () => {
  it('converts labelName', () => {
    assert.deepEqual(labelNameToLabelPrefixes('test'), []);
    assert.deepEqual(labelNameToLabelPrefixes('test-hello'), ['test']);
    assert.deepEqual(labelNameToLabelPrefixes('WHATEVER-this-label-is'),
        ['WHATEVER', 'WHATEVER-this', 'WHATEVER-this-label']);
  });
});

describe('labelNameToLabelValue', () => {
  it('returns null when no matching value found in label', () => {
    assert.isNull(labelNameToLabelValue('test-hello', ''));
    assert.isNull(labelNameToLabelValue('', 'test'));
    assert.isNull(labelNameToLabelValue('test-hello', 'hello'));
    assert.isNull(labelNameToLabelValue('test-hello', 'tes'));
    assert.isNull(labelNameToLabelValue('test', 'test'));
  });

  it('converts labelName', () => {
    assert.deepEqual(labelNameToLabelValue('test-hello', 'test'), 'hello');
    assert.deepEqual(labelNameToLabelValue('WHATEVER-this-label-is',
        'WHATEVER'), 'this-label-is');
    assert.deepEqual(labelNameToLabelValue('WHATEVER-this-label-is',
        'WHATEVER-this'), 'label-is');
    assert.deepEqual(labelNameToLabelValue('WHATEVER-this-label-is',
        'WHATEVER-this-label'), 'is');
  });

  it('fieldName is case insenstitive', () => {
    assert.deepEqual(labelNameToLabelValue('test-hello', 'TEST'), 'hello');
    assert.deepEqual(labelNameToLabelValue('test-hello', 'tEsT'), 'hello');
    assert.deepEqual(labelNameToLabelValue('TEST-hello', 'test'), 'hello');
  });
});

describe('fieldDefToName', () => {
  it('converts fieldDef', () => {
    const fieldDef = {fieldRef: {fieldName: 'field-name'}};
    const actual = fieldDefToName('project-name', fieldDef);
    assert.equal(actual, 'projects/project-name/fieldDefs/field-name');
  });
});

describe('statusRefToString', () => {
  it('converts statusRef', () => {
    assert.deepEqual(statusRefToString({status: 'foo'}), 'foo');
  });
});

describe('statusRefsToStrings', () => {
  it('converts statusRefs', () => {
    assert.deepEqual(statusRefsToStrings(
        [{status: 'hello'}, {status: 'world'}]), ['hello', 'world']);
  });
});

describe('componentStringToRef', () => {
  it('converts component', () => {
    assert.deepEqual(componentStringToRef('foo'), {path: 'foo'});
  });
});

describe('componentRefToString', () => {
  it('converts componentRef', () => {
    assert.deepEqual(componentRefToString({path: 'Hello>World'}),
        'Hello>World');
  });
});

describe('componentRefsToStrings', () => {
  it('converts componentRefs', () => {
    assert.deepEqual(componentRefsToStrings(
        [{path: 'Hello>World'}, {path: 'Test'}]), ['Hello>World', 'Test']);
  });
});

describe('issueStringToRef', () => {
  it('converts issue default project', () => {
    assert.deepEqual(
        issueStringToRef('1234', 'proj'),
        {projectName: 'proj', localId: 1234});
  });

  it('converts issue with project', () => {
    assert.deepEqual(
        issueStringToRef('foo:1234', 'proj'),
        {projectName: 'foo', localId: 1234});
  });

  it('converts external issue references', () => {
    assert.deepEqual(
        issueStringToRef('b/123456', 'proj'),
        {extIdentifier: 'b/123456'});
  });

  it('throws on invalid input', () => {
    assert.throws(() => issueStringToRef('foo', 'proj'));
  });
});

describe('issueStringToBlockingRef', () => {
  it('converts issue default project', () => {
    assert.deepEqual(
        issueStringToBlockingRef({projectName: 'proj', localId: 1}, '1234'),
        {projectName: 'proj', localId: 1234});
  });

  it('converts issue with project', () => {
    assert.deepEqual(
        issueStringToBlockingRef({projectName: 'proj', localId: 1}, 'foo:1234'),
        {projectName: 'foo', localId: 1234});
  });

  it('throws on invalid input', () => {
    assert.throws(() => issueStringToBlockingRef(
        {projectName: 'proj', localId: 1}, 'foo'));
  });

  it('throws when blocking an issue on itself', () => {
    assert.throws(() => issueStringToBlockingRef(
        {projectName: 'proj', localId: 123}, 'proj:123'));
    assert.throws(() => issueStringToBlockingRef(
        {projectName: 'proj', localId: 123}, '123'));
  });
});

describe('issueRefToString', () => {
  it('no ref', () => {
    assert.equal(issueRefToString(), '');
  });

  it('ref with no project name', () => {
    assert.equal(
        'other:1234',
        issueRefToString({projectName: 'other', localId: 1234}),
    );
  });

  it('ref with different project name', () => {
    assert.equal(
        'other:1234',
        issueRefToString({projectName: 'other', localId: 1234}, 'proj'),
    );
  });

  it('ref with same project name', () => {
    assert.equal(
        '1234',
        issueRefToString({projectName: 'proj', localId: 1234}, 'proj'),
    );
  });

  it('external ref', () => {
    assert.equal(
        'b/123456',
        issueRefToString({extIdentifier: 'b/123456'}, 'proj'),
    );
  });
});

describe('issueToIssueRef', () => {
  it('creates ref', () => {
    const issue = {'localId': 1, 'projectName': 'proj', 'starCount': 1};
    const expectedRef = {'localId': 1,
      'projectName': 'proj'};
    assert.deepEqual(issueToIssueRef(issue), expectedRef);
  });
});

describe('issueRefToUrl', () => {
  it('no ref', () => {
    assert.equal(issueRefToUrl(), '');
  });

  it('issue ref', () => {
    assert.equal(issueRefToUrl({
      projectName: 'test',
      localId: 11,
    }), '/p/test/issues/detail?id=11');
  });

  it('issue ref with params', () => {
    assert.equal(issueRefToUrl({
      projectName: 'test',
      localId: 11,
    }, {
      q: 'owner:me',
      id: 44,
    }), '/p/test/issues/detail?id=11&q=owner%3Ame');
  });

  it('federated issue ref', () => {
    assert.equal(issueRefToUrl({
      extIdentifier: 'b/5678',
    }), 'https://issuetracker.google.com/issues/5678');
  });

  it('does not mutate input queryParams', () => {
    const queryParams = {q: 'owner:me', id: 44};
    const EXPECTED = JSON.stringify(queryParams);
    const ref = {projectName: 'test', localId: 11};
    issueRefToUrl(ref, queryParams);
    assert.equal(EXPECTED, JSON.stringify(queryParams));
  });
});

it('issueNameToRef', () => {
  const actual = issueNameToRef('projects/project-name/issues/2');
  assert.deepEqual(actual, {projectName: 'project-name', localId: 2});
});

it('issueNameToRefString', () => {
  const actual = issueNameToRefString('projects/project-name/issues/2');
  assert.equal(actual, 'project-name:2');
});

it('issueToName', () => {
  const actual = issueToName({projectName: 'project-name', localId: 2});
  assert.equal(actual, 'projects/project-name/issues/2');
});

describe('commentListToDescriptionList', () => {
  it('empty list', () => {
    assert.deepEqual(commentListToDescriptionList(), []);
    assert.deepEqual(commentListToDescriptionList([]), []);
  });

  it('first comment is description', () => {
    assert.deepEqual(commentListToDescriptionList([
      {content: 'test'},
      {content: 'hello'},
      {content: 'world'},
    ]), [{content: 'test'}]);
  });

  it('some descriptions', () => {
    assert.deepEqual(commentListToDescriptionList([
      {content: 'test'},
      {content: 'hello', descriptionNum: 1},
      {content: 'world'},
      {content: 'this'},
      {content: 'is a'},
      {content: 'description', descriptionNum: 2},
    ]), [
      {content: 'test'},
      {content: 'hello', descriptionNum: 1},
      {content: 'description', descriptionNum: 2},
    ]);
  });
});

describe('valueToFieldValue', () => {
  it('converts field ref and value', () => {
    assert.deepEqual(valueToFieldValue(
        {fieldName: 'name', fieldId: 'id'},
        'value',
    ), {
      fieldRef: {fieldName: 'name', fieldId: 'id'},
      value: 'value',
    });
  });
});
