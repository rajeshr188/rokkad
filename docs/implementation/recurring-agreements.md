---
status: active
owner: project
updated: 2026-09-28
tags: [billing, subscriptions, recurring, operations]
related: [../adr/2026-09-27-recurring-agreement-evidence.md, billing-test-rehearsal.md, ../plans/subscription-monetization-rollout.md]
---

# Recurring agreements and paid cycles

## Refunded agreement release and replacement (2026-09-28)

`release_recurring_agreement` closes a narrowly supported settled Test Mode
reservation: cancelled immediate-start mandate, no next charge, at least one paid
cycle, all invoices fully refunded and all access reviews complete. It requires
an active owner/platform actor, reason and reviewed Subscription revision. It owns
its transactions; do not invoke the service from inside Workspace middleware.

```text
python manage.py release_recurring_agreement --workspace-id ID --actor-id OWNER_ID --agreement-id ID --revision ISO_UPDATED_AT --reason "Reviewed provider settlement and ended refunded access"
```

Use the appropriate restricted runtime settings. The command performs provider
GETs only: bounded complete invoice scan (including the final empty page), exact
local cycle set and paid count, every invoice/payment/plan, each saved refund and
all order payment attempts. Failed attempts are allowed alongside the exact refunded
payment; every uncertain or additional non-failed attempt blocks release. Recheck
provider collection/status and local authority/revision/evidence before atomically
closing the agreement with one immutable `reservation.released` event. No dates,
entitlements, invoices, payments, receipts or Workspace lifecycle are changed.

Unknown/empty attempts, scheduled authorizations, unpaid invoices, unreturned paid
time, completed/expired mandates and prepaid/trial conversions need separate policy.
The command does not authorize cancellation, refunds or replacement charges.
Use a new request key with the existing preparer for a separately reviewed
replacement. Local tests verify that a due first replacement payment gets its own
exact period, including a shorter end than the refunded historical term, only when
the release still matches the unchanged cancelled Subscription. Old history stays
immutable. See the [decision](../adr/2026-09-28-refunded-recurring-reservation-release.md).

Actual acceptance: Workspace **5** `annual_rehearsal`, ordinary owner **1**,
agreement **4** `sub_ThBA3n7q5fIsTI`, release event **64**, closed
**28 September 2026 12:20:16 IST**. Existing processed refund and BillingResolution
1 were independently checked through fresh API reads. All Subscription fields,
six-seat entitlements, original paid end and financial counts stayed unchanged;
access remains cancelled/read-only. Release replay and paid invoice replay passed.
The database runtime is neither superuser nor BYPASSRLS. Browser verification shows
the closed-after-refund message and original invoice/period. No replacement mandate
was created at Razorpay; actual replacement Checkout/capture remains unaccepted.

Counts: six agreements (one locally closed), seven cycles, nine invoices/payments/
queued receipts, one BillingResolution, zero held-access resolutions. The other
five agreement reservations remain held. Four provider mandates are cancelled;
annual agreement 5 remains Active and scheduled agreement 6 remains Created.
Final GET after 12:20:21 IST still found annual payment `pay_ThBR0fQ4nwVW3p`
Created with invoice Issued, and scheduled token `pay_ThM8vfcR0fWZik` Created with
no invoices/access. No retry/cancel/charge was issued. Preserve both attempts and
the submitted support cases **21146138 / 21146171**. The scheduled start passing
did not establish authorization or naturally due paid-access acceptance.

Validation: **137** broad billing tests passed in 195.220s; the final **12** release
tests passed in 64.412s after adding unrelated-paid-invoice protection. The first
release-only run caught a replacement fixture backdated before agreement creation;
the fixture was corrected, without relaxing the provider-period guard. No schema
change. New recurring authorization/mail/callbacks remain off; catalog actor inactive.
Isolated loopback review server restarted with authorization false.

Ignored evidence: `outputs/accept_annual_refund_release.py`,
`outputs/annual-refund-release-final.json`, `outputs/annual-refund-release-reviewed.png`.
The helper replays only the existing release/payment. Earlier
`check_annual_refund.py` asserts a still-held reservation and is now superseded;
do not use old initial-state assertions to undo this checkpoint.

Next independent work: explicit live/test deployment boundary and receipt/SES
readiness while provider anomalies are pending. General replacement/prepaid policy,
actual replacement payment and remaining provider acceptance are still launch gates.

## Scheduled start, support and refund continuation (2026-09-28)

Owner-authorized reports are submitted as Razorpay tickets **21146138** (annual
renewal Created after success simulation) and **21146171** (failure simulation
captured). Confirmation screenshots and exact submitted text are in ignored
`outputs/razorpay-annual-support-submitted.*` and
`outputs/razorpay-failure-support-submitted.*`. The provider says 4-8 business hours
for an update. The support contact confirmation required an additional owner
approval after automatic review; both tickets ultimately succeeded.

`prepare_recurring_agreement ... create` now accepts optional `--start-at UNIX_SECONDS`.
It must be a future integer for a new attempt. The immutable request captures it
before the provider POST; same-key replay must match it even after the date passes.
Every provider observation must match the original schedule. Invoice billing_start
must not precede it. The owner page shows the date and separate authorization/token
step, and blocks new authorization of a still-Created agreement after its start.
This does not permit conversion of existing prepaid/trial time. See the
[decision](../adr/2026-09-28-scheduled-recurring-test-start.md).

Actual sixth fixture:

- Workspace **7**, `scheduled_start`, ordinary owner **1**, monthly binding **1**,
  agreement **6**, provider subscription **`sub_ThM7GiBY7yxoHg`**, two cycles.
