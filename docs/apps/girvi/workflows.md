---
status: active
owner: girvi
updated: 2026-06-20
tags: [girvi, workflows, backend]
related: [README.md, architecture.md, models.md, userflows.md, refactor-plan.md]
---

# Girvi Backend Workflows

## Data Flow Matrix

| Workflow | Request URL | View | Form/DTO | Service | Templates | Database Writes | Side Effects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard and quick actions | `/` | `girvi_dashboard` | none | selectors and shortcut builders | `girvi/dashboard.html` | none | navigation tiles, summary cards |
| Create GivenLoan | `girvi/loan/create/` | `loan_create` | `LoanCreateForm`, initial item formset, `LoanCreateCommand` | `LoanCreationService` | `loan/loan_form.html`, `loan/_creation_preview.html` | `GivenLoan`, `LoanItem`, `LoanChangeLog` | Party-to-Customer compatibility bridge; series guardrail signal |
| Loan list | `girvi/loan/`, `girvi/loan/table/` | `loan_list`, `loan_table_partial` | `LoanFilter`, `TakenLoanFilter` | selectors only | `loan/loan_list.html`, `loan/table_htmx_loan_list.html` | none | none |
| Detail tabs | `girvi/loan/detail/<pk>/...` | `loan_detail_*_tab` | none | `get_given_loan_detail_read_model()` | `loan/loan_detail_1.html#...` | none | DEA read through facade for journal entries |
| Transition | `loan/<pk>/transition/` | `loan_transition_view` | transition form, transition payload dataclass | `LoanTransitionService` | `loan/loan_transition_form.html` | loan status, `LoanChangeLog` | Depending on command: DEA posting/reversal, notices |
| Disbursal | transition POST | `loan_transition_view` | `DisbursePayload` | `DisburseTransitionCommand`, `record_loan_disbursal()` | transition form | loan status, `LoanChangeLog`, DEA payment records | DEA voucher/posting |
| Given repayment | `girvi/loanpayment/<pk>/create/` | `loan_payment_create_view` | `GivenLoanRepaymentForm`, `InterestAccrualCommand` | `InterestAccrualService`, `GivenLoanPostingService` | `loanpayment/givenloan_repayment_form.html` | optional `LoanInterestAccrual`, DEA payment records | DEA voucher/posting |
| Taken repayment | `girvi/takenloan/<pk>/payment/create/` | `taken_loan_payment_create_view` | `TakenLoanRepaymentForm` | model helper plus DEA facade | `loanpayment/takenloan_repayment_form.html` | DEA payment records | DEA voucher/posting |
| Release | `girvi/release/<pk>/create/` | `release_create` | `ReleaseForm`, `ReleaseCreateCommand` | `ReleaseLifecycleService` | `release/release_form.html` | `Release`, loan status, item custody, `LoanChangeLog`, optional accrual rows, DEA payment records | DEA release receipt/posting |
| Bulk release | `girvi/bulk_release/`, `submit_release_formset/` | `bulk_release`, `submit_release_formset` | `BulkReleaseForm`, release formset | `BulkReleaseService` | `release/bulk_release.html`, `release/release_formset.html` | same as release per row | same as release per row |
| Renewal | `girvi/loan/renew/<pk>/` | `loan_renew` | `LoanRenewForm`, `LoanRenewalCommand` | `LoanRenewalService` | `loan/loan_renew.html` | new `GivenLoan`, cloned `LoanItem`, source status, `LoanRenewal`, optional accrual/payment records | DEA payment/disbursal posting |
| Custody return | custody return URLs | `return_item_from_lender`, `return_all_items_from_lender` | POST fields | custody service/model methods | redirects or custody partials | `LoanItem`, `RepledgeHistory` | none |
| Repledge | `girvi/custody/repledge/create/with-items/` | `create_repledge_with_items` | POST fields including optional `series_id` | `create_repledge_from_items()` | `repledge_select_items.html` | `TakenLoan`, custody fields, `RepledgeHistory` | Resolves active TakenLoan series and generates loan ID from the concrete loan table |
| Interest accrual batch | Celery task / management command | command entrypoint | `InterestAccrualCommand` | `InterestAccrualService` | none | `LoanInterestAccrual`, optional DEA journal/voucher rows | DEA accrual posting |
| Statement verification | `statement/...` | statement views | `StatementItemForm` | model methods | `statement/*.html` | `Statement`, `StatementItem` | discrepancy row generation |
| Loan item management | `loanitems/`, `loanitem/<parent>/create/`, `loanitem/<parent>/update/<id>/`, `loan/item/<pk>/detail`, pictures endpoints | `loanitem_list`, `loanitem_create_update`, `loanitem_detail`, picture modal handlers | item forms and picture upload forms | item selectors and helpers | `partials/item-*.html`, `loanitem/*.html` | `LoanItem`, pictures, legacy repledge read-only rows | none |
| Notice generation | `girvi/loan/<pk>/notify/`, `girvi/notice/`, `girvi/outdatedloans/notify/`, `girvi/outdatedloans/notify-v2/` | `create_loan_notification`, `notice`, `notify_print`, `notify_print_v2` | notice filters and message builders | print/notice helpers | notice templates and print templates | notification records / derived notice rows | reminder printing and overdue notices |
| Storage box management | `storage_boxes/` and CRUD endpoints | `list_storage_boxes`, `add_storage_box`, `update_storage_box`, `delete_storage_box`, `storage_box_detail` | storage box forms | storage box helpers | `storagebox/*.html` | `LoanItemStorageBox` | none |
| Reporting and exports | `girvi/loan-report/`, `girvi/loanbycustomer/`, `girvi/loancrosstab/`, `girvi/series-report/`, `girvi/license-report/`, `girvi/loan-listreport/`, `girvi/ledger/`, `girvi/unreleased/`, `girvi/loan/inventory-audit/export/` | report views and export views | report filters / report view params | report classes and export helpers | `reports/*.html`, export templates | read-only queries and generated files | downloads / PDF / Excel exports |
| Archive browsing | `loan_archive/`, yearly/monthly/weekly/day/today archive paths | archive class-based views | none | date archive views | `loan_archive.html` and archive templates | none | historical browsing |
| Template administration and printing | `girvi/templates/`, `preview/`, `test-print/`, `download-pack/`, frame CRUD, default/clone/toggle | template views and frame views | template/frame forms | `LoanPrintService` | `template/*.html`, PDF views | `LoanTemplate`, `TemplateFrame` | PDF/print output, template pack download |

