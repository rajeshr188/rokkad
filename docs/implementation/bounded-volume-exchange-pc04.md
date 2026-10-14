---
status: active
owner: project
updated: 2026-10-10
tags: [implementation, portability, pc-04]
---

# PC-04 bounded volume exchange

The local implementation follows the [snapshot decision](../adr/2026-10-10-bounded-volume-exchange.md).
It adds `portability_exchange` with export, inspect and stage operations; it never
commits imported Party or financial records by itself. Migration 0022 indexes
committed Party reference evidence; PC-02/03 migrations 0020/0021 remain
prerequisites for their batch workflows. No table or financial guard is added.

## Operator flow

Use the ordinary restricted-runtime environment and authorized actor. On Linux
create a mode-0700 output parent; on Windows protect the parent with the user's
ACL. Exchange files contain private customer and financial information. An export
target must not exist. Do not place it in a public media directory.

```powershell
python manage.py portability_exchange export --workspace-id SOURCE_ID --actor-id ACTOR_ID --directory PRIVATE_NEW_DIRECTORY
python manage.py portability_exchange inspect --workspace-id DESTINATION_ID --actor-id ACTOR_ID --directory EXCHANGE_DIRECTORY
python manage.py portability_exchange stage --workspace-id DESTINATION_ID --actor-id ACTOR_ID --directory EXCHANGE_DIRECTORY --expected-sha256 MANIFEST_DIGEST --chunk 1
```

Substitute actual IDs and paths. `--party-only` selects an explicitly Party-only
export. Export must run in a fresh process outside an existing transaction.
Inspect verifies every file using bounded reads and reports its destination
batch state. Compare/retain the manifest digest before staging. Stage outputs the
existing browser review URL. Staff map, review and confirm there, then stage the
next chunk. Prior Party chunks must finish; disjoint financial chunks can be
reviewed independently after Party dependencies finish. Repeating a stage request reopens that chunk's receipt; use inspect
after an interrupted run. A cancelled receipt permits restaging. Prepared batches
remain subject to the existing twenty-unfinished-batch limits.

Financial files include original supporting bytes under existing file profiles.
Connected renewals and shared release batches are not split. Imported closed
positions use the ordinary closed-position file; earlier transactions remain
unavailable. Each position is currently one file and one existing review batch.
This operator workflow does not yet provide an aggregate portfolio approval or
automatic configuration/Party-media restore. Those belong to PC-05, with remaining
funding/storage/correction graphs in PC-06. Staff can also upload individual files
through the ordinary published import screens.

## Consistency and limits

The command uses one repeatable-read database snapshot and publishes the prepared
directory after successful commit. It deliberately avoids the Company/portfolio
row locks used by small browser exports. The manifest records the snapshot date,
time, namespace, exact counts, dependency order, file sizes/hashes and source loan
cohort. Source business changes after capture do not alter those files. Missing
media, unsupported graph/state, overflow, midnight rollover or conflicting
identity allocation aborts export. No best-effort partial success is published.

| Envelope | Limit |
| --- | --- |
| Party profile | 200,000 rows; each file retains 1,000 rows / 5 MiB |
| Loans | 50,000 admitted loans; connected graph retains 20 loans / 5,000 rows |
| Financial/media file | Existing 32 MiB expanded limit; profile-specific file counts |
| Manifest/chunks | 32 MiB / 60,000 chunks |
| Aggregate/source scan | 20 GiB / 1,000,000 rows |

A parent's child group exceeding a file bound is held explicitly. Source
selection cannot include missing/foreign records, and identities are stable
across chunks. Source borrowers must resolve by exact Party reference before
ordinary financial admission. Legacy aliases can resolve through exactly one
completed native Party master row's immutable source references when no explicit
SourceIdentity exists; ambiguous/unaccepted references are held. A partial GIN
index avoids scanning that evidence for each closed loan. Number claims commit through existing Loans
commands; chunk preparation does not reserve numbers. Completion is per chunk,
not whole-directory atomicity. Existing signed review, replay, tenant isolation,
immutability and counter guards remain authoritative.

## Verification

All 213 broader regressions pass against frozen baseline 6dc71e4a plus PC-01
through PC-04 portability files, excluding concurrent Party picker/dashboard work.
The suite checks synthetic customer cohorts at audited JCL (5,887) and Lakshmi
(2,104) sizes, 1,001 child contacts, stable repeated entity bytes, cross-Workspace
exclusion and 26,649 individually validated synthetic closed files. The latter
proves layout/file-envelope coverage, not a 26,649-loan financial restore or a
production throughput benchmark. Actual 25-loan closed admission/retry/counters,
ordinary Party receipt resumption, rejected ambiguity/unaccepted references and
existing servicing/renewal/release/media roundtrips are checked separately.

A restricted-role concurrent writer commits an update, new Party and contact
during a repeatable-read export within a one-second lock timeout; exported chunks
retain the prior snapshot and exclude those later changes. Failed export removes
temporary files and rolls back source identity allocation. Altered/missing files,
wrong manifest digest, path traversal, overflow and tenant permissions are held.
All 12 final changed-path checks pass for byte splitting, bounded dependency
receipt lookup and snapshot timestamp refinements. The disposable verification
database was removed. App boundaries and ordinary
model/migration consistency checks pass. No live source record, production
Workspace or shared development database was changed.
