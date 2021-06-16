// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {prpcClient} from 'prpc-client-instance.js';
import * as projectV0 from './projectV0.js';
import {store} from './base.js';
import * as example from 'shared/test/constants-projectV0.js';
import {fieldTypes, SITEWIDE_DEFAULT_COLUMNS} from 'shared/issue-fields.js';

describe('project reducers', () => {
  it('root reducer initial state', () => {
    const actual = projectV0.reducer(undefined, {type: null});
    const expected = {
      name: null,
      configs: {},
      presentationConfigs: {},
      customPermissions: {},
      visibleMembers: {},
      templates: {},
      requests: {
        fetchConfig: {
          error: null,
          requesting: false,
        },
        fetchCustomPermissions: {
          error: null,
          requesting: false,
        },
        fetchMembers: {
          error: null,
          requesting: false,
        },
        fetchPresentationConfig: {
          error: null,
          requesting: false,
        },
        fetchTemplates: {
          error: null,
          requesting: false,
        },
      },
    };
    assert.deepEqual(actual, expected);
  });

  it('name', () => {
    const action = {type: projectV0.SELECT, projectName: example.PROJECT_NAME};
    assert.deepEqual(projectV0.nameReducer(null, action), example.PROJECT_NAME);
  });

  it('configs updates when fetching Config', () => {
    const action = {
      type: projectV0.FETCH_CONFIG_SUCCESS,
      projectName: example.PROJECT_NAME,
      config: example.CONFIG,
    };
    const expected = {[example.PROJECT_NAME]: example.CONFIG};
    assert.deepEqual(projectV0.configsReducer({}, action), expected);
  });

  it('customPermissions', () => {
    const action = {
      type: projectV0.FETCH_CUSTOM_PERMISSIONS_SUCCESS,
      projectName: example.PROJECT_NAME,
      permissions: example.CUSTOM_PERMISSIONS,
    };
    const expected = {[example.PROJECT_NAME]: example.CUSTOM_PERMISSIONS};
    assert.deepEqual(projectV0.customPermissionsReducer({}, action), expected);
  });

  it('presentationConfigs', () => {
    const action = {
      type: projectV0.FETCH_PRESENTATION_CONFIG_SUCCESS,
      projectName: example.PROJECT_NAME,
      presentationConfig: example.PRESENTATION_CONFIG,
    };
    const expected = {[example.PROJECT_NAME]: example.PRESENTATION_CONFIG};
    assert.deepEqual(projectV0.presentationConfigsReducer({}, action),
      expected);
  });

  it('visibleMembers', () => {
    const action = {
      type: projectV0.FETCH_VISIBLE_MEMBERS_SUCCESS,
      projectName: example.PROJECT_NAME,
      visibleMembers: example.VISIBLE_MEMBERS,
    };
    const expected = {[example.PROJECT_NAME]: example.VISIBLE_MEMBERS};
    assert.deepEqual(projectV0.visibleMembersReducer({}, action), expected);
  });

  it('templates', () => {
    const action = {
      type: projectV0.FETCH_TEMPLATES_SUCCESS,
      projectName: example.PROJECT_NAME,
      templates: [example.TEMPLATE_DEF],
    };
    const expected = {[example.PROJECT_NAME]: [example.TEMPLATE_DEF]};
    assert.deepEqual(projectV0.templatesReducer({}, action), expected);
  });
});

