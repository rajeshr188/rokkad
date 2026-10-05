/* Price preflight leaves the form and File inputs in place when setup is missing. */
function initPawnRateReadiness() {
  const form = document.querySelector('[data-valuation-preflight]');
  if (!form || !window.htmx) return;
  const panel = form.querySelector('[data-rate-readiness-panel]');
  const content = panel.querySelector('[data-rate-readiness-content]');
  const summary = panel.querySelector('[data-rate-readiness-summary]');
  const details = panel.querySelector('#rate-readiness-details');
  function showStatus(text, attention = false) {
    summary.textContent = text;
    panel.classList.toggle('border-warning', attention);
    summary.classList.toggle('text-danger', attention);
    if (attention) {
      if (window.bootstrap?.Collapse) window.bootstrap.Collapse.getOrCreateInstance(details, {toggle: false}).show();
      else {
        details.classList.add('show');
        panel.querySelector('[aria-controls="rate-readiness-details"]').setAttribute('aria-expanded', 'true');
      }
    }
  }
  const rows = form.querySelector('#collateral-formset');
  const series = form.querySelector('[name="series"]');
  const date = form.querySelector('[name="loan_date"]');
  let key = 0;
  let submitting = false;
  let allowSubmit = false;
  content.setAttribute('hx-params', 'series,as_of,metals,request_key');

  function values() {
    const metals = new Set();
    rows.querySelectorAll('[data-collateral-form]').forEach(row => {
      if (!row.hidden && !row.querySelector('[name$="-DELETE"]')?.checked) {
        const metal = row.querySelector('[name$="-metal"]')?.value;
        if (metal) metals.add(metal);
      }
    });
    return {series: series.value, as_of: date.value, metals: [...metals].sort().join(',')};
  }

  content.addEventListener('htmx:beforeSwap', event => {
    const document = new DOMParser().parseFromString(event.detail.xhr.responseText, 'text/html');
    const result = document.querySelector('[data-rate-readiness-result]');
    if (!result || result.dataset.requestKey !== String(key)) event.detail.shouldSwap = false;
  });

  async function check() {
    const data = values();
    const requestKey = ++key;
    htmx.trigger(content, 'htmx:abort');
    rows.querySelectorAll('[data-item-policy-rate]').forEach(hint => {
      hint.textContent = 'Policy default: checking selected series and date…';
    });
    rows.querySelectorAll('[name$="-interest_rate_override"]').forEach(input => { input.placeholder = 'Use policy'; });
    if (!data.series || !data.as_of || !data.metals) {
      content.textContent = 'Select a series, loan date and at least one collateral metal to check prices.';
      showStatus('Select a series, loan date and collateral metal');
      return false;
    }
    content.textContent = 'Checking metal prices…';
    showStatus('Checking…');
    try {
      await htmx.ajax('GET', form.dataset.valuationPreflight, {
        source: content, target: content, swap: 'innerHTML',
        values: {...data, request_key: requestKey},
      });
      const result = content.querySelector('[data-rate-readiness-result]');
      if (requestKey === key) {
        if (result?.dataset.requestKey === String(requestKey)) {
          const label = result.querySelector('[data-rate-summary]')?.textContent.trim();
          showStatus(label || 'Price check unavailable', !label || result.dataset.attention === 'true');
        }
        rows.querySelectorAll('[data-collateral-form]').forEach(row => {
          const metal = row.querySelector('[name$="-metal"]')?.value;
          const input = row.querySelector('[name$="-interest_rate_override"]');
          if (!input) return;
          const rate = result?.querySelector(`[data-policy-interest-metal="${metal}"]`)?.dataset.policyInterestRate;
          let hint = row.querySelector('[data-item-policy-rate]');
          if (!hint) {
            hint = document.createElement('div'); hint.className = 'form-text fw-semibold';
            hint.dataset.itemPolicyRate = ''; hint.setAttribute('aria-live', 'polite'); input.after(hint);
          }
          const display = rate ? Number(rate).toString() + '% / month' : 'unavailable — check setup';
          hint.textContent = 'Policy default: ' + display;
          input.placeholder = rate ? 'Policy: ' + display : 'Use policy';
        });
      }
      if (!result && requestKey === key) {
        content.textContent = 'Price check unavailable. Your form and photos are retained. Check your access or connection and try again.';
        showStatus('Price check unavailable — please retry', true);
      }
      return requestKey === key && JSON.stringify(data) === JSON.stringify(values()) &&
        result?.dataset.requestKey === String(requestKey) && result.dataset.ready === 'true';
    } catch (error) {
      if (requestKey === key) {
        content.textContent = 'Price check unavailable. Your form and photos are retained. Check your connection and try again.';
        showStatus('Price check unavailable — please retry', true);
      }
      return false;
    }
  }

  panel.querySelector('[data-check-rates]').addEventListener('click', () => {
    date.dispatchEvent(new Event('change', {bubbles: true}));
  });
  form.addEventListener('change', event => {
    if (event.target === series || event.target === date || /-(metal|DELETE)$/.test(event.target.name)) check();
  });
  if (window.jQuery) window.jQuery(series).on('select2:select select2:clear', () => check());
  rows.addEventListener('click', event => {
    if (event.target.closest('[data-remove-collateral]')) check();
  });
  new MutationObserver(() => check()).observe(rows, {childList: true});
  form.addEventListener('submit', async event => {
    if (form.dataset.draftSubmitting === 'true') { event.preventDefault(); return; }
    if (allowSubmit) { allowSubmit = false; return; }
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    const ready = await check();
    submitting = false;
    if (ready) {
      allowSubmit = true;
      form.requestSubmit(event.submitter || undefined);
    } else {
      panel.focus();
      panel.scrollIntoView({block: 'center'});
    }
  });
  check();
}
document.addEventListener("DOMContentLoaded", initPawnRateReadiness);
document.addEventListener("loan-entry:ready", initPawnRateReadiness);
