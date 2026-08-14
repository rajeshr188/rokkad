---
status: active
owner: project
updated: 2026-06-24
tags: [implementation, dea, accounting, currency, commodity]
related:
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - ../audits/dea_core_accounting_commodity_analysis.md
  - ../domain/accounting.md
  - ../constitution.md
---

# DEA Monetary Currency Guardrails

## Purpose

DEA financial accounting must treat `currency` as monetary currency only. Gold, silver, and other commodities must not enter financial `MoneyField`, `amount_currency`, statement currency, exchange-rate, trial-balance, ledger-balance, or account-balance paths as commodity quantity.

This note defines the policy and future validation points. It does not introduce commodity models. Commodity accounting will be added side-by-side later.

## Current Problem

Current DEA money paths accept currency-like strings through `djmoney` and raw database fields:

- `LedgerTransaction.amount_currency`
- `LedgerTransaction.amount_base_currency`
- `AccountTransaction.amount_currency`
- `LedgerStatement.ClosingBalance_currency`
- `AccountStatement.ClosingBalance_currency`
- `AccountStatement.TotalCredit_currency`
- `AccountStatement.TotalDebit_currency`
- `VoucherLine.amount_currency`
- `VoucherLine.amount_base_currency`
- `CurrencyConfiguration.base_currency`
- `CurrencyConfiguration.enabled_currencies`
- `ExchangeRate.base_currency`
- `ExchangeRate.quote_currency`

These fields are financial accounting fields. They must never store physical metal quantities.

## Monetary Currency Policy

### Allowed Meaning

In DEA, a monetary currency code means a legal/fiat or supported money unit used to value transactions, reports, receivables, payables, cash, bank, revenue, expenses, assets, liabilities, or equity.

Examples:

- `INR`
- `USD`
- `AUD`
- `EUR`
- `GBP`
- Other ISO 4217 monetary currencies enabled by tenant policy.

### Disallowed Meaning

The following must not be used as DEA financial currencies to represent commodity balances:

- `XAU`
- `XAG`
- `GLD`
- `SLV`
- `GOLD`
- `SILVER`
- `AU`
- `AG`
- `24K`
- `22K`
- Local metal shorthand codes.

Important nuance: ISO 4217 includes precious-metal codes such as `XAU` and `XAG`, but this project must not use those codes to represent physical gold/silver balances in financial ledgers. If market-price feeds later use those symbols, they belong in rates/valuation context, not in DEA financial transaction currency columns.

## Target Rule

Financial posting must carry:

- `money_amount`
- `currency`
- `amount_base`
- `amount_base_currency`, normally `INR`

Commodity posting must carry separate fields:

- `metal`
- `uom`
- `gross_weight`
- `purity`
- `fine_weight`
- `fixed_status`
- `rate`
- `valuation_currency`
- `valuation_amount`

Do not encode commodity quantity as `Money(10, "XAU")` or `amount_currency = "GLD"`.

## Suspicious Code Detection

The read-only command `audit_dea_currency_codes` is the current safety tool.

Run it inside a tenant schema context or with an explicit schema:

```powershell
.\.venv314\Scripts\python.exe manage.py audit_dea_currency_codes --schema tenant_schema
```

It scans transaction and statement currency columns and flags metal-like values. Any suspicious value requires manual verification before schema/data migration work.

## Future Enforcement Points

### 1. Shared Validator

Add a small validator module, suggested path:

`apps/tenant_apps/dea/validators/currency.py`

Suggested API:

```python
validate_monetary_currency_code(code: str) -> str
assert_monetary_currency_code(code: str) -> None
is_suspicious_commodity_currency_code(code: str) -> bool
```

Rules:

- Normalize to uppercase.
- Require exactly three alphabetic characters for DEA money paths.
- Reject known commodity/metal-like codes even if they are accepted by `moneyed`.
- Prefer ISO 4217 monetary currencies accepted by `moneyed`, with project-level denylist for `XAU`, `XAG`, and similar commodity symbols.
- Return normalized code for storage.

### 2. Posting Bundle Validation

Current file:

`apps/tenant_apps/dea/posting/validate.py`

Future change:

- Extend `assert_currency_fields()` to call `validate_monetary_currency_code(line.currency)`.
- Enforce `amount_base` is monetary base currency.
- Do not add commodity fields to `PostingBundle`; use a separate commodity bundle/sidecar later.

Required tests:

- `INR`, `USD`, `AUD` accepted.
- `XAU`, `XAG`, `GLD`, `SLV`, `GOLD`, `SILVER` rejected.
- Trial balance still reports only base currency.

