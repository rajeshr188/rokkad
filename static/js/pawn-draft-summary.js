/* Display entered facts only. Economic calculations and validation remain server-owned. */
document.addEventListener('DOMContentLoaded', () => {
  const summary = document.getElementById('draft-loan-summary');
  const container = document.getElementById('collateral-formset');
  if (!summary || !container) return;
  const form = container.closest('form');
  const value = name => form.elements.namedItem(name)?.value || '';
  const label = name => {
    const select = form.elements.namedItem(name);
    return select?.value ? select.selectedOptions[0]?.textContent.trim() : '';
  };
  const set = (key, text) => { summary.querySelector(`[data-summary-${key}]`).textContent = text; };
  function update() {
    set('borrower', label('borrower') || 'Choose a borrower');
    set('series', label('series') || 'Choose a series');
    set('product', label('product_version') || 'Choose a product');
    set('tenure', value('tenure_months') ? `${value('tenure_months')} months` : '—');
    const list = summary.querySelector('[data-summary-items]');
    list.replaceChildren();
    let principal = 0, complete = true, count = 0;
    container.querySelectorAll('[data-collateral-form]').forEach(row => {
      if (row.querySelector('[name$="-DELETE"]')?.checked) return;
      count++;
      const field = key => row.querySelector(`[name$="-${key}"]`);
      const entered = key => field(key)?.value || '—';
      const allocation = Number(field('allocated_principal')?.value);
      if (!field('allocated_principal')?.value || !Number.isFinite(allocation) || allocation < 0) complete = false;
      else principal += allocation;
      const item = document.createElement('li');
      const title = document.createElement('strong');
      title.textContent = entered('description') === '—' ? `Item ${count}` : entered('description');
      item.append(title);
      const photo = field('photograph');
      const lines = [
        `${entered('metal')} · Purity ${entered('purity_percentage')}%`,
        `Gross ${entered('gross_weight')} g · Net ${entered('net_weight')} g`,
        `Allocated principal ${entered('allocated_principal')}`,
        photo?.files.length ? 'Photo selected' : row.querySelector('img') ? 'Saved photo attached' : 'Photo needed',
      ];
      lines.forEach(text => { const line = document.createElement('small'); line.textContent = text; item.append(line); });
      list.append(item);
    });
    set('count', `${count} collateral item${count === 1 ? '' : 's'}`);
    set('principal', complete && count ? principal.toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2}) : '—');
  }
  function changed() {
    update();
    const preview = summary.querySelector('[data-validated-summary]');
    if (preview) preview.hidden = true;
    const oldPreview = document.querySelector('[data-economic-preview]');
    if (oldPreview) {
      oldPreview.hidden = true;
      document.getElementById('economic-preview-stale').hidden = false;
    }
  }
  form.addEventListener('input', changed);
  form.addEventListener('change', changed);
  form.addEventListener('click', event => { if (event.target.closest('[data-remove-collateral]')) changed(); });
  new MutationObserver(changed).observe(container, {childList:true});
  if (window.jQuery) jQuery(form).on('change', 'select', changed);
  update();
});
