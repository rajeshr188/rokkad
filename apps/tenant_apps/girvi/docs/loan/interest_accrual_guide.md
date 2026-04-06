# Girvi Interest Accrual Guide

_Last updated: 2026-04-06_

---

## Purpose

This guide explains:
- how **interest accrual currently works** in the `girvi` + `dea` flow,
- what is already automated,
- what users/operators should run manually when needed,
- and what future improvements are still recommended.

It is intended as the practical companion to `accrue_interest_plan.md`.

---

## Current Scope (What is implemented today)

The current V1 accrual rollout supports:

- **`GivenLoan` only**
- **simple interest only**
- **completed-month accruals only**
- persisted monthly accrual history via `LoanInterestAccrual`
- DEA accounting posting for accrued interest
- automatic catch-up before payment / release / renewal
- tenant-aware batch and backfill execution

Not included yet:
- `TakenLoan` accrual
- daily pro-rata accrual basis
- compound interest
- penalty / late fee accrual
- NPA-specific suspension rules

---

## Conceptual Model

Before this work, interest was mostly available as an **on-demand calculation** (`interest_due()`), but not as a persisted monthly accrual history.

Now the system has two related views of interest:

1. **Operational due calculation**
   - Used to understand what the customer owes as of now.
   - Based on the existing Girvi business rule for completed months.

2. **Persisted accounting accrual**
   - Stored in `LoanInterestAccrual`
   - Used to recognize earned interest period-by-period in DEA
   - Prevents missing or duplicate recognition during close / receipt / release flows

---

## How the Accrual Calculation Works Today

### 1. Basis of calculation
The service uses the same business logic already established in the app:

- completed months only,
- no daily pro-rata,
- no advance recognition of future periods.

In practice, the service looks at:
- `loan.loan_date`
- the loan’s monthly/base interest amount (`get_interest_amount`)
- the selected `as_of_date`
- any loan release date cap, if the loan has already been released

### 2. Completed-month behavior
A period is accrued only after a full month has completed.

Example:
- Loan date: `2026-01-15`
- As-of date: `2026-02-14` → **0 months accrued**
- As-of date: `2026-02-15` → **1 month accrued**
- As-of date: `2026-03-15` → **2 months accrued**

This matches the current Girvi expectation and avoids changing customer-facing dues behavior.

### 3. Idempotency protection
The system stores one row per accrued period in:
- `apps/tenant_apps/girvi/models/accrual.py`

Because accruals are persisted by loan + period, re-running the service does **not** create duplicates for periods that already exist.

This means the accrual engine is safe to:
- preview repeatedly,
- run daily,
- run at month-end,
- and run again as catch-up before settlement flows.

---

## What Gets Stored

Each accrued period is written as a `LoanInterestAccrual` row with fields such as:

- `loan`
- `period_start`
- `period_end`
- `accrued_amount`
- `base_interest_snapshot`
- `trigger_source`
- `status`
- `journal_entry_voucher`
- metadata like `created_by`, notes, timestamps

This provides a reliable audit trail of **when** interest was recognized, **for which period**, and **through which trigger path**.

---

## How DEA Accounting Works

When accrual is posted to accounting, the journal is:

- **Dr `INTEREST_RECEIVABLE`**
- **Cr `INTEREST_INCOME`**

This reflects:
- the business has earned the interest,
- but cash has not yet been collected.

### Why this matters
When the customer later pays interest, the system now clears previously recognized receivable first instead of double-booking income.

So receipt/release posting now behaves as:
- clear the accrued receivable portion first,
- then recognize only any fresh/unaccrued remainder as new income.

---

## Trigger Paths That Work Today

### 1. Tenant-wide batch command
Main command:

```bash
python manage.py accrue_loan_interest --as-of-date YYYY-MM-DD
```

Useful options:

```bash
python manage.py accrue_loan_interest --dry-run --as-of-date 2026-03-31
python manage.py accrue_loan_interest --schema tenant1 --as-of-date 2026-03-31
python manage.py accrue_loan_interest --loan-id 123 --as-of-date 2026-03-31
python manage.py accrue_loan_interest --skip-accounting --as-of-date 2026-03-31
python manage.py accrue_loan_interest --backfill --as-of-date 2026-03-31
```

### 2. Scheduled task entry point
A scheduled wrapper exists in:
- `apps/tenant_apps/girvi/tasks.py`

Task name:
- `accrue_loan_interest_batch`

This now calls the command with `respect_timing=True`, so the company preference `Loan__Accrual_Timing` actively controls whether a scheduled tenant run is allowed on that date:
- `EOM` → run on the last day of the month
- `BOM` → run on the first day of the month

