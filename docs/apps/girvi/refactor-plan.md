---
status: active
owner: girvi
updated: 2026-06-21
tags: [girvi, refactor, plan]
related: [README.md, architecture.md, models.md, workflows.md, ../../STATUS.md]
---

# Girvi Refactor Plan

## Current Architecture Problems

1. Legacy models are now explicit compatibility imports

`models/__init__.py` no longer exports deprecated `Loan` or `LoanPayment`. Explicit historical access goes through `models.legacy`, and guard tests prevent new broad imports from `apps.tenant_apps.girvi.models`.

2. Custody still points at legacy `Loan`

`LoanItemWithCustody.repledged_to` and `RepledgeHistory.taken_loan` still reference `"girvi.Loan"`, while user-facing custody screens use `TakenLoan`. Runtime mixin helpers have been updated to avoid legacy `models.loan` imports and to use current borrower naming with compatibility fallback.

3. Transition registry still mixes canonical and legacy UI metadata

Runtime execution is canonical, but `TRANSITION_STATE_REGISTRY`, `TRANSITION_UI_REGISTRY`, and `TRANSITION_FORM_UI_REGISTRY` still contain old keys such as `approve`, `disburse`, `deliver`, and `mark_defaulted`. Alias support is useful; primary UI/state docs should eventually be canonical-only.

4. Accounting side effects are synchronous and split across several places

Disbursal/release/recovery/repayment/accrual posting lives in `payment.py`, `loan_posting.py`, model helper methods, and views. The target direction is DEA/outbox event integration, but current code is synchronous DEA facade calls.

5. Views still contain business decisions

Examples:

- `views/loan.py::loan_detail` computes many financial/collateral values directly.
- `merge_loans` and `deleteLoan` perform business validation in the view.
- `loan_payment_create_view` handles accrual preference decisions and posting orchestration.

6. Model payment helpers are now compatibility wrappers

`GivenLoan.create_payment()`, `GivenLoan.create_disbursal_payment()`, `GivenLoan.create_release_payment()`, and `TakenLoan.create_payment()` remain for compatibility, but now delegate voucher creation to Girvi service helpers behind the DEA adapter.

7. Background tasks contain dead legacy paths

`notify_pending_loans()` and `notify_interest_overdue()` reference undefined `Loan`, `Customer`, and `pending_loans` names. They are likely broken if scheduled.

8. Selectors contain stale field references

`selectors.py::get_itemtype_averages()` filters `loan__loan_type="Given"`, but `GivenLoan` no longer has `loan_type` as a database field.

9. Import/export legacy payment access is explicit

`resources.py` keeps legacy `LoanPayment` import/export for historical data mapping, but it is now named `LegacyLoanPaymentResource`. `LoanPaymentResource` remains only as a compatibility alias for old import/export callers, while active payment runtime uses DEA `PaymentVoucher`.

10. URL namespace has duplicate routes and old naming

There are duplicate names/routes for statements, storage boxes, loan transition, and report aliases. Some URL paths include repeated `girvi/girvi/...` patterns.

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

- Completed 2026-06-20: disabled broken legacy `notify_pending_loans()` and `notify_interest_overdue()` task bodies so scheduled execution fails closed instead of referencing removed `Loan`/`Customer` names.
- Completed 2026-06-20: fixed `get_itemtype_averages()` stale `loan__loan_type` filter.
- Completed 2026-06-20: made interest-accrual command amount output ASCII-safe for Windows console/test runs.
- Completed 2026-06-20: fixed `create_repledge_from_items()` so repledge creation resolves an active TakenLoan series, passes it into `TakenLoan.objects.create()`, and uses the concrete loan model for loan-id sequencing.
- Add focused tests for any remaining broken paths or mark tasks unscheduled until fixed.

### P1: Complete TakenLoan/custody migration

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

- Completed 2026-06-20: kept alias maps but removed legacy primary state/UI/form entries from the transition registries; legacy-only metadata now lives in explicit compatibility registries.
- Completed 2026-06-20: added canonical TakenLoan transition state/UI/form metadata for activate and settlement transitions.
- Completed 2026-06-20: active loan detail, transition form, and unified loan list surfaces now render canonical lifecycle labels instead of raw legacy status values.
- Completed 2026-06-21: added flow-derived transition matrix tests that verify every canonical `GivenLoanFlow` and `TakenLoanFlow` transition has registry metadata and matching documented source/target states.

### P3: Move accounting calls behind one Girvi adapter

- Completed 2026-06-21: created `apps.tenant_apps.girvi.integrations.dea_adapter` as the synchronous Girvi-to-DEA boundary, kept `service_modules.posting_adapter` as a compatibility import path, and routed current payment, loan posting, accrual, repayment view, and loan journal read paths through the adapter.
- Completed 2026-06-21: moved model payment helper voucher creation into `service_modules.payment_voucher_creation`; the old model methods remain as compatibility wrappers and direct DEA `PaymentVoucher` creation is isolated behind the adapter.
- Completed 2026-06-21: routed dashboard payment count reads through selectors and the DEA adapter, removing direct runtime `PaymentVoucher` lookups from Girvi dashboard/report view surfaces.
- Legacy `models/loan.py` still imports DEA directly and is intentionally deferred to P5 legacy model containment.

### P4: Thin views

- Completed 2026-06-21: moved `loan_detail` display metrics, storage position lookup, interest reporting, and release CTA metadata into the detail read-model selector while keeping existing template context keys stable.
- Completed 2026-06-21: moved GivenLoan/TakenLoan repayment orchestration out of `views.loanpayment` into `service_modules.repayment`, including receipt catch-up accrual, payment payload shaping, posting delegation, and result-message construction.
- Completed 2026-06-21: moved bulk merge/delete selection parsing, guard validation, merge orchestration, delete orchestration, and structured operation errors into `service_modules.bulk_operations`.
- P4 view-thinning cleanup is complete for the identified `loan_detail`, repayment, and bulk merge/delete paths.

