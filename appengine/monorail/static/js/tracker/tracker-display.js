/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * Functions used by Monorail to control the display of elements on
 * the page, rollovers, and popup menus.
 *
 */


/**
 * Show a popup menu below a specified element. Optional x and y deltas can be
 * used to fine-tune placement.
 * @param {string} id The HTML id of the popup menu.
 * @param {Element} el The HTML element that the popup should appear near.
 * @param {number} opt_deltaX Optional X offset to finetune placement.
 * @param {number} opt_deltaY Optional Y offset to finetune placement.
 * @param {Element} opt_menuButton The HTML element for a menu button that
 *    was pressed to open the menu.  When a button was used, we need to ignore
 *    the first "click" event, otherwise the menu will immediately close.
 * @return Always returns false to indicate that the browser should handle the
 * event normally.
 */
function TKR_showBelow(id, el, opt_deltaX, opt_deltaY, opt_menuButton) {
  let popupDiv = $(id);
  let elBounds = nodeBounds(el);
  let startX = elBounds.x;
  let startY = elBounds.y + elBounds.h;
  if (BR_IsIE()) {
    startX -= 1;
    startY -= 2;
  }
  if (BR_IsSafari()) {
    startX += 1;
  }
  popupDiv.style.display = 'block'; // needed so that offsetWidth != 0

  popupDiv.style.left = '-2000px';
  if (id == 'pop_dot' || id == 'redoMenu') {
    startX = startX - popupDiv.offsetWidth + el.offsetWidth;
  }
  if (opt_deltaX) startX += opt_deltaX;
  if (opt_deltaY) startY += opt_deltaY;
  popupDiv.style.left = (startX)+'px';
  popupDiv.style.top = (startY)+'px';
  let popup = new TKR_MyPopup(popupDiv, opt_menuButton);
  popup.show();
  return false;
}


/**
 * Show a popup menu to the right of a specified element. If there is not
 * enough space to the right, then it will open to the left side instead.
 * Optional x and y deltas can be used to fine-tune placement.
 * TODO(jrobbins): reduce redundancy with function above.
 * @param {string} id The HTML id of the popup menu.
 * @param {Element} el The HTML element that the popup should appear near.
 * @param {number} opt_deltaX Optional X offset to finetune placement.
 * @param {number} opt_deltaY Optional Y offset to finetune placement.
 * @return Always returns false to indicate that the browser should handle the
 * event normally.
 */
function TKR_showRight(id, el, opt_deltaX, opt_deltaY) {
  let popupDiv = $(id);
  let elBounds = nodeBounds(el);
  let startX = elBounds.x + elBounds.w;
  let startY = elBounds.y;

  // Calculate pageSize.w and pageSize.h
  let docElemWidth = document.documentElement.clientWidth;
  let docElemHeight = document.documentElement.clientHeight;
  let pageSize = {
    w: (window.innerWidth || docElemWidth && docElemWidth > 0 ?
      docElemWidth : document.body.clientWidth) || 1,
    h: (window.innerHeight || docElemHeight && docElemHeight > 0 ?
      docElemHeight : document.body.clientHeight) || 1,
  };

  // We need to make the popupDiv visible in order to capture its width
  popupDiv.style.display = 'block';
  let popupDivBounds = nodeBounds(popupDiv);

  // Show popup to the left
  if (startX + popupDivBounds.w > pageSize.w) {
    startX = elBounds.x - popupDivBounds.w;
    if (BR_IsIE()) {
      startX -= 4;
      startY -= 2;
    }
    if (BR_IsNav()) {
      startX -= 2;
    }
    if (BR_IsSafari()) {
      startX += -1;
    }

  // Show popup to the right
  } else {
    if (BR_IsIE()) {
      startY -= 2;
    }
    if (BR_IsNav()) {
      startX += 2;
    }
    if (BR_IsSafari()) {
      startX += 3;
    }
  }

  popupDiv.style.left = '-2000px';
  popupDiv.style.position = 'absolute';
  if (opt_deltaX) startX += opt_deltaX;
  if (opt_deltaY) startY += opt_deltaY;
  popupDiv.style.left = (startX)+'px';
  popupDiv.style.top = (startY)+'px';
  let popup = new TKR_MyPopup(popupDiv);
  popup.show();
  return false;
}


/**
 * Close the specified popup menu and unregister it with the popup
 * controller, otherwise old leftover popup instances can mess with
 * the future display of menus.
 * @param {string} id The HTML ID of the element to hide.
 */
function TKR_closePopup(id) {
  let e = $(id);
  if (e) {
    for (let i = 0; i < gPopupController.activePopups_.length; ++i) {
      if (e === gPopupController.activePopups_[i]._div) {
        let popup = gPopupController.activePopups_[i];
        popup.hide();
        gPopupController.activePopups_.splice(i, 1);
        return;
      }
    }
  }
}


var TKR_allColumnNames = []; // Will be defined in HTML file.

