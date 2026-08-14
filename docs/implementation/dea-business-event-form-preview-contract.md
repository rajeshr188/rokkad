---
status: active
owner: dea
updated: 2026-06-24
tags: [implementation, dea, commodity, ui, posting, preview]
related:
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - ../audits/dea_core_accounting_commodity_analysis.md
  - ../adr/2026-06-24-dea-document-voucher-journal-lifecycle.md
  - ../adr/2026-06-24-dea-commodity-accounting-layer.md
  - dea-canonical-posting-path.md
  - dea-reversal-correction-contract.md
  - dea-commodity-model-schema.md
---

# DEA Business Event Form And Preview Contract

## Purpose

This document defines the UI and service contract for DEA business-event screens before mutation forms are wired.

The immediate goal is to prevent Phase 6 UI work from becoming another direct voucher/journal editing surface. Business-event screens must collect business facts, show a deterministic preview, and then hand off to existing backend services through explicit POST commands.

This contract does not add app code by itself. It is the implementation target for the next UI slices.

## Non-Negotiable Rules

- UI forms collect business facts, not debit/credit rows.
- Preview is read-only and must not create vouchers, journal entries, account transactions, ledger transactions, commodity movements, exposures, rate fixings, or payment vouchers.
- Posting happens only through backend service functions already covered by tests.
- Monetary fields use monetary currency only. Gold, silver, and other metals are selected through `Commodity` and weight fields.
- Draft screens may be edited. Posted documents are corrected by reversal plus corrected reposting, not by editing posted effects.
- Normal staff users see document workflow, preview, and posting result. Accountant/admin users may inspect voucher, journal, ledger, account, commodity movement, and exposure details.
- Every POST must use an idempotency source identity plus economic payload. Browser double-submit must not create duplicate effects.

## Screen Pattern

Every event screen should follow the same shape:

```text
GET form
  -> user enters business facts
POST preview or HTMX preview
  -> validate and normalize payload
  -> render Accounting Impact, Commodity Impact, Inventory Impact, Warnings
POST confirm
  -> call one backend service inside atomic boundary
  -> redirect to source/event detail or voucher/impact detail
```

The first implementation can combine form and preview on one page, but the logical boundary must remain clear: preview validates and explains; confirm posts.

## Preview Payload Shape

All preview builders should return a plain read model. Do not pass Django model instances directly to templates when a simpler display payload can be used.

```python
{
    "event_type": "fixed_purchase",
    "source": {
        "model": "dea.BusinessEventDraft",
        "object_id": "...",
        "display": "Purchase draft ...",
    },
    "status": "valid",  # valid | invalid | warning
    "idempotency_key_preview": "...",
    "business_facts": {...},
    "accounting_impact": {
        "creates_financial_posting": True,
        "currency": "INR",
        "debits": [{"ledger": "Inventory", "amount": "100000.00"}],
        "credits": [{"ledger": "Supplier Payable", "account": "...", "amount": "100000.00"}],
    },
    "commodity_impact": {
        "creates_commodity_movement": True,
        "metal": "GOLD",
        "gross_weight": "100.000",
        "purity": "0.995000",
        "fine_weight": "99.500",
        "from_account": "...",
        "to_account": "...",
        "fixed_status": "FIXED",
    },
    "exposure_impact": {
        "creates_exposure": False,
        "side": "",
        "open_fine_weight": "0.000",
    },
    "inventory_impact": {
        "status": "deferred",
        "message": "Inventory lot/costing integration is not in this MVP slice.",
    },
    "warnings": [],
    "errors": {},
}
```

The `idempotency_key_preview` may be masked or shortened for UI display, but the confirm POST must use the same normalized economic facts that produced the preview.

## Source Draft Boundary

The Phase 4 backend services currently require a saved `source` model. The UI must not use unsaved form state directly for posting.

MVP options, in preferred order:

1. Add a small DEA business-event draft/source model for each event family or one generic typed `BusinessEventDraft`.
2. Reuse an existing source document only where the existing model truly represents the business event.
3. Use a temporary draft object only for preview, then save before confirm.

Do not use `Voucher` as the source document for commodity business events. Voucher is accounting evidence, not the operational business fact record.

## Common Form Fields

Common fields for commodity events:

| Field | Required | Notes |
|---|---|---|
| `event_date` | Yes | Must belong to an open accounting period before confirm. |
| `party` | Event-specific | Supplier/customer/karigar as Party. |
| `commodity` | Yes | MVP: Gold/Silver. |
| `gross_weight` | Yes | Decimal, positive. |
| `purity` | Yes | Decimal, positive; normalize to internal fineness scale. |
| `fine_weight` | Yes | Calculated from gross/purity, editable only if policy allows. |
| `uom` | Yes | MVP default `g`. |
| `narration` | No | Stored in voucher/movement metadata. |
| `source_reference` | Yes | Human document number/reference for idempotency and audit. |

Common monetary fields:

| Field | Required | Notes |
|---|---|---|
| `money_amount` | Fixed/settlement flows | Positive Decimal. |
| `currency` | Monetary flows | MVP supports `INR`; must be monetary code. |
| `rate` | Fixed/rate-fixing flows | Positive Decimal per fine-weight unit. |
| `reference_number` | Settlement flows | Required for payment idempotency. |

Common account resolution:

| Account | Source |
|---|---|
| Customer/supplier monetary account | DEA party account mapping or existing account resolver. |
| Cash/bank ledger | Selected by user or default cash/bank configuration. |
| Inventory/payable/receivable/revenue ledgers | Configured defaults, visible in preview to accountant/admin. |
| Owned/vault commodity account | Configured default by metal/location. |
| Party commodity account | Derived from party/commodity/purpose where applicable. |
| Karigar custody account | Derived from karigar party, commodity, and `KARIGAR_CUSTODY` purpose. |

## Event Contracts

### Fixed Purchase

Service handoff: `apps.tenant_apps.dea.services.fixed_purchase.post_fixed_purchase()`.

Payload class: `FixedPurchasePostingPayload`.

Required form facts:

- source draft/reference
- purchase date
- supplier party/account
- inventory ledger
- payable ledger
- commodity
- gross weight
- purity
- fine weight
- supplier/from commodity account
- owned/vault/to commodity account
- money amount
- INR currency

Preview must show:

- Financial: Dr inventory ledger, Cr supplier payable ledger/account.
- Commodity: movement type `PURCHASE_RECEIPT`, fixed status `FIXED`, from supplier/offset account to owned/vault account.
- Exposure: none.
- Inventory: deferred stock/lot note.

Confirm behavior:

- Creates posted financial voucher/journal/account/ledger effects.
- Creates one immutable fixed `CommodityMovement`.
- Does not create `ExposureLine` or `RateFixing`.

### Unfixed Purchase

Service handoff: `apps.tenant_apps.dea.services.unfixed_purchase.post_unfixed_purchase()`.

Payload class: `UnfixedPurchasePostingPayload`.

Required form facts:

- source draft/reference
- purchase date
- supplier party
- commodity
- gross weight
- purity
- fine weight
- supplier/from commodity account
- owned/vault/to commodity account
- rate basis or terms
- valuation currency, default `INR`

Preview must show:

- Financial: no final payable and no journal entry before fixing.
- Commodity: movement type `PURCHASE_RECEIPT`, fixed status `UNFIXED`.
- Exposure: purchase-side open exposure for fine weight.
- Valuation: optional reporting-only valuation status.

Confirm behavior:

- Creates posted commodity-intent voucher.
- Creates one immutable `CommodityMovement`.
- Creates one open purchase `ExposureLine`.
- Does not create `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or `VoucherLine`.

### Purchase Rate Fixing

Service handoff: `apps.tenant_apps.dea.services.rate_fixing.post_purchase_rate_fixing()`.

Payload class: `PurchaseRateFixingPayload`.

Required form facts:

- open purchase exposure
- fixing date
- fine weight to fix
- rate
- supplier monetary account
- inventory ledger
- payable ledger
- INR currency

Preview must show:

- Financial: Dr inventory/valuation ledger, Cr supplier payable account.
- Commodity: no physical movement.
- Exposure: open purchase exposure reduced by fixing fine weight; fully fixed if remaining is zero.
- Settlement amount: `fine_weight * rate`, rounded to money precision.

Confirm behavior:

- Creates `RateFixing` and `RateFixingAllocation`.
- Posts monetary payable through financial voucher/journal/account/ledger rows.
- Reduces or closes the exposure.

### Fixed Sale

Service handoff: `apps.tenant_apps.dea.services.fixed_sale.post_fixed_sale()`.

Payload class: `FixedSalePostingPayload`.

Required form facts:

- source draft/reference
- sale date
- customer party/account
- receivable ledger
- revenue ledger
- commodity
- gross weight
- purity
- fine weight
- owned/vault/from commodity account
- money amount
- INR currency

Preview must show:

- Financial: Dr customer receivable ledger/account, Cr revenue ledger.
- Commodity: movement type `SALE_ISSUE`, fixed status `FIXED`, from owned/vault account out.
- Exposure: none.
- Inventory: COGS/lot costing deferred unless later policy is available.

Confirm behavior:

- Creates posted financial voucher/journal/account/ledger effects.
- Creates one immutable outgoing fixed `CommodityMovement`.
- Does not create `ExposureLine` or `RateFixing`.

### Unfixed Sale

Service handoff: `apps.tenant_apps.dea.services.unfixed_sale.post_unfixed_sale()`.

Payload class: `UnfixedSalePostingPayload`.

Required form facts:

- source draft/reference
- sale date
- customer party
- commodity
- gross weight
- purity
- fine weight
- owned/vault/from commodity account
- rate basis or terms
- valuation currency, default `INR`

Preview must show:

- Financial: no final receivable/revenue before fixing.
- Commodity: movement type `SALE_ISSUE`, fixed status `UNFIXED`.
- Exposure: sale-side open exposure for fine weight.
- Inventory: COGS/lot costing deferred.

Confirm behavior:

- Creates posted commodity-intent voucher.
- Creates one immutable outgoing `CommodityMovement`.
- Creates one open sale `ExposureLine`.
- Does not create `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or `VoucherLine`.

