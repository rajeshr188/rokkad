---
status: active
owner: project
updated: 2026-06-26
tags: [roadmap, dea, accounting, commodity, refactor]
related:
  - ../audits/dea_core_accounting_commodity_analysis.md
  - ../AGENT_MEMORY.md
  - ../STATUS.md
  - ../constitution.md
  - ../domain/accounting.md
  - ../implementation/dea-business-event-form-preview-contract.md
  - ../implementation/dea-phase-6-business-event-checkpoint.md
  - ../implementation/dea-phase-7-cleanup-readiness-audit.md
---

# DEA Commodity Accounting Refactor Plan

## Summary

This roadmap converts the DEA commodity accounting audit into implementation-ready phases. The core rule is sequencing: protect financial accounting correctness first, then define lifecycle semantics, then introduce commodity accounting side-by-side, then build business operations and UI.

Do not start by adding commodity UI or replacing balance views. The first work must make the current financial accounting behavior observable, tested, and guarded against metal-as-currency corruption.

## Guardrails

- Do not represent gold, silver, or other metals as financial currencies.
- Do not put commodity quantity into `MoneyField`, `amount_currency`, `ClosingBalance_currency`, or financial trial balance logic.
- Do not mutate posted journal entries, ledger transactions, account transactions, or future commodity movements in place.
- Do not replace existing SQL balance views until tests and replacement selectors exist.
- Prefer small, reversible tasks with characterization tests before refactors.
- Tenant app model changes must use `migrate_schemas` guidance, not plain `migrate`.

## First 5 Implementation Tasks

These are the safest, highest-value starting points.

1. **DEA Financial Posting Characterization Tests**
   - Proves current journal, ledger, account, and voucher behavior before any refactor.

2. **DEA Balance View Characterization Tests**
   - Locks down current `ledger_balances` and `account_balances` behavior before any SQL/view changes.

3. **Metal-Like Currency Data Audit**
   - Adds a read-only check/command or documented SQL to detect existing currency contamination.

4. **Trial Balance Financial-Only Regression Tests**
   - Proves trial balance is a base-currency financial report and cannot include commodity quantities.

5. **Lifecycle ADR Draft**
   - Locks business document, voucher, journal entry, reversal, correction, and idempotency semantics before code churn.

## Implementation Progress

Completed:

- Phase 1 safety work has started with financial posting characterization, balance-view characterization, suspicious currency-code audit coverage, trial-balance financial-only regression coverage, and monetary currency guardrail design.
- Phase 2 Task 2.1 is complete in `docs/adr/2026-06-24-dea-document-voucher-journal-lifecycle.md`.
- Phase 2 Task 2.2 has started with posted immutability coverage for supported `JournalEntry`, `VoucherLine`, `LedgerTransaction`, and `AccountTransaction` update/delete paths.
- Phase 2 Task 2.3 is complete for the current MVP service/engine path: duplicate posts of the same voucher return the existing journal entry, reposting the same document payload returns the existing voucher/journal entry, and changed economic payloads reverse the previous posting and create a corrected voucher.
- Phase 2 Task 2.4 is complete in `docs/implementation/dea-canonical-posting-path.md`; direct `views/voucher.py` materialization helpers and `legacy_direct_write_engine.py` are marked legacy pending characterization and replacement.
- Phase 2 Task 2.5 is complete in `docs/implementation/dea-reversal-correction-contract.md`; the target `services/reversal.py` API, idempotency rules, period policy, audit requirements, and future commodity sidecar reversal rules are defined.
- Phase 2 reversal implementation has started: `apps/tenant_apps/dea/services/reversal.py` now provides `reverse_posted_voucher()` with typed result/errors, audit logging, transaction wrapping, and idempotent duplicate-reversal behavior. `DjangoPostingEngine.reverse_voucher()` is now a compatibility wrapper around that service.
- Phase 2 reversal caller migration has started: `apps/tenant_apps/dea/facades/payments.py::reverse_payment_by_marker()` now calls `reverse_posted_voucher()` directly and focused tests verify payment marker reversal keeps `PaymentVoucher.posted` synchronized.
- Phase 2 reversal caller migration now also covers `apps/tenant_apps/dea/views/voucher.py::reverse_voucher()`: the route calls `reverse_posted_voucher()` instead of materializing reversal rows directly, and route-level characterization tests cover posted-voucher reversal plus draft rejection.
- Phase 2 canonical posting caller migration now covers `apps/tenant_apps/dea/views/voucher.py::post_voucher()`: the route delegates to `PostVoucherCommand(DjangoPostingEngine())` instead of direct period/journal/status mutation. `PostVoucherCommand` now has a controlled stored-voucher-line fallback for manual voucher types with no registered posting rule, using `materialize_journal_from_voucher_lines()` behind the command boundary.
- Phase 3 has started with `docs/adr/2026-06-24-dea-commodity-accounting-layer.md`, which accepts a side-by-side DEA commodity layer separate from financial currency accounting.
- Phase 3 schema planning is complete in `docs/implementation/dea-commodity-model-schema.md`, covering the proposed fields, constraints, indexes, lifecycle rules, tenant rollout notes, and tests for `Commodity`, `CommodityAccount`, `CommodityMovement`, `ExposureLine`, `RateFixing`, and rate-fixing allocations.
- Phase 3 first model slice is complete: `Commodity` and `CommodityAccount` now exist with a tenant migration, admin registration, model exports, validation, and focused tests. No movement, exposure, rate-fixing, posting service, report, or UI behavior was added in this slice.
- Phase 3 default commodity setup is complete: `seed_default_commodities()` and the `seed_dea_commodities` management command now create/repair tenant-local `GOLD` and `SILVER` commodity masters idempotently, with focused command/service tests.
- Phase 3 commodity movement model is complete: immutable `CommodityMovement` rows now capture source, optional voucher, commodity, gross weight, purity, fine weight, from/to commodity accounts, fixed status, valuation metadata, idempotency key, and reversal linkage without creating financial ledger/account rows.
- Phase 3 exposure/rate-fixing model foundations are complete: `ExposureLine`, `RateFixing`, and `RateFixingAllocation` now exist with tenant migration, admin diagnostics, quantity/status/currency validation, fixing allocation guardrails, and focused tests. No financial posting, business workflow, report, selector, or UI integration was added.
- Phase 3 commodity posting service skeleton is complete: `apps/tenant_apps/dea/services/commodity_posting.py` creates idempotent `CommodityMovement` and `ExposureLine` records from structured payloads with deterministic source/economic-payload keys. It remains side-by-side and is not integrated with financial posting, reports, workflows, or UI.
- Phase 3 commodity position selectors are complete: `apps/tenant_apps/dea/selectors/commodity.py` computes movement-derived metal balances by commodity account, party, location, fixed status, and as-of date with reversal offsets, using decimal quantity fields rather than `Money`.
- Phase 3 MVP commodity valuation policy is complete in `docs/implementation/dea-commodity-valuation-policy.md`: valuation is reporting-only for MVP, uses rates as market inputs, defaults to INR, defines missing-rate behavior, and defers `ValuationSnapshot`, unrealized gain/loss, and financial journal effects.
- Phase 3 valuation service/read-model foundation is complete: `apps/tenant_apps/rates/facade.py` exposes a narrow commodity valuation rate lookup and `apps/tenant_apps/dea/services/valuation.py` values position rows and exposure lines with explicit valuation statuses while creating no financial rows.
- Phase 4 Task 4.1 backend MVP slice is complete: `apps/tenant_apps/dea/services/fixed_purchase.py` posts a fixed commodity purchase by creating stored financial voucher lines through `PostVoucherCommand(DjangoPostingEngine())` and a side-by-side fixed `CommodityMovement` in one atomic service path. The slice covers INR-only fixed purchase, supplier monetary account line, inventory/payable ledger transaction, commodity movement idempotency, duplicate-post return, changed-payload rejection until correction/reversal exists, and rollback when commodity validation fails. UI, taxes, FX purchase policy, operational purchase document modeling, and fixed-purchase reversal sidecar are still deferred.
- Phase 4 Task 4.2 backend MVP slice is complete: `apps/tenant_apps/dea/services/unfixed_purchase.py` posts an unfixed commodity purchase as a posted commodity-intent voucher, immutable `CommodityMovement`, and open purchase `ExposureLine` without creating `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or voucher lines. The slice covers period validation, source/economic-payload idempotency, changed-payload rejection until correction/reversal exists, rollback on exposure validation failure, and explicit proof that final monetary payable is not created before rate fixing. UI, taxes, advances/provisional accrual policy, operational purchase document modeling, partial fixing UI, and commodity sidecar reversal remain deferred.
- Phase 4 Task 4.3 rate fixing backend MVP slice is complete for purchase and sale: `apps/tenant_apps/dea/services/rate_fixing.py` fixes all or part of an open purchase or sale `ExposureLine`, creates a `RateFixing` plus `RateFixingAllocation`, posts financial voucher lines through `PostVoucherCommand(DjangoPostingEngine())`, and reduces/closes the exposure atomically. Purchase fixing creates supplier monetary payable; sale fixing creates customer receivable/revenue. The slice covers INR-only fixing, full and partial fixing, idempotency, over-fixing rejection, closed-period rejection, and rollback before financial/commodity state changes. UI, taxes, advanced partial-settlement allocation, and reversal sidecar remain deferred.
- Phase 4 Task 4.4 backend MVP slice is complete: `apps/tenant_apps/dea/services/fixed_sale.py` posts a fixed commodity sale by creating stored financial voucher lines through `PostVoucherCommand(DjangoPostingEngine())` and a side-by-side fixed `CommodityMovement` that issues metal out of the owned/vault commodity account. The slice covers INR-only fixed sale, customer monetary account line, receivable/revenue ledger transaction, outgoing commodity movement, idempotency, changed-payload rejection until correction/reversal exists, and rollback when commodity validation fails. UI, taxes, inventory costing/COGS policy, stock availability checks, operational sale document modeling, and fixed-sale reversal sidecar are still deferred.
- Phase 4 Task 4.5 backend MVP slice is complete: `apps/tenant_apps/dea/services/unfixed_sale.py` posts an unfixed commodity sale as a posted commodity-intent voucher, outgoing immutable `CommodityMovement`, and open sale `ExposureLine` without creating `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or voucher lines. The slice covers period validation, source/economic-payload idempotency, changed-payload rejection until correction/reversal exists, rollback on exposure validation failure, and explicit proof that final monetary receivable/revenue is not created before rate fixing. UI, taxes, inventory costing/COGS policy, operational sale document modeling, partial fixing UI, and commodity sidecar reversal remain deferred.
- Phase 4 Task 4.6 backend MVP slice is complete: `apps/tenant_apps/dea/services/monetary_settlement.py` posts customer receipts and supplier payments as `PaymentVoucher` plus stored financial voucher lines through `PostVoucherCommand(DjangoPostingEngine())`. Customer receipts debit cash/bank and credit customer receivable; supplier payments debit supplier payable and credit cash/bank. The slice covers INR-only settlement, source/reference idempotency, changed-payload rejection for the same reference, closed-period rejection, and explicit proof that normal monetary settlement creates no `CommodityMovement`, `ExposureLine`, or `RateFixing` rows. UI, allocation screens, metal-in-kind settlement, invoice auto-allocation, and advanced reconciliation remain deferred.
- Phase 4 Task 4.7/4.8 backend MVP slice is complete: `apps/tenant_apps/dea/services/karigar.py` posts karigar issue and receipt as posted commodity-intent vouchers plus immutable `CommodityMovement` rows only. Issue moves metal from owned/vault account to karigar custody; receipt moves metal from karigar custody back to owned/vault. The slice covers custody-account party validation, period validation, source/economic-payload idempotency, changed-payload rejection until correction/reversal exists, and explicit proof that karigar custody movement creates no `JournalEntry`, `VoucherLine`, `LedgerTransaction`, `AccountTransaction`, `ExposureLine`, or `RateFixing` rows. UI, wastage policy, finished-goods transformation, making-charge accounting, inventory lot costing, and commodity sidecar reversal remain deferred.
- Phase 4/5 Task 4.9 backend MVP slice is complete: `apps/tenant_apps/dea/services/metal_balance_report.py` exposes a selector-backed metal balance report read model over `CommodityMovement` positions by commodity account, party, location, fixed status, and as-of date. The report returns account rows, commodity totals, and fixed-status totals using decimal quantity fields only; default totals exclude synthetic adjustment/loss-gain offset accounts while still allowing explicit account inspection. No financial journal, voucher-line, ledger, account, valuation-snapshot, or P&L behavior was added.
- Phase 4 Task 4.10 financial trial balance hardening is complete for the current backend boundary: `apps/tenant_apps/dea/test_financial_reports.py` now proves `ReportsService.trial_balance()` remains unchanged when `CommodityMovement`, `ExposureLine`, `RateFixing`, and metal balance report rows exist in the same tenant. The trial balance continues to read posted financial `LedgerTransaction.amount_base` rows only, in INR, while commodity quantities remain separate.
- Phase 5 exposure report backend MVP is complete: `apps/tenant_apps/dea/services/exposure_report.py` exposes open/partially fixed `ExposureLine` rows by party, commodity, side, status, and as-of date, with totals by commodity/side/status and optional valuation via `value_exposure_lines()`. The report is read-only, defaults to active exposure, creates no financial rows, and does not introduce valuation snapshots or settlement allocation complexity.
- Phase 5 party account and ledger statement boundary hardening is complete: `apps/tenant_apps/dea/tests/test_statement_boundary.py` proves period close, ledger audit, and account audit create monetary `LedgerStatement`/`AccountStatement` rows while commodity movements and exposure rows remain in metal/exposure reports. This slice also added narrow compatibility fixes to `Balance.get()` and `Balance.__str__()` so existing audit paths work without changing monetary balance semantics.
- Phase 5 valuation report hardening is complete: `apps/tenant_apps/dea/services/valuation_report.py` combines metal position rows and exposure rows into a read-only valuation report with status totals. Focused tests cover valued positions/exposures, missing-rate behavior, unsupported currency/purity statuses, and no financial journal, voucher-line, rate-fixing, movement, exposure, or rate side effects.
- Phase 6 first read-only report UI slice is complete: `apps/tenant_apps/dea/views/commodity_reports.py` exposes metal balance, exposure, and valuation report pages from backend read models, with links from the DEA reports hub and route-level tests. This slice intentionally adds no posting, editing, reversal, export, or business document workflows.
- Phase 6 commodity report navigation polish is complete: the shared workspace sidebar now exposes a `Commodity Reports` shortcut under accounting visibility, and both DEA dashboard variants link to the read-only metal balance, exposure, and valuation reports. Route tests cover report hub, dashboard, enhanced dashboard, and sidebar discovery.
- Phase 6 business-event UI scaffold is complete: `apps/tenant_apps/dea/views/business_events.py` exposes a GET-only `/dea/business-events/` dashboard listing fixed/unfixed purchase, rate fixing, fixed/unfixed sale, receipt/payment, karigar issue/receipt, metal balance, exposure, valuation, and financial trial balance entry points. The scaffold links only to existing read-only reports where available, marks mutation forms as not wired, and route tests prove it creates no voucher, journal, account, ledger, commodity movement, exposure, or rate-fixing side effects.
- Phase 6 business-event form/preview contract is complete in `docs/implementation/dea-business-event-form-preview-contract.md`: future screens must collect business facts, build read-only previews, show accounting/commodity/exposure/inventory impact, and hand off to existing backend services only from explicit confirm POST paths.
- Phase 6 fixed-purchase preview-only screen is complete: `/dea/business-events/fixed-purchase/` renders a business-facts form, validates INR monetary fields and commodity-account matching, builds a read-only accounting/commodity/exposure/inventory preview through `apps/tenant_apps/dea/services/business_event_preview.py`, and keeps confirm posting disabled. Route tests prove GET, preview POST, and attempted confirm POST create no voucher, voucher line, journal, ledger transaction, account transaction, payment voucher, commodity movement, exposure, or rate-fixing rows.
- Phase 6 fixed-purchase source-draft boundary is complete: `BusinessEventDraft` now persists previewed fixed-purchase source references, event dates, normalized economic payloads, preview payloads, and payload hashes through tenant migration `dea.0036`. The fixed-purchase preview POST creates or updates only this draft/source row while confirm posting remains disabled and accounting/commodity side effects remain absent.
- Phase 6 fixed-purchase posting-readiness gate is complete: `/dea/business-events/fixed-purchase/` now renders a read-only readiness checklist over the saved draft/source row. It evaluates saved source state, preview status, unchanged payload hash, open accounting period, authenticated actor, account/ledger/commodity-account mappings, and existing posted fixed-purchase voucher state without calling posting services or creating accounting/commodity rows.
- Phase 6 fixed-purchase confirm handoff service is complete: `apps/tenant_apps/dea/services/business_event_posting.py` exposes `confirm_fixed_purchase_draft()`, which row-locks the previewed draft, rejects stale previews/readiness blockers, maps the normalized draft payload into `FixedPurchasePostingPayload`, and delegates to `post_fixed_purchase()` idempotently. The UI confirm button remains disabled.
- Phase 6 fixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/fixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_fixed_purchase_draft()`, rejects member-role users, handles duplicate submits through service idempotency, and redirects to a read-only result page with business facts, posting status, voucher/journal links, ledger/account rows, and commodity movement rows.
- Phase 6 fixed-purchase stale/error UX and navigation hardening is complete: the business-events dashboard lists recent fixed-purchase drafts/results with posted/not-posted state, and blocked fixed-purchase detail pages expose a re-preview recovery action.
- Phase 6 unfixed-purchase preview-only screen is complete: `/dea/business-events/unfixed-purchase/` captures supplier party, commodity, weights, purity, commodity accounts, rate basis, and reporting valuation context; persists an `UNFIXED_PURCHASE` preview draft; and renders read-only commodity receipt plus open purchase exposure impact without creating final monetary payable before rate fixing. Confirm posting remains disabled.
- Phase 6 unfixed-purchase readiness/detail/navigation gate is complete: unfixed-purchase previews render a read-only readiness checklist; `/dea/business-events/unfixed-purchase/<draft_id>/` shows draft facts, posting status, readiness, accounting note, commodity impact, and exposure impact; and the business-events dashboard lists recent unfixed-purchase drafts. Confirm posting remains disabled.
- Phase 6 unfixed-purchase confirm handoff service is complete: `confirm_unfixed_purchase_draft()` row-locks a previewed `UNFIXED_PURCHASE` draft, rejects stale payload/readiness blockers, maps normalized payload into `UnfixedPurchasePostingPayload`, and delegates to `post_unfixed_purchase()` idempotently without enabling the UI confirm endpoint.
- Phase 6 unfixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/unfixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_unfixed_purchase_draft()`, treats duplicate submits idempotently, rejects member-role users, and redirects to a read-only unfixed-purchase result page showing the posted commodity-intent voucher, commodity movement, and open exposure rows. Tests prove it still creates no financial journal, voucher-line, ledger transaction, account transaction, payment voucher, or rate-fixing rows.
- Phase 6 purchase rate-fixing preview/readiness screen is complete: `/dea/business-events/purchase-rate-fixing/` selects an open purchase exposure, captures fixing date, fine weight, INR rate, supplier account, inventory/valuation ledger, and payable ledger, then renders side-effect-free monetary payable and exposure-reduction impact. Confirm posting remains disabled and tests prove no new financial, commodity, rate-fixing, exposure, or payment rows are created.
- Phase 6 purchase rate-fixing source-draft boundary is complete: `BusinessEventDraft.EventType.PURCHASE_RATE_FIXING` now exists with tenant migration `dea.0038`; purchase rate-fixing preview POST stores source reference, fixing date, normalized economic payload, preview payload, and payload hash, then renders readiness from that saved draft.
- Phase 6 purchase rate-fixing confirm handoff and result surface is complete: `confirm_purchase_rate_fixing_draft()` row-locks a previewed `PURCHASE_RATE_FIXING` draft, rejects stale payload/readiness blockers, maps normalized payload into `PurchaseRateFixingPayload`, and delegates to `post_purchase_rate_fixing()` idempotently. `/dea/business-events/purchase-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated; the result page shows rate fixing, voucher, journal, ledger/account, and exposure-allocation details while explicitly showing that no physical commodity movement is created by rate fixing.
- Phase 6 fixed-sale preview-only screen is complete: `/dea/business-events/fixed-sale/` collects customer account, receivable/revenue ledgers, commodity, gross/purity/fine weight, source commodity account, INR amount, and narration, then renders side-effect-free receivable/revenue and outgoing `SALE_ISSUE` commodity impact.
- Phase 6 fixed-sale source-draft/readiness gate is complete: `BusinessEventDraft.EventType.FIXED_SALE` now exists with tenant migration `dea.0039`; fixed-sale preview POST stores source reference, sale date, normalized economic payload, preview payload, and payload hash, then renders readiness from that saved draft while confirm posting remains disabled.
- Phase 6 fixed-sale confirm handoff service is complete: `confirm_fixed_sale_draft()` row-locks a previewed `FIXED_SALE` draft, rejects stale payload/readiness blockers, maps normalized payload into `FixedSalePostingPayload`, and delegates to `post_fixed_sale()` idempotently without enabling the UI confirm endpoint.
- Phase 6 fixed-sale confirm endpoint/result surface is complete: `/dea/business-events/fixed-sale/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_fixed_sale_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to a read-only result page showing business facts, posting status, voucher/journal links, ledger/account rows, and outgoing `SALE_ISSUE` commodity movement.
- Phase 6 unfixed-sale preview-only screen is complete: `/dea/business-events/unfixed-sale/` collects customer party, commodity, gross/purity/fine weight, source commodity account, rate basis, reporting valuation context, and narration. `BusinessEventDraft.EventType.UNFIXED_SALE` now exists with tenant migration `dea.0040`; preview POST persists only a source draft and renders side-effect-free outgoing `SALE_ISSUE` commodity impact plus open sale exposure impact. It explicitly avoids final monetary receivable/revenue until sale rate fixing, and confirm posting remains disabled.
- Phase 6 unfixed-sale readiness/detail/navigation gate is complete: unfixed-sale previews now link to a read-only detail page; `/dea/business-events/unfixed-sale/<draft_id>/` shows draft facts, posting status, readiness, accounting note, outgoing commodity issue impact, and open sale exposure impact; and the business-events dashboard lists recent unfixed-sale drafts. Confirm posting remains disabled and route tests prove discovery/detail surfaces stay read-only.
- Phase 6 unfixed-sale confirm handoff service is complete: `confirm_unfixed_sale_draft()` row-locks a previewed `UNFIXED_SALE` draft, rejects stale payload/readiness blockers, maps normalized payload into `UnfixedSalePostingPayload`, and delegates to `post_unfixed_sale()` idempotently. Tests prove duplicate submits return the existing commodity-intent voucher, outgoing `SALE_ISSUE` movement, and open sale exposure while creating no financial journal, voucher-line, ledger transaction, account transaction, payment voucher, or rate-fixing rows. The UI confirm endpoint remains disabled.
- Phase 6 unfixed-sale confirm endpoint/result surface is complete: `/dea/business-events/unfixed-sale/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_unfixed_sale_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to the read-only unfixed-sale result page showing the posted commodity-intent voucher, outgoing movement, and open sale exposure. Tests prove it still creates no financial journal, voucher-line, ledger transaction, account transaction, payment voucher, or rate-fixing rows.
- Phase 6 sale rate-fixing preview/readiness screen is complete: `/dea/business-events/sale-rate-fixing/` selects open sale exposures, captures fixing date, fine weight, INR rate, customer account, receivable ledger, revenue ledger, and narration, then renders side-effect-free customer receivable/revenue and exposure-reduction impact. `BusinessEventDraft.EventType.SALE_RATE_FIXING` now exists with tenant migration `dea.0041`; preview POST stores only the source/draft payload and renders a draft-based readiness checklist. Confirm posting remains disabled.
- Phase 6 sale rate-fixing confirm handoff service is complete: `confirm_sale_rate_fixing_draft()` row-locks a previewed `SALE_RATE_FIXING` draft, rejects stale payload/readiness blockers, maps normalized payload into `SaleRateFixingPayload`, and delegates to `post_sale_rate_fixing()` idempotently. Tests prove duplicate submits return the existing rate-fixing, voucher, journal entry, and allocation while creating no additional physical commodity movement. The UI confirm endpoint remains disabled.
- Phase 6 sale rate-fixing confirm endpoint/result surface is complete: `/dea/business-events/sale-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, delegates to `confirm_sale_rate_fixing_draft()`, handles duplicate submits idempotently, rejects member-role users, and redirects to a read-only sale rate-fixing result page showing rate fixing, voucher, journal, ledger/account, and exposure-allocation details. The detail page explicitly shows that sale rate fixing creates no physical commodity movement.
- Phase 6 receipt/payment preview-only screen is complete: `/dea/business-events/settlement/` captures customer receipt or supplier payment facts, persists only `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` `BusinessEventDraft` rows through tenant migration `dea.0042`, and renders read-only cash/bank, party-account, and commodity/no-commodity impact. Confirm posting remains disabled, and tests prove preview creates no voucher, payment voucher, voucher-line, journal, ledger/account transaction, commodity movement, exposure, or rate-fixing rows.
- Phase 6 receipt/payment detail/readiness/navigation gate is complete: `/dea/business-events/settlement/<draft_id>/` shows saved settlement draft facts, posting readiness, accounting impact, payment impact, and explicit no-commodity impact while keeping confirm posting disabled. The business-events dashboard links recent receipt/payment drafts to this detail page and marks them posted/not-posted without creating accounting rows.
- Phase 6 receipt/payment confirm handoff service is complete: `confirm_monetary_settlement_draft()` row-locks a previewed `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` draft, rejects stale payload/readiness blockers, maps normalized payload into `CustomerReceiptPayload` or `SupplierPaymentPayload`, and delegates to `post_customer_receipt()` / `post_supplier_payment()` idempotently.
- Phase 6 receipt/payment confirm endpoint/result surface is complete: `/dea/business-events/settlement/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_monetary_settlement_draft()`, treats duplicate submits idempotently, rejects member-role users, and redirects to the read-only settlement detail page showing payment voucher, voucher, journal, ledger/account rows, payment impact, and explicit no-commodity impact. Tests prove it creates no `CommodityMovement`, `ExposureLine`, or `RateFixing` rows.
- Phase 6 karigar issue/receipt preview screens are complete: `/dea/business-events/karigar/` captures issue or receipt custody facts, persists `KARIGAR_ISSUE` / `KARIGAR_RECEIPT` `BusinessEventDraft` rows through tenant migration `dea.0043`, renders a read-only readiness checklist, and shows commodity-only custody movement impact with no financial, exposure, rate-fixing, or payment effects. `/dea/business-events/karigar/<draft_id>/` exposes the saved draft/result surface while confirm posting remains disabled.
- Phase 6 karigar confirm handoff service is complete: `confirm_karigar_movement_draft()` row-locks a previewed `KARIGAR_ISSUE` / `KARIGAR_RECEIPT` draft, rejects stale payload/readiness blockers, maps normalized payload into `KarigarIssuePayload` or `KarigarReceiptPayload`, and delegates to `post_karigar_issue()` / `post_karigar_receipt()` idempotently. Tests prove duplicate submits create one commodity-intent voucher and one `CommodityMovement` with no financial, exposure, rate-fixing, or payment rows. The UI confirm endpoint remains disabled.
- Phase 6 karigar confirm endpoint/result surface is complete: `/dea/business-events/karigar/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_karigar_movement_draft()`, treats duplicate submits idempotently, rejects member-role users, and redirects to the karigar detail page showing the posted commodity-intent voucher and custody `CommodityMovement`. Tests prove this path still creates no `VoucherLine`, `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, `PaymentVoucher`, `ExposureLine`, or `RateFixing` rows.
- Phase 6 completion checkpoint is complete in `docs/implementation/dea-phase-6-business-event-checkpoint.md`. It records the current event-impact matrix, confirm controls, focused verification set, remaining MVP gaps, and the recommendation to start Phase 7 with cleanup readiness audit rather than deletion.
- Phase 7 cleanup readiness audit has started in `docs/implementation/dea-phase-7-cleanup-readiness-audit.md`. The first slice classifies legacy/accountant DEA surfaces, inventories direct posting paths, and adds guard tests proving key legacy routes still resolve and runtime DEA/Girvi code does not import `posting/legacy_direct_write_engine.py`.
- Phase 7 expense-post characterization is complete: `views/expense.py::post_expense_voucher()` is covered for direct-payment idempotency, duplicate journal prevention, and closed-period no-materialization before any cleanup or route changes.
- Phase 7 dead voucher-helper cleanup is complete: old direct materialization helpers were removed from `views/voucher.py` after tests confirmed voucher post/reverse behavior still passes, and a guard test now prevents those helper definitions from returning.
- Phase 7 accountant permission boundary hardening is complete for the first high-risk legacy slice: voucher hub, generic voucher CRUD/post/reverse, payment voucher CRUD, expense voucher CRUD/post, manual journal voucher CRUD, and opening-balance endpoints now require platform staff/superuser, workspace owner, or workspace role `Owner`, `Admin`, or `Accountant`.
- Phase 7 navigation cleanup is complete for the workspace sidebar DEA entry points: normal DEA users are now guided to business events and reports, while legacy/manual DEA links (voucher, payment, expense, manual journal, opening balance, period controls, diagnostics) are grouped under an accountant-only tools section visible to `Owner`, `Admin`, and `Accountant` roles.
- Phase 7 dashboard and header-navigation alignment is complete: both DEA dashboard variants now default to business-events-first/report-first quick actions and guided workflows for normal staff, while accountant-only manual tools (voucher hub, period controls, manual journal/opening balance surfaces) are shown only to `Owner`, `Admin`, and `Accountant` users. Focused role tests now cover owner vs member visibility for standard/enhanced dashboards.
- Phase 7 legacy-surface gating refinement is complete for current dashboard panels: member users now see reduced recent-vouchers/recent-entries panels with direct navigation disabled, while owner/admin/accountant users retain full drilldown links and COA preview visibility. Both dashboard templates now conditionally hide legacy-only panels, and focused role tests have been extended to verify member-to-accountant visibility boundaries.
- Phase 7 accounting tools documentation is complete: comprehensive inventory of all legacy DEA surfaces now documented in [docs/implementation/dea-phase7-accounting-tools-inventory.md](../../implementation/dea-phase7-accounting-tools-inventory.md) covering voucher hub, payment/expense/journal-entry/opening-balance workflows, period management, diagnostics, reports, ledger/account management, and bank reconciliation. Inventory includes role-gating audit findings, risk assessment by category, and Phase 8+ recommendations (period CRUD hardening, bank reconciliation audit, deprecation candidates for legacy JE views).

Current next task:

- Phase 8 planning or Phase 7 remaining work: Based on Phase 7 accounting tools inventory, either proceed with Phase 8 roadmap (role-gating hardening for period CRUD + bank reconciliation, surface relabeling/discoverability reduction) or complete remaining Phase 7 slices if identified.

Current verification:

- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_purchase_service --keepdb` with 5 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_unfixed_purchase_service --keepdb` with 5 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_rate_fixing_service --keepdb` with 10 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_sale_service --keepdb` with 5 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_unfixed_sale_service --keepdb` with 5 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_monetary_settlement_service --keepdb` with 6 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 61 tests after receipt/payment confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 27 tests after receipt/payment confirm endpoint/result surface.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after receipt/payment confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 67 tests after karigar issue/receipt preview screens.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_karigar_service --keepdb` with 6 tests after karigar issue/receipt preview screens.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after karigar issue/receipt preview screens.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 32 tests after karigar confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_karigar_service --keepdb` with 6 tests after karigar confirm handoff service.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after karigar confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 70 tests after karigar confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 32 tests after karigar confirm endpoint/result surface.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after karigar confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_purchase_service --keepdb` with 5 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_unfixed_purchase_service --keepdb` with 5 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_rate_fixing_service --keepdb` with 10 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_sale_service --keepdb` with 5 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_unfixed_sale_service --keepdb` with 5 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_monetary_settlement_service --keepdb` with 6 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_karigar_service --keepdb` with 6 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 70 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 32 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 6 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.test_financial_reports --keepdb` with 8 tests during Phase 6 completion checkpoint.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_statement_boundary --keepdb` with 2 tests during Phase 6 completion checkpoint.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected during Phase 6 completion checkpoint.
- Inconclusive: a combined backend service run timed out while printing progress dots; the same suites passed individually.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_phase7_cleanup_readiness --keepdb` with 2 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_financial_posting_characterization --keepdb` with 19 tests after Phase 7 cleanup readiness audit started.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after Phase 7 cleanup readiness audit started.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_financial_posting_characterization --keepdb` with 21 tests after expense-post characterization.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_phase7_cleanup_readiness --keepdb` with 2 tests after expense-post characterization.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after expense-post characterization.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_phase7_cleanup_readiness --keepdb` with 3 tests after removing dead voucher helpers.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_financial_posting_characterization --keepdb` with 21 tests after removing dead voucher helpers.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after removing dead voucher helpers.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_phase7_permission_boundaries --keepdb` with 3 tests after accountant permission hardening.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_phase7_cleanup_readiness --keepdb` with 3 tests after accountant permission hardening.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_financial_posting_characterization --keepdb` with 21 tests after accountant permission hardening.
- Passed: `manage.py makemigrations dea rates --check --dry-run` with no model changes detected after accountant permission hardening.
- Passed: `.venv314/Scripts/python.exe manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_phase7_permission_boundaries --keepdb` with 74 tests after Phase 7 navigation cleanup.
- Passed: `.venv314/Scripts/python.exe manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_phase7_permission_boundaries --keepdb` with 76 tests after dashboard/header navigation alignment.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_karigar_service --keepdb` with 6 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_purchase_service apps.tenant_apps.dea.tests.test_unfixed_purchase_service --keepdb` with 10 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_purchase_service apps.tenant_apps.dea.tests.test_unfixed_purchase_service apps.tenant_apps.dea.tests.test_rate_fixing_service --keepdb` with 15 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_purchase_service apps.tenant_apps.dea.tests.test_unfixed_purchase_service apps.tenant_apps.dea.tests.test_rate_fixing_service apps.tenant_apps.dea.tests.test_fixed_sale_service --keepdb` with 20 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_fixed_purchase_service apps.tenant_apps.dea.tests.test_unfixed_purchase_service apps.tenant_apps.dea.tests.test_rate_fixing_service apps.tenant_apps.dea.tests.test_fixed_sale_service apps.tenant_apps.dea.tests.test_unfixed_sale_service apps.tenant_apps.dea.tests.test_monetary_settlement_service apps.tenant_apps.dea.tests.test_karigar_service --keepdb` with 42 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_models --keepdb` with 31 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_seed_command --keepdb` with 6 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_selectors --keepdb` with 7 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_metal_balance_report_service --keepdb` with 4 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_selectors apps.tenant_apps.dea.tests.test_metal_balance_report_service --keepdb` with 11 tests.
- Passed: `manage.py test apps.tenant_apps.dea.test_financial_reports --keepdb` with 8 tests.
- Passed: `manage.py test apps.tenant_apps.dea.test_financial_reports apps.tenant_apps.dea.tests.test_metal_balance_report_service --keepdb` with 12 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_valuation_service --keepdb` with 7 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_exposure_report_service --keepdb` with 4 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_exposure_report_service apps.tenant_apps.dea.tests.test_commodity_valuation_service apps.tenant_apps.dea.test_financial_reports --keepdb` with 19 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_statement_boundary --keepdb` with 2 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_statement_boundary apps.tenant_apps.dea.tests.test_exposure_report_service apps.tenant_apps.dea.tests.test_metal_balance_report_service --keepdb` with 10 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_valuation_report_service --keepdb` with 4 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_valuation_report_service apps.tenant_apps.dea.tests.test_commodity_valuation_service apps.tenant_apps.dea.tests.test_exposure_report_service apps.tenant_apps.dea.tests.test_metal_balance_report_service --keepdb` with 19 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 4 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_report_views apps.tenant_apps.dea.tests.test_metal_balance_report_service apps.tenant_apps.dea.tests.test_exposure_report_service apps.tenant_apps.dea.tests.test_valuation_report_service --keepdb` with 16 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 6 tests after navigation polish.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_report_views apps.tenant_apps.dea.tests.test_metal_balance_report_service apps.tenant_apps.dea.tests.test_exposure_report_service apps.tenant_apps.dea.tests.test_valuation_report_service --keepdb` with 18 tests after navigation polish.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 4 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 10 tests.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 7 tests after fixed-purchase preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 13 tests after fixed-purchase preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 8 tests after fixed-purchase source-draft persistence.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 14 tests after fixed-purchase source-draft persistence.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 9 tests after fixed-purchase posting-readiness gate.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 15 tests after fixed-purchase posting-readiness gate.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 4 tests after fixed-purchase confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 13 tests after fixed-purchase confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 19 tests after fixed-purchase confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 12 tests after fixed-purchase confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 22 tests after fixed-purchase confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 14 tests after fixed-purchase draft/result dashboard navigation and blocked-detail re-preview recovery.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 24 tests after fixed-purchase draft/result dashboard navigation and blocked-detail re-preview recovery.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 17 tests after unfixed-purchase preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 27 tests after unfixed-purchase preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 20 tests after unfixed-purchase readiness/detail/navigation.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 30 tests after unfixed-purchase readiness/detail/navigation.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 8 tests after unfixed-purchase confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 34 tests after unfixed-purchase confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 23 tests after unfixed-purchase confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 37 tests after unfixed-purchase confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 26 tests after purchase rate-fixing preview/readiness screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 40 tests after purchase rate-fixing preview/readiness screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 26 tests after purchase rate-fixing source-draft boundary.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 40 tests after purchase rate-fixing source-draft boundary.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 11 tests after purchase rate-fixing confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 30 tests after purchase rate-fixing confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 47 tests after purchase rate-fixing confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 33 tests after fixed-sale preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 50 tests after fixed-sale preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 33 tests after fixed-sale source-draft/readiness gate.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 50 tests after fixed-sale source-draft/readiness gate.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 15 tests after fixed-sale confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 54 tests after fixed-sale confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 38 tests after fixed-sale confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 59 tests after fixed-sale confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 41 tests after unfixed-sale preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 62 tests after unfixed-sale preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 43 tests after unfixed-sale readiness/detail/navigation gate.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 64 tests after unfixed-sale readiness/detail/navigation gate.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 19 tests after unfixed-sale confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 68 tests after unfixed-sale confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 46 tests after unfixed-sale confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 71 tests after unfixed-sale confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 49 tests after sale rate-fixing preview/readiness screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service apps.tenant_apps.dea.tests.test_business_event_scaffold_views apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 74 tests after sale rate-fixing preview/readiness screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 22 tests after sale rate-fixing confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 49 tests after sale rate-fixing confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_commodity_report_views --keepdb` with 6 tests after sale rate-fixing confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 52 tests after sale rate-fixing confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 22 tests after sale rate-fixing confirm endpoint/result surface.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 56 tests after receipt/payment preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_monetary_settlement_service --keepdb` with 6 tests after receipt/payment preview-only screen.
- Passed: `manage.py makemigrations dea rates --check --dry-run` after receipt/payment preview-only screen.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 58 tests after receipt/payment detail/readiness/navigation gate.
- Passed: `manage.py makemigrations dea rates --check --dry-run` after receipt/payment detail/readiness/navigation gate.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_posting_service --keepdb` with 27 tests after receipt/payment confirm handoff service.
- Passed: `manage.py test apps.tenant_apps.dea.tests.test_business_event_scaffold_views --keepdb` with 58 tests after receipt/payment confirm handoff service.
- Passed: `manage.py makemigrations dea rates --check --dry-run` after receipt/payment confirm handoff service.
- Inconclusive locally: one combined `business_event_posting_service + business_event_scaffold_views + commodity_report_views` run with 77 tests timed out while tests were still progressing; a second combined run also timed out after long tenant schema setup. The same coverage passed when split into focused suites.
- Passed in output but shell wrapper timed after DB preservation: `manage.py test apps.tenant_apps.dea.tests.test_commodity_posting_service apps.tenant_apps.dea.tests.test_fixed_purchase_service --keepdb` with 11 tests.
- Passed: `manage.py makemigrations dea rates --check --dry-run`.
- Inconclusive locally: broader combined DEA regression slices timed out or collided during tenant test database setup; parallel test starts can hit the known `girvi_repl_loan_it_idx` keepdb migration race. Re-run serially before committing a larger posting/reporting change.

## Phase 1: Protect Financial Accounting Correctness

Goal: prove and protect current financial accounting semantics before introducing commodity models or changing posting internals.

### Task 1.1: Financial Posting Characterization Tests

| Field | Detail |
|---|---|
| Task name | DEA financial posting characterization tests |
| Problem it solves | Existing posting behavior is not fully protected before refactor. |
| Files likely affected | `apps/tenant_apps/dea/tests/test_financial_posting_characterization.py` or similar. |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Existing DEA test factories/helpers; no commodity work. |
| Expected behavior | Current posting engine creates balanced `JournalEntry`, `LedgerTransaction`, and optional `AccountTransaction` rows for representative vouchers. |
| Required tests | Payment voucher, journal entry voucher, sales invoice, purchase invoice, loan posting where practical; assert debit/credit totals and period assignment. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add DEA characterization tests for current financial posting behavior. Cover voucher posting through the canonical posting engine for representative payment, journal, sales, and purchase flows. Do not change production code unless a test exposes a bug that must be fixed separately." |

### Task 1.2: Ledger And Account Transaction Correctness Tests

| Field | Detail |
|---|---|
| Task name | Ledger/account transaction correctness tests |
| Problem it solves | GL and subledger semantics can be confused, especially because both feed balance logic. |
| Files likely affected | `apps/tenant_apps/dea/tests/test_ledger_account_transaction_semantics.py` |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Task 1.1 |
| Expected behavior | `LedgerTransaction` represents financial debit/credit legs; `AccountTransaction` represents party/subledger attribution and does not replace commodity obligations. |
| Required tests | Assert ledger debit/credit sides, account transaction side, control ledger relation, and that subledger totals reconcile to control ledger for a simple AR/AP case. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add tests documenting DEA LedgerTransaction and AccountTransaction semantics. Prove account lines are subledger attribution and financial GL balance remains driven by ledger postings/control accounts." |

### Task 1.3: Balance View Characterization Tests

| Field | Detail |
|---|---|
| Task name | `ledger_balances` and `account_balances` characterization |
| Problem it solves | SQL balance views hide business meaning and must not be changed blindly. |
| Files likely affected | `apps/tenant_apps/dea/tests/test_balance_views_characterization.py` |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Stable local test database with PostgreSQL views available. |
| Expected behavior | Current SQL views calculate monetary ledger/account balances for INR transactions exactly as current code expects. |
| Required tests | Opening statement plus transaction delta, multi-transaction same currency, account debtor/creditor side behavior, no transaction default behavior. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add characterization tests for DEA `ledger_balances` and `account_balances` views. Assert current INR monetary balance behavior before any refactor." |

### Task 1.4: Metal-Like Currency Data Audit

| Field | Detail |
|---|---|
| Task name | Metal-like currency data audit |
| Problem it solves | Existing tenant data may already contain gold/silver encoded as currencies. |
| Files likely affected | `apps/tenant_apps/dea/management/commands/audit_dea_currency_codes.py` or `docs/implementation/dea-currency-data-audit.md` |
| Risk level | Critical |
| Difficulty | Small |
| Dependencies | None |
| Expected behavior | Read-only report lists distinct currency codes from DEA transaction and statement tables and flags metal-like/suspicious codes. |
| Required tests | Command/unit test with mocked/query-created suspicious values if command is implemented; otherwise documented SQL only. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add a read-only DEA currency-code audit command that reports distinct financial currency values from ledger/account transactions and statements, flags metal-like codes, and does not mutate data." |

### Task 1.5: Trial Balance Financial-Only Regression Tests

| Field | Detail |
|---|---|
| Task name | Trial balance financial-only tests |
| Problem it solves | Trial balance must never become a metal balance report. |
| Files likely affected | `apps/tenant_apps/dea/test_financial_reports.py`, `apps/tenant_apps/dea/tests/test_trial_balance_currency_guardrails.py` |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Task 1.1 |
| Expected behavior | Trial balance reports posted financial journal values in base currency only. |
| Required tests | Trial balance with INR posting; non-base monetary posting uses `amount_base`; suspicious metal-like currency is rejected or explicitly excluded once guards exist. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add regression tests proving DEA trial balance is base-currency financial reporting only and cannot be used for commodity quantity balances." |

### Task 1.6: Monetary Currency Guard Design

| Field | Detail |
|---|---|
| Task name | Monetary currency guard design |
| Problem it solves | `CurrencyConfiguration.enabled_currencies` and `MoneyField` paths do not explicitly distinguish ISO money from metals. |
| Files likely affected | `docs/implementation/dea-monetary-currency-guardrails.md` first; later `dea/models/currency.py`, forms, validators. |
| Risk level | High |
| Difficulty | Small |
| Dependencies | Task 1.4 |
| Expected behavior | Document exact allowed monetary currency policy and where validation will later be enforced. |
| Required tests | Not in design task; later tests must cover validators. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Create an implementation note specifying monetary currency guardrails for DEA, including allowed code policy, suspicious metal codes, and validation points. Do not edit app code." |

## Phase 2: Define Clean Document/Voucher/Journal Lifecycle

Goal: make accounting lifecycle semantics decision-complete before changing posting internals.

### Task 2.1: Lifecycle ADR

| Field | Detail |
|---|---|
| Task name | Business document, voucher, journal lifecycle ADR |
| Problem it solves | Current code has multiple posting paths and partially overlapping states. |
| Files likely affected | `docs/adr/YYYY-MM-DD-dea-document-voucher-journal-lifecycle.md` |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Phase 1 findings |
| Expected behavior | ADR defines document states, voucher states, journal immutability, correction/reversal model, and source-document authority. |
| Required tests | None in ADR task; follow-up tests in Task 2.2 and 2.3. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Draft an ADR for DEA business document, voucher, journal entry, reversal, correction, and idempotency lifecycle. Base it on the DEA commodity audit and existing constitution. Do not edit app code." |

### Task 2.2: Posted Immutability Tests

| Field | Detail |
|---|---|
| Task name | Posted financial record immutability tests |
| Problem it solves | Posted entries must not be mutated directly. |
| Files likely affected | `apps/tenant_apps/dea/tests/test_posted_immutability.py` |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Task 2.1 preferred |
| Expected behavior | Posted `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, and posted `VoucherLine` cannot be edited through supported model/service paths. |
| Required tests | Attempt update/delete after posting; assert validation/protection; document any current gaps as expected failures only if project policy allows. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add DEA tests for posted accounting immutability. Cover JournalEntry, VoucherLine, LedgerTransaction, and AccountTransaction behavior after posting. Keep production fixes separate unless necessary." |

