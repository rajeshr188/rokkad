---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Inventory Refactor Plan: Union FK Architecture

## Status
- Decision: Union FK adopted (`Stock` lot + `StockItem` unique units).
- Scope: Refactor inventory domain while preserving existing business behavior for purchase/sales posting.
- Primary objective: maintain ledger integrity, improve auditability, and support both lot and unique item flows with strong constraints.

## Target Architecture

### Core Models
- `Stock` (lot/batch)
  - Represents fungible inventory lots.
  - Supports split/merge and parent lineage.
- `StockItem` (unique unit)
  - Represents unique physical units (HUID/barcode).
  - Typically derived from lots but may be purchased directly.
- `StockTransaction` (ledger)
  - Union FKs:
    - `stock` nullable FK
    - `stock_item` nullable FK
  - Exactly one FK must be non-null.
  - Movement direction comes from `Movement.direction`.
- `StockStatement` (checkpoint/audit)
  - Union FKs:
    - `stock` nullable FK
    - `stock_item` nullable FK
  - Exactly one FK must be non-null.
  - Stores checkpoint and physical audit values.

### Lineage
- `Stock.parent_stock` nullable self-FK for lot split lineage.
- `StockItem.parent_stock` nullable FK to source lot.
- Optional: `root_stock` and `split_event` for faster traceability/reporting.

## Non-Negotiable Constraints
- For `StockTransaction`: exactly one of `stock_id` / `stock_item_id` is set.
- For `StockStatement`: exactly one of `stock_id` / `stock_item_id` is set.
- `StockItem.variant_id == parent_stock.variant_id` when parent exists.
- No negative physical balances post-reconciliation without explicit override flag.

## Balance Calculation Strategy

### Canonical Rule
- `balance = statement_closing + sum(transactions after latest statement)`.
- If no statement exists: use all transactions.
- Never hardcode movement IDs for in/out; use `Movement.direction`.

### SQL Views
- Build a unified transaction projection view:
  - `subject_type` (`LOT` or `ITEM`)
  - `subject_id` (`COALESCE(stock_id, stock_item_id)`)
- Build unified balance view based on latest statement + post-statement txns.
- Remove any logic equivalent to `OR 1>0` in checkpoint filtering.

## Physical Stock Taking Design
- `StockStatement` must capture both:
  - System values at count time (`system_qty`, `system_wt`)
  - Physical counted values (`physical_qty`, `physical_wt`)
- Persist variances:
  - `variance_qty`, `variance_wt`
- Reconciliation posts explicit adjustment transactions; do not mutate historical transactions.

## Refactor Phases

### Phase 0: Safety Net and Baseline
- [ ] Add regression tests for current purchase/sales posting and balance computation.
- [ ] Add migration tests for data preservation.
- [ ] Snapshot current `stock_balance` outputs for comparison.

Acceptance criteria:
- Tests reproduce current behavior and catch drift during refactor.

### Phase 1: P0 Bug Fixes (Current Model, No Architecture Change Yet)
- [ ] Remove duplicate `sku` field definition from model code.
- [ ] Fix `merge()` bugs (`self.eight`, invalid `self.stock` check, unsaved new lot).
- [ ] Fix `audit()` invalid kwarg (`stock_batch`).
- [ ] Change `StockStatement.created` to `auto_now_add=True`.
- [ ] Make `StockTransaction.journal_entry` nullable for internal stock ops.
- [ ] Add missing movement codes used by code path (`RM`, `SS`) or normalize names.
- [ ] Fix `get_pure_by_cost()` call to `self.get_weight()`.
- [ ] Remove dead/broken helper (`merge_lots`) or quarantine behind feature flag.

Acceptance criteria:
- No runtime errors in split/merge/audit paths.
- Existing test suite and inventory tests pass.

### Phase 2: Introduce `StockItem` + Union FK Columns
- [ ] Create `StockItem` model with unique identifiers (`huid`, `serial_no`, barcode).
- [ ] Add nullable `stock_item` FK to `StockTransaction`.
- [ ] Add nullable `stock_item` FK to `StockStatement`.
- [ ] Add DB check constraints (exactly one FK set).
- [ ] Add helper API to resolve transaction subject uniformly.

