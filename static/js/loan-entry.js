/* Entry changes update the form only. Financial actions remain server-validated. */
(() => {
  let revision = 0, requestId = 0, controller;
  const photos = new Map();
  const root = () => document.querySelector('[data-new-loan-entry]');
  const form = () => root()?.querySelector('#new-loan-form');
  const status = text => { const node = root()?.querySelector('[data-paper-review-status]') || root()?.querySelector('[data-entry-status]'); if (node) node.textContent = text; };
  function replaceEditor(replacement) {
    // DOMParser parses noscript markup as elements; those fallback controls must
    // not duplicate the live file inputs in this JavaScript-enhanced editor.
    replacement.querySelectorAll('script, noscript').forEach(script => script.remove());
    root().replaceWith(replacement);
    replacement.querySelectorAll('input[type=file]').forEach(input => {
      const retained = photos.get(input.name);
      if (retained?.files.length) input.replaceWith(retained);
    });
    replacement.querySelector('[data-entry-file-warning]')?.remove();
    replacement.querySelector('[data-entry-photo-reselect]')?.remove();
    if (window.jQuery?.fn.djangoSelect2) window.jQuery(replacement).find('select.django-select2').djangoSelect2();
    window.htmx?.process(replacement);
    document.dispatchEvent(new Event('loan-entry:ready'));
  }
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
    status('Updating loan entry; your entered facts are retained.');
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
      replaceEditor(replacement);
      status(replacement.querySelector('[data-entry-status]')?.textContent || '');
    } catch (error) {
      if (ticket !== requestId || error.name === 'AbortError') return;
      delete current.dataset.entryChanging;
      const selection = root()?.querySelector('[name=entry_selection]');
      if (selection) selection.value = current.elements.namedItem('entry_mode').value;
      status('Entry could not be changed. Your form and photographs are retained; try again.');
    }
  }
  async function reviewPaper(button) {
    const current = form(), version = revision, ticket = ++requestId;
    controller?.abort(); controller = new AbortController();
    const data = new FormData(current); data.set('action', 'preview');
    current.querySelectorAll('input[type=file]').forEach(input => photos.set(input.name, input));
    current.dataset.paperReviewPending = 'true';
    current.setAttribute('aria-busy', 'true');
    if (button) button.disabled = true;
    status('Preparing loan review. Your entered details and photographs are retained.');
    try {
      const response = await fetch(current.getAttribute('action'), {method: 'POST', body: data,
        credentials: 'same-origin', signal: controller.signal});
      if (ticket !== requestId || current !== form()) return;
      if (version !== revision) { status('Details changed while preparing the review. Review the updated loan again.'); return; }
      if (!response.ok) throw new Error('unavailable');
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (ticket !== requestId || current !== form()) return;
      if (version !== revision) { status('Details changed while preparing the review. Review the updated loan again.'); return; }
      const replacement = doc.querySelector('[data-routine-loan-editor]');
      if (!replacement) throw new Error('unavailable');
      replaceEditor(replacement);
      const target = replacement.querySelector('[data-form-errors], #history-review-title');
      target?.focus();
      target?.scrollIntoView({block: 'start'});
    } catch (error) {
      if (ticket !== requestId || error.name === 'AbortError') return;
      status('Review could not be loaded. Your form and photographs are retained; try again.');
    } finally {
      delete current.dataset.paperReviewPending;
      current.removeAttribute('aria-busy');
      if (button) button.disabled = false;
    }
  }
  document.addEventListener('input', event => { if (root()?.contains(event.target)) revision += 1; });
  document.addEventListener('click', event => {
    if (root()?.contains(event.target) && event.target.closest('[data-apply-entry]')) change();
  });
  document.addEventListener('change', event => {
    if (!root()?.contains(event.target)) return;
    revision += 1;
    if (['entry_selection', 'series', 'series_id', 'include_old_series'].includes(event.target.name)) change();
  });
  document.addEventListener('submit', event => {
    if (event.target !== form()) return;
    if (event.submitter?.value === 'entry_change') {
      event.preventDefault(); event.stopImmediatePropagation(); change();
    } else if (event.target.dataset.entryChanging === 'true') {
      event.preventDefault(); event.stopImmediatePropagation(); status('Wait for loan entry to finish updating.');
    } else if (event.target.dataset.paperReviewPending === 'true') {
      event.preventDefault(); event.stopImmediatePropagation(); status('Wait for the loan review to finish loading.');
    } else if (event.target.matches('[data-paper-entry]') && root()?.matches('[data-routine-loan-editor]') && event.submitter?.value === 'preview') {
      event.preventDefault(); event.stopImmediatePropagation(); reviewPaper(event.submitter);
    }
  }, true);
  function enhancedSeries() {
    const select = root()?.querySelector('[name=series], [name=series_id]');
    if (select && window.jQuery) window.jQuery(select).on('select2:select select2:clear', () => { revision += 1; change(); });
  }
  document.addEventListener('DOMContentLoaded', enhancedSeries);
  document.addEventListener('loan-entry:ready', enhancedSeries);
})();