### Task 2.3: Posting Idempotency And Race Tests

| Field | Detail |
|---|---|
| Task name | Posting idempotency and double-submit tests |
| Problem it solves | Duplicate submits can create duplicate accounting effects if not guarded. |
| Files likely affected | `apps/tenant_apps/dea/test_posting_engine_controls.py`, new focused tests. |
| Risk level | Critical |
| Difficulty | Large |
| Dependencies | Task 1.1, Task 2.1 |
| Expected behavior | Same economic payload posts once; changed payload follows correction/reversal policy; voucher row locking prevents concurrent duplicate posting. |
| Required tests | Same source doc same fingerprint, changed payload, concurrent post simulation where feasible, unique fingerprint constraint. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add tests for DEA posting idempotency and double-submit behavior using existing fingerprint and voucher locking paths. Do not introduce commodity models." |

### Task 2.4: Canonical Posting Path Plan

| Field | Detail |
|---|---|
| Task name | Canonical posting path plan |
| Problem it solves | `views/voucher.py` contains direct post/reverse helpers while services and engine also post. |
| Files likely affected | `docs/implementation/dea-canonical-posting-path.md` first; later `views/voucher.py`, `services/post_doc.py`, `posting/engine.py`. |
| Risk level | High |
| Difficulty | Small |
| Dependencies | Task 2.1 |
| Expected behavior | A concrete plan identifies the canonical command/service and marks direct view materialization as legacy. |
| Required tests | Plan-only task; later refactor requires view/service regression tests. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Document the canonical DEA posting path and identify legacy direct posting paths to remove after characterization tests. Do not edit app code." |

