/**
 * Sets up the transfer ownership dialog box.
 * @param {Long} hotlist_id id of the current hotlist
*/
function initializeDialogBox(hotlist_id) {
  let transferContainer = $('transfer-ownership-container');
  $('transfer-ownership').addEventListener('click', function() {
    transferContainer.style.display = 'block';
  });

  let cancelButton = document.getElementById('cancel');

  cancelButton.addEventListener('click', function() {
    transferContainer.style.display = 'none';
  });

  $('hotlist_star').addEventListener('click', function() {
    _TKR_toggleStar($('hotlist_star'), null, null, null, hotlist_id);
  });
}

function initializeDialogBoxRemoveSelf() {
  /* Initialise the dialog box for removing self from the hotlist. */

  let removeSelfContainer = $('remove-self-container');
  $('remove-self').addEventListener('click', function() {
    removeSelfContainer.style.display = 'block';
  });

  let cancelButtonRS = document.getElementById('cancel-remove-self');

  cancelButtonRS.addEventListener('click', function() {
    removeSelfContainer.style.display = 'none';
  });
}
