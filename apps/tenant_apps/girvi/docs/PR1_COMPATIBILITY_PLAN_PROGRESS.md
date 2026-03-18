# Girvi PR-1 Compatibility Plan and Progress

Last updated: 2026-03-18
Scope: Refactored `GivenLoan` model/view/template API compatibility alignment.

## Goal
Stabilize loan/release/notice/archive flows by replacing legacy field usage with canonical refactored API names and by removing invalid relations/queries.

## Canonical Contract (Refactored)
- Loan identity: `loan_id`
- Borrower relation: `borrower`
- Loan amount display helper: `get_loan_amount_with_currency`
- Interest value: `interest_due`
- Total due numeric/currency: `total_due`, `total_due_with_currency`
- Elapsed months: `months_elapsed`

## Plan (Phased)
1. Detect drift:
- Grep templates/views for legacy tokens (`loanid`, `loan.customer`, `interestdue`, `due_with_currency`, `noofmonths`, old helper names).

2. Patch high-risk paths first:
- Loan detail templates (all variants)
- Loan archive templates
- Release templates and custody checks
- Notice view customer/loan joins

3. Re-verify:
- Diagnostics (`get_errors`) on edited files
- Re-run grep for legacy patterns
- Confirm only benign/commented leftovers remain

4. Commit in focused slice:
- Stage only PR-1 compatibility files
- Keep unrelated changes outside this commit

## Progress Snapshot
### Completed
- Fixed invalid relation prefetch in loan items tab:
  - Removed `repledgedloanitems` prefetch from `GivenLoan` items-tab fetch.

- Restored prev/next navigation compatibility:
  - Added/used `get_previous` and `get_next` semantics with `loan_id` labels.

- Updated loan detail templates to canonical names:
  - Borrower/customer display context alignment
  - `months_elapsed`, `interest_due`, `total_due_with_currency`
  - `get_loan_amount_with_currency`

- Updated loan archive templates to canonical fields:
  - `loan_id`, `loan_date`, `loan_amount`

- Updated release/custody templates:
  - `loan.customer` -> `loan.borrower`
  - `interest`/`due` -> `interest_due`/`total_due`

- Updated notice view joins and relations:
  - Notification/customer now sourced via borrower relation
  - Replaced old reverse-rel paths with `loans_received`

- Verification passes completed:
  - Diagnostics clean on edited compatibility files
  - Legacy-token sweeps now mostly clean; remaining hits are canonical uses or commented examples

### In Progress
- Preparing focused PR-1 commit from current dirty worktree

### Pending
- End-to-end functional pass in browser for:
  - Loan detail tabs
  - Loan archive pages
  - Release flows including custody check
  - Notice generation path

## Files Included in PR-1 Compatibility Slice
- `apps/tenant_apps/girvi/views/loan.py`
- `apps/tenant_apps/girvi/views/notice.py`
- `templates/girvi/loan/loan_detail.html`
- `templates/girvi/loan/loan_detail_1.html`
- `templates/girvi/loan/loan_detail_2.html`
- `templates/girvi/loan/loan_renew.html`
- `templates/girvi/loan_archive_day.html`
- `templates/girvi/loan_archive_week.html`
- `templates/girvi/loan_archive_month.html`
- `templates/girvi/loan_archive_year.html`
- `templates/girvi/release/bulk_release_details.html`
- `templates/girvi/release/release_detail.html`
- `templates/girvi/release/release_success.html`
- `templates/girvi/release_custody_check.html`

## Notes
- Workspace contains many unrelated/staging-ready changes (including guardrails/migration/docs/UI layout changes). These are intentionally excluded from the focused compatibility commit.
