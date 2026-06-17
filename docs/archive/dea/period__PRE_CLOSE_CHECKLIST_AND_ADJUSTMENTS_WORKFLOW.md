---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# DEA Pre-Close Checklist and Adjustments Workflow

_Last updated: 2026-04-03_

## Purpose

This document records the implemented month-end / period-end close workflow for the DEA app and the remaining roadmap items for a more accountant-grade close engine.

---

## What is implemented now

### 1. Pre-close checklist in the period close screen

**Entry point:** `dea_period_close`

The close confirmation page now shows:

- journal entry count for the period
- pre-close adjustment count
- draft voucher count
- checklist status for:
  - accruals
  - prepaid expense adjustments
  - depreciation
  - interest accrual
  - draft-voucher cleanup

**Guardrails:**
- users must acknowledge the checklist before closing
- the close form blocks closing when draft vouchers still exist in the period

### 2. Period adjustments workflow

**Entry point:** `dea_period_adjustments`

Users can now post structured pre-close adjustments directly from the period workflow for:

- `ACCRUAL`
- `PREPAID_EXPENSE`
- `DEPRECIATION`
- `INTEREST_ACCRUAL`
- `CUSTOM`

Each adjustment creates:

1. a `JournalEntryVoucher` review record
2. matching line items for debit / credit legs
3. a posted `Voucher` of type `PERIOD_ADJUSTMENT`
4. a real `JournalEntry` linked to the selected `AccountingPeriod`

This means the adjustment immediately affects the periodâ€™s GL before close.

### 3. Existing close logic retained

`AccountingPeriod.close_period()` still performs the simplified close by:

- identifying `Income`, `Revenue`, and `Expense` ledgers
- calculating period balances
- transferring net effect to `Retained Earnings`
- creating closing ledger / account statements
- marking the period `CLOSED`

---

## Recommended operating procedure

### Monthly / year-end close sequence

1. Open the target period detail page.
2. Use **Adjustments** to post any required entries:
   - accruals
   - prepaid releases
   - depreciation
   - loan interest accrual
3. Review the close checklist.
4. Resolve or reverse any draft vouchers.
5. Close the period.
6. Optionally lock the period after review.

---

## Current design boundary

The new workflow is a **structured manual adjustment process**.

It improves correctness and discoverability, but it is not yet a full automation engine for:

- recurring accrual templates
- auto-reversal on next-period opening
- depreciation schedule calculation
- automatic loan-interest accrual from Girvi balances
- separate `Income Summary / Profit & Loss` temporary closing ledger stages

---

## Future roadmap

### Phase 1 â€” Operational hardening

- add saved adjustment templates per company
- add approval / review status before final close
- show unresolved draft vouchers with direct links
- include close-time validation for missing required ledgers

### Phase 2 â€” Automation

- recurring accrual scheduler
- automatic reversal flags for accrual / prepaid entries
- depreciation schedule engine with monthly posting
- Girvi / loan interest accrual generation at period end

### Phase 3 â€” Advanced close architecture

- optional `Income Summary` / `P&L Clearing` ledger workflow
- close pack report export
- audit log of who reviewed each checklist item
- period reopen / correction workflow with tracked reversal entries

---

## Key files

- `apps/tenant_apps/dea/views/period.py`
- `apps/tenant_apps/dea/forms.py`
- `templates/dea/period_adjustments.html`
- `templates/dea/period_close_confirm.html`
- `apps/tenant_apps/dea/test_period_close.py`

---

## Verification snapshot

Validated with:

- `manage.py test apps.tenant_apps.dea.test_period_close apps.tenant_apps.dea.test_opening_balance_access -v 2`
- `manage.py check`

