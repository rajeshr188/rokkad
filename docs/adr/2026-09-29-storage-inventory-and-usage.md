---
status: accepted
owner: project
updated: 2026-09-30
tags: [storage, operations, rls, fw-015]
---

# Measure application media before reviewing cleanup

The owner selected FW-015 inventory, usage display and read-only cleanup preview.
Actual deletion, quarantine, quota enforcement and storage billing are excluded.

Use ordinary orgs models for global reconciliation runs and physical-object
metadata. Store each Workspace's dated aggregate in a directly owned, forced-RLS
`WorkspaceStorageUsage` row. Platform pages read global object totals and explicitly
enter a Workspace context for that Workspace's summary. Workspace settings require
the existing `workspace.settings.manage` action and matching request/RLS context.
No object download links or customer filenames appear in inventory pages.

An operator command runs under a restricted database role and existing active
superuser authority. It lists only the configured `media/application/.../` prefix,
using storage metadata rather than downloading files. Application FileFields have
an explicit coverage registry; an unclassified new field stops publication.
References include inactive/archived Workspaces, all row states, historical ticket
media snapshots and immutable legacy admission receipts. Global avatars are not
assigned using the user's navigation preference. Migration originals, backups and
other deployment prefixes remain outside this measurement.

Read references before and after listing and retain their union. Serialize jobs
with a database advisory lock. Publish objects and Workspace aggregates atomically;
incomplete/failed scans never replace the last successful result. Missing reference
size is unknown. Store dated measurements for later comparison; they are not invoices.

Count physical objects once. References within one Workspace do not duplicate
bytes. Cross-Workspace/platform sharing is shown separately without arbitrary
ownership. Category refinement on 30 September: historical-evidence references
do not change the display type of a file that has exactly one current media type.
For example, collateral photos also retained by issued tickets remain Collateral
photos. History-only files remain Historical evidence; multiple current media
types remain Multiple uses. Keep all references for ownership, sharing and cleanup
protection, and count each physical object once. Unknown ownership
stays unassigned. Objects with no known reference and older than seven days are
review candidates only; recent/unknown-age objects are separated. Concurrent
uploads, external writers and references not represented by current contracts mean
this report cannot authorize deletion. No deletion service or endpoint is included.

Later cleanup must recheck references and retention, handle concurrent writers,
provide recoverability, and record reviewed, bounded actions. Existing upload/delete
semantics are unchanged by this increment. Future billing needs its own approved
definition of billable bytes, shared objects, history, temporary files and corrections.
