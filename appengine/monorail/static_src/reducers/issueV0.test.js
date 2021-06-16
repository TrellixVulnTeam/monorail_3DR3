// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import {createSelector} from 'reselect';
import {store, resetState} from './base.js';
import * as issueV0 from './issueV0.js';
import * as example from 'shared/test/constants-issueV0.js';
import {fieldTypes} from 'shared/issue-fields.js';
import {issueToIssueRef, issueRefToString} from 'shared/convertersV0.js';
import {prpcClient} from 'prpc-client-instance.js';
import {getSigninInstance} from 'shared/gapi-loader.js';

let prpcCall;
let dispatch;

describe('issue', () => {
  beforeEach(() => {
    store.dispatch(resetState());
  });

  describe('reducers', () => {
    describe('issueByRefReducer', () => {
      it('no-op on unmatching action', () => {
        const action = {
          type: 'FAKE_ACTION',
          issues: [example.ISSUE_OTHER_PROJECT],
        };
        assert.deepEqual(issueV0.issuesByRefStringReducer({}, action), {});

        const state = {[example.ISSUE_REF_STRING]: example.ISSUE};
        assert.deepEqual(issueV0.issuesByRefStringReducer(state, action),
            state);
      });

      it('handles FETCH_ISSUE_LIST_UPDATE', () => {
        const newState = issueV0.issuesByRefStringReducer({}, {
          type: issueV0.FETCH_ISSUE_LIST_UPDATE,
          issues: [example.ISSUE, example.ISSUE_OTHER_PROJECT],
          totalResults: 2,
          progress: 1,
        });
        assert.deepEqual(newState, {
          [example.ISSUE_REF_STRING]: example.ISSUE,
          [example.ISSUE_OTHER_PROJECT_REF_STRING]: example.ISSUE_OTHER_PROJECT,
        });
      });

      it('handles FETCH_ISSUES_SUCCESS', () => {
        const newState = issueV0.issuesByRefStringReducer({}, {
          type: issueV0.FETCH_ISSUES_SUCCESS,
          issues: [example.ISSUE, example.ISSUE_OTHER_PROJECT],
        });
        assert.deepEqual(newState, {
          [example.ISSUE_REF_STRING]: example.ISSUE,
          [example.ISSUE_OTHER_PROJECT_REF_STRING]: example.ISSUE_OTHER_PROJECT,
        });
      });
    });

    describe('issueListReducer', () => {
      it('no-op on unmatching action', () => {
        const action = {
          type: 'FETCH_ISSUE_LIST_FAKE_ACTION',
          issues: [
            {localId: 1, projectName: 'chromium', summary: 'hello-world'},
          ],
        };
        assert.deepEqual(issueV0.issueListReducer({}, action), {});

        assert.deepEqual(issueV0.issueListReducer({
          issueRefs: ['chromium:1'],
          totalResults: 1,
          progress: 1,
        }, action), {
          issueRefs: ['chromium:1'],
          totalResults: 1,
          progress: 1,
        });
      });

      it('handles FETCH_ISSUE_LIST_UPDATE', () => {
        const newState = issueV0.issueListReducer({}, {
          type: 'FETCH_ISSUE_LIST_UPDATE',
          issues: [
            {localId: 1, projectName: 'chromium', summary: 'hello-world'},
            {localId: 2, projectName: 'monorail', summary: 'Test'},
          ],
          totalResults: 2,
          progress: 1,
        });
        assert.deepEqual(newState, {
          issueRefs: ['chromium:1', 'monorail:2'],
          totalResults: 2,
          progress: 1,
        });
      });
    });

    describe('relatedIssuesReducer', () => {
      it('handles FETCH_RELATED_ISSUES_SUCCESS', () => {
        const newState = issueV0.relatedIssuesReducer({}, {
          type: 'FETCH_RELATED_ISSUES_SUCCESS',
          relatedIssues: {'rutabaga:1234': {}},
        });
        assert.deepEqual(newState, {'rutabaga:1234': {}});
      });

      describe('FETCH_FEDERATED_REFERENCES_SUCCESS', () => {
        it('returns early if data is missing', () => {
          const newState = issueV0.relatedIssuesReducer({'b/123': {}}, {
            type: 'FETCH_FEDERATED_REFERENCES_SUCCESS',
          });
          assert.deepEqual(newState, {'b/123': {}});
        });

        it('returns early if data is empty', () => {
          const newState = issueV0.relatedIssuesReducer({'b/123': {}}, {
            type: 'FETCH_FEDERATED_REFERENCES_SUCCESS',
            fedRefIssueRefs: [],
          });
          assert.deepEqual(newState, {'b/123': {}});
        });

        it('assigns each FedRef to the state', () => {
          const state = {
            'rutabaga:123': {},
            'rutabaga:345': {},
          };
          const newState = issueV0.relatedIssuesReducer(state, {
            type: 'FETCH_FEDERATED_REFERENCES_SUCCESS',
            fedRefIssueRefs: [
              {
                extIdentifier: 'b/987',
                summary: 'What is up',
                statusRef: {meansOpen: true},
              },
              {
                extIdentifier: 'b/765',
                summary: 'Rutabaga',
                statusRef: {meansOpen: false},
              },
            ],
          });
          assert.deepEqual(newState, {
            'rutabaga:123': {},
            'rutabaga:345': {},
            'b/987': {
              extIdentifier: 'b/987',
              summary: 'What is up',
              statusRef: {meansOpen: true},
            },
            'b/765': {
              extIdentifier: 'b/765',
              summary: 'Rutabaga',
              statusRef: {meansOpen: false},
            },
          });
        });
      });
    });
  });

  it('viewedIssue', () => {
    assert.deepEqual(issueV0.viewedIssue(wrapIssue()), {});
    assert.deepEqual(
        issueV0.viewedIssue(wrapIssue({projectName: 'proj', localId: 100})),
        {projectName: 'proj', localId: 100},
    );
  });

  describe('issueList', () => {
    it('issueList', () => {
      const stateWithEmptyIssueList = {issue: {
        issueList: {},
      }};
      assert.deepEqual(issueV0.issueList(stateWithEmptyIssueList), []);

      const stateWithIssueList = {issue: {
        issuesByRefString: {
          'chromium:1': {localId: 1, projectName: 'chromium', summary: 'test'},
          'monorail:2': {localId: 2, projectName: 'monorail',
            summary: 'hello world'},
        },
        issueList: {
          issueRefs: ['chromium:1', 'monorail:2'],
        }}};
      assert.deepEqual(issueV0.issueList(stateWithIssueList),
          [
            {localId: 1, projectName: 'chromium', summary: 'test'},
            {localId: 2, projectName: 'monorail', summary: 'hello world'},
          ]);
    });

    it('is a selector', () => {
      issueV0.issueList.constructor === createSelector;
    });

    it('memoizes results: returns same reference', () => {
      const stateWithIssueList = {issue: {
        issuesByRefString: {
          'chromium:1': {localId: 1, projectName: 'chromium', summary: 'test'},
          'monorail:2': {localId: 2, projectName: 'monorail',
            summary: 'hello world'},
        },
        issueList: {
          issueRefs: ['chromium:1', 'monorail:2'],
        }}};
      const reference1 = issueV0.issueList(stateWithIssueList);
      const reference2 = issueV0.issueList(stateWithIssueList);

      assert.equal(typeof reference1, 'object');
      assert.equal(typeof reference2, 'object');
      assert.equal(reference1, reference2);
    });
  });

  describe('issueListLoaded', () => {
    const stateWithEmptyIssueList = {issue: {
      issueList: {},
    }};

    it('false when no issue list', () => {
      assert.isFalse(issueV0.issueListLoaded(stateWithEmptyIssueList));
    });

    it('true after issues loaded, even when empty', () => {
      const issueList = issueV0.issueListReducer({}, {
        type: issueV0.FETCH_ISSUE_LIST_UPDATE,
        issues: [],
        progress: 1,
        totalResults: 0,
      });
      assert.isTrue(issueV0.issueListLoaded({issue: {issueList}}));
    });
  });

  it('fieldValues', () => {
    assert.isUndefined(issueV0.fieldValues(wrapIssue()));
    assert.deepEqual(issueV0.fieldValues(wrapIssue({
      fieldValues: [{value: 'v'}],
    })), [{value: 'v'}]);
  });

  it('type computes type from custom field', () => {
    assert.isUndefined(issueV0.type(wrapIssue()));
    assert.isUndefined(issueV0.type(wrapIssue({
      fieldValues: [{value: 'v'}],
    })));
    assert.deepEqual(issueV0.type(wrapIssue({
      fieldValues: [
        {fieldRef: {fieldName: 'IgnoreMe'}, value: 'v'},
        {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
      ],
    })), 'Defect');
  });

  it('type computes type from label', () => {
    assert.deepEqual(issueV0.type(wrapIssue({
      labelRefs: [
        {label: 'Test'},
        {label: 'tYpE-FeatureRequest'},
      ],
    })), 'FeatureRequest');

    assert.deepEqual(issueV0.type(wrapIssue({
      fieldValues: [
        {fieldRef: {fieldName: 'IgnoreMe'}, value: 'v'},
      ],
      labelRefs: [
        {label: 'Test'},
        {label: 'Type-Defect'},
      ],
    })), 'Defect');
  });

  it('restrictions', () => {
    assert.deepEqual(issueV0.restrictions(wrapIssue()), {});
    assert.deepEqual(issueV0.restrictions(wrapIssue({labelRefs: []})), {});

    assert.deepEqual(issueV0.restrictions(wrapIssue({labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
    ]})), {});

    assert.deepEqual(issueV0.restrictions(wrapIssue({labelRefs: [
      {label: 'IgnoreThis'},
      {label: 'IgnoreThis2'},
      {label: 'Restrict-View-Google'},
      {label: 'Restrict-EditIssue-hello'},
      {label: 'Restrict-EditIssue-test'},
      {label: 'Restrict-AddIssueComment-HELLO'},
    ]})), {
      'view': ['Google'],
      'edit': ['hello', 'test'],
      'comment': ['HELLO'],
    });
  });

  it('isOpen', () => {
    assert.isFalse(issueV0.isOpen(wrapIssue()));
    assert.isTrue(issueV0.isOpen(wrapIssue({statusRef: {meansOpen: true}})));
    assert.isFalse(issueV0.isOpen(wrapIssue({statusRef: {meansOpen: false}})));
  });

  it('issueListPhaseNames', () => {
    const stateWithEmptyIssueList = {issue: {
      issueList: [],
    }};
    assert.deepEqual(issueV0.issueListPhaseNames(stateWithEmptyIssueList), []);
    const stateWithIssueList = {issue: {
      issuesByRefString: {
        '1': {localId: 1, phases: [{phaseRef: {phaseName: 'chicken-phase'}}]},
        '2': {localId: 2, phases: [
          {phaseRef: {phaseName: 'chicken-Phase'}},
          {phaseRef: {phaseName: 'cow-phase'}}],
        },
        '3': {localId: 3, phases: [
          {phaseRef: {phaseName: 'cow-Phase'}},
          {phaseRef: {phaseName: 'DOG-phase'}}],
        },
        '4': {localId: 4, phases: [
          {phaseRef: {phaseName: 'dog-phase'}},
        ]},
      },
      issueList: {
        issueRefs: ['1', '2', '3', '4'],
      }}};
    assert.deepEqual(issueV0.issueListPhaseNames(stateWithIssueList),
        ['chicken-phase', 'cow-phase', 'dog-phase']);
  });

  describe('blockingIssues', () => {
    const relatedIssues = {
      ['proj:1']: {
        localId: 1,
        projectName: 'proj',
        labelRefs: [{label: 'label'}],
      },
      ['proj:3']: {
        localId: 3,
        projectName: 'proj',
        labelRefs: [],
      },
      ['chromium:332']: {
        localId: 332,
        projectName: 'chromium',
        labelRefs: [],
      },
    };

    it('returns references when no issue data', () => {
      const stateNoReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockingIssueRefs: [{localId: 1, projectName: 'proj'}],
          },
          {relatedIssues: {}},
      );
      assert.deepEqual(issueV0.blockingIssues(stateNoReferences),
          [{localId: 1, projectName: 'proj'}],
      );
    });

    it('returns empty when no blocking issues', () => {
      const stateNoIssues = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockingIssueRefs: [],
          },
          {relatedIssues},
      );
      assert.deepEqual(issueV0.blockingIssues(stateNoIssues), []);
    });

    it('returns full issues when deferenced data present', () => {
      const stateIssuesWithReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockingIssueRefs: [
              {localId: 1, projectName: 'proj'},
              {localId: 332, projectName: 'chromium'},
            ],
          },
          {relatedIssues},
      );
      assert.deepEqual(issueV0.blockingIssues(stateIssuesWithReferences),
          [
            {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
            {localId: 332, projectName: 'chromium', labelRefs: []},
          ]);
    });

    it('returns federated references', () => {
      const stateIssuesWithFederatedReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockingIssueRefs: [
              {localId: 1, projectName: 'proj'},
              {extIdentifier: 'b/1234'},
            ],
          },
          {relatedIssues},
      );
      assert.deepEqual(
          issueV0.blockingIssues(stateIssuesWithFederatedReferences), [
            {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
            {extIdentifier: 'b/1234'},
          ]);
    });
  });

  describe('blockedOnIssues', () => {
    const relatedIssues = {
      ['proj:1']: {
        localId: 1,
        projectName: 'proj',
        labelRefs: [{label: 'label'}],
      },
      ['proj:3']: {
        localId: 3,
        projectName: 'proj',
        labelRefs: [],
      },
      ['chromium:332']: {
        localId: 332,
        projectName: 'chromium',
        labelRefs: [],
      },
    };

    it('returns references when no issue data', () => {
      const stateNoReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockedOnIssueRefs: [{localId: 1, projectName: 'proj'}],
          },
          {relatedIssues: {}},
      );
      assert.deepEqual(issueV0.blockedOnIssues(stateNoReferences),
          [{localId: 1, projectName: 'proj'}],
      );
    });

    it('returns empty when no blocking issues', () => {
      const stateNoIssues = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockedOnIssueRefs: [],
          },
          {relatedIssues},
      );
      assert.deepEqual(issueV0.blockedOnIssues(stateNoIssues), []);
    });

    it('returns full issues when deferenced data present', () => {
      const stateIssuesWithReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockedOnIssueRefs: [
              {localId: 1, projectName: 'proj'},
              {localId: 332, projectName: 'chromium'},
            ],
          },
          {relatedIssues},
      );
      assert.deepEqual(issueV0.blockedOnIssues(stateIssuesWithReferences),
          [
            {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
            {localId: 332, projectName: 'chromium', labelRefs: []},
          ]);
    });

    it('returns federated references', () => {
      const stateIssuesWithFederatedReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockedOnIssueRefs: [
              {localId: 1, projectName: 'proj'},
              {extIdentifier: 'b/1234'},
            ],
          },
          {relatedIssues},
      );
      assert.deepEqual(
          issueV0.blockedOnIssues(stateIssuesWithFederatedReferences),
          [
            {localId: 1, projectName: 'proj', labelRefs: [{label: 'label'}]},
            {extIdentifier: 'b/1234'},
          ]);
    });
  });

  describe('sortedBlockedOn', () => {
    const relatedIssues = {
      ['proj:1']: {
        localId: 1,
        projectName: 'proj',
        statusRef: {meansOpen: true},
      },
      ['proj:3']: {
        localId: 3,
        projectName: 'proj',
        statusRef: {meansOpen: false},
      },
      ['proj:4']: {
        localId: 4,
        projectName: 'proj',
        statusRef: {meansOpen: false},
      },
      ['proj:5']: {
        localId: 5,
        projectName: 'proj',
        statusRef: {meansOpen: false},
      },
      ['chromium:332']: {
        localId: 332,
        projectName: 'chromium',
        statusRef: {meansOpen: true},
      },
    };

    it('does not sort references when no issue data', () => {
      const stateNoReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockedOnIssueRefs: [
              {localId: 3, projectName: 'proj'},
              {localId: 1, projectName: 'proj'},
            ],
          },
          {relatedIssues: {}},
      );
      assert.deepEqual(issueV0.sortedBlockedOn(stateNoReferences), [
        {localId: 3, projectName: 'proj'},
        {localId: 1, projectName: 'proj'},
      ]);
    });

    it('sorts open issues first when issue data available', () => {
      const stateReferences = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockedOnIssueRefs: [
              {localId: 3, projectName: 'proj'},
              {localId: 1, projectName: 'proj'},
            ],
          },
          {relatedIssues},
      );
      assert.deepEqual(issueV0.sortedBlockedOn(stateReferences), [
        {localId: 1, projectName: 'proj', statusRef: {meansOpen: true}},
        {localId: 3, projectName: 'proj', statusRef: {meansOpen: false}},
      ]);
    });

    it('preserves original order on ties', () => {
      const statePreservesArrayOrder = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            blockedOnIssueRefs: [
              {localId: 5, projectName: 'proj'}, // Closed
              {localId: 1, projectName: 'proj'}, // Open
              {localId: 4, projectName: 'proj'}, // Closed
              {localId: 3, projectName: 'proj'}, // Closed
              {localId: 332, projectName: 'chromium'}, // Open
            ],
          },
          {relatedIssues},
      );
      assert.deepEqual(issueV0.sortedBlockedOn(statePreservesArrayOrder),
          [
            {localId: 1, projectName: 'proj', statusRef: {meansOpen: true}},
            {localId: 332, projectName: 'chromium',
              statusRef: {meansOpen: true}},
            {localId: 5, projectName: 'proj', statusRef: {meansOpen: false}},
            {localId: 4, projectName: 'proj', statusRef: {meansOpen: false}},
            {localId: 3, projectName: 'proj', statusRef: {meansOpen: false}},
          ],
      );
    });
  });

  describe('mergedInto', () => {
    it('empty', () => {
      assert.deepEqual(issueV0.mergedInto(wrapIssue()), {});
    });

    it('gets mergedInto ref for viewed issue', () => {
      const state = issueV0.mergedInto(wrapIssue({
        projectName: 'project',
        localId: 123,
        mergedIntoIssueRef: {localId: 22, projectName: 'proj'},
      }));
      assert.deepEqual(state, {
        localId: 22,
        projectName: 'proj',
      });
    });

    it('gets full mergedInto issue data when it exists in the store', () => {
      const state = wrapIssue(
          {
            projectName: 'project',
            localId: 123,
            mergedIntoIssueRef: {localId: 22, projectName: 'proj'},
          }, {
            relatedIssues: {
              ['proj:22']: {localId: 22, projectName: 'proj', summary: 'test'},
            },
          });
      assert.deepEqual(issueV0.mergedInto(state), {
        localId: 22,
        projectName: 'proj',
        summary: 'test',
      });
    });
  });

  it('fieldValueMap', () => {
    assert.deepEqual(issueV0.fieldValueMap(wrapIssue()), new Map());
    assert.deepEqual(issueV0.fieldValueMap(wrapIssue({
      fieldValues: [],
    })), new Map());
    assert.deepEqual(issueV0.fieldValueMap(wrapIssue({
      fieldValues: [
        {fieldRef: {fieldName: 'hello'}, value: 'v3'},
        {fieldRef: {fieldName: 'hello'}, value: 'v2'},
        {fieldRef: {fieldName: 'world'}, value: 'v3'},
      ],
    })), new Map([
      ['hello', ['v3', 'v2']],
      ['world', ['v3']],
    ]));
  });

  it('fieldDefs filters fields by applicable type', () => {
    assert.deepEqual(issueV0.fieldDefs({
      projectV0: {},
      ...wrapIssue(),
    }), []);

    assert.deepEqual(issueV0.fieldDefs({
      projectV0: {
        name: 'chromium',
        configs: {
          chromium: {
            fieldDefs: [
              {fieldRef: {fieldName: 'intyInt', type: fieldTypes.INT_TYPE}},
              {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
              {
                fieldRef:
                  {fieldName: 'nonApplicable', type: fieldTypes.STR_TYPE},
                applicableType: 'None',
              },
              {fieldRef: {fieldName: 'defectsOnly', type: fieldTypes.STR_TYPE},
                applicableType: 'Defect'},
            ],
          },
        },
      },
      ...wrapIssue({
        fieldValues: [
          {fieldRef: {fieldName: 'Type'}, value: 'Defect'},
        ],
      }),
    }), [
      {fieldRef: {fieldName: 'intyInt', type: fieldTypes.INT_TYPE}},
      {fieldRef: {fieldName: 'enum', type: fieldTypes.ENUM_TYPE}},
      {fieldRef: {fieldName: 'defectsOnly', type: fieldTypes.STR_TYPE},
        applicableType: 'Defect'},
    ]);
  });

  it('fieldDefs skips approval fields for all issues', () => {
    assert.deepEqual(issueV0.fieldDefs({
      projectV0: {
        name: 'chromium',
        configs: {
          chromium: {
            fieldDefs: [
              {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
              {fieldRef:
                {fieldName: 'ignoreMe', type: fieldTypes.APPROVAL_TYPE}},
              {fieldRef:
                {fieldName: 'LookAway', approvalName: 'ThisIsAnApproval'}},
              {fieldRef: {fieldName: 'phaseField'}, isPhaseField: true},
            ],
          },
        },
      },
      ...wrapIssue(),
    }), [
      {fieldRef: {fieldName: 'test', type: fieldTypes.INT_TYPE}},
    ]);
  });

  it('fieldDefs includes non applicable fields when values defined', () => {
    assert.deepEqual(issueV0.fieldDefs({
      projectV0: {
        name: 'chromium',
        configs: {
          chromium: {
            fieldDefs: [
              {
                fieldRef:
                  {fieldName: 'nonApplicable', type: fieldTypes.STR_TYPE},
                applicableType: 'None',
              },
            ],
          },
        },
      },
      ...wrapIssue({
        fieldValues: [
          {fieldRef: {fieldName: 'nonApplicable'}, value: 'v3'},
        ],
      }),
    }), [
      {fieldRef: {fieldName: 'nonApplicable', type: fieldTypes.STR_TYPE},
        applicableType: 'None'},
    ]);
  });

  describe('action creators', () => {
    beforeEach(() => {
      prpcCall = sinon.stub(prpcClient, 'call');
    });

    afterEach(() => {
      prpcCall.restore();
    });

    it('viewIssue creates action with issueRef', () => {
      assert.deepEqual(
          issueV0.viewIssue({projectName: 'proj', localId: 123}),
          {
            type: issueV0.VIEW_ISSUE,
            issueRef: {projectName: 'proj', localId: 123},
          },
      );
    });

    it('predictComponent sends prediction request', async () => {
      prpcCall.callsFake(() => {
        return {componentRef: {path: 'UI>Test'}};
      });

      const dispatch = sinon.stub();

      const action = issueV0.predictComponent('chromium',
          'test comments\nsummary');

      await action(dispatch);

      sinon.assert.calledOnce(prpcCall);

      sinon.assert.calledWith(prpcCall, 'monorail.Features',
          'PredictComponent', {
            projectName: 'chromium',
            text: 'test comments\nsummary',
          });

      sinon.assert.calledWith(dispatch, {type: 'PREDICT_COMPONENT_START'});
      sinon.assert.calledWith(dispatch, {
        type: 'PREDICT_COMPONENT_SUCCESS',
        component: 'UI>Test',
      });
    });

    describe('updateApproval', async () => {
      const APPROVAL = {
        fieldRef: {fieldName: 'Privacy', type: 'APPROVAL_TYPE'},
        approverRefs: [{userId: 1234, displayName: 'test@example.com'}],
        status: 'APPROVED',
      };

      it('approval update success', async () => {
        const dispatch = sinon.stub();

        prpcCall.returns({approval: APPROVAL});

        const action = issueV0.updateApproval({
          issueRef: {projectName: 'chromium', localId: 1234},
          fieldRef: {fieldName: 'Privacy', type: 'APPROVAL_TYPE'},
          approvalDelta: {status: 'APPROVED'},
          sendEmail: true,
        });

        await action(dispatch);

        sinon.assert.calledOnce(prpcCall);

        sinon.assert.calledWith(prpcCall, 'monorail.Issues',
            'UpdateApproval', {
              issueRef: {projectName: 'chromium', localId: 1234},
              fieldRef: {fieldName: 'Privacy', type: 'APPROVAL_TYPE'},
              approvalDelta: {status: 'APPROVED'},
              sendEmail: true,
            });

        sinon.assert.calledWith(dispatch, {type: 'UPDATE_APPROVAL_START'});
        sinon.assert.calledWith(dispatch, {
          type: 'UPDATE_APPROVAL_SUCCESS',
          approval: APPROVAL,
          issueRef: {projectName: 'chromium', localId: 1234},
        });
      });

      it('approval survey update success', async () => {
        const dispatch = sinon.stub();

        prpcCall.returns({approval: APPROVAL});

        const action = issueV0.updateApproval({
          issueRef: {projectName: 'chromium', localId: 1234},
          fieldRef: {fieldName: 'Privacy', type: 'APPROVAL_TYPE'},
          commentContent: 'new survey',
          sendEmail: false,
          isDescription: true,
        });

        await action(dispatch);

        sinon.assert.calledOnce(prpcCall);

        sinon.assert.calledWith(prpcCall, 'monorail.Issues',
            'UpdateApproval', {
              issueRef: {projectName: 'chromium', localId: 1234},
              fieldRef: {fieldName: 'Privacy', type: 'APPROVAL_TYPE'},
              commentContent: 'new survey',
              isDescription: true,
            });

        sinon.assert.calledWith(dispatch, {type: 'UPDATE_APPROVAL_START'});
        sinon.assert.calledWith(dispatch, {
          type: 'UPDATE_APPROVAL_SUCCESS',
          approval: APPROVAL,
          issueRef: {projectName: 'chromium', localId: 1234},
        });
      });

      it('attachment upload success', async () => {
        const dispatch = sinon.stub();

        prpcCall.returns({approval: APPROVAL});

        const action = issueV0.updateApproval({
          issueRef: {projectName: 'chromium', localId: 1234},
          fieldRef: {fieldName: 'Privacy', type: 'APPROVAL_TYPE'},
          uploads: '78f17a020cbf39e90e344a842cd19911',
        });

        await action(dispatch);

        sinon.assert.calledOnce(prpcCall);

        sinon.assert.calledWith(prpcCall, 'monorail.Issues',
            'UpdateApproval', {
              issueRef: {projectName: 'chromium', localId: 1234},
              fieldRef: {fieldName: 'Privacy', type: 'APPROVAL_TYPE'},
              uploads: '78f17a020cbf39e90e344a842cd19911',
            });

        sinon.assert.calledWith(dispatch, {type: 'UPDATE_APPROVAL_START'});
        sinon.assert.calledWith(dispatch, {
          type: 'UPDATE_APPROVAL_SUCCESS',
          approval: APPROVAL,
          issueRef: {projectName: 'chromium', localId: 1234},
        });
      });
    });

    describe('fetchIssues', () => {
      it('success', async () => {
        const response = {
          openRefs: [example.ISSUE],
          closedRefs: [example.ISSUE_OTHER_PROJECT],
        };
        prpcClient.call.returns(Promise.resolve(response));
        const dispatch = sinon.stub();

        await issueV0.fetchIssues([example.ISSUE_REF])(dispatch);

        sinon.assert.calledWith(dispatch, {type: issueV0.FETCH_ISSUES_START});

        const args = {issueRefs: [example.ISSUE_REF]};
        sinon.assert.calledWith(
            prpcClient.call, 'monorail.Issues', 'ListReferencedIssues', args);

        const action = {
          type: issueV0.FETCH_ISSUES_SUCCESS,
          issues: [example.ISSUE, example.ISSUE_OTHER_PROJECT],
        };
        sinon.assert.calledWith(dispatch, action);
      });

      it('failure', async () => {
        prpcClient.call.throws();
        const dispatch = sinon.stub();

        await issueV0.fetchIssues([example.ISSUE_REF])(dispatch);

        const action = {
          type: issueV0.FETCH_ISSUES_FAILURE,
          error: sinon.match.any,
        };
        sinon.assert.calledWith(dispatch, action);
      });
    });

    it('fetchIssueList calls ListIssues', async () => {
      prpcCall.callsFake(() => {
        return {
          issues: [{localId: 1}, {localId: 2}, {localId: 3}],
          totalResults: 6,
        };
      });

      store.dispatch(issueV0.fetchIssueList('chromium',
          {q: 'owner:me', can: '4'}));

      sinon.assert.calledWith(prpcCall, 'monorail.Issues', 'ListIssues', {
        query: 'owner:me',
        cannedQuery: 4,
        projectNames: ['chromium'],
        pagination: {},
        groupBySpec: undefined,
        sortSpec: undefined,
      });
    });

    it('fetchIssueList does not set can when can is NaN', async () => {
      prpcCall.callsFake(() => ({}));

      store.dispatch(issueV0.fetchIssueList('chromium', {q: 'owner:me',
        can: 'four-leaf-clover'}));

      sinon.assert.calledWith(prpcCall, 'monorail.Issues', 'ListIssues', {
        query: 'owner:me',
        cannedQuery: undefined,
        projectNames: ['chromium'],
        pagination: {},
        groupBySpec: undefined,
        sortSpec: undefined,
      });
    });

    it('fetchIssueList makes several calls to ListIssues', async () => {
      prpcCall.callsFake(() => {
        return {
          issues: [{localId: 1}, {localId: 2}, {localId: 3}],
          totalResults: 6,
        };
      });

      const dispatch = sinon.stub();
      const action = issueV0.fetchIssueList('chromium',
          {maxItems: 3, maxCalls: 2});
      await action(dispatch);

      sinon.assert.calledTwice(prpcCall);
      sinon.assert.calledWith(dispatch, {
        type: 'FETCH_ISSUE_LIST_UPDATE',
        issues:
          [{localId: 1}, {localId: 2}, {localId: 3},
            {localId: 1}, {localId: 2}, {localId: 3}],
        progress: 1,
        totalResults: 6,
      });
      sinon.assert.calledWith(dispatch, {type: 'FETCH_ISSUE_LIST_SUCCESS'});
    });

    it('fetchIssueList orders issues correctly', async () => {
      prpcCall.onFirstCall().returns({issues: [{localId: 1}], totalResults: 6});
      prpcCall.onSecondCall().returns({
        issues: [{localId: 2}],
        totalResults: 6});
      prpcCall.onThirdCall().returns({issues: [{localId: 3}], totalResults: 6});

      const dispatch = sinon.stub();
      const action = issueV0.fetchIssueList('chromium',
          {maxItems: 1, maxCalls: 3});
      await action(dispatch);

      sinon.assert.calledWith(dispatch, {
        type: 'FETCH_ISSUE_LIST_UPDATE',
        issues: [{localId: 1}, {localId: 2}, {localId: 3}],
        progress: 1,
        totalResults: 6,
      });
      sinon.assert.calledWith(dispatch, {type: 'FETCH_ISSUE_LIST_SUCCESS'});
    });

    it('returns progress of 1 when no totalIssues', async () => {
      prpcCall.onFirstCall().returns({issues: [], totalResults: 0});

      const dispatch = sinon.stub();
      const action = issueV0.fetchIssueList('chromium',
          {maxItems: 1, maxCalls: 1});
      await action(dispatch);

      sinon.assert.calledWith(dispatch, {
        type: 'FETCH_ISSUE_LIST_UPDATE',
        issues: [],
        progress: 1,
        totalResults: 0,
      });
      sinon.assert.calledWith(dispatch, {type: 'FETCH_ISSUE_LIST_SUCCESS'});
    });

    it('returns progress of 1 when totalIssues undefined', async () => {
      prpcCall.onFirstCall().returns({issues: []});

      const dispatch = sinon.stub();
      const action = issueV0.fetchIssueList('chromium',
          {maxItems: 1, maxCalls: 1});
      await action(dispatch);

      sinon.assert.calledWith(dispatch, {
        type: 'FETCH_ISSUE_LIST_UPDATE',
        issues: [],
        progress: 1,
      });
      sinon.assert.calledWith(dispatch, {type: 'FETCH_ISSUE_LIST_SUCCESS'});
    });

    // TODO(kweng@) remove once crbug.com/monorail/6641 is fixed
    it('has sane default for empty response', async () => {
      prpcCall.onFirstCall().returns({});

      const dispatch = sinon.stub();
      const action = issueV0.fetchIssueList('chromium',
          {maxItems: 1, maxCalls: 1});
      await action(dispatch);

      sinon.assert.calledWith(dispatch, {
        type: 'FETCH_ISSUE_LIST_UPDATE',
        issues: [],
        progress: 1,
        totalResults: 0,
      });
      sinon.assert.calledWith(dispatch, {type: 'FETCH_ISSUE_LIST_SUCCESS'});
    });

    describe('federated references', () => {
      beforeEach(() => {
        // Preload signinImpl with a fake for testing.
        getSigninInstance({
          init: sinon.stub(),
          getUserProfileAsync: () => (
            Promise.resolve({
              getEmail: sinon.stub().returns('rutabaga@google.com'),
            })
          ),
        });
        window.CS_env = {gapi_client_id: 'rutabaga'};
        const getStub = sinon.stub().returns({
          execute: (cb) => cb(response),
        });
        const response = {
          result: {
            resolvedTime: 12345,
            issueState: {
              title: 'Rutabaga title',
            },
          },
        };
        window.gapi = {
          client: {
            load: (_url, _version, cb) => cb(),
            corp_issuetracker: {issues: {get: getStub}},
          },
        };
      });

      afterEach(() => {
        delete window.CS_env;
        delete window.gapi;
      });

      describe('fetchFederatedReferences', () => {
        it('returns an empty map if no fedrefs found', async () => {
          const dispatch = sinon.stub();
          const testIssue = {};
          const action = issueV0.fetchFederatedReferences(testIssue);
          const result = await action(dispatch);

          assert.equal(dispatch.getCalls().length, 1);
          sinon.assert.calledWith(dispatch, {
            type: 'FETCH_FEDERATED_REFERENCES_START',
          });
          assert.isUndefined(result);
        });

        it('fetches from Buganizer API', async () => {
          const dispatch = sinon.stub();
          const testIssue = {
            danglingBlockingRefs: [
              {extIdentifier: 'b/123456'},
            ],
            danglingBlockedOnRefs: [
              {extIdentifier: 'b/654321'},
            ],
            mergedIntoIssueRef: {
              extIdentifier: 'b/987654',
            },
          };
          const action = issueV0.fetchFederatedReferences(testIssue);
          await action(dispatch);

          sinon.assert.calledWith(dispatch, {
            type: 'FETCH_FEDERATED_REFERENCES_START',
          });
          sinon.assert.calledWith(dispatch, {
            type: 'GAPI_LOGIN_SUCCESS',
            email: 'rutabaga@google.com',
          });
          sinon.assert.calledWith(dispatch, {
            type: 'FETCH_FEDERATED_REFERENCES_SUCCESS',
            fedRefIssueRefs: [
              {
                extIdentifier: 'b/123456',
                statusRef: {meansOpen: false},
                summary: 'Rutabaga title',
              },
              {
                extIdentifier: 'b/654321',
                statusRef: {meansOpen: false},
                summary: 'Rutabaga title',
              },
              {
                extIdentifier: 'b/987654',
                statusRef: {meansOpen: false},
                summary: 'Rutabaga title',
              },
            ],
          });
        });
      });

      describe('fetchRelatedIssues', () => {
        it('calls fetchFederatedReferences for mergedinto', async () => {
          const dispatch = sinon.stub();
          prpcCall.returns(Promise.resolve({openRefs: [], closedRefs: []}));
          const testIssue = {
            mergedIntoIssueRef: {
              extIdentifier: 'b/987654',
            },
          };
          const action = issueV0.fetchRelatedIssues(testIssue);
          await action(dispatch);

          // Important: mergedinto fedref is not passed to ListReferencedIssues.
          const expectedMessage = {issueRefs: []};
          sinon.assert.calledWith(prpcClient.call, 'monorail.Issues',
              'ListReferencedIssues', expectedMessage);

          sinon.assert.calledWith(dispatch, {
            type: 'FETCH_RELATED_ISSUES_START',
          });
          // No mergedInto refs returned, they're handled by
          // fetchFederatedReferences.
          sinon.assert.calledWith(dispatch, {
            type: 'FETCH_RELATED_ISSUES_SUCCESS',
            relatedIssues: {},
          });
        });
      });
    });
  });

  describe('starring issues', () => {
    describe('reducers', () => {
      it('FETCH_IS_STARRED_SUCCESS updates the starredIssues object', () => {
        const state = {};
        const newState = issueV0.starredIssuesReducer(state,
            {
              type: issueV0.FETCH_IS_STARRED_SUCCESS,
              starred: false,
              issueRef: {
                projectName: 'proj',
                localId: 1,
              },
            },
        );
        assert.deepEqual(newState, {'proj:1': false});
      });

      it('FETCH_ISSUES_STARRED_SUCCESS updates the starredIssues object',
          () => {
            const state = {};
            const starredIssueRefs = [{projectName: 'proj', localId: 1},
              {projectName: 'proj', localId: 2}];
            const newState = issueV0.starredIssuesReducer(state,
                {type: issueV0.FETCH_ISSUES_STARRED_SUCCESS, starredIssueRefs},
            );
            assert.deepEqual(newState, {'proj:1': true, 'proj:2': true});
          });

      it('FETCH_ISSUES_STARRED_SUCCESS does not time out with 10,000 stars',
          () => {
            const state = {};
            const starredIssueRefs = [];
            const expected = {};
            for (let i = 1; i <= 10000; i++) {
              starredIssueRefs.push({projectName: 'proj', localId: i});
              expected[`proj:${i}`] = true;
            }
            const newState = issueV0.starredIssuesReducer(state,
                {type: issueV0.FETCH_ISSUES_STARRED_SUCCESS, starredIssueRefs},
            );
            assert.deepEqual(newState, expected);
          });

      it('STAR_SUCCESS updates the starredIssues object', () => {
        const state = {'proj:1': true, 'proj:2': false};
        const newState = issueV0.starredIssuesReducer(state,
            {
              type: issueV0.STAR_SUCCESS,
              starred: true,
              issueRef: {projectName: 'proj', localId: 2},
            });
        assert.deepEqual(newState, {'proj:1': true, 'proj:2': true});
      });
    });

    describe('selectors', () => {
      describe('issue', () => {
        const selector = issueV0.issue(wrapIssue(example.ISSUE));
        assert.deepEqual(selector(example.NAME), example.ISSUE);
      });

      describe('issueForRefString', () => {
        const noIssues = issueV0.issueForRefString(wrapIssue({}));
        const withIssue = issueV0.issueForRefString(wrapIssue({
          projectName: 'test',
          localId: 1,
          summary: 'hello world',
        }));

        it('returns issue ref when no issue data', () => {
          assert.deepEqual(noIssues('1', 'chromium'), {
            localId: 1,
            projectName: 'chromium',
          });

          assert.deepEqual(noIssues('chromium:2', 'ignore'), {
            localId: 2,
            projectName: 'chromium',
          });

          assert.deepEqual(noIssues('other:3'), {
            localId: 3,
            projectName: 'other',
          });

          assert.deepEqual(withIssue('other:3'), {
            localId: 3,
            projectName: 'other',
          });
        });

        it('returns full issue data when available', () => {
          assert.deepEqual(withIssue('1', 'test'), {
            projectName: 'test',
            localId: 1,
            summary: 'hello world',
          });

          assert.deepEqual(withIssue('test:1', 'other'), {
            projectName: 'test',
            localId: 1,
            summary: 'hello world',
          });

          assert.deepEqual(withIssue('test:1'), {
            projectName: 'test',
            localId: 1,
            summary: 'hello world',
          });
        });
      });

      it('starredIssues', () => {
        const state = {issue:
          {starredIssues: {'proj:1': true, 'proj:2': false}}};
        assert.deepEqual(issueV0.starredIssues(state), new Set(['proj:1']));
      });

      it('starringIssues', () => {
        const state = {issue: {
          requests: {
            starringIssues: {
              'proj:1': {requesting: true},
              'proj:2': {requestin: false, error: 'unknown error'},
            },
          },
        }};
        assert.deepEqual(issueV0.starringIssues(state), new Map([
          ['proj:1', {requesting: true}],
          ['proj:2', {requestin: false, error: 'unknown error'}],
        ]));
      });
    });

    describe('action creators', () => {
      beforeEach(() => {
        prpcCall = sinon.stub(prpcClient, 'call');

        dispatch = sinon.stub();
      });

      afterEach(() => {
        prpcCall.restore();
      });

      it('fetching if an issue is starred', async () => {
        const issueRef = {projectName: 'proj', localId: 1};
        const action = issueV0.fetchIsStarred(issueRef);

        prpcCall.returns(Promise.resolve({isStarred: true}));

        await action(dispatch);

        sinon.assert.calledWith(dispatch,
            {type: issueV0.FETCH_IS_STARRED_START});

        sinon.assert.calledWith(
            prpcClient.call, 'monorail.Issues',
            'IsIssueStarred', {issueRef},
        );

        sinon.assert.calledWith(dispatch, {
          type: issueV0.FETCH_IS_STARRED_SUCCESS,
          starred: true,
          issueRef,
        });
      });

      it('fetching starred issues', async () => {
        const returnedIssueRef = {projectName: 'proj', localId: 1};
        const starredIssueRefs = [returnedIssueRef];
        const action = issueV0.fetchStarredIssues();

        prpcCall.returns(Promise.resolve({starredIssueRefs}));

        await action(dispatch);

        sinon.assert.calledWith(dispatch, {type: 'FETCH_ISSUES_STARRED_START'});

        sinon.assert.calledWith(
            prpcClient.call, 'monorail.Issues',
            'ListStarredIssues', {},
        );

        sinon.assert.calledWith(dispatch, {
          type: issueV0.FETCH_ISSUES_STARRED_SUCCESS,
          starredIssueRefs,
        });
      });

      it('star', async () => {
        const testIssue = {projectName: 'proj', localId: 1, starCount: 1};
        const issueRef = issueToIssueRef(testIssue);
        const action = issueV0.star(issueRef, false);

        prpcCall.returns(Promise.resolve(testIssue));

        await action(dispatch);

        sinon.assert.calledWith(dispatch, {
          type: issueV0.STAR_START,
          requestKey: 'proj:1',
        });

        sinon.assert.calledWith(
            prpcClient.call,
            'monorail.Issues', 'StarIssue',
            {issueRef, starred: false},
        );

        sinon.assert.calledWith(dispatch, {
          type: issueV0.STAR_SUCCESS,
          starCount: 1,
          issueRef,
          starred: false,
          requestKey: 'proj:1',
        });
      });
    });
  });
});

/**
 * Return an initial Redux state with a given viewed
 * @param {Issue=} viewedIssue The viewed issue.
 * @param {Object=} otherValues Any other state values that need
 *   to be initialized.
 * @return {Object}
 */
function wrapIssue(viewedIssue, otherValues = {}) {
  if (!viewedIssue) {
    return {
      issue: {
        issuesByRefString: {},
        ...otherValues,
      },
    };
  }

  const ref = issueRefToString(viewedIssue);
  return {
    issue: {
      viewedIssueRef: ref,
      issuesByRefString: {
        [ref]: {...viewedIssue},
      },
      ...otherValues,
    },
  };
}
