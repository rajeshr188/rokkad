(() => {
  const form = document.querySelector('[data-label-form]');
  if (!form) return;
  const items = Array.from(form.querySelectorAll('input[name="items"]'));
  const count = form.querySelector('[data-label-count]');
  const update = () => { count.textContent = `${items.filter(item => item.checked).length} selected`; };
  for (const [selector, checked] of [['[data-label-select]', true], ['[data-label-clear]', false]]) {
    const button = form.querySelector(selector);
    button.hidden = false;
    button.addEventListener('click', () => {
      items.forEach(item => { item.checked = checked; });
      if (checked) form.querySelector('[name="mode"]').value = 'SELECTED';
      update();
    });
  }
  items.forEach(item => item.addEventListener('change', update));
  update();
})();
