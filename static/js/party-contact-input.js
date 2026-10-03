/* Adapt the mixed contact field; Django's phone library validates on save. */
(() => {
  const phoneTypes = new Set(['PHONE', 'MOBILE', 'WHATSAPP']);
  function updateContactInput(select) {
    const form = select.closest('form');
    const input = form?.querySelector('[data-contact-value]');
    const help = form?.querySelector('[data-contact-phone-help]');
    if (!input) return;
    const phone = phoneTypes.has(select.value);
    const type = phone ? 'tel' : select.value === 'EMAIL' ? 'email' : select.value === 'WEBSITE' ? 'url' : 'text';
    input.type = type;
    input.setAttribute('inputmode', type);
    input.setAttribute('autocomplete', phone ? 'tel' : type === 'email' ? 'email' : 'off');
    input.placeholder = phone ? '+91 98765 43210' : '';
    input.maxLength = phone ? 32 : 255;
    const label = form.querySelector('label[for="' + input.id + '"]');
    if (label) label.textContent = phone ? 'Number:' : 'Value:';
    if (help) {
      help.hidden = !phone;
      const ids = new Set((input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
      if (phone) ids.add(help.id); else ids.delete(help.id);
      if (ids.size) input.setAttribute('aria-describedby', [...ids].join(' '));
      else input.removeAttribute('aria-describedby');
    }
  }
  document.addEventListener('change', event => {
    if (event.target.matches('[data-contact-type]')) updateContactInput(event.target);
  });
  function initialize() { document.querySelectorAll('[data-contact-type]').forEach(updateContactInput); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
