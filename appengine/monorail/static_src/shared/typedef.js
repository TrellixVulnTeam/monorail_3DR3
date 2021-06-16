// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * @fileoverview Shared file for specifying common types used in type
 * annotations across Monorail.
 */

// TODO(zhangtiff): Find out if there's a way we can generate typedef's for
// API object from .proto files.


/**
 * Types used in the app that don't come from any Proto files.
 */

/**
 * A HotlistItem with the Issue flattened into the top-level,
 * containing the intersection of the fields of HotlistItem and Issue.
 *
 * @typedef {Issue & HotlistItem} HotlistIssue
 * @property {User=} adder
 */

/**
 * A String containing the data necessary to identify an IssueRef. An IssueRef
 * can reference either an issue in Monorail or an external issue in another
 * tracker.
 *
 * Examples of valid IssueRefStrings:
 * - monorail:1234
 * - chromium:1
 * - 1234
 * - b/123456
 *
 * @typedef {string} IssueRefString
 */

/**
 * An Object for specifying what to display in a single entry in the
 * dropdown list.
 *
 * @typedef {Object} MenuItem
 * @property {string=} text The text to display in the menu.
 * @property {string=} icon A Material Design icon shown left of the text.
 * @property {Array<MenuItem>=} items A specification for a nested submenu.
 * @property {function=} handler An optional click handler for an item.
 * @property {string=} url A link for the menu item to navigate to.
 */

/**
 * An Object containing the metadata associated with tracking async requests
 * through Redux.
 *
 * @typedef {Object} ReduxRequestState
 * @property {boolean=} requesting Whether a request is in flight.
 * @property {Error=} error An Error Object returned by the request.
 */


/**
 * Resource names used in our resource-oriented API.
 * @see https://aip.dev/122
 */


/**
 * Resource name of a Project.
 *
 * Examples of valid Project resource names:
 * - projects/monorail
 * - projects/test-project-1
 *
 * @typedef {string} ProjectName
 */


/**
 * Resource name of a User.
 *
 * Examples of valid User resource names:
 * - users/test@example.com
 * - users/1234
 *
 * @typedef {string} UserName
 */

/**
 * Resource name of a ProjectMember.
 *
 * Examples of valid ProjectMember resource names:
 * - projects/monorail/members/1234
 * - projects/test-xyz/members/5678
 *
 * @typedef {string} ProjectMemberName
 */


/**
 * Types defined in common.proto.
 */


/**
 * A ComponentRef Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} ComponentRef
 * @property {string} path
 * @property {boolean=} isDerived
 */

/**
 * An Enum representing the type that a custom field uses.
 *
 * @typedef {string} FieldType
 */

/**
 * A FieldRef Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} FieldRef
 * @property {number} fieldId
 * @property {string} fieldName
 * @property {FieldType} type
 * @property {string=} approvalName
 */

/**
 * A LabelRef Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} LabelRef
 * @property {string} label
 * @property {boolean=} isDerived
 */

/**
 * A StatusRef Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} StatusRef
 * @property {string} status
 * @property {boolean=} meansOpen
 * @property {boolean=} isDerived
 */

/**
 * An IssueRef Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} IssueRef
 * @property {string=} projectName
 * @property {number=} localId
 * @property {string=} extIdentifier
 */

/**
 * A UserRef Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} UserRef
 * @property {string=} displayName
 * @property {number=} userId
 */

/**
 * A HotlistRef Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} HotlistRef
 * @property {string=} name
 * @property {UserRef=} owner
 */

/**
 * A SavedQuery Object returned by the pRPC API common.proto.
 *
 * @typedef {Object} SavedQuery
 * @property {number} queryId
 * @property {string} name
 * @property {string} query
 * @property {Array<string>} projectNames
 */


/**
 * Types defined in issue_objects.proto.
 */

/**
 * An Approval Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} Approval
 * @property {FieldRef} fieldRef
 * @property {Array<UserRef>} approverRefs
 * @property {ApprovalStatus} status
 * @property {number} setOn
 * @property {UserRef} setterRef
 * @property {PhaseRef} phaseRef
 */

/**
 * An Enum representing the status of an Approval.
 *
 * @typedef {string} ApprovalStatus
 */

/**
 * An Amendment Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} Amendment
 * @property {string} fieldName
 * @property {string} newOrDeltaValue
 * @property {string} oldValue
 */

/**
 * An Attachment Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} Attachment
* @property {number} attachmentId
* @property {string} filename
* @property {number} size
* @property {string} contentType
* @property {boolean} isDeleted
* @property {string} thumbnailUrl
* @property {string} viewUrl
* @property {string} downloadUrl
*/

/**
 * A Comment Object returned by the pRPC API issue_objects.proto.
 *
 * Note: This Object is called "Comment" in the backend but is named
 * "IssueComment" here to avoid a collision with an internal JSDoc Intellisense
 * type.
 *
 * @typedef {Object} IssueComment
 * @property {string} projectName
 * @property {number} localId
 * @property {number=} sequenceNum
 * @property {boolean=} isDeleted
 * @property {UserRef=} commenter
 * @property {number=} timestamp
 * @property {string=} content
 * @property {string=} inboundMessage
 * @property {Array<Amendment>=} amendments
 * @property {Array<Attachment>=} attachments
 * @property {FieldRef=} approvalRef
 * @property {number=} descriptionNum
 * @property {boolean=} isSpam
 * @property {boolean=} canDelete
 * @property {boolean=} canFlag
 */