### Sale Rate Fixing

Service handoff: `apps.tenant_apps.dea.services.rate_fixing.post_sale_rate_fixing()`.

Payload class: `SaleRateFixingPayload`.

Required form facts:

- open sale exposure
- fixing date
- fine weight to fix
- rate
- customer monetary account
- receivable ledger
- revenue ledger
- INR currency

Preview must show:

- Financial: Dr customer receivable account, Cr revenue ledger.
- Commodity: no physical movement.
- Exposure: open sale exposure reduced by fixing fine weight; fully fixed if remaining is zero.
- Settlement amount: `fine_weight * rate`, rounded to money precision.

Confirm behavior:

- Creates `RateFixing` and `RateFixingAllocation`.
- Posts monetary receivable/revenue through financial voucher/journal/account/ledger rows.
- Reduces or closes the exposure.

### Customer Receipt

Service handoff: `apps.tenant_apps.dea.services.monetary_settlement.post_customer_receipt()`.

Payload class: `CustomerReceiptPayload`.

Required form facts:

- source document/reference
- receipt date
- customer account
- cash/bank ledger
- receivable ledger
- money amount
- reference number
- INR currency
- payment method

Preview must show:

- Financial: Dr cash/bank, Cr customer receivable.
- Commodity: none.
- Exposure: none.

Confirm behavior:

- Creates `PaymentVoucher`.
- Creates financial voucher/journal/account/ledger effects.
- Does not create `CommodityMovement`, `ExposureLine`, or `RateFixing`.

### Supplier Payment

Service handoff: `apps.tenant_apps.dea.services.monetary_settlement.post_supplier_payment()`.

Payload class: `SupplierPaymentPayload`.

Required form facts:

- source document/reference
- payment date
- supplier account
- payable ledger
- cash/bank ledger
- money amount
- reference number
- INR currency
- payment method

Preview must show:

- Financial: Dr supplier payable, Cr cash/bank.
- Commodity: none.
- Exposure: none.

Confirm behavior:

- Creates `PaymentVoucher`.
- Creates financial voucher/journal/account/ledger effects.
- Does not create `CommodityMovement`, `ExposureLine`, or `RateFixing`.

### Karigar Issue

Service handoff: `apps.tenant_apps.dea.services.karigar.post_karigar_issue()`.

Payload class: `KarigarIssuePayload`.

Required form facts:

- source draft/reference
- issue date
- karigar party
- commodity
- gross weight
- purity
- fine weight
- owned/vault/from commodity account
- karigar custody/to commodity account

Preview must show:

- Financial: none for MVP.
- Commodity: movement type `KARIGAR_ISSUE`, fixed status `NOT_APPLICABLE`, from owned/vault to karigar custody.
- Exposure: none.
- Inventory: custody/location transfer note.

Confirm behavior:

- Creates posted commodity-intent voucher.
- Creates one immutable `CommodityMovement`.
- Does not create financial rows, exposures, or rate fixings.

### Karigar Receipt

Service handoff: `apps.tenant_apps.dea.services.karigar.post_karigar_receipt()`.

Payload class: `KarigarReceiptPayload`.

Required form facts:

- source draft/reference
- receipt date
- karigar party
- commodity
- gross weight
- purity
- fine weight
- karigar custody/from commodity account
- owned/vault/to commodity account

Preview must show:

- Financial: none for MVP unless later making-charge accounting is added.
- Commodity: movement type `KARIGAR_RECEIPT`, fixed status `NOT_APPLICABLE`, from karigar custody to owned/vault.
- Exposure: none.
- Inventory: custody/location receipt note.

Confirm behavior:

- Creates posted commodity-intent voucher.
- Creates one immutable `CommodityMovement`.
- Does not create financial rows, exposures, or rate fixings.

## Permission Contract

MVP permission split:

| Role | Allowed |
|---|---|
| Staff/operator | Create drafts, request preview, submit allowed business events if workspace policy permits. |
| Accountant | All staff actions, plus inspect vouchers, journal entries, ledgers, account statements, report diagnostics. |
| Admin/owner | Configuration, defaults, reversal/correction tools, legacy diagnostic screens. |

The first mutation screens may be owner/admin/accountant-only until operational permission policy is explicit.

## Error And Warning Contract

Validation errors should be field-addressable and template-safe:

```python
{
    "gross_weight": ["Gross weight must be positive."],
    "currency": ["Fixed purchase MVP currently supports INR only."],
    "non_field_errors": ["Accounting period is closed."],
}
```

Warnings should not block preview but may block confirm if policy requires:

- Missing default ledger/account mapping.
- Missing commodity account mapping.
- Missing latest market rate for valuation preview.
- Inventory lot/costing integration deferred.
- Posting date belongs to a closing period.

## Idempotency And Race Control

Confirm POST must include:

- source model and source id
- event type
- source reference
- normalized economic payload hash
- CSRF token

The service layer remains the final idempotency authority. UI-level hidden keys are only hints for duplicate-submit handling.

Implementation requirements:

- Use atomic service calls.
- Disable submit button after click, but never rely on that for correctness.
- On duplicate payload, show existing posted result.
- On changed payload for same source, require correction/reversal flow.
- Do not expose a second direct endpoint that bypasses preview normalization.

## Detail Page Contract

After confirm, redirect to a document/event detail page or interim posting-result page with these sections:

- Business Facts
- Posting Status
- Accounting Impact
- Commodity Impact
- Inventory Impact
- Timeline
- Links: Voucher, Journal Entry, Account Lines, Ledger Lines, Commodity Movement, Exposure, Rate Fixing, Reports

The detail page should hide raw journal/voucher diagnostics from normal staff users while still showing a simple "posted successfully" result and business-readable impact.

## Deferred Items

- Taxes, GST, making charges, wastage, COGS, lot costing, and inventory valuation.
- Non-INR monetary postings and FX valuation.
- Metal-in-kind settlement.
- Partial payment allocation against invoices/fixings.
- Explicit operational purchase/sale document models outside DEA.
- Commodity sidecar reversal UI.
- Valuation snapshots and unrealized gain/loss journal policy.

## Current Implementation Status

The Phase 6 business-event UI now follows this contract for fixed/unfixed purchase, fixed/unfixed sale, purchase/sale rate fixing, receipt/payment, and karigar custody previews.

Implemented confirm endpoint/result surfaces exist for fixed purchase, unfixed purchase, fixed sale, unfixed sale, purchase/sale rate fixing, receipt/payment, and karigar custody movements. These endpoints are POST-only, owner/admin/accountant-gated, delegate to tested handoff services, and redirect to read-only result pages.

The karigar custody screen at `/dea/business-events/karigar/` captures issue or receipt facts, persists `KARIGAR_ISSUE` / `KARIGAR_RECEIPT` `BusinessEventDraft` rows, renders readiness, and posts through `/dea/business-events/karigar/<draft_id>/confirm/`. Confirmed karigar custody movement creates a posted commodity-intent voucher and custody `CommodityMovement` only; it does not create financial, exposure, rate-fixing, or payment rows.

## Next Implementation Slice

The next safe code slice is a Phase 6 completion checkpoint before Phase 7 legacy cleanup. It should:

- Summarize which business events now produce financial rows, commodity rows, exposure rows, rate-fixing rows, and payment rows.
- Run focused business-event, posting-service, commodity-report, financial-report, and statement-boundary suites serially.
- Verify dashboard and detail navigation for every event.
- Document remaining MVP gaps: taxes, COGS, wastage, inventory lots, payment/fixing allocation, sidecar reversal UI, broader tenant/isolation regression, and legacy UI cleanup.
