'use strict';

// Time, in milliseconds, between each refresh of data from the server.
const refreshDelayMs = 60 * 1000;

// Time, in milliseconds, to shows ungrouped resolved alerts.
const recentUngroupedResolvedMs = 24 * 3600 * 1000;

class SomAlertView extends Polymer.mixinBehaviors(
    [
      AnnotationManagerBehavior,
      AlertTypeBehavior,
      BugManagerBehavior,
      PostBehavior,
      TimeBehavior,
    ],
    Polymer.Element) {
  static get is() {
    return 'som-alert-view';
  }

  static get properties() {
    return {
      _activeRequests: {
        type: Number,
        value: 0,
      },
      _allAlerts: {
        type: Array,
        value: function() {
          return [];
        },
        computed: `_computeAlerts(_alertsData.*, _alertsResolvedData.*, annotations)`,
      },
      _alerts: {
        type: Array,
        value: function() {
          return [];
        },
        computed: `_filterAlerts(_allAlerts, annotations, _filterPattern)`,
      },
      // Map of stream to data, timestamp of latest updated data.
      _alertsData: {
        type: Object,
        value: function() {
          return {};
        },
      },
      _alertsResolvedData: {
        type: Object,
        value: function() {
          return {};
        },
      },
      alertsTimes: {
        type: Object,
        value: function() {
          return {};
        },
        notify: true,
      },
      _alertStreams: {
        type: Array,
        computed: '_computeAlertStreams(tree)',
        observer: '_updateAlerts',
        value: function() {
          return [];
        },
      },
      annotations: {
        type: Object,
        value: function() {
          return {};
        },
      },
      _bugs: Array,
      _categories: {
        type: Array,
        computed: '_computeCategories(_alerts)',
      },
      _checkedAlerts: {
        type: Array,
        value: function() {
          return [];
        },
      },
      _currentAlertView: {
        type: String,
        computed: '_computeCurrentAlertView(_examinedAlert)',
        value: 'alertListPage',
      },
      _examinedAlert: {
        type: Object,
        computed: '_computeExaminedAlert(_alerts, examinedAlertKey)',
        value: function() {
          return {};
        },
      },
      examinedAlertKey: String,
      _fetchAlertsError: String,
      fetchingAlerts: {
        type: Boolean,
        computed: '_computeFetchingAlerts(_activeRequests)',
        notify: true,
      },
      _fetchedAlerts: {
        type: Boolean,
        value: false,
      },
      _hideJulie: {
        type: Boolean,
        computed:
            `_computeHideJulie(_allAlerts, _fetchedAlerts, fetchingAlerts,
              _fetchAlertsError, tree)`,
        value: true,
      },
      _pageTitleCount: {
        type: Number,
        computed: '_computePageTitleCount(_alerts, _bugs)',
        observer: '_pageTitleCountChanged',
      },
      _sections: {
        type: Object,
        value: {
          // The order the sections appear in the array is the order they
          // appear on the page.
          'default': ['notifications', 'alertsList', 'bugQueue'],
        },
      },
      trees: {
        type: Object,
        value: function() {
          return {};
        },
      },
      tree: {
        type: Object,
        observer: '_treeChanged',
      },
      user: String,
      collapseByDefault: {
        type: Boolean,
        value: false,
      },
      _filterPattern: {
        type: String,
      },
    };
  }

  created() {
    super.created();
    setTimeout(this._refreshAsync.bind(this), refreshDelayMs);
  }

  ////////////////////// Refresh ///////////////////////////

  refresh() {
    this.$.annotations.fetch();

    // Refresh annotations but nothing else on the examine page.
    if (this._currentAlertView == 'examineAlert') return;

    this.$.bugQueue.refresh();
    this.$.treeStatus.refresh();
    this._updateAlerts(this._alertStreams);
  }

  _refreshAsync() {
    this.refresh();
    setTimeout(this._refreshAsync.bind(this), refreshDelayMs);
  }

  ////////////////////// Alerts and path ///////////////////////////

  _pageTitleCountChanged(count) {
    if (count > 0) {
      document.title = '(' + count + ') Sheriff-o-Matic';
    } else {
      document.title = 'Sheriff-o-Matic';
    }
  }

  _computePageTitleCount(alerts, bugs) {
    if (alerts) {
      let count = 0;
      for (let i in alerts) {
        if (!alerts[i].resolved) {
          count++;
        }
      }
      return count;
    }
    return 0;
  }

  _treeChanged(tree) {
    if (!tree)
      return;

    this._alertsData = {};
    this._alertsResolvedData = {};
    this._fetchedAlerts = false;

    // Reorder sections on page based on per tree priorities.
    let sections = this._sections[tree.name] || this._sections.default;
    for (let i in sections) {
      this.$$('#' + sections[i]).style.order = i;
    }
    this.$.annotations.fetch();
  }

  _computeAlertStreams(tree) {
    if (!tree || !tree.name)
      return [];

    if (tree.alert_streams && tree.alert_streams.length > 0) {
      return tree.alert_streams;
    }

    return [tree.name];
  }

  _computeCurrentAlertView(examinedAlert){
    if (examinedAlert && examinedAlert.key) {
      return 'examineAlert';
    }
    return 'alertListPage';
  }

  _computeExaminedAlert(alerts, examinedAlertKey) {
    let examinedAlert = alerts.find((alert) => {
      return alert.key == examinedAlertKey;
    });
    // Two possibilities if examinedAlert is undefined:
    // 1. The alert key is bad.
    // 2. Alerts has not been ajaxed in yet.
    if (examinedAlert) {
      return examinedAlert;
    }
    return {};
  }

  _handleAlertsResponse(response, stream) {
    this._activeRequests -= 1;
    if (this._activeRequests <= 0) {
      this._fetchedAlerts = true;
    }
    if (response.status == 404) {
      this._fetchAlertsError = 'Server responded with 404: ' +
        stream + ' not found. ';
      return false;
    }
    if (!response.ok) {
      this._fetchAlertsError = 'Server responded with ' +
        response.status + ': ' +
        response.statusText;
      return false;
    }
    return response.json();
  }

  _handleAlertsError(error) {
    this._activeRequests -= 1;
    this._fetchAlertsError = 'Could not connect to the server. ' + error;
  }

  _alertsSetData(json, stream) {
    // Ignore old requests that finished after tree switch.
    if (!this._alertStreams.includes(stream))
      return;

    if (json) {
      if (json.swarming) {
        this.set('_swarmingAlerts', json.swarming);
      }
      if (json.alerts && json.alerts.length) {
        this.set(['_alertsData', this._alertStreamVarName(stream)],
                 json.alerts);
        this.alertsTimes = {};
        if (json.timestamp) {
          this.set(['alertsTimes', this._alertStreamVarName(stream)],
                  json.timestamp);
        }
      }
      if (json.resolved && json.resolved.length) {
        this.set(['_alertsResolvedData', this._alertStreamVarName(stream)],
                 json.resolved);
      }
    }
  }

  _updateAlerts(alertStreams) {
    this._fetchAlertsError = '';
    if (alertStreams.length > 0) {
      this._fetchedAlerts = false;

      alertStreams.forEach((stream) => {
        let apis = ['unresolved'];
        for (let api of apis) {
          this._activeRequests += 1;
          let base = '/api/v1/' + api + '/';
          if (window.location.href.indexOf('useMilo') != -1) {
            base = base + 'milo.';
          }
          window.fetch(base + stream, {credentials: 'include'})
              .then((resp) => {return this._handleAlertsResponse(resp,
                                                                 stream)},
                    (error) => {this._handleAlertsError(error)})
              .then((json) => {this._alertsSetData(json, stream)});
        }
      });
    }
  }

  _alertStreamVarName(stream) {
    return stream.replace(/\./g, '_');
  }

  _computeFetchingAlerts(activeRequests) {
    return activeRequests !== 0;
  }

  _countBuilders(alert) {
    if (alert.grouped && alert.alerts) {
      let count = 0;
      for (let i in alert.alerts) {
        count += this._countBuilders(alert.alerts[i]);
      }
      return count;
    } else if (alert.extension && alert.extension.builders) {
      return alert.extension.builders.length;
    } else {
      return 1;
    }
  }

  _computeAlerts(alertsData, alertsResolvedData, annotations) {
    if (!(alertsData && alertsData.base)) {
      return [];
    }
    alertsData = alertsData.base;
    if (!(alertsResolvedData && alertsResolvedData.base)) {
      alertsResolvedData = {}
    } else {
      alertsResolvedData = alertsResolvedData.base;
    }

    let allAlerts = [];
    let groups = {};
    this._computeAlertsSet(alertsData, false, annotations, allAlerts, groups);
    this._computeAlertsSet(alertsResolvedData, true, annotations, allAlerts,
                           groups);

    allAlerts = this._sortAlerts(allAlerts, annotations);
    allAlerts = this._filterUngroupedResolved(allAlerts);
    return allAlerts;
  }

  _computeAlertsSet(alertsData, resolved, annotations, alertItems,
                              groups) {
    for (let tree in alertsData) {
      let alerts = alertsData[tree];
      if (!alerts) {
        continue;
      }

      for (let i in alerts) {
        this._computeAlert(alerts[i], resolved, annotations, alertItems,
                           groups);
      }
    }
  }

  _computeAlert(alert, resolved, annotations, alertItems, groups) {
    alert.resolved = resolved;

    let ann = this.computeAnnotation(annotations, alert);
    if (ann.groupID) {
      if (!(ann.groupID in groups)) {
        let group = {
          key: ann.groupID,
          title: ann.groupID,
          body: ann.groupID,
          severity: alert.severity,
          time: alert.time,
          start_time: alert.start_time,
          links: [],
          tags: [],
          type: alert.type,
          extension: {stages: [], builders: [], grouped: true},
          grouped: true,
          alerts: [],
          resolved: resolved,
        }

        // Group name is stored using the groupID annotation.
        let groupAnn = this.computeAnnotation(annotations, group);
        if (groupAnn.groupID) {
          group.title = groupAnn.groupID;
        }

        groups[ann.groupID] = group;
        alertItems.push(group);
      }
      let group = groups[ann.groupID];
      if (alert.severity < group.severity) {
        group.severity = alert.severity;
      }
      if (alert.time > group.time) {
        group.time = alert.time;
      }
      if (alert.start_time < group.start_time) {
        group.start_time = alert.start_time;
      }
      if (alert.links) group.links = group.links.concat(alert.links);
      if (alert.tags) group.tags = group.tags.concat(alert.tags);

      if (alert.extension) {
        this._mergeStages(group.extension.stages, alert.extension.stages,
                          alert.extension.builders);
        this._mergeBuilders(group.extension.builders,
                            alert.extension.builders,
                            alert.extension.stages);
        // TODO(martiniss): Comment this back in once the logic is robust.
        // Right now this isn't very useful if you actually want to use these
        // regression ranges to determine which alerts should be grouped
        // together, etc.... In addition, usage of regression ranges by sheriffs
        // is pretty low, so I think disabling this for now should be ok, and
        // fairly unnoticed.
        //this._mergeRegressionRanges(group.extension, alert.extension);
        group.extension.reason = this._mergeReason(group.extension,
                                                   alert.extension);
      }
      group.alerts.push(alert);
      if (resolved) {
        group.resolved = true;
      }
    } else {
      // Ungrouped alert.
      alertItems.push(alert);
    }
  }

  _mergeReason(groupExtension, alertExtension) {
    if (!alertExtension.reason || !alertExtension.reason.test_names || alertExtension.reason.test_names.length == 0) {
      return alertExtension.reason;
    }

    if (!groupExtension.reason) {
      return alertExtension.reason;
    }

    if (alertExtension.reason.test_names.length != groupExtension.reason.test_names.length) {
      console.error(alertExtension.reason.test_names + " is not equal to " + groupExtension.reason.test_names + " but they were merged together. This should never happen, because merging is done server side by looking at the reason data.");
    } else {
      return groupExtension.reason;
    }
  }

  _mergeRegressionRanges(groupExtension, alertExtension) {
    if (!alertExtension.regression_ranges) {
      return;
    }

    if (!groupExtension.regression_ranges) {
      groupExtension.regression_ranges = alertExtension.regression_ranges;
      return;
    }

    let byRepo = {};
    groupExtension.regression_ranges.forEach((range) => {
      if (!range) return;
      if (!byRepo[range.repo]) {
        byRepo[range.repo] = [];
      }

      byRepo[range.repo].push(range);
    });

    alertExtension.regression_ranges.forEach((range) => {
      if (!range) return;
      if (!byRepo[range.repo]) {
        byRepo[range.repo] = [];
      }

      byRepo[range.repo].push(range);
    });

    groupExtension.regression_ranges = [];
    for (let repo in byRepo) {
      groupExtension.regression_ranges.push(
          byRepo[repo].reduce(this._mergeRegressionRange.bind(this)));
    }
  }

  _mergeRegressionRange(groupRange, alertRange) {
    if (!!groupRange.error) {
      return groupRange;
    }

    if (alertRange === undefined || !groupRange || !groupRange.positions) {
      return undefined;
    }

    // Short for groupRegressionRanges
    let gRR = groupRange.positions.map(this._parseCommitPosition);
    // Short for alertRegressionRanges
    let aRR = alertRange.positions.map(this._parseCommitPosition);

    /* There are 5 possible cases we can encounter
     * 1
     *       [  ]
     *   [ ]
     * 2
     *     [  ]
     *   [  ]
     * 3
     *     [ ]
     *   [    ]
     * 4
     *   [ ]
     *    [ ]
     * 5
     *    [  ]
     *         [  ]
     * In case 1 and 5, the regression ranges are conflicting; they don't
     * intersect at all. In this case, we record the error, and show the user
     * that this group of alerts doesn't have a common regression range.
     *
     * In the other cases, it's assumed that the error probably happened because
     * of a CL in the intersection of the regression ranges. The math below
     * finds the intersection of the two intervals.
    */
    let lower = Math.max(gRR[0], aRR[0]);
    let upper = Math.min(gRR[gRR.length - 1], aRR[aRR.length - 1]);
    if (lower > upper) {
      console.warn("Bad regression ranges", gRR, aRR)
      return {
        repo: groupRange.repo,
        error: "Invalid regression range",
        explanation: `Two regression ranges, ${gRR[0]} - ${gRR[gRR.length - 1]} and ${aRR[0]} - ${aRR[aRR.length-1]}, were merged together, but don't share any common commit positions. This probably means this alert should be split into a few different alerts, each with different root causes.`,
        bad_range: [lower, upper]
      };
    }

    let copy = Object.assign({}, groupRange);
    copy.positions = [lower, upper].map((cp) => {
      return 'refs/heads/master@{#' + cp + '}';
    });
    return copy;
  }

  _parseCommitPosition(pos) {
    let groups = /refs\/heads\/master@{#([0-9]+)}/.exec(pos);
    if (groups && groups.length == 2) {
      return Number(groups[1]);
    }
  }

  _sortAlerts(alerts, annotations) {
    alerts.sort((a, b) => {
      let aAnn = this.computeAnnotation(annotations, a);
      let bAnn = this.computeAnnotation(annotations, b);

      let aHasBugs = aAnn.bugs && aAnn.bugs.length > 0;
      let bHasBugs = bAnn.bugs && bAnn.bugs.length > 0;

      let aBuilders = this._countBuilders(a);
      let bBuilders = this._countBuilders(b);

      let aHasSuspectedCLs = a.extension && a.extension.suspected_cls;
      let bHasSuspectedCLs = b.extension && b.extension.suspected_cls;
      let aHasFindings = a.extension && a.extension.has_findings;
      let bHasFindings = b.extension && b.extension.has_findings;

      // Resolved alerts last.
      if (a.resolved != b.resolved) {
        return a.resolved ? 1 : -1;
      } else if (a.resolved) {
        // Both alerts resolved, sort by count.
        if (aBuilders < bBuilders) {
          return 1;
        }
        if (aBuilders > bBuilders) {
          return -1;
        }
      }

      if (a.severity != b.severity) {
        // Note: 3 is the severity number for Infra Failures.
        // We want these at the bottom of the severities for sheriffs.
        if (a.severity == AlertSeverity.InfraFailure) {
          return 1;
        } else if (b.severity == AlertSeverity.InfraFailure) {
          return -1;
        }

        // 7 is the severity for offline builders. Note that we want these to
        // appear above infra failures.
        if (a.severity == AlertSeverity.OfflineBuilder) {
          return 1;
        } else if (b.severity == AlertSeverity.OfflineBuilder) {
          return -1;
        }
        return a.severity - b.severity;
      }

      // TODO(davidriley): Handle groups.

      if (aAnn.snoozed == bAnn.snoozed && aHasBugs == bHasBugs) {
        // We want to show alerts with Findit results above.
        // Show alerts with revert CL from Findit first;
        // the alerts with suspected_cls;
        // then alerts with flaky tests;
        // then alerts with no Findit results.
        if (aHasSuspectedCLs && bHasSuspectedCLs) {
          for (let key in b.extension.suspected_cls) {
            if (b.extension.suspected_cls[key].reverting_cl_url) {
              return 1;
            }
          }
          return -1;
        } else if (aHasSuspectedCLs) {
          return -1;
        } else if (bHasSuspectedCLs) {
          return 1;
        } else if (aHasFindings) {
          return -1;
        } else if (bHasFindings) {
          return 1;
        }

        if (aBuilders < bBuilders) {
          return 1;
        }
        if (aBuilders > bBuilders) {
          return -1;
        }
        if (a.title < b.title) {
          return -1;
        }
        if (a.title > b.title) {
          return 1;
        }
        return 0;
      } else if (aAnn.snoozed == bAnn.snoozed) {
        return aHasBugs ? 1 : -1;
      }

      return aAnn.snoozed ? 1 : -1;
    });

    return alerts;
  }

  _filterUngroupedResolved(alerts) {
    return alerts.filter(function(alert) {
      if (!alert.resolved || alert.grouped) {
        return true;
      }

      // Ungrouped, resolved alerts: display for 1 day.
      let alert_time = moment(alert.start_time * 1000);
      let now = moment(new Date());
      return (now - alert_time) < recentUngroupedResolvedMs;
    });
  }

  _filterAlerts(allAlerts, annotations, pattern) {
    const filteredAlerts = pattern
      ? this._filterByPattern(allAlerts, annotations, pattern)
      : allAlerts;
    return filteredAlerts;
  }

  _searchAlert(alert, re) {
    if ((alert.key && alert.key.match(re)) ||
        (alert.title && alert.title.match(re)) ||
        (alert.body && alert.body.match(re))) {
      return true;
    }

    let duration = this._calculateDuration(alert);
    if (duration.match(re)) {
      return true;
    }

    if (this._searchLinks(alert.links, re)) {
      return true;
    }

    if (alert.grouped && alert.alerts) {
      for (let subAlert of alert.alerts) {
        if (this._searchAlert(subAlert, re)) {
          return true;
        }
      }
      return false;
    }

    if (this._searchBuildExtension(alert.extension, re)) {
      return true;
    }

    return false;
  }

  _searchBugs(bugs, re) {
    return bugs.some((bug) => bug.id && bug.id.toString().match(re) ||
      bug.summary && bug.summary.match(re));
  }

  _searchLinks(links, re) {
    if (links) {
      for (let link of links) {
        if (link.title.match(re)) {
          return true;
        }
      }
    }
    return false;
  }

  _searchNotes(notes, re) {
    if (notes) {
      for (let note of notes) {
        if (note.match(re)) {
          return true;
        }
      }
    }
    return false;
  }

  _searchBuildExtension(extension, re) {
    if (extension) {
      if (extension.builders) {
        for (let builder of extension.builders) {
          if (builder.name.match(re)) {
            return true;
          }
        }
      }
      if (extension.reason) {
        if ((extension.reason.name && extension.reason.name.match(re)) ||
            this._searchNotes(extension.reason.test_names, re)) {
          return true;
        }
      }
    }

    return false;
  }

  _filterByPattern(alerts, annotations, pattern) {
    // Treat pattern as case-insensitive, unless there is a capital letter
    // in the pattern.
    let re = RegExp(pattern, pattern.match(/[A-Z]/) ? "" : "i");
    return alerts.filter((alert) => this._searchAlert(alert, re) ||
      this._searchBugs(this.computeBugs(this.computeAnnotation(annotations, alert)), re) // eslint-disable-line max-len
    );
  }

  _mergeExtensions(extension) {
    if (!this._haveGrouped(extension)) {
      return extension;
    }

    // extension is a list of extensions.
    let mergedExtension = {stages: [], builders: []};
    for (let i in extension) {
      let subExtension = extension[i];
      this._mergeStages(mergedExtension.stages, subExtension.stages,
                        subExtension.builders);
      this._mergeBuilders(mergedExtension.builders, subExtension.builders,
                          subExtension.stages);
    }

    return mergedExtension;
  }

  _mergeStages(mergedStages, stages, builders) {
    for (let i in stages) {
      this._mergeStage(mergedStages, stages[i], builders);
    }
  }

  _mergeStage(mergedStages, stage, builders) {
    let merged = mergedStages.find((s) => {
      return s.name == stage.name;
    });

    if (!merged) {
      merged = {
        name: stage.name,
        status: stage.status,
        logs: [],
        links: [],
        notes: stage.notes,
        builders: [],
      };

      mergedStages.push(merged);
    }
    if (stage.status != merged.status && stage.status == 'failed') {
      merged.status = 'failed';
    }

    // Only keep notes that are in common between all builders.
    merged.notes = merged.notes.filter(function(n) {
      return stage.notes.indexOf(n) !== -1;
    });

    merged.builders = merged.builders.concat(builders);
  }

  _mergeBuilders(mergedBuilders, builders, stages) {
    for (let i in builders) {
      this._mergeBuilder(mergedBuilders, builders[i], stages);
    }
  }

  _mergeBuilder(mergedBuilders, builder, stages) {
    let merged = mergedBuilders.find((b) => {
      // TODO: In the future actually merge these into a single entry.
      return b.name == builder.name &&
             b.first_failure == builder.first_failure &&
             b.latest_failure == builder.latest_failure;
    });

    if (!merged) {
      merged = Object.assign({stages: []}, builder);
      mergedBuilders.push(merged);
    }

    merged.start_time = Math.min(merged.start_time, builder.start_time);
    merged.first_failure =
        Math.min(merged.first_failure, builder.first_failure);
    if (builder.latest_failure > merged.latest_failure) {
      merged.url = builder.url;
      merged.latest_failure = builder.latest_failure;
    }

    merged.stages = merged.stages.concat(stages);
  }

  _computeHideJulie(alerts, fetchedAlerts, fetchingAlerts,
                              fetchAlertsError, tree) {
    if (fetchingAlerts || !fetchedAlerts || !alerts ||
        fetchAlertsError !== '' || !tree) {
      return true;
    }
    return alerts.length > 0;
  }

  ////////////////////// Alert Categories ///////////////////////////

  _alertItemsWithCategory(alerts, category) {
    return alerts.filter(function(alert) {
      if (category == AlertSeverity.Resolved) {
        return alert.resolved;
      } else if (alert.resolved) {
        return false;
      }

      if (category == AlertSeverity.InfraFailure) {
        // Put trooperable alerts into "Infra failures" on sheriff views
        return this.isTrooperAlertType(alert.type) ||
               alert.severity == category;
      }
      return alert.severity == category;
    }, this);
  }

  _computeCategories(alerts) {
    let categories = [];
    alerts.forEach(function(alert) {
      let cat = alert.severity;
      if (alert.resolved) {
        cat = AlertSeverity.Resolved;
      } else if (this.isTrooperAlertType(alert.type)) {
        // Collapse all trooper alerts into the "Infra failures" category.
        cat = AlertSeverity.InfraFailure;
      }
      if (!categories.includes(cat)) {
        categories.push(cat);
      }
    }, this);

    return categories;
  }

  _getCategoryTitle(category, trees) {
    return {
      0: 'Tree closers',
      1: 'Stale masters',
      2: 'Probably hung builders',
      3: 'Infra failures',
      4: 'Consistent failures',
      5: 'New failures',
      6: 'Idle builders',
      7: 'Offline builders',
      // Special categories
      10000: 'Recently resolved alerts',
    }[category];
  }

  _isInfraFailuresSection(category) {
    return category === AlertSeverity.InfraFailure;
  }

  _isResolvedSection(category) {
    return category === AlertSeverity.Resolved;
  }

  ////////////////////// Annotations ///////////////////////////

  _computeGroupTargets(alert, alerts) {
    // Valid group targets:
    // - must be of same type
    // - must not be with itself
    // - must not consist of two groups
    // - must be unresolved or grouped
    return alerts.filter((a) => {
      return a.type == alert.type && a.key != alert.key &&
             (!alert.grouped || !a.grouped) &&
             (!a.resolved || a.grouped);
    });
  }

  _handleAnnotation(evt) {
    let target = evt.composedPath()[0];
    this.$.annotations.handleAnnotation(target.get('alert'), evt.detail);
  }

  _handleComment(evt) {
    let target = evt.composedPath()[0];
    this.$.annotations.handleComment(target.get('alert'));
  }

  _handleLinkBug(evt) {
    let target = evt.composedPath()[0];
    this.$.annotations.handleLinkBug([target.get('alert')]);
  }

  _handleFileBug(evt) {
    let target = evt.composedPath()[0];
    this.$.annotations.handleFileBug([target.get('alert')]);
  }

  _handleLinkBugBulk(evt) {
    this.$.annotations.handleLinkBug(this._checkedAlerts,
                                     this._uncheckAll.bind(this));
  }

  _handleRemoveBug(evt) {
    let target = evt.composedPath()[0];
    this.$.annotations.handleRemoveBug(target.get('alert'), evt.detail);
  }

  _handleSnooze(evt) {
    let target = evt.composedPath()[0];
    this.$.annotations.handleSnooze([target.get('alert')]);
  }

  _handleSnoozeBulk(evt) {
    this.$.annotations.handleSnooze(this._checkedAlerts,
                                    this._uncheckAll.bind(this));
  }

  _handleGroupBulk(evt) {
    this.$.annotations.handleGroupAlerts(
        this._checkedAlerts,
        this._uncheckAll.bind(this));
  }

  // This opens the bulk ungroup dialog.
  _handleUngroupBulk(evt) {
    let groups = this._checkedAlerts.filter((alert) => {
      return alert && alert.grouped;
    });

    this.$.annotations.handleUngroupBulk(groups);
  }

  // This is called after the user has confirmed the bulk ungroup operation.
  _handleBulkUngrouped(evt) {
    let checkedKeys = new Set();
    for (let i in evt.detail) {
      checkedKeys.add(evt.detail[i].key);
    }

    let categories = Polymer.dom(this.root).querySelectorAll(
      '.alert-category'
    );
    for (let i = 0; i < categories.length; i++) {
      categories[i].checkKeys(checkedKeys, true);
    }
  }

  _hasGroupAll(checkedAlerts) {
    // If more than two of the checked alerts are a group...
    let groups = checkedAlerts.filter((alert) => {
      return alert && alert.grouped;
    });
    return checkedAlerts.length > 1 && groups.length < 2;
  }

  _hasUngroupAll(checkedAlerts) {
    // If more than two of the checked alerts are a group...
    let groups = checkedAlerts.filter((alert) => {
      return alert && alert.grouped;
    });
    return groups.length > 0;
  }

  _handleUngroup(evt) {
    let target = evt.composedPath()[0];
    this.$.annotations.handleUngroup(target.get('alert'));
  }

  _handleResolve(evt) {
    let target = evt.composedPath()[0];
    let alert = target.get('alert');
    if (alert.grouped) {
      this._resolveAlerts(alert.alerts, true);
    } else {
      this._resolveAlerts([alert], true);
    }
  }

  _handleResolveBulk(evt) {
    this._resolveAlerts(this._checkedAlerts, true);
    this._uncheckAll();
  }

  _handleUnresolve(evt) {
    let alert = evt.target.get('alert');
    if (alert.grouped) {
      this._resolveAlerts(alert.alerts, false);
    } else {
      this._resolveAlerts([alert], false);
    }
  }

  _resolveAlerts(alerts, resolved) {
    let tree = this.tree.name;
    let url = '/api/v1/resolve/' + encodeURIComponent(tree);
    let keys = alerts.map((a) => {
      return a.key;
    });
    let request = {
      'keys': keys,
      'resolved': resolved,
    };
    this.postJSON(url, request)
        .then(jsonParsePromise)
        .then(this._resolveResponse.bind(this));
  }

  _findAlertIndexByKey(alerts, key) {
    for (let i in alerts) {
      if (alerts[i].key == key) {
        return i;
      }
    }
    return -1;
  }

  _resolveResponse(response) {
    for (let i in response.keys) {
      // Search for the existing alert and remove it from the alerts data.
      let key = response.keys[i];
      let alerts = this._alertsData[response.tree];
      let index = this._findAlertIndexByKey(alerts, key);
      let alert;
      if (index != -1) {
        alert = alerts[index];
        this.splice(['_alertsData', response.tree], index, 1 );
      } else {
        let alerts = this._alertsResolvedData[response.tree];
        index = this._findAlertIndexByKey(alerts, key);
        if (index != -1 ) {
          alert = alerts[index];
          this.splice(['_alertsResolvedData', response.tree], index, 1 );
        }
      }

      // Re-add it to the correct structure.
      if (alert) {
        if (response.resolved) {
          this.push(['_alertsResolvedData', response.tree], alert);
        } else {
          this.push(['_alertsData', response.tree], alert);
        }
      }
    }

    return response;
  }

  _handleChecked(evt) {
    let categories = Polymer.dom(this.root).querySelectorAll(
      '.alert-category'
    );
    let checked = [];
    for (let i = 0; i < categories.length; i++) {
      checked = checked.concat(categories[i].checkedAlerts);
    }
    this._checkedAlerts = checked;
  }

  _uncheckAll(evt) {
    let categories = Polymer.dom(this.root).querySelectorAll(
      '.alert-category'
    );
    for (let i = 0; i < categories.length; i++) {
      categories[i].uncheckAll();
    }
  }
}

customElements.define(SomAlertView.is, SomAlertView);