/**
 * A FieldValue Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} FieldValue
 * @property {FieldRef} fieldRef
 * @property {string} value
 * @property {boolean=} isDerived
 * @property {PhaseRef=} phaseRef
 */

/**
 * An Issue Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} Issue
 * @property {string} projectName
 * @property {number} localId
 * @property {string=} summary
 * @property {StatusRef=} statusRef
 * @property {UserRef=} ownerRef
 * @property {Array<UserRef>=} ccRefs
 * @property {Array<LabelRef>=} labelRefs
 * @property {Array<ComponentRef>=} componentRefs
 * @property {Array<IssueRef>=} blockedOnIssueRefs
 * @property {Array<IssueRef>=} blockingIssueRefs
 * @property {Array<IssueRef>=} danglingBlockedOnRefs
 * @property {Array<IssueRef>=} danglingBlockingRefs
 * @property {IssueRef=} mergedIntoIssueRef
 * @property {Array<FieldValue>=} fieldValues
 * @property {boolean=} isDeleted
 * @property {UserRef=} reporterRef
 * @property {number=} openedTimestamp
 * @property {number=} closedTimestamp
 * @property {number=} modifiedTimestamp
 * @property {number=} componentModifiedTimestamp
 * @property {number=} statusModifiedTimestamp
 * @property {number=} ownerModifiedTimestamp
 * @property {number=} starCount
 * @property {boolean=} isSpam
 * @property {number=} attachmentCount
 * @property {Array<Approval>=} approvalValues
 * @property {Array<PhaseDef>=} phases
 */

/**
 * A IssueDelta Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} IssueDelta
 * @property {string=} status
 * @property {UserRef=} ownerRef
 * @property {Array<UserRef>=} ccRefsAdd
 * @property {Array<UserRef>=} ccRefsRemove
 * @property {Array<ComponentRef>=} compRefsAdd
 * @property {Array<ComponentRef>=} compRefsRemove
 * @property {Array<LabelRef>=} labelRefsAdd
 * @property {Array<LabelRef>=} labelRefsRemove
 * @property {Array<FieldValue>=} fieldValsAdd
 * @property {Array<FieldValue>=} fieldValsRemove
 * @property {Array<FieldRef>=} fieldsClear
 * @property {Array<IssueRef>=} blockedOnRefsAdd
 * @property {Array<IssueRef>=} blockedOnRefsRemove
 * @property {Array<IssueRef>=} blockingRefsAdd
 * @property {Array<IssueRef>=} blockingRefsRemove
 * @property {IssueRef=} mergedIntoRef
 * @property {string=} summary
 */

/**
 * An PhaseDef Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} PhaseDef
 * @property {PhaseRef} phaseRef
 * @property {number} rank
 */

/**
 * An PhaseRef Object returned by the pRPC API issue_objects.proto.
 *
 * @typedef {Object} PhaseRef
 * @property {string} phaseName
 */

/**
 * An Object returned by the pRPC v3 API from feature_objects.proto.
 *
 * @typedef {Object} IssuesListColumn
 * @property {string} column
 */


/**
 * Types defined in permission_objects.proto.
 */

/**
 * A Permission string returned by the pRPC API permission_objects.proto.
 *
 * @typedef {string} Permission
 */

/**
 * A PermissionSet Object returned by the pRPC API permission_objects.proto.
 *
 * @typedef {Object} PermissionSet
 * @property {string} resource
 * @property {Array<Permission>} permissions
 */


/**
 * Types defined in project_objects.proto.
 */

/**
 * An Enum representing the role a ProjectMember has.
 *
 * @typedef {string} ProjectRole
 */

/**
 * An Enum representing how a ProjectMember shows up in autocomplete.
 *
 * @typedef {string} AutocompleteVisibility
 */

/**
 * A ProjectMember Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} ProjectMember
 * @property {ProjectMemberName} name
 * @property {ProjectRole} role
 * @property {Array<Permission>=} standardPerms
 * @property {Array<string>=} customPerms
 * @property {string=} notes
 * @property {AutocompleteVisibility=} includeInAutocomplete
 */

/**
 * A Project Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} Project
 * @property {string} name
 * @property {string} summary
 * @property {string=} description
 */

/**
 * A Project Object returned by the v0 pRPC API project_objects.proto.
 *
 * @typedef {Object} ProjectV0
 * @property {string} name
 * @property {string} summary
 * @property {string=} description
 */

/**
 * A StatusDef Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} StatusDef
 * @property {string} status
 * @property {boolean} meansOpen
 * @property {number} rank
 * @property {string} docstring
 * @property {boolean} deprecated
 */

/**
 * A LabelDef Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} LabelDef
 * @property {string} label
 * @property {string=} docstring
 * @property {boolean=} deprecated
 */

