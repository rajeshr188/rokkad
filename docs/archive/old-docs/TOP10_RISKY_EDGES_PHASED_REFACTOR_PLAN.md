---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Phased Refactor Plan: Top 10 Risky Dependency Edges

Date: 2026-05-03
Applies to: tenant runtime paths
Prerequisite: [DEPENDENCY_POLICY_MATRIX.md](DEPENDENCY_POLICY_MATRIX.md)

## Scope and Constraints

- DEA remains mandatory for every tenant workspace.
- notify_v2 replaces notify this quarter.
- Financial posting must move to strong eventual consistency (transactional outbox + async consumers).
- Priority starts with Sales and Contact signal flows.

## Top 10 Risky Edges (Prioritized)

1. sales.signals -> sales models posting side effects (synchronous reversal/repost)
   - File anchors:
     - apps/tenant_apps/sales/signals.py (pre_save Invoice/Receipt)
     - apps/tenant_apps/sales/signals.py (pre_save/post_save InvoiceItem)

2. contact.signals -> dea.models (direct account creation from Customer post_save)
   - File anchor:
     - apps/tenant_apps/contact/signals.py

3. sales.models.sale -> dea.models (JournalEntry/Voucher direct dependency)
   - File anchor:
     - apps/tenant_apps/sales/models/sale.py

4. sales.models.receipt -> dea.models (JournalEntry/Voucher direct dependency)
   - File anchor:
     - apps/tenant_apps/sales/models/receipt.py

5. purchase.models.purchase -> dea.models (direct posting dependency)
   - File anchor:
     - apps/tenant_apps/purchase/models/purchase.py

6. purchase.models.payment -> dea.models (direct posting dependency)
   - File anchor:
     - apps/tenant_apps/purchase/models/payment.py

7. product.models.stock -> dea.models (JournalEntry direct dependency)
   - File anchor:
     - apps/tenant_apps/product/models/stock.py

8. girvi.models.loan_refactored -> dea.models (BusinessDoc/JournalEntry coupling)
   - File anchor:
     - apps/tenant_apps/girvi/models/loan_refactored.py

9. dea.models.payment -> girvi.models (reverse domain import)
   - File anchor:
     - apps/tenant_apps/dea/models/payment.py

10. notify and girvi legacy coupling (legacy notify paths still referenced)
   - File anchors:
     - apps/tenant_apps/girvi/tasks.py
     - apps/tenant_apps/notify/views.py

## Refactor Phases

## Phase 0 (Week 1): Foundation for Eventual Consistency

Goal: Build the platform rails before touching business flows.

Deliverables:
1. Add tenant-safe transactional outbox model and migration.
2. Add canonical event envelope (event_id, tenant_id, aggregate_id, event_type, idempotency_key, payload_version).
3. Add DEA posting consumer worker with idempotent processing state.
4. Add DLQ table/queue and replay command.
5. Add feature flags:
   - ENABLE_ASYNC_DEA_POSTING
   - ENABLE_SYNC_POSTING_FALLBACK

Acceptance:
1. Domain transaction can atomically persist business change + outbox row.
2. DEA consumer can process the same event repeatedly without duplicate voucher entries.
3. Replay job can reprocess failed events safely.

## Phase 1 (Weeks 2-3): Start with Sales and Contact Signal Flows

Goal: Eliminate highest-risk synchronous signal side effects first.

### Edge 1: sales.signals synchronous reversal/repost

Current risk:
- Hidden side effects in pre_save/post_save.
- Potential partial updates and non-deterministic behavior under retries.

Refactor actions:
1. Freeze signal behavior behind feature flag.
2. Replace posting side effects with event emission from explicit application service methods:
   - sale.invoice.updated
   - sale.receipt.updated
   - sale.item.updated
3. Keep inventory consistency local, but emit inventory movement events for accounting impact.
4. Convert signals to thin audit-only hooks or remove entirely.

Acceptance:
1. No runtime accounting mutation from sales signals.
2. Posting occurs asynchronously through DEA consumer.

### Edge 2: contact.signals direct account creation in DEA

Current risk:
- Cross-context write in signal.
- Tight coupling to DEA model schema and lookup constants.

Refactor actions:
1. Replace Customer post_save side effect with event emission:
   - contact.customer.created
   - contact.customer.type_changed
2. DEA consumer creates/updates account projection from event payload.
3. Remove direct DEA imports from contact signals.

Acceptance:
1. contact app has zero direct DEA model writes in runtime signal path.
2. Account creation/update in DEA is idempotent and traceable by event_id.

## Phase 2 (Weeks 4-5): Sales Domain Model Decoupling

