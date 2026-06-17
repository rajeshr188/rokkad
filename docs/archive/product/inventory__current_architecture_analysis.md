---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

Search complete: Find all stock-related code

Searched for files matching `**/*stock*`, 12 matches

Searched for files matching `**/*inventory*`, no matches

Searched for regex `Stock|StockTransaction|StockStatement|StockBalance|Movement`, 200 results

Searched for files matching `**/apps/tenant_apps/product/managers.py`, 1 match

Searched for files matching `**/apps/tenant_apps/product/forms.py`, 1 match

Searched for files matching `**/apps/tenant_apps/product/urls.py`, 1 match

Searched for files matching `**/apps/tenant_apps/product/admin.py`, 1 match

Searched for regex `StockManager|StockForm|stock_url|StockAdmin|StockTransactionAdmin|StockStatementAdmin` (`**/apps/tenant_apps/product/**`), 16 results

Searched for files matching `**/apps/tenant_apps/product/tests.py`, 1 match

Searched for files matching `**/apps/tenant_apps/product/tests/test_stock.py`, no matches

Searched for files matching `**/apps/tenant_apps/product/signals.py`, 1 match

Searched for regex `Stock|StockTransaction|StockStatement|StockBalance|Movement` (`**/apps/tenant_apps/product/migrations/**`), 98 results

Here is the full architectural review. I'll cover the current state, all bugs, design flaws, and a concrete enhancement plan.

---

## Architectural Review: Inventory / Stock Domain

### What Was Intended

A **ledger-style per-lot inventory system** where:
- Each `Stock` is a lot/batch of a `ProductVariant` received from a purchase
- Every movement (purchase, sale, split, merge) is recorded as a `StockTransaction`
- Periodic `StockStatement` snapshots act as audit checkpoints to limit how many transactions have to be summed for balance calculation
- `StockBalance` is a PostgreSQL VIEW that materializes the current balance efficiently
- Unique/individual items (with HUID or laser-etched serial) are distinguished from bulk lots via `is_unique`

The core accounting pattern is correct and well-suited for jewellery inventory (tracking weight is primary; quantity is secondary).

---

### 1. Confirmed Bugs

#### 1a. Duplicate `sku` field on `Stock`
```python
sku = models.CharField(max_length=4, ...)   # line 27
...
sku = models.CharField(max_length=20, ...)  # line 35 â€” silently overrides
```
The first is dead. Python takes the last definition. The migration has `max_length=20` so the DB is fine, but the model source is misleading and will confuse future migrations.

#### 1b. `merge()` has a typo â€” `self.eight` â†’ `self.weight`
```python
weight=lot.weight + self.eight,  # AttributeError at runtime
```

#### 1c. `merge()` checks `self.stock` which doesn't exist
```python
if self.variant != lot.variant or self.stock != lot.stock:
```
`Stock` has no `stock` field. This raises `AttributeError` before doing anything.

#### 1d. `merge()` never saves `new_lot` before transacting
```python
new_lot = Stock(variant=self.variant, weight=..., quantity=...)
# no new_lot.save() â€” new_lot.pk is None
new_lot.transact(...)  # StockTransaction.objects.create(stock=new_lot) â†’ IntegrityError
```

#### 1e. `split()` and `merge()` call `transact()` without `journal_entry`
`transact()` has `journal_entry` as a required positional parameter, and `StockTransaction.journal_entry` is a NOT NULL FK. Both `split()` and `merge()` pass no `journal_entry`, causing an `IntegrityError` at the DB level.

#### 1f. `__str__` calls `current_balance()` twice
```python
def __str__(self):
    cb = self.current_balance()   # 2 aggregate queries
    return f"... | {self.current_balance()} | ..."  # 2 more queries
```
Four DB queries per string representation. This fires on every list view row, admin row, select box option, and log line.

#### 1g. `audit()` passes `stock_batch=self` to `StockStatement.objects.create()`
`StockStatement` has no `stock_batch` field. This raises `TypeError`.

#### 1h. `StockStatement.created = auto_now=True` â€” corrupts audit timeline
`auto_now=True` updates `created` on **every** `.save()`. Since `stock_in_txns(ls)` and `stock_out_txns(ls)` filter by `created__gte=ls.created`, re-saving any statement silently shifts the cutoff date, causing transactions to be double-counted or missed. Must be `auto_now_add=True`.

#### 1i. Critical bug in `stock_balance` SQL VIEW â€” `OR 1>0` makes checkpoint filter useless
```sql
AND ((stock_st.created isnull) or product_stocktransaction.created >= stock_st.created or 1>0)
```
The `OR 1>0` is always true. Every statement-backed stock counts **all** transactions, completely defeating the purpose of the checkpoint. The entire performance and correctness argument for `StockStatement` is undermined by this.

#### 1j. `Movement` fixtures don't include `RM` and `SS`
The migration fixture only seeds: `P, PR, S, SR, A, AR, AD, R`.  
Code uses `"RM"` (merge remove) and `"SS"` (split source), meaning those transact calls would fail with a FK violation.

#### 1k. `get_pure_by_cost()` calls a method without `()`
```python
return self.get_weight * self.purchase_touch  # get_weight is a method, not a property
```
Should be `self.get_weight()`.