- Request key `4a0693cb-64eb-40e2-8fec-84b1f464a5e0`; frozen start **1790578221**,
  **28 September 2026 12:20:21 IST**, matched by provider GET.
- Checkout showed Test Mode and INR 5 refundable authorization with fictional
  contact and the official domestic Visa test card. The optional OTP was skipped
  through the displayed provider control; the bank-page action opened a blank tab.
  Checkout later reported failure, but token **`pay_ThM8vfcR0fWZik`** remained
  **Created**, amount 500 paise, with no invoice/order/error and no paid access.
- Last GET **12:05:14 IST**: agreement Created, paid_count 0, remaining_count 2,
  no invoices; the token was still Created. No retry, alternate card, simulator
  charge or cancellation was attempted. The blank bank tab was closed after the
  observed failure. **Naturally due held-access acceptance remains open.**
- Resume with GET of these exact identities. If still unsettled, preserve the
  attempt and obtain provider clarification; a failed UI is not a settled API
  failure. Do not rerun the preparer or alter dates/clock. If authorization later
  succeeds, refresh the saved agreement, inspect actual invoice boundaries and
  payment status before any charge simulation or access action. Once the start
  passes, a still-Created agreement requires review rather than fresh authorization.

Original annual final payment **`pay_ThBR0fQ4nwVW3p`** / invoice
**`inv_ThBQyvwJjIJcQ0`**, agreement **5**, remained Created/Issued at **12:05:19 IST**,
with subscription Active and paid_count 1. It also remains untouched.

The existing owner invoice review now routes recurring full refunds through fresh
provider cycle/payment/plan/agreement and every saved refund verification. Local
full-refund totals/IDs, active authority and current Subscription revision are
rechecked under the Company lock. `retain_access` changes no access; `end_access`
requires a terminal provider mandate, the exact current applied term and no other
unreturned current/future paid periods. Immutable BillingResolution and both audit
streams commit together. Replays return the decision without reactivation. The
Workspace reservation is not released. See the
[refund decision](../adr/2026-09-28-recurring-refund-access-review.md).

Actual refund acceptance used the earlier cancelled annual agreement **4**, Workspace
**5** (`annual_rehearsal`), invoice **8**, cycle **6**, provider invoice
`inv_ThBA4L4sgovtkx`, payment `pay_ThBBX5Xu5XRjTu`. The owner clicked Razorpay's
final refund confirmation after automatic review required user handoff. Provider
refund **`rfnd_ThMJ3PKV1YHev4`** was independently fetched as **processed** for
**INR 17,688.20**, payment fully refunded, mandate Cancelled with no next charge.
The existing reconciliation command recorded it while every Subscription and
entitlement field stayed unchanged. The ordinary owner's browser then recorded
`end_access` as **BillingResolution 1**; the fictional Workspace became read-only.
Original purchased end **28 September 2027 00:00 IST** and six-seat entitlement
evidence stayed intact. Paid invoice replay and stale-revision same-decision replay
preserved the cancelled access state, financial counts and original cycle evidence.

All **127** agreement/owner/cycle/held-access/refund/review/recovery tests pass. The
first broader run exposed two test fixtures needing updates for the new provider
refund read and explicit Workspace context; the complete rerun passed. No schema
change or production deployment. Restricted-role verification confirms nine
invoices/payments/queued receipts, seven cycles, one BillingResolution and zero
RecurringAccessResolutions. New authorization and mail are off; callback/tunnel
remain off; catalog actor is inactive. Four earlier mandates are cancelled; the
annual completion mandate remains Active and this sixth mandate remains Created.

Evidence/helpers in ignored `outputs/`: `scheduled-start-setup.json`,
`scheduled-start-evidence.json`, `inspect_scheduled_authorization.py`,
`annual-refund-before.json`, `annual-refund-evidence.json`, `annual-refund-final.json`,
`annual-refund-reviewed.png`, `inspect_annual_refund.py`, `check_annual_refund.py`,
and `fw019-schedule-refund-tests.log`. The checker replays only already-recorded
evidence; it never issues a provider refund. Do not overwrite historical evidence
by rerunning old initial-state assertions after this refund.

Next: reconcile provider replies/pending attempts, then financially settled
reservation release and safe replacements, live-mode isolation/operations, paid
receipt delivery/SES and commercial pilot decisions. A shorter due-date acceptance
has not succeeded; the existing October fixtures remain the fallback. Do not
claim the pilot or FW-019 is complete.

## Owner authorization and cancellation

Workspace settings > Billing > **Recurring payments** now shows prepared
agreements, frozen terms, provider observations and the last twelve paid cycles.
The operator still creates/binds agreements through the commands below. Owner
self-service creation and a launch duration have not been introduced.

With Test Mode keys and `BILLING_RECURRING_ENABLED=True`, a prepared `created`
agreement can be authorized in Checkout after explicit consent. The server
rechecks provider identity/plan, Workspace lifecycle, seats and existing paid/trial
time. Confirmation verifies the signature against the saved subscription ID.
Authorization alone does not grant access. Failed confirmation retries the same
payment identity. The page can refresh status and reconcile a known Razorpay invoice
ID through the existing paid-cycle verifier, even when new authorization is paused.

Stopping renewals saves an immutable request before any provider I/O. The
post-commit delivery cancels the mandate immediately and independently fetches
confirmation; local paid dates/status and entitlements remain unchanged. A timeout
is shown as pending/uncertain, never success. The owner may refresh status. A
cancelled mandate cannot be restarted and the reservation remains until financial
reconciliation permits replacement. In-flight payments and refunds are separate.

If the process dies before delivery, locate the agreement's `cancel.requested`
event ID through scoped operator inspection, then run under restricted runtime:

