---
status: accepted
owner: project
updated: 2026-07-06
tags: [adr, girvi, dea, lifecycle, accrual]
related: [girvi-flow-boundaries-with-dea.md, 2026-06-24-dea-document-voucher-journal-lifecycle.md, ../implementation/girvi-services.md]
---

# ADR: Girvi Release And Interest Accrual Lifecycle Boundary

Date: 2026-06-27
Status: Accepted
Owners: Girvi Team, DEA Team, Platform Architecture
Tags: girvi, dea, lifecycle, accrual, custody, accounting
Supersedes: -
Superseded by: -

## Summary

Girvi GivenLoan release should remain a single business use case that atomically coordinates settlement eligibility, collateral custody handoff, release document creation, lifecycle closure, and final release receipt posting. Interest accrual remains a separate periodic business event with its own persisted records and DEA posting path, but release may invoke a catch-up accrual step before completion. The boundary is clarified as: custody change is part of release completion, accrual is not part of release state itself, and release must not silently complete when required accrual integrity or custody integrity fails.

## Context / Problem Statement

The current Girvi release flow already combines several concerns:

1. Settlement readiness is checked from the canonical settlement selector.
2. Collateral custody must move from vault or lender-related operational custody into customer custody.
3. A Release document is created.
4. The GivenLoan lifecycle advances through request_closure and complete_closure in the V2 flow.
5. DEA release receipt posting may occur for the final settlement receipt.

Interest accrual interacts with release because the system can optionally run a catch-up accrual before release using Loan__Catchup_On_Release preferences. That introduces an architectural question: should accrual be considered part of the release lifecycle, and should collateral custody be treated as an independent workflow or as a release side effect?

Recent defects showed two boundary problems:

1. Release-state checks were too easy to confuse with transient in-memory state.
2. Persisting the Release row before custody handoff made an in-vault item appear non-releasable during the same transaction.

The system needs a clearer contract so release, accrual, and posting remain consistent without spreading state changes across disconnected manual flows.

## Decision

Girvi GivenLoan release is defined as a compound business workflow with one authoritative orchestration service.

1. Collateral custody change is part of the loan-release lifecycle.
2. Interest accrual is a separate business event, not a release-state transition.
3. Release may invoke accrual catch-up before completion, but only as a pre-release accounting preparation step.
4. Release completion must fail closed when required custody or required accrual preconditions fail.
5. DEA posting remains downstream of successful release orchestration, not the driver of custody or operational state.

## Decision Details

1. Scope:
   - apps.tenant_apps.girvi.service_modules.release_lifecycle
   - apps.tenant_apps.girvi.service_modules.accrual
   - apps.tenant_apps.girvi.service_modules.custody
   - apps.tenant_apps.girvi.flows
   - apps.tenant_apps.girvi.selectors
   - apps.tenant_apps.girvi.integrations.dea_adapter

2. Boundaries:
   - Release orchestration owns custody handoff, release document creation, lifecycle closure, and final release receipt invocation.
   - Accrual orchestration owns monthly period calculation, accrual row persistence, and optional DEA accrual posting.
   - The release workflow may call accrual as a prerequisite step, but accrual does not own release state.
   - Views and forms must remain thin coordinators and must not update custody or lifecycle state directly.

3. Data and contracts:
   - Release remains the persisted source document for release completion.
   - LoanInterestAccrual remains the persisted source document for periodic interest accrual.
   - Settlement preview may continue to use the canonical settlement selector for an immediate operational quote.
   - Final release settlement should move to an accrual-row authoritative basis after catch-up accrual and reconciliation checks guarantee the required rows exist through the release date.
   - Release and accrual posting continue through DEA adapters and posting services with idempotent markers.

4. Operational model:
   - Release is synchronous and atomic within one transaction for operational state and custody mutation.
   - Accrual is a separate synchronous command today, optionally invoked by release as catch-up.
   - Future async or outbox-based posting may be added later, but the ownership boundaries above remain unchanged.

## Rationale

1. Custody change is not optional decoration around release. A released loan with collateral still in vault or with lender custody is operationally inconsistent.
2. Accrual and release are related but not identical. Accrual expresses earned interest over time; release expresses final closure and collateral handoff.
3. Keeping release as the orchestration owner avoids split-brain behavior where one screen changes the document, another changes custody, and a third posts accounting.
4. Keeping accrual as its own event preserves a clean accounting and reporting trail for monthly recognition instead of hiding it inside release.
5. Treating catch-up accrual as a pre-release step reflects the business need without collapsing the concepts into one state machine.

## Consequences

### Positive

1. Release has one clear source of orchestration truth.
2. Custody and operational state remain aligned at the end of release.
3. Interest accrual keeps its own auditable record set and accounting trail.
4. Future reconciliation can test explicit invariants across release, custody, and posting.

### Negative / Costs

