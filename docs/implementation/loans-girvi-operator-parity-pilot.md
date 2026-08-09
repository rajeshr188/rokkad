---
status: active
owner: project
updated: 2026-08-09
tags: [loans, girvi, pilot, operations, acceptance]
related: [../plans/loan-operational-parity-pilot.md, ../plans/loans-girvi-consolidation-fit-gap.md, loans-configurable-document-operations.md]
---

# Girvi And Loans Operator Parity Pilot

## Current State

Pilot preparation has started for tenant `jcl1`. The last clean Loans
checkpoint is `2eba0b0`; the exact pilot runtime checkpoint remains pending
while separate accounting/Girvi changes are uncommitted.
The starting data is intentionally not transferred or synchronized:

| Product | Existing customer loans | State summary |
| --- | ---: | --- |
| Loans | 8 | 1 active, 1 draft, 1 cancelled, 5 closed |
| Girvi | 8 | 2 active, 6 closed |

Loans currently has one active license, one series, nine collateral items, no
storage hierarchy, no physical-verification session, no operational notice,
and no active custom loan-ticket assignment. The compliant fixed ticket is
therefore the current Original/Duplicate renderer. Document integrity reports
zero findings.

This is a real operator evaluation, not an automated migration or seed script.
Create independent Girvi and Loans records with equivalent business facts.
Never copy primary keys, lifecycle rows, accounting evidence, or custody rows
between applications.

## Start Gate

Record these before scoring a scenario:

| Evidence | Required value | Result |
| --- | --- | --- |
| Commit | Exact tested commit | Pending; last clean Loans checkpoint `2eba0b0` |
| Worktree | No unreviewed runtime changes | **Blocked: accounting/Girvi runtime changes are uncommitted** |
| Tenant | `jcl1` | Ready |
| Workspace Owner | Named operator | Pending |
| Accounting mode | Explicitly `DEFERRED` or `DEA` | `DEFERRED` |
| Backup identity and restore location | Named disposable-development snapshot | Pending |
| Document integrity | Zero findings | Pass |
| Printer | Make/model, driver, A4/A5 stock, duplex setting | Pending |

Do not score accounting clarity unless the accounting mode is recorded. In
`DEFERRED`, pending outboxes are expected and must not be described as posted.
In `DEA`, voucher/journal evidence and readiness must reconcile.

### Automated Preflight Record

On 2026-08-09:

- Django system check passed.
- `makemigrations --check --dry-run` reported no changes for `dea`, `loans`,
  or `girvi`.
- `jcl1` document integrity passed with zero findings.
- 42 focused document persistence and renderer tests passed.
- The first 191-test cross-product run exceeded five minutes; the warmed retry
  exceeded ten minutes and surfaced failures before completion. It is not a
  pass and must not be cited as one.
- The first isolated failure was a test that implicitly assumed DEA while the
  new policy defaults to `DEFERRED`. After the scenario explicitly selected
  `DEA`, that focused borrower-accounting guidance test passed.

The official operator clock and score remain stopped. First consolidate the
current accounting/Girvi runtime changes into a reviewed checkpoint, retain
explicit accounting-mode setup in tests, and complete smaller product-specific
preflight suites. Test-runner schema setup time is not an application score.

## Shared Scenario Facts

Use the same human-readable facts in both products while allowing each product
to allocate its own identifiers:

- one active Party with a long regional-language name and complete contact;
- one gold item and one silver item with photographs;
- different metal-based monthly rates and allocated principal per item;
- a current valuation that passes the configured maximum LTV;
- one repayment containing interest and principal;
- one overdue date suitable for an overdue notice;
- one retained item and one returned item for release-and-renew;
- one intentionally misplaced storage observation;
- a second loan suitable for full release;
- a correction target whose later dependent event proves reverse-order
  rejection.

Record the exact facts in the session notes. Equivalent facts matter more than
matching generated numbers.

## Scenario Worksheet