### Task 2.5: Reversal And Correction Service Contract

| Field | Detail |
|---|---|
| Task name | Reversal/correction service contract |
| Problem it solves | Reversal behavior exists in multiple places and correction semantics are not fully explicit. |
| Files likely affected | `docs/implementation/dea-reversal-correction-contract.md`; later `dea/services/reversal.py` or posting engine methods. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 2.1 |
| Expected behavior | Defines one service API for reversing/correcting financial vouchers and future commodity movements. |
| Required tests | Later tests for reversal idempotency, period lock behavior, source link preservation. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Create a DEA reversal/correction service contract document covering posted voucher reversal, correction voucher creation, period handling, idempotency, and future commodity movement reversal." |

## Phase 3: Introduce Commodity Accounting Side-By-Side

Goal: add commodity accounting without disturbing financial ledger balances or reports.

### Task 3.1: Commodity Architecture ADR

| Field | Detail |
|---|---|
| Task name | Commodity accounting architecture ADR |
| Problem it solves | New commodity models are an architectural decision and must not be improvised in migrations. |
| Files likely affected | `docs/adr/YYYY-MM-DD-dea-commodity-accounting-layer.md` |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Phase 1, Task 2.1 |
| Expected behavior | ADR states commodities are separate from monetary currencies and defines MVP model boundaries. |
| Required tests | None in ADR task. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Draft an ADR introducing DEA commodity accounting as a side-by-side layer separate from financial currency accounting. Define MVP models and non-goals." |

