---
status: active
owner: project
updated: 2026-09-28
tags: [billing, configuration, receipts, deployment]
---

# Billing provider configuration and readiness

Provider approval and a matching configuration do not constitute launch acceptance.
New billing configuration uses `BILLING_PROVIDER_MODE=disabled|test|live`, default
disabled, alongside the existing key pair, webhook secret and separate checkout/
recurring activation switches. Keep web and worker mode consistent. Isolated
`billing_rehearsal` selects test explicitly; automated tests use dummy credentials.
Current recurring workflows still reject live mode. No live keys were loaded and
no production configuration was changed in this increment.

```text
python manage.py check_billing_configuration
python manage.py check_billing_configuration --include-evidence --require-configured
```

Use the appropriate restricted runtime settings. The first command is offline;
the second additionally reads aggregate local evidence. Neither contacts Razorpay,
sends mail, changes records or prints credentials/contact details. `configuration_ready`
means mode/key/webhook settings agree. `launch_ready` remains false; provider
acceptance, live recurring implementation, callbacks/monitoring, receipt delivery,
commercial terms and approved activation must be checked separately. Dedicated SES
readiness is reported separately from shared Django mail.

Wrong or disabled mode prevents SDK construction/signature acceptance, and webhook
processing returns 503 before persisting an event. Pausing only new recurring
authorization preserves configured Test Mode recovery. New one-off invoice snapshots
freeze mode; mismatched key replay/capture/refund is refused. Recurring invoices use
the saved binding mode. Existing snapshots stay immutable: old unclassified one-off
records remain recoverable in test but cannot be silently treated as live. Do not
switch a populated rehearsal database to live. A mode conflict or unclassified
invoice in the inventory blocks `--require-configured` when evidence is requested.

Actual read-only rehearsal check at **12:31 IST** found two test plan bindings,
five held reservations, zero unknown creation outcomes, zero webhook failures,
two unclassified historical one-off invoices and nine queued receipts. The latter
two invoices were not rewritten. Seven recurring receipt previews showed `[TEST]`
and the no-real-money notice. Rendering used explicit approved sender/origin values
in a local preview context because this isolated runtime intentionally has incomplete
SES settings; its actual configuration report still shows those mail blockers.
Every queue row remained unchanged. Evidence:
`outputs/billing-configuration-readiness-20260928.json` and
`outputs/check_billing_mode_readiness.py`. Runtime role is not superuser/BYPASSRLS.

Normal SES dispatch refuses test/unclassified receipts before claiming an attempt.
It requires both explicit live process mode and recorded live invoice mode. Local
capture remains available; it changes queue status to preview-only if explicitly
used through the capture command. The read-only check above rendered directly and
did not capture/change the queue. A separate, recipient-authorized Test Mode receipt
delivery rehearsal remains work; never bulk-send the fictional test queue.

AWS case **179042575700203** now confirms SES production access in Mumbai as of
**28 September 2026 11:20:42 IST**, quota **50,000/day**, rate **14/second**, sandbox
exit immediate. This was read after owner sign-in, without changing AWS settings.
General dispatch stays disabled. Recheck scoped IAM (including the expired temporary
recipient exception), workers, feedback/recovery, suppression and SQS/DLQ before
bounded activation. Prior sender probes are not paid-receipt delivery evidence.

See the [mode decision](../adr/2026-09-28-explicit-billing-provider-mode.md),
[mail runbook](platform-mail.md) and [launch gates](../plans/subscription-monetization-rollout.md).

Validation covered 218 billing/mail tests. The broad run passed 216; two mail UI
fixtures required ordinary test static storage instead of a missing manifest.
The final 47-test rerun passed, including both corrected cases and the configuration/
receipt boundaries. Live-send transport tests use explicit dummy live mode and
mocked payment/SES providers. No live network sends occurred. Documentation links
and scoped whitespace checks also pass.

## Receipt rehearsal preparation after the checkpoint

The owner selected **admin@rokkad.com** for the next controlled receipt rehearsal.
Use it as the billing contact when preparing a new isolated Test Mode checkout;
do not rewrite existing invoice snapshots or substitute a destination on their
queued deliveries. The next bounded implementation needs an explicit single-
delivery Test Mode send path with exact recipient matching, ordinary suppression,
attempt/feedback evidence and no uncertain-send replay. It must not turn on the
general queue. Prepare the exact new paid receipt before requesting its send.

Read-only server checks at **12:44 IST, 28 September 2026** found the dedicated
SES configuration ready, credentials mode 0600, no dispatch marker, dispatch/
feedback/recovery timers disabled and inactive, health timer enabled and active,
and zero sticky alerts. The production mail queue had zero due messages and no
flags: one delivered invitation and the two previously accepted bounce/complaint
fixtures. No service or configuration was changed; no message was sent. IAM and
source/DLQ counts were not revalidated by this check.

A read-only transaction rendered invoice 9 from agreement 5 as a content reference:
`outputs/receipt-rehearsal-draft.html` and
`outputs/receipt-rehearsal-preflight-20260928.json`. It shows the simulated annual
INR 17,688.20 receipt, TEST subject/body and billing Reply-To. The invoice's saved
recipient remains fictional, all nine rehearsal receipts remain queued, and the
selected source has zero send attempts. This preview is neither a newly paid
fixture nor proof of delivery to the chosen inbox. Local rehearsal settings still
contain no SES credentials; the server's readiness does not make this local
runtime send-ready. Keep the existing annual/scheduled provider uncertainties
and support tickets separate from this preparation.
