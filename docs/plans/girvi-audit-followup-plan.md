# Girvi Audit Follow-Up: Small Phased Implementation Plan

Status: Phases 1-6 complete on 2026-07-15. Phase 7 remains explicitly deferred.

Destructive cleanup follow-up (no production/legacy protection mode) completed
on branch `dea-kiss` on 2026-08-08. Wave 4 remains an optional operator-run
schema reset requiring explicit target approval; runtime cleanup through Wave 5
is complete.

## Summary

Convert the audit into a conservative stabilization track that improves Girvi without reopening broad architecture work. The first slices should reduce operational risk around numbering, settlement, idempotency, and integration tests; larger UI/accounting/event-driven changes stay deferred until the core workflows are safer.

## Key Changes

### Phase 1: Stabilization Guardrails

**Status: Complete.** `test_tenant_workflow_integration.py` now exercises Party bridge and collateral creation, generated numbering, real DEA disbursal/repayment/release posting, repayment split, release catch-up accrual, custody handoff, settlement snapshot, and closure in a tenant schema. Repeated repayment POST and release duplicate-submit behavior are characterized. The integration test exposed and fixed custody-only persistence being blocked by the normal collateral edit guard.

- Add focused tenant-level integration tests for the current happy paths:
  - create GivenLoan with Party bridge and collateral
  - disburse loan and verify DEA posting exists
  - record repayment and verify principal/interest split
  - release loan with accrual catch-up, custody handoff, release snapshot, and DEA receipt
- Add concurrency/idempotency characterization tests for repayment and release double-submit behavior.
- Add no behavior changes except test-only fixes required to make the current contract explicit.

### Phase 2: Sequence Numbering

**Status: Complete.** Sequence migration `0028`, sync dry-run/apply command, non-consuming preview, locked allocation, stale-sequence skipping, manual-ID uniqueness, and Series sequence controls are implemented. `migrate_schemas --tenant --plan --noinput` and `migrate_schemas --tenant --noinput` were clean on 2026-07-15.

- Implement the existing `GirviNumberSequence` plan in small slices:
  - add sequence model and migration
  - add dry-run/apply backfill from existing GivenLoan, TakenLoan, and Release IDs
  - route preview through non-consuming sequence reads
  - route allocation through locked sequence rows
- Keep manual legacy IDs supported with cross-table uniqueness checks.
- Do not renumber existing loans or releases.
- Tenant rollout must use `migrate_schemas`.

### Phase 3: Repayment Idempotency

**Status: Complete.** Browser keys are preserved through POST, blank references receive deterministic service-owned markers, duplicate keys return the existing payment, distinct valid keys create separate payments, and overpayments remain blocked.

- Add a service-owned idempotency key for repayment submissions.
- Use deterministic source-event identity when `reference_number` is blank, so browser double-submit cannot create duplicate receipts.
- Preserve current form fields and DEA posting behavior.
- Add tests for:
  - repeated POST with same idempotency key returns existing payment
  - different keys create separate payments only when business-valid
  - overpayment remains blocked

### Phase 4: Settlement Calculator Cleanup

**Status: Complete.** `release_settlement.py` owns selector quote, paid-interest, accrual-row basis, release snapshot values, and variance classification. Selector/accrual query failures are no longer silently converted to zero-value fallbacks; the legitimate no-posted-accrual case returns explicit selector compatibility metadata.

- Extract one canonical settlement calculation module for:
  - selector quote
  - accrual-row settlement basis
  - paid principal/interest
  - final release snapshot values
  - variance classification
- Keep release preview selector-based, but final release must use the existing snapshot contract.
- Replace broad final-settlement fallbacks with explicit compatibility results that reconciliation can report.
- Do not change the Girvi interest month policy in this phase.

### Phase 5: Reconciliation And Operations Hardening

**Status: Complete.** The reconciliation report covers all planned release, custody, receipt, variance, and repayment anomalies, including an explicit category for releases finalized on selector compatibility basis.

- Expand reconciliation coverage for:
  - closed loan without release
  - release with non-customer custody
  - release receipt mismatch against snapshot
  - accrual-row/selector variance beyond rounding tolerance
  - repayment duplicate/idempotency anomalies
- Surface the new categories in the existing Girvi reconciliation or operations console.
- Keep this read-only except controlled retry/status actions that already exist.

