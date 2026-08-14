---
status: active
owner: girvi
updated: 2026-07-06
tags: [girvi, refactor, plan]
related: [README.md, architecture.md, models.md, workflows.md, url-compatibility-matrix.md, ../../plans/active.md, ../../plans/girvi-release-accrual-hardening.md, ../../STATUS.md]
---

# Girvi Refactor Plan

## Current Architecture State

This plan is now a refactor status record plus a narrow follow-up checklist. P0-P5 are complete for the original stabilization scope. P6 remains the local URL/template cleanup track. P7 remains the accepted target direction for event-driven DEA posting, but execution is paused by project decision; the active project-level source of truth is [../../plans/active.md](../../plans/active.md).

Release/accrual hardening is tracked separately in [../../plans/girvi-release-accrual-hardening.md](../../plans/girvi-release-accrual-hardening.md). As of 2026-07-06, R1-R5 are implemented for the planned hardening scope: release ordering, stage outcomes, catch-up failure policy, reconciliation checks, and release settlement snapshots using accrual-row authority with selector compatibility fallback.

## Architecture Problems And Resolution Status

1. Legacy models are now explicit compatibility imports

`models/__init__.py` no longer exports deprecated `Loan` or `LoanPayment`. Explicit historical access goes through `models.legacy`, and guard tests prevent new broad imports from `apps.tenant_apps.girvi.models`.

2. Custody legacy FK migration is complete

`LoanItem.repledged_to` and `RepledgeHistory.taken_loan` were migrated from legacy `"girvi.Loan"` references to `TakenLoan` through a guarded tenant migration. Runtime custody reads use current borrower/lender naming with compatibility fallback, and legacy repledged item mutation routes are blocked.

3. Transition registry canonical cleanup is complete

Runtime execution and primary UI metadata use canonical lifecycle states and transition metadata. Legacy aliases remain only as compatibility input for old URLs/imported values, with matrix tests guarding canonical transition metadata.

4. Accounting side effects are synchronous but behind a Girvi adapter

Runtime posting still uses synchronous DEA facade calls, but current refactored paths go through `apps.tenant_apps.girvi.integrations.dea_adapter` and service helpers. The event/outbox target remains accepted but paused. Outbox scaffolding exists and must not be wired further until the P7 track is explicitly unpaused.

5. High-value view-thinning scope is complete for current MVP paths

The original `loan_detail`, repayment, bulk merge/delete, release, custody, repledge, transition, storage-box, and form-validation targets now delegate to selectors, workflow services, or form-validation services. Future view-thinning should be targeted to newly touched workflows instead of treated as a blanket phase.

6. Model payment helpers are now compatibility wrappers

`GivenLoan.create_payment()`, `GivenLoan.create_disbursal_payment()`, `GivenLoan.create_release_payment()`, and `TakenLoan.create_payment()` remain for compatibility, but now delegate voucher creation to Girvi service helpers behind the DEA adapter.

7. Background tasks contain dead legacy paths

`notify_pending_loans()` and `notify_interest_overdue()` now fail closed with disabled results instead of referencing removed legacy names. Active reminder/accrual behavior should use the current notify_v2 and accrual task paths.

8. Known stale selector field references from this plan are fixed

The stale `selectors.py::get_itemtype_averages()` `loan__loan_type="Given"` filter was removed. Add targeted selector regression tests whenever old report queries are touched.

9. Import/export legacy payment access is explicit

`resources.py` keeps legacy `LoanPayment` import/export for historical data mapping, but it is now named `LegacyLoanPaymentResource`. `LoanPaymentResource` remains only as a compatibility alias for old import/export callers, while active payment runtime uses DEA `PaymentVoucher`.

10. URL namespace has duplicate routes and old naming

There are duplicate names/routes for statements, storage boxes, loan transition, and report aliases. Some URL paths include repeated `girvi/girvi/...` patterns.

This is the main remaining local cleanup area in this plan. The compatibility matrix exists, but alias retirement and HTMX partial cleanup should remain incremental because legacy tenant roots and bookmarked URLs are still intentionally supported.

## Cleaned-Up Architecture Proposal

Target layers:

```text
templates
  -> views
    -> forms for input validation
    -> selectors for reads
    -> use-case services for writes
      -> domain/lifecycle services
      -> accounting event publisher or DEA facade adapter
        -> DEA
```

Models should keep:

