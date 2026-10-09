/* Labels describe the existing fields; no financial values are calculated here. */
function initDirectEntryLayout() {
  const root = document.querySelector('[data-new-loan-entry]');
  if (!root || !root.querySelector('[data-draft-save-form]') || root.dataset.directLabelsReady) return;
  root.dataset.directLabelsReady = 'true';
  const update = () => {
    const date = root.querySelector('[name=loan_date]'), tenure = root.querySelector('[name=tenure_months]');
    const dateLabel = root.querySelector('[data-direct-date-label]'), tenureLabel = root.querySelector('[data-direct-tenure-label]');
    if (dateLabel && date) dateLabel.textContent = /^\d{4}-\d{2}-\d{2}$/.test(date.value)
      ? date.value.split('-').reverse().join('/') : date.value || 'Choose a date';
    if (tenureLabel && tenure) tenureLabel.textContent = tenure.value || 'Enter tenure';
  };
  root.addEventListener('input', update);
  root.addEventListener('change', update);
  update();
}
document.addEventListener('DOMContentLoaded', initDirectEntryLayout);
document.addEventListener('loan-entry:ready', initDirectEntryLayout);
