---
status: active
owner: project
updated: 2026-06-22
tags: [agents, context, architecture]
related: [README.md, STATUS.md, constitution.md, domain/accounting.md, implementation/dependency-policy.md]
---

# Agent Memory

This document stores durable project context for AI agents. The root [AGENTS.md](../AGENTS.md) defines the operating rules; this file explains what the system is and how to reason about it.

## Project Identity

Rokkad is a tenant-aware SaaS mini ERP for small businesses, especially jewellery, pawn/loan, commodity, inventory, and future commerce workflows.

Accounting is the central source of truth. Loans, inventory, future sales/purchase documents, and commodity transactions are business documents that produce accounting, stock, and commodity ledger effects.

The product must feel document-centric, not module-centric.

## Core Mental Model

Business Event
-> Source Document
-> Posting Engine
-> Voucher
-> Journal Entry
-> Financial Ledger
-> Inventory Ledger
-> Commodity Ledger
-> Reports

Users should create business documents, not manual journal entries.

## Core Modules

- Accounting
- Loans / Girvi
- Inventory
- Future sales/commerce
- Future purchase/procurement
- Commodity management
- Workspace management
- Subscription management
- Authorization
- Onboarding
- Customer portal
- Notifications

## Design Principles

1. Accounting is central.
2. Business documents create vouchers.
3. Vouchers post journal entries.
4. Journal entries are immutable.
5. Corrections happen through reversals.
6. Every accounting entry must link back to its source document.
7. Commodity is tracked as inventory/position, not as normal currency.
8. Multitenancy uses workspace/tenant isolation.
9. UI should follow business workflows, not database tables.
10. Normal users work with documents; accountants can inspect vouchers, journal entries, and ledgers.

## Important Domain Concepts

Use a generic party model where possible:

- Customer
- Supplier
- Broker
- Employee

A party can have multiple roles.

Use source documents:

- Sale
- Purchase
- Loan
- Receipt
- Payment
- Expense
- Stock Adjustment
- Commodity Contract
- Commodity Settlement

Do not make accounting models depend directly on UI forms. UI creates documents; posting rules create vouchers and journal entries.

## Accounting Architecture

Other domains should not bypass DEA for ledger effects.

Business documents are not ledger entries. Posting converts business intent into `Voucher`, `VoucherLine`, and `JournalEntry`.

Use immutable journal entries.

If a posted document changes:

1. Reverse the previous journal entry.
2. Create a new corrected journal entry.

Do not edit posted journal lines in place.

Use a posting engine:

- `PostingContext`
- `PostingRuleRegistry`
- `PostingRule`
- `PostingBundle`
- `Voucher`
- `VoucherLine`
- `JournalEntry`
- `LedgerLine`
- `AccountLine`

Each document should expose `get_economic_payload()` or equivalent structured data for fingerprinting and idempotency.

## Architecture Rules

