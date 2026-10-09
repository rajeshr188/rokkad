---
status: complete
owner: operations
updated: 2026-10-10
tags: [backups, recovery, r2, acceptance]
---

# Encrypted off-server backup and recovery acceptance

BS-03 completes its first actual encrypted upload, download and checksum
verification. BS-04's technical restore and compatible runtime-image recovery
pass. The owner confirms both recovery-key copies saved/checked. Ordered hourly
R2 publication and conservative remote/local retention are activated and a complete
production backup cycle passes.

The [decision](../adr/2026-10-10-independent-encrypted-database-backups.md),
[operator flow](../flows/off-server-database-recovery.md) and
[ordered plan](../plans/backup-storage-and-evidence-efficiency.md) describe the
continuing gates. No production business rows, migrations, application containers,
media credentials are changed. The hourly completion hook now implements the
selected remote/local retention while protecting local points without remote coverage.

## Provisioning and secret custody

Created the private Standard bucket `rokkad-production-backups`, with public access
disabled. The owner explicitly approves token `rokkad-production-backup-20261010`,
Object Read & Write for this bucket only, valid until revoked. Its exact allowed
source addresses are 172.235.9.64/32 and 2600:3c08::2000:edff:fe68:163/128. The
IPv6 addition receives separate at-action approval after the initial IPv4-only
request is denied: the server actually connects to Cloudflare over IPv6.

The token is installed at `/etc/rokkad/backup-r2.json`, root-owned 0600, with the
public age recipient. It is absent from web environment/configuration and no
private age identity is uploaded to production. Media credentials stay separate.

The browser's SSH process cannot connect. Automatic approval review initially
rejects workstation credential staging because authorization covers server storage.
The owner subsequently approves a temporary Windows-user-encrypted transfer.
Current-user DPAPI cannot cross the browser/terminal's different Windows identities;
instead a temporary Windows-user-owned nonexportable document-encryption certificate
encrypts the same bridge. Terminal decryption happens only in memory, followed by
SSH installation. Both encrypted transfer files and the temporary certificate/private
key are removed. No plaintext credential file or secret is emitted to chat/Git.

The owner approves key preparation outside Git/OneDrive. Official age v1.3.2 Windows
release digest is checked before generation. The private identity's Windows ACL is
explicitly protected, with exactly the current Windows user and SYSTEM allowed.
The generator's Unix-style world-readable warning blocks progress until that ACL
is explicitly repaired/verified. The owner selects password-manager plus offline
recovery copies; saving/checking is initially unconfirmed. The owner subsequently
confirms both copies saved and checked before activation. Generating a file and
successfully decrypting with it do not by themselves prove recovery custody.

Ubuntu age 1.2.1 is installed from the trusted package repository on production.
Candidate operators are first tested under the private release directory and then
installed as root-only host scripts. New operator code uses the existing boto3 SDK,
never app APIs.

## First real backup

Snapshot: `20261009T220003Z` (10 October, 03:30:03 IST).
Encrypted package: 167,127,064 bytes; ciphertext SHA-256:
`521f4c2e0660c5e903c2c0f9054cbf4655554eaec66e762a2350896a0e19b06b`.

The operator verifies the completed local dump, sidecar and catalogue, streams its
fixed recovery package through age, uploads a unique artifact, downloads/hashes the
actual bytes, and conditionally publishes/readbacks a completion marker. Invalid,
stale, changed, inaccessible or corrupt evidence fails closed. A retry validates
the same completed artifact without replacing it. An upload never authorizes expiry.

The package contains the database, frozen runtime environment, settings, compose,
release metadata and checksummed recovery manifest. Dedicated backup credentials
and the private identity are excluded. Database backups contain all Workspaces;
they are operator recovery artifacts, outside Workspace media inventory/billing.

## Actual isolated restore

Downloaded ciphertext is decrypted on Windows and streamed through SSH into the
protected test folder. No local plaintext customer dump or server private identity
is written. Received database/configuration hashes match the encrypted manifest.
Restore creates only new target `rokkad_backup_restore_20261010`, refusing an existing
target. Owner-only `pg_restore --exit-on-error` succeeds on PostgreSQL 16.

All 879,350 rows across 202 snapshot tables match the isolated restore. The comparison
streams the snapshot's COPY data and restored COPY output, using counts and SHA-256
row modular-sum/XOR fingerprints without exporting customer rows. This includes
financial events, agreement snapshots, retained sources, media references and
control-plane/billing rows. It is a snapshot comparison, not a comparison to a live
database that may receive later transactions.

Normal non-root application startup and regenerated static assets pass. The
isolated settings copy changes only its exact database-target guard and static
output path; it retains the restricted runtime role. Outbound mail and billing
effects are disabled, and no workers or payment actions run. Checks verify:

- All 39,196 ordinary CLOSED positions and 19 held claims, including each Workspace's
  expected totals, original source access, ordinary details and number searches.
