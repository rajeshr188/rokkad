---
status: active
owner: project
updated: 2026-09-22
tags: [migration, media, rehearsal, r2]
---

# Verified legacy photo attachment

This follows [preservation](linode-media-preservation-20260921.md) and the
[attachment decision](../adr/2026-09-22-legacy-media-attachment-evidence.md).
It applies to the accepted isolated rehearsal, not the live Linode application.

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
non-rehearsal databases, a database-name mismatch, privileged runtime roles, duplicate
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

## September rehearsal

Private evidence directory: `outputs/linode-media-attachments-20260922/`.
The plan resolves **28,224** photographs: **1,148 Party**, **5,988 active
collateral**, and **21,088 closed-history**. There are **29,366** separate
application objects including **1,142** default profile copies. Two source
customers without defaults remain unselected; missing originals remain excluded.
The exact plan SHA-256 is
`62d8d184af08e32b74e10bd3741695bc85c342326ffdecb518bfa65dd22005b8`.

Execution and final verification are in progress. Do not treat the plan as proof
that attachments have been created. Production remains live and unchanged.

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
