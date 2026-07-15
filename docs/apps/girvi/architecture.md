---
status: active
owner: girvi
updated: 2026-07-05
tags: [girvi, architecture, django]
related: [README.md, models.md, workflows.md, userflows.md, refactor-plan.md, ../../adr/girvi-flow-boundaries-with-dea.md]
---

# Girvi Architecture

## Responsibility

Girvi owns pawn-loan operations inside each tenant schema. It is responsible for operational loan state, collateral records, custody, releases, renewals, repledges, payments initiated from loan screens, interest accruals, physical verification statements, license/series controls, print documents, notices, and loan reporting.

Girvi does not own general ledger accounting. Current code posts accounting effects synchronously through `apps.tenant_apps.dea.facade`, mainly from `apps/tenant_apps/girvi/service_modules/payment.py`, `loan_posting.py`, and `accrual.py`. The accepted direction in `docs/adr/2026-05-03-girvi-businessdoc-decoupling.md` is to move toward event/outbox integration.

## Layer Map

Models:

- `models/loan_refactored.py`: active `BaseLoan`, `GivenLoan`, `TakenLoan`, lifecycle enums, calculation helpers.
- `models/loan_item.py`: collateral items, repledged item compatibility, item pictures, storage boxes.
- `models/release.py`: release document for `GivenLoan`.
- `models/accrual.py`: persistent monthly accrual rows.
- `models/renewal.py`: renewal audit relationship.
- `models/license.py`: license, license documents, and series/guardrails.
- `models/statement.py`: stock/collateral verification sessions.
- `models/template.py`: loan-ticket template and frame configuration.
- `models/loan.py`: deprecated legacy `Loan`, `LoanPayment`, and `LoanChangeLog`.

Request/UI layer:

- `urls.py` is grouped by feature: core utilities, archives, license, loan, item, payment, series, template, release, custody, statement, storage boxes.
- `views/loan.py` handles loan list/detail/create/update/delete, transition form endpoint, split/merge, renewal, and lazy detail tabs.
- `views/release.py` handles release list/create/detail/update/delete and bulk release.
- `views/loanpayment.py` records given/taken loan repayments.
- `views/custody_views.py` handles custody checks, repledge creation, return from lender, and taken-loan collateral screens.
- `views/template.py`, `views/license.py`, `views/series.py`, `views/statement.py`, `views/storagebox.py`, `views/prints.py`, and `views/reports.py` cover supporting workflows.

Forms and presentation:

- `forms.py` contains most ModelForms and workflow forms, including `LoanForm`, initial item formsets, `ReleaseForm`, transition forms, repayment forms, statement/storage forms, and print/template forms.
- `templates/girvi/` contains page and partial templates. The app uses `django-template-partials` style fragments such as `loan_list.html#loan-table`, `loan_detail_1.html#items-tab`, and `release_form.html#release-form-content`.
- `tables.py` defines `django-tables2` tables for given loans, taken loans, unified lists, loan items, and releases.
- `filters.py` defines django-filter filters for given/taken loans, loan items, and releases.

Domain/application services:

- `services.py` is a public aggregation module that re-exports use-case services and still contains calculation helpers.
- `service_modules/creation.py`: command-style `LoanCreationService`.
- `service_modules/transitions.py`: `LoanTransitionService` orchestration.
- `service_modules/payment.py`: loan disbursal/release/reversal accounting facade calls.
- `service_modules/loan_posting.py`: repayment/release/auction/sale posting orchestration.
- `service_modules/accrual.py`: interest-accrual preview/execution and DEA posting.
- `service_modules/preferences.py`: Girvi runtime preference adapter over central `PreferenceService`, preserving legacy `Loan__...` and `Interest_Rate__...` storage while avoiding direct runtime `CompanyPreferences` imports.
- `service_modules/release_lifecycle.py`: release creation, catch-up accrual, status movement, custody update, accounting receipt.
- `service_modules/renewal.py`: source-loan renewal, successor-loan creation, catch-up accrual, disbursal posting.
- `service_modules/custody.py`: custody read models and commands.
- `service_modules/split_merge.py`: item split and loan merge.
- `service_modules/printing.py`: loan-ticket template readiness and rendering orchestration.

Lifecycle:

- `flows.py` is the runtime state machine layer. `GivenLoanFlow` uses `LoanLifecycleState`; `TakenLoanFlow` uses `TakenLoanLifecycleState`. Legacy status values are normalized before runtime decisions.
- `transition_registry.py` maps transition keys to forms, payload DTOs, command classes, UI metadata, and state descriptions.
- `transitions/payloads.py` contains dataclass DTOs for transition form payloads.
- `transitions/commands.py` executes transition methods and handles side effects such as disbursal posting, auction recovery posting, and reversals.

Read boundary:

- `selectors.py` is the main read/query layer for loan lists, unified loan rows, totals, analytics, and detail read models.
- `facade.py` is the cross-app interface. Other apps should prefer it over importing Girvi models directly.

Background and signals:

- `tasks.py` contains Celery tasks for exports, reminders, and scheduled interest accrual.
- `signals.py` updates legacy aggregate values when items change and applies series guardrails after loan create/delete.

## Current Dependency Direction

Ideal direction:

`views -> forms/selectors/services -> models -> DEA facade for accounting effects`

Girvi runtime preference reads should go through `service_modules/preferences.py`, not through `apps.orgs.preferences.CompanyPreferences` directly.

Current reality:

- Views sometimes still compute business decisions directly, especially around loan detail metrics, merge/delete guards, and payment setup.
- Models still contain payment creation helpers that instantiate DEA `PaymentVoucher` through `django.apps.apps.get_model`.
- Services call DEA facade synchronously.
- Selectors are mostly read-only, but some older selector code still references legacy field names.
- Templates contain HTMX routing and some workflow decision presentation.

## Hidden Coupling

- `GivenLoan` and `TakenLoan` both use `Customer` from the contact app. Party migration is planned, but Girvi is still contact-customer based.
- `LoanItemWithCustody.repledged_to` and `RepledgeHistory.taken_loan` still point to `"girvi.Loan"` instead of `TakenLoan`, even though runtime screens now use `TakenLoan`.
- `resources.py` imports legacy `LoanPayment`, while payment runtime has moved to DEA `PaymentVoucher`.
- `tasks.py` has notification tasks that reference undefined legacy names (`Loan`, `Customer`, and `pending_loans`).
- `transition_registry.py` still carries legacy UI/state registry rows alongside canonical transition rows.
- `models/__init__.py` wildcard-imports both legacy and refactored model modules, increasing accidental legacy usage risk.
