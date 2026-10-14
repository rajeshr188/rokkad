---
status: active
owner: project
updated: 2026-10-10
tags: [implementation, portability, pc-05]
---

# Fresh-Workspace business package

PC-05 builds on [bounded exchange](bounded-volume-exchange-pc04.md) and the
[accepted atomic package decision](../adr/2026-10-10-fresh-business-package.md).
It is local implementation, not a production deployment. Migration
`data_portability.0023_business_package_receipt`, with its predecessors, is required.

## Coverage and destination

`rokkad-business-package/1` carries the existing checksummed exchange, explicit
setup JSON, exact source financial/setup bindings, customer business codes and
metadata, profile/gallery photos, customer documents and identifier relationships,
and private hashed media. Supported loan financial/custody histories and original
issued bytes still use the published servicing or closed-position files.
Business logo/theme and the simple/extended loan workflow are carried separately;
destination name, routing, ownership and account preferences remain independently
chosen. Their source presentation is shown in the reconciliation review.

The [fixed setup schema](../contracts/fresh-business-setup-v1-rows.json) includes
licences, supported revisions, series and both numbering counters, products and
versions, effective economics/metal interest/fees, monitoring, origination choices,
document layouts/assets/assignments and print profiles/assignments, Party role
definitions/customer counter, and supported Rates sources/quote history.
All references receive fresh destination IDs. Effective dates and frozen contracts
remain original; setup author IDs and source users are excluded. Restored licences are inactive
until reviewed by the destination owner. Source verification labels are not newly
performed destination customer verification.

Destination business tables must be empty, with no subscription/access decisions
and no non-owner staff membership. An automatically seeded product catalogue is
not empty. Use an explicitly provisioned empty Workspace; do not delete existing
setup or records simply to pass this precondition. Existing commercial recovery
policy keeps normal HTTP business activity unavailable until explicit activation.
Ownership, permission, Workspace context and lifecycle checks remain in force.

Users, password/session data, portal/staff grants, billing, provider credentials,
Notify setup/jobs and unused retained historical records are excluded explicitly.
Unpaid drafts/proposals are excluded, while reserved counters remain preserved.
Khata, funding, storage/verification dependencies and unsupported financial
corrections hold the package instead of being silently dropped. Legacy licence
verification/owner attestation and quote histories with changed source definitions
also hold this version until a reviewed adapter exists. Customer duplicate or
ambiguous identity conflicts require the ordinary individual review path; the
package does not fabricate duplicate exceptions or infer merges.

## Operator sequence

Use the restricted runtime connection and an independently authorized actor.
Create a protected local parent directory, including Windows ACL protection.
The package contains private customer evidence and is not encrypted by this
version. Transfer it through an approved private channel; never publish it.
Replace the placeholders in these commands with the actual authorized identities.

```text
python manage.py business_package export --workspace-id SOURCE --actor-id ACTOR --directory PRIVATE_NEW_DIRECTORY
python manage.py business_package preview --workspace-id DESTINATION --actor-id ACTOR --directory COPIED_PRIVATE_DIRECTORY --expected-sha256 RETAINED_PACKAGE_SHA --review-file NEW_PRIVATE_REVIEW_FILE
python manage.py business_package restore --workspace-id DESTINATION --actor-id ACTOR --directory COPIED_PRIVATE_DIRECTORY --expected-sha256 RETAINED_PACKAGE_SHA --review-file CHECKED_PRIVATE_REVIEW_FILE --confirm
```

Export requires a fresh process and starts repeatable read before source SQL.
It prepares a temporary directory and publishes only after DB commit. The result
reports SHA and counts; retain the SHA separately from the files. Preview verifies
all bounded files and restores dependencies through normal services in a rollback
transaction. Read the private review file: counts, loan positions, source coverage,
local numbers, licence hold, media and exclusions. Approval expires in one hour.
No customer/financial records survive preview; temporary file copies are cleaned.

Restore checks the same actor, Workspace, source SHA and current reconciliation.
It commits setup, Party imports, financial origins/files, customer media and receipt
together. Late failure rolls back database writes and removes files created by the
attempt. The standalone command owns cleanup through the outer Workspace commit.
Repeated confirmed submission returns the existing protected receipt, without
reapplying records or altering later servicing. Retry is admission evidence, not
a fresh assertion that every loan remains unchanged.

After success, review destination licence authority, running series, economics,
monitoring, printing and new-loan readiness. Activate commercial access separately
and admit staff deliberately. Source history does not approve destination books
or promise future direct capture. PC-06 continuation acceptance follows.

## Bounds and verification

Existing exchange/parser/file limits remain. Setup adds 50,000 rows/16 MiB;
package manifest 32 MiB; each extra media blob 32 MiB; 200,000 unique extra blobs;
combined directory 20 GiB. Media count means unique content hashes, not necessarily
physical destination copies. The atomic restore can take substantial time and
temporary media/disk capacity. Rehearse large portfolios and avoid retaining an
unbounded long transaction; no real production package acceptance is implied.

All **177 broader isolated regressions** pass across package restoration,
existing exchange/browser loan restoration, Party master/children/bundles,
commercial access policy, registry/RLS and media inventory. All **12 final
changed-path checks** pass against the final candidate, including actual standalone
commands/retry, original counter/code preservation, active and minimal closed
positions, collateral/customer/logo bytes, temporary/late-failure cleanup,
standing terms/monitoring/quote dates, printing/asset assignments and malformed
source/foreign-reference holds. The broader run preceded the final branding/count
changes; the 12 final checks cover those changes. Test data is synthetic, not
production source-book acceptance or an audited-size complete-package migration.

The isolated source is baseline `6dc71e4a` plus the verified PC-01 through PC-04
files and this slice, excluding concurrent Party-picker/dashboard candidates.
The disposable `test_rokkad_package_20261010` database is removed; all twenty
PC-05 candidate files match the verified snapshot. Model/migration consistency,
supported-app boundaries and current documentation links pass. No shared schema,
production records/files, server processes, R2 settings or port-8000 review snapshot
were changed. Source setup author IDs remain excluded after automatic approval
review rejected an optional proposal to carry them; there is no outstanding
permission request or alternative transfer of those IDs.
