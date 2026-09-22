---
status: active
owner: project
updated: 2026-09-22
tags: [status, architecture]
---

# Status

## Owner/team setup and shared navigation (2026-09-22)

Business profile, team, invitation and role forms now use responsive grouped
screens with English/Hindi guidance and linked validation errors. Working alone
is explicitly supported; invitations explain their email consequence and show
the existing seat-capacity snapshot correctly. Role changes require an explicit
Save action and validate against the actor's permitted roles. Profile edits now
bind uploaded logos. Existing ownership, permission and audited service rules
remain authoritative. Sensitive management pages use no-store responses.

Shared workspace/account navigation and setup checklist labels are translated.
Stored role names remain unchanged; dynamic setup descriptions and deeper
administration/provider messages still have translation work remaining.

Validation: 195 organization/onboarding tests passed; after browser refinements,
29 owner/team and shared-shell tests passed on a fresh database. Browser review
found and fixed an empty invitation role selector, now covered by a regression
assertion. Local English/Hindi phone/desktop checks covered team, invitations,
business profile/edit and setup guidance without submitting business forms or
sending invitations. English and the normal viewport were restored. Physical
touch, screen-reader checks, real invitation delivery and novice-staff acceptance
remain pending. See the [delivery notes](implementation/accessible-directory-redesign.md).

Next: consolidate staff workflow acceptance on isolated test data, from customer
entry through loan issue, payment and release. Resolve task-blocking findings
before cutover; account/billing/deeper role administration and remaining dynamic
translations are still outside this completed slice. Production cutover has not
occurred.

## Rates and notification screen simplification (2026-09-22)

Rates now groups source/metal, per-gram prices and effective-time evidence in
accessible English/Hindi forms. Quote and source detail explain corrections,
withdrawals, history and tax/valuation boundaries. Rates and notification batches
have searchable 25-row pages, responsive cards and native Django result partials
with progressive HTMX, keyboard result focus and normal GET fallbacks.

Notification review separates recipients/documents, eligible digital sends and
printed/posted records. Actions follow existing permissions; sent/cancelled digital
jobs are excluded from the send count. Setup distinguishes configuration checks
from delivery evidence and uses grouped fields with linked errors. Empty withdrawal
and WhatsApp setup POSTs now bind and validate; secret values never re-render.
No delivery services, financial calculations, models or migration rules changed.

Validation: 82 Rates/Notify tests passed on a fresh database, including restricted
RLS coverage; 33 targeted tests passed after final help/permission refinements.
Import-boundary, gettext and diff checks pass. Local Chrome review covered empty
directories, Rates entry and WhatsApp setup at phone/desktop widths, Hindi labels,
ISO date/time controls and live search focus. Populated lists, paging, quote history
and batch review were exercised with isolated test fixtures. No business forms or
notifications were submitted in the accepted rehearsal. Physical touch, screen
reader, provider delivery and novice-operator acceptance remain pending.

Owner/team setup and shared navigation are now delivered in the section above.
Complete staff task acceptance remains required before cutover. The whole-product
redesign and production cutover are not complete.

## Existing-series continuation and policy forms (2026-09-22)

An imported license can now be explicitly verified for new lending while retaining
its license/series IDs and old loans' immutable revision links. The workflow requires
actual current validity and document evidence, final frozen-source hash/reference
and complete loan/release counter review. It appends an audited VERIFICATION revision,
reserves numbers without issuing one, and activates the current license projection.
Stale reviews, backward counters, overlapping numeric prefixes and incomplete
evidence fail closed. Exhausted series remain exhausted. The migration preserves
forced RLS and immutable evidence, and blocks disbursal against an old reference
revision even after verification. See the [operator flow](flows/legacy-license-continuation.md)
and [decision](adr/2026-09-22-verified-legacy-license-continuation.md).

Calculation, fee and monitoring forms now use separate native disclosures, grouped
Django partials, linked errors, method/ratio guidance and English/Hindi labels.
Failed submissions and amendments reopen the relevant section. Small progressive
navigation opens linked sections; all forms work without JavaScript. Hindi native
date controls explicitly use ISO values. Existing policy services and financial
rules are unchanged. Pages are no-store and excluded from HTMX history snapshots.

Validation: 123 tests passed on a fresh database across regulatory evidence,
number allocation, legacy import/export/restore, drafting and setup UI. After the
browser corrections, all 47 final continuation/UI tests passed on another fresh
database, including real form submission, Hindi dates/guidance, incomplete raw
verification rejection, old-loan servicing/export and new draft/approval/disbursal.
Migration drift, Django checks, JavaScript syntax, gettext and import-boundary
checks pass. Browser review confirmed 390px/1280px layouts, English/Hindi policy
rendering and disclosure navigation. Logs: `outputs/ux-license-continuation-20260922/`.
Physical-device, screen-reader and novice-operator acceptance remain pending.

The schema migration is applied only to the local accepted rehearsal. No real
license was verified, no rehearsal business data was changed and nothing was
deployed to Linode. Actual documents and the later final frozen numbering review
remain required at cutover; staff product/policy/price readiness remains separate.
Next UX slice: Rates and notifications; whole-product/operator acceptance is pending.

## Branch readiness, licenses and numbering (2026-09-22)

Loan setup now highlights the first unfinished existing check and keeps access to
servicing visible. The checklist renders its metal-price step once, separates
document/printing review, and places secondary administration links in a disclosure.
A responsive license register distinguishes imported references from lending
licenses. Status remains guidance from the existing selector, not approval or
verification of evidence. Loan-entry visibility respects the existing permission.

License creation/amendment/renewal and numbering forms now use grouped fields,
shared native field/error partials, linked corrections, document-reselection help
and Hindi labels. Numbering examples are explicitly illustrative; real previews
remain on the license page, before regulatory history. Empty POSTs bind correctly.
Series service validation returns to the form with values preserved; failed updates
still roll back identity and both counters. Setup pages are private/no-store and
exclude HTMX history snapshots. No service rules, models or migrations changed.

