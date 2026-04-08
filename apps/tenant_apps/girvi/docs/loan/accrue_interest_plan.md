# Girvi Interest Accrual Plan

_Last updated: 2026-04-06_  
_Status: Phase 4 V1 work completed; only the optional DEA period-close UI handoff remains pending_

---

## Purpose

This document records the agreed direction for adding **interest accrual** to the `girvi` loan system and integrating it cleanly with `dea` accounting.

It is intended to be the long-term reference for:
- scope decisions,
- posting rules,
- trigger behavior,
- scheduling policy,
- and implementation progress.

---

## Current Verified State

The current repository now has the core accrual engine and trigger hooks implemented.

### What exists now
- `BaseLoan.interest_due()` in `apps/tenant_apps/girvi/models/loan_refactored.py` still defines the baseline **completed-month** calculation behavior.
- `LoanInterestAccrual` provides a persisted audit trail for recognized periods.
- `InterestAccrualService` supports preview + execute, remains idempotent, and can optionally post DEA journal entries.
- receipt and release posting rules now clear `INTEREST_RECEIVABLE` before recognizing any additional `INTEREST_INCOME`.
- a tenant-aware management command (`accrue_loan_interest`) and scheduled task entry point (`accrue_loan_interest_batch`) are available.
- payment, release, and renewal flows now perform accrual catch-up before settlement logic.

### What is still missing
- no UI visibility yet for `last_accrual_date` / outstanding accrued interest,
- no one-time backfill workflow for legacy open loans,
- no dedicated handoff yet from the DEA period-adjustment screen into the Girvi accrual service.

---

## Agreed V1 Scope

### Include in V1
- `GivenLoan` only
- simple interest only
- completed-month accruals only
- persisted accrual history
- DEA journal posting
- automated and manual trigger paths
- catch-up accrual before settlement events

### Explicitly defer for later
- compound interest
- penalty / late fee accrual
- NPA-specific interest suspension rules
- `TakenLoan` accrual
- daily pro-rata accrual basis

---

## Core Design Decisions

### 1. Preserve the current business calculation rule
For V1, the accrual engine should follow the same semantics already used by:
- `BaseLoan.interest_due()`
- `InterestCalculationService.months_between()`

That means:
- interest is recognized on **completed month intervals**,
- not on daily pro-rata basis,
- and not as future income in advance.

This keeps the first rollout compatible with current loan dues and avoids breaking existing user expectations.

### 2. Use an accrual audit model instead of a mutable running total
Recommended new model:
- `LoanInterestAccrual`

Suggested fields:
- `loan`
- `period_start`
- `period_end`
- `accrued_amount`
- `base_interest_snapshot`
- `trigger_source`
- `status`
- `journal_entry_voucher` / `voucher` link
- timestamps and created-by metadata

A uniqueness / idempotency rule should prevent duplicate accrual rows for the same loan-period.

### 3. Use the existing service-layer pattern
The repo already follows a strong `Command -> Preview -> Result` service pattern for Girvi workflows.

Interest accrual should follow the same approach with something like:
- `InterestAccrualCommand`
- `InterestAccrualPreview`
- `InterestAccrualResult`
- `InterestAccrualService`

This keeps the new logic consistent with `LoanCreationService`, `LoanRenewalService`, and `ReleaseLifecycleService`.

### 4. Book accrued interest into DEA before cash is collected
Recommended accounting entry for accrual posting:
- **Dr `INTEREST_RECEIVABLE`**
- **Cr `INTEREST_INCOME`**

When the customer later pays interest, the system should clear the receivable instead of recognizing the same income a second time.

**Implementation update (2026-04-06):**
- `InterestAccrualService.execute(post_to_accounting=True)` now creates a `JournalEntryVoucher` with `entry_type="ACCRUAL"` and posts it through the DEA journal-entry posting engine.
- receipt and release posting rules now split interest into:
  - receivable-clearing portion, and
  - fresh-income portion (if any remainder exists).
- ledger lookup now supports the stable key `INTEREST_RECEIVABLE` while remaining compatible with the existing seeded ledger name `Interest Receivables`.

### 5. Make settlement flows catch up any missed accruals
Even if the batch scheduler did not run, these flows should force a catch-up accrual before final settlement logic:
- release flow,
- renewal flow,
- interest/principal receipt flow.

This ensures the loan can still be closed or renewed correctly without depending purely on background jobs.

---

## Scheduling Policy: End of Month vs Beginning of Month

### Decision
**Do not hard-code the engine to end-of-month only.**

Instead:
1. keep the accrual engine **idempotent and callable any day**, and
2. provide a **company-level schedule preference** for when the automated batch should run.

### Recommended user-facing option
Add a preference like:
- `loan_interest_accrual_timing`
  - `EOM` = End of month
  - `BOM` = Beginning of next month

### Recommended default
- **Default: `EOM`**

This is the safer default for accounting teams because it aligns naturally with month-end review and period close.

### Important accounting guardrail
If the user selects **Beginning of Month (`BOM`)**, it should mean:
- run the accrual job on the **first day of the next month**,
- for the **interest already earned in the period that just closed**.

It should **not** mean booking the entire upcoming month's interest in advance.

### Practical interpretation
- `EOM`: March interest is accrued on `2026-03-31`
- `BOM`: March interest is accrued on `2026-04-01` as the catch-up run for the closed March period

