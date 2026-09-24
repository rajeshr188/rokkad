---
status: active
owner: project
updated: 2026-09-24
tags: [migration, cutover, deployment, linode, r2]
---

# Three-branch production cutover

The owner selected a **separate Linode server** on September 22 and subsequently
created it for hosted cutover rehearsal on September 23. Keep the existing `rokkad.com`
application live during preparation. Build
the current RLS application on the new server with a separate PostgreSQL database
and private R2 application prefix. Never upgrade the old tenant database in place
or promote the September 21 browser rehearsal to production.

The accepted rehearsal proves conversion of its snapshot. It does not include
customers, loans, payments, releases or media added afterwards. The final cutover
imports one complete frozen snapshot for JCL, JSK and Lakshmi together.

## September 24 release requirements

The [consolidated candidate](release-candidate-20260924.md) now has committed source
and a clean versioned image, with fresh/restored migration and restricted-runtime
checks. Its security scan flags 11 dependencies; review and resolve those findings
before promotion. This candidate has not replaced the running rehearsal image or
changed production routing. Use the linked report for exact image identity and
remaining gates.

Preference-library retirement and the simplified loan number/date UI were verified
in `rokkad:rehearsal-prefs-retired-20260924`. Final production must
build from the reviewed current code and requirements, including migration
`configuration.0003_retain_legacy_preference_data`, through the owner-only settings.
Do not install the retired preference packages or delete their retained tables.
Fresh and populated-upgrade paths were verified on the rehearsal host. This does
not replace final runtime-role/RLS, staff journey, recovery or source reconciliation
checks. Use a reviewed committed source and clean build with the security gate
cleared; rehearsal patch images are verification artifacts, not the final release
procedure.
See [current status](../STATUS.md) for later evidence superseding the older planning
checkpoint below.

Customer Workspace creation also prepares the four standard loan-product drafts
automatically. For existing/import-created active Workspaces, run
`python manage.py seed_default_loan_products --workspace-id ID` with the restricted
runtime settings once per intended Workspace. This idempotent preparation preserves
existing terms/statuses and never enables products. The owner/setup administrator
must review and enable the products offered for new lending. Do not infer new-lending
approval from imported product references. See the
[product preparation decision](../adr/2026-09-24-automatic-draft-loan-products.md).

Include subscription migrations `0010_workspaceaccessdecision` and
`0011_access_decision_evidence_guard` through the owner-only migration settings.
Keep `BILLING_CHECKOUT_ENABLED=False` until Razorpay provider acceptance. Commercial
expiry now allows seven days of normal access before read-only access; it does not
suspend the Workspace. Before opening production, explicitly review every intended
Workspace's subscription, entitlements and effective activity mode. While payments
are unfinished, use the audited platform access command/form for a dated normal
access extension and record the reason. Choose production dates and actual target
Workspace/platform-actor IDs at cutover; do not blindly copy rehearsal grants.
Grants never bypass lifecycle or staff permissions and do not create paid evidence.
Verify owner/staff reads, forbidden writes, saved PDF retrieval, exports and extension
expiry/revocation under the runtime role. See the
[subscription operator guide](../domain/subscriptions.md).

The access migration is additive. For a rehearsal application rollback, restore the
prior compose image and retain the new evidence table/migrations; do not reverse
the migration and discard audited decisions. An old image does not enforce the new
continuity policy, so confirm usable subscriptions before reopening on that image.

## Readiness before scheduling downtime

The owner requested cutover planning on September 23 after the ticket designer
merge and JSK stationery correction. The implementation checkpoint is `f2c6014d`
on `rls-mvp`, committed locally but not pushed at this review. Tracked files are
clean; private local outputs and scratch files are deliberately untracked.
The accepted ticket layouts are database configuration, not Git contents. Use the
final hosted bundle described below, including the rupee, amount-in-words and
optional-borrower-photo fixes. Older local exports are superseded. TEST-series
assignments, licences, customers, loans and issued sample PDFs are rehearsal only.

The pre-cutover UX work covers desktop, tablet/phone and English/Hindi. The owner
accepted the JCL customer-to-full-release journey and ticket previews, but that
does not establish acceptance of imported-loan servicing or every device/language.
Finish a bounded review of daily branch tasks, payment receipts and release memos;
do not reopen the document architecture or add unrelated designer features.
Physical printing was explicitly waived as a ticket merge prerequisite and must
not be reintroduced as an approval gate. Record its alignment as untested.