- field definitions
- relationships
- simple derived properties
- local invariants that do not require cross-app side effects

Models should not keep:

- DEA voucher creation
- workflow orchestration
- request/user-specific behavior
- multi-step lifecycle commands

Views should keep:

- request parsing
- form binding
- calling selectors/services
- messages and redirects
- choosing full template vs partial template

Views should not keep:

- accounting decisions
- lifecycle mutation logic
- split/merge/release validation rules
- financial computation beyond display formatting

Services should own:

- loan creation
- lifecycle transitions
- release
- renewal
- payment posting use cases
- custody return/repledge
- split/merge
- interest accrual

Selectors should own:

- list querysets
- detail read models
- dashboard/report read models
- cross-app read shape for templates

## Suggested Folder Structure

Keep Django conventions, but split large flat modules:

```text
apps/tenant_apps/girvi/
  models/
    loan_refactored.py
    loan_item.py
    release.py
    accrual.py
    renewal.py
    license.py
    statement.py
    template.py
    legacy.py              # explicit compatibility imports for deprecated Loan/LoanPayment
  domain/
    lifecycle.py           # state vocabularies and pure mapping helpers
    money.py               # interest/amount calculations
    custody.py             # pure custody rules
  selectors/
    loans.py
    dashboard.py
    detail.py
    reports.py
  services/
    loan_creation.py
    loan_transition.py
    release.py
    renewal.py
    repayment.py
    disbursal.py
    accrual.py
    custody.py
    split_merge.py
    printing.py
  integrations/
    dea_adapter.py         # current sync adapter, later event publisher
    notify_adapter.py
  views/
    ...
```

This can be phased. Do not rename everything at once; add new modules as old ones become too large or actively changed.

## Priority Refactor Plan

### P0: Stabilize broken/dead paths

Status: complete for the original stabilization scope.

- Completed 2026-06-20: disabled broken legacy `notify_pending_loans()` and `notify_interest_overdue()` task bodies so scheduled execution fails closed instead of referencing removed `Loan`/`Customer` names.
- Completed 2026-06-20: fixed `get_itemtype_averages()` stale `loan__loan_type` filter.
- Completed 2026-06-20: made interest-accrual command amount output ASCII-safe for Windows console/test runs.
- Completed 2026-06-20: fixed `create_repledge_from_items()` so repledge creation resolves an active TakenLoan series, passes it into `TakenLoan.objects.create()`, and uses the concrete loan model for loan-id sequencing.
- Focused guard tests now cover disabled legacy tasks and current critical cleanup paths.

### P1: Complete TakenLoan/custody migration

Status: complete for the original custody migration scope.

- Completed 2026-06-20: changed `LoanItem.repledged_to` and `RepledgeHistory.taken_loan` from legacy `"girvi.Loan"` references to `TakenLoan` through a guarded migration that verifies existing FK IDs map to `TakenLoan` rows before altering constraints.
- Completed 2026-06-20: replaced active custody helper assumptions around `loan.customer` with borrower-compatible resolution and removed the runtime `models.loan` import from collateral lookup.
- Completed 2026-06-20: `RepledgedLoanItem` remains readable for legacy/import compatibility, but old create/update/delete UI routes now reject mutation and users must manage active collateral through custody/repledge workflows.
- Completed 2026-06-20: added focused tests for repledge creation, bulk return from lender, `TakenLoan.return_all_collateral()`, `TakenLoan.can_close()`, and release blocking/return behavior when collateral is with lenders.
- Completed 2026-06-20: changed direct TakenLoan read properties for amount, weight summary, item description, and current value to read from `RepledgeHistory` instead of `RepledgedLoanItem`.
- Completed 2026-06-20: changed TakenLoan principal queryset reads for selector totals, manager `total_loan_amount()`, interest-base principal, and itemwise amount annotations to use `RepledgeHistory.repledged_amount`.
- Completed 2026-06-20: changed TakenLoan queryset weight and current-value annotations to use `RepledgeHistory.loan_item`.
- Completed 2026-06-20: changed TakenLoan item-interest direct reads, interest-base queryset annotations, and selector totals to derive interest from `RepledgeHistory.repledged_amount` and `LoanItem.interestrate`.
- Completed 2026-06-20: renamed refactored loan interest metric annotations to `calculated_*` names so evaluated querysets do not shadow read-only model properties such as `loan_amount`, `total_interest`, and `total_due`.

