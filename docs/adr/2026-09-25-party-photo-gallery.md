---
status: accepted
owner: project
updated: 2026-09-25
---

# Party photo gallery and selected default

Customers need several identity photographs while borrower identification and loan
tickets use only one. Add a private, directly Workspace-owned `PartyPhoto` table.
Keep `Party.profile_photo` as the selected default to preserve existing document
and import contracts. Do not duplicate default state on each gallery row.

Existing profile file references are backfilled without copying storage objects.
An upload becomes the default and preserves earlier photos. Choosing a default
changes only the Party pointer. Removing the default selects the oldest remaining
photo, or clears the pointer when the gallery is empty. Customer merges retain both
galleries, deduplicate identical file references and prefer the target's default.

Mutations use the Party edit permission and lock the Party row. File delivery uses
authorized, non-cacheable application routes. Forced RLS and a database parent guard
protect the new table, including bulk writes. Removed file bytes are retained because
historical records may reference them; removal does not rewrite issued documents.

Legacy non-default images already stored as migration evidence remain available in
Documents / KYC. Subsequent legacy photo admissions also register gallery entries.
This change does not introduce a new spreadsheet image-import profile.
