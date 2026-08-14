---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# ADR: Girvi BusinessDoc Decoupling

Date: 2026-05-03
Status: Accepted
Owners: Girvi Team, DEA Team, Platform Architecture
Tags: girvi, dea, event-driven, coupling, migration
Related:
- ../GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md
- ../TOP10_RISKY_EDGES_PHASED_REFACTOR_PLAN.md
- ../DEPENDENCY_POLICY_MATRIX.md

## Summary

Decouple Girvi loan lifecycle runtime from DEA BusinessDoc inheritance and synchronous posting side effects. Girvi should persist domain state and emit versioned events to outbox; DEA asynchronously creates/posts PaymentVoucher and ledger entries with idempotent consumers.

## Context / Problem Statement

Current implementation couples Girvi domain models and lifecycle services directly to DEA posting internals.

Evidence:
1. apps/tenant_apps/girvi/models/loan_refactored.py imports BusinessDoc and JournalEntry.
2. apps/tenant_apps/girvi/service_modules/payment.py performs synchronous PaymentVoucher creation and posting.
3. Cross-domain runtime coupling increases fragility, complicates retries, and violates dependency policy edge target (E).

Constraints:
1. DEA remains mandatory and central per tenant.
2. Strong eventual consistency is the chosen posting model.
3. No big-bang rewrite is allowed.

## Decision

1. Girvi domain lifecycle operations will emit outbox events as the integration contract for accounting effects.
2. DEA consumer will own posting execution and idempotency handling.
3. Girvi runtime model and service paths will not require DEA posting inheritance/calls.
4. BusinessDoc coupling in Girvi will be removed or neutralized in runtime paths after staged cutover.

## Decision Details

1. Scope:
   - apps/tenant_apps/girvi/models/loan_refactored.py
   - apps/tenant_apps/girvi/service_modules/payment.py
   - apps/tenant_apps/girvi/models/release.py
   - DEA consumer and posting rule resolution path

2. Allowed coupling after migration:
   - Girvi -> platform outbox publisher (A)
   - Girvi -> DEA via event contract only (E)

3. Forbidden coupling after migration:
   - Girvi runtime direct posting calls into DEA engine/services
   - Girvi runtime reliance on DEA posting inheritance behavior

4. Integration events:
   - loan.disbursed
   - loan.payment.received
   - loan.released

## Rationale

1. Improves reliability with retry-safe async posting.
2. Removes hidden cross-context side effects from request path.
3. Aligns with dependency policy and phased refactor roadmap.
4. Enables clearer ownership: Girvi owns business state, DEA owns accounting posting.

## Consequences

### Positive

1. Reduced cross-app coupling and lower blast radius of DEA changes.
2. Better observability for posting lag/failure via event pipeline metrics.
3. Cleaner domain model semantics inside Girvi.

### Negative / Costs

1. Requires outbox + worker operations and monitoring.
2. Introduces temporary dual-path complexity during migration.
3. Requires UI handling for posting pending state.

## Rollout / Migration Plan

Execution note (2026-06-21): implementation of the async event-driven cutover is currently paused; this ADR remains the accepted architecture direction.

1. Phase A: add outbox, consumer, idempotency, DLQ (no behavior change).
2. Phase B: dual-write events from Girvi while sync posting remains enabled.
3. Phase C: enable async posting for pilot tenants and reconcile parity.
4. Phase D: disable sync posting by operation type: disbursal, payment, release.
5. Phase E: remove runtime DEA posting coupling from Girvi and enforce via CI.

Rollback criteria:
1. Reconciliation drift greater than 0.1% on pilot cohort for two windows.
2. Posting failure rate greater than 0.5% sustained over 30 minutes.

Rollback action:
1. Re-enable ENABLE_GIRVI_SYNC_POSTING.
2. Keep event emission active for audit while consumer posting is paused.

## Guardrails and Observability

1. Feature flags:
   - ENABLE_GIRVI_OUTBOX_EMIT
   - ENABLE_DEA_EVENT_CONSUMER
   - ENABLE_GIRVI_SYNC_POSTING

2. Metrics:
   - outbox lag p95
   - posting success/failure rate
   - duplicate/idempotency conflict rate
   - reconciliation drift

3. Alerts:
   - lag > 60s p95
   - failure rate > 0.5%
   - DLQ growth > threshold

## Test Strategy

1. Unit:
   - event payload generation and idempotency key composition.
2. Integration:
   - girvi action -> outbox -> DEA posting -> voucher state.
3. Regression:
   - parity checks against legacy synchronous posting on pilot tenants.

## Alternatives Considered

1. Keep current synchronous posting with retries in request path.
   - Rejected: still tightly coupled and operationally brittle.
2. Immediate full rewrite removing all old paths at once.
   - Rejected: high migration and outage risk.

## Open Questions

1. Final location of outbox model (new platform app vs existing app).
2. Whether BusinessDoc remains for non-posting metadata only during transition.

## Review Trigger

Revisit when:
1. Pilot cutover metrics fail SLO thresholds.
2. DEA posting rules require incompatible payload evolution (schema_version bump).