#### 1l. `merge_lots()` module-level function is completely broken
Uses `StockLot` (non-existent model), calls `.current_balance()` on a queryset (doesn't exist), accesses `.wt` / `.qty` as attributes instead of dict keys. Dead code that would crash on import if called.

---

### 2. Design Problems

#### 2a. Single model conflates lot and individual item
`is_unique: BooleanField` is used to switch between two fundamentally different entity types â€” a **lot** (fungible, splittable, qty > 1) and an **individual item** (unique, has HUID/barcode, qty == 1). These have different behaviours, different validation rules, different UI, and different lifecycle events. Using a boolean flag for structural polymorphism leads to scattered `if is_unique` conditionals and unclear invariants.

#### 2b. No split lineage / parent-child tracking
When a lot is split, the child stocks have no reference back to the parent. You cannot:
- See what lot a piece was split from
- Reconcile the original purchase to its derived items
- Build a traceability view (lot â†’ items)

#### 2c. Two independent balance computations that can drift
`current_balance()` (Python) and `StockBalance` (SQL VIEW) use different logic:
- Python uses `movement_type__direction` (flexible, data-driven)
- SQL VIEW uses hardcoded movement type IDs (`P`, `SR`, `AD`, `AR` as "in")

If you add a new movement type (e.g., `TRF` for transfer), the VIEW won't count it correctly without a migration, but the Python method will â€” silently producing different numbers for the same stock.

#### 2d. `StockTransaction.journal_entry` is NOT NULL â€” blocks internal movements
All internal operations (split, merge, adjustment) must manufacture a `JournalEntry` or the transaction cannot be saved. The accounting system shouldn't be mandatory for warehouse-internal events. `journal_entry` should be nullable with an optional link.

#### 2e. `status` is a stored denormalized field â€” can drift from reality
`status` is written by `update_status()` after each `transact()` call. If a transaction is ever corrected, bulk-updated, or deleted directly (the purchase signals do this), `status` is never recalculated. It will show `"Available"` for a sold-out stock or `"Empty"` for stock that has been returned.

#### 2f. `purchase_touch` is NOT NULL with no default â€” breaks non-purchase stocks
A stock created by a transfer or an adjustment, not from a purchase, must still supply `purchase_touch`. There's no semantically appropriate value.

#### 2g. `reorder_level` belongs on `ProductVariant`, not `Stock`
Reorder level is a property of the product, not a batch. Also, there is no signal, manager annotation, or view that uses it â€” it stores a value but nothing reads it.

#### 2h. Physical audit is not modelled
`StockStatement.method` has `"Physical"` as an option, but there are no fields for actual counted values (`physical_wt`, `physical_qty`) or the resulting variance. A physical audit statement is structurally identical to an auto-computed one in the current model, which means the system cannot record what was actually counted versus what was calculated â€” the entire point of a physical audit.

#### 2i. `StockLotManager` is dead code
A manager named `StockLotManager` exists in `managers.py` with no model to attach to. It's a remnant of a prior refactor.

---

### 3. Architecture: What Should Have Been Built

```
ProductVariant
    â”‚
    â”œâ”€â”€ Stock (Lot)  [bulk, fungible, splittable]
    â”‚       â”‚  parent FK â†’ Stock (self, for split lineage)
    â”‚       â”‚
    â”‚       â”œâ”€â”€ StockTransaction  [append-only ledger]
    â”‚       â”‚       movement_type FK â†’ Movement
    â”‚       â”‚       journal_entry FK â†’ JournalEntry (nullable)
    â”‚       â”‚
    â”‚       â””â”€â”€ StockStatement (Auto checkpoint)
    â”‚               auto_now_add, immutable once created
    â”‚
    â”œâ”€â”€ StockItem (Unique)  [individual, has HUID/barcode]
    â”‚       lot FK â†’ Stock (which lot it was split from)
    â”‚       [same transaction/statement pattern, or separate]
    â”‚
    â””â”€â”€ StockAudit (Physical count)
            physical_wt, physical_qty
            system_wt, system_qty (computed at audit time)
            variance_wt, variance_qty (stored for historical record)
            audited_by FK â†’ User
            status: Reconciled / Pending / Discrepancy

StockBalance [DB VIEW]
    direction-aware: JOIN movement_type ON direction
    no hardcoded IDs, no OR 1>0
```

---

### 4. Enhancement Roadmap

| Priority | Fix |
|---|---|
| **P0 â€” Bugs** | Fix `auto_now` â†’ `auto_now_add` on `StockStatement.created` |
| **P0 â€” Bugs** | Fix `OR 1>0` in `stock_balance` SQL VIEW |
| **P0 â€” Bugs** | Make `StockTransaction.journal_entry` nullable |
| **P0 â€” Bugs** | Add `RM` and `SS` to Movement fixture migration |
| **P0 â€” Bugs** | Fix `merge()`: typo `self.eight`, remove `self.stock`, add `.save()` |
| **P0 â€” Bugs** | Fix `audit()`: remove `stock_batch=self` kwarg |
| **P0 â€” Bugs** | Fix `__str__`: use `cb` variable already computed, not a second call |
| **P1 â€” Design** | Add `parent = ForeignKey('self', null=True)` to `Stock` for split lineage |
| **P1 â€” Design** | Make `purchase_touch` nullable (not all stocks are from purchase) |
| **P1 â€” Design** | Replace VIEW hardcoded IDs with direction JOIN |
| **P1 â€” Design** | Add `StockAudit` model with `physical_wt/qty`, `variance_wt/qty`, `audited_by` |
| **P1 â€” Design** | Move `reorder_level` â†’ `ProductVariant` |
| **P2 â€” Cleanup** | Remove duplicate `sku` field definition |
| **P2 â€” Cleanup** | Remove dead `StockLotManager` and `merge_lots()` function |
| **P2 â€” Cleanup** | Fix `get_pure_by_cost()` â†’ `self.get_weight()` |
| **P2 â€” Cleanup** | Remove Stock `quantity`/`weight` fields (or rename to `initial_*`) |
| **P3 â€” Enhance** | Derive `status` as a `@property` from `StockBalance` instead of storing it |
| **P3 â€” Enhance** | Add variant-level aggregate VIEW: total stock qty/wt per ProductVariant |
| **P3 â€” Enhance** | Add `low_stock` annotation using `reorder_level` on variant queries |
| **P3 â€” Enhance** | Signals: auto-create StockStatement checkpoint after N transactions |

---

Would you like me to start implementing fixes, beginning with the P0 bugs?

Good question â€” this is the core tension. If `StockTransaction.stock` is a FK, it can only point to one table. Here are the three realistic patterns, with the tradeoffs for your domain:

---

## Pattern A: GenericForeignKey (Django Content Types)

```python
class StockTransaction(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    subject = GenericForeignKey('content_type', 'object_id')  # â†’ Stock OR StockItem
```

`PurchaseItem` would work the same way â€” one FK to the purchase item, subject points to either model.

**Problem:** No DB-level FK constraint. Can't do `SELECT ... JOIN` in SQL. `StockBalance` VIEW becomes impossible. `StockFilter` can't filter by lot easily. Works fine at Python level, terrible at DB level. **Not suitable given you already have a SQL VIEW.**

---

## Pattern B: Two Nullable FKs (Union FK)

```python
class StockTransaction(models.Model):
    lot = models.ForeignKey('Stock', null=True, blank=True, on_delete=models.CASCADE)
    item = models.ForeignKey('StockItem', null=True, blank=True, on_delete=models.CASCADE)
    # DB constraint: exactly one must be non-null

class PurchaseItem(models.Model):
    stock = models.OneToOneField('Stock', null=True, blank=True, ...)     # lot purchase
    stock_item = models.OneToOneField('StockItem', null=True, blank=True, ...) # unique item
```

Enforce `CHECK (lot_id IS NOT NULL) != (item_id IS NOT NULL)` at DB level via migration.

**Problem:** Every query has to handle two branches. `StockBalance` VIEW needs a `UNION` or `COALESCE(lot_id, item_id)`. Workable but every join is awkward. The `transact()` method on `Stock` has no equivalent on `StockItem` unless you duplicate it.

---

## Pattern C: Multi-Table Inheritance â€” Recommended

```python
class StockUnit(models.Model):
    """Common parent â€” holds the FK target for all relationships."""
    created = models.DateTimeField(auto_now_add=True)
    variant = models.ForeignKey(ProductVariant, ...)
    status = ...

class Stock(StockUnit):          # lot/batch
    lot_no = models.CharField(...)
    purchase_touch = models.DecimalField(...)
    parent = models.ForeignKey('self', null=True, ...)  # split lineage

class StockItem(StockUnit):      # unique/individual
    huid = models.CharField(max_length=7, unique=True)
    serial_no = models.CharField(...)
    lot = models.ForeignKey(Stock, null=True, ...)  # which lot it came from

class StockTransaction(models.Model):
    stock_unit = models.ForeignKey(StockUnit, on_delete=models.CASCADE)
    # â†‘ points to the parent â€” Django resolves to Stock or StockItem automatically
    movement_type = models.ForeignKey(Movement, ...)
    weight = models.DecimalField(...)
    quantity = models.IntegerField(...)

class PurchaseItem(models.Model):
    stock_unit = models.OneToOneField(StockUnit, null=True, ...)
    # works whether the purchase produced a lot or a unique item
```

The `StockBalance` VIEW joins on `product_stockunit.id` â€” single clean FK, same SQL structure as today.

```
PurchaseItem â†’ (post) â†’ Stock.objects.create(...)     # lot buy
                      â†’ StockItem.objects.create(...)  # unique item buy
              Both are StockUnit subclasses, so:
              purchase_item.stock_unit = new_lot_or_item

StockTransaction.stock_unit_id â†’ product_stockunit.id (always)
```

---

## Summary

| | GenericFK | Union FK | MTI (StockUnit) |
|---|---|---|---|
| DB FK integrity | âœ— | âœ“ | âœ“ |
| SQL VIEW / JOIN | âœ— | Awkward | âœ“ Same as today |
| PurchaseItem FK | GenericFK too | Two nullable cols | One col |
| `transact()` method | On each model | Duplicated | On `StockUnit` once |
| Migration from current | Medium | Easy | Medium |
| Django ORM support | Built-in | Manual | Built-in MTI |

**MTI is the right answer.** Your `StockBalance` VIEW survives largely unchanged â€” just `JOIN product_stockunit` instead of `JOIN product_stock`. `transact()`, `current_balance()`, `audit()` all live on `StockUnit`. `Stock` and `StockItem` each add their own fields and type-specific methods (`split()` only on `Stock`; `generate_barcode()` only on `StockItem`).

The migration path: rename `Stock` â†’ `StockUnit` (with type discriminator field added), create `Stock` and `StockItem` as MTI children with the fields that belong to each type only.

Want me to proceed with implementing this refactor?

Your skepticism is valid. MTI can look elegant but hide complexity. For your inventory use case, this is the real comparison.

## Core Shapes

### Union FK
One transaction table with two nullable FKs:
- `stock_id` (lot)
- `stock_item_id` (individual item)
- DB check: exactly one non-null

### MTI
Parent table + child tables:
- `stock_unit` (parent)
- `stock` child (lot fields)
- `stock_item` child (item fields)
- `stock_transaction.stock_unit_id` points to parent

---

## Deep Tradeoff Matrix

### 1. Referential Integrity and Safety

**Union FK**
- Strong integrity if you add constraints:
  - exactly one of two FKs populated
  - optional trigger: movement rules by type
- Failure mode: developers forget to set one FK in code unless centralized service layer exists.

**MTI**
- Single FK in transactions is safer at write-time.
- Harder rule enforcement for â€œthis movement must target lot onlyâ€ unless you also track type discriminator (`kind`) and validate.

Verdict: Slight edge MTI for write simplicity; Union FK is equally safe with strict DB check constraints.

---

### 2. Query Complexity

**Union FK**
- Every reporting query has branching:
  - `COALESCE(stock_id, stock_item_id)`
  - left join both tables
  - or `UNION ALL` of lot-flow + item-flow
- ORM filters become repetitive and easy to get wrong.

**MTI**
- Transaction queries are simple (always join parent).
- But if list view needs subtype-specific fields, you still join child tables.

Verdict: Edge MTI for day-to-day querying; Union FK requires more discipline in SQL/ORM.

---

### 3. Performance at Scale

**Union FK**
- One transaction row, one FK index used per row.
- Reporting with `UNION`/dual-join can be heavier but controllable with partial indexes:
  - index where `stock_id IS NOT NULL`
  - index where `stock_item_id IS NOT NULL`
- Great write throughput; predictable storage.

**MTI**
- Reads often require join parentâ†’child to know subtype fields.
- Writes for creating units need parent insert + child insert.
- For very high volume, MTI join overhead can dominate unless cached/materialized views are used.

Verdict: Union FK can be faster on write-heavy systems; MTI cleaner on read logic but may cost joins.

---

### 4. SQL View / Balance Engine

You already depend on a `stock_balance` view concept.

**Union FK**
- Need either:
  - two views (`lot_balance`, `item_balance`) + aggregate view, or
  - one view with `COALESCE(unit_id)` and CASE logic.
- More verbose, but explicit and controllable.

**MTI**
- Cleanest if balances are parent-level first.
- If lot and item balance math diverges, you still branch by subtype.

Verdict: MTI cleaner only if balance semantics are mostly shared.

---

### 5. Domain Fit (Lot vs Unique Item Semantics)

Your domain has behavior differences:
- lot can split/merge
- item has barcode/huid lifecycle
- both move through sale/purchase/audit

**Union FK**
- Lets lot/item remain truly separate aggregates with separate methods and invariants.
- Clear boundaries.

**MTI**
- Encourages shared base behavior, which is good.
- Risk: over-sharing logic and accidental â€œgenericâ€ operations that should be type-specific.

Verdict: If semantics diverge further over time, Union FK ages better.

---

### 6. Django Developer Ergonomics

**Union FK**
- Explicit but repetitive:
  - custom queryset helpers needed everywhere
  - forms/serializers need branching
- Admin and filters need custom handling.

**MTI**
- Cleaner model API:
  - `transaction.stock_unit`
  - polymorphic access patterns possible
- But Django MTI debugging/migrations are less intuitive for teams unfamiliar with it.

Verdict: For team simplicity, Union FK is often easier to reason about; MTI is cleaner once team is comfortable.

---

### 7. Migration Risk from Current Code

Current code is single `Stock` model.

**Union FK migration path**
- Add `StockItem` table.
- Add nullable `stock_item_id` to transaction/purchase references.
- Backfill existing rows into `stock_id`.
- Add DB check constraint.
- Low disruption, incremental.

**MTI migration path**
- Introduce parent table and convert existing `Stock` rows into parent+child structure.
- Touch many FKs and views.
- Higher migration complexity and rollback risk.

Verdict: Union FK is lower-risk for your current stage.

---

## Recommended Decision for Your System Now

Given your current maturity and codebase:
1. Start with **Union FK** now (lower migration risk, explicit lot/item boundaries).
2. Add strict DB constraints and service-layer APIs so branching is centralized.
3. Keep an internal â€œvirtual unit idâ€ abstraction in services/repositories.
4. Revisit MTI only if:
   - shared behavior dominates,
   - subtype branching becomes painful,
   - and team is ready for a larger refactor.

---

## If You Choose Union FK, Do These Non-Negotiables

1. Add constraint: exactly one FK set on `StockTransaction`.
2. Add same rule on `PurchaseItem` target reference.
3. Create a single transaction creation service:
   - `record_movement(subject, movement_type, qty, wt, journal_entry=None)`
4. Add repository helpers:
   - `for_lot()`, `for_item()`, `for_subject()`
5. Build two balance views and one unified reporting view.
6. Add test matrix:
   - purchase/sale/split/merge/audit for lot
   - purchase/sale/audit for item
   - cross-type reporting totals.

If you want, I can draft the exact schema and constraints for a Union FK implementation tailored to your current models.

Great question. In Union FK, split lineage is handled on the stock tables themselves, not on the transaction table.

Core idea:
1. Lineage lives in Stock and StockItem with parent references.
2. StockTransaction only records movement events against either stock or stock_item.
3. You reconstruct lineage from parent links, and reconstruct quantity/weight flow from transactions.

Recommended lineage fields

On Stock (lot):
1. parent_stock (nullable FK to Stock): when a lot is split from another lot.
2. root_stock (nullable FK to Stock): optional denormalized pointer to original ancestor for fast tree queries.
3. split_event_id (nullable FK to StockTransaction): optional link to the transaction that created this child lot.

On StockItem (individual piece):
1. parent_stock (nullable FK to Stock): which lot this item came from.
2. parent_stock_item (nullable FK to StockItem): if item-to-item derivation is ever allowed.
3. split_event_id (nullable FK to StockTransaction): optional source event.

On StockTransaction (Union FK):
1. stock (nullable FK to Stock)
2. stock_item (nullable FK to StockItem)
3. DB check constraint: exactly one is non-null
4. Optional pair to represent transfer provenance:
   source_stock/source_stock_item and dest_stock/dest_stock_item
   This helps model split/merge as one logical event instead of two rows.

How split works in Union FK

Example: split one lot into one child lot and one item.

Step 1:
Create child Stock row:
1. parent_stock = original lot
2. quantity, weight = split portion

Step 2:
Create StockItem row (if needed):
1. parent_stock = original lot
2. quantity = 1, weight = piece weight

Step 3:
Record movement rows:
1. OUT on original lot (movement SS or SPLIT_OUT)
2. IN on child lot (movement AD or SPLIT_IN)
3. IN on stock_item (movement AD_ITEM or SPLIT_IN_ITEM)

This preserves:
1. structural lineage through parent fields
2. accounting lineage through transaction rows

How to query lineage

For a lot:
1. Ancestors: recursive query via parent_stock
2. Descendants: reverse recursive query
3. Materialized approach: store lineage_path string or closure table for speed if tree depth grows

For an item:
1. Immediate source lot: parent_stock
2. Original root lot: traverse parent_stock chain until null
3. Transaction evidence: split_event_id and related transaction set

Recommended constraints for correctness

1. Exactly-one target on transaction:
   (stock_id is not null) xor (stock_item_id is not null)

2. Parent consistency:
   if stock_item.parent_stock is set, stock_item.variant must equal parent_stock.variant

3. No cyclic lineage:
   enforce in application service, or use recursive check in DB trigger

4. Split conservation:
   sum(child split quantities/weights) must never exceed available balance of parent at split time

Practical service pattern

Create one domain service:
InventorySplitService.split_lot(parent_stock, allocations, journal_entry)

It should atomically:
1. validate available balance
2. create child rows with parent references
3. write all OUT/IN transactions
4. optionally write one SplitEvent table row tying all transaction rows together

So, in Union FK, parent-child tracking is first-class and clean, as long as lineage is modeled on Stock and StockItem, and transactions are treated as movement history, not lineage structure.


Perfect topic. In Union FK, the biggest risk is ending up with two parallel systems. The trick is to define one balance engine and one audit workflow that works for both subject types.

## 1. Balance Calculation in Union FK

Assume StockTransaction has:
1. stock_id nullable
2. stock_item_id nullable
3. exactly one is non-null (DB check)

Define a logical subject key:
1. subject_type: LOT or ITEM
2. subject_id: id in corresponding table

You can compute balance in two layers.

### Layer A: Canonical ledger query
Build a unified transaction view:

1. subject_type = 'LOT' when stock_id is not null
2. subject_type = 'ITEM' when stock_item_id is not null
3. subject_id = COALESCE(stock_id, stock_item_id)

Then aggregate:
1. in_qty / in_wt by movement direction '+'
2. out_qty / out_wt by movement direction '-'
3. current_qty = opening_qty + in_qty - out_qty
4. current_wt = opening_wt + in_wt - out_wt

### Layer B: Snapshot optimization (statement checkpoints)
For each subject (lot or item), keep latest statement:
1. closing_qty, closing_wt
2. statement_created_at

Current balance is:
$$
\text{current} = \text{statement closing} + \sum(\text{txns after statement})
$$

If no statement exists:
$$
\text{current} = \sum(\text{all txns})
$$

This keeps performance stable even with large history.

Key rule: do not hardcode movement IDs for in/out. Use Movement.direction, or you will drift.

## 2. Listing Both Lots and Unique Units Together

You want three list modes:

1. Lots-only view
2. Items-only view
3. Unified inventory view

For unified list, use a projection with common columns:
1. subject_type (LOT/ITEM)
2. display_code (lot_no for lots, huid/serial/barcode for items)
3. variant
4. balance_qty
5. balance_wt
6. status
7. last_audit_at

UI recommendation:
1. one table with a Type badge
2. type-specific secondary columns conditionally rendered
3. filters: type, variant, non-zero balance, unaudited since N days

This gives operations one inventory screen without hiding semantic differences.

## 3. Auditing in Union FK

Audit should be subject-centric, not model-centric.

Use one StockStatement table with nullable union FK:
1. stock_id nullable
2. stock_item_id nullable
3. exactly one non-null

Or keep two statement tables (lot statement / item statement) and expose a unified view. I prefer one union statement table for consistency.

For each audit run:
1. pick subject (lot or item)
2. compute system balance from statement+ledger
3. record statement row:
   system_qty/system_wt
   physical_qty/physical_wt
   variance_qty/variance_wt
   method (AUTO/PHYSICAL)

Important: keep both system and physical values in statement. Do not overwrite one with the other.

## 4. Physical Stock Taking Impact

Physical taking differs by type:

### Lots (batch)
1. Usually counted by total qty + weight
2. Variance often at aggregate level
3. You may accept tolerance thresholds (weight loss/gain limits)

### Unique items (HUID)
1. Presence/absence scan by HUID/barcode
2. Quantity is often binary per item (0 or 1)
3. Weight mismatch may indicate wrong tagging or swap

Operationally:
1. scan all HUID items and mark found/missing
2. weigh/count lot buckets
3. produce reconciliation sheet with:
   missing unique items
   unexpected found items
   lot shortages/excesses by weight and qty

Adjustment posting:
1. do not edit old transactions
2. post explicit adjustment transactions after audit close
3. link adjustment txns to audit statement id for traceability

## 5. Practical Schema Rules You Need

Non-negotiable constraints:
1. exactly one FK set on StockTransaction
2. exactly one FK set on StockStatement
3. unique latest statement logic per subject should be query-safe
4. indexes:
   stock_id, created
   stock_item_id, created
   movement_type_id, created
5. optional partial indexes where FK is not null

## 6. Suggested Workflow End-to-End

1. Purchase creates LOT (or ITEM for directly unique purchase)
2. Split creates ITEM children with parent lot link, plus split in/out txns
3. Sale consumes from ITEM or LOT (policy-driven)
4. Periodic auto statement checkpoints created for active subjects
5. Physical audit records system vs physical and variance
6. Reconciliation posts adjustment txns, then a closing physical statement

If you want, next I can draft:
1. exact SQL view shape for unified balances
2. exact statement table fields for physical audit
3. the reconciliation flow (scan -> variance -> adjustment posting) as service methods.



Let me read the view and the relevant form/signal code. 

Searched for text `stockin_journalentry` (`**/apps/tenant_apps/product/views/stock.py`), 1 result

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/stock.py#225-225), lines 225 to 284

Searched for text `create` (`**/apps/tenant_apps/product/views/stock.py`), 9 results

Searched for text `stock/create` (`**/apps/tenant_apps/product/urls.py`), 2 results

So `/product/stock/create/` maps to `stockin_journalentry`. The error is `JournalEntry has no voucher`. Let me find where `.voucher` is accessed after creating the `JournalEntry`.  

Searched for text `.voucher` (`**/apps/tenant_apps/product/**/*.py`), no results

Searched for regex `post_save.*JournalEntry|JournalEntry.*post_save|journal_entry.*voucher|voucher.*journal` (`**/apps/**/*.py`), 20 results

Searched for text `voucher` (`**/apps/tenant_apps/dea/signals.py`), no results

Searched for text `StockInForm` (`**/apps/tenant_apps/product/forms.py`), 1 result

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/forms.py#573-573), lines 573 to 640

Searched for regex `class JournalEntry|voucher.*FK|FK.*voucher|OneToOne.*voucher` (`**/apps/tenant_apps/dea/models/*.py`), 4 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/models/journal.py#1-1), lines 1 to 90

Now the problem is clear. `JournalEntry.voucher` is a **NOT NULL FK** to `Voucher` â€” but `stockin_journalentry` does `JournalEntry.objects.create(desc="Stock In Entry")` with no `voucher`, which will raise an `IntegrityError` or, if there's a signal or the `__str__` is called on the result, the `RelatedObjectDoesNotExist` shown. 

This means the stock-in flow was written before `JournalEntry` gained its mandatory `voucher` FK. The form's `clean()` creates a `Stock` record without a journal entry, and the view tries to create a bare `JournalEntry`. Let me check how other parts of the system create a `JournalEntry` to understand the required `Voucher` path.  

Searched for regex `class Voucher|class VoucherStatus|VoucherType|objects.create` (`**/apps/tenant_apps/dea/models/voucher.py`), 4 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/services/post_doc.py#1-1), lines 1 to 100

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/models/voucher.py#1-1), lines 1 to 80

Now I have the full picture. Here is the diagnosis:

---

## Root Cause

`JournalEntry.voucher` is a **NOT NULL FK** to `Voucher`. The `stockin_journalentry` view does:

```python
journal_entry = JournalEntry.objects.create(desc="Stock In Entry")
```

This will fail at the DB level with an `IntegrityError` since `voucher_id` is required. The exception you see (`JournalEntry has no voucher`) is Django's descriptor complaint when something tries to access `journal_entry.voucher` on an object that was constructed in memory but couldn't actually be saved â€” or was fetched and the FK IS NULL.

**The real architectural issue:** The Stock-In flow predates the DEA voucher system. When `JournalEntry` was refactored to require a `Voucher` (which itself requires a `VoucherType`, `voucher_date`, and a `business_doc` generic FK pointing to a real object), the stock-in path was never updated.

## How Other Modules Do It

Every other module (purchase, sales, girvi) that creates a `JournalEntry` goes through `create_and_post_voucher_for_doc()` in post_doc.py. That function:
1. Creates a `Voucher` (DRAFT) with `voucher_type` + `voucher_date` + `business_doc` pointing to the source document
2. Posts the voucher, which creates the `JournalEntry` linked to it

## What This Means for Stock-In Without a Purchase Doc

Without a business document to hang the `Voucher` on, you have two paths:

**Option A â€” Use `StockTransaction` itself as the business doc**  
This is the cleanest: `StockTransaction` becomes the business document. After saving it, call `create_and_post_voucher_for_doc(stock_transaction, user, "Stock In", engine)`. Requires a `"Stock In"` `VoucherType` to exist in the DB, and a posting rule registered for it.

**Option B â€” Make `StockTransaction.journal_entry` nullable (was already on the roadmap as P0 fix)**  
Stock movements that aren't double-entry financially (internal adjustments, opening balance loads) simply don't need a `JournalEntry`. The field should be `null=True, blank=True`. This unblocks the form immediately while the proper voucher flow is wired up later.

## Immediate Fix

The P0 fix from the roadmap â€” make `journal_entry` nullable â€” is the right unblock. Let me check the current field definition before touching it: 

Searched for text `journal_entry` (`**/apps/tenant_apps/product/models/stock.py`), 9 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/stock.py#330-330), lines 330 to 355

`journal_entry` is **already** `null=True, blank=True` on `StockTransaction`. The problem is not there. The error happens because the view tries to **create** a `JournalEntry` object without a `voucher` â€” which is now a NOT NULL FK on `JournalEntry` itself.

The fix is simple: **stop creating a bare `JournalEntry` in the view**. Since `StockTransaction.journal_entry` is already nullable, just skip creating one entirely when posting a stock-in without a backing financial document. 

Replacing 22 lines with 22 lines in [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/stock.py)


```

```


Checked [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/stock.py), no problems found

Fixed. Here's the full picture:

**What broke:** The view was trying `JournalEntry.objects.create(desc="Stock In Entry")` â€” but `JournalEntry.voucher` is a NOT NULL FK (added when the DEA voucher system was refactored). A bare `JournalEntry` can no longer be created standalone; it must be attached to a `Voucher` which in turn requires a `VoucherType` and a `business_doc`.

**The fix:** `StockTransaction.journal_entry` is already `null=True, blank=True`, so the field was always designed to be optional. The view now simply leaves `journal_entry = None` when no `journal_entry_id` is passed via GET. The transaction saves cleanly without a double-entry link.

**When it's appropriate (and when it isn't):**
- âœ… Direct stock-in without financial backing â€” opening balance loads, manual adjustments, testing â€” `journal_entry = None` is correct
- âš ï¸ Stock-in from a purchase invoice â€” should pass `?journal_entry_id=<id>` so the transaction is linked to the purchase voucher's JE. That path still works as before.