/**
 * A ComponentDef Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} ComponentDef
 * @property {string} path
 * @property {string} docstring
 * @property {Array<UserRef>} adminRefs
 * @property {Array<UserRef>} ccRefs
 * @property {boolean} deprecated
 * @property {number} created
 * @property {UserRef} creatorRef
 * @property {number} modified
 * @property {UserRef} modifierRef
 * @property {Array<LabelRef>} labelRefs
 */

/**
 * A FieldDef Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} FieldDef
 * @property {FieldRef} fieldRef
 * @property {string=} applicableType
 * @property {boolean=} isRequired
 * @property {boolean=} isNiche
 * @property {boolean=} isMultivalued
 * @property {string=} docstring
 * @property {Array<UserRef>=} adminRefs
 * @property {boolean=} isPhaseField
 * @property {Array<UserRef>=} userChoices
 * @property {Array<LabelDef>=} enumChoices
 */

/**
 * A ApprovalDef Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} ApprovalDef
 * @property {FieldRef} fieldRef
 * @property {Array<UserRef>} approverRefs
 * @property {string} survey
 */

/**
 * A Config Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} Config
 * @property {string} projectName
 * @property {Array<StatusDef>=} statusDefs
 * @property {Array<StatusRef>=} statusesOfferMerge
 * @property {Array<LabelDef>=} labelDefs
 * @property {Array<string>=} exclusiveLabelPrefixes
 * @property {Array<ComponentDef>=} componentDefs
 * @property {Array<FieldDef>=} fieldDefs
 * @property {Array<ApprovalDef>=} approvalDefs
 * @property {boolean=} restrictToKnown
 */


/**
 * A PresentationConfig Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} PresentationConfig
 * @property {string=} projectThumbnailUrl
 * @property {string=} projectSummary
 * @property {string=} customIssueEntryUrl
 * @property {string=} defaultQuery
 * @property {Array<SavedQuery>=} savedQueries
 * @property {string=} revisionUrlFormat
 * @property {string=} defaultColSpec
 * @property {string=} defaultSortSpec
 * @property {string=} defaultXAttr
 * @property {string=} defaultYAttr
 */

/**
 * A TemplateDef Object returned by the pRPC API project_objects.proto.
 *
 * @typedef {Object} TemplateDef
 * @property {string} templateName
 * @property {string=} content
 * @property {string=} summary
 * @property {boolean=} summaryMustBeEdited
 * @property {UserRef=} ownerRef
 * @property {StatusRef=} statusRef
 * @property {Array<LabelRef>=} labelRefs
 * @property {boolean=} membersOnly
 * @property {boolean=} ownerDefaultsToMember
 * @property {Array<UserRef>=} adminRefs
 * @property {Array<FieldValue>=} fieldValues
 * @property {Array<ComponentRef>=} componentRefs
 * @property {boolean=} componentRequired
 * @property {Array<Approval>=} approvalValues
 * @property {Array<PhaseDef>=} phases
 */


/**
 * Types defined in features_objects.proto.
 */

/**
 * A Hotlist Object returned by the pRPC API features_objects.proto.
 *
 * @typedef {Object} HotlistV0
 * @property {UserRef=} ownerRef
 * @property {string=} name
 * @property {string=} summary
 * @property {string=} description
 * @property {string=} defaultColSpec
 * @property {boolean=} isPrivate
 */

/**
 * A Hotlist Object returned by the pRPC v3 API from feature_objects.proto.
 *
 * @typedef {Object} Hotlist
 * @property {string} name
 * @property {string=} displayName
 * @property {string=} owner
 * @property {Array<string>=} editors
 * @property {string=} summary
 * @property {string=} description
 * @property {Array<IssuesListColumn>=} defaultColumns
 * @property {string=} hotlistPrivacy
 */

/**
 * A HotlistItem Object returned by the pRPC API features_objects.proto.
 *
 * @typedef {Object} HotlistItemV0
 * @property {Issue=} issue
 * @property {number=} rank
 * @property {UserRef=} adderRef
 * @property {number=} addedTimestamp
 * @property {string=} note
 */

/**
 * A HotlistItem Object returned by the pRPC v3 API from feature_objects.proto.
 *
 * @typedef {Object} HotlistItem
 * @property {string=} name
 * @property {string=} issue
 * @property {number=} rank
 * @property {string=} adder
 * @property {string=} createTime
 * @property {string=} note
 */

/**
 * Types defined in user_objects.proto.
 */

/**
 * A User Object returned by the pRPC API user_objects.proto.
 *
 * @typedef {Object} UserV0
 * @property {string=} displayName
 * @property {number=} userId
 * @property {boolean=} isSiteAdmin
 * @property {string=} availability
 * @property {UserRef=} linkedParentRef
 * @property {Array<UserRef>=} linkedChildRefs
 */

/**
 * A User Object returned by the pRPC v3 API from user_objects.proto.
 *
 * @typedef {Object} User
 * @property {string=} name
 * @property {string=} displayName
 * @property {string=} availabilityMessage
 */
