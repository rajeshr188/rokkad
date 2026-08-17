---
status: accepted
owner: project
updated: 2026-08-17
tags: [adr, workspace, lifecycle, subscription, billing]
related:
  - ../architecture/control-plane-contracts.md
  - 2026-07-02-tenant-billed-subscription-architecture.md
---

# Workspace Lifecycle And Billing Boundary

## Status

Accepted.

## Context

`Company.is_deleted` currently represents both archive visibility and access,
while model/admin hard-delete paths can erase a Workspace. Subscription has
`status`, duplicate `is_active`, trial/end dates, and time-dependent mutation in
`save()`. Workspace middleware currently uses subscription state as an entry
gate. Operational availability and commercial state therefore influence each
other without an explicit boundary.

## Decision

Workspace operational lifecycle and Subscription billing lifecycle are
independent state machines.

The smallest required Workspace states are `ACTIVE`, `SUSPENDED`, `ARCHIVED`,
and `DELETION_PENDING`. Shared-schema creation is synchronous, so no
`PROVISIONING` state is added. `DELETED` is physical absence after a privileged
retention workflow, not a stored state. Lifecycle transitions govern entry,
business mutation, recovery/export, and erasure eligibility; they never change
RLS ownership or Subscription status.

Subscription retains `TRIAL`, `ACTIVE`, `PAST_DUE`, `CANCELLED`, and `EXPIRED`.
`Subscription.status` is stored state. One billing policy derives effective
state from it, dates, and persisted provider events. `is_active` and mutation
from `save()` cease to be authorities. Provider events drive explicit,
idempotent, locked transition services. Billing recovery remains reachable in
non-active billing states and does not establish Workspace identity.

## Alternatives considered

1. Extend `is_deleted` with more booleans. Rejected because combinations create
   invalid implicit states.
2. Reuse Subscription status as Workspace lifecycle. Rejected because safety
   suspension, customer archive, payment recovery, and retention are different
   concerns.
3. Add provisioning and deleted states immediately. Rejected because current
   creation has no asynchronous provisioning and a deleted row cannot carry a
   truthful state.
4. Derive all billing state from dates. Rejected because cancellation, provider
   outcomes, and manual recovery are events, not date calculations alone.

## Consequences

Suspension/archive no longer corrupts commercial history, and payment failure
does not erase Workspace context needed for recovery. Lifecycle needs a model
migration and guarded transition service. Billing still needs a separate Phase
4 repair and webhook replay tests.

## Migration implications

Phase 3 adds the Workspace state field, maps `is_deleted` rows to `ARCHIVED`,
guards transitions, replaces hard-delete UI, and tests access/export/recovery.
Phase 4 centralizes billing transitions, removes duplicate authority, and keeps
recovery paths available. Retention/purge implementation requires an explicit
later operational acceptance step.

