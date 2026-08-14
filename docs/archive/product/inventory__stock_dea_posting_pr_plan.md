---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Stock-DEA Posting Integration PR Plan

## Purpose
This document tracks the PR series that integrates inventory stock movements with DEA posting engine using Voucher + JournalEntry workflows, while preserving inventory as the system of record for quantity/weight.

## Scope
- Integrate selected stock movements with `create_and_post_voucher_for_doc()`.
- Add stock-specific VoucherTypes and posting rules.
- Support dual currency tracking policy:
  - INR for valuation (money)
  - USD for weight ledger convention (metal quantity proxy)
- Keep internal/non-economic movements inventory-only.

## Out Of Scope
- Rebuild of product inventory model architecture.
- Replacement of purchase/sales voucher flows.
- New reporting UI beyond minimal operational feedback.

## Policy Matrix (Authoritative)
| Movement Scenario | StockTransaction | Voucher/JE Required | VoucherType | Notes |
|---|---|---|---|---|
| Purchase item post | Yes | Already covered by purchase posting path | Existing purchase type | Must not double-post |
| Sales issue/consumption | Yes | Already covered by sales posting path | Existing sales type | Must not double-post |
| Opening balance import/manual | Yes | Yes (can be batch-posted) | Stock Opening Balance | Dr Inventory / Cr Opening Equity |
| Direct stock in (non-purchase) | Yes | Yes | Stock In | Economic inflow not tied to purchase invoice |
| Direct stock out (non-sales) | Yes | Yes | Stock Out | Economic outflow not tied to sales invoice |
| Adjustment up/down (physical reconcile) | Yes | Yes | Stock Adjustment | Variance write-up/write-down |
| Split/Merge lot structure | Yes | No | N/A | Internal quantity topology only |

## PR Breakdown

### PR-1: Policy And Invariants
Objective:
- Freeze movement-to-posting policy and anti-double-posting rules.

Deliverables:
- This policy matrix accepted.
- Explicit invariants in docs:
  - Every physical movement => StockTransaction.
  - Only economic events => Voucher/JE posting.
  - Purchase/Sales-linked transactions should reference existing JE when available; never create duplicate voucher for same event.

Validation:
- Team sign-off in PR comments.

---

### PR-2: VoucherType Seeds
Objective:
- Add stock movement voucher types in DEA.

Deliverables:
- Migration seed (idempotent):
  - `Stock Opening Balance`
  - `Stock In`
  - `Stock Out`
  - `Stock Adjustment`

Validation:
- Seed applies successfully in all schemas.
- Lookup by name works via `_resolve_voucher_type` in `post_doc.py`.

Rollback:
- Reverse migration deletes only seeded types if safe (or leaves immutable reference data by policy).

---

### PR-3: Posting Rules
Objective:
- Implement posting rules and register by voucher type names.

Deliverables:
- Rule modules in DEA posting rules package.
- Rules return balanced lines in both currencies per policy.
- Fingerprint payload for idempotent repost checks.

Validation:
- Unit tests: each rule balanced per currency.
- Rule registration verified at app startup.

---

### PR-4: StockTransaction Integration Hook
Objective:
- Wire stock movement service to optionally post voucher for economic events.

Deliverables:
- Service helper that:
  - decides if movement requires posting,
  - calls `create_and_post_voucher_for_doc(doc=stock_txn, ...)`,
  - persists returned `journal_entry` on stock transaction.
- Guard to prevent duplicate posting for purchase/sales paths.

Validation:
- Integration tests for direct in/out, opening, adjustment.
- Idempotency test: unchanged payload returns previous posted voucher.

---

### PR-5: UX + Retry Operationalization
Objective:
- Ensure operator can recover from posting failures safely.

Deliverables:
- UI messages:
  - inventory saved + posting succeeded
  - inventory saved + posting failed (retry available)
- Retry action for pending/unposted stock transactions.

Validation:
- Manual and automated flow tests for failure/retry.

---

### PR-6: Reconciliation + Backfill
Objective:
- Establish control checks between inventory and DEA books.

Deliverables:
- Reconciliation report:
  - inventory aggregate vs DEA inventory ledgers by currency.
- Backfill command to post missing vouchers for historical eligible stock transactions.

Validation:
- Dry-run mode and apply mode both tested.
- Tolerance-based mismatch alerts.

## Definition Of Done (Program)
- All PRs merged in order.
- No double-posting in purchase/sales integrated flows.
- Economic stock movements produce voucher+JE linkage.
- Reconciliation report passes on fresh transactions.
- Docs updated and adopted by operations team.

## Branching And Commit Convention
- Branches:
  - `feature/stock-dea-pr1-policy`
  - `feature/stock-dea-pr2-vouchertypes`
  - `feature/stock-dea-pr3-posting-rules`
  - `feature/stock-dea-pr4-stock-hook`
  - `feature/stock-dea-pr5-ux-retry`
  - `feature/stock-dea-pr6-reconciliation`
- Commit style:
  - `stock-dea(prX): <scope> <summary>`

## Tracking Checklist
- [ ] PR-1 merged
- [ ] PR-2 merged
- [ ] PR-3 merged
- [ ] PR-4 merged
- [ ] PR-5 merged
- [ ] PR-6 merged

## Open Decisions
- [ ] Exact ledger keys for INR valuation lines.
- [ ] Exact ledger keys for USD weight lines.
- [ ] Whether opening balance posting is immediate or end-of-day batch.
- [ ] Variance threshold policy for auto-post vs manual approval.

