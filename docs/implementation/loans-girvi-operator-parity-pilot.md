---
status: active
owner: project
updated: 2026-08-09
tags: [loans, girvi, pilot, operations, acceptance]
related: [../plans/loan-operational-parity-pilot.md, ../plans/loans-girvi-consolidation-fit-gap.md, loans-configurable-document-operations.md]
---

# Girvi Capability Extraction And Loans Acceptance Runbook

## Current State

Pilot preparation is complete for tenant `jcl1`. The exact tested runtime
checkpoint is `ab399e2e80abdb3e63afeca31b36cbcf1f52f13b`.
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

Loans is the target platform. Girvi is inspected or exercised only to extract
the mature rule and expected operator outcome. This is not a migration or seed
script. Never copy primary keys, lifecycle rows, accounting evidence, or
custody rows between applications.

## Start Gate

Record these before accepting a scenario:

| Evidence | Required value | Result |
| --- | --- | --- |
| Commit | Exact tested commit | `ab399e2e80abdb3e63afeca31b36cbcf1f52f13b` |
| Worktree | No unreviewed runtime changes | Pass: clean at preflight start |
| Tenant | `jcl1` | Ready |
| Workspace Owner | Named operator | `rajesh` (`rajesh@rajesh.com`) |
| Accounting mode | Explicitly `DEFERRED` or `DEA` | `DEFERRED` |
| Backup identity and restore location | Named disposable-development snapshot | `backup/pre_parity_ab399e2_20260809.dump`; custom archive list validated; SHA-256 `0B0974621C61579C74272494FF843E8D98176D983857D52CDBF83A879E08A950` |
| Document integrity | Zero findings | Pass |
| Printer | Make/model, driver, A4/A5 stock, duplex setting | Pending |

Do not accept accounting behavior unless the accounting mode is recorded. In
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

The capability run starts when scenario P1 begins. The runtime consolidation
and split preflight are complete. Printer metadata is required before accepting
physical-document scenarios.

### Exact-checkpoint preflight record

Checkpoint `ab399e2e80abdb3e63afeca31b36cbcf1f52f13b` passed the following
completed, sequential gates on 2026-08-09:

- clean worktree, Django system check, diff check, and zero migration drift for
  DEA, standalone accounting, Loans, and Girvi;
- 40 standalone-accounting kernel/scenario/posting/projection tests;
- 4 standalone-accounting separate-connection concurrency tests on a freshly
  recreated test database;
- 33 accounting configuration, facade, access, and visual-workflow tests;
- 13 Loans accounting-readiness and outbox tests;
- 30 Loans disbursal, lifecycle, accounting, and correction tests;
- 16 Loans draft/UI tests, including a complete fresh tenant migration replay;
- 58 Girvi service, adapter, payment, transition, and exact-replay tests;
- 6 Girvi PostgreSQL tenant workflow and immutability tests; and
- `jcl1` document integrity with zero findings.

One earlier mixed accounting run passed all assertions but failed during tenant
teardown because old `--keepdb` schemas exhausted PostgreSQL's transaction lock
budget. The concurrency suite was rerun alone on a recreated test database and
passed; only completed reruns above count as preflight evidence.

## Scenario Facts

Use these human-readable facts in Loans. Refer to an equivalent Girvi workflow
only when needed to establish a rule that is not already documented:

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

Record the exact facts in the session notes. Business outcomes matter more than
matching legacy screens or generated numbers.

## Scenario Worksheet

For every row: extract or cite the Girvi rule, classify it, then execute Loans.
Do not use database/admin shortcuts.

