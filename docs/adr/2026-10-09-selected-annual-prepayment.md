---
status: accepted
owner: project
updated: 2026-10-09
tags: [billing, annual, prepaid, razorpay]
---

# Offer annual prepayment beside monthly automatic renewal

The owner chooses INR 14,990 once for twelve calendar months, six total members,
no automatic renewal, alongside INR 1,499 monthly recurring billing. Annual saves
INR 2,998 versus twelve monthly collections. Seller remains the confirmed individual,
unregistered for GST; no customer GST is charged. Annual recurring is separate and
remains unpublished. Initial annual rollout is JSK, retaining the monthly pilot scope.

Use one selected Plan and an independent default-zero publication setting, plus a
named Workspace cohort. Never enable the generic private catalog. The canonical
active owner with verified email reviews signed, thirty-minute terms. Active trials
must expire. Other access decisions, unsettled purchases and recurring mandates
require review. Ordinary subsequent annual prepayment on the same plan preserves
remaining paid time; there is no implicit renewal or switching of paid monthly time.

Reuse immutable Invoice snapshots, SubscriptionEvent, Payment, the one-off capture
service, entitlement projection and receipt intent. A global login/CSRF POST adapter
calls a transaction-owning service. Commit the invoice/order intent under the Company
lock before one provider order POST. A timeout or persistence error keeps that intent;
neither a fresh review nor retry creates another order. Same-key retries recover the
saved identity. Browser confirmation and signed webhooks share idempotent capture.
Publication pause never prevents recovery. Access begins on verification and lasts
twelve calendar months; replay cannot extend it. No new table or migration.

Only an explicitly reviewed cancelled, never-authorized, unpaid agreement may release
its reservation. Own short transactions around provider reads. Require zero paid and
authorization counts, no schedule/current period, no local financial/authorization
history and a complete provider invoice scan. Cancel each issued unpaid invoice with
committed single-dispatch audit; unknown outcomes are fetched, never reposted. All
invoices must then be cancelled/expired and every order attempt terminal failed.
Recheck provider identity, local revision and history under the Company lock before
setting closed_at and appending reservation.unpaid_released. Preserve all evidence,
trial dates and access. Paid/refunded/scheduled mandates still use separate policies.

Provider contracts: [Orders](https://razorpay.com/docs/api/orders/create/),
[cancel subscription](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/),
[cancel unpaid invoice](https://razorpay.com/docs/api/payments/invoices/cancel/).
Failed or uncertain order attempts need reconciliation before replacement; no
unattended retry or new charge is implied. Actual provider and deployment acceptance
are tracked in Status separately from local implementation.

A verified, closed, cancelled agreement with reservation.unpaid_released evidence
is unused history, not a permanent choice of annual billing. If every historical
agreement satisfies this condition and the existing first-purchase checks pass,
the owner may review either offer again. Monthly requires fresh signed consent and
a new agreement; original request-key replays retain the closed original. Ordinary
cancellation, paid/refunded history, pending annual invoices and uncertain attempts
remain blocked. Display the monthly offer above the previous agreement history.
Both purchase services still serialize reservations using the same Company lock.
