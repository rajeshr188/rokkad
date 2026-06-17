---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Girvi PR-1 Compatibility Plan and Progress

Last updated: 2026-03-18 (post-push sweep + validation)
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
- Browser-level end-to-end functional pass for key PR-1 flows

### Pending
- End-to-end functional pass in browser for:
  - Loan detail tabs
  - Loan archive pages
  - Release flows including custody check
  - Notice generation path

- Test hygiene in legacy girvi test module:
  - `apps/tenant_apps/girvi/tests.py` raises `NameError: TestCase is not defined` during Django test discovery.
  - This is a pre-existing blocker unrelated to PR-1 compatibility templates/views.

## 2026-03-18 Delta Update (After Commit Push)
### Remote status
- Focused PR-1 compatibility commit pushed to origin:
  - Branch: `dea-kiss`
  - Commit: `c87e3e8`
  - Message: `girvi: align templates/views with refactored loan API and track PR1 progress`

### Compatibility sweep result
- Broad legacy token sweep re-run across:
  - `templates/girvi/**`
  - `apps/tenant_apps/girvi/views/**`

- Outcome:
  - No active legacy contract mismatches found in target runtime paths.
  - Residual hits were benign only:
    - Canonical fields (for example `total_due_with_currency`)
    - JavaScript parameter naming (`loanId`)
    - Commented legacy snippets in non-runtime comments

### Validation run result
- `python manage.py check`:
  - Passed with no system issues.

- `python manage.py test apps.tenant_apps.girvi.tests`:
  - Blocked by pre-existing issue in `apps/tenant_apps/girvi/tests.py`:
    - `NameError: name 'TestCase' is not defined`
  - This prevented full automated functional assertion at app test-suite level.

### Current assessment
- PR-1 compatibility slice is stable at static/diagnostic level and published to remote.
- Remaining work for full sign-off is browser E2E flow validation (loan detail/archive/release/custody/notice) and optional cleanup of legacy `tests.py` so test discovery can run end-to-end.

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

