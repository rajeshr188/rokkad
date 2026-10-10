---
status: active
owner: project
updated: 2026-10-10
tags: [flow, billing, payments, operations]
related: [../adr/2026-09-09-workspace-checkout-evidence.md, ../plans/project-hardening.md]
---

# Workspace subscription checkout

## Choose monthly or annual after an unused cancellation

Available plans offers monthly automatic renewal (INR 1,499/month) and annual
one-time prepayment (INR 14,990). After an explicit verified unused-mandate release,
the monthly page shows fresh consent above the cancelled agreement history.
Selecting monthly creates a new agreement only after owner consent; it cannot
restart the old agreement. Selecting annual creates a one-time order. Once either
purchase is in progress, resolve it before switching to prevent overlapping payments.

## Annual prepaid journey (enabled for JSK, 9 October)

Open [JSK Annual prepaid payment](https://rokkad.com/w/jsk/settings/billing/annual/)
as its canonical owner. Billing, Plans and Recurring payments link to it. Review
INR 14,990 once for twelve months, six members, zero customer GST, no recurring mandate
and no automatic renewal. Accept the explicit checkbox and choose Continue to one-time
payment. Complete your chosen available payment method on Razorpay.

Closing checkout grants no paid access. A verified capture records one invoice,
payment and twelve-month term, preserves historical trial dates, and queues a receipt.
Browser confirmation and signed provider callbacks share the same idempotent writer.
If confirmation is uncertain, Retry payment confirmation checks that same payment;
check Billing/contact support rather than paying again. An unknown order creation
retains its invoice reservation and needs provider-identity reconciliation; a failed
payment attempt also requires review before a replacement purchase.

The paid year starts when the payment is verified. Later voluntary annual renewal
on the same plan adds a year after the existing paid end if it is still future.
There is no automatic debit at expiry. Normal seven-day grace/read-only policy applies.
The current pilot still needs its first real capture, invoice/access and receipt checks;
routine receipt sending has not yet been enabled.

JSK's unfinished monthly agreement and unpaid invoice were verified cancelled, and
the unused reservation explicitly released. No successful charge or refund occurred.
The historical agreement stays visible; it cannot be reactivated. Other paid recurring
or refunded agreements need their own review; this is not a general mid-term switch.

Operator recovery: release_unused_recurring takes an explicit Workspace, actor,
agreement and reason. Only a cancelled never-authorized unpaid mandate qualifies;
it cancels issued unpaid invoices once and verifies all attempts terminal failed before
release. For an uncertain annual order, public_prepaid.reconcile_order binds a located
provider order only when its saved receipt, amount, currency and Workspace match. It
never creates or pays an order; normal payment reconciliation follows separately.


## Monthly subscription journey (current)

**8 October rollout:** only JSK can start the paid monthly flow. Its owner can
review the offer now, then continue after the unchanged trial ends at 23:39:08 IST.
The named pilot is live; first real payment/receipt acceptance and wider publication
are still pending. Other Workspaces keep their existing access and free-trial
options. See the [pilot plan](../plans/monthly-billing-pilot.md).

1. **See the offer.** The owner opens Workspace Settings → Billing → Plans →
   Review monthly subscription (or Recurring payments). The offer is INR 1,499
   monthly for one Workspace, owner plus five staff, up to twelve collections,
   with no customer GST under the current seller setup. During an active trial,
   the offer shows its end time and cannot create a payment agreement.
2. **Accept terms after expiry.** Continue with monthly subscription saves the
   owner’s current terms and one durable Razorpay agreement attempt. It does not
   charge or grant paid access. Duplicate clicks cannot create a second mandate.
3. **Authorize with Razorpay.** The same owner reviews the saved agreement and
   chooses Authorize recurring payments. Payment details and any authentication
   remain on Razorpay. Merely closing Checkout does not establish payment.
4. **Verify the payment.** Signed provider events and fetched paid-invoice/captured-
   payment evidence establish the exact amount and period. Rokkad records one
   invoice/payment/cycle, activates the paid plan and queues one receipt. Missing
   or uncertain confirmation requires recovery of that same attempt, not repayment.
5. **Continue or cancel.** Subsequent verified recurring collections extend access
   by their actual paid periods. Stop future renewals cancels the provider mandate
   while preserving paid time; it is not a refund. The agreement stops after its
   maximum collections; replacement currently needs support review.

After JSK acceptance, clearing the named cohort opens the same selected offer to
other eligible owners. JCL and Lakshmi each need their own owner consent and
payment. Expired trials can convert after verified capture; annual and existing
agreement replacement are not part of this public flow.

For new users, public pricing currently shows the available 30-day free trial and
the planned INR 1,499 continuation while the pilot is restricted. Wider activation
automatically changes home/pricing/FAQ to show available monthly billing. Users
verify email, create a Workspace, configure the business and then review its Plans
page when ready to activate lending. Configuration does not start a trial or grant
commercial access. One public trial
Workspace per owner is optional; a new history-free Workspace can choose paid
billing directly once public activation is approved. An active trial must finish
before paid consent. Team invitations reserve seats within the six-member limit.
No card is required for the trial and it never converts or charges automatically.

Receipt delivery is not yet automatic for this pilot: scheduled mail remains
invitation/account-only. Review and verify the first receipt, then enable the
reviewed ongoing scope before broader paying-customer launch. Existing billing
records and saved invoices remain available independently of email delivery.

The one-off checkout and earlier Test Mode preparation below are separate,
historical implementation details; generic checkout remains disabled.


Provider setup/test-mode preparation resumes under selected FW-019 through
[FW-002](../plans/future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance).
The owner reports SaaS reclassification, application submission and completed KYC;
account approval and Live/Test activation were reported on September 27. Saved
test keys now verify Payments/Plans/Subscriptions access; workflow acceptance remains open. Use the
[active rollout](../plans/subscription-monetization-rollout.md#test-mode-preparation)
to select an isolated rehearsal runtime before installing private test credentials.
The acceptance below remains required before real paid onboarding.

New checkout/order routes now require `BILLING_CHECKOUT_ENABLED=True`; the default
is false. Use dated, audited platform administrator access decisions while provider
acceptance remains unfinished. Existing captured-payment confirmation, reconciliation,
webhook and invoice routes retain their verification and permissions. See the
[access policy and operator guide](../domain/subscriptions.md).

This is SaaS subscription billing, separate from borrower loan repayments. It does
not introduce accounting or license-scoped access.

## Owner flow

For an operator-prepared recurring agreement, Settings > Billing > Recurring
shows the saved amount, interval and cycle count. The owner explicitly consents
before opening Checkout. Test bindings say Test Mode; live bindings use ordinary
payment consent. The signed authorization return grants no access: the verified
paid invoice determines the exact paid period. Stopping future renewals preserves
paid time. Pausing new authorizations leaves existing payment recovery and
cancellation available in the configured matching mode. Scheduled live starts and
replacement agreements remain unavailable pending further review. This local code
has not been activated in production. See the
[recurring runbook](../implementation/recurring-agreements.md).

The separately gated one-off checkout flow is:

1. Open the target Workspace's Settings > Billing and select a plan.
2. Select monthly/yearly. The displayed price reloads for that cycle. Starting a
   trial is a separate explicit action; paid checkout charges immediately.
3. Pay creates an order through `payment/order/` (`order-create`). The browser sends
   plan, cycle and a UUID checkout key. The server fixes the actual price and GST
   rounded to paise. Razorpay receives that amount, INR and a unique CHK reference.
4. Checkout returns the payment IDs/signature to `payment/create/` (`payment-create`).
   The server checks owner/context, invoice scope, saved-order HMAC, fetched payment
   identity, captured state, amount and currency. Browser plan/price fields cannot
   choose the activated contract.
   After Razorpay returns payment evidence, the button becomes Retry payment
   confirmation if verification fails. It sends the same payment IDs/signature
   without reopening Checkout; cycle changes are disabled. After leaving/reloading
   the page, inspect Billing before starting another purchase.
5. Activation writes payment, paid invoice, commercial dates, plan entitlements and
   audit evidence atomically. A receipt goes to the saved billing contact after
   commit. Open Billing to view/download the Workspace invoice.

Retries with the same checkout key reuse an already saved provider order. Captured
payment retries return the original result. Multiple independently created orders
are not interchangeable: once the subscription changes, older unpaid orders need
operator reconciliation. Do not pay a second order to fix a slow confirmation.

New checkouts require ACTIVE or SUSPENDED Workspace state. Already captured payments
can be recorded even after Workspace suspension/archive without restoring its
operational lifecycle. Billing remains owner-only, using Company.owner_id rather
than a role's display name. Another Workspace's invoice returns no payment access.

## Provider setup and events

Configure matching `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and a separate nonempty
`RAZORPAY_WEBHOOK_SECRET` in the selected deployment's private runtime environment.
Do not copy live keys to examples. Configure the global callback
`/subscriptions/webhook/razorpay/` on the deployed HTTPS origin. A Workspace-specific
callback is not the provider entry point. The [isolated Test Mode rehearsal](../implementation/billing-test-rehearsal.md)
verified wallet captures, signed events, recovery and refunds; live/provider-method
and receipt-delivery acceptance remain separate.

Verified raw-body HMAC and provider event ID bind the stored event. The event row is
locked before replay checks; reuse of an event ID with a different body is rejected.
`payment.captured` reads `payload.payment.entity` and uses the same capture service
as browser confirmation. `payment.authorized` grants nothing; `payment.failed`
does not revoke paid access. Subscribe only to implemented events for routine
processing. `refund.processed` verifies the exact refund and payment through provider
GET requests before recording immutable evidence. Other unsupported events remain
FAILED and return 500 for review.

References: [create order](https://razorpay.com/docs/api/orders/create/),
[payment entity](https://razorpay.com/docs/api/payments/entity/),
[payment webhook payloads](https://razorpay.com/docs/webhooks/payments/),
[refund events](https://razorpay.com/docs/webhooks/refunds/) and
[refund entity](https://razorpay.com/docs/api/refunds/entity/).

## Recovery and acceptance still required

Known Test Mode recurring agreements now have a separate
[paid-cycle path](../implementation/recurring-agreements.md#paid-cycle-processing-and-recovery)
behind the same signed webhook. `subscription.charged` and recurring captured
payments require provider-fetched invoice/payment/agreement/plan evidence. Exact
provider invoice periods drive access, never callback arrival time. Lifecycle
observations alone grant or revoke nothing. The existing owner checkout above
remains one-off. The separate **Recurring payments** page supports owner
authorization of operator-prepared Test Mode agreements, status refresh, known
paid-invoice recovery and cancellation of future renewals. Cancellation preserves
paid access and reports uncertainty until verified; creation remains operator-only.
See the [owner-flow runbook](../implementation/recurring-agreements.md#owner-authorization-and-cancellation).

If recurring collection is **Pending**, the owner page explains that Razorpay may
retry. If it is **Halted**, the page explains that automatic collection has stopped.
Already-paid access follows its original end/grace policy; an unpaid invoice adds
no time. Refresh status or contact support to review the existing agreement and
invoice before making another payment or creating a replacement.

A verified payment for a future recurring period appears under **Payments awaiting
access review** and in invoice history. Its exact period and payment are saved;
existing access stays unchanged. The invoice and receipt explain the hold. Contact
support for billing review: rechecking the invoice or reaching its start date does
not activate it. Review payments remain visible even after agreement replacement.
An operator can now run the [authorized review command](../implementation/recurring-agreements.md#applying-a-held-period)
once the period starts and before it expires, after reviewing the current
subscription. Successful application appears as **Applied after billing review**;
the invoice shows when it was reviewed. The Billing dashboard remains the source
for current access. Command retries do not reactivate access after later changes.

- Provider success plus local rollback/timeout can leave an orphan provider order.
  PostgreSQL and Razorpay are not one transaction. Reconcile using the CHK receipt,
  Workspace note and provider IDs before creating another attempt; never manually
  mark an unverified invoice paid. The recovery tools below require a known checkout
  invoice; they cannot recreate missing/orphan contracts or invent capture history.
- Stale subscription revisions, unknown orders and legacy invoices fail closed.
  Inspect FAILED ProviderWebhookEvent rows and provider evidence. Known stale
  invoices can be resolved after a verified full return, as described below. Existing invoice rows
  are not backfilled with inferred contracts.
- Processed partial/full refunds are recorded individually; duplicate deliveries
  cannot increase totals twice. Partial refunds retain access. Full refunds retain
  access pending owner review (the conservative default); they never revoke a newer
  purchase. Owners can now record a final access decision as described below.
  Chargebacks, issuing refunds and proration remain separate work. Unsupported events remain unresolved.
- A paid commercial term is active only while stored status is ACTIVE and now < end_date.
  At the exact end time, the canonical policy derives EXPIRED without rewriting
  stored status, events or Workspace lifecycle. Missing end_date fails closed.
  The separate activity policy now provides seven days of normal access after natural
  expiry, then read-only access. Platform extensions can preserve stored entitlements;
  an entitlement override alone does not extend commercial activity permission.
  Billing/invoice recovery remains owner-authorized; no scheduler is required.
  A newly captured purchase starts a new term after expiry (and may select another
  plan); replaying an already paid invoice never revives an expired term.
  Natural trial expiry uses the same seven-day grace. Cancellation/past-due/stored
  expired states do not receive automatic grace. Latest platform restrictions remain
  effective across renewal until lifted or expired; lifecycle restrictions always win.
- After-commit receipts are best effort: delivery failure is logged and cannot undo
  payment. A crash may miss delivery; there is no durable receipt retry queue yet.
- Complete provider test-mode browser/webhook/retry acceptance on an HTTPS endpoint
  before enabling real paid onboarding. Current tests mock all provider I/O and mail.

## Migration

Run `python manage.py migrate --settings django_project.settings.migration` with
the migration owner. Migration 0004 adds checkout evidence and unique order IDs;
0005 protects saved evidence against rewriting. Migrations 0006/0007 add immutable
processed refund evidence in the existing billing control plane. Check duplicate non-null order IDs
before migration; do not delete financial records to satisfy the constraint.
Historical invoices remain readable through Workspace-scoped routes.

## Recover a known payment or refund

Open **Settings > Billing > invoice > Check or recover a payment**. Supply the
existing provider payment ID and a review reason. For a processed refund also
supply its refund ID. **Check provider records** validates identifiers, Workspace,
amount and currency without writing. **Verify and apply** re-fetches evidence and
records the result atomically. A successful check does not guarantee application:
a stale subscription revision, missing capture history or conflicting refund totals
can still block application. The invoice shows total processed refunds and flags a
full refund for owner access review. Original paid invoice and subscription terms
remain intact.

Trusted operators can use the same owner-authorized service through:

```powershell
python manage.py reconcile_subscription_payment --workspace-id 12 --actor-id 7 --invoice-id 42 --payment-id pay_example --reason "Reviewed provider dashboard"
```

This is read-only by default. Add `--apply` to save, or `--refund-id rfnd_example`
to check/record a processed refund. IDs above are placeholders. Use the restricted
runtime settings, not migration settings. Actor must be the current owner with
Membership or the existing platform override. The command establishes and clears
Workspace context. Each apply attempt that succeeds appends a reason/actor audit
record; replay does not duplicate capture, refund or receipt effects.

These tools only fetch provider evidence; they never issue charges/refunds. Refunds
must already be processed at Razorpay. Pending/failed refunds cannot change the
local total. Recovery keeps strict order/Workspace/price/revision checks. For unknown
orders, missing contracts, stale captures or refunds without a recorded capture,
stop and retain the failed webhook for a separately reviewed support resolution.
Do not edit frozen evidence or bypass revision checks. After resolving the cause,
provider redelivery can safely retry FAILED events; processed replay is harmless.

No durable receipt resend queue or general failed-event replay command is added.
Before commercial launch, exercise recovery and review decisions with Razorpay
test-mode webhooks on HTTPS. Truly orphan/legacy contracts remain a support case;
never infer missing ownership or purchased terms.

## Resolve a billing review

Open **Settings > Billing > Billing reviews**, then the invoice. The paginated queue
shows unresolved full refunds and unpaid checkouts. An unpaid checkout may be
abandoned rather than problematic; check its payment first. Fully processed and
resolved invoices leave the queue but retain their visible final decision.

Under **Resolve billing review**, choose a decision and enter a reason:

- **Retain existing access and expiry**: acknowledges a recorded full refund without
  granting time, reactivating cancelled access or changing its expiry.
- **End the current refunded term now**: cancels the subscription through the
  canonical transition service. It requires a full recorded refund, the latest
  completed checkout, matching current plan/end date and a term that has started
  and has not expired. It cannot cancel newer purchases or unstarted renewal terms.
- **Record stale payment as fully returned**: for a known issued checkout whose
  saved subscription revision is stale, supply its payment ID and all processed
  refund IDs (space-separated, maximum 20). Provider GET checks must prove the exact
  order, amount, currency and full refund. It records the received-and-returned money
  without granting a term, changing the current subscription or sending a welcome
  receipt. The invoice remains financial evidence with its full refund and decision.

Review submissions include the subscription revision you saw; a changed subscription
requires reloading before a new decision. Identical replay returns the original
resolution, while a conflicting decision is rejected. Decisions, actor, reason and
before-state evidence are immutable. Normal Workspace ownership/membership checks
apply again under the Company lock. No Workspace lifecycle or loan data changes.

These are final decisions, not editable annotations. Partial refunds cannot close
an access review or a stale-payment return. An orphan provider order with no frozen
local checkout cannot be resolved through this screen; support must investigate
provider evidence without fabricating a contract. Failed provider events are retained;
a late callback for an already resolved payment cannot activate access again.

Migrations 0008/0009 add and protect BillingResolution in the global billing control
plane. Existing invoices, payment/refund evidence and tenant isolation remain intact.
