(() => {
  function initialize() {
    const form = document.getElementById('paper-closure-form');
    if (!form || form.dataset.initialized) return;
    form.dataset.initialized = 'yes';
    const picker = document.getElementById('paper-loans');
    if (window.jQuery && jQuery.fn.select2) {
      jQuery(picker).select2({width: '100%', minimumInputLength: 1, maximumSelectionLength: Number(picker.dataset.max),
        ajax: {url: picker.dataset.searchUrl, dataType: 'json', delay: 300,
          data: params => ({q: params.term, page: params.page || 1}), processResults: data => data}});
    }
    const update = () => {
      let total = 0, count = 0;
      form.querySelectorAll('.paper-row').forEach(row => {
        const amount = Number(row.querySelector('[name$="-amount"]').value);
        const checkbox = row.querySelector('[name$="-include"]');
        if (checkbox.checked && !checkbox.disabled && Number.isFinite(amount)) {total += amount; count++;}
        const delta = amount - Number(row.dataset.due);
        const note = row.querySelector('.paper-difference');
        note.textContent = Number.isFinite(delta) && Math.abs(delta) > 0.005 ?
          (delta < 0 ? `₹${(-delta).toFixed(2)} shortfall: needs an authorized interest concession.` : `₹${delta.toFixed(2)} above due: review before recording.`) : '';
        note.classList.toggle('text-danger', Boolean(note.textContent));
        const details = row.querySelector('details');
        const payer = row.querySelector('[name$="-paid_by"]').value;
        const recipient = row.querySelector('[name$="-collector_name"]').value;
        details.querySelector('summary').textContent = `Paid by ${payer}; received by ${recipient} · details`;
      });
      const output = document.getElementById('paper-total');
      if (output) output.textContent = `${count} selected · Actual collections ₹${total.toLocaleString('en-IN', {minimumFractionDigits: 0, maximumFractionDigits: 2})}`;
    };
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    form.addEventListener('submit', event => {
      if (event.submitter?.value === 'complete' && !form.querySelector('[name="confirmed"]').checked) {
        event.preventDefault(); form.querySelector('[name="confirmed"]').focus();
      }
    });
    update();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
  document.addEventListener('htmx:load', initialize);
})();
