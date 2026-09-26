// Browser submit contract, including the price-preflight event ordering.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('static/js/pawn-draft-submit.js', 'utf8');

function harness() {
  const status = {hidden: true, textContent: ''};
  const save = {name: 'action', value: 'save', textContent: 'Save draft', disabled: false};
  const preview = {name: 'action', value: 'preview', textContent: 'Preview economics', disabled: false};
  const fields = [{name: 'borrower', value: '4'}, {name: 'submission_token', value: 'same-form-reference'},
    {name: 'photograph', files: ['camera-photo.jpg']}];
  const form = {
    dataset: {}, attrs: {}, fields, buttons: [save, preview],
    querySelector: () => status, querySelectorAll: () => [save, preview],
    addEventListener(name, callback) { this[name] = callback; },
    append(input) { fields.push(input); input.remove = () => fields.splice(fields.indexOf(input), 1); },
    setAttribute(name, value) { this.attrs[name] = value; }, removeAttribute(name) { delete this.attrs[name]; },
  };
  const document = {querySelector: () => form, createElement: () => ({}),
    addEventListener(name, callback) { this[name] = callback; }};
  const window = {addEventListener(name, callback) { this[name] = callback; }};
  vm.runInNewContext(source, {document, window});
  document.DOMContentLoaded();
  function submit(submitter = save, prevented = false) {
    const event = {submitter, defaultPrevented: prevented, preventDefault() { this.defaultPrevented = true; }};
    form.submit(event);
    return event;
  }
  return {form, status, save, preview, window, submit};
}

test('saving locks buttons and preserves action, identity and photograph input', () => {
  const h = harness();
  assert.equal(h.submit().defaultPrevented, false);
  assert.equal(h.save.disabled, true);
  assert.equal(h.preview.disabled, true);
  assert.equal(h.save.textContent, 'Saving…');
  assert.equal(h.status.hidden, false);
  assert.match(h.status.textContent, /draft is saved/);
  assert.equal(h.form.fields.find(row => row.name === 'action').value, 'save');
  assert.equal(h.form.fields.find(row => row.name === 'submission_token').value, 'same-form-reference');
  assert.deepEqual(h.form.fields.find(row => row.name === 'photograph').files, ['camera-photo.jpg']);
  assert.equal(h.submit().defaultPrevented, true);
  assert.equal(h.submit(null).defaultPrevented, true);
  assert.equal(h.form.fields.filter(row => row.name === 'action').length, 1);
});

test('prevented price-check event remains editable, resumed preview keeps preview action', () => {
  const h = harness();
  h.submit(h.preview, true);
  assert.equal(h.save.disabled, false);
  assert.equal(h.form.dataset.draftSubmitting, undefined);
  assert.equal(h.form.fields.find(row => row.name === 'action'), undefined);
  h.submit(h.preview);
  assert.equal(h.form.fields.find(row => row.name === 'action').value, 'preview');
  assert.equal(h.preview.textContent, 'Preparing preview…');
  assert.match(h.status.textContent, /No loan is created/);
});

test('Back after failed navigation restores controls with the original submission identity', () => {
  const h = harness();
  h.submit();
  h.window.pageshow({persisted: true});
  assert.equal(h.save.disabled, false);
  assert.equal(h.preview.disabled, false);
  assert.equal(h.save.textContent, 'Save draft');
  assert.equal(h.status.hidden, true);
  assert.equal(h.form.fields.find(row => row.name === 'action'), undefined);
  assert.equal(h.form.fields.find(row => row.name === 'submission_token').value, 'same-form-reference');
  assert.equal(h.submit().defaultPrevented, false);
});

test('keyboard submission defaults to save without needing a clicked button', () => {
  const h = harness();
  h.submit(null);
  assert.equal(h.form.fields.find(row => row.name === 'action').value, 'save');
  assert.equal(h.save.textContent, 'Saving…');
});