| Work | Current evidence / remaining action |
| --- | --- |
| Destination server | Created: Ubuntu 26.04, approximately 4 GiB RAM, Docker/Compose and verified SSH access. Release a9f793fc serves rehearsal.rokkad.com over HTTPS. PostgreSQL 16.15 schema, runtime/RLS checks, isolated R2 probes and local schema-stage restore passed. New source data, durable credentials and off-server recovery remain pending. |
| Database conversion | Accepted snapshot and separate clean-target replay reconcile all source loan IDs. Fresh data and a later opening date require new preparation. |
| Media | Rehearsal attachment, source retention, private access and duplicate-free retry verified. Missing and blank source images remain explicitly reported. |
| Imported-loan servicing | Dedicated imported interest-only/partial-principal collection, coupled reversal and payment-aware export/restore are implemented. Owner completed and accepted the practice run on September 23. Reduced-principal interest starts at the next original charge boundary. Destination-host smoke checks remain part of deployment. |
| Documents and branch UX | JCL plain-paper and JSK data-only ticket previews accepted; TEST-series activation/reprints verified. Finish payment receipt/release memo and essential staff/device/language checks. |
| Production media configuration | `prod_r2` is implemented and settings-tested; deployment and authenticated storage tests on the new host are pending. |
| Media reliability | Local R2 reads have intermittently timed out or made photos unavailable; successful retries are not a resolution. Verify upload/read/print reliability from the destination host before opening. |
| Production media admission | Implemented exact manifest/checksum binding for database/server/runtime role, private R2 location, source snapshot and Workspace IDs/slugs. Local rejection and attachment/retry tests pass. Actual target manifest and hosted execution await the new server and durable credentials. |
| Application release | Build a versioned image from a clean committed checkout, review security patch levels, apply migrations and run deployment checks. Do not include unrelated local changes or private output files. |
| Access and lending | Configure actual owners/staff, Memberships, lifecycle/subscriptions, current licences, products, series, rates/policies and document numbering through normal services. Imported licences/products are historical references, not new-lending setup. |
| Recovery | Capture and test restoration of the destination database and media evidence; retain the old application, database and media. Record backup locations privately. |
| Timing | Local database-only cold admission took 6,059 seconds (~101 minutes). Measure preparation, database import, media and verification on the new host before choosing the window. |

Required branch journeys are ordinary login and Workspace isolation, borrower
search, a new-loan workflow with current setup, imported balance/interest display,
full release and supported reversal, printing and private media. Rehearse financial
writes in a disposable target, not as throwaway transactions in the final business
database. Use the dedicated opening-aware repayment path through Record payment;
generic event writing and unsupported native servicing remain guarded.

### Imported collections: implementation and rehearsal scope

On September 23 the owner confirmed that branches need both interest-only and
partial-principal collections on migrated loans. The owner then confirmed for
JCL, JSK and Lakshmi: **charge on the reduced principal from the next monthly
anniversary**. Preserve interest already earned for the current monthly period;
do not prorate from the payment date or shift the loan's original anniversary.
For example, for a loan with anniversaries on the 15th, a principal repayment on
September 23 reduces the base for the charge following the October 15 anniversary
(October 16 under the preserved inclusive calendar). Interest-only payment does
not change that principal base. The new `opening-payments/1` continuation extends
the unchanged-principal rule through dedicated repayment/release services.

The implemented boundary and acceptance coverage are:

- Preview and record interest-only and partial-principal payments with the
  confirmed interest rule, preserving original dates, upfront coverage and opening
  debt. Reconcile cash allocation, per-item principal and remaining obligations;
  handle interest beyond the original schedule explicitly.
- Couple any required interest catch-up with the payment in one authorized,
  Workspace-scoped, locked and idempotent transaction. Do not merely remove
  `assert_pawn_loan_financial_actions_allowed` or expose the internal event writer.
- Reuse the existing fee/interest-before-principal allocation and highest-rate-item
  principal allocation where compatible. Show the allocation before submission.
  Resolve the exact anniversary-day and month-end boundaries in executable tests:
  the payment must not retrospectively lower a charge already due that day.
- Make balances, interest explanations, receipts, subsequent full release and
  newest-first reversal agree, including same-day retry and reversal cases.
  Payment alone must not return collateral or claim physical closure.
- Preserve immutable repayment allocation evidence through export and restore.
  Payment-bearing histories use the version 2 export contract, including repayment
  allocation lines. Histories without payments retain the unchanged v1 contract.
