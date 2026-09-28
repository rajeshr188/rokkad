---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, subscriptions, refunds, replacement]
---

# Release reviewed, fully refunded Test Mode agreements explicitly

Cancellation and a refund access decision still preserve the Workspace reservation.
An explicit operator command can now close a narrow settled case: a verified,
immediate-start Test Mode mandate that is cancelled, has no next charge, and has
at least one paid cycle, with every invoice fully refunded and its access review
completed. Scheduled authorizations, empty/unknown attempts, unpaid invoices,
unreturned periods, completion/expiry and prepaid/trial conversions remain reserved
for separate policies. No automatic release follows provider status alone.

Require a current active owner/platform actor, explicit Workspace, reason and
reviewed Subscription revision. Own short Workspace transactions around provider
reads. Scan provider invoices through the final empty page, reject repeated IDs,
and require the exact local cycle set and provider paid count. Re-fetch each
invoice/payment/plan, every saved processed refund, and all order payment attempts.
Only the known refunded payment and terminal failed attempts are accepted. Recheck
the invoice set and cancelled mandate after those reads. An outage, incomplete
collection, extra payment or mismatch leaves the reservation intact.

Under the Company lock, revalidate authority, revision, local full-refund totals,
refund identities and access decisions. Subscription must be cancelled, without a
legacy mandate, future trial, unpaid purchase or other unsettled paid/held invoice.
Set existing `closed_at` and append one immutable `reservation.released` event
atomically. Existing database guards freeze closed history. Replay returns that
event without provider writes or reopening. The command changes no Subscription,
entitlement, invoice, payment, refund or receipt. No schema change is needed.

A replacement uses the existing durable creation workflow with a new request key.
It gets no access until independently verified payment. The first due replacement
cycle may replace a longer refunded historical end date only when the latest
release matches the unchanged cancelled Subscription revision, the replacement
was created after release, and no unreturned paid evidence remains. Apply its exact
period end and frozen offer; retain the refunded period in immutable history.
Future payments still go to review. Old payment/release replays cannot reactivate
access or close a newer reservation.

Provider read contracts:
[subscription invoices](https://github.com/razorpay/razorpay-python/blob/master/documents/subscription.md),
[order payment attempts](https://razorpay.com/docs/api/orders/fetch-payments/).
This bounded Test Mode workflow does not constitute live replacement acceptance.
