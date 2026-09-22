---
status: active
owner: project
updated: 2026-09-22
tags: [migration, media, r2, portability]
---

# Linode filesystem media to private R2

## Current checkpoint

Preservation is complete: 32,554 files (31,405 branch originals and 1,149 separately
labelled shared candidates), 591,274,335 bytes, copied directly to private R2 and
read-back SHA-256 verified. The object set/sizes reconcile, retries refuse overwrite,
anonymous S3 access is rejected, public endpoints are disabled, and 13 evidence files
are also preserved and verified. See [the preservation record](../implementation/linode-media-preservation-20260921.md).

Application attachment and R2 integration are complete in the accepted isolated
rehearsal: 28,224 source images and 29,366 separate application copies reconcile.
Private access checks pass and all 252 financial/Party fingerprints are unchanged.
See [the attachment record](../implementation/linode-media-attachments.md).
Production runtime credentials, current lending/access setup and final frozen
database/media reconciliation remain. The final source freeze is not scheduled.
The owner selected a separate, not-yet-created Linode server. The tested `prod_r2`
settings and [cutover runbook](../implementation/linode-production-cutover.md)
prepare that deployment; no live configuration has been changed.

## Selected destination and current boundary

The owner selected Cloudflare R2 for the new application's media and supplied
`root@rokkad.com`, `/var/www/rokkad/media` as the production source. The directory
matches the historical production settings. After the initial authentication
failure, the owner installed temporary key access. Read-only SSH inventory verified
the root, schema folders, deployed historical commit and source settings. File
bytes were initially hashed on Linode; the later preservation copy is recorded above.
Retain host-key verification and never collect passwords/private keys in chat.

The owner confirmed password login and requested the next step. Prepared private
`outputs/linode-media-ssh-20260921/authorize.ps1` for execution in the owner's own
PowerShell terminal. It generates the dedicated key under
`%LOCALAPPDATA%/RokkadMigration/linode-media-20260921/` with restricted local access,
outside OneDrive, then uses an interactive SSH password prompt to install only the
public key. The SSH `restrict` option disables forwarding and PTY, not root command
execution. The paired `revoke.ps1` removes this exact authorization after migration.
Both scripts are syntax-checked. The owner ran authorization and live key
verification succeeded. Revocation remains required after migration. No SSH
password is stored.