For the long term, whenever a stock movement needs to generate an accounting entry (e.g. recording the cost of goods received), use `create_and_post_voucher_for_doc()` from `dea/services/post_doc.py` with the `StockTransaction` as the business doc and a `"Stock In"` `VoucherType`. That's the proper integration point but requires a `VoucherType` seed and a posting rule, which is a separate PR.

Let me look at both systems together before answering.  

Searched for text `StockTransaction` (`**/apps/tenant_apps/dea/models/journal.py`), no results

Searched for text `JournalEntry` (`**/apps/tenant_apps/product/models/stock.py`), 4 results

Compacted conversation

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/stock.py#1-1), lines 1 to 60

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/models/journal.py#1-1), lines 1 to 80

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/models/stock.py#60-60), lines 60 to 270

Searched for text `VoucherType` (`**/apps/tenant_apps/dea/models/voucher.py`), 2 results

Searched for text `stockin_journalentry\|def stock_in\|def stockin` (`**/apps/tenant_apps/product/views/stock.py`), no results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/models/voucher.py#1-1), lines 1 to 80

Searched for regex `def stock` (`**/apps/tenant_apps/product/views/stock.py`), 5 results

Searched for regex `stock|StockTransaction|journal_entry` (`**/apps/tenant_apps/purchase/**`), 20 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/product/views/stock.py#243-243), lines 243 to 284

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/purchase/views/purchase.py#1-1), lines 1 to 80

