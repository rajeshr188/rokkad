# Inventory Service Layer Reference

## Purpose
This document is the long-term reference for inventory movement writes after PR-3.
It defines the service contract, invariants, and integration expectations for purchase/sales.

## Source of Truth
- Service module: `apps/tenant_apps/product/inventory/services/movements.py`
- Primary class: `InventoryMovementService`

All inventory movement writes must go through this service.

## Why This Layer Exists
- Centralize StockTransaction/StockStatement writes.
- Enforce Union FK semantics for `Stock` and `StockItem` subjects.
- Keep movement creation atomic and consistent.
- Make business document integrations (purchase/sales) reuse one path.

## Public API

### 1) `record_movement(subject, movement_type_id, quantity, weight, journal_entry=None, reason=None, description=None)`
Creates one `StockTransaction` row for either `Stock` or `StockItem`.

Behavior:
- Validates movement type.
- Accepts exactly one subject (`Stock` or `StockItem`).
- Creates transaction with correct FK side populated.
- Allows nullable `journal_entry` for internal/non-accounting movements.
- Updates subject status.

### 2) `split_lot(parent_stock, splits, reason=None)`
Splits a parent lot into child lots/items and records the related movements.

Behavior:
- Validates requested split totals against parent balance.
- Creates child records.
- Records separation movement for parent and add movement for children.
- Preserves lineage using `parent_stock` fields.

### 3) `merge_lots(lots, reason=None)`
Merges multiple compatible lots into one lot and records movements.

Behavior:
- Validates lots are merge-compatible.
- Creates destination lot with combined balances.
- Records remove movement on sources and add movement on destination.

### 4) `create_checkpoint(subject, method='Auto')`
Creates a `StockStatement` checkpoint for a lot/item based on transactions.

Behavior:
- Uses previous checkpoint as baseline.
- Aggregates in/out movements by movement direction.
- Writes one statement row for subject.

### 5) `record_physical_count(subject, physical_qty, physical_wt)`
Creates a physical `StockStatement` without mutating movement history.

Behavior:
- Snapshots system quantity/weight at count time.
- Stores physical counted quantity/weight.
- Stores variance quantity/weight.
- Marks the statement `Reconciled` when variance is zero, otherwise `Discrepancy`.

### 6) `reconcile_statement(statement)`
Closes a physical discrepancy by posting an explicit inventory adjustment movement.

Behavior:
- Uses `AD` when physical is above system.
- Uses `R` when physical is below system.
- Marks the physical statement `Reconciled` and timestamps it.

### 7) `perform_physical_audit(subject, physical_qty, physical_wt, reconcile=False)`
Convenience wrapper to record a physical count and optionally reconcile it immediately.

### 8) `get_balance(subject)`
Returns current quantity/weight balance for a lot/item.

## Invariants (Do Not Break)
- Write path invariant: no ad-hoc `StockTransaction.objects.create(...)` outside service.
- Union FK invariant: transaction/statement must reference exactly one of stock or stock_item.
- Atomicity invariant: multi-step operations (`split_lot`, `merge_lots`) run inside DB transaction.
- Status invariant: subject status stays in sync after movement writes.

## Model Delegation Pattern
`Stock` and `StockItem` model methods are compatibility wrappers and delegate to service:
- `Stock.transact()`
- `Stock.audit()`
- `Stock.split()`
- `Stock.merge()`
- `StockItem.transact()`
- `StockItem.audit()`

Imports are intentionally lazy inside methods to avoid circular imports.

## Accounting Integration: Voucher-First (New Rule)
Historical behavior directly tied business docs to JournalEntry creation during stock movement.
The new expected flow is:

1. Business document (Purchase/Sales) creates or updates Voucher.
2. Voucher posting process creates JournalEntry.
3. Inventory movement links that JournalEntry when accounting trace is required.
4. Internal/non-accounting movements are allowed with `journal_entry = null`.

Implications:
- Purchase/Sales models should not be the primary origin of JournalEntry objects.
- Inventory service remains accounting-agnostic; it accepts optional JournalEntry linkage.
- Voucher posting is the accounting boundary; movement service is the inventory boundary.

## Integration Checklist for Purchase/Sales PRs
- Use `InventoryMovementService.record_movement(...)` for all stock effects.
- Do not create `StockTransaction` rows directly in purchase/sales models/signals.
- Ensure business doc lifecycle creates/updates Voucher first.
- Pass `journal_entry` from posted Voucher only when available/required.
- Keep unpost/reverse paths symmetric and idempotent.

## Current Integration Status
- Purchase flow: migrated to voucher-resolved journal linkage and service-backed inventory writes.
- Sales flow: migrated to voucher-resolved journal linkage and service-backed inventory writes.
- Sales `InvoiceItem` supports either `Stock` or `StockItem` as the inventory subject.
- Internal approval handoff remains non-accounting and may use null `journal_entry`.

## Current Read Model Status
- Canonical transaction projection view: `inventory_txn_projection`
- Canonical balance view: `inventory_balance`
- Compatibility lot view: `stock_balance` now selects lot rows from `inventory_balance`
- `Stock.current_balance()` and `StockItem.current_balance()` read from the canonical SQL view with Python fallback
- Movement direction is derived from `Movement.direction`; no hardcoded in/out movement lists remain in the SQL read model

## Physical Audit Rules
- Physical statements preserve both system values and counted values.
- Reconciliation posts a new stock movement instead of editing historical transactions.
- Physical statements keep `Closing_qty` and `Closing_wt` at the pre-reconciliation system balance so later adjustment transactions remain visible in the audit trail.
- Zero-variance counts are closed without posting an adjustment movement.

## Test Expectations
At minimum, each integrating domain must cover:
- Post and unpost parity.
- Correct subject side (`stock` vs `stock_item`) on movement rows.
- Behavior with and without `journal_entry` linkage.
- Reversal paths preserving final balances.
