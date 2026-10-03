---
status: accepted
owner: project
updated: 2026-09-30
tags: [storage, fw-015, party, loans]
---

# Retain detached Party and collateral files for reviewed cleanup

The storage-removal review found that the September 25 Party gallery contract was
not enforced at transaction commit: django-cleanup remained enabled on Party and
PartyPhoto. Switching a default, replacing an upload or merging gallery rows could
delete bytes still used elsewhere. PartyDocument replacement/removal could likewise
delete a file retained by an immutable migration receipt. Existing tests checked
rows/files before deferred commit callbacks executed and missed this distinction.

Exclude Party, PartyPhoto and PartyDocument from django-cleanup using its existing
model-level ignore mechanism. Keep the package for other models; this is not a
global cleanup-policy change. Photo selection, removal, merging, permissions,
audit and RLS remain as before. Stored bytes survive committed detachments.

Draft collateral row/photo removal also retains bytes. Its previous physical-delete
check saw only PawnCollateralPhoto rows in the current Workspace; it could not
prove the absence of issued-ticket, legacy-admission or other-Workspace references.
Keep draft-state/renewal guards, row locking and audit; mark the single-photo removal
audit as retaining the file for review. Do not run global reference queries from a
workspace request or bypass RLS to authorize file deletion.

Failed-upload compensation remains limited to newly uploaded files from the failed
command. Existing document-issue save-failure compensation remains unchanged. These
are distinct from deleting a previously committed attachment. Provider failures or
an outer transaction rollback can still leave files for reconciliation.

Retained bytes are not necessarily permanent records or billable storage. The
inventory decides whether any current or historical reference remains; detached
unreferenced files can become review candidates. A later reviewed cleanup workflow
must provide recovery, retention decisions and concurrency controls before physical
deletion. This correction introduces no purge endpoint, schema change or storage
billing. It cannot restore files already deleted before deployment.

See [cleanup and retirement plan](../plans/recoverable-media-cleanup.md).
