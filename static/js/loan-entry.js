/* Entry changes update the form only. Financial actions remain server-validated. */
(() => {
  let revision = 0, requestId = 0, controller;
  const photos = new Map();
  const root = () => document.querySelector('[data-new-loan-entry]');
  const form = () => root()?.querySelector('#new-loan-form');
  const status = text => { const node = root()?.querySelector('[data-entry-status]'); if (node) node.textContent = text; };
  async function change() {
    const current = form();
    if (!current) return;
    const ticket = ++requestId, version = revision;
    controller?.abort(); controller = new AbortController();
    const data = new FormData(current); data.set('action', 'entry_change');
    current.querySelectorAll('input[type=file]').forEach(input => {
      photos.set(input.name, input);
      data.delete(input.name); // Keep the actual File input locally until an ordinary save.
    });
    current.dataset.entryChanging = 'true';
    status('Updating entry purpose; your entered facts are retained.');
    try {
      const response = await fetch(current.getAttribute('action'), {method: 'POST', body: data,
        credentials: 'same-origin', signal: controller.signal});
      if (ticket !== requestId || current !== form()) return;
      if (version !== revision) { change(); return; }
      if (!response.ok) throw new Error('unavailable');
      const html = await response.text();
      if (ticket !== requestId || current !== form()) return;
      if (version !== revision) { change(); return; }
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const replacement = doc.querySelector('[data-new-loan-entry]');
      if (!replacement) throw new Error('unavailable');
      replacement.querySelectorAll('script').forEach(script => script.remove());
      root().replaceWith(replacement);
      replacement.querySelectorAll('input[type=file]').forEach(input => {
        const retained = photos.get(input.name);
        if (retained?.files.length) input.replaceWith(retained);
      });
      replacement.querySelector('[data-entry-file-warning]')?.remove();
      if (window.jQuery?.fn.djangoSelect2) window.jQuery(replacement).find('select.django-select2').djangoSelect2();
      window.htmx?.process(replacement);
      document.dispatchEvent(new Event('loan-entry:ready'));
      status(replacement.querySelector('[data-entry-status]')?.textContent || '');
    } catch (error) {
      if (ticket !== requestId || error.name === 'AbortError') return;
      delete current.dataset.entryChanging;
      const selection = root()?.querySelector('[name=entry_selection]');
      if (selection) selection.value = current.elements.namedItem('entry_mode').value;
      status('Entry could not be changed. Your form and photographs are retained; try again.');
    }
  }
  document.addEventListener('input', event => { if (root()?.contains(event.target)) revision += 1; });
  document.addEventListener('click', event => {
    if (root()?.contains(event.target) && event.target.closest('[data-apply-entry]')) change();
  });
  document.addEventListener('change', event => {
    if (!root()?.contains(event.target)) return;
    revision += 1;
    if (event.target.name === 'entry_selection' || ['series', 'series_id'].includes(event.target.name)) change();
  });
  document.addEventListener('submit', event => {
    if (event.target !== form()) return;
    if (event.submitter?.value === 'entry_change') {
      event.preventDefault(); event.stopImmediatePropagation(); change();
    } else if (event.target.dataset.entryChanging === 'true') {
      event.preventDefault(); event.stopImmediatePropagation(); status('Wait for the entry purpose to finish updating.');
    }
  }, true);
  function enhancedSeries() {
    const select = root()?.querySelector('[name=series], [name=series_id]');
    if (select && window.jQuery) window.jQuery(select).on('select2:select select2:clear', () => { revision += 1; change(); });
  }
  document.addEventListener('DOMContentLoaded', enhancedSeries);
  document.addEventListener('loan-entry:ready', enhancedSeries);
})();