- Other apps should import DEA through `apps.tenant_apps.dea.facade`.
- Other apps should import Girvi cross-domain reads through `apps.tenant_apps.girvi.facade` or selectors.
- Girvi lifecycle work should prefer command/use-case services over model methods or large view logic.
- Girvi runtime lifecycle is canonicalized: `GivenLoan` uses `LoanLifecycleState`, legacy loan statuses/actions are compatibility aliases, and `TakenLoan` uses a smaller dedicated lifecycle.
- Girvi app analysis docs live under `docs/apps/girvi/` and should be updated when Girvi models, workflows, UI routes, services, or lifecycle behavior change.
- Contacts should not directly know Girvi internals for loan summary data.
- Tenant seed/setup failures should surface as actionable setup messages, not silent zero values.
- Posting logic belongs in DEA posting services/rules, not views or templates.
- Current Girvi borrower/lender posting paths resolve DEA subledger accounts by party role and purpose (`BORROWER_LOAN_RECEIVABLE`, `LENDER_LOAN_PAYABLE`) instead of reading `Customer.account` directly.
- Current DEA sales/purchase invoice posting paths resolve customer/supplier accounts by party role and purpose (`CUSTOMER_RECEIVABLE`, `SUPPLIER_PAYABLE`) instead of direct `Customer.account` reads.
- Experimental operational `sales`, `purchase`, and `approval` tenant apps were removed from runtime on 2026-06-19. DEA `SalesInvoiceVoucher` and `PurchaseInvoiceVoucher` remain accounting documents; future commerce/procurement apps must be rebuilt around commodity, inventory, settlement, and DEA posting boundaries rather than gold/silver-as-currency balances.
- Party has a tenant UI at `/party/` for list/search/filter, create/edit, detail tabs, role add/end, read-only contact/address/KYC data, DEA party account mapping visibility, and linked customer loan activity.
- Party profile data is editable from Party detail: single profile photo, contact methods, addresses, identifiers, and documents can be maintained directly before Phase 9 operational foreign-key migration work.
- Party profile photos can be maintained from Party detail by either choosing an image file or capturing an image from the device camera.
- Party contact forms validate phone/mobile/WhatsApp through `django-phonenumber-field` with region `IN`, store phone numbers in E.164 format, and Party relationships are maintained from the Party detail Relationships tab.
- Party stores textual relation identity directly on `Party` through `relation_label` and `relation_name` for values like `S/o Kumar`; structured `PartyRelationship` remains for links to saved Party records.
- Party duplicate merge is service-backed and conservative: source parties are archived, non-conflicting profile children and DEA mappings are moved, and merges stop on legacy-customer, identifier, or active DEA mapping conflicts.
- Party list has filtered CSV/XLSX export for Owner/Admin users. The first version is intentionally flat: Party identity fields, contact summary, active roles, and legacy customer linkage; child profile tables remain separate.
- Party Phase 9 uses nullable shadow FKs on operational documents first. Current shadow links include Girvi borrower/lender loans and DEA sales/purchase invoice vouchers; DEA account resolution prefers explicit Party links and falls back to Customer.
- Party detail loan history now uses a Girvi facade read model that aggregates active/closed Given/Taken loans plus payment, notice, and collateral summaries for both Party-linked and legacy bridged-customer records.
- Girvi given-loan creation is Party-first while still compatibility-safe: users select an active Party, the create path ensures a legacy `Customer` bridge as needed, and `GivenLoan.borrower` plus `GivenLoan.borrower_party` are both populated.
- Party codes are tenant-local stable identifiers. Normal creation auto-generates sequential `P-000001` style codes when blank; manual/custom codes remain supported for imports and legacy bridge records.
- Girvi TakenLoan amount, weight, current-value, and item-interest read models should use `RepledgeHistory` plus linked `LoanItem` data; `RepledgedLoanItem` is retained only as readable legacy/import compatibility data.
- Refactored Girvi interest query annotations use `calculated_*` names to avoid shadowing read-only model properties such as `loan_amount`, `total_interest`, and `total_due`.
- Girvi transition registries should keep canonical state/UI/form metadata as primary. Legacy transition metadata belongs only in explicit compatibility registries while aliases remain accepted for old URLs/imported values.
- Girvi active list/detail/transition UI should render canonical lifecycle labels through lifecycle display helpers rather than raw persisted status values.
- Girvi transition matrix tests derive canonical transition source/target states from `flows.py`; adding or changing a canonical `GivenLoanFlow` or `TakenLoanFlow` transition should update registry state metadata in the same change.
- Girvi operational endpoints now use centralized permission gates in `views/access.py` (`girvi_permission_required`, `GirviPermissionRequiredMixin`) so create/edit/delete, transition/disbursal, repayment, release mutation, and report routes are not merely login-guarded.
- Girvi customer notice communication now standardizes on notify_v2 batch dispatch: bulk and single-loan notice entrypoints map reminder/auction notice codes to notify_v2 events/channels, and the legacy bulk notice URL is retained only as an alias to the same notify_v2 workflow.
- Girvi MVP document/PDF generation now has a shared `GirviDocumentService` entry point in `service_modules/printing.py`; existing loan ticket and release Form H endpoints call that service, and a new permission-gated repayment receipt PDF route (`girvi_payment_receipt_pdf`) is exposed from loan detail payment rows.
- Girvi safe-operations admin surface now includes a permission-gated Operations Console (`girvi_operations_console`) that centralizes posting/outbox health, controlled retry for failed outbox rows, series/rate setup checks, and recent `LoanChangeLog` audit events.
- Girvi essential report coverage now includes a dedicated permission-gated Operational Controls report (`loan_operational_controls_report`) with outstanding aging, collateral custody, release-readiness, and rate-exception sections; the additional per-retry audit-log emission follow-up is intentionally deferred.
- Girvi policy centralization now covers key workflow guardrails in `policies.py`: release eligibility (`assert_can_create_release`), repayment permission (`assert_can_record_repayment`), and transition readiness (`assert_loan_transition_allowed`), and these checks are used directly by release, repayment, and transition views.
- Girvi view-thinning for Phase 3 now includes release-create orchestration extraction: release preview/submit business flow is centralized in `service_modules/release_workflow.py`, while `views/release.py` handles HTTP/form/messaging concerns.
- Girvi view-thinning for Phase 3 now also includes repayment and transition helper extraction: repayment preview/form-initial/message emission now lives in `service_modules/repayment_workflow.py`, and transition name/form/policy resolution now lives in `service_modules/transition_workflow.py`.
- Girvi view-thinning for Phase 3 now includes custody helper extraction: release-check checklist reads, release-with-return gate/effect orchestration, and release-custody API payload construction now live in `service_modules/custody_workflow.py`, with `views/custody_views.py` focused on request/response messaging.
- Girvi view-thinning for Phase 3 custody flows now also includes taken-loan collateral-return and single-item lender-return execution: `return_taken_loan_collateral` and `return_item_from_lender` delegate mutation orchestration to `service_modules/custody_workflow.py` and keep view-level handling to HTTP/messaging.
- Girvi transition command cleanup now extracts disbursal and recovery side-effect orchestration into `service_modules/transition_side_effects.py`, and custody repledge create request parsing/execution now lives in `service_modules/repledge_workflow.py`.
- Girvi forms-to-workflow cleanup for Phase 3 has started: `LoanItemStorageBoxForm` keeps input validation only, while range-assignment/save side effects moved to `service_modules/storagebox_workflow.py` and are invoked by `views/storagebox.py`.
- Girvi forms-to-workflow cleanup now also covers release forms: `BaseReleaseFormSet.clean()` delegates duplicate/stale release-row workflow checks to `service_modules/release_form_validation.py`, and `ReleaseForm.save()` override was removed to keep the form validation-focused.
- Girvi release-form cleanup now also delegates single-form business checks to `service_modules/release_form_validation.py`: `ReleaseForm.clean_loan()` and `ReleaseForm.clean_release_amount()` no longer embed release state/due-cap logic directly.
- Girvi forms-to-workflow cleanup now also covers repayment forms: `GivenLoanRepaymentForm.clean()` and `TakenLoanRepaymentForm.clean()` delegate settlement/split validation checks to `service_modules/repayment_form_validation.py`.
- Girvi forms-to-workflow cleanup now also covers loan-item forms: `LoanItemForm.clean()` and `InitialLoanItemForm.clean()` delegate collateral-value and initial-row required/default checks to `service_modules/loan_item_form_validation.py`.
- Girvi Phase 3 task 27 is now complete for current MVP view paths: create/release/repayment/transition/custody/repledge orchestration lives in workflow/service modules (including `loan_workflow.py` for create-preview parsing and update persistence), and views are primarily HTTP/message coordinators.
- Girvi Phase 3 task 28 is now complete for current MVP form paths: release, repayment, loan-item, and loan/create/renew/storage-box business validations are delegated to form-validation service modules, while forms remain binding/input-shape oriented.
- Girvi Phase 3 task 29 is complete for current MVP read paths: operations-console report summaries are built by `build_operations_console_read_model`; repledge-history report query/filter/count payload is built by `build_repledge_history_read_model`; item-custody API payload is built by `build_item_custody_status_payload`; dashboard aggregate/count context is built by `build_girvi_dashboard_read_model`; and reconciliation/operational-controls report context shaping is built by selector context helpers before render.
- Girvi Phase 3 task 30 is complete for current MVP scope: statement verification read calculations moved to selectors with compatibility delegators, and `models/loan_refactored.py` high-usage read-only calculations (Given/Taken loan amounts, interest amounts, weight summaries, item descriptions, current values, total payment splits, interest due/accrual/receivable, last accrual date) now delegate to selector helpers.
- Girvi Phase 3 task 31 is complete: runtime `LoanChangeLog` consumers use package-level model imports, migration compatibility helper `migrate_old_loan_to_new_structure` imports `OldLoan` from `models.legacy`, architecture tests restrict direct `models.loan`/`models.legacy` imports to explicit compatibility seams, only `management/commands/missingcol.py` may import deprecated legacy loan models in command surfaces, runtime modules are guarded from importing legacy manual commands (`do`, `missingcol`), and legacy command lifecycle policy is documented in `docs/implementation/girvi-legacy-command-lifecycle.md`.
- Girvi Phase 3 task 34 is complete: runtime notify integration in key Girvi workflows now routes through `integrations/notification_adapter` (with lazy imports to avoid app-load cycles), key boundary views/selectors/transitions no longer directly import notify/contact model modules, and AST guard tests enforce that boundary for `selectors.py`, `views/loan.py`, `views/notice.py`, `views/prints.py`, and `transitions/commands.py`.
- Current Girvi-to-DEA synchronous posting/read integration should go through `apps.tenant_apps.girvi.integrations.dea_adapter`; `service_modules.posting_adapter` exists only as a compatibility import path.
- Girvi refactored loan model payment methods are compatibility wrappers only; voucher creation logic belongs in `service_modules.payment_voucher_creation` and the DEA adapter boundary.
- Girvi P3 adapter cleanup is complete for refactored runtime paths. Deprecated `models/loan.py` may still import DEA directly until P5 legacy model containment.
- Girvi loan detail display data belongs in selectors/read models. Current detail metrics, storage position lookup, interest reporting, release CTA metadata, and action-readiness data are built by `apps.tenant_apps.girvi.selectors` and consumed by thin view rendering.
- Girvi loan detail action-readiness uses `build_given_loan_action_readiness` to show the primary next action, settlement state, collateral state, accounting journal presence, and timeline event count before the full tabbed detail surface.
- Girvi repayment use cases belong in `service_modules.repayment`: GivenLoan receipt catch-up accrual, repayment payload shaping, DEA posting delegation, TakenLoan repayment posting, and result messages should stay out of `views.loanpayment`.
- Girvi repayment UI capture presets belong in `service_modules.repayment_workflow` and should be derived from the shared repayment preview. Given/Taken repayment screens expose exact-settlement, interest-only, and principal-only presets while service success messages report total, principal, interest, and remaining outstanding.
- Girvi release UI readiness belongs in `service_modules.release_workflow`: `build_flow_context` is the shared read model for release pages and custody-check pages, covering settlement, custody, recipient, Form H document expectation, and accounting-posting expectation while `submit` remains the guarded mutation path.
- Party-centric Girvi loan history belongs behind `apps.tenant_apps.girvi.facade.get_party_loan_history_summary`; Party views/templates should consume that read model for active/closed loans, outstanding split, payment totals, notices, collateral, repayment shortcuts, and release/Form H document links instead of importing Girvi models directly.
- Girvi-to-DEA accounting readiness belongs in `apps.tenant_apps.girvi.integrations.dea_adapter`: it owns posting event contract versioning, event type/rule metadata, idempotency keys, source-document economic payload extraction, posting-status reads, and reversal delegation. Runtime Girvi code should not import DEA internals directly.
- Girvi bulk merge/delete use cases belong in `service_modules.bulk_operations`: selection parsing, guard validation, merge orchestration, delete orchestration, and structured operation errors should stay out of `views.loan`.
- Deprecated Girvi `Loan` / `LoanPayment` must not be imported from `apps.tenant_apps.girvi.models`; use `apps.tenant_apps.girvi.models.legacy` only for explicit historical compatibility surfaces. Runtime code should use `GivenLoan`, `TakenLoan`, and DEA `PaymentVoucher` paths.
- Girvi legacy payment import/export is intentionally labelled as `LegacyLoanPaymentResource`; `LoanPaymentResource` is only a compatibility alias for old import/export callers.
- DEA posting fingerprints must be based on stable economic payloads, not voucher row ids, timestamps, statuses, or display metadata. Current DEA idempotency coverage expects duplicate posting of the same voucher or same source-document payload to return existing accounting effects, while changed economic payloads reverse the previous voucher and create a corrected posting.
- DEA voucher reversal workflow belongs in `apps.tenant_apps.dea.services.reversal.reverse_posted_voucher()`. `DjangoPostingEngine.reverse_voucher()` and `apps.tenant_apps.dea.views.voucher.reverse_voucher()` delegate to that service; new callers should use it directly so duplicate reversals are idempotent and reversal audit details stay centralized.
- DEA voucher posting workflow belongs behind `apps.tenant_apps.dea.posting.commands.PostVoucherCommand`. `apps.tenant_apps.dea.views.voucher.post_voucher()` delegates to that command; rule-backed voucher types continue through `DjangoPostingEngine`, while manual stored-line voucher types without registered rules use the command's controlled `materialize_journal_from_voucher_lines()` fallback.
- DEA Phase 3 commodity accounting is accepted as a side-by-side layer, not a financial currency extension. Future commodity work should model `Commodity`/`Metal`, `CommodityAccount`, immutable `CommodityMovement`, `ExposureLine`, and `RateFixing` separately from `MoneyField`, `LedgerTransaction`, `AccountTransaction`, and financial trial balance.

