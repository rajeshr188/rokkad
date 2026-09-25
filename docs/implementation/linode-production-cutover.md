---
status: active
owner: project
updated: 2026-09-25
tags: [migration, cutover, deployment, linode, r2]
---

# Three-branch production cutover

## Current application and recovery checkpoint

As verified on September 25, the application release is `713e0b64`, image
`rokkad:rc-20260925-713e0b64`, with static volume
`rokkad_production_static_713e0b64` and Loans migrations through 0026.
Image ID: `sha256:a045348992a0d1f63fab41ea0634a9afda4de98391078bbe3ebd84ca5ef28792`.
It includes corrected disbursal attempts, Tabs/Classic details, same-day policy
revisions, collateral quantities/authorized overrides, camera selection and
Indian monetary display. Production serves the temporary hostname below.
JSK uses 95% LTV and WH gold/silver rates of 1.1%/3%; JCL/Lakshmi retain 80% LTV.
Previously approved terms and issued PDF bytes are preserved.

Latest deployment evidence: `acceptance-20260925/camera-money-deployment.json`.
Last deployment-verified server-only backup:
`backups/operational/production-20260925T145913Z.dump`, 55,717,830 bytes, SHA-256
`191208efba013f8965bcce9cd29b97277da0e3fce371123542b10a0ccc00a986`.
The hourly timer may create newer backups; inspect its private `latest.json`
before recovery. Detailed rollout evidence is in [Status](../STATUS.md).

## Earlier September 25 deployment checkpoints

The following image, migration, counter and backup values describe those earlier
checks. They are not instructions to revert the current application or reset data.

Earlier application release: `511c7cd8` (corrected disbursal attempts), image
`rokkad:rc-20260925-511c7cd8`, static volume `rokkad_production_static_7dad893a`.
Migrations 0023/0024 retain historical snapshots and backfill current loan links.
The migration settles deferred constraints before Django creates FK indexes;
the populated-upgrade regression covers this requirement. The new server's production web writers were
briefly stopped during migration; the old legacy server was not changed. Candidate/deployed runtime checks passed for
all three branch snapshot links and JSK 06703's INR 7,150 review/detail, without
disbursing it or changing source events. Evidence:
`acceptance-20260925/redisbursement-deployment.json`. Original INR 7,149.95
disbursal and reversal are retained. Once a replacement attempt exists, fix
forward with compatible code; do not restore the former one-to-one schema.
See [the correction workflow](../flows/correct-a-disbursed-loan.md).
Backup at this checkpoint: `backups/operational/production-20260925T082336Z.dump`,
55,646,091 bytes, SHA-256
`ab9de593d9009b5520a8ece05edd4e15254380a6bff6f4c6ee5ebdaa1a727c7d`.

Previous application release: `7dad893a` (paper-closure transition), image
`rokkad:rc-20260925-7dad893a`, static volume `rokkad_production_static_7dad893a`.
Migration 0022 is applied. All three branches remain paper-first; owner controls
system-first date/retirement, with administrator reason-required exceptions.
Candidate/deployed 50-loan previews and entry/guide/history/settings pages passed,
without recording closures or modifying loan/counter/transition rows. Evidence:
`acceptance-20260925/paper-closures-deployment.json`. Backup at this checkpoint:
`backups/operational/production-20260925T074416Z.dump`, 55,620,036 bytes, SHA-256
`320ff354a61974b58639891ba105d3ff2ee8c60c4dc8bfb503abe0178d123987`.
See [the staff workflow](../flows/paper-closure-transition.md). After paper entries
exist, fix forward or use a compatible image; pre-paper code cannot interpret
date-only handovers. Never restore an older production snapshot over new work.

Previous application release: `58858717` (series interest overrides and setup readiness),
image `rokkad:rc-20260925-58858717`, static volume
`rokkad_production_static_26855c3c`. JSK WH policies 9/10 use gold 1.1% and silver
3% monthly from 25/09/2026; every other series retains 2%/4%. Existing financial
rows and numbering are unchanged. Migration 0021 is applied. Verification evidence:
`acceptance-20260925/wh-interest-deployment.json` and
`acceptance-20260925/series-readiness-deployment.json`. Backup at this checkpoint:
`backups/operational/production-20260925T065036Z.dump` (55,610,193 bytes; SHA-256
`81ec712171f3eedcd19009f7474e393d51b664c0d79cf7fe07ca4f5a1f40a3f8`).
Application rollback may use `a8e78108`, which understands series policies.
Older images require disabling active series overrides first; see the series ADR.

