/* Mirror entered facts for review, without calculating or saving domain data. */
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('party-photo-editor')?.addEventListener('toggle', event => {
    if (!event.target.open) document.getElementById('party-camera-stop')?.click();
  });
  const form = document.querySelector('[data-entry-form] form, form[data-entry-form]');
  if (!form) return;
  function update() {
    document.querySelectorAll('[data-entry-field]').forEach(target => {
      const field = form.elements.namedItem(target.dataset.entryField);
      if (!field) return;
      let value = field.value;
      if (field.tagName === 'SELECT') value = field.value ? field.selectedOptions[0]?.textContent : '';
      if (field.type === 'checkbox') value = field.checked ? 'Yes' : 'No';
      target.textContent = value || target.dataset.empty || 'Not entered';
    });
  }
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
});
