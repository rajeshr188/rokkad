---
status: active
owner: project
updated: 2026-09-23
tags: [migration, media, rehearsal, r2]
---

# Verified legacy photo attachment

This follows [preservation](linode-media-preservation-20260921.md) and the
[attachment decision](../adr/2026-09-22-legacy-media-attachment-evidence.md).
It supports the accepted isolated rehearsal and an explicitly bound new production
destination. It does not attach media to the old live Linode application.

## Operator flow

1. Install the pinned requirements, including django-storages and boto3.
2. Apply ordinary owner migrations to the explicitly named rehearsal database.
   New tables require runtime grants as in the reviewed replay runbook.
3. Run `linode_media plan` using restricted runtime settings, an explicit database,
   actor and schema-to-Workspace mapping, the checksummed source-reference map,
   checksummed customer-photo source evidence, installation namespace and archive
   checksum. It resolves the entire destination graph before writing its plan.
4. Select `django_project.settings.rehearsal_r2`, with `ROKKAD_REHEARSAL_DB_NAME`
   and `ROKKAD_REHEARSAL_R2_CREDENTIALS` pointing to the protected credential file.
   Never pass secrets as command-line arguments or place them in the repository.
5. Run `linode_media apply` with the exact plan path/checksum, same destination
   mapping and actor, an evidence output directory, and `--confirmed`.
   The command rechecks the full plan, conditionally creates and verifies separate
   application objects, then admits each attachment through authorized services.
   Interrupted runs can replay the same plan. Accepted receipts are not duplicated.
6. Verify attachment counts/hashes, source-original retention, unchanged financial
   fingerprints and ordinary-owner private routes, then test an identical retry.
7. Launch only the dedicated rehearsal browser with
   `scripts/start_rehearsal_web.ps1 -DatabaseName <rehearsal> -R2CredentialFile <protected-file>`.
   Omitting the credential argument retains the previous filesystem-only mode.

Use `manage.py linode_media --help` for the explicit arguments. The command refuses
unbound non-rehearsal databases, a database-name mismatch, privileged runtime roles, duplicate
Workspace destinations, changed evidence checksums, candidates, and changed target
bindings. Import access is checked again at each admission and on receipt replay.

Storage objects live below `media/application/<rehearsal-database>/`; backup
originals remain below `media/legacy/<installation>/`. FileField names are relative
to the application prefix. Mutable Party fields never share an object. If the
application storage location changes later, migrate/copy those objects and verify
them before changing the runtime prefix.

Source customer default flags are authoritative; no default means no profile
selection. Existing local profile photos cause a review stop. Existing receipts
remain after user removal/replacement so retry does not resurrect deleted media.
Storage failure before database admission leaves no false success receipt; a
verified but unattached copy may remain and will be checked on retry.

The [django-storages S3 options](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)
support separate default/static backends, private ACL defaults and authenticated
URLs. Application links continue through Workspace-authorized routes; no public
R2 domain is enabled. A storage URL is not a replacement for application access
control.

## Production target binding

The [production admission decision](../adr/2026-09-23-production-media-target-binding.md)
adds `--target-manifest` and `--target-sha256` to both plan and apply. Use
`--settings django_project.settings.prod_r2` and a restricted runtime connection.
Owner migrations remain a separate operation. Do not use the migration role for
attachment admission.

Create the manifest only after the new database, Workspaces, private R2 prefix and
durable credentials exist. Keep this non-secret file with the private operator
evidence. Its exact structure is shown below; these are illustrative values, not a
reviewed or usable deployment target:

```json
{
  "profile": "linode-media-target/1",
  "database": {
    "name": "rokkad_production",
    "host": "127.0.0.1",
    "port": 5432,
    "user": "rokkad_runtime",
    "server_address": "127.0.0.1",
    "server_port": 5432
  },
  "storage": {
    "endpoint": "https://<account-id>.r2.cloudflarestorage.com",
    "bucket": "rokkad-production-media",
    "location": "media/application/production/<deployment-id>"
  },
  "source": {
    "namespace": "<source-installation-uuid>",
    "archive_sha256": "<reviewed-dump-sha256>"
  },
  "workspaces": {
    "jcl": {"id": 1, "slug": "jcl"},
    "jsk": {"id": 2, "slug": "jsk"},
    "lakshmipawnbroker": {"id": 3, "slug": "lakshmipawnbroker"}
  }
}
```

Replace every example database value and Workspace ID/slug from the actual new
target. Schema keys must be the actual source schema names. Read the connected
identity under the runtime role with:

```sql
SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port();
```

`host`/`port` describe the configured TCP connection; `server_address`/`server_port`
describe the connected PostgreSQL server. Unix socket connections are not admitted
by this contract. The manifest accepts no passwords, keys or extra properties.
SHA-256 is over the exact file bytes; formatting changes require a new checksum
and plan. Retain the reviewed file alongside the plan, not just its hash.

Run the existing plan command with the source reference/customer file paths and
checksums, namespace, archive checksum, explicit database, actor, Workspace map and
output directory. Add the production settings and both target arguments:

```text
python manage.py linode_media plan --settings django_project.settings.prod_r2
  --database <database> --actor <owner-id> --workspaces <schema-to-id-json>
  --target-manifest <target.json> --target-sha256 <target-sha256>
  --references <references.jsonl> --references-sha256 <references-sha256>
  --customers <customers.jsonl> --customers-sha256 <customers-sha256>
  --namespace <source-uuid> --archive-sha256 <dump-sha256> --output <plan-directory>

python manage.py linode_media apply --settings django_project.settings.prod_r2
  --database <database> --actor <owner-id> --workspaces <schema-to-id-json>
  --target-manifest <target.json> --target-sha256 <target-sha256>
  --plan <plan.jsonl> --plan-sha256 <reviewed-plan-sha256>
  --output <apply-directory> --confirmed --workers 16
```