describe('project selectors', () => {
  it('viewedProjectName', () => {
    const actual = projectV0.viewedProjectName(example.STATE);
    assert.deepEqual(actual, example.PROJECT_NAME);
  });

  it('viewedVisibleMembers', () => {
    assert.deepEqual(projectV0.viewedVisibleMembers({}), {});
    assert.deepEqual(projectV0.viewedVisibleMembers({projectV0: {}}), {});
    assert.deepEqual(projectV0.viewedVisibleMembers(
        {projectV0: {visibleMembers: {}}}), {});
    const actual = projectV0.viewedVisibleMembers(example.STATE);
    assert.deepEqual(actual, example.VISIBLE_MEMBERS);
  });

  it('viewedPresentationConfig', () => {
    assert.deepEqual(projectV0.viewedPresentationConfig({}), {});
    assert.deepEqual(projectV0.viewedPresentationConfig({projectV0: {}}), {});
    const actual = projectV0.viewedPresentationConfig(example.STATE);
    assert.deepEqual(actual, example.PRESENTATION_CONFIG);
  });

  it('defaultColumns', () => {
    assert.deepEqual(projectV0.defaultColumns({}), SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(
        projectV0.defaultColumns({projectV0: {}}), SITEWIDE_DEFAULT_COLUMNS);
    assert.deepEqual(
        projectV0.defaultColumns({projectV0: {presentationConfig: {}}}),
        SITEWIDE_DEFAULT_COLUMNS);
    const expected = ['ID', 'Summary', 'AllLabels'];
    assert.deepEqual(projectV0.defaultColumns(example.STATE), expected);
  });

  it('defaultQuery', () => {
    assert.deepEqual(projectV0.defaultQuery({}), '');
    assert.deepEqual(projectV0.defaultQuery({projectV0: {}}), '');
    const actual = projectV0.defaultQuery(example.STATE);
    assert.deepEqual(actual, example.DEFAULT_QUERY);
  });

  it('fieldDefs', () => {
    assert.deepEqual(projectV0.fieldDefs({projectV0: {}}), []);
    assert.deepEqual(projectV0.fieldDefs({projectV0: {config: {}}}), []);
    const actual = projectV0.fieldDefs(example.STATE);
    assert.deepEqual(actual, example.FIELD_DEFS);
  });

  it('labelDefMap', () => {
    assert.deepEqual(projectV0.labelDefMap({projectV0: {}}), new Map());
    assert.deepEqual(projectV0.labelDefMap({projectV0: {config: {}}}),
        new Map());
    const expected = new Map([
      ['one', {label: 'One'}],
      ['enum', {label: 'EnUm'}],
      ['enum-options', {label: 'eNuM-Options'}],
      ['hello-world', {label: 'hello-world', docstring: 'hmmm'}],
      ['hello-me', {label: 'hello-me', docstring: 'hmmm'}],
    ]);
    assert.deepEqual(projectV0.labelDefMap(example.STATE), expected);
  });

  it('labelPrefixValueMap', () => {
    assert.deepEqual(projectV0.labelPrefixValueMap({projectV0: {}}),
        new Map());
    assert.deepEqual(projectV0.labelPrefixValueMap(
        {projectV0: {config: {}}}), new Map());
    const expected = new Map([
      ['eNuM', new Set(['Options'])],
      ['hello', new Set(['world', 'me'])],
    ]);
    assert.deepEqual(projectV0.labelPrefixValueMap(example.STATE), expected);
  });

  it('labelPrefixFields', () => {
    assert.deepEqual(projectV0.labelPrefixFields({projectV0: {}}), []);
    assert.deepEqual(projectV0.labelPrefixFields({projectV0: {config: {}}}),
        []);
    const expected = ['hello'];
    assert.deepEqual(projectV0.labelPrefixFields(example.STATE), expected);
  });

  it('enumFieldDefs', () => {
    assert.deepEqual(projectV0.enumFieldDefs({projectV0: {}}), []);
    assert.deepEqual(projectV0.enumFieldDefs({projectV0: {config: {}}}), []);
    const expected = [example.FIELD_DEF_ENUM];
    assert.deepEqual(projectV0.enumFieldDefs(example.STATE), expected);
  });

  it('optionsPerEnumField', () => {
    assert.deepEqual(projectV0.optionsPerEnumField({projectV0: {}}), new Map());
    const expected = new Map([
      ['enum', [
        {label: 'eNuM-Options', optionName: 'Options'},
      ]],
    ]);
    assert.deepEqual(projectV0.optionsPerEnumField(example.STATE), expected);
  });

  it('viewedPresentationConfigLoaded', () => {
    const loadConfigAction = {
      type: projectV0.FETCH_PRESENTATION_CONFIG_SUCCESS,
      projectName: example.PROJECT_NAME,
      presentationConfig: example.PRESENTATION_CONFIG,
    };
    const selectProjectAction = {
      type: projectV0.SELECT,
      projectName: example.PROJECT_NAME,
    };
    let projectState = {};

    assert.equal(false, projectV0.viewedPresentationConfigLoaded(
        {projectV0: projectState}));

    projectState = projectV0.reducer(projectState, selectProjectAction);
    projectState = projectV0.reducer(projectState, loadConfigAction);

    assert.equal(true, projectV0.viewedPresentationConfigLoaded(
        {projectV0: projectState}));
  });

  it('fetchingPresentationConfig', () => {
    const projectState = projectV0.reducer(undefined, {type: null});
    assert.equal(false,
        projectState.requests.fetchPresentationConfig.requesting);
  });

  describe('extractTypeForFieldName', () => {
    let typeExtractor;

    describe('built-in fields', () => {
      beforeEach(() => {
        typeExtractor = projectV0.extractTypeForFieldName({});
      });

      it('not case sensitive', () => {
        assert.deepEqual(typeExtractor('id'), fieldTypes.ISSUE_TYPE);
        assert.deepEqual(typeExtractor('iD'), fieldTypes.ISSUE_TYPE);
        assert.deepEqual(typeExtractor('Id'), fieldTypes.ISSUE_TYPE);
      });

      it('gets type for ID', () => {
        assert.deepEqual(typeExtractor('ID'), fieldTypes.ISSUE_TYPE);
      });

      it('gets type for Project', () => {
        assert.deepEqual(typeExtractor('Project'), fieldTypes.PROJECT_TYPE);
      });

      it('gets type for Attachments', () => {
        assert.deepEqual(typeExtractor('Attachments'), fieldTypes.INT_TYPE);
      });

      it('gets type for AllLabels', () => {
        assert.deepEqual(typeExtractor('AllLabels'), fieldTypes.LABEL_TYPE);
      });

      it('gets type for AllLabels', () => {
        assert.deepEqual(typeExtractor('AllLabels'), fieldTypes.LABEL_TYPE);
      });

      it('gets type for Blocked', () => {
        assert.deepEqual(typeExtractor('Blocked'), fieldTypes.STR_TYPE);
      });

      it('gets type for BlockedOn', () => {
        assert.deepEqual(typeExtractor('BlockedOn'), fieldTypes.ISSUE_TYPE);
      });

      it('gets type for Blocking', () => {
        assert.deepEqual(typeExtractor('Blocking'), fieldTypes.ISSUE_TYPE);
      });

      it('gets type for CC', () => {
        assert.deepEqual(typeExtractor('CC'), fieldTypes.USER_TYPE);
      });

      it('gets type for Closed', () => {
        assert.deepEqual(typeExtractor('Closed'), fieldTypes.TIME_TYPE);
      });

      it('gets type for Component', () => {
        assert.deepEqual(typeExtractor('Component'), fieldTypes.COMPONENT_TYPE);
      });

      it('gets type for ComponentModified', () => {
        assert.deepEqual(typeExtractor('ComponentModified'),
            fieldTypes.TIME_TYPE);
      });

      it('gets type for MergedInto', () => {
        assert.deepEqual(typeExtractor('MergedInto'), fieldTypes.ISSUE_TYPE);
      });

      it('gets type for Modified', () => {
        assert.deepEqual(typeExtractor('Modified'), fieldTypes.TIME_TYPE);
      });

      it('gets type for Reporter', () => {
        assert.deepEqual(typeExtractor('Reporter'), fieldTypes.USER_TYPE);
      });

      it('gets type for Stars', () => {
        assert.deepEqual(typeExtractor('Stars'), fieldTypes.INT_TYPE);
      });

      it('gets type for Status', () => {
        assert.deepEqual(typeExtractor('Status'), fieldTypes.STATUS_TYPE);
      });

      it('gets type for StatusModified', () => {
        assert.deepEqual(typeExtractor('StatusModified'), fieldTypes.TIME_TYPE);
      });

      it('gets type for Summary', () => {
        assert.deepEqual(typeExtractor('Summary'), fieldTypes.STR_TYPE);
      });

      it('gets type for Type', () => {
        assert.deepEqual(typeExtractor('Type'), fieldTypes.ENUM_TYPE);
      });

      it('gets type for Owner', () => {
        assert.deepEqual(typeExtractor('Owner'), fieldTypes.USER_TYPE);
      });

      it('gets type for OwnerModified', () => {
        assert.deepEqual(typeExtractor('OwnerModified'), fieldTypes.TIME_TYPE);
      });

      it('gets type for Opened', () => {
        assert.deepEqual(typeExtractor('Opened'), fieldTypes.TIME_TYPE);
      });
    });

    it('gets types for custom fields', () => {
      typeExtractor = projectV0.extractTypeForFieldName({projectV0: {
        name: example.PROJECT_NAME,
        configs: {[example.PROJECT_NAME]: {fieldDefs: [
          {fieldRef: {fieldName: 'CustomIntField', type: 'INT_TYPE'}},
          {fieldRef: {fieldName: 'CustomStrField', type: 'STR_TYPE'}},
          {fieldRef: {fieldName: 'CustomUserField', type: 'USER_TYPE'}},
          {fieldRef: {fieldName: 'CustomEnumField', type: 'ENUM_TYPE'}},
          {fieldRef: {fieldName: 'CustomApprovalField',
            type: 'APPROVAL_TYPE'}},
        ]}},
      }});

      assert.deepEqual(typeExtractor('CustomIntField'), fieldTypes.INT_TYPE);
      assert.deepEqual(typeExtractor('CustomStrField'), fieldTypes.STR_TYPE);
      assert.deepEqual(typeExtractor('CustomUserField'), fieldTypes.USER_TYPE);
      assert.deepEqual(typeExtractor('CustomEnumField'), fieldTypes.ENUM_TYPE);
      assert.deepEqual(typeExtractor('CustomApprovalField'),
          fieldTypes.APPROVAL_TYPE);
    });

    it('defaults to string type for other fields', () => {
      typeExtractor = projectV0.extractTypeForFieldName({projectV0: {
        name: example.PROJECT_NAME,
        configs: {[example.PROJECT_NAME]: {fieldDefs: [
          {fieldRef: {fieldName: 'CustomIntField', type: 'INT_TYPE'}},
          {fieldRef: {fieldName: 'CustomUserField', type: 'USER_TYPE'}},
        ]}},
      }});

      assert.deepEqual(typeExtractor('FakeUserField'), fieldTypes.STR_TYPE);
      assert.deepEqual(typeExtractor('NotOwner'), fieldTypes.STR_TYPE);
    });
  });

  describe('extractFieldValuesFromIssue', () => {
    let clock;
    let issue;
    let fieldExtractor;

    describe('built-in fields', () => {
      beforeEach(() => {
        // Built-in fields will always act the same, regardless of
        // project config.
        fieldExtractor = projectV0.extractFieldValuesFromIssue({});

        // Set clock to some specified date for relative time.
        const initialTime = 365 * 24 * 60 * 60;

        issue = {
          localId: 33,
          projectName: 'chromium',
          summary: 'Test summary',
          attachmentCount: 22,
          starCount: 2,
          componentRefs: [{path: 'Infra'}, {path: 'Monorail>UI'}],
          blockedOnIssueRefs: [{localId: 30, projectName: 'chromium'}],
          blockingIssueRefs: [{localId: 60, projectName: 'chromium'}],
          labelRefs: [{label: 'Restrict-View-Google'}, {label: 'Type-Defect'}],
          reporterRef: {displayName: 'test@example.com'},
          ccRefs: [{displayName: 'test@example.com'}],
          ownerRef: {displayName: 'owner@example.com'},
          closedTimestamp: initialTime - 120, // 2 minutes ago
          modifiedTimestamp: initialTime - 60, // a minute ago
          openedTimestamp: initialTime - 24 * 60 * 60, // a day ago
          componentModifiedTimestamp: initialTime - 60, // a minute ago
          statusModifiedTimestamp: initialTime - 60, // a minute ago
          ownerModifiedTimestamp: initialTime - 60, // a minute ago
          statusRef: {status: 'Duplicate'},
          mergedIntoIssueRef: {localId: 31, projectName: 'chromium'},
        };

        clock = sinon.useFakeTimers({
          now: new Date(initialTime * 1000),
          shouldAdvanceTime: false,
        });
      });

      afterEach(() => {
        clock.restore();
      });

      it('computes strings for ID', () => {
        const fieldName = 'ID';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['chromium:33']);
      });

      it('computes strings for Project', () => {
        const fieldName = 'Project';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['chromium']);
      });

      it('computes strings for Attachments', () => {
        const fieldName = 'Attachments';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['22']);
      });

      it('computes strings for AllLabels', () => {
        const fieldName = 'AllLabels';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['Restrict-View-Google', 'Type-Defect']);
      });

      it('computes strings for Blocked when issue is blocked', () => {
        const fieldName = 'Blocked';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['Yes']);
      });

      it('computes strings for Blocked when issue is not blocked', () => {
        const fieldName = 'Blocked';
        issue.blockedOnIssueRefs = [];

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['No']);
      });

      it('computes strings for BlockedOn', () => {
        const fieldName = 'BlockedOn';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['chromium:30']);
      });

      it('computes strings for Blocking', () => {
        const fieldName = 'Blocking';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['chromium:60']);
      });

      it('computes strings for CC', () => {
        const fieldName = 'CC';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['test@example.com']);
      });

      it('computes strings for Closed', () => {
        const fieldName = 'Closed';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['2 minutes ago']);
      });

      it('computes strings for Component', () => {
        const fieldName = 'Component';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['Infra', 'Monorail>UI']);
      });

      it('computes strings for ComponentModified', () => {
        const fieldName = 'ComponentModified';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['a minute ago']);
      });

      it('computes strings for MergedInto', () => {
        const fieldName = 'MergedInto';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['chromium:31']);
      });

      it('computes strings for Modified', () => {
        const fieldName = 'Modified';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['a minute ago']);
      });

      it('computes strings for Reporter', () => {
        const fieldName = 'Reporter';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['test@example.com']);
      });

      it('computes strings for Stars', () => {
        const fieldName = 'Stars';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['2']);
      });

      it('computes strings for Status', () => {
        const fieldName = 'Status';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['Duplicate']);
      });

      it('computes strings for StatusModified', () => {
        const fieldName = 'StatusModified';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['a minute ago']);
      });

      it('computes strings for Summary', () => {
        const fieldName = 'Summary';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['Test summary']);
      });

      it('computes strings for Type', () => {
        const fieldName = 'Type';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['Defect']);
      });

      it('computes strings for Owner', () => {
        const fieldName = 'Owner';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['owner@example.com']);
      });

      it('computes strings for OwnerModified', () => {
        const fieldName = 'OwnerModified';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['a minute ago']);
      });

      it('computes strings for Opened', () => {
        const fieldName = 'Opened';

        assert.deepEqual(fieldExtractor(issue, fieldName),
            ['a day ago']);
      });
    });

    describe('custom approval fields', () => {
      beforeEach(() => {
        const fieldDefs = [
          {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Goose-Approval'}},
          {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Chicken-Approval'}},
          {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Dodo-Approval'}},
        ];
        fieldExtractor = projectV0.extractFieldValuesFromIssue({
          projectV0: {
            name: example.PROJECT_NAME,
            configs: {
              [example.PROJECT_NAME]: {
                projectName: 'chromium',
                fieldDefs,
              },
            },
          },
        });

        issue = {
          localId: 33,
          projectName: 'bird',
          approvalValues: [
            {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Goose-Approval'},
              approverRefs: []},
            {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Chicken-Approval'},
              status: 'APPROVED'},
            {fieldRef: {type: 'APPROVAL_TYPE', fieldName: 'Dodo-Approval'},
              status: 'NEED_INFO', approverRefs: [
                {displayName: 'kiwi@bird.test'},
                {displayName: 'mini-dino@bird.test'},
              ],
            },
          ],
        };
      });

      it('handles approval approver columns', () => {
        assert.deepEqual(fieldExtractor(issue, 'goose-approval-approver'), []);
        assert.deepEqual(fieldExtractor(issue, 'chicken-approval-approver'),
            []);
        assert.deepEqual(fieldExtractor(issue, 'dodo-approval-approver'),
            ['kiwi@bird.test', 'mini-dino@bird.test']);
      });

      it('handles approval value columns', () => {
        assert.deepEqual(fieldExtractor(issue, 'goose-approval'), ['NotSet']);
        assert.deepEqual(fieldExtractor(issue, 'chicken-approval'),
            ['Approved']);
        assert.deepEqual(fieldExtractor(issue, 'dodo-approval'),
            ['NeedInfo']);
      });
    });

    describe('custom fields', () => {
      beforeEach(() => {
        const fieldDefs = [
          {fieldRef: {type: 'STR_TYPE', fieldName: 'aString'}},
          {fieldRef: {type: 'ENUM_TYPE', fieldName: 'ENUM'}},
          {fieldRef: {type: 'INT_TYPE', fieldName: 'Cow-Number'},
            bool_is_phase_field: true, is_multivalued: true},
        ];
        // As a label prefix, aString conflicts with the custom field named
        // "aString". In this case, Monorail gives precedence to the
        // custom field.
        const labelDefs = [
          {label: 'aString-ignore'},
          {label: 'aString-two'},
        ];
        fieldExtractor = projectV0.extractFieldValuesFromIssue({
          projectV0: {
            name: example.PROJECT_NAME,
            configs: {
              [example.PROJECT_NAME]: {
                projectName: 'chromium',
                fieldDefs,
                labelDefs,
              },
            },
          },
        });

        const fieldValues = [
          {fieldRef: {type: 'STR_TYPE', fieldName: 'aString'},
            value: 'test'},
          {fieldRef: {type: 'STR_TYPE', fieldName: 'aString'},
            value: 'test2'},
          {fieldRef: {type: 'ENUM_TYPE', fieldName: 'ENUM'},
            value: 'a-value'},
          {fieldRef: {type: 'INT_TYPE', fieldId: '6', fieldName: 'Cow-Number'},
            phaseRef: {phaseName: 'Cow-Phase'}, value: '55'},
          {fieldRef: {type: 'INT_TYPE', fieldId: '6', fieldName: 'Cow-Number'},
            phaseRef: {phaseName: 'Cow-Phase'}, value: '54'},
          {fieldRef: {type: 'INT_TYPE', fieldId: '6', fieldName: 'Cow-Number'},
            phaseRef: {phaseName: 'MilkCow-Phase'}, value: '56'},
        ];

        issue = {
          localId: 33,
          projectName: 'chromium',
          fieldValues,
        };
      });

      it('gets values for custom fields', () => {
        assert.deepEqual(fieldExtractor(issue, 'aString'), ['test', 'test2']);
        assert.deepEqual(fieldExtractor(issue, 'enum'), ['a-value']);
        assert.deepEqual(fieldExtractor(issue, 'cow-phase.cow-number'),
            ['55', '54']);
        assert.deepEqual(fieldExtractor(issue, 'milkcow-phase.cow-number'),
            ['56']);
      });

      it('custom fields get precedence over label fields', () => {
        issue.labelRefs = [{label: 'aString-ignore'}];
        assert.deepEqual(fieldExtractor(issue, 'aString'),
            ['test', 'test2']);
      });
    });

    describe('label prefix fields', () => {
      beforeEach(() => {
        issue = {
          localId: 33,
          projectName: 'chromium',
          labelRefs: [
            {label: 'test-label'},
            {label: 'test-label-2'},
            {label: 'ignore-me'},
            {label: 'Milestone-UI'},
            {label: 'Milestone-Goodies'},
          ],
        };

        fieldExtractor = projectV0.extractFieldValuesFromIssue({
          projectV0: {
            name: example.PROJECT_NAME,
            configs: {
              [example.PROJECT_NAME]: {
                projectName: 'chromium',
                labelDefs: [
                  {label: 'test-1'},
                  {label: 'test-2'},
                  {label: 'milestone-1'},
                  {label: 'milestone-2'},
                ],
              },
            },
          },
        });
      });

      it('gets values for label prefixes', () => {
        assert.deepEqual(fieldExtractor(issue, 'test'), ['label', 'label-2']);
        assert.deepEqual(fieldExtractor(issue, 'Milestone'), ['UI', 'Goodies']);
      });
    });
  });

  it('fieldDefsByApprovalName', () => {
    assert.deepEqual(projectV0.fieldDefsByApprovalName({projectV0: {}}),
        new Map());

    assert.deepEqual(projectV0.fieldDefsByApprovalName({projectV0: {
      name: example.PROJECT_NAME,
      configs: {[example.PROJECT_NAME]: {
        fieldDefs: [
          {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
          {fieldRef: {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
          {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
          {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
          {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
        ],
      }},
    }}), new Map([
      ['ThisIsAnApproval', [
        {fieldRef: {fieldName: 'yay', approvalName: 'ThisIsAnApproval'}},
        {fieldRef: {fieldName: 'ImAField', approvalName: 'ThisIsAnApproval'}},
      ]],
      ['Legal', [
        {fieldRef: {fieldName: 'TalkToALawyer', approvalName: 'Legal'}},
      ]],
    ]));
  });
});

let dispatch;

describe('project action creators', () => {
  beforeEach(() => {
    sinon.stub(prpcClient, 'call');

    dispatch = sinon.stub();
  });

  afterEach(() => {
    prpcClient.call.restore();
  });

  it('select', () => {
    projectV0.select('project-name')(dispatch);
    const action = {type: projectV0.SELECT, projectName: 'project-name'};
    sinon.assert.calledWith(dispatch, action);
  });

  it('fetchCustomPermissions', async () => {
    const action = projectV0.fetchCustomPermissions('chromium');

    prpcClient.call.returns(Promise.resolve({permissions: ['google']}));

    await action(dispatch);

    sinon.assert.calledWith(dispatch,
        {type: projectV0.FETCH_CUSTOM_PERMISSIONS_START});

    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Projects',
        'GetCustomPermissions',
        {projectName: 'chromium'});

    sinon.assert.calledWith(dispatch, {
      type: projectV0.FETCH_CUSTOM_PERMISSIONS_SUCCESS,
      projectName: 'chromium',
      permissions: ['google'],
    });
  });

  it('fetchPresentationConfig', async () => {
    const action = projectV0.fetchPresentationConfig('chromium');

    prpcClient.call.returns(Promise.resolve({projectThumbnailUrl: 'test'}));

    await action(dispatch);

    sinon.assert.calledWith(dispatch,
        {type: projectV0.FETCH_PRESENTATION_CONFIG_START});

    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Projects',
        'GetPresentationConfig',
        {projectName: 'chromium'});

    sinon.assert.calledWith(dispatch, {
      type: projectV0.FETCH_PRESENTATION_CONFIG_SUCCESS,
      projectName: 'chromium',
      presentationConfig: {projectThumbnailUrl: 'test'},
    });
  });

  it('fetchVisibleMembers', async () => {
    const action = projectV0.fetchVisibleMembers('chromium');

    prpcClient.call.returns(Promise.resolve({userRefs: [{userId: '123'}]}));

    await action(dispatch);

    sinon.assert.calledWith(dispatch,
        {type: projectV0.FETCH_VISIBLE_MEMBERS_START});

    sinon.assert.calledWith(
        prpcClient.call,
        'monorail.Projects',
        'GetVisibleMembers',
        {projectName: 'chromium'});

    sinon.assert.calledWith(dispatch, {
      type: projectV0.FETCH_VISIBLE_MEMBERS_SUCCESS,
      projectName: 'chromium',
      visibleMembers: {userRefs: [{userId: '123'}]},
    });
  });
});

describe('helpers', () => {
  beforeEach(() => {
    sinon.stub(prpcClient, 'call');
  });

  afterEach(() => {
    prpcClient.call.restore();
  });

  describe('fetchFieldPerms', () => {
    it('fetch field permissions', async () => {
      const projectName = 'proj';
      const fieldDefs = [
        {
          fieldRef: {
            fieldName: 'testField',
            fieldId: 1,
            type: 'ENUM_TYPE',
          },
        },
      ];
      const response = {};
      prpcClient.call.returns(Promise.resolve(response));

      await store.dispatch(projectV0.fetchFieldPerms(projectName, fieldDefs));

      const args = {names: ['projects/proj/fieldDefs/testField']};
      sinon.assert.calledWith(
          prpcClient.call, 'monorail.v3.Permissions',
          'BatchGetPermissionSets', args);
    });
  });
});
