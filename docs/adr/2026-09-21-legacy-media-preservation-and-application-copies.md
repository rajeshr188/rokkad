---
status: accepted
owner: project
updated: 2026-09-21
tags: [migration, media, portability, r2]
---

# Preserve legacy originals separately from application media

The owner selected private Cloudflare R2 for the new system and explicitly
approved `rokkad-production-media` and a one-week migration credential scoped to
that bucket. Production media remains on Linode. SQL references do not contain
file bytes, filenames repeat across source tenants, and some references are missing
from their expected tenant folders. Shared-folder candidates have unproved ownership.

Preserve inventoried originals before attaching files to application records.
Object keys include the installation namespace, source branch, content SHA-256
and original relative path. A separate `unresolved-shared` group retains candidate
files without asserting any destination Workspace/Party/loan association. Unknown
associations must never be inferred from a filename match alone.

The operator verifies source bytes against the inventory, uses conditional creates
to refuse overwrites, reads every object back and verifies its SHA-256. Checksummed
manifests retain the source-record-to-object map and copy receipts. This is logical
preservation by the migration workflow, not a claim of bucket Object Lock or an
undeletable storage account. The source remains live; final frozen database/media
reconciliation is still required.

Preservation names must not be assigned directly to mutable Party FileFields.
Party photo removal calls `profile_photo.delete()`, and ordinary document cleanup
may delete a stored file. The later attachment service must make separate application
copies, bind exact source/import identities, retain provenance and verify the copy.
Each mutable field needs its own storage object so deleting one attachment cannot
delete another retained file. Original preservation objects remain independent.
Do not mutate accepted opening or archive documents to add binary references.

The existing private-media authorization decision remains authoritative: business
files are delivered through authorized Workspace routes. Object-specific signed
PUT/GET URLs used privately for the operator transfer are not a new user delivery
API. They are short lived, transmitted over SSH in memory and never persisted in
receipts. Long-lived R2 credentials remain on the operator's machine; production
does not need a new transfer dependency or stored cloud secret for this copy.

The expiring migration token is not a permanent application credential. Backend
dependencies, runtime credentials, authenticated attachment services, closed-history
attachment retention and isolation tests remain necessary before media is usable
inside the new application. A copied bucket alone does not satisfy that boundary.

See [the media plan](../plans/linode-media-to-r2.md) and
[private delivery decision](2026-09-09-private-business-media-delivery.md).
