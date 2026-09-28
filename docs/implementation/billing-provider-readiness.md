---
status: active
owner: project
updated: 2026-09-28
tags: [billing, configuration, receipts, deployment]
---

# Billing provider configuration and readiness

## Live recurring workflow support (2026-09-28)

The existing recurring services now support immediate-start live agreements with
matching saved mode, explicit credentials and owner/Workspace authority. The new
authorization flag remains default-off. Live creation/authorization also require a
webhook secret and no test or unclassified billing evidence. Catalog registration
continues to require both purchase flags paused; enablement is a separate launch
action after all applicable release gates are accepted.

Pausing `BILLING_RECURRING_ENABLED` blocks new creation and Checkout authorization,
while configured same-mode confirmation, GET-only uncertain-creation reconciliation,
verified paid-cycle recovery, cancellation and explicit held/refund access review
remain available. Cancellation still commits a single dispatch claim; uncertain
results are fetched, never blindly reposted. Live consent/receipts omit Test Mode
wording. Scheduled live starts and live reservation release remain blocked.

This checkpoint uses only fictional live-mode fixtures and mocked provider/SES
responses. No live keys, live plan registration, provider writes, emails, production
deployment or migration occurred. The working offer and illustrative tax remain
unpublished. `live_recurring_supported=true` describes code capability;
`launch_ready=false` remains deliberate. See the
[decision](../adr/2026-09-28-mode-matched-live-recurring-workflows.md).

Validation: 135 existing billing regressions passed; after completing the live
receipt fixture settings, the final 63-test live/cycle run passed (28 live-mode
cases and 35 existing cycle cases). All provider and SES calls were mocked. The
two browser authorization-retry tests and documentation/whitespace checks pass.
The live suite is included in CI; no schema change is required.

Next: prepare a reviewed production release with both purchase flags off, inventory
legacy billing evidence, and define the bounded pilot/rollback procedure. Actual
activation still depends on commercial terms, protected live credentials/catalog,
HTTPS webhook and operations acceptance, receipt dispatch scope, and unresolved
provider renewal/failure/held-period acceptance. Existing Test Mode uncertainties
must be preserved and never promoted to live.

## Live catalog preparation (2026-09-28)

The catalog command supports explicit live plan review/registration. Use matching private live settings,
both checkout/recurring switches off, and a separately reviewed production database.
Never use the populated Test Mode rehearsal database for this step.

```text
python manage.py prepare_recurring_agreement --actor-id <platform-admin> bind --mode live --plan-id <local-plan> --cycle monthly --provider-plan-id <existing-live-plan> --reason "Reviewed launch catalog" --preview
```

Preview performs a provider GET and prints verified local price/tax/seat terms,
without saving. After reviewing those exact terms, the same command without
`--preview` registers only the immutable local catalog mapping. It does not create
a Razorpay plan or subscription, charge money, publish the offer or enable Checkout.
Both operations require platform authority, explicit matching mode and a reason;
Test Mode defaults remain compatible. Test previews may run while creation is paused.
Live preparation rejects test bindings and test/unclassified one-off invoices before
provider access. Both modes reject conflicting bindings; evidence and offer changes
are rechecked before persistence. Provider amount, currency and interval must match.

No live keys were loaded, live plan created/bound, production migration applied or
provider-side write made in this increment. Commercial tax and launch terms remain
unapproved. The [catalog decision](../adr/2026-09-28-live-recurring-catalog-preparation.md)
separates this capability from supported live agreement/payment workflows.
The 39-test regression run and final 13-test catalog run pass; CI includes the
catalog suite. No schema change is needed.

GET-only provider checks at **14:14 IST** still show annual agreement 5 Active,
one of two cycles paid, final payment Created and invoice Issued. Scheduled
agreement 6 is Expired with zero paid cycles and its INR 5 token still Created.
Local records were unchanged. Ticket-number inbox search still found only the
11:49/11:50 acknowledgements for 21146138/21146171. Preserve both uncertainties;
do not retry, cancel, refund or release their reservations based on this check.

Provider approval and a matching configuration do not constitute launch acceptance.
New billing configuration uses `BILLING_PROVIDER_MODE=disabled|test|live`, default
disabled, alongside the existing key pair, webhook secret and separate checkout/
recurring activation switches. Keep web and worker mode consistent. Isolated
`billing_rehearsal` selects test explicitly; automated tests use dummy credentials.
Recurring workflows now support the matching saved mode as described above.
No live keys were loaded and no production configuration was changed.

```text
python manage.py check_billing_configuration
python manage.py check_billing_configuration --include-evidence --require-configured
```

Use the appropriate restricted runtime settings. The first command is offline;
the second additionally reads aggregate local evidence. Neither contacts Razorpay,
sends mail, changes records or prints credentials/contact details. `configuration_ready`
means mode/key/webhook settings agree. `launch_ready` remains false; provider
acceptance, reviewed live deployment, callbacks/monitoring, receipt delivery,
commercial terms and approved activation must be checked separately. Dedicated SES
readiness is reported separately from shared Django mail.

Wrong or disabled mode prevents SDK construction/signature acceptance, and webhook
processing returns 503 before persisting an event. Pausing only new recurring
authorization preserves configured mode-matched recovery. New one-off invoice snapshots
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

## Addressed receipt command and paid fixture (2026-09-28)