Searched for regex `def post|stock|journal_entry|StockTransaction` (`**/apps/tenant_apps/purchase/models/**`), 20 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/purchase/models/purchase.py#635-635), lines 635 to 720

Now I have enough context. Here is a clear, opinionated answer.

---

## Stock-In Flow Design

### The three distinct stock-in origins

| Scenario | DEA side | Inventory side |
|---|---|---|
| **Purchase** | Purchase invoice is the business doc; `PurchaseItem.post()` calls `record_movement("P")` linking to the purchase's JournalEntry. Already works correctly. | `Stock` or `StockItem` created by `_sync_inventory_subject()` |
| **Opening balance** | "Opening Balance" voucher type; Dr Inventory / Cr Capital or Opening-Stock equity account | `StockTransaction(movement_type="OB")` |
| **Manual adjustment / found stock** | "Adjustment" voucher type; Dr Inventory / Cr Stock-Adjustment P&L account â€” or no accounting entry at all if the business doesn't track it | `StockTransaction(movement_type="AD")` |

---

### Are the two systems independent?

**They should be â€” and your code already mostly expresses this correctly:**

```
StockTransaction.journal_entry = ForeignKey(JournalEntry, null=True, blank=True)
```

That nullable FK is the right architecture. It says:

> Every physical movement **must** have a `StockTransaction`. A `JournalEntry` is **optionally attached** when there is also a financial effect to record.