Goal: Move sales domain off direct DEA model dependencies.

### Edge 3: sales.models.sale -> dea.models
### Edge 4: sales.models.receipt -> dea.models

Refactor actions:
1. Introduce SalesAccountingPort interface in sales application layer.
2. Replace direct voucher/journal calls with event emission and optional query projection reads.
3. Move all posting decision rules to DEA posting rules keyed by event_type.
4. Keep sales models as pure domain state + invariants.

Acceptance:
1. sales model modules do not import dea models in runtime paths.
2. All accounting entries for sales originate from DEA consumer.

## Phase 3 (Weeks 6-7): Purchase and Product Decoupling

Goal: Remove direct accounting dependencies from procurement and inventory domain logic.

### Edge 5: purchase.models.purchase -> dea.models
### Edge 6: purchase.models.payment -> dea.models
### Edge 7: product.models.stock -> dea.models

Refactor actions:
1. Add purchase/inventory event contracts:
   - purchase.invoice.recorded
   - purchase.payment.recorded
   - inventory.valuation.adjusted
2. Route accounting effects to DEA consumer via outbox.
3. Keep product ledger logic domain-local; emit accounting-impact events only.
4. Build reconciliation report comparing purchase/product totals vs DEA totals.

Acceptance:
1. purchase/product runtime paths no longer import dea models for posting.
2. Reconciliation drift is zero in smoke datasets.

## Phase 4 (Weeks 8-9): Girvi and DEA Reverse-Dependency Cleanup

Goal: Break bidirectional coupling and finish core finance boundary hardening.

### Edge 8: girvi.models.loan_refactored -> dea.models
### Edge 9: dea.models.payment -> girvi.models

Refactor actions:
1. Replace `BusinessDoc` inheritance coupling with event-driven posting integration.
2. Move source document resolution from DEA model import logic to source metadata payload + domain adapter registry.
3. Introduce read-model projections if DEA screens need loan context.

Acceptance:
1. girvi runtime model layer does not import DEA posting models.
2. dea runtime model layer does not import girvi models.

## Phase 5 (Weeks 10-11): notify Legacy Retirement and Final Hardening

Goal: Complete notify_v2 migration and remove risky legacy edges.

### Edge 10: notify legacy coupling

Refactor actions:
1. Stop all new writes to notify legacy tables/services.
2. Repoint girvi notifications to notify_v2 events only.
3. Keep compatibility read bridge temporarily; then remove.
4. Delete legacy signal/task integration paths after verification window.

Acceptance:
1. Runtime notification flow is notify_v2-only.
2. No runtime imports from girvi to notify legacy services.

## Execution Model Per Edge

For each edge, use the same change protocol:

1. Contract: define event schema + payload version.
2. Dual path: run sync + async behind flags for one sprint.
3. Verify: compare outputs with reconciliation checks.
4. Cutover: disable sync path.
5. Cleanup: remove dead imports/code and add guardrail tests.

## Test and Verification Plan

1. Unit tests:
   - event emission for each workflow
   - idempotent DEA consumer behavior
2. Integration tests:
   - end-to-end business action -> outbox -> DEA posted voucher
3. Regression tests:
   - sales and purchase balance/aging unchanged vs baseline
4. Operational checks:
   - outbox lag p95 < 30s (target), then < 10s
   - posting failure rate < 0.5%
   - DLQ backlog near zero

## Ownership Suggestion

1. Platform team:
   - outbox infrastructure, consumer, replay, metrics, guardrails
2. Sales/Contact domain team:
   - Phase 1 and Phase 2 migrations
3. Purchase/Product domain team:
   - Phase 3 migrations
4. Girvi + DEA team:
   - Phase 4 migrations
5. Notify team:
   - Phase 5 retirement

## PR Sequencing (Small Batches)

1. PR-1: outbox schema + envelope + feature flags
2. PR-2: DEA consumer idempotency + replay command
3. PR-3: Sales signal to event conversion
4. PR-4: Contact signal to event conversion
5. PR-5: Sales model decoupling from DEA
6. PR-6: Purchase decoupling from DEA
7. PR-7: Product accounting-impact eventing
8. PR-8: Girvi/DEA bidirectional edge removal
9. PR-9: notify_v2 cutover + legacy freeze enforcement
10. PR-10: dead code removal + architecture import guardrails

## Definition of Done

1. All 10 risky edges are converted to allowed policy types (`A` or `E`) from [DEPENDENCY_POLICY_MATRIX.md](DEPENDENCY_POLICY_MATRIX.md).
2. No runtime `X`-edge imports remain in tenant apps.
3. DEA posting is fully async and idempotent.
4. notify legacy paths are retired from runtime.

