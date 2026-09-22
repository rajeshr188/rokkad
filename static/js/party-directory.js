/* Progressive enhancement: ordinary GET forms and links remain the fallback. */
(() => {
  if (window.rokkadPartyDirectoryReady) return;
  window.rokkadPartyDirectoryReady = true;
  let focusResults = false;
  const isDirectory = event => event.detail.target?.id === 'party-results';
  const finish = () => document.getElementById('party-results')?.removeAttribute('aria-busy');
  document.addEventListener('htmx:beforeRequest', event => {
    if (!isDirectory(event)) return;
    document.getElementById('party-search-error').hidden = true;
    focusResults = event.detail.elt?.hasAttribute('data-results-page');
    event.detail.target.setAttribute('aria-busy', 'true');
  });
  document.addEventListener('htmx:beforeSwap', event => {
    if (!isDirectory(event)) return;
    const xhr = event.detail.xhr;
    if (xhr.status >= 200 && xhr.status < 300 && xhr.getResponseHeader('X-Rokkad-Fragment') !== 'party-results') {
      event.detail.shouldSwap = false;
      const destination = new URL(xhr.responseURL, window.location.href);
      if (destination.origin === window.location.origin) window.location.assign(destination.href);
    }
  });
  document.addEventListener('htmx:afterSwap', event => {
    if (!isDirectory(event)) return;
    finish();
    const heading = document.getElementById('party-results-title');
    document.getElementById('party-search-announcement').textContent = heading?.textContent || '';
    const languageNext = document.getElementById('navbar-language')?.closest('form')?.querySelector('[name=next]');
    if (languageNext) languageNext.value = window.location.pathname + window.location.search;
    if (focusResults) heading?.focus();
  });
  document.addEventListener('htmx:afterRequest', event => {
    if (!isDirectory(event)) return;
    finish();
    if (event.detail.failed) document.getElementById('party-search-error').hidden = false;
  });
})();
