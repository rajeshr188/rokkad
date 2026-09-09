/* HTMX retrieves suggestions; the server owns valuation arithmetic. */
document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('collateral-formset');
  const date = document.getElementById('id_loan_date');
  if (!container || !date || !window.htmx) return;
  const states = new WeakMap();
  const field = (row, name) => row.querySelector(`[name$="-${name}"]`);
  function initialise(row) {
    if (states.has(row)) return states.get(row);
    const input = field(row, 'latest_appraised_value');
    const panel = document.createElement('div');
    panel.className = 'form-text';
    panel.setAttribute('role', 'status');
    panel.setAttribute('aria-live', 'polite');
    panel.setAttribute('hx-params', 'metal,gross_weight,net_weight,purity,as_of,request_key');
    input.insertAdjacentElement('afterend', panel);
    const state = {input, panel, manual: input.value !== '', key: 0, timer: null};
    states.set(row, state);
    panel.addEventListener('htmx:beforeSwap', event => {
      const response = new DOMParser().parseFromString(event.detail.xhr.responseText, 'text/html');
      const result = response.querySelector('[data-appraisal-result]');
      if (!result || result.dataset.requestKey !== String(state.key) || row.hidden) event.detail.shouldSwap = false;
    });
    panel.addEventListener('htmx:afterSwap', () => {
      const result = panel.querySelector('[data-appraisal-result]');
      if (result?.dataset.requestKey !== String(state.key) || row.hidden) return;
      if (!state.manual && result.dataset.value) fill(state, result.dataset.value);
    });
    panel.addEventListener('click', event => {
      if (!event.target.closest('[data-apply-appraisal]')) return;
      const value = panel.querySelector('[data-appraisal-result]')?.dataset.value;
      if (value) { state.manual = false; fill(state, value); }
    });
    return state;
  }
  function fill(state, value) {
    state.input.value = value;
    state.input.dispatchEvent(new CustomEvent('input', {bubbles: true, detail: {appraisalSuggestion: true}}));
  }
  function request(row) {
    const state = initialise(row);
    clearTimeout(state.timer);
    state.key += 1;
    htmx.trigger(state.panel, 'htmx:abort');
    if (!state.manual) fill(state, '');
    const values = {
      metal: field(row, 'metal').value, gross_weight: field(row, 'gross_weight').value,
      net_weight: field(row, 'net_weight').value, purity: field(row, 'purity_percentage').value,
      as_of: date.value, request_key: state.key,
    };
    if (row.hidden || field(row, 'DELETE')?.checked) { state.panel.replaceChildren(); return; }
    if (!values.as_of || !values.gross_weight || !values.net_weight || !values.purity) {
      state.panel.textContent = 'Enter gross weight, net weight, purity, and loan date for a suggested appraisal.';
      return;
    }
    state.panel.textContent = 'Checking buying rate…';
    state.timer = setTimeout(() => {
      htmx.ajax('GET', container.dataset.appraisalUrl, {source: state.panel, target: state.panel, swap: 'innerHTML', values}).catch(() => {
        if (values.request_key === state.key) state.panel.textContent = 'Suggestion unavailable. Enter an appraisal manually or try again.';
      });
    }, 350);
  }
  container.addEventListener('input', event => {
    const row = event.target.closest('[data-collateral-form]');
    if (!row) return;
    const state = initialise(row);
    if (event.target === state.input) {
      if (!event.detail?.appraisalSuggestion) state.manual = state.input.value !== '';
      return;
    }
    if (/-(metal|gross_weight|net_weight|purity_percentage)$/.test(event.target.name)) request(row);
  });
  date.addEventListener('change', () => container.querySelectorAll('[data-collateral-form]').forEach(request));
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === 1 && node.matches('[data-collateral-form]')) initialise(node);
  }))).observe(container, {childList: true});
  container.querySelectorAll('[data-collateral-form]').forEach(row => {
    const state = initialise(row);
    if (!state.manual) request(row);
  });
});
