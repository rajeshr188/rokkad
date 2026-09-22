---
status: accepted
owner: project
updated: 2026-09-22
tags: [migration, media, portability, rls]
---

# Attach verified legacy media without changing accepted financial evidence

The preserved Linode originals are independent of application attachments, as
decided in [the preservation ADR](2026-09-21-legacy-media-preservation-and-application-copies.md).
The next step uses ordinary Party and Loans services and the existing private
Workspace routes. It does not create another import UI or a general synchronization
framework.

An operator plan binds a checksummed reference map and customer-photo source rows
to explicit destination Workspaces and one database snapshot. Customer identities
resolve through canonical Party source UUIDs. Active item references must match the
accepted opening batch's original item/loan/path evidence; closed item references
must match the accepted archive snapshot. Shared-folder candidates remain excluded.

Each source photo has one immutable, directly Workspace-owned `LegacyMediaReceipt`
with a unique source-system/record identity. Admission locks the Workspace,
reauthorizes the owner, verifies application-copy bytes, invokes the domain service,
and commits the attachment and receipt together. A retry of identical evidence
does not recreate files or attachments removed by an ordinary Party workflow.
Changed evidence requires review; it cannot silently replace an admitted photo.
Receipts describe completed imports; they do not grant media access.

Party retains every verified customer photo as an unverified OTHER document. Only
an explicit source default sets the profile photo, and only when the profile field
is empty. The document and profile use different objects. Absence of a source
default never selects an arbitrary image. Local changes are not overwritten.

Active collateral gets an append-only `LEGACY_IMPORT` photo with preserved source
provenance. Its stored timestamp is the import time, labelled as such in the UI;
the original capture date remains unknown. It is neither a new appraisal nor a
rewrite of approval, opening balances, or historical calculations.

Visual verification found that twelve repeated source hashes decode to uniform
opaque grey pixels. Those exact fingerprints cover at least 24,946 source image
references, including 5,283 active collateral images. Retain the supplied bytes,
but label confirmed blank images explicitly; they are not usable photographs or
proof of physical identity. A valid file/hash or successful image load proves
transfer integrity, not the usefulness of its content. Other hashes remain
unclassified until separately reviewed. This classification does not modify
accepted source documents or any financial/custody evidence.

Closed history gets a Loans-owned `HistoricalLoanAttachment` sidecar with direct
Workspace ownership, same-Workspace parent guard, forced RLS and SQL immutability.
The accepted archive JSON remains unchanged. Its existing JSON export does not
include binary attachments; preservation manifests and media must be retained
separately. Authorized archive readers can view/download sidecars in the archive.

Application copies use a database-specific R2 prefix distinct from preservation.
Conditional PUT refuses overwrites, and SHA-256 readback precedes database admission.
Photographs are checked with Pillow and named using their detected format, because
many source `.jpg` names contain PNG bytes. Database rollback can leave an unattached
copy; deterministic names and conditional verification make retry safe. Automatic
deletion of such objects is deliberately excluded from the importer.

The first command is rehearsal-only. Explicit opt-in settings load a protected
credential file and change media storage only; static files remain local. The
temporary migration credential is not a production runtime credential. Production
configuration, final frozen source/media reconciliation and cutover remain separate
work. See the [attachment runbook](../implementation/linode-media-attachments.md).
