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
sku = models.CharField(max_length=20, ...)  # line 35 — silently overrides
```
The first is dead. Python takes the last definition. The migration has `max_length=20` so the DB is fine, but the model source is misleading and will confuse future migrations.

#### 1b. `merge()` has a typo — `self.eight` → `self.weight`
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
# no new_lot.save() — new_lot.pk is None
new_lot.transact(...)  # StockTransaction.objects.create(stock=new_lot) → IntegrityError
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

#### 1h. `StockStatement.created = auto_now=True` — corrupts audit timeline
`auto_now=True` updates `created` on **every** `.save()`. Since `stock_in_txns(ls)` and `stock_out_txns(ls)` filter by `created__gte=ls.created`, re-saving any statement silently shifts the cutoff date, causing transactions to be double-counted or missed. Must be `auto_now_add=True`.

#### 1i. Critical bug in `stock_balance` SQL VIEW — `OR 1>0` makes checkpoint filter useless
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
`is_unique: BooleanField` is used to switch between two fundamentally different entity types — a **lot** (fungible, splittable, qty > 1) and an **individual item** (unique, has HUID/barcode, qty == 1). These have different behaviours, different validation rules, different UI, and different lifecycle events. Using a boolean flag for structural polymorphism leads to scattered `if is_unique` conditionals and unclear invariants.

#### 2b. No split lineage / parent-child tracking
When a lot is split, the child stocks have no reference back to the parent. You cannot:
- See what lot a piece was split from
- Reconcile the original purchase to its derived items
- Build a traceability view (lot → items)

#### 2c. Two independent balance computations that can drift
`current_balance()` (Python) and `StockBalance` (SQL VIEW) use different logic:
- Python uses `movement_type__direction` (flexible, data-driven)
- SQL VIEW uses hardcoded movement type IDs (`P`, `SR`, `AD`, `AR` as "in")

If you add a new movement type (e.g., `TRF` for transfer), the VIEW won't count it correctly without a migration, but the Python method will — silently producing different numbers for the same stock.

#### 2d. `StockTransaction.journal_entry` is NOT NULL — blocks internal movements
All internal operations (split, merge, adjustment) must manufacture a `JournalEntry` or the transaction cannot be saved. The accounting system shouldn't be mandatory for warehouse-internal events. `journal_entry` should be nullable with an optional link.

#### 2e. `status` is a stored denormalized field — can drift from reality
`status` is written by `update_status()` after each `transact()` call. If a transaction is ever corrected, bulk-updated, or deleted directly (the purchase signals do this), `status` is never recalculated. It will show `"Available"` for a sold-out stock or `"Empty"` for stock that has been returned.

#### 2f. `purchase_touch` is NOT NULL with no default — breaks non-purchase stocks
A stock created by a transfer or an adjustment, not from a purchase, must still supply `purchase_touch`. There's no semantically appropriate value.

#### 2g. `reorder_level` belongs on `ProductVariant`, not `Stock`
Reorder level is a property of the product, not a batch. Also, there is no signal, manager annotation, or view that uses it — it stores a value but nothing reads it.

#### 2h. Physical audit is not modelled
`StockStatement.method` has `"Physical"` as an option, but there are no fields for actual counted values (`physical_wt`, `physical_qty`) or the resulting variance. A physical audit statement is structurally identical to an auto-computed one in the current model, which means the system cannot record what was actually counted versus what was calculated — the entire point of a physical audit.

#### 2i. `StockLotManager` is dead code
A manager named `StockLotManager` exists in `managers.py` with no model to attach to. It's a remnant of a prior refactor.

---

### 3. Architecture: What Should Have Been Built

```
ProductVariant
    │
    ├── Stock (Lot)  [bulk, fungible, splittable]
    │       │  parent FK → Stock (self, for split lineage)
    │       │
    │       ├── StockTransaction  [append-only ledger]
    │       │       movement_type FK → Movement
    │       │       journal_entry FK → JournalEntry (nullable)
    │       │
    │       └── StockStatement (Auto checkpoint)
    │               auto_now_add, immutable once created
    │
    ├── StockItem (Unique)  [individual, has HUID/barcode]
    │       lot FK → Stock (which lot it was split from)
    │       [same transaction/statement pattern, or separate]
    │
    └── StockAudit (Physical count)
            physical_wt, physical_qty
            system_wt, system_qty (computed at audit time)
            variance_wt, variance_qty (stored for historical record)
            audited_by FK → User
            status: Reconciled / Pending / Discrepancy

StockBalance [DB VIEW]
    direction-aware: JOIN movement_type ON direction
    no hardcoded IDs, no OR 1>0
