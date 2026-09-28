---
status: active
owner: project
updated: 2026-09-28
tags: [billing, razorpay, rehearsal, operations]
related: [../plans/subscription-monetization-rollout.md, ../flows/subscription-checkout.md]
---

# Isolated Razorpay billing rehearsal

This Windows-only rehearsal exercises Orders checkout and the implemented
recurring flow in fictional Workspaces. It does not activate production billing.

## Environment and boundaries

- Dedicated local database: `rokkad_baseline_rehearsal_billing_20260927`.
  Created empty; no customer or borrower data was copied. All migrations through
  Subscriptions 0012 were initially applied using the owner-only migration settings;
  the recurring increments subsequently applied 0013-0016 in this same database.
- Web and callback settings: `django_project.settings.billing_rehearsal`.
  Restricted runtime grants reuse the existing non-superuser, non-BYPASSRLS role.
  Startup checks passed with no pending migrations. Expected deployment warnings
  concern loopback HTTP/cookies, disabled email and the unused debug toolbar.
- Web: `http://127.0.0.1:8083`. Only the fictional ordinary owner can purchase for
  the `billing_rehearsal` Workspace. The unpublished test plan explicitly sets
  INR 1,499/month, INR 14,990/year and six total members. The existing 18% test tax
  yields INR 1,768.82 or INR 17,688.20; production tax treatment remains undecided.
- Settings reject any database outside `rokkad_baseline_rehearsal_billing_*`,
  a non-loopback database host, or non-Test Mode Razorpay keys. DEBUG and trial
  start are off. Separate cookie names and a local signing key isolate sessions.
  The banner explicitly identifies fictional data and simulated payments.
- Email dispatch is off, SES credentials are blank, Django email is in memory,
  and file storage is local. Paid-receipt intent may be queued in this database;
  it must not be dispatched to fictional recipients.

## Private credentials

`scripts/billing_rehearsal_credentials.py` decrypts current-user Windows DPAPI
files only in process memory. The keys are in
`%LOCALAPPDATA%\Rokkad\private\razorpay-test.dpapi`; a separate
`billing-rehearsal.dpapi` contains the Django and webhook signing secrets.
No credential values belong in repository files, logs, screenshots or chat.
DPAPI requires the original Windows user token; the sandbox token could not
decrypt the file, while execution under the owner account succeeded.

A temporary private `billing-webhook-secret.txt` in that same directory is the
owner's manual dashboard-entry handoff. The plaintext handoff was removed after the
owner configured the webhook; the encrypted original is retained. Browser credential-entry
rules require the owner to enter and submit the webhook secret.

## Public callback

`scripts/billing_rehearsal_webhook.py` serves port 8893 on loopback. Its WSGI
wrapper forwards only signed POSTs to `/subscriptions/webhook/razorpay/`, with
an exact path, no query, bounded Content-Length/body and constant-time HMAC.
Cookies, authorization and forwarded hosts are discarded; the Django handler
also verifies the raw-body signature and records/reconciles event identities.
The wrapper never exposes login, checkout, admin, static files or other URLs.

The owner explicitly approved a temporary Cloudflare tunnel carrying simulated
payment IDs, amounts and fictional contact details. The first automatic review
rejected this transmission without destination-specific approval; the owner
then supplied that approval. The installed official `cloudflared` executable
connects only to `http://127.0.0.1:8893`, with no autoupdate. Never tunnel port 8083.
The temporary URL is in ignored `outputs/billing-rehearsal-tunnel.err.log`.
It is session-specific, not a stable callback for deployment.

In Razorpay **Test Mode**, configure that HTTPS origin plus the exact callback
path, the separate signing secret, and these implemented events only:
`payment.captured`, `payment.authorized`, `payment.failed`, `refund.processed`,
and the now-implemented recurring lifecycle events: `subscription.authenticated`,
`subscription.paused`, `subscription.resumed`, `subscription.activated`,
`subscription.pending`, `subscription.halted`, `subscription.charged`,
`subscription.cancelled`, `subscription.completed`, `subscription.updated`.
The September 28 recurring rehearsal configured all fourteen Test Mode events.
Disable this temporary dashboard webhook before stopping the tunnel after acceptance.

## Start and verify

Set `ROKKAD_REHEARSAL_DB_NAME` explicitly and
`DJANGO_SETTINGS_MODULE=django_project.settings.billing_rehearsal` in a process
running as the Windows user who saved the DPAPI files. Run
`python scripts/start_web.py` for runtime/schema checks, then:

```powershell
python manage.py runserver 127.0.0.1:8083 --noreload --insecure --settings django_project.settings.billing_rehearsal
python scripts/billing_rehearsal_webhook.py
```

Use the project's `.venv314\Scripts\python.exe`. Each server needs a separate
process. `--insecure` is Django's static-file switch for this loopback-only server
with DEBUG off, not a relaxation of provider TLS checks. Start helpers hidden
when automated. Current process IDs are in ignored
`outputs/billing-rehearsal-processes.json`; verify command lines before stopping
them. Never stop unrelated Rokkad rehearsals.

