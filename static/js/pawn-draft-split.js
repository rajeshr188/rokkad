document.querySelectorAll('[data-draft-split-form]').forEach((form) => {
  const refresh = () => {
    const mode = form.querySelector('input[name="split_mode"]:checked')?.value || 'selected';
    form.querySelectorAll('[data-split-selection]').forEach((section) => {
      section.hidden = section.dataset.splitSelection !== mode;
    });
  };
  form.addEventListener('change', (event) => {
    if (event.target.name === 'split_mode') refresh();
  });
  refresh();
});
