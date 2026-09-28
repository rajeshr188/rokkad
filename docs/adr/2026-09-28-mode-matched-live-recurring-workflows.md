---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, recurring, provider-mode, recovery]
related: [2026-09-28-live-recurring-catalog-preparation.md, 2026-09-28-explicit-billing-provider-mode.md]
---

# Use the existing recurring workflow in the saved provider mode

The catalog can now represent a reviewed live plan, but agreement services still
refuse live credentials. Extend the existing financial workflow to explicit,
matching test/live configuration rather than maintaining a second implementation.
This supersedes the Test Mode-only workflow restriction in the catalog decision;
it does not activate production or establish provider acceptance.

New agreement creation and owner authorization require the default-off
`BILLING_RECURRING_ENABLED` flag. Live creation additionally requires a nonblank
webhook secret and an evidence inventory without test bindings, test one-off
invoices or unclassified one-off invoices. A saved binding must match the configured
mode and frozen commercial offer. Keep web, commands and workers on the same mode;
concurrent mixed-mode processes and promotion of a populated rehearsal database
remain unsupported. Catalog registration still requires both purchase flags off.

Creation remains operator-prepared with active owner/platform authority, Workspace
serialization, six-member capacity checks and one committed attempt before one
provider POST. Unknown outcomes retain the reservation and require locating the
original provider identity, followed by GET-only reconciliation. No new endpoint,
schema or automatic creation retry is added.

Authorization uses the server-held subscription ID and verifies the returned
payment signature against that identity. Live Checkout and owner consent omit the
Test Mode label. Authorization and mandate lifecycle changes alone grant no access.
Signed paid events and owner recovery verify matching mode, invoice/payment/plan
identity, captured amount/currency and exact period before recording one cycle,
invoice, payment and receipt intent. Replays do not reactivate access.

Pausing new authorizations must not disable existing confirmation, status refresh,
creation reconciliation, paid-cycle recovery, cancellation, held-period application
or explicit refund/access review. These operations use the saved binding's mode and
the existing authority/evidence checks. Unrelated conflicting database evidence
blocks new live authorizations but cannot prevent recovery of an already matching
agreement. Wrong or disabled credentials still fail closed.

Cancellation commits intent and a dispatch claim before at most one provider POST;
uncertain cancellation uses GET-only recovery. Paid time and reservations remain.
Future captured periods stay held until an eligible, fresh, explicit access review.
Refund review requires the same exact current period and verified settlement as
before; it never initiates a refund. Existing receipt dispatch requires saved live
evidence, live worker mode and configured mail delivery.

Scheduled live creation/authorization and live reservation release are deliberately
unavailable. Prepaid/trial transitions, replacement settlement policy and provider
acceptance need separate work. Configuration reports distinguish supported live
code from launch acceptance: `live_recurring_supported=true`, `launch_ready=false`.
Prices/tax, mandate duration, supported payment methods, HTTPS callback/monitoring,
reviewed production deployment and a bounded pilot still require launch review.

Validation uses fictional identifiers, dummy live-prefixed keys and mocked provider
responses in the test database. No live credential or provider request is used.
Official provider contracts checked 28 September:
[Checkout integration and signature verification](https://razorpay.com/docs/payments/subscriptions/integration-guide/)
and [subscription cancellation](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/).
