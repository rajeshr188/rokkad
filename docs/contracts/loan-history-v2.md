---
status: active
owner: loans
updated: 2026-09-30
tags: [loans, portability, contract]
---

# loan-history/2

Two UTF-8 JSONL lines: manifest, then one loan. The authoritative shape is
[the JSON schema](loan-history-v2.schema.json); the
[fictional weekly example](examples/loan-history-weekly-v2.jsonl) includes an
advance-covered first month, a repayment, an exact 14/31 fraction and full release.

Use **Data tools > Import Loans**. Import the exact borrower source identity first,
select matching destination license revision, series and product, preview the whole
history, then confirm. Preview writes no loan; confirmation repeats reconciliation
atomically under the existing authorization/RLS boundary. Earlier v1 files remain
accepted; the schema download has a separate v1 link.

V2 adds:

- Required frozen `minimum_first_month`; partial methods FULL_MONTH, SLAB,
  STARTED_WEEKS and ACTUAL_DAYS, with simple interest.
- Required product tuple: flexible partial payment / NONE / FLEXIBLE /
  REDUCE_PRINCIPAL, or single-payment bullet / NONE / AT_MATURITY / NOT_APPLICABLE.
- Exact fraction and unrounded decimal strings. Format permits up to 40 decimal
  places, but import requires exact equality with the engine's Decimal calculation;
  accepting more digits does not authorize invented precision.
- Each accrual's `period_days`, inclusive `elapsed_days`, `chargeable_days`,
  `calculated`, `advance_applied`, item `lines`, and `release_catch_up`.
  Chargeable days is the full period for the first-month minimum, capped seven-day
  blocks for weekly mode, elapsed days for daily mode, and null for full/slab modes
  after the first period. Dates and the frozen rule define the exact fraction.
- `event_recorded` on every timeline record. False is allowed only for an accrual
  with zero principal/interest/fees. Its saved item calculations still reconcile;
  restoring it does not create a synthetic financial event.

Source identities and actors remain source claims; destination evidence records
the importing operator. Fixed-precision database accrual projections are checked
against the exact calculation. Advance application, every event balance checkpoint,
full settlement, custody return and contractual obligations must reconcile.
Full-release catch-up immediately precedes release on the same date.

Bounds remain 5 MiB, 20 collateral items, 240 timeline records, 12-month original
tenure, ten-year cutover window. Binary files, Workspace configuration, opening
positions, renewals, auctions, reversals, capitalization, concessions, connected
funding and storage movements are outside this contract. Opening evidence retains
its separate supported export/restore path. Full backups remain necessary for the
complete system and attachments.