Previous application release: `26855c3c` (loan series labels and borrower picker),
image `rokkad:rc-20260925-26855c3c`, static volume
`rokkad_production_static_26855c3c`. JCL C07549 displays Series C; read-only checks
passed for all three branch borrower searches without changing loans or counters.
Evidence: `acceptance-20260925/loan-directory-deployment.json`; backup at this
checkpoint: `backups/operational/production-20260925T061702Z.dump`.

The September 25 photo/date release is `8fa5d273`, image
`rokkad:rc-20260925-8fa5d273`, with static volume
`rokkad_production_static_8fa5d273`. Its additive Party migration preserved all
1,142 current profile references in the private gallery. Candidate and deployed
checks passed for all branches, runtime RLS, private photos, date display, imported
ticket copies and unchanged native reprints. Server evidence is
`acceptance-20260925/party-gallery-deployment.json`; backup at this checkpoint is
`backups/operational/production-20260925T055540Z.dump`. The previous web/static
configuration is saved as `production-compose.before-party-gallery.yml`.

## Current operating decision: temporary production hostname

On September 25 the owner authorized real retained transactions at
`rehearsal.rokkad.com` for one or two days before changing `rokkad.com`. The owner
reconfirmed no old-system changes since the final backup. The temporary hostname
now routes to the configured final production database/image; the old practice
container is stopped, with its data retained. This supersedes the earlier plan to
wait for live-domain DNS before exposing production. Keep old services and both
live-domain DNS records unchanged, and keep branch writes paused there.

New transactions belong to production and must survive the later hostname change.
Do not rerun snapshot import or restore pre-operation backups over this database.
Use production Workspace paths (`jcl`, `jsk`, `lakshmipawnbroker`), not old
`rehearsal-*` bookmarks. The owner-approved temporary Google origin and callback
`https://rehearsal.rokkad.com/accounts/google/login/callback/` are saved, preserving
both live-domain callbacks and the existing secret. Actual Google sign-in completed
and showed all three production Workspaces with Owner access; the original
`redirect_uri_mismatch` is resolved. No business transactions were submitted by
the agent during this verification.