The controlled path is implemented in `rehearse_billing_receipt`. Its default is a
read-only preview. It accepts one UUID and exact saved inbox, with active billing
owner authority and a short operator reference. The runtime must be explicitly
isolated Test Mode, loopback PostgreSQL, and a verified restricted role. General
mail settings still gate sending; this command does not enable or configure SES.
Normal dispatch continues to refuse test receipts. Each explicit test send records
an audit with its committed Attempt; uncertainty and even throttling never cause
an automatic second test send. See the
[decision](../adr/2026-09-28-controlled-test-receipt-delivery.md).

```text
python manage.py rehearse_billing_receipt --delivery <uuid> --actor-id <owner-id> --recipient <chosen-inbox> --reference RECEIPT-20260928-01 --preview-html <new-private-file.html>
```

Use the isolated worker settings. Add `--send` instead of `--preview-html` only for
the reviewed single message after the worker is ready and sending is authorized.
Never run the general dispatch queue as part of this rehearsal. Feedback must be
correlated to this exact attempt before acknowledging its private SQS event.

Actual fixture: Workspace 8 (`receipt_rehearsal`), agreement 7,
`sub_ThNGXGUnXOsYKw`, invoice `inv_ThNGY1xgSjZrOd`, payment
`pay_ThNJQMGDDN7b8u`. The ordinary test owner authorized the official domestic test
card through Checkout; the app verified the signature and separately recovered the
captured monthly payment. Invoice 10 / cycle 8 records INR 1,768.82, with illustrative
18% tax and six total seats. Its contact was set to **admin@rokkad.com** in the new
Workspace billing account before capture. Delivery is
`eb388c08-b030-410a-8be5-6dadf747287c`, initially queued with zero attempts. Exact subject:
`[TEST] Rokkad payment received: RCY-inv_ThNGY1xgSjZrOd`.
`outputs/receipt-rehearsal-ready.html` is the reviewed receipt content.
Reconciliation replay preserved all invoice/payment/cycle/delivery counts.

Ten invoices/payments/receipts and eight cycles now exist. The older annual
and scheduled attempts still report Created and were not retried/cancelled. New
recurring authorization is off again on the review server; local mail remains off.
The new agreement was Active before receipt-rehearsal cleanup. No live funds or
real card were used. [Official test-card/OTP guidance](https://raw.githubusercontent.com/razorpay/markdown-docs/master/payments/payments/test-card-details.md)
was checked before this new authorization.

All 56 targeted receipt/configuration/mail tests passed, including ten new cases
for runtime isolation, exact addressing, authority, audit rollback, paused sending,
suppression, replay and uncertain/throttled attempts. The new suite is in CI.
The server-worker archive contains application source only. Automatic approval
review initially blocked setup and later credential transfer; the owner explicitly
authorized both. The separate image is built. A temporary root-only environment
contains the restricted local database credential and Razorpay Test Mode keys;
its independent signing key was generated on the server. SES credentials remain
server-private. An encrypted SSH connection listens only on `127.0.0.1:55419`.
The server readiness check has no blockers, sending is disabled, and the exact
receipt preview passed against the actual restricted rehearsal database.

The owner then explicitly approved the single email. SES accepted one audited
attempt; targeted SQS reconciliation recorded **Send** and **Delivery**, with no
unrelated messages acknowledged. Delivery is **delivered**, attempt count **1**,
with no error. The app visibly reports **Delivered to recipient mail server**;
evidence is in `outputs/receipt-delivery-evidence-20260928.json` and
`outputs/receipt-rehearsal-delivered.png`. This is recipient-server acceptance,
not proof of inbox placement, authentication headers or a successful reply.
Those checks remain open; do not send another receipt to establish them.

The temporary credential file was removed and the SSH process/listener stopped.
The dispatch marker is absent and only the existing health timer is active.
Production containers/timers are unchanged; no general dispatch was enabled.
Fresh provider invoice inspection found exactly this one paid invoice, then the
ordinary owner cancellation workflow cancelled agreement 7 only. Paid period and
all financial/receipt counts are unchanged. Nine older receipts remain queued;
both older unsettled mandates remain untouched. Production activation and live
recurring acceptance remain separate work.

## Received receipt and billing reply acceptance (2026-09-28)

The exact receipt was found in admin@rokkad.com's Inbox. Sender, amount, invoice,
paid period and explicit no-real-charge notice match the saved invoice and render.
Gmail shows Reply-To billing@rokkad.com, mailed-by bounce.notify.rokkad.com,
signing domain notify.rokkad.com and TLS. Its original message summary reports
SPF/DKIM/DMARC **PASS** and delivery after three seconds. No receipt was resent.

Owner-approved reply `RECEIPT-REPLY-20260928-01` was sent at 13:40 IST to the
automatically selected billing address, with only a labelled test explanation.
Admin and billing share the same Google mailbox, so the Sent copy and thread label
were insufficient delivery evidence. Google Admin > Reporting > Email Log Search,
filtered by the exact reply Message-ID and billing@rokkad.com, confirms one matching
message and **1/1 delivered**, **Delivered to Gmail mailbox** at **13:40:50 IST**
after **0.93 seconds**, with TLS-enabled receipt. No alias/routing settings changed.
Private screenshot evidence:

- `outputs/receipt-inbox-authentication-20260928.png`
- `outputs/receipt-reply-sent-20260928.png`
- `outputs/receipt-billing-reply-delivered-20260928.png`

This closes controlled paid-test-receipt content, inbox, authentication and reply
acceptance. Before monitored activation, review deployed source/worker versions,
source/DLQ counts, IAM exception cleanup, alerts and exact send scope. Google Admin
currently shows Workspace prepayment pending with 12 trial days remaining; owner
account billing completion is needed for ongoing monitored-inbox continuity.
General dispatch and live recurring remain disabled; no payment was initiated here.