### P2: Finish canonical transition cleanup

Status: complete for the original transition cleanup scope.

- Completed 2026-06-20: kept alias maps but removed legacy primary state/UI/form entries from the transition registries; legacy-only metadata now lives in explicit compatibility registries.
- Completed 2026-06-20: added canonical TakenLoan transition state/UI/form metadata for activate and settlement transitions.
- Completed 2026-06-20: active loan detail, transition form, and unified loan list surfaces now render canonical lifecycle labels instead of raw legacy status values.
- Completed 2026-06-21: added flow-derived transition matrix tests that verify every canonical `GivenLoanFlow` and `TakenLoanFlow` transition has registry metadata and matching documented source/target states.

### P3: Move accounting calls behind one Girvi adapter

Status: complete for current synchronous runtime paths.

- Completed 2026-06-21: created `apps.tenant_apps.girvi.integrations.dea_adapter` as the synchronous Girvi-to-DEA boundary, kept `service_modules.posting_adapter` as a compatibility import path, and routed current payment, loan posting, accrual, repayment view, and loan journal read paths through the adapter.
- Completed 2026-06-21: moved model payment helper voucher creation into `service_modules.payment_voucher_creation`; the old model methods remain as compatibility wrappers and direct DEA `PaymentVoucher` creation is isolated behind the adapter.
- Completed 2026-06-21: routed dashboard payment count reads through selectors and the DEA adapter, removing direct runtime `PaymentVoucher` lookups from Girvi dashboard/report view surfaces.
- Deprecated `models/loan.py` remains a legacy compatibility surface; runtime paths should not depend on it.

### P4: Thin views

Status: complete for the identified MVP paths.

- Completed 2026-06-21: moved `loan_detail` display metrics, storage position lookup, interest reporting, and release CTA metadata into the detail read-model selector while keeping existing template context keys stable.
- Completed 2026-06-21: moved GivenLoan/TakenLoan repayment orchestration out of `views.loanpayment` into `service_modules.repayment`, including receipt catch-up accrual, payment payload shaping, posting delegation, and result-message construction.
- Completed 2026-06-21: moved bulk merge/delete selection parsing, guard validation, merge orchestration, delete orchestration, and structured operation errors into `service_modules.bulk_operations`.
- P4 view-thinning cleanup is complete for the identified `loan_detail`, repayment, and bulk merge/delete paths.

### P5: Legacy model containment

Status: complete for the original legacy containment scope.

- Completed 2026-06-21: stopped exporting deprecated `Loan` / `LoanPayment` from `apps.tenant_apps.girvi.models`; legacy access now goes through `models.legacy`, stale commands were moved to `GivenLoan` where appropriate, and `test_legacy_model_containment` guards against new broad legacy imports.
- Completed 2026-06-21: labelled legacy payment import/export as `LegacyLoanPaymentResource`, retained `LoanPaymentResource` as a compatibility alias, corrected the legacy payment loan FK widget to use legacy `Loan`, and labelled legacy/manual Girvi management commands in command help.
- Completed 2026-06-21: set explicit legacy command policy for manual utilities: `do` is runtime-disabled with a clear command error, and `missingcol` is opt-in only via `GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS=1` for controlled import/rehearsal operations, with guardrail tests enforcing this behavior.
- Completed 2026-06-21: architecture tests prevent new runtime imports of legacy `Loan` outside explicit compatibility seams.

P5 exit criteria:

- Met: no runtime Girvi module should import deprecated `Loan` directly outside explicit compatibility surfaces.
- Met: legacy command intent is explicit, tested, and documented.

### P6: URL and template cleanup

Status: active follow-up track in this document.

- Remove duplicate URL names after bookmarked legacy URLs have aged out.
- Normalize path prefixes and names.
- Consolidate repeated HTMX partial names and targets.
- Keep public route aliases only where required.
- Completed 2026-06-21: added `docs/apps/girvi/url-compatibility-matrix.md` with duplicate path/name inventory, canonical-vs-alias mapping, and staged cleanup sequence before route removal.
- Completed 2026-06-21: normalized internal base navigation template reverses from legacy storage-box alias names to canonical `girvi_*` names while retaining alias routes in `urls.py`.
- Completed 2026-07-05: SaaS IA route-canonicalization work made `/w/<workspace_slug>/loans/...` read-only aliases available for loan list/detail/tab/PDF/report surfaces while keeping mutation routes and legacy roots active for compatibility.

