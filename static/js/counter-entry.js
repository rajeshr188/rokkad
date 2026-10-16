/* Unsaved facts stay in this document; nothing is persisted in browser storage. */
(() => {
  if (window.rokkadCounterEntryReady) return;
  window.rokkadCounterEntryReady = true;
  let dirty = Boolean(document.querySelector('#new-loan-form[data-unsaved-entry]'));
  let activeForm = document.querySelector('#new-loan-form');
  let submitting = false;
  let leavingByHtmx = false;
  const edited = event => {
    if (event.target.closest?.('#new-loan-form')) dirty = true;
  };
  document.addEventListener('input', edited);
  document.addEventListener('change', edited);
  document.addEventListener('submit', event => {
    if (event.target.id === 'new-loan-form' && !event.defaultPrevented) submitting = true;
  });
  window.addEventListener('beforeunload', event => {
    if (!dirty || submitting) return;
    event.preventDefault();
    event.returnValue = '';
  });
  window.addEventListener('pageshow', () => { submitting = false; });
  document.addEventListener('htmx:beforeRequest', event => {
    if (!dirty || submitting || !event.detail.requestConfig?.boosted) return;
    if (!window.confirm('Leave this loan entry? Unsaved changes will be lost.')) event.preventDefault();
    else { leavingByHtmx = true; dirty = false; }
  });
  document.addEventListener('htmx:afterRequest', event => {
    if (!event.detail.requestConfig?.boosted) return;
    if (leavingByHtmx && event.detail.failed) dirty = true;
    leavingByHtmx = false;
  });
  document.addEventListener('htmx:afterSwap', () => {
    const current = document.querySelector('#new-loan-form');
    if (current !== activeForm) {
      activeForm = current;
      dirty = Boolean(current?.hasAttribute('data-unsaved-entry'));
      submitting = false;
    }
  });
})();
