# Union FK Refactor: PR Execution Plan

## Purpose
This document breaks the Union FK inventory refactor into small, mergeable PRs with clear blast radius, migration strategy, rollback notes, and validation criteria.

Related reference:
- `union_fk_refactor_plan.md` (architecture and phased roadmap)

## PR Strategy
- Keep each PR deployable and reversible.
- Prefer additive schema changes before behavior switches.
- Put behavior changes behind flags where practical.
- Never combine destructive data migration with business logic changes in one PR.

---

## PR-1: P0 Inventory Bug Fix Pack (No Architecture Shift)

### Objective
Stabilize existing inventory behavior before introducing Union FK.

### Changes
- Fix `Stock.merge()` runtime bugs:
  - typo (`self.eight` -> `self.weight`)
  - invalid field access (`self.stock`)
  - ensure new lot save before transactions
- Fix `Stock.audit()` invalid kwargs (`stock_batch`)
- Fix `Stock.get_pure_by_cost()` method call usage
- Remove duplicate `sku` declaration in model source
- Change `StockStatement.created` from `auto_now` to `auto_now_add`
- Make `StockTransaction.journal_entry` nullable
- Add/normalize missing movement codes referenced by code paths (`RM`, `SS`)
- Remove or isolate dead `merge_lots()` helper and stale `StockLot` references

### Suggested migration files
- `00xx_inventory_p0_fixes.py`
- `00xy_inventory_movement_seed_updates.py`

### Blast radius
- `apps/tenant_apps/product/models/stock.py`
- `apps/tenant_apps/product/migrations/*`
- Potential minor edits in purchase/sales posting code due to nullable journal links

### Acceptance checks
- Split/merge/audit flows execute without runtime errors
- Existing product test suite passes
- New inventory regression tests pass

### Rollback
- Safe rollback via migration reverse for schema-only changes
- Keep old movement IDs intact; only add missing types

---

## PR-2: Introduce `StockItem` + Union FK Columns (Additive Schema)

### Objective
Add new schema for unique units and Union FK targets while leaving old behavior intact.

### Changes
- Add `StockItem` model
- Add nullable `stock_item` FK to:
  - `StockTransaction`
  - `StockStatement`
- Add DB check constraints:
  - exactly one of (`stock_id`, `stock_item_id`) must be set for each row
- Add lineage fields:
  - `Stock.parent_stock` (self-FK)
  - `StockItem.parent_stock` (FK to Stock)

### Suggested migration files
- `00xz_add_stockitem_and_union_fk.py`
- `00ya_add_union_fk_constraints.py`

### Blast radius
- Product models and migrations only
- No purchase/sales behavior switch yet

### Acceptance checks
- Can create `StockItem`
- Constraints reject dual-null and dual-set transaction/statement rows
- Existing transaction creation paths continue to work (still using `stock_id`)

### Rollback
- Drop additive columns and model in reverse migration
- No data rewrite yet

---

## PR-3: Inventory Service Layer (Single Write Path)

### Objective
Centralize movement writes and remove ad-hoc transaction creation.

### Changes
- Introduce domain service module, e.g.:
  - `inventory/services/movements.py`
- Core APIs:
  - `record_movement(subject, movement, qty, wt, journal_entry=None, reason=None)`
  - `split_lot(parent_stock, allocations, ...)`
  - `merge_lots(lots, ...)`
  - `create_checkpoint(subject, method='Auto')`
- Refactor `Stock.transact()` to delegate to service or deprecate direct usage

### Suggested migration files
- None (code-only PR)

### Blast radius
- Product model methods
- Product stock views

### Acceptance checks
- No direct `StockTransaction.objects.create(...)` from views/models except service
- Unit tests for service API invariants and atomic behavior

### Rollback
- Revert service usage to existing paths (code-only rollback)

---

## PR-4: Purchase Integration to Union Subject API

### Objective
Route purchase posting through unified movement API with lot/item target support.

### Changes
- Update purchase posting/unposting to use service API
- Support purchase lines producing:
  - lot (`Stock`) default
  - unique unit (`StockItem`) where applicable
- Ensure journal linkage optional for internal moves, preserved for accounting moves

### Suggested migration files
- None unless purchase model needs optional `stock_item` relation fields

### Blast radius
- `apps/tenant_apps/purchase/models/purchase.py`
- `apps/tenant_apps/purchase/signals.py`
- Product inventory services

### Acceptance checks
- Purchase post/unpost parity with pre-refactor outputs
- Correct movement rows with union subject semantics

### Rollback
- Feature flag fallback to old posting path

---

## PR-5: Sales Integration to Union Subject API

