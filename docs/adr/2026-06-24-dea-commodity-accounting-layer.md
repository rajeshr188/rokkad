---
status: accepted
owner: dea
updated: 2026-06-24
tags: [adr, dea, accounting, commodity, metals, valuation, exposure]
related:
  - ../constitution.md
  - ../domain/accounting.md
  - ../audits/dea_core_accounting_commodity_analysis.md
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - ../implementation/dea-monetary-currency-guardrails.md
  - 2026-06-24-dea-document-voucher-journal-lifecycle.md
---

# ADR: DEA Commodity Accounting Layer

Date: 2026-06-24
Status: Accepted
Owners: DEA Team, Platform Architecture

## Summary

DEA will introduce commodity accounting as a side-by-side layer next to financial double-entry accounting.

Financial accounting remains monetary: INR/USD/AUD/etc, journal entries, ledger transactions, account transactions, trial balance, profit and loss, and balance sheet readiness.

Commodity accounting tracks metals as quantities and obligations: gold/silver, UOM, gross weight, purity/fineness, fine weight, fixed/unfixed exposure, rate fixing, commodity receivable/payable, metal balance, position, and valuation.

Gold, silver, and other metals must not be represented as financial currencies in `MoneyField`, `amount_currency`, balance views, or trial balance logic.

## Context

The DEA commodity audit found a conceptual drift: current financial balance paths are multi-currency and can technically accept arbitrary currency codes. If metal is encoded as a currency code, financial accounting reports can be polluted by commodity balances.

Current evidence:

- `LedgerTransaction`, `AccountTransaction`, `LedgerStatement`, and `AccountStatement` use `MoneyField` and currency columns.
- `dea/utils/currency.py::Balance` is a multi-currency money value object, not a metal balance object.
- `ledger_balances` and `account_balances` aggregate by currency and cannot distinguish monetary currencies from accidental metal codes.
- `ReportsService.trial_balance()` is now protected as base-currency financial reporting, but commodity quantities still need their own model.
- `rates.Rate` already separates `metal`, `currency`, and `purity`, but rates are valuation inputs, not accounting currency configuration.
- Product/Girvi have metal/weight concepts, but they are not immutable DEA commodity accounting records.

The accepted lifecycle ADR says future commodity movements must be immutable and posted side-by-side with financial journal entries, not materialized into financial `LedgerTransaction`.

## Decision

### 1. Commodity Accounting Is Separate From Financial Currency Accounting

DEA will not rename gold/silver into currencies.

Financial fields:

- `money_amount`
- `currency`
- `amount_base`
- `valuation_currency`
- `valuation_amount`

Commodity fields:

- `metal`
- `uom`
- `gross_weight`
- `purity` / `fineness`
- `fine_weight`
- `fixed_status`
- `rate`

Forbidden representations:

- `amount_currency = "GLD"` for physical gold.
- `Money(10, "XAU")` for owned gold quantity.
- `AccountTransaction` as customer/supplier metal receivable/payable.
- Trial balance rows for metal grams or tolas.

### 2. Commodity Records Are Posted Side-By-Side With Vouchers

The target posting shape is:

```text
Business Document
  -> Posting Command
    -> Voucher
      -> Financial JournalEntry + LedgerTransaction + AccountTransaction
      -> CommodityMovement + ExposureLine
      -> Future InventoryMovement adapter
```

Financial effects and commodity effects are created in the same atomic posting command when a business event has both effects.

Examples:

- Fixed purchase: financial payable/inventory value plus commodity movement increasing owned metal.
- Unfixed purchase: commodity movement/exposure now, final monetary payable only when fixed.
- Rate fixing: closes exposure and posts monetary payable/receivable according to fixing side.
- Karigar issue: commodity custody movement, usually no P&L at issue.

### 3. MVP Commodity Models

The MVP layer will start with explicit models that are small enough to implement and test safely.

| Model | MVP status | Purpose |
|---|---|---|
| `Commodity` or `Metal` | MVP | Master data for Gold/Silver and future metals. |
| `CommodityAccount` | MVP | Balance bucket for owned metal, party metal obligation, karigar custody, location/vault, or adjustment account. |
| `CommodityMovement` | MVP | Immutable metal movement or obligation movement linked to source document and optional voucher. |
| `ExposureLine` | MVP | Open fixed/unfixed commodity exposure from purchase/sale/rate-fixing flows. |
| `RateFixing` | MVP | Business document that fixes rate for all/part of open exposure. |
| `CommodityPosition` | Selector first | Derived balance/position by metal/account/party/location/fixed status; persist later only if needed. |
| `CommodityLot` | Deferred | Lot/costing traceability when inventory costing requires it. |
| `ValuationSnapshot` | Deferred | Periodic mark-to-market snapshots and unrealized gain/loss reporting. |
| `SettlementLine` | Deferred | Explicit partial settlement allocation when fixing/payment allocation becomes complex. |

### 4. Commodity Master Data

`Commodity` / `Metal` should contain:

- `code`: tenant-local stable code such as `GOLD` or `SILVER`.
- `name`
- `default_uom`: MVP default should be gram unless tenant policy says otherwise.
- `is_active`