### Task 3.2: Commodity Model Schema Plan

| Field | Detail |
|---|---|
| Task name | Commodity model schema plan |
| Problem it solves | Models must be decision-complete before migrations. |
| Files likely affected | `docs/implementation/dea-commodity-model-schema.md` |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Task 3.1 |
| Expected behavior | Defines fields, constraints, indexes, relationships, state choices, and tenant/migration notes for commodity models. |
| Required tests | Plan must list model tests to write with implementation. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Create a detailed schema plan for DEA Commodity/Metal, CommodityAccount, CommodityMovement, ExposureLine, RateFixing, and optional ValuationSnapshot. Do not write migrations." |

### Task 3.3: Commodity Master And Account Models

| Field | Detail |
|---|---|
| Task name | Commodity master and commodity account models |
| Problem it solves | Need explicit metal and balance bucket concepts. |
| Files likely affected | `dea/models/commodity.py`, `dea/models/__init__.py`, migrations, admin. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 3.2 |
| Expected behavior | Gold/silver master records and commodity accounts exist without changing financial ledger/account balances. |
| Required tests | Model creation, uniqueness, active status, account purpose/location/party constraints, tenant migration smoke. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement DEA Commodity/Metal and CommodityAccount models from the approved schema plan, with migrations, admin registration, and focused model tests. Do not alter financial Ledger or Account behavior." |

