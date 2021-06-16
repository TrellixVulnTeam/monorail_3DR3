'use strict';

class SomAlertItem extends Polymer.mixinBehaviors(
    [AlertTypeBehavior, TimeBehavior, BugManagerBehavior], Polymer.Element) {
  static get is() {
    return 'som-alert-item';
  }

  /**
   * Fired when an alert requests that the link bug dialog be shown.
   *
   * @event link-bug
   */

  /**
   * Fired when an alert requests that the file bug dialog be shown.
   *
   * @event file-bug
   */

  /**
   * Fired when an alert requests that the snooze dialog be shown.
   *
   * @event snooze
   */

  /**
   * Fired when an alert requests that the group dialog be shown.
   *
   * @event group
   */

  /**
   * Fired when an alert has an annotation change that needs to be sent to the
   * server.
   *
   * @event annotation-change
   * @param {Object} changes The changes to be sent to the server.
   */

  static get properties() {
    return {
      alert: Object,
      examining: {
        type: Boolean,
        value: false,
      },
      treeName: {
        type: String,
        value: '',
      },
      annotation: {
        type: Object,
        value: {},
      },
      selectedAlert: {
        tupe: String,
        value: '',
      },
      checked: {
        type: Boolean,
        value: false,
        observer: '_alertChecked',
      },
      openState: {
        type: String,
        value: '',
      },
      _bugs: {
        type: Array,
        computed: 'computeBugs(annotation)',
      },
      _commentsClass: {
        type: String,
        computed: '_computeCommentsClass(_numComments)',
      },
      _cssClass: {
        type: String,
        computed: '_computeCssClass(annotation.snoozed, alert.resolved)',
      },
      _duration: {
        type: String,
        computed: '_calculateDuration(alert)'
      },
      _latestTime: {
        type: String,
        computed: '_formatTimestamp(alert.time)'
      },
      _numComments: {
        type: Number,
        computed: '_computeNumComments(annotation.comments)',
      },
      _snoozeTimeLeft: {
        type: String,
        computed: '_computeSnoozeTimeLeft(annotation.snoozeTime)',
      },
      _hasUngroup: {
        type: Boolean,
        computed: '_computeHasUngroup(alert)',
      },
      // _hasResolve and _hasUnresolve disabled.
      _hasResolve: {
        type: Boolean,
        value: false,
      },
      _hasUnresolve: {
        type: Boolean,
        value: false,
      },
      _isCollapsed: {
        type: Boolean,
        computed: '_computeIsCollapsed(openState, alert, annotation, collapseByDefault)',
      },
      _startTime: {
        type: String,
        computed: '_formatTimestamp(alert.start_time)'
      },
      _groupNameInput: Object,
      collapseByDefault: Boolean,
    };
  }

  ready() {
    super.ready();
    this._groupNameInput = this.$.groupName;
  }

  _alertChecked(isChecked) {
    this.dispatchEvent(new CustomEvent('checked', {
      bubbles: true,
      composed: true,
    }));
  }

  _helpLinkForAlert(alert) {
    // TODO(zhangtiff): Add documentation links for other kinds of alerts
    if (this._alertIsWebkit(alert)) {
      return 'http://www.chromium.org/blink/sheriffing';
    }
    return null;
  }

  _alertIsWebkit(alert) {
    // TODO(zhangtiff): Find a better way to categorize alerts
    return alert.key && alert.key.includes('chromium.webkit');
  }

  _comment(evt) {
    this.dispatchEvent(new CustomEvent('comment', {
      bubbles: true,
      composed: true,
    }));
    evt.preventDefault();
  }

  _computeCommentsClass(numComments) {
    if (numComments > 0) {
      return 'comments-link-highlighted';
    }
    return 'comments-link';
  }

  _computeNumComments(comments) {
    if (comments) {
      return comments.length;
    }
    return 0;
  }

  _computeSnoozeTimeLeft(snoozeTime) {
    if (!snoozeTime)
      return '';
    let now = moment(new Date());
    let later = moment(snoozeTime);
    let duration = moment.duration(later.diff(now));
    let text = '';
    if (duration.days()) {
      text += duration.days() + 'd ';
    }
    if (duration.hours()) {
      text += duration.hours() + 'h ';
    }
    if (duration.minutes()) {
      text += duration.minutes() + 'm ';
    }
    if (text == '') {
      text += duration.seconds() + 's ';
    }
    return text + 'left';
  }

  _computeCssClass(snoozed, resolved) {
    return (snoozed || resolved) ? 'dimmed' : '';
  }

  _computeHasUngroup(alert) {
    return alert && !!alert.grouped;
  }

  _linkBug(evt) {
    this.dispatchEvent(new CustomEvent('link-bug', {
      bubbles: true,
      composed: true,
    }));
  }

  _fileBug(evt) {
    this.dispatchEvent(new CustomEvent('file-bug', {
      bubbles: true,
      composed: true,
    }));
  }

  _formatTimestamp(timestamp) {
    if (timestamp != undefined) {
      return new Date(timestamp * 1000).toLocaleString();
    }
    return '';
  }

  _haveLinks(selected, alert) {
    let links = this._getLinks(selected, alert);
    return links && links.length > 0;
  }

  _removeBug(evt) {
    let bug = evt.model.bug;
    this.dispatchEvent(new CustomEvent('remove-bug', {
      detail: {
        bug: String(bug.id),
        summary: bug.summary,
        project: String(bug.projectId),
        url: 'https://crbug.com/' + bug.projectId + '/' + bug.id,
      },
      bubbles: true,
      composed: true,
    }));
  }

  _snooze(evt) {
    if (this.annotation.snoozed) {
      this.dispatchEvent(new CustomEvent('annotation-change', {
        detail: {
          type: 'remove',
          change: { 'snoozeTime': true },
        },
        bubbles: true,
        composed: true,
      }));
    } else {
      this.dispatchEvent(new CustomEvent('snooze', {
        bubbles: true,
        composed: true,
      }));
    }
    evt.preventDefault();
  }

  _ungroup(evt) {
    this.dispatchEvent(new CustomEvent('ungroup', {
      bubbles: true,
      composed: true,
    }));
  }

  _resolve(evt) {
    this.dispatchEvent(new CustomEvent('resolve', {
      bubbles: true,
      composed: true,
    }));
  }

  _unresolve(evt) {
    this.dispatchEvent(new CustomEvent('unresolve', {
      bubbles: true,
      composed: true,
    }));
  }

  _updateGroupName(evt) {
    let oldTitle = this.alert.title;
    // Value comes from a different source depending on whether this event was
    // triggered by a focus change or a key input.
    let value = evt.target.value || evt.detail.keyboardEvent.target.value;

    if (value == oldTitle) return;

    this.dispatchEvent(new CustomEvent('annotation-change', {
      detail: {
        type: 'add',
        change: { 'group_id': value },
      },
      bubbles: true,
      composed: true,
    }));
  }

  _haveSubAlerts(alert) {
    return alert && alert.alerts && alert.alerts.length > 0;
  }

  _getSelected(selected, alert) {
    if (!alert) {
      return selected;
    }

    if (selected && alert.grouped && alert.alerts) {
      // This alert is a group, search for the selected sub-alert.
      let subAlert = alert.alerts.find((a) => {
        return a.key == selected;
      });

      if (subAlert) {
        // Return the selected alert.
        return subAlert;
      }
    }

    return alert;
  }

  _getExtension(selected, alert) {
    return this._getSelected(selected, alert).extension;
  }

  _getImportantLinks(selected, alert) {
    let links = this._getSelected(selected, alert).links;
    if (!links) {
      return [];
    }
    return links.filter((link) => {
      return link.title && link.title.indexOf('(failed)') > -1;
    });
  }

  _haveOtherLinks(selected, alert) {
    let allLinks = this._getLinks(selected, alert);
    let importantLinks = this._getImportantLinks(selected, alert);
    if (allLinks && importantLinks) {
      return allLinks.length > 0 && allLinks.length > importantLinks.length;
    }

    return allLinks && allLinks.length > 0;
  }

  _getLinks(selected, alert) {
    return this._getSelected(selected, alert).links;
  }

  _computeIsCollapsed(openState, alert, annotation, collapseByDefault) {
    if (!alert || !annotation) return;
    // If opened is not defined, fall back to defaults based on annotation
    // and collapseByDefault.
    if (openState == 'opened') {
      return false;
    } else if (openState == 'closed') {
      return true;
    }
    return alert.resolved || annotation.snoozed || collapseByDefault;
  }

  _toggle(evt) {
    let path = evt.path;
    for (let i = 0; i < path.length; i++) {
      let itm = path[i];
      if (itm.classList && itm.classList.contains('no-toggle')) {
        // Clicking on a bug, checkbox, etc shouldn't affect toggled state.
        return;
      }
    }
    this.openState = this._isCollapsed ? 'opened' : 'closed';
  }
}

customElements.define(SomAlertItem.is, SomAlertItem);
