# Monorail API v1

Monorail API v1 aims to provide nearly identical interface to Google Code issue tracker's API for existing clients' smooth transition. You can get a high-level overview from the documents below.

* [Code example in python](example.py)


Rate limiting:

* We count requests for each signed in account.
* The rate limit is currently 450 requests per minute.  We can adjust that per-account if needed.
* We enforce the limit in a five-minute window, so 2250 requests are allowed within any given 5 minutes.
* Individual requests that take more than 5s count as 2 requests.  This could happen for complex issue searches, especially free text and negated free text terms.
* If the client exceeds the rate limit, it will get response code 400, in which case it should wait and try again.
* These parameters are defined in settings.py and framework/ratelimiter.py.


This API provides the following methods to read/write user/issue/comment objects in Monorail:

[TOC]

## monorail.groups.create

* Description: Create a new user group.
* Permission: The requester needs permission to create groups.
* Parameters:
	* groupName(required, string): The name of the group to create.
	* who_can_view_members(required, string): The visibility setting of the group. Available options are 'ANYONE', 'MEMBERS' and 'OWNERS'.
	* ext_group_type(string): The type of the source group if the new group is imported from the source. Available options are 'BAGGINS', 'CHROME_INFRA_AUTH' and 'MDB'.
* Return message:
	* groupID(int): The ID of the newly created group.
* Error code:
	* 400: The group already exists.
	* 403: The requester has no permission to create a group.

## monorail.groups.get

* Description: Get a group's settings and users.
* Permission: The requester needs permission to view this group.
* Parameters:
	* groupName(required, string): The name of the group to view.
* Return message:
	* groupID(int): The ID of the newly created group.
	* groupSettings(dict):
		* groupName(string): The name of the group.
		* who_can_view_members(string): The visibility setting of the group.
		* ext_group_type(string): The type of the source group.
		* last_sync_time(int): The timestamp when the group was last synced from the source. This field is only meaningful for groups with ext_group_type set.
	* groupOwners(list): A list of group owners' emails.
	* groupMembers(list): A list of group members' emails.
* Error code:
	* 403: The requester has no permission to view this group.
	* 404: The group does not exist.

## monorail.groups.settings.list

* Description: List all group settings.
* Permission: None.
* Parameters:
	* importedGroupsOnly(boolean): A flag indicating whether only fetching settings of imported groups. The default is False.
* Return message:
	* groupSettings(list of dict):
		* groupName(string): The name of the group.
		* who_can_view_members(string): The visibility setting of the group.
		* ext_group_type(string): The type of the source group.
		* last_sync_time(int): The timestamp when the group was last synced from the source. This field is only meaningful for groups with ext_group_type set.
* Error code: None.

## monorail.groups.update

* Description: Update a group's settings and users.
* Permission: The requester needs permission to edit this group.
* Parameters:
	* groupName(required, string): The name of the group to edit.
	* who_can_view_members(string): The visibility setting of the group.
	* ext_group_type(string): The type of the source group.
	* last_sync_time(int): The timestamp when the group was last synced from the source.
	* body(dict):
		* groupOwners(list of string): A list of owner emails.
		* groupMembers(list of string): A list of member emails.
* Return message: Empty.
* Error code:
	* 403: The requester has no permission to edit this group.

## monorail.issues.comments.delete

* Description: Delete a comment.
* Permission: The requester needs permission to delete this comment.
* Parameters:
	* projectId(required, string): The name of the project.
	* issueId(required, int): The ID of the issue.
	* commentId(required, int): The ID of the comment.
* Return message: Empty.
* Error code:
	* 403: The requester has no permission to delete this comment.
	* 404: The issue and/or comment does not exist.

## monorail.issues.comments.insert

* Description: Add a comment.
* Permission: The requester needs permission to comment an issue.
* Parameters:
	* projectId(required, string): The name of the project.
	* issueId(required, int): The ID of the issue.
	* sendEmail(boolean): A flag indicating whether to send notifications. The default is True.
	* Request body(dict):
		* content(string): Content of the comment to add.
		* updates(dict): Issue fields to update.
			* summary(string): The new summary of the issue.
			* status(string): The new status of the issue.
			* owner(string): The new owner of the issue.
			* labels(list of string): The labels to add/remove.
			* cc(list of string): A list of emails to add/remove from cc field.
			* blockedOn(list of string): The ID of the issues on which the current issue is blocked.
			* blocking(list of string): The ID of the issues which the current issue is blocking.
			* mergedInto(string): The ID of the issue to merge into.
			* components(list of string): The components to add/remove.
* Return message:
	* author(dict):
		* htmlLink(string): The link to the author profile.
		* name(string): The name of the author.
	* canDelete(boolean): Whether current requester could delete the new comment.
	* content(string): Content of the new comment.
	* id(int): ID of the new comment.
	* published(string): Published datetime of the new comment.
	* updates(dict): Issue fields updated by the new comment.
* Error code:
	* 403: The requester has no permission to comment this issue.
	* 404: The issue does not exist.

## monorail.issues.comments.list

