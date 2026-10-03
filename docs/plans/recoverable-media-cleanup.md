---
status: active
owner: project
updated: 2026-09-30
tags: [fw-015, storage, recovery, operations]
---

# Recoverable media cleanup and rehearsal retirement

Committed Party/collateral retention is corrected and both historical rehearsals
have been retired after verified recovery and owner approval. A reusable production
orphan-cleanup workflow is now implemented as an offline operator command; no
automatic lifecycle rule is enabled. See the [operator runbook](../implementation/reviewed-media-cleanup.md).
The production application prefix had no cleanup candidates in the latest
reviewed snapshot, so there is no production space-reclamation operation to run.

## File-removal review

| Path | Previous behaviour | Decision |
| --- | --- | --- |
| Party default replacement/clear | django-cleanup deletes old file after commit | Ignore automatic cleanup; gallery/history can share it |
| Gallery removal/merge | django-cleanup deletes removed row's file after commit | Ignore automatic cleanup; removal changes attachment rows |
| Party document replacement/removal | django-cleanup deletes old file after commit | Retain bytes; migration receipt can still reference them |
| Draft collateral photo/item removal | Deletes bytes after checking same-Workspace photo rows | Retain bytes for global reference/retention review |
| Failed draft upload | Compensates only new uploads recorded by that failed command | Keep; transport cleanup failures remain reconciliation candidates |
| Failed document issue save | Deletes newly saved artifact when issue save fails | Keep; broader transaction rollback can still leave an object |
| Historical attachments / inherited collateral | Already ignored by automatic cleanup / guarded by renewal references | Preserve existing guards |
| Template assets, licence revisions, issued artifacts, notification artifacts, logos and global avatars | Other FileFields remain registered with django-cleanup; domain immutability/protection limits applicable mutations | Unchanged; review before broadening a purge or promising universal retention |

The retention fix is documented in the
[decision](../adr/2026-09-30-retain-detached-party-and-collateral-media.md).
Regression checks must execute commit callbacks; ordinary transaction-wrapped tests
can otherwise pass before django-cleanup's deferred deletion occurs.

## Smallest recoverable cleanup pilot

Use an operator-run procedure before adding a web delete button or bucket lifecycle
rule. The original proposed pilot used two synthetic baseline diagnostic objects;
those and the four unused template PDFs were subsequently included in the approved
whole-rehearsal retirement. They are no longer available as pilot candidates.
Test the reusable workflow with new synthetic fixtures in an isolated scope before
selecting any real production candidates. The bounded procedure below remains the
design reference; its original two-object scope is historical.

1. Produce a private manifest naming the exact bucket, prefix, object keys, sizes,
   modification times, ETags, source inventory, operator and reason. Bound the pilot
   to those two objects; no wildcard/prefix deletion. Seven-day age is only a review
   threshold, never authorization.
2. Stop all writers for the affected rehearsal scope, including local practice apps,
   imports and scripts. Inventory's advisory lock serializes inventories only; it
   does not stop uploads. Do not extend this procedure to live production while
   writers continue. Future online cleanup requires a write-coordination contract.
3. Recheck references under the restricted role against the correct retained
   database, including historical receipts/snapshots. Confirm complete coverage,
   exact scope and unchanged object metadata; any uncertainty stops the pilot.
4. Copy each candidate into a private recovery package outside the application
   prefix. Stream and hash its contents, verify the saved copy, and demonstrate
   recovery into an isolated location. Keep sensitive manifests/media server-side
   or in an approved private backup location, never a synced project folder.
5. Present the exact manifest digest, count, bytes, retention deadline and successful
   recovery check for operator approval. Suggested recovery retention is 30 days
   after cleanup; confirm it at approval. Copying alone does not reclaim bytes.
6. With writers still stopped, recheck references, metadata and recovery bytes before
   removing exact original keys. Record durable per-object intent/outcome and partial
   failures. A retry must reconcile actual original/recovery state, not repeat a
   blind delete. Restore must reject an occupied original key rather than overwrite.
7. Reconcile afterwards and separately record application bytes removed versus total
   bytes retained in recovery. Recovery expiry is a later explicit action, not part
   of the pilot or an assumption that object-store versioning/Object Lock is enabled.

This procedure is now implemented for bounded offline batches through
`cleanup_storage`: at most 50 objects, 20 MiB each and 64 MiB total, with verified
recovery retained indefinitely. The original two-object pilot was superseded by
rehearsal retirement; new synthetic tests verified the reusable command and real R2
transport. No background deletion or recovery-package expiry is implemented.

## The two rehearsal environments: retain, archive, then retire

Recovery preparation and isolated verification completed on 30 September; see
[the recovery report](../implementation/rehearsal-recovery-20260930.md).
Both database/media/configuration packages and the matching runtime images are
verified on-server and in a private R2 archive by full readback. Disposable test
copies were removed. The owner subsequently approved retirement; fresh source-change,
writer, archive and production-reference checks passed. Both historical databases,
two stopped hosted runtimes and their media prefixes are now removed. Retain the
five verified archives with **no automatic expiry**. See
[retirement evidence](../implementation/rehearsal-retirement-20260930.md).
Restore-test limits are recorded in the recovery report.

They contained 1,665,493,265 bytes of media; most objects were referenced by their
respective rehearsal databases. They were historical test/recovery environments,
not the current business database served on rokkad.com. The table records the
retired scopes, not currently available databases or media.

| Environment | Database | Media location |
| --- | --- | --- |
| Local baseline rehearsal | `rokkad_baseline_rehearsal_linode_20260921` | `media/application/rokkad_baseline_rehearsal_linode_20260921/` |
| Former hosted rehearsal | `rokkad_cutover_rehearsal` | `media/application/production/hosted-rehearsal-20260923/` |

The completed retirement required these safeguards for each environment:

- A final database dump with a checked catalog and an isolated restore test.
- A complete media package whose exact keys, sizes and content hashes are verified;
  a database dump alone cannot recover photographs or PDF assets.
- The matching application image/source identifier, migration state, settings and
  secret-recovery arrangements stored privately. A database/media-only archive may
  be insufficient to reproduce the old environment.
- A manifest tying these components together, showing the capture time, restore-test
  result, backup location and an agreed retention/recovery deadline. Verify an
  independent copy; a sole backup on the same Linode is not disaster recovery.
- Confirmation that no remaining local/hosted rehearsal app, job or migration helper
  will write to either prefix. The former hosted web container is stopped, but that
  alone does not prove all writers are stopped.

Only then approve the named environment(s) for retirement. Initially retain the
verified recovery packages and remove the retired runtime/prefix only within the
reviewed scope. Do not delete a shared database container, proxy, Docker volume or
network merely because it has "rehearsal" in its name; production uses shared
infrastructure. Production's `rokkad_production_20260924` database and
`media/application/production/linode-rls/` prefix are explicitly excluded, as are
preserved migration originals/reports and the old legacy server.

The retired loose prefixes reclaimed 1.67 GB relative to the post-archive bucket;
2.30 GB remains in private recovery archives, including databases/images/configuration.
This is not a net 1.67 GB bucket saving compared with the pre-archive state.
Moving or expiring recovery archives requires a separate decision. Retirement is
not evidence that migration created 1.67 GB of production orphans.