- Test opening principal/interest/fees, month boundaries, cumulative rounding,
  item allocations, repeated collections, release after payments, reversal,
  transaction rollback, role permissions, cross-Workspace denial and export/restore.

The existing 43 opening continuation/release/obligation/event-storage and deployment
tests passed on September 23 in the isolated ticket test database. This proves the
existing bounded paths, not the new payment requirement. New payment regression
evidence is recorded in [Status](../STATUS.md). The generic guard remains intact;
no rehearsal or production financial records were changed by implementation.

### Accepted template transfer bundle

The owner explicitly requires JCL and JSK printing to work at cutover without
rebuilding templates or manually selecting a paper profile. The final bundle is
`outputs/server-rehearsal-20260923/cutover-templates-final-20260923/`, also retained
on the rehearsal host under `/home/rokkad/deploy/rehearsal/` with the same directory
name. It supersedes `outputs/production-readiness-20260923/templates/`.

It contains layout ZIPs, paper-profile JSON and a SHA-256 manifest. Sources are
hosted JCL revision 7/profile 2 and JSK revision 4/profile 3. Included changes:
JCL amount-in-words auto-fit; rupee principal formatting; optional absent borrower
photos; JCL plain A4 side-by-side with four background assets; JSK preprinted A5
original/duplicate with business name/address omitted. Existing front-pair
profiles remain; reverse artwork does not automatically enable reverse printing.
No customers, loans, licences, issued PDFs or destination assignment IDs are in
the layout packs. Source revision IDs in the manifest are provenance only.

The installer is `scripts/install_cutover_ticket_templates.py`. Build the final
application from the checkout containing this script and `INR_SYMBOL` support;
baseline `a9f793fc` alone cannot load the updated layouts. Keep the bundle private.
Run with the production **restricted runtime settings/role**, after destination
Workspace/series import and before reopening. No schema migration is required.

Prepare a private `template-target.json` with the exact destination values:
`manifest_sha256` (hash of manifest.json bytes), `database`, `database_host`,
`runtime_role`, `media_location` (the private production storage location),
`rehearsal: false`, and `workspaces` containing `jcl` and `jsk`, each with verified
destination `id` and `slug`. Do not copy the bundled rehearsal target values.

```sh
python scripts/install_cutover_ticket_templates.py \
  --bundle /private/cutover-templates-final-20260923 \
  --target /private/template-target.json
```

The installer verifies target bindings and source checksums, imports/reuses
matching revisions via ordinary services, then publishes/assigns layout **and
paper profile together as each Workspace's default**. Existing/future series
inherit the pair. Every existing series is checked for conflicting overrides;
failure means review the override, not silently overwrite it. Each Workspace is
atomic; rerunning reuses configuration and assignments. On rehearsal this passed
for all eight JCL and three JSK series. Retry created no duplicate configuration;
wrong database, storage, manifest and deployment-mode bindings were rejected.

Before opening, verify default-profile previews (no manual `profile` query) and
one representative eligible loan per branch. JCL's real licence must have the
owner-confirmed printed business name/address/contact; actual validity/evidence
must be configured normally. JSK requires its preprinted stationery. Neither a
template assignment nor synthetic evidence authorizes production lending.
Do not promote practice loans/licences. Physical alignment remains a separately
recorded check, not a reinstated approval gate. Existing issued PDFs stay intact.

### Opening-date boundary

Current opening servicing rejects an action dated on or before the opening date.
Plan an overnight freeze after close of business on date D, a reviewed opening
through D, and reopening no earlier than D+1 in the application timezone. The
measured duration may require a longer window. Do not promise same-day servicing
or backdate balances to bypass this rule; same-day opening support would need a
separate explicit design and verification.

## New-server configuration

Use the existing versioned-image `docker-compose.production.yml`. Select the R2
settings in the Compose interpolation environment (not only inside its service
`env_file`):

```text
ROKKAD_IMAGE=<registry>/<image>@sha256:<verified-image-digest>
ROKKAD_PRODUCTION_SETTINGS=django_project.settings.prod_r2
```

The protected `.env.production.runtime` supplies the existing explicit runtime DB,
Django/email settings and these media values. The account endpoint and bucket below
are the owner's approved destination; access credentials must be separately issued
for production and stored privately on the new server.

