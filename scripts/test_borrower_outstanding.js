// Exercise overlapping responses without a browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function check(fieldId) {
  let change;
  const requests = [];
  const select = {value: '1', addEventListener: (_, fn) => { change = fn; }};
  const panel = {dataset: {url: '/balances/'}, textContent: '',
    replaceChildren(...nodes) { this.nodes = nodes; this.textContent = ''; }};
  const context = {
    URL, AbortController,
    window: {location: {origin: 'https://example.test'}},
    document: {getElementById: id => id === fieldId ? select : id === 'borrower-outstanding' ? panel : null,
      addEventListener: (name, fn) => { if (name === 'DOMContentLoaded') fn(); }},
    fetch: () => new Promise(resolve => requests.push(resolve)),
    DOMParser: class { parseFromString(id) { return {querySelector: () => ({dataset: {borrowerResult: id}})}; }},
  };
  vm.runInNewContext(fs.readFileSync('static/js/pawn-borrower-outstanding.js', 'utf8'), context);
  select.value = '2';
  const second = change();
  requests[1]({ok: true, text: async () => '2'});
  await second;
  assert.equal(panel.nodes[0].dataset.borrowerResult, '2');
  requests[0]({ok: true, text: async () => '1'});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(panel.nodes[0].dataset.borrowerResult, '2', 'late previous borrower must not replace current balance');
  select.value = '';
  await change();
  assert.equal(panel.nodes.length, 0, 'clearing borrower removes balance');
  select.value = '3';
  const third = change();
  requests[2]({ok: false});
  await third;
  assert.match(panel.textContent, /unavailable balance does not mean zero/);
  console.log(`${fieldId}: borrower response race, clear and failure states: PASS`);
}
Promise.all(['id_borrower', 'id_borrower_id'].map(check))
  .catch(error => { console.error(error); process.exitCode = 1; });
