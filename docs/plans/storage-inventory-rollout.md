---
status: complete
owner: project
updated: 2026-09-30
tags: [storage, fw-015, operations]
---

# FW-015 storage visibility rollout

The owner selected inventory, Workspace usage and read-only cleanup previews.
Deletion, quarantine and billing are a later decision.

Deliver a restricted-role background command, scoped to the configured production
application prefix, with explicit reference coverage and atomic publication. Show
global counts/review fingerprints in Platform console > Storage and scoped summary
bytes/counts/categories in Workspace Settings > Storage usage and platform detail.
Daily scans provide dated snapshots; failed scans preserve the last completed result.

Required acceptance: unique/shared byte accounting, historical references,
inactive Workspace coverage, RLS and action authorization, concurrent reference
changes, partial-list failure, no provider requests during HTTP rendering, scoped
metadata-only R2 calls, mobile review, owner-only migration, a first production
scan and a scheduled-run check. Backups/evidence stay on the server.

Next increment: investigate review candidates, review existing file-removal paths,
then design recoverable, reference-aware cleanup with explicit operator approval.
The inventory itself did not change file-removal semantics. The subsequent
[retention correction](../adr/2026-09-30-retain-detached-party-and-collateral-media.md)
retains committed Party and draft collateral files for reference-aware review.
Failed-upload compensation remains unchanged; reconciliation is still necessary.

See [the decision](../adr/2026-09-29-storage-inventory-and-usage.md) and
[the operator guide](../flows/storage-usage.md).

## Delivery evidence

Deployed on 30 September 2026 as
`rokkad:storage-inventory-20260930-2b332cc6b6bc`. All 37 focused tests, desktop/mobile
review, 22 restricted production renders and 16 source hashes passed. The additive
migration and server-only backup completed. Two scans agree on 29,770 objects /
880,056,600 bytes, with no missing or unreferenced keys in the production application
prefix. The daily timer/service acceptance passed; schedule is approximately
03:15 IST with up to five minutes jitter. See Status for scope and private evidence.

This visibility increment is complete. FW-015 as a whole remains open for reviewed
cleanup and additional scopes. Review inventory-metadata retention before expanding
scan frequency or retaining detailed object rows indefinitely; dated usage aggregates
remain the durable metering history. This is not a billing policy.

The [30 September scope review](../implementation/storage-scope-review-20260930.md)
reconciled both rehearsal prefixes and preserved migration evidence. It found six
unreferenced rehearsal objects totalling 2.53 MiB; production has none. Most bucket
storage remains referenced or deliberately preserved. Next, review existing removal
paths and design a recoverable cleanup pilot. Whole rehearsal retirement is a
separate retention/recovery decision; no deletion has been authorized or executed.

The [recoverable cleanup plan](recoverable-media-cleanup.md) records the removal-path
review, bounded diagnostic pilot and separate rehearsal backup/restore requirements.
Retention correction is the prerequisite; a physical purge workflow is not yet live.
