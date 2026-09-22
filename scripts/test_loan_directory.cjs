const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('static/js/loan-directory.js', 'utf8');

function harness() {
  const listeners = {}, nodes = {}, redirects = [];
  const node = id => nodes[id] = {
    id, attrs: {}, hidden: true, textContent: '', focused: false,
    setAttribute(key, value) { this.attrs[key] = value; },
    removeAttribute(key) { delete this.attrs[key]; },
    focus() { this.focused = true; },
  };
  const results = node('loan-results'), heading = node('loan-results-title');
  heading.textContent = '3 loans found';
  node('loan-search-error'); node('loan-search-announcement');
  const next = {value: ''};
  node('navbar-language').closest = () => ({querySelector: () => next});
  const window = {location: {origin: 'https://example.test', href: 'https://example.test/loans/', pathname: '/loans/', search: '?q=test', assign: url => redirects.push(url)}};
  vm.runInNewContext(source, {window, URL, document: {getElementById: id => nodes[id], addEventListener: (name, fn) => {listeners[name] = fn;}}});
  const emit = (name, detail = {}) => {
    const event = {detail: {target: results, ...detail}};
    listeners[name](event);
    return event.detail;
  };
  return {nodes, results, heading, next, redirects, emit, listeners};
}

test('typing keeps focus; explicit paging focuses the results and announces updates', () => {
  const h = harness();
  h.emit('htmx:beforeRequest', {elt: {hasAttribute: () => false}});
  assert.equal(h.results.attrs['aria-busy'], 'true');
  h.emit('htmx:afterSwap');
  assert.equal(h.heading.focused, false);
  assert.equal(h.nodes['loan-search-announcement'].textContent, '3 loans found');
  assert.equal(h.next.value, '/loans/?q=test');
  h.emit('htmx:beforeRequest', {elt: {hasAttribute: () => true}});
  h.emit('htmx:afterSwap');
  assert.equal(h.heading.focused, true);
  assert.equal(h.results.attrs['aria-busy'], undefined);
});

test('expired sessions navigate normally; external redirects never navigate', () => {
  const h = harness();
  const response = responseURL => ({status: 200, responseURL, getResponseHeader: () => null});
  const detail = h.emit('htmx:beforeSwap', {xhr: response('https://example.test/login/')});
  assert.equal(detail.shouldSwap, false);
  assert.deepEqual(h.redirects, ['https://example.test/login/']);
  assert.equal(h.emit('htmx:beforeSwap', {xhr: response('https://other.test/login/')}).shouldSwap, false);
  assert.equal(h.redirects.length, 1);
  assert.equal(h.emit('htmx:beforeSwap', {xhr: {status: 200, getResponseHeader: () => 'loan-results'}}).shouldSwap, undefined);
});

test('failed searches show recovery and subsequent attempts clear the warning', () => {
  const h = harness();
  h.emit('htmx:beforeRequest');
  h.emit('htmx:afterRequest', {failed: true});
  assert.equal(h.nodes['loan-search-error'].hidden, false);
  assert.equal(h.results.attrs['aria-busy'], undefined);
  h.emit('htmx:beforeRequest');
  assert.equal(h.nodes['loan-search-error'].hidden, true);
});

test('linked filter errors open the collapsed filter and focus its control', () => {
  const h = harness(), disclosure = {open: false};
  const field = h.nodes.id_loan_date_to = {closest: () => disclosure, focus() {this.focused = true;}};
  let prevented = false;
  h.listeners.click({target: {closest: () => ({hash: '#id_loan_date_to'})}, preventDefault() {prevented = true;}});
  assert.equal(prevented, true);
  assert.equal(disclosure.open, true);
  assert.equal(field.focused, true);
});
