---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, collateral]
---

# Legacy collateral with net-only weight and Bronze

The owner confirmed that the old register's weight excludes stones and other
non-metal parts. The retained active cohort has 2,470 such item weights, including
seven Bronze items. Requiring invented gross weights or mapping Bronze to OTHER
would change the source facts before import.

`PawnCollateralItem.gross_weight` is nullable. Null means not recorded, never zero
or a copy of net weight. Its positive and gross-at-least-net database constraints
still apply to known values. `blank=False` stays in place, so ordinary native
draft forms, draft service validation and approval `full_clean()` still require
gross weight. A future opening writer must explicitly validate the migration
contract and exclude only this missing field from ordinary model validation.
This does not authorize direct ORM creation as a public import path.

Opening review v2 accepts null gross weight while retaining required positive net
weight, separate purity and a weight-evidence reference. V1 and strict complete
history retain their existing required-weight contracts. Bronze is an explicit
Loans metal, supported by v2. It is never translated to Gold, Silver or OTHER.
Native draft forms continue offering their existing Gold/Silver choices.

Existing valuation resolves the exact metal code. Reviewed opening collateral can
use an approved appraisal with the LATEST_APPRAISAL policy. Missing commodity rates
remain missing; no precious-metal fallback or invented historic appraisal is added.
The frozen opening preserves source quantity, physical facts and custody/valuation
references. Unknown gross is displayed explicitly in loan details and summaries.

The source adapter selects review v2 for explicit `jcl-owner/2` preparation and
maps Bronze exactly. It leaves balances, maturity, remaining obligations,
continuation and destination references unapproved. Missing due dates and source
errors still prevent reconciliation. These changes prepare an opening commit;
they do not create financial records or establish source evidence as true.

Migration `0011_legacy_collateral_evidence` changes only existing fields, preserving
Workspace ownership/RLS. Tests cover document boundaries, known-weight SQL checks,
native validation, Bronze appraisal/release/reversal and the unknown-weight UI.
See the [first-import plan](../plans/first-legacy-import.md).
