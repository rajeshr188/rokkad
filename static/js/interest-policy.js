/* Keep policy guidance optional, and irrelevant controls out of the way. */
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-interest-policy-form]');
  if (!form) return;
  const field = name => form.elements.namedItem(`configuration-${name}`);
  const label = name => field(name)?.selectedOptions?.[0]?.textContent.trim() || '';
  const update = () => {
    const slab = field('partial_month_method').value === 'SLAB';
    ['partial_month_cutoff_days', 'partial_month_lower_fraction'].forEach(name => {
      const wrapper = form.querySelector(`[data-policy-field="${name}"]`);
      // Keep validation errors visible, and values submitted for future revisions.
      wrapper.hidden = !slab && !wrapper.querySelector('.errorlist');
    });
    const compound = form.querySelector('[data-policy-field="capitalization_interval_periods"]');
    compound.hidden = field('interest_method').value !== 'COMPOUND' && !compound.querySelector('.errorlist');
    const scope = field('series').value ? label('series') : label('license');
    const summary = form.querySelector('[data-interest-policy-summary]');
    summary.textContent = `${scope} · ${field('effective_from').value || 'Choose a start date'} · Full first month minimum · Then: ${label('partial_month_method')}. Earlier approved loans keep their terms.`;
  };
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
});
