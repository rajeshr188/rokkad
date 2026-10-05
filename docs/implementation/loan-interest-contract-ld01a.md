---
status: complete-local
owner: project
updated: 2026-10-05
tags: [loans, interest, ld-01a, compatibility]
related: [../plans/unified-loan-domain-correction.md, ../adr/2026-10-05-shared-monthly-interest-contract.md]
---

# LD-01A shared monthly interest calculation

## Implemented behavior

Direct, recorded-paper and explicitly reviewed imported contracts use the same
original-date calendar. A 5 April loan with its first month paid upfront remains
covered through 5 May; the next charge starts 6 May. Independent month-end clamps
preserve the original anchor. Later monthly charges use item principal balances
through the preceding covered day. First-period principal remains original, even
after a same-day repayment. Interest is HALF_UP per item per monthly period at the
agreement's captured economic-policy quantum. Principal, cash and fees retain paise.

`domain/monthly_contract.py` supplies the small shared calendar and rounding helpers.
Existing native accrual, paper cumulative collection and opening continuation retain
their evidence shapes and recognition purposes while using the corrected arithmetic
for explicit new versions. Native policy/2 monitoring delegates to its accrual
preview instead of the independent daily segmentation forecast. Active native
simple/full-month flexible/single-payment bullet obligation forecasts also reuse
that calculation with knowledge capped at the reporting date, subtracting advance
coverage once and using the appropriate principal after receipts. Immutable original
schedules retain their allocation capacity. Flexible and periodic-interest bullet
schedules use the same item-rounded monthly amounts.

Native simple/full-month repayment previews include eligible unposted charges.
The existing locked, authorized atomic receipt writer recognizes them before
allocation. Invalid submissions roll back both steps, and retries recognize nothing
twice. Receipt reversal restores allocation while the independently owed native
monthly charge remains recognized. Paper staff item splits remain required where
applicable; native allocation retains its existing ordering.

## Evidence and compatibility

- New itemized approval/disbursal and native renewal successors freeze policy/2.
  Earlier pending approvals missing the version retain policy/1 until reapproval.
- New paper admissions and paper successors use recorded-anniversary/3, with saved
  quantum supplied by standing terms or explicitly reviewed agreement exceptions.
- Reviewed opening/3 binds simple/full-month policy/2 and its quantum to the source
  agreement. Cutover recognized and unpaid baselines remain separate and are
  subtracted once. Existing older preparation adapters still prepare their legacy
  reviewed profile; they do not automatically invent a new policy mapping.
- Native policy/2 complete histories export as loan-history/3 and restore exact
  inclusive fractions, item charges, zero accruals and full-release evidence.
  Published v1/v2 schemas and old readers retain their original interpretation.
  See [the v3 contract](../contracts/loan-history-v3.md).
- Portability migration 0018 extends the existing immutable batch guard. It adds
  no table and converts no financial rows. Its reverse refuses while v3 batches exist.

The reviewed paper contract-correction path can explicitly adopt /3 with an actual
policy quantum, compensate and replay supported dependent financial events while
retaining original events and reviewed item allocations. It does not overwrite
borrower receipts or issued documents. Native/opening cohorts needing broader
frozen-term or cutover-baseline corrections still require their supported reviewed
correction path before rollout; this slice does not automatically convert them.

## Rollout boundary

Run `check_loan_interest_contracts --workspace-id ID` in the appropriate restricted
runtime context to inventory the explicitly selected Workspace. This read-only
command distinguishes shared contracts, review candidates and unsupported evidence,
including servicing events, saved accruals and issued documents. Inspect dependencies
before correction. No production inventory or conversion has been performed here.

Existing direct full release/renewal/auction prerequisites remain; completed native
periods may still require finalization before settlement. Product-specific partial
methods remain genuine agreement choices, not entry-channel choices. Wider common
operation eligibility is LD-02; broader reduced-principal opening admission is LD-04.
Native regular accrual reversal requires reviewed correction before continuation;
retained rows cannot be silently treated as paid interest or reused. Re-recognition
after native coupled settlement reversal still needs dependency/correction integration
where the original monthly row already exists. These are explicit review blockers,
not permission to lose a charge or replace immutable evidence. Broader historical
closed-native and installment/periodic-obligation parity remains LD-06.
Full history/3 retains its bounded supported scope, excluding reversals and renewals.
Do not describe this slice as universal import/admission or production activation.

After new evidence has been written, retain compatible readers when stopping writes;
do not roll back to old binaries that cannot interpret corrected versions.

## Verification

Verification uses disposable `loan-interest-ld01a-qa-20261005` and dedicated
`test_rokkad_ld01a_20261005` under `django_project.settings.test`. Production,
running candidates and their application/media data remain unchanged.

The broad run exercised **1,753 tests in 1,270.230s**: 1,713 passed, with 19
failures and 21 errors. Thirty-five unsuccessful tests came from stale monthly
boundary fixtures, the new snapshot-version assertion and a policy mock missing
its rounding quantum. Correction scenarios now run after the inclusive anniversary
while retaining their original monetary, compensation and custody assertions.
The final affected-module run passes **159 tests in 216.110s**, including all
35 corrected cases, receipt and batch corrections, renewal/closure corrections,
settlement facts, policy/economics, shared-contract checks and history/3. No
application code changed after the broad run; only the six stale test fixtures
and assertions were corrected. The full 1,753-test run was not repeated.

The remaining five unsuccessful tests reproduce independently at unchanged
checkpoint `c1c34d4e` in the separate baseline container/database: four failures
and one error in five tests (1.024s). These concern draft submission references,
opening-page wording, draft-edit wording, receipt date formatting and an access
test's mocked Workspace. Their implementation and assertions are unchanged by
this slice. Do not present the broad suite as wholly green.

Django system checks report no issues (one existing silenced check), migration
drift checks report no changes, scoped Python parsing passes, and scoped
`git diff --check` passes. Portability migration 0018 ran only in the disposable
test database. No application database migration, rollout inventory, conversion
or deployment has been performed.
