---
status: active
owner: project
updated: 2026-09-29
tags: [billing, configuration, receipts, deployment]
---

# Billing provider configuration and readiness

## Frozen seller and explicit tax settings (2026-09-28)

Superseded configuration status: the 29 September checkpoints below record the
confirmed seller installed and live catalog bound. Earlier entries are historical.

Deployed to production web and mail workers, now on `rokkad:billing-paused-99bda8c1cb27`
with billing/sending paused. No schema, provider or financial-record changes.
Seller fields remain unconfigured. New live offers/orders require all of:

| Setting | Required preparation |
| --- | --- |
| `BILLING_TAX_RATE` | Explicit `0` for this unregistered-supplier pilot; base default is empty |
| `BILLING_SELLER_NAME` | Reviewed legal seller name; not a credential or PAN |
| `BILLING_SELLER_ADDRESS` | Reviewed billing address |
| `BILLING_SELLER_TAX_STATUS` | Explicit `unregistered`; other treatments currently rejected |

The owner subsequently confirmed the seller status/address in the
[JSK pilot review](../plans/monthly-billing-pilot.md#confirmed-jsk-pilot-review-2026-09-28).
The fields remain empty in production until the configuration step.
`check_billing_configuration`
reports configuration blockers without printing seller/address values; it never
asserts launch readiness. Test/rehearsal settings explicitly retain 18% and existing
financial records are not rewritten.

New live checkout and recurring binding snapshots freeze seller details. Recurring
invoices inherit that binding. HTML/PDF invoices and receipts show the saved issuer
and no-GST wording; historical invoices retain recorded tax and never borrow current
seller settings. New authorization rejects stale/missing seller terms; payment
recovery and cancellation remain available with matching provider credentials.

Changing current seller/tax settings does not update an existing mandate or its
frozen future-cycle terms. A legal seller or GST-status change therefore needs an
explicit collection/transition review before further billing, rather than an env
edit alone. Preserve already received payment evidence throughout that review.

The paused deployment passed restricted runtime and unchanged-evidence checks;
no migration was needed. Next: review and configure the live seller/catalog.
Invoice readiness does not resolve remaining
provider outcomes, mandate duration, pilot Workspace or live activation approval.
See the [decision](../adr/2026-09-28-frozen-billing-seller.md) and
[deployment evidence](billing-paused-release-20260928.md#seller-invoice-update-deployed-2026-09-28).

Validation: 221 billing/mail regressions and four checkout retry tests pass, with
mocked provider/mail transports. The unsaved one-page PDF preview was text-checked
and visually inspected; schema-drift, boundary and documentation checks pass.
Private local evidence: `outputs/seller-billing-regressions.log` and
`outputs/seller-invoice-20260928/`. The preview is not an issued invoice.

## Confirmed seller configuration (2026-09-29)

Applied at **11:45 IST** to the existing shared environment consumed by web and
mail workers. The only changes are:

```dotenv
BILLING_TAX_RATE=0
BILLING_SELLER_NAME=Rajesh Rathod H
BILLING_SELLER_ADDRESS=11, 9th Cross Street, Rajiv Gandhi Nagar, Vellore, Tamil Nadu, India
BILLING_SELLER_TAX_STATUS=unregistered
```

Web was recreated on its current Party/Loans image
`rokkad:party-loan-pages-20260929-5143b3441f2b`; workers keep the billing-compatible
`rokkad:billing-paused-99bda8c1cb27`. Compose, settings modules, credential files,
watchdog command, timers and images were preserved. No schema or database mutation.
The server-private `billing-seller-20260929/` folder holds the previous environment,
candidate, bounded apply/rollback evidence and sanitized final report.

Both runtimes validate the exact seller through `live_seller()` and an unsaved
monthly offer through `_offer(..., mode="live")`: INR 1,499 total, zero GST, six
members. Prepared duration remains 12 monthly collections, quantity one. Restricted
read-only fingerprints of every subscriptions table match before/after; JSK's
trial and full access are unchanged. Web catalog remains private, HTTPS login is
200, zero restarts; worker queue flags/due messages are zero. Dispatch remains
disabled and monitoring timers active.

Provider mode remains disabled, all purchase/trial/recurring/sending gates false.
No live key or webhook secret is present, no provider request or charge occurred,
and no plan/binding was saved. The owner confirmed keys are not generated yet.
The approved-website Live Mode Generate Key page is handed to the owner; credential
generation must be completed by the owner under the browser tool policy. Save the
CSV outside the repository/OneDrive; never paste credentials into chat or logs.
Subsequent protected import, authenticated GET-only plan verification, explicit
server credential placement and live catalog binding remain pending. Test keys
and test evidence stay isolated; key availability is not launch approval.

Local sanitized results: `outputs/live-seller-20260929/prepare.json` and
`outputs/live-seller-20260929/apply.json`.

## Live keys and bound monthly catalog (2026-09-29)

Owner-generated live keys authenticated successfully at **11:51 IST** against the
official Payments, Plans and Subscriptions GET APIs; all initially returned empty
collections. Current-user DPAPI encryption and round-trip verification passed in
`%LOCALAPPDATA%/Rokkad/private/live/razorpay-live.dpapi`, with inheritance disabled
and access limited to that Windows user. The original CSV remains in Downloads;
it was not copied into the repository or deleted. No secret values are in evidence.

Keys are staged at `/root/rokkad-billing-live.env`, root-owned mode 0600, transferred
only over encrypted SSH. This file is **not** referenced by persistent Compose,
systemd workers or watchdog. It was used only by bounded preparation processes with
explicit live mode and all checkout/trial/recurring/sending gates false. Persistent
web and workers remain provider-disabled; images and environment are unchanged.

One durable local dispatch record preceded a single POST creating only a provider
plan. GET verification confirmed `plan_ThkgxD2zC0o8FL`: **monthly, interval 1,
INR 149900 paise**, Rokkad Workspace Monthly. Subsequent provider Payments and
Subscriptions listings were empty. An uncertain plan attempt must be reviewed by
GET/reference, never automatically reposted. See the official
[plan creation contract](https://razorpay.com/docs/api/payments/subscriptions/create-plan/).

An unsaved restricted production preview verified that provider plan against the
confirmed zero-tax seller and six-member monthly offer. No existing superuser was
available. The owner explicitly approved a dedicated temporary operator for this
catalog operation. User **10**, `fw019_catalog_operator_20260929`, has no usable
password or email; it created separate Plan **2** and live binding **1** through
`review_plan_binding`/`bind_plan`. Binding records its actor and reason. The operator
is now inactive with staff/superuser flags false, verified by an independent cleanup
pass and final read-only review. No existing owner or staff account was elevated.

Only the separate plan/binding and operator/profile were added. Shared Plan 1 and
every other subscription-table fingerprint remain unchanged. The new plan preserves
the existing non-seat internal values, sets six members, zero extra-user price and
zero new-trial days. Annual 14990 is a working unpublished value; no annual binding
or purchase path exists. It does not accept legacy feature/limit values as product
claims or authorize overages. Twelve collections with quantity one belong to future
agreement preparation; no agreement was created or assigned to JSK.

At **11:58 IST**, all three operating Workspaces pass private-catalog checks and
retain full access on their original trials. Agreement/invoice/payment/receipt
counts remain zero. HTTPS login is 200; mail queue flags/due messages are zero,
dispatch marker absent, sending paused. The operator is disabled. Because persistent
provider mode is disabled, its inventory reports the live binding as another mode;
a read-only in-memory live-mode inventory is clean. Keep that expected diagnostic
distinct from test/live mixing; no Test Mode data was promoted or rewritten.

Next: prepare the mode-specific signed HTTPS webhook, load reviewed credentials
consistently into web/workers while keeping purchase gates false, and review the
receipt worker's sending scope before collections. Existing Test Mode uncertainties,
failure/recovery/held-period acceptance and JSK's unexpired trial are still open.
No real collection or activation was authorized.

Sanitized local evidence: `outputs/live-key-verification-20260929.json`,
`outputs/live-monthly-plan-20260929.json`, `outputs/live-credential-placement-20260929.json`,
`outputs/live-catalog-prepared-20260929.json`, `outputs/live-catalog-applied-20260929.json`
and `outputs/live-catalog-verified-20260929.json`. Server-private records remain in
`billing-seller-20260929/` under the deployment folder. Older seller preflight helpers
asserted one plan; do not rerun them unchanged after this intentional catalog addition.

## Monthly pilot commercial preparation (2026-09-28)

The owner selected monthly-only INR 1,499 with six total members and
operator-prepared agreements; seller name **Rajesh Rathod H**. Personal-PAN/no-GST
replies and the account's unsupported GST-linking page inform a commercial-invoice
draft with no GST collected, pending final status/address review. An unsaved
read-only offer preview produced 149900 paise and zero tax at 15:19 IST.

That preparation identified missing seller details and an implicit tax default.
The deployed implementation above addresses them; reviewed live configuration
remains. See [pilot preparation](../plans/monthly-billing-pilot.md).

## Paused production candidate (2026-09-28)

The full billing source at `4a131587ee80` was deployed at **14:55 IST**, after a fresh
verified backup and all six subscriptions migrations. Production retains its three
trials and unchanged billing/lending fingerprints; new recurring tables are empty.
Runtime/RLS, grants, owner/public pages and static checks pass. Billing and sending
remain explicitly disabled. Mail worker images were aligned at **15:03 IST**;
feedback/recovery/health passed and remain active, with dispatch paused. Restricted
runtime, unchanged attempts and clear queue checks passed at **15:05 IST**. See the
[deployment and rollback record](billing-paused-release-20260928.md#deployment-result).
Live activation remains separately gated by provider/commercial acceptance.

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

The paused web deployment above completes the initial release/evidence review;
worker alignment is also complete. Bounded pilot acceptance remains. Actual
activation still depends on commercial terms, protected live credentials/catalog,
HTTPS webhook and operations acceptance, receipt dispatch scope, and unresolved
provider renewal/failure/held-period acceptance. Existing Test Mode uncertainties
must be preserved and never promoted to live.

## Live catalog preparation (2026-09-28)

The deployed catalog increment requires `BILLING_ALLOW_TRIAL_START=False` as well as
checkout/recurring false during live preview/binding. With checkout and trial signup
paused, the generic owner catalog hides active plans and links to prepared recurring
terms. Production web and workers now use `rokkad:billing-paused-99bda8c1cb27`,
verified at 16:07 IST with billing/sending paused and unchanged records.
Do not enable trial signup or one-off checkout for the operator-prepared pilot.
See the [decision](../adr/2026-09-28-private-operator-billing-catalog.md).

The catalog command supports explicit live plan review/registration. Use matching private live settings,
checkout/trial/recurring switches off, and a separately reviewed production database.
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