## Evidence and remaining acceptance

Transport-only synthetic checks passed through HTTPS: unrelated path 404,
unsigned callback 400, signed `payment.authorized` event 200 and its replay 200.
This synthetic event is explicitly identified as
`rehearsal-synthetic-transport-20260927`; it grants no access and is not evidence
of an actual provider payment or provider-generated webhook.

Focused helper and rehearsal-settings tests passed, covering live-key,
database/host isolation, callback routing/signatures, header stripping, disabled
delivery and the opt-in billing banner. Checkout browser login succeeds with the
fictional ordinary owner and shows the agreed monthly/annual base prices.

Provider-generated acceptance now passed using Test Mode wallet payments:

| Check | Observed result |
| --- | --- |
| Failed international card attempt | Processed failure webhook; zero paid records, terms or receipts before success |
| Monthly capture | INR 1,768.82; one paid invoice/payment/monthly term and one queued receipt |
| Duplicate capture and new event ID | No additional payment, term or receipt; end date unchanged |
| Conflicting reused event ID | HTTP 400; original record unchanged |
| Annual capture | INR 17,688.20; second term starts at monthly end and adds twelve months |
| Browser confirmation outage | Webhook committed annual capture; actual provider reconciliation succeeded without duplicate extension |
| Partial/full refund of older monthly purchase | INR 100 + INR 1,668.82; two verified processed refunds, unchanged newer annual access |
| Refund replay under new event IDs | No duplicate refund rows or increased refund total |
| Final database | Two paid invoices and two payment records (monthly payment refunded), two queued receipts, six-member limit, active through 2027-10-27, zero failed webhook rows |

The initial generic Visa card was rejected as international. Netbanking and other
card authentication attempts remained incomplete; do not infer those methods are
accepted from wallet success. The successful wallet flow used only a fictional
contact and a simulated OTP. No bank/customer credentials or real money were used.

Browser inspection exposed stale invoice template fields. Dashboard/detail now
use `status`/`paid_at`; annual details use the frozen checkout cycle and do not
invent an invoice period. After a provider callback, the checkout button now
retries only confirmation with the same IDs/signature and disables cycle changes.
Two Node tests (`node --test scripts/test_checkout_confirmation.js`) exercise
provider-error and network-error recovery against the actual checkout script.
Real local invoice rendering verified paid state, annual description and date.

Sanitized evidence is in ignored `outputs/billing-rehearsal-*-evidence.json`.
Provider IDs remain in isolated records/local evidence, not published docs.
Actual receipt delivery, card/netbanking acceptance, rollback/missing-event
scenarios beyond this observed confirmation failure, final refund review, live
configuration and automatic recurring lifecycle acceptance remain outstanding.
Live checkout, live keys, production plans and general email dispatch remain off.

Cleanup completed September 27: the temporary webhook visibly shows Disabled in
Razorpay Test Mode. Its Cloudflare tunnel and local callback processes are stopped;
port 8893 is no longer listening. The isolated database and local web server on
port 8083 remain available for review. The temporary plaintext signing-secret
handoff file was removed; the encrypted private credentials remain available.
Any further provider acceptance needs a fresh temporary tunnel and webhook setup.

The subsequent [recurring foundation](recurring-agreements.md) applied migrations
0013/0014, then paid-cycle migrations 0015/0016, to this same isolated database
and restarted the local review server. Existing
Orders payment/refund/receipt evidence was retained. Do not reuse this fixture's
future paid term for an immediate recurring agreement without transition review.

## Recurring provider continuation (2026-09-28)

A fresh fictional `recurring_rehearsal` Workspace completed actual recurring
initial authorization/capture, signed webhooks, replay, owner invoice recovery and
cancellation. One paid monthly cycle covers 28 September 00:01:43 IST through
28 October 00:00 IST, with six members. Cancellation preserves that paid term and
the held agreement reservation. The catalog fixture operator has an unusable
password and is now inactive; the ordinary owner was not promoted.

