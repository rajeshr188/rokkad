---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, recurring, access, evidence]
related: [2026-09-28-future-recurring-payment-evidence.md, ../implementation/recurring-agreements.md]
---

# Apply eligible held recurring periods through explicit review

Future captured payments are recorded without early access. Add a bounded,
operator-invoked application command for those future-period holds once due.
This supersedes the earlier decision's absence of an access-resolution workflow;
it preserves its immutable payment evidence and prohibition on timer/replay activation.

Use the existing canonical owner/platform billing authorization, active actor and
explicit Workspace context. Require a reason and the reviewed Subscription
updated_at revision. Refetch invoice, payment, agreement and plan from Razorpay
using Test Mode credentials; exact evidence must match the saved cycle and the
payment must be captured with no refund. Under the Company lock, recheck ownership,
revision, Workspace lifecycle, agreement reservation, local refund evidence, plan,
existing dates and member/invitation capacity. Local refunds share this lock.
Provider verification is a point-in-time read, not a distributed transaction;
a later refund remains governed by the existing separate refund-review policy.

Only original future-period holds qualify. Require period_start <= now < period_end,
an ACTIVE Workspace, a current verified/unclosed agreement, matching plan and no
overlapping or newer subscription/trial time. Local cancelled/trial subscriptions
remain separate review cases. Provider mandate cancellation does not discard a
paid period: an unclosed cancelled mandate may still qualify. Closed/replaced
agreements, other review reasons, expired holds and plan conflicts stay blocked.

Set the exact saved period end, transition through the ordinary billing service,
and project the frozen entitlements while preserving explicit overrides. Never
change renewal settings, platform access decisions, membership, Workspace lifecycle,
invoice/cycle snapshots or provider dates. Never initiate a charge/refund or release
an agreement reservation. Existing platform restrictions and RLS remain effective.

Record one global control-plane `RecurringAccessResolution` per cycle, linked
through the cycle's immutable Workspace agreement. Store actor, reason, verified
provider evidence and before/after Subscription revisions and terms. Migration
0017 adds a unique cycle link and PostgreSQL insert-linkage/immutability guards.
The application and resolution/audit records commit atomically. A repeated command
returns the saved resolution without reapplying access, even after later cancellation,
refund or expiry. There is no generic model permission or tenant-business table.

Resolved cycles count as previously applied access for subsequent paid cycles.
The owner list removes them from unresolved reviews and displays the resolution;
invoice detail and newly rendered receipt wording describe the historical review
outcome without promising current access. Existing queued/sent receipt artifacts
are not rewritten and no second receipt is queued.

No timer, owner web mutation route, live activation or production deployment is
included. Actual future test evidence must remain held until due; success branches
use isolated automated tests, never a changed rehearsal clock or provider dates.