The inventory book (weight/qty ledger) and the accounts book (value ledger) are two separate journals that happen to reference the same events. Jewellery businesses have always maintained them separately â€” a traditional *maalthi* keeps only weight, the *khaata* keeps money. Neither waits for the other.

The broken design you hit was the opposite: `JournalEntry.voucher` is **NOT NULL**, so if you try to create a JournalEntry without a proper Voucher+VoucherType setup, it crashes. The inventory system must never be gated by the DEA system being ready.

---

### Should there be an independent "Stock Journal Entry"?

**No â€” not as a model. But yes as a pattern.** Here is what "independent" actually means:

A `StockTransaction` **is** the stock journal entry. It records:
- which subject (lot or item)
- movement type (direction: `+` or `-`)
- weight and quantity
- when
- optionally: which financial event caused it (`journal_entry`)

You don't need a parallel "StockJournalEntry" model. What you need is a clean **service-level API** that has three modes:

```python
# 1. Pure inventory move (opening balance, adjustment, split, merge)
InventoryMovementService.record_movement(
    subject=stock,
    movement_type_id="OB",  # or "AD"
    weight=Decimal("10.500"),
    quantity=1,
    journal_entry=None,  # no accounting entry yet
)

# 2. Purchase-linked move (already works via PurchaseItem.post())
InventoryMovementService.record_movement(
    subject=stock,
    movement_type_id="P",
    weight=...,
    quantity=...,
    journal_entry=purchase_item.get_journal_entry(),  # linked to purchase voucher
)

# 3. Accounting-posted adjustment (when user wants DEA for the adjustment too)
#    â€” post the voucher first, then call record_movement with the JE
voucher = create_and_post_voucher_for_doc(stock_txn, user, "Stock Adjustment", engine)
je = voucher.journal_entries.get()
txn.journal_entry = je
txn.save()
```