### Why this approach is better
This gives the business operational flexibility without breaking accounting correctness:
- finance teams who close books monthly can prefer `EOM`
- teams who batch work on the first of the month can choose `BOM`
- the economic accrual basis stays the same in both modes

### Technical recommendation
Even with `EOM` / `BOM` scheduling, the underlying service should still be callable daily and remain idempotent. The setting should control the **scheduled batch window**, not the internal ability to catch up accurately.

---

## Recommended Trigger Paths

| Trigger | Purpose | Recommendation |
|---|---|---|
| Daily / scheduled batch | Recognize newly due interest | Yes |
| Management command | Backfill, rerun, recovery | Yes |
| DEA period-close screen | Manual finance fallback | Yes |
| Release / renewal / receipt flow | Catch up missed accrual before settlement | Yes |

### Batch trigger recommendation
Use the tenant-aware management command now added in the repo:

```bash
python manage.py accrue_loan_interest --as-of-date YYYY-MM-DD
```

Current supported options include:
- `--schema` to scope to one tenant,
- `--loan-id` to scope to one loan,
- `--dry-run` for preview-only runs,
- `--skip-accounting` to create accrual rows without DEA posting,
- `--backfill` to explicitly mark a one-time catch-up run for open loans.

A scheduled Celery entry point is also available as `accrue_loan_interest_batch`, and the same command can still be run via **OS cron / Windows Task Scheduler** where simpler operations are preferred.

---

## Proposed Implementation Phases

### Phase 0 - Discovery and decision log
- [x] Reviewed current `girvi` interest calculation path
- [x] Reviewed current `dea` manual interest accrual flow
- [x] Agreed V1 scope and accounting direction
- [x] Agreed configurable `EOM` / `BOM` scheduling policy

### Phase 1 - Domain model and service
- [x] Add `LoanInterestAccrual` model
- [x] Add `InterestAccrualService`
- [x] Add preview + execute flow with idempotency rules
- [x] Add read helpers such as `gross accrued`, `interest paid`, `interest outstanding`

### Phase 2 - DEA posting integration
- [x] Seed / verify `INTEREST_RECEIVABLE` ledger
- [x] Post accrual vouchers into DEA
- [x] Make receipts and releases clear receivable instead of double-booking income

### Phase 3 - Trigger rollout
- [x] Add tenant-aware management command
- [x] Add scheduled batch entry point
- [x] Add catch-up hooks in release / renewal / payment flows
- [ ] Wire manual `dea_period_adjustments` support to Girvi accrual generation

> **Pending finance handoff:** the DEA period-close / period-adjustment UI in `apps/tenant_apps/dea/views/period.py` still does **not** directly invoke `InterestAccrualService`. Today the operational fallback is to run `python manage.py accrue_loan_interest ...` (or the scheduled task) before or during month-end close. This remains the one unfinished trigger-side integration from the original checklist.

### Phase 4 - UI, reporting, and verification
- [x] Show `last_accrual_date` and interest metrics in loan screens
- [x] Add backfill for open loans
- [x] Add tests for month boundaries, idempotency, and settlement correctness

**Phase 4 start note (2026-04-06):** begin with loan-detail reporting visibility so branch users can see accrued interest, paid interest, receivable-clearing position, and the most recent accrual date directly from the main `GivenLoan` screen.

**Implementation update (2026-04-06):** the main `GivenLoan` detail screen and cross-domain read model now expose:
- gross accrued interest,
- interest paid to date,
- accrued outstanding interest,
- receivable balance already recognized in DEA,
- and the most recent accrual date.

**Backfill update (2026-04-06):** the tenant-aware `accrue_loan_interest` command now supports an explicit `--backfill` mode for one-time catch-up runs on open loans while recording `BACKFILL` in the accrual audit trail.

**Verification update (2026-04-06):** test coverage now explicitly includes:
- month-boundary behavior (no accrual before the first full month completes),
- idempotent reruns when all due periods are already present,
- accrual-aware settlement posting for receipt/release flows.

---

## Key Files Expected to Change

### Girvi
- `apps/tenant_apps/girvi/models/loan_refactored.py`
- `apps/tenant_apps/girvi/services.py`
- `apps/tenant_apps/girvi/views/loanpayment.py`
- `apps/tenant_apps/girvi/service_modules/payment.py`
- `apps/tenant_apps/girvi/service_modules/release_lifecycle.py`
- `apps/tenant_apps/girvi/service_modules/renewal.py`
- `apps/tenant_apps/girvi/tasks.py`
- `apps/tenant_apps/girvi/management/commands/accrue_loan_interest.py`
- `apps/tenant_apps/girvi/management/commands/update_loans.py` (pattern reference)

### DEA
- `apps/tenant_apps/dea/views/period.py`
- `apps/tenant_apps/dea/forms.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_receipt.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_release.py`
- `apps/tenant_apps/dea/management/commands/seed_core_ledgers.py`

---

## Summary Recommendation

### Final recommendation for timing
- **Support both `EOM` and `BOM` as a user/company option**
- **Default to `EOM`**
- keep the service callable any time,
- and interpret `BOM` as **post last month's earned accrual on the first day of the next month**, not as future-month advance income.

This gives the best balance of:
- accounting correctness,
- operational flexibility,
- and implementation safety.
