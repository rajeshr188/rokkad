const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('static/js/counter-entry.js', 'utf8');

function harness(seeded = false) {
  const dom = {}, win = {};
  let accept = false, prompts = 0;
  let bound = seeded;
  let form = {hasAttribute: () => bound};
  vm.runInNewContext(source, {
    document: {querySelector: selector => selector.includes('[data-unsaved-entry]') ? (form && bound ? form : null) : form, addEventListener: (name, callback) => {dom[name] = callback;}},
    window: {addEventListener: (name, callback) => {win[name] = callback;}, confirm: () => {prompts++; return accept;}},
  });
  const unload = () => {
    let blocked = false;
    win.beforeunload({preventDefault() {blocked = true;}});
    return blocked;
  };
  return {dom, win, unload, edit: () => dom.input({target: {closest: () => ({})}}),
    accept: () => {accept = true;}, prompts: () => prompts,
    navigateAway: () => {form = null; dom['htmx:afterSwap']();},
    openEntry: () => {bound = false; form = {hasAttribute: () => false}; dom['htmx:afterSwap']();}};
}

test('only unsaved entry edits block ordinary navigation', () => {
  const h = harness();
  assert.equal(h.unload(), false);
  h.dom.input({target: {closest: () => null}});
  assert.equal(h.unload(), false);
  h.edit();
  assert.equal(h.unload(), true);
});

test('a posted preview or error redisplay is already an unsaved entry', () => {
  assert.equal(harness(true).unload(), true);
});

test('blocked validation keeps protection; ordinary submitted forms may navigate', () => {
  const h = harness(); h.edit();
  h.dom.submit({target: {id: 'new-loan-form'}, defaultPrevented: true});
  assert.equal(h.unload(), true);
  h.dom.submit({target: {id: 'new-loan-form'}, defaultPrevented: false});
  assert.equal(h.unload(), false);
  h.win.pageshow();
  assert.equal(h.unload(), true);
});

test('boosted departure requires confirmation and failed navigation retains protection', () => {
  const h = harness(); h.edit();
  let blocked = false;
  const event = {detail: {requestConfig: {boosted: true}}, preventDefault() {blocked = true;}};
  h.dom['htmx:beforeRequest'](event);
  assert.equal(blocked, true);
  h.accept(); h.dom['htmx:beforeRequest'](event);
  assert.equal(h.unload(), false);
  h.dom['htmx:afterRequest']({detail: {failed: true, requestConfig: {boosted: true}}});
  assert.equal(h.unload(), true);
});

test('in-page price checks do not prompt or discard the dirty marker', () => {
  const h = harness(); h.edit();
  h.dom['htmx:beforeRequest']({detail: {requestConfig: {boosted: false}}});
  assert.equal(h.prompts(), 0);
  assert.equal(h.unload(), true);
});

test('in-page swaps preserve edits; a new counter page resets the entry lifecycle', () => {
  const h = harness(); h.edit();
  h.dom['htmx:afterSwap']();
  assert.equal(h.unload(), true);
  h.navigateAway();
  assert.equal(h.unload(), false);
  h.openEntry(); h.edit();
  assert.equal(h.unload(), true);
});
