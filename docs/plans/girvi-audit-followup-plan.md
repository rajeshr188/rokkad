# Girvi Audit Follow-Up: Small Phased Implementation Plan

Status: Phases 1-6 complete on 2026-07-15. Phase 7 remains explicitly deferred.

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