* Description: List all comments for an issue.
* Permission: The requester needs permission to view this issue.
* Parameters:
	* projectId(required, string): The name of the project.
	* issueId(required, int): The ID of the issue.
	* maxResults(int): The max number of comments to retrieve in one request. The default is 100.
	* startIndex(int): The starting index of comments to retrieve. The default is 0.
* Return message:
	* totalResults(int): Total number of comments retrieved.
	* items(list of dict): A list of comments.
		* attachments(dict): The attachment of this comment.
		* author(dict): The author of this comment.
		* canDelete(boolean): Whether the requester could delete this comment.
		* content(string): Content of this comment.
		* deletedBy(dict): The user who has deleted this comment.
		* id(int): The ID of this comment.
		* published(string): Published datetime of this comment.
		* updates(dict): Issue fields updated by this comment.
* Error code:
	* 403: The requester has no permission to view this issue.
	* 404: The issue does not exist.

## monorail.issues.comments.undelete

* Description: Restore a deleted comment.
* Permission: The requester needs permission to delete this comment.
* Parameters:
	* projectId(required, string): The name of the project.
	* issueId(required, int): The ID of the issue.
	* commentId(required, int): The ID of the comment.
* Return message: Empty.
* Error code:
	* 403: The requester has no permission to delete this comment.
	* 404: The issue and/or comment does not exist.

## monorail.issues.get

* Description: Get an issue.
* Permission: The requester needs permission to view this issue.
* Parameters:
	* projectId(required, string): The name of the project.
	* issueId(required, int): The ID of the issue.
* Return message:
	* id(int): ID of this issue.
	* summary(string): Summary of this issue.
	* stars(int): Number of stars of this issue.
	* starred(boolean): Whether this issue is starred by the requester.
	* status(string): Status of this issue.
	* state(string): State of this issue. Available values are 'closed' amd 'open'.
	* labels(list of string): Labels of this issue.
	* author(dict): The reporter of this issue.
	* owner(dict): The owner of this issue.
	* cc(list of dict): The list of emails to cc.
	* updated(string): Last updated datetime of this issue.
	* published(string): Published datetime of this issue.
	* closed(string): Closed datetime of this issue.
	* blockedOn(list of dict): The issues on which the current issue is blocked.
	* blocking(list of dict): The issues which the current issue is blocking.
	* projectId(string): The name of the project.
	* canComment(boolean): Whether the requester can comment on this issue.
	* canEdit(boolean): Whether the requester can edit this issue.
	* components(list of string): Components of the issue.
* Error code:
	* 403: The requester has no permission to view this issue.
	* 404: The issue does not exist.

## monorail.issues.insert

* Description: Add a new issue.
* Permission: The requester needs permission to create a issue.
* Parameters:
	* projectId(required, string): The name of the project.
	* sendEmail(boolean): A flag indicating whether to send notifications. The default is True.
	* body(dict):
		* blockedOn(list of dict): The issues on which the current issue is blocked.
		* blocking(list of dict): The issues which the current issue is blocking.
		* cc(list of dict): The list of emails to cc.
		* description(required, string): Content of the issue.
		* labels(list of string): Labels of this issue.
		* owner(dict): The owner of this issue.
		* status(required, string): Status of this issue.
		* summary(requred, string): Summary of this issue.
		* components(list of string): Components of this issue.
* Return message:
	* id(int): ID of this issue.
	* summary(string): Summary of this issue.
	* stars(int): Number of stars of this issue.
	* starred(boolean): Whether this issue is starred by the requester.
	* status(string): Status of this issue.
	* state(string): State of this issue. Available values are 'closed' and 'open'.
	* labels(list of string): Labels of this issue.
	* author(dict): The reporter of this issue.
	* owner(dict): The owner of this issue.
	* cc(list of dict): The list of emails to cc.
	* updated(string): Last updated datetime of this issue.
	* published(string): Published datetime of this issue.
	* closed(string): Closed datetime of this issue.
	* blockedOn(list of dict): The issues on which the current issue is blocked.
	* blocking(list of dict): The issues which the current issue is blocking.
	* projectId(string): The name of the project.
	* canComment(boolean): Whether the requester can comment on this issue.
	* canEdit(boolean): Whether the requester can edit this issue.
	* components(list of string): Components of this issue.
* Error code:
	* 403: The requester has no permission to create a issue.

## monorail.issues.list

* Description: List issues for projects.
* Permission: The requester needs permission to view issues in requested projects.
* Parameters:
	* projectId(required, string): The name of the project.
	* additionalProject(list of string): Additional projects to search issues.
	* can(string): Canned query. Available values are 'all', 'new', 'open', 'owned', 'starred' and 'to_verify'.
	* label(string): Search for issues with this label.
	* maxResults(int): The max number of issues to retrieve in one request. The default is 100.
	* owner(string): Search for issues with this owner.
	* publishedMax(int): Search for issues published before the timestamp.
	* publishedMin(int): Search for issues published after the timestamp.
	* q(string): Custom query criteria, e.g. 'status:New'.
	* sort(string): Fields to sort issues by.
	* startIndex(int): The starting index of issues to retrieve. The default is 0.
	* status(string): Search for issues of this status.
	* updatedMax(int): Search for issues updated before the timestamp.
	* updatedMin(int): Search for issues updated after the timestamp.
