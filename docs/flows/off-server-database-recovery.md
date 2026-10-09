---
status: active
owner: operations
updated: 2026-10-10
tags: [backups, recovery, r2]
---

# Encrypted off-server database recovery

This is a platform-operator workflow. It contains every Workspace and is never a
tenant-facing download, app endpoint or storage-billing feature. The
[decision](../adr/2026-10-10-independent-encrypted-database-backups.md) and
[ordered plan](../plans/backup-storage-and-evidence-efficiency.md) control activation.

## Owner key custody

Use age X25519 keys. Generate the private identity outside production, Git and
OneDrive; store it in the owner's password manager and a second offline recovery
copy. Copy only the public `age1...` recipient to the uploader. Do not paste private
keys, passwords or S3 secret credentials into chat or commit them. Merely generating
the key does not establish two recoverable copies. Confirm actual custody before
using real database backups as an accepted disaster-recovery path.

For the prepared identity, open the protected file yourself, save its entire text
as a password-manager secure note, then reopen/check that note. Copy the file to
encrypted offline storage, check it, and disconnect/store that device safely.
Clear the clipboard afterward. A second folder on the same computer or OneDrive
does not establish an independent offline recovery copy. Confirm both actual copies.

## Host setup

The dedicated private Standard bucket is `rokkad-production-backups`. Keep public
access disabled and do not add a blanket expiry rule. Use an account token with
Object Read & Write scoped only to that bucket. The prepared production token is
restricted to 172.235.9.64/32 and 2600:3c08::2000:edff:fe68:163/128, the exact
production server IPv4/IPv6 addresses, and has no automatic expiry. Monitor failures
and rotate or revoke it when needed; a new recovery host needs a separately scoped
credential because it cannot use this IP-restricted token automatically.

Install age from the trusted OS package repository. The Python operator uses the
existing boto3 SDK and retention catalogue validator. Its root-owned 0600 config
is `/etc/rokkad/backup-r2.json`:

```json
{
  "bucket": "rokkad-production-backups",
  "endpoint": "https://ACCOUNT_ID.r2.cloudflarestorage.com",
  "access_key_id": "DEDICATED_BACKUP_ACCESS_KEY",
  "secret_access_key": "DEDICATED_BACKUP_SECRET",
  "recipient": "age1PUBLIC_RECIPIENT"
}
```

These placeholders are deliberately invalid. Install actual values through a
secure operator channel without logging them. Do not place backup credentials in
the web process or reuse media credentials. The hourly uploader needs no private
decryption key.

Run `python3 scripts/publish_operational_backup.py` under the host operator account
only after configuration. The initial operator is installed/tested as an inactive
candidate until acceptance; merely existing in the checkout does not run it.

After the 10 October actual recovery and owner custody acceptance, the existing
hourly service uses `finish_off_server_backup.py --apply` as its completion hook.
Its root-only acceptance file binds the exact public recipient, recovered image
and selected policy. The default command without `--apply` validates a dry run;
it does not upload or delete. Replacing the image/key requires renewed acceptance.

Run `python3 scripts/preserve_backup_runtime.py` once per accepted release to
stream its exact image through gzip and age, verify downloaded ciphertext and
publish a separate `releases/v1/` completion. This artifact is excluded from ordinary
backup expiry. Actual decryption/loading must reproduce the exact compatible image
ID; do not infer independent recoverability from upload alone.

## What a completed upload means

The operator validates a fresh existing dump, sidecar/checksum and catalogue;
captures compatible deployment metadata/configuration; streams the package to age;
uploads a unique encrypted object; downloads and hashes it; and conditionally
publishes/readbacks a completion marker. Retries verify an existing completed
artifact without replacing it. Network, access, changed source or corrupt-byte
failures do not produce local completion or authorize expiry. Unfinished artifacts
may remain remote for separately scoped orphan review.

The encrypted tar includes database.dump, recovery.json, runtime.env,
production_settings.py, production-compose.yml and production-release.json.
Runtime credentials and configuration are encrypted inside the artifact; private
age identities and dedicated uploader credentials are excluded. Completion metadata
contains only identifiers/hashes/sizes, not customer rows or runtime secrets.

Upload verification proves the downloaded ciphertext matches. It does not prove
that a private key is recoverable, that a full database restore works, or that the
compatible runtime image survives host loss. Retention remains unchanged.

## Actual restore acceptance

1. Retrieve a completed marker and its exact artifact with a separately authorized
   recovery credential. Download and verify SHA-256 and size; do not rely on ETags.
2. Recover the private identity from the owner's chosen storage. Use it only in
   a protected operator-controlled environment. Decrypt the downloaded artifact;
   verify the package's dump checksum and deployment configuration hashes.
3. Establish a compatible runtime image/source recovery path independent of the
   failed server. An image ID alone is not an available image. Protect this release
   artifact separately from expiring hourly/daily objects.
4. Restore into a new explicitly named isolated database; refuse any existing
   production or rehearsal target. Provision the required owner/runtime roles and
   grants on a new cluster before restore. Use owner-only schema setup and then run startup,
   readers and adversarial isolation checks with the restricted runtime role.
5. Compare snapshot table/source fingerprints, native balances and representative
   ordinary/source screens. Verify the 39,196 closed positions and 19 held claims
   when this snapshot contains the accepted conversion. Preserve media references;
   database backups do not copy R2 photo contents.
6. Keep outbound payments/messages disabled. Record only aggregate acceptance and
   source hashes; keep customer rows, raw logs and temporary private identity on the
   protected operator side. Remove temporary private-key copies after the test.

The 10 October test restores a new database on the existing PostgreSQL 16 cluster.
Its isolated settings retain an exact target guard, normal non-root app user and
restricted database role; static assets are regenerated into the isolated directory.
All snapshot rows, closed/held cohorts and native/isolation readers pass. The
private key stays on Windows while decrypted bytes stream through SSH. The exact
independent image also decrypts/loads successfully. See the
[acceptance record](../implementation/encrypted-backup-recovery-20261010.md).
This is not an acceptance of new-host role provisioning or managed PostgreSQL.

Actual restore, owner key custody and compatible image recovery pass on 10 October;
the ordered hourly completion/retention hook is active and its full cycle passes.
Preserve the latest 24 completed backups plus the last copy from each of 30 UTC
dates remotely. Locally keep the newest six copies plus every older copy without
matching retained remote coverage. Initially all 35 local copies remain, including
32 pre-R2 points. No backfill or deletion of those uncovered points is implied;
remote coverage builds from activation. The uploader alone still has no expiry
authority. The completion operator hashes actual remote bytes for local-expiry
candidates and rechecks all evidence before deletion. Protect release images,
deployment/rehearsal checkpoints, other recipients and incomplete/orphan objects.

Check `rokkad-production-backup.service` result/journal and the private
`backups/off-server/retention-last.json` report for freshness, low space and failures.
Missing remote access, failed publication, corruption, stale evidence or a changed
image/key fails the service and stops expiry. Do not silently fall back to the old
local-only expiry policy. Continue periodic operator recovery checks and arrange
capacity when the guarded free-space headroom is insufficient.

Current scope uses full dumps. It does not provide continuous WAL/PITR, automated
database failover or a managed database. Evaluate those separately where needed.