MVP starts with Gold and Silver. Other metals can be enabled later, but financial currency configuration must remain separate.

### 5. Commodity Accounts

`CommodityAccount` is the commodity equivalent of a balance bucket, not a GL account.

Recommended account purposes:

- `OWNED_STOCK`
- `VAULT`
- `KARIGAR_CUSTODY`
- `PARTY_RECEIVABLE`
- `PARTY_PAYABLE`
- `ADJUSTMENT`
- `LOSS_GAIN`

Key fields:

- `metal`
- `account_type` / `purpose`
- optional `party`
- optional `location`
- optional `financial_control_ledger` for reconciliation only
- `is_active`

Commodity accounts must not appear in financial chart of accounts or trial balance as metal balances.

### 6. Commodity Movements

`CommodityMovement` is an immutable posted row.

Key fields:

- `source_content_type`, `source_object_id`
- optional `voucher`
- `movement_date`
- `metal`
- `uom`
- `gross_weight`
- `purity`
- `fine_weight`
- `from_account`
- `to_account`
- `movement_type`
- `fixed_status`
- optional `rate`
- optional `valuation_currency`
- optional `valuation_amount`
- optional `is_reversal_of`
- actor/audit metadata

Rules:

- Fine weight is the primary balance quantity.
- Gross weight and purity are retained for traceability.
- Posted movements are immutable.
- Reversal is an opposite movement linked to the original movement.
- Movement creation belongs in commodity posting services, not views/templates.

### 7. Exposure And Rate Fixing

Unfixed transactions need explicit exposure. They must not create false final AR/AP or revenue/purchase values before rate is fixed.

`ExposureLine` should contain:

- source document/event
- party
- metal
- side: purchase/sale
- original fine weight
- open fine weight
- fixed status
- rate basis/reference
- valuation currency
- optional current valuation amount for reporting

`RateFixing` should contain:

- fixing number/date
- party
- linked exposure(s)
- metal
- fine weight fixed
- rate
- currency
- financial posting voucher

Posting a rate fixing reduces open exposure and creates/adjusts monetary receivable/payable according to the exposure side.

### 8. Valuation Policy Is Reporting-First For MVP

MVP valuation uses market rates from the rates module as reporting inputs.

Initial policy:

- Store transaction rate/fixing rate on source documents and commodity records where needed.
- Derive current valuation in selectors/reports using `rates.Rate`.
- Do not post unrealized gain/loss automatically in MVP.
- Defer persisted `ValuationSnapshot` until period reporting or mark-to-market requirements are clear.

### 9. Integration Boundaries

DEA commodity accounting should expose services/selectors to domain apps.

Suggested future files:

- `apps/tenant_apps/dea/models/commodity.py`
- `apps/tenant_apps/dea/services/commodity_posting.py`
- `apps/tenant_apps/dea/services/commodity_reports.py`
- `apps/tenant_apps/dea/services/valuation.py`
- `apps/tenant_apps/dea/selectors/commodity.py`
- `apps/tenant_apps/dea/posting/commodity_types.py`

Product/inventory and Girvi should not write commodity rows directly. They should call a DEA commodity posting facade or service with a structured business-event payload.

### 10. Tenant And Data Safety

Commodity schema changes are tenant app changes and must use `migrate_schemas` guidance.

Before data migration:

- Run `audit_dea_currency_codes` across tenant schemas.
- Identify metal-like values in financial currency columns.
- Verify whether any tenant has `GLD`, `SLV`, `XAU`, `XAG`, `GOLD`, `SILVER`, or local metal codes in money columns.
- Do not auto-convert suspicious values without manual verification.

Commodity models will be introduced side-by-side. Existing financial reports remain unchanged except for stronger guardrails preventing metal-like currency codes.

## Consequences

Positive:

- Trial balance remains financial and base-currency safe.
- Metal balances become explicit and auditable.
- Fixed/unfixed bullion workflows get a correct model.
- Girvi collateral, product stock, karigar custody, and future purchase/sale flows can reconcile through one commodity layer.
- Rate fixing and exposure can be added without corrupting financial GL.

Tradeoffs:

- More models and services than the current money-only implementation.
- Business documents must decide whether they produce financial effects, commodity effects, or both.
- Reports must be split into financial reports and commodity reports.
- Existing multi-currency balance code stays for money only and needs guardrails.

## Implementation Direction

Near-term Phase 3 order:

1. Create detailed commodity model schema plan before migrations.
2. Implement `Commodity` / `Metal` and `CommodityAccount` with model tests.
3. Implement immutable `CommodityMovement` with reversal linkage and selectors.
4. Implement `ExposureLine` and `RateFixing` model tests.
5. Add `commodity_posting` service skeleton.
6. Add commodity position selectors and basic metal balance report tests.
7. Only then wire fixed/unfixed purchase/sale operations.

## Non-Goals

This ADR does not implement:

- Commodity migrations.
- Commodity UI.
- Inventory costing lots.
- Automated mark-to-market accounting.
- Hedging/risk analytics.
- Full enterprise commodity trading functionality.

Those remain future phases after MVP metal movement, exposure, and fixing behavior is stable.