```text
CLOUDFLARE_R2_BUCKET=rokkad-production-media
CLOUDFLARE_R2_BUCKET_ENDPOINT=https://a4ef4693882baea8a69ab098ad167eef.r2.cloudflarestorage.com
CLOUDFLARE_R2_ACCESS_KEY=<production-runtime-access-key>
CLOUDFLARE_R2_SECRET_KEY=<production-runtime-secret>
ROKKAD_PRODUCTION_MEDIA_LOCATION=media/application/production/linode-rls
ROKKAD_TRUST_HTTPS_PROXY=True
```

`linode-rls` is the proposed stable deployment identity. Confirm it in the target
manifest before any copy. Keep it across application releases. Production copies
must be created under this prefix; changing a setting does not move rehearsal
objects. The migration token expires after one week and is not the runtime token.
Preservation and rehearsal prefixes remain separate. Prefix separation is an
application convention, not a claim of provider-enforced credential isolation.
Retain an independent recoverable backup of originals and manifests.

Only set proxy trust after verifying the HTTPS proxy overwrites the forwarded
scheme header and clients cannot reach the application port directly. Compose
binds that port to loopback. Test HTTPS redirects, login/CSRF and secure cookies at
the real hostname. Do not publish a broad `/media/` alias, public R2 endpoint or
cache private responses. Business files retain authorized application routes.
Check branding/avatar rendering separately; this configuration enables no public
bucket. Static files remain on the existing WhiteNoise backend and need
`collectstatic` in the deployed static volume.

The separate migration service uses `.env.production.migration` and the owner-only
settings. Web, monitoring and importer processes use the restricted runtime role.
Provision explicit target-database grants and verify forced RLS. Start workers only
for explicitly selected Workspaces; do not enable notifications during rehearsal.