### Task 3.4: Commodity Movement Model

| Field | Detail |
|---|---|
| Task name | Immutable commodity movement model |
| Problem it solves | Need accounting-grade metal quantity effects separate from GL. |
| Files likely affected | `dea/models/commodity.py`, migrations, admin, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 3.3 |
| Expected behavior | Commodity movements capture metal, gross weight, purity, fine weight, from/to accounts, source document, voucher, and reversal link. |
| Required tests | Fine-weight calculation/validation, positive quantities, source/voucher linkage, reversal movement relationship, posted immutability. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement immutable DEA CommodityMovement model linked to source document and optional voucher, with gross weight, purity, fine weight, from/to commodity accounts, reversal linkage, and tests. Keep financial ledger untouched." |

### Task 3.5: Exposure And Rate Fixing Models

| Field | Detail |
|---|---|
| Task name | ExposureLine and RateFixing models |
| Problem it solves | Unfixed purchase/sale cannot be represented without open exposure and fixing. |
| Files likely affected | `dea/models/commodity.py`, migrations, admin, tests. |
| Risk level | High |
| Difficulty | Large |
| Dependencies | Task 3.4 |
| Expected behavior | Open fixed/unfixed exposure can be created, partially fixed, closed, and linked to rate fixing documents. |
| Required tests | Open weight cannot go negative, fixing quantity <= open quantity, fixed/unfixed state transitions, reversal/correction metadata. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement DEA ExposureLine and RateFixing models for fixed/unfixed commodity exposure, with constraints and tests. Do not post financial effects yet." |

### Task 3.6: Commodity Posting Service Skeleton

| Field | Detail |
|---|---|
| Task name | Commodity posting service skeleton |
| Problem it solves | Need a single service to create commodity movements/exposures atomically with business events. |
| Files likely affected | `dea/services/commodity_posting.py`, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 3.4, Task 3.5 |
| Expected behavior | Service validates and creates commodity movements/exposure records without financial journal side effects yet. |
| Required tests | Movement creation, exposure creation, reversal helper, idempotent source/event key behavior. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Create a DEA commodity posting service skeleton that can create immutable CommodityMovement and ExposureLine records from structured payloads, with tests. Keep it side-by-side and do not integrate with financial posting engine yet." |

### Task 3.7: Commodity Position Selectors

| Field | Detail |
|---|---|
| Task name | Commodity position selectors |
| Problem it solves | Need readable metal balances before reports/UI. |
| Files likely affected | `dea/selectors/commodity.py` or `dea/selectors.py`, tests. |
| Risk level | Medium |
| Difficulty | Medium |
| Dependencies | Task 3.4 |
| Expected behavior | Selectors return gross/fine weight by metal, commodity account, party, location, and fixed/unfixed status. |
| Required tests | Sum movements by account/metal/date; reversal movements offset; no financial `MoneyField` usage. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add DEA commodity position selectors that compute metal balances from CommodityMovement records by metal/account/party/location/as-of date. Include tests." |

### Task 3.8: Valuation Model Plan

| Field | Detail |
|---|---|
| Task name | Commodity valuation model plan |
| Problem it solves | Valuation policy can become complex and should not block MVP movements. |
| Files likely affected | `docs/implementation/dea-commodity-valuation-policy.md`; later valuation models/services. |
| Risk level | Medium |
| Difficulty | Small |
| Dependencies | Task 3.7 |
| Expected behavior | Defines MVP valuation as reporting-only using Rates, with deferred periodic snapshots and unrealized gain/loss. |
| Required tests | Later valuation selector tests. |
| MVP-critical or deferrable | Deferrable unless valuation is required for launch. |
| Suggested Codex implementation prompt | "Document DEA commodity valuation MVP policy: rate source, valuation currency, reporting-only valuation, and deferred ValuationSnapshot/unrealized gain/loss accounting." |

## Phase 4: Business Operations

Goal: implement business operations in a safe order, using commodity side-by-side models and financial postings only where appropriate.

### Task 4.1: Fixed Purchase

| Field | Detail |
|---|---|
| Task name | Fixed purchase document and posting |
| Problem it solves | Business needs metal purchase with known price and payable/cash effect. |
| Files likely affected | DEA or future purchase domain models/services, `dea/posting/rules/*`, `dea/services/commodity_posting.py`, tests. |
| Risk level | Critical |
| Difficulty | Large |
| Dependencies | Phase 1, Phase 2, Task 3.6 |
| Expected behavior | Fixed purchase creates financial payable/inventory value and commodity movement increasing owned metal. |
| Required tests | Valid purchase posts financial DR/CR, supplier account line, commodity movement, idempotency, reversal. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement fixed purchase MVP using approved document contract. Posting must create financial voucher/journal/account effects and side-by-side commodity movement. Include tests and no UI redesign." |

### Task 4.2: Unfixed Purchase

| Field | Detail |
|---|---|
| Task name | Unfixed purchase document and exposure |
| Problem it solves | Business receives/commits metal before final price is fixed. |
| Files likely affected | Purchase document/service, commodity posting service, exposure selectors/tests. |
| Risk level | Critical |
| Difficulty | Large |
| Dependencies | Task 4.1, Task 3.5 |
| Expected behavior | Unfixed purchase creates commodity movement/exposure without false fixed monetary payable, except explicit advances/provisional policy. |
| Required tests | Open exposure creation, metal balance increase, no final AP unless configured, idempotency, reversal. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement unfixed purchase MVP. It must create commodity movement and open purchase exposure while keeping financial ledger balances free of final payable until rate fixing." |

### Task 4.3: Rate Fixing

| Field | Detail |
|---|---|
| Task name | Purchase/sale rate fixing |
| Problem it solves | Open unfixed exposures need final settlement rate and monetary effect. |
| Files likely affected | `RateFixing` service, DEA posting rule/service, tests. |
| Risk level | Critical |
| Difficulty | Large |
| Dependencies | Task 4.2 and/or Task 4.5 |
| Expected behavior | Fixing reduces open exposure and posts monetary payable/receivable according to exposure side. |
| Required tests | Partial/full fixing, quantity <= open, financial posting, exposure close, reversal. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement MVP rate fixing for commodity exposures. Support partial fixing, close exposure quantities, and post financial payable/receivable when fixed. Include reversal/idempotency tests." |

### Task 4.4: Fixed Sale

| Field | Detail |
|---|---|
| Task name | Fixed sale document and posting |
| Problem it solves | Business needs fixed-price metal sale and customer receivable/revenue. |
| Files likely affected | Sale document/service, DEA posting rules, commodity posting service, tests. |
| Risk level | Critical |
| Difficulty | Large |
| Dependencies | Task 4.1, Task 3.7 |
| Expected behavior | Fixed sale posts monetary receivable/revenue/tax and decreases commodity position. |
| Required tests | Stock/metal availability validation, financial posting, customer account line, commodity outflow, reversal. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement fixed sale MVP with financial receivable/revenue posting and commodity outflow. Keep commodity quantity out of financial currency fields. Include tests." |

### Task 4.5: Unfixed Sale

| Field | Detail |
|---|---|
| Task name | Unfixed sale document and exposure |
| Problem it solves | Business delivers/sells metal before final customer price is fixed. |
| Files likely affected | Sale document/service, exposure models/selectors, tests. |
| Risk level | High |
| Difficulty | Large |
| Dependencies | Task 4.4, Task 3.5 |
| Expected behavior | Unfixed sale decreases owned metal and creates open sale exposure without final revenue/receivable until fixing. |
| Required tests | Open sale exposure, metal outflow, no final AR/revenue before fixing, reversal. |
| MVP-critical or deferrable | MVP-critical if unfixed sale is in launch scope; otherwise deferrable |
| Suggested Codex implementation prompt | "Implement unfixed sale MVP with commodity outflow and open exposure, deferring final financial receivable/revenue until rate fixing. Include tests." |

