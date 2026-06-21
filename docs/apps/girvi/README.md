---
status: active
owner: girvi
updated: 2026-06-18
tags: [girvi, app-docs, overview]
related: [architecture.md, models.md, workflows.md, userflows.md, refactor-plan.md, url-compatibility-matrix.md, ../../domain/girvi.md]
---

# Girvi App

Girvi is the tenant loan-management app. It manages pawn loans given to customers, loans taken from lenders against repledged collateral, collateral custody, releases, renewals, payments, interest accruals, licenses, series, storage boxes, statements, notices, print templates, exports, and reports.

The app is currently between two architectural eras:

- The active runtime loan models are `GivenLoan` and `TakenLoan` in `apps/tenant_apps/girvi/models/loan_refactored.py`.
- The legacy `Loan` and `LoanPayment` models remain in `apps/tenant_apps/girvi/models/loan.py` for compatibility, migrations, import/export, and historical data.
- Runtime lifecycle decisions now go through canonical flows in `apps/tenant_apps/girvi/flows.py`.
- Accounting side effects are synchronous today and go through Girvi services into the DEA facade. ADRs still point toward event-driven outbox posting as the target architecture.

## Primary Entry Points

- URLs: `apps/tenant_apps/girvi/urls.py`
- Views: `apps/tenant_apps/girvi/views/`
- Forms: `apps/tenant_apps/girvi/forms.py`
- Models: `apps/tenant_apps/girvi/models/`
- Services: `apps/tenant_apps/girvi/services.py` and `apps/tenant_apps/girvi/service_modules/`
- Lifecycle: `apps/tenant_apps/girvi/flows.py`, `apps/tenant_apps/girvi/transition_registry.py`, `apps/tenant_apps/girvi/transitions/`
- Selectors/facade: `apps/tenant_apps/girvi/selectors.py`, `apps/tenant_apps/girvi/facade.py`
- Templates: `templates/girvi/`
- Background jobs: `apps/tenant_apps/girvi/tasks.py`
- Signals: `apps/tenant_apps/girvi/signals.py`

## Main Concepts

- `GivenLoan`: money lent to a borrower against pledged items.
- `TakenLoan`: money borrowed from a lender, often backed by repledged collateral.
- `LoanItem`: pledged collateral item for a `GivenLoan`.
- `RepledgedLoanItem`: read-only legacy compatibility model linking original collateral to a `TakenLoan`; active movement uses custody fields and `RepledgeHistory`.
- `Release`: one-to-one closure document for a `GivenLoan`.
- `LoanInterestAccrual`: monthly interest recognition audit rows.
- `LoanRenewal`: audit link between a source loan and its renewed successor.
- `License` and `Series`: compliance and numbering setup for loans/releases.
- `LoanTemplate` and `TemplateFrame`: configurable loan-ticket/PDF printing.
- `Statement` and `StatementItem`: physical collateral verification.

## Read Next

- [Architecture](architecture.md)
- [Models](models.md)
- [Workflows](workflows.md)
- [Userflows](userflows.md)
- [Refactor Plan](refactor-plan.md)
- [URL Compatibility Matrix](url-compatibility-matrix.md)