## Multi-tenant SaaS Assumptions

The app is workspace-based.

A user can:

- own multiple workspaces
- belong to multiple workspaces
- switch workspace from navbar

Workspace features:

- members
- roles
- invitations
- subscription
- settings

All business data belongs to a workspace/tenant context.

Migration execution should respect the `django-tenants` split: tenant app changes use `migrate_schemas`, and shared app changes use `migrate_schemas --shared`.

## UX Memory

The home dashboard should be action-first:

- Create Sale
- Create Purchase
- Create Loan
- Receive Payment
- Make Payment
- Stock Adjustment
- Commodity Settlement

Every source document should follow a consistent page pattern:

- Overview
- Payments / Settlements
- Inventory Impact
- Commodity Impact
- Accounting Impact
- Attachments
- History / Timeline

Prefer timelines and activity feeds over isolated reports.

## Navigation Memory

Main sidebar direction:

- Home
- Activities
- Parties
  - Customers
  - Suppliers
- Operations
  - Sales
  - Purchases
  - Loans
  - Receipts
  - Payments
  - Commodity
- Inventory
- Accounting
- Reports
- Settings

## Tech Preferences

Backend:

- Django
- PostgreSQL
- HTMX
- Bootstrap 5
- `django-template-partials` where useful

Prefer server-rendered UI with HTMX partial updates. Avoid heavy SPA complexity unless clearly necessary.

## Current Active Work

The active design track is Girvi event-driven DEA posting. See [plans/active](plans/active.md) and the archived full spec at [GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC](archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md).

## Documentation Memory

- Canonical docs live under `docs/`.
- Historical source docs live under `docs/archive/`.
- Accepted architecture decisions live under `docs/adr/`.
- Every markdown file under `docs/` should start with frontmatter.
- Every doc should link back to `README.md` where practical for navigation.
