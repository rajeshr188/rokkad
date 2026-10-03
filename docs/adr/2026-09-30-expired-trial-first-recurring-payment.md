---
status: accepted
owner: project
updated: 2026-09-30
tags: [billing, trial, recurring, pilot]
related: [2026-09-28-mode-matched-live-recurring-workflows.md, ../plans/monthly-billing-pilot.md]
---

# Apply the first verified recurring payment after natural trial expiry

The owner selected JSK as the first monthly pilot after its existing trial ends.
Its trial uses Plan 1; the reviewed paid offer uses Plan 2. Existing creation and
authorization correctly refuse unexpired trial time, but the paid-cycle handler
also holds a different-plan first payment after expiry. The trial model's generic
end_date can extend beyond trial_end_date and is not evidence of paid coverage.

Allow the existing paid-cycle transaction to change the plan and apply the exact
verified provider period for a subscription still marked trial only when:

- The trial has an explicit end, no later than both agreement creation and the
  provider period start. The period has started and has not expired.
- The Workspace is active, its agreement is current and verified, and members
  plus pending invitations fit the frozen offer.
- There is no legacy mandate, earlier invoice of any status, or recurring cycle
  history for this Workspace. Other histories require separate review.
- All existing provider identity, captured amount, currency, refund, period,
  overlap, mode and idempotency checks pass.

Switch to the frozen paid plan, use its entitlement projection and the exact
period end, and record the previous plan, generic end and trial end in the existing
subscription transition event. Preserve original trial dates, subscription start,
owner, Workspace lifecycle and historical events. The generic trial end_date is
replaced by verified paid coverage; it is not carried forward as paid time.

Unqualified trial payments remain recorded for review without changing access.
Future periods remain held; replay never changes the original decision. Receipt
queue failure rolls back financial records and the transition together. No new
table, migration, force-paid action, scheduled live start, early trial conversion
or paid-plan replacement policy is introduced. Creation/authorization stay gated.

This local correction does not prove Razorpay failure simulation or held-period
acceptance. The pilot risk review separately records those unverified scenarios.
