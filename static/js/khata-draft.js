document.addEventListener('DOMContentLoaded', () => {
  const panel = document.getElementById('khata-opening-estimate');
  if (!panel) return;
  const fields = ['agreed_limit', 'monthly_rate', 'frequency'].map(name => document.getElementById(`id_${name}`));
  let timer, sequence = 0, controller;
  async function refresh() {
    const key = ++sequence;
    controller?.abort();
    if (fields.some(field => !field.value || !field.checkValidity())) {
      panel.textContent = 'Enter valid terms to see an opening illustration. No charge is posted.';
      return;
    }
    const url = new URL(panel.dataset.url, location.origin);
    fields.forEach(field => url.searchParams.set(field.name, field.value));
    const values = fields.map(field => field.value).join('|');
    controller = new AbortController();
    panel.textContent = 'Calculating opening illustration…';
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('unavailable');
      const html = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (key !== sequence || fields.map(field => field.value).join('|') !== values) return;
      const result = html.querySelector('[data-khata-estimate]');
      if (!result) throw new Error('unavailable');
      panel.replaceChildren(result);
    } catch (error) {
      if (key === sequence && error.name !== 'AbortError') panel.textContent = 'Illustration unavailable. Review valid terms to see the server calculation before saving; unavailable does not mean zero.';
    }
  }
  fields.forEach(field => field.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(refresh, 250); }));
  refresh();
});
