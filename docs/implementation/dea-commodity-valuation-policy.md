---
status: active
owner: dea
updated: 2026-06-24
tags: [implementation, dea, commodity, valuation, rates, policy]
related:
  - ../adr/2026-06-24-dea-commodity-accounting-layer.md
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - dea-commodity-model-schema.md
  - dea-monetary-currency-guardrails.md
---

# DEA Commodity Valuation Policy

## Summary

This document defines the MVP valuation policy for the DEA commodity accounting layer.

Commodity valuation is reporting-only for MVP. It helps users understand the INR value of metal positions and open exposure, but it must not create financial journal entries, trial balance rows, unrealized gain/loss postings, or party monetary receivables/payables.

The financial accounting layer remains base-currency monetary accounting. The commodity accounting layer tracks quantity, purity, position, exposure, and valuation side-by-side.

## Non-Negotiable Rules

- Do not value gold/silver by treating them as currencies.
- Do not use `Money(fine_weight, "GOLD")`, `amount_currency = "GLD"`, or financial balance views for metal quantity.
- Do not include commodity quantity or reporting valuation rows in financial trial balance.
- Do not post unrealized valuation movements automatically in MVP.
- Do not create `LedgerTransaction` or `AccountTransaction` rows from valuation-only reports.
- Do not mutate posted `CommodityMovement` rows to refresh valuation.

## Current Inputs

### Commodity Position

Commodity quantity position comes from `CommodityMovement` rows and selectors in `apps.tenant_apps.dea.selectors.commodity`.

Primary quantity:

- `fine_weight`

Supporting traceability:

- `gross_weight`
- `purity`
- `uom`
- `commodity`
- `commodity_account`
- `party`
- `location_label`
- `fixed_status`

### Rate Source

The current rates app provides:

- `rates.RateSource`
- `rates.Rate`

Current `Rate` fields relevant to valuation:

- `metal`: `Gold`, `Silver`, `Bronze`
- `currency`: `INR`, `USD`
- `purity`: `24k`, `22k`, `18k`, etc.
- `buying_rate`
- `selling_rate`
- `timestamp`
- `rate_source`

The DEA commodity layer currently uses `Commodity.code` values such as `GOLD` and `SILVER`. MVP adapters must map:

| Commodity code | Rates metal |
|---|---|
| `GOLD` | `Rate.Metal.GOLD` / `Gold` |
| `SILVER` | `Rate.Metal.SILVER` / `Silver` |

Other commodities need explicit mapping before valuation is enabled.

## Valuation Currency

MVP valuation currency is INR.

Reasons:

- DEA trial balance and core financial reporting are base-currency oriented.
- Existing jewellery/girvi workflows primarily use INR.
- Rates app already supports INR.

Future support for USD valuation can be added after currency conversion policy is explicit. Do not mix USD valuation with INR financial reporting unless exchange-rate treatment is designed and tested.

## Rate Selection Policy

For MVP reporting selectors:

1. Use latest available `Rate` at or before the report `as_of` date/time.
2. Filter by mapped metal.
3. Prefer `currency = INR`.
4. Prefer purity basis `24k` for fine-weight valuation.
5. Use `buying_rate` for owned stock and custody positions by default.
6. Use `selling_rate` only when explicitly valuing sale-side exposure.

Fine weight is already normalized metal content, so valuation should use a fine-metal rate. If the rates app stores 24k rate, then:

```text
valuation_amount = fine_weight * latest_24k_rate
```

Do not multiply by purity again when valuing fine weight.

If a future selector values gross weight directly, it must explicitly apply purity:

```text
fine_weight = gross_weight * purity
valuation_amount = fine_weight * latest_24k_rate
```

## Position Valuation

Commodity position valuation should be derived, not stored, for MVP.

Selector output may add:

- `valuation_currency`
- `valuation_rate`
- `valuation_amount`
- `rate_timestamp`
- `rate_source`
- `valuation_status`

Recommended `valuation_status` values:

| Status | Meaning |
|---|---|
| `VALUED` | A suitable rate was found and amount was calculated. |
| `MISSING_RATE` | No applicable rate exists. |
| `UNSUPPORTED_COMMODITY` | Commodity has no rates mapping. |
| `UNSUPPORTED_CURRENCY` | Requested valuation currency is not supported. |

## Exposure Valuation

Open `ExposureLine` records represent fixed/unfixed commodity exposure.

MVP valuation should calculate management value of open exposure:

```text
open_exposure_value = open_fine_weight * selected_market_rate
```

This value is not final settlement amount unless a `RateFixing` is posted.

Policy by side:

| Exposure side | Default valuation rate |
|---|---|
| `PURCHASE` | buying rate |
| `SALE` | selling rate |

Rate-fixing documents store contractual fixing rate and valuation amount. Market valuation of open exposure should not overwrite the fixing document.

