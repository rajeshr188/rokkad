---
status: active
owner: project
updated: 2026-06-29
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
- DEA commodity schema planning is in `docs/implementation/dea-commodity-model-schema.md`; it should be kept current as Phase 3 model slices land.
- DEA now has the first commodity model foundation: `Commodity` and `CommodityAccount` with tenant migration `0033`, admin registration, exports, monetary-code guard validation, and party-obligation account validation.
- DEA default commodity setup now exists through `apps.tenant_apps.dea.services.commodity_seed.seed_default_commodities()` and the `seed_dea_commodities` command. It creates/repairs tenant-local `GOLD` and `SILVER` records idempotently.
- DEA now has immutable `CommodityMovement` with tenant migration `0034`, source/voucher links, explicit commodity quantity fields, from/to commodity accounts, monetary valuation currency validation, idempotency/reversal links, read-only admin diagnostics, and tests.
- DEA now has `ExposureLine`, `RateFixing`, and `RateFixingAllocation` foundations with tenant migration `0035`, admin diagnostics, quantity/status/currency validation, and fixing allocation guardrails.
- DEA now has a side-by-side commodity posting service skeleton in `apps.tenant_apps.dea.services.commodity_posting`, with structured payloads and deterministic source/economic-payload idempotency keys for `CommodityMovement` and `ExposureLine` creation.
- DEA now has commodity position selectors in `apps.tenant_apps.dea.selectors.commodity` that compute movement-derived balances by account, party, location, fixed status, and as-of date with reversal offsets.
- DEA MVP commodity valuation policy is documented in `docs/implementation/dea-commodity-valuation-policy.md`: valuation is reporting-only, defaults to INR, uses rates as market inputs, reports missing rates explicitly, and defers `ValuationSnapshot`, unrealized gain/loss, and financial journal effects.
- DEA now has valuation read-model foundation: `rates.facade.get_latest_commodity_valuation_rate()` and `dea.services.valuation` value commodity position rows and exposure lines with buying/selling side policy, missing/unsupported statuses, and no financial transaction side effects. The next safe DEA commodity slice is Phase 4 fixed purchase backend MVP; keep it command/service focused and avoid UI redesign, broad purchase-module work, snapshots, and unrealized gain/loss accounting.
- DEA Phase 4 fixed purchase backend MVP now exists in `apps.tenant_apps.dea.services.fixed_purchase`: fixed purchases create INR-only financial voucher/journal/account effects through `PostVoucherCommand(DjangoPostingEngine())` and a separate fixed `CommodityMovement` atomically. The service is idempotent by source plus economic payload, rejects changed payloads for the same source until correction/reversal is implemented, and keeps commodity quantity out of financial currency paths. The next safe DEA slice is unfixed purchase backend MVP: commodity receipt plus open purchase exposure with no false final monetary payable.
- DEA Phase 4 unfixed purchase backend MVP now exists in `apps.tenant_apps.dea.services.unfixed_purchase`: unfixed purchases create a posted commodity-intent voucher, immutable `CommodityMovement`, and open purchase `ExposureLine` without `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or `VoucherLine` rows. Final monetary AP must wait for rate fixing. The next safe DEA slice is rate fixing backend MVP: fix open exposure quantity, record `RateFixing`, and create monetary payable through financial posting.
- DEA Phase 4 purchase and sale rate fixing backend MVP now exists in `apps.tenant_apps.dea.services.rate_fixing`: `post_purchase_rate_fixing()` fixes purchase exposure into monetary supplier payable, and `post_sale_rate_fixing()` fixes sale exposure into monetary customer receivable/revenue. Both paths record `RateFixing`/`RateFixingAllocation`, post financial effects through `PostVoucherCommand(DjangoPostingEngine())`, and reduce or close exposure atomically.
- DEA Phase 4 fixed sale backend MVP now exists in `apps.tenant_apps.dea.services.fixed_sale`: fixed sales create INR-only receivable/revenue financial effects through `PostVoucherCommand(DjangoPostingEngine())` and a separate outgoing `CommodityMovement` from the owned/vault commodity account. The service is idempotent by source plus economic payload and keeps metal quantity out of financial currency paths. The next safe DEA slice is unfixed sale backend MVP: commodity issue plus open sale exposure with no false final monetary receivable/revenue before rate fixing.
- DEA Phase 4 unfixed sale backend MVP now exists in `apps.tenant_apps.dea.services.unfixed_sale`: unfixed sales create a posted commodity-intent voucher, outgoing `CommodityMovement`, and open sale `ExposureLine` without `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or `VoucherLine` rows. Final monetary AR/revenue waits for `post_sale_rate_fixing()`.
- DEA Phase 4 receipt/payment backend settlement MVP now exists in `apps.tenant_apps.dea.services.monetary_settlement`: customer receipts and supplier payments create `PaymentVoucher` records and financial voucher lines through `PostVoucherCommand(DjangoPostingEngine())`. Normal cash/bank settlement is monetary-only and must not create `CommodityMovement`, `ExposureLine`, or `RateFixing` rows.
- DEA Phase 4 karigar issue/receipt backend MVP now exists in `apps.tenant_apps.dea.services.karigar`: karigar issue and receipt create posted commodity-intent vouchers plus immutable `CommodityMovement` rows only. Issue moves metal from owned/vault to karigar custody; receipt moves metal from karigar custody back to owned/vault. It must not create financial journal/account rows, exposure lines, or rate fixings.
- DEA Phase 4/5 metal balance report backend MVP now exists in `apps.tenant_apps.dea.services.metal_balance_report`: `build_metal_balance_report()` wraps commodity position selectors into account rows, commodity totals, and fixed-status totals by commodity account, party, location, fixed status, and as-of date. It uses decimal metal quantities only, excludes synthetic adjustment/loss-gain offset accounts from default totals, and creates no financial rows.
- DEA Phase 4 financial trial balance hardening with commodity records present is complete for the current backend boundary: `ReportsService.trial_balance()` is covered against commodity movements, open exposures, standalone rate-fixing rows, and metal balance report reads affecting financial totals.
- DEA Phase 5 exposure report backend MVP now exists in `apps.tenant_apps.dea.services.exposure_report`: `build_exposure_report()` returns open/partially fixed exposure rows and totals by commodity/side/status from `ExposureLine`, with party, commodity, side, status, as-of, and optional reporting-only valuation support. It creates no financial rows and does not introduce valuation snapshots.
- DEA Phase 5 party account and ledger statement boundary hardening is complete: period close, ledger audit, and account audit are covered so monetary `LedgerStatement`/`AccountStatement` rows remain separate from commodity movements/exposures, which belong in metal/exposure reports. `Balance.get()` now aliases existing currency lookup and `Balance.__str__()` uses an explicit locale so existing audit paths work.
- DEA Phase 5 valuation report hardening is complete: `apps.tenant_apps.dea.services.valuation_report` combines metal balance positions and exposure rows into a read-only valuation report with status totals, explicit missing/unsupported-rate states, and no financial transaction or snapshot side effects.
- DEA Phase 6 first read-only commodity report UI slice is complete: `apps.tenant_apps.dea.views.commodity_reports` exposes metal balance, exposure, and valuation report pages from backend read models, links them from the DEA reports hub, and keeps the slice free of posting/editing workflows.
- DEA Phase 6 commodity report navigation polish is complete: the workspace sidebar and both DEA dashboard variants expose read-only commodity report links under existing accounting visibility. The next safe DEA slice is business-event UI design scaffolding only; do not wire mutation/posting screens until document states, preview behavior, permissions, and correction paths are designed.
- DEA Phase 6 business-event UI scaffold is complete: `/dea/business-events/` is GET-only, lists planned purchase/sale/rate-fixing/settlement/karigar workflows, links only to existing read-only reports, and keeps mutation/posting forms disabled. The next safe DEA slice is to define the business-event form and preview contract before wiring any POST screens to backend services.
- DEA Phase 6 business-event form/preview contract is documented in `docs/implementation/dea-business-event-form-preview-contract.md`. Future event UI should follow the pattern GET form -> read-only preview -> explicit confirm POST, keep preview side-effect free, and wire services only after preview/permission/idempotency behavior is tested. The next safe DEA slice is a fixed-purchase preview-only screen with confirm posting disabled.
- DEA Phase 6 fixed-purchase preview-only screen is complete: `/dea/business-events/fixed-purchase/` collects business facts, validates INR and commodity-account matching, renders side-effect-free accounting/commodity/exposure/inventory impact from `apps.tenant_apps.dea.services.business_event_preview`, and rejects/keeps disabled confirm posting. The next safe DEA slice is a minimal fixed-purchase business-event draft/source boundary before any confirm POST can call posting services.
- DEA Phase 6 fixed-purchase source-draft boundary is complete: `BusinessEventDraft` with tenant migration `0036` stores fixed-purchase source references, event dates, normalized economic payloads, preview payloads, and payload hashes. Fixed-purchase preview POST creates/updates that draft only; confirm posting remains disabled.
- DEA Phase 6 fixed-purchase posting-readiness gate is complete: the preview page now renders a read-only checklist for saved source, preview status, payload hash, open accounting period, authenticated actor, account/ledger/commodity-account mappings, and absence of an existing posted fixed-purchase voucher. It still does not call posting services or create accounting/commodity rows.
- DEA Phase 6 fixed-purchase confirm handoff service is complete: `apps.tenant_apps.dea.services.business_event_posting.confirm_fixed_purchase_draft()` locks the previewed `BusinessEventDraft`, rejects stale previews/readiness blockers, maps the normalized payload into `FixedPurchasePostingPayload`, and calls `post_fixed_purchase()` idempotently.
- DEA Phase 6 fixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/fixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls the handoff service, treats duplicate submits as existing success, and redirects to `/dea/business-events/fixed-purchase/<draft_id>/`, which shows business facts, posting status, voucher/journal links, ledger/account rows, and commodity movement rows. The next safe DEA slice is fixed-purchase stale/error UX hardening and draft list/navigation before cloning the pattern to unfixed purchase.
- DEA Phase 6 fixed-purchase stale/error UX and navigation hardening is complete: the business-events dashboard lists recent fixed-purchase drafts/results with posted/not-posted state, and blocked fixed-purchase detail pages link users back to re-preview. The next safe DEA slice is an unfixed-purchase preview-only screen that mirrors the fixed-purchase contract while keeping final monetary payable out of preview/posting until rate fixing.
- DEA Phase 6 unfixed-purchase preview-only screen is complete: `/dea/business-events/unfixed-purchase/` collects supplier party, metal weights/purity, commodity accounts, rate basis, and reporting valuation context; persists an `UNFIXED_PURCHASE` preview draft; and renders read-only commodity receipt plus open purchase exposure impact with no voucher, journal, ledger, account, movement, exposure, rate-fixing, or payment rows. The next safe DEA slice is an unfixed-purchase readiness/detail/navigation gate before enabling any confirm posting.
- DEA Phase 6 unfixed-purchase readiness/detail/navigation gate is complete: unfixed previews now show a read-only readiness checklist, `/dea/business-events/unfixed-purchase/<draft_id>/` shows draft facts, posting status, readiness, commodity impact, and exposure impact, and the business-events dashboard lists recent unfixed-purchase drafts. Confirm posting remains disabled. The next safe DEA slice is an unfixed-purchase confirm handoff service that locks a previewed draft and maps it to `UnfixedPurchasePostingPayload` without adding the UI confirm endpoint yet.
- DEA Phase 6 unfixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/unfixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_unfixed_purchase_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/unfixed-purchase/<draft_id>/`, which shows the posted commodity-intent voucher, commodity movement, and open exposure rows while still creating no financial journal, ledger, account, voucher-line, payment, or rate-fixing rows.
- DEA Phase 6 purchase rate-fixing preview/readiness screen is complete: `/dea/business-events/purchase-rate-fixing/` selects an open purchase `ExposureLine`, captures fixing date/weight/rate and monetary account/ledger targets, renders side-effect-free monetary payable and exposure-reduction impact, and keeps confirm posting disabled. Tests prove preview creates no new voucher, voucher-line, journal, ledger/account transaction, commodity movement, exposure, rate-fixing, or payment rows.
- DEA Phase 6 purchase rate-fixing source-draft boundary is complete: `BusinessEventDraft.EventType.PURCHASE_RATE_FIXING` with tenant migration `0038` stores rate-fixing source references, fixing dates, normalized economic payloads, preview payloads, and payload hashes. The purchase rate-fixing preview POST creates/updates only that draft/source row and renders a draft-based readiness checklist.
- DEA Phase 6 purchase rate-fixing confirm endpoint/result surface is complete: `/dea/business-events/purchase-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_purchase_rate_fixing_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/purchase-rate-fixing/<draft_id>/`, which shows business facts, posting status, rate fixing, voucher/journal links, ledger/account rows, exposure allocation, and no physical commodity movement.
- DEA Phase 6 sale rate-fixing confirm endpoint/result surface is complete: `/dea/business-events/sale-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_sale_rate_fixing_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/sale-rate-fixing/<draft_id>/`, which shows rate-fixing, voucher, journal, ledger/account, and exposure-allocation details without physical commodity movement.
- DEA Phase 6 receipt/payment preview-only screen is complete: `/dea/business-events/settlement/` captures customer receipt or supplier payment facts, persists only `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` `BusinessEventDraft` rows, and renders read-only cash/bank, party-account, payment, and commodity/no-commodity impact. Confirm posting remains disabled; tests prove preview creates no voucher, payment voucher, voucher-line, journal, ledger/account transaction, commodity movement, exposure, or rate-fixing rows.
- DEA Phase 6 receipt/payment detail/readiness/navigation gate is complete: `/dea/business-events/settlement/<draft_id>/` shows saved settlement draft facts, posting readiness, accounting impact, payment impact, and explicit no-commodity impact while keeping confirm posting disabled. The business-events dashboard links recent receipt/payment drafts to this detail page.
- DEA Phase 6 receipt/payment confirm handoff service is complete: `confirm_monetary_settlement_draft()` row-locks a previewed `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` draft, rejects stale payload/readiness blockers, maps normalized payload into `CustomerReceiptPayload` or `SupplierPaymentPayload`, and delegates to `post_customer_receipt()` / `post_supplier_payment()` idempotently.
- DEA Phase 6 receipt/payment confirm endpoint/result surface is complete: `/dea/business-events/settlement/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_monetary_settlement_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/settlement/<draft_id>/`, which shows payment voucher, voucher, journal, ledger/account rows, payment impact, and explicit no-commodity impact.
- DEA Phase 6 karigar issue/receipt preview screens are complete: `/dea/business-events/karigar/` captures issue or receipt custody facts, persists `KARIGAR_ISSUE` / `KARIGAR_RECEIPT` drafts, renders readiness, and shows commodity-only custody impact. Confirm posting remains disabled and no financial, exposure, rate-fixing, or payment rows are created by preview.
- DEA Phase 6 karigar confirm handoff service is complete: `confirm_karigar_movement_draft()` row-locks previewed karigar drafts, rejects stale/readiness-blocked payloads, maps to `KarigarIssuePayload` / `KarigarReceiptPayload`, and delegates to karigar posting idempotently. Tests prove duplicate submit safety and that the service creates one commodity-intent voucher plus one custody `CommodityMovement` with no financial, exposure, rate-fixing, or payment rows.
- DEA Phase 6 karigar confirm endpoint/result surface is complete: `/dea/business-events/karigar/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_karigar_movement_draft()`, handles duplicate submits idempotently, rejects member-role users, and shows the posted commodity-intent voucher plus custody `CommodityMovement` on the karigar detail page.
- DEA Phase 6 completion checkpoint is complete in `docs/implementation/dea-phase-6-business-event-checkpoint.md`. It records the current financial/commodity/exposure/rate-fixing/payment impact matrix for business events, focused verification results, remaining MVP gaps, and the recommendation to start Phase 7 with a cleanup readiness audit.
- DEA Phase 7 cleanup readiness audit has started in `docs/implementation/dea-phase-7-cleanup-readiness-audit.md`. Legacy/accountant DEA surfaces are classified before deletion, direct posting paths are inventoried, and `test_phase7_cleanup_readiness.py` guards key accountant route resolution plus absence of runtime imports from `posting/legacy_direct_write_engine.py`.
- DEA Phase 7 expense-post characterization is complete. `views/expense.py::post_expense_voucher()` is covered for direct-payment idempotency, duplicate journal prevention, and closed-period no-materialization before any route cleanup or facade refactor.
- DEA Phase 7 dead voucher-helper cleanup is complete. `views/voucher.py` no longer defines the old direct materialization helpers; voucher post/reverse remain routed through `PostVoucherCommand(DjangoPostingEngine())` and `reverse_posted_voucher()`, and `test_phase7_cleanup_readiness.py` guards against helper reintroduction.
- DEA Phase 7 accountant permission hardening has a shared helper in `apps.tenant_apps.dea.views.access`. Voucher hub, generic voucher CRUD/post/reverse, payment voucher CRUD, expense voucher CRUD/post, manual journal voucher CRUD, and opening-balance endpoints now require platform staff/superuser, workspace owner, or workspace role `Owner`, `Admin`, or `Accountant`.

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

The current SaaS UI information architecture audit lives at [ui/saas_information_architecture_audit.md](ui/saas_information_architecture_audit.md). It records the target separation between public/platform pages, authenticated global workspace management, tenant ERP, workspace settings/admin, and a future customer/member portal. Future UI route/template work should use that document as the baseline and proceed incrementally with compatibility aliases.

Phase 2 route/template standardization has begun with compatibility-only naming: `django_project.shared_urlpatterns` now defines service/public/auth/global route groups and keeps the old aggregate export, while templates can extend intent-specific base aliases (`base_public.html`, `base_auth.html`, `base_global.html`, `base_tenant.html`, `base_workspace_settings.html`, `base_customer_portal.html`). Do not remove legacy route inclusion or old layout files until route coverage and redirects are tested.

Phase 2.2 route intent cleanup keeps effective URLs unchanged but makes ownership explicit: `django_project.urls` is the active public-schema URLConf, `django_project.tenant_urls.TENANT_ERP_URLPATTERNS` groups tenant ERP prefixes, and `django_project.public_urls` is a legacy parity URLConf. Route boundary tests live in `django_project/test_route_intent.py`. The next safe SaaS IA slice is Phase 2.3 template layout cleanup, not navigation redesign or route moves.

Phase 2.3 template layout cleanup moved clear first-party layout stragglers to intent aliases without changing URLs or navigation. `django_project/test_template_layout_intent.py` guards low-level layout usage and alias block contracts. Remaining direct `layouts/base.html` usage should stay limited to infrastructure wrappers (`base_public`, `base_auth`, `base_customer_portal`, low-level layout files, allauth/slick wrappers, and legacy `_base`). The next safe slice is Phase 2.4 workspace settings layout separation.

Phase 2.4 workspace settings layout separation moved clear workspace-admin/settings templates to `base_workspace_settings.html` and added no-op `workspace_settings_sidebar` include points in `layouts/management.html`. This does not change URLs or visible navigation. The next safe slice is Phase 2.5 shell render smoke tests before any navigation/sidebar visual changes.

Phase 2.5 shell render smoke tests live in `django_project/test_shell_render_smoke.py` and render synthetic children for the public, auth, global, workspace-settings, and tenant shell aliases. These tests should be kept green before Phase 3 navigation/sidebar changes. The next safe slice is route/template inventory documentation or a similarly non-behavioral cleanup checkpoint.

Phase 2.6 route/template inventory documentation lives in `docs/ui/route_template_inventory.md`. It records current URLConf ownership, route-family ownership, shell aliases, known mixed boundaries, and guard tests. The next safe SaaS IA work is Phase 3 navigation and workspace switcher planning while keeping compatibility routes in place.

Phase 3.1 navigation and workspace switcher planning lives in `docs/ui/navigation_workspace_switcher_plan.md`. The accepted sidebar ADRs still apply: `templates/components/navigation/sidebar.html` remains the live tenant sidebar source of truth, `django_project/navigation.py` is future-only, and the next safe SaaS IA slice is to replace the inline topbar workspace dropdown with the reusable `components/navigation/workspace_switcher.html` partial while preserving current route behavior.

Phase 3.2 workspace switcher reuse is complete: `templates/components/navigation/main_nav.html` includes `components/navigation/workspace_switcher.html` with `workspace_switcher_variant="navbar"`, and the partial keeps its standalone mode for other surfaces. Authenticated global and tenant shell smoke tests cover switcher rendering. The next safe SaaS IA slice is Phase 3.3 settings sidebar extraction into `components/navigation/workspace_settings_sidebar.html`, starting with desktop links before mobile duplication cleanup.

Phase 3.3 desktop settings-sidebar extraction is complete: `templates/layouts/management.html` delegates desktop workspace settings/team/invitation links to `components/navigation/workspace_settings_sidebar.html` with `workspace_settings_sidebar_variant="desktop"`. The mobile management offcanvas intentionally still has inline duplicate links. The next safe SaaS IA slice is Phase 3.4 to add a mobile variant to the same partial and remove the mobile duplicate links.

Phase 3.4 mobile settings-sidebar extraction is complete: `templates/layouts/management.html` delegates mobile workspace settings/team/invitation links to `components/navigation/workspace_settings_sidebar.html` with `workspace_settings_sidebar_variant="mobile"`. The next safe SaaS IA slice is Phase 3.5 account-management sidebar extraction for the remaining duplicated account links in the management shell.

Phase 3.5 account-management sidebar extraction is complete: `templates/layouts/management.html` delegates desktop and mobile account links to `components/navigation/account_sidebar.html` with `account_sidebar_variant="desktop"` or `"mobile"`. The next safe SaaS IA slice is Phase 3.6 workspace-manager sidebar extraction for the remaining duplicated `My Workspaces` and `New Workspace` links.

Phase 3.6 workspace-manager sidebar extraction is complete: `templates/layouts/management.html` delegates desktop and mobile `My Workspaces` / `New Workspace` links to `components/navigation/workspace_manager_sidebar.html` with desktop/mobile variants. The next safe SaaS IA slice is Phase 3.7 management shell wording cleanup and final navigation partial inventory before moving to visual polish.

Phase 3.7 management shell cleanup is complete: `templates/layouts/management.html` has clean ASCII shell comments, obsolete duplicate-sidebar wording is removed, and `docs/ui/navigation_workspace_switcher_plan.md` records the final management navigation partial inventory. The next safe SaaS IA slice is Phase 3.8 management-shell compatibility review before visual polish.

Phase 3.8 management-shell compatibility review is complete: `django_project/test_shell_render_smoke.py` renders an authenticated owner management shell and asserts key labels plus route targets still resolve after partialization. The next safe SaaS IA slice is Phase 3.9 visual-polish checklist for the global/settings management shell before CSS/layout changes.

Phase 3.9 management shell visual-polish checklist lives at `docs/ui/management_shell_visual_polish_checklist.md`. It defines compatibility constraints, visual review criteria, and the Phase 3.10 recommendation before CSS/layout-density changes. The next safe SaaS IA slice is Phase 3.10 first management-shell visual polish pass with route names, labels, partial ownership, and permission behavior preserved.

Phase 3.10 first management-shell visual polish pass is complete: `layouts/management.html` uses restrained neutral control-plane styling, management sidebar partials share `mgmt-nav-link`, mobile links have active-state parity with desktop, and offcanvas styling moved away from inline purple treatments. The next safe SaaS IA slice is Phase 3.11 browser/screenshot review for desktop/mobile overflow and spacing.

Phase 3.11 rendered management-shell review is complete: the generated management shell HTML showed the control-plane shell was constrained by the default `container-lg mt-4` wrapper. `layouts/base.html` now provides a backward-compatible `main_wrapper_class` block, and `layouts/management.html` overrides it with `container-fluid p-0 mt-0`. Local Chrome headless screenshot attempts did not create files in this environment, so the next safe SaaS IA slice is Phase 3.12 reproducible browser/live-server visual smoke setup before more visual polish.

Phase 3.12 reproducible management-shell visual smoke coverage is complete: `django_project/test_management_shell_visual_smoke.py` renders an authenticated owner management shell and guards the full-width wrapper, desktop/mobile management nav classes, active states, and control-plane route safety without new browser dependencies. The next safe SaaS IA slice is Phase 3.13 management-shell CSS extraction to a dedicated static stylesheet without behavior changes.

Phase 3.13 management-shell CSS extraction is complete: `static/css/management.css` owns the management shell styles, `layouts/management.html` loads it through `{% static %}`, and `mgmt_extra_css` remains available. Synthetic shell smoke rendering now overrides staticfiles storage to avoid stale collected-manifest failures for newly added static assets. The next safe SaaS IA slice is Phase 3.14 static asset readiness checks for the new stylesheet.

Phase 3.14 static asset readiness is complete: `findstatic css/management.css --verbosity 2` finds the management stylesheet in project static files, `collectstatic --dry-run --noinput --verbosity 1` succeeds and includes `css/management.css`, and `test_management_shell_visual_smoke.py` guards staticfiles discovery. The next safe SaaS IA slice is Phase 3.15 final Phase 3 navigation/management-shell review and commit preparation.

Phase 3.15 final Phase 3 navigation/management-shell review is complete in `docs/ui/phase3_navigation_management_shell_review.md`. The review confirms route names, labels, permissions, and partial ownership are preserved, records verification commands, and recommends one phase-level commit before starting Phase 4 invitation/team flow cleanup.

Phase 4.1 invitation/team flow cleanup has started with documentation and guard tests only. `docs/ui/invitation_team_flow_cleanup_plan.md` maps incoming invitations as a global account surface, sent invitations/team members as workspace settings surfaces, and records current URL compatibility constraints before any route aliases or behavior changes. `django_project/test_invitation_team_flow_intent.py` guards current route names/paths, shell intent, and the known unbased invite-success template gap.

Phase 4.2 route-intent cleanup is complete without URL breakage: `apps.orgs.urls` now groups workspace manager, account invitation, workspace invitation, team member, and account profile route lists explicitly, then aggregates them in the same compatibility order. `django_project/test_invitation_team_flow_intent.py` guards the grouping and effective route order. The next safe slice is Phase 4.3 copy/heading clarification for incoming versus sent invitations, including existing mojibake cleanup, while keeping route names and form actions unchanged.

Phase 4.3 copy/heading clarification is complete without route or form-action changes. Received invitations are labelled "Invitations for You", sent workspace invitations are labelled "Sent Workspace Invitations", team invite copy consistently says team member/workspace invitation, and known invitation/team mojibake has focused guard coverage. The next safe slice is Phase 4.4 workspace-scoped redirect cleanup, especially the unbased invite-success page and sent-invitation return path.

Phase 4.4 workspace-scoped redirect cleanup is complete without removing compatibility URLs. `team_invite` now redirects to `team_invite_success` with `workspace_id` query context, `invite_success` uses the workspace settings shell and links back to sent invitations in the same workspace context, `team_invitations_list` honors explicit `workspace_id` query context with access checks, and invitation revoke redirects back to the revoked invitation's workspace sent-list context. The next safe slice is Phase 4.5 accept/decline characterization for direct django-invitations accept links versus the custom orgs accept/decline flow.

Phase 4.5 accept/decline characterization is complete. The direct `team_accept_invitation` route still uses `invitations.views.AcceptInvite`; with current settings it confirms on GET, accepts before signup, and redirects to `account_signup`. The `invite_accepted` signal can create membership or pending invitation intent, but it does not select active workspace, emit orgs audit, or redirect to workspace dashboard. The custom `team_invitations` POST flow remains the product-complete path through `control_plane.accept_invitation`. The next safe slice is Phase 4.6 authorization coverage for invite, revoke, role change, remove member, self-leave, and selected-workspace fallback.

Phase 4.6 authorization coverage is complete. `InvitationTeamAuthorizationTests` covers invite access checks, invite role-grant policy enforcement, unauthorized revoke denial, team remove/change-role workspace gates, sole-owner self-leave blocking, and selected-workspace sent-invitation fallback requiring `team_invite`. The next safe slice is to decide Phase 4.7 scope: either add canonical compatibility aliases for account/settings routes or first wrap the direct invitation accept URL with an orgs-owned adapter now that authorization characterization is in place.

Phase 4.7 direct invitation accept adapter is complete. The existing `team_accept_invitation` route path/name now points to `apps.orgs.views.team_accept_invitation`: authenticated matching users use the orgs control-plane accept path, active workspace selection, and workspace-dashboard redirect; unauthenticated users still fall back to `invitations.views.AcceptInvite`; authenticated email mismatches fail closed. Canonical route aliases are deferred until after the Phase 4 set is reviewed and committed. The next safe step is Phase 4 final review and phase-level commit preparation.

Phase 4 final review is complete in `docs/ui/phase4_invitation_team_flow_review.md`. It records compatibility preservation, authorization coverage, verification commands, and deferred canonical route aliases. After commit, the next safe SaaS IA work is either canonical route aliases for account/settings routes or Phase 5 broader authorization cleanup.

Canonical route aliases are phase-reviewed in `docs/ui/canonical_route_aliases_phase_review.md`. Additive aliases now expose `/app/`, `/app/workspaces/`, `/app/workspaces/new/`, `/app/invitations/`, `/app/memberships/`, and `/workspace/<id>/settings/...` paths for workspace settings/team/invitations while preserving existing `/orgs/...` routes and names. `django_project/test_route_intent.py` guards alias resolution and legacy route stability. Management navigation now uses `app_workspaces`, `app_workspace_create`, `app_invitations`, `workspace_settings_home`, `workspace_settings_preferences`, `workspace_settings_team`, `workspace_settings_invite`, and `workspace_settings_invitations` while keeping old route names as active-state compatibility. Workspace-scoped sent-invitation returns now use `workspace_settings_invitations` for invite POST success, invite-success back links, and revoke returns.

Phase 5.1 authorization cleanup is documented in `docs/ui/authorization_cleanup_inventory.md` with guard tests in `django_project/test_authorization_surface_intent.py`. The baseline maps public, global authenticated, workspace settings, tenant ERP, and future customer/member portal authorization surfaces; guards the route-plane split; and records known login-only tenant app gaps before behavior changes. Phase 5.2 added canonical settings path extraction to `SecureWorkspaceMiddleware`, so `/workspace/<id>/settings/...` aliases now participate in path workspace resolution alongside legacy `/orgs/workspace/<id>/...` and `/orgs/company/<id>/...` paths. Phase 5.3 added middleware workspace-required coverage for every current tenant ERP prefix, including `party`, `data-tools`, and `notify-v2`. Phase 5.4 added `apps.tenant_apps.party.access` with Party workspace, permission, action, decorator, and CBV mixin helpers plus focused helper tests. Phase 5.5 converted Party list/detail to the Party view action guard and Party export to the Party export action permission. Phase 5.6 converted Party create/customer-convert to the Party create action guard and Party update to the Party edit action guard. Phase 5.7 converted Party profile-photo, contact-method, and address mutations to the Party edit action guard. Phase 5.8 converted Party identifier, document, and relationship mutations to the Party edit action guard. Phase 5.9 converted Party role add/end and duplicate merge to the Party edit action guard. Phase 5 Party authorization review is documented in `docs/ui/phase5_party_authorization_review.md`. Broad Contact authorization cleanup is intentionally skipped because Party is replacing Contact. Phase 5.10 added `apps.tenant_apps.product.access` with Product workspace, permission, action, decorator, and CBV mixin helpers backed by generic data permissions, and converted product/product type/generated product/variant/product variant catalog paths to Product action guards. Phase 5.11 converted Product stock list/detail/search, transaction/statement lists, split/merge/delete, stock-in/stock-out, physical audit, opening balance import, and import template paths to Product action guards; `stock_select` now reads `?q=` safely for the current route. Phase 5.12 converted Product pricing, price override, image, and attribute views to Product action guards. Phase 5.13 added Rates and Notify shared access helpers and converted rate/rate-source, legacy Notify, and Notify v2 user-facing routes to action guards while keeping the external WhatsApp webhook public. Phase 5.14 closes SaaS IA authorization cleanup for current Party, Product, Rates, Notify, and utility data-tool route groups. DEA/Girvi remain separate domain-specific permission tracks, and the next safe slice is a Phase 5 review/commit checkpoint before Phase 6 onboarding.

Phase 6 onboarding is phase-reviewed in `docs/ui/phase6_onboarding_review.md`. The completed scope includes onboarding inventory, read-only workspace setup checklist service, dashboard checklist card, workspace settings setup page, completion redirects to setup, onboarding workspace creation through orgs control-plane, onboarding team invitations through orgs control-plane, and user-specific setup completion/dismiss state through `WorkspaceSetupState`. Existing `/onboarding/...` URLs remain compatibility entrypoints, setup remains advisory/non-blocking, and the new setup-state migration is shared/control-plane data. The next safe action is to commit Phase 6 as a single phase-level commit, then start Phase 7 modern fintech UI polish.

Phase 7.1 modern fintech UI polish planning is complete in `docs/ui/phase7_modern_fintech_ui_polish_plan.md`, with guard tests in `django_project/test_phase7_ui_polish_intent.py`. Phase 7 starts with management/workspace setup surfaces and keeps routes, permissions, middleware, schemas, and advisory setup behavior unchanged. The next safe SaaS IA slice is Phase 7.2: add a small management/setup visual vocabulary to `static/css/management.css` and apply it to `templates/company/workspace_setup.html` only.

Phase 7.2 workspace setup visual vocabulary is complete: `static/css/management.css` owns setup hero, progress, task, action, and status classes, and `templates/company/workspace_setup.html` uses them without changing canonical setup-state forms, checklist links, settings-shell ownership, or advisory behavior. The next safe SaaS IA slice is Phase 7.3: polish the workspace dashboard setup card using the new vocabulary where practical, while preserving dashboard visibility and dismiss behavior.

Phase 7.3 dashboard setup-card polish is complete: `templates/company/workspace_dashboard.html` loads `css/management.css` and uses the setup hero, progress, task, action, and status classes while preserving `setup_state.should_show_dashboard_card`, canonical setup navigation, dismiss POST behavior, and checklist action URLs. The next safe SaaS IA slice is Phase 7.4: extract repeated setup checklist markup into a shared partial only if behavior remains exactly unchanged.

Route-map clarification: SaaS IA Phase 2 is complete for route/template intent standardization, not for the full target `/w/<workspace_slug>/...` route map in the IA audit. Current canonical control-plane aliases are `/app/...` and `/workspace/<id>/settings/...`; `/w/<workspace_slug>/...` should be a separate future alias/redirect phase. Preferences visibility is now explicit for `Owner`, `Admin`, and platform `Superuser` users through `workspace_settings_preferences`.

Phase 7.4 setup checklist task partial extraction is complete: `templates/components/setup/setup_checklist_task.html` owns repeated setup task/status/action markup, and both `workspace_setup.html` and `workspace_dashboard.html` include it with page-specific heading/id context. The next safe SaaS IA slice is Phase 7.5: review and polish the global workspace selector/workspace-list surface without changing route behavior or membership checks.

Phase 7.5 global workspace selector polish is complete: `templates/company/workspace_home.html` now reads as a workspace manager with summary tiles, active workspace state, canonical create/invitations/settings links, and preserved `workspace_select` switching plus invitation accept/decline POST behavior. The next safe SaaS IA slice is Phase 7.6: public/auth page polish planning and guard tests before visual changes.

Phase 7.6 public/auth route-template inventory and guard tests are complete: `docs/ui/phase7_public_auth_polish_plan.md` records current public pages, allauth paths, django-invitations entrypoints, shell ownership, missing pricing/short-auth aliases, and missing public templates. `django_project/test_phase7_public_auth_intent.py` guards that inventory. The next safe SaaS IA slice is Phase 7.7: first public/auth visual polish pass while preserving current allauth/social-auth/invitation behavior.

Phase 7.7 first public/auth visual polish pass is complete: `static/css/public.css` owns shared public/auth styling, `base_public.html` and `base_auth.html` load it with full-width shell wrappers, `templates/pages/home.html` now presents a product-specific SaaS ERP funnel without inline CSS or remote placeholder imagery, and login/signup/password-reset pages share an auth panel/card layout while preserving allauth/social-auth behavior. The next safe SaaS IA slice is Phase 7.8: render-review public/auth pages and make only focused overflow/spacing fixes if needed.

Phase 7.8 public/auth render review is complete: render smoke coverage now exercises `/`, `/accounts/login/`, `/accounts/signup/`, and `/accounts/password/reset/`. Auth pages no longer crash when a Google client id exists but no django-allauth `SocialApp` is configured; `google_oauth_context` exposes `GOOGLE_OAUTH_ENABLED`, and login/signup templates conditionally render Google auth CTAs. The next safe SaaS IA slice is Phase 7.9: tenant ERP dashboard/navigation density polish without changing business workflows.

Phase 7.9 tenant ERP dashboard/navigation density polish is complete: `static/css/workspace.css` owns tenant shell/sidebar/dashboard classes, `base_tenant.html` loads it, tenant layout/sidebar inline style blocks are removed, and `templates/company/workspace_dashboard.html` uses denser page-header, stat-grid, and quick-action classes while preserving existing routes, permission conditions, setup-card behavior, tenant isolation, and posting workflows.

Phase 7.10 first-pass UI polish review is complete in `docs/ui/phase7_modern_fintech_ui_polish_review.md`. Phase 7 should be treated as UI infrastructure and surface cleanup, not the final high-fidelity fintech redesign. Deeper visual redesign, pricing/short-auth/invitation aliases, missing public templates, and the full `/w/<workspace_slug>/...` target route-map rollout remain separate future work. The next safe SaaS IA action is to commit Phase 7, then start Phase 8 regression consolidation.

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

DEA Phase 7 cleanup readiness audit has started, expense-post characterization is complete, dead voucher helper definitions have been removed, and the first accountant permission boundary hardening is complete. The next recommended DEA slice is navigation cleanup: normal staff should be guided to business events and reports, while accountant/admin users retain manual voucher, payment, expense, journal, opening-balance, period, and diagnostic routes.

## Documentation Memory

- Canonical docs live under `docs/`.
- Historical source docs live under `docs/archive/`.
- Accepted architecture decisions live under `docs/adr/`.
- Every markdown file under `docs/` should start with frontmatter.
- Every doc should link back to `README.md` where practical for navigation.