Configuration follows the existing private-media decision and the documented
[S3 storage options](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html).
Proxy trust requires the conditions in
[Django's HTTPS proxy documentation](https://docs.djangoproject.com/en/6.0/ref/settings/#secure-proxy-ssl-header).

## Final cutover sequence

1. **Agree the window and fallback deadline.** Measure a full new-server rehearsal
   first. Tell all three branches when entries stop and which URL to use after
   reopening. Record the responsible operator, target identity, release digest,
   source namespace and final opening date/time zone (Asia/Kolkata). Prepare the
   destination hostname/TLS and routing change in advance without moving users.
2. **Stop every legacy business writer.** Put all old entry points into maintenance
   mode, including direct-origin access; stop scheduled jobs, workers, admin/API
   entry and integrations that can write. Let in-flight work finish and verify
   writers have stopped. A banner or DNS change alone is not a write freeze.
   Keep destination business access closed as well.
3. **Capture the final source.** Take a complete PostgreSQL custom-format dump and
   a corresponding media snapshot/manifest while writes remain stopped. Record
   hashes, times and source commit. Retain recoverable copies; validate archive
   readability and media bytes. Do not restore the old dump into the new RLS DB.
4. **Prepare the changed data.** Compare with the accepted package using
   `linode_migration check-source`, then regenerate reviewed Party, opening and
   closed-history inputs for the final archive and opening date. Reuse only
   decisions whose exact supporting evidence still matches. Recalculate opening
   interest through the selected boundary; do not reuse September 21 balances or
   discard newly recorded payments/releases under earlier blanket assumptions.
   Resolve new holds before admission. A changed checksum/date invalidates reuse
   of the old accepted package even when most records look identical.
5. **Import into the clean production target.** Apply the frozen package through
   `linode_migration replay`, with exact target database, actor and Workspace map.
   Preserve immutable receipts; resume interrupted runs only with identical
   accepted inputs. Copy/hash-verify final new or changed media, generate a plan
   bound to these imported identities and attach separate application copies.
   Known blank/missing files remain exceptions, not fabricated photographs.
6. **Reconcile before opening.** Run `linode_migration verify` and media verification.
   Account for every source loan once; reconcile borrowers, active/closed/excluded
   counts, principal, interest, fees, releases, collateral, next interest dates and
   source identities per branch. Check private files, cross-Workspace denial,
   media hashes, final backups, owner access and normal page/print journeys.
   The owner accepts this final report, not just the earlier rehearsal.
   Then complete [license continuation](../flows/legacy-license-continuation.md)
   for each matching legal license: current document/dates, final dump SHA-256 and
   reviewed loan/release high-water counters including closed/excluded records.
   Check next-number previews, remaining ceilings, active products and policies.
   Rehearse new draft/approval/disbursal in an isolated copy; do not insert a fake
   acceptance loan into the production target. Verification preserves old loan
   evidence and series IDs. Keep business access closed until these checks pass.
7. **Switch users, then enable new-system writes.** Route the agreed production
   hostname to the new server. Keep the old origin in maintenance/read-only mode
   throughout DNS propagation so old and new URLs cannot both accept entries.
   Validate external HTTPS/login and all branch links; require a fresh login.
   Record the exact time business writes open and start only approved workers and
   integrations. Observe the first real entries, collections/releases and uploads.
8. **Retain recovery and close temporary access.** Keep the old database/media and
   accepted snapshots for the agreed retention period. Verify scheduled destination
   backups and alerts. Revoke the temporary migration token/SSH key after copy and
   acceptance are complete; retain the separately managed runtime credential.

The data import is not an ongoing two-way sync. If preparation or verification
misses the window, use the fallback below rather than reopening both systems.

## Fallback boundary

**Before any new-system business write:** keep the new target closed, route users
back to the unchanged old application, verify routing, then deliberately reopen
legacy writes. Record that the target/package is superseded. The next attempt
requires a new frozen snapshot; never overlay it on an abandoned serviced target.

**After new-system business writes:** freeze new writes and preserve both systems'
evidence. Prefer repairing the new deployment. Returning to the old application
requires explicit reconciliation and controlled transfer of every new transaction;
switching DNS back alone would lose those business events. Never delete posted
target records to simulate rollback.

## Immediate next action

### Hosted rehearsal deployment

The dedicated host serves `https://rehearsal.rokkad.com`; the owner manages DNS
through Linode, not Cloudflare. Only the new subdomain was added. Caddy supplies
HTTPS and static files; the application is bound to `127.0.0.1:8000`, and PostgreSQL
is accessible only through the `rokkad-rehearsal` Docker network. The live production
hostname/source is unchanged. TCP 80 and 443 are reachable; SSH remains the
operator access path.

Host configuration lives in `/home/rokkad/deploy/rehearsal/`:

- `web-compose.yml` runs the pinned application image `rokkad:a9f793fc` and Caddy
  image digest `sha256:0c994536bddb66445885237f1a5dcc1916bccea922661c76b4e9fc24061f9b52`.
- `hosted_rehearsal.py` extends `prod_r2`, checks the exact rehearsal database/media
  prefix, enables the existing banner, isolates secure cookies and disables outgoing
  email via the in-memory backend. This is a read-only deployment mount, not a change
  to the application image. Use exact `prod_r2` for target-bound media command
  admission when appropriate; the existing command deliberately checks that module.
- `.env.runtime` and `.env.migration` remain separate mode-0600 files. The runtime
  file has no migration-owner password. The explicitly approved temporary R2 token
  is for this rehearsal only; replace it before production.
- `Caddyfile` overwrites forwarded protocol, serves only collected static files,
  and rejects raw `/media/` paths. HTTPS uses one-hour HSTS without subdomain/preload
  scope. Public bucket/custom-domain privacy remains a separate acceptance check.
- `admin-login.json` contains the generated rehearsal administrator password. Read
  it privately over SSH; never include it in logs, Git or chat. Placeholder email is
  not verified ownership of a mailbox.
- `backups/` retains a checksummed schema-stage dump; its separate restored check
  database is `rokkad_restore_check_20260923`. This is a local recovery check, not an
  off-server backup strategy. Re-test recovery after real rehearsal data is loaded.

Operator commands from that directory:

```bash
sudo docker compose -f web-compose.yml ps
sudo docker compose -f web-compose.yml logs --tail 80 web proxy
sudo docker compose -f web-compose.yml exec web python manage.py check --deploy --database default
```

The owner supplied `C:\Users\rajes\backup_20260923_115257.sql`, SHA-256
`3be7cedd0eaf0556b8aa1c70b5c843b6b8c7d3c016665a783243eb663ca44a21`.
Its private host copy is `source/backup_20260923_115257.sql` in the deployment
directory. Scoped offline preparation is retained in
`outputs/hosted-source-20260923/`; subsequent owner answers and disjoint source
classification are separately sealed in `outputs/hosted-owner-decisions-20260923/`.
Use those explicit source-ID decisions for the two outstanding inactive-borrower
exceptions, two newly cancelled records and duplicate-entry principal correction;
see Status. The current classification has 6,368 outstanding loans, 39,162
closed-history records and three unused/cancelled records. That source review
preceded the completed admission described below. Preserve original source facts
and use the recalculated September 23 openings
through existing financial services. Do not reuse September 21 balances/package
or turn a duplicate correction into an invented payment. No source freeze or
production routing change is authorized by this rehearsal preparation.

The owner subsequently authorized admission. The newly prepared package is
`outputs/hosted-reviewed-package-20260923/`, SHA-256
`cfc13d37d6eb5d052c7f6b9e1e509fa215a83a857a30390eefb66e5bf734a80b`.
It records offline preparation explicitly; it is not labelled a capture of an
already accepted database. The ordinary destination previews and commits remain
mandatory. Hosted Workspace IDs are JCL 1, JSK 2 and Lakshmi 3, under
`hosted-import-owner` Owner Memberships, with Admin Memberships for
`rehearsal-admin`. All DML runs under the restricted runtime role.

The import completed in `rokkad-reviewed-import-20260923` using the deployed release
plus PostgreSQL client tools. Operator files and evidence are under
`~/deploy/rehearsal/import/`; secrets remain in the existing private host settings.
Inspect `docker logs --tail 20 rokkad-reviewed-import-20260923` and
`import/finish.log`. All reconciliation, 19 rolled-back servicing samples,
29 real HTTPS page checks and post-import backup recovery passed. The isolated
render container initially needed the existing collected-static volume mounted;
that verification-only issue is resolved. Never reset or merge another source
package into these Workspaces. `run/completion-manifest.json` is written only after
all queued checks pass; its SHA-256 is
`0a470b7e15b676785d7f4b577ebd3ba81759694337d47268c468e03f56dcad0e`.
The complete private reports are also retained locally under
`outputs/server-rehearsal-20260923/import-results/run/`. Admission/reconciliation
took 99.2 minutes, excluding offline preparation and media. Recovery restored the
49,909,423-byte backup into `rokkad_import_restore_20260923`, retaining both copies;
all 160 table content hashes and runtime/RLS/migration checks matched.
Opening balances are dated September 23; payment/release practice starts September
24 under the current servicing contract. Preserve verification before practice.

### Remaining cutover work

The owner has completed and accepted the imported-payment practice run. Move to
production media admission, essential UI/printing checks, destination provisioning
and recovery using this single readiness checklist. Do not repeat the accepted
collection exercise as a new approval gate.

The production media admission command now implements the exact target contract;
see the [manifest and operator steps](linode-media-attachments.md#production-target-binding).
It retains rehearsal behavior and refuses mismatched targets before copying.
Prepare the real manifest only after the separate server/database, Workspaces and
durable credentials are configured. The server, HTTPS and rehearsal schema are now
prepared, and isolated R2 probes passed using the approved temporary token.
Workspaces and the supplied database snapshot are now imported and verified.
Hosted media now has 28,347 verified attachments, including 55 freshly copied
originals. All 3,614 remaining exact branch paths were rechecked and remain
missing: 2,465 have no preserved candidate and 1,149 have unverified shared
candidates (1,144 known blank images and five customer photographs). Carry this
exception list into final-source review; never attach candidates by filename
alone or claim all photos were recovered. Final frozen media capture/reconciliation
remains pending. The approved/active loan-details print shortcut is deployed to
rehearsal; include `templates/loans/pawn/detail.html` in the final release along
with INR_SYMBOL support and the corrected default template packs.
Storage probes do not establish
complete external privacy, workload reliability or production cutover readiness.

Resolve required business-flow gaps before choosing a freeze date.
Continue deployment on the separate Linode: the image, HTTPS and restricted RLS
database are prepared. Complete durable application/provider credentials and
off-server backup acceptance while the old system remains live. Do not switch
production routing as part of rehearsal preparation.

The fresh non-frozen September 23 snapshot completed a timed hosted database
rehearsal in 99.2 minutes for admission/reconciliation. Complete and measure media
separately; this is not yet an end-to-end database-plus-media timing. Source activity
continues: rehearsal reports are preparation evidence, not final balances.
Include extraction/preparation, media changes and final validation when agreeing
the all-branch freeze window and fallback deadline,
then follow the final frozen-snapshot sequence above. Never layer that final dump
onto the practice database or assume old decisions about discarded payments apply
to newly recorded transactions.
No freeze date, DNS switch or production financial import has been executed.