### Task 4.6: Receipt/Payment

| Field | Detail |
|---|---|
| Task name | Business-event receipt/payment settlement |
| Problem it solves | Cash/bank settlement must remain monetary and document-linked. |
| Files likely affected | `dea/models/payment.py`, `dea/facades/payments.py`, `dea/services/settlement.py`, views/tests as needed. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Phase 2, existing payment tests |
| Expected behavior | Receipts/payments settle monetary party balances only; they cannot settle metal exposure except through rate fixing or explicit metal-in-kind document. |
| Required tests | Customer receipt, supplier payment, allocation, duplicate reference/idempotency, reject commodity exposure settlement through money payment. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Harden DEA receipt/payment behavior as monetary-only settlement. Add tests showing payments reduce financial party balances and do not settle commodity exposures directly." |

### Task 4.7: Issue To Karigar

| Field | Detail |
|---|---|
| Task name | Karigar metal issue |
| Problem it solves | Metal sent to artisan must be tracked as custody movement, not expense. |
| Files likely affected | Commodity document/service models, `dea/services/commodity_posting.py`, selectors/tests; possible product integration later. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 3.4, Task 3.7 |
| Expected behavior | Metal moves from own/vault commodity account to karigar custody commodity account. |
| Required tests | Issue validates available metal, creates movement, updates karigar balance, reversal offsets movement. |
| MVP-critical or deferrable | MVP-critical for jeweller workflow |
| Suggested Codex implementation prompt | "Implement MVP karigar issue as a commodity movement from vault/owned metal to karigar custody account, with tests. Do not post P&L by default." |

### Task 4.8: Receive From Karigar

| Field | Detail |
|---|---|
| Task name | Karigar metal receipt |
| Problem it solves | Returned/processed metal must close custody balance and optionally record wastage/charges. |
| Files likely affected | Commodity document/service models, commodity posting, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 4.7 |
| Expected behavior | Metal moves from karigar custody to vault/finished goods; wastage is explicit adjustment; labor charges are monetary if billed. |
| Required tests | Receive against open issue, partial receive, wastage, making charge payable if included, reversal. |
| MVP-critical or deferrable | MVP-critical for jeweller workflow |
| Suggested Codex implementation prompt | "Implement MVP karigar receipt against prior issue, moving commodity balances back from karigar custody and recording wastage explicitly. Include tests." |

### Task 4.9: Metal Balance Report

| Field | Detail |
|---|---|
| Task name | Basic metal balance report |
| Problem it solves | Users need proof of metal position separate from trial balance. |
| Files likely affected | Commodity selectors/reports, `templates/dea/reports/*` later, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 3.7, at least one movement-producing operation |
| Expected behavior | Report shows gross/fine weight by metal/account/location/party/as-of date. |
| Required tests | Movement sums, reversals, filters, tenant isolation, no financial `MoneyField` dependency. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement basic DEA metal balance report selector and minimal report output using CommodityMovement data. Include tests; UI can be minimal." |

### Task 4.10: Financial Trial Balance

| Field | Detail |
|---|---|
| Task name | Financial trial balance hardening |
| Problem it solves | Trial balance must remain financial-only after commodity models exist. |
| Files likely affected | `dea/services/reports.py`, report views/templates, tests. |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Task 1.5, Task 3.4 |
| Expected behavior | Trial balance ignores commodity movements/exposures and reports base-currency financial ledger balances only. |
| Required tests | Trial balance with both financial and commodity records; commodity-only movement does not affect financial totals. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Harden DEA financial trial balance after commodity models exist. Add tests proving commodity movements/exposures do not affect financial trial balance." |

## Phase 5: Reports And Selectors

Goal: move reporting toward explicit financial selectors and commodity selectors.

### Task 5.1: Financial Report Selectors

| Field | Detail |
|---|---|
| Task name | Financial report selectors |
| Problem it solves | Financial reporting logic is service-heavy and should be explicit about posted/base-currency financial data. |
| Files likely affected | `dea/selectors/financial.py`, `dea/services/reports.py`, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 1.5 |
| Expected behavior | Trial balance, ledger statement, and party statement reads use clear financial selectors. |
| Required tests | Period/as-of filtering, posted-only, base currency, no commodity rows. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Extract or add DEA financial report selectors for trial balance, ledger statement, and party account statement. Keep behavior unchanged and add tests." |

### Task 5.2: Party Account Statement

| Field | Detail |
|---|---|
| Task name | Party monetary account statement |
| Problem it solves | Party statements must stay monetary and role/purpose-aware. |
| Files likely affected | `dea/services/account_resolution.py`, `dea/selectors/financial.py`, party/DEA templates later, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 5.1 |
| Expected behavior | Statement shows monetary AR/AP/loan balances by party role/purpose and excludes commodity balances. |
| Required tests | Customer receivable, supplier payable, borrower loan receivable, lender loan payable, no commodity movement included. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement/strengthen DEA party monetary account statement selectors with role/purpose account mapping, excluding commodity accounts. Include tests." |

### Task 5.3: Ledger Statement

| Field | Detail |
|---|---|
| Task name | Financial ledger statement selector |
| Problem it solves | Ledger statement should read immutable financial postings consistently. |
| Files likely affected | `dea/selectors/financial.py`, `views/ledger.py`, templates later, tests. |
| Risk level | Medium |
| Difficulty | Medium |
| Dependencies | Task 5.1 |
| Expected behavior | Ledger statement lists posted financial journal lines by period/as-of date, with voucher/source links. |
| Required tests | Date filters, reversal entries, voucher links, base/original monetary amounts. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add a DEA financial ledger statement selector that lists posted ledger movements with voucher/source links and tests." |

### Task 5.4: Commodity Position Report

| Field | Detail |
|---|---|
| Task name | Commodity position report |
| Problem it solves | Users need owned/custody/party metal position by account. |
| Files likely affected | `dea/selectors/commodity.py`, `dea/services/commodity_reports.py`, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 4.9 |
| Expected behavior | Report shows positions by metal, account purpose, party/location, fixed status. |
| Required tests | Grouping, as-of date, reversal offset, tenant isolation. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Add DEA commodity position report selectors using CommodityMovement and ExposureLine data. Include grouping/filter tests." |

### Task 5.5: Exposure Report

| Field | Detail |
|---|---|
| Task name | Commodity exposure report |
| Problem it solves | Open unfixed transactions need risk/operations visibility. |
| Files likely affected | `dea/selectors/commodity.py`, report service/templates later, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 4.2, Task 4.5 |
| Expected behavior | Shows open unfixed purchase/sale exposure by party, metal, fine weight, age, and indicative valuation. |
| Required tests | Open/closed exposure, partial fixing, filtering by party/metal/date. |
| MVP-critical or deferrable | MVP-critical for unfixed launch |
| Suggested Codex implementation prompt | "Implement DEA commodity exposure report selectors for open unfixed purchase/sale exposure with partial fixing support and tests." |

### Task 5.6: Valuation Report

| Field | Detail |
|---|---|
| Task name | Commodity valuation report |
| Problem it solves | Management needs base-currency view of metal position value without polluting financial statements. |
| Files likely affected | `dea/services/valuation.py`, `dea/selectors/commodity.py`, `rates/facade.py`, tests. |
| Risk level | Medium |
| Difficulty | Medium |
| Dependencies | Task 3.8, Task 5.4 |
| Expected behavior | Report values metal positions using selected rate source/as-of date and labels valuation as management/reporting value. |
| Required tests | Rate lookup, missing rate behavior, valuation currency, no GL posting. |
| MVP-critical or deferrable | Deferrable unless valuation is launch requirement |
| Suggested Codex implementation prompt | "Implement MVP commodity valuation report using Rates as valuation input. Keep valuation reporting-only and do not create financial journal entries." |

## Phase 6: Workflow And UI Cleanup

Goal: after backend correctness exists, make screens business-event centric.

### Task 6.1: Business Event Dashboard

| Field | Detail |
|---|---|
| Task name | Business event dashboard |
| Problem it solves | Users currently navigate accounting/database objects rather than business events. |
| Files likely affected | DEA or shared dashboard views/templates/navigation. |
| Risk level | Medium |
| Difficulty | Medium |
| Dependencies | Phase 4 minimal flows |
| Expected behavior | Dashboard entry points for purchase, sale, receipt/payment, rate fixing, karigar issue/receipt. |
| Required tests | Route permission, rendered actions, links to document lists/forms. |
| MVP-critical or deferrable | Deferrable until backend operations exist |
| Suggested Codex implementation prompt | "Create a business-event dashboard linking to available DEA commodity/business operations. Keep accounting inspection screens separate." |

### Task 6.2: Purchase And Sale Screens

| Field | Detail |
|---|---|
| Task name | Purchase/sale event screens |
| Problem it solves | Sales/purchase invoice vouchers are monetary accounting forms, not bullion operation screens. |
| Files likely affected | Purchase/sale views/forms/templates/domain app; DEA integration views only if DEA owns MVP docs. |
| Risk level | Medium |
| Difficulty | Large |
| Dependencies | Task 4.1 through Task 4.5 |
| Expected behavior | Fixed/unfixed purchase/sale screens capture party, metal, weights, purity, rate/fixing status, and preview effects. |
| Required tests | Form validation, preview context, post action, permission gates. |
| MVP-critical or deferrable | MVP-critical once operations are implemented |
| Suggested Codex implementation prompt | "Build MVP business-event purchase/sale screens for fixed and unfixed commodity transactions, consuming existing backend services and showing accounting/commodity preview." |

### Task 6.3: Rate Fixing Screens

