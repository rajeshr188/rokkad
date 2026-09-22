/* Ordinary GET forms and links work without this enhancement. */
(() => {
  if (window.rokkadReferenceDirectoryReady) return;
  window.rokkadReferenceDirectoryReady = true;
  let focusResults = false;
  const isDirectory = event => event.detail.target?.id === 'reference-results';
  const finish = () => document.getElementById('reference-results')?.removeAttribute('aria-busy');
  document.addEventListener('htmx:beforeRequest', event => {
    if (!isDirectory(event)) return;
    document.getElementById('reference-search-error').hidden = true;
    focusResults = event.detail.elt?.hasAttribute('data-results-page') || event.detail.elt?.id === 'reference-search-form';
    event.detail.target.setAttribute('aria-busy', 'true');
  });
  document.addEventListener('htmx:beforeSwap', event => {
    if (!isDirectory(event)) return;
    const xhr = event.detail.xhr;
    if (xhr.status >= 200 && xhr.status < 300 && xhr.getResponseHeader('X-Rokkad-Fragment') !== 'reference-results') {
      event.detail.shouldSwap = false;
      const destination = new URL(xhr.responseURL, window.location.href);
      if (destination.origin === window.location.origin) window.location.assign(destination.href);
    }
  });
  document.addEventListener('htmx:afterSwap', event => {
    if (!isDirectory(event)) return;
    finish();
    const heading = document.getElementById('reference-results-title');
    document.getElementById('reference-search-announcement').textContent = heading?.textContent || '';
    const languageNext = document.getElementById('navbar-language')?.closest('form')?.querySelector('[name=next]');
    if (languageNext) languageNext.value = window.location.pathname + window.location.search;
    if (focusResults) (document.querySelector('#reference-results [data-form-errors]') || heading)?.focus();
  });
  document.addEventListener('htmx:afterRequest', event => {
    if (!isDirectory(event)) return;
    finish();
    if (event.detail.failed) document.getElementById('reference-search-error').hidden = false;
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('#reference-results [data-form-errors] a');
    if (!link) return;
    const field = document.getElementById(link.hash.slice(1));
    if (!field) return;
    event.preventDefault();
    const disclosure = field?.closest('details');
    if (disclosure) disclosure.open = true;
    field?.focus();
  });
})();