1. The release service remains a high-value orchestration surface and needs stronger tests than a simple CRUD flow.
2. The current settlement selector and accrual rows still represent partially overlapping truth for interest economics.
3. Failure policy for catch-up accrual must become explicit and may break permissive user flows that currently continue with warnings.

## Rollout / Migration Plan

1. Slice 1 (immediate): keep release orchestration as the single release writer and preserve custody-before-release persistence ordering.
   - Exit criteria: release path updates custody, persists release, completes closure, and posts receipt without ordering regressions.
2. Slice 2: introduce explicit release-stage result semantics in `ReleaseLifecycleService`.
   - Stages: readiness_checked, accrual_catchup, custody_transferred, release_saved, closure_completed, posting_completed.
   - Exit criteria: errors and warnings are emitted with stage ownership.
3. Slice 3: implement configurable catch-up accrual failure policy for release.
   - Add `Loan__Release_Fail_Closed_On_Accrual_Error` preference.
   - Default recommendation: fail-closed enabled for new tenants.
   - Exit criteria: warning-only and fail-closed paths both covered by tests.
4. Slice 4: add release integrity reconciliation checks and reporting.
   - Assertions: closed loan has release row, release row has all items with customer, positive outstanding at release has posted release receipt unless explicitly waived.
   - Exit criteria: report route or selector output used by operations console and covered by tests.
5. Slice 5: implement authoritative release-time interest basis.
   - Accepted target: final release settlement uses accrual rows after release-date catch-up, not raw runtime selector recomputation.
   - Preview rule: repayment and release screens may continue to display selector-computed interest before final submission.
   - Finalization rule: release execution runs catch-up accrual through `release_date`, then calculates final release interest from eligible accrual rows minus interest already paid.
   - Exit criteria: final release amount is snapshotted on the release document or equivalent source record, reconciliation can compare selector quote versus accrual-row settlement, and compatibility tests cover existing loans.

Rollback criteria:
- Roll back this direction if release completion regularly requires operational pauses between custody handoff and closure that cannot be represented safely inside one orchestrated use case.
- Roll back this direction if accrual posting latency or availability makes synchronous catch-up on release operationally unacceptable.

## Guardrails and Observability

1. Feature flags:
   - Loan__Catchup_On_Release
   - future Loan__Release_Fail_Closed_On_Accrual_Error

2. Metrics:
   - release attempts
   - release failures by stage: readiness, accrual, custody, lifecycle, posting
   - loans in ClosurePending without release rows beyond an expected time threshold
   - closed loans with any non-customer collateral custody remaining

3. Alerts:
   - release succeeded but receipt posting missing when outstanding amount was positive
   - release row exists but any loan item remains in vault or with lender
   - accrual catch-up failures during release above threshold

## Test Strategy

1. Unit:
   - release-state detection must ignore stale in-memory reverse release state
   - release custody mutation must occur before release persistence
   - accrual preview must cap effective end date at release date
   - settlement selector must remain stable for principal, interest, and overpayment splits
   - accrual-row release settlement must equal posted/draft eligible accruals through release date minus interest already paid after catch-up

2. Integration:
   - settled loan with in-vault items releases successfully end to end
   - loan with lender-held items blocks release until returned
   - loan with positive outstanding amount creates release receipt posting after release completion
   - release with catch-up accrual enabled posts accrual rows before final receipt posting

3. Reconciliation/regression:
   - closed loan without release row is a mismatch
   - release row with non-customer custody is a mismatch
   - positive settlement at release without posted release receipt is a mismatch unless explicitly waived

## Alternatives Considered

1. Move custody entirely outside release into a separate manual workflow.
   - Rejected because release would no longer guarantee physical handoff integrity.

2. Make interest accrual fully implicit inside release with no separate accrual records.
   - Rejected because monthly interest recognition would lose its own auditable business event and accounting trail.

3. Make DEA posting drive release state and custody transitions.
   - Rejected because accounting posting is downstream from operational release, not the owner of physical collateral state.

4. Keep current permissive warning-only accrual behavior permanently.
   - Rejected because it allows closure to complete while financial preparation is incomplete.

## Open Questions

1. Should catch-up accrual failure be fail-closed by default for all tenants or controlled by preference?
2. Should release preview show the exact accrual periods that will be backfilled before completion?
3. Should ClosurePending remain a short-lived technical waypoint or become a true operational hold state with explicit user actions?

Resolved on 2026-07-06:

1. Release-time settlement interest should eventually become accrual-row authoritative. Runtime selector interest remains the preview and fallback quote until catch-up, reconciliation, and compatibility tests are complete.

## Review Trigger

Revisit when:
1. Girvi release moves to asynchronous or outbox-driven posting.
2. Monthly accrual-row settlement implementation materially changes the release data model or accounting posting contract.
3. Operational users need a multi-step physical handoff workflow that cannot be modeled safely inside one release orchestrator.
