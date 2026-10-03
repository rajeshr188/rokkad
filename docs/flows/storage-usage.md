---
status: active
owner: project
updated: 2026-09-30
tags: [storage, operations, fw-015]
---

# Understanding storage usage

Workspace Owners/Admins with `workspace.settings.manage` open **Settings > Storage
usage**. The platform administrator opens **Platform console > Storage** for the
physical inventory, or a Workspace's **Storage** tab for its scoped summary.

## What the numbers mean

- **Assigned:** object bytes referenced only by this Workspace. Multiple rows or
  photo defaults referencing the same stored key count once.
- **Shared:** objects referenced by multiple Workspaces or both platform and
  Workspace records. These are shown separately; no billing allocation is invented.
- **Missing:** known references not observed in the completed listing. Their size
  is unknown, not zero. A concurrent upload or deletion may require another scan.
- **Platform:** global profile pictures, not assigned to the user's selected Workspace.
- **Unreferenced / recent:** no known reference and modified within seven days, or
  modification time unavailable. This is not evidence that deletion is safe.
- **Unreferenced / review:** no known reference and older than seven days. This
  remains a candidate for investigation, not a confirmed orphan or deletion approval.

Categories describe current media types. A collateral or customer photo stays in
its photo category when tickets or import history also reference it. A file used
in more than one current media category is counted once under **Multiple uses**.
Files retained only by history appear under **Historical evidence**. Retained
ticket-photo evidence and migration receipts can keep a replaced image referenced.
All business states and archived/suspended
Workspaces participate. Unknown ownership is never inferred from a path or filename.

The scope is the configured application media prefix, not the whole R2 bucket.
Original migration archives, rehearsal, backups, other deployment prefixes, object
versions, transfers and requests are excluded. Import/export data held in database
JSON and downloads generated in memory are not extra stored R2 objects. This is
measured storage visibility, not a bill, quota or price estimate. Display units use
1024-byte steps (the standard Django file-size formatter).

## Refresh and review

The operator schedules `manage.py reconcile_storage --actor-id <platform-admin-id>`
under production runtime settings and the restricted runtime database role. The
selected identity is recorded in the run/audit; an inactive/non-platform identity
cannot run it. Page refresh reads the last successful database snapshot only.
The page displays reconciliation time and a stale warning after two days. A failed
or incomplete run leaves the previous successful snapshot visible.

The platform review list is paginated at 25 and shows a fingerprint, size, age and
Workspace-reference count. It provides no download links or customer filenames.
Authorized operator investigation can resolve the fingerprint through private
inventory metadata. Keep that metadata on the server; do not export it into a
synced folder or assume the list is a deletion manifest.

Removing a customer photo/document or draft collateral attachment removes its
current attachment, while retaining stored bytes for reference-aware review.
Switching the default customer photo does not delete the previous gallery image.
Historical evidence can keep those bytes assigned; otherwise they may appear as
unreferenced candidates on a later scan. Removal is not a promise of immediate
storage reduction. See the [cleanup and retirement plan](../plans/recoverable-media-cleanup.md).

These pages cannot delete files or create charges. An authorized platform operator
can separately prepare a reviewed cleanup batch during a maintenance window,
with verified recovery, fresh reference checks and an audit of each removed file.
Recovery copies are retained; a removed original does not immediately eliminate
all backup storage. See the [operator procedure](../implementation/reviewed-media-cleanup.md).
Historical snapshots are retained for comparison. Storage pricing, quotas and
billing remain deferred; current usage does not restrict uploads or lending.

## Current production schedule and initial result

The production operator runs `rokkad-storage-inventory.timer` daily at about
03:15 IST, with up to five minutes jitter. The job uses the current web container's
runtime settings and operator identity 9 (`admin@rokkad.com`); it does not run under
the migration owner. A server-only operational backup preceded installation.
Two acceptance scans on 30 September agreed on 29,770 objects / 880,056,600 bytes,
all referenced in the selected production application prefix. The separate
[scope review](../implementation/storage-scope-review-20260930.md) subsequently
checked rehearsal and preservation prefixes. The absence of candidates here does not establish that the bucket
contains no legacy/rehearsal orphans, or that each file's contents are intact.

For a failed run, inspect `journalctl -u rokkad-storage-inventory.service` on the
server, verify the active operator identity, restricted database role, R2 listing
permission and field coverage, then rerun the command. Do not bypass RLS or broaden
the prefix to make a scan pass. A rollback of the web image should stop/disable this
new timer if the older image lacks the command; retain the additive inventory tables
and evidence rather than reversing their migration and losing measurements.
