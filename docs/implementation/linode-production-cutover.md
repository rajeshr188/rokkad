---
status: active
owner: project
updated: 2026-09-23
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

The owner requested cutover planning on September 23 after the ticket designer
merge and JSK stationery correction. The implementation checkpoint is `f2c6014d`
on `rls-mvp`, committed locally but not pushed at this review. Tracked files are
clean; private local outputs and scratch files are deliberately untracked.
The accepted ticket layouts are database configuration, not Git contents: export
the current JCL revision 1/profile 1 and corrected JSK revision 4/profile 2 plus
assets through the supported pack/profile workflow for deployment. Do not use
the older JSK recovery pack with duplicated business headings. TEST-series
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
| Destination server | Owner selected separate Linode; creation, SSH address and verified access pending. |
| Database conversion | Accepted snapshot and separate clean-target replay reconcile all source loan IDs. Fresh data and a later opening date require new preparation. |
| Media | Rehearsal attachment, source retention, private access and duplicate-free retry verified. Missing and blank source images remain explicitly reported. |
| Imported-loan servicing | Owner confirmed both interest-only collections and partial principal repayments are required, with reduced-principal interest from the next monthly anniversary. Both remain unsupported for imported openings and are go-live blockers. Implement and test this bounded continuation path. New TEST-loan payment acceptance does not cover imported openings. |
| Documents and branch UX | JCL plain-paper and JSK data-only ticket previews accepted; TEST-series activation/reprints verified. Finish payment receipt/release memo and essential staff/device/language checks. |
| Production media configuration | `prod_r2` is implemented and settings-tested; deployment and authenticated storage tests on the new host are pending. |
| Media reliability | Local R2 reads have intermittently timed out or made photos unavailable; successful retries are not a resolution. Verify upload/read/print reliability from the destination host before opening. |
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

### Imported collections: required next implementation

On September 23 the owner confirmed that branches need both interest-only and
partial-principal collections on migrated loans. The owner then confirmed for
JCL, JSK and Lakshmi: **charge on the reduced principal from the next monthly
anniversary**. Preserve interest already earned for the current monthly period;
do not prorate from the payment date or shift the loan's original anniversary.
For example, for a loan with anniversaries on the 15th, a principal repayment on
September 23 reduces the base for the October 15 charge. Interest-only payment
does not change that principal base. The existing reviewed rule covers unchanged
original principal only, so this confirmed extension still needs implementation;
the owner answer does not make the current payment handler safe to enable.

Keep this work inside the existing collection workflow. Its required boundary is:

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
  The current opening export's frozen row contract does not include repayment
  allocation lines; enabling payments without addressing that would leave
  portability incomplete. Preserve existing export compatibility explicitly.
- Test opening principal/interest/fees, month boundaries, cumulative rounding,
  item allocations, repeated collections, release after payments, reversal,
  transaction rollback, role permissions, cross-Workspace denial and export/restore.

The existing 43 opening continuation/release/obligation/event-storage and deployment
tests passed on September 23 in the isolated ticket test database. This proves the
existing bounded paths, not the new payment requirement; no payment guard has
been relaxed and no rehearsal or production financial records changed.

### Accepted template transfer bundle

Read-only export completed on September 23 under the rehearsal runtime role.
Private local files are in `outputs/production-readiness-20260923/templates/`:
`jcl-layout.zip`, `jcl-profile.json`, `jsk-layout.zip`, `jsk-profile.json` and
`manifest.json`. Layout/profile definitions and each archived asset SHA-256 were
checked against the current published configuration. JCL includes four background
assets; JSK includes none and declares its business name preprinted. The existing
front-pair profiles are retained; included reverse artwork is not automatically
enabled. The manifest records content hashes and source revision provenance.

These bundles contain configuration only, with no customers, loans, licences,
issued documents or assignment rows. Keep them outside Git. Import into the
destination as drafts through the supported layout-pack and profile services,
check hashes/previews, then assign using real destination Workspace/series IDs.
Never reuse rehearsal IDs or activate a TEST-series mapping in production.

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

First implement and rehearse the confirmed imported-payment workflow above,
including reversal and export/restore, while keeping unsupported operations
guarded. Then address production media admission, essential UI/printing checks,
destination provisioning and recovery using this single readiness checklist.
Resolve required business-flow gaps before choosing a freeze date.
Create the separate Linode server when ready for hosted
deployment testing; prepare access, immutable release image, HTTPS, restricted RLS
runtime, durable R2 credentials and verified backups while the old system remains
live. Do not push, purchase infrastructure or switch routing as part of discussion.

Then take a fresh non-frozen snapshot for a timed, disposable end-to-end rehearsal
on that host. Source activity may continue during this rehearsal: its reports are
preparation evidence, not the final balances. Measure extraction/preparation,
database import, media changes and validation together; the old approximately
101-minute database-only local run is not a promised downtime estimate.
Use the measured result to agree the all-branch freeze window and fallback deadline,
then follow the final frozen-snapshot sequence above. Never layer that final dump
onto the practice database or assume old decisions about discarded payments apply
to newly recorded transactions.
No freeze date, DNS switch or production financial import has been executed.
