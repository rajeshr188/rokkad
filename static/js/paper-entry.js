function initPaperEntry() {
  const form = document.querySelector('form[data-paper-entry]');
  if (!form) return;
  let revision = 0;
  let pending;
  const relevant = name => ['series_id', 'date', 'metal', 'principal', 'exceptions'].includes(name)
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
    if (!form.elements.namedItem('series_id')?.value || !form.elements.namedItem('date')?.value) return;
    if (form.elements.namedItem('exceptions')?.checked) return;
    const current = revision;
    const data = new FormData(form);
    form.querySelectorAll('input[type=file]').forEach(input => data.delete(input.name));
    data.set('action', 'terms');
    try {
      const response = await fetch(form.getAttribute('action'), {method: 'POST', body: data, credentials: 'same-origin'});
      if (!response.ok || current !== revision || form.elements.namedItem('exceptions')?.checked) return;
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const terms = doc.querySelector('#standing-terms');
      if (!terms) return;
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
      if (tenure && updatedTenure) tenure.value = updatedTenure.value;
      form.dispatchEvent(new Event('loan-terms:loaded'));
    } catch (_) {
      // The ordinary terms submit remains available without JavaScript.
    }
  };
  form.addEventListener('input', event => {
    if (event.target.name === 'confirm_review') return;
    invalidate();
    if (event.target.name?.endsWith('-allocated_principal')) total();
  });
  form.addEventListener('change', event => {
    if (event.target.name === 'confirm_review') return;
    invalidate();
    if (event.target.name === 'exceptions') {
      form.elements.namedItem('tenure').readOnly = !event.target.checked;
      for (const input of form.querySelectorAll('[name$="-interest_rate_override"]')) input.readOnly = !event.target.checked;
    }
    if (!relevant(event.target.name)) return;
    total();
    clearTimeout(pending);
    pending = setTimeout(load, 150);
  });
  form.addEventListener('loan-collateral:changed', () => {
    for (const input of form.querySelectorAll('[name*="-item_principal_"]')) input.value = '';
    invalidate();
    total();
    load();
  });
  total();
  load();
}
document.addEventListener("DOMContentLoaded", initPaperEntry);
document.addEventListener("loan-entry:ready", initPaperEntry);
