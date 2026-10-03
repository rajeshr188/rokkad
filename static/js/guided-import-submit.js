document.querySelectorAll('form[data-import-submit]').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    if (form.dataset.submitting === 'yes') { event.preventDefault(); return; }
    form.dataset.submitting = 'yes';
    form.setAttribute('aria-busy', 'true');
    form.querySelectorAll('button[type="submit"]').forEach(function (button) {
      button.dataset.originalLabel = button.textContent;
      button.disabled = true;
      button.textContent = 'Working… please wait';
    });
  });
});
window.addEventListener('pageshow', function () {
  document.querySelectorAll('form[data-import-submit]').forEach(function (form) {
    delete form.dataset.submitting;
    form.removeAttribute('aria-busy');
    form.querySelectorAll('button[data-original-label]').forEach(function (button) {
      button.disabled = false;
      button.textContent = button.dataset.originalLabel;
    });
  });
});