---

### Concrete missing pieces

1. **`"OB"` Movement type** â€” Opening Balance â€” doesn't exist in your fixture. Add it with direction `"+"`. Semantically distinct from `"AD"` (which is an adjustment, not initial entry).

2. **`purchase_touch` is NOT NULL** â€” blocks the opening balance form because old stock doesn't always have a "purchase touch". Make it nullable or give it a sensible default like `0.000`.

3. **`stockin_journalentry` view is misnamed** â€” it's actually a direct stock-in form. Rename it to `stock_in_direct` or `stock_adjust_in`. The name implies a JE which it no longer creates.

4. **Opening balance as a batch workflow** â€” when a user first sets up the system, they'll have 100+ lots to enter. A CSV/bulk import form scoped to `movement_type="OB"` would be more practical than entering one by one.

---

### Summary

- Inventory system is **primary and always runs** â€” every physical movement gets a `StockTransaction`.
- DEA system is **secondary and optionally linked** â€” attach a `JournalEntry` when there's a financial posting to make.
- `StockTransaction.journal_entry = None` is valid and intentional for internal moves, opening balances (until posted), splits, merges, and any scenario where the accounts side isn't ready.
- The models already express this correctly; the gap is just missing `"OB"` movement type + nullable `purchase_touch` + cleaner view naming.

