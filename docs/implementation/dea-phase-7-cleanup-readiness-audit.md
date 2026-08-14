---
status: active
owner: project
updated: 2026-06-25
tags: [dea, phase-7, cleanup, accounting, legacy]
related:
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - dea-phase-6-business-event-checkpoint.md
  - dea-canonical-posting-path.md
  - dea-reversal-correction-contract.md
  - ../STATUS.md
  - ../AGENT_MEMORY.md
---

# DEA Phase 7 Cleanup Readiness Audit

Phase 7 cleanup starts with characterization, not deletion. The goal is to remove or hide confusing legacy surfaces only after proving replacement workflows exist and accountant workflows remain intact.

## Cleanup Rule

Do not delete, hide, or redirect any DEA accounting surface until it is classified and covered by tests.

## Surface Classification

| Surface | Current route/code | Current role | Phase 7 classification | Cleanup direction |
|---|---|---|---|---|
| Business events dashboard | `dea_business_events_dashboard`, `views/business_events.py` | Operational entry point for purchase, sale, rate fixing, settlement, karigar flows. | Keep. | Preferred staff workflow. Continue improving workflow UX, not legacy cleanup target. |
| Business-event confirm routes | `dea_fixed_purchase_confirm`, `dea_unfixed_purchase_confirm`, `dea_purchase_rate_fixing_confirm`, `dea_fixed_sale_confirm`, `dea_unfixed_sale_confirm`, `dea_sale_rate_fixing_confirm`, `dea_monetary_settlement_confirm`, `dea_karigar_movement_confirm` | Canonical MVP event posting routes. | Keep. | These replace routine staff voucher editing for covered business events. |
| Voucher hub | `dea_voucher_hub`, `views/voucher_hub.py` | Accountant/admin entry point to manual accounting documents. | Keep with label hardening. | Should be accountant-facing, not normal staff default. |
| Generic voucher CRUD | `dea_voucher_list`, `dea_voucher_detail`, `dea_voucher_create`, `dea_voucher_update`, `dea_voucher_delete` | Manual voucher inspection and draft/manual line entry. | Keep temporarily; characterize further. | Keep for accountants until business-event coverage and permission boundaries are complete. |
| Generic voucher post | `dea_voucher_post`, `views/voucher.py::post_voucher` | Posts draft vouchers. | Keep as accountant/manual path. | Already delegates to `PostVoucherCommand(DjangoPostingEngine())`; now owner/admin/accountant gated. |
| Generic voucher reverse | `dea_voucher_reverse`, `views/voucher.py::reverse_voucher` | Reverses posted vouchers. | Keep as accountant/manual path. | Already delegates to `reverse_posted_voucher()`; now owner/admin/accountant gated. |
| Payment voucher CRUD | `dea_payment_*`, `views/payment.py` | Legacy/direct monetary payment entry. | Characterize before hiding. | Covered operationally by receipt/payment business events for basic customer receipt and supplier payment; now owner/admin/accountant gated while remaining legacy/accountant accessible. |
| Expense voucher CRUD/post | `dea_expense_*`, `views/expense.py::post_expense_voucher` | Expense-specific accounting document and direct post button. | Characterized; keep temporarily. | Focused tests now prove direct-payment idempotency and closed-period no-materialization. Now owner/admin/accountant gated until a replacement command facade or business-event flow is chosen. |
| Journal entry voucher CRUD | `dea_journal_entry_voucher_*`, `views/journal_entry_voucher.py` | Accountant manual JE document. | Keep. | Manual financial adjustment remains MVP-critical for accountants; now owner/admin/accountant gated. |
| DEA sales invoice voucher | `dea_sales_invoice_create`, `views/sales_invoice.py` | Legacy accounting sales invoice surface. | Replace/hide later after characterization. | Business-event fixed/unfixed sale now covers commodity-aware sale flows; legacy sales invoice may remain for non-commodity monetary invoice workflows. |
| Purchase invoice voucher model/views | `PurchaseInvoiceVoucher`, `views/purchase_invoice.py` if routed elsewhere | Legacy accounting purchase invoice surface. | Needs verification. | Commodity purchase events cover bullion purchase; preserve monetary purchase behavior until non-commodity purchase policy is clear. |
| Opening balance routes | `views/opening_balance.py` routes | Financial opening balances. | Keep; split commodity opening later. | Financial opening balance remains needed; commodity opening balance needs separate future flow. |
| Ledger/account statements | `ledger/*`, `account/*`, audit/statement routes | Financial ledger/subledger inspection. | Keep. | Must remain monetary-only; do not use for commodity balances. |
| Commodity reports | `dea_metal_balance_report`, `dea_exposure_report`, `dea_valuation_report` | Commodity read models. | Keep. | These are the replacement reporting paths for metal positions/exposure/valuation. |
| Legacy direct-write engine | `posting/legacy_direct_write_engine.py` | Historical posting implementation. | Delete after import audit and final confirmation. | Runtime code should not import it. Phase 7 guard test now protects this. |
| Old materialization helpers in `views/voucher.py` | `_create_journal_entry`, `_create_ledger_transactions`, `_create_account_transactions`, `_create_reversal_journal_entry` | Historical helper code retained in voucher view module. | Removed. | Guard tests now fail if these helper definitions return to the voucher view. |
| SQL balance views | `ledger_balances`, `account_balances` migrations/views | Financial read model. | Keep with guardrails. | Do not replace during cleanup; they need their own tested migration strategy. |

