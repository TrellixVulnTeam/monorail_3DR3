// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Variables for console Javascript access to the currently visible/selected records.
var records = [];
var selectedRecords = [];

var recentModule = (function(){
'use strict';

var indexSelected = {};
var logServer = '//' + window.location.host;
var tags = [];
var cursor;
var table;
var loadMore;
var loading;
// Provide access to imported DOM in tests.
// In production, currentDocument == document.
var currentScript = document._currentScript || document.currentScript;
var currentDocument = currentScript.ownerDocument;

function init() {
  table = currentDocument.querySelector('#table');
  loading = currentDocument.querySelector('#loading');
  loadMore = currentDocument.querySelector('#loadMore');
}

function main() {
  init();
  loadTags();
  loadMore.addEventListener('click', loadNextQuery);
  window.addEventListener('hashchange', loadTags);
}

function loadTags() {
  var hash = window.location.hash.slice(1);
  tags = hash ? hash.split(',') : [];
  cursor = null;
  clearTable();
  loadNextQuery();
  updateFilterList();
  updateRawJSONLink();
}

function clearTable() {
  records = [];
  selectedRecords = [];
  indexSelected = {};
  [].forEach.call(table.querySelectorAll('tr ~ tr'), function(row) {
    row.remove();
  });
}

function processJSON(json)  {
    loading.classList.add('hide');
    cursor = json.more ? json.cursor : null;
    loadMore.disabled = !cursor;
    json.results.forEach(addRow);
}

function loadNextQuery() {
  loading.classList.remove('hide');
  loadMore.disabled = true;
  loadJSON(nextURL(), processJSON);
}

function nextURL() {
  var url = logServer + '/query';
  var params = [];
  if (tags.length > 0) {
    params.push('tags=' + tags.join(','));
  }
  if (cursor) {
    params.push('cursor=' + cursor);
  }
  if (params.length) {
    url += '?' + params.join('&');
  }
  return url;
}

function loadJSON(url, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('get', url, true);
  xhr.responseType = 'json';
  xhr.onload = function() {
    callback(xhr.response);
  };
  xhr.send();
}

function addRow(record) {
  if (!record.codereview_hostname && !!record.issue){
    // Old events pre-Gerrit didn't have it set and assumed public Rietveld.
    record.codereview_hostname = 'codereview.chromium.org';
  }
  var index = records.length;
  records.push(record);
  var row = newElement('tr');
  var items = [
    newElement('span', new Date(record.timestamp * 1000)),
    newFieldValue(record, 'project'),
    newFieldValue(record, 'owner'),
    newFieldValue(record, 'codereview_hostname'),
    newFieldValue(record, 'issue'),
    newFieldValue(record, 'patchset'),
    newFieldValue(record, 'action'),
    newFieldValue(record, 'verifier'),
    newFieldValue(record, 'message'),
    newDetailLinks(record),
  ];
  items.forEach(function(item) {
    var cell = newElement('td');
    cell.appendChild(item);
    row.appendChild(cell);
  });
  row.addEventListener('click', function(event) {
    if (event.target.tagName !== 'A') {
      row.classList.toggle('selected');
      indexSelected[index] = !indexSelected[index];
      updateSelectedRecords();
    }
  });
  table.appendChild(row);
}

function newFieldValue(record, field) {
  var value = record.fields[field];
  var tag = field + '=' + value;
  if (record.tags.indexOf(tag) !== -1 && tags.indexOf(tag) === -1) {
    return newLink(value, '#' + tags.concat([tag]).join(','));
  }
  return newElement('span', value);
}

function newDetailLinks(record) {
  var span = newElement('span');
  span.appendChild(newJsonDialogLink(record));
  var statusLink = newStatusLink(record.fields);
  if (statusLink) {
    span.appendChild(newElement('span', ' '));
    span.appendChild(statusLink);
  }
  var reviewLink = newReviewLink(record.fields);
  if (reviewLink) {
    span.appendChild(newElement('span', ' '));
    span.appendChild(reviewLink);
  }
  return span;
}

function newJsonDialogLink(record) {
  var a = newLink('[json]');
  a.addEventListener('click', function(event) {
    event.preventDefault();
    a.href = '';
    var dialog = newElement('dialog');
    var textarea = newElement('textarea', JSON.stringify(record, null, '  '));
    textarea.selectionStart = textarea.selectionEnd = 0;
    textarea.addEventListener('click', function(event) {
      event.stopPropagation();
    });
    dialog.appendChild(textarea);
    dialog.addEventListener('click', function() {
      dialog.remove();
    });
    currentDocument.body.appendChild(dialog);
    dialog.showModal();
  });
  return a;
}

function newStatusLink(fields) {
  if (!fields.issue || !fields.patchset) {
    return null;
  }
  return newLink('[status]', logServer + '/v2/patch-status/' +
      fields.codereview_hostname + '/' + fields.issue + '/' + fields.patchset);
}

function isGerritHostname(hostname){
  var parts = hostname.split(',')[0].split('-');
  return parts[parts.length - 1] === 'review';
}

function newReviewLink(fields) {
  if (!fields.issue || !fields.codereview_hostname) {
    return null;
  }
  var path_prefix;
  var patchset;
  // Gerrit.
  if (isGerritHostname(fields.codereview_hostname)){
    path_prefix = '/c/';
    patchset = fields.patchset ? '/' + fields.patchset : '';
  } else {
    // Rietveld.
    path_prefix = '/';
    patchset = fields.patchset ? '#ps' + fields.patchset : '';
  }
  return newLink('[review]', '//' + fields.codereview_hostname + path_prefix +
      fields.issue + patchset);
}

function updateFilterList() {
  if (tags.length === 0) {
    filterList.textContent = 'None';
    return;
  }
  filterList.textContent = '';
  tags.forEach(function(tag, i) {
    var otherTags = tags.slice();
    otherTags.splice(i, 1);
    if(i) {
      filterList.appendChild(newElement('span', ', '));
    }
    filterList.appendChild(newLink(tag, '#' + otherTags.join(',')));
  });
  filterList.appendChild(newElement('span', ' '));
  var a = newElement('a', '[clear all]');
  a.href = '';
  filterList.appendChild(a);
}

function updateRawJSONLink() {
  rawJSONLink.href = '/query/' + tags.join('/');
}

function newLink(text, url) {
  var a = newElement('a', text);
  a.href = url ? url : '//';
  return a;
}

function newElement(tag, text) {
  var element = currentDocument.createElement(tag);
  if (text) {
    element.textContent = text;
  }
  return element;
}

function updateSelectedRecords() {
  selectedRecords = [];
  for (var i in indexSelected) {
    if (indexSelected[i]) {
      selectedRecords.push(records[i]);
    }
  }
}

window.addEventListener('load', main);

return {
  'main': main,
  // Export methods for tests.
  'init': init,
  'processJSON': processJSON,
  'document': currentDocument,
};

})();