Subsequent approved staff onboarding preserved five exact Google subjects and
enabled the reviewed branch memberships. Shankar now owns Lakshmi; Rajesh retains
Admin access there and ownership of JCL/JSK. JCL Member includes the four approved
daily financial actions for Umesh, and future users of that local role. The second
Lakshmi account remains conditional on actual verified Google sign-in. See
[staff application evidence](../STATUS.md#approved-staff-access-and-lakshmi-ownership-applied-2026-09-25).

`temporary-production.json` is the current routing evidence. The old additive
`Caddyfile.production-candidate` is stale after this decision: regenerate it from
the current proxy when the owner approves the later domain switch. Preserve the
same database/storage/number counters, update allowed hosts/CSRF/Site and OAuth
callbacks, and redirect the temporary hostname after verification. Do not blindly
reload the earlier candidate or reopen the practice container as production.

Hourly server-only database backups are active under `backups/operational` with
an initial archive check. Review capacity/retention and off-server recovery during
the short transition; current copies have no pruning or external failure alerts.
See [current evidence](../STATUS.md#production-on-temporary-hostname-2026-09-25).

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

This section preserves the preparation sequence. The current production hostname,
application and retained-data requirements above supersede pre-activation steps.

The [dependency-refreshed candidate](dependency-refresh-20260924.md) now has committed
source and a clean versioned image, with 1,911 passing regressions, fresh/restored
migration and restricted-runtime checks. Its scan reports no known Python dependency
advisories across 71 checked distributions. It is deployed to rehearsal; production
routing remains unchanged. Use the linked report for exact image identity and the
remaining operator/configuration/recovery and frozen-source cutover requirements.

### September 24 final-source candidate

The complete package is imported and reconciled in `rokkad_production_20260924`,
with media attached and local recovery verified. Subsequent release `d078db38`
supports the owner's explicit document deferral and approved branch lending setup.
See the [current checkpoint](../STATUS.md#approved-lending-setup-applied-to-isolated-production-2026-09-25)
for image identity, settings and remaining cutover work. The source comparison
below records the initial inspection, not the current admission status.

The owner explicitly refused maintenance changes to the old site: leave its
services and configuration unchanged. The reported staff pause remains the freeze
mechanism; any new entries invalidate the final-snapshot assumption. Google client
configuration and the chosen owner's linked subject have been privately transferred
and configured on the isolated target with explicit approval. Interactive owner
sign-in was subsequently verified at the temporary hostname. Temporary R2 credentials are approved for final migration only;
the separately approved durable replacement is now installed and verified in the
production runtime environment. Its bucket-level permissions do not enforce the
application prefix; application configuration and admission target checks bind that
prefix. See [the completed import checkpoint](../STATUS.md#final-import-media-and-local-recovery-verified-2026-09-25)
for source-media attachment and recovery. No DNS
switch is authorized until final reconciliation is presented and approved.

At the proprietor-header checkpoint the target used image
`rokkad:rc-20260925-e5822c02` and migration `loans.0020_license_proprietor`. The JSK unnamed-series correction preserves
its numeric-only register and continued at 06703 at correction time; WH then
remained WH02145. Preserve subsequent allocations. Its audited
forward-only reservation leaves financial rows and the sealed package intact.
See [numbering evidence](../STATUS.md#jsk-unnamed-series-continuation-corrected-2026-09-25).
The owner explicitly defers original licence
documents until later; all four licences carry audited owner-attested validity
from the continuation date to January 10, 2030. This supersedes the immediate upload
requirement for this approved cutover; it does not claim document verification.
The common JSK policies and owner-provided September 25 prices are installed, and
new-loan approval/ticket/disbursal passed in the restored copy with all test writes
rolled back. Preserve the existing licence/series identities and frozen history.

Private current release/routing records are `production-release.json` and
`temporary-production.json` under `cutover-20260924`. The older
`routing-preparation.json` records pre-activation preparation: its compose binds
production to `127.0.0.1:8001` and uses its own collected static volume. The candidate
Caddyfile retains rehearsal and adds production/WWW routes; it has not been loaded.
Both production hostnames currently resolve to the old IPv4 and IPv6 addresses.
An approved IPv4 switch must remove/update the old AAAA records as well. Verify
HTTPS and actual Google callback for the later live-domain switch. Branch writes
are already authorized on the retained temporary-hostname production database.
Same-day metal quotes must be refreshed on later dates before new-loan approval; never relabel
the owner's September 25 references as current future-day quotes.

The owner supplied the custom archive `C:\Users\rajes\backup_20260924_230136.sql`
(11,711,243 bytes; SHA-256
`e2c91ded1d56b6391c0a9dc9c72f0392238490c654612ba477a8e002d5de09e6`) and confirmed
all three branches stopped writes after it. Treat this as the proposed final
source, pending verification of all technical writers and matching media. This
confirmation does not itself authorize a DNS switch or reopen destination writes.

Read-only comparison against accepted package `cfc13d37d6eb5d052c7f6b9e1e509fa215a83a857a30390eefb66e5bf734a80b`
found 35/18/23 added loans for JCL/JSK/Lakshmi, respectively. JSK adds 29 payments
and 29 releases; Lakshmi adds 24 of each. Thirty existing JSK loans, 24 Lakshmi
loans and two Lakshmi addresses changed; inspected tables have no removed rows.
These are raw source counts, not approved classifications. The old package is
not reusable for admission. Regenerate and review the complete package, including
changed payment/release facts and the proposed September 24 opening boundary;
current servicing can begin only on a later local calendar date. Confirm the
final boundary in the accepted report before admission. Reconcile final media
separately. No import or production routing change occurred in this inspection.

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

This is the September 24 pre-activation readiness assessment, retained for its
evidence and remaining recovery/UX limits. The current release and operating
decision at the top supersede its unfinished import/authentication/setup tasks.

The owner requested cutover planning on September 23 after the ticket designer
merge and JSK stationery correction. The rehearsal image assessed here was the verified
`rokkad:rc-20260924-fd011920` on `release/2026-09-24-rc1`; this supersedes the earlier
`f2c6014d` planning checkpoint. See the
[September 24 operational acceptance](rehearsal-acceptance-20260924.md) for current
recovery/workflow evidence and remaining configuration findings.
The accepted ticket layouts are database configuration, not Git contents. Use the
final hosted bundle described below, including the rupee, amount-in-words and
optional-borrower-photo fixes. Older local exports are superseded. TEST-series
assignments, licences, customers, loans and issued sample PDFs are rehearsal only.

The pre-cutover UX work covers desktop, tablet/phone and English/Hindi. The owner
accepted the JCL customer-to-full-release journey, ticket previews and imported
payment practice. The latest restored-copy servicing and staff probes also pass,
but do not establish every operator/device/language journey. Finish a bounded
visual review of payment receipts/release memos and the remaining Hindi labels;
do not reopen the document architecture or add unrelated designer features.
Physical printing was explicitly waived as a ticket merge prerequisite and must
not be reintroduced as an approval gate. Record its alignment as untested.

| Work | Evidence / remaining action at the September 24 checkpoint |
| --- | --- |
| Destination server | Ubuntu 26.04, approximately 4 GiB RAM; candidate `fd011920` serves rehearsal.rokkad.com over HTTPS. PostgreSQL runtime/RLS and latest-backup restore checks pass. Web is loopback-only; database has no published host port. Cloud firewall source restrictions still need direct review. |
| Database conversion | Accepted snapshot and separate clean-target replay reconcile all source loan IDs. Fresh data and a later opening date require new preparation. |
| Media | Rehearsal attachment, source retention, private access and duplicate-free retry verified. Missing and blank source images remain explicitly reported. |
| Imported-loan servicing | Owner accepted practice September 23. Destination admission checked 19 samples; September 24 restored-copy payment, receipt, release, memo, retry and newest-first reversal passed in all three branches. Reduced-principal interest starts at the next original charge boundary. |
| Documents and branch UX | JCL plain-paper and JSK data-only tickets accepted. Latest image passed 36 reader/editor/collector page checks, borrower filtering and phone/tablet ticket/date display. Receipt/memo PDF responses pass; visual approval and incomplete recent Hindi labels remain. |
| Production media configuration | `prod_r2`, private-prefix writes/reads and authenticated storage are verified on the new rehearsal host. Final production needs its separately reviewed durable credentials and deployment identity. |
| Media reliability | Hosted private read/upload and saved PDF checksum probes pass; earlier local timeouts are retained as history. Verify the final production prefix and representative reads/prints before reopening; rehearsal success is not final-target admission. |
| Production media admission | Hosted source-bound media attachment and duplicate-free retry completed September 23. Exact database/server/runtime-role/storage/source/Workspace bindings must be rebuilt and checked for the final frozen snapshot and fresh production target. |
| Application release | Clean versioned candidate `fd011920` deployed; 1,911 regressions pass; 71 Python distributions checked with zero known advisories or skips. Authentication/proxy configuration findings in the acceptance report must be resolved before promotion. |
| Access and lending | Configure actual owners/staff, Memberships, lifecycle/subscriptions, current licences, products, series, rates/policies and document numbering through normal services. Imported licences/products are historical references, not new-lending setup. |
| Recovery | Latest backup restored on-host in 38.98 seconds including 117-table comparison. Backups remain server-only as instructed; server-loss recovery destination/retention is not yet accepted. Retain old application/database/media and private evidence locations. |
| Timing | Hosted admission took 5,857.4 seconds plus 92.0 seconds reconciliation (~99.2 minutes), excluding preparation/media/smoke/recovery. Hosted media increment planning/apply took 208.94/1,883.56 seconds; these are separate samples, not a complete downtime estimate. Budget the full frozen-source workflow before choosing the window. |

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
ROKKAD_AUTH_TRUSTED_PROXY_COUNT=1
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
2. **Maintain the agreed legacy write pause.** For this cutover the owner explicitly
   requires no changes to the old site, services or configuration. Staff have
   reported stopping entries; record that this is operational coordination, not
   technical enforcement. Recheck for source changes before final approval; any
   later writes require renewed source preparation. Technical maintenance of old
   entry points would require a changed owner instruction. Keep destination
   business access closed during preparation.
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
   hostname to the new server only after final approval. Under the current owner
   instruction the old origin remains unchanged and can still accept entries;
   coordinate the staff pause throughout DNS propagation and explicitly verify
   staff use the new origin before reopening. Do not claim a technical writer
   freeze or silently install maintenance mode on the old server.
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
