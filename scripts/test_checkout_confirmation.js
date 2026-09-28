// Execute the real checkout script with only its DOM/provider boundaries replaced.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const template = fs.readFileSync(path.join(__dirname, '../templates/subscriptions/checkout.html'), 'utf8');
const script = template.slice(template.lastIndexOf('<script>') + 8, template.lastIndexOf('</script>'))
    .replace(/{% url "workspace_subscriptions:order-create"[^%]*%}/g, '/order/')
    .replace(/{% url "workspace_subscriptions:payment-create"[^%]*%}/g, '/confirm/')
    .replace(/{{[\s\S]*?}}/g, '1').replace(/{%[\s\S]*?%}/g, '/fixture/');

for (const failure of ['provider', 'network']) {
    test(`retry after ${failure} error confirms the same payment without a second order`, async () => {
        const elements = new Map();
        function element(id) {
            if (!elements.has(id)) elements.set(id, {
                value: id === 'billing-cycle-input' ? 'yearly' : '', disabled: false,
                classList: { add() {}, remove() {} },
                addEventListener(type, action) { this[type] = action; },
                querySelector(selector) { return { value: selector.includes('csrf') ? 'csrf-fixture' : '1' }; },
            });
            return elements.get(id);
        }
        const cycles = [{ disabled:false }, { disabled:false }];
        cycles.forEach(c => { c.addEventListener = () => {}; });
        const calls = [];
        let checkout, opens = 0, confirmations = 0;
        const sandbox = {
            document: {
                getElementById: element, querySelectorAll: () => cycles,
                addEventListener(type, action) { action(); },
            },
            crypto: { randomUUID: () => 'fixture-request' },
            window: { location: { href:'', search:'' } },
            Razorpay: function (options) { checkout = options; this.open = () => { opens++; }; },
            fetch: async (url, options) => {
                calls.push({ url, body:options.body });
                if (url === '/order/') return { json: async () => ({ order_id:'order_fixture', amount:1768820, currency:'INR' }) };
                confirmations++;
                if (confirmations === 1 && failure === 'network') throw new Error('Network unavailable');
                return { json: async () => confirmations === 1
                    ? { success:false, error:'Provider temporarily unavailable' }
                    : { success:true, redirect_url:'/billing/' } };
            },
        };
        vm.runInNewContext(script, sandbox);
        const settle = () => new Promise(resolve => setImmediate(resolve));
        const button = element('razorpay-button');
        button.click({ preventDefault() {} });
        await settle();
        checkout.handler({ razorpay_order_id:'order_fixture', razorpay_payment_id:'pay_fixture', razorpay_signature:'signature-fixture' });
        await settle();
        assert.equal(button.textContent, 'Retry payment confirmation');
        assert.equal(button.disabled, false);
        assert.equal(element('confirmation-note').hidden, false);
        assert.ok(cycles.every(c => c.disabled));
        button.click({ preventDefault() {} });
        await settle();
        assert.equal(calls.filter(c => c.url === '/order/').length, 1);
        const retries = calls.filter(c => c.url === '/confirm/');
        assert.equal(retries.length, 2);
        assert.equal(retries[0].body, retries[1].body);
        assert.equal(opens, 1);
        assert.equal(sandbox.window.location.href, '/billing/');
    });
}
