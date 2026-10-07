function initPawnBorrowerOutstanding() {
  const select = document.getElementById('id_borrower') || document.getElementById('id_borrower_id');
  const panel = document.getElementById('borrower-outstanding');
  if (!select || !panel) return;
  let sequence = 0, controller;
  async function refresh() {
    const key = ++sequence;
    controller?.abort();
    panel.replaceChildren();
    if (!select.value) return;
    const borrower = select.value;
    controller = new AbortController();
    panel.textContent = 'Loading borrower balances…';
    try {
      const url = new URL(panel.dataset.url, window.location.origin);
      url.searchParams.set('borrower', borrower);
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('unavailable');
      const html = await response.text();
      const document = new DOMParser().parseFromString(html, 'text/html');
      const result = document.querySelector('[data-borrower-result]');
      if (key !== sequence || borrower !== select.value) return;
      if (!result || result.dataset.borrowerResult !== borrower) throw new Error('unavailable');
      panel.replaceChildren(result);
    } catch (error) {
      if (key === sequence && error.name !== 'AbortError') panel.textContent = 'Borrower balances are unavailable. Open the borrower’s loans to check; an unavailable balance does not mean zero.';
    }
  }
  if (window.jQuery) window.jQuery(select).on('change', refresh);
  else select.addEventListener('change', refresh);
  refresh();
}
document.addEventListener("DOMContentLoaded", initPawnBorrowerOutstanding);
document.addEventListener("loan-entry:ready", initPawnBorrowerOutstanding);
