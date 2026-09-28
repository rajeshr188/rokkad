---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, recurring, provider, dates]
related: [2026-09-27-recurring-paid-cycles.md]
---

# Accept verified annual invoices ending at midnight IST

Actual INR Test Mode authorization produced an annual paid invoice beginning
28 September 2026 at 01:08:48 IST and ending 28 September 2027 at 00:00 IST.
The captured amount matches the frozen annual offer, but the elapsed duration is
364 days, 22 hours, 51 minutes and 12 seconds. The existing minimum of 365 full
days incorrectly rejects this financial evidence.

Retain the existing monthly 28-31 and annual 365-366 elapsed-day checks. Add one
narrow annual case: duration strictly greater than 364 and less than 365 days,
with the fetched invoice end exactly midnight Asia/Kolkata on the start date's
next calendar anniversary. Clamp February 29 to February 28 in a non-leap year.
This provider boundary uses a fixed timezone, independent of UI timezone settings.
Arbitrary short periods, neighboring seconds and a whole missing day do not qualify.
Monthly admission is unchanged; other provider period shapes still need review.

This calculates an expected boundary only to validate provider evidence. Persist
the original invoice start/end timestamps unchanged; never add inferred time to
access. Identity, plan, full payment, refund, agreement creation, overlap, cycle
count and payment-time checks remain required. Future periods still need separate
access review; replay remains idempotent. No migration or live activation.

This amends the duration rule in the
[paid-cycle decision](2026-09-27-recurring-paid-cycles.md). Actual provider evidence
and acceptance scope are in the [runbook](../implementation/recurring-agreements.md).
