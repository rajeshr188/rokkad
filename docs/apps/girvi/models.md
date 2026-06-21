---
status: active
owner: girvi
updated: 2026-06-18
tags: [girvi, models, domain]
related: [README.md, architecture.md, workflows.md, ../../domain/girvi.md]
---

# Girvi Models

## Loan Model Split

The active loan model layer is in `apps/tenant_apps/girvi/models/loan_refactored.py`.

`BaseLoan` is abstract. It provides common audit fields, `loan_id`, `series`, `loan_date`, `tenure`, `status`, `interest_type`, common calculations, payment totals, interest due/outstanding helpers, navigation helpers, release creation delegation, and status history.

`GivenLoan` represents money lent to a borrower against collateral. It has:

- `borrower -> contact.Customer`
- `borrower_party -> party.Party` nullable shadow link during Party migration
- `series -> girvi.Series`
- `payments -> dea.PaymentVoucher` generic relation
- `loanitems -> LoanItem`
- `release -> Release` one-to-one
- `status -> LoanLifecycleState`

`TakenLoan` represents money borrowed from a lender. It has:

- `lender -> contact.Customer`
- `lender_party -> party.Party` nullable shadow link during Party migration
- optional `original_loan -> GivenLoan`
- `series -> girvi.Series`
- `payments -> dea.PaymentVoucher` generic relation
- `repledgedloanitems -> RepledgedLoanItem`
- `status -> TakenLoanLifecycleState`

The legacy `Loan` model remains in `models/loan.py`. It is explicitly marked deprecated and still defines old `loan_type`, `status`, `LoanPayment`, and `LoanChangeLog` compatibility structures.

## Lifecycle States

`LoanLifecycleState` is the canonical `GivenLoan` lifecycle:

- `Draft`
- `PendingApproval`
- `Approved`
- `ActiveCurrent`
- `ActiveOverdue`
- `ActiveNPA`
- `ClosurePending`
- `RenewalPending`
- `AuctionInitiated`
- `AuctionInProgress`
- `AuctionComplete`
- `Closed`
- `Renewed`
- `WrittenOff`
- `Rejected`
- `Cancelled`

Legacy `LoanStatus` values such as `Created`, `Disbursed`, `Released`, `Defaulted`, `Auctioned`, and `Repledged` are compatibility inputs only. `flows.py` normalizes them with `normalize_legacy_given_loan_status()`.

`TakenLoanLifecycleState` is intentionally smaller:

- `Draft`
- `Active`
- `SettlementPending`
- `Closed`
- `Cancelled`

`normalize_legacy_taken_loan_status()` maps old values into this smaller lifecycle.

## Collateral Models

`LoanItem` is the pledged item for a `GivenLoan`.

Important fields:

- `loan -> GivenLoan`
- `item -> product.ProductVariant`
- `itemtype`: `Gold`, `Silver`, `Bronze`
- `quantity`, `weight`, `purity`
- `loanamount`, `interestrate`, `interest`
- `itemdesc`
- custody fields inherited from `LoanItemWithCustody`

`LoanItem.save()` recalculates `interest` as `interestrate / 100 * loanamount`. `current_value()` uses `RateCacheService`.

`LoanItemPic` stores pictures for loan items and enforces one default picture per item.

`LoanItemStorageBox` organizes physical items by start/end item range, item type, and location. It validates range order, item type consistency, and range overlap.

`RepledgedLoanItem` links an original `LoanItem` to a `TakenLoan` and stores repledged amount/rate/interest. It remains a read-only compatibility structure for old rows and import mapping; active collateral movement uses custody fields plus `RepledgeHistory`. Direct TakenLoan amount, weight, description, current-value, and item-interest properties plus principal, interest, weight, and current-value queryset annotations now read from `RepledgeHistory`.

## Custody Models and Mixins

`models/custody_tracking.py` defines:

- `ItemCustodyStatus`: `in_vault`, `with_lender`, `with_customer`
- `LoanItemWithCustody`: abstract custody fields and operations
- `RepledgeHistory`: audit trail for repledge and return events
- `TakenLoanCollateralMixin`: helper methods for taken-loan collateral
- `GivenLoanReleaseMixin`: release eligibility and return-then-release workflow

Important caveat: some custody fields still reference `"girvi.Loan"` and some helper code uses old `loan.customer` naming. This is a refactor hotspot because runtime models now use `TakenLoan` and `GivenLoan.borrower`.

## Release and Renewal

`Release` in `models/release.py` is a one-to-one closure document for a `GivenLoan`.

Important fields:

- `loan -> GivenLoan`
- `release_id`
- `release_date`
- `released_by -> Customer`
- `created_by -> User`

`Release.save()` generates a release id using `ReleaseIDGenerator` and requires `created_by` on creation.

`LoanRenewal` in `models/renewal.py` records a renewal from source loan to successor loan. It stores mode, renewal date, interest/principal paid, top-up amount, creator, and notes.

## Interest Accrual

`LoanInterestAccrual` in `models/accrual.py` is an audit row per completed interest period for a `GivenLoan`.

Important fields:

- `loan -> GivenLoan`
- `period_start`, `period_end`
- `accrued_amount`
- `base_interest_snapshot`
- `months_covered`
- `trigger_source`
- `status`
- optional `journal_entry_voucher -> dea.JournalEntryVoucher`

It enforces `period_end > period_start` and uniqueness per loan/period.

## License, Series, and Guardrails

`License` stores pawn-broker/business compliance data, expiry metadata, documents, and helper reports.

`LicenseDocument` stores uploaded license files and metadata.

`Series` controls loan id formatting and has operational guardrails:

- loan count threshold
- loan amount threshold
- deactivation rule
- `deactivated_for_loans`
- `deactivated_for_releases`

`signals.py` calls `series.check_and_apply_deactivation()` after `GivenLoan`/`TakenLoan` saves and deletes.

## Statements and Templates

`Statement` and `StatementItem` implement physical verification of unreleased loans/collateral. Completion can auto-create discrepancy rows for missing loans.

`LoanTemplate` and `TemplateFrame` define configurable loan ticket PDFs. One template can be default; `TemplateFrame.clean()` validates frame geometry against template dimensions.