| ID | Operator outcome | Required Loans evidence | Decision | Status |
| --- | --- | --- | --- | --- |
| P1 | Set up license, numbering and required business policy | active license/series, next-number clarity, expiry behavior, full effective-dated calculation policy | PORT/REPLACE | **Accepted 2026-08-09 by Owner** |
| P2 | Create and disburse a mixed-metal customer loan | Party, two items, photos, item principal/rates, LTV rejection test, immutable approval/disbursal evidence | REPLACE | **Accepted 2026-08-09 by Owner** |
| P3 | Print and scan physical identity | Original/Duplicate ticket, signatures, item label, QR opens correct loan | PORT | **Active** |
| P4 | Place and transfer collateral | complete Branch/Vault/Cabinet/Box path, item and destination scan, immutable movement/current location | PORT | Pending |
| P5 | Accrue and record repayment | interest calculation, allocation, receipt, event/accounting disposition, Party statement | REPLACE | Pending |
| P6 | Complete full release | complete settlement, all remaining items returned, signatures, Form H/release memo, loan closed | PORT | Pending |
| P7 | Release and renew | old loan closed, selected item returned, retained/additional items on newly numbered loan, renewal agreement | REPLACE | Pending |
| P8 | Handle overdue communication | due/overdue report, notice source, idempotent delivery/retry evidence | PORT | Pending |
| P9 | Verify physical inventory | frozen expectation, found/misplaced observation, blocked transfer/release, reasoned correction, discrepancy notice | PORT | Pending |
| P10 | Correct an operator mistake | later-dependency rejection, reverse chronological compensation, immutable reason and resulting balance/custody | REPLACE | Pending |
| P11 | Produce daily/regulatory outputs | active, daily, interest, overdue, release/renewal, storage, license, Party reports plus required PDFs | PORT | Pending |
| P12 | Test permissions and isolation | ordinary staff denied Owner actions; unknown/cross-workspace source is not exposed | REPLACE | Pending |

For each scenario record:

- start/end time and operator step count;
- first unclear label or next action;
- validation errors and whether the recovery instruction was actionable;
- workaround, administrator intervention, or retry;
- generated document/report identifiers;
- source event, custody, notice, and accounting evidence;
- any unexplained financial or custody difference.

## Acceptance Record

Each scenario is `PASS`, `FAIL`, or `BLOCKED`. A failure must name the smallest
Loans implementation slice and the Girvi rule it preserves. It passes only when
the operator outcome, evidence, permissions, error recovery, and required
physical output are complete.

No acceptance can override a critical failure. Money, custody, tenant
isolation, required documents, backup/restore, or unexplained reconciliation
must be corrected before the scenario passes.

### P1 Acceptance

The workspace Owner accepted P1 on 2026-08-09 after the software gate. This
accepts the license, independent bounded numbering, expiry behavior, and full
effective-dated calculation-policy setup as the operating boundary for the
following scenarios. P1 and P2 are accepted; P3 is the active gate.

### P2 Software Evidence

The P2 implementation gate passed on 2026-08-09. The draft UI presents each
gold/silver tranche's resolved rate, allocated principal, selected value, LTV
maximum, and interest alongside total deductions and net cash. An LTV failure
is attached to the offending allocated-principal input and does not consume a
number. Owner feedback then added the missing numbering context: create shows
the non-consuming next expected number for each selectable series before and
after economics preview, while a saved draft shows its allocated official
number. Mandatory photographs, approval snapshots, and disbursal snapshots
retain the immutable item and policy evidence. The 18-test draft UI suite and
11 focused economics, draft, approval, and disbursal tests pass. Owner
execution of the mixed-metal browser workflow was accepted on 2026-08-09. P2
is complete and P3 physical identity is the active gate.

### P2 Acceptance

The workspace Owner accepted P2 on 2026-08-09 after exercising the mixed-metal
origination and disbursal workflow, including the number-visibility and
deferred-accounting corrections found during the walkthrough. This accepts
Party selection, two-item gold/silver economics, photographs, item LTV
recovery, immutable approval/disbursal evidence, and truthful `PENDING`
accounting disposition in `DEFERRED` mode.

## Physical Document Matrix

Use the detailed matrix in
[Loans configurable document operations](loans-configurable-document-operations.md).
At minimum print the Loans ticket on intended A4 and A5 paths, verify
Original/Duplicate identity and shared verification ID, sign both signature
areas, scan the QR from paper, inspect margins at Actual size/100%, and test the
driver's duplex flip edge. Record printer, driver, stock, scaling, operator and
date. On-screen PDF inspection is not a physical pass.

## Exit

The capability pass is complete only when all Loans scenario evidence is
accepted, the printer matrix is signed, backup/restore is rehearsed, no
critical failure is open, and remaining Girvi capabilities are classified
`PORT`, `REPLACE`, `RETIRE`, or `DEFER`. A separate retirement ADR is still
required before Girvi origination, routes, records, or schema are changed.
