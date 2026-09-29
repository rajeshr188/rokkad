---
status: accepted
owner: project
updated: 2026-09-29
tags: [billing, trial, onboarding, eligibility]
related: [2026-09-29-selected-public-trial.md, ../plans/public-workspace-trial.md]
---

# One public trial Workspace per owner account

The owner selected one 30-day public trial Workspace per owner account on
29 September. Creating another Workspace must not restart free access. Existing
internal trials and current customer access are unchanged.

Use the existing `trial.started` SubscriptionEvent as the accepted allowance
evidence. Its saved actor ID and public-trial terms version identify the accepting
account independently of current Workspace ownership, subscription status or plan.
Recognize the `public-trial-` terms namespace, including earlier accepted versions.
Internal trials without those public terms do not consume this allowance.

Keep Company-first locking, then lock the canonical owner account before the
selected Plan and eligibility check. This serializes competing starts in different
Workspaces. Subscription and event commit together: rejected or rolled-back starts
consume nothing. No new table, provider action or entitlement authority is needed.
The consent version changes and records `max_trial_workspaces_per_owner=1`.

Expiry, cancellation, ownership transfer and catalog replacement do not reset the
original actor's allowance. Receiving an existing Workspace does not consume the
recipient's own allowance. The page replaces the start action with a support
message after use; the service independently rejects a forged or stale POST.

This is an account-level limit, not proof that different accounts belong to
different people. Ordinary Workspace deletion is disabled; retained billing events
must not be removed to restore eligibility. A future physical-retention workflow
must preserve the consumed allowance before erasing its source evidence.

The selected-trial release and activation review completed later on 29 September;
the [free offer is enabled](../implementation/public-trial-release-20260929.md).
Paid billing remains paused and requires its separate acceptance.