### Objective
Route sales posting/unposting through unified movement API and support item-level deduction where needed.

### Changes
- Refactor sales posting/unposting to use `record_movement`
- Ensure sales item can consume lot or specific unique item as per policy
- Preserve journal behavior

### Suggested migration files
- Optional if sales item needs extra nullable relation for `StockItem`

### Blast radius
- `apps/tenant_apps/sales/models/sale.py`
- Product inventory services

### Acceptance checks
- Sales/returns maintain correct balance transitions
- Approval and unpost paths remain consistent

### Rollback
- Feature flag fallback to old sales movement path

---

## PR-6: Unified Balance Views and Query Adapters

### Objective
Replace drift-prone balance logic with one canonical, direction-driven SQL projection.

### Changes
- Add unified transaction projection view (`LOT` + `ITEM`)
- Add unified balance view using latest checkpoint + post-checkpoint txns
- Remove any hardcoded movement-ID in/out lists in SQL logic
- Eliminate conditions equivalent to `OR 1>0`

### Suggested migration files
- `00yb_create_inventory_txn_projection_view.py`
- `00yc_create_inventory_balance_view.py`

### Blast radius
- Product SQL views/migrations
- Read paths in product views/filters/tables

### Acceptance checks
- Balance parity against Python calculation (sample datasets)
- Query performance acceptable under production-like volume

### Rollback
- Revert views to legacy definitions
- Keep old model methods as fallback

---

## PR-7: Physical Audit and Reconciliation

### Objective
Implement explicit physical counting and reconciliation without mutating history.

### Changes
- Extend statements with:
  - `system_qty`, `system_wt`
  - `physical_qty`, `physical_wt`
  - `variance_qty`, `variance_wt`
- Add audit/reconciliation service:
  - snapshot system
  - record physical count
  - post adjustment txns
- Add discrepancy reporting and status flags

### Suggested migration files
- `00yd_extend_stockstatement_for_physical_audit.py`

### Blast radius
- Product models/forms/views/templates for stock statement
- Reporting screens

### Acceptance checks
- Physical count can close with explicit adjustment entries
- Variance history is preserved and traceable

### Rollback
- Keep old statement fields; gate new workflow by feature flag

---

## PR-8: Unified Inventory Listing UI/Filters

### Objective
Expose lots and unique units in separate + unified views with consistent balance data.

### Changes
- Add list modes:
  - Lots-only
  - Items-only
  - Unified
- Add filters by type, variant, non-zero balance, audit age
- Keep existing UX patterns (HTMX + partials)

### Suggested migration files
- None (view/template/filter layer)

### Blast radius
- Product filters/views/templates/tables

### Acceptance checks
- Unified list shows correct type badge and balances
- Sorting/filtering/pagination still HTMX-safe

### Rollback
- Revert to legacy lot-only list screens

---

## PR-9: Legacy Cleanup and Hardening

### Objective
Remove old branching and obsolete artifacts after cutover stability.

### Changes
- Retire `is_unique` behavioral branching from `Stock`
- Remove stale managers and dead helpers
- Add data quality management command
- Expand test matrix and concurrency checks

### Suggested migration files
- `00ye_cleanup_legacy_inventory_fields.py` (only if safe)

### Blast radius
- Product domain internals + docs

### Acceptance checks
- No code path depends on deprecated fields/logic
- Full integration suite green

### Rollback
- Keep deprecations for one release cycle before dropping columns

---

## Cross-PR Governance

### Feature Flags
- `INVENTORY_UNION_FK_WRITE_PATH`
- `INVENTORY_UNION_FK_READ_PATH`
- `INVENTORY_PHYSICAL_AUDIT_V2`

### Deployment Sequence
1. PR-1 through PR-3 (stability + schema + service)
2. PR-4 and PR-5 (domain integrations)
3. PR-6 (read model switch)
4. PR-7 and PR-8 (audit + UX)
5. PR-9 (cleanup)

### Test Gates (must pass each PR)
- Tenant-aware unit tests
- Purchase/sales post-unpost integration tests
- Balance parity tests
- Migration forward+backward smoke tests

## Tracking Board
- [ ] PR-1 merged
- [ ] PR-2 merged
- [ ] PR-3 merged
- [ ] PR-4 merged
- [ ] PR-5 merged
- [ ] PR-6 merged
- [ ] PR-7 merged
- [ ] PR-8 merged
- [ ] PR-9 merged

## Notes
- Keep PRs focused; avoid combining schema, service, and UI in one PR.
- For every PR touching balance logic, include before/after parity report on sample production-like data.
- Do not delete legacy columns until one release after read-path cutover.