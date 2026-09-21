---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, restore, reconciliation]
---

# Rebuild and reconcile opening exports before restoration

The [opening evidence export](2026-09-12-opening-evidence-export.md) retains the
reviewed opening and supported servicing but uses source-database-local references.
Copying those keys into another Workspace or importing only the opening would
misrepresent debt, releases and custody.

Add a Loans-owned per-loan restore command with explicit destination borrower,
licence revision, series and product version. Parse a bounded export, validate its
profile, original opening, event/schedule fingerprints, chronology and references,
then rebuild the opening with the existing authorized writer. Restore additional
dated appraisals and rebuild full releases and their coupled reversals through the
same financial calculations used for live servicing.

Shared private release/reversal writers accept an explicit effective date from the
restore transaction. Public live commands keep their current-date behavior and
signatures. No clock is patched in production code. Historical releases receive
deterministic source-scoped numbers and use their evidenced return timestamps;
native loan/release counters are not consumed. Original numbers remain in source
evidence. Unsupported actions are rejected, not omitted.

Before commit, compare the rebuilt export at the source as-of date with the source
graph. Normalize only explicit source/destination references, local numbering,
newly recorded actor/timestamp metadata and derived fingerprints. Compare the
remaining fields across loan, items, policy, events, accruals, releases, reversals,
closing lines, custody, obligations/allocations/schedule changes, appraisals,
lifecycle details, recorded balance, concession and collection preview. A mismatch
rolls back the complete loan and provenance.

The existing immutable `HistoricalLoanImport` stores the destination-bound opening
document and the full original export plus restore request under `references.restore`.
Original actor IDs/timestamps are retained there as source claims; local records
identify the operator who performed restoration. No source actor is impersonated,
and no new table or migration is required. Source-verification records survive
re-export as retained evidence; restore does not re-extract or authenticate a dump.
Appraisal reference quotes remain frozen source claims. Their context carries the
source Workspace explicitly, preserved across subsequent restores, and the appraisal
page labels it. A source quote ID never becomes a destination Rates foreign key.

The shared financial-origin identity prevents a complete import, ordinary opening
or changed restoration from activating the same source loan again. Identical
confirmed restore retries reauthorize and return the original result without
reapplying servicing, even when new servicing has occurred. Existing ordinary
openings are not augmented by this command. It is a restore into an unmapped
financial origin, not an overwrite or history-merging feature.

Operator CLI preview runs the full restore under rollback. Commit requires an
explicit flag and the exact checksum of the reviewed source, destination Workspace
and mappings. Both paths require owner historical-import access, export, release
and Workspace administration permissions and matching forced-RLS context. The
complete-history browser upload remains a separate strict format.

New exports advertise restore support. Earlier exports with the same format and
`restore_supported=false` remain readable; that flag describes the producing
version's capability, not authorization. Bounds and canonical graph reconciliation
still apply. Repeated migrations retain ancestry and remain subject to the 5 MiB
limit; this is not an unrestricted archive format.

This completes the bounded engineering round-trip path. Actual jcl selection,
balances, missing due terms, destination and cutover require the existing pilot
review. No real source loan is imported by this implementation. See the
[operator flow](../flows/legacy-opening-import.md#restore-an-opening-export).
