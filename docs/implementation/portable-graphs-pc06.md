---
status: active
owner: project
updated: 2026-10-10
tags: [implementation, portability, pc-06]
---

# Wider graph coverage and operational continuation

PC-06 extends the [existing programme](../plans/data-portability-completion-20261010.md)
through the [accepted decision](../adr/2026-10-10-portable-corrections-and-physical-storage.md).
It reuses the ordinary financial aggregates, owner review, private files and
restricted-role restoration. No production change, shared database migration,
deployment, commit or push is part of this local verification.

## Explicit profiles

| Profile | Added coverage | Fixed bounds |
| --- | --- | --- |
| `loan-servicing-bundle/2` | Retained compensated origination correction | Existing 35-model inventory; 20 loans, 5,000 rows, 200 files, 32 MiB expanded |
| `loan-servicing-bundle/3` | Version 2 plus referenced storage hierarchy and immutable movements | Fixed 37-model inventory; same bounds |
| `loan-servicing-bundle/4` | Version 3 plus connected funding terms/events/pledges/returns/reversals/draft metadata and funding counter | Fixed 50-model inventory; same bounds; at most 100 connected funding loans |
| `rokkad-business-package/2` | Wider supported financial chunks; 24-model setup with all physical locations and funding counter; source-only licence/quote evidence | Existing private directory, fresh unactivated destination, atomic preview/confirmation; setup 50,000 rows / 16 MiB and directory 20 GiB |

Published servicing/package version 1 meanings and inventories remain unchanged.
Normal source graphs still export version 1. Wider profiles are selected from
actual evidence, rather than made into a new staff origination/lifecycle choice.
The existing browser file review and operator exchange/package commands consume
these profiles. A funding lender resolves from its exact accepted canonical Party
identity; an absent/foreign/ambiguous claim is held, never matched by display name.

## What changes

Neutral earlier payout/reversal attempts are validated against their own frozen
agreement. The corrected actual origination and later servicing remain the only
outstanding borrower position. Source correction IDs/hashes are validated together
and remapped together; the exact original packet remains retained.

Physical locations use source-namespace identities scoped to the destination.
Shared ancestors are reused only with identical configuration. They do not pull
every loan sharing a vault/box into a financial chunk. Original movement times and
chains reconcile to the current physical projection; ordinary subsequent manual
transfers use the existing authorized service.

Funding balances stay separate from borrower balances. Its original activation
terms, LTV evidence and custody movements are retained. Replaying custody order
allows successive pledges of the same item without defeating active-item uniqueness.
Funded borrower collateral remains visible to ordinary monitoring. The standalone
restore matches number configuration and never reduces an existing counter; the
fresh package retains the source counter including unused reservations.
Original event/header times remain source history where the original return
balance depends on recording-time knowledge. Restored actor references identify
the current importer; the local immutable receipt records admission separately.
Source user identities are retained only in the original private packet.

A reviewed retained item can start with zero remaining principal while its
jewellery remains held. Migration 0069 requires the exact accepted review/4 or
review/5 mapping at deferred constraint validation. Original positive principal and
remaining zero stay explicit; no fictional repayment/disbursal is generated.
Negative initial allocation and ordinary new zero-allocation lending remain invalid.

Licences remain inactive. Imported verification/attestation is labelled source
evidence, and ordinary licence review/save records a new local revision before
new lending. Imported approval evidence can only accompany an accepted servicing
packet. Source user accounts, setup author IDs, staff roles and access are excluded.
Source quotes keep their actual observation/effective dates and frozen source
definition, even if that source was later renamed. Current quote entry and normal
daily-confirmation/correction/withdrawal guards remain intact.

## Verification and release

Verification uses `.tmp/portability-review-20261010/source-pc06`, the previously
verified PC-05 baseline plus an explicit candidate file list. Unrelated shared
Party/dashboard edits and the independent port 8000 review snapshot are excluded.
Tests create only `test_rokkad_continuation_20261010`, with adversarial DML under
restricted non-bypass-RLS roles. The broad run passes 322 regressions; one new
fresh-workspace fixture lacked its required local `schema_name`. After fixing
that fixture, the fresh-workspace acceptance passes separately: 323 cases are
covered across the two runs. Production code did not change after the broad run.
All 51 PC-05/06 candidate files match the final isolated snapshot and pass syntax
and supported-app boundary checks. Model/migration consistency, scoped whitespace
and current-document links pass; the disposable test database is removed.

New acceptance covers corrected origination and day-after-anniversary continuation,
zero-debt retained items, storage roundtrip/future movement, funding repayment and
closure, return/pledge reversal, re-pledging, original PDF bytes, missing exact
lender, false reversal rejection and next funding number. The ordinary native-loan
acceptance exercises real PDF rendering, unknown/current valuation, unchanged
frozen approval, local future-capture review, repayment, release and re-export.
Existing paper/history/checkpoint/renewal/auction/browser/package and RLS regressions
remain required.
The fresh-package acceptance also provisions its own destination owner membership,
activates a trial separately after restoration, reviews the imported licence and
creates/approves/pays the next ordinary direct loan. Access and local lending
authority are established explicitly rather than copied from source setup.

Release needs the owner-only migration sequence including Loans 0069–0071,
Rates 0005 and Data portability 0024–0025 after earlier PC migrations. Runtime web
and worker roles remain restricted. Schema downgrade refuses retained new evidence
where the earlier schema could no longer represent or validate it. Restore the
verified pre-release backup for such rollback; do not delete financial evidence.

This is bounded supported transfer, not a universal Workspace/account clone.
Khata and physical-verification graphs are held; routing, ownership, subscriptions,
secrets, notification jobs and source future-capture consent are excluded.
Unconnected unpaid funding drafts/cancellations and unpaid pawn proposals are
declared exclusions; applicable posted funding must be covered. Current monitoring
requires usable current evidence/setup; missing/stale evidence remains unknown.
Fictional acceptance does not certify real books or a large production migration.