For every row, first complete Girvi, reset the timer and operator notes, then
complete Loans. Do not use database/admin shortcuts.

| ID | Operator outcome | Required evidence | Girvi | Loans |
| --- | --- | --- | --- | --- |
| P1 | Set up license, numbering and required business policy | active license/series, next-number clarity, expiry behavior | Pending | Pending |
| P2 | Create and disburse a mixed-metal customer loan | Party, two items, photos, item principal/rates, LTV rejection test, immutable approval/disbursal evidence | Pending | Pending |
| P3 | Print and scan physical identity | Original/Duplicate ticket, signatures, item label, QR opens correct loan | Pending | Pending |
| P4 | Place and transfer collateral | complete Branch/Vault/Cabinet/Box path, item and destination scan, immutable movement/current location | Pending | Pending |
| P5 | Accrue and record repayment | interest calculation, allocation, receipt, event/accounting disposition, Party statement | Pending | Pending |
| P6 | Complete full release | complete settlement, all remaining items returned, signatures, Form H/release memo, loan closed | Pending | Pending |
| P7 | Release and renew | old loan closed, selected item returned, retained/additional items on newly numbered loan, renewal agreement | Pending | Pending |
| P8 | Handle overdue communication | due/overdue report, notice source, idempotent delivery/retry evidence | Pending | Pending |
| P9 | Verify physical inventory | frozen expectation, found/misplaced observation, blocked transfer/release, reasoned correction, discrepancy notice | Pending | Pending |
| P10 | Correct an operator mistake | later-dependency rejection, reverse chronological compensation, immutable reason and resulting balance/custody | Pending | Pending |
| P11 | Produce daily/regulatory outputs | active, daily, interest, overdue, release/renewal, storage, license, Party reports plus required PDFs | Pending | Pending |
| P12 | Test permissions and isolation | ordinary staff denied Owner actions; unknown/cross-workspace source is not exposed | Pending | Pending |

For each product and scenario record:

- start/end time and operator step count;
- first unclear label or next action;
- validation errors and whether the recovery instruction was actionable;
- workaround, administrator intervention, or retry;
- generated document/report identifiers;
- source event, custody, notice, and accounting evidence;
- any unexplained financial or custody difference.

## Scorecard

Score `0` failed, `1` completed with serious confusion/workaround, `2` completed
with minor friction, or `3` clear and complete. Double-weight the four agreed
selection priorities.

| Criterion | Weight | Girvi | Loans | Evidence |
| --- | ---: | ---: | ---: | --- |
| Complete domain workflow | 2 | Pending | Pending | |
| Architecture/audit clarity | 2 | Pending | Pending | |
| Document clarity | 2 | Pending | Pending | |
| Ease and readable next action | 2 | Pending | Pending | |
| Operator time/error recovery | 1 | Pending | Pending | |
| Custody/location correctness | 1 | Pending | Pending | |
| Permission/tenant safety | 1 | Pending | Pending | |
| Accounting/reconciliation quality | 1 | Pending | Pending | |

The score cannot override a critical failure. A product is ineligible if money,
custody, tenant isolation, a required document, backup/restore, or unexplained
reconciliation fails.

## Physical Document Matrix

Use the detailed matrix in
[Loans configurable document operations](loans-configurable-document-operations.md).
At minimum print the same ticket on intended A4 and A5 paths, verify
Original/Duplicate identity and shared verification ID, sign both signature
areas, scan the QR from paper, inspect margins at Actual size/100%, and test the
driver's duplex flip edge. Record printer, driver, stock, scaling, operator and
date. On-screen PDF inspection is not a physical pass.

## Exit

The pilot is complete only when all scenario evidence and scores are filled,
the printer matrix is signed, backup/restore is rehearsed, no critical failure
is open, and remaining Girvi capabilities are classified `PORT`, `REPLACE`, or
`RETIRE`. The winner and loser remain undecided until a separate retirement ADR
is accepted.
