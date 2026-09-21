---
status: active
owner: project
updated: 2026-09-21
tags: [migration, portability, operator]
---

# Reviewed Linode replay

`manage.py linode_migration` packages the accepted conversion, compares another
snapshot, replays it into three clean Workspaces, and reconciles every imported
record. This is an operator workflow for the known Linode source, using existing
import services. It does not restore old SQL into the shared-schema database.

## Validated September 21 run

The approved discovery snapshot was replayed into the newly created
`rokkad_baseline_rehearsal_cutover_20260921` database. Cold admission used clean
commit `f276b9b8`; final validation safeguards, tests, complete replay and
reconciliation used clean commit `da3c91ec`. The actor used ordinary owner
Memberships under the restricted runtime role. Target Workspace IDs were
deliberately assigned in a different order from the accepted browser rehearsal.

| Source | Party masters | Contacts | Addresses | Openings | Closed archive | Excluded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| JCL | 5,882 | 1,898 | 3,997 | 2,355 | 26,664 | 0 |
| JSK | 646 | 513 | 621 | 1,483 | 3,811 | 1 |
| Lakshmi | 2,102 | 1,085 | 2,104 | 2,435 | 8,658 | 0 |
| Total | 8,630 | 3,496 | 6,722 | 6,273 | 39,133 | 1 |

All 45,407 source loan IDs reconcile exactly once. Opening principal is
199,847,583 and interest is 22,614,850, with no unpaid fees. Reconciliation checks
every input/document, identity, balance, collateral record, remaining obligation
and next interest boundary, including the distinct-address and corrected-purity
decisions. Restricted-role checks confirmed cross-Workspace and missing-context
isolation. Extra archive versions and wrong source-branch provenance fail closed.

The final checkout passed 56 focused tests and the import-boundary guard. All 31
scoped page renders, 22 opening exports, three archive exports and 22 full-release
and retry simulations passed. Servicing was rolled back. The complete replay
passed; all 291 business-table fingerprints matched afterwards, and reconciliation
passed again. The accepted browser rehearsal's recorded 33 business-table hashes
were separately checked unchanged during this work.

Private evidence is in `outputs/linode-clean-replay-20260921/`; start with
`completion.json` and `verification.json`. `evidence-manifest.json` seals the
reports, logs, release/migration metadata and fingerprints. The approved package
is `outputs/linode-reviewed-package-20260921/`, with manifest SHA256:

```text
6b8fa81cc11f0a5200c62f98856d677088aa1879d8063a0b06da0ec2e1df140e
```

Cold admission took 6,059 seconds (about 101 minutes) on this local machine.
Production timing requires its own measurement; this excludes media, final-source
preparation and acceptance. The result is `RECONCILED_DATABASE_ONLY`.
Production remains live, and no media copy or production cutover is claimed.

## Inputs and preparation

Retain the original archive, the private package directory, its independently
recorded manifest SHA256, an explicit JSON source-to-destination Workspace map
(`jcl`, `jsk`, `lakshmipawnbroker`), the authorized actor ID and target database
name. Packages contain personal and financial information; keep them outside Git
and protect their backups. Do not edit accepted packages.

`package` captures the complete, unserviced accepted rehearsal. Required options:
`--dump`, `--package-dir`, `--workspace-map-file`, `--actor-id`,
`--expected-database`, `--source-namespace`, `--approval-reference`, and
`--exclusions-file`. The exclusions JSON maps each source schema to its reviewed
excluded records (empty arrays where none). The command checks complete source
loan coverage and preserves the original Party batch decisions and financial
evidence. It refuses pending batches or a serviced rehearsal.

Provision an empty destination using normal owner-only migrations and explicit
grants to the restricted runtime role. Create three Workspaces and their ordinary
Owner Memberships using the current control plane. Do not use the migration owner
or a superuser as the importer runtime. New lending, subscriptions and staff access
are separate setup tasks. Replayed licences are legacy references and the imported
servicing product is retired for new lending.

## Operator commands