## Loan Creation

URL: `girvi/loan/create/`

View: `views/loan.py::loan_create`

Forms/services:

- `LoanCreateForm`
- initial item formset from `build_initial_loan_item_formset()`
- `LoanCreateCommand`
- `LoanCreationService`

Flow:

1. GET builds initial loan data from latest active series, default date preference, and optional borrower Party.
2. Template `templates/girvi/loan/loan_form.html` renders the loan form and initial collateral rows.
3. The creation preview uses `girvi/loan/create/preview/` and `LoanCreationService.preview()`.
4. POST validates the loan form and item formset.
5. The view ensures the selected Party has a compatibility `Customer` bridge, assigning borrower/customer roles as needed.
6. `LoanCreationService.execute()` creates a `GivenLoan` in `Draft`, stores both `borrower` and `borrower_party`, creates initial `LoanItem` rows, and writes a `LoanChangeLog`.
7. The view redirects to loan detail with `HX-Redirect`.

Database changes:

- `GivenLoan`
- `LoanItem`
- `LoanChangeLog`

Side effects:

- No accounting side effect on create.
- Party-to-Customer compatibility bridge may create a legacy customer record for the selected Party.
- `post_save` signal may apply series guardrails.

## Loan List and Filtering

URLs:

- `girvi/loan/`
- `girvi/loan/table/`

Views:

- `loan_list`
- `loan_table_partial`

Read layer:

- `given_loan_base_qs()`
- `taken_loan_base_qs()`
- `filter_unified_loans()`
- `get_loan_totals()`

Flow:

1. `loan_kind=given` uses `LoanFilter` and `LoanTable`.
2. `loan_kind=taken` uses `TakenLoanFilter` and `TakenLoanTable`.
3. `loan_kind=all` merges shaped rows with `UnifiedLoanTable`.
4. HTMX filters and pagination target `#loan-table-container` and render `loan_list.html#loan-table`.

Database changes: none.

## Loan Detail

URL: `girvi/loan/detail/<pk>/`