Let me read the actual service code so the answer is grounded in what exists.  

Searched for regex `posting.*rule|PostingRule|registry|VoucherType.*seed|fixtures` (`**/apps/tenant_apps/dea/**`), 20 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/services/post_doc.py#1-1), lines 1 to 120

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/posting/rules)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/posting/registry.py)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/posting/rules/purchase_invoice.py#1-1), lines 1 to 80

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/dea/posting/rules/base.py)

Now the full picture is clear. Here's the concrete answer:

---

## Yes â€” a three-mode service API is exactly the right solution

Let me explain what the DEA pipeline actually *is* before connecting it to stock movements.

### The DEA pipeline in your system today

```
Business Doc (PurchaseInvoice / StockTransaction / etc.)
    â”‚
    â”œâ”€â”€ Voucher  (created by create_and_post_voucher_for_doc)
    â”‚       voucher_type â†’ "PURCHASE_GOODS" / "Stock In" / etc.
    â”‚       business_doc = GenericFK â†’ the doc that triggered it
    â”‚
    â”œâ”€â”€ JournalEntry  (created by PostVoucherCommand)
    â”‚       voucher â†’ FK above
    â”‚
    â””â”€â”€ LedgerTransaction(s)  (created by the PostingRule.build_posting())
            DR: Inventory Ledger  â‚¹10,000
            CR: Opening Equity    â‚¹10,000
```