Use the settings appropriate for the destination. For local isolation use
`django_project.settings.baseline_rehearsal` and set `ROKKAD_REHEARSAL_DB_NAME` to
the explicitly named `rokkad_baseline_rehearsal_...` database. The following example
uses placeholders, not production credentials:

```powershell
python manage.py linode_migration check-source --package-dir PACKAGE --expected-package-sha256 SHA --dump SNAPSHOT --output-dir REPORT --settings django_project.settings.baseline_rehearsal
python manage.py linode_migration replay --package-dir PACKAGE --expected-package-sha256 SHA --dump SNAPSHOT --workspace-map-file MAP --actor-id ACTOR --expected-database DATABASE --output-dir REPORT --commit --settings django_project.settings.baseline_rehearsal
python manage.py linode_migration verify --package-dir PACKAGE --expected-package-sha256 SHA --workspace-map-file MAP --actor-id ACTOR --expected-database DATABASE --output-dir REPORT --settings django_project.settings.baseline_rehearsal
```

`check-source` reports added, removed and changed source IDs across the extracted
legacy tables without destination writes. Any archive checksum change requires
fresh preparation, even if those tables happen to match. For a changed snapshot,
rerun the existing source preparation/review workflow; this command does not
generate or approve its new opening balances. A different cutover date also needs
new reviewed inputs.

`replay` verifies every package file before writes and checks all three Workspace
permissions. A new package requires clean Workspaces. Retry the exact same command
after interruption: atomic setup, Party identities, exact opening documents and
archive hashes preserve admission progress. It never merges into the accepted
rehearsal database. Its final state is `ADMITTED_RECONCILIATION_REQUIRED`.

`verify` requires that run's output binding and compares all Party fields and
identities, all signed opening/source documents, balances, collateral, schedules,
next interest boundaries, complete closed documents and source-ID partition. It
checks forced RLS with missing and cross-Workspace context. Success writes
`verification.json` with `RECONCILED_DATABASE_ONLY`, not production readiness.
Reconciliation is for the unserviced opening snapshot; perform it before allowing
users to start transactions. Preserve the report with the package and release ID.

## Remaining cutover prerequisites

Production is still live. Final cutover requires a scheduled write freeze and a
new complete database snapshot, new preparation/reconciliation, production access
and valid lending setup, and acceptance before users switch. Do not layer a fresh
dump over this rehearsal.

Photographs/documents live on the same Linode server filesystem, not Cloudflare
R2. Inventory the actual media root and path layout; separately capture file
contents, sizes, checksums and source-record references. Copy to the selected
destination storage and verify tenant-scoped access and completeness. No media
copy is claimed by these database commands. R2 source-bucket credentials are not
needed to retrieve these files.

The stated production commit configures `MEDIA_ROOT=/var/www/rokkad/media` in
`django_project/settings/prod.py`; base settings select `TenantFileSystemStorage`
with tenant-relative `%s/` media. This is a code-derived starting point, not a
verified live-server path.
Legacy customer photos use `contact.CustomerPic.image` (`customer_pics/...`) and
proof documents use `contact.Proof.doc` (`upload/files/proofs/...`). Verify
the actual deployed settings, tenant prefixes and files before backup/mapping.
The current database replay does not import those two media models.

The September 21 dump's read-only reference inventory found 1,153 customer photo
rows (JCL 18, JSK 250, Lakshmi 885) and 30,685 nonempty loan-item picture references
(14,723; 4,867; 11,095 respectively). The three `contact_proof` tables contain no
rows in this snapshot. These are reference counts, not verified file counts or a
claim that no documents exist elsewhere. Source paths and record associations are
retained privately in `outputs/linode-media-inventory-20260921/references.jsonl`;
the summary records its checksum. Loan-item picture paths in this dump start with
`loan_pics/`. No source file contents were available or copied.
All 31,838 schema/path pairs are distinct, but 5,180 stored relative paths occur in
more than one source schema. Preserve the schema in every association and verify
the deployed storage's resolution of each path; a flat merge by filename could
associate a different branch's photograph. Matching relative paths do not prove
matching file contents or matching physical source locations.
