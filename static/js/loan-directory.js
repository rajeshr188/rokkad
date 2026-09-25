/* Ordinary GET forms and links work without this enhancement. */
(() => {
  if (window.rokkadLoanDirectoryReady) return;
  window.rokkadLoanDirectoryReady = true;
  // Select2 emits jQuery change events; submit through the existing GET/HTMX form.
  if (window.jQuery) window.jQuery(document).on('change', '#id_borrower', function () {
    const form = document.getElementById('loan-search-form');
    if (!form) return;
    const legacySearch = form.querySelector('[name="borrower_q"]');
    if (legacySearch) legacySearch.value = '';
    form.requestSubmit();
  });
  let focusResults = false;
  const isDirectory = event => event.detail.target?.id === 'loan-results';
  const finish = () => document.getElementById('loan-results')?.removeAttribute('aria-busy');
  document.addEventListener('htmx:beforeRequest', event => {
    if (!isDirectory(event)) return;
    document.getElementById('loan-search-error').hidden = true;
    focusResults = event.detail.elt?.hasAttribute('data-results-page') || event.detail.triggeringEvent?.type === 'submit';
    event.detail.target.setAttribute('aria-busy', 'true');
  });
  document.addEventListener('htmx:beforeSwap', event => {
    if (!isDirectory(event)) return;
    const xhr = event.detail.xhr;
    if (xhr.status >= 200 && xhr.status < 300 && xhr.getResponseHeader('X-Rokkad-Fragment') !== 'loan-results') {
      event.detail.shouldSwap = false;
      const destination = new URL(xhr.responseURL, window.location.href);
      if (destination.origin === window.location.origin) window.location.assign(destination.href);
    }
  });
  document.addEventListener('htmx:afterSwap', event => {
    if (!isDirectory(event)) return;
    finish();
    const heading = document.getElementById('loan-results-title');
    document.getElementById('loan-search-announcement').textContent = heading?.textContent || '';
    const languageNext = document.getElementById('navbar-language')?.closest('form')?.querySelector('[name=next]');
    if (languageNext) languageNext.value = window.location.pathname + window.location.search;
    if (focusResults) heading?.focus();
  });
  document.addEventListener('htmx:afterRequest', event => {
    if (!isDirectory(event)) return;
    finish();
    if (event.detail.failed) document.getElementById('loan-search-error').hidden = false;
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('[data-filter-error]');
    if (!link) return;
    const field = document.getElementById(link.hash.slice(1));
    if (!field) return;
    event.preventDefault();
    const disclosure = field?.closest('details');
    if (disclosure) disclosure.open = true;
    field?.focus();
  });
})();