| Field | Detail |
|---|---|
| Task name | Rate fixing workflow UI |
| Problem it solves | Open exposures need a guided fixing workflow. |
| Files likely affected | Rate fixing views/forms/templates, exposure selectors. |
| Risk level | Medium |
| Difficulty | Medium |
| Dependencies | Task 4.3, Task 5.5 |
| Expected behavior | User selects open exposure, enters fixing weight/rate, previews financial and exposure impact, posts. |
| Required tests | GET preview, POST valid/invalid, partial fixing, permission gates. |
| MVP-critical or deferrable | MVP-critical for unfixed launch |
| Suggested Codex implementation prompt | "Build MVP rate fixing screens backed by ExposureLine and RateFixing services, with preview and permission tests." |

### Task 6.4: Receipt/Payment Screens

| Field | Detail |
|---|---|
| Task name | Receipt/payment workflow cleanup |
| Problem it solves | Receipt/payment should be business-event settlement, not generic voucher editing. |
| Files likely affected | `dea/views/payment.py`, payment templates/forms, settlement selectors/tests. |
| Risk level | Medium |
| Difficulty | Medium |
| Dependencies | Task 4.6 |
| Expected behavior | Monetary receipt/payment screens show party outstanding, allocation, posting preview, and posted result. |
| Required tests | Form validation, settlement allocation, posting status, no commodity exposure settlement. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Refine DEA receipt/payment screens around monetary settlement workflow with preview and posting status. Do not expose commodity settlement through cash payment forms." |

### Task 6.5: Karigar Screens

| Field | Detail |
|---|---|
| Task name | Karigar issue/receipt UI |
| Problem it solves | Karigar custody needs operational screens. |
| Files likely affected | Commodity/karigar views/forms/templates/selectors. |
| Risk level | Medium |
| Difficulty | Medium |
| Dependencies | Task 4.7, Task 4.8 |
| Expected behavior | Issue/receive pages show karigar balances, open issues, weights, wastage, and charges. |
| Required tests | Permission, validation, preview, posting result, report links. |
| MVP-critical or deferrable | MVP-critical for jeweller workflow |
| Suggested Codex implementation prompt | "Build MVP karigar issue and receipt screens using commodity posting services, with tests for preview, posting, and permission boundaries." |

### Task 6.6: Voucher And Journal Detail Cleanup

| Field | Detail |
|---|---|
| Task name | Voucher/journal detail inspection cleanup |
| Problem it solves | Accountants need clear links from business documents to vouchers, journals, account lines, commodity movements, and reversals. |
| Files likely affected | `templates/dea/voucher_detail.html`, `templates/dea/journalentry_detail.html`, related views/selectors. |
| Risk level | Low |
| Difficulty | Medium |
| Dependencies | Phase 2, Task 3.4 |
| Expected behavior | Detail pages show financial effects and commodity effects separately with source links. |
| Required tests | Render context includes linked journal/commodity movements/reversals; permission gate. |
| MVP-critical or deferrable | Deferrable until commodity records exist |
| Suggested Codex implementation prompt | "Clean up DEA voucher and journal detail pages to show source document, financial lines, commodity movements, reversal/correction links, and posting metadata separately." |

### Task 6.7: Commodity Position Dashboard

| Field | Detail |
|---|---|
| Task name | Commodity position dashboard |
| Problem it solves | Commodity balances/exposure need a dedicated overview separate from accounting dashboard. |
| Files likely affected | Commodity dashboard view/template/selectors. |
| Risk level | Low |
| Difficulty | Medium |
| Dependencies | Task 5.4, Task 5.5 |
| Expected behavior | Dashboard shows metal position, open exposure, karigar balances, missing rates, and links to reports. |
| Required tests | Selector context, route permission, empty state. |
| MVP-critical or deferrable | Deferrable |
| Suggested Codex implementation prompt | "Create a commodity position dashboard backed by commodity selectors, showing metal balances, open exposures, karigar balances, and rate warnings." |

## Phase 7: Legacy Cleanup

Goal: remove confusing legacy paths only after replacement flows and tests exist.

### Task 7.1: Deprecate Commodity-As-Currency Logic

| Field | Detail |
|---|---|
| Task name | Deprecate commodity-as-currency paths |
| Problem it solves | Future code may reintroduce metal as financial currency. |
| Files likely affected | `dea/models/currency.py`, form validators, posting validators, tests. |
| Risk level | Critical |
| Difficulty | Medium |
| Dependencies | Phase 1, Phase 3 |
| Expected behavior | Metal-like codes are rejected from financial currency configuration and posting inputs. |
| Required tests | Reject `GOLD`, `SILVER`, `GLD`, `SLV`, `XAU`, `XAG`; allow valid monetary currencies used by project. |
| MVP-critical or deferrable | MVP-critical |
| Suggested Codex implementation prompt | "Implement monetary currency validators that reject metal-like commodity codes in DEA financial currency fields and forms. Include regression tests." |

### Task 7.2: Replace Old Balance Views Safely

| Field | Detail |
|---|---|
| Task name | Balance view replacement or hardening |
| Problem it solves | Current views aggregate by currency and can hide semantic errors. |
| Files likely affected | DEA migrations, `LedgerBalance`, `AccountBalance`, report selectors, tests. |
| Risk level | Critical |
| Difficulty | Large |
| Dependencies | Task 1.3, Task 5.1 |
| Expected behavior | Financial balance views/selectors are monetary-only, tested, and do not include commodity balances. |
| Required tests | Existing characterization tests still pass or are deliberately updated; commodity movements excluded. |
| MVP-critical or deferrable | Deferrable until reports/selectors are stable |
| Suggested Codex implementation prompt | "Harden or replace DEA financial balance views using existing characterization tests. Ensure views/selectors are monetary-only and commodity records are excluded." |

### Task 7.3: Remove Direct View Posting

| Field | Detail |
|---|---|
| Task name | Remove direct voucher post/reverse helpers |
| Problem it solves | Posting logic in views duplicates engine behavior. |
| Files likely affected | `dea/views/voucher.py`, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 2.4, canonical service tests |
| Expected behavior | Voucher UI delegates posting/reversal to canonical services/commands only. |
| Required tests | Post/reverse views use service path, preserve messages/redirects, permissions, failure behavior. |
| MVP-critical or deferrable | Deferrable until services are fully covered |
| Suggested Codex implementation prompt | "Refactor DEA voucher post/reverse views to call the canonical posting/reversal services. Remove direct journal materialization from views after tests cover behavior." |

### Task 7.4: Remove Legacy Direct Write Engine

| Field | Detail |
|---|---|
| Task name | Remove legacy direct write engine |
| Problem it solves | Legacy engine can confuse future posting behavior. |
| Files likely affected | `dea/posting/legacy_direct_write_engine.py`, import tests. |
| Risk level | Medium |
| Difficulty | Small |
| Dependencies | Search proves no runtime callers; tests in Phase 1/2 pass. |
| Expected behavior | No production code imports or uses legacy direct write engine. |
| Required tests | Architecture/import guard test preventing new imports. |
| MVP-critical or deferrable | Deferrable |
| Suggested Codex implementation prompt | "Remove DEA legacy_direct_write_engine after proving no runtime callers remain. Add an architecture guard test preventing reintroduction." |

### Task 7.5: Simplify BusinessDoc Auto-Post

| Field | Detail |
|---|---|
| Task name | Remove or disable implicit BusinessDoc auto-post |
| Problem it solves | Save-time auto-post can hide accounting failures and duplicate explicit commands. |
| Files likely affected | `dea/models/doc.py`, document models, tests. |
| Risk level | High |
| Difficulty | Medium |
| Dependencies | Task 2.1, explicit posting paths covered |
| Expected behavior | Meaningful accounting documents post only through explicit command/service paths. |
| Required tests | Saving source doc does not silently auto-post unless explicitly configured; posting command still works. |
| MVP-critical or deferrable | Deferrable until explicit paths are stable |
| Suggested Codex implementation prompt | "Refactor DEA BusinessDoc auto-post behavior so accounting effects are created only through explicit posting commands. Preserve compatibility where required and add tests." |

### Task 7.6: Remove Confusing Legacy UI

| Field | Detail |
|---|---|
| Task name | Legacy UI cleanup |
| Problem it solves | Generic voucher/database screens confuse normal staff workflows. |
| Files likely affected | DEA urls/views/templates/navigation. |
| Risk level | Low |
| Difficulty | Medium |
| Dependencies | Phase 6 replacement screens |
| Expected behavior | Normal users see business-event screens; accountant/admin retains inspection tools. |
| Required tests | Navigation/permission tests for staff/accountant/admin. |
| MVP-critical or deferrable | Deferrable |
| Suggested Codex implementation prompt | "Clean up DEA navigation so normal staff use business-event screens and accountant/admin users access voucher/journal/ledger inspection tools. Add permission/navigation tests." |

## Recommended Execution Order

1. Phase 1 tasks 1.1 through 1.5.
2. Phase 2 tasks 2.1 through 2.5.
3. Phase 3 ADR and schema plan, then models in small migrations.
4. Phase 4 fixed purchase, unfixed purchase, purchase/sale rate fixing, fixed sale, unfixed sale, receipt/payment, karigar issue/receipt.
5. Phase 5 report selectors for trial balance, party statement, metal balance, exposure.
6. Phase 6 UI only after backend behavior is stable.
7. Phase 7 cleanup only after replacement tests and flows exist.

## Acceptance Criteria For Starting Commodity Models

Do not start Phase 3 implementation until these are true:

- Current financial posting characterization tests pass.
- Current balance view characterization tests pass.
- Trial balance financial-only regression tests exist.
- Data audit for suspicious currency codes has been run or documented.
- Lifecycle ADR is accepted.
- Commodity architecture ADR is accepted.

## Acceptance Criteria For Legacy Cleanup

Do not remove legacy posting/view/balance code until these are true:

- Replacement service path exists.
- Tests cover old behavior and new behavior.
- Data migration/audit risk is understood.
- UI routes have compatibility or explicit deprecation decision.
- `docs/STATUS.md` and relevant implementation docs are updated in the implementation task.
