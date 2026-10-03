---
status: accepted
owner: project
updated: 2026-09-30
tags: [fw-015, storage, recovery, operations]
---

# Reviewed offline media cleanup

The owner selected the remaining recoverable cleanup workflow after rehearsal
retirement. Storage pricing, quotas and billing remain explicitly deferred.
Deliver an operator command using existing inventory/reference contracts, with no
new tables, public endpoint, timer, automatic expiry or new authorization role.

Require an active platform administrator in global context and a restricted
database role. Select exact object IDs from a completed, matching-prefix inventory
less than 24 hours old. Only unreferenced review candidates older than seven days
are eligible; age is not deletion authority. An operator must supply the reason
that retention obligations have been reviewed. Bounds are 50 objects, 20 MiB each
and 64 MiB total. Reject changed metadata, ambiguous keys, referenced/history/shared
objects, and coverage drift. No cross-prefix or bucket-wide operation is exposed.

The workflow is plan, private inspection, recovery preparation, exact-digest
approval, execution, and optional restoration. Preparation stores full copies and
a signed manifest at an independent private `recovery/media-cleanup/<run-id>/`
prefix in the same bucket. Verify every recovery object's bytes using SHA256.
Keep recovery indefinitely; expiry is a separate future operational decision.

Execution/restoration requires a stopped-writers maintenance window, acknowledged
by the exact bucket/prefix. This includes web, workers, imports, scripts, scheduled
jobs, pending uploads and external credentials/users. The command cannot prove
external writers are stopped. It also takes SHARE NOWAIT locks on every registered
FileField table, Company and global profile rows' tables, and historical admission
receipts. These block row writers until the command finishes. Read references under
forced RLS, entering every Workspace explicitly, including inactive/archived scopes.
The existing advisory transaction lock serializes storage operations. Neither the
advisory lock nor table locks alone prevent raw object-store uploads.

Use fresh exact-object HEAD checks immediately before deletes, not an assumption
that R2 supports conditional deletion. R2's documented conditional GET and
create-only PUT are used for reads and restoration; see
[Cloudflare's API support table](https://developers.cloudflare.com/r2/api/s3/api/).
Create-only restoration refuses an occupied destination. Uncertain restore outcomes
can reconcile a matching previously attempted write, without overwriting anything.

Object-store operations cannot roll back with a database transaction. Therefore
the authoritative per-object audit is a signed, atomically replaced and fsynced
checkpoint in a private 0700 POSIX directory outside source/media trees. Persist
intent before an external mutation and outcome after verification. Database
AuditLog entries summarize successful phases; a later SQL failure does not erase
file evidence. A retry rechecks references, recovery and source state. A missing
source is accepted only after saved deletion intent; a replacement at a completed
key is never deleted. Once restoration starts, deletion replay is forbidden.

The storage UI remains a read-only usage/review surface. This offline command is
the selected core cleanup increment. Online writer coordination, a web review queue,
scheduled cleanup, recovery expiry and commercial storage policy are separate work.
See the [operator runbook](../implementation/reviewed-media-cleanup.md).
