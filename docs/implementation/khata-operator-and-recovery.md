---
status: active
owner: project
updated: 2026-10-01
tags: [khata, forms, recovery, validation]
---

# Khata operator forms and native recovery checkpoint

Implemented locally following the owner-approved summaries/documents slice.
No production deployment, workspace activation, destructive restore or ordinary
loan mutation is part of this checkpoint. No new table or migration is needed.

`web/khata_forms.py` provides ordinary scoped Django forms. `khata_workflows.py`
connects them directly to the existing Loans-owned services. Routes cover new
drafts, series/owner policy setup and each supported action: proposal, deposit,
photo, opening approval, withdrawal, interest/finalization, revision approval/
activation, exchange, unopened return, reserved handover, settlement, cancellation
and bounded correction. Templates use responsive Bootstrap fields and native
disclosures. Readable item/source labels include IDs; the service menu remains
collapsed until needed. Review editing preserves instructions without posting.

Signed review tokens carry the original instructions and service preview hash,
bound to workspace/actor/account/action/business day, with a 30-minute age limit.
They preserve the request UUID through confirmation and retries. Multi-item fields
round-trip their lists. Confirmation revalidates scoped fields and delegates all
posting, locks, accounting, policy, collateral/photo and authorization checks to
the services. Existing source hashes reject stale reviews. Interest finalization
adds a read-only preview and optional hash recheck, preserving the previous service
call contract. Read-only GETs never approve, pay or change custody.

Photographs use authenticated, account/workspace-scoped GETs and retained MIME/
size/SHA-256 checks, with private/no-store/nosniff responses. Photo policy enforcement
remains at approval/exchange/withdrawal boundaries. Native backup downloads require
`data.export` and include all workspace khata evidence, regardless of register
filters. They expose an archive SHA-256 response header and remain private.

`services/khata_recovery.py` owns the exact recovery inventory. The later
[series status decision](../adr/2026-10-03-khata-series-status.md) adds a fourteenth
table and retirement field, preserving strict schema/guard matching. Earlier
thirteen-table archives require their matching image or full database/media recovery.
The later [selected-label extension](khata-label-batches.md) keeps fourteen tables
but changes the label-guard fingerprint; earlier fourteen-table archives also need
their matching guard image/schema before forward migration.
The ZIP preserves all native model fields, exact source-local identities, complete
source JSON and original media bytes. Manifest schema and financial trigger/function
fingerprints refuse incompatible definitions. External prerequisite fingerprints
retain no passwords/authentication secrets. Canonical export-date reconciliation
contains P/U, unpaid/due interest, the full interest schedule and held/eligible item
identities. Capture locks the workspace and khata tables against concurrent writes.

`manage.py khata_recovery` exports a new backup or previews an exact restore.
Restore requires matching original workspace identity, matching recovered borrower/
staff/licence/rate prerequisites, an empty khata destination and an independently
retained archive checksum. The offline table-owner connection is required; runtime
restore is refused even with application owner permission. No browser restore, key
mapping, evidence merge, historical cash replay or paper-account import is exposed.

Restore preserves rows using parameterized inserts while owner-only user triggers
are temporarily disabled inside the transaction. Forced RLS and FK/CHECK/UNIQUE
constraints remain enabled. Typed parent/ownership, file/payload hashes and canonical
reconciliation are verified before trigger re-enablement and commit. Default preview
performs the restore and rolls back without file writes. Commit additionally requires
workspace slug confirmation. Conflicting media/evidence refuse recovery; failures
remove only newly created files. Khata PK sequences move forward, never backwards.
Ordinary-loan sequences are untouched. The bounded limit is 50,000 rows and 256 MiB
expanded manifest/media; this does not replace complete database/private-media backup.

Validation covers two-step posting, retry identity, tampered/shared/expired/stale
reviews, cross-workspace fields, opening/receipt/correction/exchange/handover/settlement
and setup workflows; exact recovery/re-export, corrected interest and reductions,
closed custody, original PDFs/photos, runtime-owner separation, checksum/prerequisite
refusal and rollback of rows/guards/new media. Current results are in [Status](../STATUS.md).

The subsequent [label/release review](khata-release-review-20261002.md) delivers
khata labels and explicit unsupported statutory/default boundaries. Remaining
work is final candidate/recovery/hardware acceptance and the separately approved
named workspace pilot.
Unsupported correction kinds remain refused. See the [operator flow](../flows/khata-servicing-and-recovery.md)
and [decision](../adr/2026-10-01-khata-operator-forms-and-native-recovery.md).
