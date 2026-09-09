(() => {
  const selection = document.getElementById('batch-selection');
  const loans = document.getElementById('batch-loans');
  if (loans && window.jQuery?.fn.select2) {
    window.jQuery(loans).select2({
      width: '100%', maximumSelectionLength: 20,
      placeholder: 'Search loan number, borrower or phone',
      ajax: {url: loans.dataset.searchUrl, dataType: 'json', delay: 250,
        data: params => ({q: params.term || '', page: params.page || 1})}
    }).on('change', () => selection.dispatchEvent(new Event('selection-changed', {bubbles: true})));
  }
  function collectors() {
    document.querySelectorAll('.collector-fields').forEach(section => {
      const select = section.querySelector('select');
      const update = () => section.querySelectorAll('.collector-other').forEach(field => {
        field.hidden = select.value !== 'other';
      });
      select.onchange = update;
      update();
    });
  }
  collectors();
  document.addEventListener('htmx:afterSwap', collectors);
  document.addEventListener('htmx:beforeRequest', event => {
    if (event.detail.elt === selection) {
      const button = document.querySelector('#batch-confirm button[type=submit]');
      if (button) button.disabled = true;
    }
  });
  document.addEventListener('submit', event => {
    if (event.target.id === 'batch-confirm' && event.target.querySelector('button[type=submit]').disabled) {
      event.preventDefault();
    }
  });
})();
