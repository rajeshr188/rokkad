/* Keep server validation authoritative; make its recovery path keyboard usable. */
document.addEventListener('DOMContentLoaded', () => {
  const summary = document.querySelector('[data-form-errors]');
  if (!summary) return;
  summary.focus();
  summary.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link) return;
    const target = document.getElementById(link.hash.slice(1));
    if (!target) return;
    event.preventDefault();
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    const control = target.matches('input, select, textarea, button') ? target : target.querySelector('input, select, textarea, button');
    const enhanced = control?.nextElementSibling?.querySelector('[role="combobox"]');
    (enhanced || control)?.focus();
    target.scrollIntoView({ block: 'center' });
  });
});
