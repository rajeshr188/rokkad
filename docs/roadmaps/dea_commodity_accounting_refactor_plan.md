---
status: active
owner: project
updated: 2026-06-24
tags: [roadmap, dea, accounting, commodity, refactor]
related:
  - ../audits/dea_core_accounting_commodity_analysis.md
  - ../AGENT_MEMORY.md
  - ../STATUS.md
  - ../constitution.md
  - ../domain/accounting.md
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

Current next task:

- Start Phase 3 with `docs/adr/YYYY-MM-DD-dea-commodity-accounting-layer.md`, defining the side-by-side commodity layer before model migrations.

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
4. Phase 4 fixed purchase, unfixed purchase, rate fixing, fixed sale.
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
