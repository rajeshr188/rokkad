---
status: accepted
owner: project
updated: 2026-09-30
tags: [billing, consent, transactions, self-service]
---

# Owner preparation of the selected monthly subscription

Build self-service while existing trials run; do not enable paid publication before
the JSK pilot and release review. The initial public offer is INR 1,499/month,
zero customer GST, six members including the owner, and up to twelve collections.
Annual and replacement subscriptions remain separate reviews.

`BILLING_PUBLIC_RECURRING_BINDING_ID=0` is the default. Selecting one verified
binding, together with `BILLING_RECURRING_ENABLED`, publishes only that monthly
offer. It never enables the generic one-off/annual catalog. Current price, seats,
tax, seller, mode and the entire frozen binding snapshot must still match.

The Workspace billing page requires an active canonical owner with membership
and verified sign-in email. It issues a signed thirty-minute review containing
the owner, Workspace, binding snapshot, twelve-cycle duration, terms version and
request UUID. GET makes no billing records or provider requests. The unchecked
consent checkbox is required again on POST. The service rechecks authority,
eligibility and the reviewed snapshot under the Company lock before committing
the immutable consent event and exclusive agreement reservation together.

The exact `/app/billing/recurring/start/` POST is a global control-plane adapter
under the existing `/app/` global route convention. It accepts only the signed
Workspace identity, requires login and normal CSRF, and delegates to the existing
transaction-owning creation service. Ordinary Workspace middleware/RLS is unchanged.
The service enters explicit Workspace contexts for writes and commits intent
**before** the single provider POST. No nested transaction is manually committed,
and no tenant data is read through profile preference or browser-supplied prices.

Only a Workspace without billing/access history, or with a naturally expired trial
and no financial/agreement/access-exception history, may create its first public
agreement. Capacity includes pending invitations. Active trials cannot be cut short.
Existing agreements always retain their owner recovery/cancellation page. A double
click reuses the same verified attempt; another review or unknown outcome cannot
create a second mandate. Provider timeout or local persistence failure retains the
durable reservation for support reconciliation. No automatic replacement is offered.

Agreement creation grants no access and sends no email. Existing Razorpay Checkout
authorization, signed paid-cycle verification, exact-period access, cancellation,
invoice and durable receipt services remain authoritative. Trial expiry never
authorizes a charge. Receipts use the frozen invoice recipient and amount.

No new table, migration or queue is required. The existing monitored mail dispatcher
can include receipts by removing its invitation/account-only source filter after
the live queue and first receipt have been reviewed. That operational change stays
paused; fake SES tests are not evidence of live receipt delivery.