The `registry` maps a `VoucherType.name` string â†’ a `PostingRule` class. The rule has one method: `build_posting(ctx)` â†’ `PostingBundle` â†’ list of ledger lines. That's all. The engine runs the rule, writes the ledger movements, and stamps the voucher as POSTED.

**The missing piece for stock-in** is just two things: a `VoucherType` row named `"Stock In"` in the DB, and a `StockInRule` file in `posting/rules/`.

---

### What each of the three modes means in code

**Mode 1 â€” Pure inventory, no accounting (today's fix)**
```python
# User enters opening balance
txn = InventoryMovementService.record_movement(
    subject=stock, movement_type_id="OB",
    weight=Decimal("10.500"), quantity=1,
    journal_entry=None,   # â† no DEA involvement
)
# StockTransaction saved. Inventory book updated. Done.
```

**Mode 2 â€” Inventory triggered by purchase (already works)**
```python
# PurchaseItem.post() does this internally
txn = InventoryMovementService.record_movement(
    subject=stock, movement_type_id="P",
    weight=item.weight, quantity=item.quantity,
    journal_entry=item.get_journal_entry(),  # â† the purchase invoice's JE
)
# StockTransaction.journal_entry points to the purchase invoice's JE
# The accounting was posted when the purchase was posted â€” not here
```
Note: in this mode the `StockTransaction` borrows the purchase invoice's `JournalEntry`. The stock movement doesn't own its own voucher â€” it's a side-effect of the purchase posting.

**Mode 3 â€” Inventory movement that needs its own accounting entry**

This is what "use `create_and_post_voucher_for_doc`" means:

```python
# 1. Save the StockTransaction first (inventory book)
txn = InventoryMovementService.record_movement(
    subject=stock, movement_type_id="AD",
    weight=Decimal("5.000"), quantity=1,
    journal_entry=None,  # temporarily None
)

# 2. Now post a voucher where the StockTransaction IS the business doc
voucher, je = create_and_post_voucher_for_doc(
    doc=txn,               # â† StockTransaction is the business doc
    user=request.user,
    voucher_type_input="Stock In",   # must exist in VoucherType table
    engine=posting_engine,
)

# 3. Link the JE back to the transaction
txn.journal_entry = je
txn.save(update_fields=["journal_entry"])
```

For this to work, `StockTransaction` must implement `get_economic_payload()` (used for idempotency fingerprinting) and there must be a `StockInRule.build_posting()` that says what the ledger entries are. For example:

```python
# posting/rules/stock_in.py
@register_rule("Stock In")
class StockInRule(BasePostingRule):
    def build_posting(self, ctx) -> PostingBundle:
        txn = ctx.doc  # the StockTransaction
        cost = txn.weight * txn.stock.purchase_touch * current_gold_rate
        return PostingBundle(lines=[
            DualLedgerLine(
                ledger_dr=get_ledger_id_by_key("INVENTORY"),
                ledger_cr=get_ledger_id_by_key("OPENING_STOCK_EQUITY"),
                amount=cost,
                memo=f"Stock in {txn.pk}",
            )
        ])
```

---

### When you actually need Mode 3 (and when you don't)

| Use case | Mode | Reason |
|---|---|---|
| Opening balance entry | Mode 1 now â†’ Mode 3 later if auditors need a balanced entry | Opening stock has equity counterpart but small businesses often skip the DEA entry |
| Manual adjustment (+) | Mode 1 typically | Corrections are internal; DEA only if stock variance is being written up |
| Purchase receipt | Mode 2 | The purchase invoice already posts `DR Inventory / CR AP`; duplicating it in Mode 3 would double-count |
| Foundry return (goods received from manufacturer) | Mode 3 | This is a real goods receipt with a cost â€” needs its own voucher |
| Approval return (goods returned by customer) | Mode 3 | Reverses the earlier sale entry |

The key rule: **one economic event â†’ one posted voucher**. If the purchase invoice already covers the DR Inventory, the stock transaction from `PurchaseItem.post()` should NOT also own a voucher.

---

### Summary

The three-mode service API is right. The code already supports all three structurally. The only work remaining for Mode 3 to be usable is:

1. Seed a `VoucherType` row: `name="Stock In"` (migration or fixture)
2. Write `posting/rules/stock_in.py` with a `StockInRule`
3. Register it in apps.py alongside the other rules
4. Add `get_economic_payload()` to `StockTransaction` for idempotency

That's a self-contained PR. Nothing about the current model needs to change.
