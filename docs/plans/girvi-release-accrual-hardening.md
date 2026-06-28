---
status: active
owner: project
updated: 2026-06-27
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
5. Slice R5: Decide authoritative release-time interest basis.

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

## Slice R5: Authoritative Interest Basis Decision

Objective:

Finalize whether release-time settlement interest remains selector-computed or becomes accrual-row authoritative.

Tasks:

1. Produce an evidence note comparing both approaches on current data flows.
2. Decide and document in follow-up ADR or ADR amendment.
3. Implement only after decision acceptance with migration/test plan.

Acceptance criteria:

1. Decision artifact accepted.
2. Clear compatibility approach for existing loans and reports.

Test gate:

1. Decision-level architecture review complete.
2. No implementation starts before decision acceptance.

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
- [ ] R4 reconciliation checks implemented.
- [ ] R5 authoritative interest basis decision accepted.
