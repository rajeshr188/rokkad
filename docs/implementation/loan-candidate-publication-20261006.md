---
status: active
owner: project
updated: 2026-10-06
tags: [loans, release, production, verification]
---

# Loan candidate publication and production acceptance

## Latest verified candidate and copied inventory

The current runtime candidate is **ef3c82a539ef4116b60902be48bf616f2dbf47d8**.
Its [full release CI](https://github.com/rajeshr188/rokkad/actions/runs/37482671270)
passes every gate. The separately identified clean server-built image is
rokkad:loan-continuation-ef3c82a5-server, image ID
**sha256:24ab73c0732e417e6b5b22b656e0bb6bfdcbb677a4e4e6f4dc61f0fb880ea2a7**.
The committed source ZIP SHA-256 is
**c62fa283549dc13472f46647d4034fd28db64275603ca47b2b490a29d0e17585**.
This is a staging artifact, not a production deployment.

Owner migrations from Loans 0032 to 0063 and dependencies pass on the approved
same-server restore. Restricted runtime/schema drift, owner-startup rejection
and original pending-migration rejection are verified. The query correction has
no migration/startup change. Selected RA00500/D01623 reads and no-context /
cross-Workspace RLS reads pass under the current committed artifact.

Complete restricted repeatable-read/read-only inventories finished at
**20:43:24 IST** against the consistent **19:26:18 IST** source snapshot:

| Workspace | Active | Closed | Supported active/closed | Unadmitted archive identities |
| --- | ---: | ---: | ---: | ---: |
| JCL | 2,598 | 10 | 2,608 | 26,664 |
| JSK | 1,580 | 79 | 1,659 | 3,840 |
| Lakshmi | 2,440 | 0 | 2,440 | 8,711 |

JCL also has one APPROVED loan; JSK one APPROVED and six CANCELLED; Lakshmi two
DRAFT. All **6,707** ordinary active/closed calculations are supported by their
retained contracts: **316** native-event-fold/1 and **6,391** opening profile /2.
No contract is automatically adopted. Transaction coverage is SYSTEM_RECORDED
for **303**, UNCONFIRMED for **6,404**. Assessment freshness is STALE for **152**
and UNASSESSED for **6,555**; valuation is UNASSESSED for all **6,707**. These are
independent cohort flags, not collection authorization or a claim that a refresh
will succeed without eligible valuation/book evidence.

All **183** original non-metadata table projections preserve every source
row/value before and after these checks. Only new additive columns are excluded
from original projections; Django migration/content-type/permission rows are
expected to change. The 39,215 archives remain retained source claims, not
automatically admitted ordinary closed financial records.

The final directory fix passes **14** browsing/inventory regressions (13.424s)
and **47** archive/admission regressions on a fresh generated database (34.112s).
The first broader reused-QA attempt encountered a pre-existing global-rate fixture
and failed one global exists assertion; the fresh run passes all 47 and destroys
its own generated database. The real current-artifact inventory is complete;
the earlier provisional mounted-module probe below remains historical.

## Integrity-query capacity finding and recovery preparation

A verification-only SQL sort of expanded customer JSON failed with PostgreSQL
temporary-file **No space left on device**. The failed query stopped; it did not
post finance. Resource contention on the shared host is a real finding; absence
of a production availability impact has not been established.

The replacement streams original COPY rows from the sealed custom-format backup
and original-column COPY rows from staging, hashes each row with SHA-256, and
sorts only fixed-size hashes in operator memory. Row counts and complete sorted
row multisets match for all 183 original business/evidence projections.
No expanded SQL sort or full customer export to this workstation is needed.
Original backup checksum, column maps and fingerprint evidence remain server-only.

Free disk was **796,966,912 bytes**. Only this rehearsal's unused superseded
59f62107 server image and exact identified 14:21/14:54 staging cache IDs were
removed. There was no global image/cache/volume prune. Free space became
**1,840,254,976 bytes**; current candidate/production image identities and sealed
backups remain intact. Capacity must be checked again for an eventual release.
The cold checkpoint/restore uses the same already approved staging database,
validates the backup catalogue before replacement and streams the backup to
restore without a redundant container-local dump. Cold recovery **passes at
20:56:11 IST**: all **202 public tables and 199 sequence positions** restore
exactly. Restricted startup, RA00500/D01623 reads and all three Workspace censuses
repeat successfully; the full pre-restore cohort results are retained because
all restored rows and the reader artifact match. The full all-loan forecast cohort
calculation was not repeated after restore. Post-read table/sequence comparisons
remain equal, and the production image is unchanged.

The migrated stage checkpoint is **83,484,273 bytes**, SHA-256
**67d737d2d1a4ae2073393a0c47a6ca504c0804610f741fc4a5135e03005c25f2**.
It and the original source backup remain in the approved private server folder.
This recovery replaces only the disposable staging database; production is not
migrated, financially posted or deployed. About 1.7 GiB headroom remains after
recovery, so capacity still needs review before rollout.
Actual media remains unavailable in this rehearsal; private local media is empty.

**Remaining:** D01623 correction implementation and acceptance; a real direct-entry
source comparison; actual book/monitoring disposition and staff acceptance; actual
media recovery and separately authorized production rollout. The following sections
retain the publication/check history and findings, not a deployment-ready claim.

The owner requested proceeding with commit/CI, live cohort inventory, real source
examples and staging on 6 October. The accepted local LC-01–07 candidate includes
the separately completed LD work already committed on
`work/loan-servicing-contract-ld01`. Local source, finance/portability regressions,
restricted runtime and fictional full recovery are recorded in
[LC-07 delivery](loan-release-acceptance-lc07.md).

Candidate `b69df6ab71af27a85100cfa59325bd85f097323f` is committed and pushed.
Its clean committed-source image is `rokkad:loan-continuation-b69df6ab`, digest
`sha256:2453bbf53a5cd0642138b76d7900a2aad7cd7230638ec556162063e8ae4d629a`.
The first [exact-commit CI run](https://github.com/rajeshr188/rokkad/actions/runs/37455205020)
failed in foundation checks: 14 journey fixtures omitted current public-trial
requirements, and one auction-access mock omitted the command business-write
prerequisite. The fixtures are corrected without changing runtime policy:
verified sign-in email, explicitly selected six-member trial and current consent;
second-Workspace isolation fixtures use separate test commercial access. The
auction unit fixture verifies delegation to the business-write boundary.
All **24 journey/access tests pass** (117.532s) in isolated PostgreSQL QA; current
docs/import boundaries and whitespace checks pass. A new exact-head CI run is required.
The correction commit is `dce0d00a5e9b31979ed6d5ab98d50841cca3f91c`; its
[rerun](https://github.com/rajeshr188/rokkad/actions/runs/37456878400) passes the
foundation step. Its clean committed-source image digest is
`sha256:1b8d27d5f7bb8f8488c788368723973a87027dbe03ebee7b5001e2b8d878c37f`.
Production-settings restricted runtime, schema/cohort reads and actual owner-role
rejection pass on both fictional recovery databases, with all 202 public tables
unchanged. The first local owner-rejection attempt mistakenly retained runtime
credentials; it did not test owner startup and was corrected before reporting
the complete successful check. None of these are a production-copy rehearsal.

The release CI job allowance is raised from 25 to 45 minutes because the Loans
suite now contains over 1,800 test methods, besides foundation, recurring/mail,
quote/isolation and image gates. No checks are removed. A new exact-head run is
required after this workflow change.

CI on `dce0d00a` completed the 277-check billing/mail stage with one error in the
static invitation-flow assertion (not a billing/provider runtime failure).
CI on `422763d5` reproduces that same error. The old assertion expected invitation
mutation immediately after opening the transaction, omitting the current Company
lock, policy and capacity checks. It is corrected to compare policy/mutation order
within each function and retain the transaction-before-mutation assertion.
All **15 invitation static checks pass** locally (0.009s), after the runtime-image
QA harness was supplied with the required repository docs fixture. Publication
and exact-head CI await the corrected full Loans-suite run. The first local run
completed **1,296 tests in 821.602s**, with three failures and 82 errors. Its
namespace-package discovery imported many files without package context. An
explicit repository top level discovers **2,089 tests and zero import errors**;
the CI Loans command now specifies it. Three historical migration tests also
downgraded the shared database across an irreversible migration and left later
tests on an older schema. Separate empty migration-test databases now
copy only explicitly supplied generated fixtures and their
prerequisites, never production/customer records. The shared QA schema is restored.
The missing-submission-reference runtime correction preserves invalid POST
references instead of silently replacing them. Entry-purpose switches retain an
existing reference and create one only if absent. Quote-policy and receipt-format unit fixes
pass **three checks** (0.041s). All **41 migration/submission/opening/paper-entry/
recovery regressions pass** (215.625s), including all three isolated populated
upgrades and exact recovery. PostgreSQL's earlier deadlock log identifies
autovacuum competing with the test fixture transaction; the isolated recovery
rerun passes. No recovery lock is weakened and autovacuum is not disabled.
The correctly discovered full suite and exact-head CI remain pending.

Commit `13be3ae90360aa7445fe5c6fdb00924824e333a4` is pushed. Its
[CI run](https://github.com/rajeshr188/rokkad/actions/runs/37462610675) passes
migrations/startup, foundation and billing/mail. All **2,089 Loans tests** run
(1397.670s), with three failures and four errors: two restore tests required an
untracked `.tmp` folder; two recovery tests deadlocked; three assertions exposed
chronology wording, a one-day quote incorrectly treated as expired, and a replaced
entry-purpose roundtrip reference. Standard temporary directories remove the local
folder assumption. Test recovery fixtures now take the existing archive table
locks before any fixture writes, matching offline-command ordering and avoiding
the identified autovacuum cycle. Production locks and autovacuum remain unchanged.
The chronology assertion uses the current error; quote expiry is checked at day
eight; entry switching preserves the supplied reference. All **eight finding and
missing-reference guard regressions pass** (13.759s); full corrected CI is pending.
All **35 related multi-item entry/submission/quote regressions pass** (18.465s).

The 13be3ae9 image is
`sha256:a9a50c37778f39356faa5a85a22eef2f09432ec56a6f7c800c83415ecb039878`.
Production-settings restricted startup, schema/cohort reads and owner-role startup
rejection pass on both fictional recovery databases. All **202 public tables remain
unchanged**. This is still not production-copy recovery or source acceptance.

Commit `e3c95ba4c137f5c83a9d14a872f6b0b41c9aa1d8` is pushed. Its
[CI run](https://github.com/rajeshr188/rokkad/actions/runs/37467856353) passes
all **2,089 Loans tests** (933.489s), all **203 foundation checks** and all
**277 billing/mail checks**. The later 34-test quote gate fails in its old
migration test, which downgrades the shared database across irreversible Loans
0058; the following RLS quote reader then sees a missing quote-age column.
The migration rehearsal now uses its own empty historical database, preserves
legacy values/dates/unknown authors and checks withdrawal through the upgraded
database guard. Command permissions and RLS remain covered by the other quote
tests. Once schema isolation is corrected, the temporary Rates-only test role
also needs read-only access to Loans quote-age settings; that grant is added
without superuser, bypass-RLS or settings-write privileges.
All **34 quote/migration/isolation checks pass locally** (28.279s). The workflow
runs this shorter gate before Loans for faster migration-failure feedback; no
check is removed. Final corrected exact-head CI is pending.

The e3c95ba4 image is
`sha256:6e7589ad269751b37ce818859232fd85ab94a694c9e32a813e64fc6ae2cffd49`.
Production-settings restricted startup, schema/cohort reads and owner-role startup
rejection again pass on both fictional recovery databases. All **202 public
tables remain unchanged**. Production-copy approval and actual acceptance remain
separate pending gates.

Final test/ordering correction `59f62107067c6311cbaed77d4761a78c8f4a9b6e` is
committed and pushed. Its [full rerun](https://github.com/rajeshr188/rokkad/actions/runs/37473199386)
**passes every release gate**. Runtime loan code is unchanged from the fully passing Loans
candidate e3c95ba4; the final changes concern Rates test isolation/grants, workflow
ordering and execution documentation. Every release check remains enabled.
The clean final image is
`sha256:18bd706e4a176ef65997944e18191a61bc9c823cff7d05876b2e5243d4a99069`.
Production-settings restricted startup, schema/cohort reads and owner-role startup
rejection pass on both fictional recovery databases; all **202 public tables
remain unchanged**. The later documentation-only evidence commit does not replace
the pinned candidate image/source/CI identity. Full CI is green and the approved
private copy is exact; upgrade/recovery, actual source acceptance and the D01623 correction remain open; no
production deployment or financial admission is claimed.
CI must pass against the exact published commit before
the candidate is treated as verified for release. Real-source acceptance and the
production-copy migration rehearsal are additional gates; a branch push does not
deploy the application. No live loan, source archive or risk snapshot is changed
by this verification.

## Production baseline captured on 6 October

The established deployment transport is available. A probe inside the existing
production app verified a non-superuser/non-bypass runtime and PostgreSQL
repeatable-read/read-only enforcement. The database is
`rokkad_production_20260924`; Loans is at `0032_series_partial_interest` and
data portability at `0017_loan_history_v2`. The live application image is
`rokkad:ticket-autofit-20261001-8dd479dbb0bf`.

The following is one consistent read at **16:43:27 IST**, not a frozen ongoing
claim. Staff were recording real JSK closures between probes.

| Workspace | Active | Closed | Other states | Retained archive snapshots |
| --- | ---: | ---: | --- | ---: |
| JCL | 2,592 | 10 | 1 approved | 26,664 |
| JSK | 1,585 | 73 | 1 approved, 6 cancelled | 3,840 |
| Lakshmi Pawn Broker | 2,440 | 0 | 2 drafts | 8,711 |

These archive counts are retained evidence, not automatically admitted ordinary
closed loans. Source financial-origin event counts are JCL 165 disbursals/2,438
openings, JSK 145/1,514 and Lakshmi 2/2,439. Counts of source events are not current
active-origin counts: reversals and current state must be examined by the candidate
on an isolated, consistent production restore.

The owner confirmed **JCL RA00500** (correcting RA0500). It is an active loan dated
2 September 2026, principal 60,000 at 2% monthly, three-month tenure, admitted by
a 24 September migration opening. It is an opening example, not direct lending.
Its recorded principal is not proof of collection interest or complete books.

The owner also selected **Lakshmi D01623**. Rokkad stores a DRAFT with an October
2 disbursal and its reversal, so its current recorded debt is zero. The owner
confirmed the actual paper facts: 24 September payout, principal 2,100 at 4%
monthly, 84 advance interest and 10 document charge, net proceeds 2,006,
three-month tenure and no later receipts or closure. Verification must preserve
the reversal and test the retained-native correction adapter; no actual source
event or draft has been changed. The current 12-month standing default must not
replace the actual three-month agreement.
Borrower names, documents, attachments and free-text evidence are not included in
the sanitized baseline. Private probe evidence is under
`.tmp/lc07-publish-20261006/`.

## Production-copy approval gate

Automatic approval review rejected the full server-side production copy because
the general staging authorization did not explicitly cover the sensitive payload
and destination. The rejected operation did not execute. The owner subsequently
explicitly approved copying `rokkad_production_20260924` into the new private database
`rokkad_lc07_stage_b69df6ab_20261006` on the same established server. Full backups
remain in its private deployment folder, without a customer-data download
to this local workspace. A separate runtime role, local file storage, disabled
notifications/provider calls and no public routing are required. Production
data/application remain unchanged. This duplicates all tenants' sensitive records
and consumes disk; it was retried only after explicit approval.

The approved copy completed from a consistent **6 October 19:26:18 IST** exported
read-only snapshot. All **186 public tables** match the new restore by row counts
and sorted complete-row fingerprints. The compressed backup is **83,215,176
bytes**, SHA-256
`f2baf7ade484450a05e975e0cc154993e36e5bb8fc4c7beaa176cd0bb01bb0b2`.
Backup, source fingerprints and runtime credentials remain inside the server's
mode-0700 `loan-continuation-20261006-b69df6ab` folder. No full dump/customer
records were copied off-server. This checkpoint has not copied or verified actual
R2 media; database recovery and media recovery remain distinct. Production
migrations, loan financial writes and routing changes were not performed.

## Approved restore upgrade rehearsal

The large local application-image transfer was too slow. Two unfinished loads
were stopped, without replacing the production image or changing routing.
Instead, the clean `59f62107` Git archive was uploaded and rebuilt on the server.
The input archive SHA-256 matches the local committed build:
`3b63a25890e9e4aec28bc9348d823ecfc26c3bd287be6bd1f6ec2406f4439e94`.
Staging uses `rokkad:loan-continuation-59f62107-server`, image ID
`sha256:2357a5c1974c3a3944b6cc301dc025a1056b0297101f2d8719d2f6c21d43adef`.
This server-built artifact is distinct from the earlier local image; its source
commit is identical to the green full CI. All server rehearsal reports identify
this actual artifact, rather than claiming the local image was transferred.
Neither artifact has been deployed. A later release must select the same tested
artifact for all readers.

The first owner-runner attempt stopped before migrations because production uses
`POSTGRES_PASSWORD_FILE`. The corrected runner reads the established secret only
inside the server and supplies it only to ephemeral owner commands. Runtime
settings contain no owner credentials. A new restricted non-bypass runtime role
has grants for staging; provider credentials, production encryption keys and
shared cache configuration are absent. Mail/providers are disabled; storage/cache
are private and no public listener or worker is started.

Owner-only migrations, restricted startup, schema drift and owner/pending-migration
startup rejection pass. All **183** original tables other than Django migration,
content-type and permission metadata retain every original row/value (new additive
columns excluded from original projections). These three metadata tables are
expected to gain migration/model/permission rows. No source loan, approval,
event, snapshot, document reference or archive has been admitted or rewritten.
Full Workspace inventories and the migrated cold recovery are still running.

The actual copied cases also pass restricted read-only checks: **RA00500** is
ACTIVE, principal 60,000, three months at 2%, supported imported opening profile
`original-anniversary-upfront-inclusive/2`. Its calculated collection amount is
61,200 on 6 October, against 60,000 recorded debt; this is an internal computed
position, not a staff-certified receipt/collection claim. **D01623** is still DRAFT,
24 September, principal 2,100 at 4%, three months and zero recorded debt. Its
retained-native adapter has no qualifying original-day approval; fresh-draft
admission correctly refuses posted history. Explicit correction remains required.
Queries with no Workspace context or targeting Lakshmi inside JCL return zero
ordinary rows. No case probe posts finance or completes source acceptance.

## Real-data archive-query finding

The approved restore found a performance defect that small generated fixtures did
not expose. JCL's unadmitted archive count ran for more than **600 seconds**.
PostgreSQL had already auto-analyzed both restored tables; missing restore
statistics were ruled out. A masked `EXPLAIN` showed the combined admission
predicate scanning the Workspace's imports for each retained row.

The read selector now asks whether a newer snapshot with the exact same scoped
identity exists, and separates ordinary bound-ID and old-document-ID admission
matches into equivalent `EXISTS` expressions. Existing source-identity indexes
remain sufficient; PostgreSQL uses hashed admission subplans. Names, original
number matching, financial origins and tenant-authority rules are unchanged.
All **14 browsing/inventory regressions pass** (13.424s). The provisional read-only
module probe on the real restore returns unchanged counts:

| Workspace | Unadmitted archive identities | Query seconds |
| --- | ---: | ---: |
| JCL | 26,664 | 3.028 |
| JSK | 3,840 | 0.727 |
| Lakshmi | 8,711 | 0.689 |

This bounded diagnostic explicitly mounted the edited selector over the earlier
image; it is not claimed as a new committed-image acceptance. The old slow
inventory job was stopped. Publish the corrected source, rebuild its actual
artifact, rerun full CI and complete normal inventories/cold recovery under that
artifact before claiming release verification.

## Selected-source correction finding

A further restricted, repeatable-read/read-only probe at **17:02:26 IST** found
that D01623's retained approval is dated 2 October and freezes a 2 October loan
date. It is not an original-day approval for the confirmed 24 September paper
payout. Lakshmi's digital economic/rate policies were created on 25 September
and 2 October; even the later backdated-effective policies were entered after
the actual day's cutoff. The retained-native correction path therefore cannot
establish the required original-day evidence.

A generated, customer-free reproduction under a restricted non-bypass role
confirms this boundary (**one test passes**, 0.736s): after a later-dated native
payout is fully reversed and the draft has its actual earlier paper date, the
adapter selects retained-native review, finds no qualifying approval/policy,
and rejects review. General completed-draft admission also rejects existing
posted history. The original approval/events remain unchanged and debt stays
zero. This is a guarded unsupported correction, not successful paper admission.
The reproduction is not a production-copy migration rehearsal.

Before claiming D01623 can be recorded or accepted, add an explicit reviewed
paper correction for this fully reversed native shape. Retain the same loan,
number/items, old approval, payout and reversal; validate the actual agreement,
deductions and proceeds; then establish one supported unreversed recorded origin
without claiming a historical digital approval. Preserve ordinary unpaid-draft
admission and the stricter retained-approval path. Do not select a weaker writer
automatically after a missing/stale evidence or authorization failure. This
requires targeted command, chronology, retry, reversal, servicing and isolation
checks; it is not resolved by removing an old price/policy cutoff.

## Next verification gates

1. Published ef3c82a5 and full exact-commit CI are complete. Keep that verified
   runtime/source/image identity distinct from later documentation-only commits.
2. The consistent server-only production checkpoint, original restore, actual
   owner migration upgrade from 0032, restricted runtime, original-value integrity
   and full inventories are complete. Migrated cold recovery passes all 202
   table/199 sequence comparisons and repeated runtime/source/census reads.
   Review actual capacity/media limitations. Keep full customer artifacts on
   the server; no production migration is authorized by this rehearsal.
3. Implement and test D01623's explicit actual-paper correction for its fully
   reversed native graph, preserving old financial/approval evidence. Then verify
   the confirmed example in staging; no production posting is implied.
4. Compare the confirmed JCL reference, a real direct-entry example and Lakshmi case with actual
   books; staff must confirm the source figures, including receipts and remaining
   principal or closure. Disposition independent book/monitoring cohorts.
   Software-generated facts alone do not provide acceptance.
5. Resolve findings and verify release identity, CI, fresh database/media backup/recovery and
   compatible web/worker readers before deployment.

See the [acceptance matrix](../flows/loan-continuation-release-acceptance.md) and
[consolidation plan](../plans/loan-continuation-consolidation.md).