A download to the owner's computer is unnecessary. Run a bounded transfer from
Linode to the selected private destination, preserving the source. Cloudflare
documents filesystem uploads using [rclone copy](https://developers.cloudflare.com/r2/examples/rclone/).
Use a dedicated production business-media bucket, with rehearsal files isolated
from production. The owner initially confirmed the bucket had not been created;
the approved bucket now exists and its dedicated migration credentials were saved
privately and verified. The old local R2 environment fields point at another account
and must not be used for this destination. The existing
Chrome Cloudflare dashboard is now signed in. There is an existing empty `rokkad`
bucket, but the owner had not identified it as the production target. The proposed
separate bucket is `rokkad-production-media`, Standard storage, automatic Asia
Pacific placement, private by default. After automatic approval review blocked
the agent-selected name, the owner explicitly approved it. Bucket creation then
succeeded; the dashboard confirms public access disabled and zero objects.
Existing buckets remain unchanged. The guarded SDK check found the local endpoint
belongs to a different account and made no authenticated request. The owner
explicitly approved a dedicated one-week Object Read & Write token for this bucket;
Cloudflare confirmed creation. The user completed secure local entry,
with no secret values printed in tool output or chat, using
`outputs/linode-media-ssh-20260921/configure-r2.ps1`; it writes only to the protected
LocalAppData migration directory, outside OneDrive. This expiring migration token
must not become the permanent application credential.

The ordinary `STORAGES.default` is Django FileSystemStorage. Development/production
R2 options exist but their storage override is commented out. The existing
`helpers.cloudflare.storages.MediaFileStorage` uses an object prefix of `media/`;
the database stores names relative to that prefix. Avoid double-prefixing keys.
`django-storages` and `boto3` are now pinned and installed. The dedicated
`rehearsal_r2` settings select the private backend with an isolated application
prefix and explicit protected credentials; ordinary settings remain unchanged.
Keep static-file deployment separate from business media.

Preserve the [private-media decision](../adr/2026-09-09-private-business-media-delivery.md):
authorized Workspace routes read private objects with server credentials. Do not
switch borrower or collateral links to public URLs. Disable public bucket/custom
domain and `r2.dev` delivery for this bucket; see
[Cloudflare's public-access controls](https://developers.cloudflare.com/r2/buckets/public-buckets/).
Public logos/avatar behavior must be handled separately when enabling R2, without
making the business bucket public. This plan extends deployment preparation; it
does not change the existing authorization architecture or enable production R2.

## Smallest delivery sequence

1. **Inventory through SSH.** Verify the deployed media backend, resolved root and
   tenant directory layout. Match source database references to regular files
   within the verified root; flag traversal, unexpected symlinks, missing and
   unreadable files. Record relative paths, byte counts and SHA-256 hashes in a
   private manifest. Inventory additional assets separately rather than assuming
   the known photo tables cover the whole media directory. Limit concurrency to
   protect the live server. Reads during live writes are provisional.
2. **Copy and verify.** Use a migration-specific destination prefix, retaining
   installation, source schema and path identity. Never flatten filenames or
   delete source files. Copy through securely configured, bucket-scoped credentials.
   Check destination bytes against the source SHA-256 and size; a successful
   upload or object ETag alone is not the complete integrity proof. A changed
   source file gets a separately identified version, not an overwrite of accepted
   evidence. Retrying an identical file must reuse its verified result.
3. **Attach through the application.** Bind each file by installation, schema,
   source table/primary key and field to the exact imported destination identity.
   Use an auditable, retry-safe command with ordinary import authority and RLS.
   Configure the existing Django storage backend for R2 in the intended target,
   with isolated rehearsal settings. Do not mutate accepted opening documents or
   manufacture loans merely to provide a photo parent.
   Use separate application copies: Party photo removal and document cleanup can
   delete their FileField objects, so these fields must not reference the preserved
   originals or share one mutable object. See the
   [preservation decision](../adr/2026-09-21-legacy-media-preservation-and-application-copies.md).
4. **Verify usability and privacy.** Reconcile references into attached, retained,
   missing, invalid or conflicting outcomes. Check authorized customer/loan/history
   views, anonymous object access, other-Workspace IDs and revoked access. Retain
   byte hashes, attachment receipts and exceptions. Missing files remain visible
   exceptions; never claim a complete media migration from database counts alone.
5. **Finish against the frozen snapshot.** Pre-copy while legacy remains live,
   then reconcile new/changed media against the final database during the planned
   write freeze. Retain a separate recoverable media snapshot and source manifest;
   an evolving working bucket alone is not the backup. Keep Linode files and the
   final database/media backup for recovery until cutover acceptance is complete.

## Association implementation and remaining boundaries

| Source | Destination and implementation boundary |
| --- | --- |
| `contact.CustomerPic.image` | Implemented through deterministic imported Party identity: all verified images become unverified documents, and source defaults alone select separate profile copies. |
| `contact.Proof.doc` | Map to the correct Party document/identifier where supported; preserve source verification claims distinctly from new verification. This snapshot has no proof rows, but the final snapshot may differ. |
| Active `girvi.LoanItem.pic` | Implemented through exact opening/item source references and verified bytes. Legacy provenance and unknown capture date are explicit; confirmed blank source images are labelled. |
| Closed-loan item photos | Implemented with immutable Workspace-owned attachments and private archive delivery. Accepted archive JSON is unchanged; forced RLS and parent isolation are tested. |
| Other filesystem assets | Inventory and retain separately; resolve logos, account pictures and unreferenced files explicitly. Do not discard them or attach by filename/name similarity. |

The database replay does not perform these associations; the separate rehearsal
`linode_media` command plans and admits them through domain services. This remains a
bounded legacy migration, not a new general synchronization framework or migration
UI project.

## Known discovery evidence

The September 21 dump contains 31,838 photo references: 1,153 customer photos and
30,685 loan-item pictures. The inventory is private under
`outputs/linode-media-inventory-20260921/`. It records reference paths, not verified
file existence or bytes. There are 5,180 relative paths occurring in more than one
source schema; schema-aware resolution is mandatory. Extract customer default flags
from the source as part of preparation; the initial reference JSONL omits them.

The accepted rehearsal now has database reconciliation and media
copy/association/privacy evidence. Production cutover remains pending. Twelve
confirmed source hashes account for 24,946 blank references, including 5,283 active
collateral images; these must not be counted as usable photographs.

## Live inventory result

Private evidence is in `outputs/linode-media-live-20260921/`, including a readable
`review.html` and checksummed manifests. All 31,405 files in the three branch trees
hashed successfully (589,157,649 bytes). Exact branch paths match 28,224 discovery
references; 3,614 are absent (JCL 3,159; JSK 455; Lakshmi zero). These include
102 operational-loan photos, 3,507 historical photos and five customer photos.

Older shared `customer_pics/` and `loan_pics/` folders contain 3,324 files and
1,149 exact-path candidates for the missing JCL references. Candidates include
23 operational photos, 1,121 closed-loan photos and five customer photos. Their
tenant association remains unproved. Another 2,465 references have no exact path
in the checked locations; recovery must inspect relevant backups or retain an
explicit missing-file exception. Do not search unrelated tenant directories and
guess matches. Neither candidate presence nor a matching filename certifies identity.

The 3,181 branch files absent from the discovery reference list include other
asset types and possibly newly added or older files; retain them pending source
classification. Reads were stable per file, not a globally frozen snapshot.
The live source can change between inventory and copy: revalidate hashes before
copying and reconcile again at final freeze. This inventory preceded the completed
rehearsal attachment described above.
