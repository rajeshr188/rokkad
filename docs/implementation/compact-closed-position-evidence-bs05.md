---
status: complete-local
owner: loans
updated: 2026-10-10
tags: [loans, storage, evidence, portability, bs05]
---

# BS-05 compact future closed-position evidence

Follow the [accepted decision](../adr/2026-10-10-compact-closed-position-evidence.md)
and [storage plan](../plans/backup-storage-and-evidence-efficiency.md).

## Stored and portable representations

New closed-position admission stores loan-closed-position-admission/2 in the
ordinary HistoricalLoanImport and loan-closed-position-evidence/2 in its sole
MIGRATION_OPENING. Both retain the accepted original details, zero-debt position,
history coverage, destination mapping and small source references. They do not
embed the full retained source JSON. The existing protected archive_evidence FK
points to the selected immutable HistoricalLoanEvidence document; archive retains
its local ID, SHA-256 and the reviewed family snapshot ID/hash pairs.

The stored nested position remains loan-closed-position/1 with
retained_evidence=null. This is an internal referenced representation, not a
standalone export. The version-2 financial envelope supplies the missing source
binding. An admission without a source document still has archive=null.

The opening reader validates the stored event, original loan facts, exact mapping,
origin equality/hash and version pairing before source hydration. For compact
evidence it verifies the selected source and every frozen family snapshot under
the current Workspace, recomputes document hashes, checks exact loan identity and
validates retained known facts against the accepted position. Hydration returns a
deep copy; posted payloads and their fingerprints are never changed. Snapshots
added after admission do not silently alter the frozen accepted position.

Ordinary balance, servicing and evidence-quality/inventory readers recognize both
stored versions. Export still emits the published loan-closed-position/1 document
or its unchanged media bundle with the full verified selected source and files.
The file needs no access to the exporting database. Fresh-Workspace admission
resolves its own exact Party/series mappings and allocates new source/origin/event
IDs. It uses compact storage while preserving the portable position and source.

## Compatibility and database guards

Existing version-1 posted origins/events are untouched. Preparation recognizes
their source origin and retains version-1 shape for exact replay and refreshed
reviewed batches. Unadmitted old batch fingerprints cannot be silently converted
to the new representation; fresh review is required. Signed single-loan reviews
continue to bind the complete supplied position/source/mapping and frozen family.

Owner-only migration 0068 replaces only guard functions. Old profile branches
remain; new branches enforce source identity/hash/FK and every selected snapshot,
known source facts, no embedded source, exact version pairing and the same sole
zero checkpoint. Existing immutable loan/source/origin/event triggers and forced
RLS stay in place. A reverse migration refuses to remove version-2 support after
compact origins exist. Deploy compatible readers and this migration together;
do not roll back to old readers over compact records.

Native, paper, direct and active-position contracts, authority and number claims
are unchanged. No full earlier history, cash collection, payout or physical return
event is fabricated. The exact temporary 190-record JCL recovery cohort is not
expanded. No new table, form or import profile is introduced.

## Verification and operational scope

All 112 closed-position admission/batch/contract regressions, 180 broader
compatibility tests and ten pure balance tests pass. The final broader run covers
ten compact-specific cases plus bounded evidence, servicing, directory, paper
history, opening evidence, terminal admission and retained-source portability.
Fresh PostgreSQL schema setup uses django_project.settings.test; adversarial DML
uses a restricted NOSUPERUSER/NOBYPASSRLS role, including source hiding and zero
foreign-row updates. The exact disposable test database is destroyed afterward.

The compact cases verify immutable source/event/origin writes, source deletion
refusal, missing/corrupt source blocking read and export, forged references/hash/
source identity/known facts/version pairs, rollback refusal, and populated
version-1 guard upgrades with original bytes unchanged. Version-1 retries and
batch review preserve their stored fingerprints; old media files restore into
fresh compact records with exact content. Unadmitted old batch fingerprints need
fresh review. The existing intentionally inconsistent directory fixture remains
explicitly version 1; new guards are not weakened to construct that old case.

A larger fictional source demonstrates an admission snapshot below 2,500 bytes
and over 80,000 bytes avoided per financial source copy. This is a representation
check, not a production compressed-backup savings estimate. All nine changed/new
modules pass parse/import-boundary checks; tracked app boundaries, curated local
documentation links, scoped whitespace and model/migration consistency pass.

This slice prevents two full source copies for future closed admissions. It does
not rewrite or reclaim the roughly 585 MiB already duplicated in posted records.
Actual savings depend on each source document; small financial facts intentionally
remain in both origin and event. No production migration/deployment, business-row
conversion, backup retention change or media change is performed by this slice.

A later production release also needs the BS-04 backup gate renewed for its exact
compatible image: preserve, download/decrypt and verify that release image before
recording new image recovery acceptance. The current live image remains accepted;
this local slice changes neither the hourly hook nor its acceptance configuration.
