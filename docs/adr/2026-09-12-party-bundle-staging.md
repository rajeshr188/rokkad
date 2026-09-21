---
status: accepted
owner: project
updated: 2026-09-12
tags: [adr, portability, staging, security]
---

# Validate and stage Party bundles without automatic commits

The owner authorized the recommended follow-up to the
[Party ZIP exporter](2026-09-12-party-export-bundle.md). The existing upload endpoint
now accepts this exact `party-bundle/1` format through a separate ZIP form. It stages
nonempty profiles into ordinary ImportBatch/ImportRow records and produces the
existing previews. No model, migration, dependency, billing exemption, destination
resolution change or aggregate commit command is introduced.

## Archive boundary

Accept at most 31 MiB compressed and 31 MiB expanded; each entity member remains
bounded to 5 MiB and 1,000 records. Each metadata member is at most 128 KiB. Before
ZipFile allocates directory entries, require an ordinary single-disk, comment-free
end record declaring exactly 14 members with at most 16 KiB of central directory.
Reject ZIP64, prepended non-ZIP data, trailing data, missing/extra/duplicate members,
unsafe names, symlinks, encryption and compression other than stored/deflate. Member
names are the exact six entity paths, six schema paths, README.txt and manifest.json;
read bounded bytes in memory and never extract the archive. Absolute byte limits
bound highly compressible exports without rejecting valid files by a ratio guess.
Django may use its standard temporary upload handling; the app retains no ZIP file.

Decode UTF-8 JSON with duplicate keys/nonfinite values rejected. Validate exact
manifest fields, version, PARTIAL coverage, UUID namespace, aware snapshot timestamp,
limits, ordered entity declarations/import order, nonnegative integer counts,
EMPTY/INCLUDED distinctions and one checksum/size entry for every other member.
Require embedded schemas to match the six server-owned schemas. Uploaded schemas
and README are data only: never execute references, render instructions, or select
models/destinations from them. Validate every JSONL file with the existing bounded
parser, compare declared counts and reject duplicate/noncanonical UUID record IDs.
All child references (both relationship endpoints) must use the bundle namespace
and refer to a master ID in the package. Existing domain validation remains in
per-profile previews; invalid business values cannot be committed.

Checksums detect byte changes, not authenticity. Source namespace is untrusted
lineage, never permission or a destination selector. Existing imports retain
conflict detection and reject claims inconsistent with retained source identities.
New exports set zip_import_supported=true; earlier false values remain accepted
because that field described the exporting app's then-current capability. Old
exports without the optional role_types limit also remain valid. No field allows
auto-commit or relaxed validation.

## Staging and review

Require explicit matching Workspace context, membership/Party read and data.import
permissions, ACTIVE lifecycle, and the existing commercial middleware rules. Parse
the full archive before staging. Under the ordinary Company row lock, recheck access
and reserve capacity for all nonempty profiles against the 20-unfinished-batch cap.
Call the existing staging and validation services in manifest order inside one
transaction. Exceptions roll back every new batch/row/audit entry; row-level domain
issues remain visible in NEEDS_MAPPING previews. Empty profiles create no batch.
The bundle audit records outer SHA-256, namespace and per-profile batch UUIDs, never
raw private values. No Party, role definition or identity is created by staging.

POST redirects to a GET receipt signed with a dedicated salt, bound to Workspace
and valid for one day. It contains only profile and batch identifiers; current
Workspace permission/RLS checks still apply. It lists live batch states and empty
profiles, so refresh does not re-stage an upload. Individual batches remain in
Recent imports after receipt expiry. Re-uploading intentionally creates fresh
previews within the cap; existing commit identity rules prevent duplicate Parties.

Operators review/commit master first, then explicitly revalidate child previews
against the committed parents. Roles require destination role-type mapping. Each
profile has its own warning acknowledgement, approval digest and atomic commit;
no partial bundle is silently marked completed, and no bundle-wide rollback of
previously committed profiles is promised. Cancellation remains per batch.

The then-recommended combined preview/atomic commit follow-up is now implemented
in the [atomic commit decision](2026-09-12-atomic-party-bundle-commit.md). The preceding
separate-commit description records this staging-only checkpoint. Preset transfer/deletion, full Workspace archives, KYC files,
Loans restoration and opening-position semantics remain separate future work.
