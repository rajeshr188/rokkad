---
status: accepted
owner: project
updated: 2026-08-17
tags: [adr, workspace, entitlement, subscription, features]
related:
  - ../architecture/control-plane-contracts.md
  - 2026-07-02-tenant-billed-subscription-architecture.md
---

# Workspace Entitlement Contract

## Status

Accepted.

## Context

Plans currently contain feature booleans and numeric limits,
`SubscriptionEntitlement` duplicates them into rows,
`Subscription.can_access_feature()` reads Plan directly, seat capacity falls
back from entitlement to Plan, and `SubscriptionAccessService` mixes
authentication, Membership, billing, and features. Missing feature rows are
often treated as enabled. Business-facing module metadata also carries feature
codes without a canonical typed resolver.

## Decision

One entitlement service is the only runtime feature/limit API:

```python
entitlements.enabled(workspace, "loans.core")
entitlements.require(workspace, "notify_v2.whatsapp")
entitlements.limit(workspace, "workspace.max_members")
```

Codes are stable, namespaced identifiers registered centrally. Business
capabilities own their meaning; the control plane owns validation and
resolution. Boolean and numeric results are typed. Missing, malformed,
disabled, or commercially unavailable paid grants fail closed. Always-on
features require explicit defaults.

Plan fields remain commercial inputs. `SubscriptionEntitlement` is the target
effective Workspace projection, consumed only through the service. Overrides
must have provenance, actor, reason, and optional expiry and must survive normal
plan projection intentionally. Billing effective state is an input to
entitlement resolution, but entitlement denial never changes request identity,
Membership, lifecycle, or RLS.

## Alternatives considered

1. Read Plan fields directly. Rejected because business code would couple to
   pricing tiers and custom overrides could not be represented safely.
2. Keep Plan and entitlement rows as coequal fallbacks. Rejected because missing
   or stale rows produce inconsistent answers.
3. Put feature checks inside `WorkspaceAccess`. Rejected because actor
   authorization and Workspace commercial grants are independent.
4. Fail open when a row is missing. Rejected because it silently grants paid
   capabilities and limits.

## Consequences

Business apps depend only on codes and typed decisions. Seats and module access
share one resolver. Phase 4 must define the registry, reconcile current rows,
separate override provenance, and replace plan/model/service shortcuts.

## Migration implications

Phase 4 introduces the service and registry, projects Plan grants through
explicit subscription transitions, migrates seats and module checks, and adds
missing/malformed/override/billing-state tests. Phase 8 adds registry and caller
contract checks; Phase 9 removes direct commercial knowledge from surviving
business apps.