The accelerated failure control issued a future invoice but left its payment
attempt Created. No completed failure or successful subsequent collection was
observed; full renewal acceptance remains open. See the
[recurring evidence and remaining work](recurring-agreements.md#actual-provider-rehearsal-2026-09-28).

Cleanup repeated September 28: the fourteen-event Test webhook is Disabled,
tunnel/callback stopped, recurring authorization flag false. The review web server
remains on 8083. Final isolated totals are three invoices/payments/queued receipts,
one recurring cycle, zero failed webhook rows. Email delivery remains disabled.
Provider plan and cancelled subscription evidence are retained; no live or
production resources were changed. Any renewed provider test requires a fresh
temporary callback setup; this cancelled agreement cannot authorize another cycle.

The subsequent `renewal_followup` diagnostic used a fresh agreement and kept the
webhook disabled. Actual initial capture was recovered through the owner page;
one more invoice/payment/receipt and recurring cycle were recorded. The single
accelerated success attempt captured after about six minutes, but its future paid
period was rejected by the app's started-period guard. Local authorization is
disabled again; the provider agreement was cancelled only after capture settled.
See the
[diagnostic continuation](recurring-agreements.md#renewal-diagnostic-continuation-2026-09-28).
That checkpoint had four invoices/payments/queued receipts and two recurring cycles;
no emails were dispatched. Do not confuse the local feature flag with provider
mandate cancellation.

The reviewed future-payment increment subsequently recovered that captured renewal
once as financial evidence with access held for review. Its exact 28 October to
28 November period is retained. Repeated owner recovery creates no duplicates,
and independent restricted-role comparison confirms every existing Subscription
field and entitlement row is unchanged. Current totals are five invoices/payments/
queued receipts and three recurring cycles. Receipt HTML and owner hold wording
were checked; email remains disabled. Both test mandates remain cancelled, and
new authorization/webhook/tunnel remain off. Applying held access requires the
explicit reviewed command; replay or reaching the start date cannot activate it. See
[current acceptance](recurring-agreements.md#future-period-financial-recording-2026-09-28).

The subsequent held-access workflow applied migration 0017 only to this isolated
database and restarted the local review server with authorization disabled. Actual
provider-backed application refused the October 28 start while still in the future;
all subscription/entitlement rows and financial/audit/receipt counts were unchanged.
There are zero access resolutions. The successful due branch is covered by isolated
tests, not by altering this rehearsal's clock or saved dates. See the
[command and acceptance limits](recurring-agreements.md#applying-a-held-period).

A third fresh `failure_recovery` fixture subsequently tested the Dashboard's
**Charge as failure** control once. It unexpectedly settled as Captured with the
agreement still Active, so actual failure/Pending/Halted recovery remains open.
Unpaid recovery granted nothing; the eventual future capture was recorded once
with access held and no change to the initial term/entitlements. Cancellation and
independent provider verification followed settlement. Current totals are seven
invoices/payments/queued receipts, five cycles and zero access resolutions. All
three test mandates are cancelled and authorization/mail/webhook/tunnel remain off.
See the [latest evidence and diagnostic draft](recurring-agreements.md#failure-simulation-continuation-2026-09-28).

Annual continuation subsequently passed actual initial capture, paid-invoice
recovery/replay and cancellation in a fourth fictional Workspace. It exposed and
fixed the annual midnight-IST invoice boundary; exact provider dates are retained.
Current totals are eight invoices/payments/queued receipts, six cycles and zero
access resolutions. All four mandates are cancelled, the catalog actor is disabled,
and authorization/mail/callbacks remain off. Annual renewal/completion remains open.
See [annual acceptance](recurring-agreements.md#annual-provider-acceptance-2026-09-28).

A fifth annual fixture subsequently captured/recovered its initial year. Its single
final accelerated renewal remains Created/Issued at 01:34:08 IST on September 28.
The fifth agreement stays Active pending reconciliation; the four earlier mandates
remain cancelled. Authorization/mail/callbacks/catalog actor are off. No early
cancellation or repeat charge was made. Nine invoices/payments/queued receipts,
seven cycles and zero resolutions are saved; unpaid recovery preserved all access.
See [exact identities and resume instructions](recurring-agreements.md#annual-final-charge-attempt-and-production-critical-path-2026-09-28).

On September 28 the earlier annual fixture was fully refunded and explicitly
ended through owner access review; invoice/cycle history and original dates remain
intact. One BillingResolution now exists. Both Razorpay diagnostic reports are
submitted (21146138 / 21146171). A sixth scheduled-start fixture has an unresolved
INR 5 authorization token and no paid invoice/access. The older annual final charge
also remains pending. New authorizations/mail/callbacks are off. Follow the
[current checkpoint](recurring-agreements.md#scheduled-start-support-and-refund-continuation-2026-09-28)
before resuming; old initial-state assertions no longer describe the refunded fixture.

The later release checkpoint closed only the fully refunded annual agreement 4
with event 64. Its Workspace remains read-only; original dates/financial history
and all counts are preserved. The other five reservations remain held. No new
replacement mandate was created. Follow the
[release checkpoint](recurring-agreements.md#refunded-agreement-release-and-replacement-2026-09-28)
and `outputs/accept_annual_refund_release.py`; older refund checkers asserting
`closed_at is None` are now superseded. Both pending payment attempts remain Created
after the scheduled start; authorization/mail/callbacks remain off.

References checked September 27:
[Razorpay test card/OTP guidance](https://github.com/razorpay/markdown-docs/blob/master/payments/payments/test-card-details.md),
[idempotent normal refunds](https://razorpay.com/docs/api/refunds/normal-refunds-idempotent).
Refund requests used separate stable idempotency keys and exact known test-payment
identities; no retry with an unknown outcome or manually fabricated paid state.
