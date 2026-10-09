---
status: accepted
owner: operations
updated: 2026-10-10
tags: [backups, recovery, storage, rls]
---

# Independent encrypted database recovery

The owner selects BS-03/04 and a password manager plus an offline recovery copy
for the private decryption key. Current hourly full PostgreSQL dumps are validated
but remain on the same host as the live database. A managed PostgreSQL evaluation
is separate from this recovery work; no live database migration is selected.

Use a dedicated private R2 bucket, `rokkad-production-backups`, outside application
media. A host-only operator uses dedicated bucket-scoped credentials, never web
credentials. It reuses completed dump/checksum/catalogue evidence, encrypts with
the established age tool using only a public recipient, uploads a unique artifact
and encrypted recovery metadata, downloads and verifies ciphertext bytes, then
publishes a completed marker. Do not implement custom cryptography or a generic
backup framework. Existing app models, financial evidence and RLS are unchanged.

The private age identity belongs in the owner's password manager and offline
copy. The hourly uploader needs no private key. Actual recovery may use the
identity temporarily in an operator-controlled isolated environment; never put
it in the app, backup bucket, Git, logs or persistent hourly server configuration.
Key creation is not proof that both recovery copies have been saved.

No upload failure or incomplete marker permits local expiry. Keep current local
retention while proving remote upload and actual restore. Remote retention remains
the newest 24 completed hourly copies plus the latest completed copy per UTC day
over 30 days. Keep release checkpoints separately protected. Six recent local
copies may be activated only after actual restore and owner custody/retention
acceptance; code availability or a successful upload does not satisfy that gate.

After actual restore/image acceptance and owner custody confirmation, select six
recent local snapshots **plus all older snapshots without matching retained remote
coverage**. This protects pre-R2 points during transition. Never delete an existing
local restore point solely because a different new snapshot uploaded. Release images,
deployment checkpoints, other recipients and orphan objects stay protected. A new
image/key requires renewed compatible recovery acceptance before expiry.

Use an explicit dedicated prefix and authenticated remote completion records.
Missing, corrupt, changed, stale or incompatible evidence fails closed. SHA-256
verification downloads actual bytes; object ETags are not substituted for hashes.
Do not expose a Workspace-facing endpoint or count these operator artifacts in
Workspace storage billing/inventory. One recovery archive contains all Workspaces.

Restore acceptance requires a downloaded and decrypted archive, compatible
owner-only schema setup, restricted runtime startup and adversarial RLS checks,
native balances, source hashes and current closed/held cohorts. Disable outbound
mail and payment effects in the isolated environment. Record operator proofs
without exporting customer rows. Never restore over production or an existing
rehearsal database.

Managed PostgreSQL must separately prove role/grant, forced-RLS, trigger/function,
version, connection, restore and migration compatibility. Buying a managed service
does not replace independent recovery or establish those checks automatically.

References: [ordered plan](../plans/backup-storage-and-evidence-efficiency.md),
[constitution](../constitution.md), [age](https://github.com/FiloSottile/age),
[R2 scoped authentication](https://developers.cloudflare.com/r2/api/tokens/).
