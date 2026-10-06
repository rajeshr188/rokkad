---
status: active
owner: project
updated: 2026-10-06
tags: [loans, continuation, forecast, evidence]
---

# LC-02: forecasts and independent evidence quality

The continuation selector now accepts `forecast_through` separately from
`as_of_date`. The latter remains the knowledge date and recorded-balance date.
Native shared periods and recorded anniversary forecasts use their existing
knowledge caps. Opening continuation validates its retained graph and selects
actions effective through the knowledge date, then projects that bounded position
to the horizon. It retains checkpoint recognition, unpaid carry and period-specific
advance evidence. The original anniversary and next-boundary calculation remain
profile-specific; shared-policy opening displays use saved per-item rounding.

`obligation_state` selects this reader for existing recorded-anniversary contracts
and supported native/shared-policy opening simple/full-month bullet/flexible loans.
The source schedule remains immutable capacity. The dynamic state replaces only
the remaining/due/overdue read projection, retaining schedule identity, original
maturity and integrity findings. Legacy opening schedule and daily-only forecast
meanings remain unchanged. A future continuation refuses `collection_balance` so
a maturity estimate cannot accidentally become an amount to collect today.

`evidence_quality` exposes assessment, transaction, valuation and calculation
dimensions separately. A successful payment read can disclose supported calculation
even when its saved risk assessment is stale. Reports disclose saved risk quality
alongside their unchanged recorded debt; they do not imply a settlement quote.
Opening history/principal basis is visible without requiring a current assessment;
the loan sidebar labels checkpoint principal rather than claiming original payout.
CSV/XLSX/PDF position exports and Party statements append quality columns; transaction
rows leave position-quality columns empty. Earlier monetary columns stay in place.

Risk snapshot V6 carries financial-history start, principal basis, servicing profile
and support status. V5 assessments become stale and use the existing refresh path.
Dashboard aggregates remain one query; portfolio financial totals exclude inconsistent
current calculations. Provisional book coverage remains countable independently of
unavailable valuation. No new table, migration, posting mechanism or conversion.

The capture audit found `earlier_payout` evidence on native-contract disbursals was
not recognized as paper activity by transaction completeness. It now requires a
book review, as do known paper receipts/closures and staff-reported missing activity.
Ordinary system capture remains operationally supported and is expressly labelled
`SYSTEM_CAPTURE_ASSUMPTION`, not complete-book certification. A reviewed per-loan
Rokkad-only transition remains distinct. Existing notice/recovery prerequisites,
fingerprints, authorization, locks, postings and coupled reversals are retained.

Verification: 28 real-admission tests pass (75.488s), with eight new forecast
cases for later reductions, knowledge caps and both item/rounding variants.
Four actual refresh/report/export quality integrations pass (8.455s). The affected
482-test run passes 480 (408.385s); two test expectations required correction for
the new reference wording and a fake assessment's missing overdue amount. The
final 39 focused checks all pass (15.119s), including both repaired cases and final
metadata/export/HTTP assertions. Three final sidebar HTTP checks pass (4.269s).
No single clean 482-test rerun is claimed.
Django checks, migration drift, 27 changed/new Python parses, nine template
compilations and whitespace checks pass. Logs are ignored under
`.tmp/lc02-20261006/`. Validation is also recorded in Status and the staged plan.
Fixtures are
fictional technical acceptance, not real-book or production acceptance. Local
preview images and production are unchanged. Quote reuse is not enabled here:
LC-06 has the owner's seven-day default and Workspace-owner configurability.