This allows future Celery Beat / scheduler automation without changing the core service.

### 3. Catch-up before settlement flows
Even if the batch job was missed, the system now catches up accruals before:

- loan payment receipt,
- loan release,
- loan renewal.

These paths are now governed by company-level preference toggles:
- `Loan__Catchup_On_Receipt`
- `Loan__Catchup_On_Release`
- `Loan__Catchup_On_Renewal`

The accounting side of batch/backfill posting is also now influenced by:
- `Loan__Auto_Post_Accruals`
- `Loan__Allow_Backfill_Posting`

This is important because it makes the accrual process more robust and less dependent on background jobs always running on time.

---

## Reporting Visibility Available Today

The main `GivenLoan` detail screen now shows:

- gross accrued interest
- interest paid to date
- accrued outstanding interest
- DEA receivable balance
- last accrual date

This gives branch and finance users a quick operational snapshot from the normal loan detail page.

---

## Preference UI: How To Reach It

### Workspace/company preference page
This is the main UI page for tenant-specific settings.

You can reach it by:
- opening the workspace sidebar and clicking **Preferences**, or
- visiting:
  - `/orgs/workspace/<workspace_id>/preferences/`

Named route:
- `workspace_preferences`

This page is backed by:
- `apps/orgs/views.py` → `CompanyPreferenceBuilder`
- `templates/company/company_preferences.html`

### Legacy company preference URL
A backward-compatible route still exists:
- `/orgs/company-preferences/`

Named route:
- `company-preferences`

Templates like `templates/_base.html` and `templates/tenant.html` still link here.

### Built-in dynamic-preferences page
The package’s own default URLs are also currently mounted at:
- `/dynamic_preferences/`

However, this is more of a framework-level page and the project already recommends relying on the custom workspace preference UI instead.

### Global vs company behavior in practice
- **Global preferences** act as the system fallback defaults.
- **Company/workspace preferences** override those values for the selected tenant.

The runtime helper:
- `apps/orgs/preferences.py` → `CompanyPreferences`

resolves values in that order automatically.

## Operational Guidance

### Recommended normal usage
For ongoing operations:
- run the scheduled/batch accrual process regularly,
- keep catch-up hooks enabled for release/renewal/receipt,
- use `--dry-run` before major month-end or backfill runs if needed.

### Recommended backfill usage
If older open loans need to be caught up:

```bash
python manage.py accrue_loan_interest --backfill --as-of-date YYYY-MM-DD
```

Use `--dry-run` first if the run is large.

---

## Known Limitation Still Pending

One optional finance-side integration is still pending:

- the DEA period-close / period-adjustment UI in
  `apps/tenant_apps/dea/views/period.py`
  does **not yet directly call** `InterestAccrualService`.

### Current workaround
Use the batch command (or scheduled task) before or during month-end close.

This is documented and should not be missed in future work.

---

## Recommended Future Improvements

### High priority
1. **DEA period-close UI handoff**
   - Add a button/action in the DEA period adjustment/close screen to trigger Girvi accrual generation directly.
   - This is the main remaining operational integration gap.

2. **Company-level schedule preference (`EOM` / `BOM`)**
   - Keep the engine idempotent daily.
   - Let companies choose whether the scheduled run happens at end-of-month or beginning-of-next-month.

3. **Backfill runbook / admin UX**
   - Add a documented finance/admin process or a simple UI trigger for one-time backfill runs.

### Medium priority
4. **Richer reporting**
   - accrual summaries by tenant / branch / month
   - receivable aging and period trend views
   - dashboard widgets for overdue accrued interest

5. **Reversal / correction tooling**
   - Support controlled reversal or adjustment of an already posted accrual period if needed for accounting cleanup.

6. **Manual finance approval workflow**
   - Optional review/approve layer before posting large month-end accrual batches.

### Long-term enhancements
7. **Daily pro-rata accrual option**
   - If the business wants more precise time-based recognition later.

8. **Penalty / late-fee accrual**
   - Separate from standard earned interest.

9. **`TakenLoan` accrual support**
   - Extend the same pattern to liabilities where required.

10. **NPA-specific rules**
   - Suspend or change accrual behavior for non-performing loans if finance policy requires it.

---

## Summary

### Current state in one line
Interest accrual is now **persisted, idempotent, DEA-posted, batch-runnable, and automatically caught up during key settlement flows**.

### Main future work
The biggest remaining improvement is to wire the **DEA period-close UI** directly to the Girvi accrual service and optionally add richer scheduling/reporting controls.
