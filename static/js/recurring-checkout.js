/* A successful callback is confirmed again on retry; never open another Checkout. */
(() => {
    const button = document.getElementById('recurring-authorize');
    if (!button) return;
    const consent = document.getElementById('recurring-consent');
    const result = document.getElementById('recurring-result');
    const token = document.querySelector('[name=csrfmiddlewaretoken]').value;
    let callback = null;
    let busy = false;
    consent.addEventListener('change', () => { button.disabled = busy || (!callback && !consent.checked); });
    async function post(url, body) {
        const response = await fetch(url, {method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': token}, body: JSON.stringify(body)});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Verification is unavailable. Refresh status or contact support.');
        return data;
    }
    function ready() {
        busy = false;
        button.disabled = !callback && !consent.checked;
    }
    async function confirm() {
        busy = true;
        button.disabled = true;
        try {
            await post(button.dataset.confirmUrl, callback);
            result.textContent = 'Authorization verified. Paid periods are checked separately. Refresh agreement status to see updates.';
            button.textContent = 'Authorization verified';
        } catch (error) {
            result.textContent = error.message;
            button.textContent = 'Retry authorization confirmation';
            ready();
        }
    }
    button.addEventListener('click', async () => {
        if (busy) return;
        if (callback) { await confirm(); return; }
        if (!consent.checked) return;
        busy = true;
        button.disabled = true;
        try {
            const options = await post(button.dataset.startUrl, {});
            options.handler = async response => {
                callback = {razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_signature: response.razorpay_signature};
                await confirm();
            };
            options.modal = {ondismiss: () => {
                if (!callback) {
                    result.textContent = 'Checkout closed. Refresh status before trying again if you completed authorization.';
                    ready();
                }
            }};
            new Razorpay(options).open();
        } catch (error) { result.textContent = error.message; ready(); }
    });
})();
