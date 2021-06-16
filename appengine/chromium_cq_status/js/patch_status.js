// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

var patchStatusModule = (function() {

var attemptStart = 'patch_start';
var attemptEnd = 'patch_stop';

var container = null;

// Provide access to imported DOM in tests.
// In production, currentDocument == document.
var currentScript = document._currentScript || document.currentScript;
var currentDocument = currentScript.ownerDocument;

var actionInfo = {
  patch_start: {
    description: 'CQ started processing patch',
    cls: 'important',
  },
  patch_stop: {
    description: 'CQ stopped processing patch',
    cls: 'important',
  },
  patch_failed: {
    description: 'CQ rejected the patch',
    cls: 'important',
  },
  patch_ready_to_commit: {
    description: 'Patch is ready to be committed',
    cls: 'important',
    duplicate: function() { return true; },
  },
  patch_tree_closed: {
    description: 'Patch blocked on closed tree',
    cls: 'bad',
    duplicate: lastTreeClosedRecordEqual,
  },
  patch_throttled: {
    description: 'Patch blocked on throttled CQ',
    cls: 'bad',
  },
  patch_committing: {
    description: 'Patch is being committed',
    cls: 'normal',
  },
  patch_committed: {
    description: 'Patch committed successfully',
    cls: 'good',
  },
  verifier_skip: {
    description: 'Tryjobs skipped',
    cls: 'normal',
    filter: tryjobVerifierCheck,
  },
  // This is a useful message for debugging logs, but it will re-appear each
  // time CQ is restarted (manually or via auto_deploy.py). To avoid flooding CQ
  // status app with unnecessary updates, we ignore this message here.
  verifier_start: {
    filter: function() { return false; }
  },
  // We decided to hide this message as it duplicates information in other
  // messages, e.g. verifier_retry, verifier_jobs_update. We'll keep it in raw
  // CQ logs for easier debugging.
  verifier_trigger:  {
    filter: function() { return false; }
  },
  verifier_jobs_update: jobsUpdateInfo,
  verifier_error: {
    description: 'Error fetching tryjob status',
    cls: 'bad',
    filter: tryjobVerifierCheck,
  },
  verifier_pass: {
    description: 'All tryjobs passed',
    cls: 'good',
    filter: tryjobVerifierCheck,
  },
  verifier_fail: {
    description: 'Patch failed tryjobs',
    cls: 'bad',
    filter: tryjobVerifierCheck,
  },
  verifier_retry: verifierRetryInfo,
  verifier_timeout: {
    description: 'Timeout waiting for tryjob to trigger',
    cls: 'bad',
    filter: tryjobVerifierCheck,
  },
};

tryjobStatus = [
  'passed',
  'failed',
  'running',
  'not-started',
];

function jobStateToStatus(jobState) {
  switch(jobState) {
    case 'JOB_NOT_TRIGGERED': return 'not-started';
    case 'JOB_PENDING': return 'not-started';
    case 'JOB_RUNNING': return 'running';
    case 'JOB_SUCCEEDED': return 'passed';
    case 'JOB_FAILED': return 'failed';
    case 'JOB_TIMED_OUT': return 'failed';
    default: return 'not-started';
  }
}

function jobStatePrint(jobState) {
  switch(jobState) {
    case 'JOB_NOT_TRIGGERED': return 'not triggered';
    case 'JOB_PENDING': return 'pending';
    case 'JOB_RUNNING': return 'running';
    case 'JOB_SUCCEEDED': return 'succeeded';
    case 'JOB_FAILED': return 'failed';
    case 'JOB_TIMED_OUT': return 'timed out';
    default: return 'in unknown state';
  }
}

function init() {
  container = currentDocument.querySelector('#container');
}

function main() {
  init();
  container.textContent = 'Loading patch data...';
  loadPatchsetRecords(function(records) {
    displayAttempts(records);
    scrollToHash();
  });
}

function loadPatchsetRecords(callback) {
  var url = '//' + window.location.host + '/query/codereview_hostname=' +
      codereview_hostname + '/issue=' + issue + '/patchset=' + patchset;
  var records = [];
  var moreRecords = true;
  function queryRecords(cursor) {
    var xhr = new XMLHttpRequest();
    xhr.open('get', url + (cursor ? '?cursor=' + encodeURIComponent(cursor) : ''), true);
    xhr.onreadystatechange = function() {
      if (xhr.readyState === XMLHttpRequest.DONE) {
        response = JSON.parse(xhr.responseText);
        records = records.concat(response.results);
        if (response.more) {
          queryRecords(response.cursor);
        } else {
          records.reverse();
          callback(records);
        }
      }
    };
    xhr.send();
  }
  queryRecords(null);
}

function displayAttempts(records) {
  container.textContent = '';
  var recordGroups = splitByAttempts(records.filter(function(record) {
    return 'action' in record.fields;
  }));
  var attempts = [];
  recordGroups.forEach(function(recordGroup, i) {
    var lastRecord = recordGroup[recordGroup.length - 1];
    var attempt = {
      number: i + 1,
      start: recordGroup[0].timestamp,
      ended: lastRecord.fields.action == attemptEnd,
      lastUpdate: lastRecord.timestamp,
      tryjobs: {},
      rows: [],
      header: null,
    };
    var previousRecord;
    recordGroup.forEach(function(record) {
      var info = actionInfo[record.fields.action];
      if (!info) {
        console.warn('Unexpected action ' + record.fields.action +
                     ' at timestamp ' + record.timestamp);
        return;
      }
      if (typeof info === 'function') {
        info = info(attempt, record);
      }
      if (!info || (info.filter && !info.filter(record))) {
        return;
      }
      if (info && info.duplicate && previousRecord &&
          previousRecord.fields.action == record.fields.action &&
          info.duplicate(record, previousRecord)) {
        // If the previous record is a duplicate of the current, remove previous
        // one, so we show the record with the latest timestamp, which in turn
        // allows user to see that there is progress and that CQ is not stuck.
        attempt.rows.pop();
      }
      var duration = getDurationString(attempt.start, record.timestamp);
      attempt.rows.push(newRow(record.timestamp, duration, info.description,
                               record.fields.message, info.cls));
      previousRecord = record;
    });
    attempt.header = newHeader(attempt);
    attempts.push(attempt);
  });

  if (attempts.length === 0) {
    container.textContent = 'No attempts found.';
    return;
  }
  attempts.reverse();
  attempts.forEach(function(attempt) {
    container.appendChild(attempt.header);
    attempt.rows.reverse();
    attempt.rows.forEach(function(row) {
      container.appendChild(row);
    });
  });
}

function splitByAttempts(records) {
  var recordGroups = [];
  var recordGroup = null;
  records.forEach(function(record) {
    if (record.fields.action == attemptStart) {
      if (recordGroup) {
        console.warn('Attempt group started before previous one ended.');
        return; // Skip repeated start action.
      } else {
        recordGroup = [];
      }
    }
    if (recordGroup) {
      recordGroup.push(record);
    } else {
      console.warn('Attempt record encountered before start signal.');
    }
    if (record.fields.action == attemptEnd) {
      if (recordGroup) {
        recordGroups.push(recordGroup);
      } else {
        console.warn('Attempt group ended before starting.');
      }
      recordGroup = null;
    }
  });
  if (recordGroup) {
    recordGroups.push(recordGroup);
  }
  return recordGroups;
}

function newRow(timestamp, duration, description, message, cls) {
  var row = newElement('row', '', cls);
  row.appendChild(newElement('timestamp', new Date(timestamp * 1000)));
  row.appendChild(newElement('duration', '(' + duration + ')'));
  var descriptionNode = newElement('description');
  if (typeof description === 'string') {
    descriptionNode.textContent = description;
  } else {
    descriptionNode.appendChild(description);
  }
  row.appendChild(descriptionNode);
  if (message) {
    row.appendChild(newElement('message', '(' + message + ')'));
  }
  return row;
}

function newHeader(attempt) {
  var header = newElement('header');

  var h3 = newElement('h3');
  var anchor = newElement('a', 'Attempt #' + attempt.number);
  anchor.name = attempt.number;
  anchor.href = '#' + attempt.number;
  h3.appendChild(anchor);
  header.appendChild(h3);

  if (attempt.ended) {
    header.appendChild(newElement('div', 'Total duration: ' + getDurationString(attempt.start, attempt.lastUpdate)));
  } else {
    header.appendChild(newElement('div', 'In progress for: ' + getDurationString(attempt.start, Date.now() / 1000)));
    header.appendChild(newElement('div', 'Last update: ' + getDurationString(attempt.lastUpdate, Date.now() / 1000) + ' ago'));
  }

  var builders = Object.getOwnPropertyNames(attempt.tryjobs).sort();
  if (builders.length !== 0) {
    header.appendChild(newElement('span', (attempt.ended ? 'Last' : 'Current') + ' tryjob statuses: '));
    builders.forEach(function(builder) {
      header.appendChild(newTryjobBubble(builder, attempt.tryjobs[builder].status, attempt.tryjobs[builder].url));
      header.appendChild(newElement('span', ' '));
    });
    header.appendChild(newElement('br'));
  }

  header.appendChild(newElement('div', 'Status update timeline:'));

  return header;
}

function newElement(tag, text, cls) {
  var element = currentDocument.createElement(tag);
  if (text) {
    element.textContent = text;
  }
  if (cls) {
    element.classList.add(cls);
  }
  return element;
}

function getDurationString(startTimestamp, timestamp) {
  var seconds = parseInt(timestamp - startTimestamp);
  if (seconds < 60) {
    return seconds + ' second' + plural(seconds);
  }
  var minutes = parseInt(seconds / 60);
  if (minutes < 60) {
    return minutes + ' minute' + plural(minutes);
  }
  var hours = parseInt(minutes / 60);
  minutes -= hours * 60;
  return hours + ' hour' + plural(hours) + (minutes ? ' ' + minutes + ' minute' + plural(minutes) : '');
}

function plural(value) {
  return value === 1 ? '' : 's';
}

function simpleTryjobVerifierCheck(record) {
  return record.fields.verifier === 'simple try job';
}

function tryjobVerifierCheck(record) {
  return record.fields.verifier === 'try job';
}

function lastTreeClosedRecordEqual(record, previousRecord) {
  return previousRecord.fields.message == record.fields.message;
}

function verifierRetryInfo(attempt, record) {
  var builder = record.fields.builder;
  var node = newElement('div');
  node.appendChild(newElement('span', 'Retrying failed tryjob: ' + builder));
  return {
    description: node,
    cls: 'bad',
    filter: tryjobVerifierCheck,
  };
}

function jobsUpdateInfo(attempt, record) {
  // Update latest attempt tryjob state.
  if(!tryjobVerifierCheck(record)) return null;
  var states = record.fields.jobs;
  var node = newElement('div');
  var firstLine = true;
  forEachJobState(states, function(jobState, jobs) {
    tryjobs = [];
    jobs.forEach(function(job, i) {
      builder = job.builder;
      if (!attempt.tryjobs[builder]) {
        attempt.tryjobs[builder] = initialTryjobState();
      }
      if (attempt.tryjobs[builder].jobState !== jobState) {
        attempt.tryjobs[builder].builder = builder;
        attempt.tryjobs[builder].status = jobStateToStatus(jobState);
        attempt.tryjobs[builder].jobState = jobState;
        attempt.tryjobs[builder].url = job.url;
        tryjobs.push(attempt.tryjobs[builder]);
      }
    });
    if(tryjobs.length === 0) return null;
    if (!firstLine) {
      node.appendChild(newElement('br'));
    }
    firstLine = false;
    node.appendChild(newElement('span', 'Tryjob' + plural(tryjobs.length) + ' ' + jobStatePrint(jobState) + ': '));
    tryjobs.forEach(function(tryjob, i) {
      node.appendChild(newTryjobBubble(
        tryjob.builder, tryjob.status, tryjob.url));
      node.appendChild(newElement('span', ' '));
    });
  });

  return firstLine ? null : {
    description: node,
    cls: 'normal',
    filter: tryjobVerifierCheck,
  };
}

function initialTryjobState() {
  return {
    builder: null,
    status: 'triggered',
    jobState: null,
    url: null,
  };
}

function forEachBuilder(jobs, callback) {
  for (var master in jobs) {
    for (var builder in jobs[master]) {
      callback(builder, jobs[master][builder]);
    }
  }
}

function forEachJobState(states, callback) {
  for (var jobState in states) {
    if (states.hasOwnProperty(jobState)) {
      callback(jobState, states[jobState]);
    }
  }
}

function newTryjobBubble(builder, status, url) {
  var bubble = newElement('a', builder, 'tryjob');
  bubble.classList.add(status);
  bubble.title = status;
  if (url) {
    bubble.href = url;
  }
  bubble.addEventListener('mouseenter', bubbleHighlight);
  bubble.addEventListener('mouseleave', bubbleUnhighlight);
  return bubble;
}

function bubbleHighlight(event) {
  [].forEach.call(currentDocument.querySelectorAll('a.tryjob[href="' + event.target.href + '"]'), function(bubble) {
    bubble.classList.add('highlight');
  });
}

function bubbleUnhighlight(event) {
  [].forEach.call(currentDocument.querySelectorAll('a.tryjob[href="' + event.target.href + '"]'), function(bubble) {
    bubble.classList.remove('highlight');
  });
}

function scrollToHash() {
  if (!location.hash) {
    return;
  }
  var node = currentDocument.querySelector('a[name="' + location.hash.slice(1) + '"]');
  var scrollY = 0;
  while (node) {
    scrollY += node.offsetTop;
    node = node.offsetParent;
  }
  window.scrollTo(0, scrollY);
}

return {
  'main': main,
  'init': init,
  'displayAttempts': displayAttempts,
  'document': currentDocument,
};

})();
