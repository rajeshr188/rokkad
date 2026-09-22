---
status: active
owner: project
updated: 2026-09-22
tags: [migration, cutover, deployment, linode, r2]
---

# Three-branch production cutover

The owner selected a **separate Linode server** on September 22. It has not been
created. Keep the existing `rokkad.com` application live during preparation. Build
the current RLS application on the new server with a separate PostgreSQL database
and private R2 application prefix. Never upgrade the old tenant database in place
or promote the September 21 browser rehearsal to production.

The accepted rehearsal proves conversion of its snapshot. It does not include
customers, loans, payments, releases or media added afterwards. The final cutover
imports one complete frozen snapshot for JCL, JSK and Lakshmi together.

## Readiness before scheduling downtime

The owner added a pre-cutover UX/accessibility/onboarding redesign on September 22,
covering desktop, tablet/phone and English/Hindi. Complete its
[task-based acceptance](../plans/project-wide-ux-revamp.md) before scheduling the
freeze. Local design work does not require buying the production server now.

| Work | Current evidence / remaining action |
| --- | --- |
| Destination server | Owner selected separate Linode; creation, SSH address and verified access pending. |
| Database conversion | Accepted snapshot and separate clean-target replay reconcile all source loan IDs. Fresh data and a later opening date require new preparation. |
| Media | Rehearsal attachment, source retention, private access and duplicate-free retry verified. Missing and blank source images remain explicitly reported. |
| Production media configuration | `prod_r2` is implemented and settings-tested; deployment and authenticated storage tests on the new host are pending. |
| Production media admission | `linode_media` still refuses non-rehearsal databases. Add an exact approved target/storage binding and tests before the final timed rehearsal; never remove its guard ad hoc. |
| Application release | Build a versioned image from a clean committed checkout, review security patch levels, apply migrations and run deployment checks. Do not include unrelated local changes or private output files. |
| Access and lending | Configure actual owners/staff, Memberships, lifecycle/subscriptions, current licences, products, series, rates/policies and document numbering through normal services. Imported licences/products are historical references, not new-lending setup. |
| Recovery | Capture and test restoration of the destination database and media evidence; retain the old application, database and media. Record backup locations privately. |
| Timing | Local database-only cold admission took 6,059 seconds (~101 minutes). Measure preparation, database import, media and verification on the new host before choosing the window. |

Required branch journeys are ordinary login and Workspace isolation, borrower
search, a new-loan workflow with current setup, imported balance/interest display,
full release and supported reversal, printing and private media. Rehearse financial
writes in a disposable target, not as throwaway transactions in the final business
database. Ordinary partial repayments on imported openings remain guarded; go-live
must not imply that this unsupported workflow has become available.

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

Begin the prioritized UX audit and redesign on isolated data. When a hosted review
or deployment rehearsal is needed, create the separate Linode server and provide
its IP/SSH login identity through normal access setup. Provision the clean target
and permanent R2 credentials, finish guarded production media admission, and run a
timed rehearsal on that host after the redesigned workflows are accepted.
No freeze date, DNS switch or production financial import has been executed.
