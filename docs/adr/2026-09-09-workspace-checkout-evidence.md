---
status: accepted
owner: project
updated: 2026-09-09
tags: [adr, billing, workspace]
related: [../architecture/control-plane-contracts.md, ../flows/subscription-checkout.md]
---

# Workspace checkout evidence

Keep Subscription, Invoice, Payment and provider events in the existing global
control plane. Browser billing actions require explicit matching Workspace context
and canonical ownership plus Membership, or the existing platform override. A
provider signature is never browser authorization for another Workspace's invoice.

Use Invoice as the one-off checkout intent. Freeze Workspace, plan, cycle, paise,
currency, billing contact, plan entitlements and subscription revision before order
creation. The UUID checkout key and provider order ID are unique. PostgreSQL guards
the saved snapshot, financial fields, ownership and assigned order against updates.
Legacy invoices stay legacy; no guessed payment bindings or automatic backfill.

Order creation does not grant a trial, change an existing subscription's plan or
project entitlements. A new subscription is explicitly PAST_DUE. Captured payments
must match the saved order, amount and currency. Browser confirmation additionally
verifies the saved-order HMAC and fetches payment state from the provider. Signed
webhooks use payload.payment.entity. Both paths share Company/Invoice/Subscription
locks and an atomic activation, Payment, entitlement projection and audit write.
Identical successful replay does not renew twice or schedule another receipt.

One purchase buys one calendar month/year. Same-plan active renewal extends the
later of now and the current end date. Other eligible purchases start now. Active
plan changes need a separate proration decision. One-off checkout sets auto_renew
false; no recurring mandate is created. Explicit entitlement overrides survive.

An old pending checkout cannot overwrite a changed subscription. Such captures,
unknown/legacy orders and refunds need reconciliation; retain failed webhook events
for operator review. Failed payment attempts never revoke another successful
purchase. Billing activation never changes Workspace lifecycle.

Consequences: local transactions cannot undo a provider-created order. Receipt
delivery is best effort after commit, not a durable email outbox. Provider test-mode
acceptance and reconciliation/refunds remain separate work before commercial launch.
Paid-period expiry is now derived through the canonical policy as described below. See the flow for these explicit limitations.

## Paid-period expiry follow-through

Stored ACTIVE does not grant unlimited time. Paid access requires now < end_date;
at the exact end instant or with no end date, derive EXPIRED/recovery-only. Do not
mutate stored status, updated_at, payment evidence or Workspace lifecycle on reads.
This avoids a scheduler dependency and preserves checkout revision/replay semantics.
The same policy gates middleware, service access, boolean features and capacity
limits. Overrides cannot buy time beyond the subscription. Owner billing recovery
stays available. Same-plan early renewal extends the remaining term; after expiry,
a new captured purchase starts now and may select a different plan. Old paid-invoice
replay leaves expiry unchanged. Trials retain their existing boundary policy.

## Verified recovery and processed refunds

Reuse the same captured-payment service for owner-authorized recovery of known
invoices, with provider GET verification, an explicit reason and audit record.
Operator check is read-only by default; apply rechecks ownership under the Company
lock. Never introduce a force-paid/revision-bypass switch or initiate refunds here.

PaymentRefund is immutable evidence in the existing global billing control plane,
linked through Payment/Invoice to the Workspace subscription. It is not a business
app Workspace-owned table. Unique provider refund identity, positive amount and
PostgreSQL UPDATE/DELETE guards protect evidence; Company/Invoice/Payment locks
serialize aggregate refund projection. Only verified processed refunds contribute
to the total, which cannot exceed the original payment. Refunds do not rewrite
paid invoice evidence, subscription terms or Workspace lifecycle. Full refunds
require owner review; no automatic cancellation can invalidate a newer paid term.
Legacy/orphan/stale contracts without enough verified history remain blocked for a
separate reviewed resolution. Issuing refunds and access-review resolution are not
part of the evidence-recording path.

## Final review decisions

BillingResolution stores one immutable owner decision per invoice, linked to the
existing global billing control plane. Services authorize before provider I/O and
again under the Company lock, compare the displayed subscription revision, and
append an audit event atomically. Final replay is idempotent; conflicting decisions
are rejected. The queue is Workspace-scoped and paginated.

A full refund may retain existing access or end only the current started term from
the latest completed checkout. Ending a future renewal or an older purchase must
not revoke another paid period. A stale, known checkout may instead be closed as
fully returned using verified processed refunds covering its entire amount. This
records payment/refund history without applying old terms or granting access.
Unknown/orphan/legacy contracts remain blocked; no force-paid bypass is introduced.
