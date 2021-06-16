// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {ChopsAutocomplete} from
  'elements/chops/chops-autocomplete/chops-autocomplete';
import {connectStore} from 'reducers/base.js';
import * as userV0 from 'reducers/userV0.js';
import * as projectV0 from 'reducers/projectV0.js';
import {arrayDifference} from 'shared/helpers.js';
import {userRefsToDisplayNames} from 'shared/convertersV0.js';


/**
 * `<mr-autocomplete>` displays an autocomplete input.
 *
 */
export class MrAutocomplete extends connectStore(ChopsAutocomplete) {
  /** @override */
  static get properties() {
    return {
      ...ChopsAutocomplete.properties,
      /**
       * String for the name of autocomplete vocabulary used.
       * Valid values:
       *  - 'project': Names of projects available to the current user.
       *  - 'member': All members in the current project a user is viewing.
       *  - 'owner': Similar to member, except with groups excluded.
       *
       * TODO(zhangtiff): Implement the following stores.
       *  - 'component': All components in the current project.
       *  - 'label': Well-known labels in the current project.
       */
      vocabularyName: {type: String},
      /**
       * Object where the keys are 'type' values and each value is an object
       * with the format {strings, docDict, replacer}.
       */
      vocabularies: {type: Object},
    };
  }

  /** @override */
  constructor() {
    super();
    this.vocabularyName = '';
    this.vocabularies = {};
  }

  /** @override */
  stateChanged(state) {
    const visibleMembers = projectV0.viewedVisibleMembers(state);
    const userProjects = userV0.projects(state);
    this.vocabularies = {
      'project': this._setupProjectVocabulary(userProjects),
      'member': this._setupMemberVocabulary(visibleMembers),
      'owner': this._setupOwnerVocabulary(visibleMembers),
    };
  }

  // TODO(zhangtiff): Move this logic into selectors to prevent computing
  // vocabularies for every single instance of autocomplete.
  _setupProjectVocabulary(userProjects) {
    const {ownerOf = [], memberOf = [], contributorTo = []} = userProjects;
    const strings = [...ownerOf, ...memberOf, ...contributorTo];
    return {strings};
  }

  _setupMemberVocabulary(visibleMembers) {
    const {userRefs = []} = visibleMembers;
    return {strings: userRefsToDisplayNames(userRefs)};
  }

  _setupOwnerVocabulary(visibleMembers) {
    const {userRefs = [], groupRefs = []} = visibleMembers;
    const groups = userRefsToDisplayNames(groupRefs);
    const users = userRefsToDisplayNames(userRefs);

    // Remove groups from the list of all members.
    const owners = arrayDifference(users, groups);
    return {strings: owners};
  }

  /** @override */
  update(changedProperties) {
    if (changedProperties.has('vocabularyName') ||
        changedProperties.has('vocabularies')) {
      if (this.vocabularyName in this.vocabularies) {
        const props = this.vocabularies[this.vocabularyName];

        this.strings = props.strings || [];
        this.docDict = props.docDict || {};
        this.replacer = props.replacer;
      } else {
        // Clear autocomplete if there's no data for it.
        this.strings = [];
        this.docDict = {};
        this.replacer = null;
      }
    }

    super.update(changedProperties);
  }
}
customElements.define('mr-autocomplete', MrAutocomplete);