View: `loan_detail`

Flow:

1. Fetches `GivenLoan` with borrower, creator, series, items, renewals.
2. Builds runtime flow via `build_runtime_loan_flow()`.
3. Computes outgoing transition labels and builds UI actions with `build_transition_actions()`.
4. Computes collateral weight/value, due ratios, storage location, renewal links, interest reporting, and changelog.
5. Renders `templates/girvi/loan/loan_detail_1.html`.

Lazy detail tabs:

- `items`: `loan_detail_items_tab`
- `payments`: `loan_detail_payments_tab`
- `transactions`: `loan_detail_transactions_tab`
- `statement`: `loan_detail_statement_tab`
- `notices`: `loan_detail_notices_tab`
- `release`: `loan_detail_release_tab`

These tabs use `get_given_loan_detail_read_model()`.

## Lifecycle Transitions

URL: `loan/<pk>/transition/`

View: `loan_transition_view`

Core files:

- `flows.py`
- `transition_registry.py`
- `service_modules/transitions.py`
- `transitions/commands.py`
- `transitions/payloads.py`

Flow:

1. User selects a transition action from loan detail.
2. View normalizes aliases with `normalize_transition_name()` and `resolve_runtime_transition_name()`.
3. View loads the configured form class from `transition_registry.py`.
4. POST validates form data.
5. `LoanTransitionService.execute()` builds the runtime flow, checks `can_proceed()`, builds a payload DTO, and executes the command class.
6. Generic commands only call the FSM method. Specialized commands also call accounting/reversal services.
7. Flow success saves loan status and creates `LoanChangeLog`.

Important side effects:

- `disburse_loan`/TakenLoan `activate` calls `record_loan_disbursal()`.
- `complete_auction` calls auction recovery posting.
- `undo_disbursal` calls `reverse_loan_disbursal()`.
- Legacy aliases are accepted but runtime methods are canonical.

## Disbursal Posting

Trigger:

- GivenLoan `disburse_loan`
- TakenLoan `activate`

Command: `DisburseTransitionCommand`

Accounting service: `service_modules/payment.py::record_loan_disbursal`

Flow:

1. FSM moves `GivenLoan` to `ActiveCurrent` or `TakenLoan` to `Active`.
2. `record_loan_disbursal()` resolves the borrower/lender DEA account by role and purpose.
3. It creates/posts a `PaymentVoucher` through DEA facade `create_and_post_payment`.
4. Idempotency marker is `DISBURSAL-<MODEL>-<pk>`.

Direction:

- `GivenLoan`: `PAYMENT`
- `TakenLoan`: `RECEIPT`

## Repayment

Given loan URL: `girvi/loanpayment/<pk>/create/`

View: `loan_payment_create_view`

Form: `GivenLoanRepaymentForm`

Service: `GivenLoanPostingService.post_repayment()`

Flow:

1. User submits total amount, optional interest amount, date, method, reference.
2. If preference `loan_catchup_on_receipt` is enabled, `InterestAccrualService.execute()` runs before posting.
3. `GivenLoanPostingService` creates and posts a receipt `PaymentVoucher`.
4. Redirects back to loan detail.

Taken loan URL: `girvi/takenloan/<pk>/payment/create/`

View: `taken_loan_payment_create_view`

Form: `TakenLoanRepaymentForm`

Flow:

1. Creates a `PaymentVoucher` through `TakenLoan.create_payment()`.
2. Posts it through DEA facade `post_payment_voucher()`.
3. Redirects to taken-loan collateral detail.

## Release

URLs:

- `girvi/custody/loans/<loan_id>/release/check/`
- `girvi/release/<pk>/create/`
- `girvi/release/create/`

Views:

- `release_loan_check_custody`
- `release_create`

Service: `ReleaseLifecycleService`

Flow:

1. User starts release from loan detail.
2. Custody check verifies whether any items are with lenders.
3. If all items are in vault, the release form opens.
4. `ReleaseForm` validates selected loan/date/released_by.
5. `ReleaseLifecycleService.preview()` checks if the lifecycle can request/complete closure.
6. `execute()` optionally runs catch-up accrual (`loan_catchup_on_release`).
7. Creates `Release`.
8. Moves collateral items to customer where possible.
9. Runs `request_closure` if needed, then `complete_closure`.
10. Posts release receipt through `record_loan_release()`.
11. Redirects to loan detail.