```

---

### 4. Enhancement Roadmap

| Priority | Fix |
|---|---|
| **P0 — Bugs** | Fix `auto_now` → `auto_now_add` on `StockStatement.created` |
| **P0 — Bugs** | Fix `OR 1>0` in `stock_balance` SQL VIEW |
| **P0 — Bugs** | Make `StockTransaction.journal_entry` nullable |
| **P0 — Bugs** | Add `RM` and `SS` to Movement fixture migration |
| **P0 — Bugs** | Fix `merge()`: typo `self.eight`, remove `self.stock`, add `.save()` |
| **P0 — Bugs** | Fix `audit()`: remove `stock_batch=self` kwarg |
| **P0 — Bugs** | Fix `__str__`: use `cb` variable already computed, not a second call |
| **P1 — Design** | Add `parent = ForeignKey('self', null=True)` to `Stock` for split lineage |
| **P1 — Design** | Make `purchase_touch` nullable (not all stocks are from purchase) |
| **P1 — Design** | Replace VIEW hardcoded IDs with direction JOIN |
| **P1 — Design** | Add `StockAudit` model with `physical_wt/qty`, `variance_wt/qty`, `audited_by` |
| **P1 — Design** | Move `reorder_level` → `ProductVariant` |
| **P2 — Cleanup** | Remove duplicate `sku` field definition |
| **P2 — Cleanup** | Remove dead `StockLotManager` and `merge_lots()` function |
| **P2 — Cleanup** | Fix `get_pure_by_cost()` → `self.get_weight()` |
| **P2 — Cleanup** | Remove Stock `quantity`/`weight` fields (or rename to `initial_*`) |
| **P3 — Enhance** | Derive `status` as a `@property` from `StockBalance` instead of storing it |
| **P3 — Enhance** | Add variant-level aggregate VIEW: total stock qty/wt per ProductVariant |
| **P3 — Enhance** | Add `low_stock` annotation using `reorder_level` on variant queries |
| **P3 — Enhance** | Signals: auto-create StockStatement checkpoint after N transactions |

---

Would you like me to start implementing fixes, beginning with the P0 bugs?

Good question — this is the core tension. If `StockTransaction.stock` is a FK, it can only point to one table. Here are the three realistic patterns, with the tradeoffs for your domain:

---

## Pattern A: GenericForeignKey (Django Content Types)

```python
class StockTransaction(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    subject = GenericForeignKey('content_type', 'object_id')  # → Stock OR StockItem
```

`PurchaseItem` would work the same way — one FK to the purchase item, subject points to either model.

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

## Pattern C: Multi-Table Inheritance — Recommended

```python
class StockUnit(models.Model):
    """Common parent — holds the FK target for all relationships."""
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
    # ↑ points to the parent — Django resolves to Stock or StockItem automatically
    movement_type = models.ForeignKey(Movement, ...)
    weight = models.DecimalField(...)
    quantity = models.IntegerField(...)

class PurchaseItem(models.Model):
    stock_unit = models.OneToOneField(StockUnit, null=True, ...)
    # works whether the purchase produced a lot or a unique item
```

The `StockBalance` VIEW joins on `product_stockunit.id` — single clean FK, same SQL structure as today.

```
PurchaseItem → (post) → Stock.objects.create(...)     # lot buy
                      → StockItem.objects.create(...)  # unique item buy
              Both are StockUnit subclasses, so:
              purchase_item.stock_unit = new_lot_or_item

StockTransaction.stock_unit_id → product_stockunit.id (always)
```

---

## Summary

| | GenericFK | Union FK | MTI (StockUnit) |
|---|---|---|---|
| DB FK integrity | ✗ | ✓ | ✓ |
| SQL VIEW / JOIN | ✗ | Awkward | ✓ Same as today |
| PurchaseItem FK | GenericFK too | Two nullable cols | One col |
| `transact()` method | On each model | Duplicated | On `StockUnit` once |
| Migration from current | Medium | Easy | Medium |
| Django ORM support | Built-in | Manual | Built-in MTI |

**MTI is the right answer.** Your `StockBalance` VIEW survives largely unchanged — just `JOIN product_stockunit` instead of `JOIN product_stock`. `transact()`, `current_balance()`, `audit()` all live on `StockUnit`. `Stock` and `StockItem` each add their own fields and type-specific methods (`split()` only on `Stock`; `generate_barcode()` only on `StockItem`).

The migration path: rename `Stock` → `StockUnit` (with type discriminator field added), create `Stock` and `StockItem` as MTI children with the fields that belong to each type only.

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
- Harder rule enforcement for “this movement must target lot only” unless you also track type discriminator (`kind`) and validate.

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
- Reads often require join parent→child to know subtype fields.
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
- Risk: over-sharing logic and accidental “generic” operations that should be type-specific.

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
3. Keep an internal “virtual unit id” abstraction in services/repositories.
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