### Phase 6: Legacy Containment

**Status: Complete for the retained compatibility scope.** Disabled tasks, legacy resources, model wrappers, and selector compatibility paths are explicitly named, and architecture guard tests restrict runtime legacy imports. Legacy models remain retained for historical/import reads.

- Move remaining visible legacy surfaces behind explicit compatibility naming:
  - disabled tasks
  - legacy import/export resources
  - model payment wrappers
  - selector fallback paths
- Add guard tests that prevent new runtime code from calling legacy payment/loan paths directly.
- Do not delete legacy models until import/export and historical read needs are confirmed.

### Phase 7: Later, Larger Work

**Status: Deferred by design.** Completion of Phases 1-6 does not automatically authorize the async DEA cutover, auction/sale document design, broad Party conversion, or broad UI redesign.

- Resume event-driven Girvi-to-DEA posting only after Phases 1-5 are green.
- Introduce first-class auction/sale source documents before expanding auction recovery behavior.
- Continue Party-first conversion for release recipient and edit forms after core settlement/payment safety is stable.
- Defer broad UI redesign; only make workflow UI changes needed for confirmation/idempotency and clearer release/repayment review screens.

## Test Plan

- Run focused Girvi tests after each phase:
  - `python manage.py test apps.tenant_apps.girvi.tests.test_id_generation_service -v 2 --keepdb`
  - `python manage.py test apps.tenant_apps.girvi.tests.test_loan_creation_service -v 2 --keepdb`
  - `python manage.py test apps.tenant_apps.girvi.tests.test_repayment_service -v 2 --keepdb`
  - `python manage.py test apps.tenant_apps.girvi.tests.test_release_lifecycle_service -v 2 --keepdb`
  - `python manage.py test apps.tenant_apps.girvi.tests.test_reconciliation_selector -v 2 --keepdb`
- Add at least one tenant-schema integration test file for create -> disburse -> repay -> release.
- For migration phases, verify with `migrate_schemas` rather than plain `migrate`.

Completion verification on 2026-07-15:

- Consolidated stabilization suite: 74 tests passed.
- Tenant-schema integration: real PaymentVoucher, Voucher, and JournalEntry persistence verified for disbursal, repayment, and release.
- `python manage.py makemigrations girvi --check --dry-run`: no changes detected.
- `python manage.py migrate_schemas --tenant --plan --noinput`: no planned operations.
- `python manage.py migrate_schemas --tenant --noinput`: no migrations to apply.

## Assumptions

- Keep current user-facing behavior stable unless a phase explicitly changes it.
- Treat `docs/plans/girvi-number-sequence-migration-plan.md` as the source of truth for numbering implementation.
- Treat current release/accrual R1-R5 work as implemented; this plan hardens it rather than replacing it.
- Do not start async/outbox DEA cutover in this track.

## Destructive Cleanup Follow-Up (dea-kiss)

This section applies only to the explicit destructive cleanup mode accepted for
this branch: no production data protection guarantees and no legacy integration
continuity guarantees.

### Wave 3: Remove Cross-App Coexistence Dependency

Status: Complete on 2026-08-07.

- Girvi create routes no longer import or depend on the Loans feature-gate
  facade.
- `apps.tenant_apps.girvi.views.loan` now keeps create/create-preview behavior
  self-contained under Girvi boundaries.
- Feature-gate test expectations were updated to stop asserting forced Girvi ->
  Loans redirects for creation routes.
- The later completion slice removed the unified portfolio DTOs/selectors,
  comparison command, view/route/template, and coexistence readiness check.

Verification:

- Focused suite: `python manage.py test apps.tenant_apps.loans.tests.test_feature_gate`
- Result: pass.

### Wave 4: Clean Girvi Schema Reset Plan (Destructive)

Status: Optional operator action (runbook ready, not executed).

Goal: reset Girvi tenant tables and migration state for a clean canonical model
surface after compatibility deletion, accepting full local data loss in the
target reset schemas.

Execution guardrails:

- Run only on explicitly approved non-production schemas.
- Take DB backup/dump before any reset step.
- Stop if reset cannot be tenant-scoped.

Proposed sequence:

1. Preflight
  - Verify active git branch and clean migration intent for Girvi.
  - Record target schema list and backup artifact paths.
2. Freeze writes
  - Disable operator access to Girvi mutation routes during reset window.
3. Drop/reset Girvi tenant artifacts
  - Remove Girvi tenant tables in target schemas.
  - Clear tenant migration entries for Girvi app in those schemas only.
4. Rebuild from current canonical migrations
  - Apply tenant migrations with `migrate_schemas --tenant`.
5. Post-reset checks
  - Run focused Girvi test suite.
  - Run smoke checks for loan create/disburse/repay/release paths.
6. Publish reset ledger
  - Record schema list, backup IDs, migration command output summary, and
    validation result in `docs/STATUS.md`.

Required deliverables before execution:

- A concrete command runbook under `docs/implementation/` with copy/paste-safe
  tenant-scoped commands.
- A rollback note that uses backup restore only (no partial table surgery).

Runbook delivered:

- `docs/implementation/girvi-destructive-schema-reset-runbook.md`

### Wave 5: Canonical Naming and Test Suite Cleanup

Status: Complete on 2026-08-08.

Goal: remove transitional naming and leave one clear model/service/test surface
for Girvi runtime behavior.

Proposed sequence:

1. Canonical model module naming
  - Move runtime model definitions from `models/loan_refactored.py` into a
    canonical `models/loan.py` runtime surface.
  - Keep legacy compatibility model classes in an explicitly named archival
    module used only where strictly required.
2. Import surface consolidation
  - Runtime services/selectors/views import from `apps.tenant_apps.girvi.models`
    only.
  - Add/update AST guard tests to block direct transitional module imports.
3. Lifecycle compatibility cleanup
  - Remove residual legacy lifecycle alias/mapping where no longer needed by
    active runtime code paths.
4. Test suite rationalization
  - Keep one focused canonical suite for create, transitions, repayment,
    release, and posting boundaries.
  - Remove duplicate transitional tests that assert legacy import paths.
5. Exit validation
  - Run focused Girvi suite and one tenant integration scenario end-to-end.

Definition of done for Wave 5:

- No runtime imports of `loan_refactored` from Girvi app code.
- No runtime imports of removed compatibility modules.
- Focused canonical suite green.

Progress on 2026-08-07:

- Service modules now import `GivenLoan`, `TakenLoan`, and lifecycle enums from
  the canonical `apps.tenant_apps.girvi.models` package instead of
  `models.loan_refactored`.
- `models/release.py` no longer imports the broad `girvi.services` aggregator at
  module load; `ReleaseIDGenerator` is resolved lazily at release creation.
  This removes the model-package startup cycle that previously prevented
  canonical imports.
- Focused Girvi plus Loans feature-gate suite: 70 tests passed.
- Remaining transitional imports are model-internal/bootstrap paths in
  `flows.py`, `models/__init__.py`, `models/license.py`, and `models/loan.py`.
  The next slice must consolidate the model modules before blocking these
  imports with an AST guard.

Completion on 2026-08-08:

- `models/loan.py` is now the canonical `GivenLoan`/`TakenLoan` model module.
- Deprecated `Loan`/`LoanPayment` runtime models and resources are deleted;
  migration `0029` removes their schema state. Active `LoanChangeLog` lives in
  `models/audit.py`.
- Flows and runtime service modules use the canonical model package. License
  model helpers resolve `GivenLoan` through Django's app registry to avoid
  model-load cycles.
- `test_model_import_boundaries.py` prevents `loan_refactored` from returning
  and rejects any `legacy_loan` runtime import.
- `managers.py` is canonical; `managers_refactored.py` is deleted.
- Legacy lifecycle status and transition alias translation is deleted.
- Notify uses generic `NotificationItem` links instead of the removed direct
  Girvi-loan M2M.
- Girvi/Loans coexistence selectors, comparison command, view/route/template,
  and readiness check are deleted.
- `makemigrations girvi notify loans --check --dry-run` reports no changes.
- Fresh tenant migration replay and the final 64-test affected cross-app suite
  pass. Focused import/lifecycle/registry suites pass. The full
  `apps.tenant_apps.girvi.tests` package is now a tenant-aware release gate:
  database-backed series guardrail tests provision isolated tenant schemas, and
  all 409 tests pass.