- Direct and paper entry screens, native detail/closure readers, Loan health and
  six native loan samples across all three Workspaces.
- No-context hiding and cross-Workspace isolation. An adversarial UPDATE under the
  restricted role sees zero foreign rows and rolls back in the isolated target.
- No pending migrations, superuser or BYPASSRLS privileges for the runtime role.

This test uses a separate database in the existing PostgreSQL cluster. It proves
logical restore and restricted application behavior, not new-host role/bootstrap
provisioning, automated failover or managed-provider compatibility. A recovery host
must create the required owner/runtime roles and grants before restore, recover
configuration securely, and obtain a separate recovery credential because the
production token only allows this server's addresses.

## Independent compatible application artifact

The exact current runtime is saved, gzip-compressed, age-encrypted and preserved
under `releases/v1/`, outside ordinary hourly/daily expiry. Its downloaded encrypted
artifact is 227,755,129 bytes. Decryption streams from Windows through SSH to a
Docker load; the loaded image exactly matches:
`sha256:7b1a2aab8c04be1e74b7409a4e9e4d08e1d7bb8be59e629aa3c2a1b36d721436`.
Production container identity and running deployment stay unchanged. Repeat this
preservation and recovery acceptance for subsequent releases; an image ID alone
does not establish availability after host loss.

## Validation, cleanup and remaining gates

28 Linux unit/integration tests pass, including real age roundtrip, wrong-key and
tampered-ciphertext rejection, remote corruption/access/completion failures,
idempotent retries, fixed bucket/prefix boundaries and all nine existing retention
regressions. Retention tests cover exact hourly/daily selection, remote changes,
missing/corrupt/stale evidence, protected foreign recipients/release/orphan objects,
six local copies plus uncovered history, custody/image gates, and failed-publication
refusal before any expiry. Actual encrypted database and runtime recovery pass.

The exact newly created test database, regenerated static files and test plaintext/
ciphertext are removed after acceptance. Private aggregate reports remain in
`loan-position-release-20261010/bs04-restore/` on the server. Post-cleanup free space
is 9.375 GiB; this is a measurement, not a growth guarantee. Existing deployments,
media and hourly/local backup recovery remain intact.

## Hourly activation and final acceptance

The owner confirms password-manager and offline copies saved/checked. Root-only
`/etc/rokkad/backup-acceptance.json` binds actual database restore, exact image
recovery, owner custody and selected policy to this public recipient/image. A new
image or key requires renewed compatible recovery acceptance before expiry.

The dry run preserves both initial remote points and all 34 then-existing local
backups, with zero deletions. A separate systemd drop-in changes only the backup
service's completion hook to `finish_off_server_backup.py --apply`. Original unit
files, timer and dump command are preserved; application containers do not restart.

Each hourly cycle completes/validates the ordinary dump, publishes/downloads/hashes
encrypted R2 bytes, validates remote metadata/object presence, prepares the complete
retention plan, downloads/hashes every local-expiry candidate's retained remote
artifact, rechecks evidence, then expires only recognized redundant points.
Publication, missing/stale/changed evidence, custody/image or capacity failures stop
expiry and fail the service for operator attention. Existing private journals record
exact validated proposals and completion; ETags only detect changes, never substitute
for SHA-256. The S3 compatibility boundary follows
[Cloudflare's documented operations](https://developers.cloudflare.com/r2/api/s3/api/).

Remote retention is newest 24 completed backups plus latest per UTC day across
30 days. Local retention is newest six completed snapshots plus any local snapshot
without matching **retained** remote coverage. This conservative transition protects
pre-R2 recovery points; it does not delete them just because a new backup uploaded.
No historical backfill or blanket bucket expiry is performed. Release images,
deployment/rehearsal checkpoints, other recipients and incomplete/orphan objects
stay outside ordinary expiry.

The full manually triggered production cycle completes on 10 October at 04:35 IST:
snapshot `20261009T230417Z`, three verified retained remote database points, all 35
local copies retained including 32 without remote coverage; zero local/remote
deletions. The backup service succeeds, newest catalogue/checksum and remote binding
pass, HTTPS and all six timers are healthy. The live image and original unit files
match. Final free space is 9.141 GiB. Remote daily coverage builds from activation;
this does not claim that thirty prior dates are already backed up independently.

Do not restore the former standalone local retention hook as a silent fallback
when R2 fails. Preserve local copies and resolve service failure; a rollback to a
different policy requires its own review. Continue space/failure monitoring and
periodic operator recovery rehearsal. Protect the earlier 32 local points until
their independent recovery coverage is separately reviewed. This work bounds new
local hourly growth, not all future database/image growth.

Managed PostgreSQL is a separate [feasibility review](managed-postgresql-feasibility-20261010.md).
No paid cluster is created or existing unrelated cluster repurposed. Compact future
source profiles remain BS-05; existing immutable financial/source bytes are preserved.
