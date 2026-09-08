/* Keep unsubmitted form edits from being lost during Workspace switching. */
(() => {
  let dirty = false;
  function markDirty(event) {
    if (event.target.closest('main form') && !event.target.closest('[data-workspace-switch]')) dirty = true;
  }
  document.addEventListener('input', markDirty);
  document.addEventListener('change', markDirty);
  document.addEventListener('submit', event => {
    if (event.target.matches('[data-workspace-switch]') && dirty) {
      if (!window.confirm('You have unsaved changes. Switch Workspace and discard them?')) {
        event.preventDefault();
        return;
      }
    }
    dirty = false;
  });
  window.addEventListener('beforeunload', event => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = '';
  });
})();