/**
 * Close all popup menus.  Also, reset the hover state of the menu item that
 * was selected. The list of popup menu names is computed from the list of
 * columns specified in the HTML for the issue list page.
 * @param menuItem {Element} The menu item that the user clicked.
 * @return Always returns false to indicate that the browser should handle the
 * event normally.
 */
function TKR_closeAllPopups(menuItem) {
  for (let col_index = 0; col_index < TKR_allColumnNames.length; col_index++) {
    TKR_closePopup('pop_' + col_index);
    TKR_closePopup('filter_' + col_index);
  }
  TKR_closePopup('pop_dot');
  TKR_closePopup('redoMenu');
  menuItem.classList.remove('hover');
  return false;
}


/**
 * Close all the submenus (of which, one may be currently open).
 * @return Always returns false to indicate that the browser should handle the
 * event normally.
 */
function TKR_closeSubmenus() {
  for (let col_index = 0; col_index < TKR_allColumnNames.length; col_index++) {
    TKR_closePopup('filter_' + col_index);
  }
  return false;
}


/**
 * Find the enclosing HTML element that controls this section of the
 * page and set it to use CSS class "opened".  That will make the
 * section display in the opened state, regardless of what state is
 * was in before.
 * @param {Element} el The HTML element that the user clicked on.
 * @return Always returns false to indicate that the browser should handle the
 * event normally.
 */
function TKR_showHidden(el) {
  while (el) {
    if (el.classList.contains('closed')) {
      el.classList.remove('closed');
      el.classList.add('opened');
      return false;
    }
    if (el.classList.contains('opened')) {
      return false;
    }
    el = el.parentNode;
  }
}


/**
 * Toggle the display of a column in the issue list page.  That is
 * done by adding or removing a CSS class of an enclosing HTML
 * element, and by CSS rules that trigger based on that CSS class.
 * @param {string} colName The name of the column to toggle,
 * corresponds to a CSS class.
 * @return Always returns false to indicate that the browser should
 * handle the event normally.
 */
function TKR_toggleColumn(colName) {
  let controlDiv = $('colcontrol');
  if (controlDiv.classList.contains(colName)) {
    controlDiv.classList.remove(colName);
  } else {
    controlDiv.classList.add(colName);
  }
  return false;
}


/**
 * Toggle the display of a set of rows in the issue list page.  That is
 * done by adding or removing a CSS class of an enclosing HTML
 * element, and by CSS rules that trigger based on that CSS class.
 * TODO(jrobbins): actually, this automatically hides the other groups.
 * @param {string} rowClassName The name of the row group to toggle,
 * corresponds to a CSS class.
 * @return Always returns false to indicate that the browser should
 * handle the event normally.
 */
function TKR_toggleRows(rowClassName) {
  let controlDiv = $('colcontrol');
  controlDiv.classList.add('hide_pri_groups');
  controlDiv.classList.add('hide_mile_groups');
  controlDiv.classList.add('hide_stat_groups');
  TKR_toggleColumn(rowClassName);
  return false;
}


/**
 * A simple class that can manage the display of a popup menu.  Instances
 * of this class are used by popup_controller.js.
 * @param {Element} div The div that contains the popup menu.
 * @param {Element} opt_launcherEl The button that launched the popup menu,
 *     if any.
 * @constructor
 */
function TKR_MyPopup(div, opt_launcherEl) {
  this._div = div;
  this._launcher = opt_launcherEl;
  this._isVisible = false;
}


/**
 * Show a popup menu.  This method registers the popup with popup_controller.
 */
TKR_MyPopup.prototype.show = function() {
  this._div.style.display = 'block';
  this._isVisible = true;
  PC_addPopup(this);
};


/**
 * Show a popup menu.  This method is called from the deactive method,
 * which is called by popup_controller.
 */
TKR_MyPopup.prototype.hide = function() {
  this._div.style.display = 'none';
  this._isVisible = false;
};


/**
 * When the popup_controller gets a user click, it calls deactive() on
 * every active popup to check if the click should close that popup.
 */
TKR_MyPopup.prototype.deactivate = function(e) {
  if (this._isVisible) {
    let p = GetMousePosition(e);
    if (nodeBounds(this._div).contains(p)) {
      return false; // use clicked on popup, remain visible
    } else if (this._launcher && nodeBounds(this._launcher).contains(p)) {
      this._launcher = null;
      return false; // mouseup element that launched menu, remain visible
    } else {
      this.hide();
      return true; // clicked outside popup, make invisible
    }
  } else {
    return true; // already deactivated, not visible
  }
};


/**
 * Highlight the issue row on the list page that contains the given
 * checkbox.
 * @param {Element} cb The checkbox that the user changed.
 * @return Always returns false to indicate that the browser should
 * handle the event normally.
 */
function TKR_highlightRow(el) {
  let checked = el.checked;
  while (el && el.tagName != 'TR') {
    el = el.parentNode;
  }
  if (checked) {
    el.classList.add('selected');
  } else {
    el.classList.remove('selected');
  }
  return false;
}