### 3. Currency Configuration

Current file:

`apps/tenant_apps/dea/models/currency.py`

Future change:

- `CurrencyConfiguration.clean()` validates `base_currency` and every enabled code.
- `get_enabled_currencies()` returns only normalized monetary codes.
- Reject duplicates after normalization.
- Reject commodity/metal-like codes.

Required tests:

- Valid base/enabled monetary currencies save.
- Lowercase input normalizes or fails consistently.
- Metal-like codes fail validation.

### 4. Exchange Rates

Current file:

`apps/tenant_apps/dea/models/currency.py`

Future change:

- `ExchangeRate.clean()` validates `base_currency` and `quote_currency` as monetary currencies.
- `XAU`/`XAG` valuation rates should not use DEA `ExchangeRate`.
- Metal market prices should remain in `rates.Rate` or future commodity valuation services.

Required tests:

- `USD -> INR` allowed.
- `XAU -> INR` rejected in DEA exchange rates.
- Rates app remains separate for metal/purity/rate valuation.

### 5. Manual Forms And Opening Balances

Current files:

- `apps/tenant_apps/dea/forms.py`
- `apps/tenant_apps/dea/forms_vouchers.py`
- `apps/tenant_apps/dea/views/opening_balance.py`

Future change:

- Validate any user-entered monetary currency code before constructing `Money`.
- Opening-balance wizard and CSV import must reject metal-like currency values.
- Manual journal/voucher forms remain accountant-only monetary tools.
- Metal opening balances must use future commodity opening balance documents.

Required tests:

- Opening balance CSV rejects `XAU`/`GLD`.
- Manual voucher forms reject suspicious codes.
- Existing INR workflows remain unchanged.

### 6. Materialization And Reports

Current files:

- `apps/tenant_apps/dea/services/materialize_journal.py`
- `apps/tenant_apps/dea/services/reports.py`
- `apps/tenant_apps/dea/models/ledger.py`
- `apps/tenant_apps/dea/models/account.py`

Future change:

- Materialization should reject non-monetary currency rows before writing transactions.
- Trial balance/P&L/balance sheet must use base-currency financial rows only.
- `Ledger.current_balance()` and `Account.current_balance()` remain monetary-balance APIs.
- Commodity balances must come from future commodity selectors/models.

Required tests:

- Suspicious metal-like currency cannot be materialized into financial transactions.
- Trial balance remains base-currency-only.
- Account statements remain monetary-only.

## Data Verification Before Enforcing

Before adding hard validators to existing models, run the audit command against all tenant schemas.

Manual verification checklist:

- Confirm no legitimate tenant financial data uses suspicious metal-like currency codes.
- If suspicious rows exist, classify each row:
  - true monetary posting mistake
  - commodity quantity wrongly stored as money
  - old import artifact
  - test/demo data
- Do not auto-convert suspicious rows without a reviewed migration plan.
- Preserve source document references before any correction.

## Staged Implementation Plan

### Stage 1: Read-Only Detection

Status: started.

- Keep `audit_dea_currency_codes`.
- Run it per tenant.
- Add characterization tests around financial reports and balance views.

### Stage 2: Validator Module

- Add shared validator and unit tests.
- Do not wire it into model saves yet.
- Use it first in posting validation tests.

### Stage 3: Posting Enforcement

- Enforce monetary codes in `posting/validate.py`.
- Add regression tests for rejected `XAU`/`GLD` posting bundles.
- Keep existing financial posting behavior unchanged for INR/USD/AUD.

### Stage 4: UI/Input Enforcement

- Add form/opening-balance CSV validation.
- Surface user-facing errors: "Gold and silver are commodities, not financial currencies."

### Stage 5: Model Enforcement

- Add model `clean()` validation to `CurrencyConfiguration` and `ExchangeRate`.
- Consider transaction/statement model validation only after legacy data is clean.

### Stage 6: Commodity Sidecar

- Introduce commodity models side-by-side.
- Keep metal balances out of financial transaction tables.

## Non-Goals

- Do not rename gold/silver into currencies.
- Do not use `XAU`/`XAG` as physical metal balance units in DEA.
- Do not remove multi-currency monetary accounting.
- Do not change production data automatically.
- Do not replace `rates.Rate`; it is a useful valuation input and should integrate with commodity valuation later.

## Acceptance Criteria For The Next Code Slice

The next implementation slice should be considered complete when:

- A shared monetary currency validator exists.
- Validator tests cover accepted monetary codes and rejected commodity-like codes.
- Posting validation rejects suspicious commodity-like currency codes.
- Existing Phase 1 financial posting/report tests still pass.
