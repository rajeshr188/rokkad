# Stock Movement Recording Guide (Post Integration)

## Purpose
This is the operational and technical guide for how stock movements must be recorded after Stock-DEA posting integration is complete.

The system keeps two linked books:
- Inventory book (StockTransaction): quantity + weight truth
- DEA accounting book (Voucher/JournalEntry/LedgerTransaction): valuation and control entries

## Core Rules
1. Every physical stock movement must create a StockTransaction.
2. Economic stock movements must additionally create/post a Voucher and JournalEntry.
3. Internal structural movements (split/merge) remain inventory-only.
4. Purchase/sales business docs remain primary posting source for their own economic events.
5. Never create duplicate vouchers for the same economic event.

## Currency Convention
- INR: valuation book (money)
- USD: weight book convention (metal quantity proxy)

Important:
- Balancing must hold per currency.
- Do not net INR and USD against each other.

## Standard Flow Template
1. Validate user action and movement type.
2. Create StockTransaction via inventory service.
3. If movement is economic and not already covered by purchase/sales posting:
   - call `create_and_post_voucher_for_doc(doc=stock_txn, voucher_type_input=<type>, engine=...)`
   - attach returned `journal_entry` to `stock_txn`.
4. Show operator outcome (posted or pending/retry required).

## Movement-By-Movement Recording

### A) Purchase Receipt
When:
- Stock enters due to purchase invoice line posting.

What to record:
- StockTransaction movement type `P`.
- JournalEntry link should reference purchase posting JE.

Posting source:
- Purchase posting flow (existing), not stock direct flow.

Do not:
- Post a second `Stock In` voucher for same purchase line.

---

### B) Sales Issue / Consumption
When:
- Stock exits due to sales invoice fulfillment.

What to record:
- StockTransaction movement type `S` (or domain equivalent).
- JournalEntry link should reference sales posting JE when available.

Posting source:
- Sales posting flow (existing), not stock direct flow.

Do not:
- Post a second `Stock Out` voucher for same sales line.

---

### C) Direct Stock In (Outside Purchase)
When:
- Manual intake not linked to purchase invoice.
- Conversion return, found stock with approved valuation, etc.

What to record:
- StockTransaction movement type `AD` or dedicated direct in movement.
- VoucherType: `Stock In`.
- JournalEntry must be linked back to transaction.

Typical accounting intent:
- INR: Dr Inventory Value / Cr Counterparty (clearing/surplus/etc.)
- USD: Dr Inventory Weight / Cr Counterparty Weight

---

### D) Direct Stock Out (Outside Sales)
When:
- Manual removal not linked to sales invoice.
- Damage, loss, write-off, operational issue.

What to record:
- StockTransaction movement type `R` or dedicated direct out movement.
- VoucherType: `Stock Out`.
- JournalEntry linked back to transaction.

Typical accounting intent:
- INR: Dr Loss/Expense / Cr Inventory Value
- USD: Dr Loss/Adjustment Weight / Cr Inventory Weight

---

### E) Opening Balance
When:
- Initial data load at go-live or migration cutover.

What to record:
- StockTransaction movement type `OB`.
- VoucherType: `Stock Opening Balance`.
- May be posted row-wise or in approved batch.

Typical accounting intent:
- INR: Dr Inventory Value / Cr Opening Equity
- USD: Dr Inventory Weight / Cr Opening Weight Equity/Control

Operational recommendation:
- Use CSV import for lots/items.
- Post as controlled batch with audit trail.

---

### F) Physical Audit Reconciliation
When:
- Physical count differs from system balance.

What to record:
- If physical > system: adjustment-in StockTransaction.
- If physical < system: adjustment-out StockTransaction.
- VoucherType: `Stock Adjustment`.
- JE linked to adjustment transaction.

Typical accounting intent:
- Positive variance:
  - INR Dr Inventory / Cr Gain-Revaluation-or-Surplus
  - USD Dr Inventory Weight / Cr Adjustment Weight Reserve
- Negative variance:
  - INR Dr Loss / Cr Inventory
  - USD Dr Adjustment Weight Loss / Cr Inventory Weight

---

### G) Split / Merge
When:
- Lot restructuring without net economic change.

What to record:
- StockTransactions for structural movement traces.
- No voucher posting required.
- `journal_entry` remains null.

Reason:
- No new economic event, only internal shape change.

## Failure Handling
If voucher posting fails after stock transaction save:
1. Keep stock transaction committed (physical truth preserved).
2. Mark as posting pending/failed.
3. Offer retry action that reuses idempotent posting call.
4. Log error and actor context.

## Idempotency And Corrections
- Use economic fingerprint via posting rule payload.
- Re-post unchanged movement should return existing posted voucher.
- Materially changed economics should create corrected voucher path per DEA semantics.

## Reconciliation Controls
Daily/periodic controls should compare:
1. Inventory aggregate valuation vs INR inventory ledger balance.
2. Inventory aggregate weight vs USD inventory-weight ledger balance.
3. Count of economic stock transactions vs count of posted stock vouchers.
4. Unposted stock transactions aging report.

## Minimal Test Matrix
1. Purchase movement: linked, no duplicate stock voucher.
2. Sales movement: linked, no duplicate stock voucher.
3. Direct stock in: stock txn + posted voucher + JE link.
4. Direct stock out: stock txn + posted voucher + JE link.
5. Opening balance import: OB txns and posting behavior per chosen policy.
6. Adjustment reconciliation: correct direction and posted voucher.
7. Split/merge: no posting attempt.
8. Retry posting on failure: successful idempotent recovery.

## Operator Quick SOP
1. Use purchase/sales modules for normal business docs.
2. Use direct stock in/out only for exceptions.
3. Use opening balance import at initialization only.
4. Run reconciliation report daily.
5. Resolve pending posting queue before period close.

## Reference Paths
- `apps/tenant_apps/product/inventory/services/movements.py`
- `apps/tenant_apps/product/models/stock.py`
- `apps/tenant_apps/product/views/stock.py`
- `apps/tenant_apps/dea/services/post_doc.py`
- `apps/tenant_apps/dea/posting/registry.py`
- `apps/tenant_apps/dea/posting/rules/`
