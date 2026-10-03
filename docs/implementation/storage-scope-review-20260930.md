---
status: complete
owner: project
updated: 2026-09-30
tags: [storage, fw-015, operations, migration]
---

# R2 storage scope review — 30 September 2026

Read-only investigation of `rokkad-production-media` following the FW-015
production inventory rollout. No object was deleted, quarantined or rewritten;
no application configuration, business data or legacy server was changed.
Cleanup remains a separate, reviewed operation.

## Results

The bucket listing contained **121,378 objects / 3,237,145,152 bytes** (3.24 GB
decimal). Counts are a dated observation, not a promise that subsequent uploads
are included.

| Scope | Objects | Bytes | Finding |
| --- | ---: | ---: | --- |
| Production application | 29,770 | 880,056,600 | All referenced; no missing references |
| Local baseline rehearsal application | 29,381 | 831,444,125 | Two unreferenced diagnostic objects; no missing references |
| Hosted rehearsal application | 29,518 | 834,049,140 | Four unreferenced template assets; no missing references |
| Preserved legacy originals and preservation reports | 32,697 | 644,873,304 | All expected keys and sizes match |
| Attachment evidence reports | 12 | 46,721,983 | All expected keys and sizes match |

Exact scopes, relative to the bucket:

- `media/application/production/linode-rls/`
- `media/application/rokkad_baseline_rehearsal_linode_20260921/`
- `media/application/production/hosted-rehearsal-20260923/`
- `media/legacy/6ca968d626474dbb8e3924f0c1a12ed6/`
- `media/attachment-reports/rokkad_baseline_rehearsal_linode_20260921/`

## Six review candidates

Together these occupy **2,651,905 bytes (2.53 MiB)**, approximately 0.08% of the
bucket. Absence from reference sets does not itself authorize deletion.

Two JPEGs, totalling 2,155,580 bytes, are in the baseline rehearsal's
`diagnostics/jcl-upload-20260922/` directory. Their dates, sizes and location match
the synthetic upload probes recorded in Status and the retained `probe_storage.py`
helper. That helper generates noise images, uploads them, verifies content hashes
and leaves them stored. They are diagnostic cleanup candidates, not borrower photos.
This investigation did not download their contents or repeat that content check.

Four PDFs, totalling 496,325 bytes, are in the hosted rehearsal's
`loans/documents/workspace-1/layout-2/revision-2/assets/` directory, uploaded on
23 September around 09:22 UTC. They have no reference in the checked rehearsal
database. Their path identifies template assets, but the exact creation/rollback
history and recovery value have not been established. Keep them pending that
review; do not describe them as proven disposable files.

Private candidate manifests retain exact keys, fingerprints, byte counts, upload
times and ETags on the server. No customer filenames are published in this report.

## Evidence and limits

Used the existing production runtime storage client to list metadata in this one
known bucket. No object bodies were downloaded and no other bucket/account was
accessed. The deployed daily inventory continues to scan only its configured
production application prefix; this broader review was an operator investigation.

Reference reads ran in PostgreSQL READ ONLY transactions under the restricted
`rokkad_runtime` role, with database and media-prefix assertions. Reads covered all
workspace contexts, installed FileFields, issued-document media snapshots and
immutable media-admission receipts. The older baseline schema lacks the later
Party photo gallery table; this was explicitly recorded instead of silently
treating a failed reference query as an empty table. Hosted rehearsal was inspected
using its retained image and settings in a temporary collector, without restarting
its stopped web service. References from the local database were transferred only
as SHA256 object-key digests, with counts/sizes and coverage metadata.

Preservation reconciliation combined the original 32,554-entry copy plan,
immutable admission references from all three databases and 13 preservation-report
receipts. All 32,697 expected keys/sizes matched, with zero missing, unexplained or
size-mismatched objects. This includes the 1,149 unresolved shared-folder originals:
unresolved ownership does not make preserved migration evidence an orphan.
The separate 12 attachment reports also matched their copy receipts exactly by
key and size. These are **metadata checks**, not new byte-level integrity checks.
See the [preservation decision](../adr/2026-09-21-legacy-media-preservation-and-application-copies.md)
and [attachment evidence decision](../adr/2026-09-22-legacy-media-attachment-evidence.md).

Raw inventory, reference digests, coverage records and candidate manifests remain
under the private server directory
`/home/rokkad/deploy/cutover-20260924/storage-scope-review-20260930/`.
The review did not copy a database backup or customer media to the local project.

## Recommended next increment

Review existing file-removal paths and define recoverable cleanup before adding
execution controls. Any pilot needs a fresh reference check, precise reviewed
keys, protection against changes since review, retained recovery evidence and an
explicit operator decision. Do not enable automatic deletion from these findings.

The two rehearsal prefixes together occupy 1,665,493,265 bytes (1.67 GB decimal).
Most files remain referenced by their respective rehearsal databases. Retiring a
whole rehearsal environment is a distinct retention decision requiring confirmation
that it is no longer needed and a verified recovery package covering its database,
media and configuration. It must not be presented as ordinary orphan cleanup.
Preserved originals and migration evidence remain retained.