#### Next Pass Checklist (P6)

- Refresh `docs/apps/girvi/url-compatibility-matrix.md` against current `urls.py`, `urls/custody_urls.py`, and `/w/<workspace_slug>/loans/...` read-only aliases.
- Normalize remaining duplicated prefixes and naming drift in Girvi routes and corresponding template href/action references under `templates/girvi/`.
- Consolidate repeated HTMX partial endpoints and target ids used by `templates/girvi/loan/_transition_form_inner.html`, `templates/girvi/loan/loan_detail_1.html`, and `templates/girvi/partials/`.
- Add regression tests for route reversals and key UI pages using canonical names.
- Keep mutation routes, POST targets, and success redirects on compatibility paths until each workflow receives its own route-migration slice.

P6 exit criteria:

- Canonical URLs are primary and covered by reverse-resolution tests.
- Remaining aliases are intentional, documented, and time-bounded.
- No duplicate HTMX partial wiring for the same business action.

### P7: Event-driven DEA cutover

Status: paused by project decision. Do not continue async cutover wiring until this track is explicitly unpaused in [../../plans/active.md](../../plans/active.md) or a successor plan.

- Completed 2026-06-21: drafted P7 skeleton artifacts: `GirviPostingOutboxEvent` model and migration, `integrations/outbox.py` enqueue helper, and draft event contract/payload helpers in `integrations/dea_adapter.py` (not yet wired into live posting flows).
- Current runtime behavior: synchronous Girvi-to-DEA posting remains active through the Girvi DEA adapter.
- Retained scaffolding: outbox model, enqueue helper, event contract helpers, operational selector/report visibility, and retry surface for failed/dead-letter outbox rows.
- Deferred behavior: live publisher hooks, DEA consumer implementation, feature-flagged dual posting, parity reconciliation, and synchronous-posting removal.

#### Next Pass Checklist (P7)

Only start this checklist after the paused track is reopened:

- Confirm event contract types and payload schema for disbursal, repayment, release, accrual, auction/sale recovery, renewal, undo, and adjustments.
- Audit the existing outbox model/status fields against retry, dead-letter, replay, and observability requirements before adding more migrations.
- Add publisher hooks in current synchronous posting entry points in shadow mode only.
- Add DEA consumer-side idempotency guards keyed by deterministic source document identifiers.
- Add feature flags for dual-write or dual-post execution with parity logging.
- Add reconciliation command/report to compare sync posting output vs event-consumer output for the same source document set.
- Cut over in stages: shadow mode, tenant-scoped async enablement, then default async with sync fallback off.

P7 exit criteria:

- Event pipeline is idempotent, replay-safe, and observable.
- Posting parity is demonstrated across representative lifecycle scenarios.
- Synchronous posting paths are removed or retained only as controlled rollback paths.
- UI/reporting clearly distinguishes posting pending, posted, failed, and dead-letter states.

## Related Active Follow-Ups

These active tracks are intentionally not duplicated inside this refactor plan:

- Release/accrual hardening: [../../plans/girvi-release-accrual-hardening.md](../../plans/girvi-release-accrual-hardening.md). R1-R5 are implemented for the current planned scope.
- Party rollout: [../../plans/party-rollout.md](../../plans/party-rollout.md). Girvi borrower/lender Party integration should continue through compatibility-safe shadow links and facades.
- Centralized preferences: [../../plans/centralized-preferences-architecture-plan.md](../../plans/centralized-preferences-architecture-plan.md). New preference reads should use the central service/Girvi adapter path, not raw legacy managers.

## Testing Gaps To Close

- P6 URL duplicate cleanup/regression and canonical route reverse tests.
- P7 event/outbox consumer, idempotency, shadow parity, and pending/failed/dead-letter UI tests after the paused track is reopened.
- Release/accrual regression follow-up:
  - tenant-level end-to-end release with real DEA posting and accrual rows
  - selector/accrual variance edge cases beyond focused unit coverage
- End-to-end lifecycle plus accounting posting coverage for:
  - GivenLoan create -> approve -> disburse
  - receipt with catch-up accrual
  - release with custody return
  - renewal with successor disbursal
  - TakenLoan activate -> repayment -> settlement
- Tenant rollout checks should use `migrate_schemas` for tenant app migration validation, especially around Girvi custody, outbox, and Party shadow-link migrations.
