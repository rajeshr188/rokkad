---
status: accepted
owner: project
updated: 2026-09-27
tags: [billing, recurring, payments, evidence]
related: [2026-09-27-recurring-agreement-evidence.md, 2026-09-24-subscription-access-continuity.md]
---

# Recurring paid periods come from verified invoice evidence

September 28 amendment: the
[future-payment decision](2026-09-28-future-recurring-payment-evidence.md)
supersedes the started-period admission requirement below. Verified future money
is recorded with access held for review; it never activates early or by replay.
The remaining verification and immutable-evidence contract is preserved.

The [annual boundary amendment](2026-09-28-annual-invoice-calendar-boundary.md)
also admits the precisely verified midnight-IST anniversary period observed in
actual annual invoices; the duration rule below is amended for that shape only.

Extend the recurring agreement foundation with an immutable `RecurringCycle` in
the global billing control plane. It links one provider invoice and its exact
billing period to the existing local Invoice/Payment and Workspace agreement.
Provider invoice identity, payment identity and agreement/period identity are
unique. Company-row serialization rejects overlapping periods even under different
invoice IDs. PostgreSQL protects cycle history, Workspace/invoice/payment linkage,
and the linked invoice/payment's original financial identity. Refund state can
still change through the existing verified refund service.

Only provider-fetched paid invoices with matching captured payments qualify.
Verify subscription identity/notes and frozen provider plan; cross-check invoice,
payment, order, INR amount, full settlement and one quantity-one plan line without
add-ons. Authorization-only invoices, mismatched/partial payments and previously
unrecorded refunded payments grant nothing. Provider invoice billing_start/end are
the purchased period; never add a month to webhook receipt time or reuse the
subscription entity's mutable current period. Monthly/yearly validation currently
accepts 28-31/365-366 day periods. A period must have started, have positive valid
timestamps and not predate agreement creation. Other period shapes, scheduled
future periods and changed agreements require review, not inferred dates.

Record invoice, captured payment, cycle, entitlement projection, paid-through change,
audit and durable receipt intent atomically. A replay returns its original cycle
without changing dates/status or generating another receipt, including after a
refund. Older cycles can fill missing financial history but cannot shorten or
reactivate a newer term. An expired historical period stays expired under existing
grace/read-only policy. A newer verified purchase can recover access. Explicit
entitlement overrides survive projection; operational suspension and platform
restrictions remain authoritative.

Closed/replaced agreements, archived Workspaces and conflicting existing terms can
record financial evidence with `access_action=review`, without granting access.
The operator command exposes this result; no automatic forced resolution exists.
Recurring full-refund access termination is excluded from the manual-purchase
review action until agreement/cycle cancellation review exists. Refund rows and
retain-access evidence reuse the existing paths. Future charging is never stopped
by refund bookkeeping or local Subscription cancellation alone.

Signed `subscription.charged` and recurring `payment.captured` events share the
paid-cycle service. Supported subscription lifecycle events fetch current provider
state and append an observation only, using a null actor for provider automation.
Authorization/failure/cancellation observations do not edit purchased access.
Existing raw-body HMAC, event-ID replay checks and retryable FAILED evidence remain
the entry boundary. Unknown agreements cannot be silently reconstructed by a webhook.
Owner recovery takes explicit Workspace/agreement/provider-invoice IDs and a reason.

Recovery accepts known Test Mode agreements even when new creation is disabled;
live keys remain rejected. No schema backfill, customer authorization UI, production
activation or real recurring provider acceptance is included. Provider I/O is mocked
in boundary/concurrency tests; receipt intent is not evidence of delivery.

Provider contracts checked 2026-09-27:
[subscription events](https://razorpay.com/docs/webhooks/subscriptions/),
[subscription invoices](https://razorpay.com/docs/api/payments/subscriptions/fetch-invoices/),
[invoice entity](https://razorpay.com/docs/api/payments/invoices/entity/).
Invoice examples expose the subscription/payment/order identity, plan line and
billing boundaries needed for this verification. Actual account-specific payload
acceptance is still required before enabling a paying pilot.
