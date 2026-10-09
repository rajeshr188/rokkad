function initPaperEntry() {
  const form = document.querySelector('form[data-paper-entry]');
  if (!form || form.dataset.paperEntryReady) return;
  form.dataset.paperEntryReady = 'true';
  let revision = 0;
  let pending;
  let previousNumber = form.elements.namedItem('number')?.value || '';
  const relevant = name => ['series_id', 'date', 'metal', 'principal', 'exceptions', 'source_license_from_setup'].includes(name)
    || /^collateral-\d+-(description|metal|allocated_principal|interest_rate_override|DELETE)$/.test(name);
  const invalidate = () => {
    revision += 1;
    form.querySelector('#history-review-title')?.closest('section')?.remove();
    form.querySelector('[name=review_token]')?.remove();
  };
  const total = () => {
    const rows = [...form.querySelectorAll('[data-collateral-form]')];
    if (!rows.length) return;
    let cents = 0;
    for (const row of rows) {
      if (row.querySelector('[name$="-DELETE"]')?.checked) continue;
      const raw = row.querySelector('[name$="-allocated_principal"]')?.value || '';
      if (!/^\d+(\.\d{1,2})?$/.test(raw)) continue;
      const [whole, fraction = ''] = raw.split('.');
      cents += Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
    }
    const principal = form.elements.namedItem('principal');
    if (principal) principal.value = (cents / 100).toFixed(2);
  };
  const load = async () => {
    // Reviewed facts must remain untouched until staff choose Edit details.
    if (form.querySelector('#history-review-title')) return;
    if (!form.elements.namedItem('series_id')?.value || !form.elements.namedItem('date')?.value) return;
    const current = revision;
    const data = new FormData(form);
    form.querySelectorAll('input[type=file]').forEach(input => data.delete(input.name));
    data.set('action', 'terms');
    try {
      const response = await fetch(form.getAttribute('action'), {method: 'POST', body: data, credentials: 'same-origin'});
      if (!response.ok || current !== revision) return;
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (current !== revision) return;
      const terms = doc.querySelector('#standing-terms');
      if (!terms) return;
      // Refresh calculations without closing the optional details being edited.
      for (const selector of ['[data-paper-additional-details]', '[data-paper-payout-details]', '[data-paper-term-exceptions]', '[data-paper-license-details]']) {
        const before = form.querySelector(selector), after = terms.querySelector(selector);
        if (before && after) after.open = before.open || after.open;
      }
      form.querySelector('#standing-terms')?.replaceWith(terms);
      const activity = form.querySelector('#paper-activity');
      const updated = doc.querySelector('#paper-activity');
      if (activity && updated) { updated.open = activity.open; activity.replaceWith(updated); }
      for (const input of form.querySelectorAll('[name$="-interest_rate_override"]')) {
        const source = doc.getElementsByName(input.name)[0];
        if (source) input.value = source.value;
      }
      const product = form.elements.namedItem('product_version_id');
      if (product && !product.value) product.value = doc.querySelector('[name=product_version_id]')?.value || '';
      const tenure = form.elements.namedItem('tenure');
      const updatedTenure = doc.querySelector('[name=tenure]');
      if (tenure && updatedTenure) {
        tenure.value = updatedTenure.value;
        tenure.readOnly = updatedTenure.readOnly;
        const help = form.querySelector('#id_tenure_helptext');
        const updatedHelp = doc.querySelector('#id_tenure_helptext');
        if (help && updatedHelp) help.textContent = updatedHelp.textContent;
      }
      for (const name of ['number', 'source_reference', 'paper_number_suggestion']) {
        const field = form.elements.namedItem(name), updated = doc.querySelector(`[name="${name}"]`);
        if (field && updated) field.value = updated.value;
      }
      previousNumber = form.elements.namedItem('number')?.value || '';
      const guidance = form.querySelector('#paper-number-guidance');
      const updatedGuidance = doc.querySelector('#paper-number-guidance');
      if (guidance && updatedGuidance) guidance.replaceWith(updatedGuidance);
      form.dispatchEvent(new Event('loan-terms:loaded'));
    } catch (_) {
      // The ordinary terms submit remains available without JavaScript.
    }
  };
  form.addEventListener('input', event => {
    if (event.target.name === 'confirm_review') return;
    if (event.target.name === 'number') {
      const reference = form.elements.namedItem('source_reference');
      if (reference && reference.value === previousNumber) reference.value = event.target.value;
      previousNumber = event.target.value;
    }
    invalidate();
    if (event.target.name?.endsWith('-allocated_principal')) total();
  });
  form.addEventListener('change', event => {
    if (event.target.name === 'confirm_review') return;
    invalidate();
    if (event.target.name === 'exceptions') {
      const fields = form.querySelector('[data-paper-term-fields]');
      if (fields) fields.hidden = !event.target.checked;
      form.elements.namedItem('tenure').readOnly = !event.target.checked;
      const help = form.querySelector('#id_tenure_helptext');
      if (help && event.target.checked) help.textContent = 'Enter the tenure actually agreed on paper.';
      for (const input of form.querySelectorAll('[name$="-interest_rate_override"]')) input.readOnly = !event.target.checked;
    }
    if (!relevant(event.target.name)) return;
    total();
    clearTimeout(pending);
    pending = setTimeout(load, 150);
  });
  form.addEventListener('click', event => {
    if (event.target.closest('[data-paper-edit-terms]')) {
      event.preventDefault();
      const details = form.querySelector('[data-paper-term-exceptions]');
      if (details) details.open = true;
      const additional = form.querySelector('[data-paper-additional-details]');
      if (additional) additional.open = true;
      const choice = form.elements.namedItem('exceptions');
      choice.checked = true;
      choice.dispatchEvent(new Event('change', {bubbles: true}));
      form.elements.namedItem('tenure').focus();
    }
    if (event.target.closest('[data-paper-edit]')) {
      event.preventDefault();
      invalidate();
      const root = form.closest('[data-new-loan-entry]');
      root?.removeAttribute('data-paper-review');
      root?.querySelector('[data-paper-review-heading]')?.remove();
      for (const node of root?.querySelectorAll('[data-paper-entry-heading], [data-paper-entry-details], #draft-loan-summary') || []) node.hidden = false;
      const details = form.querySelector('#loan-details');
      details?.setAttribute('tabindex', '-1');
      details?.focus();
    }
  });
  form.addEventListener('loan-collateral:changed', () => {
    for (const input of form.querySelectorAll('[name*="-item_principal_"]')) input.value = '';
    invalidate();
    total();
    load();
  });
  if (!form.querySelector('#history-review-title')) { total(); load(); }
  form.querySelector('#history-review-title')?.focus();
}
document.addEventListener("DOMContentLoaded", initPaperEntry);
document.addEventListener("loan-entry:ready", initPaperEntry);
