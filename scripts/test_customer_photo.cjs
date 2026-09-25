const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {readFileSync} = require('node:fs');
const selection = readFileSync('static/js/camera-selection.js', 'utf8');
const source = readFileSync('static/js/customer-photo.js', 'utf8');

function harness({secure = true, fail = false} = {}) {
  const node = () => ({events: {}, hidden: false, disabled: false, files: [],
    addEventListener(name, fn) { this.events[name] = fn; }, focus() { this.focused = true; }});
  const selectors = ['input[type=file]', 'input[type=checkbox]', '[data-photo-preview]',
    '[data-photo-camera]', '[data-photo-video]', '[data-photo-start]', '[data-photo-capture]',
    '[data-photo-stop]', '[data-photo-discard]', '[data-photo-status]', '[data-photo-controls]'];
  const nodes = Object.fromEntries(selectors.map(s => [s, node()]));
  const input = nodes[selectors[0]], clear = nodes[selectors[1]], preview = nodes[selectors[2]];
  Object.defineProperty(input, 'value', {set(value) { if (value === '') this.files = []; }});
  preview.getAttribute = () => '/w/test/parties/1/photo/';
  const video = nodes['[data-photo-video]'];
  video.play = async () => {};
  video.videoWidth = 1920; video.videoHeight = 1080;
  const form = node(), root = node(), document = node(), window = node();
  root.dataset = {ready: 'selected', error: 'fallback', waiting: 'waiting', live: 'live', stopped: 'stopped'};
  root.querySelector = key => nodes[key]; root.closest = () => form;
  document.querySelector = () => root;
  const callbacks = [], canvas = {getContext: () => ({drawImage() {}}), toBlob(fn) { callbacks.push(fn); }};
  document.createElement = () => canvas;
  window.isSecureContext = secure;
  const pending = [], revoked = [], streams = [];
  const mediaDevices = {getUserMedia(options) {
    assert.equal(options.audio, false);
    return fail ? Promise.reject(new Error('denied')) : new Promise(resolve => pending.push(resolve));
  }};
  vm.runInNewContext(selection + source, {document, window, navigator: {mediaDevices},
    URL: {createObjectURL: file => 'blob:' + file.name, revokeObjectURL: url => revoked.push(url)},
    DataTransfer: class { constructor() {this.files = []; this.items = {add: file => this.files.push(file)};} },
    File: class {constructor(parts, name, options) {this.name = name; this.type = options.type;}},
  });
  document.events.DOMContentLoaded();
  const resolve = () => {const track = {stopped: false, stop() {this.stopped = true;}};
    const stream = {getTracks: () => [track], track}; streams.push(stream); pending.shift()(stream); return stream;};
  const click = name => nodes['[data-photo-' + name + ']'].events.click();
  return {input, clear, preview, nodes, form, document, window, callbacks, canvas, revoked, resolve, click, pending};
}

test('capture becomes the normal upload, previews it, and stops all tracks', async () => {
  const h = harness(); const opening = h.click('start'); const stream = h.resolve(); await opening;
  h.clear.checked = true;
  h.click('capture'); h.callbacks.shift()({});
  assert.equal(stream.track.stopped, true);
  assert.equal(h.input.files[0].name, 'customer-photo.jpg');
  assert.equal(h.input.files[0].type, 'image/jpeg');
  assert.equal(h.preview.src, 'blob:customer-photo.jpg');
  assert.equal(h.clear.checked, false);
  assert.equal(h.canvas.width, 1280); assert.equal(h.canvas.height, 720);
});
test('cancel while permission is pending stops a late stream', async () => {
  const h = harness(); const opening = h.click('start'); h.click('stop');
  const stream = h.resolve(); await opening;
  assert.equal(stream.track.stopped, true);
  assert.equal(h.nodes['[data-photo-camera]'].hidden, true);
});
test('upload selection wins over an older asynchronous capture', async () => {
  const h = harness(); const opening = h.click('start'); h.resolve(); await opening; h.click('capture');
  const upload = {name: 'chosen.png', type: 'image/png'};
  h.input.files = [upload]; h.input.events.change(); h.callbacks.shift()({});
  assert.equal(h.input.files[0], upload); assert.equal(h.preview.src, 'blob:chosen.png');
});
test('discard restores saved preview and revokes the temporary URL', () => {
  const h = harness(); h.input.files = [{name:'selected.jpg', type:'image/jpeg'}]; h.input.events.change();
  h.click('discard'); assert.equal(h.preview.src, '/w/test/parties/1/photo/');
  assert.deepEqual(h.revoked, ['blob:selected.jpg']); assert.equal(h.input.files.length, 0);
});
test('denied and insecure camera access keep ordinary file upload available', async () => {
  for (const options of [{fail:true}, {secure:false}]) {
    const h = harness(options); await h.click('start');
    assert.equal(h.nodes['[data-photo-status]'].textContent, 'fallback');
    assert.equal(h.input.disabled, false);
  }
});
test('leaving, hiding or submitting stops the active camera', async () => {
  for (const event of ['submit','pagehide','visibilitychange']) {
    const h = harness(); const opening = h.click('start'); const stream = h.resolve(); await opening;
    if (event === 'submit') h.form.events.submit();
    else if (event === 'pagehide') h.window.events.pagehide();
    else { h.document.hidden = true; h.document.events.visibilitychange(); }
    assert.equal(stream.track.stopped, true);
  }
});