## Direct Posting Surface Inventory

| Posting surface | Current implementation | Risk | Required characterization before cleanup |
|---|---|---|---|
| Business event confirm services | `services/business_event_posting.py` delegates to event-specific services. | Low; canonical for covered events. | Existing business-event route and service tests. |
| Generic voucher post view | `views/voucher.py::post_voucher` -> `PostVoucherCommand(DjangoPostingEngine())`. | Medium; accountant manual route. | Existing tests prove stored-line manual posting and closed-period rejection. |
| Generic voucher reverse view | `views/voucher.py::reverse_voucher` -> `reverse_posted_voucher()`. | Medium; accountant correction route. | Existing tests prove service delegation and draft rejection. |
| Expense voucher post view | `views/expense.py::post_expense_voucher` -> `create_and_post_voucher_for_doc()`. | Medium/High; direct document post path. | Characterized for direct-payment idempotency, closed-period behavior, and no duplicate journal rows. |
| `create_and_post_voucher_for_doc()` | Canonical document-to-voucher service for existing financial docs. | Medium; broad dependency surface. | Already covered by financial posting characterization; keep. |
| `PostVoucherCommand` manual stored-line fallback | Posts `VoucherLine` rows for manual vouchers. | Medium; useful accountant path but financial-only. | Existing tests cover manual line posting; add currency guard tests before broad UI exposure changes. |
| `posting/legacy_direct_write_engine.py` | Historical duplicate implementation. | High if imported. | Phase 7 guard test proves no runtime imports from DEA/Girvi runtime modules. |

## Characterization Added In This Slice

Added `apps/tenant_apps/dea/tests/test_phase7_cleanup_readiness.py`.

It currently proves:

- Accountant legacy routes still resolve before cleanup:
  - `dea_voucher_hub`
  - `dea_voucher_post`
  - `dea_voucher_reverse`
  - `dea_expense_post`
- Runtime DEA/Girvi modules do not import `apps.tenant_apps.dea.posting.legacy_direct_write_engine`.

This test is deliberately small. It gives Phase 7 a safety rail without changing runtime behavior.

Added `apps/tenant_apps/dea/tests/test_financial_posting_characterization.py` coverage for `views/expense.py::post_expense_voucher()`.

It currently proves:

- A direct-payment expense post creates one posted voucher, one journal entry, and balanced financial ledger effects.
- Re-submitting the same expense post route is idempotent and does not create duplicate posted vouchers or journal entries.
- A closed accounting period redirects without creating posted vouchers, ledger transactions, or account transactions.