```text
python manage.py process_recurring_cancellation --request-id EVENT_ID
```

Use the isolated billing settings and explicit rehearsal DB as below. Undispatched
requests are delivered once; an existing `cancel.dispatched` event forces GET-only
recovery. No timer is installed. Even a crash before the first POST after claiming
dispatch requires provider/operator review; do not delete events or repeat the POST.
If the requesting actor lost ownership or became inactive, dispatch stops for
operator review. A current owner can still refresh the agreement independently.

See the [owner-action decision](../adr/2026-09-27-recurring-owner-actions.md).
Automated owner-flow tests mock provider calls. Actual initial payment and
cancellation acceptance subsequently passed in the isolated provider rehearsal
below; new authorization is disabled again after cleanup.

This is FW-019's agreement, paid-cycle and prepared owner-flow implementation.
`apps.subscriptions.recurring` and `prepare_recurring_agreement` register a frozen
provider plan, create one durable Workspace agreement attempt, and recover a known
provider ID. They never authorize a payment, issue a receipt or grant access.
Owner actions on those prepared records are described above.

### Collection failure and recovery

The owner page now explains verified Pending and Halted states. Pending can still
be retried by Razorpay; Halted means automatic collection has stopped. Both notices
preserve already-paid time, explain that an unpaid invoice cannot extend it and
direct the owner to review the existing agreement/invoice before another payment
or replacement. Cancellation uncertainty and verified ended-state notices take
precedence. A successful status refresh removes stale attention wording.

For a provider rehearsal, record the initial paid Subscription/entitlement rows
and financial/receipt counts, then trigger one Test Mode failure and observe the
payment and agreement with GET requests. A Created payment is unsettled: do not
repeat the charge or cancel the agreement merely because the simulator is slow.
Once a definitive failed/pending outcome is observed, refresh Rokkad and compare
the saved baseline. Unpaid invoice recovery must grant nothing. Recovery requires
verified paid invoice evidence, not an Active mandate or changed current-period
dates. An accelerated future capture remains held for the explicit due-period review.