* Return message:
	* totalResults(int): Total number of issues retrieved.
	* items(list of dict): A list of issues.
		* author(dict): The reporter of this issue.
		* blockedOn(list of dict): The issues on which the current issue is blocked.
		* blocking(list of dict): The issues which the current issue is blocking.
		* canComment(boolean): Whether the requester can comment on this issue.
		* canEdit(boolean): Whether the requester can edit this issue.
		* cc(list of dict): The list of emails to cc.
		* closed(string): Closed datetime of this issue.
		* description(string): Content of this issue.
		* id(int): ID of this issue.
		* labels(list of string): Labels of this issue.
		* owner(dict): The owner of this issue.
		* published(string): Published datetime of this issue.
		* starred(boolean): Whether this issue is starred by the requester.
		* stars(int): Number of stars of this issue.
		* state(string): State of this issue. Available values are 'closed' and 'open'.
		* status(string): Status of this issue.
		* summary(string): Summary of this issue.
		* updated(string): Last updated datetime of this issue.
* Error code:
	* 403: The requester has no permission to view issues in the projects.

## monorail.users.get

* Description: Get a user.
* Permission: None.
* Parameters:
	* userId(required, string): The email of the user.
	* ownerProjectsOnly(boolean): Whether to only return projects the user owns. The default is False.
* Return message:
	* projects(dict):
		* name(string): The name of the project.
		* htmlLink(string): The relative url of this project.
		* summary(string): Summary of this project.
		* description(string): Description of this project.
		* role(string): Role of the user in this project.
		* issuesConfig(dict): Issue configurations.
* Error code: None.

## monorail.components.create

* Description:  Create a component.
* Permission: The requester needs permission to edit the requested project.
* Parameters:
	* projectId(required, string): The name of the project.
	* componentName(required, string): The leaf name of the component to create.
	* body(dict):
		* parentPath(string): Full path of the parent component.
		* description(string): Description of the new component.
		* admin(list of string): A list of user emails who can administer this component.
		* cc(list of string): A list of user emails who will be added to cc list when this component is added to an issue.
		* deprecated(boolean): A flag indicating whether this component is deprecated. The default is False.
* Return message:
	* componentId(int): The ID of the new component.
	* projectName(string): The name of the project this new component belongs to.
	* componentPath(string): The full path of the component.
	* description(string): Description of the new component.
	* admin(list of string): A list of user emails who can administer this component.
	* cc(list of string): A list of user emails who will be added to cc list when this component is added to an issue.
	* deprecated(boolean): A flag indicating whether this component is deprecated.
	* created(datetime): Created datetime.
	* creator(string): Email of the creator.
	* modified(datetime): Last modified datetime.
	* modifier(string): Email of last modifier.
* Error code:
	* 400: The component name is invalid or already in use.
	* 403: The requester has no permission to create components in the project.
	* 404: The parent component does not exist, or the project does not exist.

## monorail.components.delete

* Description:  Delete a component.
* Permission: The requester needs permission to edit the requested component.
* Parameters:
	* projectId(required, string): The name of the project.
	* componentPath(required, string): The full path of the component to delete.
* Return message: None.
* Error code:
	* 403: The requester has no permission to delete this component, or tries to delete component that has subcomponents.
	* 404: The component does not exist, or the project does not exist.

## monorail.components.list

* Description:  List all components of a given project.
* Permission: None.
* Parameters:
	* projectId(required, string): The name of the project.
* Return message:
	* components(list of dict):
		* componentId(int): The ID of the new component.
		* projectName(string): The name of the project this new component belongs to.
		* componentPath(string): The full path of the component.
		* description(string): Description of the new component.
		* admin(list of string): A list of user emails who can administer this component.
		* cc(list of string): A list of user emails who will be added to cc list when this component is added to an issue.
		* deprecated(boolean): A flag indicating whether this component is deprecated.
		* created(datetime): Created datetime.
		* creator(string): Email of the creator.
		* modified(datetime): Last modified datetime.
		* modifier(string): Email of last modifier.
* Error code:
	* 403: The requester has no permission to delete this component, or tries to delete component that has subcomponents.
	* 404: The project does not exist.

## monorail.components.update

* Description:  Update a component.
* Permission: The requester needs permission to edit the requested component.
* Parameters:
	* projectId(required, string): The name of the project.
	* componentPath(required, string): The full path of the component to delete.
	* updates(list of dict):
		* field(required, string): Component field to update. Available options are 'LEAF_NAME', 'DESCRIPTION', 'ADMIN', 'CC' and 'DEPRECATED'.
		* leafName(string): The new leaf name of the component.
		* description(string): The new description of the component.
		* admin(list of string): The new list of user emails who can administer this component.
		* cc (list of string): The new list of user emails who will be added to cc list when this component is added to an issue.
		* deprecated(boolean): The new boolean value indicating whether this component is deprecated.
* Return message: None.
* Error code:
	* 400: The new component name is invalid or already in use.
	* 403: The requester has no permission to edit this component.
	* 404: The component does not exist, or the project does not exist.