The closed-period path still logs the caught posting failure through the legacy view wrapper. That behavior is characterized, not redesigned, in this slice.

Removed dead helper definitions from `apps/tenant_apps/dea/views/voucher.py`.

This slice:

- Confirmed runtime searches only found these helpers as definitions in the voucher view module, not as active DEA/Girvi callers.
- Removed `_create_journal_entry()` and `_create_reversal_journal_entry()` from `views/voucher.py`.
- Kept active voucher posting through `PostVoucherCommand(DjangoPostingEngine())`.
- Kept active voucher reversal through `services.reversal.reverse_posted_voucher()`.
- Added a Phase 7 guard test that fails if `_create_journal_entry`, `_create_ledger_transactions`, `_create_account_transactions`, or `_create_reversal_journal_entry` are reintroduced into `views/voucher.py`.

Added `apps/tenant_apps/dea/views/access.py` and `apps/tenant_apps/dea/tests/test_phase7_permission_boundaries.py`.

This slice:

- Adds shared DEA accountant-only access helpers:
  - `assert_dea_accountant_access()`
  - `dea_accountant_required`
  - `DeaAccountantRequiredMixin`
- Allows platform superuser/staff, workspace owner, and workspace roles `Owner`, `Admin`, or `Accountant`.
- Fails closed when no tenant workspace is resolved from the request.
- Applies the boundary to:
  - voucher hub
  - generic voucher CRUD/post/reverse
  - payment voucher CRUD
  - expense voucher CRUD/post
  - manual journal-entry voucher CRUD
  - opening balance wizard/import/template/validation endpoints
- Tests owner access for representative GET surfaces.
- Tests `Member` role denial for representative GET surfaces and post/reverse actions before object lookup.
- Leaves period lock/unlock on the existing Django permission decorators for this slice; that remains a follow-up because those routes already require `dea.can_lock_period` / `dea.can_unlock_period`.

## Immediate Phase 7 Work Queue

1. Characterize expense voucher posting. Complete.
   - Focused tests cover `post_expense_voucher()` idempotency, closed-period behavior, and duplicate journal prevention for direct-payment expenses.
   - Keep it temporarily as accountant-only until a thinner command facade or replacement business-event flow is chosen.

2. Confirm no runtime callers use old helper functions in `views/voucher.py`. Complete.
   - Search/call graph for `_create_journal_entry`, `_create_ledger_transactions`, `_create_account_transactions`, and `_create_reversal_journal_entry`.
   - Deleted the dead helper definitions after focused voucher post/reverse characterization passed.

3. Permission audit for legacy/accountant surfaces. Complete for first high-risk slice.
   - Generic voucher, payment, expense, journal-entry, opening-balance, period-locking, and reversal routes should be owner/admin/accountant gated before staff rollout.
   - Implemented shared owner/admin/accountant gating for voucher, payment, expense, manual journal voucher, and opening-balance surfaces.
   - Period lock/unlock still require their existing Django permissions and should be reviewed in a follow-up if workspace-role-only access is desired.

4. Navigation cleanup.
   - Normal staff navigation should emphasize business events.
   - Accountant/admin navigation may retain voucher, journal, ledger, period, and diagnostic routes.

5. Legacy sales/purchase invoice policy.
   - Decide whether DEA sales/purchase invoice voucher screens remain as monetary-only accountant tools or become hidden behind legacy/accountant menus.
   - Do not delete until non-commodity purchase/sale requirements are clear.

6. Legacy direct-write engine deletion.
   - Delete `posting/legacy_direct_write_engine.py` only after import guard and posting/reversal characterization pass in the same PR.

## Current Recommendation

Next code slice: navigation cleanup. Keep normal staff pointed at business events and reports, while retaining voucher, payment, expense, manual journal, opening-balance, period, and diagnostic routes under accountant/admin-facing navigation.