Razorpay documents four consecutive simulated failures as the path to Halted and
distinguishes invoice-level Attempt Charge from subscription-level test charging.
Use the current Dashboard controls and wait for each outcome; never assume a click
proved the transition. See [Test Subscriptions](https://razorpay.com/docs/payments/subscriptions/test/)
(checked 2026-09-28). Actual account outcomes, not the documented expectation,
determine which acceptance items can be marked complete.

Local regression coverage now includes signed Pending -> Halted -> Active
observations preserving subscription/entitlement rows, grace/read-only boundaries,
future captured recovery with duplicate delivery, and delayed Pending hints that
refetch current Active provider state. The 50 paid-cycle/owner tests pass; those
mocked branches do not establish actual provider failure delivery or recovery.

`recurring_cycles` now verifies paid provider invoices/payments and records their
exact periods through the existing signed webhook and explicit recovery command.
This separate service can grant purchased access, unlike agreement preparation.

## Runtime and migration

Migrations 0013-0017 add global billing evidence and PostgreSQL identity/history
guards. Apply only with `django_project.settings.migration`, explicitly targeting
the isolated rehearsal database. Web/operator processes use the restricted runtime
role. Never point test preparation at the production database. All existing local
and production feature flags remain unchanged by this implementation.

`BILLING_RECURRING_ENABLED` defaults false. Even when enabled, the preparation
services reject anything except configured `rzp_test_` credentials. The existing
DPAPI-backed [rehearsal settings](billing-test-rehearsal.md) can be used by the
Windows owner without copying keys into the repository or command line. Known
agreement payment recovery remains available when new creation is disabled, with
Test Mode credentials only. The temporary rehearsal webhook/tunnel are stopped
after the September 28 initial-cycle/cancellation acceptance below.

## Operator commands

Run outside a surrounding transaction/Workspace context. The command opens its own
short Workspace transactions and commits the attempt before the remote create call.
The placeholders below identify already reviewed local/provider entities, not
secret values. Use an empty fictional Workspace; the previous paid Orders fixture
has future paid time and must not be converted automatically.

```text
python manage.py prepare_recurring_agreement --settings django_project.settings.billing_rehearsal --actor-id PLATFORM_ADMIN_ID bind --plan-id PLAN_ID --cycle monthly --provider-plan-id plan_PROVIDER_ID --reason "Reviewed test offer"
python manage.py prepare_recurring_agreement --settings django_project.settings.billing_rehearsal --actor-id OWNER_ID create --workspace-id WORKSPACE_ID --binding-id BINDING_ID --total-count 12 --request-key UUID
python manage.py prepare_recurring_agreement --settings django_project.settings.billing_rehearsal --actor-id OWNER_ID reconcile --workspace-id WORKSPACE_ID --agreement-id AGREEMENT_ID --provider-subscription-id sub_PROVIDER_ID --reason "Located original attempt"
```

`--settings` is a Django global option, placed before the subcommand.
No default duration is silently selected: 12 above is an
example for an operator test, not a launch promise. The initial implementation
accepts 1-100 explicit cycles; provider limits still apply. The provider catalog
plan must already exist and match the configured tax-inclusive price/currency,
monthly/yearly interval and frozen local entitlements. Catalog registration is
platform-admin-only; ordinary staff, including Workspace Admins, cannot initiate
or reconcile agreements. Canonical owners and platform administrators can.

Creation freezes a UUID in provider notes with the Workspace ID. It sends quantity
one, explicit total count and `customer_notify=false`; no contact information,
add-ons, discount offer, authorization link delivery or customer payment is sent.
There is no automatic creation retry. The verified provider ID is immutable.

## Uncertain outcomes

The local reservation persists if provider creation times out, its response fails
validation, or the app fails after remote success. Repeated keys and new attempts
cannot POST again. Find the original subscription in Razorpay Test Mode by its
notes, then supply that ID to `reconcile`. Recovery fetches both subscription and
plan, validates the expected identity/terms, and appends actor/reason evidence.
It does not trust a copied JSON payload or an operator's claim of payment.
An empty provider search result is not proof of absence; the attempt remains held.

One open agreement per Workspace is enforced by a database constraint and Company
lock. Manual Orders creation/capture uses the same reservation check. Existing
paid-invoice replay remains idempotent. Pending manual invoices block new recurring
creation. Active paid/trial time, legacy mandates, suspended/archived Workspaces
and over-capacity memberships/invitations require review instead of silent changes.

Even verified cancellation/completion/expiry only records provider status. The
reservation stays held until later cycle reconciliation/cancellation services can
prove safe closure. No supported force-clear, delete or retry-POST escape exists.

## Paid-cycle processing and recovery

For a known verified agreement, `subscription.charged` or a recurring
`payment.captured` event fetches the invoice, payment, agreement and provider plan.
It verifies subscription/Workspace notes, order/payment/invoice linkage, exact INR
amount, full settlement, one plan line and explicit billing_start/billing_end.
The period must not predate agreement creation and must fit a monthly
(28-31 days) or annual (365-366 days) period. Annual periods also accept the
precise midnight-IST anniversary shape described in the
[annual boundary decision](../adr/2026-09-28-annual-invoice-calendar-boundary.md);
payment time cannot be in the future.
Verified future periods are recorded with access held for review, as described
below. Unsupported period shapes and unrecorded refunded payments are rejected
for investigation; do not infer dates or settlement.

The shared transaction records one `RecurringCycle`, paid Invoice/Payment,
any eligible entitlement projection/paid-through change, audit and queued receipt. It never
adds time based on delivery date. Identical replay, including after a refund,
does not reactivate access or create another receipt. Different IDs covering an
overlapping period fail closed. A late older cycle records history without
shortening a newer term. Expired periods use existing grace/read-only policy.

Lifecycle events (`subscription.authenticated`, `activated`, `pending`, `halted`,
`cancelled`, `completed`, `paused`, `resumed`, `updated`) only fetch and record
current provider status. They never grant access or revoke paid time. Provider
observations have no invented human actor. Unsupported events remain FAILED.
Authorization-only payments with no valid paid plan period cannot become cycles.

Recover a missing event as the canonical owner/platform operator:

```text
python manage.py reconcile_recurring_cycle --settings django_project.settings.billing_rehearsal --workspace-id WORKSPACE_ID --actor-id OWNER_ID --agreement-id AGREEMENT_ID --provider-invoice-id inv_PROVIDER_ID --reason "Recover missing paid-cycle event"
```

This command applies verified evidence; it does not initiate a charge. It returns
the cycle, local invoice and `access_action`: applied, retained or review.
Closed/replaced mandates, archived Workspaces and conflicting existing terms can
record paid financial evidence while leaving access for review. No force-paid or
reservation-release command is provided. Existing owner invoice/download and mail
status permissions apply to these ordinary local invoices.

The normal refund webhook/reconciliation still records verified partial/full
refunds. Full refund alone does not remove access. The manual `end_access` review
action rejects recurring invoices until agreement/cycle access review is delivered;
stopping future charges is a separate provider cancellation. Recurring receipts
describe the purchased period and identify held access review without claiming a
one-off purchase or a successful cancellation.

### Future periods and access review

The [future-payment decision](../adr/2026-09-28-future-recurring-payment-evidence.md)
allows verified captured, unrefunded future payments into financial history with
`access_action=review` and frozen `access_review_reason=future_period`. Existing
Subscription fields and entitlements are untouched. A first payment creates only
a past-due financial parent with end date equal to payment time, no trial and no
entitlements. Unresolved review cycles are excluded from evidence of already-applied access
when evaluating later started cycles, preserving manual/trial overlap guards.

The owner page lists review payments across all Workspace agreements with
pagination, separate from the latest twelve ordinary cycles. Invoice detail and
receipt wording explain unchanged access and the need for billing review.
Neither invoice replay nor the clock reaching period_start grants access. Use the
explicit workflow below; do not edit immutable cycles or snapshots to clear a hold.

### Applying a held period

Migration 0017 and the [held-access decision](../adr/2026-09-28-held-recurring-access-resolution.md)
add one immutable resolution per cycle. Under restricted runtime settings, inspect
the scoped cycle/invoice and current Subscription terms, including its exact
`updated_at.isoformat()` revision, then run:

```text
python manage.py apply_recurring_period --settings django_project.settings.billing_rehearsal --workspace-id WORKSPACE_ID --actor-id OWNER_OR_PLATFORM_ID --cycle-id CYCLE_ID --revision REVIEWED_SUBSCRIPTION_UPDATED_AT --reason "Reviewed due paid period"
```

The command accepts Test Mode credentials with new authorization disabled. It
requires an active canonical owner/platform administrator and matching Workspace
context, a nonempty reason and a current reviewed revision. Provider invoice,
payment, agreement and plan are fetched again; evidence must match the saved cycle,
with no provider/local refund. The Company lock serializes local refund, ownership,
subscription and capacity changes. A provider refund occurring after verification
remains a separate review under the existing refund policy.

Only original future-period holds with start <= now < end qualify. The Workspace
must be ACTIVE; the verified agreement must still hold its reservation and be
unclosed. Provider cancellation can coexist with paid access. Closed/replaced
agreements, changed plans, local cancelled/trial subscriptions, overlapping/newer
dates and excess members/pending invitations remain blocked for separate review.
No automatic renewal setting or platform restriction is changed.

Success applies the exact saved end and frozen entitlements, preserving overrides,
and records actor/reason plus before/after terms/revisions atomically. Original
cycle/invoice snapshots are never edited. A retry returns the resolution without
reapplying access, even after refund/expiry/cancellation; no duplicate receipt.
Resolved holds participate in subsequent paid-cycle access checks and move out of
the owner's unresolved list. Invoice detail/new receipt rendering show the historical
resolution; already queued/sent receipt artifacts stay unchanged. No timer, owner
web apply route, reservation release or live activation is provided.

September 28 validation: 98 distinct held-access/recurring/owner/refund-review/
checkout tests passed across two runs (71 then 39, with overlapping held-access
coverage and three added cases). Restricted-role concurrency, immutability, local
refund/ownership races, rollback and current-access guards are covered. Migration
drift check passes. Only the isolated rehearsal DB received migration 0017.
Actual Test Mode provider reads verified the retained renewal, but application
correctly refused its future 28 October start. Subscription, entitlements and all
financial/audit/receipt counts stayed unchanged, with zero resolutions. Evidence:
`outputs/held-access-guard-acceptance.json`. Due-success uses automated fixtures;
naturally due provider application, failure/recovery and remaining acceptance are
still open. No clock or provider-date changes, charge, refund or email dispatch.

## Validation and remaining work

The following September 27 checkpoints describe implementation-time fixtures;
the September 28 provider rehearsal below supersedes their empty-table state.

`apps.subscriptions.test_recurring` covers frozen monthly/annual prices and seats,
ownership/mode gates, mismatched identities/terms, timeout and post-success local
failure recovery, database history guards and concurrent in-flight attempts.
Existing Orders checkout tests cover compatibility of the added exclusion guard.
September 27 validation: 14 recurring tests and 24 existing Orders checkout tests
pass, including restricted-role creation/recovery and immutable-evidence rejection.
Migration drift and current-doc link checks pass. Migrations 0013/0014 are applied
only in the isolated billing rehearsal database; its restricted runtime reads all
three empty tables and recurring preparation remains disabled. The paid-cycle
increment subsequently applied 0015/0016 in the same isolated database: all four
recurring tables remain empty, restricted reads pass and the prior two Orders
invoices/payments are intact. The local review server was restarted.
The paid-cycle increment adds 23 focused cases for exact periods, signed replay,
out-of-order delivery, provider/transaction failure, identities/amounts/currency,
refunds, annual pricing, grace/read-only, receipt content and restricted-role
concurrent capture/history guards. The earlier 65 agreement/Orders/recovery/review
tests also pass. Provider boundaries are mocked: no real recurring mandate or payment has been
created or accepted by this increment.

The owner increment adds 15 backend cases and two JavaScript retry cases. The
combined owner/paid-cycle/Orders suite passes 62 tests. Documentation links and
schema drift checks pass. The empty owner page and source assets were checked in
the isolated browser; prepared states use mocked provider tests.
After adding the terminal-status regression guard, the 52 owner/paid-cycle/agreement
tests also pass, bringing this increment's distinct backend coverage to 76 tests.

Next: remaining recurring renewal/failure acceptance, scheduled transitions from prepaid
terms, self-service creation/duration selection and release of settled reservations.
No production rollout or general email sending is included.

## Actual provider rehearsal (2026-09-28)

Historical checkpoint: the future-period rejection described here and in the
diagnostic continuation is superseded by
[future-period financial recording](#future-period-financial-recording-2026-09-28).

This first checkpoint is followed by the diagnostic continuation below, which
resolves the earlier pending attempt and verifies a fresh provider renewal capture.

The separate `recurring_rehearsal` fictional Workspace used a monthly provider plan
at INR 1,768.82 (agreed INR 1,499 base plus illustrative 18% tax), six total members
and an explicit three-cycle test duration. An isolated catalog operator with an
unusable password bound the plan; the ordinary fictional owner created/authorized
the agreement. The catalog operator is now inactive. No production account or
commercial duration was created. The existing paid Orders Workspace was untouched.

| Check | Actual Test Mode result |
| --- | --- |
| Checkout authorization and initial collection | Signature verified; one provider invoice paid and payment captured |
| Exact paid dates | 28 Sep 2026 00:01:43 IST to 28 Oct 2026 00:00 IST; one local cycle/invoice/payment and queued receipt |
| Early capture before complete invoice evidence | Missing billing timestamps rejected; provider retry processed after timestamps became available |
| Owner known-invoice recovery | Existing verified cycle returned without duplicate access, payment or receipt |
| Signed same-ID / new-ID replay | Both 200; record counts and paid end unchanged; new-ID test explicitly synthetic |
| Conflicting payload using original event ID | 400; original record unchanged |
| Owner cancellation | One durable request/dispatch/confirmation; independent provider GET and signed event confirm cancelled |
| Paid access after cancellation | Active through the same paid end, six-member entitlement; reservation retained |
| Accelerated renewal failure | Inconclusive: unpaid future invoice issued, payment attempt Created; no completed failure/pending event observed |

The dashboard's **Charge this now > Charge as failure** advanced the provider's
current period to 28 October–28 November despite no collected payment. Rokkad
correctly kept only the original paid period. Cancellation subsequently stopped
the agreement; the future invoice remained issued/unpaid at final inspection.
Do not count this as successful renewal, completed failed collection or pending/
halted recovery. Future-period capture is intentionally rejected by the current
verifier; never fake the application clock or substitute guessed dates to pass
accelerated testing. [Razorpay's Test Mode guide](https://razorpay.com/docs/payments/subscriptions/test/)
describes accelerated charging; the observed account outcome still needs resolution.

Next acceptance work: investigate the Created attempt with provider evidence,
then use a fresh fictional agreement to verify subsequent successful collection,
completed failure/recovery and annual recurring periods. Review how accelerated
future periods should be exercised before accepting them; any production semantic
change needs its own decision and boundary tests. Preserve this cancelled agreement
and its held reservation. Final recurring refund-access review, settled reservation
release, prepaid transition and self-service creation remain separate work.

Private IDs and financial evidence are retained in ignored
`outputs/recurring-provider-setup.json`, `recurring-provider-initial-cycle.json`,
`recurring-provider-evidence.json`, `recurring-provider-replay.json` and
`recurring-cleanup-evidence.json` (all under `outputs/`). The final UI proof is
`outputs/recurring-cancelled-paid-period.png`; webhook cleanup proof is
`outputs/recurring-webhook-disabled.png`. These are local artifacts, not published
credentials or production acceptance. No support message was sent.

Cleanup: Test webhook Disabled; Cloudflare tunnel and port 8893 callback stopped;
local web server restarted on 8083 with recurring authorization false. Restricted
runtime and disabled mail verified. Totals are one recurring cycle, three local
invoices/payments/queued receipts including earlier Orders evidence, zero failed
webhook rows. No receipt dispatch, live charge, production data or deployment.

## Renewal diagnostic continuation (2026-09-28)

The first fixture's Created renewal subsequently became Failed with
`BAD_REQUEST_ERROR`, `card_mandate_not_active`, "Mandate not active". Because
cancellation preceded that observation, it cannot establish the underlying cause.
A fresh `renewal_followup` Workspace reused the verified monthly binding with a new
explicit three-cycle agreement, without reactivating the catalog operator. Initial
authorization/capture succeeded. The webhook stayed disabled: owner recovery of
the actual paid invoice created one cycle/payment/invoice/queued receipt and
six-member access through 28 October 00:00 IST. Authorization alone had created
none of those financial/access records.

Exactly one **Charge as Success** request issued the next invoice for 28 October
to 28 November. The payment remained Created for several minutes, then captured
successfully: provider paid_at is 28 September 00:23:40 IST, about 5 minutes 33
seconds after payment creation. The next observation at 00:23:52 confirmed capture.
Provider invoice status is paid, amount_paid=176882, amount_due=0, paid_count=2.
An intermediate token read showed Failed alongside recurring Confirmed; this did
not establish the outcome. Treat interim provider states as observations, not
permission to re-charge, cancel early or weaken payment verification.

Owner recovery of the now-paid future invoice reached the existing explicit
started-period rejection. Its money remains in provider and diagnostic evidence;
no local recurring invoice/payment/cycle/receipt or future access was invented.
The earlier initial paid period remains active through 28 October. This proves
provider subsequent capture and the app's future-period guard, not end-to-end
renewal accounting/access. After settlement, ordinary owner cancellation and an
independent provider GET confirmed cancelled with no next charge. Both test
agreements are now cancelled with their financial reservations retained.

Actual unpaid-invoice recovery preserved access. The service now checks unpaid
status before interpreting the absent payment ID, giving an actionable explanation
instead of "Invalid provider identity". Identity, amount, settlement and period
checks remain intact. All 39 paid-cycle/owner tests pass, including unchanged dates,
revision and financial/audit/receipt counts on unpaid recovery. The same message
passed actual browser review.

Private evidence: `outputs/renewal-followup-setup.json`,
`outputs/renewal-followup-evidence.json`, `outputs/renewal-mandate-observations.jsonl`
and `outputs/renewal-attempt-observations.jsonl`. UI proof is
`outputs/renewal-unpaid-recovery.png`; future-period rejection and final cleanup are
`outputs/renewal-future-period-review.png` and `outputs/renewal-followup-cancelled.png`.
Final local checks are in `outputs/renewal-local-verification.json`. The provisional
support draft at `outputs/razorpay-recurring-support-draft.txt` is marked superseded:
the pending payment captured before any message was sent. Do not submit its stale
intermediate assertions as a current provider failure.

New local authorization is disabled; mail and callback/tunnel remain off. Final
isolated totals are four local invoices/payments/queued receipts and two recurring
cycles; the future provider-paid invoice is deliberately not counted locally.
Next is a reviewed approach to recording verified future paid periods without
granting access early, followed by failure/pending/halted recovery and annual
recurring acceptance. Do not fake the clock, change immutable provider dates or
force-clear reservations. Test evidence alone does not permit live activation.

## Future-period financial recording (2026-09-28)

Implemented the reviewed admission boundary above without schema changes. Actual
owner recovery fetched the already captured future renewal with Test Mode provider
GETs and recorded one additional invoice/payment/cycle/queued receipt. The exact
period remains 28 October 00:00 IST through 28 November 00:00 IST, INR 1,768.82
including illustrative tax. A second owner recovery returned the same evidence.

Restricted-role verification compared every existing Subscription field and all
entitlement rows to a snapshot taken before recovery: unchanged. Initial access
still ends 28 October and retains six total members. Totals are now five local
invoices/payments/queued receipts and three recurring cycles. The future cycle is
`review`; the provider agreement remains cancelled. Receipt HTML was rendered and
checked for the hold explanation; nothing was dispatched. No new charge was made.

Seventy recurring-cycle/owner/checkout tests passed. Three focused tests then
passed for refined annual/owner assertions plus new review pagination coverage,
giving 71 distinct tests overall. Future monthly/annual admission, first-payment
non-active state, signed replay after start/refund, immutable evidence, rollback,
manual overlap protection and restricted-role concurrency are covered. Migration
drift check reports no changes. Annual provider acceptance remains unproven.

Private evidence: `outputs/future-period-before.json`,
`outputs/future-period-acceptance.json`, `outputs/future-period-receipt-preview.html`
and `outputs/future-period-recorded.png`. Older diagnostic count files/scripts
describe their checkpoint and must not be rerun as current acceptance assertions.

New authorization, callback/tunnel and mail remain off; both test mandates remain
cancelled with reservations retained. No live/production changes. Next: explicitly
authorized, audited application of eligible held periods when due, followed by
remaining failure/pending/halted recovery and provider acceptance. Clock changes,
replay and manual evidence edits are not access-resolution tools.

## Failure simulation continuation (2026-09-28)

Prepared a fresh fictional `failure_recovery` Workspace with the existing monthly
binding, ordinary owner and explicit three-cycle Test Mode agreement. Customer
notifications remained false. Initial card authorization/capture and owner recovery
passed with webhook/tunnel disabled, adding a period from 28 September 00:47:42 IST
through 28 October 00:00 IST and six total members. Authorization alone granted no
access. A snapshot preserved every Subscription and entitlement field before the
subsequent failure attempt.

On the active provider agreement, selected **Charge this now > Charge as failure**
once. Razorpay issued the October 28-November 28 invoice. The payment stayed
Created for several minutes, then was observed Authorized at 00:54:48 IST and
Captured at 00:55:08 IST. Provider paid_at is 00:54:48 IST. The invoice is paid in
full (176882 paise INR), paid_count=2, auth_attempts=0 and status remained Active.
No Pending/Halted/completed failure was observed. The
[documented failure expectation](https://razorpay.com/docs/payments/subscriptions/test/)
was not reproduced; do not infer why or mark failure recovery accepted. No extra
charge, payment-method change or cancellation happened while it was unsettled.

Actual unpaid-invoice recovery was rejected with the explanatory message and
preserved access, entitlements and financial/receipt counts. After verified capture,
ordinary owner recovery recorded the future cycle once with access_action=review.
A second recovery added no invoice/payment/cycle/receipt. Every pre-existing
Subscription field and entitlement row matched the baseline after reconciliation
and cancellation; original paid access still ends October 28. No early activation
or changed provider dates/clock. Cancellation occurred only after capture settled;
independent GET confirms Cancelled and charge_at=null.

The owner UI now explains Pending/Halted collection attention separately from paid
access. Fifty paid-cycle/owner tests pass, including signed failure/status-recovery
observations, unchanged paid access and entitlement rows, grace/read-only policy,
future captured recovery/replay and delayed Pending hints fetching current Active
status. These mocked event tests are not real provider webhook failure delivery.
Actual failure webhook/retry/halted recovery remains open; the temporary callback
was deliberately kept disabled for this provider read/recovery rehearsal.

Private evidence: `outputs/failure-recovery-setup.json`,
`outputs/failure-recovery-before.json`, `outputs/failure-attempt-observations.jsonl`,
`outputs/failure-recovery-evidence.json`, `outputs/failure-recovery-unchanged.json`,
`outputs/failure-recovery-recovered.json` and `outputs/failure-recovery-final.png`.
The new `outputs/razorpay-failure-simulation-support-draft.txt` describes this exact
run for possible provider clarification; it has not been sent. It is separate from
the older superseded renewal-pending draft. Do not send credentials or turn an
unexpected successful capture into a claim of lost payment.

Final isolated totals: seven invoices/payments/queued receipts, five recurring
cycles, zero access resolutions. All three Test Mode mandates are cancelled with
reservations retained. New authorizations, callback/tunnel and mail remain off.
No real charge, live resource, schema change or production deployment. Next:
clarify/reproduce the failure control before testing actual Pending/Halted recovery;
annual recurring, naturally due hold application and other rollout gates remain.

## Annual provider acceptance (2026-09-28)

A fourth fictional Workspace, `annual_rehearsal` (id 5), uses annual binding 2,
provider plan `plan_ThBA22ILekgnAE`, agreement 4 / `sub_ThBA3n7q5fIsTI`, and two
explicit test cycles. The annual base is INR 14,990 with illustrative 18% tax,
INR 17,688.20 total, and six total members. The owner approved temporarily enabling
the existing passwordless isolated catalog administrator for this binding; it was
disabled in a finally block before owner authorization. No owner received admin
privileges. Provider notifications, local email and the callback/tunnel stayed off.

Actual browser authorization with the official fictional card captured
`pay_ThBBX5Xu5XRjTu` against `inv_ThBA4L4sgovtkx` / `order_ThBA4StXq2mlX8`.
Provider invoice amount/paid/due are 1768820/1768820/0 paise. Its billing_start is
1790537928 (28 September 2026 01:08:48 IST), billing_end 1822069800 (28 September
2027 00:00 IST), and paid_at 1790537950. Authorization alone created no local paid
period. Owner recovery initially rejected this legitimate 364-day, 22:51:12 period.

The [annual boundary fix](../adr/2026-09-28-annual-invoice-calendar-boundary.md)
accepts the exact next anniversary at midnight IST for an annual duration strictly
between 364 and 365 days. This is an additional precise shape, not a general
one-day tolerance. Original invoice dates, amount/identity verification, payment
checks and future-access holds remain unchanged. Monthly validation is unchanged.
Other short provider periods still require review.

After loading the fix with new authorization disabled, owner recovery created
local invoice 8 and cycle 6, one captured Payment and one queued receipt. Access
is Active through the exact provider end, with six members. A repeated owner
recovery created nothing. Owner cancellation followed settlement; independent
provider reads confirmed all four test agreements Cancelled with charge_at null.
A restricted-role comparison of all annual Subscription and entitlement fields
and financial counts proved replay/cancellation preserved them. Reservations remain
held. Totals are eight invoices/payments/queued receipts, six cycles, zero held
access resolutions. Catalog actor, new authorization, email and callback/tunnel
are off; no production change, live charge or schema migration.

Validation covers 69 distinct cycle/access/owner tests across a 68-test run and
two focused passes (one corrected test and one additional future-annual case).
The main run's only error was missing explicit Workspace context in the new owner
recovery test, corrected before rerunning. Tests cover actual timestamps, exact
period replay, leap/calendar boundaries, display timezone independence, wrong
boundary seconds and future money remaining held even after replay at its start.
Ignored evidence: `outputs/annual-recurring-setup.json`,
`outputs/annual-recurring-evidence.json`, `outputs/annual-recurring-before.json`,
`outputs/annual-recurring-final.json` and `outputs/annual-recurring-final.png`.

This accepts initial annual capture/recovery/cancellation, not annual accelerated
renewal, final-cycle completion, naturally due held access, real failure/Pending/
Halted recovery or live method availability. Those and receipt delivery remain
separate gates. The earlier failure-simulation diagnostic draft is still unsent.

## Annual final-charge attempt and production critical path (2026-09-28)

The next rehearsal uses fresh fictional Workspace `annual_completion` (id 6),
existing annual binding 2 and a two-cycle agreement 5 / `sub_ThBL2wVYJZadDN`.
No catalog actor was activated. Initial Test Mode card authorization captured
`pay_ThBP7bP8zw8aN5` for `inv_ThBL3dKSALSLFe` / `order_ThBL3mDlVVQsS3`.
Owner recovery applied the exact period 28 September 2026 01:21:40 IST through
28 September 2027 00:00 IST, six members, with local invoice 9/cycle 7 and one receipt.

One Dashboard **Charge as Success** request at approximately 01:23 IST created
`inv_ThBQyvwJjIJcQ0`, `order_ThBQz2EVyGR408`, and `pay_ThBR0fQ4nwVW3p` for
1768820 paise. Its future period is 1822069800 to 1853692200 (28 September 2027
through 28 September 2028, 366 days). The single attempt remained Created through
25 bounded read-only observations and a final API check at **01:34:08 IST**.
Invoice status is Issued, paid_count=1, remaining_count=0, auth_attempts=1, and
agreement Active. The dashboard says the amount is yet to be authenticated by the
bank; no test authentication action was displayed. This is not a completed failure,
renewal capture or Completed mandate. No retry, manual invoice charge, card change
or cancellation was used to force an outcome.

Actual unpaid-invoice recovery refused to grant the future year. Independent
restricted-role comparison of every Subscription/entitlement field and financial
counts matched the initial baseline. Totals remain nine invoices/payments/queued
receipts, seven cycles, zero access resolutions. **Four previous mandates are
cancelled; this fifth mandate remains active with the pending attempt preserved.**
New authorization, local email, callback/tunnel and catalog actor are off. The
bounded watcher has exited. No real charge, production change or schema migration.

Resume by GET-reading this exact payment, invoice and agreement before any mutation.
If captured/paid, recover the existing invoice once; its future access must remain
held, then observe final-cycle status and finish cleanup. If still Created or
Authorized, retain the attempt and obtain provider clarification. If it fails,
record the actual error/state before deciding recovery. Do not run the fresh-fixture
preparer again to work around an unknown outcome. Unused prepared success-check
helpers are not acceptance evidence until their assertions run successfully.

Two additional regression tests cover Completed status preserving paid access,
final-invoice recovery/replay after completion, retained replacement reservation,
no cancellation POST on an ended agreement, and rejection of a thirteenth invoice
on a twelve-cycle contract while final-cycle replay still succeeds. All **56**
cycle/owner tests pass. No production application behavior changed in this increment.

The Checkout initially displayed a `traffic_env=production` URL parameter alongside
its Test Mode ribbon. Automatic approval review paused form entry. Read-only checks
proved `rzp_test_` credentials, the existing test binding and matching provider
agreement; application code rejects live recurring keys. The owner then explicitly
approved this exact fictional test rehearsal and it proceeded. No URL/mode setting
was altered and no live credentials or real card were used.

Separately, Razorpay's [card mandate FAQ](https://razorpay.com/docs/payments/subscriptions/faqs)
says domestic-card subsequent debits above INR 15,000 require customer AFA outside
its listed exceptional categories. The illustrative annual total is INR 17,688.20.
Confirm that approval journey and account/method eligibility before publishing an
annual automatic-renewal promise. This rule is **not a verified cause** of the test
attempt remaining Created. A separate annual diagnostic draft is saved locally,
not sent; the earlier failure-simulation draft is also unsent.

Evidence: `outputs/annual-completion-setup.json`, `annual-completion-evidence.json`,
`annual-completion-before.json`, `annual-completion-observations.jsonl`,
`annual-completion-unchanged.json`, `annual-completion-pending.json`, and
`annual-completion-pending.png` (all under ignored `outputs/`). The
[production critical path](../plans/subscription-monetization-rollout.md#production-critical-path-reviewed-2026-09-28)
now names implementation, commercial and external gates. There is no committed
launch date. Existing monthly held fixtures start 28 October; a shorter scheduled
fixture is a candidate requiring implementation and actual acceptance, not a waived
check or permission to change the clock/evidence.
