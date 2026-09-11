// Browser-event contract tests; no packages or network required.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('static/js/pawn-rate-readiness.js', 'utf8');

function harness() {
  const node = () => ({
    events: {}, dataset: {}, attrs: {},
    addEventListener(name, callback) { this.events[name] = callback; },
    setAttribute(name, value) { this.attrs[name] = value; },
    focus() {}, scrollIntoView() {},
  });
  const content = node(), panel = node(), button = node(), form = node(), rows = node();
  const series = {value: '1'}, date = {value: '2026-09-11'}, metal = {value: 'GOLD'};
  const photograph = {files: [{name: 'collateral.jpg'}]};
  const row = {querySelector: selector => selector.endsWith('DELETE"]') ? {checked: false} : metal};
  rows.querySelectorAll = () => [row];
  content.querySelector = () => content.result;
  panel.querySelector = selector => selector.includes('content') ? content : button;
  form.querySelector = selector => ({
    '[data-rate-readiness-panel]': panel, '#collateral-formset': rows,
    '[name="series"]': series, '[name="loan_date"]': date,
  })[selector];
  form.dataset.valuationPreflight = '/w/example/loans/internal/valuation-readiness/';
  form.submitted = [];
  form.requestSubmit = submitter => {
    const event = {submitter, prevented: false, preventDefault() { this.prevented = true; }};
    form.events.submit(event);
    if (!event.prevented) form.submitted.push(submitter);
  };
  const pending = [];
  const htmx = {
    trigger() {},
    ajax(method, url, options) {
      return new Promise((resolve, reject) => pending.push({method, url, options, resolve, reject}));
    },
  };
  const document = {
    addEventListener(name, callback) { this.ready = callback; },
    querySelector() { return form; },
  };
  vm.runInNewContext(source, {
    document, window: {htmx}, htmx,
    MutationObserver: class { observe() {} },
  });
  document.ready();
  const complete = async (call, ready) => {
    content.result = {dataset: {requestKey: String(call.options.values.request_key), ready: String(ready)}};
    call.resolve();
    await Promise.resolve();
  };
  const submit = (submitter = {value: 'save'}) => form.events.submit({submitter, preventDefault() {}});
  return {form, content, series, metal, photograph, pending, complete, submit};
}

test('missing prices block submission and preflight sends no borrower data or files', async () => {
  const h = harness();
  await h.complete(h.pending.shift(), false);
  const files = h.photograph.files;
  const submitted = h.submit();
  const call = h.pending.shift();
  assert.equal(call.method, 'GET');
  assert.deepEqual(Object.keys(call.options.values).sort(), ['as_of', 'metals', 'request_key', 'series']);
  assert.equal(h.content.attrs['hx-params'], 'series,as_of,metals,request_key');
  await h.complete(call, false);
  await submitted;
  assert.equal(h.form.submitted.length, 0);
  assert.equal(h.photograph.files, files);
});

test('a successful fresh check submits once with the original preview action', async () => {
  const h = harness();
  await h.complete(h.pending.shift(), true);
  const action = {name: 'action', value: 'preview'};
  const submitted = h.submit(action);
  await h.submit(action); // Second click while checking must not send again.
  assert.equal(h.pending.length, 1);
  await h.complete(h.pending.shift(), true);
  await submitted;
  assert.deepEqual(h.form.submitted, [action]);
});

test('changing metals while a successful check is in flight cannot submit stale results', async () => {
  const h = harness();
  await h.complete(h.pending.shift(), true);
  const submitted = h.submit();
  const call = h.pending.shift();
  h.metal.value = 'SILVER';
  await h.complete(call, true);
  await submitted;
  assert.equal(h.form.submitted.length, 0);
});

test('a failed request keeps the form in place and permits a later retry', async () => {
  const h = harness();
  await h.complete(h.pending.shift(), true);
  const submitted = h.submit();
  h.pending.shift().reject(new Error('offline'));
  await submitted;
  assert.equal(h.form.submitted.length, 0);
  assert.match(h.content.textContent, /retained/);
  const retry = h.submit();
  await h.complete(h.pending.shift(), true);
  await retry;
  assert.equal(h.form.submitted.length, 1);
});
