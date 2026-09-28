const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const script = fs.readFileSync(path.join(__dirname, '../static/js/recurring-checkout.js'), 'utf8');

for (const failure of ['network', 'provider']) {
    test(`authorization confirmation ${failure} retry cannot open a second Checkout`, async () => {
        const elements = new Map();
        function element(id) {
            if (!elements.has(id)) elements.set(id, {disabled: true, checked: false,
                dataset: {startUrl: '/start/', confirmUrl: '/confirm/'},
                addEventListener(type, action) { this[type] = action; }});
            return elements.get(id);
        }
        const calls = [];
        let checkout, opens = 0, confirmations = 0;
        vm.runInNewContext(script, {
            document: {getElementById: element, querySelector: () => ({value: 'csrf'})},
            Razorpay: function(options) { checkout = options; this.open = () => { opens++; }; },
            fetch: async (url, options) => {
                calls.push({url, body: options.body});
                if (url === '/start/') return {ok: true, json: async () => ({subscription_id: 'sub_fixture'})};
                confirmations++;
                if (confirmations === 1 && failure === 'network') throw new Error('Unavailable');
                return {ok: confirmations > 1, json: async () => ({error: 'Unavailable'})};
            },
        });
        const button = element('recurring-authorize');
        await button.click();
        assert.equal(opens, 0);
        element('recurring-consent').checked = true;
        element('recurring-consent').change();
        await button.click();
        await checkout.handler({razorpay_payment_id: 'pay_fixture', razorpay_signature: 'fixture'});
        assert.equal(button.textContent, 'Retry authorization confirmation');
        await button.click();
        assert.equal(opens, 1);
        const retry = calls.filter(c => c.url === '/confirm/');
        assert.equal(retry.length, 2);
        assert.equal(retry[0].body, retry[1].body);
        assert.equal(button.disabled, true);
        assert.equal(button.textContent, 'Authorization verified');
    });
}