### P5: Legacy model containment

- Completed 2026-06-21: stopped exporting deprecated `Loan` / `LoanPayment` from `apps.tenant_apps.girvi.models`; legacy access now goes through `models.legacy`, stale commands were moved to `GivenLoan` where appropriate, and `test_legacy_model_containment` guards against new broad legacy imports.
- Completed 2026-06-21: labelled legacy payment import/export as `LegacyLoanPaymentResource`, retained `LoanPaymentResource` as a compatibility alias, corrected the legacy payment loan FK widget to use legacy `Loan`, and labelled legacy/manual Girvi management commands in command help.
- Completed 2026-06-21: set explicit legacy command policy for manual utilities: `do` is runtime-disabled with a clear command error, and `missingcol` is opt-in only via `GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS=1` for controlled import/rehearsal operations, with guardrail tests enforcing this behavior.
- Add architecture tests to prevent new runtime imports of legacy `Loan`.

#### Next Pass Checklist (P5)

- Decide command policy for manual legacy commands in apps/tenant_apps/girvi/management/commands/do.py and apps/tenant_apps/girvi/management/commands/missingcol.py (archive, disable with explicit failure message, or retain as import-rehearsal only).
- Implement the chosen policy in command classes and help text.
- Add or update guard tests in apps/tenant_apps/girvi/tests/test_cleanup_guardrails.py and apps/tenant_apps/girvi/tests/test_legacy_model_containment.py so runtime paths cannot regress to broad legacy imports.
- Run focused tests for containment and command behavior.

P5 exit criteria:

- No runtime Girvi module imports deprecated Loan directly outside explicit legacy compatibility surfaces.
- Legacy command intent is explicit, tested, and documented.

### P6: URL and template cleanup

- Remove duplicate URL names after bookmarked legacy URLs have aged out.
- Normalize path prefixes and names.
- Consolidate repeated HTMX partial names and targets.
- Keep public route aliases only where required.
- Completed 2026-06-21: added `docs/apps/girvi/url-compatibility-matrix.md` with duplicate path/name inventory, canonical-vs-alias mapping, and staged cleanup sequence before route removal.
- Completed 2026-06-21: normalized internal base navigation template reverses from legacy storage-box alias names to canonical `girvi_*` names while retaining alias routes in `urls.py`.

#### Next Pass Checklist (P6)

- Inventory duplicate route names and aliases in apps/tenant_apps/girvi/urls.py and any included view route modules.
- Build a route compatibility matrix with canonical route name/path, temporary alias route, and removal target date or condition.
- Normalize duplicated prefixes and naming drift in Girvi routes and corresponding template href/action references under templates/girvi/.
- Consolidate repeated HTMX partial endpoints and target ids used by templates/girvi/loan/_transition_form_inner.html, templates/girvi/loan/loan_detail_1.html, and templates/girvi/partials/.
- Add regression tests for route reversals and key UI pages using canonical names.

P6 exit criteria:

- Canonical URLs are primary and covered by reverse-resolution tests.
- Remaining aliases are intentional, documented, and time-bounded.
- No duplicate HTMX partial wiring for the same business action.

### P7: Event-driven DEA cutover

- Status 2026-06-21: paused by project decision; do not continue async cutover wiring until unpaused.

- Implement outbox event publishing for disbursal, repayment, release, accrual, auction/sale recovery.
- Add DEA consumer idempotency and reconciliation checks.
- Run sync and async in parallel behind feature flags.
- Remove synchronous posting once parity is proven.
- Completed 2026-06-21: drafted P7 skeleton artifacts: `GirviPostingOutboxEvent` model and migration, `integrations/outbox.py` enqueue helper, and draft event contract/payload helpers in `integrations/dea_adapter.py` (not yet wired into live posting flows).

#### Next Pass Checklist (P7)

- Define event contract types and payload schema for Girvi posting events in apps/tenant_apps/girvi/integrations/dea_adapter.py and a new outbox module under apps/tenant_apps/girvi/integrations/.
- Add outbox persistence model and migration in Girvi tenant app with status fields required for retry, dead-letter handling, and replay safety.
- Add publisher hooks in current synchronous posting entry points: disbursal, repayment, release, accrual, and auction/sale recovery.
- Add DEA consumer-side idempotency guards keyed by deterministic source document identifiers.
- Add feature flags for dual-write or dual-post execution (sync plus async shadow mode), with parity logging.
- Add reconciliation command/report to compare sync posting output vs event-consumer output for the same source document set.
- Cut over in stages: shadow mode, tenant-scoped async enablement, then default async with sync fallback off.

P7 exit criteria:

- Event pipeline is idempotent, replay-safe, and observable.
- Posting parity is demonstrated across representative lifecycle scenarios.
- Synchronous posting paths are removed or retained only as controlled rollback paths.

## Testing Gaps To Close

- Broken Celery notification tasks.
- Transition alias coverage for canonical lifecycle cleanup.
- Selector/report stale field references.
- Import/export resources after `LoanPayment` archive migration.
- Legacy/manual command lifecycle policy is now explicit and documented: `do` remains disabled, `missingcol` remains opt-in for controlled import/rehearsal only, and guardrails prevent runtime coupling to these manual legacy commands.
- URL duplicate cleanup/regression.
- End-to-end lifecycle plus accounting posting for:
  - GivenLoan create -> approve -> disburse
  - receipt with catch-up accrual
  - release with custody return
  - renewal with successor disbursal
  - TakenLoan activate -> repayment -> settlement