127 focused tests pass across setup UI, license/series services, numbering,
regulatory evidence, loan UI and shell rendering (23.723s). Gettext compilation,
diff checking and the 699-file import-boundary check pass. Read-only rehearsal
browser checks confirm next-step navigation, imported-reference warnings, saved
series values and 390px/1280px reflow without page overflow. No license, sequence,
production or accepted rehearsal business record changed. Physical touch, screen
reader, document upload and operator acceptance remain pending.
Next: calculation, fee and monitoring form guidance, followed by Rates and
notifications. See [implementation evidence](implementation/accessible-directory-redesign.md#branch-readiness-licenses-and-numbering).

## Loan search and servicing overview (2026-09-22)

The loan directory now puts search and status first, with license/series/date
filters in a disclosure and responsive cards in place of the wide table. Search
includes customer phone numbers. Native partials provide private HTMX results,
ordinary GET/history fallbacks, retained pagination filters and announced updates.
Invalid choices/dates and reversed date ranges show linked corrections instead
of partially filtered results. New-loan visibility follows the existing permission.

The displayed principal is explicitly the amount at creation/import, not today's
balance. Loan detail places the recommended action and full release before other
actions, with jump links to balances, collateral, documents and history. Imported
opening loans no longer advertise their unsupported auction workflow. Financial
calculations, command permissions and immutable migration evidence are unchanged.
New labels/guidance have compiled Hindi translations.

127 focused Django tests were checked across loan UI, opening release, Party UI and
shell rendering; one fixture/message assertion was corrected and its test plus two
affected directory tests pass on rerun. Four JavaScript tests, gettext compilation
and the 699-file import-boundary check pass. Read-only rehearsal browser checks
confirm live search, typing focus, keyboard filter-error recovery, desktop pointer
recovery and no horizontal overflow at 390px/1280px. Phone pointer/touch and complete assistive-technology/device
acceptance remain pending. No production or rehearsal business records changed.
See [implementation evidence](implementation/accessible-directory-redesign.md#loan-search-and-servicing-overview).
Next: simplify branch setup forms and readiness guidance, then continue Rates and
notifications; physical-device, print and operator acceptance still precede cutover.

## Collections and single-loan full release (2026-09-22)

Full release now follows three sections: review the dated settlement, match the
selected collateral, then record cash and physical handover. Native template
partials render the quote and item list. Release-day interest is explicitly included
in the displayed interest/fees, preventing double counting. Authorized interest
concessions sit in an optional disclosure; ordinary release staff see guidance
instead of concession inputs. Existing command permissions still reject forged
concessions. Unavailable/blocked quotes disable the completion button.

Repayment now explains allocation preview, recorded-balance limits and the separate
full-release path. Both forms bind empty POSTs, retain input/request keys on errors,
use linked errors and no-store responses, and keep existing CSRF, settlement,
handoff and retry semantics. Loan detail links directly to release history/memos.
Added English/Hindi guidance changes no calculations, models or migrations.

99 focused tests pass across loan UI, concessions, imported opening release,
repayment allocation, release readiness and shared-shell rendering. The 699-file
import-boundary check and gettext compilation pass. Read-only browser checks on
the accepted rehearsal confirm the new release page, optional concession disclosure
and 390px layout without horizontal overflow. No production or rehearsal payment,
release or custody record changed. Real collection/handover, keyboard/screen-reader,
physical-device and print acceptance remain pending. See
[the flow](flows/single-loan-collection.md) and
[implementation](implementation/accessible-directory-redesign.md#collections-and-full-release).
Next: simplify the loan directory and servicing overview for daily counter work.

## Loan review, disbursal and printing guidance (2026-09-22)

Draft/approved loan detail now places customer, date, tenure and the principal-to-net
payment breakdown before the next action. Drafts use the existing read-only review
calculation; approved loans use the same frozen-economics parser as disbursal.
Owner combined review and separate disbursal share a native template partial.
Payment forms have linked errors, an explicit payment-date label and clear guidance
that recording disbursal does not transfer money. Empty POSTs now bind correctly.
The existing approval POST, service checks, signed owner review and replay rules
remain intact; there is no new approval or payment protocol.

Loan documents are grouped with download/print guidance. Loan-ticket availability
requires a non-draft loan and approval evidence; key facts/schedule availability
requires a saved schedule. Existing PDF issuance, evidence and reprint services are
unchanged. New guidance is translated into Hindi. Detail and disbursal responses
are no-store and exclude HTMX history snapshots.

142 focused Django tests, gettext compilation and the 699-file import-boundary
check pass. Regression and browser evidence are recorded in
[the redesign implementation](implementation/accessible-directory-redesign.md#loan-review-disbursal-and-printing).
The local rehearsal web server was restarted with its existing settings. Read-only
browser review confirms an imported loan offers its existing schedule without
inventing an approval ticket; the document card fits at 390px. No production or
accepted rehearsal business records changed. The older port-8000 development
database lacks a previously introduced media column and was not migrated here.
Complete desktop/mobile payment walkthroughs and physical printing remain pending.
Next: collections and full-release guidance, with the existing settlement rules.

## Customer photos, identity and first-loan guidance (2026-09-22)

Customer create/edit now offer webcam or front/rear mobile camera capture, local
file preview, retake and discard before saving. Captures use the existing multipart
ImageField and private media boundary. Camera tracks stop after capture, cancellation,
submission or leaving the page; ordinary upload remains available without camera access.

The customer record connects address and identity review to a customer-prefilled
loan draft. Identity forms have distinct control IDs and linked errors. Branch
setup and blocked loan entry explain the next prerequisite with permission-aware
actions. Draft entry uses shared accessible fields/errors and private no-store
responses. Added Hindi copy covers the new guidance and labels; remaining legacy
screen copy and the full approval/disbursal/release redesign are still pending.

128 focused Django tests and 10 JavaScript tests pass, along with the 699-file
import-boundary check. Browser review confirms local photo selection/discard,
edit controls/private preview URL, identity navigation and the missing-license
handoff to branch setup. Phone-width setup layout was inspected. Physical webcam,
mobile-camera and assistive-technology acceptance remain pending. No production
or accepted rehearsal business records changed. See
[implementation evidence](implementation/accessible-directory-redesign.md#customer-photos-identity-and-first-loan-guidance).

## Customer entry and onboarding introduction (2026-09-22)

The next redesign slice simplifies Party creation/editing: identity/contact first,
additional fields in a native disclosure, linked server-error summary with focus
recovery, retained text, file-reselection guidance and plain next-step explanation.
Native template partials share accessible field/error markup. Writes remain normal
CSRF-protected Django submissions through existing authorization/save boundaries;
no HTMX write protocol, model or financial service changed. Empty POSTs now bind
correctly and show required-field errors. Private form responses are no-store.

The onboarding introduction now has a responsive, labelled progress display and a
practical customer-visit guide, optional preferences and an existing-Workspace
link. It distinguishes account introduction from actual lending readiness, without
changing completion redirects, permissions or saved preference history. Customer
entry and guide copy are translated into Hindi; legacy Email mistranslation was
corrected. The obsolete schema/DEA onboarding flow document is replaced.

78 focused tests and the 699-file import-boundary check pass. Browser checks cover
customer-form error focus and English/Hindi phone/tablet layouts; the signed-in
onboarding browser journey remains pending. Evidence is recorded in
[the redesign implementation](implementation/accessible-directory-redesign.md#customer-entry-and-introduction).
Full onboarding form/setup redesign, customer detail/KYC, lending/release journeys
and physical-device/operator acceptance remain pending. No production or financial
rehearsal records were changed.

## Native-partial redesign: first implemented slice (2026-09-22)

The owner chose Django 6 native template partials, HTMX and current Bootstrap.
The active shared shell now pins Bootstrap 5.3.8 with SRI, exposes a keyboard skip
link and correct page language, and uses explicit language submission. The Party
directory has responsive records, progressive search/filter/pagination via one
native partial, permission-aware actions, filtered exports and English/Hindi copy.
Full pages remain the no-JavaScript/history fallback. Partial reads retain normal
authorization and private caching; borrower HTML is excluded from HTMX history
storage. Existing local HTMX 1.9.10 remains; no whole-app HTMX 2 upgrade is claimed.

63 focused Party/private-media/shared-shell tests pass. A broader 68-check run has 64 passes
and four old management-shell failures reproduced with original HEAD templates.
Hindi catalogue syntax/duplicate/format issues were repaired and gettext compilation
passes with legacy metadata warnings. Browser checks confirm live search with focus
retained, result announcements, pagination focus, Back restoration and language
switching with filters retained; responsive and translation rollout remains scoped
to this first slice. See [implementation](implementation/accessible-directory-redesign.md)
and [decision](adr/2026-09-22-native-template-partials-ui.md).

Next: first-day setup/onboarding and customer creation, then lending/release flows.
Whole-product redesign, Hindi coverage, assistive-technology and physical-device
acceptance are not complete. Production and accepted financial evidence are unchanged.

## UX and onboarding redesign now precedes cutover (2026-09-22)

The owner requires a thorough accessibility and user-flow redesign before moving
production. Confirmed targets: desktop, tablet/phone, **English and Hindi**. The
[existing UX plan](plans/project-wide-ux-revamp.md) now defines a live task audit,
first-day/returning-customer prototypes, incremental implementation and bilingual
accessibility/operator acceptance. Initial source review identified a tour that
collects preferences and obsolete schema/DEA onboarding documentation; these are
audit inputs, not a claim that all live screens have been tested or redesigned.

The accepted migration/media evidence remains intact. Production stays live; the
final freeze and switch follow UX acceptance and deployment readiness. The separate
server is still not created; procurement is no longer the immediate next task.
No UI code, financial behavior or infrastructure changed in this planning update.

## Separate-server cutover preparation (2026-09-22)

The owner selected a separate Linode server and confirmed it is not yet created.
The [cutover runbook](implementation/linode-production-cutover.md) now records
preparation, all-branch write freeze, final database/media snapshot, fresh reviewed
inputs, exact-target import/reconciliation, routing, reopening and the fallback
boundary before/after new-system business writes. The local 101-minute database
admission is not a production downtime estimate; measure the full run on the host.

Added explicit `django_project.settings.prod_r2` and opt-in production Compose
selection for web/monitoring. It requires a durable production-only media prefix,
HTTPS R2 endpoint and nonempty credentials, preserves static storage, enforces
secure cookies/HTTPS and trusts proxy scheme headers only by explicit opt-in.
Ten deployment/settings tests pass, including rejection of preservation/rehearsal
prefixes and invalid credentials/endpoints. No server, bucket, credential, database,
DNS or running application was changed by this preparation.

Next: provision the separate server and verified SSH access, issue permanent
runtime credentials, configure current branch lending/access, add the guarded
production-target media command path, and perform a timed clean-host rehearsal.
The media command remains rehearsal-only. No production readiness or cutover is
claimed, and no freeze window has been scheduled.

## Legacy media attachment verified in the isolated rehearsal (2026-09-22)

The source-bound attachment implementation and rehearsal R2 backend are complete.
All 28,224 verified branch image references are attached: 1,148 customer images,
5,988 active collateral photos and 21,088 closed-history photos, requiring 29,366
separate application objects including 1,142 default profile copies. Owner-only
admission, immutable receipts, forced RLS, source/parent checks, private delivery,
retry behavior and SQL immutability have passed 60 relevant tests (56 media/archive
tests and four registry/forced-RLS metadata tests).

Only `rokkad_baseline_rehearsal_linode_20260921` received the new migrations.
All application object keys/sizes and all 28,224 source/target receipts reconcile.
Every new object was read back and hash-verified during admission. A full identical
retry recognized 28,224 existing receipts and created nothing. The 32,554 preserved
original/candidate files and 13 preservation reports remain intact. Twelve private
HTTP probes across three Workspaces pass authorized byte/hash checks, anonymous
denial and cross-Workspace denial; nine detail pages render without direct R2 URLs.
Ordinary-owner browser checks cover customer, active and closed-history images.
Bounded transport and interrupted-body retries resolved connection failures without
disabling certificate validation or accepting partial bytes.

Visual inspection found plain grey placeholders in the source. Twelve decoded
source hashes account for at least 24,946 blank image references: 5,283 active
collateral, 19,661 closed-history and two customer images. Those exact fingerprints
are labelled as blank in the application. Other images are unclassified; transfer
integrity is not proof of usable photographic evidence.

See [the attachment runbook](implementation/linode-media-attachments.md) and
[decision](adr/2026-09-22-legacy-media-attachment-evidence.md). The private evidence
directory is `outputs/linode-media-attachments-20260922/`; `review.html` links to
sample records. All 252 financial and Party metadata fingerprints match the
pre-attachment snapshot. State is **REHEARSAL_MEDIA_VERIFIED**, not production
cutover. The live Linode application, original media and ordinary development
database are unchanged. Permanent runtime credentials, production access/current
lending setup, a guarded production-target media path, and final frozen-source
preparation/reconciliation remain.

## Media preservation copy verified in private R2 (2026-09-21)

After the owner saved the approved bucket-scoped credentials, **32,554 files**
(**591,274,335 bytes**, about 564 MiB) were copied directly from Linode to
`rokkad-production-media`: all 31,405 inventoried branch files and 1,149 separately
labelled shared-folder recovery candidates. Every source hash matched inventory,
every destination object was read back and SHA-256 verified, and all destination
keys/sizes reconcile. Conditional creation refused overwrites; all 15 sample
retries verified existing bytes. There were no source/destination verification
failures. The source application/media and both rehearsal databases were unchanged.

Thirteen evidence/report files were also copied and hash-verified in R2, including
the source-record map, copy receipts and exception reports. Private local evidence
is `outputs/linode-media-copy-20260921/`; `review.html` is the readable result.
The bucket has no custom domain and its public development URL is disabled.
An unsigned GET of a known photo from Linode was rejected with HTTP 400,
`InvalidArgument: Authorization`. An earlier local TLS transport failure was not
counted as privacy evidence. See [the completed preservation record](implementation/linode-media-preservation-20260921.md).

This preservation checkpoint was **MEDIA_PRESERVATION_VERIFIED_ATTACHMENTS_PENDING**;
the September 22 entry above completes rehearsal attachment, not go-live.
Of 31,838 discovery references, 28,224 have verified branch originals, 1,149 have
unverified shared-folder candidates, and 2,465 have no exact file in checked
locations. The missing branch references still include 102 active-loan photos,
3,507 closed-history photos and five customer photos. Separately, **203 active
collateral items had no photograph reference recorded at all**. Among 6,293 active
items, 5,988 have verified originals. Do not silently turn candidate matches or
newly captured pictures into original evidence.

Offline source evidence now preserves all 1,153 customer-photo rows and their
default flags: 1,147 customers, six with multiple photos and two with no marked
default. No application attachments were created during this preservation step;
the later attachment implementation uses separate application copies so ordinary
cleanup cannot delete preserved originals. See [the preservation decision](adr/2026-09-21-legacy-media-preservation-and-application-copies.md).
Permanent runtime credentials, missing-file disposition and the final frozen
database/media cutover remain.
The one-week migration token must not become the production application credential.

## Live media inventory complete; copy and recovery pending (2026-09-21)

The owner installed temporary SSH access and reported "ssh ready". Key-based
login succeeded. Read-only checks verified `/var/www/rokkad/media`, the three
schema directories and deployed commit `4312573fa2dca9f8bea3abd1ab84aadb5bd1e1cd`
under `/root/app/rokkad`. Deployed code retains TenantFileSystemStorage, tenant
relative `%s/` and the stated production media root. No application or media
files were written. Inventory reads ran serially with idle I/O priority and a
20 MiB/s cap; only manifests and hashes were saved locally.

All **31,405 branch files** were readable and stable during their individual
hash reads: **589,157,649 bytes**, about 562 MiB (disk allocation about 642 MiB).
The discovery dump's **31,838 photo references** reconcile as follows:

| Source branch | Exact branch-path matches | Missing from branch folder |
| --- | ---: | ---: |
| JCL | 11,582 | 3,159 |
| JSK | 4,662 | 455 |
| Lakshmi | 11,980 | 0 |
| Total | 28,224 | 3,614 |

Missing references comprise **102 operational-loan photos** (77 JCL, 25 JSK),
3,507 closed-loan photos and five JCL customer photos. Separate read-only inventory
of the two older shared photo folders found 1,149 exact-path JCL candidates,
including 23 operational photos and all five customer photos. These remain
unverified associations, not recovered attachments. The other 2,465 missing
references have no exact path in the checked branch/shared folders. No same-branch
filename-stem alternatives were found. The 3,181 branch files absent from the
discovery reference list are retained for classification, not declared orphans.

Evidence and a readable report are private under
`outputs/linode-media-live-20260921/` (`review.html`, filesystem/reference manifests,
missing classification, shared-folder candidates and checksums). This is live-file
evidence against the discovery dump, not a database/filesystem-consistent snapshot.
No images/documents have been transferred to R2 or attached to the rehearsal.

The owner confirmed the R2 bucket is **not created**. Existing local R2 environment
fields are populated but their validity/permissions were not tested; do not treat
them as usable production credentials. `django-storages`/`boto3` are absent from
the current requirements, so the inactive helper alone is not a working deployment.
The owner signed in to Cloudflare. The account has an existing empty `rokkad`
bucket alongside unrelated application buckets. Preparation selected a separate
`rokkad-production-media` bucket, Standard storage and automatic Asia Pacific
placement. Automatic approval review initially rejected the agent-selected permanent
name. The owner then explicitly approved `rokkad-production-media`; creation
succeeded and the dashboard confirms Standard storage, zero objects and **Public
Access: Disabled**. Existing buckets were not modified. The local R2 endpoint
belongs to a different account, so the guarded SDK check sent no credentials or
request there. The owner explicitly approved the one-week, bucket-only Object
Read & Write token `rokkad-media-migration-20260921`; Cloudflare confirmed its
creation. The one-time credential result page is retained for the user. Token
secrets were not printed in tool output or chat. The syntax-checked private
`configure-r2.ps1` helper is ready for secure terminal entry into
LocalAppData outside OneDrive; credentials must not be pasted into chat. Next
configure the approved private R2 access, preserve missing-file exceptions and
verify candidate provenance, then implement and test the bounded attachment path.

## Linode media destination selected: private R2 (2026-09-21)

The owner chose Cloudflare R2 for new-system media and supplied
`root@rokkad.com`, `/var/www/rokkad/media` for source access. A read-only SSH
attempt reached the server but authentication failed (`publickey,password`);
no source files were accessed or changed. The owner uses password login and
authorized preparation of temporary key access. Private operator scripts are ready
under `outputs/linode-media-ssh-20260921/`: `authorize.ps1` generates a dedicated
key outside OneDrive in the user's LocalAppData, restricts local directory access,
installs its public key using the owner's interactive password login, and verifies
key authentication. `revoke.ps1` removes that exact authorization and key pair.
Both scripts passed PowerShell syntax checks. The owner subsequently ran
authorization in their own terminal; agent key authentication succeeded as recorded
above. The password was not shared. The key disables forwarding and PTY but permits root commands; it must be
removed after migration. Destination bucket/credentials remain pending. No media
was copied.

The repository currently uses filesystem storage; the R2 helper/options are
present but the production override is commented out. Existing authorized Party
and Loans file routes should continue reading private storage. Direct Linode-to-R2
copy avoids requiring a local download, but file verification and source-to-record
attachment remain separate required steps. Closed-history media needs an explicit
retention/delivery extension; database replay alone does not attach any media.
See [the bounded migration plan](plans/linode-media-to-r2.md). Live pre-copy can
reduce transfer work; final acceptance still needs the frozen database and media
snapshot. This does not authorize or schedule a production write freeze.

## Reviewed-snapshot replay proven in a clean target (2026-09-21)

The accepted inputs are captured in a private, checksummed three-Workspace package.
The `linode_migration` command composes existing import services for replay and
full reconciliation in a clean target, and reports source changes without applying
old decisions to a new dump. The fresh database
`rokkad_baseline_rehearsal_cutover_20260921` was built from a clean checkout using
ordinary migrations, restricted runtime grants and ordinary owner Memberships.
Workspace IDs were deliberately reassigned to exercise destination remapping.
Cold admission used `f276b9b8`; final safeguards, tests, replay and reconciliation
used `da3c91ec`. Both checkouts were clean.

All **6,273 operational openings**, **39,133 closed records** and the **one reviewed
exclusion** reconcile: all **45,407 source loan IDs** are accounted for exactly
once. Party totals are 8,630 masters, 3,496 contacts and 6,722 addresses. Every
opening balance, collateral record, remaining schedule, next interest boundary,
signed source document and closed document was checked. Totals remain
199,847,583 principal and 22,614,850 interest, with no unpaid fees.

The final clean checkout passed **56 tests** and the import-boundary guard.
All 31 scoped page renders, 22 opening exports, three archive exports and 22
full-release/retry simulations passed; all servicing was rolled back. A complete
package replay succeeded, all **291 business-table fingerprints** remained
identical, and final reconciliation passed again. Cross-Workspace and missing-
context RLS checks passed. The accepted browser rehearsal's 33 recorded business-
table fingerprints were also checked unchanged during this work.

Evidence is private under `outputs/linode-clean-replay-20260921/`, including
`completion.json`, `verification.json`, release/migration metadata, logs and an
evidence checksum manifest. The reviewed input package is
`outputs/linode-reviewed-package-20260921/`. Cold admission took about 101 minutes
on this local machine; this excludes media and fresh-source preparation and is
not a production timing guarantee. See [the operator runbook](implementation/linode-reviewed-replay.md).

The owner confirmed production photographs/documents live on the same Linode
server filesystem, not Cloudflare R2. Actual media root/path inventory, separate
file backup, association mapping and verified destination copy remain pending.
The SQL dump does not contain those file bytes.
Read-only inventory found 31,838 photo references in this dump; 5,180 relative
paths occur in multiple source schemas. Preserve tenant-specific path resolution
when copying. No media files have been copied or verified.

## Owner accepted the browser rehearsal (2026-09-21)

The owner reported: "all reviewed and looks great,whats next?" This accepts the
presented three-Workspace rehearsal review. No further review of the same imported
snapshot is queued. It does not establish a production cutover date, media recovery,
new-lending setup or acceptance of financial workflows not exercised in the review.

The accepted-snapshot package and clean-target proof are complete as recorded
above. A new Migration Center UI is not required. Next complete media
inventory/copy mapping, production owner
and staff access, valid current lending setup, and the required servicing scope.
Then schedule the write freeze, obtain a fresh complete database and media snapshot,
rebuild/reconcile the final target and accept its report before switching users.
Linode remains live throughout preparation; this discovery dump is not a delta base.

## Separate rehearsal browser access ready (2026-09-21)

The imported JCL, JSK and Lakshmi data is available locally at
`http://127.0.0.1:8081/accounts/login/?next=/app/workspaces/` using the dedicated
`migration-rehearsal-owner` account. Its password and branch links are in the private
`outputs/linode-rehearsal-access-20260921/access.html` file. The account now uses
ordinary owner Memberships, with the former platform override removed. Three local
zero-price trials run through October 5; no paid purchase or provider subscription
was made. Existing account credentials in the normal app were not changed.

The opt-in `baseline_rehearsal_web` settings retain the isolated database guard,
use separate session/CSRF cookies, local media/cache/email, loopback hosts, and a
yellow rehearsal banner. The launch script binds only to `127.0.0.1`. The baseline
database override now copies the inherited mapping instead of mutating dev settings.
Three configuration tests passed. Actual password/CSRF HTTP login, branch selection,
all three loan lists, sample interest-detail pages, Party lists and closed-history
lists passed (12 scoped pages). Cross-branch object IDs returned 404; anonymous loan
access required login. All checked business-table hashes remain unchanged. The login
page was visually checked and left open; debug toolbar is hidden in this profile.

The owner subsequently accepted the presented review, as recorded above.
Production cutover, media, current lending
setup and any required unsupported servicing remain pending. See the
[rehearsal access guide](flows/linode-rehearsal-access.md) for restart instructions.

## Owner decisions applied: rehearsal loan holds resolved (2026-09-21)

The isolated September 21 rehearsal now contains **6,273 operational loans**
(JCL 2,355; JSK 1,483; Lakshmi 2,435), **39,133 closed evidence records**, and
one owner-excluded unused/cancelled JSK entry, WH01223. All 45,407 source loan IDs
are accounted for exactly once, with **zero unresolved loan holds** in this dump.
The ten JSK matching addresses are imported as distinct identities; Party totals
are 8,630 masters, 3,496 contact methods and 6,722 addresses.

Owner decisions closed the earlier exceptions: 190 inactive-customer loans are
retained as owner-reported closed with unknown release dates; payments on 14 loans
are excluded from calculations while retained in evidence (one closed, 13 open);
six exact collateral purity values are corrected to 100% in new JSK/Lakshmi `/2`
source profiles after confirming no release records. Earlier `/1` profiles and
sealed evidence remain unchanged. The earlier question's incorrect “12” payment
cohort count is explicitly corrected to 13 in the decision evidence.

Opening principal is **199,847,583 INR**, interest **22,614,850 INR**, fees zero at
September 21. Every opening and closed document, balance, obligation, source graph
and next interest boundary reconciled. All 19 additional loans passed detail-page,
export and full-release/retry rollback checks; RLS checks passed. The focused suite
passed 119 tests, including source-bound exclusions and distinct-address review.
The later command/browser-evidence checks also passed the 20-test opening module.
Report: `outputs/linode-owner-decisions-20260921/review.html`; its manifest covers
71 private files. See the [completed owner-decision record](implementation/linode-owner-decisions-20260921.md)
and [review boundaries](adr/2026-09-21-owner-reviewed-migration-exceptions.md).

Separate browser access is ready and the owner accepted the presented review above.
These records are still in `rokkad_baseline_rehearsal_linode_20260921`, not the normal
application or `jcl-13`. Production remains pending: retained Party preparation
decisions, required servicing, current lending setup/access/media and a clean-build
release, followed by a legacy write freeze and fresh complete dump into a fresh
target. Full settlement and coupled reversal work; ordinary partial repayments
remain guarded. This supersedes the unresolved counts in earlier checkpoints below.

## Three-Workspace loan rehearsal completed with holds (2026-09-21)

The owner's "no fees are unpaid,proceed" answer completed the outstanding fee
fact. Source-bound admission and independent reconciliation completed in the
isolated `rokkad_baseline_rehearsal_linode_20260921` database:

| Workspace | Operational openings | Closed source evidence | Held active loans |
| --- | ---: | ---: | ---: |
| JCL | 2,345 | 26,474 | 200 |
| JSK | 1,478 | 3,811 | 6 |
| Lakshmi | 2,431 | 8,658 | 4 |
| Total | 6,254 | 38,943 | 210 |

All 45,407 source loan IDs are accounted for in disjoint sets. Every accepted
opening document, source record, collateral mapping, balance, obligation and
next monthly interest boundary reconciled. Opening principal is 198,573,923 INR,
interest 22,317,483 INR and fees zero at the September 21 rehearsal checkpoint.
Twenty-one representative detail pages, exports and full-release/retry rollback
checks passed. Restarting all three opening runners verified existing fingerprints
and made no extra admissions. Closed-history documents and findings match exactly;
archive admission left checked operational table counts and hashes unchanged.
Restricted-role cross-Workspace and missing-context RLS checks passed.
R09911 is closed source evidence, with the approved December 16, 2025 date retained.
This supersedes preparation-only/pending-fee states below. Linode and the normal
application database remain unchanged; these records are separate from `jcl-13`.

The Linode adapter now normalizes description line breaks/tabs with exact raw
source evidence and before/after transformations. Empty obligation rows are
rejected during offline validation, matching the existing writer constraint.
The focused regression suite passed all 70 tests; code checkpoint `7d8e131a`.
Local report: `outputs/linode-opening-rehearsal-20260921/review.html`. Its manifest
covers 791 private evidence files and all local report links resolve. See the
[admission rehearsal record](implementation/linode-opening-rehearsal-20260921.md).

Production is still pending: resolve the 210 active-loan holds, ten duplicate
Party addresses and retained Party preparation decisions; establish required
servicing, current lending setup/access/media and a clean-build release; then
freeze legacy writes and migrate a fresh complete archive into a fresh target.
Opening servicing currently supports full-settlement catch-up/release and coupled
reversal; ordinary partial repayments remain guarded.

## Three-Workspace loan review packages prepared (2026-09-21)

Reused the existing source-preview, opening-review and closed-evidence adapters on
the same hashed discovery archive. All 6,464 unreleased loans have observed Party
links in the isolated rehearsal database. There are 6,456 opening-review drafts
and eight incomplete-collateral holds; every held source graph is retained.
Fourteen loans have recorded payments, and 190 JCL borrowers are inactive.
All 38,943 released source loans produce schema-valid historical-evidence
documents. This is preparation only: zero loan, event, setup or archive writes.

`preview_legacy_closed_archive` now accepts an optional versioned `--source-profile`,
checks its schema before extraction, and preserves reviewed correction provenance
and original row hashes. Existing invocations remain compatible. Fifteen focused
archive/profile tests initially passed, including correction retention and early
mismatch rejection. After the owner's "same rules as jcl" confirmation,
`linode-owner-terms/1` explicitly scopes shared interest and missing-tenure rules
to these source profiles. The combined owner-rule/archive/profile suite passed
29 tests. The report now includes 6,442 interest illustrations and month counts;
22 calculations remain held (14 payment cases and eight source/collateral cases).
630 missing-tenure cases use the confirmed three-month fallback. These remain
illustrations, not accepted balances.

Local review: `outputs/linode-loan-review-20260921/review.html`; each Workspace has
opening gaps, all active borrower links, payment review, setup evidence and closed
history exceptions. Draft balances, custody and terms remain unapproved. The
source-verified operational bridge now accepts an explicit versioned source profile
through single/bounded staging and the operator command, retaining it in signed
source evidence. The owner then confirmed net weight for JSK and Lakshmi.
`linode-owner/1` separately scopes those confirmed terms and net-weight facts to
the three versioned Linode profiles; older JCL profiles stay restricted. All
6,456 drafts were regenerated as v2 in each Workspace's `confirmed-opening/`
directory, with unknown balances/custody intact. Source preparation, terms,
staging and reconciliation suites passed 57 tests, including synthetic JSK and
Lakshmi stage/commit/retry through canonical Party mappings and source-drift rejection.
Raw legacy borrower references
now resolve the canonical Party UUID at the Loans opening boundary; ambiguous
bindings fail before financial writes. All 14 opening-import tests passed,
including canonical mapping, retry, ambiguity and Workspace isolation.
Source/financial gates remain intact. Actual balances/fees and current custody
still require evidence; destination setup must be prepared before real admission.
All 45,407 loan IDs and 38,943 archived candidate documents
were reconciled; source hashes, active graphs and report links passed verification.
Final combined regression run: all 98 focused tests passed. The final report
manifest covers 107 private evidence files, including the subsequent custody attestation.
The owner subsequently confirmed branch custody for the rehearsal apart from
flagged exceptions. Its separate evidence covers 6,254 unflagged candidates;
the 210 flagged loans stay excluded from that attestation. Fees/charges remain
unanswered, so actual opening documents have not been financially admitted.
See [loan review preparation](implementation/linode-loan-review-20260921.md).

## Three-Workspace Party rehearsal completed with explicit holds (2026-09-21)

The local isolated database `rokkad_baseline_rehearsal_linode_20260921` now contains
the verified Party import below. This supersedes the earlier preparation-only
state; Linode and the normal application database were not modified.

| Workspace | Parties | Contacts | Addresses | Held source rows |
| --- | ---: | ---: | ---: | ---: |
| rehearsal-jcl-20260921 | 5,882 | 1,898 | 3,997 | 0 |
| rehearsal-jsk-20260921 | 646 | 513 | 611 | 10 |
| rehearsal-lakshmi-20260921 | 2,102 | 1,085 | 2,104 | 0 |

All 18,848 prepared source rows reconcile as 18,838 committed plus ten held JSK
duplicate-address rows. No duplicate winner was inferred. Source content,
accepted digests, parent links and saved child fields match preparation. Replaying
every completed batch leaves counts unchanged. Raw SQL checks under the restricted
runtime role confirm cross-Workspace and missing-context read isolation. The
adapter now uses canonical master UUIDs for child parent lookup, retaining raw
legacy customer references as provenance. The targeted preparation/name-review/
child suite passed all 65 tests.

The 187 preparation review items remain explicit production-review facts: 180
missing related-person names, five unsupported relationship labels and two
conflicting defaults. Rehearsal omissions/default proposals are not production
acceptance. Obsolete pending attempts were cancelled; committed rows were retained.

The same source was classified into 6,464 unreleased opening-review candidates and
38,943 released history candidates. Fourteen unreleased loans have payments and
eight have loan-level source errors (review categories may overlap). No loans or
historical archives were admitted in this database. Next is source-bound opening
evidence and setup reconciliation; balances, interest and custody cannot be
inferred from source totals. Final production migration still requires a write
freeze, fresh full archive/media and business acceptance.

Local report: `outputs/linode-party-rehearsal-20260921/review.html`, with verification,
receipts, held rows, source evidence and a SHA-256 manifest. See the
[rehearsal record](implementation/linode-party-rehearsal-20260921.md).

## Isolated three-Workspace rehearsal target preparation (historical checkpoint, 2026-09-21)

`rokkad_baseline_rehearsal_linode_20260921` is a new local-only database with the
current owner-only migrations applied. It initially had three empty Workspaces:
`rehearsal-jcl-20260921`, `rehearsal-jsk-20260921`, and
`rehearsal-lakshmi-20260921`. The local operator account has an unusable password.
No business data had been created at this initial checkpoint; the completed Party
rehearsal above is the current state.

The fresh-database rehearsal exposed a deployability gap: the cluster's existing
restricted runtime role did not automatically have grants on a newly created
database. `scripts/provision_runtime_role.py` now has an explicit
`ROKKAD_RUNTIME_GRANT_EXISTING=1` mode. It verifies the existing login stays
non-superuser, non-`BYPASSRLS`, non-owner and grant-only before granting the target
database. After provisioning, the runtime role passed Django checks and saw zero
Party, import, operational-loan and evidence records in each separate Workspace
context. The next slice at that checkpoint was Party preparation, which must
handle the 1,000-row package limit and retain unsupported relationship labels for
review before any Party commit.

That preparation is now available through `prepare_legacy_party`. It produces
chunked canonical JSONL with the source system
`legacy:<installation-uuid>:<schema>`, which the Party staging service accepts
without mislabelling it as a native Rokkad export. The three discovery-profile
runs produced 11,777 JCL, 1,780 JSK and 5,291 Lakshmi Party source records with
zero contract-validation errors. Their 187 retained review items are 180 missing
related-person names, five unmapped relationship labels and two duplicate source
defaults. Those files were subsequently staged and committed as recorded above,
with ten duplicate-address rows held.

## Linode production discovery snapshot inventoried (2026-09-21)

The supplied archive is a valid PostgreSQL custom-format dump despite its `.sql`
extension. It is an inventory-only snapshot of `rokkaddbv1`, made by PostgreSQL
15.7, with SHA-256
`f50e992a5813571e5d64316534cf073c08a96059780420be47bf7211eab163a6`.

The authoritative legacy Company map confirms `jcl` (Company 2), `jsk` (Company
3) and `lakshmipawnbroker` (Company 6). The three schemas contain 8,630 customers,
45,407 loans, 22,835 payments, 38,943 releases and 6,464 unreleased loan candidates.
This is not an import result and no destination data was written.

The ongoing source is live. Rehearsals use this snapshot in isolation; production
cutover will require an announced write freeze and a fresh final archive. The final
target is built from that complete final snapshot rather than a best-effort stream
of changing rows. The discovery report records the owner-approved correction for
JCL loan `R09911`: source date `2026-12-16` is to be treated as `2025-12-16`, with
the original value retained as evidence and rechecked in the final snapshot. See
[the discovery report](implementation/linode-production-discovery-20260921.md).

## Production migration redesign: Django-tenants source to RLS target (2026-09-21)

The requested production migration is separate from the local September rehearsals.
Linode production is pinned to `4312573fa2dca9f8bea3abd1ab84aadb5bd1e1cd`, an
ancestor of `rls-mvp`. It used `django-tenants` with one PostgreSQL schema per
Company; the target uses shared-schema PostgreSQL RLS with an explicit Workspace
context. This is a forward data conversion from a known historical source, not a
database upgrade in place or a restore of the old database into the target.

The intended scope is three independently mapped Workspaces: JCL, JSK and Lakshmi
Pawn Brokers. The source schema names, exact table shapes and volume must be
discovered from a fresh, read-only custom-format production dump before any target
writes. The old application remains the rollback system until written business
acceptance of the new system.

The local portability baseline is committed as `a3e0e2b8` on `rls-mvp`. It provides
Party bundles, strict loan-history contracts, reviewed active-opening contracts and
closed-loan evidence archives. It remains a release candidate, not a production
cutover tool: it needs deployment migration rehearsal and source adapters for the
actual Linode schemas. Prior local JCL rehearsals are evidence about test data
only; they do not establish that Linode production has been imported.

Versioned `linode-jcl/1`, `linode-jsk/1` and `linode-lakshmi/1` source profiles now
match this archive. All three completed read-only previews; their unresolved source
errors are review inputs, not destination writes. The JCL profile applies the
owner-approved `R09911` date correction only after matching its exact raw source
value. See the [source-profile decision](adr/2026-09-21-versioned-legacy-source-profiles.md).

The Party portion of the isolated rehearsal is complete as recorded above.
Active-opening evidence, archive admission and final cutover remain pending.
See the
[production migration design](architecture/production-tenants-to-rls-migration.md).

## Closed-loan archive rehearsal completed (2026-09-19)

The owner authorized the next step: retain closed-loan history in the same test
Workspace 10, separate from the 2,101 operational loans. Fresh extraction of the
September 12 jcl dump yields 26,474 schema-valid closed-evidence documents, zero
held, and excludes all 2,463 unreleased loans. Source/review hashes are checked
before acceptance through the existing owner-authorized `accept_evidence` service
in transactions of 100, with committed receipts and replay checks. No new API,
schema or financial behavior is introduced.

Unknown principal/balance, missing payments/collateral and contradictory dates
remain source claims. The mutable stored source amount is retained raw, not
promoted to debt or original principal. Source preparation is in
`outputs/jcl-closed-archive-source-20260919/`; acceptance and verification artifacts
are in `outputs/jcl-closed-archive-import-20260919/`.

All 26,474 distinct closed source loans are now accepted, zero held. Acceptance
used the public Loans archive service and did not create browser upload batches.
Every persisted document, canonical hash, source identity, actor and review matched
the fresh prepared source. Representative search, pagination and detail views passed;
five canonical exports round-tripped exactly and replay reused the accepted rows.
Before/after full-row fingerprints match for loans, financial events, collateral,
custody, releases, repayment schedules/obligations, number sequences, operational
import origins and Parties. The operational-loan count remains 2,101.

Retained findings include 16 date-order contradictions, 15,429 records with unknown
payment evidence and 10,624 with unknown structured collateral; counts overlap.
Original principal and reported balance remain unknown for all records rather than
being invented from mutable legacy amounts. Source borrower references remain
claims and create no Party links. This is historical retention, not certified
settlement or operational closed-loan reconstruction.

COMPLETE, `verification.json`, `review.html`, per-batch receipts and sample exports
are present. Access: TEST - jcl current 20260912 → Workspace settings → Historical
loan evidence (`/w/test-jcl-current-20260912/data-tools/history-archive/`). No
application/schema changes. The 362 held active candidates remain separate work.

## Full eligible rehearsal completed (2026-09-17)

The owner authorized all eligible current jcl loans in the corrected test Workspace
10, retaining seven existing loans and holding payment/inactive-borrower/invalid
cases. Document preflight finds 2,101 eligible and 362 unique holds: 11 payment
cases, 185 inactive-borrower cases (one overlaps), plus 167 validation cases
(155 nonpositive source valuations, 12 invalid descriptions).

Added bounded `legacy_opening.stage_many` to extract one fresh source snapshot
for up to 20 individually reviewed loans. Existing authorization, source matching,
unfinished-batch cap, signed approval, commit and retry guards remain. All 16 bridge
tests pass, including extraction-once parity, late-source-failure atomicity,
input bounds, duplicate selection and authorization before extraction.
Admission completed in 105 chunk transactions: 2,094 new loans plus the seven
preserved samples, 2,101 ACTIVE loans total. Independent reconciliation matched
every immutable source document/digest, borrower, item count, opening event and
principal/interest balance. No unfinished staging or duplicate origins remain.
Opening principal is 41,625,093 and unpaid interest 3,968,680 at September 12;
additional projected collection interest through September 17 is 146,636.
Fees remain zero and custody simulated for this rehearsal.

Eight representative detail pages, collection quotes and restore-supported
opening exports passed across all four admitted series. jcl-13 still has its
original seven records, including CLOSED C07432 with its release history.
Evidence is `outputs/jcl-full-rehearsal-20260917/`: COMPLETE, `review.html`,
`summary.json`, all reconciled loans, per-chunk receipts and 362 held records.
The 167 validation holds comprise 155 nonpositive valuations and 12 invalid
descriptions. Hold reason counts overlap for one payment/inactive-borrower case.
No production migration or reset of jcl-13 occurred. Next: review portfolio totals
and resolve held source records; actual fees/custody and final destination remain
production-cutover decisions. This correctness run is not a throughput SLA.

## Imported-loan interest month breakdown (2026-09-17)

Active opening-loan detail pages now show elapsed months/days, chargeable months
excluding the upfront month, monthly item-total interest, cumulatively rounded
charges, import-date month count/unpaid interest, additional months/interest and
next increase date. The explanation uses the existing original-anniversary
calculator and distinguishes calculated charges from unpaid opening debt. Closed
loans do not display an ongoing-interest breakdown. No financial records changed.

Validation: all 10 opening continuation tests pass, including new anniversary-day,
short-month, pre-cutover and partial-paid/cumulative-rounding checks. All 14 sample
detail pages render; each of the 13 active breakdown totals matches recorded plus
projected interest. Corrected C00045 shows 23 chargeable months / 6,900 on September
17, and R05856 44 / 2,992. C07432 in jcl-13 remains closed without a live projection.

## Corrected seven-loan interest rehearsal completed (2026-09-17)

The owner confirmed all calculated interest after the upfront first month remains
unpaid. Reused the existing empty operational test Workspace 10, **TEST - jcl
current 20260912** (`test-jcl-current-20260912`), with its existing source-bound
Parties, legacy series and retired product. Imported the same seven source loans
through preview, source re-extraction and signed opening admission, carrying
13,682 unpaid interest at September 12 alongside 58,230 principal (71,912 total).
R05856 carries 2,992; B03795 890; C00045 6,900; C03982 1,640; C04872 1,260.
C07432 and RA00532 remain zero-interest at cutover because their origination is
September 12 and the first month is paid upfront. Fees remain zero and custody
simulated; the owner instruction does not resolve the held payment-history cases.

All seven are ACTIVE and passed source verification, retry, cutover/anniversary
checks, full-release rollback, export, persisted balance-selector reconciliation
and detail-page HTTP 200 checks. No release persisted in Workspace 10. Independent
reads confirm jcl-13 still has its original seven records, including CLOSED C07432
with its September 15 release and the other six ACTIVE zero-interest simulations.
No immutable origins or earlier financial history were overwritten.

Evidence: `outputs/jcl-corrected-rehearsal-20260917/review.html`, `summary.json`,
`verification.json`, input documents, seven exports and COMPLETE. Next: compare
the corrected sample in Workspace 10 with the old-system amounts before choosing
the final destination/import strategy. No application/schema changes were needed.

## Rehearsal interest mismatch diagnosed (2026-09-17)

The owner reported no interest on the seven imported loans. Read-only checks of
saved evidence and the exposure selector confirm that all seven were imported with
zero unpaid cutover interest. The rehearsal operator assumed prior interest settled;
therefore these inputs are unsuitable for matching old-system balances. Prior
verification established consistency with those assumptions, not financial parity.
Five older loans have cumulative September 12 calculation baselines of B03795 890,
C00045 6,900, C03982 1,640, C04872 1,260 and R05856 2,992, but none was admitted
as unpaid debt. These calculated amounts are not independently verified receivables.

On September 17 the monthly-anniversary continuation yields zero additional
interest for all seven. Future-date exposure checks return increases for the six
batch loans (earliest B03795 September 21); thus the calculation is functioning
under the saved assumptions. C07432 now has a subsequent servicing event and must
not be reset or reimported over. No financial rows were changed during diagnosis.
Evidence: `outputs/jcl13-interest-diagnosis-20260917/diagnosis.json`.
Next: agree the intended unpaid-interest premise and prepare a corrected isolated
rehearsal or an explicit supported correction, preserving existing financial history.

## jcl-13 varied six-loan rehearsal completed (2026-09-15)

After reviewing C07432, the user authorized the recommended small varied batch.
Imported R05856, B03795, C00045, RA00532, C03982 and C04872 through the existing
source-verified opening bridge. Workspace 11 now has seven ACTIVE rehearsal loans;
2,456 of the 2,463 active source candidates remain unimported. The sample spans
four series, gold/silver/mixed collateral, older/recent dates and January 31.

Explicit simulation retains original principal and assumes zero unpaid interest
and fees at September 12, first month/all interest through cutover settled, and
collateral in custody. Calculated cumulative interest remains in the continuation
baseline, preventing recharging pre-cutover amounts. These are not verified
production balances or custody; no historical receipts or appraisals were invented.
The retired rehearsal product is reused. R/B/RA series now allow existing-loan
release numbering while inactive legacy licences continue denying new lending.

All six passed rolled-back opening previews, independent source re-extraction,
signed admission, exact retry, zero additional interest at cutover, next-anniversary
boundary checks, full-release rollback with unchanged counters, export and persisted
ACTIVE/detail HTTP 200 checks. The entire six-loan admission transaction committed
only after those domain checks passed; subsequent reads verified persistence.
No releases were saved. B03343 initially failed its nonpositive source valuation;
it remains held and B03795 replaced it. An overlong operator terms reference was
shortened, preserving the full assumptions in review_reference. No rules relaxed.

Private evidence: `outputs/jcl13-batch-rehearsal-20260915/review.html`,
`verification.json`, per-loan exports and COMPLETE. Eleven payment cases and 185
inactive-borrower cases remain held (groups can overlap). No application/schema
change. Next is owner inspection of this sample and real checkpoint reconciliation
before production admission; this is not a full-portfolio import or load test.

## jcl-13 one-loan rehearsal completed (2026-09-15)

The user confirmed rehearsal scope. C07432 is now the single operational loan in
Workspace 11: loan 23, ACTIVE, opening checkpoint September 12. Explicit rehearsal
assumptions are principal 12,000, unpaid interest/fees zero, first month paid and
collateral in custody; these are not verified production facts. Valuation remains
UNVERIFIED and gross weight unknown. A retired rehearsal servicing product and
release-enabled C series support existing-loan servicing; the inactive legacy
licence still prevents new lending. The other 2,462 candidates remain unimported.

The first attempt rolled back its entire loan transaction because the verification
script expected RELEASED instead of the domain's CLOSED state. Reused the saved
setup and reran only admission with the corrected assertion. Independent checks
after commit confirm exactly one active loan and one opening event, list/detail
HTTP 200, idempotent retry, 12,000 current release quote and 240 additional interest
on October 13. Full release was exercised inside a rollback: no release or counter
consumption persisted. Opening export succeeded and declares earlier history
unavailable. Evidence: `outputs/jcl13-opening-rehearsal-20260915/review.html` and
`verification.json`. No application code or schema changed.

Next: inspect C07432 in jcl-13 Loans, then reconcile real checkpoint balances,
paid coverage and custody before broader admission. Opening servicing remains
limited to the supported collection/full-release and coupled reversal paths.
The preparation and Party sections below describe their earlier checkpoints.

## jcl-13 active-loan preparation (2026-09-15)

After the user requested the next migration step, re-extracted the September 12
jcl dump and matched all 2,463 active candidates to 1,093 imported borrowers in
Workspace 11. Created two inactive legacy licence references and seven inactive
series through Loans services, reserving prior known source number ranges. Source
licence validity stays unknown and these references cannot authorize new lending.
No product, loan, financial event, appraisal or obligation was created.

The report is `outputs/jcl13-active-preparation-20260915/review.html`, with source
evidence, new destination IDs, all candidate mappings and proposed pilot C07432
(source principal 12,000; one gold item; no source payment rows). Snapshot interest
illustrations remain unapproved diagnostics; opening balances and cutover remain
unset. Eleven payment-bearing loans retain their reconciliation hold. Another
185 loans reference source-inactive borrowers; no borrower status was changed.
Independent read-only checks verify all borrower bindings, reserved counters,
unknown licence dates, denied new lending and zero financial rows.

The user subsequently confirmed a rehearsal; the one-loan result is recorded above.
Real balances/fees, paid coverage and custody still need reconciliation before
production admission.
No source absence is interpreted as zero debt or confirmed collateral possession.

## jcl-13 delegated conflict resolution and import (2026-09-15)

The user delegated resolution and import. Preserve distinct legacy customer IDs
without merging same-name source records or asserting verified real-world identity.
Recorded batch-specific name decisions through the existing review service. The
two relationship validation messages concern one customer (`contact_customer:3718`),
not two customers: its unknown R/o relationship and related-name projection are
left blank, with exact original claims retained in the replacement CSV's unmapped
source columns and completed review evidence. Both addresses for customer 6272
are retained with neither selected as default; original true flags remain evidence.

The import completed through existing restricted-runtime Party services, with one
transaction per bounded batch: 5,880 Parties, 1,893 phones and 3,992 addresses.
All 12 logical batches are COMPLETED; two superseded batches were cancelled and
replaced with corrected source files. All 900 matching-name groups retain separate
source IDs. Customer statuses remain 4,210 ACTIVE and 1,670 INACTIVE. Completed
batch receipts, reviewed inputs, decisions and verification are in
`outputs/jcl13-party-import-20260915/`, with COMPLETE and `review.html` present.
Do not rerun the one-shot import script or duplicate these records.

Independent read-only verification passed: exact source customer names/statuses,
5,880 distinct source-to-Party bindings, all 5,885 child parent links, unknown
relationship fields, both retained non-default addresses, all 12 completed review
pages returning HTTP 200, and no Party/child rows in jsk-13 or lsp-13. No operational
loans existed in jcl-13 at that checkpoint. Existing archive evidence was not changed. The synchronous
child batches took several minutes each; this run establishes correctness, not a
bulk-throughput guarantee. Next is destination setup and a reconciled active-loan
opening pilot, separately from historical archive acceptance.

## jcl-13 Party import prepared, not committed (2026-09-15)

Prepared the full jcl customer set from the verified September 12 dump for
Workspace 11 (`jcl-13`), owned by punba: 5,880 customers (including 1,670 inactive),
1,893 phone rows and 3,992 addresses. Staged and validated 12 bounded CSV batches
through existing Party portability services in one restricted-runtime transaction:
six master, two phone and four address batches. Same-name and same-parent peers
remain together across the 1,000-row batch boundaries. Exact source rows, CSVs,
proposed mappings and validation evidence are retained privately in
`outputs/jcl13-party-preparation-20260915/`; start with `review.html` and
`decisions.html`.

Master validation finds 1,226 valid rows and 4,654 rows in 900 matching-name groups.
No keep-separate decisions, merges or source identity bindings were made at staging.
One customer produces two relationship errors: unsupported R/o and a relationship
label/name pair that fails Party validation. Proposed INDIVIDUAL/credit-hold defaults are explicit;
legacy R/W/S categories remain source evidence, not imported legal types or roles.
All child batches require parent imports and revalidation. Independent source-key
checks also expose one customer with two default addresses; flags remain unchanged.

Independent read-only verification confirms all 12 persisted batch fingerprints
and summaries, and all review views returned HTTP 200. Party, phone, address,
source identity and operational-loan counts remain zero in jcl-13. The archive is
separate: the live database now shows one completed archive pilot and two staged,
observed during verification; this Party task did not alter archive records.
Next: review matching-source-name decisions, the two relationship errors and
default-address choice, then confirm master import before revalidating children.

## Archive pilots staged under punba (2026-09-15)

The user selected `punba` as owner. Created `jcl-13` (Workspace 11), `jsk-13`
(12), and `lsp-13` (13) through `create_workspace_from_form`, including canonical
ownership, Owner Membership, localhost domains and creation audit. Source mappings
remain jcl, jsk and lakshmipawnbroker respectively. Applied the two previously
tested archive migrations: Loans 0013 and data portability 0014, with forced RLS
and guards. Earlier notes that these migrations are unapplied are historical.

Staged exactly three selected pilot documents in each Workspace through the archive
service under the restricted runtime role. All nine documents match the reviewed
file fingerprints. All nine review views returned HTTP 200 with no-store caching.
Creation and staging completed in one transaction. Independent read-only checks
verified persisted ownership, three source-matched STAGED batches per Workspace,
and RLS visibility excluding the other Workspaces. Accepted historical evidence,
operational loans/events and Parties are all zero in the new Workspaces.

The handoff is `outputs/archive-pilots-staged-20260915/review.html`; its manifest
records Workspace IDs, source identities, file fingerprints and review paths.
No acceptance tokens are saved. Sign in as punba and review the staged batches
before explicit historical retention acceptance. No bulk import or active-loan
admission was performed. The September 13 offline reports remain unchanged.

## Three archive destinations confirmed; owner pending (2026-09-13)

The owner selected `jcl → jcl-13`, `jsk → jsk-13`, and explicitly clarified
`lakshmipawnbroker → lsp-13` (not `srilakshmipawnbrokertmd`). These destination
Workspaces do not yet exist. Creation awaits the requested owner choice: existing
`jcl`/`jsk` belong to `rajesh`, while recent migration test Workspaces belong to
`punba`. Do not infer ownership or copy either account's authority silently.

Separate offline reports are complete for all three sources in the current dump:
26,474 jcl, 3,773 jsk, and 8,577 lakshmipawnbroker released candidates pass the
unchanged archive schema, with no held documents. The latter two retain unknown
normalized weights; the jcl-only owner attestation is not applied across sources.
Raw timestamp findings affect 24, 8 and 54 loans respectively. Three pilots per
source are linked in `outputs/archive-pilots-20260913/review.html`, with exact
source/destination mappings and SHA-256 fingerprints in its manifest. Every ZIP
passed CRC verification and each pilot matches its ZIP member bytes exactly.
The new source runs blocked all application database queries. No records staged
or accepted, no Workspaces created, and no main database migrations applied.
Read-only migration planning confirms exactly the two prepared archive migrations
are needed for in-app staging. Next: resolve ownership, create the three named
Workspaces through the existing control-plane service, and stage the selected
source-matched pilots for owner review.

## Archive exception review and pilot proposal (2026-09-13)

Adapter revision 2 resolves the 121 description holds by mapping CR/LF/tab runs
to one space in normalized facts, with exact before/after provenance. Raw source
rows remain byte-identical to the first report; other controls are still rejected.
The fresh private report is
`outputs/jcl-closed-archive-review-20260913-v2/case-review.html`.
All 26,474 released-loan candidates pass the unchanged archive schema; zero held.
Raw timestamp review identifies 24 loans with findings: 23 release-before-origination,
13 payment-before-origination, and one future origination (overlapping counts).
These source claims remain unchanged, including R09911's December origination
against March payment/release timestamps. Calendar-date-only checks had shown
16 closure-order findings; raw timestamps expose additional same-day contradictions.

Three unaccepted pilot files are selected: R00001 (unknown payments), R02505
(recorded payments), A00049 (normalized description). Selection excludes source
ERRORs and timeline findings and is a workflow proposal, not a representative
sample or financial certification. Destination remains unselected; no staging,
acceptance, main database migration or Workspace mutation occurred. The full
source run blocked application database queries. All 39 focused tests pass;
ZIP CRC, pilot-to-ZIP byte equality, source-file equality, syntax and import
boundaries pass. Next: choose the destination for reviewing this three-record
historical-retention pilot. See the [archive flow](flows/historical-loan-archive.md).

## Read-only closed-loan source preparation (2026-09-13)

Prepared the current September 12 `jcl` dump through the offline
`preview_legacy_closed_archive` command, with all application database queries
blocked. The private report is
`outputs/jcl-closed-archive-preview-20260913/review.html` (completion marker present).
Of 26,474 source-released loans, 26,353 pass the closed-evidence schema and 121
are held because collateral descriptions contain control characters. The other
2,463 unreleased loans are outside this archive selection. Zero records were
accepted; no main database migrations or Workspace changes were performed.

All 96,711 extracted source rows remain in the report, including held evidence.
Candidates preserve unknown original principal and settlement balance. Among valid
candidates, 10,624 lack structured collateral, 15,426 lack payment rows, and 16
have closure-before-origination claims. R09911's future origination is flagged.
The 36 focused adapter, dump parser and archive contract tests pass; every valid
candidate passed encode/parse/review and the resulting ZIP passed CRC verification.
Next: review held collateral and source exceptions, then select a small historical
retention pilot and destination before acceptance. See the
[archive flow](flows/historical-loan-archive.md#offline-source-preparation).

## Historical closed-loan archive (2026-09-13)

Owner-authorized slice 2 adds `loan-closed-evidence/1` and a separate historical
archive upload/review/browse/export flow. Loans owns immutable HistoricalLoanEvidence;
data portability owns staged LoanArchiveBatch. Both have direct Workspace ownership,
forced RLS and SQL guards for immutable evidence and same-source batch results.
Unknown and contradictory source facts can be retained after explicit owner review;
no operational loan, Party, payment, custody or obligation row is created. Identical
retries reuse a snapshot; changed snapshots append. Current financial import and
opening/restore rules remain unchanged. See the
[decision](adr/2026-09-13-historical-closed-loan-archive.md) and
[flow](flows/historical-loan-archive.md).

Migrations are prepared locally: Loans 0013 and data portability 0014 create each
table together with ownership/RLS/guards. They have not been applied to the main
database. No model-state changes remain according to the owner-settings migration
check. All 78 focused archive, registry/RLS, generic import containment, complete
history and opening import/restore tests passed in 66.454 seconds in isolated
`test_rokkad_closed_archive_20260913`, which was destroyed afterward. Evidence:
`.tmp/closed-archive-tests-final.log`. The initial run found two test assumptions
(stored permission alias and old registry count); both are corrected. The four
pure contract tests also passed separately. System check, 569-file import guard,
direct syntax/boundary/whitespace checks on 13 affected Python files and 393 local
links across 18 docs pass. No real-source import or deployment performed.

## Frozen opening portability contract (2026-09-13)

The owner-authorized contract slice freezes 18 row kinds and 185 fields for
`loan-opening-export/1` in Loans-owned `opening_contract.py` and a published row
definition. Export and restore share the fixed inventory; decoding no longer
reads `_meta.fields`, model nullability or model converters. Existing wire names,
unknown values, nested evidence, canonical hashes and admission checks remain.
See the [decision](adr/2026-09-13-frozen-opening-wire-contract.md).

Two synthetic old-implementation exports were captured in a separate disposable
database (2 capture tests passed). All 93 focused export/restore/import, staging,
validation and complete-history regression tests passed in 71.894 seconds in
`test_rokkad_opening_contract_20260913`, which was destroyed afterward. Both frozen
fixtures restore and re-export with equal financial meaning. All 6 standalone
contract tests also passed, including the subsequently added published-definition
check. Evidence: `.tmp/opening-contract-tests.log` and
`.tmp/opening-contract-baseline.log`. Runtime system check, syntax/boundary/whitespace
checks on all 5 affected Python files and 332 local links across 15 docs pass.
No schema migration, deployment or real financial import.

## Portability validation classification (2026-09-13)

Owner-authorized slice 0B adds Loans-owned reporting categories for malformed
data, missing evidence, historical inconsistency and operational readiness.
Opening results preserve all existing reconciliation gates and ERROR severities;
separate readiness checks remain NOT_EVALUATED. Offline reports show categories
and occurrence counts. Complete-history schema/command/setup failures carry
structured metadata through preview rollback, and upload/review displays it.
Exception messages, accepted documents, canonical hashes, approval payloads,
financial rules, permissions and database schema remained unchanged in that slice.
Closed facts without settlement evidence still fail complete-history admission;
the separate historical archive is recorded above.
See the [decision](adr/2026-09-13-portability-validation-classification.md).

Validation: all 94 focused validation/report, history/opening import, restore,
legacy staging and native lifecycle/economics tests passed in 96.987 seconds in
the separate disposable `test_rokkad_validation_categories_20260913` database,
which was destroyed afterward. Evidence: `.tmp/validation-classification-tests.log`.
The initial 29 pure checks also passed. Runtime system check, the 569-file import
guard, direct syntax/boundary/whitespace checks on all 11 affected Python files
(including untracked files), all 60 opening issue classifications, 337 local links
across 16 docs and affected documentation whitespace pass. No deployment or real
financial import was performed by that classification slice. Later delivery is
recorded above.

## Generic Loans import containment (2026-09-13)

The owner-authorized audit slice 0A is implemented locally. All Loans models are
excluded from generic import choices and rejected before upload parsing and at
the import resource factory. The generic import route now requires matching
Workspace context, ACTIVE lifecycle and current data.view/data.import/
workspace.settings.manage grants; role names no longer authorize that write.
Generic export inventory and the supported staged Party/Loans workflows remain
unchanged. No schema, financial calculation, RLS or normal business data changes.
See the [decision](adr/2026-09-13-generic-loans-import-containment.md) and
[follow-up plan](plans/loans-portability-audit-followup.md).
Validation: all 77 focused generic-import, Party portability, complete-history and
opening-import tests passed in 61.206 seconds in the separate disposable
`test_rokkad_import_boundary_20260913` database. Runtime system check, the
569-file import guard and its four unit tests, 355 local links across 15 docs,
and affected diff whitespace pass. Evidence: `.tmp/import-boundary-tests-final.log`.
The first run exposed the pre-existing generic-create sequence-reset limitation;
restricted-role tests now preserve that denial and prove rollback, alongside
permitted update and cross-Workspace denial. No runtime privileges were broadened.
Later historical acceptance/admission slices have not begun.

## Loans architecture audit

Documentation audit completed (2026-09-12), against the working tree over
`92aa3600`, including existing uncommitted work. Start with
[the audit and prioritized findings](architecture/loans-portability-audit.md);
it links the lifecycle/dependency map, 60 classified semantic rules, applicability
and example matrices, declared schema inventory, alternatives, proposed target
and [incremental follow-up](plans/loans-portability-audit-followup.md).
The principal gap is accepted historical evidence separate from operational
admission. Existing complete-history and opening writers already preserve part
of that distinction; outcome-only closed history has no accepted destination.
The audit also flags a P0 integrity/authorization design exposure: reachable
generic model import still offers Loans models outside command admission and
uses role-name authorization. No customer-data exploit or cross-Workspace breach
was attempted or established. Other key findings concern export/recovery access,
ORM-coupled opening contracts, limited export coverage and historical setup coupling.

Validation: the isolated focused run reports 54 tests passed in 60.485 seconds,
covering history, opening restore/validation, evidence/RLS guards and generic
registry behavior. Its test database was separate from normal development data.
PowerShell marked normal stderr progress as a native error and returned 1 despite
the test runner's `OK`; the audit records that distinction. All 564 checked local
links across 21 documentation files and documentation whitespace/fences pass. Documentation-only
delivery; no application/schema/migration changes or financial import by this task.
All proposed implementation awaits owner review. Current jcl preparation and its
separate decisions/holds below are not superseded by the audit.

## Current checkpoint

Current jcl preparation completed in isolated test Workspace 10 (2026-09-12),
`test-jcl-current-20260912`, through normal Workspace/Party/setup services under
the restricted runtime role. Private searchable review and checksummed files:
`outputs/jcl-current-preparation-20260912/review.html`.

Imported 1,093 customers, 755 contacts and
1,104 addresses. All customer source IDs have separate Party
bindings; 613 matching-name source records were explicitly reviewed and retained.
Two different addresses for one customer were both source defaults. Both addresses
were retained with destination default unset; raw flags and that adaptation remain
in provenance. The initial failed attempt rolled back before the corrected import.

Added a bounded reviewed-name decision to the existing Party preview/commit flow,
with per-record source digests, exact matching destination IDs, reason, audit and
warning acknowledgement. Stronger identity checks and replay guards remain; these
decisions cannot become reusable presets. No models or migrations were added. See
the [decision](adr/2026-09-12-reviewed-party-name-collisions.md).

Prepared all 2,463 active-source loan packages with exact borrower links, readable
numbers, original billing dates and recorded tenure (three-month fallback for 193
missing/zero tenures). Workspace 10 has two inactive legacy licence references,
seven series, a retired historical-servicing product, the approved test monitoring
thresholds and the owner test gold quote of INR 15,500/g pure metal (buy/sell).
Loan counters preserve every known source number: C07433, RA00533, A10000,
H09991, LEGACY6-10000 and exhausted R/B at 10001. H and LEGACY6 are inactive. These
licence references cannot authorize new lending.

The owner explicitly kept all 11 payment-bearing unreleased loans on hold until
checked. Each has a full-principal payment marked with release but no release row;
no settlement or custody was invented. For the other 2,452, the September 12
illustration totals principal 45271218 and interest
4891222, assuming original principal unchanged, first month
paid upfront and no later collections/concessions. Fees, custody, paid coverage,
remaining obligations and financial approval remain unconfirmed. Complete gold
valuation proposals cover 1,659 loans; the rest lack at least
one current metal value. No financial loan, event or appraisal was committed.
Workspace 9 still has its unchanged C00121 pilot and one appraisal.

Validation: eight new reviewed-name tests passed, alongside Party/preset regression
checks. Read-only restricted-RLS verification checks exact parent links, completed
batch pages and private cache headers, zero financial writes, number guards and
Workspace 9 preservation. The local report checks search, pagination, all 11 holds,
valuation filtering, collateral details and file links. Next: review the proposed
balances/custody and fees for the 2,452; financial cohort staging/commit and current
appraisal execution follow separate approval. The 11 remain held. New-lending
activation and limited-evidence released-history support remain separate pending
work; the deferred history filter is not part of this slice.

Previous checkpoint:

Current jcl dump received and compared (2026-09-12). Actual supplied path is
`C:\Users\rajes\backup_20260912_224652.sql`; its 11,628,020 bytes are a PostgreSQL
custom archive despite the extension. Private verified copy and receipt are under
`outputs/jcl-current-source-20260912/`; SHA-256
`e33f78f3fb96e8c23a029f9b933492e02e2a2af7b27e0cf20686b178fe91a27f`.
The stable legacy installation namespace and selected jcl schema are unchanged.
Full source review is `outputs/jcl-current-preview-20260912/review.html`; comparison
and per-record/per-loan changes are in
`outputs/jcl-current-comparison-20260912/review.html`. September 12 is an explicit
diagnostic comparison date, not an approved financial cutover.

New source: 96,711 selected rows, 5,880 customers, 28,937 loans, 18,441 collateral
items, 11,085 payments, 26,474 releases, 2 licences and 7 series. All 2,463 unreleased
loans have complete collateral under the selected rule and no source validation
errors. Their stored principal totals 45,351,608, not a certified opening balance.
11 active loans have payment history requiring reconciliation before the unchanged-
principal opening path; 2,452 have no payment rows, which is not proof of no payment.
1,093 borrowers serve the active set; 613 fall in 189 repeated-name groups. Released
records partition into 15,066 retained and 11,408 collateral exclusions. One
released/excluded loan R09911 is dated 2026-12-16 and remains an explicit source
exception. Latest nonfuture loan date is September 12; payment/release business
dates reach September 5 in Asia/Kolkata (September 4 in UTC).

Of the old 2,446 prepared loans, 2,249 are now released, 3 are absent and 194 remain
unreleased; 2,269 current active loans were outside that old preparation. C00121 is
released in the new source on 2025-01-21, conflicting with the earlier active pilot.
No loan or financial evidence was overwritten. Cancelled the five old unfinished
Party batches through the normal service in Workspace 9 after verifying their
preserved source artifacts; one audit records both dump hashes and batch IDs.
The receipt is `outputs/jcl-current-source-20260912/superseded-batches.json`.
The earlier preparation report is historical, not a current import plan.

Current source numbering requires C07433, RA00533 (new series) and exhausted
R/B at 10001 under a 10000 ceiling. H's floor stays at least 9991 from the earlier
observed source, although its current maximum is lower; never rewind a counter
because a source row disappeared. Destination counters/setup were not changed.
A fresh isolated rehearsal destination is recommended for this current snapshot
so the obsolete pilot need not be rewritten; it has not been created or approved
as a live destination. Same-name identity resolution, opening balances/fees/custody,
the 11 payment-bearing active loans and bulk service composition remain pending.

Adapter compatibility was extended only for observed, source-code-verified shapes:
optional exact `girvi_loanitem.is_repledged` and `girvi_series.loan_type` columns.
They stay in raw facts/hashes. Repledged/unknown flags propagate a source hold to
the loan; series types other than explicit Given do likewise. This dump's 18,441
flags are false and all seven series are Given. Scoped inventory ignores unrelated
schema identifiers (the archive has jsk-knb), while selected-schema/table checks,
exact column variants and cross-schema COPY rejection remain strict. General
inventory mode still rejects unsupported identifiers. No source SQL/code executed.

Validation: 39 adapter and source-bound opening tests passed, including both known
column shapes, unknown columns, sibling schema scope, repledge/type holds and
existing staging guards. The full real extraction completed through the existing
bounded command. No current-source Party or Loans batch has been committed.

Previous checkpoint:

Active jcl batch preparation saved (2026-09-12), following owner authorization.
Private handoff: `outputs/jcl-active-preparation-20260912/review.html`, with all
2,446 new active-loan technical proposals and a checksummed completion manifest.
This advances the earlier preview to actual destination setup and Party staging;
no additional financial loan, customer or appraisal has been committed.

Prepared the second inactive legacy licence reference (ID 7/revision 7), five
remaining series (R 11, H 12, LEGACY6 13, A 14, B 15) and their separate loan/release
sequences. Existing C remains series 5. Loan ranges reserve every source suffix,
including released, held and excluded loans: R08066, H09991, LEGACY6-10000, A10000,
B10001 (exhausted at 10000), C00123. C's unused TEST-C- prefix was changed to C,
width 5, preserving its existing 999999 ceiling and independent release sequence.
New series use the ordinary 10000 ceiling, not an interpretation of source
max_limit. H and LEGACY6 remain inactive. These are historical servicing series;
all new-loan issuance remains denied by unknown-validity legacy references. A
verified licence and coordinated successor numbering/lending setup remain pending.

Added the ordinary Loans `reserve_sequence_through` service: matching Workspace
and setup access, existing sequence row lock, bounded evidence/range validation,
forward-only counter update and audit. Exact/lower retries cannot rewind later
allocations; reaching the ceiling produces the exhausted marker. No migration.

The active candidates reference 1,237 customers: existing Party 8 is retained;
1,236 masters, 622 contacts and 1,203 addresses are staged in five ordinary Party
batches (at most 1000 rows each). Equal-name groups stay in one chunk so splitting
cannot bypass duplicate detection. 769 master rows have duplicate-name conflicts,
including 2 also matching the existing Party name; 467 pass individual checks but
their batches are not commit-ready. There are 230 repeated-name groups across 770
in-scope source customers, linked to 1,552 candidate loans. Distinct source IDs and
borrower links are preserved; no automatic merge, rename or duplicate-guard bypass.
The full-source R/o conversion hold is outside this active batch. 1,824 child rows
await parent import; one address resolves to the existing pilot borrower.

Proposed principal is 21,651,825 and illustrative April 9 interest is 11,359,106
for the 2,446 new candidates. Fees, cohort balance/coverage/custody confirmation
and opening obligations remain unresolved. Actual review fields stay null where
unconfirmed; proposed figures are separate from accepted opening evidence. Test
monitoring policy 4 is referenced. Current gold estimates cover 1,751 candidates;
695 lack complete current valuation. Quotes must be checked afresh at execution;
no bulk appraisal or financial staging/commit orchestration was added.

Validation: 29 numbering, pilot-readiness and licence/setup tests passed. All
2,446 source proposals match freshly rebuilt candidates from the hash-verified
records; every destination setup/number check passed. Read-only restricted-runtime
verification confirms five review pages HTTP 200/no-store, saved batch hashes and
summaries, six reserved sequences and new-origination denial. C00121 remains the
only loan, with one financial event and one appraisal. An initial preparation run
rolled back fully on a child mapping error; its incomplete private artifact folder
is marked `-rolled-back` and has no completion marker. Use only the final handoff.

Previous checkpoint:

Full jcl migration preview prepared (2026-09-12), without staging or application
writes. Freshly extracted the supplied archive through the existing offline
adapter, verified its hash and reused the jcl-owner/2 diagnostic rules at the
April 9 rehearsal checkpoint. Private output is
`outputs/jcl-migration-preview-20260912/migration-review.html`; the same directory
contains full per-loan/customer/contact/address proposals, setup mappings, a
read-only Workspace 9 reference, raw source evidence and a checksummed completion
manifest. Two one-time composition/render scripts live under `.tmp/`.

Reconciled 54,713 selected source records: 5,431 customers, 1,324 contacts, 3,378
addresses, 2 licences, 6 series, 19,240 loans, 8,644 items, 769 payments and 15,919
releases. Loans partition exactly into 3,321 unreleased and 15,919 released.
The authorised incomplete-collateral rule excludes 873 unreleased and 11,299
released loans (12,172 total); their source records remain preserved in the report.
Retained active 2,448 = 2,446 new review candidates + C00121 already imported +
R07743 held for inconsistent loan/item principal and monthly interest. Stored
principal for the retained active set is 21,678,041, including the held loan.

The 2,447 calculable active loans have stored principal 21,656,825 and illustrative
April 9 interest 11,360,806. These are not approved cohort opening balances: the
calculation assumes unchanged principal, first-month coverage and no subsequent
collections. C00121's confirmation cannot approve all other loans or custody.
Tenure is three months: 298 recorded, 2,150 owner-directed missing-tenure fallbacks.
Retained collateral: Gold 1,775 items / 10,884.170g net; Silver 688 / 75,181.500g;
Bronze 7 / 29,500g. The approved test gold price gives 126,588,678.25 aggregate
metal estimates (including source holds); 1,753 loans have complete estimates and
695 do not. Silver needs a quote; Bronze is unsupported by the current Rates lookup.

Existing Party validators accept 5,430 customer conversions and all 1,324 contact /
3,378 address proposals. One R/o relationship label remains held. Case/slash
relationship variants are normalised; optional relationships without a named
person remain unset with raw labels retained. Defaults and every transformation
are explicit proposals, not hidden source edits. Existing source borrower identity
and C00121 resolve to the pilot; all 19,240 source loan numbers are unique.
The second licence reference and five series remain to prepare. Blank source
series is proposed as LEGACY6, preserving the original loan numbers.

All 4,620 retained released records are held for the unimplemented limited-evidence
released-history path. 727 have payment rows, 3,893 do not; 11 have linked source
date errors. Release dates are not treated as reconstructed receipts.
No source loan/payment/release date is later than 2024-10-10. The owner confirmed
that this jcl dump is for testing and will supply a fresh dump with the latest
activity later. Source freshness therefore does not block the rehearsal. The
later dump must be re-extracted and reconciled before live cutover; these rehearsal
estimates are not confirmed production balances. No cohort financial commit is
authorised by this preview. Generated preview artifacts retain their original
snapshot; this clarification supersedes their pending source-freshness question.

Verification: source counts and four principal partitions independently reconcile
to the fresh adapter output; all source loans are represented once, pilot lookup
and exception identity checks pass. Existing validation ran inside PostgreSQL
READ ONLY under restricted rokkad_runtime. All 11 completion-manifest hashes and
9 local report links verified. Node checks exercised search, pagination, state /
disposition filters and customer exceptions over all 19,240 loan and 5,431 customer
rows. No business code or financial state changed.

Previous checkpoint:

Current valuation completed for C00121 (2026-09-12): saved owner-approved test
Gold INR 15,500/g 24K buying and selling quote (rate 5), then recorded a current
RATE_BASED appraisal (9/version 1) for 34,875 = 3g net x 75% x 15,500. Monitoring
policy 4/version 1 is active. Current eligible value/LTV now resolve. The loan
remains ACTIVE, full-release quote 7,300, with its single opening financial event;
accepted source review, old unverified value and frozen financial policy are intact.

The existing appraisal service/form now offers Rate-based appraisal. It requires
a reviewed current quote ID, configured price freshness and the exact calculated
value; quote/value changes fail, as do existing authorization/version/custody
boundaries. The record clearly identifies a rate-based assessment, not physical
inspection. Later rate changes do not rewrite it. No migration is needed.
Bulk import orchestration is still to compose this ordinary Loans command with
source conversion; generic import does not silently create current appraisals.
See [the decision](adr/2026-09-12-rate-based-collateral-appraisal.md).

Validation: 35 affected reappraisal/opening-restore/pilot regressions passed across
the suite and final corrected-fixture rerun. The new first rate-based appraisal
round trip retains method, amount and source-scoped quote context. Actual owner
loan-detail and appraisal-history views render HTTP 200 with 34,875; the saved
monitoring assessment is CURRENT. The real appraisal exports and validates, and
no loan financial event was added.


Previous checkpoint:

Pilot monitoring configured and recognisability accepted (2026-09-12): the owner
confirmed C00121 is recognisable and approved the proposed test thresholds.
Created Workspace 9 default monitoring policy 4/version 1 through the existing
service under restricted rokkad_runtime, effective September 12. Values: grace 3,
maturity warning 30 days, DPD watch/escalation 1/90 days, LTV .75/.80/1.00,
rate/appraisal freshness 7/90 days. Current assessment resolves this policy;
SUBSTANDARD/CRITICAL reflects the reviewed old maturity, not an import failure.
The full-release quote remains 7,300 and no financial records changed.

The owner proposes using current rates to value collateral at import and supplied
15,500 INR/g for 24K gold. The owner subsequently approved the same selling price; rate 5
is saved in Workspace 9. C00121's recorded 3g net/75% purity yields a
34,875 metal estimate. The later RATE_BASED appraisal satisfies the frozen LATEST_APPRAISAL
policy; see the current checkpoint. Rates alone never silently create an appraisal.

Previous checkpoint:

C00121 operational pilot improvement (2026-09-12): owner completed the opening
import into Workspace 9 (loan ID 16, batch COMPLETED). Corrected its generated
display number to C00121 through an owner-authorized, audited command; original
financial/source evidence and batch approval remain unchanged. Future opening
inputs can explicitly propose `setup.local_loan_number`, with existing-number and
future-sequence checks. Older inputs and exact retries remain compatible.

The ordinary loan detail now leads to Collect and release, shows the actual dated
collection quote and original maturity/grace, and distinguishes the brought-forward
balance from unposted collection interest. Unsupported repayment/accrual/renewal
links and the expected native-accrual error are removed for openings only.
Owner list, detail and release views rendered HTTP 200 under read-only runtime
Workspace context, showing C00121 and the correct destinations.

Validation: 44 targeted opening/pilot/import/release/restore tests passed under
restricted-role fixtures; 11 native workflow/document regressions also passed.
Migration drift and supported-app boundaries passed; 300 curated documentation
links passed. A rolled-back rehearsal on the actual pilot collected
7,250 with a 50 interest concession, returned the collateral, rendered a release
receipt PDF carrying C00121, reversed settlement/custody, and validated exported
evidence. The retained loan is ACTIVE with only its original opening event; no
collection, release, PDF issue or release-number advancement was committed.
The September 12 quote is 7,300 (principal 5,000; interest 2,300 including 600 since
cutover). Current appraisal/LTV remain unknown by design.

Monitoring setup was subsequently approved and saved; see the current checkpoint.
Production migration readiness remains separate from this isolated pilot. See the
[operational-readiness decision](adr/2026-09-12-opening-pilot-operational-readiness.md).

Previous checkpoint:


Settings sidebar links fixed (2026-09-12): the workflow and document URL tags
were printing their paths instead of assigning the variables used by the adjacent
links. Restored explicit URL assignments using the sidebar Workspace slug. The
owner's real Workspace 9 workflow and documents pages return HTTP 200; both
sidebar instances have correct destinations/active states and no raw path text.
No loan/import state changed.

Previous portability checkpoint:

Legacy evidence gaps implemented; C00121 staged (2026-09-12). Inactive legacy
licence references now retain unknown dates under database constraints and identity/
revision/disbursal guards. New lending, activation and ordinary amendment/renewal
cannot use them. V2 explicit UNVERIFIED valuation evidence retains an old amount
and optional source date without creating an approved appraisal or current LTV.
Full settlement of an opening may return all collateral without valuation; native
and partial-release checks stay strict. Export/restore preserve unknown evidence
and restore a later first appraisal correctly. Registers, documents and review/detail
pages label unknown validity and historical source values.

Validation: 91 opening, adapter, licence and reappraisal regressions passed; 36
numbering, partial-release boundary, readiness, report and document checks passed
after correcting the document projection's compatibility with existing fixtures.
The nine document tests passed on the final rerun. Four modified templates compiled;
migration drift check found no changes. See the
[decision](adr/2026-09-12-legacy-opening-unknown-evidence.md).

Applied exactly the four pending normal-database migrations using owner settings:
portability 0013 and Loans 0010/0011/0012. Using restricted `rokkad_runtime`, prepared
the source-bound borrower, inactive legacy reference, series and retired compatible
product in isolated Workspace 9, then freshly verified the dump and staged C00121.
The READY preview shows principal 5,000, unpaid interest 1,700, fees zero and one
collateral item. HTTP GET of the real owner review returned 200 and displayed the
source loan, unknown-evidence labels and preview action. No financial loan exists
yet: the full writer preview rolled back. The remaining step is owner review and
confirmation of the complete staged input in Import Loans > prepared legacy openings.
The private proposal/review includes its exact route and mappings. Original dump
and owner workbook are unchanged; no production cutover was approved.

Previous source clarification checkpoint:

C00121 custody/grace and source gaps clarified (2026-09-12): owner confirmed
custody at the April 9 rehearsal and three grace days. The source valuation is
old; no appraisal date or current value was confirmed. Licence validity was not
recorded because that old field was decorative. Saved the verbatim clarification
in the private proposal and populated custody/grace in the candidate. Existing
validation now passes those fields as well as confirmed balances and coverage.

The remaining source gap is concrete: opening validation requires a dated
appraisal, while destination history setup requires a licence revision covering
the original loan date. Preserve the old undated value and licence label as source
claims; do not invent dates, treat the old value as current, or weaken ordinary
origination checks. The next bounded adapter/domain review is truthful treatment
of these missing historical facts. Party/setup mappings and remaining obligation
rows are also pending. No loan was staged/imported, no schema or app code changed,
and no application DB writes were made in this checkpoint.

Previous balance checkpoint:

C00121 opening balance confirmed (2026-09-12): the owner replied `correct` to
the 2026-04-09 rehearsal balance of principal 5,000, unpaid interest 1,700 and fees
zero, with the first month paid upfront and no subsequent payments or concessions.
Recorded that exact question/answer in the private pilot proposal, populated its
cutover, balances, unchanged single-item principal and v2 coverage checkpoint,
and updated `outputs/legacy-pilot-jcl-20260912/pilot-review.md`. This confirms the
rehearsal inputs, not a production cutover or final financial commit.

The existing document validator passes the balance, cutover and continuation
checks. Remaining fields are custody/appraisal, destination Party/licence/series/
product mappings, remaining obligations and grace days. Validation is retained in
the private `pilot-validation.json`; the full document remains unreconciled and
unstaged. No application DB rows or migrations changed in this checkpoint.

Previous maturity checkpoint:

Owner-directed maturity fallback (2026-09-12): the latest instruction preserves
recorded maturity terms and uses three calendar months from the original loan date
where maturity is missing. This supersedes the no-fixed-date proposal below.
C00121's prepared review now uses 2025-01-10 from 2024-10-10, with the owner
instruction retained separately from unchanged dump facts. No new model or
no-fixed-date feature is needed for this pilot.

The jcl source bridge now permits zero source tenure only with reviewed tenure
three and the explicit owner terms evidence reference. It preserves positive
recorded tenure and rejects conflicting or invalid values. The signed immutable
wrapper retains raw tenure, selected maturity and decision basis; export carries
that evidence. Browser review explains the fallback and overdue effect. Interest
continues from its original anniversary; cutover never starts a fresh tenure.
General offline candidates still leave unreviewed groups empty.

Validation: 47 source-owner/staging, opening import and restore tests passed, then
the additional end-of-month staging/commit test passed (31 January maps to 30 April).
Coverage includes evidence-required fallback, preservation of six-month source
tenure, invalid values, source scope, exact confirmation, retry and exported
provenance. No normal-DB migrations or real Party/loan/setup imports were performed.
Workspace 9 remains the isolated destination. Reviewed opening balances/coverage,
custody/appraisal, licence/setup and remaining obligation/grace inputs are still
needed before staging C00121. See the [pilot plan](plans/first-legacy-import.md).

Previous pilot preparation checkpoint (maturity decision superseded above):

One-loan pilot preparation (2026-09-12): the owner selected a new isolated test
Workspace. Created `TEST - jcl migration rehearsal` (ID 9,
`test-jcl-migration-rehearsal`) through the normal control-plane creation service,
owned by the existing `gov` owner account. Verified owner membership/action access
and zero loans under the restricted runtime role. No Party, loan or business setup
was staged or imported; no normal-database migrations were applied.

Prepared a private review at
`outputs/legacy-pilot-jcl-20260912/pilot-review.md` with its source proposal JSON.
C00121 is the proposed pilot: original principal 5,000, one gold item and monthly
interest 100. Fresh read-only archive extraction matches the cached candidate and
retains its five supporting source records. The April 9 rehearsal calculation
estimates 1,700 additional interest under stated payment/coverage assumptions;
it is not an approved opening balance. The owner subsequently confirmed C00121
is repayable on redemption with no fixed due date; the stored three-month tenure
is not its contractual maturity. Inspection found the existing opening validator,
commit and schedule writer require fixed maturity/dated obligations, and the loan
model requires positive tenure. Explicit no-fixed-date opening support is the next
bounded implementation prerequisite; C00121 remains held without fabricated dates.
This answer applies to C00121 only. Balance/coverage, custody/appraisal, licence
validity and mapped setup also remain before staging and owner confirmation. The
destination is resolved; source selection and production cutover are not approved.
Migrations Loans 0010/0011 and portability 0013 remain unapplied to the normal DB.
See the [first-import plan](plans/first-legacy-import.md).

Previous restore checkpoint:

Opening restore and reconciliation (2026-09-12): implemented one-loan operator
preview/confirmed restore of `loan-opening-export/1`. The source original opening,
identity, chronology, fingerprints and references are checked before writes. Explicit
destination mappings reuse the existing opening writer. Shared dated release and
reversal calculations rebuild supported servicing and dated appraisals without
changing the application clock or consuming native numbering counters.

Before acceptance, compare the rebuilt financial/custody/obligation graph, recorded
balances, concessions and collection estimate with the source after explicit local
reference normalization. Any difference rolls back the loan. The complete original
export and restore request are retained in immutable provenance; source actors and
timestamps remain source claims, while new records identify the restoring operator.
Same-input retry never repeats servicing or resets newer activity. Changed inputs,
existing ordinary openings and complete-history origins conflict.

Validation: 122 regressions passed, covering opening restore/export/import,
source staging, complete history, native loan services, release/concession/batch
workflows and reappraisal. After final record-bound and quote-provenance changes,
22 restore/reappraisal tests, two bound checks and the final source-scope check
passed. Coverage includes active/closed/reversed/re-released loans, covered first
month, multiple items, dated appraisals, forged checksums/financial records,
permission revocation, RLS, explicit confirmation, immutable provenance, rollback
and replay after newer servicing. Nine-file syntax/dependency checks and 421
current-document links passed. Appraisal quote IDs retain and display their source
Workspace rather than being treated as destination Rates references.

`restore_loan_opening` defaults to a rolled-back preview. Commit requires both
`--commit` and its reviewed `--expected-sha256`. The browser complete-history upload
continues to reject opening files and points to this dedicated path. New opening
exports advertise restore support; old same-format exports remain readable. No new
migration or actual source import was performed. The next MVP step is a concrete
one-loan pilot review and rehearsal; missing due terms, R07743, source selection,
destination and cutover decisions remain held. See the
[restore decision](adr/2026-09-12-opening-restore-reconciliation.md) and
[operator flow](flows/legacy-opening-import.md#restore-an-opening-export).

Previous export checkpoint:

Opening evidence export (2026-09-12): the owner loan download now selects
`loan-opening-export/1` for reviewed openings. It preserves the accepted source
review and available dump-verification records, supported later events, release
cash/concessions/reversals, collateral/custody, appraisals and remaining-obligation
evidence. The manifest marks pre-cutover history unavailable and references as
source-database-local. Recorded balance and unposted collection estimates are
separate. Export checks frozen bindings and supported continuation under Workspace,
loan and collateral locks, requires owner/export access and records an audit only.

This is an evidence download, explicitly `restore_supported=false`; it does not
complete the opening-and-servicing round-trip requirement. Complete-history import
rejects it clearly and its existing import/export contract remains unchanged.
Validation: 59 focused/regression tests passed across opening export, source
staging, complete history, opening commit and full release; the export-permission
revocation check also passed after its final addition. Coverage includes released
and reversed cash/concession evidence, source verification retention, retry without
duplicate debt, changed collateral/custody rejection, bounds, RLS, POST/CSRF and
profile rejection. Five-file syntax/dependency checks and 413 documentation links
passed. No new migration or real source import was performed. Restore/reconciliation and
actual source/destination/cutover review remain before the active pilot. Missing
due terms and R07743 stay held. See the [export decision](adr/2026-09-12-opening-evidence-export.md)
and [file contract](contracts/loan-opening-export-v1.md).

Previous staging checkpoint:

Legacy source staging and browser approval (2026-09-12): connected the one-loan
jcl opening bridge to a fresh bounded dump extraction, immutable source evidence,
existing Loans staging and the authorized opening command. Staging verifies exact
archive/selection/source identity, borrower and complete item facts, and holds
source errors, payments, changed principal or missing tenure. The operator command
stages only and prints a browser route; owners review the selected loan and explicit
destination setup, preview under rollback and confirm through a one-hour signed
approval bound to operator/Workspace/batch/content. Cancellation erases unfinished
staged values only; completed replay rechecks access.

Migration 0013 adds an immutable profile to the existing forced-RLS staging table
and validates the exact accepted result document. Complete-history handlers/listing
remain isolated from opening batches, including after cancellation. No new table
or automatic bulk runner was added. The UI is available under Import Loans ?
Review prepared legacy loan openings after owner schema migrations are applied.

73 source-adapter, staging/browser, complete-history, opening-commit and document
review tests passed, including ten new bridge tests. Coverage includes tampering,
expired/wrong approval, CSRF, explicit confirmation, source/profile immutability,
cancellation, permission revocation, RLS, stale-destination rollback and the staging
command. Migration drift, ten-file syntax/dependency checks and 406 documentation
links passed. Migration 0013 was applied to the test database only. No real source loan
was staged/imported and no source file or owner workbook changed. Next engineering
slice: truthful opening export. Actual reviewed balances, due terms, destination
and cutover are still required for the pilot; R07743 and unresolved loans stay held.
See the [staging decision](adr/2026-09-12-legacy-opening-staging.md) and
[operator flow](flows/legacy-opening-import.md).

Previous domain commit checkpoint:

Authorized opening commit (2026-09-12): implemented per-loan v2 preview/commit
with owner/context/lifecycle checks, Workspace serialization, exact Party identity,
reviewed original tenure/maturity, licence/product and explicit servicing policy.
Preview rolls back the full writer; commit requires confirmation of the exact
review/setup fingerprint. Loan, net-only/Bronze collateral, migration appraisals,
policy, one opening event, remaining obligations, immutable provenance and audit
commit atomically. No historical approval/disbursal/receipt or custody move is
fabricated, and no live loan-number counter is consumed.

Complete history and openings share immutable financial-origin identity. Legacy
IDs are scoped by source schema; older raw-key complete imports are recognized
without modification. Changed accepted input conflicts; an authorized identical
retry returns its original import summary without resetting subsequent servicing.

The 130-test regression suite passed. After adding older-identity compatibility,
40 focused opening/history/review tests passed, including all 12 new commit tests.
They cover preview rollback, release/reversal, retries, both directions of origin
conflict, two source schemas, old bindings, number/Party mismatch, authorization,
restricted-role RLS/immutability and late rollback. Migration drift, seven-file
syntax/dependency/whitespace checks and 350 documentation links passed. No new schema migration,
production write or real source-candidate activation occurred. Source-selection/
approval integration, original due-term review, truthful opening export and the
actual destination/cutover rehearsal remain pending. See the
[commit decision](adr/2026-09-12-authorized-opening-commit.md) and
[first-import plan](plans/first-legacy-import.md).

Previous collateral mapping checkpoint:

Legacy collateral evidence mapping (2026-09-12): opening review v2 and the existing
collateral model now preserve unknown gross weight, positive net weight and
separate purity; Bronze maps distinctly. Native draft/approval weight checks and
v1/complete-history contracts remain strict. Loan details display unknown gross
explicitly. Migration 0011 alters existing fields only and was applied to the test
database; no development/production migration or financial import was run.

115 targeted tests passed, including six new mapping, validation, SQL, UI and
Bronze full-release/reversal checks. Migration drift, syntax/dependency checks,
targeted diff whitespace checks and 340 documentation links passed. The refreshed offline report at
`.tmp/legacy-collateral-jcl-20260912/` maps all 2,470 items (1,775 Gold, 688 Silver,
seven Bronze) across 2,448 retained active loans without database queries or source
changes. All remain unreconciled pending financial/destination evidence; the
existing R07743 discrepancy remains held. Recorded tenure is 3 for 298 candidates
and 0 for 2,150. Legacy code does not supply a contractual maturity calculation;
missing due terms remain a review decision, not a default three-month extension.
Next: authorized opening commit/source binding and a small rehearsal; truthful
opening export and final cutover/destination approval remain activation gates.
See the [collateral decision](adr/2026-09-12-legacy-collateral-evidence.md) and
[first-import plan](plans/first-legacy-import.md).

Previous full-release checkpoint:

Loans opening full-release servicing (2026-09-12): connected reviewed v2 opening
loans to the existing full-release service and form. It posts only the additional
collection interest since cutover, then records cash/concession, schedule termination,
collateral return and closure atomically. Original-date billing and cumulative
rounding are preserved. Interest beyond remaining scheduled interest is explicitly
identified in the receipt, without fabricating new due dates. Coupled reversal
restores catch-up, settlement, concession, original schedule and custody; independent
opening/catch-up reversal is rejected. Date-aware exposure and item principal now
recognize closed intervals and later reversal. The loan page labels migration
collection catch-up distinctly. Generic event posting, native monthly accrual,
partial-principal repayments, renewals and auctions remain blocked for this origin.

160 financial, UI, history, opening, obligation and dashboard regression tests
passed, including 11 new service/UI tests covering first-month coverage, prior unpaid
interest/fees, cumulative rounding, concession, permissions, cross-Workspace
rejection, retry, coupled reversal and transaction rollback. Strict `loan-history/1`
export explicitly rejects opening-position loans; its new rejection was rechecked.
Migration drift reports no changes; syntax/dependency checks, diff whitespace checks
and 348 documentation links passed. No new table/migration, source candidate changes,
owner workbook changes or production writes. Next: legacy evidence mapping and
authorized opening commit/source-adapter rehearsal; truthful opening export and
approved destination/source/cutover evidence remain activation gates. See the
[servicing decision](adr/2026-09-12-opening-full-release-servicing.md) and
[first-import plan](plans/first-legacy-import.md).

Previous continuation-and-obligations checkpoint:

Loans opening continuation and obligations (2026-09-12): added explicit
`loan-opening-review/2` for the inclusive original-anniversary aggregate collection
rule. It requires reviewed first-month coverage, unchanged item principal and
cumulative recognized baseline through the exact cutover, separately from unpaid
opening interest. Exposure projects only the additional baseline after cutover;
it does not replay native daily interest or create historical receipts/losses.
Reviewed remaining obligations now persist in existing immutable schedule tables
through an owner-authorized, scoped, loan-locked service with exact retry comparison
and atomic rollback. Original due dates/maturity are preserved, and the delinquency
selector uses reviewed grace instead of the destination product default.

114 focused/regression tests passed across verification runs, including 15 new
continuation, obligations and review-adapter tests. Coverage includes inclusive
month ends/leap years, cumulative rounding, covered interest, overdue dates, replay,
conflicts, missing actor, cross-Workspace access, rollback and restricted-role
immutability/RLS. Migration drift reports no changes; syntax/dependency checks and
343 documentation links passed. No source candidates, owner workbook or production
rows changed. Opening financial posting and native accrual remain disabled;
projection currently rejects subsequent servicing events. Next is posting and
full-release/reversal integration, followed by the actual authorized opening
commit and source adapter rehearsal. Source evidence gaps and final handover remain
in the [first-import plan](plans/first-legacy-import.md). See the
[v2 checkpoint](contracts/loan-opening-review-v2.md) and
[continuation decision](adr/2026-09-12-opening-collection-continuation.md).

Previous opening-foundation checkpoint:

Loans opening foundation (2026-09-12): added the `MIGRATION_OPENING` event
and internal frozen `loan-opening-evidence/1` envelope. Recorded balances and
per-item principal now recognize reviewed cutover amounts without inventing a
disbursal, accrual or payment. Reads reject dates before cutover, duplicate/mixed
origins, mismatched destination references and overlapping servicing events.
Opening amounts remain separate from new lending and collection totals; original
maturity comes from reviewed evidence. Migration 0010 enforces one opening per
loan on the existing immutable, forced-RLS event table. Restricted-role tests cover
mutation rejection and absent/cross-Workspace invisibility.
88 existing financial/history/report/dashboard regression tests and 40 opening,
review, legacy-calculation and vocabulary tests passed (13 new opening tests).
Migration drift, changed-file syntax/dependency checks and 324 documentation links
also passed.
The migration was exercised in the test database only. Generic event posting and
native interest continuation explicitly reject opening loans until the remaining
servicing integration is complete. No operational importer, real opening balances
or production changes were made. Next: original-period interest continuation,
remaining obligations and servicing; then the authorized, idempotent opening
commit and adapter rehearsal. Evidence gaps and final handover remain tracked in
the [first-import plan](plans/first-legacy-import.md).

Previous release-concession checkpoint:

Loans migration prerequisite (2026-09-12): implemented explicit interest
concessions for single-loan full release. Cash plus concession must equal the
current settlement; concessions can consume only uncapitalized interest and
require a bounded reason plus Workspace administration authorization in addition
to release permission. Immutable event values separate interest paid from
interest conceded; reversal restores both, and retries verify the original cash,
concession and reason. The full-release form, release detail and memo expose the
loss separately. Existing mandatory memo interest binding includes the loss and
reason for older published layouts. Strict `loan-history/1` export rejects
concession histories rather than omitting the loss. No new table or migration.
102 financial/UI/history regression tests and 72 offline preparation tests passed;
the former include 10 new service/UI/permission/reversal/replay/rollback/export/RLS
tests and two new pure balance tests. Migration drift check reports no changes.
No real loans imported or production data changed. Active opening/servicing,
legacy evidence handling, destination mappings, actual import commit/rehearsal and
fresh cutover remain required; released records need their own limited-evidence
path. The [first-import plan](plans/first-legacy-import.md) fixes this delivery scope.

Previous collection-preparation checkpoint:

Loans portability collection clarification (2026-09-12): the owner accepts
negotiated collections and treats accepted interest shortfalls as interest lost;
fractional rounding must not block preparation. Implemented explicit offline
`jcl-owner/2`: sum item monthly interest, multiply by additional months, then
HALF_EVEN-round the total once. The report preserves unrounded interest and the
rounding adjustment, and leaves actual cash interest/interest loss unknown.
Version 1 remains available with its prior conservative behavior. The unchanged
April 9 rehearsal now calculates 2,447 of 2,448 retained active loans; R07743 alone
has a calculation hold for source errors. The previous 1,700 results, all source
records, exclusions and opening candidates are unchanged. 72 focused
database-prohibited tests pass. No imports or live release changes. Original due
terms, gross weight, Bronze, custody/valuation, source correction and opening
financial evidence remain unresolved. Exact-settlement live release needs explicit
interest-concession support before serving this practice on imported loans. See
the [decision](adr/2026-09-12-legacy-collection-estimates-and-concessions.md).

Previous preparation checkpoint:

Loans portability preparation (2026-09-12): implemented the Loans-owned pure
`original-anniversary-upfront-inclusive/1` collection calculator and explicit
`jcl-owner/1` offline source profile. Owner examples cover inclusive anniversaries,
short-month clamping with restored original day and HALF_EVEN amount rounding.
The profile maps source weight to net weight with evidence only for the reviewed
legacy namespace/tenant; gross remains unknown. On the unchanged April 9 rehearsal,
2,448 retained active loans produce 1,700 collection illustrations, 747 holds for
unconfirmed fractional aggregation and one source-error hold. All 2,470 retained
items receive net weight; seven Bronze items remain unmapped. All 54,713 source
rows, summary and exclusion manifest are byte-identical to the prior rehearsal.
66 focused database-prohibited tests pass. A separate owner-rule HTML report and
JSON diagnostics expose results without altering the owner-edited workbook.
Nothing imported; opening balances/terms/continuation remain unfilled and no
servicing or accounting behavior changed. The then-next fractional aggregation
question is superseded by the owner clarification above. See the
[worksheet implementation](implementation/legacy-reconciliation-worksheet.md).

Branch: `rls-mvp`. Current published application checkpoint: `92aa3600`, the first
business-dashboard metrics (`56950044`) and its queue-link test correction, following same-day origination quotes and approval
evidence in `62121439` and monitoring hardening in `9a430aa2` (2026-09-12).
Previous published application checkpoint: `62121439` (2026-09-12); GitHub Workspace
RLS checks passed for that checkpoint (run `34674917994`). The first dashboard
run found an outdated queue-link test; the correction is pushed and replacement
CI run `34684910855` is still in progress. Prior CI success does not establish
the new checkpoint result.
All four orgs checkpoints are pushed: workspace/role settings (`ee31dda`),
team/invitations (`0177fc3`), lifecycle/navigation (`e434828`), and final
account/preferences, slug adapters and unused backup-view removal (`38eb1e3`).
Both Loans and orgs view organization are complete and published.
Document form organization is published: 13 layout/overlay/asset and
print-profile forms moved to `web/document_forms.py`, with existing public imports
preserved. Document setup handlers use the owning module; no business rules changed.
The three license/series setup forms are also extracted into `web/license_forms.py`
with compatible public imports. Both form increments are published as `16be7149`.
The three economic-setup forms are published into `web/economic_forms.py`
with public imports preserved and unchanged behavior; published as `7c043eb0`.
The eight funding forms are extracted into `web/funding_forms.py` with compatible
public imports and unchanged behavior. Five storage/physical-verification forms
are also extracted into `web/custody_forms.py`. Funding and custody increments
are published as `fdb5e97f` alongside the test Workspace assertion fixes.
No production deployment or real provider payment, refund or email was performed.

The [hardening plan](plans/project-hardening.md) is the current delivery queue.
The [project review](architecture/2026-09-09-project-review.md) preserves the original
findings; its baseline descriptions are not a claim that fixed defects remain.

| Area | State |
| --- | --- |
| Bilingual branding | Approved Rokkad / रोक्कड़ artwork applied to shared UI, portal, admin, browser icons, checkout, billing communications, and README; see [branding](implementation/branding.md) |
| Workspace/RLS, local role grants, private-media routes, business setup | Implemented; access/media checkpoint `4d15477` published |
| Multiple-loan full release | Implemented, owner reviewed; `4b08c3f` published |
| CI/container runtime foundation and Workspace operator commands | Included in the local hardening checkpoint |
| Checkout, paid expiry, recovery, processed refunds and final owner review | Included in the local hardening checkpoint; development migrations through subscriptions.0009 applied |
| R08 current documentation | Current entry points rewritten; dated context archived and linked; documentation-link check added to CI |
| R09/R10 onboarding and legacy configuration/guardrails | Completed locally: current tour choices, six unused settings removed, tracked-source import guard in CI |
| R13 dependencies/templates | Completed locally: four unused direct packages and 14 unreachable templates removed |
| R11 dashboard reliability | Incomplete-queue warning and explicit unavailable monetary totals implemented; batching complete with shared calculations and restricted-role verification |
| R07/R12 routing/modules | R07 complete locally: all 136 canonical routes use direct Workspace adapters; response rewriting removed. Loans views portion of R12 complete: compatibility imports plus focused web modules; orgs views portion also complete locally; model/form/renewal-service review remains separate |

## Latest validation

- First business-dashboard increment committed and pushed as `56950044`
  (2026-09-12). The approved second financial-health increment is local: saved
  projected interest, economic exposure, eligible collateral value and per-loan
  shortfall, with freshness counts and explicit unavailable totals. It adds one
  SQL aggregate, retains Workspace/RLS and existing read/admin permissions, and
  excludes closed loans. V3 provenance copies canonical financial components;
  older assessments enter the ordinary bounded refresh backlog without a schema
  migration or GET mutation. See the
  [decision](adr/2026-09-12-dashboard-assessment-financial-evidence.md) and
  [operator guide](flows/business-dashboard.md). Focused regression: 44 tests pass,
  including canonical refresh-to-card values, V2 upgrade, missing/malformed
  evidence, closed-loan exclusion, per-loan shortfalls and restricted-role scope.
  GitHub run `34684380941` found one outdated queue-link fixture; its existing
  local correction is now published as `92aa3600`. The corrected fixture, final
  owner/member dashboard assertions and Rates regressions pass (36 tests).
  Final combined regression: all 589 Loans, Rates and MVP operator-journey tests
  pass (231.361 seconds) in an isolated review tree/database excluding concurrent
  portability/history work. Final scoped files match that tested tree. No migration
  drift; 252 current-doc links, supported-app imports and whitespace checks pass.
  Replacement GitHub CI run `34684910855` is still in progress; no CI pass is claimed.
  Live browser accessibility review confirms
  the cards, unassessed warning and authorized Loan health link; screenshot capture
  timed out, so pixel-level inspection remains unverified. No normal-development
  worker was started and no loan/rate/appraisal data was changed by this increment.
  Full launch-capacity testing remains shelved under FW-004.

- Owner supplied interest rounding examples (2026-09-12): 148 for the paired
  148.20/148.50 question, 149 for 148.80 and 150 for 149.50. Interpreting the first
  response as applying to both, these match whole-rupee HALF_EVEN and the inspected
  legacy Decimal round() behavior. Recorded in the
  [rounding cases](implementation/legacy-reconciliation-worksheet.md#interest-rounding-examples-received-2026-09-12).
  No aggregation/partial-payment rule was inferred. Documentation and arithmetic
  verification only; no workbook, source data or financial behavior changed.
  Next: bounded legacy-rule calculation/tests and source-specific net-weight
  preparation; financial activation and remaining evidence review stay separate.

- Owner corrected legacy weight interpretation (2026-09-12): it is NET weight
  excluding stones and other non-metal parts. This supersedes the earlier gross
  interpretation. The original answer and correction are recorded in the
  [weight interpretation](implementation/legacy-reconciliation-worksheet.md#source-weight-meaning-confirmed-2026-09-12)
  and opening contract. Do not deduct stones again, infer purity from net weight,
  or invent gross weight. Documentation only; source values, workbook, candidate
  mapping and financial data unchanged. Next: interest rounding; gross remains unknown.

- Owner corrected cash handover to 9,790 for the 10,000 example (2026-09-12),
  resolving the initial 9,890 typo. Upfront 200 interest and 10 document charge
  are deducted; principal remains 10,000. Both statements are preserved in the
  [reconciliation notes](implementation/legacy-reconciliation-worksheet.md#net-cash-handover-confirmed-2026-09-12).
  Next: source weight meaning and rounding. Documentation only; no source record,
  workbook, calculation or financial import changed.

- Owner confirmed April 1 as the first release date requiring 10,400 for the
  January 31 example (2026-09-12). Original anniversaries are restored after February;
  collection increases after the inclusive boundary, not after a permanently shifted
  February date. Recorded in the
  [calendar rule](implementation/legacy-reconciliation-worksheet.md#original-anniversary-restored-after-february-2026-09-12)
  and opening contract. Next: net cash handover, weight meaning and rounding.
  Documentation only; current validators/servicing and financial data are unchanged.

- Owner confirmed March 1 as the first additional monthly-interest date for a
  January 31, 2026 loan (2026-09-12). Upfront coverage includes February 28.
  Recorded in the
  [short-month example](implementation/legacy-reconciliation-worksheet.md#january-31-short-month-boundary-clarified-in-chat-2026-09-12).
  Next: the following charge date, to distinguish original anniversaries from
  dates carried forward after February. Documentation only; no financial changes.

- Owner confirmed February 11 as the first release date requiring 10,200 for the
  January 10 example (2026-09-12). Upfront coverage includes February 10; the full
  additional 200 applies from February 11. Recorded in the
  [collection rules](implementation/legacy-reconciliation-worksheet.md#first-additional-interest-date-clarified-in-chat-2026-09-12)
  and opening contract. Next: January 31/non-leap-February treatment. Documentation
  only; no workbook, calculation or financial data changed.

- Owner clarified February 20 release collection (2026-09-12): for the same
  10,000 loan at 2% dated January 10, collect 10,200 at release, comprising principal
  plus 200 additional interest. Upfront 200 interest and 10 document charge remain
  already collected. Recorded in the
  [reconciliation notes](implementation/legacy-reconciliation-worksheet.md#february-20-release-clarified-in-chat-2026-09-12).
  Next: establish the first release date on which that additional 200 is payable;
  do not assume a boundary-day/grace rule. Documentation only; no financial writes.

- Owner clarified first-month interest/document-charge collection (2026-09-12):
  a 10,000 loan at 2% dated Jan 10 collects 200 interest and 10 document charge at
  disbursal; Jan 20 release collects only 10,000 principal. Recorded in the
  [reconciliation notes](implementation/legacy-reconciliation-worksheet.md#first-month-collection-clarified-in-chat-2026-09-12)
  and opening contract. Preserve paid first-month coverage and settled fee; missing
  payment rows do not imply no upfront collections. Net cash handover and later
  partial-month treatment remain unspecified. Documentation only; no workbook,
  calculation, source record or financial import changed. Next: the same loan
  released February 20, to establish subsequent partial-month collection.

- Owner's saved reconciliation responses reviewed and recorded (2026-09-12).
  Monthly boundaries follow original loan-date anniversaries (Jan 10 to Feb 10).
  Owner reports no separate receipts/waivers and confirms released means paid and
  closed. Bronze is a distinct source metal requiring support. Cutover was not
  understood; brief acknowledgements supplied no maturity/grace/correction values.
  All per-loan balances and evidence cells remain blank. See the
  [verbatim responses](implementation/legacy-reconciliation-worksheet.md#owner-responses-received-2026-09-12).
  Workbook read only; no formulas, balances, code, database or import state changed.
  Next: clarify partial-month collection in ordinary business terms, then remaining
  month-end/weight rules and rehearsal balance evidence. No final handover date
  needs to be chosen merely to continue the rehearsal/design.

- Representative `jcl` source reconciliation worksheet completed locally
  (2026-09-12). The offline preview now emits source-linked comparison JSON with
  explicit date/timezone. The private Excel worksheet contains nine retained active
  loans plus one released payment control, source items/payments, inspectable
  expressions and blank owner-response/balance fields. See the
  [worksheet guide](implementation/legacy-reconciliation-worksheet.md).
  At the illustrative 2026-04-09 Asia/Kolkata date, 99 of 2,448 retained active
  loans have differing gross-interest expressions; all retained active loans have
  no payment rows. Largest difference: 1,800. Neither expression, missing-payment
  coverage nor cutover is approved. R07743's principal/monthly-interest mismatch
  remains unresolved. Existing source selection and all 54,713 rows are preserved.
  Validation: 53 focused tests pass; all sample workbook interest calculations and
  item sums match independent Python calculations. Source-change/zero checks,
  recalculation, formula-error scan and visual review of all three sheets pass.
  Native Excel execution was not tested. No database read/write or financial import.
  Next: owner review of Interest rule and Payment coverage before agreeing the
  pilot financial rule and opening balance basis.

- Opening-position offline validation/reconciliation implemented locally
  (2026-09-12). Loans-owned checks reconcile per-item principal, remaining principal
  and recognized-interest obligations, original dates/periods, bases and full-period
  recognition/advance carry. Dump preparation (`--prepare-openings`) leaves missing
  financial evidence explicit; `validate_loan_openings` rechecks bounded JSONL without
  database access. No opening event, loan, financial posting or destination binding
  is created. See [review contract](contracts/loan-opening-review-v1.md).
  The `jcl` run preserved all 54,713 source rows and generated 2,448 retained active
  candidates; all need review, with one retained source-error loan. No document is
  reconciled/import-ready. Standalone revalidation matches the generated report.
  Validation: 45 focused database-prohibited tests pass (22 new opening checks and
  23 existing dump-preview tests); all 54,713 source records and selection summary
  compare equal with the prior scope preview. All seven scoped Python files pass
  syntax/import-boundary/whitespace checks; 302 documentation links pass.
  Next: a representative source reconciliation worksheet and agreement on the pilot
  calculation rule, rehearsal cutover and balance evidence before financial activation.

- Opening-position contract draft and reversible collateral exclusion proposal
  completed locally (2026-09-12). Owner selected preservation of existing billing
  dates/agreed rules and suggested skipping incomplete collateral. The contract
  distinguishes cutover balances from missing historic events, preserves maturity
  and requires original-period recognition/advance carry to avoid double charging.
  See [contract](contracts/loan-opening-position-mvp.md) and
  [proposed financial decision](adr/2026-09-12-loans-opening-position-contract.md).
  `--propose-skip-incomplete-collateral` adds whole-loan proposed dispositions,
  scope fingerprint and a separate manifest without dropping any source row.
  The `jcl` proposal skips 873 unreleased / 11,299 released loans and retains 2,448
  unreleased / 4,620 released for review. Skipped unreleased source principal totals
  6,570,885; retained unreleased source principal totals 21,678,041, neither asserted
  as an outstanding balance. One retained unreleased loan still has a source error.
  Verified all 54,713 original facts, IDs, hashes and issues are unchanged in the
  ignored `.tmp/legacy-preview-jcl-scope-20260912/` report. **23 focused tests passed**,
  including selection criteria, whole-graph preservation, source-scope checks,
  stable/changing selection fingerprints and unknown-amount reporting. Financial
  implementation and final exclusion acceptance remain pending; no database writes.

- Read-only legacy dump preview implemented and exercised locally (2026-09-12).
  The owner selected `jcl`: the offline `preview_legacy_dump` command extracted
  54,713 records across nine tables, including 5,431 customers and 19,240 loans
  (3,321 unreleased / 15,919 released). HTML, summary JSON and per-record JSONL are
  in ignored `.tmp/legacy-preview-jcl-20260912/`; every record remains not
  import-ready. The report flags 3,094 records with errors, including linked parent
  findings; this is not a count of unique rejected loans. Source issues include
  1,520 item rows with zero weight (871 on unreleased loans), 19 release and eight
  payment dates before their loans, and loan/item total differences. No source
  values were repaired or financial balances inferred. Source IDs and schema scope
  reconcile with the earlier offline review. **17 focused tests passed** for COPY
  parsing, bounds/timeouts, source tenant separation, identity stability, reference
  and value findings, HTML escaping, safe errors, no database queries and output
  completion/overwrite behavior. See [operator guide](flows/legacy-dump-preview.md)
  and [decision](adr/2026-09-12-offline-legacy-dump-preview.md).
  No new tables, migrations, database writes, web upload or financial import.
  Next: opening-position and limited-evidence released-record contract decisions.

- Legacy source/dump review completed locally (2026-09-12), using owner-supplied
  commit `c9fb81bc70adafa1d942721d642bfb2b38953f41` without switching branches or
  executing legacy code/SQL. Optional release amounts explain a source path with
  release records and no payments; model/report interest calculations differ and
  the dump lacks some fields in the supplied commit. Offline reconciliation finds
  6,107 unreleased loans, 6,103 with separate items; selected anomalies include 23
  releases and 9 payments before their loan timestamps, two active principal/item
  mismatches and one active monthly-interest/item mismatch. Checked source foreign
  references and payment split arithmetic pass; economic balances remain unapproved.
  An ignored local CSV classifies all 22,987 source loans for review, with none
  marked import-ready. See [source review](implementation/legacy-dump-source-review.md).
  No application behavior, database data, migration state or live counters changed.

- Actual migration sources clarified (2026-09-12): legacy schema-per-tenant Django
  production dump first, simple linked Excel registers second. Offline archive
  inspection found 6,924 customers, 22,987 loans and 16,880 releases; 15,876 released
  loans have no linked rows in the selected payment table. These are source counts,
  not a completed financial audit or proof that history is unavailable elsewhere.
  No SQL was executed and no database was restored or modified. The next step is
  mapping/reconciliation against the matching legacy application code, classifying
  complete histories, active opening requirements and limited-evidence releases.
  See [actual source priorities](plans/data-portability.md#actual-source-priorities-2026-09-12).
  Dump/Excel loan adapters, bulk migration, opening positions and limited-evidence
  historical record imports are not implemented; the earlier complete-history
  synthetic tests do not establish compatibility with these sources.

- Owner-authorized closed-loan operator acceptance completed locally (2026-09-12).
  The published closed example now has independent source loan/release identities
  and number 00043, avoiding conflict with the accepted active example. Preview
  retained no loan; confirmed import restored CLOSED state, five events, settlement
  909, zero principal/interest/fees, full collateral return and no active repayment
  schedule or remaining obligations. The canonical export is byte-for-byte identical
  to the revised source and matches immutable provenance. Verified the completed
  browser screen, unchanged active example and unchanged live loan-number counters.
  Both synthetic active and closed operator import/export checks now pass. A real
  customer/vendor source remains the next acceptance step; no new MVP feature was
  introduced by this check.

- Owner completed the synthetic active-loan import and exported its canonical
  JSONL (2026-09-12). Read-only verification confirms the downloaded file is
  byte-for-byte identical to the original active example, matches immutable import
  provenance, and reconciles with stored principal 900 / interest 0 / fees 0 at
  the source cutover. The batch is COMPLETED and the restored loan is ACTIVE.
  This closes the local operator import/export check for that synthetic sample;
  real-source compatibility and a manual closed-loan check remain unclaimed.

- Owner-approved local Loans example preview completed (2026-09-12). Created a
  clearly labelled synthetic borrower through Party portability, an inactive
  historical test licence/series and a retired compatible TEST-V1 product using
  the existing setup lifecycle. The active example is READY: three events, one
  collateral item, recorded principal 900 / interest 0 / fees 0, and remaining
  contractual principal 900 / interest 20. Verified the browser confirmation
  screen, no retained loan from preview and unchanged live loan-number counters.
  The loan has not been committed; this is synthetic operator acceptance evidence,
  not validation of a real customer or vendor source.

- Canonical Loans JSONL MVP implemented locally (2026-09-12). See the
  [source contract](contracts/loan-history-jsonl.md),
  [operator flow](flows/loans-history-import.md), and
  [decision](adr/2026-09-12-loans-canonical-history-import.md). Dedicated upload,
  exact Party/setup mapping, rolled-back reconciliation preview, signed explicit
  atomic commit, persistent attempts/cancellation, immutable source provenance and
  canonical export cover active and fully released flexible simple-interest
  histories, one complete loan per file. Decimal spellings normalize before source
  hashing; source IDs, original numbers and same-day event order are preserved.
  Native and imported histories round-trip, and a restored active loan accepts
  native repayments. Source collectors/actors remain historical claims.
  Validation: **857 regression tests passed** in 375.797 seconds across portability,
  Loans, Party and the registry; **28 final focused tests passed** in 19.721 seconds
  after the final decimal, approval-digest, concurrent-commit, migration and timezone
  checks. Focused coverage includes native active/full-release export and restore,
  cross-Workspace round-trip, HTTP/CSRF, RLS, evidence immutability, duplicate/conflict,
  late-failure rollback, approval tampering/expiry/revocation and concurrent replay.
  Owner migrations loans.0009 and data_portability.0011?0012 are applied locally.
  Both new tables have forced RLS and enabled provenance/batch guards; runtime is
  nonsuperuser/non-bypass, and the registry covers 110 models. The intermediate
  batch migration denies all restricted DML until its Workspace policy exists.
  Django database checks, migration drift, tracked/untracked import boundaries and
  current documentation links pass. No production deployment, production historical
  import or live counter rewrite. Broader structures, vendor adapters, archives and
  Party history filtering remain deferred. Next operator step: prepare and preview
  a representative real canonical source file; no vendor compatibility is claimed.

- Historical Loans setup preparation implemented locally (2026-09-12); see the
  [operator flow](flows/loans-import-preparation.md) and
  [decision](adr/2026-09-12-loans-history-setup-preview.md). Owner-only preparation
  is linked from Loans setup and Party imports. It checks original licence/date,
  matching destination series, flexible-product contract/grace/tenure/availability
  and displays deterministic source-identity-based loan/release number candidates.
  Expired/inactive setup and retired versions do not become active; live counters
  are unchanged. Existing-number conflicts and configured future overlaps fail.
  Results are unsaved previews, not reservations or import approvals; financial
  history staging/reconciliation/commit, persistent provenance and canonical Loans
  export remain outstanding. Both active and fully released histories remain in
  scope. No migration or financial write. Validation: **237 selected tests passed**
  in 152.994 seconds across portability, Loans setup/numbering/products/evidence
  guards and registry, including nine new scoped service/HTTP tests. Django checks,
  migration drift and import boundaries pass; 291 links checked in 19 docs.

- Loans historical-evidence prerequisite implemented locally (2026-09-12); see the
  [guard decision](adr/2026-09-12-loans-history-evidence-guards.md). Owner-only
  migration 0008 is applied: fifteen append-only evidence tables reject UPDATE/
  DELETE and validate new Workspace/loan references, including parent-derived
  allocation/custody links. Actor clearing is also rejected; hard deletion cannot
  strip retained attribution. Mutable loan/collateral state is unaffected.
  Validation: **553 Loans tests passed** in 210.959 seconds, including six new
  restricted-role guard tests and native workflow regressions. Two existing UI
  fixture assumptions were corrected: owner-role autocomplete scope and dashboard
  period-query preservation. Final local inspection verifies all fifteen triggers
  enabled, forced RLS and a nonsuperuser/non-bypass runtime role. Django database
  checks, migration drift and import-boundary checks pass. No business data rewrite,
  new table or Loans import endpoint. The next portability implementation is
  explicit historical setup/number mapping and the historical import command.

- Bounded Loans portability contract review completed (2026-09-12); see the
  [contract](contracts/loan-history-mvp.md) and
  [decision](adr/2026-09-12-loans-complete-history-mvp.md). Selected existing flexible
  partial-payment structure includes both complete ACTIVE histories and CLOSED
  full-release histories, with source chronology, setup/number mapping, financial/
  obligation/custody reconciliation and explicit exclusions. Native disbursal,
  repayment and release commands are unsuitable historical replay APIs due to
  current-date/quote checks and number allocation. Read-only local PostgreSQL
  inspection found no non-internal triggers on six core event/snapshot/release/
  schedule tables. Immediate next implementation is targeted evidence protection
  and restricted-role/native workflow verification before historical writes.
  Validation: 15 existing schedule/interest/vocabulary tests passed; 279 local
  links checked in 16 documentation files. These are baseline calculation checks,
  not historical-import or SQL mutation acceptance. No financial mutation, schema
  migration or Loans import endpoint was added.

- Portability scope clarification (2026-09-12): moved the optional history progress
  filter to [FW-006](plans/future-work.md#fw-006-party-bundle-history-progress-filter)
  at owner request. Clarified that active/closed loan state is separate from
  complete/incomplete source history; the Loans roadmap can cover both active and
  closed histories within supported profiles. No Loans implementation or financial
  mutation was performed; existing historical-command and opening-position
  prerequisites remain explicit in the [plan](plans/data-portability.md#loans-scope-clarification-2026-09-12).

- Party portability MVP closeout completed locally (2026-09-12) under the owner's
  explicit no-drift constraint. **Zero further portability feature slices are
  required or queued.** History filtering is deferred; the
  [scope boundary](plans/data-portability.md#mvp-scope-closeout-2026-09-12) separates
  delivered Party functionality from the future roadmap. Fixed duplicate Bundle
  history markup inside the import page's browser-title block and clarified that
  only ZIP staging creates new history entries. Validation: **29 existing history,
  cancellation and combined-commit tests passed** in 36.661 seconds; rendered title
  and single history section verified; 342 local documentation links checked in
  25 files. The preceding 281-test regression result remains the broader baseline.
  No service, schema, permission, migration or dependency change; no deployment
  or production acceptance. Generic legacy data-tools review remains a separate
  open item; this closeout does not certify the whole SaaS MVP as release-ready.

- First business-dashboard increment implemented locally (2026-09-12). Existing
  data.view access now exposes customer/active-borrower/active-loan counts, today's
  canonical recorded principal and unpaid interest, and period-filtered new issues,
  new-loan net cash, average per calendar day and separate renewal counts. Activity
  supports today/month/30 days/custom (up to 366 days), retains queue pagination
  filters and shows invalid input without replacing the requested period. Current
  portfolio cards stay current. Invalid opening/balance/cash evidence makes complete
  money totals unavailable instead of exposing partial sums. New-loan cash explicitly
  excludes renewal top-ups. See the [metric guide](flows/business-dashboard.md).
  Balance queries are batched with the existing canonical event fold; no health
  calculation, persistent cache, schema change or worker dependency is introduced.
  Six new-selector queries cover one nonempty batch; subsequent 250-loan batches
  add one event query. CPU/event-history cost remains linear; capacity is unproven.
  Validation: all **79 related tests passed** in 93.573 seconds, including nine
  new metric/form tests, canonical balance and servicing/renewal regressions, and
  the restricted-role HTTP operator journey. Ten focused integration checks also
  passed after correcting a new fixture's PartyRoleType field name. Coverage includes
  capitalization/reversals, current/future dates, missing evidence, empty portfolios,
  customer de-duplication, query batching, RLS, access denial and preserved filters.
  Live browser checks confirmed the overview and Today filter on the development
  dashboard; screenshot capture timed out, so pixel-level inspection is unverified.
  No loan mutation, migration, worker startup, capacity run, commit or push occurred.
  Concurrent Party portability changes are preserved.

- Coordinated Party bundle cancellation implemented locally (2026-09-12); see the
  [cancellation decision](adr/2026-09-12-party-bundle-cancellation.md). Saved review
  pages provide explicit confirmation to cancel every currently unfinished member
  atomically. Workspace/member locks serialize with aggregate commit; completed
  imports and immutable history are retained, already cancelled profiles are skipped.
  Cancelled staged raw/canonical values, issues and approvals are cleared; mappings,
  defaults, source identifiers and audit metadata remain. Changed groups receive one
  aggregate audit; authorized no-op replay makes no changes. Old combined approvals
  cannot commit cancelled groups. Empty history is expected until ZIP staging or
  verified legacy recovery; individual CSV/XLSX/JSONL imports do not create groups.
  No migration, schema or dependency change. Validation: **281 tests passed, zero
  failures**, in 279.202 seconds across portability, Party and registry. Eight new
  tests cover staged-value cleanup, completed evidence, authorized replay, late
  rollback, stale approval, confirmation/CSRF and concurrent cancel versus commit
  under restricted RLS roles. Django database checks and migration-drift checks pass;
  import boundaries pass for 566 tracked files plus compile/boundary checks for 50
  portability/shared-service files. Documentation checks pass (332 links/25 files).
  The later MVP closeout defers history filtering; no further portability feature
  slice is queued.

- Persistent Party bundle history implemented locally (2026-09-12), documented in
  the [history decision](adr/2026-09-12-persistent-party-bundle-history.md). ImportBundle
  retains immutable source namespace/checksum, actor/time and six typed batch links;
  progress derives from current batch states. Import Party data shows paginated
  history and stable Workspace review URLs. Reopening creates a fresh membership-checked
  receipt, while one-hour operator/Workspace approval expiry, role mapping, stale
  checks and atomic commit/replay remain unchanged. A saved page rejects approvals
  for another group. Empty/repeated uploads retain distinct history attempts.
  Owner-only migration 0010 is applied locally: ninth portability table, direct
  Workspace ownership, forced RLS, immutable SQL membership guards and model registry
  gate (108 Workspace-owned models). The migration recovers legacy staging-audit
  groups only when retained actor/source/profile/batch evidence matches; malformed,
  missing or overlapping groups are skipped without guessing. Reversal refuses
  retained history. Staging/history/audits share one transaction. No ZIP storage,
  dependency or business schema changes; individual workflows remain available.
  Validation: **273 tests passed, zero failures**, in 261.997 seconds across Party,
  portability and registry, including ten new history tests covering expiry,
  role-mapped atomic completion, live progress, current access/lifecycle, RLS,
  immutable/misbound SQL, rollback, empty/repeated groups, legacy recovery and CSRF.
  Runtime superuser/bypass flags are false; history RLS/force/grants are true.
  Database checks and migration drift pass; 566 tracked import boundaries and
  49 additional Python files, 325 documentation links and whitespace checks pass.
  No production operation or customer-data import;
  concurrent Loans work is preserved.
  **Exactly one next slice:** coordinated cancellation of all unfinished profiles
  in a saved bundle, preserving completed evidence and history. It has not started.
  Preset transfer/deletion, full archives, KYC files, Loans and physical erasure remain
  deferred; Loans restoration/opening-position semantics require separate contracts.

- Dependency-aware Party bundle review and atomic commit implemented locally
  (2026-09-12), documented in the
  [atomic decision](adr/2026-09-12-atomic-party-bundle-commit.md). Staging results link
  to one combined review with explicit role mapping and row-level normalized values,
  dispositions and before/after issues. The existing commands evaluate dependencies
  inside an always-rolled-back savepoint; no Party, identity, audit, batch revision
  or business code allocation is retained by preview. Internal sequence gaps can
  occur. This path must remain database-only or use on_commit for external effects.
  One-hour operator/Workspace-bound signed approval covers staged input, role
  definitions and the evaluated plan. Confirmation repeats the commands under locks,
  checks deferred constraints and compares the approved plan before saving all
  profiles together. Any error/staleness rolls back the aggregate. Completed immutable
  summaries retain its approval hash for permission-checked replay; aggregate and
  per-profile audits are retained only on success. The page uses normal Workspace,
  import/create/edit, CSRF, ACTIVE/commercial and no-store boundaries.
  No models, migrations, dependencies or business schema changes. Individual batch
  workflows remain; partially completed/cancelled bundles cannot be combined.
  Validation: **263 tests passed, zero failures**, in 204.896 seconds across Party,
  portability and registry. All 13 focused aggregate tests also passed, including
  concurrent confirmation, late rollback, stale input/destination, role mapping,
  permission rechecks, callback discard, CSRF and SQL marker immutability. An earlier
  concurrency fixture omitted its required address city and correctly received no
  approval; the fixture now supplies valid input and asserts preview readiness.
  Runtime database checks and migration drift are clean; 564 tracked import boundaries,
  46 additional Python files, 317 documentation links and whitespace checks pass. No production
  operation or real customer import; concurrent Loans work is preserved.
  The then-recommended persistent history follow-up is now implemented in the
  checkpoint above. Preset transfer,
  full archives, binary KYC and Loans remain deferred; Loans restoration/opening-position
  semantics require separate contracts.

- Same-day origination quote enforcement implemented locally (2026-09-12).
  Calculated/lower-of approval now requires today's positive Workspace quotes;
  the initial implementation uses today's loan/disbursal dates as the recommended
  scope assumption. Appraisal-only date behavior is unchanged. Approval freezes
  quote identity, source/author, price, dates and rule evidence. Disbursal rejects
  old, replaced, corrected/withdrawn or missing legacy quote evidence without
  changing approved amounts. Simple-review and renewal fingerprints bind quotes;
  completion rechecks preserve atomic rollback and authorized completed replay.
  Draft guidance separates availability from approval freshness, suggestions
  exclude later-today quotes, and loan detail/recovery pages show evidence/links.
  See the [decision](adr/2026-09-12-origination-quote-freshness.md) and
  [review](implementation/origination-rate-freshness-review.md). Historical entry
  remains an unconfirmed separate contract tracked in FW-005.
  Final isolated checkpoint validation: all **613 Loans/Rates/onboarding/routes/
  deployment tests passed** in 176.536 seconds. All 18 focused origination tests
  also passed, including renewal quote replacement, rollback and successful fresh
  review. All 43 control-plane contract-gate/operator-journey tests and four
  JavaScript preflight tests pass. The first isolated attempt reused
  a database containing unrelated portability tables and hit flush errors; the
  successful run uses a fresh dedicated test database. Earlier fixture/mock errors
  are resolved. The CI contract registry now names the renamed bounded-pass test.
  Browser inspection failed twice because the browser-control connection timed
  out; rendered response and service tests pass, but visual acceptance is pending.
  No normal-data mutation, worker startup or capacity benchmark occurred.
  Source-boundary, documentation-link and whitespace checks pass. Unrelated Party
  portability changes are excluded from this checkpoint.

- Party ZIP validation and staging implemented locally (2026-09-12), documented
  in the [staging decision](adr/2026-09-12-party-bundle-staging.md). The existing
  import page accepts `party-bundle/1` and validates the complete archive before
  staging all nonempty profiles into existing previews in one transaction. Strict
  path/member/schema/hash/count/reference checks reject unsupported or corrupted
  packages; empty profiles create no batches. No Party data is committed by upload.
  Existing context, RLS, import/read permissions, ACTIVE lifecycle and commercial
  checks remain enforced. Company serialization reserves the entire bundle against
  the 20-unfinished-batch limit, including concurrent uploads. A signed Workspace-bound
  receipt lists live profile previews; refresh cannot repeat the staging POST.
  Operators commit master, revalidate children, map role types and confirm each
  profile separately. Re-upload creates fresh previews; commit replay stays idempotent.
  Limits: 31 MiB compressed/expanded, 14 exact members, 128 KiB metadata members,
  1,000 records/5 MiB per entity. No extraction, retained ZIP, new models, migrations
  or dependencies. New exports advertise ZIP support; older exports remain accepted.
  Validation: **250 tests passed, zero failures**, in 161.687 seconds across Party,
  portability and registry, including 15 new parser/staging/concurrency tests.
  Fourteen parser/staging tests passed again after final fixture/error cleanup.
  Runtime database checks and migration drift are clean; 564 tracked import boundaries,
  44 additional Python files, current documentation links and whitespace checks pass.
  No production operation or real customer import; concurrent Loans changes preserved.
  The then-recommended combined review/atomic commit is now implemented in the
  checkpoint above. Preset transfer/deletion, full archives, binary KYC and Loans remain
  deferred; Loans restoration/opening-position semantics still need a separate contract.

- Bounded Party ZIP export implemented locally (2026-09-12), documented in the
  [bundle decision](adr/2026-09-12-party-export-bundle.md). `party-bundle/1` includes
  all six existing JSONL profiles, schemas, README and a checksummed manifest from
  one lock-stabilized snapshot. The existing export endpoint exposes the download
  with unchanged export/read permissions, CSRF protection and lifecycle recovery.
  Bounds: 1,000 records/5 MiB per profile and 1,000 role types for snapshot locking;
  any failure aborts all files, identity allocation and audit writes. Empty profiles
  remain explicit. Company locking briefly delays new Workspace-owned rows;
  existing Party/type/child locks prevent changes, and busy sources return retry.
  No models, migrations, dependencies, business schema changes or server file storage.
  Validation: **235 tests passed, zero failures**, in 136.894 seconds across Party,
  portability and tenant registry. Nine new bundle tests cover complete cross-Workspace
  import/replay, checksums, isolation, permissions, CSRF/recovery, overflow/rollback,
  restricted-role concurrent inserts/updates/deletes, busy sources and independent
  other-Workspace writes. Eight focused bundle/existing-download tests passed again
  after final response/manifest cleanup. Runtime database checks, migration drift,
  564 tracked import boundaries, 42 additional Python files, 296 documentation links
  and whitespace checks pass. No real customer import or production operation.
  Preset transfer/deletion, full archives, binary KYC and Loans remain deferred;
  Loans restoration/opening-position semantics still require a separate contract.
  The then-recommended ZIP validation/staging follow-up is now implemented in
  the checkpoint above. Aggregate import transactions remain deferred. Concurrent
  unrelated work is preserved.

- Monitoring checkpoint reviewed in an isolated export of the staged files
  (2026-09-12), excluding concurrent Party portability changes. All 519 Loans
  tests passed; the first invocation also reported one loader error from an
  incorrect Rates test-module label. The corrected Rates, onboarding, scoped-route
  and deployment run passed all 74 tests in 30.103 seconds. No application test
  failed. Staged Python syntax, 564 tracked import boundaries, current documentation
  links and whitespace checks pass. No large capacity test was restarted.
  The [origination review](implementation/origination-rate-freshness-review.md)
  records the owner's same-day quote requirement at approval and the missing
  approval quote provenance. Enforcement is not implemented. Delayed-disbursal,
  historical-date and legacy-approval handling are documented proposals for the
  next increment; monitoring age limits and existing loan terms remain unchanged.

- Bounded XLSX input implemented locally (2026-09-12) for all six Party profiles.
  The existing mapping/preview/approved atomic commit and canonical JSONL export
  pipeline accepts one visible values-only worksheet with text headers. Text,
  booleans and supported General numeric values preserve declared adapter semantics;
  native dates, custom numeric formats, excessive precision, formulas/cached formula
  values, hidden data, merged cells, links, macros and unsupported features fail.
  ZIP/XML structural limits and actual coordinate validation precede openpyxl loading;
  no filesystem extraction or malformed-batch persistence occurs.
  CSV/XLSX share source identity and matching preset versions. Migration 0009 is
  applied locally and extends only the existing SQL preset association guard;
  no new model, table, dependency or canonical business schema is introduced.
  See the [XLSX flow](flows/party-master-portability.md#xlsx-input-2026-09-12) and
  [decision](adr/2026-09-12-bounded-xlsx-input.md).
  Validation: all 226 portability/Party/registry tests passed in 136.682 seconds,
  including 21 XLSX parser/integration tests and a restricted-role concurrent XLSX
  preset commit. Runtime flags remain restricted; forced RLS/grants and the XLSX
  preset matching guard are verified. Database checks, model drift, 564 tracked
  import boundaries, 40 additional Python syntax/import checks, 285 local links
  and whitespace checks pass. No real customer import or production operation occurred.
  The then-recommended Party export bundle is now implemented in the checkpoint
  above. Full Workspace archives, binary KYC and Loans transfer remain deferred.
  Unrelated monitoring/capacity work is preserved.

- Reusable CSV mapping presets implemented locally (2026-09-12) for all six Party
  profiles. Operators save an exact reviewed CSV configuration under a name and
  select an immutable version on a matching profile/source/header batch. Applying
  copies the configuration and runs a fresh preview; current Party references,
  role types and commit permissions remain authoritative. Changed configurations
  append versions, identical latest saves replay, and earlier batch approvals stay
  unchanged. Explicit manual replacement clears preset association. The review UI
  displays current mapping, selected version and save confirmation.
  See the [preset flow](flows/party-master-portability.md#reusable-csv-mapping-presets-2026-09-12)
  and [decision](adr/2026-09-12-csv-mapping-presets.md).
  Migration 0008 is applied locally: MappingPresetVersion adds the eighth directly
  scoped portability table, and ImportBatch gains a nullable selected-version FK.
  Forced RLS, immutable version/batch-match guards and model-specific registry
  coverage protect the addition (107 registered Workspace-owned models). Runtime
  has neither superuser nor RLS bypass, grants and new-column access pass, and
  database checks report no issues. Party models and released exchange schemas
  are unchanged. There is no source-data transfer or production action.
  Validation: all 204 portability/Party/registry tests passed in 297.625 seconds,
  including 14 preset tests and two new restricted-role concurrent-save tests.
  The final save-confirmation UI recheck also passed (1 test).
  Model drift, 559 tracked import boundaries and 37 additional Python syntax/import
  checks and 268 documentation links pass. Presets are bounded to 1,000 retained versions per Workspace and
  256 KiB configuration each; defaults remain private and may contain customer data.
  The next recommendation at that checkpoint was bounded XLSX input for the
  implemented Party profiles (subsequently implemented). Preset deletion/transfer, JSONL presets, cross-file archives, binary
  KYC and Loans remain deferred. Unrelated monitoring/capacity work is preserved.

- Party relationship portability implemented locally (2026-09-12):
  `party-relationship/1` reuses staged CSV/JSONL mapping, preview approval, atomic
  commit and partial export. Both exact portable Party references are required;
  endpoint bindings are approved, locked and revalidated. Native directional
  from/to/type uniqueness (including inactive links), self-link rejection, notes
  and active state are preserved. Duplicate imports never overwrite or silently
  bind unrelated existing links. Replay/export detect moved endpoints; deletion
  retains immutable source evidence and both parent identities as a tombstone.
  See the [relationship flow](flows/party-master-portability.md#party-relationships-with-both-party-references-2026-09-12).
  Migration 0007 adds the nullable relationship target and related-parent FK to
  ChildIdentity and extends SQL guards without adding tables or changing Party
  models. It is applied locally. Runtime has neither superuser nor RLS bypass;
  forced RLS, DML grants, new-column access and database system checks pass.
  Validation: all 188 portability/Party/registry tests passed in 258.004 seconds,
  including 12 relationship tests and three new restricted-role concurrency tests
  for repeated commit, first export and both endpoint/relationship row locks.
  Model drift, 559 tracked import boundaries, 34 additional portability/shared
  Python syntax/import checks and 256 documentation links pass.
  The next recommendation at that checkpoint was reusable, versioned CSV mapping
  presets for the implemented Party profiles (subsequently implemented). Cross-file atomic archives, merge
  identity repair, XLSX, binary KYC and Loans remain deferred. No real customer
  import or production action occurred; unrelated monitoring work is preserved.

- Party role portability implemented locally (2026-09-12): `party-role/1` reuses
  staged CSV/JSONL mapping, preview/approval, atomic commit and partial export.
  Explicit source-key to active destination PartyRoleType mapping is mandatory;
  resolved definition snapshots are bound to approval and rechecked under locks.
  Imports preserve native active-role uniqueness, allow distinct inactive/ended
  history, and create no role definitions, memberships or staff permissions.
  Stable child aliases/results and tombstones apply; nonempty role metadata blocks
  export. See the [role flow](flows/party-master-portability.md#party-roles-with-explicit-type-mapping-2026-09-12).
  Migration 0006 extends ChildIdentity and SQL role/type/parent/Workspace guards,
  adding no table. Migration 0006 is applied locally; restricted runtime role,
  forced RLS/grants and database system checks pass. All 173 portability/Party/
  registry tests passed in 204.440 seconds, including a restricted-role contention
  test proving destination role rows remain locked. Two existing sequence assertions
  now explicitly select their test Workspace instead of counting owner-visible
  fixtures from other Workspaces. Model drift, 559 tracked import boundaries,
  30 portability/shared-service syntax/import checks, current documentation links
  and whitespace checks pass.
  The recommendation at this checkpoint was Party relationships with explicit
  references to both Parties (subsequently implemented). No production operation or real customer import
  occurred, and unrelated monitoring/capacity work is preserved.


- Party identifier portability implemented locally (2026-09-12):
  `party-identifier/1` adds identifier type/value, masked value and ISO expiry dates
  to the shared staged pipeline, with stable child identities, exact parent
  references and no-op replay. Source verification/timestamps remain provenance;
  local verification and Party PAN/GST summaries are unchanged. Duplicate types,
  source/local changes and deleted identities conflict. Metadata-bearing native
  identifiers fail export explicitly; binary documents and internal hashes remain
  outside the contract. See the [identifier flow](flows/party-master-portability.md#identifiers-without-documents-2026-09-12).
  Migration 0005 extends ChildIdentity and SQL relationship/result/tombstone guards;
  no new table or domain model is introduced. Existing Party save handlers reuse
  the shared identifier save helper. Migration 0005 is applied locally; the
  restricted runtime role, forced RLS, grants and database system checks pass.
  All 159 portability/Party/registry tests passed in 187.849 seconds, including
  identifier concurrency. Model drift checks, 559 tracked import boundaries,
  27 portability/shared-service syntax/import checks and current documentation
  links pass. No real customer import or production action occurred; unrelated monitoring/capacity work is preserved. The next recommendation at that checkpoint was Party roles
  with explicit role-type mapping (subsequently implemented).


- Party contact/address portability implemented locally (2026-09-12). The existing
  pipeline now selects `party-contact/1` and `party-address/1`, with exact portable
  parent references, CSV mapping, canonical JSONL, preview/approval, atomic commit,
  unchanged replay and partial export. Shared Party save helpers preserve native
  validation and primary/default behavior; source verification claims remain
  provenance only. Imports never demote existing primary/default records of the
  same type. Summary changes require warning acknowledgment; canonical phone
  ordering preserves the source summary, and inconsistent native summaries stop
  export explicitly. See the [child flow](flows/party-master-portability.md#contact-methods-and-addresses-2026-09-12)
  and [decision](adr/2026-09-12-party-child-portability.md).
  Two scoped identity/source tables and ImportRow.child_identity were added;
  migrations 0003/0004 are applied to local development. SQL guards enforce
  Workspace/parent/profile relationships, immutable evidence and deletion-only
  tombstones. The restricted development role, runtime grants and forced RLS on
  all seven tables are verified; database system checks are clean. Native deletion remains supported; moved identities require later
  explicit resolution. No production operation or real customer import occurred.
  Validation: the broader run passed 146 of 147 tests (177.466 seconds); its one
  concurrency error exposed JSONB default ordering changing approval messages.
  Default messages now sort deterministically. The final focused rerun passed all
  65 tests in 70.929 seconds, including both child concurrency cases.
  All 82 existing Party regressions in that broader run passed. Model drift,
  559 tracked import boundaries, 25 portability/shared-service syntax/import checks
  and current documentation links pass. The next recommendation at that checkpoint
  was Party identifiers without binary documents (subsequently implemented).
  Loans, generic tools, files, roles, relationships, full archives and erasure remain
  outside this increment. Existing unrelated monitoring/capacity work is preserved.


- Full-capacity baseline measured locally (2026-09-12), with eight restricted-role
  workers and concurrent portfolio reads/repayment-reversal pairs. The continuous
  100 x 3,000-active run failed the one-hour gate: 121,869/300,000 (40.6%) observed
  at 3,589.09 seconds; 122,400 after shutdown. Zero errors; sampled financial,
  quote-provenance and scoped isolation checks passed. Foreground p95 was 0.462
  seconds for portfolio reads and 0.275 seconds for repayment/reversal pairs
  (648 samples each). The 100 x 10,000-active/200,000-closed dataset was fully
  prepared (26.8 GB), but its timed phase suffered a 706-second measurement gap
  and stopped as invalid continuous-load evidence. Its 2,800 post-stop assessments
  are not a one-hour result. Available correctness checks passed; temporary-role
  cleanup and absence of remaining test clients were verified. A second upper-size
  retry was stopped at owner request after 19,185/1,000,000 assessments were observed
  at 940.65 seconds; zero errors were reported, but no final monetary-validation
  pass ran. Its clients are stopped and temporary role removed. Further large-scale
  testing is shelved until better hardware is available and the owner resumes it,
  under [FW-004](plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity). See the
  [capacity report](implementation/monitoring-capacity-test.md) for exact results,
  test overhead/limits, measured query bottlenecks and retry instructions.
  No normal development or production worker was started. The
  [Loan health guide](flows/loan-health-monitoring.md#when-a-loan-needs-another-assessment)
  documents daily/source-triggered refresh and operational DPD labels versus
  formal NPA classification; lender-specific NPA design is unscheduled FW-003.
  This turn changes benchmark tooling/documentation, not application rules.
  This monitoring-capacity work is included in `9a430aa2` and the current
  origination publication checkpoint.

- Party master portability implemented locally (2026-09-12): CSV/canonical JSONL
  staging, explicit mapping and normalization, validation/preview, approval-bound
  atomic commit, stable identities/source aliases, immutable provenance and canonical
  partial export. The [operator guide](flows/party-master-portability.md) describes
  the actual flow, limits and recovery access. Five directly Workspace-owned tables
  and two ordinary migrations are applied to local development; forced RLS, runtime
  grants and the restricted development role are verified. No customer records were
  imported into the normal development database and no production action occurred.
  The frozen Party schema and implementation deviations are recorded in the
  [contract](contracts/rokkad-data-v1.md) and [architecture](architecture/data-portability.md).
  The latest owner instruction permits leaving generic data-tools unchanged; their
  immediate-commit/authorization issues remain open. XLSX, Party children, Loans,
  files, full archives and erasure were deferred at this checkpoint. Its next
  recommendation was Party contact methods and addresses (subsequently implemented). Unrelated capacity work is preserved.
  Validation: the broad Party/tenancy/lifecycle/access/control-plane/export run
  executed 218 tests in 238.947 seconds: 217 passed and one unrelated test-discovery
  error. The control-plane registry still names Loans command test
  `test_reports_successful_bounded_batch`, renamed in concurrent monitoring work
  to `test_reports_successful_bounded_pass`; that reference was not changed by
  this slice. Both portability modules passed, including restricted-role round
  trips and concurrent commit/first export. The earlier focused run passed all
  37 tests before the additional within-batch duplicate regression. Documentation
  checks pass (215 local links in 17 documents), as do tracked import boundaries
  (559 Python files) and whitespace checks. No pending model migrations remain.

- Mixed-capacity/worker increment (local, after published `21a48aee`): all 591
  broader Loans, Rates, onboarding, scoped-route and deployment regressions passed
  (242.569 seconds). The first broad run exposed three old dashboard test doubles
  missing ORM prefetch support; those pure calculation tests now call the existing
  fold directly. Focused worker/concurrency/financial tests passed (30 tests,
  42.886 seconds). Mixed benchmarks at 3,000/10,000 active loans plus 600/2,000
  closed loans passed under restricted RLS, covering four product structures,
  repayment/reversal histories, multiple collateral items and price invalidation.
  Schedule prefetch reduced refresh-50 queries from 5,124 to 4,724 with matching
  financial results; no stable wall-time improvement is claimed for this change.
  The committed 10,000-loan worker sample refreshed 50 loans in 7.593 seconds.
  Worker passes now commit each loan separately and rotate through explicitly
  configured Workspaces, using a short busy pause while work succeeds. Concurrency
  checks prove earlier loan locks are released, completed work is visible, and
  another Workspace remains isolated. The owner selected a one-hour freshness
  target after a metal-price change; full 100-organization/300,000-1,000,000 active
  load acceptance remains outstanding. All 183 local documentation links across
  18 files, 559 tracked import boundaries, three new-module syntax/import checks
  and whitespace checks pass. No migration or development/production worker
  startup. Both capacity increments remain local and uncommitted. See the
  [mixed results and acceptance target](implementation/rates-appraisal-monitoring-review.md#mixed-workload-and-worker-increment-2026-09-11).

- First capacity increment (local, after published `21a48aee`): closed loans no
  longer receive live health reads, rate/policy/source invalidation or active
  alert work. Concurrent closure discards success/error refresh writes; a real
  release reversal resumes monitoring. Same-refresh component reuse preserves
  repayment/reversal results and rejects another loan/date. All 581 broader Loans,
  Rates, onboarding and scoped-route regressions passed (240.725 seconds).
  Homogeneous restricted-RLS benchmarks at 3,000 and 10,000 active loans passed:
  refresh-50 queries fell from 6,904 to 4,004 (42% fewer); the 10,000-loan sample
  fell from 10.479 to 4.623 seconds. This is an initial microbenchmark, not mixed
  production-load acceptance. All 169 documentation links across 15 files,
  559 tracked import boundaries and whitespace checks pass. No migration, worker
  startup or development policy mutation was needed. Capacity changes remain
  uncommitted for the next checkpoint. See the [results and remaining priority](implementation/rates-appraisal-monitoring-review.md#first-capacity-increment-2026-09-11).

- Checkpoint review: authenticated browser checks confirmed Loan health loads and
  shows the empty active-loan state; economic setup fields and history were
  inspected. Populated portfolio and amendment submissions were verified in
  disposable tests, preserving development policies. Amendment mode now has an
  explicit heading, save-new-version button and cancel link, including after
  validation errors. All 43 monitoring/setup checks passed (13.203 seconds),
  including a valid amendment, missing reason and duplicate submission. Browser
  screenshot capture timed out; no visual screenshot acceptance is claimed.

- Capacity review: owner specified 3,000-10,000 active loans per organization,
  30-100 loans processed per organization/day and at least 100 organizations.
  Active-only assessment selection is confirmed. Current worker cadence,
  duplicated reads, batch lock duration and residual closed-snapshot/alert work
  need launch-scale hardening. See the [capacity findings](implementation/rates-appraisal-monitoring-review.md#launch-capacity-requirements-and-review-2026-09-11).
  Existing regression results below do not establish this capacity. This review
  changes documentation only; no production load test or worker startup occurred.
- Monitoring completeness/amendment increment: all 576 broader Loans, Rates,
  onboarding and scoped-route regressions passed (224.937 seconds). All 83 final
  focused/concurrency/migration/deployment checks passed (45.085 seconds), followed
  by 24 coverage-basis display checks (7.068 seconds). Tests include first-failure
  recovery, committed and rolled-back invalidation under restricted RLS, competing
  batches/amendments, date rollover, incomplete totals and upgrade preservation.
  Loans 0007 is applied to local `rokkad_shared_dev`; runtime/database, pending
  migration and drift checks pass. Four JavaScript guards, 544 tracked import
  boundaries, 15 new Python modules, 179 documentation links across 21 files and
  whitespace pass. Both Compose configurations validate without resolving secrets.
  Optional repeating-worker wiring is implemented but has not been started or
  deployed. All four Rates/appraisal/monitoring increments are included in this reviewed
  checkpoint, published as `21a48aee` on `origin/rls-mvp`.
- Freshness/reappraisal increment: all 558 broader Loans, Rates, route and operator
  regressions passed (190.570 seconds); 53 final focused checks passed (29.606
  seconds), including competing reviewers, read-only history access, original
  approval/as-of preservation, transaction-local risk invalidation, and restricted
  SQL rejection of appraisal mutation/cross-item or cross-Workspace linkage.
  The migration rehearsal preserved legacy appraisal values/dates/authors and
  marked saved assessments stale. Loans migration 0006 is applied to local
  `rokkad_shared_dev`; runtime/database, pending-migration and drift checks pass.
  Four JavaScript guards, 544-file tracked import guard, all 13 new Python modules,
  163 links in 18 documentation files, and whitespace pass. No production or
  physical-device acceptance. All three Rates/appraisal increments are uncommitted.
- Rates quote-evidence increment: all 563 Loans, Rates, onboarding, scoped-route
  and operator-journey tests passed in a fresh disposable database (192.195 seconds).
  Final focused checks passed all 31 tests (12.767 seconds), including the final
  quote-detail link, migration rehearsal, concurrent corrections and restricted-role
  cross-Workspace revision denial. Four JavaScript preflight tests also pass.
  The upgrade test preserves an invalid legacy quote's amount, purity and date and
  proves it can be withdrawn without deleting history. Import checks cover 544
  tracked files and all seven new Python modules; 152 links across 16 current docs
  and whitespace pass. Migration drift is clear. Rates migration 0003 is applied
  to local `rokkad_shared_dev`; restricted runtime/database checks and the pending
  migration check pass. Existing quote values are preserved. No production action
  or physical device acceptance. Both Rates increments remain uncommitted.
- Rates setup/readiness increment: all 137 focused Loans, onboarding, scoped-route,
  Rates access and RLS tests passed (67.068 seconds) in a fresh disposable test
  database. Four Node preflight interaction tests passed, covering missing prices,
  successful submission, stale responses and retry after failure. Runtime check,
  migration drift, tracked-source and all three new-module import checks pass.
  No schema changes or normal development data changes. The first broader run
  encountered retained test-data assumptions; the fresh-database run passed.
  Physical browser/device acceptance remains outstanding; quote age enforcement
  belongs to the subsequent freshness increment. Changes are local and uncommitted.
- Custody form extraction: all 78 collateral/media/storage/verification, setup UI
  and scoped-route tests passed (57.905 seconds). The initial run exposed three
  funding UI tests assuming globally empty tables; scoping their lookups and
  numbering assertions to the fixture Workspace fixed them. Runtime behavior is
  unchanged. Across funding/custody, all 31 class ASTs and three formset definitions
  match; 13 public aliases preserve class identity. Runtime/import checks,
  explicit new-module boundary checks, 139 documentation links and whitespace pass.
- Funding form extraction: all 103 setup UI, funding service/persistence/domain
  and scoped-route tests passed (56.212 seconds). All 31 previous forms.py class
  ASTs match and all eight public aliases preserve class identity. Runtime check,
  tracked import guard, explicit new-module boundary check, 139 documentation
  links and whitespace checks pass.
- Economic form extraction: all 69 economic-default, setup UI, economic-policy,
  pawn-economics and scoped-route tests passed (26.998 seconds). All 34 original
  class ASTs from the previous forms.py checkpoint match; three public aliases
  preserve class identity. Runtime check, tracked import guard and explicit new
  module import-boundary validation pass. Documentation links and whitespace pass.
- [Workspace RLS checks for 16be7149](https://github.com/rajeshr188/rokkad/actions/runs/34594565045)
  passed, including dependency/docs/import checks, migration and restricted-runtime
  gates, boundary/first-loan checks, Loans regressions, image build and image
  runtime/static assets. Remaining-form review changes documentation only; all
  139 checked local documentation links pass.
- License/series form extraction: all 62 setup UI, license regulatory and scoped
  route tests passed (28.185 seconds). Across both form extractions, all 50
  original class ASTs match and all 16 public aliases preserve class identity.
  Runtime system check and tracked import guard pass; both new, untracked form
  modules also pass the same import-boundary validator explicitly.
- Document form extraction: 121 document/layout/print-profile, scoped-route and
  shell tests passed (18.438 seconds), plus all 32 setup UI tests (7.590 seconds).
  All 50 form class ASTs are unchanged; all 13 compatibility imports resolve to
  the owning class objects. Runtime system check, import-boundary check and its
  four unit tests, 138 documentation links and whitespace checks pass.
- [Workspace RLS checks for 38eb1e3](https://github.com/rajeshr188/rokkad/actions/runs/34591042913)
  passed: dependencies/docs/import boundaries, owner migrations and restricted
  runtime checks, boundary/first-loan checks, Loans regressions, image build and
  image runtime/static assets. Publication/review documentation passes all 138
  checked local links; no application changes were made during this review.
- Orgs views completion: all 229 orgs, invitations, ownership, role-grant, lifecycle,
  context/platform-override, shell, Loans-route and retirement checks passed
  (29.893 seconds). All 14 route-map source checks passed after the path update.
  Sixty-six moved function/class ASTs match; 137 public exports remain. No unresolved
  globals or imports back to orgs.views. System check, migration drift, import guard,
  current-doc links and staged whitespace pass. No business/schema changes.

- Lifecycle/navigation extraction: all 171 orgs, lifecycle, ownership, context,
  platform-override, slug-shell, shell-render and Loans-route tests passed
  (28.329 seconds). The updated dashboard source-dependency check passed separately.
  Seven function/decorator ASTs match; no unresolved globals or imports back to
  views.py. System check, migration drift, import guard, documentation links and
  staged whitespace pass. No service/model/template or policy changes.

- Team/invitation extraction: all 161 orgs, invitation/verified-email, ownership,
  role-grant, lifecycle, slug-shell and shell-render checks passed (14.363 seconds).
  Eleven handlers and three helpers retain identical ASTs; mock targets were
  updated without changing assertions. System check, migration drift, import guard,
  documentation links and staged whitespace checks pass. No policy/schema changes.

- First orgs extraction: all 174 workspace/settings, role-grant, ownership,
  lifecycle, shell and Loans-route tests passed in the final run (29.900 seconds).
  Nine handlers and three helpers retain identical function/decorator ASTs.
  Test mocks follow moved dependencies; assertions remain unchanged. Runtime
  system check, migration drift, 532-file import guard, 136 current-doc links and
  staged whitespace checks pass. No service, model, template or permission changes.

- Loans views completion: all 595 Loans, Party UI/history, route and shell tests
  passed together (124.773 seconds), plus four import-guard unit tests. All 56
  moved function/decorator ASTs match; 142 existing handler/helper exports remain
  available. No unresolved globals, feature-module cycles or imports back to
  views.py. Runtime system check, migration drift, import guard (528 Python files),
  132 current-doc links and staged whitespace checks pass. No business/schema changes.

- R12 print-profile setup: all 115 setup, print-profile, layout, document-issuance
  and Workspace-route tests passed. Nine handlers and two helpers retain identical
  function/decorator ASTs. Shared preview assets load through one helper without
  importing views.py. Runtime system, import-boundary, documentation-link and
  whitespace checks pass.

- R12 license/series setup: all 90 setup, license services/regulatory, numbering,
  notice and Workspace-route tests passed. Twelve handlers and four helpers retain
  identical function/decorator ASTs; two mock targets follow the moved dependencies.
  Runtime system, import-boundary, documentation-link and whitespace checks pass.

- R12 economic setup: all 58 setup/Workspace-route tests passed. Handler and
  decorator ASTs match the original; ten imports moved to the dedicated module.
  Runtime system, import-boundary, documentation-link and whitespace checks pass.

- R12 product setup: all 66 product-catalog/setup/Workspace-route tests passed.
  Moved five handlers (62 lines) with matching function/decorator ASTs; original
  public imports and route callbacks retained. Runtime system, staged import guard,
  documentation-link and whitespace checks pass.

- Checkpoint review: all 680 Loans/Party UI/billing/onboarding/deployment/route/shell
  tests passed in one combined run. Four import-guard unit checks, the staged-source
  import scan (514 Python files), runtime system check, migration drift and 128
  documentation links passed. Staged whitespace is clean after normalizing malformed
  line endings in five archived documents. Credential-pattern and artifact checks
  found no unexpected staged files; local secrets, logs and media are excluded.

- R07 complete: the broad Loans, borrower UI, legacy route and shell run exercised
  594 tests: 591 passed and three stale compatibility/UI assertions failed.
  Corrected those expectations; all 50 focused route/legacy/shell tests then passed,
  including a new response-preservation test (595 unique checks covered across runs).
  Earlier focused runs also corrected obsolete URL expectations, a query-chain
  mock and a whole-database assertion that needed to target its own series.
- All 136 canonical routes resolve directly and preserve their original decorated
  callbacks. Two-Workspace page checks prohibit dispatcher use; membership/domain
  conflicts, CSRF, action permissions, lifecycle/numbering, HTML/HTMX navigation,
  binary documents and streaming response preservation are covered. No business
  service or schema change. Runtime system, 128 current-doc links and whitespace
  checks pass. Provider and physical-device acceptance remain deferred.
- Per-family history is retained in the [routing record](implementation/loans-workspace-routing.md).

- R11 batching: 54 targeted regressions and the 100-loan benchmark passed.
  Queries fell from 401 to 5; median selector time from 418 ms to 19 ms
  (restricted role also 19 ms). Persisted schedule/payment/reversal parity and
  foreign-Workspace denial verified. No schema or cache changes.

- Saved the approved gold-stroke / Hindi ra monogram logo as
  `static/images/brand/rokkad-bilingual-monogram.png`; verified byte-for-byte
  against the generated source. This save does not replace current UI assets.

- Branding: runtime system check, static collection dry run, eight affected
  template compilation checks, Hindi text checks, documentation links, and diff
  whitespace checks passed. Existing shell smoke suite: 15 passed,
  one setup-page failure reproduced with pre-branding base/navigation templates
  (`test_workspace_settings_setup_page_renders_checklist`); its stale label assertions
  were corrected and the shell suite passed during R07 completion. Desktop (1440px) and
  mobile (375px) browser renders of home, login, Workspace, portal, and admin
  loaded the logo without horizontal overflow. Bootstrap was cached for visual
  verification because sandbox browser access to the CDN was unavailable;
  external icon fonts/scripts were not part of this visual check. No deployment,
  billing-provider action, or issued-document mutation was performed.

- R11: 33 selector/template/route tests and a synthetic 100-loan service-backed
  benchmark passed. Queue calculation: 5/41/201/401 queries at 1/10/50/100 active
  bullet loans; 100-loan median 418 ms. See [scope and baseline](implementation/dashboard-reliability.md).

- R13: 73 route/Party UI/dashboard-selector/deployment checks passed. Clean Docker
  build and pip check passed; removed packages verified absent, current templates
  loaded, model/template/URL checks and static collection passed without network.
  Local runtime check and migration drift passed. Corrected the rollout-doc test
  to inspect the linked R08 history. See [removal evidence](implementation/dependency-template-cleanup.md).

- R09/R10: 26 onboarding/deployment tests and four import-guard tests passed;
  guard scanned 493 tracked Python files. New tour preferences preserve historical
  answers and confer no membership/permissions. Removed only definition-only
  schema-tenancy settings. Runtime system check, migration drift, local-doc links
  and whitespace pass; no migration or normal development data changes.

- Foundation: 90 foundation/access/MVP checks plus six deployment-entrypoint tests;
  clean Docker build, restricted startup/HTTP smoke, negative owner-role startup
  and collectstatic verified in a removed disposable stack.
- Operator commands: 25 command/product/notice checks, including fresh-process
  restricted-role context and cleanup.
- Paid expiry: 51 subscription checks and 65 broader boundary checks (overlapping).
- Recovery: 15 dedicated checks, including concurrency, rollback and scope denial.
- Final reviews: 46 review/recovery/checkout checks, followed by 12 final review
  checks including concurrency and rollback. Provider I/O and receipt mail mocked.
- Latest documentation increment: 119 local links/fragments across 12 curated
  entry files and whitespace checked. Nine prior documents (8,066 source lines)
  preserved with archive notices and rebased relative links. No runtime behavior or schema changes; no database suite needed.

Exact historical validation and known limitations are retained in the
[status snapshot](archive/context/2026-09-09/STATUS.md). These counts describe runs
at their checkpoints, not a claim that one fresh whole-repository suite ran today.
The fb3db63 CI run was superseded by the publication-record push.
[Workspace RLS checks for af22f23](https://github.com/rajeshr188/rokkad/actions/runs/34588817552)
passed, including dependency/docs/import gates, runtime-role and boundary/first-loan
checks, Loans regressions, image build and image runtime/static-asset verification.

## Deferred acceptance and owner decisions

[FW-001](plans/future-work.md#fw-001-optional-owner-configurable-license-scope):
license scoping is optional and shelved; fresh review and explicit approval required.
[FW-002](plans/future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance):
Razorpay setup/provider testing is shelved; the owner has not begun setup. Mocked
billing checks do not establish real paid-onboarding acceptance.

Physical phone/camera and printer checks remain deferred. External storage/CDN
privacy, production TLS/restore/alerting and selected-deployment acceptance remain
open. Orphan/legacy payment contracts are support investigations, not guessed
reconstructions. Refund issuance, proration and chargebacks are not automated.

## Next increment

The owner requested a Rates/appraisal/monitoring review after a missing quote
blocked new-loan creation. [Review findings and proposed increments](implementation/rates-appraisal-monitoring-review.md)
are documented and the order is approved. Increment 1 is implemented locally:
shared usable-quote guidance in setup, actual series/date/metal preflight, a Rates
detour that keeps the form in place, and row-specific missing-input errors.
Increment 2 is also implemented locally: effective-dated, append-only quote
corrections/withdrawals, explicit pure-metal/per-gram entry, positive validation,
actor/source snapshots, protected source history and corresponding lookup/risk
invalidation changes. Rates migration 0003 is applied to the development database;
regression, migration and restricted-runtime validation passed.
See the [quote operator guide](flows/metal-rate-entry.md). Increment 3 is implemented:
current monitoring enforces configured quote/appraisal ages, and active held
collateral supports reviewed, immutable appraisal versions with reference context.
See [reassessment](flows/collateral-reassessment.md). Migration/regression validation
passed; Loans 0006 is applied locally. Increment 4 is implemented locally: all-active portfolio coverage, date-based
freshness, bounded repeating refresh, transactional invalidation and immutable
policy amendments. Validation passed and Loans 0007 is applied to local `rokkad_shared_dev`.
UI and amendment submission review is complete; checkpoint `21a48aee` is pushed.
The 100 x 3,000-active capacity test failed its one-hour gate locally. Fair bounded
worker turns and closed-loan cleanup are implemented. Further large-scale testing
is owner-shelved until better hardware is available under
[FW-004](plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity); the one-hour
capacity target remains unproven. See the [capacity report](implementation/monitoring-capacity-test.md).
The optional repeating worker still requires explicit Workspace configuration and startup.
See [Loan health](flows/loan-health-monitoring.md). The owner selected same-day
quotes at approval; enforcement and quote provenance are now implemented locally.
See the [origination review](implementation/origination-rate-freshness-review.md).
Historical entry remains a separate unconfirmed contract (FW-005).

The selected Loans view organization work is complete; see the
[module map and compatibility rules](implementation/loans-view-organization.md).
The orgs view split is also complete; see the
[orgs module map](implementation/orgs-view-organization.md). Publication and CI
verification are complete. Document layout and print-profile forms are extracted
along with the three license/series setup forms in this checkpoint. The remaining
form-family review's economic-setup extraction is complete in this local checkpoint.
Funding and storage/physical-verification forms are also extracted locally.
The selected form extractions are published, and publication CI passed for
`1fea70be`. Intake/lifecycle forms remain together. See the
[review and validation scope](plans/project-hardening.md#remaining-r12-module-review).
Model and renewal-service restructuring are lower priority and remain unimplemented.
Razorpay and license scoping remain shelved.

Keep this file short: update current state and relevant evidence; move superseded
milestones to the [context archive](archive/context/README.md), retaining links.