Database changes:

- `LoanInterestAccrual` when catch-up creates rows.
- `Release`
- `LoanItem.custody_status`
- `GivenLoan.status`
- `LoanChangeLog`
- DEA `PaymentVoucher` and ledger records.

## Bulk Release

URLs:

- `girvi/bulk_release/`
- `submit_release_formset/`

Views:

- `bulk_release`
- `submit_release_formset`

Service: `BulkReleaseService`

Flow:

1. User selects loans from loan list.
2. Bulk form builds a preview formset.
3. Submit uses strict or partial commit policy.
4. Each valid row uses release lifecycle creation.

## Renewal

URL: `girvi/loan/renew/<pk>/`

View: `loan_renew`

Service: `LoanRenewalService`

Flow:

1. User opens renewal form for a source `GivenLoan`.
2. Preview computes outstanding principal, interest due, collateral value, and new principal.
3. POST validates mode: `PAY_AND_RENEW` or `TOPUP_RENEW`.
4. Optional catch-up accrual runs when preference `loan_catchup_on_renewal` is enabled.
5. Optional renewal payment is created.
6. New successor `GivenLoan` is created in `Draft`.
7. Items are cloned/scaled to the new loan.
8. Source loan runs `request_renewal` then `complete_renewal`.
9. New loan is submitted, approved, disbursed, and its disbursal accounting is posted.
10. `LoanRenewal` audit row links source and successor.

## Custody and Repledge

URLs are grouped under `CUSTODY_URLPATTERNS` in `urls.py`.

Services:

- `build_loan_custody_summary()`
- `build_release_custody_check()`
- `create_repledge_from_items()`
- `return_all_items_from_taken_loan()`
- `build_taken_loan_collateral_context()`

Flow:

1. Available loan items are selected from unreleased `GivenLoan` collateral in vault.
2. The user may select a TakenLoan series; otherwise the service chooses the first active TakenLoan series, falling back to the first active loan series.
3. A `TakenLoan` is created for a lender with that series.
4. Selected items are moved to `with_lender` custody and linked to the taken loan.
5. Returning collateral moves items back to `in_vault`.
6. Release workflow blocks or warns when items are still with lenders.

Migration note: custody history and active repledge fields now target `TakenLoan` through a guarded migration. `RepledgedLoanItem` remains readable for old rows and import mapping, but legacy mutation routes are closed; active collateral movement should use custody/repledge workflows.

Coverage note: focused guardrail tests cover repledge creation, bulk return from lender, `TakenLoan.return_all_collateral()`, `TakenLoan.can_close()`, and release blocking/return behavior while items are with lenders.

Read-model note: direct TakenLoan amount, weight summary, item description, current value, and item-interest properties read from `RepledgeHistory`. Principal, interest, weight, and current-value queryset annotations also read from `RepledgeHistory`; `RepledgedLoanItem` remains readable only for legacy/import compatibility.

## Interest Accrual

Manual/service entry: `InterestAccrualService`

Scheduled entry:

- Celery task `accrue_loan_interest_batch`
- Management command `accrue_loan_interest`

Flow:

1. Preview normalizes as-of date.
2. It computes completed monthly periods from `loan_date` to effective end date.
3. Existing period rows are skipped.
4. Execution creates `LoanInterestAccrual` rows.
5. If `post_to_accounting=True`, DEA facade posts an accrual batch and updates row status.

Trigger sources:

- manual
- scheduled
- period close
- release catch-up
- renewal catch-up
- receipt catch-up
- backfill

## Statements

URLs start at `statements/` and `statement/create/`.

Models:

- `Statement`
- `StatementItem`

Flow:

1. User creates a verification session.
2. User scans/adds statement items.
3. Marking complete finds unreleased loans missing from the session and creates discrepancy rows.
4. Reopening clears completion metadata.

## Printing and Templates

Templates:

- `LoanTemplate`
- `TemplateFrame`

Services:

- `LoanPrintService`
- `documents/loan_ticket.py`

Flow:

1. Admin configures templates and frames.
2. Template readiness checks required files/frames.
3. Preview/test print renders sample loan.
4. Loan detail/list print actions render PDFs or labels.