## Missing Rate Behavior

Missing rate must be visible and non-silent.

Selectors should not return zero valuation unless a real zero rate exists, which should normally be invalid. Missing rate should produce:

- quantity fields populated,
- valuation amount blank/null,
- `valuation_status = MISSING_RATE`,
- actionable metadata such as missing commodity/currency/purity.

Views/reports should show a rate setup warning rather than pretending the commodity has zero value.

## Rounding Policy

MVP rounding:

- Keep quantity precision as stored on movement rows.
- Keep rates at the precision stored in `rates.Rate`.
- Round valuation amount to 2 decimal places for INR display.
- Store no rounded valuation snapshot in MVP.

When later posting financial valuation entries, rounding must be tested independently because rounding differences can affect journal balance.

## Fixed Transactions

Fixed purchase/sale documents may store transaction/fixing rate and monetary valuation amount on source documents or commodity records.

Rules:

- The fixed rate is business evidence for that event.
- The fixed amount can be used to create financial postings when the financial posting rule is implemented.
- Later market valuation reports may show current value separately.
- Market valuation must not rewrite fixed transaction rate.

## Unfixed Transactions

Unfixed purchase/sale should:

- create commodity movement if physical/custody movement happened,
- create/open exposure for unfixed quantity,
- avoid final monetary AR/AP/revenue/purchase amount until rate fixing,
- optionally show reporting valuation using latest market rate.

Reporting valuation of unfixed exposure is not settlement.

## Rate Fixing

`RateFixing` is the point where open exposure becomes fixed at contractual rate.

MVP model-level behavior already supports:

- fixing quantity,
- rate,
- currency,
- valuation amount,
- allocation to exposure.

Future posting behavior should:

- validate allocation totals,
- reduce `ExposureLine.open_fine_weight`,
- move exposure status toward partially fixed/fixed,
- create financial receivable/payable postings according to side,
- keep commodity movement effects separate from financial journal effects.

## Deferred Financial Accounting For Valuation

The following are explicitly deferred:

- periodic mark-to-market entries,
- unrealized gain/loss accounting,
- valuation reserve accounts,
- automatic revaluation at period close,
- realized gain/loss policy for commodity price changes,
- FX conversion for non-INR commodity valuation.

When implemented later, unrealized valuation must go through normal DEA voucher/journal posting rules and must never mutate commodity quantity rows.

## Deferred ValuationSnapshot

Do not add `ValuationSnapshot` for MVP.

Add it later only if one of these becomes required:

- period-close valuation audit trail,
- historical mark-to-market reporting,
- management reports that must reproduce old rate assumptions,
- financial unrealized gain/loss posting,
- high-cost repeated valuation queries.

If added later, snapshot rows should store:

- `as_of`
- `commodity`
- account/party/location grouping if applicable
- `fine_weight`
- `valuation_rate`
- `valuation_currency`
- `valuation_amount`
- `rate_source`
- policy version
- creation metadata

Snapshots remain reporting evidence unless a separate financial voucher posts accounting effects.

## Service Direction

Current file:

- `apps/tenant_apps/dea/services/valuation.py`

Implemented MVP functions:

- `value_position_rows(position_rows, as_of, currency="INR")`
- `value_exposure_lines(exposures, as_of, currency="INR")`

These functions call a rates facade rather than importing rates internals broadly across DEA.

Current `rates.facade` exposes `get_latest_commodity_valuation_rate()` for commodity valuation lookup.

## Test Plan Before Services

When implementing valuation services, add tests for:

- latest rate at or before `as_of`,
- commodity code to rates metal mapping,
- missing rate returns `MISSING_RATE`,
- unsupported commodity returns `UNSUPPORTED_COMMODITY`,
- buying rate for position/purchase exposure,
- selling rate for sale exposure,
- fine-weight valuation does not multiply purity twice,
- INR amount rounding,
- no `LedgerTransaction` or `AccountTransaction` rows created,
- tenant isolation.

## Current Implementation State

Implemented:

- `apps.tenant_apps.rates.facade.get_latest_commodity_valuation_rate()`
- `apps.tenant_apps.dea.services.valuation.value_position_rows()`
- `apps.tenant_apps.dea.services.valuation.value_exposure_lines()`
- focused valuation service tests

Still deferred:

- reports,
- UI,
- financial journal posting,
- `ValuationSnapshot`,
- unrealized gain/loss accounting.

## Next Implementation Task

Start Phase 4 fixed purchase backend MVP.

Scope:

- define a small fixed purchase command/service contract,
- create financial voucher/journal/account effects through existing canonical posting paths,
- create side-by-side commodity movement through commodity posting service,
- add idempotency and focused tests,
- avoid UI redesign.

Do not add reports, broad purchase module UI, `ValuationSnapshot`, or unrealized gain/loss accounting in the fixed purchase slice.