Acceptance criteria:
- Can write/read transactions and statements for both lot and item.
- DB rejects invalid dual-null or dual-set rows.

### Phase 3: Service Layer and Posting Flows
- [ ] Introduce inventory domain services:
  - `record_movement(subject, movement, qty, wt, journal_entry=None, reason=None)`
  - `split_lot(...)`
  - `merge_lots(...)`
  - `audit_subject(...)`
- [ ] Refactor purchase post/unpost to use service.
- [ ] Refactor sales post/unpost to use service.
- [ ] Ensure all writes are `transaction.atomic`.

Acceptance criteria:
- No direct ad-hoc transaction writes from model/view code.
- Purchase/sales use a single movement API.

### Phase 4: Unified Balances and Listing
- [ ] Replace legacy `StockBalance` view with unified subject balance view.
- [ ] Add list endpoints for:
  - Lots only
  - Items only
  - Unified inventory list
- [ ] Add filters by subject type, variant, status, last_audit_age.

Acceptance criteria:
- Unified list returns both lots/items with correct balances.
- Query performance remains acceptable with indexes.

### Phase 5: Physical Audit Workflow
- [ ] Extend statement schema with system/physical/variance fields.
- [ ] Build stock-taking flow for lot counts and item scans.
- [ ] Add reconciliation workflow that posts adjustment transactions.
- [ ] Add discrepancy reports and approval path.

Acceptance criteria:
- Physical count can be completed and reconciled without editing history.
- Variances are fully traceable.

### Phase 6: Cleanup and Hardening
- [ ] Remove obsolete `is_unique` branching in `Stock` once migration complete.
- [ ] Remove dead managers/utilities and unused code paths.
- [ ] Add data quality checks/commands.
- [ ] Add operational docs and runbooks.

Acceptance criteria:
- No legacy branches controlling lot vs unique behavior.
- Domain behavior fully represented by explicit models and constraints.

## Flaw Mitigation Matrix
- 2a Single model conflation: solved by explicit `Stock` + `StockItem` + union FKs.
- 2b No lineage: solved via `parent_stock` and optional root/split_event links.
- 2c Balance drift: solved by direction-driven unified balance views + one canonical service.
- 2d Journal mandatory: solved by nullable journal FK with optional accounting linkage.
- 2e Status drift: derive from balance view or recalc in domain service; avoid stale persistence.
- 2f `purchase_touch` rigidity: allow nullable/conditional semantics by subject and source flow.
- 2g Reorder level scope: move to `ProductVariant` and compute low-stock from unified balances.
- 2h Physical audit gap: explicit system vs physical fields and reconciliation transactions.
- 2i Dead code: remove `StockLotManager` artifacts and broken helpers.

## Indexing and Performance Checklist
- [ ] Composite indexes: (`stock_id`, `created`), (`stock_item_id`, `created`).
- [ ] Index on `movement_type_id` and `created`.
- [ ] Partial indexes for non-null union FK columns.
- [ ] Covering indexes for list filters (`variant_id`, `status`, `updated`).

## Testing Checklist
- [ ] Unit tests: split, merge, movement posting, checkpoint balance math.
- [ ] Integration tests: purchase->stock, sale->deduction, return flows.
- [ ] Audit tests: physical mismatch and adjustment posting.
- [ ] Data migration tests: old `Stock` records preserved and mapped correctly.
- [ ] Concurrency tests: simultaneous movement posting on same subject.

## Risks and Mitigations
- Risk: dual-write inconsistency during transition.
  - Mitigation: temporary feature flag + single write path via service.
- Risk: reporting drift while old/new views coexist.
  - Mitigation: comparison job and threshold alerts.
- Risk: migration downtime.
  - Mitigation: staged migrations, backfill scripts, and retry-safe idempotent operations.

## Execution Tracking

### Milestone Log
- [ ] M0 Baseline tests in place
- [ ] M1 P0 bug fixes merged
- [ ] M2 `StockItem` and union FK schema live
- [ ] M3 Service layer adopted by purchase/sales
- [ ] M4 Unified balance/listing live
- [ ] M5 Physical audit workflow live
- [ ] M6 Legacy cleanup complete

### Notes
- Keep all migration scripts idempotent and reversible where practical.
- Prefer adding new paths behind a feature flag before removing legacy behavior.

