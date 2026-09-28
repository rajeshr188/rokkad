---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, recurring, payments, evidence]
related: [2026-09-27-recurring-paid-cycles.md, ../implementation/recurring-agreements.md]
---

# Record future recurring payments without granting early access

Subsequent increment: the [held-access decision](2026-09-28-held-recurring-access-resolution.md)
adds the separate authorized resolution workflow described as pending below.
The original financial evidence and replay/early-access restrictions are preserved.

Actual Razorpay Test Mode accelerated renewal captured money for a future monthly
invoice. Rejecting that invoice entirely leaves received money outside local
financial history. This decision changes financial admission, not the commercial
access clock or provider billing dates.

Accept a fully verified, captured, unrefunded future invoice into the ordinary
Invoice/Payment/RecurringCycle transaction. Keep the existing exact identity,
frozen amount/currency/plan, period duration, agreement creation, overlap and cycle
count checks. Payment time must not be in the future. The future period's exact
start/end are retained; never infer them from the mandate's mutable current period.

Record `access_action=review` and the frozen invoice marker
`access_review_reason=future_period`. Do not change an existing Subscription's
dates, status, plan, renewal setting or entitlements. If no Subscription exists,
create only the non-active financial parent required by Invoice, with past-due
status, no trial or entitlements, and an end timestamp equal to payment time.
This parent is not a purchased access grant.

Held review cycles are financial evidence, not evidence of already-applied access.
Exclude them when evaluating whether a later started cycle can safely replace
existing manual/trial terms or retain previously granted recurring time.

The cycle and invoice snapshot remain immutable. Replay returns the original
record without access changes, including when the period subsequently starts or
the payment is refunded. No receipt is duplicated. Future receipts and the owner
page state that payment is recorded, access is unchanged, and a separate billing
review is needed; they do not promise automatic activation at the start date.
Show unresolved review periods even if they are older than the last twelve cycles.

This increment reuses existing review evidence and introduces no table, migration,
timer, activation route, force-paid action or reservation release. Applying a held
period requires a separate authorized, audited workflow with fresh refund, current
subscription, agreement and Workspace checks. That workflow remains a launch
prerequisite. Existing refund recording works for the newly recorded money; a
refund alone neither grants nor removes access.

Test Mode-only provider recovery and the default-off creation/authorization gates
remain in force. No live activation, production deployment or receipt dispatch is
part of this decision.
