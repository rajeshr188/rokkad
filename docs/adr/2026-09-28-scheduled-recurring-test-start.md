---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, subscriptions, testing]
---

# Freeze an optional scheduled start for Test Mode agreements

The existing accelerated monthly renewals cover periods beginning 28 October.
FW-019 needs actual naturally due held-access acceptance without changing a clock
or rewriting financial evidence. Razorpay documents an explicit `start_at` and
early Test Mode charging. A short scheduled fixture can investigate whether the
provider preserves that future invoice boundary; it is not acceptance by itself.

The operator preparation service and command accept optional `start_at` /
`--start-at` as an integer Unix timestamp. New attempts require a representable
future instant. The existing immutable request snapshot stores it before the
single provider POST. Request-key replay must match it, even after time passes;
replay never creates another provider agreement. Every later provider agreement
verification requires the exact frozen timestamp. Omitted schedules retain the
existing immediate behavior.

Paid invoice periods cannot begin before this frozen start. Existing amount,
currency, plan, period, refund, ownership and idempotence checks remain mandatory.
Future captured periods still require a separate audited access review. New
authorization of a still-Created agreement is blocked once its scheduled start
passes; reconciliation and cancellation remain available. The owner page shows
the exact scheduled time and distinguishes authorization/token payment from paid
access. Authentication alone never creates an invoice, receipt or paid term.

This does not implement conversion of existing trial/prepaid terms, change the
commercial mandate duration, introduce a scheduler or enable Live Mode. No new
schema or exception to immutable evidence/Workspace isolation is required.

Provider references checked 28 September 2026:
[create subscription](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/)
and [Test Mode](https://razorpay.com/docs/payments/subscriptions/test/).
Actual provider invoice dates determine whether the shorter fixture is useful;
never relax validation or alter saved dates to make the rehearsal pass.
