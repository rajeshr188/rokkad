---
status: active
owner: project
updated: 2026-09-09
tags: [flow, billing, payments, operations]
related: [../adr/2026-09-09-workspace-checkout-evidence.md, ../plans/project-hardening.md]
---

# Workspace subscription checkout

Provider setup/test-mode acceptance is currently shelved at the owner's request as
[FW-002](../plans/future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance).
The steps below are a future acceptance guide, not a current request to configure
Razorpay. They remain required before real paid onboarding.

This is SaaS subscription billing, separate from borrower loan repayments. It does
not introduce accounting or license-scoped access.

## Owner flow

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
callback is not the provider entry point. No real payment/provider rehearsal has
been performed for this increment.

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
- Paid access is available only while stored status is ACTIVE and now < end_date.
  At the exact end time, the canonical policy derives EXPIRED without rewriting
  stored status, events or Workspace lifecycle. Missing end_date fails closed.
  Features and limits are unavailable even with explicit entitlement overrides.
  Billing/invoice recovery remains owner-authorized; no scheduler is required.
  A newly captured purchase starts a new term after expiry (and may select another
  plan); replaying an already paid invoice never revives an expired term.
  Trial expiry retains its existing policy; there is no implicit paid grace period.
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
