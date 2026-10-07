// Exercise shared controllers together: one click must never add two paper rows.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

for (const purpose of ['direct', 'paper']) {
  test(`${purpose}: add/remove once, preserve deleted rows and sum active principal`, () => {
    const node = () => ({events: {}, dataset: {}, addEventListener(name, fn) {
      (this.events[name] ||= []).push(fn);
    }, dispatchEvent(event) { for (const fn of this.events[event.type] || []) fn(event); }});
    const form = node(), container = node(), add = node();
    const total = {value: '1'}, principal = {value: ''};
    const row = () => {
      const deletion = {checked: false}, amount = {value: '1000'};
      return {hidden: false, querySelector(selector) {
        return selector.includes('DELETE') ? deletion : selector.includes('allocated_principal') ? amount : {focus() {}};
      }};
    };
    const rows = [row()];
    container.closest = () => form;
    container.querySelectorAll = () => rows;
    container.insertAdjacentHTML = () => { rows.push(row()); container.lastElementChild = rows.at(-1); };
    form.querySelectorAll = selector => selector === '[data-collateral-form]' ? rows : [];
    form.querySelector = () => null;
    form.elements = {namedItem: name => name === 'principal' ? principal : {value: '', checked: false}};
    const ids = {'collateral-formset': container, 'add-collateral': add,
      'empty-collateral-form': {innerHTML: '__prefix__'}, 'id_collateral-TOTAL_FORMS': total};
    const context = {Event, document: {getElementById: id => ids[id],
      querySelector: () => purpose === 'paper' ? form : null,
      addEventListener: (name, fn) => { if (name === 'DOMContentLoaded') fn(); }}};
    vm.runInNewContext(fs.readFileSync('static/js/pawn-collateral-editor.js', 'utf8'), context);
    vm.runInNewContext(fs.readFileSync('static/js/paper-entry.js', 'utf8'), context);
    context.initPawnCollateralEditor(); // Reinitializing the same root cannot duplicate handlers.
    add.dispatchEvent(new Event('click'));
    assert.equal(rows.length, 2);
    assert.equal(total.value, '2');
    if (purpose === 'paper') assert.equal(principal.value, '2000.00');
    container.dispatchEvent({type: 'click', target: {closest: () => ({closest: () => rows[1]})}});
    assert.equal(rows[1].querySelector('DELETE').checked, true);
    assert.equal(rows[1].hidden, true);
    assert.equal(total.value, '2', 'deleted row indices stay stable for photos and review');
    if (purpose === 'paper') assert.equal(principal.value, '1000.00');
    total.value = '100';
    add.dispatchEvent(new Event('click'));
    assert.equal(rows.length, 2, 'do not add beyond the supported 100 rows');
  });
}
