(() => {
  const form = document.getElementById('closing-selection');
  if (!form) return;
  const loans = form.querySelector('#closing-loans');
  const purpose = form.querySelector('#closing-purpose');
  const maximum = () => purpose.value === 'CURRENT' ? 20 : 50;
  function changed() {
    const tooMany = loans.selectedOptions.length > maximum();
    const warning = document.getElementById('closing-selection-changed');
    warning.hidden = false;
    warning.textContent = tooMany ? `Choose up to ${maximum()} loans for this mode. Remove loans to continue.` : 'Selection changed. Continue to review before confirming.';
    form.querySelector('button[type="submit"]').disabled = tooMany;
    document.querySelectorAll('form[data-closing-review] button[type="submit"], form[data-closing-review] button:not([type])').forEach(button => {
      button.disabled = true;
    });
  }
  form.addEventListener('change', changed);
  if (window.jQuery?.fn.select2) {
    const picker = window.jQuery(loans);
    function initialize() {
      if (picker.data('select2')) picker.select2('destroy');
      picker.select2({
        width: '100%', maximumSelectionLength: maximum(), minimumInputLength: 1,
        placeholder: 'Type to search loans',
        ajax: {url: loans.dataset.searchUrl, dataType: 'json', delay: 250,
          data: params => ({q: params.term || '', page: params.page || 1})}
      });
    }
    initialize();
    picker.on('select2:open', () => {
      const search = picker.data('select2').$container.find('.select2-search__field');
      search.attr({'aria-label': 'Search loans by number or borrower', 'aria-describedby': 'closing-search-help'});
    });
    picker.on('change', changed);
    purpose.addEventListener('change', initialize);
  }
})();
