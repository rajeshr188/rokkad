---
status: active
owner: project
updated: 2026-07-06
tags: [plans, active, girvi, release, accrual]
related: [../adr/2026-06-27-girvi-release-accrual-lifecycle-boundary.md, ../STATUS.md, ../implementation/girvi-services.md]
---

# Girvi Release And Accrual Hardening Plan

This plan implements the accepted ADR for release and accrual boundaries in small, verifiable slices.

## Goal

Deliver a release workflow that is fail-safe, stage-explicit, and reconcilable while preserving accrual as a separate business event that can be invoked as a release prerequisite.

## Scope

- Release orchestration, readiness checks, lifecycle transitions, posting handoff.
- Accrual catch-up behavior when triggered by release.
- Reconciliation checks for release-custody-accounting integrity.

Out of scope:

- Full async outbox cutover for release posting.
- Broad UI redesign.

## Execution Order

1. Slice R1: Preserve and lock the release ordering invariant.
2. Slice R2: Introduce explicit release stage outcomes.
3. Slice R3: Add configurable accrual failure policy for release.
4. Slice R4: Add release integrity reconciliation checks.
5. Slice R5: Implement authoritative release-time interest basis.

## Slice R1: Ordering Invariant

Objective:

Keep release behavior atomic and preserve custody transfer before release persistence.

Tasks:

1. Keep release orchestration as the only write path for release completion.
2. Guard against regressions that persist release before custody transfer.
3. Ensure item-level idempotent handling for already-with-customer cases remains safe.

Acceptance criteria:

1. In-vault collateral release succeeds when settlement and readiness are clear.
2. Any custody failure aborts release and no closure/posting side effect is committed.
3. Existing custody-before-release ordering regression test remains green.

Test gate:

1. manage.py test apps.tenant_apps.girvi.tests.test_release_lifecycle_service -v 2 --keepdb

## Slice R2: Explicit Release Stage Outcomes

Objective:

Return deterministic stage-level outcomes from release orchestration for observability and supportability.

Tasks:

1. Extend release execution result with stage status fields:
   - readiness_checked
   - accrual_catchup
   - custody_transferred
   - release_saved
   - closure_completed
   - posting_completed
2. Emit stage-aware warnings/errors instead of generic message aggregation.
3. Keep view behavior thin while surfacing stage-level diagnostics to operators.

Acceptance criteria:

1. A failed release identifies the first failed stage and reason.
2. A successful release shows all stages completed in order.
3. Existing success/error UI semantics remain backward compatible.

Test gate:

1. New stage-aware unit tests in release lifecycle test module.
2. Existing release workflow and create-view integration tests green.

## Slice R3: Configurable Catch-up Failure Policy

Objective:

Control whether release should fail closed when release-triggered accrual catch-up fails.

Tasks:

1. Add preference key Loan__Release_Fail_Closed_On_Accrual_Error.
2. Implement behavior:
   - false: warning-only (current compatibility mode)
   - true: fail release before custody/release persistence
3. Keep Loan__Catchup_On_Release as the trigger switch for catch-up execution.

Acceptance criteria:

1. Catch-up disabled: release path does not attempt accrual.
2. Catch-up enabled + fail-closed disabled: accrual failure warns and continues.
3. Catch-up enabled + fail-closed enabled: accrual failure blocks release.

Test gate:

1. Preference-driven release lifecycle tests for both policy modes.
2. Focused command-level checks for accrual-triggered release path.

## Slice R4: Reconciliation Checks

Objective:

Introduce operational checks for release integrity across lifecycle, custody, and accounting.

Tasks:

1. Add selector/service checks for mismatches:
   - closed loan without release row
   - release row with non-customer custody remaining
   - positive release-time outstanding without posted release receipt
2. Expose checks in an operations report/console surface.
3. Add targeted tests and fixture scenarios for each mismatch type.

Acceptance criteria:

1. Mismatch categories are deterministic and queryable.
2. Clean paths produce zero false positives in focused test fixtures.
3. Operations users can identify and triage each mismatch type.

Test gate:

1. Selector/service tests for mismatch classification.
2. Route/report tests if a UI/report surface is added.

## Slice R5: Authoritative Interest Basis Implementation

Objective:

Move final release-time settlement interest to an accrual-row authoritative basis while keeping selector-computed interest available for preview and compatibility fallback.

Accepted decision:

1. Repayment and release previews may continue to show selector-computed interest from `loan_interest_due()` as the operational quote.
2. Before final release, release execution must run catch-up accrual through `release_date` when catch-up is enabled.
3. Final release settlement interest should then be derived from eligible `LoanInterestAccrual` rows through the release date, minus interest already paid.
4. The final release document or equivalent source record must snapshot the settled interest amount so future policy/rate changes do not rewrite historical settlement.
5. Implementation uses R4 reconciliation checks so the cutover can detect under-accrual, over-accrual, missing posting, and selector-vs-accrual variance.

Tasks:

1. Add a release settlement basis helper that can calculate:
   - selector quote
   - accrual-row gross recognized interest through release date
   - paid interest
   - final accrual-row interest due
   - variance between selector quote and accrual-row due
2. Ensure release catch-up creates all missing accrual periods through `release_date` before the final settlement amount is calculated.
3. Define eligible rows for release settlement:
   - rows for the same `GivenLoan`
   - `period_end <= release_date`
   - status allowed by policy, initially `POSTED` plus same-transaction rows when posting is required and succeeds
4. Add a compatibility path for tenants where accrual posting is disabled:
   - release can use newly created draft accrual rows only when the release policy explicitly allows non-posted accrual settlement
   - otherwise release should fail closed or warn according to the existing accrual failure policy
5. Snapshot final release interest/principal/total settlement values on the release source record or an explicit settlement snapshot model.
6. Update release preview UI/read model to show both the current quote and any accrual catch-up periods that will be created before completion.
7. Add reconciliation checks for:
   - selector quote differs from accrual-row settlement beyond rounding tolerance
   - release completed without accrual rows through release date
   - posted release receipt interest does not match the release settlement snapshot
8. Keep repayment settlement on selector-computed preview until a separate repayment accrual-authority decision is made.

Acceptance criteria:

1. Existing release preview behavior remains stable before final submission.
2. Final release settlement uses accrual-row due after catch-up when the cutover flag/policy is enabled.
3. Historical releases retain their original settlement numbers through persisted snapshots.
4. Reconciliation can classify selector-vs-accrual variances without blocking read-only reporting.
5. Existing loans without complete accrual history have a documented backfill or compatibility path.

Test gate:

1. Release lifecycle tests for accrual-row final settlement.
2. Reconciliation tests for missing accrual rows, selector/accrual variance, and release receipt mismatch.
3. Backfill/compatibility tests for existing loans with partial accrual history.
4. Existing release, repayment, and accrual service tests remain green.

## Risks

1. Policy flip to fail-closed can block current operational release flows if accrual configuration is incomplete.
2. Stage-level result refactor can break UI expectations if not backward compatible.
3. Reconciliation checks can create noisy alerts without precise mismatch classification.

## Rollback Conditions

1. Release throughput degrades due to accrual checks and blocks critical operations.
2. Stage refactor creates regressions in release completion or messaging paths.
3. Reconciliation checks produce unacceptable false-positive rates.

## Ownership

- Girvi Team: release and accrual orchestration logic.
- DEA Team: posting semantics and receipt/accrual posting boundary checks.
- Platform/Orgs: preference definitions and defaults.

## Progress Checklist

- [x] R1 ordering invariant established and covered by regression test.
- [x] R2 stage outcome model implemented.
- [x] R3 catch-up fail policy preference implemented.
- [x] R4 reconciliation checks implemented in the existing loan accounting reconciliation report.
- [x] R5 authoritative interest basis decision accepted: final release settlement should become accrual-row authoritative after catch-up/reconciliation safeguards.
- [x] R5 authoritative interest basis implemented with release settlement snapshots, accrual-row basis when posted accrual rows exist, and selector compatibility fallback.