These are wrapped argument lists; join each invocation for the operator's shell
and quote JSON/path values appropriately. Keep credentials in protected runtime
configuration, never on this command line. Review the plan and its summary before
apply. The first JSONL record binds `linode-media-plan/2` to the target checksum;
rehearsal plans cannot be reused for production. All rows are rechecked before
copying begins, including source snapshot, Workspace and resolved attachment/name
bindings. A changed target, source or prefix requires replanning. Identical retry
retains receipt idempotency and does not restore user-removed media.

Production application copies use the manifest's stable production prefix;
originals stay under `media/legacy/` in the same private bucket. Planning does not
construct an R2 client or copy objects. Successful apply reports
`PRODUCTION_MEDIA_ATTACHED` with `production_ready: false`: hosted storage checks,
reconciliation, backup recovery and cutover remain separate requirements. Local
tests use isolated PostgreSQL and filesystem copies, not production or R2.

## September rehearsal

### September 23 hosted reuse

The hosted September 23 dataset now has 28,347 verified references attached:
1,148 Party, 6,082 active collateral and 21,117 historical-loan photographs. This
uses 29,489 private application objects under
`media/application/production/hosted-rehearsal-20260923`. The explicitly bound
prod_r2 admission path was used with the restricted runtime role; its generic
`PRODUCTION_MEDIA_ATTACHED` report does not mean the rehearsal is production.

All three exact-plan retries created nothing. All 252 business-data fingerprints
match, fifteen private HTTP/denial probes passed, and all 32,567 earlier
preservation objects/reports remain intact. 25,054 attached references are known
blank source images. Of 124 newer references, 69 reused already-preserved exact
branch paths; the remaining 55 were found and copied after explicit owner
authorization (JCL 27, JSK 9, Lakshmi 19). Read-only, no-symlink source reads and
conditional R2 writes/read-back hashes verified those originals, then ordinary
restricted-role admission attached all 55 as collateral photos. The preservation
inventory now totals 32,622 objects. Of the 55 fresh files, 53 match known blank
source hashes. Increment plan SHA-256:
`ce9a08dcc9133654462a34b9ea30dfe9d543557d00f0e84cac5601f90508c215`.
The 2,465 older missing files and 1,149 unverified shared candidates remain excluded.
The subsequent exception review rechecked all 3,614 exact branch paths read-only
on September 23; all remain absent. Current imported-record mapping resolves
102 active collateral references, 3,507 historical references and five customer
photographs. Shared candidates comprise 1,144 known blank images and five
unverified customer images; 344 exception paths also occur in another branch's
references. No candidate was attached. Retain these exceptions explicitly rather
than inventing photographs or inferring ownership from a matching filename.
The aggregate review, detailed source checks and checksums are retained in the
server-only `media-exceptions-20260923/` directory.
Fresh old-Linode access was limited to those 55 paths; same-path changes to other
files since the September 21 preservation are not independently checked.

Detailed evidence and the post-media backup stay on the server under
`/home/rokkad/deploy/rehearsal/` (`media-reuse/`, `media-increment-20260923/` and
`backups/`). The owner chose
server retention after automated review rejected exporting the database to the
OneDrive workspace. Recursive media/customer metadata export was also rejected;
do not retry those exports without explicit authorization. Local project docs
contain aggregate results; older local preparation inputs are not final reports.

### September 21 local dataset

Private evidence directory: `outputs/linode-media-attachments-20260922/`.
The completed import contains **28,224** source images: **1,148 Party**, **5,988 active
collateral**, and **21,088 closed-history**. There are **29,366** separate
application objects including **1,142** default profile copies. Two source
customers without defaults remain unselected; missing originals remain excluded.
The exact plan SHA-256 is
`62d8d184af08e32b74e10bd3741695bc85c342326ffdecb518bfa65dd22005b8`.

All attachments and 29,366 application objects reconcile against the plan. The
32,554 preserved source files and 13 preservation reports remain intact. Twelve
ordinary-owner HTTP probes across all three Workspaces verify exact image hashes,
private cache headers, anonymous denial and cross-Workspace denial. Nine detail
pages render without direct R2 URLs. Browser checks cover customer, active-loan and
closed-history images. All 252 financial and Party metadata fingerprints are
unchanged. A full identical retry recognizes all 28,224 receipts and creates
nothing. Sixty focused tests pass. Production remains live and unchanged.

Visual and pixel-level inspection also confirmed **24,946 blank grey source image
references** across twelve exact hashes: **5,283 active collateral**, **19,661
closed history**, and **two customer images**. These files transfer correctly but
are not usable photographs. The application labels these confirmed fingerprints;
the private `source-image-quality.json` preserves decoded dimensions, uniform
RGBA extrema and counts. The other 3,278 image references have not been visually
certified. Do not present the 28,224 attached-image count as usable-photo coverage.

Known source gaps remain: 102 active photo references lack branch files; 203 active
items have no recorded photo reference; 3,507 closed-history photo references and
five customer photo references lack branch files. The 1,149 unverified shared
candidates stay preserved separately. No source dates, images or ownership are
invented. The one-week credential will expire; use a separately approved runtime
credential before any production deployment.
