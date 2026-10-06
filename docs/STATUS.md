---
status: active
owner: project
updated: 2026-10-06
tags: [status, architecture]
---

# Status

## LC candidate publication and live verification started (6 October)

The owner requested commit/CI and production/source verification. Established
production SSH access is available; repeatable-read/read-only probes through the
restricted app runtime verified the actual JCL, JSK and Lakshmi cohorts. At
16:43:27 IST, active counts were **2,592 / 1,585 / 2,440**, closed **10 / 73 / 0**,
and retained archive snapshots **26,664 / 3,840 / 8,711**. Staff are operating the
live application, so these are dated snapshot counts rather than an unchanged
production fingerprint claim.

Candidate **b69df6ab** is committed and pushed on
`work/loan-servicing-contract-ld01`; its clean committed-source image builds.
The first exact-commit GitHub CI run failed in the foundation step: 14 first-loan
journey fixtures omitted the current public-trial consent/catalog/email requirements,
and one auction-access mock omitted the command's business-write prerequisite.
The fixtures now use the verified sign-in email, explicitly selected six-member
public offer and current consent. Additional isolation Workspaces use separate
test access, not another public signup. The auction unit test verifies delegation
to the business-write boundary. All **24 corrected journey/access tests pass**
(117.532s); documentation/import-boundary/whitespace checks pass. A new exact-head
CI run is required; CI is not yet green.

Production is at Loans **0032** / portability **0017**, while the candidate is at
Loans **0063**. A real production-copy upgrade rehearsal is required in addition
to fictional local recovery. No candidate migrations or financial writes have
been applied to production. The owner confirmed **JCL RA00500**, active and dated
2 September, and **Lakshmi D01623**. D01623 is a reversed-payout draft in Rokkad;
the owner confirmed its actual 24 September paper payout: 2,100 principal at 4%
monthly, 84 advance interest, 10 document charge, 2,006 proceeds, three-month
tenure and no later payment/closure. That confirmation does not post debt.

Automatic approval review rejected the full production-to-staging database copy
because the general staging authorization did not explicitly cover all sensitive
customer records and the destination. Specific server-only-copy approval has been
requested; no staging copy was created. Local checks continue; actual staff
acceptance, production-copy rehearsal and deployment remain open.
See [execution record](implementation/loan-candidate-publication-20261006.md).

## LC-07 release preparation verified locally (6 October)

The new dated Workspace release inventory reads ordinary active/closed contracts,
balances, common current-action prerequisites, independent book/assessment/valuation
quality, current draft/approval state counts and unadmitted archive identities.
PostgreSQL enforces repeatable-read/read-only execution; an attempted DML write
is rejected and transaction/context cleanup passes. No adoption, monitoring refresh,
book attestation, archive conversion or servicing authorization is performed.

All **225 release-focused regressions pass** (252.483s). Application boundaries,
four boundary-unit checks, Python/JSON parsing and current-document links pass.
Four existing test fixtures now use the tenancy billing-clock helper; statutory
auction fixtures use a genuine approved/disbursed loan instead of a fake ACTIVE
row. All **87 final fixture/tenancy/inventory regressions pass** (64.917s), including
the genuine statutory-auction origin and unavailable pre-cutover position.

Full local recovery restores **202 public tables and nine media files** exactly,
both before migration and from a migrated cold checkpoint. The source database
remains unchanged. The clean candidate image starts under restricted runtime;
owner-role and pending-migration startup are rejected. Schema drift passes. The
first offline build lacked cached dependency layers; the clean build succeeded
with downloads enabled, retaining both logs. The frozen candidate is uncommitted.

The local source has 15 supported **legacy** recorded loans across two Workspaces,
with stale/unassessed monitoring and incomplete/behind paper coverage disclosed;
none were automatically upgraded. These are fictional acceptance records, not a
current production JCL/JSK/Lakshmi inventory. Real production cohorts, actual
staff/source acceptance, committed/CI release identity and production deployment
remain pending. The owner selected JCL **RA0500**; its source comparison and a
Lakshmi paper example remain outstanding. See [delivery](implementation/loan-release-acceptance-lc07.md) and
[operator acceptance gates](flows/loan-continuation-release-acceptance.md).

## LC-06 prospective quote age locally complete (6 October)

New metal-dependent lending uses the latest applicable positive quote within an
owner-configured maximum, default seven inclusive local calendar days. Owners
configure it under Loans setup > Loan entry; zero means same-day. Photo setup
administrators can see the limit but cannot change it. The existing Loans-owned,
forced-RLS settings table and preference audit are reused.

New approvals freeze `quote-age-origination-v2`, the applied limit and each quote's
age outside immutable source identity. Current settings/eligibility/identity checks
and signed simple, renewal and valuation reviews prevent stale pending actions.
Old v1 approvals retain same-day semantics. Completed retries, actual historical
dates, paper/imported admission and independent monitoring policies are preserved.

The affected **143-test run passes** (59.478s). The broader **480-test run passes
477** (431.644s), with one PostgreSQL recovery deadlock and two obsolete fixtures:
one-day quote expiry and an ACTIVE row without financial origin. Both fixtures
were corrected without weakening command guards. All **52 follow-up checks pass**
(33.575s), including the three failures, new Khata cases and exact owner-setting
recovery. All **25 final presentation/boundary checks pass** (8.314s). Selected
checks pass across runs; this is not one clean 480-test rerun. Django checks,
no migration drift, six LC-06 templates, 104 changed/new Python parses, JSON
inventories and whitespace checks pass. Migration 0063 was generated and applied
only in disposable QA. Logs are under `.tmp/lc06-20261006/`. See the
[delivery](implementation/prospective-quote-age-lc06.md) and
[decision](adr/2026-10-06-configurable-prospective-quote-age.md).

Next: LC-07 release acceptance. No production deployment or bulk archive conversion
is part of LC-06.

## LC-05 bounded evidence extensions locally complete (6 October)

All six extensions are implemented: supplied multi-item opening paper splits,
actual paper fee components, multi-item archive reconciliation, delegated import
preparation with owner admission, precisely timed checkpoints, and verified closed
positions without invented receipts. Terminal positions are ordinary CLOSED loans,
with original agreement evidence, zero debt at closure and unavailable earlier
financial totals. Unknown custody stays unknown. Database guards prevent new
financial events or reopening through a nonexistent settlement reversal.

Old profile meanings and current allocation priority remain unchanged. Review/5
same-day paper receipts require actual timestamps; date-only paper closures and
renewals still cannot use the cutover day. Opening export/4 and servicing bundles
retain explicit allocations, timestamps and terminal evidence across restoration.
Delegated preparation creates no finance or customer/catalog definitions; owner
preview and commit retain source, permission, stale-review and atomicity checks.

All **475 affected regressions pass** (388.162s), followed by **37 final checks**
(27.232s) covering final validation wording, terminal inventory/HTTP, supplied
splits, native eligibility, timed restore and delegated staging-command access.
An earlier recovery deadlock passes in isolation and in the complete final run.
Django checks, no migration drift, nine template compilations, 81 changed/new Python
parses, runtime JSON inventories and whitespace checks pass. Migrations 0061/0062
were verified only in the disposable QA database, including reapplying final 0062
SQL. Logs are private under `.tmp/lc05-20261006/`. See the
[delivery record](implementation/bounded-loan-evidence-lc05.md),
[contracts](contracts/bounded-loan-evidence-lc05.md) and
[decision](adr/2026-10-06-bounded-loan-evidence-extensions.md).

Next: LC-06, latest applicable prospective quote with seven-day default maximum
age configurable by the Workspace owner. No production deployment, actual
source-book acceptance or automatic/bulk archive conversion is included.

## LC-04 completed-payout presentation locally complete (6 October)

Saved loans now expose one **Record completed payout** action. It selects the
existing general recorded editor or retained-native approval/reversed-origin
review from saved evidence. Old GET links redirect; issued native POST reviews
and recorded/native retries remain compatible. Genuine approvals, policy/quote
identity, source documents, permissions, stale-review and correction guards remain.
Recorded/opening snapshots cannot enter native reissue. Current lending is unchanged.
See the [delivery record](implementation/completed-payout-presentation-lc04.md).

New paper entry optionally maps an existing source licence revision, checked for
Workspace/series ownership and actual-date coverage, and frozen with reviewed
terms. Legacy reference validity remains unknown. Saved draft mappings and prior
request shapes remain unchanged. Missing mapping permits admission but still blocks
bounded portable history; no existing loan is backfilled or archive promoted.

All **257 affected regression tests pass** (293.327s), covering direct lending,
completed drafts, earlier approval/correction, paper entry, archive admission,
history/4, exact recovery and real four-path continuation. All **18 final LC-04
checks pass** (6.514s), including three additional form/mapping/native-exclusion
boundaries. Django checks, no migration drift, six template compilations,
41 changed/new Python parses and whitespace checks pass. Private evidence is under
`.tmp/lc04-20261006/`.

LC-05's extensions are now locally complete above; the selected configurable seven-day
quote age remains LC-06. Changes remain local and uncommitted. No migration,
production deployment, historical conversion or staff/source-book acceptance.

## LC-03 settlement preparation locally complete (6 October)

Full release, renew-now and current auction completion now share validated
continuation preparation. Modern native simple/full-month contracts automatically
recognize completed monthly periods during settlement, matching repayment/release.
Legacy/non-full-month finalization prerequisites and specialized posting, custody,
exact retry, approval, coverage, statutory and reversal guards remain. Completed
paper renewal still records actual past facts. See the
[delivery record](implementation/loan-settlement-continuation.md) and
[plan](plans/loan-continuation-consolidation.md).

Opening servicing uses frozen schedule allocation capacity, separately from the
dynamic risk forecast. Shared monthly native renewal/auction cap scheduled interest
without reducing actual collected debt. Policy/2 auction cash precision is paise;
opening renewal reversal retains exact source amount spelling. No source or schedule
is rewritten and no migration is needed.

The **541-test affected regression** passes 539 (649.203s); two recovery tests hit
PostgreSQL deadlocks. Both pass on isolated rerun. All **29 final targeted checks**
pass (77.446s), including **14 real four-admission settlement tests** with single/
multiple items and paise/whole-rupee policies, and retained partial-month behavior.
Selected checks pass across runs, not one clean 541-test rerun. Django checks,
no migration drift, 34 changed/new Python parses and whitespace checks pass.
Private evidence is under `.tmp/lc03-20261006/`.

Next is LC-04 admission presentation. Changes remain local and uncommitted;
production, historical conversion and quote-age behavior are unchanged.

## LC-02 forecasts and evidence presentation locally complete (6 October)

The owner authorized LC-02 and selected **seven-day quote maximum age by default,
configurable by the Workspace owner** for LC-06. The
[plan](plans/loan-continuation-consolidation.md) and
[delivery record](implementation/loan-continuation-forecast-and-quality.md) track
shared monthly remaining-obligation forecasts and independent evidence disclosure.
Reporting-date knowledge is separate from maturity horizon. Supported opening
forecasts use reviewed checkpoints and later known reductions without replaying
pre-cutover history or rewriting source schedules. Reads do not post interest.

Repayment previews, loan details, Loan health, dashboard, recorded reports/Party
statements and position exports disclose assessment freshness, book coverage,
valuation availability/freshness and calculation support separately. V6 snapshots
include principal/history basis; older V5 projections require ordinary refresh.
Native-contract earlier-payout evidence now requires paper-book review; ordinary
current capture is explicitly an assumption, not certification of off-system books.
Known missing paper activity cannot be overridden by origin. Financially inconsistent
current projections are excluded from portfolio monetary totals.

Focused **28 real-admission continuation tests** pass (75.488s), including eight
new single/multiple-item and paise/whole-rupee forecast cases after later reductions.
All **four real-admission quality integration tests** pass (8.455s). The broader
**482-test affected run** passed 480 checks (408.385s). Its two failures were test
expectations: the opening screen's more precise monthly-reference wording, and a
new aggregate test omitting overdue evidence while expecting a usable assessment.
Those fixtures are corrected. All **39 final focused checks pass** (15.119s),
including both cases, final valuation blockers in exports, native/paper repayment
HTTP disclosure, retained earlier-payout coverage, dashboard totals and all export
formats. All selected checks are verified across runs, not a claim of a single
clean 482-test rerun. A final opening-principal sidebar label refinement passes
all three opening/native/paper HTTP checks (4.269s).

Django checks, model/migration drift and repository whitespace checks pass;
all **27 changed/new Python files parse** and **nine templates compile**.
Private evidence is under `.tmp/lc02-20261006/`. Existing posting, idempotency,
reversal, notice dispatch and isolation guards pass in the affected suite.
Next is LC-03's release/renewal/auction preparation and orchestration.
Changes remain local and uncommitted. No production change, migration, deployment,
historical conversion or quote-workflow change is included.

## LC-01 continuation read consolidation locally complete (6 October)

The owner's new brief selects capture/verification, financial admission and common
servicing as separate boundaries. The
[staged continuation plan](plans/loan-continuation-consolidation.md),
[decision](adr/2026-10-06-loan-continuation-read-boundary.md) and
[source inventory](implementation/loan-continuation-inventory.md) record the next
work and remaining compatibility requirements. LC-01 adds real direct,
completed-paper, history/4 and opening-review/4 admission characterization and a
small read-only continuation selector for collection and exposure. Existing
recognition/allocation/reversal writers remain intact. **20 real-admission tests**
pass against consolidated consumers (53.102s) and restored HEAD consumers (52.121s):
single/multiple items, paise/whole-rupee policy, advance, reduction, anniversary,
repayment preview, recorded/collection/risk bases, once-only recognition/retry,
reversal prerequisites, cutover and restricted-role Workspace boundaries.

The affected **419-test run** passed 418 checks in 356.157s; its sole failure was a
pre-existing document test fake event missing `payload`. The exact failure was
reproduced with unchanged HEAD read consumers. That fixture now supplies the real
event field, and all **9 document tests pass** (0.150s). All selected checks are
therefore verified across these runs; this is not a claim of a single clean rerun
of all 419. A pre-existing fixed-date native fixture also now freezes `now` as well
as `localdate` so its approval/disbursal chronology does not drift with wall time.
Django checks pass, migrations report no changes, changed Python files parse,
whitespace checks pass and the moved legacy projection is AST-identical to its
prior algorithm. Private evidence is under `.tmp/continuation-20261006/`.

Confirmed remaining work includes independent quality presentation, maturity
forecast/obligation dispatch, release/renewal/auction orchestration, completed-payout
compatibility/UI consolidation and bounded evidence extensions. Completed-paper
history admission can omit a licence revision and then cannot export history/4;
LC-04 must address that mapping without inventing original evidence. Opening
pre-cutover counters and valuation are not claimed equivalent to full history.
The [plan](plans/loan-continuation-consolidation.md) records LC-02 as the next slice.
No production data, deployment, bulk conversion or quote-age threshold is included.

## Complete repository checkpoint verified (6 October)

The owner authorized committing all remaining changes and pushing the current
`work/loan-servicing-contract-ld01` branch to GitHub. This checkpoint includes the
previously separate platform console/lifecycle, storage inventory/usage/recoverable
cleanup, media-retention tests, owner monthly self-service and expired-trial paid
conversion code, the read-only import-media audit helper, and five fictional Form E
and Khata sample PDFs. Existing architecture decisions and runbooks remain the
contracts; this checkpoint does not enable public billing or execute live cleanup.

Focused validation passes **188 tests in 379.476s**, covering console authority,
lifecycle, storage inventory/recovery/retention, public recurring consent, expired
trials and recurring provider/cycle behavior in isolated QA with mocked providers.
All 24 pending Python files parse, 11 changed/new page templates compile, staged
whitespace checks pass, and model/migration checks report no changes. Credential
pattern checks are clean; PDF contents are fictional. Private verification logs and
temporary dependencies remain ignored under `.tmp/commit-all-20261006/`.

This is source publication, not a production deployment, full-repository regression
claim or live-provider acceptance. Earlier loan delivery and remaining LD-08
production gates below retain their meaning. Local preview database configuration
is separate from Git; no database or private-media backup is committed.

## Unified historical browsing delivered; LD-08 technical preparation verified locally (5 October)

The owner selected unified browsing instead of speculative bulk reconstruction,
then authorized presentation cleanup and LD-08. Loans now pages/searches ordinary
loans and retained closed source claims together, with clear Historical record
labels and private detail links. Unknown principal/dates/settlement remain unknown;
admitted identities replace archive cards with ordinary loans. Snapshot and legacy
source scoping, invalid-filter rejection, mapped-filter disclosure and restricted
Workspace isolation are tested. Financial monitoring/reports remain ordinary-only.
One New loan action stays prominent; stale payout, opening-auction, completeness,
portability and journey guidance is corrected without changing financial writers.

The affected regression passes **106 tests in 68.314s**, followed by **14 final
boundary tests in 7.756s** covering unknown dates, Workspace scope, old import
identities and generated current risk/valuation. Four JavaScript tests pass.
At the owner's request, a fictional two-item Lakshmi example goes through ordinary
New loan with standing terms, actual item splits, advance/fees, both saved rounding
choices and ordinary closure. This is not a real source document or staff signoff.
An older artificial ACTIVE-without-origin UI assertion reproduces on unchanged
LD-07 and remains outside the affected suite; no whole-repository green claim.

The retained September 21 review has 38,943 closed candidates, all with unknown
normalized original principal; 16,156 have unknown normalized payments. No archive
is financially admitted. A separate reviewed batch reconstruction project remains
deferred. These counts are old snapshot evidence, not current production inventory.

An isolated clone of the fictional local rehearsal restores **202 public tables**
and **9 private media files** exactly before owner-only additive migrations. Clean
image startup caught and fixed `.dockerignore` excluding runtime portability
contracts. Restricted startup and model/migration consistency pass. The exact
committed candidate `792662b5` is frozen as `rokkad:loan-domain-ld08-792662b5`
and passes startup/template compilation with a non-superuser, non-bypass-RLS
runtime role and no owner credentials in its environment. Original local
rehearsal and production data/schema remain unchanged. Live target inventory,
actual target recovery/operator acceptance, final candidate release checks and
controlled production rollout remain pending. See the
[delivery and runbook](implementation/unified-browsing-and-ld08.md).

The owner's screen-review preview is now exposed only on localhost **8079**, using
the exact committed candidate and restored fictional database. Authenticated direct
and paper New loan forms, both import entry screens and Loans directory load; all
27 local paper-screen assets pass. Existing previews on 8077/8078 and production
remain unchanged. Private pilot credentials are reused without publishing them.

The owner's default-entry issue was traced to workspace-wide Direct saves while
fictional series P retained its Paper override. The normal setup form now appends
a Direct policy for P, preserving the other economic values. The plain New loan
URL verifies Direct in Rokkad (from setup). No code or production settings changed.

## LD-07 portability complete locally (5 October)

The owner authorized LD-07. New `loan-servicing-bundle/1` preserves supported
connected financial/custody records, accepted archives, source reviews, photographs,
statutory evidence and exact original issued PDFs. Ordinary export selects it when
broader semantics are needed; earlier JSONL wires/readers retain their meaning.
Restricted-role admission creates fresh local identities after explicit per-loan
Party/licence/series/product mapping and full financial/custody reconciliation.
Preview rolls back records and provisional files; commit binds its exact checksum.
Changed bundles cannot overwrite an accepted source loan. Original approval labels
distinguish source claims from local imported evidence, and original PDFs remain
authenticated source-copy downloads. Destination future capture stays paper/mixed.

The affected regression passes **645 tests in 589.278s**; final focused verification
passes **53 tests in 88.501s**, including all **23 new LD-07 cases**. Current linked
renewal/reversal and cancelled successors, corrected/closed recorded loans, shared
paper closure, checkpoint auction/reversal, original file bytes, runtime RLS and
separate exact Workspace recovery pass. System checks, migration-history/model drift,
Loans Python parsing and scoped whitespace checks pass. No schema change is needed.

ZIP admission currently uses the operator command; the browser upload remains JSONL.
Funding/storage/capitalization and oversized or unknown graphs are explicitly held.
LD-08 actual source inventory, staff acceptance, staging and controlled rollout remain
pending. No application/candidate/production migration, conversion or deployment is
performed. See the [delivery record](implementation/portable-servicing-ld07.md) and
[contract](contracts/loan-servicing-bundle-v1.md).

## LD-06 servicing and future capture complete locally (5 October)

The owner authorized LD-06 and selected an optional per-loan transition to future
Rokkad-only capture, after complete records are checked through today. Existing
immutable transaction reviews retain the reviewed prefix, agreement/collateral
binding and explicit future choice. Paper/mixed remains the default. Current
supported actions can maintain coverage; paper activity/history corrections require
another review. No financial agreement, maturity or origin is changed by this choice.

Current opening auctions now use dedicated checkpoint catch-up, whole-debt recovery,
statutory service and custody. Coupled reversal restores recovery, recognition,
obligations and custody without reversing the opening. Common renewal/auction
prerequisites and signed correction dependency inventories use dated financial,
accrual and collateral facts. Existing successor approval and bounded replay remain.

Reminders retain original checked-source and current financial fingerprints. Stale
amounts reject at dispatch even under complete Rokkad-only capture; a freshly
reviewed new position can have a distinct immutable notice intent. Old per-loan
portable wires explicitly hold auction/capture graphs until wider LD-07 profiles;
exact Workspace recovery retains the complete records and statutory files.

The final affected regression passes **627 tests in 748.276s**, including 17 new
LD-06 cases. The focused follow-up passes **27 tests in 19.254s**; system checks,
migration drift and Loans Python parsing also pass. Coverage includes signed HTTP
review, restricted-role immutability/isolation, exact recovery, reduced checkpoint
auction/reversal, current valuation freshness and stale-message rejection.
Migration 0060 is additive on existing forced-RLS models, with no new
table. All schema exercise is confined to disposable QA. No application/candidate/
production migration, conversion or deployment is performed. See the
[delivery record](implementation/servicing-operations-ld06.md) and
[decision](adr/2026-10-05-servicing-operations-and-future-capture.md).

## LD-05 recorded source history complete locally (5 October)

The owner authorized explanation and implementation of LD-05. New loan-history/4
admits supported complete flexible monthly source agreements through the existing
recorded origination, receipt and full-release writers. Actual source item
allocations, receipt splits and eligible cutover debt reconcile without replacing
a lower-rate-item reduction with native highest-rate-first. No old digital
approval, price/appraisal row, extra cash origin or separate loan model is created.
Earlier native history/1, /2 and /3 and ordinary direct/paper entry keep their rules.

Compatible ACTIVE/RETIRED servicing products may have been configured after the
original transaction. Original validity is verified or explicitly unknown under
an inactive legacy licence reference; current issuance stays guarded. Original
book/number remain searchable immutable source aliases with unique local numbers.
Same-book duplicate identities, conflicting retries, ambiguous Party mappings and
future number reservations are held. Existing namespace/legacy-schema scoping and
shared opening/history identity remain intact. No alias table is added.

V4 export/restore includes supported original and later paper/current receipts
and closure. Source actors, original action purpose and known handover time remain
source claims separate from local completed recording. Unknown actor/time/cash
remain unknown. Export verifies frozen contract, item balances, derived recognition,
state/custody and reviewed transaction coverage. Corrections, standalone recognition,
linked renewal/auction and additional custody/funding/storage need wider portability;
no such operations are silently omitted. Source archive/opening retention stays
separate; no existing archive or old calculation cohort is automatically converted.

The affected regression passes **450 tests in 267.804s**, including all **22 new
LD-05 tests**, real upload/review/schema/commit/detail HTTP coverage, changed-source
retries, restricted-role immutability/isolation, active/closed and continued
paper/current servicing round trips, and restoration into another Workspace.
Final conservation/normalized-alias and ordinary paper-writer follow-up passes
**100 tests in 69.320s**, including all 22 new LD-05 tests.
The affected list retains LD-04's exclusion of the old pilot renewal-link assertion,
independently proven failing on LD-03. The whole repository suite is not claimed
green; previously reported unrelated baseline failures remain outside this scope.

System checks, migration drift/history consistency against the dedicated test DB,
672-file Python parsing and scoped whitespace checks pass. Migration 0019 extends
the immutable portability batch profile guard and refuses downgrade with v4
batches. Only disposable QA's test_rokkad_ld04_20261005 was migrated. No application,
candidate or production schema migration, live-data conversion or deployment was
performed. Source preparation/staff acceptance is still required for rollout.
LD-06 is next: remaining operations, correction dependencies, coverage transition
and risk/schedule parity. See the
[delivery record](implementation/recorded-source-history-ld05.md) and
[contract](contracts/loan-history-v4.md).

## LD-04 reduced-principal opening continuation complete locally (5 October)

The owner authorized LD-04 and confirmed the January example: a 1,000 principal
payment on 20 January reduces a 10,000 loan's next interest base to 9,000 from
2 February. New review/4 records explicit remaining item principal, current-period
bases, cumulative/current recognized and unpaid interest, and current/future
advance coverage. Shared calendar and captured-policy rounding continue from
that verified cutover; original maturity/grace stays unchanged. No earlier
payments, approvals, payouts or digital historical catalog rows are fabricated.

The existing writer, common servicing reads, receipt/full-release/reversal,
opening detail, export/3 and restore/exact recovery retain those facts. Earlier
review/2 and /3 and published export contracts keep their meaning. Unknown or
inconsistent checkpoint facts remain held. Advance over-coverage from a future
principal reduction needs explicit resolution; zero remaining principal is
explicitly outside this opening admission profile. Wider source allocations,
operations/capture transition and portability remain later slices.

The final affected regression passes **299 tests in 192.437s**.
Final admission/validation follow-up passes **55 tests in 15.139s**, including
all **26 new LD-04 tests** and the existing positive-principal blocker. The initial
299-test broader run had one failure: the old pilot UI test expects the renewal
link to be absent. It fails identically on prior LD-03 source `a8605f3e`; no
LD-04 renewal-link change is involved. That exact assertion was retained and
excluded from the successful final list, while the other pilot and opening
renewal cases remain included. The whole repository suite is not claimed green;
previous unrelated baseline failures remain outside this scope.

System checks, migration drift/history consistency against the dedicated test
database, 556-file Python parsing and scoped whitespace checks pass. Migration
0059 adds a Workspace-scoped locked guard rejecting mixed opening/payout/renewal
origins in either insertion order; restricted-role DML, immutability and isolation
are checked. All schema exercise is confined to disposable QA's
`test_rokkad_ld04_20261005`. No application/candidate/production migration,
existing-cohort conversion or deployment is included.

The supplied January rule example is tested; its test rate/advance assumptions
are labeled explicitly. Representative actual checkpoint evidence and staff
acceptance remain required before rollout. LD-05 is next. See the
[implementation record](implementation/reduced-principal-opening-ld04.md) and
[checkpoint decision](adr/2026-10-05-reduced-principal-opening-checkpoint.md).

## LD-03 completed-payout admission complete locally (5 October)

The owner authorized LD-03. General completed-payout recording now reuses the
shared paper editor and recorded-history writer for an unpaid DRAFT/APPROVED loan,
preserving its identity, number reservation, original date, item IDs, genuine
approvals, photos and issued copies. Supported actual unapproved terms can be
reviewed without historical destination Rates/economic-policy rows or a fabricated
approval. Posted/reversed origins and frozen approval discrepancies need explicit
correction. Direct current lending keeps its existing checks.

Signed source review and locked admission protect against stale facts, duplicate
source/number and concurrent double payout; retries return the same financial
origin. Known receipts/closure reconcile on that same loan. Missing complete-book
verification stays provisional. Monitoring uses current eligible valuation,
independently of original evidence. Migration 0058 narrowly permits evidenced
completed payouts under legacy references, requiring a validated matching recorded
snapshot before commit; references stay inactive and cannot authorize new lending.

Final affected regression passes **303 tests in 202.897s**, including **24 new
LD-03 tests**, genuine native evidence, multiple retained items, photo/document
retention, editor/retry, concurrent admission, restricted-role guards/immutability/
isolation, current monitoring and exact recovery. System and migration-drift checks,
553-file Python parsing and scoped whitespace checks pass. The earlier broad run's
only error was an invalid launcher module name; its functional cases passed and the
corrected final list is green. The full repository suite was not repeated; prior
unrelated baseline failures remain outside this scope.

Migration 0058 was exercised only in disposable QA's dedicated test database.
No application/candidate/production database change, existing-contract conversion
or deployment is included. LD-04 reduced-principal opening continuation is next;
wider profiles, operations/correction, capture transition and portable export remain
later slices. See the [implementation record](implementation/completed-payout-admission-ld03.md).

## LD-02 common repayment and full release complete locally (5 October)

The owner authorized LD-02. Shared factual eligibility now separates action purpose
from loan origin while reusing existing authorized, locked, immutable writers.
Supported native shared-monthly bullet loans accept reviewed completed paper
receipts and closures. Paper/opening loans retain current digital collections.
Legacy recorded event-fold repayments remain compatible without invented monthly
terms. Full settlement needs no collateral price/appraisal; partial release keeps
valuation/LTV checks. Native shared-monthly release recognizes completed periods
atomically, retaining existing paired current-period reversal.

Unknown handover remains PAPER_CLOSED until a separately evidenced return. Native
completed paper activity now requires explicit book verification, without creating
an automatic completeness claim. Existing opening multi-item completed principal
allocations remain blocked before posting; wider profile support is pending.
Bounded history export explicitly rejects source facts it cannot preserve;
exact-identity Loans recovery remains available.

Final scoped verification passes **256 tests in 251.059s**, including frozen opening
restore, paired reversal, concurrent posting, native paper recovery, restricted-role
posting/immutability/isolation and risk/coverage reads. The wider 294-test run found
three outdated blocker assertions and one frozen-release zero-representation
regression; these were corrected and rechecked in the final suite. System checks,
migration-drift checks, Python parsing and scoped whitespace checks pass. The full
repository suite was not repeated; the prior unrelated baseline failures remain.
No new migration, application database change, contract conversion or deployment
is included. LD-03 admission is next; wider operation/correction, opening profile,
coverage transition and portable-profile work remain later slices. See the
[implementation record](implementation/loan-servicing-eligibility-ld02.md).

## LD-01A shared monthly contract complete locally (5 October)

The owner authorized the shared-calendar/policy-rounding slice. Corrected direct
snapshots use policy version 2; new paper contracts use recorded-anniversary/3;
reviewed policy-based openings and complete history use explicit version 3 profiles.
The common original-date calendar keeps 5 May covered for a 5 April upfront loan
and starts the next charge on 6 May. Captured policy quantum rounds each item per
monthly period, and first-period principal stays original. Compatibility,
schedule/settlement/monitoring checks and reviewed paper correction are implemented.

Native full-month charges can be finalized when their period starts. Ordinary
repayment now recognizes the due charge atomically before allocating the receipt,
preventing skipped interest and overstated principal repayment. Preview, notice and
risk calculations use the same eligible monthly charge. Active supported bullet
maturity forecasts exclude advance already paid and use dated principal bases;
original schedules remain immutable allocation capacity. Failed writes roll back
recognition; retries cannot duplicate it. Existing frozen profiles are
retained for exact historical reproduction and require reviewed adoption; the
read-only `check_loan_interest_contracts --workspace-id ...` command inventories
them. No existing Workspace or production financial rows have been converted.

Additive portability migration 0018 enables v3 staging while retaining profile
immutability and exact result binding. It was exercised only in isolated QA with
test settings; production and running candidates remain unchanged.

The broad run exercised **1,753 tests in 1,270.230s**. It found 35 stale calendar
fixtures/policy assertions and five unrelated failures/errors. After correcting
only those stale tests, the final affected-module run passes **159 tests in
216.110s**. All five unrelated cases reproduce at unchanged checkpoint
`c1c34d4e` (four failures and one error in five tests); the broad suite is not
claimed wholly green and was not repeated. System, migration-drift, Python parsing
and scoped whitespace checks pass. See the [implementation and verification
record](implementation/loan-interest-contract-ld01a.md) for the failure inventory,
reviewed-adoption limits and compatible rollback. LD-02 was subsequently implemented
above; wider opening admission and correction/operation integration are later slices.

## Shared interest contract clarified (5 October)

The owner confirmed one monthly boundary for direct, backdated paper and imported
loans: a 5 April loan with its first month paid upfront incurs its next charge on
**6 May**, with no new charge on 5 May. Rounding follows the standing economic
policy captured for the agreement. Source channel does not select another calendar
or rounding convention. Existing source amounts and cutover recognition remain
evidence; calculation errors require explicit correction of affected postings.

The plan now inserts **LD-01A before LD-02** to align calendar, policy rounding,
principal-period bases and affected collection/schedule/settlement/risk paths.
LD-01's 239 passing tests characterize the old implementations; they do not
verify this newly confirmed common contract. At that clarification checkpoint,
only documentation changed; the implementation is recorded above. Deployments
remain unchanged.
See the [correction plan](plans/unified-loan-domain-correction.md).

## LD-01 shared servicing reads complete (5 October)

The owner selected the correction direction and requested a checkpoint/start.
Checkpoint `89f7321e` on `work/loan-servicing-contract-ld01` captures completed
shared entry and the review; unrelated billing/platform/storage work is preserved
uncommitted. LD-01 now centralizes read-only contract/position resolution for
repayment preview, reminder balances and repayment form context. Existing native,
recorded and opening calculations remain intact. Unsupported recorded profiles,
mixed origins and operational records without a financial origin fail explicitly.
Optional coverage metadata does not create a book attestation.

Verification passes **239 affected tests in 94.193s**, including **16 new contract
tests**, native origination, itemized paper entry/payment, opening servicing and
reversal, reminders and restricted-role isolation. The isolated QA container and
`test_rokkad_ld01_20261005` database use test settings. An initial broader run had
six local QA media-permission errors; those directories were corrected and the
final suite passes. No financial code was changed to work around the harness.

No new migration, posting change or action permission was introduced. Production
and running candidates 8077/8078 are unchanged. The loan work is checkpointed
separately from pending unrelated changes; LD-02 and later slices remain pending.
See the [implementation](implementation/loan-servicing-contract-ld01.md),
[plan](plans/unified-loan-domain-correction.md) and
[accepted direction](adr/2026-10-05-unified-loan-admission-and-continuation.md).

## Loan-domain correction review (5 October)

The requested current-checkout analysis is complete; the architecture correction
is **proposed, not implemented**. The review covers release HEAD
`4b93f67fe9412f6f401db97707e78d7ffaca9566` and the dirty UR-15--23 work, with
source/protected-file fingerprints. Direct, recorded-paper and imported loans
already share PawnLoan. Remaining friction is fragmented continuation/eligibility,
strict supported import profiles and the older earlier-payout historical-row gate.
The current paper path already accepts supported past agreements without historical
destination quotes or a fabricated approval.

The [review](architecture/ordinary-loan-domain-review-20261005.md) distinguishes
invariants, current lending controls, source evidence, servicing prerequisites and
implementation limits. The [proposed ADR](adr/2026-10-05-unified-loan-admission-and-continuation.md)
and [incremental plan](plans/unified-loan-domain-correction.md) preserve frozen
calendar/rounding differences, one financial origin, cutover coverage and existing
posting/RLS safeguards. Recommended first slice **LD-01** centralizes read-only
contract/position resolution for repayment preview and reminder balances, with no
schema or posting change. Later work needs verified source/checkpoint examples and
an explicit future-capture transition; it must not silently convert old contracts.

This task changed documentation only. Application bytes and prior dirty work are
preserved; no database-backed tests, migration, production inspection, deployment
or accepted-event rewrite occurred. Prior candidate verification below remains
prior evidence and does not establish acceptance of the proposed correction.

## UR-23 local delivery checkpoint (3 October)

UR-23 New loan refinement is complete locally. The ordinary Series field applies
the configured entry purpose; the duplicate selector and prominent mode navigation
are removed. A compact **Entry: From paper / Direct in Rokkad — Change** control
allows an exception. Switching retains common facts, paper references/activity,
native appraisals/overrides and, with JavaScript, selected photographs. These
read-only changes cannot save a loan or carry forward an old signed paper review.
Ordinary financial submissions retain their explicit purpose and existing checks.

Final verification passes **142 affected tests in 78.846s**, actual desktop/mobile
and no-JavaScript round trips, ordinary paper admission, direct price/date preflight
and exact saved-PDF hashes. Candidate 8078 runs
`rokkad:entry-refined-20261003-a80e473e` through migration 0057; all **1,529** runtime
source files match. Existing loan rows and saved-file bytes were unchanged during
the update. No new migration or financial service change was needed. Without
JavaScript, typed facts are retained but photographs need reselection after a
purpose change; the screen explains this. Production and candidate 8077 are
unchanged. See the [plan](plans/unified-loan-recording.md) and
[candidate evidence](implementation/joint-loan-candidate-20261003.md).

## Previous UR-19–22 checkpoint (3 October)

UR-19–22 shared loan entry is complete locally. New loan reuses purpose navigation
and the collateral editor; standing purpose defaults follow series -> license ->
Workspace -> DIRECT with an explicit per-action switch. Every paper item keeps its
actual principal/rate; the server sums principal and individually rounded charges.
Staff specify multi-item paper principal payments. Full closure, supported
corrections/replay, recovery and ordinary Renew performed now work across items.
Existing direct approval/valuation and highest-rate-first repayment remain intact.

Verification passes **502 regressions in 445.006s** and **105 overlapping final
receipt/draft checks in 61.683s**. Actual desktop/mobile admission, paper receipt
and closure, no-JavaScript add/review, signed confirmation and exact saved-PDF
checks pass. That checkpoint used `rokkad:shared-entry-20261003-d91d4ea3`
through migration 0057; all 1,525 runtime files match the scoped source. Existing
loan rows and saved files were fingerprinted before/after update and unchanged;
verified physical database/media backups and previous containers are retained.
Production and candidate 8077 are unchanged. Optional completed linked paper
renewal retains its single-group boundary; independent multi-item entry is supported.
Real staff/paper/hardware and hosted release acceptance remain pending. See the
[plan](plans/unified-loan-recording.md), [decision](adr/2026-10-03-shared-collateral-entry.md)
and [candidate evidence](implementation/joint-loan-candidate-20261003.md).

The first 502-case run had one recovery-export deadlock against QA autovacuum.
PostgreSQL logs identify the vacuum process; the final isolated run suppresses
vacuum only on disposable QA test tables. No production recovery lock or guard
was changed. The static import guard still reports four preexisting Loans test
files importing billing internals (eight findings, present in baseline 22db74f8);
there are no new findings from this delivery. Track that existing test-boundary
cleanup separately; this checkpoint does not claim the global guard is clean.


## Previous UR-15-18 checkpoint (3 October)

Business clarification (3 October): imported loans and Lakshmi paper-first loans
primarily use Flexible Partial Payment. This is recorded as the preferred product
for the agreed entry simplification: populated standing terms, calculated deductions
and exceptions when needed. UR-15–17 implementation now adds configurable standing
tenure (Lakshmi: 12 months), dated agreement defaults, calculated deductions and
collapsed exceptions; routine confirmation is separate from optional whole-book
verification. Monitoring retains calculated known amounts with provisional and
unavailable counts. UR-15–18 are complete locally: 422 regressions pass (369.684
seconds), with 156 overlapping affected cases, 18 final form/monitoring checks
after visual polish, and desktop/mobile/no-JavaScript
acceptance. Candidate 8078 now uses `rokkad:paper-simple-20261003-c5462662` through
migration 0056; 1,519 runtime files match the scoped source. Existing loan contracts,
including the local trial loan 1234, remain unchanged. Production is unchanged.
Previous image/container and verified database/media backups are retained. See the
[tracking plan](plans/unified-loan-recording.md) and
[standing-terms decision](adr/2026-10-03-standing-terms-and-routine-paper-entry.md).

## Combined loan candidate and recovery verified locally (2026-10-03)

Commit `22db74f8` is now built as `rokkad:joint-loans-20261003-22db74f8`
in a separate persistent fictional database/media environment at
http://127.0.0.1:8078. All 1,515 runtime application/settings/template/static files
match the committed archive. The complete merged graph through Loans 0055,
model-drift/dependency checks, restricted production startup and owner refusal
pass. Canonical Khata opening/exchange/reduction/settlement examples and paper
receipt/closure/deduction/renewal examples pass actual desktop/mobile/no-JS
browser checks, shared borrower totals, saved-PDF hashes and role/tenant/CSRF
boundaries. The original 8077 pilot and production remain unchanged.

Full logical recovery preserves rows, sequences and media, but ordinary native
recovery correctly refuses two deparsed CHECK-expression fingerprint differences.
No guard is relaxed. A separate physical recovery server passes source/copy
`pg_verifybackup`, exact full rows/sequences/roles/media and both native
preview/commit reconciliations with restricted startup. The operating candidate
stays unchanged. Private evidence and login details are in the
[combined candidate record](implementation/joint-loan-candidate-20261003.md).
Staff/book, physical camera/printer/QR, off-device backup, hosted and production
acceptance remain pending. Actual customer facts are not needed for this fictional
candidate; representative real-book reconciliation belongs to adoption acceptance.
Further Khata enhancements stay deferred.

## Joint loan checkpoint committed (2026-10-03)

The owner stopped further Khata enhancements and asked to defer the remainder in
Future work, commit the implemented Khata and paper-first work, and explain their
joint release. The scoped local commit `22db74f8` includes shared loan dependencies and
the complete merged migration graph; unrelated billing/storage/console application
changes remain pending; the required storage schema/model prerequisite is included.
**1,081 broad cases pass** in the initial 1,103-test run (632.856 seconds). Its 22 errors all came from an omitted private-media reference dependency, now included. **486 affected/integration tests pass in 295.000 seconds** across 33 modules on the corrected staged tree. Counts overlap. All 2,263 frozen source files
match the exact staged source. A fresh isolated test database exercises both
branches and the merged Loans leaf 0055, then is destroyed. No model drift is
detected; forced-RLS registry and tenant/financial boundaries pass. No deployment
or real Workspace change follows from committing. Follow the
[joint release guide](flows/khata-and-paper-first-release.md).

## Paper completion programme in progress (2026-10-03)

The owner authorized the ordered remaining recommendations in the
[tracking plan](plans/unified-loan-recording.md). UR-08 now supplies optional
original closing numbers with explicitly labelled system assignments, later
source-referenced customer handover without changed money, paper-book progress,
and atomic batch reviews retaining a separate per-loan confirmation. Archive
closure can leave physical cash/handover unconfirmed. The first 128 regressions
passed; a subsequent corrected 34-test run passed including new forced-RLS
checkpoint metadata, restricted-role isolation, and handover evidence guards.

UR-09's original DISBURSAL contract slice compensates old calculations, saves
new recorded policy/disbursal/schedule snapshots, and replays retained receipt
totals. Original date/principal/rate and exact unchanged-date closure reconciliation
passed domain/document checks. A 32-test run also passed original/successor terms,
paired funding, unchanged native forward dependencies and both current/paper
opening renewals. Closure/paired renewal date and custody evidence revisions
passed the final 52-test focused run in 43.229 seconds, including scope/immutability,
handovers, current/paper opening renewals, ordinary forms and retained documents.
A database movement guard exposed the need for explicit
restatement identity, which now has a deferred financial-evidence binding.
Old snapshots and issued document bytes remain retained. The next broader run
passed **599 tests in 421.791 seconds**. This is not completion of the programme.
Nine captured fictional pages passed desktop/mobile/no-JavaScript verification
with full local static assets, no overflow or page errors. Before/after handover
PDFs were reconciled and visually inspected; earlier issued bytes survive.
UR-11 now supplies a versioned 89-table original-identity native recovery archive,
ordinary download and offline owner-only preview/restore, preserving complete
correction/renewal/custody/coverage graphs and retained files. It requires the
matching recovered database/external identities; it is not a cross-Workspace
importer. UR-12 connects recorded-origin current auctions to agreed anniversary
debt, current completeness and existing statutory/custody checks, with coupled
recognition/custody reversal. **125 integration tests passed in 51.604 seconds**
on a fresh isolated database, including native entry, funding, statutory service,
corrections, imported-opening renewals and native recovery. The reused earlier QA
database had retained unrelated fixtures; fresh verification resolved global-count
failures. A document binding omission was also corrected and verified.
An additional **147 boundary tests passed in 141.454 seconds**, covering archive
duplicate guards, transaction reviews, notifications and shared receipt corrections.
Final broad release checks passed **745 tests in 463.689 seconds** on another
fresh isolated database. The earlier broad attempt found an optional document
payload fixture compatibility issue; its fallback is corrected and verified.
No model drift was detected; all 1,401 frozen QA source files match the checkout.
The five isolated QA databases were removed after their runners finished;
frozen source, checksums, screenshots and local verification evidence are retained.
Migrations 0047–0049 and 0051–0055 were exercised on isolated QA databases;
their application to operating Workspaces and deployment remain pending.
Real Lakshmi acceptance examples and the rollout environment have been requested;
no staff sign-off or real Workspace change is claimed. Local technical checks are
complete for the implemented profile; the full programme remains open. The
[operator/release guide](flows/paper-first-operator-and-release.md) and
[tracking plan](plans/unified-loan-recording.md) identify those remaining steps.

Entries are dated delivery checkpoints, newest first. Earlier images, counters,
access assignments and outstanding tasks describe their checkpoint, not the
current live state; later entries supersede them. Private runtime evidence and
backups remain on the server.

## Khata document navigation verified locally (2026-10-03)

Phase nine adds saved-document search/type/date/order filters and 25-row pagination,
active mobile section visibility, a no-JavaScript section chooser and fixed
contextual action/review returns. **29 focused tests pass in 14.083 seconds** and
**498 frozen Linux regressions pass in 250.389 seconds**. Actual desktop/mobile/
no-JavaScript checks verify 25 + 3 pages, retained filters, exact PDF hashes,
invalid-range errors, contextual links and viewer export denial. Screenshots are
inspected without overflow or page errors.

The local fictional pilot runs `khata-local-20261003-2216df647199`. All 1,435
application/settings files match the image; twelve scoped UI/read/test paths overlay
the verified label base. Unrelated ordinary changes/migrations are excluded. Schema,
financial/custody commands and native guards are unchanged. Full-worktree/frozen
model drift, restricted-runtime startup/static and owner-startup refusal checks pass;
pre-switch backups and the prior container are retained. New fictional draft
QNAV00001 has 28 saved document issues, one simulated receipt and no approval/cash/
interest. All pre-existing source rows and media bytes remain unchanged. Restricted
native readiness and fourteen-table/39-file archive verification pass, with unchanged
guards. Production, remote CI, named staff trials and hardware/off-device acceptance
remain open. See [the checkpoint](implementation/khata-document-navigation.md).

## Khata selected label batches verified locally (2026-10-03)

Phase eight adds a searchable 100-item picker, explicit item batches and
no-JavaScript print-displayed-batch for accounts above 100 held items. Selected
membership/order and PDF bytes are immutable; new returned/foreign/oversized
selections fail completely. Existing combined/all-item layouts keep their bounds.
Complete 100 x 60 mm labels, 6 pt minimum and private item QR routes remain.
Migration Khata 0042 extends only the guard; no-op full-checkout merge 0050 joins
the unrelated ordinary branch, which is excluded from this pilot image.

The final scoped image passes **489 Linux regressions in 289.451 seconds**.
All **1,432 application/settings files** match its frozen manifest;
only eight label paths differ from the verified series base. Model drift,
dependencies, owner-runtime refusal and restricted runtime/static checks pass.
Actual desktop/mobile/no-JavaScript browser checks cover 100 + 5 chunks, two-item
selection, search, exact retry, viewer refusal and authenticated scans. PDF size,
UUID order and minimum text sizes pass across 107 pages; representative rendered
pages/screens are inspected. The separate fictional draft QLABEL00001 records
105 simulated receipts/two returns and three issues, with no approval, withdrawal
or interest. Saved PDFs/memberships remain exact after returns; all pre-existing
source rows and media bytes are unchanged. Native fourteen-table encoding/readiness
and selected-batch restore pass. Guard-mismatched old archives still need their
matching image/schema or full database/media recovery. Backups and rollback
containers are retained. Production/remote CI/physical hardware are unchanged.

See [the current checkpoint](implementation/khata-label-batches.md). Next: phase 9
presentation and saved-document navigation; operator/release acceptance remains
separate.

## Khata series status controls verified locally (2026-10-03)

Phase seven adds setup-authorized signed pause/resume and permanent retirement,
reasoned append-only history and database-guarded availability. Existing lending
checks stop drafts, openings, withdrawals and increases; servicing continues.
The new Workspace-owned table has forced RLS and native recovery coverage.
Migration 0041 branches from Khata 0040; a no-operation 0046 merge preserves the
separate ordinary Loans branch in the checkout. The local candidate overlays
only the Khata branch and explicitly scoped application changes on the prior
verified image. The frozen image passes **480 regressions in
290.652 seconds**, including new status tests and existing archive checks.
Actual desktop/mobile/viewer/no-JavaScript pause, resume and retirement checks pass;
exact confirmation retry records no extra transition. Four screenshots are inspected.
All 12 account/policy/financial/custody/photo/document table fingerprints are unchanged;
only one fictional unused acceptance series and its recorded status events are added.
Prior collection, report, exception and guidance browser checks also pass.
All 1,429 application/settings files match the frozen image. Both the composed
schema and full checkout's merge pass drift checks. Pre-migration database/media
backups, restricted non-root/read-only runtime and stopped prior web are retained.
Current localhost candidate: `khata-local-20261003-6bfe7f30d391`, image `sha256:31dabdc493e9070bd4d8a68d58a819974f7e6d4fa8e747f66172abdf8ef4d85f`.
No production update or unrelated ordinary Loans activation. Next: bounded selected
label batches; hosted/operator/physical acceptance remains separate.
See [the series checkpoint](implementation/khata-series-status.md).

## Independent paper entry and later renewal verified locally (2026-10-03)

UR-07 follows the owner's simplified workflow: record each paper loan independently,
with original dates/terms, total receipts and financial closure. No unknown renewal
sequence is required. Advance interest and deducted document charges reconcile to
paper proceeds; physical cash can remain unspecified. A closed paper record can
leave customer handover unconfirmed through explicit PAPER_CLOSED custody, without
inventing a storage exit or customer return.

Already-entered active recorded loans can use ordinary Renew for a new approved
decision now, or record a known completed paper renewal with actual dates/number,
net cash and retained/relabelled collateral. The owner's INR 12,000 example yields
INR 1,550 after INR 240 advance interest, INR 10 charge and INR 10,200 old settlement.
Recorded contract and current interest-position copies retain immutable issued
bytes. Native real-time approval remains required for a successor performed now.

Verification passed 508 broad regressions (333.608 seconds), 98 native renewal/
reversal and paper checks (130.459 seconds), 154 document/coverage checks (68.819
seconds), 90 final settlement/register checks (67.196 seconds) and 15 final routine
paper checks (8.488 seconds). These runs overlap. Desktop/mobile/no-JavaScript
checks passed for entry, closure and renewal, with no overflow/page errors; contract
and position PDFs were reconciled and visually inspected. Changed coverage produces
a new position copy while earlier issued bytes remain intact. Runtime import
boundaries include untracked Loans files; Python syntax, local links, diff whitespace
and migration drift checks passed. Unknown handover is a reconciliation warning,
not invalid closed debt; receipt corrections/registers retain the same uncertainty.
The isolated paper-first test database was removed after verification.

Migration 0045 and this work are local only; no pilot
or production migration/deployment has been performed. Recorded-origin restorable
portability, auction recovery, imported-opening renewal and broader amendments
remain open. See the [tracking plan](plans/unified-loan-recording.md) and
[decision](adr/2026-10-03-independent-paper-loans-and-renewal.md).

## Unified recording UR-06 transaction coverage verified locally (2026-10-03)

Per-loan paper transaction review is implemented through ordinary loan detail.
Signed confirmation or an explicit missing-record report freezes actor, source,
checked-through date and financial fingerprint. New paper admission creates the
initial review atomically. Current monitoring/reporting retains provisional values
when coverage is incomplete; definitive dashboard totals respect this boundary.
Reports and borrower statement CSV/XLSX/PDF expose the same coverage status/date.

Reviewed repayment/overdue reminders freeze the review and agreed collection amount.
The common Notify provider boundary rechecks source, current date/amount, review,
consent, contact, current risk and confirmed message. An obsolete intent remains;
a fresh paper review can support a new intent. No historical messages are sent by
admission or transaction review. Migrations 0043/0044 add review isolation/immutability
and notice bindings; they are local only.

Verification passed **358 regressions in 268.845 seconds** and **143 final checks
in 62.584 seconds**, plus two final canonical-collection checks. Coverage includes
signed/stale/retried reviews, concurrent confirmations, opening checkpoint scope,
correction invalidation, guarded provider dispatch, obsolete-intent replacement,
RLS/immutability, reports/documents and existing native notifications. Desktop,
mobile and no-JavaScript review checks pass; report/statement PDFs were text-checked
and visually inspected. Migration consistency, 841 tracked/29 changed Python
import-boundary checks, 1,356 final source hashes and 955 curated documentation
links pass. The isolated monitoring test database was removed.

This is the completeness/monitoring/reminder slice of UR-06. Recorded contract and
schedule documents, restorable recorded-origin portability and subsequent renewal/
auction integration remain pending. No production or pilot changes. See the
[decision](adr/2026-10-03-loan-transaction-completeness.md).

## Unified recording UR-05 initial archive admission verified locally (2026-10-03)

The initial closed-loan archive admission is implemented locally through the
ordinary paper-history form and canonical writer. Known normalized archive facts
must agree; missing facts require identified supporting records. All retained
snapshots of the same source bind the review. The existing immutable financial-origin
registry gains a protected archive link in migration 0042, retaining forced RLS and
shared source uniqueness across history/opening imports. Archive list/detail and
ordinary loan detail link both ways; original documents and media stay retained.

Verification passed **335 regression tests in 342.664 seconds**, covering archive,
opening/history imports, existing paper history, corrections, numbering, reports,
documents, monitoring and tenant registry. The final form/source-snapshot review
passed **86 tests in 66.712 seconds**. Tests cover missing facts, conflicting source
snapshots, amount/date/borrower mismatches, immutable cross-Workspace link guards
under a restricted role, concurrent admission, retries and rollback. Desktop/mobile/
no-JavaScript checks pass. Migration consistency, 841 tracked/10 changed Python
import boundaries, 1,347 source hashes and 1,029 curated documentation links pass.
The isolated archive-admission test database was removed.

This first slice excludes renewal-chain archive admission and broader calculation
profiles. Migration 0042 is local only; no production/pilot changes or bulk conversions. See the
[decision](adr/2026-10-03-archive-admission.md).

## Unified recording UR-04 batch correction verified locally (2026-10-03)

Whole-batch receipt correction is implemented locally. Every member is checked,
changed paper-loan settlements must reconcile to actual cash, and the combined
collection must match before atomic posting. Original batch, releases and handovers
remain. Detail/history, reconciliation CSV and regenerated memos expose reviewed
amounts with provenance. No new model or migration.

Batch/settlement/release regressions passed **87 tests in 193.101 seconds**. Final
correction/report/monitoring/document integration passed **105 tests in 102.097
seconds**, including the simplified closure form and subsequent native-member
reversal. Coverage includes mixed native/admitted batches, atomic rollback, stale
reviews, safe retries, concurrent confirmation, authorization and restricted-role
Workspace isolation. Desktop/mobile/no-JavaScript checks pass; corrected batch
release PDF pages were text-checked and visually inspected. Migration consistency,
841 tracked/27 changed Python import-boundary checks and 952 curated documentation
links pass. All correction sources match the tested snapshot (1,343 hashes match;
one concurrent, unrelated Khata test edit was inspected and left untouched).
The isolated batch test database was removed.

Contract/custody/date amendments remain outside this receipt correction profile;
UR-05 archive admission and UR-06 completeness/integration remain pending.
No production or pilot changes. See the
[implementation checkpoint](implementation/unified-loan-recording.md).

## Khata action guidance and draft experience verified locally (2026-10-03)

Phase six is implemented locally: separate proposal/approval/current-source status,
next-step guidance, usable approval choices, known prerequisite filtering and explicit
receipt catch-up/finalization explanation. The draft reuses borrower search and
actual outstanding, offers a bounded native search and canonical monthly/annual
opening illustration, also shown during signed draft review. No schema or financial
command changes. Opening acknowledgement remains a documented design proposal.
The frozen image passes **469 Linux regressions in 286.994 seconds**, including
archive checks and 11 new guidance tests. Actual desktop/mobile, viewer and
no-JavaScript browser checks pass, alongside earlier servicing, collections,
reports and exception screens; four new screenshots are inspected. All 1,424
application/settings files match the frozen image. The candidate is composed from
the prior verified Khata archive plus 15 explicit application paths; financial
models/services/migrations and unrelated apps retain their prior bytes. Separately
evolving ordinary Loans work remains in the checkout and is not activated here.
Current localhost candidate: `khata-local-20261003-ac52235bea54`, image
`sha256:06f7970074913db752104ea62c18cd2e0aa461948744a618782d591b0048af5e`.
Non-root/read-only runtime, private persistent storage, pre-update backups and
stopped rollback are verified. No production update or pilot financial confirmation.
Next: series pause/retire controls; operator/hosted/physical gates remain separate.
See [the guidance checkpoint](implementation/khata-action-guidance.md).

## Unified recording UR-04 settlement extension verified locally (2026-10-03)

Receipt correction now reconciles a later recorded renewal or single-loan full
return with actual settlement cash. The original agreement, successor principal,
dates, numbering and custody remain unchanged. Canonical financial compensations
and replacement settlements retain originals; shared selectors update operational
figures and regenerated documents with correction provenance. Forward successor
activity is locked and bound to review. No new model or migration is required.

The broad regression run passed **598 tests in 376.269 seconds**. Final financial,
UI, reports, release-batch and document checks passed **233 tests in 172.665 seconds**.
Desktop/mobile/no-JavaScript review checks pass; corrected release/renewal PDFs
were text-checked and visually inspected. A small PDF pagination fix keeps section
headings with their tables. Migration consistency, source hashes, app boundaries
and documentation links pass.

The final readable review labels passed **31 settlement tests in 46.838 seconds**.
The isolated settlement test database was removed after verification.

Broader contract/custody/date amendments and shared
release-batch receipts remain explicitly unsupported, so UR-04 is not an unrestricted
history editor. No production or existing pilot was changed. See the
[decision](adr/2026-10-02-recorded-settlement-corrections.md) and
[implementation checkpoint](implementation/unified-loan-recording.md).

## Unified recording UR-04 receipt correction verified locally (2026-10-02)

The ordinary Loans detail/repayment interface now has a local administrator review
for missing, replaced or voided receipts on active paper anniversary contracts.
It previews dependent allocations, retains old evidence, adds dated compensation
and replays actual receipt totals. Existing loan/event/obligation records are reused.
Signed review, source reference checks, locked atomic posting and retry guards are
verified. The broad regression run passed **568 tests in 327.261 seconds**; final
provenance, UI, reporting, servicing and printed-receipt checks passed **135 tests in
39.424 seconds**. Desktop/mobile/no-JavaScript captured-response checks pass and
the corrected receipt PDF was visually inspected. Migration consistency, import
boundaries, source hashes and documentation links pass.
The isolated correction test database was removed after verification.

Cross-renewal/closure/custody corrections remain unsupported and explicitly blocked;
UR-04 remains open for that extension. This is a delivered receipt correction
boundary, not complete lifecycle correction. No production or existing pilot has
changed. See the
[decision](adr/2026-10-02-recorded-receipt-corrections.md) and
[tracking plan](plans/unified-loan-recording.md).

## Unified recording UR-03A renewal extension (2026-10-02)

The ordinary paper-history interface now records unchanged/reduced/top-up carry or
actual full principal repayment and a fresh advance. Signed review reconciles old
and new principal, carry, gross advance, actual cash received/paid and any explicit
old-interest offset. Collateral staying held versus actual same-day return/repledge
is independent, with source/successor custody evidence and recipient. Existing
canonical renewal/settlement/opening records are reused; no new migration is needed.

Loan detail, renewal report/export, pledge book and printed agreement show actual
cash separately from carried debt. Monitoring exposure and new-contract interest
use the successor's agreed principal. New-contract advance interest, fees,
concessions and capitalization remain outside this paper profile.

The broad run passed **522 tests in 299.410 seconds**. Final evidence/review and PDF
checks passed **126 tests in 35.353 seconds**, including report/export, documents,
native lifecycle and paper histories. This covers full redraw and carry with both
custody paths, interest offsets, later receipts/closure, multiple renewals, signed
review, retries, rollback and restricted-role isolation. Desktop/mobile/no-JavaScript
captured-response checks pass; printed cash/return evidence was inspected. Source
hashes, migration consistency, import boundaries and documentation links pass.
The isolated test database was removed after verification.
See the [implementation checkpoint](implementation/unified-loan-recording.md).

The [plan](plans/unified-loan-recording.md) now marks UR-03A locally complete; UR-04
is next. No production, real loan, archive or existing pilot was changed. Rollout
and the remaining unified-recording stages remain pending.

## Renewal scope clarified after UR-03 (2026-10-02)

The owner clarified that a renewed loan's principal depends on the customer's
agreement: unchanged carry, reduction through repayment, or increase through a
top-up. The earlier answer established retained collateral and a new numbered loan;
it did not exclude top-ups. The local UR-03 writer already supports unchanged or
reduced principal, but fixes top-up at zero. This is a scope gap in the initial
implementation, not a business restriction.

[UR-03A](plans/unified-loan-recording.md) now tracks the required top-up extension
before UR-04. The reconciliation must distinguish old principal, principal repaid,
additional advance, new principal, interest settlement and actual cash directions.
The owner subsequently accepted both actual full principal repayment/fresh advance
and principal carry; collateral handling is independent. The implementation and
verification checkpoint above supersedes the original zero-top-up limitation.
Earlier test counts apply to their original bounded checkpoint.

## Unified recording UR-03 local admission (2026-10-02)

The ordinary New loan workflow now offers **Already completed on paper**. A signed
review reconciles original payout, total-only receipts, carried-principal renewals
and full closure before committing the complete history atomically. The confirmed
profile preserves next-anniversary principal reductions and retained custody on
renewal. It uses ordinary loan/event/schedule/release/renewal records, original
numbers with counter reservation, scoped borrower selection and source/retry guards.
No historical digital approval or original metal-price entry is required.

Current receipts/full release, anniversary exposure and principal-sensitive
maturity/delinquency reads are integrated. Details show paper source and the
confirmed-through date; pledge-book renewal cash is distinct from principal carry.
Existing fixed schedule allocations remain immutable. Unsupported subsequent
renewal, dependent correction, automatic notices, auctions and portable export
remain guarded pending the next stages. Archive conversion remains UR-05.

The combined run passed **508 tests** in 282.588 seconds, covering concurrent
submissions, restricted-role admission/isolation, native origination/servicing,
opening history, risk readers, numbering, documents and portability. A further **171 tests passed** in 60.743 seconds after the final document/UI
changes: truthful recorded-paper memos and the unsupported fixed-schedule KFS guard. Desktop/mobile/no-JavaScript
captured-response checks passed; final source hashes, migration consistency,
scoped import boundaries, whitespace and documentation links are checked. The
isolated test database was removed after verification. See the
[implementation evidence](implementation/unified-loan-recording.md) and
[tracking plan](plans/unified-loan-recording.md). No production, real loan, archive
or existing local pilot has changed; rollout remains pending.

## Unified recording UR-02 storage foundation (2026-10-02)

The next [tracked slice](plans/unified-loan-recording.md) extends existing immutable
policy/disbursal snapshots with explicit recorded-contract/payout bases. Approved
origins retain their approval requirement; recorded origins retain source facts
without a fictional approval and identify the current monitoring selection
separately. Migration 0041 adds checked relationships and retains forced RLS and
append-only guards. Financial readers, current valuation and the pledge book are
adapted; unsupported approval-based export/ticket and original-payout reversal
cannot misrepresent this new basis. **309 regressions passed**, including ten new
recorded-origin tests and restricted-role SQL guards. Two additional published
history-schema tests initially lacked documentation fixtures in the disposable
container; their exact pure test methods passed separately after including those
files. Application source was unchanged between these checks. Model/migration
consistency, application boundaries, source hashes and documentation checks pass;
see [implementation details](implementation/unified-loan-recording.md).

This is a storage/read-model foundation, not an enabled paper-origination screen.
UR-03 must add ordinary draft/review and atomic complete-timeline admission with
source identity, original-number reservation and duplicate protection. No live
loan, archive, production database or existing local pilot has changed.

## Unified recording UR-01 verified locally (2026-10-02)

Following the owner's implementation instruction, the
[tracked adaptation plan](plans/unified-loan-recording.md) now has six delivery
slices. UR-01 extends ordinary Repayment for reviewed opening loans: actual paper
date, total received, source reference, signed allocation review and confirmation.
It reuses canonical collection/repayment records, preserves date-only source facts
and actual recording actor/time, and protects retries and duplicate references.
Later financial activity, outstanding fees and multi-item principal allocation
remain explicit unsupported cases. No never-entered loan admission or archive
conversion is claimed. Paper metadata survives opening export/restore and appears
in loan history/receipt projections; existing correction and future exposure
readers use the same events. Repayment currency precision is normalized correctly.

The final Linux test run reports **163 passes in 60.732 seconds** across new paper
receipt, opening/payment/restore/export/release, event storage, native lifecycle,
document/layout and risk/monitoring suites. Fictional Django HTTP responses pass
Chromium desktop/mobile/no-JavaScript layout checks, with screenshots inspected.
All 1,293 application/template files match the tested source snapshot; boundary,
documentation-link and scoped whitespace checks pass. See the
[implementation evidence and limits](implementation/unified-loan-recording.md).
No production deployment, schema migration, real-data posting or existing local
pilot replacement. UR-02 recorded origination and separate monitoring basis are next.

## Unified loan recording direction documented (2026-10-02)

The owner accepted ordinary Loans support for business performed now and recorded
afterward, including Lakshmi's mixed paper backlog from 24 September. The
[ADR](adr/2026-10-02-unified-loan-recording.md),
[business workflow](flows/unified-loan-recording.md) and
[delivery plan](plans/unified-loan-recording.md) separate actual contract, historical
decision evidence and current monitoring. Lakshmi's total-only receipt example is
confirmed: INR 2,000 pays INR 200 interest and INR 1,800 principal. Fees and
exceptional allocations are not inferred from that answer. Qualified archived
loans may later be admitted as ordinary closed loans after reconciliation, with
immutable source retention, explicit links and duplicate guards; no blanket
conversion is promised. Documentation only: no application/configuration/data
changes, migrations, conversion or deployment in this checkpoint. Implementation
and representative contract/evidence assessment remain pending.
Documentation validation passes: 889 links in the current-docs set and 57 links
in the additional decision/workflow/plan references; scoped whitespace checks pass.

## Khata cash and custody reports verified locally (2026-10-02)

Phase five delivers a date-filtered, source-linked cash daybook and current
custody/pending-return register across all account states, with 25-row pagination,
all-matching totals and authorized bounded CSV. Later not-received evidence removes
fictitious receipt cash; actual refunds retain their separate dated outflow.
Receipt cohort filters do not reconstruct historical custody. Item/piece counts
and metal weights remain distinct. No migration, financial writes or notifications.
Eleven focused Linux cases pass in 9.123 seconds after an aggregate alias collision
was fixed before freezing. The frozen image passes **435 regressions in 221.837
seconds**, plus 23 existing historical-archive checks in 4.757 seconds for those
changes present in the shared snapshot. Actual Chromium verifies report filters /
pages/source links/full CSV/private headers/viewer export refusal/mobile/no-JavaScript
and prior Khata tabs/servicing/custody/collections/events/exceptions. Four report
screenshots are inspected; no page errors or document overflow. QA uses the exact
configured Bootstrap bytes/SRI; asset configuration is unchanged.

At this report checkpoint, localhost candidate: `khata-local-20261002-2fc1557b6beb`, image
`sha256:0a763226b6c8fae3c7cb3628aec2f0f1f313589d15d5e02d87ed6a7136cc5a8b`. All 1,418 application/settings files match the frozen archive
and image. Schema/no-drift/dependency/restricted-runtime/static/owner-refusal checks
pass. Fictional database/media and pre-update backups/checksums are retained with
stopped web `khata-img-20261002-web-pre-reports`. Later edits are documentation only.
Production is unchanged; hosted/operator/physical and remote-CI acceptance remain
separate. The later action-guidance checkpoint above completes phase six; optional reminders
retain their separate intent/delivery gate. See [the report checkpoint](implementation/khata-operational-reports.md).

## Historical closed-loan browser made readable locally (2026-10-02)

The owner reported that old closed-loan details were difficult to find and looked
lost. The existing archive now has a readable local list/detail: customer-name,
loan-number and source-ID search; customer and DD/MM/YYYY dates in the 25-record
list; collateral, supplied payments, source item amounts/rates, payment splits,
release/recipient records and retained borrower/loan fields on detail. Mutable
source loan amounts remain explicitly distinct from original principal/current
balances; missing payments, empty lists and zero remain distinct. No totals or
settlement events are inferred. Source inconsistencies stay visibly flagged.
Raw evidence/export and owner upload tools sit in secondary disclosures.

All **23 focused presenter/HTTP/archive regressions pass in 9.749 seconds** on
Linux using a disposable fictional database, including unchanged document/export,
source identity binding, escaping, customer search/pagination, read access and
existing adversarial RLS/acceptance checks. Actual Chromium layout/disclosure
checks pass on captured fictional Django HTTP responses at 1440/390 px, including
no-JavaScript use, without page errors or document-width overflow. Desktop list
and mobile detail screenshots are inspected. These are captured-response layout
checks, not a live production browser acceptance test.

No schema, financial data, import/reimport, production deployment or existing
localhost pilot change occurs. Production rollout and real JCL page verification
remain pending. See the [implementation](implementation/historical-loan-browser.md)
and [archive flow](flows/historical-loan-archive.md).

## Khata collection worklist and readable events (2026-10-02)

The owner authorized phase four. The separate active-account worklist shows
oldest unpaid / next anniversary, instalment unpaid versus total dues, overdue
days, 7/30/90-day upcoming windows and authorized receipt shortcuts. Future
amounts are labelled estimates from activated terms, with annual monthly charges
grouped at the anniversary. Totals precede pagination; evidence-review accounts
remain visible. Current eligible-item LTV and historical warned exchanges are
separate, including missing prices and subsequently corrected sources.
History links to readable immutable event details: exact IN/OUT groups, saved
valuations/price dates/policy, actual references/consent, allocations/charge segments
and related sources. No financial writes, migration, ordinary-loan changes or
production activation. Twelve new boundary/provenance/access cases pass in
11.001 seconds. The first frozen run caught a redundant date that failed statement
JSON validation; it was removed before any pilot switch. The corrected source
passes 38 document/layout/collection checks in 26.649 seconds. The final frozen
image passes **424 Linux regressions in 217.369 seconds**.
Actual Chromium verifies filters, saved groups/values, exact links, private access,
viewer/foreign refusal, desktop/mobile/no-JavaScript use and prior tab/register /
servicing/custody/exception checks. Styled screenshots are inspected; no page
JavaScript errors occur. QA uses exact configured Bootstrap bytes/SRI because
sandbox CDN sockets are blocked; application assets are unchanged.

Current localhost candidate: `khata-local-20261002-53cb3807081f`, image
`sha256:ff9b400b815abc4a9be261f24ed9ab3597794cae1dd4940ea84f4d0579e4343b`.
All 1,410 application/settings files match the archive and actual image.
Schema/no-drift/dependency/restricted-runtime/static/owner-refusal checks pass.
Fictional database/media are preserved with pre-update backups/checksums and stopped
web `khata-img-20261002-web-pre-collections`. Later changes are documentation only.
Optional reminders remain queued for a separately reviewed Loans-intent/Notify v2
delivery contract. Cash/custody reports are next; production, hosted/operator /
physical and remote-CI acceptance remain separate.
See the [collection/event checkpoint](implementation/khata-collection-worklist.md).

## Khata measured read performance (2026-10-02)

Phase three is authorized. A dedicated fictional benchmark uses supported services,
25/250/1,000 items, 41 accounts, corrected receipts/exchanges, pending/actual returns,
photos, twelve months of interest and four concurrent readers under the restricted
runtime role. Warm direct-view latency, queries, Python allocation and response
bytes are measured separately from network/browser/hosted acceptance.
Measurements support lazy panel data, compact source-backed balance reads,
database register filters before replay and 25-item custody pages with exact
QR/history/photo links. Financial calculators/posting/guards are unchanged; no
persistent money cache or migration is introduced. Canonical balances and fixture
counts match at all three sizes. In the final quiet 1,000-item run, History falls
from 147.97 to 38.22 ms, custody from 195.38 to 31.96 ms, and four simultaneous
history reads from 506.86 to 146.88 ms. These are local direct-view diagnostics,
not hosted latency promises; native dropdowns and larger financial histories still scale.

Six new equivalence/boundary cases pass in 5.135 seconds. The final frozen image
passes **412 Linux regressions in 200.291 seconds**. Actual Chromium verifies
custody pages/exact links/legacy bookmarks, private photos, viewer/foreign scope,
mobile/no-JavaScript use and prior tabs/register/servicing/exception flows.
Styled screenshots are inspected; no page JavaScript errors occur. QA uses exact
configured Bootstrap 5.3.8 bytes/SRI to overcome sandbox CDN restrictions.

Current localhost candidate: `khata-local-20261002-de09e77ef1d9`, image
`sha256:f8a4023a4b0020b867798afeb457e29e7d6376badee38d2387744f00e26b1ae7`.
All 1,405 application/settings files match the archive and actual image.
Schema/no-drift/dependency/restricted-runtime/static/owner-refusal checks pass.
Existing fictional database/media are preserved with pre-update backups/checksums
and prior web `khata-img-20261002-web-pre-performance` retained stopped. Later
changes are documentation only. Collection/event follow-up is next; production,
remote CI, hosted/operator and physical acceptance remain separate.
See the [read-performance checkpoint](implementation/khata-read-performance.md).


## Khata searchable servicing (2026-10-02)

The owner authorized phase two. Pending returns now have a paginated/photo-assisted
browser with source-history links and per-item handover entry. Entry selects the
exact active reservation source server-side; selection also pairs it automatically.
Reduction approval uses searchable multiple selection; later photo attachment
uses searchable single selection and retains camera/upload preview. Filters/pages
preserve selection, and ordinary form controls remain available without JavaScript
or through an explicit fallback. The signed review, per-item recipient/reference,
revalidation, hard reduction LTV/due checks and private media contracts are unchanged.
No migration, new operation type, production activation or economic change.
The 37 focused checks pass in 19.433 seconds. The final frozen image passes
**406 Linux regressions in 197.108 seconds**, including seven new servicing-selection
cases. Actual Chromium passes pending-source pairing, persistent multiple selection
across searches/pages, single photo selection, protected thumbnails/camera controls,
search failure and pending-debounce native fallback, viewer/foreign-account refusal,
mobile/no-JavaScript access and existing exchange/register/tab/exception checks.
Correctly styled desktop/mobile screenshots are inspected; no page JavaScript errors.
The sandbox blocked the CDN, so QA serves the exact configured Bootstrap 5.3.8
CSS/JS bytes with matching SRI hashes; application asset configuration is unchanged.

Current localhost candidate: `khata-local-20261002-535598b92cbb`, image
`sha256:51d3fe51099cc750948300a9a941808ef43044aa53e605e2ffa5af0ee1056112`.
All 1,403 application/settings files match the source archive and actual image.
Schema/no-drift/dependency/restricted-runtime/static/owner-refusal checks pass.
Existing fictional database/media are preserved, with pre-update backups/checksums
and prior web `khata-img-20261002-web-pre-servicing-final` retained stopped.
Later changes are documentation only. See the
[servicing checkpoint](implementation/khata-collateral-usability.md#searchable-servicing-follow-up-2-october).
Measured large-account performance is next; production, remote CI and physical
acceptance remain separate.

## Khata phased improvements: exception guidance (2026-10-02)

The owner selected phased delivery when all recommendations cannot form one
coherent change. [Future Work](plans/future-work.md#improvement-delivery-sequence)
now records the complete recommended order and parallel operator/release gates.
The first slice adds exact-source correction guidance, source-prefilled review,
bounded links to actual blocking operations and an in-app/support runbook.
Existing ACTIVE-only whole receipt/unhanded exchange correction rules remain;
no new financial kinds, source mutation, migration or production activation occurs.
The final frozen image passes **399 Linux regressions in 184.928 seconds**.
The four new scope/form/blocked-preview/access cases pass in 2.648 seconds;
49 existing checks also passed during the initial focused run. Browser acceptance
covers exact guidance and support, source-prefilled forms, linked blockers,
refused previews without confirmation, foreign-account isolation, viewer refusal,
mobile/no-JavaScript access and prior register/tab regressions. Desktop/mobile
screenshots are inspected; no page JavaScript errors occur.

Current candidate: `khata-local-20261002-1cde3312c625`; image
`sha256:e5cd51eb489c7c16d6adc75816b73e75acbf4f5aeae88267893ac9ae97ea3b82`. All 1,402 application/settings files match the frozen archive
and actual image. Schema/no-drift/dependency/restricted-runtime/static/owner-refusal
checks pass. The localhost pilot retains its fictional records/media, pre-update
backups/checksums and prior web `khata-img-20261002-web-pre-exceptions`. Later delivery changes
are documentation only. See the [correction checkpoint](implementation/khata-corrections.md#exception-guidance-follow-up-2-october).
Broader exception commands still need specified cash/interest/custody outcomes
within phase one; pending-return/searchable servicing is next in the operational
sequence. Production, remote CI and physical acceptance remain unchanged.

## Khata completeness and operations review (2026-10-02)

The owner requested review and recommendations after the tab/register work. The
[completeness review](implementation/khata-release-review-20261002.md#current-completeness-review)
maps the agreed lifecycle to implemented services and existing test evidence.
Opening, staged draws, agreed-limit simple interest, anniversary collections,
approved changes/reductions, grouped exchanges, settlement and actual returns are
implemented locally. This does not mark real-money/operator acceptance complete.

Highest-priority findings are bounded ACTIVE-account correction/support coverage,
ordinary dropdowns/manual item-reservation pairing outside exchange, full replay
and custody construction behind visible pagination, and missing explicit Khata
collection/notice and cash/custody reporting workflows. Further recommendations
cover readable operation evidence/warnings, action prerequisites, series status
management, bounded label batches above 100 held items and living-doc reconciliation.
Deliberate exclusions are separated from implementation gaps; same-limit renewal
is not currently supported even though broader early discussion mentioned renewal.

This is a read-only source/document/evidence review. The existing verified
candidate's 395 passing regressions and browser acceptance are cited, not rerun
or represented as a load/hardware/hosted acceptance test. No application, financial
policy, production or fictional pilot-record changes occur. Prioritized findings
are recorded for owner review; no additional financial scope is accepted.

## Khata register metrics and detail tabs (2026-10-02)

The owner clarified the metric placement applies to the Khata register. Financial
totals are now equal-height cards above the filters, with matching count/range in
the results-table header. Account detail uses Overview, Actions, Collateral,
Interest, History and Documents sections with ordinary Bootstrap-styled links.
Actions reuse state/permission-aware workflows in four groups; relevant shortcuts
appear in Collateral/Interest. Legacy QR/item/source/history/exchange links resolve
the correct section. Document errors select Documents. Only one panel renders;
no financial calculation, write permission or migration change is introduced.

The final frozen image passes **395 Linux regressions in 183.149 seconds**,
including tab/source/document/access cases. The old QR test now checks the active
Collateral panel and exact item anchor instead of the former open disclosure.
Schema, dependency, restricted production-profile/static startup and owner-startup
refusal checks pass. Actual read-only Chromium checks cover aligned/filtered
register totals, count/range placement, six sections, grouped actions, photos,
interest, history filtering/pagination, exact source/exchange links, viewer access,
mobile overflow and navigation without JavaScript. Desktop/mobile screenshots
are inspected; no page JavaScript errors occur.

Current local candidate: `khata-local-20261002-0d22c65edc36`; image
`sha256:544544d43ae6ced2c9c62d97644a608baba46497afd431459265612beb0caa92`.
All 1,399 application/settings files match the frozen source and actual image.
The fictional pilot at `http://127.0.0.1:8077` preserves records and media, with
pre-update database/media backups and the previous web retained as
`khata-img-20261002-web-pre-tabs`. Only later documentation changes differ from
the frozen archive. See the updated [workflow](flows/khata-account-workflow.md) and
[usability checkpoint](implementation/khata-collateral-usability.md).
Production and hosted/remote CI remain unchanged.

## Khata source-history browsing (2026-10-02)

Following the owner's request, detail-page source history now uses 25-event
pages, newest/oldest business-date and sequence sorting, event-type/inclusive-date
filters, exact operation lookup and item/reference search. Grouped item matches
are deduplicated. Correction and return-source links locate exact related events
across pages/filters. Recording time, actor, direct item links and payment
references help identify events. Display filters do not alter balances or hide
compensating audit sources. No migration or financial policy changes.

The 43 focused history/collateral/integration checks pass in 24.744 seconds,
including 52 same-day receipts across pages, inclusive dates, invalid filters,
item/exchange deduplication, corrections outside the current page, unchanged
balances and account/workspace boundaries. The history candidate
`khata-local-20261002-16c741a72ede` passes **392 Linux regressions in 183.508 seconds**.
A final table-width/keyboard-scroll-only change is frozen as
`khata-local-20261002-10e98f81aa49`; its seven history cases pass in 5.502 seconds.
Manifest comparison proves this is the only application change since the full
regression run. Final image:
`sha256:a7a03b562498cd8bf8a310368f1343a69de936f5015e2c7fe867001a045fac1f`.
Schema/no-drift/dependency/restricted-runtime/static/owner-refusal checks pass.
Actual Chromium verifies filters, retained sort/date/search through page two,
disjoint rows, exact source lookup, invalid dates, empty matches, unchanged
balances, reset, item search and viewer reads. Final mobile rows remain readable
in a keyboard-focusable horizontal-scroll container; screenshots are inspected.
All 1,398 application/settings files match both the source archive and built image.
The local pilot retains current database/media and private pre-update backups;
prior web is retained stopped as `khata-img-20261002-web-pre-history-layout`.
Browser checks perform no business writes. The
[workflow](flows/khata-account-workflow.md) and
[checkpoint](implementation/khata-collateral-usability.md) describe the controls.
976 local documentation links and whitespace checks pass; later edits update
docs only. Production remains unchanged.

## Khata camera capture and register clarity (2026-10-02)

Owner-requested webcam/mobile front/rear capture is implemented on receiving and
later photo attachment, with live/still previews, available-device choice,
removal and native mobile picker fallback. Tracks stop on switch/close/file
selection/submit/page exit; late requests cannot revive a closed camera. JPEG
captures use existing private photo validation/storage. Detail custody rows now
show each item's latest protected thumbnail while preserving prior photos and
UUID scan anchors. The register separates agreed limit from actual principal
outstanding and links **Items awaiting handover** to pending custody, with a
plain explanation of record counts. No financial policy or migration changes.

The 53 focused collateral UI/integration/operator tests pass in 28.496 seconds,
including captured-JPEG persistence and latest-photo selection without changing
originals. Final frozen `khata-local-20261002-cbb08c7071bf` passes **385 Linux regressions
in 183.491 seconds**, dependency/schema/no-drift/static/restricted-runtime and
owner-startup-refusal checks. Image ID:
`sha256:4f6630e45e98b0dfabc40dc0d0b25216f08c7b134d3d90ccdc9fe3e81fafff5f`.
Actual Chromium with a synthetic video device verifies JPEG capture/receipt,
front/rear constraints, late-request closure, track cleanup, removal, native
picker hints, simulated denial/file fallback, later camera attachment, private
detail thumbnails, separate real limit/principal figures, pending-return drilldown
and mobile layout. Desktop/mobile screenshots are inspected. Physical webcams,
phone camera selection, hosted HTTPS and off-device acceptance remain open.
The localhost pilot is updated with pre-update database/media backups and prior
web retained stopped as `khata-img-20261002-web-pre-camera`. Fictional KH00004 now
includes camera Item 73 and two captured photos; its two pending outgoing items
and original KH00001/KH00002 are preserved. Production remains unchanged. See the updated
[workflow](flows/khata-account-workflow.md) and
[implementation checkpoint](implementation/khata-collateral-usability.md).
The frozen archive and all 1,395 application/settings files match; 974 local
documentation links and whitespace checks pass. Later edits update docs only.

## Khata collateral usability implementation (2026-10-02)

Following explicit owner authorization, all three usability improvements are
implemented: direct combined receiving/photos with actual-receipt confirmation
and Save and add another; a scoped 25-item collateral browser; and searchable
outgoing/incoming exchange tables with persistent selected groups and replacement
receipt round trips. Review shows exact per-metal group totals and retained cover.
Small private thumbnails verify originals without altering retained bytes.

Receipt/photo remain separate immutable sources. Invalid uploads and partial-file/
row failures roll back receipt and clean newly written files; retry fingerprints
include photo bytes. Existing approval, photo, same-metal, LTV, policy, custody and
ordinary-loan contracts remain unchanged. No migration is needed. The 45 focused
UI/storage/search plus opening/workflow cases pass in 24.328 seconds, including
203-item browsing, cross-account/workspace refusal and incoming-reuse filtering.
Final frozen `khata-local-20261002-569b1175f32e` passes **384 Linux regressions
in 185.540 seconds**, plus dependency/schema/no-drift/static/restricted-runtime and
owner-startup-refusal checks. Image ID:
`sha256:46c5fdb4030c4583f7c569efecb6376e19ec30c456ffdee6c5d9c8390847cea5`.
Actual Chromium verifies receiving/photo preview, Save and add another, pagination,
selection retention, replacement-receipt round trip, explicit selection, reviewed
group exchange, pending custody, private thumbnail, mobile stacking and viewer
refusal. Numeric searches target the exact item ID. The updated localhost pilot
retains its database/media volumes, private pre-update backups/checksums and stopped
prior web containers. Original KH00001/KH00002 remain unchanged; additional fictional
KH00003/KH00004 retain browser evidence. Production is unchanged; hosted, remote CI,
off-device and physical acceptance remain open. See the
[checkpoint](implementation/khata-collateral-usability.md).

Final documentation validation passes 972 local links across 40 current/Khata
guides and whitespace checks. The frozen archive hash is intact; all 1,394
application files in its apps/templates/static/settings inventory match the
verified source. Later edits update delivery documentation only.

## Khata workflow reference and collateral usability proposal (2026-10-02)

The owner requested the walkthrough as a lasting developer/user reference and
asked about combined collateral receipt/photos and searching large holdings.
The [account workflow](flows/khata-account-workflow.md) now records setup through
financial settlement and physical closure, worked limit/rate/LTV examples, current
screen actions, identification, supported boundaries and links to authoritative
services. It explains receipt versus exchange IN/OUT membership versus handover.

Inspected forms, selectors, models and exchange services confirm that current
item lists have no dedicated search/pagination. The
[usability proposal](plans/khata-collateral-usability.md) records one receiving/photo
screen, a paginated item browser and searchable outgoing/incoming selections with
visible selected groups. These are proposals, not implemented app behavior. No
new schema/financial policy, application source, frozen candidate or production
change is made. Validation passes 965 local links across 39 current/Khata guides
and the whitespace check; application tests are not repeated for these prose-only edits.

## Khata Linux image verified and persistent local pilot ready (2026-10-02)

After the owner fixed/started Docker and instructed proceeding, the frozen source
`khata-local-20261002-8e030b414955` builds successfully. Verified local image ID:
`sha256:a84bef3712092d0c99a67b0d0a697356551a0bccc3c9f8834248013b07d41bf3`.
The source snapshot/requirements/base pin and revision label are retained; no
Git commit/push, registry publication or production deployment occurs.

A complete fictional PostgreSQL/media recovery passes all 199 table/1,287 original
row fingerprints using independently sorted row bytes after rechecking the original
Windows evidence. The permissions-table discrepancy was Windows/Linux collation
ordering. Original native evidence and PDF bytes reconcile. Restricted runtime
startup succeeds; owner web startup is rejected with `tenancy.E020`. The non-root
image runs with a read-only root filesystem and runtime-only credentials. Package,
migration/model and static checks pass. **372 Linux regressions pass in 133.932
seconds**, covering Khata, RLS/storage and ordinary-loan/Party/dashboard/document
preservation on a separate test database/media volume.

New local workspace `khata-73081a4c` has fictional monthly/annual KH agreements
opened through actual services on the setup day. Owner/viewer username login,
protected pages, 16 static assets, CSRF and role/workspace refusals pass against
actual Gunicorn HTTP. The existing `container_dev` profile enables local HTTP
review; production-profile HTTPS-cookie/runtime checks remain separate. App/database
stay on an internal network; a credential-free relay publishes only localhost:8077.
Billing is disabled, mail captured and no external providers/workers are activated.

Before handover, the disposable tmpfs database is copied with local-socket
`pg_basebackup`/SHA256 manifest, verified twice with `pg_verifybackup` and moved to
the dedicated persistent Docker volume. All main public rows and sequence states
match before/after; the physical copy is 100,935,680 bytes. Database/web restart
and actual HTTP checks pass again. Private fictional login/settings and complete
evidence remain under `.tmp/khata-image-20261002/`.

The local review app is http://127.0.0.1:8077; use the private test-login file.
Production JCL/JSK/Lakshmi data, roles and deployments remain unchanged. Hosted/TLS
pilot bindings, remote CI, off-device recovery, physical 100 x 60 mm printer/phone
QR and owner/operator scope acceptance remain open. See the
[image/local pilot checkpoint](implementation/khata-image-pilot-20261002.md).

## Khata test candidate preparation and full fictional recovery pass (2026-10-02)

The owner selected a new test workspace and 100 x 60 mm labels. A new local
fictional workspace, `khata-83f6003f`, uses an independent KH series with active
monthly/annual and closed agreements. Services record an exchange with pending
return, photo, preserved label/statement, corrected receipt, settlement and actual
handover. No real customer/production workspace, ordinary-loan record or production
migration is changed. The simulated dates are 10 October/10 November 2026.

The repeatable local drill applies owner-only migrations from empty, then restores
a complete pg_dump and saved private-media ZIP into new disposable databases.
All **199 public tables / 1,287 rows**, **196 sequences** and **4 files / 139,718
bytes** reconcile. Native preview leaves no rows/files; committed exact-identity
recovery preserves source/media/P/U/interest/custody, advances Khata sequences
monotonically and leaves ordinary sequences unchanged. A restricted NOLOGIN role
sees zero Khata rows outside Workspace context, passes all software readiness
checks, retrieves original PDFs and records a new fictional withdrawal successfully.
The unused-counter assertion was aligned with the existing safe sequence contract;
no lending or recovery-service changes were required.

An allowlisted source-freeze tool captures current source/member hashes and archive
checksum without Git staging/commit/push or copying secrets/media/backups. Two
unchanged trial captures are byte-identical; final snapshot evidence is retained
in `.tmp/khata-test-candidate-20261002/`. Four import-boundary unit checks, the
841-tracked-file boundary scan, dependency and operator-script syntax checks pass.
Recovered PDF samples render correctly. Disposable fictional evidence/databases
remain inspectable; no real data or credentials are copied into local backups.
Final owner-settings system/migration checks pass without model drift. Source
inventory covers all present application/static/template/locale build inputs;
928 documentation links across 36 current/Khata files pass.

Docker Desktop's local engine cannot start after permitted startup checks, so
container-image verification remains open. The frozen source is a local snapshot,
not a committed/image-verified release. Remote CI, hosted test deployment/logins,
off-device candidate recovery, paper printer/QR and owner/operator scope acceptance
remain pending. No production pilot is activated. See the
[candidate checkpoint](implementation/khata-test-candidate-20261002.md) and
[test-pilot acceptance guide](flows/khata-test-pilot-acceptance.md).

## Khata collateral labels and pilot review implemented locally (2026-10-02)

Khata collateral can now be issued as one selected-item label, one combined label
for all physically held items, or one 100 x 60 mm page per held item. Labels keep
complete item UUIDs/descriptions/quantity/weights/purity/storage and custody at
issuance, with net totals by metal. Pending returns are labelled; actual returns
exclude new labels. A 6 pt floor and overflow refusal preserve all text. Authenticated
UUID scans resolve the current account/item custody and open its detail disclosure.
Issuance is a scoped, permission/write-availability checked, idempotent POST; original
PDF bytes remain in Documents for private reprints after later custody changes.
No label changes actual debt, agreement terms or physical custody.

Migration 0040 extends existing document issues with LABEL snapshots and SQL
held-item/identity/selection/custody guards. Existing A4 guards remain intact and
all kinds stay immutable. Forced RLS/file inventory are reused; the registry gate
advances to 0040. Native recovery includes saved labels with original payload/bytes;
guard-version mismatches still require recovery into the matching older schema
followed by forward migration, rather than a weakened restore.

A read-only readiness page/CLI checks migration, forced RLS, restricted runtime
role, enabled/present source guards, file coverage, eligible series, balances and
native evidence encoding/integrity. It never activates a pilot or certifies saved
off-device backups, real restore rehearsal or hardware acceptance. The release
review records the supported/unsupported statutory/default and correction boundaries,
and remaining candidate/named-workspace/operator/hardware/recovery/monitoring gates.

Validation: 346 selected regression tests pass in 191.107 seconds, including khata
workflow/integration/recovery, restricted-role/RLS/storage checks and ordinary loan,
Party/portal/dashboard/ticket/layout preservation. A further 12 final label/readiness
tests pass, including missing-guard refusal. A fictional three-page combined/individual
sample with Tamil text and pending return is rendered and visually reviewed; every
text span fits the page and remains at least 6 pt. System/migration consistency
checks pass. All 25 existing ordinary collateral/media/combined-label tests also
pass in 6.487 seconds; syntax/whitespace and 944 local documentation links pass.
Only the dedicated fictional test database receives migration 0040;
no development/production migration, deployment, real-account changes or pilot
activation occurs. See the [release review](implementation/khata-release-review-20261002.md),
[operator guide](flows/khata-labels-and-pilot-review.md) and
[decision](adr/2026-10-02-khata-labels-and-pilot-review.md).

## Khata operator forms and native recovery implemented locally (2026-10-01)

The next owner-authorized slice adds scoped forms for all supported opening,
financial, custody, revision, settlement and bounded correction commands. Signed,
30-minute reviews bind actor/workspace/account/action/date and preserve request
UUIDs; services recheck original evidence before posting. Editing reviews retains
instructions. Series setup supports independent/associated numbering, with owner
WARN/BLOCK policies. Private photo reads verify original bytes and stay scoped.

Native `khata-native-recovery/1` ZIPs capture all thirteen khata tables, complete
source/revision/period/segment/allocation/custody evidence and original photos/PDFs.
Schema/financial-guard fingerprints and export-date P/U/interest/custody reconciliation
are retained. Offline exact-identity restore requires the table-owner connection,
matching prerequisite identities, an empty khata destination and an independently
retained archive SHA-256. Preview inserts/reconciles and rolls back without media
writes. Commit requires explicit workspace confirmation; runtime restore is denied.
This is trusted disaster recovery, not edited/paper import or workspace cloning.
Existing evidence/media conflicts refuse recovery; failed restores roll back rows/
trigger state and remove only new files. No ordinary-loan numbering is changed.

Validation: 335 selected regression tests pass in 211.941 seconds, including khata
services/integration/UI/recovery, forced-RLS/storage coverage and ordinary product,
Party/portal/dashboard/ticket/layout preservation. A further 26 focused tests pass
on final review-editing, recovery parent validation and continued servicing changes.
Exact recovery/re-export includes corrected receipts, formal reduction, settlement,
closed custody and original media; restricted runtime export/restore boundaries,
stale/tampered/shared/date-expired reviews and compensation cleanup are covered.
Migration consistency reports no changes. System and documentation checks pass.
Only the dedicated local test database is used for writes; no new migration,
production deployment, real restore or workspace activation occurs.

Item labels, statutory/default boundaries, final release verification and a
separately approved named workspace pilot remain. Unsupported correction kinds
stay unavailable. See the [checkpoint](implementation/khata-operator-and-recovery.md),
[operator flow](flows/khata-servicing-and-recovery.md) and
[decision](adr/2026-10-01-khata-operator-forms-and-native-recovery.md).

## Khata borrower/dashboard, documents and summaries integrated locally (2026-10-01)

Party history, the new-loan borrower card and verified portal summaries now include
actual khata debt. Shared totals precede pagination; mixed borrowers count once,
and agreed limits/unused entitlement never become outstanding. Dashboard principal
includes both kinds, with a compact separate khata interest/custody card. Ordinary
recorded interest, saved health, lending activity and reports retain their labelled
scope. Portal statements no longer subtract already-reflected payments twice.

A scoped, paginated khata register/detail exposes balances, schedules, current
same-day cover suggestions/policies, custody and source/correction links. Both
independent and associated series are included. Missing prices leave known debt
intact; settlement clears debt while actual returns remain visible.

Migration 0039 adds immutable, directly owned, forced-RLS document issues with
source/agreement/position/licence guards, retained private-file coverage and exact
hash/size-verified reprints. Approved agreements/amendments, payouts, interest,
exchanges, reductions/handovers, settlement, corrections and today's statements
use typed snapshots. Late-issued vouchers retain their source prefix; later
changes never rewrite saved PDFs. Complete text flows across A4 pages.

308 focused/regression tests pass, initially including 22 new integration/document cases,
ordinary product/Party/portal/dashboard/ticket/layout regressions and restricted-
role isolation/immutability checks. Final renderer/state-label refinements pass a further 23 integration tests plus
the existing Party selector cases. A fictional multilingual, long-address/multiple-collateral
PDF is rendered and visually reviewed. Migration consistency, system, documentation
and syntax/whitespace checks pass.
Only the dedicated local test database was migrated; no production deployment
or workspace activation.

Full servicing command forms/private photo access, labels/statutory boundaries,
native recovery, unsupported corrections and pilot acceptance remain release
work. See the [checkpoint](implementation/khata-integration.md),
[workflow guide](flows/khata-balances-and-documents.md) and
[decision](adr/2026-10-01-khata-summaries-and-documents.md).

## Khata correction safeguards implemented locally (2026-10-01)

Administrator-authorized, immutable CORRECT sources now link uniquely to their
original operations. Whole receipt correction requires confirmation that money
was not received or fully refunded; it restores dues without altering charges,
allocations, principal or entitlement. Unhanded exchange cancellation logically
releases original reservations and reserves replacements for actual return, with
hard retained LTV and independent handover evidence.

Later dependencies are identified and refused; independent receipts can unwind
newest-first. Payout/opening, charges, active amendments/reductions, settlement,
completed returns and complex corrections remain unavailable. Money/custody
capabilities are required in addition to administration and Workspace write access.

Migration 0038 extends existing forced-RLS tables and uses account-locked active
membership guards. SQL recognizes compensation by operation sequence. 163
focused/regression tests pass, including 22 new correction cases. Migration
consistency, system, documentation and syntax/whitespace checks pass. Only the
dedicated local test database was migrated; no development/production activation
or ordinary-loan workflow changes.

UI/documents, shared summaries, native recovery and pilot review of correction
coverage remain release gates. See the [checkpoint](implementation/khata-corrections.md)
and [bounded correction ADR](adr/2026-10-01-khata-bounded-corrections.md).

## Khata exchanges, reduction returns and settlement implemented locally (2026-10-01)

All three authorized backend workflows are implemented. Same-metal grouped
exchanges use current approved prices and the owner's WARN/BLOCK policies.
Typed outgoing reservations stop backing withdrawals immediately; linked actual
handovers retain recipient/reference evidence. Formal reduction returns require
cleared due interest and hard retained LTV after repayment, independently of
exchange warning mode. Active reduction handovers recheck current cover and dues.

Settlement atomically collects principal and all unpaid interest through closure,
including annual accrued interest not yet due. Closing partial months use exact
activated revision segments and actual days; the original first-month floor is
preserved once. Financial settlement stops interest and zeroes entitlement, while
`SETTLED_RETURN_PENDING` preserves physical return obligations until the final
handover changes the account to `CLOSED`.

Migration 0037 adds guarded, directly owned selection evidence with forced RLS,
registry coverage and additive source/lifecycle fields. 141 focused/regression
tests pass, including 26 new custody/settlement cases. Tests cover warnings/blocks,
stale reviews, hard LTV, annual/partial/same-day closing interest, prior receipts,
permission separation, rollback, retries, concurrent exchanges/settlement and
restricted-role bypass attempts. Migration consistency, system, documentation and
syntax/whitespace checks pass. Only the dedicated local test database was migrated.

Corrections/compensation, operational UI/documents, shared summaries and native
recovery remain release gates. No development/production activation or changes
to existing flexible-loan workflows. See the
[custody/settlement checkpoint](implementation/khata-custody-settlement.md).

## Khata approved agreement changes implemented locally (2026-10-01)

The next backend slice adds immutable active-account proposals, separate approval
and activation operations, and principal repayment within formal limit reductions.
Only activated terms affect interest or future withdrawals. Limit increases add
unused entitlement without inventing principal; repayments reduce principal
without replenishing entitlement. Account number, opening date, payment anniversary,
frequency, LTV and lender identity remain fixed. Approvers cannot collect principal
without repayment authority; a cashier can execute an approved repayment.

Migration 0036 extends existing source shapes/guards, without new tenant tables or
ordinary-loan data changes. Canonical position replay and withdrawal guards now
recognize formal reductions. Interest uses exact dated segments under activated
revisions, summed before monthly half-up rounding. The original first-month floor
is preserved once. Already billed months and receipts remain immutable; raw
backdating, omitted repayment, unactivated segment sources and overdrawing repaid
capacity fail under the restricted database role.

115 focused/regression tests pass: 21 revision cases plus all earlier khata,
registry, ordinary partial-month policy and storage inventory suites. Coverage
includes annual dues, same-day ordering, half-paise segments, financial reductions,
licence servicing boundaries, stale approval, retries, permission separation and
concurrent activation. Migration consistency, Django system, documentation links
and Python syntax/whitespace checks pass. Only the dedicated local test database
was migrated; no development/production migration or activation.

This is a financial agreement-change checkpoint, with no collateral leaving
custody. Exchanges, reduction returns, settlement, corrections, UI/documents,
shared summaries and recovery remain delivery gates. See the
[agreement-change checkpoint](implementation/khata-agreement-changes.md).

## Khata interest finalization and collection implemented locally (2026-10-01)

The owner's next-step instruction now adds immutable completed-month charges,
exact calculation segments and interest allocations in migration 0035. Monthly
and annual anniversary dues retain the agreed monthly rate unit. Partial receipts
pay oldest dues first, reject advance/excess payments, and change neither principal
nor unused entitlement. Balances subtract actual receipts; clearing overdue dues
removes the interest-based withdrawal block.

Finalization and cash receipt are separate source operations, committed atomically
when collection needs catch-up finalization. Current-date commands enforce existing
repayment authority and Workspace write restrictions, UUID retries, review freshness
and Workspace/account locks. Three directly owned tables have forced RLS, registry
coverage, immutable evidence and parent/math/allocation guards. Deferred database
checks reject incomplete periods/segments/receipts; restricted-role tests reject
forged charges, skipped older dues, over-allocation and later additions to receipts.

94 focused/regression tests pass: 20 collection tests plus existing khata,
tenancy registry, ordinary partial-month policies and storage inventory suites.
Coverage includes annual billing without compounding, short-month clamping and
restoration, frozen charge authority, concurrent cashiers, rollback, commercial
access and permission separation. Migration consistency, Django system checks,
documentation links and syntax/whitespace checks pass. Migration 0035 was applied
only to the dedicated local test database; no development/production migration.

This checkpoint supports completed months under activated opening terms. Approved
limit/rate changes, exchanges, reductions, settlement/corrections, UI/documents,
shared summaries and recovery remain pending. Revision/settlement delivery must
extend the calculation/source guards together; those actions remain unavailable.
See the [collection checkpoint](implementation/khata-interest-collection.md).

## Khata opening, custody and staged withdrawals implemented locally (2026-10-01)

The owner's next-slice instruction is implemented in the local backend. Migration
0034 adds five guarded/RLS tables for source operations, owner policies, collateral,
valuation and photos. Receipt, approval and payout are separate; first payout
starts interest on the full limit. Staged withdrawals enforce current price cover,
unused entitlement, photo policy and overdue WARN/BLOCK. Unopened items can be
returned with evidence; cancellation cannot abandon held items or cancel debt.

Approval and payout snapshots bind typed valuation rows to their exact reviewed
items/prices. Later rows cannot extend an earlier frozen valuation. Deferred
database guards reject incomplete receipt/photo/valuation evidence and over-LTV
payouts, including raw restricted-role DML. Photos participate in retained private
storage inventory. Existing ordinary-loan operations are unchanged by this slice.

74 focused/regression tests pass: all khata modules, tenancy registry, existing
partial-month interest policies and storage inventory. They include concurrent
cashiers, retries/rollback, stale terms/prices/policies, current photo enforcement,
overdue blocking, permission separation, populated cross-workspace evidence and
raw history/LTV attacks. Migration drift, Django system, documentation and
syntax/whitespace checks pass. Verified migration rollback/reapply only on the
dedicated local test database after confirming no khata operation/custody rows.

No khata UI, production migration or enablement. Interest receipts, formal
revisions, exchanges, reductions/settlement and corrections remain next, followed
by documents, shared summaries and recovery. See the
[opening checkpoint](implementation/khata-opening.md) for exact delivered scope.

## Khata foundation and calculator implemented locally (2026-10-01)

Following the owner's implementation instruction, delivered the first backend
slice: independent/licence-associated series, immutable numbered draft identities,
append-only agreement proposals, authorized retry-safe services and pure KHATA-1
interest/entitlement/LTV calculations. Migration 0033 adds three directly owned
tables with forced RLS, parent guards, evidence/identity protection and registry
gates. A database allocator advances/fixes series numbering atomically; cancelled
accounts cannot recycle numbers or unfreeze licence association.

42 tests pass in a dedicated local test database: khata calculator/foundation/
concurrency, tenancy registry and existing partial-month policy tests. Raw
adversarial DML runs under a restricted role. Initial validation found and fixed
an address-length validator omission and updated the registry count for three
new models. See the [checkpoint and exact boundaries](implementation/khata-foundation.md).

Only DRAFT/CANCELLED are admitted; no financial activation, collateral workflow,
UI, auto-created series or production migration/enablement. Ordinary flexible-loan
services and policies remain unchanged by this slice. Full servicing, integration,
documents and recovery remain the next delivery work; these tests are not full
khata product acceptance.

Migration drift and Django system checks pass. Documentation checks cover 794
curated links and 25 khata-document links; syntax/whitespace checks pass.

## Khata independent and licence-associated series confirmed (2026-10-01)

Round 11 replaces mandatory licence attachment with workspace-owned khata series
and an optional same-workspace licence. The series owns its counter; numbers are
unique across all khata series in the workspace. Licence association (including
none) freezes at first issued account number; later changes use a new series with
a distinct prefix. Existing numbers, evidence and ordinary-loan sequences remain
unchanged by this design.

Updated the ADR, technical/delivery designs, screen proposal and scenario plan.
Added K39-K42 and planned SERIES-01 through SERIES-04 checks covering both modes,
number collisions, association freeze/races, isolation, totals and documents.
Independent series require no placeholder licence; lender identity is captured
explicitly, and reports offer a no-licence filter. No code, migration, test
implementation or production change was made.

Documentation checks pass: 788 curated links and 22 khata-document links, plus
scoped whitespace validation. Business/runtime tests remain planned.

## Khata concrete technical design prepared (2026-10-01)

Prepared the [technical design](architecture/khata-technical-design.md) against
current Loans, access, numbering and tenancy contracts. It specifies 13 candidate
records, dedicated khata counters under existing licences, account states and
existing action permissions, KHATA-1 interest/entitlement calculations, immutable
operations and ownership guards. Financial settlement stops interest independently
of physical handover; reserved outgoing items cannot secure another withdrawal.

Added concrete calculation, servicing, isolation, concurrency, correction,
document/recovery and ordinary flexible-loan preservation test cases. These are
planned tests, not executed checks. Annual leap-day/same-day revision conventions,
valuation freshness, correction coverage, licence/default boundaries and exact
document/recovery schemas remain identified technical review items. Business
scope remains as confirmed in rounds 1-10. Documentation only; no application,
migration, workspace configuration or production changes.

Documentation validation passes: 788 curated local links and 22 links in the
five khata design documents; scoped Git whitespace checks pass.

## Khata first-release scope confirmed (2026-10-01)

Round 10 confirms separate khata series, existing authorised loan approvers for
opening and limit/rate changes, new khatas without historical/paper import,
today-dated routine entries and no added charges, penalties or funding/repledging
in the first release. Updated ADR, screen/scenario plans and the
[consolidated scope/checklist](plans/khata-delivery-design.md#first-release-scope-and-implementation-checklist).
Collateral recording cannot invent new cash payout or silently import old paper
principal. Native khata recovery remains separate from historical migration.

Concrete schema/sequence mapping, correction/date edges, documents, preservation
tests and pilot preparation remain engineering work. Scope confirmation has not
changed application code, schema, existing products or production data.

## Khata D1-D5 accepted; flexible-loan compatibility explicit (2026-10-01)

Owner explicitly confirmed the five screen-review decisions: start/end day and
monthly paise rounding, one-time opening minimum across revisions, entitlement
carry-forward without repayment replenishment, oldest-due partial interest
allocation with advance/excess payments deferred, and clearance of due interest
before reduction returns while unbilled interest stays on schedule. Updated ADR,
scenario plan, screen review and delivery design to remove superseded pending
markers. Architecture remains proposed and implementation has not started.

Clarified that khata is a distinct offering in the existing Loans area, sharing
Party identity/access rather than ordinary-loan economics. Preservation of the
existing flexible products, current loans and future flexible originations in
JCL, JSK and Lakshmi is now an explicit release requirement. The delivery plan
requires workspace-policy fixtures, ordinary workflow regressions, mixed-account
summary reconciliation and migration/evidence preservation. Those code-level
checks are planned, not claimed as passed. Documentation links and whitespace
checks pass; no application or production change was made.

## Khata delivery design prepared; policy choices still pending (2026-10-01)

Prepared the [implementation design and sequence](plans/khata-delivery-design.md)
after inspecting actual disbursal, item-principal, obligation, media and access
contracts. Recommend explicit khata records/services within Loans, without
weakening ordinary-loan guards or inventing a maturity date. The proposal maps
record responsibilities, transactional commands, physical handover, reporting,
documents, portability, RLS and release/recovery requirements.

Delivery proceeds from design closure through calculator/evidence, complete
servicing, UI/integration and a separately reviewed named pilot. No real account
creation is enabled before servicing and correction readiness. The five D1-D5
recommendations remain pending confirmation. Documentation only: no application,
schema, product setup, tests or production records changed.

## Khata screen and calculation review prepared (2026-10-01)

At the owner's request, prepared a [screen-by-screen proposal](plans/khata-screen-review.md)
for the list, opening, account overview, withdrawal/deposit, exchange, interest
receipt, agreement change/reduction and settlement/history/settings. The compact
overview separates limit, actual principal, drawable amount and next interest due;
long guidance stays in contextual help. Reduction returns visibly enforce the
confirmed mandatory LTV check.

Five explicitly proposed decisions cover boundary days/rounding, minimum interest
across first-month revisions, unused drawing entitlement after amendments, partial
interest allocation and due-interest clearance for reduction returns. Fictional
examples and acceptance cases make each reviewable. No new business decisions
are inferred from the request to proceed. Remaining authorization, documents,
correction/default and portability design is retained. Documentation only; no
application, schema, tests, product configuration or production changes.

## Khata requirements refined through round 8; discussion only (2026-10-01)

Recorded the owner's confirmed staged-withdrawal, full-limit interest,
monthly/annual payment, formal limit-change and valuation-based exchange rules.
The [proposed ADR](adr/2026-10-01-khata-agreement-design.md) separates confirmed
requirements from the architecture proposal. The
[living plan](plans/khata-agreements.md) contains 38 scenarios with confirmed,
proposed and open outcomes, plus confirmed monthly-only rate entry and future
acceptance gates. FW-021 tracks this discovery; no delivery priority changed.
No application code, schema, configuration or production data changed. Existing
ordinary-loan rules remain authoritative; khata implementation awaits a later
owner instruction after design refinement.

Round 2 confirms mid-period old/new-limit interest splitting, actual-withdrawal
coverage at agreed LTV, principal reductions only through formal reduction/renewal,
current-rate exchange valuation and monthly/annual payment in arrears. Exchange
value shortfalls now warn and proceed by default, with owner-selected strict
enforcement and later top-ups. This refines the earlier blanket equivalence rule.
Exchange and account-LTV shortfalls are distinct.

Round 3 confirms anniversary dues (10 October to 10 November or next 10 October)
and four months' interest for an annual payer closing after four months. One
owner exchange policy warns/allows even for value shortfalls or account-LTV
breaches, or disallows the exchange. Separate top-up follow-up is deferred.
Overdue interest also has owner-selected warn/block behaviour. Round 4 fixes rate entry to a monthly percentage,
independent of monthly/annual payment. Annual-rate entry is deferred; retain the
monthly unit in agreement evidence and documents.

Round 5 confirms simple interest, a full first-month minimum collected at month
end, later actual-day partial months, and short-month clamping with restoration
of the original anniversary. Overdue block mode prevents withdrawals/exchanges
but permits payments, deposits and settlement. Limit revisions retain number
and anniversary; reducing below outstanding principal requires repayment of the
difference. A fictional dated walkthrough now covers staged draws, exchange,
increase, reduction and closure.

Round 6 confirms month one is included in the annual bill for annual payers;
early closure collects the full first-month minimum. Actual-day fractions use
actual days between anniversaries, with symmetric dated increase/reduction splits.
Current warn/block policies govern subsequent operations on existing accounts,
preserving completed transactions. Khata has no fixed maturity and continues
until borrower settlement. Boundary-day/rounding details remain proposed.

Round 7 confirms default overdue warnings from the day after due date, grouped
same-metal exchanges, no cross-metal replacement, returns through reduction or
settlement, and dated monthly-rate revisions preserving earlier calculations.
A reduction-return example explains selecting whole items while retaining
coverage for reduced actual principal. Round 8 confirms that coverage as a
mandatory reduction-return check, with no exchange-warning override. Standalone
excess returns are not selected. Next review the screen flow and remaining
calculation/operational details. Documentation only; no deployment.

## Consistent ticket frame auto-fit deployed (2026-10-01)

Implemented measured v4 SHRINK fitting for complete scalar text and table rows,
with a largest-fitting tenth-point font search and 6 pt floor. Explicit leading
scales with the font; padding, frame geometry and short text retain their settings.
Character thresholds no longer unnecessarily shrink precision frames. New starter
and editor-added frames default to SHRINK; old schema/Flow/explicit WRAP/ERROR
semantics remain. Renderer evidence has a distinct v4-fit2 identifier.

All 160 document/setup regression tests pass, including existing artifact reprints.
Fictional English/Tamil paragraphs, long identifiers and tables were rendered and
visually reviewed. Production is `rokkad:ticket-autofit-20261001-8dd479dbb0bf`, a
scoped five-file patch over the prior live image. Baseline hashes, candidate build,
zero-migration plan, drift and a fresh verified server-only backup passed. Candidate
checks rendered RA00594, C07565 and 30 recent active JCL loans without issuing PDFs.
No production borrower data was downloaded.

JCL's audited template revision 6 (version 5) is published and resolves for every
active series. The five remaining WRAP text frames now use SHRINK; geometry,
starting typography and paper profiles are unchanged. Activation and independent
verification preserved the full contact block in both copies and the earlier
mixed-metal weight fix. Previous revision 5 remains immutable; business, customer,
issued-document and numbering rows were unchanged. Stored PDF reprints retain
their existing bytes. Content that cannot fit at 6 pt still requires a larger frame.

Live source hashes and read-only checks in all three Workspaces passed under the
restricted role; no migrations remain. Runtime configuration, mail/storage timers
and mail health are preserved. Private deployment/template evidence remains under
`/home/rokkad/deploy/cutover-20260924/ticket-autofit-20261001/`.

See [the decision](adr/2026-10-01-ticket-frame-autofit.md).

## Exact interest history and contextual policy help deployed (2026-09-30)

Implemented loan-history/2 alongside v1: exact calendar fractions/unrounded values,
item rates/bases/charges, advance application, event-free accruals and release catch-up
are reconciled on export and restore. Product mappings explicitly preserve supported
bullet/flexible contracts. Existing staging, approval, idempotence and RLS remain;
0017 extends the immutable batch profile guard. Other history exclusions remain.

Calculation setup now has a Bootstrap help drawer, full guide/read-only example,
conditional slab/compound fields and pre-save summary. Existing loan snapshots and
JSK WH policy 5 are unchanged. All 53 focused/regression tests pass, including exact
weekly restore, all four treatments, early closure, native advance-covered release,
mixed rates, cross-Workspace restore, corruption rejection, profile immutability,
setup mapping, older v1 compatibility and calendar examples. Another 76 compatibility
tests passed for opening contracts/export/restore, history guards, bundle history and
legacy opening admission: 129 tests across the final suites. Migration drift is
clean; 768 curated documentation links pass.

Production is `rokkad:interest-help-history-20260930-6fe8241d45bd`, a scoped 19-file
patch over the prior live image. Baseline hashes, candidate schema drift and the
single migration plan passed before a fresh verified server-only backup. Owner-only
migration 0017 and candidate/live read-only checks passed under the restricted role
in JCL, JSK and Lakshmi; no pending migrations remain. The new static volume preserves
previous assets, and the public hashed interest-policy script matches the source.
Mail/storage timers and runtime configuration are retained; mail health passed.
JSK WH policy 5 remains unchanged. No production loan was imported or repriced.

Live browser checks confirmed the help drawer and full guide, the fictional weekly
example (440 calculated / 300 advance applied / 140 additional), conditional slab
fields and the pre-save summary. The verification tab was closed without saving
form selections. Private deployment evidence remains under
`/home/rokkad/deploy/cutover-20260924/interest-help-history-20260930/`.

See [the decision](adr/2026-09-30-exact-interest-history-v2.md) and
[contract](contracts/loan-history-v2.md).

## Partial-month choices deployed; JSK WH uses started weeks (2026-09-30)

New calculation-policy revisions now have a full first-month minimum followed by
full-month, slab, started seven-day blocks, or actual-day charging. Weekly/day
fractions use the actual monthly period length; weekly charges cap at one month.
Monthly opening principal bases, advance consumption and servicing workflows are
retained. Setup supports complete series calculation policies above license and
Workspace defaults. Approval, disbursal and renewal freeze the new minimum flag;
earlier rows/payloads retain their prior meaning. New-policy paise rounding handles
the database quantum's trailing zeros, while old snapshots retain their precision
behavior. Exact recurring fractions stay in event evidence, with explicit rounding
only for the existing fixed-precision accrual projections.

Production is `rokkad:partial-interest-20260930-b42a046cdc53`, a reviewed twenty-file
application/migration patch on the combined-label image. Migration 0032 was applied
through owner-only settings after a verified server-only backup. Candidate and live
checks passed in all three Workspaces under the restricted runtime role, including
forced RLS, no pending migrations, setup rendering, resolution and source hashes.
Static assets, mail/storage timers and configuration were retained. The first
candidate attempt rejected a case-sensitive verification string; schema rollback
and old-web restoration succeeded before the corrected check and deployment.
Private evidence remains under
`/home/rokkad/deploy/cutover-20260924/partial-interest-20260930/`.

The owner-authorized activation appended **policy 5, revision 1**, effective
**30 September 2026**, specifically for **JSK WH (LINODE-2, series 9)**. It retains
gold 1.1%/silver 3% monthly, simple interest, 95% LTV and one upfront month, with
STARTED_WEEKS after the first-month minimum. The audited transaction verified hashes
of existing JSK loans, approvals, disbursals, policy snapshots and events were
unchanged; the other series still resolves its previous policy. The live browser
shows WH and the selected weekly rule. No existing loan was repriced or charged.

All **107 distinct focused/regression tests passed across the final runs**, covering
the accepted table, leap years/month ends, first-month minimum, advance application,
approval freezing, weekly release persistence/idempotence, setup, isolation,
origination, redisbursal, renewal and older history compatibility. Test fixtures were
corrected for scoped series IDs, historical migration model state, static storage
and release numbering. Migration drift and curated documentation links are clean.

The bounded `loan-history/1` contract accepts the optional minimum flag while keeping
old documents valid. It explicitly refuses weekly/daily history export because its
fraction format cannot guarantee exact restore; complete database backups retain
the evidence. See the [policy guide](flows/loan-interest-policies.md) and
[decision](adr/2026-09-30-series-partial-month-interest.md).

## Combined loan collateral label deployed; interest policies reviewed (2026-09-30)

Loan detail > Collateral now offers **Print one label for all collateral** alongside
the existing individual labels. The single 100 × 60 mm PDF includes every recorded
item's description and saved quantity, net-weight totals separately by metal, and
one QR link to the authenticated loan. Tamil shaping and font fitting preserve full
text; content that cannot fit at the minimum readable size is rejected with guidance
to use individual labels. Successful rendering records the existing per-item label
audit entries atomically, sharing the combined PDF checksum. No financial events
or new database tables are involved.

All **25 distinct collateral-media tests passed** after fixture corrections, covering
dimensions/content, audit records, overflow rollback, permissions and Workspace
boundaries. A fictional mixed-metal/Tamil PDF was rendered and visually inspected.
Read-only candidate and deployed checks passed in JCL, JSK and Lakshmi without
creating label audit records; the production browser displays the new link.

Production is now `rokkad:loan-label-20260930-366c681c499d`
(`sha256:68e594ce00b30c6fa88da45373e55e6197627378123673e2610ffe17d1ef1c0e`),
a four-file patch on the guided-import image. Baseline source hashes, a fresh
server-only recovery backup, candidate checks and automatic rollback protected the
switch. Static assets, schema, runtime configuration and mail workers/timers were
unchanged; unrelated local billing work was excluded. Private release evidence is
under `/home/rokkad/deploy/cutover-20260924/loan-label-20260930/`.

A restricted-role, read-only review also verified the current interest defaults
and their enforcement. The [interest policy guide](flows/loan-interest-policies.md)
records monthly rates by Workspace/series, the distinct rate and calculation-rule
inheritance, approval/disbursal freezing, authorized overrides and imported-loan
exceptions. No interest policy or existing loan terms were changed.

## Guided outstanding-register import deployed (2026-09-30)

The first FW-007 customer workflow now accepts its explicit XLSX/CSV template,
selects the original licence/series and handover, matches existing/new customers,
previews individual collateral/terms and totals, groups exceptions, and commits a
confirmed batch atomically through the existing opening engine. Exact retries
reuse results; changed source identities, stale reviews and future-number clashes
hold the batch. Owner authority, write access, forced RLS and immutable evidence
remain enforced. No new disbursal or fabricated historic receipts are produced.

This first profile is limited to unchanged principal, first-month interest paid
upfront, original-anniversary aggregate interest and known bullet maturity/custody.
Other rules, reduced-principal openings, manual paper entry, arbitrary source
mapping and richer customer/media input remain FW-007 work; complete Workspace
export/restore remains FW-012. The [workspace guide](flows/guided-outstanding-register-import.md)
explains these limits and the shared architecture.

All **61 focused/regression tests passed**, including 13 guided-workflow tests,
real HTTP/CSRF, source replay, customer drift, multi-item totals, all-or-nothing
rollback, XLSX/formula handling, restricted-role RLS, immutable results, protected
numbering and subsequent release. Fictional desktop/mobile pages were rendered
and inspected using the exact verified Bootstrap stylesheet; no page overflow
at 390 px. Workbook structure roundtrip passed.

Production is now `rokkad:guided-import-20260930-14a3228cbcf7`, a 15-file patch on
`rokkad:expired-trial-20260930-110476c6eb7f`. Only
`data_portability.0016_guidedopeningbatch` was pending and applied through owner-only
migration settings after a verified server-only recovery backup. Runtime checks
confirm forced RLS, restricted database role, no pending migrations, nine owner
GET/download checks across JCL/JSK/Lakshmi, and zero created import batches. Public
HTTPS still requires sign-in, all source hashes match, and mail/storage timers,
configuration and mail health are preserved. Separate local FW-019 billing changes
were excluded. The initial collectstatic attempt found the inherited read-only
static volume; the corrected command uses a dedicated writable collector mount,
while the web mount remains read-only. Candidate checks passed before switching.
Private deployment/recovery evidence remains in
`/home/rokkad/deploy/cutover-20260924/guided-import-20260930/`; no customer data or
backup was copied off the server. No real loan import was part of deployment.

## FW-019 monthly self-service implemented locally; activation remains paused (2026-09-30)

Added the selected INR 1,499/month offer, six-member/twelve-collection consent,
signed thirty-minute review and owner-facing agreement-creation POST. Authority,
verified email, current frozen terms, natural trial expiry, lifecycle and capacity
are checked again before the durable consent/reservation commits. Provider creation
occurs outside a Workspace transaction; duplicate/uncertain attempts retain the
existing recovery path. Generic one-off/annual catalog publication stays separate.

The new `BILLING_PUBLIC_RECURRING_BINDING_ID` defaults to zero. No production
configuration, source release, billing/access record, provider agreement or outgoing
email was changed. JSK/JCL/Lakshmi trials and the attended JSK-first plan remain.
The existing monitored mail batch can include receipts after the reviewed first
receipt and queue inspection; its prepared scope and rollback are documented in
the [pilot plan](plans/monthly-billing-pilot.md).

All **178 focused and regression tests passed** in 305.155 seconds, including the
**14 new self-service tests** covering real HTTP transaction boundaries, restricted
runtime role, changed/stale/tampered consent, ownership/CSRF, seats/lifecycle,
active-trial rejection, timeout/double-submit recovery, exact paid period and one
receipt despite replay/dispatch repetition. Provider/SES calls use fictional mocks;
this is not real payment or delivery evidence. Regression coverage includes public
trials, recurring creation/owner actions/cycles/access, live-mode boundaries,
expired-trial conversion and scoped mail dispatch. Django checks and scoped diff
whitespace checks passed. Local result: `outputs/public-recurring-regression-20260930.log`.
See the [decision](adr/2026-09-30-owner-monthly-self-service.md). Next: deploy paused,
verify release preservation, then conduct the approved-scope JSK pilot after expiry
before enabling public paid subscriptions and recurring receipt dispatch.

## FW-019 existing-Workspace rollout agreed; self-service scope clarified (2026-09-30)

Owner accepted JSK first, then JCL/Lakshmi before their seven-day grace periods
end on **15 October at 23:39 IST**. An explicit temporary-access decision is the
fallback if delayed; no grant, date change or charge was made. Current paid flow
still requires operator-created agreements. Recommended next implementation is
the monthly owner offer/consent/creation/recovery flow and paid receipt dispatch
scope during the trial window, with public paid activation after pilot review.
See [the documented sequence](plans/monthly-billing-pilot.md#existing-workspace-rollout-and-self-service-preparation-2026-09-30).

## FW-019 JSK pilot prepared; expired-trial payment fix deployed (2026-09-30)

The owner selected JSK after natural trial expiry: **8 October at 23:39:08 IST**.
Prepare attended activation on **9 October or later**; no automatic charge or
activation approval is implied. Read-only checks verified the frozen live
INR 1,499/six-member offer, clean billing evidence, public callback routing and
active mail monitoring. Fees will be reconciled after the approved settlement.

Found and fixed a first-payment gap: expired trial Plan 1 could not adopt paid
Plan 2. A verified current capture now converts only a naturally expired,
history-free trial with an eligible active Workspace, matching agreement and seat
capacity. It uses exact paid dates and records old terms; preserves trial dates;
and rejects early/future/conflicting histories. Replay and receipt-failure rollback
are covered. **139 billing tests passed**, including twenty new Test/Live cases.

Deployed only `apps/subscriptions/recurring_cycles.py` at **18:30:43 IST** as
**rokkad:expired-trial-20260930-110476c6eb7f** over the import-repairs image.
Candidate/live restricted read-only checks, source/configuration hashes, public
HTTPS and four mail timers passed. JSK's trial/three members and zero billing
records are unchanged. Both purchase gates stay false; public trial and mail stay
enabled. No migration, provider write, charge or email. Temporary candidate
credentials copy removed; private rollback/release evidence retained server-side.

The [pilot runbook](plans/monthly-billing-pilot.md#jsk-selected-after-natural-trial-expiry-2026-09-30)
specifies approval, one durable agreement, exact payment/access verification,
reconciliation before retry, one approved receipt and settlement/renewal monitoring.
Sandbox failure/held-period acceptance remains unproved, tracked separately from
the bounded pilot; full FW-019 is not complete. See the
[transition decision](adr/2026-09-30-expired-trial-first-recurring-payment.md).

## FW-019 fee clarification removed as a launch gate (2026-09-30)

The owner accepts learning exact Razorpay charges from real payments. Updated
the pilot plan, rollout checklist and stable memory: detailed fee/promotion
clarification no longer blocks launch; reconcile actual deductions after the
first approved settlement. Customer pricing remains INR 1,499/month.
Next is a limited monthly pilot readiness/risk review, with unresolved provider
test outcomes still recorded honestly. No activation, collection, trial change or
support message was performed. See the
[revised pilot preparation](plans/monthly-billing-pilot.md#owner-accepts-fee-uncertainty-prepare-a-limited-pilot-2026-09-30).

## FW-009 Digio acknowledgement and business handoff verified (2026-09-30)

Reviewed Digio Support Desk's **16:44 IST** reply from Richa Sharma. It acknowledges
the enquiry and copies bd@digio.in to connect with us. Gmail shows signing by
digio.in; response recipients include admin@rokkad.com and Digio support/business,
not the requested support@rokkad.com. No eligibility, hosting, method or pricing
answer is supplied. Await the business team's response; supplier selection remains
pending. Updated the [enquiry record](plans/borrower-identity-feasibility.md).
Read-only email review; no follow-up sent or registration/integration performed.

## FW-019 post-call email verified; technical resolution still unproved (2026-09-30)

Verified Razorpay's **17:48 IST** email from Farooq.K in pricing ticket 21174094,
including Gmail sender/signing details. It adds first-payment examples for INR 1,499:
net UPI INR 1,474.82, cards INR 1,447.71, Aadhaar eMandate INR 1,447.68. Listed
components sum correctly; these are quotes, not verified settlements. Renewal,
promotion and mandate-variant fee combinations remain open.

The email says integration ticket 21146138 was resolved, but a fresh Dashboard
check still shows In Progress with our escalation latest. It supplies no working
authorization, failure/recovery or shorter-test procedure, only generic creation
instructions. Technical launch acceptance remains unproved. No message, provider
mutation or live activation was performed. See the
[post-call review](plans/monthly-billing-pilot.md#post-call-pricing-email-verified-2026-09-30-1748-ist).

## Import corrections deployed; retained facts restored without re-import (2026-09-30)

Deployed **rokkad:import-repairs-20260930-fa40fe550478**, a six-file patch over the
auctioneer-handover image. A fresh server-only PostgreSQL backup passed archive
catalogue and SHA-256 checks before repairs. No schema migration was required.
See the [audit and repair checkpoint](implementation/import-confidence-audit-20260930.md)
and [decision](adr/2026-09-30-retained-import-particulars-and-quantity-repair.md).

- JCL's unused unnamed series 5 now has an empty prefix and next **10000**, after
  checking the sealed numeric history through 9999, prefix overlap and no native
  use. The existing ceiling remains **10000**; this does not extend the register.
  Existing loan numbers and the other sequences were not changed.
- Restored **6,411** null operational collateral quantities from accepted opening
  evidence: JCL **2,455**, JSK **1,514**, Lakshmi **2,442**. Each of the **6,391**
  affected loans has an actor/source-linked correction audit. The restricted-role
  operator locked each loan and compared before/after hashes of all loan fields,
  collateral fields except quantity, events and issued-document evidence. All
  passed, including loans with later releases. No balance/event/custody rewrites.
- New opening imports retain quantity directly. The working Form E reader now
  surfaces completed import borrower/address particulars and recorded tenure,
  including C04526. It labels source-snapshot identity honestly and distinguishes
  an owner maturity assumption from recorded original tenure. Original valuation,
  unsupported history and other genuine source gaps remain explicit.
- Ordinary customer status and contact/address default edits now record the
  authenticated actor, object and before/after flags atomically, including
  demotions/deletions. The eight older JCL changes remain preserved with incomplete
  attribution; no retrospective actors or reset to source choices were invented.

**180 tests passed**: 154 opening/repair/reader/numbering/Party/Form E tests plus
26 Party-child import compatibility tests. Coverage includes replay, audit-failure
rollback, conflicting quantities, later full releases, permissions and restricted
Workspace isolation. Candidate and deployed C04526 checks passed; deployed file
hashes match, no migrations are pending, HTTPS requires login, and mail/storage
worker configuration/timers and mail health remain intact.
The final enforced-read-only rerun matched all 6,411 quantities with zero repairs
remaining. The temporary runtime-credentials copy was removed and 31 private
artifacts were sealed; the original audit evidence is retained unchanged.

Private backup and correction evidence remain server-side under
`import-repairs-20260930/`; no sensitive copy was placed in OneDrive. No Form E
review or permanent batch was created. Further statutory work stays paused.
Next is the bounded guided customer migration journey (FW-007), followed by proved
export/restore coverage (FW-012); neither is claimed complete. No commit/push requested.

## Import confidence audit completed; bounded corrections identified (2026-09-30)

Completed the owner-authorized read-only audit against the final source/package
and current production. [Full report](implementation/import-confidence-audit-20260930.md).
All 45 sealed files and three freshly extracted source indexes match. The restricted
runtime role used enforced read-only transactions; the main run used a repeatable
snapshot. No business writes, deployment, re-import or Form E attestation occurred.

All **8,639 imported customer identities, 6,391 opening loans, 39,215 archived
closed records and three accepted exclusions** reconcile. Frozen balances,
borrower/loan identities, original dates, collateral economics, original schedules
and interest readers pass. Every source loan is accounted once. JSK's 33 later
closures are preserved, with 33 release and five accrual events; native later loans
are counted separately. Current recorded balances are not final collection quotes.

All **28,422** media receipts/targets and **29,564** application objects pass fresh
existence/size checks; **3,614** files remain documented as missing at original
source. This did not re-download/hash every R2 object or certify backup prefixes.

The bounded findings are:

- JCL's unused unnamed source series (destination 5) remains active with invented
  prefix `LEGACY6-`/next 1 instead of continuing the numeric register through 9999.
  No native loans exist in it. Correct its continuation under numbering guards
  before using it; this audit did not change the counter.
- **6,411** collateral quantities are retained in opening evidence but absent from
  the newer operational quantity column. Prepare source-backed mapping/reader
  corrections, not manual re-entry or changes to frozen evidence.
- C04526 retains its borrower, linked address and recorded tenure. Form E's native
  ticket-only identity projection and explicit unknown tenure hide available
  source evidence. Unknown original valuations/gross weight remain genuine gaps.
- Eight JCL records changed after import: one customer status, three primary
  contact flags, four default-address flags. Original inputs match, but inspected
  audit evidence is insufficient to attribute every later change. Preserve current
  choices; improve traceability rather than resetting them.

Four raw-source/package customer-status differences map exactly to the owner's
outstanding-loan decisions for RA00554/C07517/RA00575/C07545. They are accepted
interpretations, distinct from the eight later changes. Recorded tenure exists for
5,780 openings; 611 use the documented missing-maturity rule. No opening establishes
a valuation dated to original pawning. Preservation is verified within the accepted
scope; this is not blanket certification of historical statutory completeness.

Private evidence stays under the server's `import-confidence-20260930/` directory.
Three operator audit scripts and the report are now in the working tree. An initial
archive-shape checker failure and a resource-exhausted follow-up were corrected;
final runs completed. Follow-up queries now select narrow fields and used resource
caps; web remained running with zero restarts. Scripts passed syntax checks.
Next: the small numbering/retained-fact/provenance queue in the
[active plan](plans/portability-confidence-and-completion.md), then guided migration.
Further statutory work remains paused; no commit/push was requested.

## Priority reset: import confidence before further statutory work (2026-09-30)

The owner feels spread across too many features and has explicitly put legacy-data
correctness and robust, usable portability ahead of further statutory forms.
Recorded the [single active sequence](plans/portability-confidence-and-completion.md):
read-only three-Workspace import confidence report → demonstrated repairs → guided
migration (FW-007) → export/restore coverage and complete-package scope (FW-012).
Further FW-013 implementation, Form E source attestations and permanent print batches
are paused. Existing deployed features and JCL E-1 remain intact. No application,
schema, financial data, source-review or production configuration change was made.

Preliminary evidence review confirmed the September 25 checkpoint documents 8,639
customers, 6,391 outstanding openings, 39,215 closed-history records and three
accepted exclusions, plus 28,422 attached media references and 3,614 missing source
files. These are historical acceptance figures, not a new claim about live totals.
Read-only server metadata confirms `MIGRATION_AND_LOCAL_RECOVERY_VERIFIED`,
`RECONCILED_DATABASE_ONLY`, an exact source match, and package
`650becbb16bcd44c2cb9af2281eaeb3d5497dda72a546aaa790b2cc125028400` bound to
`rokkad_production_20260924`. No customer rows, source dump or backup were downloaded.

Code review establishes that the old `verify_package` assumes a just-imported
target: exact Party/loan/event counts and equality of mutable Party fields. It must
not be rerun unchanged to assess a system with legitimate later business activity.
The selected audit must separate frozen import evidence, current records and later
events, and classify actual mismatches versus source limitations, approved
interpretations and reader gaps. C04526's Form E review warning alone does not
establish an import defect; trace its fields from retained source to reader first.

Memory, active/future work and portability/statutory plans now reflect this scope.
Older migration plan checkpoints are explicitly historical. Full source-to-live
reconciliation and the confidence report remain the next deliverable; no clean-data
certification, repair or portability-completion claim is made. Documentation-only
changes were checked for consistency; no code tests or deployment were needed.

## Auctioneer handover deployed; first JCL Form E book opened (2026-09-30)

Deployed the reviewed 12-file handover patch as
**rokkad:auctioneer-handover-20260930-bac8e8898a04**, over the billing-cancellation
image. Administrators can save a fixed per-licence cohort (up to 100 complete loan
numbers), print/download a reviewed version, and reconcile every original loan
against subsequent releases, repayments, custody and notice-readiness changes.
Prior omissions need explicit reselection; closed/settled/held loans cannot enter
the remaining list. Saved versions preserve their reviewer/time, canonical recorded
balances and particulars. No sending, auction transition, collateral movement or
financial write is introduced. The in-workspace staff guide explains the boundary
from statutory catalogues and postal service. See the
[handover guide](flows/auctioneer-handover.md) and
[ADR](adr/2026-09-30-auctioneer-handover-reconciliation.md).

**78 tests passed** across handover, statutory notices, Form E batches and the
Workspace registry. Coverage includes duplicate/stale/expired confirmations,
release/repayment reconciliation, manual withholding, immutable/cohort/version SQL
guards, restricted-role isolation, permissions, CSRF, private hash-checked exports
and spreadsheet formula protection. Migration drift/system checks passed; fictional
English/Tamil print-media rendering and Indian money formatting were inspected.
Administrative print HTML preserves facts, not byte-identical PDF layout.

Production preparation compared the four existing-file hashes with the retained
local release archive; unrelated dirty changes were not packaged. Automatic review
rejected downloading live source into OneDrive, so no production source was copied:
hash-only comparison was used. A private server-side operational backup preceded
the sole additive `loans.0031_auctioneer_handovers` migration. Both new models have
direct ownership, forced RLS, table/sequence grants and SQL immutability; registry
coverage is now 126 models, with the unchanged 14 media FileFields.
Candidate and deployed read-only checks passed: 21 page renders, three real loan
projections, zero saved handovers, one existing Form E book, all 12 source hashes,
unchanged configuration/billing/mail flags and timers, and mail health. Private
logs/manifests remain in the server's `auctioneer-handover-20260930/` cutover folder.
No auctioneer message or business transaction was created by release verification.

Rebased the separate cleanup operator to
**rokkad:storage-cleanup-20260930-a08a54876c8b** with unchanged cleanup sources.
Read-only discovery passed with no candidates; no cleanup ran.

Separately, the owner selected **JCL C, landscape A4, from 01/01/2026**, confirmed
the physical sample and specified a new book. Opened **E-1**, licence **813/94**,
starting at page **1**, through the existing authorized service with an explicit
assisted-operation note. There are **1,500 pending entries**; the first 100 have no
hard mapping blockers but still require original-evidence review. No source review
or permanent print batch was invented/saved. Earlier paper references were not
supplied and remain explicit. Next Form E acceptance is review of the first entries
and the first full/partial saved batch; this is not certification of historical
completeness or the entire statutory suite.

## FW-009 approved provider enquiries sent (2026-09-30)

Following explicit owner approval of the exact message and all three recipients,
sent separate enquiries from admin@rokkad.com to Surepass contact@surepass.io
(15:15 IST), Digio support@digio.in (15:16), and Cashfree care@cashfree.com (15:17).
Each body requests replies to support@rokkad.com; no account Reply-To setting was
changed. Gmail confirmed every send and the Sent search showed all three messages.
Evidence: `outputs/fw009/provider-enquiries-sent.png`. The initial sending block
below is resolved. Provider delivery, sales routing, eligibility and pricing remain
unconfirmed; no registration, purchase, integration or live identity collection.
The [review](plans/borrower-identity-feasibility.md) records the exact enquiry and
delivery evidence. Optional guidance for the JCL pilot remains the agreed direction.

## FW-009 provider comparison resumed; enquiry awaiting approval (2026-09-30)

The owner selected optional staff guidance for the identity/name-address pilot,
with separate optional phone possession checks and no new loan-approval gate.
J Champalal Pawn Brokers (JCL) is the proposed first lender; replies should go to
support@rokkad.com. Refreshed the [feasibility review](plans/borrower-identity-feasibility.md)
with Digio, Surepass and Cashfree capabilities, pricing unknowns, selection criteria
and one comparable enquiry. Surepass's advertised OVSE/app and DigiLocker routes
make it a leading candidate alongside Digio; no supplier or integration is selected.
The exact Surepass email is saved as a Gmail draft from admin@rokkad.com.
Automatic approval review rejected Send because the external payload includes
operating-model and pilot-lender details; explicit message approval is required.
No enquiry was sent; Digio/Cashfree remain prepared local text. No registration,
paid commitment, live identity test, application or production change occurred.

## FW-019 awaiting provider test guidance (2026-09-30)

At **14:39:52 IST**, the preserved shorter provider agreement had **expired** with
zero paid cycles and no invoices. The INR 5 payment candidate remains Created;
local financial/mail counts and absence of Workspace access are unchanged.
This attempt is terminal and cannot become the shorter successful acceptance by
waiting. No replacement attempt or provider mutation was made.
The subsequent ticket check found **21146138** still In Progress with our escalation
as the latest message; no technical procedure or alternative has arrived there.

The read-only recheck at **12:58:59 IST** found the preserved shorter test still
Created, with zero paid count/invoices and no Workspace access. Its INR 5 payment
candidate also remains Created. Ticket **21146138** is In Progress with our approved
technical escalation as the latest message; closed ticket **21146171** has no
technical answer. Pricing ticket **21174094** has no new clarification beyond the
29 September responses and displays a response target of 1 October, 13:43.

The earliest-launch work is blocked on provider guidance/external evidence for
authorization, failed renewal/recovery and shorter held-access acceptance.
Remaining fee clarification and bounded live-pilot acceptance are also open.
Resume when Razorpay supplies a supported procedure or a documented alternative
that can be reviewed and validated. Production paid billing remains disabled;
this checkpoint does not mark FW-019 complete.

## FW-019 cancellation notice deployed with billing paused (2026-09-30)

Production read-only readiness found the reviewed pre-confirmation cancellation
notice/refund-policy link missing from the live image. Deployed only
`templates/subscriptions/recurring.html` as
**rokkad:billing-cancel-20260930-c1db71cd66e6** over the current Form E image.
Candidate and live unsaved-agreement renders pass; exact source and preserved
configuration hashes match. Frozen INR 1,499/zero-GST/six-member offer, permanent
admin, JSK trial expiry/member count and zero live financial records were verified
under the restricted role in a read-only transaction. Billing gates stay false;
public trials/mail stay enabled. Four mail timers and login/pricing/refund HTTPS
checks passed. No payment, email, trial change or migration occurred.

The separate cleanup operator was rebased to
**rokkad:storage-cleanup-20260930-e7d7bd28c3dd** with identical cleanup sources;
read-only candidate discovery passed, with no cleanup performed. Private rollback
and release evidence: `billing-cancellation-release-20260930/` under the existing
server cutover directory. See [billing readiness evidence](plans/monthly-billing-pilot.md#cancellation-notice-deployed-and-live-readiness-verified-2026-09-30).
The preserved short authorization was still Created at 12:52 IST. Provider
failure/recovery, shorter held-access validation and fee clarification remain open.

## FW-019 shorter test attempted; technical escalation submitted (2026-09-30)

Prepared one fictional monthly Test Mode agreement with a thirty-minute scheduled
start using the existing implementation/binding. Updated only the isolated local
billing database's five pending additive migrations; historical paid/mail counts
were preserved. The official test-card authorization opened a blank bank page and
checkout reported failure. At 12:49:45 IST, the agreement and INR 5 payment candidate
remain Created, with zero invoices/paid count and no Workspace Subscription/access.
No retry, simulator charge, refund or cancellation was performed.

All **119** focused recurring/owner/cycle/held-access/live-boundary tests passed
in a dedicated database. No app defect was established or billing rule weakened.
The user-approved technical escalation was sent and verified in ticket **21146138**,
referencing **21146171**, asking for working authorization, failure/recovery and a
shorter supported acceptance path or precise limitations. New local authorization
is disabled again; webhook/tunnel/mail remain disabled, production unchanged.
The [pilot plan](plans/monthly-billing-pilot.md#shorter-rehearsal-attempted-and-technical-escalation-sent-2026-09-30)
records exact evidence and criteria for replacing the 28 October check. Both
provider failure/recovery and naturally due held-access acceptance remain open.

## Form E deployed; physical book opening remains branch-controlled (2026-09-30)

Owner approved proceeding with rollout. Deployed the reviewed 19-file Form E patch
on the existing statutory release as `rokkad:form-e-20260930-16449e12f6d0`.
The five changed existing files were compared against live source; unrelated dirty
repository changes were not packaged. A private server-side operational backup
completed before the exact `loans.0030_pledge_book` migration using owner settings.
No other migration was pending. Runtime table/sequence grants, forced RLS and
immutability triggers were verified for all four new tables.

Candidate and live checks passed: 40 existing/navigation pages plus Form E-specific
renders, nine live series projections, 18 PDFs across both layouts and two existing
private document reads. All 19 source hashes match the release manifest; email and
billing flags/configuration and timers were preserved, mail health passed, and
anonymous requests to the JCL/JSK book pages redirect to sign-in. Final container
check shows running with zero restarts. Checks were read-only; no real books,
reviews, batches or loan transactions were created. The 111-test local validation
and numbered fictional PDF inspections from the preceding checkpoint remain the
implementation evidence. Physical sample acceptance and each branch's opening
date/page/reference are deliberately captured when an administrator opens a book.

Rebased the separate cleanup operator to
`rokkad:storage-cleanup-20260930-dbb25cc5c6fe`, based on the new live image. Its
read-only candidate discovery passed with no candidates; no cleanup executed.
Both runtime and operator now register all 14 FileFields, including retained Form E
PDFs. The inventory timer uses the current web container.

Private deployment manifests, logs and configuration remain on the server under
`/home/rokkad/deploy/cutover-20260924/form-e-deploy-20260930/`; private backups remain
server-side. Local source-only release tooling is under ignored
`outputs/form-e-deploy-20260930/`. Entry point: **Reports > Statutory forms & notices
> Form E books & daily activity**. JCL: `/w/jcl/loans/statutory/books/`; JSK:
`/w/jsk/loans/statutory/books/`. Unsupported historical/renewal mapping and reviewed
Tamil headings remain explicit follow-up work; saved evidence does not certify
complete historic or statutory compliance.

## Form E permanent batches and daily annotation workflow implemented locally (2026-09-30)

Added one immutable book per licence/series with either accepted A4 layout, explicit
opening date/page and earlier paper-book reference. Administrators review original
evidence, add source-backed missing particulars and retain unresolved gaps; no
frozen loan facts are overwritten. Unsupported origins/renewals and ambiguous payout
attempts remain blocked. Pending queues show the first 100 eligible unbatched loans
and total count. Shared measured pagination supports full groups or a closed partial
page; long entries continue without clipping.

Finalisation locks the book/selected loans, rejects stale confirmations, preserves
actor/time, scope, hashes, per-loan physical page ranges and exact private PDF bytes.
Repeated identical requests return the original batch; changed/reused selections
cannot duplicate pages. Facing sheets receive separate consecutive numbers; evidence
appendices are unnumbered. Exact downloads verify the hash and never regenerate
missing/corrupt files. Later entries use the next page without renumbering old ones.
Daily printable activity includes business/recorded dates, late-entry discovery,
collections, partial/full releases, available recipient details, reversals, renewal
warnings and saved page references for manual annotation. No printing/filing or
per-entry annotation completion is fabricated.

Migration `0030_pledge_book` adds four directly Workspace-owned forced-RLS tables,
SQL immutability/parent guards and consecutive page-allocation checks. The retained
batch FileField is covered by storage inventory (14 local fields; 13 in current
production). Existing administrator/export/write authority is reused. Updated the
in-Workspace statutory guide, [staff guide](flows/form-e-pledge-book.md),
[implementation](implementation/form-e-pledge-book.md), future-work record and
[ADR](adr/2026-09-30-form-e-preserved-print-batches.md).

Validation: **111 tests passed** across Form E, statutory notices, RLS registry,
storage inventory and reviewed cleanup, including duplicate/stale submissions,
full/partial/late numbering, exact downloads, failure rollback/file compensation,
source review, late activity, CSRF/authorization and restricted-role isolation.
Migration drift and system checks passed. Both numbered fictional A4 PDFs were
rendered and visually checked, including Tamil particulars and evidence appendices.
Evidence is under ignored `outputs/form-e-20260930/`. No production changes or real
books/batches were created. Next: physical acceptance and a controlled migration/
rollout with cleanup-operator rebase; choose each branch's opening scope explicitly.
Reviewed Tamil headings and unsupported historical/renewal mappings remain pending.

## Both Form E layouts selectable locally (2026-09-30)

Owner accepted both layouts. Added a Print layout selector for facing portrait A4
or single-sheet landscape A4, sharing the same report projection and permissions.
The PDF button submits the current filters and layout. Facing A4 stays the default
for old links. Both preserve all fields, allow long-entry continuation, and include
evidence notes in the selected orientation; no stored book or business data changes.
All 15 Form E tests passed, including paper dimensions, five/six-entry pagination,
long-entry tail preservation and route selection/validation. Fictional five-entry
samples in both layouts, including Tamil particulars, were rendered and visually
checked across all five output pages. This is local only, not deployed. Saved
batches, permanent numbering and physical print acceptance remain outstanding;
future retained batches must freeze their chosen layout and exact PDF.

## Single-sheet landscape Form E alternative sampled (2026-09-30)

Owner requested a simpler single A4 landscape sheet, one loan per row, preserving
the earlier fields and manual-update workflow. Created a fictional five-loan sample
at `output/pdf/form-e-a4-landscape-sample.pdf`, including Tamil particulars, mixed
item rates, quantities, gross/net weights, Indian amount grouping and later-event
handwriting space. All cells passed fit checks; the one-page A4 landscape PDF was
rendered and visually inspected. This is a layout alternative for review, not a
change to the application renderer, fixed page capacity or production deployment.
The earlier paired-A4 sample remains available for comparison.

## Form E working register and facing-A4 preview implemented locally (2026-09-30)

Added a read-only licence/series/date-scoped pledge-book projection and facing-A4
PDF preview. Admission requires actual payout/opening evidence; unpaid approvals
are excluded and closed operational histories remain available. Native original
amounts/articles come from frozen disbursal/approval evidence. First-ticket identity
is labelled by capture date; missing original address, owner, recipient address or
valuation stays explicit. Imported original principal is distinct from remaining
balance; a cutover valuation is not relabelled as original. Archived source claims
without licence/series mappings are counted as excluded, never silently omitted
under a complete-book claim. Payments, concessions, reversals and renewal caveats
retain their source distinctions.

The trial print format has up to five ordinary entries per Left/Right pair, aligned
long-entry continuations and an evidence appendix. It supports Tamil particulars,
Indian money grouping and dd/mm/yyyy dates. It does not allocate permanent pages,
store a print batch or establish physical filing. A 100-entry bound requests narrower
filters instead of truncating. No new table, migration or dependency was introduced.

Validation: 13 new projection/UI/PDF tests passed; the final combined Form E,
statutory notice and loan UI run passed all 99 tests. Migration drift and system
checks passed. The three-page fictional sample was rendered and visually checked,
including both facing sheets and the evidence appendix. Source/sample/test logs are
under ignored `outputs/form-e-20260930/`. Form E remains local, separate from the
deployed statutory notice release. Final production check confirms web running
with zero restarts; the storage timer executes the current web image and therefore
includes its new statutory reference fields.

Next: physical sample/capacity review, evidence-gap handling, retained full/partial
print batches with stable page references, and the daily annotation aid. See the
[field mapping and delivery notes](implementation/form-e-pledge-book.md).

## Statutory notice workflow deployed; Form E selected next (2026-09-30)

Owner accepted the catalogue for deployment with cosmetic refinements deferred,
confirmed no open auctions, and described auctioneer-prepared notices followed by
branch posting and a reconciled unreleased-loans handover. Updated the staff guide
to preserve this responsibility split and to distinguish the remaining consolidated
handover-list feature. Owner selected two facing A4 pages for Form E.

Restricted READ ONLY preflight confirmed zero initiated/in-progress auctions across
all six Workspaces. Private operational backup, the exact one-migration plan
(`loans.0029_statutory_notices`), migration and runtime grants/RLS checks passed.
Deployed `rokkad:statutory-notices-20260930-76e120aeb6a3`: 28 candidate and live
pages rendered; all 18 source hashes, migration state, HTTPS login boundary,
mail health and preserved feature flags/timers passed. No borrower notices sent
or business transactions created. Private release evidence remains at
`/home/rokkad/deploy/cutover-20260924/statutory-deploy-20260930/`.

Rebased the cleanup operator to `rokkad:storage-cleanup-20260930-b8fe1096e0f4`
with both statutory file references covered. Read-only candidate discovery passed;
no cleanup executed. Form E implementation is separate from this deployed release.

## Workspace statutory staff reference expanded (2026-09-30)

Expanded the existing statutory scope page into the full staff workflow reference:
preparation, manual printing/posting, acknowledgement or returned-cover handling,
readiness review, corrections, late dates and attachment requirements. Added a
Workspace settings link labelled Statutory workflow guide and a contextual link
from every statutory auction notice screen; the Reports entry remains. The page
keeps implemented versus planned forms explicit and does not change permissions
or auction rules. The repository operator guide documents all three entry points.

Validation: the existing administrator UI/private-download/access test passed,
rendering the updated guide and notice screens; Django system checks and diff
whitespace passed. Local changes only; deployment remains pending with the
statutory workflow's template review, existing-auction inspection and migration.

## Razorpay mail checked and callback questions prepared (2026-09-30)

Read the scoped admin@rokkad.com Razorpay mail search. Latest message: 29 September
22:17 IST, ticket 21174094; no 30 September message in the results. Email confirms
the owner-supplied fee components, requests callback availability within three
days, and says technical cases 21146138/21146171 remain under investigation without
a technical answer. Added the [call brief](plans/monthly-billing-pilot.md#mail-verification-and-callback-brief-2026-09-30),
including itemized settlement questions, failed-renewal/recovery evidence and
confirmation that the quote addressed to "Hanumanram" belongs to Rokkad's account.
Clarified that 28 October is an existing test-period dependency, not a Razorpay
waiting rule; JSK's 8 October expiry does not authorize launch. Read-only browser
and official documentation review only: no message, callback commitment, API
mutation, trial change or billing activation. No fresh provider API verification.

## Statutory auction postal workflow implemented locally (2026-09-30)

Owner selected FW-013's statutory suite, prioritising complete manual auction
notice handling independently of borrower email/WhatsApp reminders. Added reviewed
catalogue preview/preservation, printing, article/date/receipt capture, acknowledgement/
POD and returned-cover referral/officer-receipt/certificate routes, administrator
readiness review and withdrawal. Late facts are retained but cannot clear missed
deadlines. Start and completion now require the statutory evidence rather than
a Notify SENT job; existing open auctions receive no implicit exemption.

The Workspace Reports guide shows scenario/form coverage and the remaining
generators. Loan auction actions link to Statutory notice & readiness. English
catalogue headings, shaped Tamil particulars, exact reprints, actual event dates,
recorder attribution and private hash-checked downloads are implemented. Both new
tables have forced RLS, scope guards and append-only SQL protection; both new file
references are included in storage inventory/retention. Auction commands also
enforce the existing business-write access policy.

Validation: 211 focused notice, loan service/UI, setup, document, registry and
storage tests passed. The final 16-test statutory run also passed, including the
exact-45-day boundary. Fictional single-page and three-page PDFs were rendered
and visually checked, including Tamil text; samples and test logs are under ignored
`outputs/statutory-notices-20260930/`. Migration drift and documentation whitespace/
links are checked. No production database, deployment or recipient contact occurred.

This is the first local increment, not completion of every prescribed form or legal
certification. Reviewed Tamil statutory wording, multi-pledge catalogue support,
remaining forms and current-rule/physical-paper acceptance remain explicit in the
[delivery plan](plans/statutory-forms-and-notices.md). Deployment needs the owner-role
migration, runtime grants, refreshed storage tooling and review of existing open
auctions. See the [operator guide](flows/statutory-auction-notices.md) and
[decision](adr/2026-09-30-statutory-auction-service-evidence.md).

## Statutory postal notices compared with existing implementation (2026-09-30)

Reviewed the official Rules and current Loans/Notify source in response to the
owner's reminder-notice question. Added the gap analysis to
[FW-013](plans/future-work.md#statutory-notices-and-postal-service-evidence).
Existing loan notices, a generic auction PDF and batch Printed/Posted markers are
useful foundations, but do not implement prescribed postal service. Auction start
currently relies on a SENT digital job, without the statutory notice interval,
acknowledgement/returned-service procedure or authority/publication evidence.
Borrower delivery is distinct from the platform SES queue; provider availability
must not be inferred from channel choices. Current-law/service review remains
required before compliance claims. Repository/source review only: no production
inspection, notices sent or application changes; documentation whitespace checked.

## Form E page capacity and printing readiness planned (2026-09-30)

Expanded [FW-013](plans/future-work.md#form-e-daily-maintenance-and-printing-by-licenceseries)
with a sample-tested default capacity per print layout, a licence/series pending
queue and full/partial-page printing. Full-page readiness is a convenience cue;
partial pages remain printable for daily upkeep. Finalised page contents/numbers
stay fixed, with exact reprints and late entries on subsequent pages. Actual layout
fit must accommodate long content and handwriting. No entry count is fixed yet;
20 is illustrative. Planning only; documentation whitespace validation passed.

## Form E first version simplified to print and manually annotate (2026-09-30)

Owner prefers handwritten payment/release updates to already printed pledge-book
entries. Updated [FW-013](plans/future-work.md#form-e-daily-maintenance-and-printing-by-licenceseries)
to print new entries with room for annotations and offer a simple daily activity
list covering older loans, partial payments and late-recorded events. Normal app
recording still maintains the digital register. Routine replacement pages and an
annotation-acknowledgement workflow are outside the first version. Original PDFs
remain exact print snapshots and cannot reproduce later handwritten notes. This
supersedes the earlier proposed automatic revised-page workflow; planning only,
with no application or production changes. Documentation whitespace check passed.

## Form E daily pledge-book workflow captured in FW-013 (2026-09-30)

Expanded [FW-013](plans/future-work.md#form-e-daily-maintenance-and-printing-by-licenceseries)
at owner request with a continuously maintained register, separate licence/series
views, ledger-style PDF output and daily printing. The plan explicitly handles
payments/releases against already printed entries through an update worklist,
stable references and preserved/revised print artifacts. It includes historical
coverage gaps, actual versus recorded dates, bilingual print acceptance and a
staged delivery proposal. The supplied ledger photo is a format reference only;
its customer data was not copied into the repository.

Reviewed the official Rules text for Rule 7, Form E and the language provision.
Current amendments and acceptance of electronic/loose-leaf replacement procedures
remain review items, not established compliance claims. This is unscheduled future
work: no application, lending, database or production changes were made. Validation
for this increment is documentation/link and whitespace review only.

## Storage media categories corrected and refreshed (2026-09-30)

Owner approved correcting JCL's misleading Collateral photos count. Classification
now ignores the historical-evidence label only when choosing a display category;
all references remain intact for ownership, sharing and cleanup protection.
Files with one current media type retain it; history-only files remain Historical
evidence and multiple current types remain Multiple uses. The Workspace table
explains this distinction. No schema, file or lending-record changes.

All 52 storage inventory/cleanup/retention and architecture tests passed. Deployed
`rokkad:storage-category-20260930-625feb7250e4` after the private operational backup
and candidate checks. Candidate/live checks rendered 22 pages; both runtime source
hashes, restricted role, migration plan, mail health, existing flags/timers and
HTTPS login boundary passed. Private release/rollback evidence is under
`.../cutover-20260924/storage-category-20260930/` on the new server.

Refreshed inventory **4**, completed **30 September, 10:06 IST**. JCL now shows
**2,303 Collateral photos / 16,951,125 bytes**, comprising 2,245 imported photos
and 58 recent non-import photos, with zero missing references. All 58 recent files
passed live existence checks. Workspace total is 11,820 objects / 74,747,984 bytes;
new business uploads since the earlier diagnostic explain growth in those totals.
All six Workspace category sums equal their assigned object/byte totals.
An actual rendered JCL page shows 2,303 in the correct row. A further photo arrived
after the scan (2,304 current keys); all pre-scan photo keys are covered. The dated
measurement updates on subsequent reconciliation, not each upload/page request.

Rebased the unchanged cleanup operator files onto this release as
`rokkad:storage-cleanup-20260930-5023e640932a`; its read-only candidate check passes
against inventory 4 with no candidates. No cleanup executed. The operator's initial
concurrent check correctly refused the running inventory lock and passed afterwards.

## JCL collateral storage category discrepancy verified (2026-09-30)

Owner reported only two collateral-photo objects in Workspace storage despite
recent uploads. Restricted READ ONLY inspection confirmed **55 non-import photos
since 24 September across 54 loans**; all 55 objects exist in production storage.
Inventory 3 (30 September, 03:19 IST) includes all 2,300 current JCL collateral
photo keys: two classified `collateral_photos`, 2,298 `multiple_uses`. Of the recent
55, 53 also have historical-evidence references and consequently appear under
Multiple uses. The other 2,245 photo rows are legacy imports.

The current disjoint category rule moves a photo into Multiple uses whenever ticket
or import evidence also references it. This is misleading as a photo count; it is
not a missing-upload finding. JCL's snapshot includes 11,811 assigned objects /
73,088,696 bytes, with zero missing references. No database or object changes were
made during diagnosis. Recommended correction: preserve the current media type
when its only additional use is historical evidence, retaining every protection
reference and counting physical bytes once. Classification/UI correction remains
pending; all-photo existence beyond the 55 recent objects was checked against the
inventory rather than individual live HEAD requests.

## FW-015 reviewed offline cleanup available to operators (2026-09-30)

Owner requested completion of the remaining cleanup workflow and explicit deferral
of storage pricing, quotas and billing; those commercial items are now separately
called out in FW-015. Added `cleanup_storage` with candidates/plan/private inspection,
verified recovery preparation, exact-digest execution and restoration. No schema,
web endpoint, automatic purge, expiry, quota or charging changes.

The command uses existing platform authority and the restricted role, checks all
registered current/historical/global references, and bounds review to 50 old
unreferenced objects / 64 MiB total / 20 MiB each. Execute/restore requires an exact
stopped-writers acknowledgement plus NOWAIT reference-table locks and the inventory
advisory lock. Atomic signed filesystem checkpoints persist per-object intent and
outcome across SQL rollback or uncertain provider responses. Changed/referenced
objects, missing/corrupt recovery and occupied restore keys stop the operation.
Restoration permanently disables deletion replay for that plan.

Thirty new cleanup tests, nineteen storage/retention regressions and one architecture
check pass (50 total). A restricted second PostgreSQL connection demonstrated
reference-write lock exclusion. Real R2 acceptance used two isolated synthetic
objects: conditional GET, create-only PUT, hash readback, exact deletion and byte/
metadata restoration passed; both test objects were removed. No customer objects
or business records changed. Initial read-only production candidate query: none
in inventory 3.

Operator image `rokkad:storage-cleanup-20260930-55a3f2ce5a92` and private launcher/
evidence are under `.../cutover-20260924/storage-cleanup-20260930/` on the new server.
Production web remains `rokkad:media-retention-20260930-b65c552f57c4`. No restart or
migration. The launcher refuses a changed base release until its operator image
is reviewed/rebuilt. Online writers, automatic expiry and a web cleanup queue remain
outside this offline workflow. See [runbook](implementation/reviewed-media-cleanup.md)
and [decision](adr/2026-09-30-reviewed-offline-media-cleanup.md).

## Both historical rehearsal environments retired (2026-09-30)

Owner approved proceeding after verified recovery preparation. Retain the five
private recovery archives with **no automatic expiry**. The baseline 8081 server
was found running and stopped; unrelated billing rehearsal 8083 remains. Disabled
restart for the two stopped hosted runtimes. Both source databases were frozen and
all **321 table fingerprints** matched the archived snapshots before deletion.
Fresh full R2 SHA256 readback passed for all five archives; exact rehearsal object
listings were unchanged and production had no references into either retired scope.

Removed both historical rehearsal databases and the two stopped hosted runtimes;
shared PostgreSQL/proxy/network/volumes remain. Audited exact-key batches removed
**58,899 objects / 1,665,493,265 bytes**; both rehearsal prefixes are empty.
Recovery archives remain **2,299,177,212 bytes** in R2, plus verified server packages.
This reclaims the loose copies, not all storage associated with recovery.

Final production reference check: **29,770 objects / 880,056,600 bytes**, all
references present; unchanged from pre-retirement. Production image, HTTPS login
boundary and mail/storage timers pass; old legacy server untouched. Temporary
transfer helpers were removed. Completion around **01:25 IST**; no code deployment.
Exact scopes, private evidence and recovery limits are in the
[retirement record](implementation/rehearsal-retirement-20260930.md).
General production orphan cleanup, quarantine and storage billing remain separate.

## Both rehearsal recovery packages verified on-server and in R2 (2026-09-30)

Owner approved private recovery preparation, isolated restore tests and a private
R2 archive; separately confirmed sensitive server-side staging after automatic
review required that explicit destination approval. No source retirement approved.

Captured the local baseline through a shared PostgreSQL snapshot and streamed its
dump directly to the new server without a dump in OneDrive. Hosted backup's before/
after table fingerprints match. Isolated restores verified every public table:
baseline **160 tables / 295,602 rows**, hosted **161 / 275,390**. Matching historical
images booted with zero pending migrations, restricted read-only roles and no
network; unscoped Party/Loans reads returned no rows.

Copied, archived, reconstructed and SHA256-verified **58,899 media objects /
1,665,493,265 bytes**. Original before/after R2 listings match. Recovered applications
resolved all **29,379 baseline / 29,514 hosted** current/historical media references.
Environment archives also retain database dumps and private recovery configuration;
shared artifacts retain both historical application images, PostgreSQL, baseline
source, manifests and the recovery recipe. All **five R2 objects / 2,299,177,212 bytes**
passed full streamed SHA256 readback under
`rokkad-production-media/recovery/rehearsal-retirement/20260930/22c54576e1d9d1ad/`.

Removed only this turn's temporary capture/upload/restore containers, disposable
restored copies and temporary transfer settings. All original rehearsal databases/
media and server-side verified packages remain. Production image/HTTPS and existing
mail/storage timers passed final checks; no old-server change. Private evidence is
under `/home/rokkad/deploy/cutover-20260924/rehearsal-recovery-20260930/`.

Limits: these are data/media and read-only app recovery checks, not live OAuth,
business-write, mail/payment or all-UI acceptance. The Windows baseline's
English_India.1252 collation differs from the Linux drill's default locale; data and
constraints match, while exact locale sorting requires separate review. R2 is
independent of the Linode but remains the same account/bucket, with no immutability
or automatic expiry claim. Actual retirement needs a fresh source-change/writer
check and explicit scope/retention approval. See
[recovery evidence](implementation/rehearsal-recovery-20260930.md) and
[retirement plan](plans/recoverable-media-cleanup.md).

## FW-015 committed-media retention correction deployed (2026-09-30)

The owner requested the next cleanup increment and guidance on retiring 1.67 GB of
rehearsal media. Removal-path review found that django-cleanup could delete Party
default/gallery files after commit despite the gallery's retention contract, and
Party documents despite retained admission receipts. Draft collateral deletion
checked only current same-Workspace photo rows before physically deleting bytes.

Party, PartyPhoto and PartyDocument now explicitly opt out of automatic cleanup.
Draft collateral photo/item removal retains bytes for reference-aware operator
review while preserving attachment removal, draft/renewal guards, locking, permission
checks and audit. Single-photo removal records `file_retained_for_review`. Failed
command compensation of newly uploaded files remains unchanged. This prevents
future deletion through the corrected paths; it does not recover previously deleted
files. No physical purge, quarantine, new schema or billing was introduced.

Validation: **165 tests passed** across commit-callback retention, Party UI,
collateral operations, draft uploads and storage inventory, plus four import-boundary
tests. A six-file overlay excludes unrelated Party UI changes. Deployed
`rokkad:media-retention-20260930-b65c552f57c4` after the established server-only backup.
Candidate/live checks each rendered 22 pages under restricted READ ONLY access,
confirmed no pending migrations and disabled cleanup registration for the three
Party models. All six deployed hashes, existing mail configuration/health, runtime
flags and the storage timer passed. Previous image remains
`rokkad:storage-inventory-20260930-2b332cc6b6bc`; private release/backup/rollback evidence
is under `/home/rokkad/deploy/cutover-20260924/media-retention-20260930/`.
Code/docs remain uncommitted locally.

The [recovery plan](plans/recoverable-media-cleanup.md) records existing removal
paths, the proposed two-diagnostic-object pilot and separate rehearsal retirement.
Keep both rehearsal environments until complete database/media/configuration
packages have been verified and restored in isolation, with independent recovery
and an approved retention period. Those rehearsal packages have **not** been prepared
or restore-tested by this increment. Moving files to another R2 prefix does not
reduce total bucket bytes. No existing media was deleted and the old server was
unchanged. See the [decision](adr/2026-09-30-retain-detached-party-and-collateral-media.md)
and [usage guide](flows/storage-usage.md).

## FW-015 legacy and rehearsal storage review (2026-09-30)

Completed a read-only metadata review of the existing production-media bucket:
121,378 objects / 3,237,145,152 bytes across production, two rehearsal prefixes,
preserved originals and migration reports. Production still has no missing or
unreferenced objects in the checked snapshot. Rehearsal databases account for all
but six objects / 2,651,905 bytes: two synthetic upload diagnostics and four
template PDFs whose creation history/retention need review. No missing application
references were found in either rehearsal scope.

All 32,697 preserved-original/report keys and sizes match the copy plan plus
immutable admission evidence; all 12 separate attachment reports also match their
receipts. This is metadata reconciliation, not fresh content-hash verification.
Preserved unresolved originals are evidence, not orphans. No objects were deleted,
no app/legacy-server changes were made, and private raw evidence stays on the server.
The two rehearsal scopes occupy 1.67 GB but remain referenced: environment retirement
requires its own retention/recovery decision. See the
[scope review](implementation/storage-scope-review-20260930.md) for exact scopes,
coverage, limits and the proposed recoverable-cleanup increment.

## FW-015 inventory and usage deployed (2026-09-30)

Owner selected storage inventory, Workspace usage and read-only cleanup previews.
Implemented a metadata-only R2 listing restricted to the configured application
prefix, explicit coverage of all 11 FileFields plus ticket snapshots and admission
receipts, two reference passes and atomic publication. A forced-RLS Workspace
summary and global physical-object metadata separate exclusive, shared, platform,
missing and unreferenced objects. Unknown ownership stays unassigned. No file
contents, deletion, quarantine, quota enforcement or billing are part of this work.

Platform console > Storage provides counts/bytes and paginated review fingerprints;
workspace settings and the platform workspace detail provide scoped usage/category
summaries. Completed run time and stale/failure states prevent partial scans from
looking current. Dated aggregate snapshots are retained. The first release adds
orgs.0010_storage_inventory through owner-only migration settings; web/job remain
restricted runtime. See [rollout](plans/storage-inventory-rollout.md) and
[guide](flows/storage-usage.md).

Validation: 37 focused tests passed, covering metadata-only prefix scope, registry
coverage, RLS DML/read denial, database-superuser rejection, workspace/admin action
boundaries, shared-byte accounting, archived and retained evidence, references
arriving during listing, duplicate/partial listing failure and audit rollback.
Fictional desktop/390px browser review passed with no document overflow.
Deployed `rokkad:storage-inventory-20260930-2b332cc6b6bc` after a server-only
backup and the single owner-only additive migration. Candidate/live checks rendered
22 pages, confirmed restricted runtime/RLS, denied ordinary platform access and
verified all 16 source hashes. Existing mail health/timers, worker configuration,
public trials and account/invitation mail are preserved; checkout/recurring stay off.
Preparation caught and corrected review-script permissions/PYTHONPATH before the
migration ran. No borrower/loan records or R2 objects were mutated.

First production scan: **29,770 objects / 880,056,600 bytes** in
`rokkad-production-media/media/application/production/linode-rls/`, all assigned to
one Workspace. JCL: 11,811 objects / 73,088,696 bytes; JSK: 5,043 / 348,221,910;
Lakshmi: 12,916 / 458,745,994. The three test Workspaces have zero measured objects.
No missing references, shared objects or unreferenced objects were found **within
this prefix**. This does not certify original migration/rehearsal/backup prefixes
or byte-level image integrity. Dated historical references intentionally retain
files even when their current UI attachment was replaced.

Daily timer `rokkad-storage-inventory.timer` is enabled/active, scheduled around
03:15 IST plus up to five minutes jitter. Its service acceptance produced a second
completed scan with identical counts/bytes and passed the aggregate/RLS check. The
next run was verified for 30 September 03:19:17 IST. Private source/migration/backup/scan/
rollback evidence remains on the server under
`/home/rokkad/deploy/cutover-20260924/storage-inventory-20260930/`.
The release excludes unrelated Party edits. Code/docs remain uncommitted locally.

## FW-010 guided suspension/restoration (2026-09-29)

Implemented the owner-approved lifecycle increment: workspace detail offers review
screens for ACTIVE -> SUSPENDED and SUSPENDED -> ACTIVE. Each shows the workspace,
owner and signed-in actor; requires reason, typed slug and acknowledgement; and
explains the access impact. Restoration previews canonical subscription access and
never creates commercial access, extends a trial or changes subscription dates.
Lifecycle history shows the latest ten actor/time/from/to/reason records separately
from subscription access decisions. The in-app guide and repository guide cover use.

The service uses global active-superuser authorization, CSRF-protected POSTs,
15-minute signed reviews, a Workspace row lock and the existing atomic lifecycle
transition/audit service. Changed/replayed confirmations fail closed. Audit failure
rolls back the state. No schema, RLS, ownership, business-record or billing changes.

Validation: 37 focused console/new lifecycle/existing lifecycle tests passed,
including restricted-role boundaries, CSRF, state replay, token tampering/expiry,
wrong actor/target, changed projected access, atomic audit failure and unchanged
subscription data. Fictional desktop and 390px mobile review passed with no
horizontal document overflow. Candidate rendered 15 production pages within a
restricted READ ONLY transaction and denied ordinary users. Server-only operational
backup completed; private release evidence is under
`/home/rokkad/deploy/cutover-20260924/platform-lifecycle-20260929/`.

Deployed `rokkad:platform-lifecycle-20260929-d1caed09cb6d`. All 15 live render/
authorization checks and seven exact source hashes passed; anonymous HTTPS requires
sign-in. Mail health passed, all four mail timers remain active, and worker/config
hashes are preserved. Account/invitation mail and public trials remain enabled;
paid checkout/recurring remain disabled. No real workspace was suspended or restored
for verification. The unrelated Party changes remain outside this seven-file release.
Code/docs remain uncommitted in the working tree.

## FW-010 first platform console deployed (2026-09-29)

Delivered the owner-selected read-only console at `/app/platform/`: overview and
review signals, searchable/filterable Workspace directory, detail tabs for current
access/owner/team/invitations/access history, existing management links and an
in-app operator guide. Navigation appears for active superusers in the main header,
Workspace-manager sidebar and Django-admin header. Permanent platform identity
remains `admin@rokkad.com`; no permissions or accounts were changed.

Directory pages are bounded at 25 and invitation pages at ten. Effective access
uses canonical policy; active lifecycle is not labelled paid access. Invitation
delivery, acceptance and current membership stay distinct. Empty filters/results,
inactive Workspace links and secret exclusion are covered. Suspended/deletion-pending
metadata is available, but no new restoration or impersonation workflow is added.
Archived recovery uses a canonical alias to the existing restore list.

Sixteen focused console/onboarding/canonical-route tests passed, including restricted
role, global-context and GET-only/no-store boundaries, SELECT-only selectors,
grace/expiry/extension semantics and bounded pagination. Fictional desktop and 390px
browser checks passed for search, tabs and document overflow. The first candidate
caught a new-template-directory permission error; packaging was corrected before
deployment, preserving the image's non-root runtime user.

Web image `rokkad:platform-console-20260929-980dd0c5cfe5` overlays eleven reviewed
files on `rokkad:trial-landing-20260929-044f48f88473`. Candidate and deployed checks
rendered nine pages in restricted READ ONLY transactions and denied an ordinary
user. All eleven live source hashes match. Anonymous HTTPS requires login; the
existing non-platform browser session receives 403 as intended. Trial/account/mail
flags remain enabled, checkout/recurring disabled, worker/settings/env hashes
unchanged, all four mail timers active and mail health passed. No migration or
business-data mutation was part of this release.

Backup, candidate logs, manifest, prior compose/release metadata and `deployed.json`
remain private under server `platform-console-20260929/`. Rollback restores the
saved compose and release metadata and recreates web only; no database restore or
worker change is required. [Operator guide](flows/platform-console.md) describes
scope and remaining work. This completes the focused first increment, not the full
FW-010 discovery/delegation backlog. Repository changes remain uncommitted.

## FW-019 WhatsApp fee reply recorded; method totals still need clarification (2026-09-29)

The owner supplied a WhatsApp response citing 21174094. It quotes a 0.9%
subscription add-on plus 2% payment-method fee, 18% GST on fees, INR 7 one-time
UPI mandate setup, INR 22 eMandate setup and INR 20 automatic payments. The
INR 5 lakh credit covers eligible payment-method charges only; subscription
fees remain payable. No independent Dashboard/sender verification is claimed.

For the quoted percentage-only scenario, INR 1,499 x 2.9% x 1.18 gives about
INR 51.30 fees / INR 1,447.70 remaining, before setup or other deductions.
The promotional INR 15.92 estimate assumes only the 0.9% add-on plus its GST
remains; tax waiver treatment is not established. The PDF's INR 17 UPI recurring
fee and method-specific stacking still need itemized examples. Decimal arithmetic
was checked; no code/runtime or customer pricing changed. A written clarification
is prepared but not sent, and no callback/alternate number was supplied.
See [fee interpretation](plans/monthly-billing-pilot.md#owner-supplied-whatsapp-pricing-reply-2026-09-29).

## FW-019 public landing, pricing and FAQ aligned with live trial (2026-09-29)

Published at **20:58 IST** after desktop and 390px mobile review. The homepage
retains the pawn-lending story and now offers a 30-day trial: owner plus five staff,
no card, no automatic charge and one trial Workspace per owner account. Pricing
replaces the obsolete Starter/Operations/Scale tiers with the available free trial
and a clearly unavailable planned INR 1,499/month continuation. FAQ covers account
verification, explicit trial start, invitations/reserved seats, expiry and refunds;
retired ERP/inventory/accounting claims were removed from those pages. Anonymous
navigation and the shared footer expose pricing/FAQ, with refund-policy access.

Twelve existing page/route checks passed. Restricted READ ONLY candidate and live
render checks passed for all three pages, with live HTTPS/signup and five source
hashes verified. All three mobile pages had no horizontal overflow; the collapsed
navigation opened correctly. No new account, invitation, message or charge was
created. The paid-billing switches remain false and public trials/mail remain true.

Web now uses `rokkad:trial-landing-20260929-044f48f88473`, a five-template overlay on
the exact previous image. Mail workers, timers, signing/settings, secret files,
static volume and watchdog configuration were preserved. The last observed natural
heartbeat at 20:57:01 IST was sent with no health flags. Production backup and
rollback evidence are private under `trial-landing-20260929/`. The prior recurring
cancellation-template clarification is still pending its separate billing release.
See [release details](implementation/public-trial-release-20260929.md#public-pages-release-2026-09-29).

## FW-019 cancellation wording reviewed and onboarding health refreshed (2026-09-29)

At **20:48 IST**, a restricted READ ONLY production check still shows one observed
new owner account: verified email, accepted public trial with full access, two
members and one accepted invitation delivered on its first attempt. Whether this
is a genuine customer and teammate browser activity remain unverified. Queue due is zero,
health flags are empty, and all four mail timers are enabled/active. The natural
scheduled health run at **20:46:49 IST** sent the external heartbeat successfully.
Free trials and account/invitation mail remain enabled; paid billing stays disabled.

Dashboard review finds pricing **21174094 Active** with no reply yet and target
1 October 13:43; technical **21146138 In Progress** still ends with the prior
owner-approved follow-up, and **21146171 Closed** has no technical answer. No new
message, transaction or simulation was submitted. The previous provider payment
observations remain the latest; this check did not repeat those API calls.

Cancellation/refund wording was compared with the existing service, owner-approved
policy and provider cancellation reference. The local recurring page now explains
before confirmation that Razorpay must confirm cancellation and a payment already
in progress may still settle; it links the existing refund policy. Paid-time,
refund, authorization and cancellation behavior are unchanged. Two existing focused
owner-page/CSRF and completed-agreement tests passed. This template clarification
is prepared for the next billing release, **not deployed**. See the
[wording review](plans/monthly-billing-pilot.md#cancellation-wording-review-2026-09-29).

## FW-019 Razorpay pricing reply and attachment reviewed; recurring fee gaps remain (2026-09-29)

The owner-requested review read the **19:55 IST** email for ticket **21170392**.
Support confirms 90-day amount-credit eligibility for UPI, credit cards on UPI,
domestic debit cards, domestic Visa/Mastercard/RuPay credit cards, netbanking,
wallets, BNPL and cardless EMI. It excludes AMEX, Diners, card EMI, prepaid,
corporate/business and other international cards. Support says the pricing ticket
will be resolved and that technical tickets 21146138/21146171 remain under
investigation; this is not technical acceptance or a fresh payment result.

The owner saved the pricing PDF after Chrome's attachment automation was blocked.
Its complete single-page table was extracted and visually reviewed. For the band
covering INR 1,499 it lists initial UPI INR 7 and auto UPI INR 17; generic UPI is
separately 2%. Card appears at both 2% and 0.90%, with no condition explaining the
duplicate rates. NACH initial/auto is INR 30/10, Aadhaar eMandate INR 30/5 and
eMandate INR 22/20. There is no explicitly labelled subscription add-on, GST note
or definition of initial versus automatic charges. These are listed fee components,
not confirmed all-in recurring costs. The owner-approved clarification was submitted
through Dashboard as ticket **21174094**, referencing resolved 21170392, which has
no reply box. Its email Reply-To matches the previously unmonitored address, so no
email was sent. Confirmation gives a 4-8 business-hour status-update expectation; the refreshed
Dashboard shows Active with a target of **1 October, 13:43**.
The existing approved phone was retained; no new contact or callback commitment
was supplied. Local proof: `outputs/razorpay-pricing-followup-created-20260929.png`.

Fresh provider GETs at **20:36:48 IST** still show annual Active, paid_count 1/2,
last payment Created/invoice Issued; the attempted failure remains Captured/Paid,
with its cleaned-up agreement Cancelled, paid_count 2/3. The short scheduled
fixture remains Expired, paid_count 0, authorization Created. Local billing/mail
record counts are unchanged. No charge, retry or provider mutation was made.
See [reply review and next work](plans/monthly-billing-pilot.md#pricing-support-reply-2026-09-29-1955-ist).

## FW-019 external mail alerts activated and delivery verified (2026-09-29)

Better Stack heartbeat 499750 is connected to the production mail-health watchdog.
The owner approved temporary read-only access to the single staged URL file,
encrypted SSH transfer, one missed-heartbeat/recovery test and reading only those
test emails. The URL is now in root-only server configuration (0600); the local
secret file and its temporary access were removed by deleting that file.

The controlled one-minute interval plus one-minute grace test opened incident
1024376789 at **20:14 IST**. Its failure email arrived in admin@rokkad.com. Resuming
healthy pings at **20:16 IST** automatically resolved the incident and delivered
the recovery email to the same inbox. Both received messages were inspected.
The normal name, five-minute interval, five-minute grace and email-only routing
are restored. Mail workers stayed enabled throughout; no customer email was
created by this rehearsal. Configuration/image preservation checks passed.

The next natural scheduled heartbeat passed at **20:21:21 IST**. Current health
has no flags, queue due is zero and all four mail timers remain enabled/active.
No paid monitoring upgrade was added. See the
[acceptance and response runbook](implementation/onboarding-monitoring.md#external-alerts-active-2026-09-29).
Paid subscription launch still needs its separate Razorpay acceptance gates.

## FW-019 external monitor created; activation approval pending (2026-09-29)

The owner completed Better Stack sign-in for admin@rokkad.com. Its separate Rokkad
team has one member and remains on the Free plan. The existing rokkad.com website
monitor is Up. Heartbeat 499750, **Rokkad platform mail health**, was created with
five-minute checks plus five-minute grace and email-only alerts. No upgrade,
payment method, extra team member or test alert was added.

The dashboard now supplies an incidents.betterstack.com heartbeat URL. Local
watchdog code accepts that exact HTTPS host alongside the documented uptime host;
redirect refusal, fixed path and secret-redaction remain enforced. Four focused
watchdog tests passed. Scheduled production heartbeat publication remains disabled.

The secret is staged privately. Automatic approval review rejected granting the
normal Windows task operator full control over the staging directory; the pending
request is limited to temporary read-only access to its single URL file, encrypted
SSH transfer and local deletion. Separate requests cover one missed-heartbeat/
recovery email test and reading only those test messages in the admin inbox.
No mailbox access or alternative transfer bypass was attempted after rejection.
See [monitor setup and acceptance](implementation/onboarding-monitoring.md#rokkad-heartbeat-created-acceptance-pending-2026-09-29).

## FW-019 first observed signup/trial/team join passed (2026-09-29)

At **19:38 IST**, the newly observed Workspace has a verified owner and an accepted
30-day public trial through 29 October 19:34 IST, a six-member entitlement and
`auto_renew=False`. Its team invitation was delivered on the first attempt at
19:37:23 IST and accepted at 19:37:28. Two Memberships now exist: Owner and the
invited Admin, matching the invitation role. The verification email was also
delivered on its first attempt. Queue due is zero with no health flags.

These are read-only production observations of activity initiated outside this
agent's work. They prove recorded signup, verification, trial and team acceptance;
they do not establish that this is a real customer rather than an owner-run test,
or prove the teammate's subsequent browser work and role-specific operations.
No account, invitation, resend or charge was created by the monitoring commands.
The [report and runbook](implementation/onboarding-monitoring.md) capture the
remaining checks. External alert routing is still unconfigured; paid launch gates
remain as recorded below.

## FW-019 onboarding report deployed; external alert route pending (2026-09-29)

The read-only platform report is live, available from Django administration /
Onboarding Progress / Onboarding report to the permanent platform administrator.
It shows signup and verification, saved onboarding milestones, owned Workspaces,
public-trial acceptance and effective access, invitation/mail outcomes and current
membership. GET-only access, a shared active-superuser/global-context guard and
bounded pagination keep it separate from customer Workspace permissions. It reads
existing records and exposes no invitation tokens or borrower data.

At **19:33 IST**, deployed source hashes, PostgreSQL READ ONLY report/template
acceptance, restricted runtime and the next scheduled mail run passed. Web and mail
consumers use `rokkad:onboarding-monitor-20260929-df4b82f62000`, image
`sha256:71d5844da938e29aa9efd603696c47bb0383522cdc7d8e00daa3915234f6a6d2`.
The five-file overlay and optional host watchdog hook required no migration/static
rebuild. Release checks preserved existing access and billing/mail records; the
public 30-day trial and account/invitation sending remain enabled, while checkout,
recurring and scheduled receipt sending remain disabled. Eight focused tests passed.

There were no new accounts at preparation. A signup appeared naturally during
post-release verification, then created a Workspace. At **19:35 IST**, its verification email was delivered
on the first attempt, email verification was complete, and explicit public-trial
acceptance granted full access for 30 days through 29 October. There were no team
invitations yet. This is observed activity, not an agent-created fixture or proof
of a completed real-customer team journey. Customer identity stays out of this
repository. See the latest checkpoint in the monitoring runbook.

The owner chose **admin@rokkad.com** for failure alerts. The watchdog's tested
optional Better Stack heartbeat sends no customer payload, withholds success when
unhealthy/paused and refuses redirects. It is **disabled**: the external account,
recipient, actual free allowance and a bounded failure/recovery delivery test remain
to be resolved. Existing local health is clear; no external alert was sent and no
monitoring upgrade or access change was made.

Razorpay review at **19:25 IST** still shows annual renewal Created/Issued unpaid
and the failure simulation Captured/Paid. Annual ticket **21146138 In Progress**
has no newer substantive answer after the authorized follow-up; failure **21146171
Closed** has no technical response. Pricing **21170392 Active**, with no fee answer
and response target 1 October 11:14 AM. There are zero live agreements and the
private monthly binding remains present. Do not convert a resolved/closed ticket
into payment acceptance or enable charging. The 28 October held-period check,
failure/recovery, fee confirmation and bounded live pilot remain outstanding.

See [monitoring and rollback](implementation/onboarding-monitoring.md) and the
[monthly pilot](plans/monthly-billing-pilot.md). Next observe the new account's
remaining steps and finish the independent external alert route.

## FW-019 public 30-day trial deployed and enabled (2026-09-29)

Verified at **19:07 IST**: the approved free offer is live, using production Plan 3
and `BILLING_ALLOW_TRIAL_START=True` in web and worker. Terms are 30 days, owner
plus five staff, one trial Workspace per owner account, no card and no automatic
charge. Verified-owner consent is required. Checkout and recurring remain false;
private Plan 2 and annual billing are not published. Existing Workspace access,
trial dates and all observed billing/mail/Company/Membership records are unchanged.

Web and all mail consumers use `rokkad:public-trial-20260929-e06bb85c285c`, image
`sha256:bdc850b3f6fcac64ec39216d09b2b7ce2e694e3f4d05a9fe7c38634caa370afe`.
The 13-file overlay contains reviewed trial selection, consent, owner allowance,
seat serialization and corrected account-page copy. Existing UI outside those
files, static assets, credentials and 117 forced-RLS tables are preserved. No
migration was required. A fresh operational backup and deployed source hashes passed.

Restricted-runtime acceptance used fictional non-admin records in a transaction
that was fully rolled back. It passed verified-owner enforcement, private/stale
terms rejection, 30 days, six seats, repeat/second-Workspace refusal, customer copy,
grace/read-only and no financial/mail side effects. No persistent account, trial,
invitation or email was created. This complements the earlier local browser and
real account/invitation delivery acceptance; it is not a new live signup/email test.

The first enable attempt rolled back because inherited production settings force
the trial flag false. The shared deployment settings now explicitly read the
reviewed environment flag, defaulting false. Candidate web/worker checks passed
before retry. HTTPS login/signup, supervised mail workers, the subsequent scheduled
run and health all passed; queue due is zero with no monitoring flags. Invitation
and account mail remain enabled in batches of ten; receipts remain excluded.

See the [release/rollback record](implementation/public-trial-release-20260929.md).
Next monitor the first genuine owner signup/trial/team journey and continue the
separate Razorpay monthly pilot gates. FW-019 remains in launch validation for
paid subscriptions; no collection or paid conversion is enabled by this release.

## FW-019 ongoing account mail enabled and owner trial allowance implemented (2026-09-29)

At **18:49 IST**, production web and worker now both have
`ACCOUNT_EMAIL_ENABLED=True`, alongside enabled invitation mail. Dispatch uses
`--send --limit 10 --invitations-and-accounts`, approximately 60 seconds after
each completed run, with a 300-second service timeout for the bounded batch.
Receipts remain outside its scope. The image, signing configuration, static
assets and scoped SES credentials are unchanged; the web has no SES credentials.

Candidate checks, supervised dispatch/feedback/recovery, health and the next
natural scheduled run passed. All four timers are active/enabled, the due queue
is empty and monitoring reports no flags. Activation sent no new test messages;
billing/mail records, Company/Membership/invitation rows and existing Workspace
access fingerprints are unchanged. Runtime remains restricted with 117 forced-RLS
tables. Trial, checkout and recurring activation flags remain false.
Private configuration backups/evidence are in `account-mail-activation-20260929/`;
sanitized local reports are `outputs/account-mail-activation-*-20260929.json`.
See the [mail runbook](implementation/platform-mail.md#ongoing-account-and-invitation-mail-enabled-2026-09-29).

The owner selected **one public trial Workspace per owner account**. Local code
now serializes starts across Workspaces using the owner row after the Company
lock, and checks the original actor in retained public trial acceptance events.
Expiry, ownership transfer and plan replacement cannot restore the allowance;
internal transition trials do not consume it. Consent and customer copy include
the limit, and the UI replaces a used trial's start action with a support message.
The service independently refuses direct POSTs. No schema change is required.
See the [decision](adr/2026-09-29-owner-public-trial-allowance.md).

**51 focused tests passed**, covering trial/catalog, billing and access policy,
including five new allowance regressions and different-Workspace concurrent starts
under a restricted role. The first race fixture incorrectly nested different
Workspace contexts; it was corrected to give each thread its own context and the
full focused run passed. Production still lacks the selected-public-trial source.
Next deploy and verify that reviewed release with Plan 3 selected while creation
is paused, then activate the free trial after launch acceptance. Paid checkout,
recurring charges and annual billing remain separate pending work.

## FW-019 account-email delivery rehearsal (2026-09-29)

Owner authorized exactly two emails to `admin+account-test-20260929@rokkad.com`
using a separate non-admin test account. User **11** has no staff/superuser flags
and no Workspace membership. A bounded worker invocation enabled account mail
only within that process; global web/worker flags and invitation-only scheduling
were unchanged. The permanent administrator was not modified.

Both messages reached the admin inbox and have reconciled **delivered** evidence,
one attempt each: verification `ac09c13c-1de3-4eb6-b459-399f5bdba4db` and reset
`efb9e159-5ef6-4d7c-9dd5-1b5d2680debb`. The verification link was consumed through
the live site and confirmed the exact test address. The reset was requested through
the ordinary allauth HTTP handler in the bounded worker and its received link
opened the live Change Password form. The user completed the required password
handoff; the account acquired a usable password, and reopening the actual received
link produced **Bad Token**, proving reuse rejection before cleanup. User 11 was
then disabled and its password made unusable. It retains no membership or platform
privileges. No third email was sent or authorized. Ongoing account sending remains
paused pending a reviewed scheduling/activation step; this completes the bounded
delivery and link-acceptance rehearsal, not public-trial activation.

Private reports are in `account-mail-20260929/acceptance-*.json`; sanitized local
copies are `outputs/account-mail-acceptance-*-20260929.json`. Browser proof is in
`outputs/account-email-confirmed-20260929.png` and
`outputs/account-reset-replay-rejected-20260929.png`. Do not copy reset tokens into docs.

## FW-019 account-mail release deployed with account sending paused (2026-09-29)

At **18:22 IST**, web and all mail consumers moved to
`rokkad:account-mail-20260929-702d1c64ba50`, image
`sha256:a5c71b750eb6eca2e5ffb44e0dda9aa5d44624b51c3a41a773af8e3e48a0d4ea`.
The ten-file overlay contains the reviewed account-mail source and a targeted
adapter/flag change to production base settings; it preserves current UI source
and static assets. The public-trial implementation is not part of this overlay.
A fresh operational backup was verified before the single owner-only migration
`platform_mail.0002`; restricted runtime DML/sequence grants and the exactly-one
source constraint were verified afterward.

Web/worker signing secrets match (compared privately), token configuration and
canonical origin match, and the web still has no SES credentials. Existing
configuration/credential files and container environment are unchanged. Production
uses restricted `rokkad_prod_runtime`, with **117 forced-RLS tables** unchanged.
Existing billing, mail, Company/Membership/invitation fingerprints and Workspace
access/trial dates are unchanged; no account intent, attempt or message was created.

The first service switch rolled back because supervised health ran before paused
timers were restored. Its only flags were the deliberately inactive timers. The
additive migration remained applied safely; the retry reused it, restored timers
before health, and passed. All four timers are active/enabled, supervised workers
passed, HTTPS login returns 200, and mail health has no flags. Dispatch remains
**invitation-only, limit one**. `ACCOUNT_EMAIL_ENABLED=False`; trial, checkout and
recurring gates remain false, with provider configuration still live.

Next: specifically authorized verification/reset delivery using a separate
non-admin test account, then account-mail activation and public-trial deployment.
The rehearsal inbox is `admin+account-test-20260929@rokkad.com`; the owner later
approved the two-message check described above. No permanent administrator
credentials or privileges are changed.
Private release evidence/backups are under `account-mail-20260929/` in the existing
deployment directory; sanitized local evidence is in
`outputs/account-mail-{inventory,prepare,apply,verify}-20260929.json`.

## FW-019 account verification/reset mail implemented locally (2026-09-29)

Added a durable global account-email source to the existing monitored SES outbox,
with an allauth adapter for verification/password-reset hooks. No token-bearing
bodies or passwords are persisted. Restricted-role tests cover real signup and
reset HTTP flows, valid native links, single-use resets, state/expiry/suppression
checks, rollback and concurrent-request deduplication. Signup policy and ordinary
allauth rate limits remain in place. Both invitation/account adapter settings now
use the explicit adapter, preserving the old invitation-only signup policy.

**72 focused mail tests passed**, including 15 new cases. Provider calls were
mocked; no real account email was sent. The trial suites also passed their 25
tests; an initial package-discovery invocation could not import four mail modules,
so the mail suite was rerun successfully using explicit module labels.
An additional **18 invitation authorization/acceptance checks passed**. One older
mock-based test still assumed authorization preceded the Workspace seat lock;
its fixture now reflects the existing lock and asserts denial occurs before
capacity evaluation or invitation creation. No invitation service behavior changed.

`ACCOUNT_EMAIL_ENABLED` defaults to false. New account-only and combined
invitation/account scopes exclude receipts as appropriate before batch limits.
Migration `platform_mail.0002`, web/worker release, runtime grants, matched signing
configuration and authorized real verification/reset acceptance remain pending.
Production was not changed: invitations remain enabled, account mail remains on
locmem, public trials and payments remain paused. Next deploy the coordinated
account-mail release while paused, then perform controlled delivery acceptance
before publishing the public trial. See the [runbook](implementation/platform-mail.md#account-mail-prepared-not-deployed-2026-09-29)
and [decision](adr/2026-09-29-durable-account-email.md).

## FW-019 trial catalog saved and browser journey rehearsed (2026-09-29)

Production now has **Plan 3: Rokkad 30-day public trial**, INR 0 monthly/annual,
30 days and six total members. The reviewed `prepare_public_trial` command defaults
to preview, requires active platform administration and paused trial/payment flags,
and refuses to overwrite changed terms. Apply saves the separate Plan and audit;
repeating it preserves the same plan. Preparation ran under permanent administrator
**admin@rokkad.com / user 9**, without changing privileges or credentials. Existing
Plans 1/2, Company/Membership rows and every non-Plan billing table have unchanged
fingerprints. No Workspace assignment, provider binding, subscription or payment
was created. Invitation sending remains enabled; trial/checkout/recurring flags
remain false. No web/worker image was replaced.

A fresh isolated PostgreSQL database and restricted `rokkad_runtime` browser server
completed signup, local email verification, ordinary New Workspace creation,
30-day trial consent, invitation creation/capture, teammate signup and verified
acceptance. Unverified acceptance was rejected first. Final evidence: two members,
capacity six, one accepted invitation, one trial event, auto-renew false, full
access, and zero invoices/payments/agreements/provider events or sending attempts.
Email was captured locally, not delivered through SES. The browser/server were
closed afterward; fictional fixtures and proof remain in ignored outputs.

**23 focused tests passed**, including three new catalog preparation cases and the
trial/catalog boundary suite. Signup/login copy now describes supported customer,
loan, reminder and rate workflows; obsolete accounting/ERP promises were removed.
The trial success message no longer repeats the word trial. These source changes
still need deployment with the already tested trial implementation.

**New verified launch gap:** production `EMAIL_BACKEND` is Django's **locmem**
backend. Account verification/password-reset mail therefore stays in process memory;
it is not sent by the invitation-only SES worker. Verification is optional at sign-in,
but trial acceptance and invitation acceptance require a verified email. Google
SocialApp is configured and its established verified path is separate. No backend,
credential or authentication setting changed during this read-only check.

Next: implement and accept account-verification/reset delivery, then deploy the
selected trial with `BILLING_PUBLIC_TRIAL_PLAN_ID=3`, review public eligibility/support
controls, and activate only the free-trial gate. Payment acceptance stays separate.
See [trial preparation](plans/public-workspace-trial.md).

## FW-019 public trial consent and seat enforcement implemented locally (2026-09-29)

The approved **30-day trial for owner plus five staff** now has a separate selected
Plan boundary and explicit versioned consent. A verified canonical owner must
accept in the matching Workspace context. Private/changed/unselected plans,
existing billing/access history and over-capacity Workspaces are rejected. Trial
creation records terms and exact end, projects six seats, and sets auto-renew false.
No provider mandate, invoice or payment is created. New-owner onboarding routes
from Workspace creation to consent, then team setup; billing displays trial end
and the seven-day grace/read-only boundary.

A real seat test exposed the old installed-app short-name check that bypassed the
limit. The resolver now uses Django's app registry. Company locks serialize trial
start, invitation reservation/acceptance and member creation; direct member adds
respect pending reservations. Existing members are not removed or changed.

**82 focused tests passed**, including restricted-role HTTP and service journeys,
simultaneous trial acceptance and competing last-seat invitations, no-charge
expiry/grace behavior, private catalog isolation and existing access preservation.
Documentation link validation passed. No production configuration, Plan, customer
subscription or sending operation changed in this increment; public trial and
both payment creation switches remain off in production. Invitation dispatch
continues with the previously verified enabled configuration.

Next: prepare the separate zero-price Plan with reviewed supported features,
rehearse browser signup/consent/invitation acceptance, review one-trial-per-Workspace
abuse/support controls, then deploy and activate the public trial while keeping
payments paused. See [trial preparation](plans/public-workspace-trial.md) and the
[selected-offer decision](adr/2026-09-29-selected-public-trial.md).

## Ongoing invitations enabled; public trial prepared; pricing ticket routed (2026-09-29)

At **17:12 IST**, owner-authorized invitation-only email activation completed.
Compose, public and private worker settings now agree on sending enabled; dispatch
timer/marker are active with **one invitation per run**, 60 seconds after completion.
The current web/worker images, billing flags and credential values were preserved.
Two earlier attempts caught disabled overrides and rolled back before dispatch.
At **17:14 IST**, a subsequent scheduled run succeeded; restricted read-only checks
show zero due messages, clear queue/health and unchanged billing/mail records.
Feedback/recovery/health remain active. No new email or test fixture was created;
existing invitation delivery/acceptance evidence is retained. Receipts are excluded
from the scheduled worker. See [operations](implementation/platform-mail.md#ongoing-invitation-dispatch-enabled-2026-09-29).

**35 tests passed**: 34 existing invitation/mail/onboarding cases and a new
restricted-role database journey covering fresh Workspace creation, queued invite,
one provider submission despite two worker runs, verified membership acceptance,
and no subscription/invoice/payment. Provider sending is mocked; this is not a
fresh browser signup or mailbox-delivery rehearsal.

Owner selected preparation of a public trial and confirmed **30 days**, owner plus
five staff, no card and no automatic charge. The [offer and acceptance plan](plans/public-workspace-trial.md)
is prepared. Public trials remain off because the current flag exposes both active
internal/private plans; separate trial selection and consent need implementation.
Existing five-member/14-day trial Plan 1 and six-member/monthly Plan 2 are unchanged.

Razorpay's fee-email reply was an unmonitored-mailbox notice. The authorized inquiry
was submitted through Dashboard with separately approved phone confirmation:
**21170392 Active**, target **1 October 11:14 AM** displayed. Annual **21146138**
is now **In Progress**, target **29 September 5:48 PM** displayed. Failure
**21146171 Closed** has no technical answer in its conversation; acceptance stays
open and no provider charge was retried. See [support evidence](plans/monthly-billing-pilot.md#dashboard-support-routing-and-trial-preparation-2026-09-29).

## FW-019 fee inquiry sent and future seller transition recorded (2026-09-29)

Owner reconfirmed the current personal-PAN merchant setup and possible future
company/GST registration. Deployed individual seller Rajesh Rathod H and explicit
unregistered/no-GST invoice treatment already match; no production changes needed.
[FW-020](plans/future-work.md#fw-020-company-registration-and-gst-ready-seller-transition)
records the future provider/entity/GST invoice transition, with original seller
snapshots and active mandate continuity preserved. No PAN number was collected.

At **12:53 IST**, the separately owner-authorized merchant fee inquiry was sent
from admin@rokkad.com to the verified Razorpay support recipient. Gmail confirms
Message sent and the sent message content. Subscription/method/setup fees, GST,
promotion coverage and post-promotion rates remain pending provider confirmation.
The technical ticket thread still ends with our 10:21 follow-up; no later technical
reply was visible. No uncertain payment was retried or other provider state changed.

Google's INR 500 payment remains the last verified credited result; its remaining
tax-profile request is separate. No PAN/GSTIN submission or account classification
change was made. All charging/sending gates remain paused. See the
[pilot checkpoint](plans/monthly-billing-pilot.md#individual-seller-continuation-and-fee-inquiry-sent-2026-09-29).

## FW-019 merchant and inbox launch review (2026-09-29)

Read-only Razorpay review confirms recurring cards/UPI AutoPay and mandate methods
Activated, with Card/UPI/eMandate Enabled in Subscriptions settings. Fee Bearer is
**You pay the fee**. The displayed promotion and conflicting public subscription
rates do not establish the merchant's contracted fees; that gate remains open.

After owner sign-in, Google Business Starter is **Active**, with one license and
paid service beginning **10 October**. The owner paid the initially pending INR 500
and requested re-verification: Google now shows **INR 500 credit, no balance due**,
last manual payment **29 September**, and the payment-pending warning has cleared.
Both Business Starter and the 100 GB storage add-on are now Active. The initial
payment requirement is complete; India tax information remains requested and
ongoing account funding remains necessary. No payment, message, settings change
or billing activation was performed by the agent. An earlier additional screenshot
was blocked by automatic approval review; the owner's subsequent explicit
read-only payment re-verification succeeded without an alternative access method.

The rollout now consolidates the current deployed state and remaining gates,
replacing stale top-level live-key/local-only statements. FW-019 remains in launch
validation: provider failure/recovery and naturally due holds, exact fees, mailbox
continuity, JSK eligibility and bounded approval precede activation. Actual callback,
first payment/invoice/receipt and settlement still require pilot observation.
Existing held fixtures begin **28 October**; JSK's **8 October 23:39 IST** trial end
is not a launch date. Annual stays unpublished and charging/sending stay paused.
This checkpoint changes documentation only. See the
[current rollout](plans/subscription-monetization-rollout.md) and
[merchant/inbox evidence](plans/monthly-billing-pilot.md#merchant-methods-fees-and-inbox-review-2026-09-29).

## Receipt dispatch scope deployed with sending paused (2026-09-29)

`dispatch_platform_mail --receipts-only` now excludes invitations before the batch
limit, rejects an explicit invitation for sending/capture, and cannot combine with
invitation-only scope or global stale recovery. It reuses the ordinary dispatch
service: live payment classification, paid source, enablement, suppression, attempts
and uncertain-outcome handling are unchanged. The reviewed first-receipt procedure
requires one explicit delivery ID and limit one after separate send approval.

All **55 focused mail tests passed**, including receipt/invitation selection,
disabled sending/mode boundaries, replay, feedback and controlled Test Mode receipt
coverage. At **12:30 IST**, the command-only overlay
`rokkad:receipt-worker-20260929-e4bee6e23a41` was deployed to worker service and
watchdog references. Restricted read-only preflight and post-deployment checks pass;
all billing/mail fingerprints are unchanged, with six historical attempts and zero
receipts. Web image, schema, credentials and shared runtime settings are unchanged.

Scheduled dispatch remains **invitation-only, disabled, marker absent**; its
supervised start was skipped before Docker invocation. Feedback/recovery/health
runs succeeded and timers resumed; queue due/flags and health flags are zero.
HTTPS login is 200. Checkout, new trials, recurring authorization and sending remain
false. No email, invoice, payment, agreement or live collection was created.

The refreshed support thread still ends with our **10:21 IST** follow-up; no later
technical reply was present. Existing provider failures/held-period acceptance and
actual live callback delivery remain open. Next: review merchant subscription
methods/fees and inbox continuity, then resolve provider acceptance and JSK trial
eligibility before any named pilot activation. Private deployment evidence and
rollback are in `receipt-worker-20260929/` on the deployment host. See the
[receipt runbook](implementation/platform-mail.md#receipt-only-preparation-2026-09-29).

## Live webhook registration verified (2026-09-29)

The owner entered the webhook secret and submitted Razorpay's Live Mode form.
Dashboard reference **ThlAT5rGIawXNH**, created **12:20:44 IST**, is **Enabled** at
`https://rokkad.com/subscriptions/webhook/razorpay/`. Details confirm a secret was
provided, the exact 14 supported events, and admin@rokkad.com for creation/failure
alerts. The secret was not displayed or exported from the Dashboard.

At **12:22 IST**, restricted read-only production checks confirm unchanged billing
table fingerprints, zero webhook events/agreements/invoices/payments, private
catalogs and full access on all three original trials. The permanent admin remains
user 9; temporary operator 10 remains disabled. Configuration/evidence checks pass;
`launch_ready=false`. Checkout, new trials, recurring authorization and sending
remain false. HTTPS login is 200; mail queue due/flags zero, latest watchdog clear,
feedback/recovery/health timers active and dispatch disabled with no marker.

Registration is complete; **actual provider event delivery remains unverified**.
Earlier signed malformed-body diagnostics prove routing/HMAC handling only. Next:
review receipt-worker dispatch scope and remaining provider delivery/failure/recovery
acceptance, preserving JSK's trial and the separate activation decision. No charge
or email was sent. See the
[updated runtime evidence](implementation/billing-provider-readiness.md#permanent-admin-and-live-webhook-runtime-2026-09-29).

## Permanent platform admin and paused live webhook runtime (2026-09-29)

The owner explicitly designated **admin@rokkad.com** as permanent platform admin.
Existing active, verified user **9** now has staff/superuser flags; audit **58801**
records the grant. Existing sign-in is unchanged, as are Workspace memberships,
canonical ownership and subscriptions. Temporary catalog operator **10** remains
disabled with no usable password and no admin flags.

At **12:15 IST**, persistent web and workers received the root-only live key file
and a distinct webhook secret, with **BILLING_PROVIDER_MODE=live**. Checkout, new
trials, recurring authorization and platform sending remain false. Compose,
dispatch/feedback/recovery service definitions and watchdog now use the same live
configuration. Application images and database schema are unchanged.

Read-only preflight and final checks passed in both runtimes under the restricted
database role. All billing-table fingerprints are unchanged; all three Workspaces
retain full trial access and private catalogs. JSK's 8 October trial is preserved.
Configuration/evidence checks pass; `launch_ready` remains false. HTTPS login is
200, web has zero restarts, mail queue flags/due messages zero. Feedback/recovery/
health timers were restored; dispatch stays disabled and its marker absent.

The public callback rejects an invalid signature with HTTP 400. A correctly signed
malformed body reaches payload validation and returns HTTP 400 without inserting a
webhook event. This verifies HTTPS routing and HMAC handling, **not a provider event
delivery**. No subscription, invoice, payment, receipt or charge was created.

The Razorpay Live Mode form is prepared with the verified callback URL, failure
alerts to admin@rokkad.com and 14 supported events. Registration remains pending
the owner's secret-entry/submission handoff required by browser credential policy.
The handoff secret is in a current-user-only local folder outside the repository;
it was not printed or committed. Configuration backups and sanitized verification
are retained server-private under `live-webhook-20260929/`.

Next: verify the saved provider webhook, review receipt dispatch scope and preserve
the unresolved provider acceptance/trial eligibility gates. See the
[runtime checkpoint](implementation/billing-provider-readiness.md#permanent-admin-and-live-webhook-runtime-2026-09-29).

## Live credentials verified and monthly catalog bound (2026-09-29)

The owner generated the live keys and provided the downloaded CSV. At **11:51 IST**,
GET-only Payments, Plans and Subscriptions authentication returned HTTP 200 with
empty live collections. Keys were encrypted with current-user Windows DPAPI in a
dedicated restricted folder outside OneDrive, then staged over SSH in root-only
`/root/rokkad-billing-live.env` (0600). The source CSV remains in Downloads. No key
was printed, committed or loaded into persistent web/worker environments.

At **11:52 IST**, exactly one live provider catalog plan was created and GET-verified:
`plan_ThkgxD2zC0o8FL`, monthly interval one, **149900 paise INR**. It contains no
customer mandate or collection. The provider still returned zero live subscriptions
and payments. A server-side GET independently verified the same plan.

Production had no platform administrator. After explicit owner approval, a dedicated
operator with no usable password (user **10**) briefly prepared local Plan **2**
and immutable live binding **1** through the canonical service, with an audit reason.
At **11:57 IST**, the operator was disabled and staff/superuser flags removed;
independent cleanup verified this. Its identity remains solely for audit linkage.
No existing user received new authority.

The frozen monthly offer has six members and zero GST with the confirmed seller.
Twelve collections/quantity one remain prepared agreement terms, not an existing
subscription. Non-seat internal values retain the original plan's values; annual
14990 is an unpublished working value with no annual binding. The shared trial
Plan 1, all subscription/financial table fingerprints, trial dates and access are
unchanged. Only the separate Plan/binding and operator/profile were added.

Final restricted checks at **11:58 IST**: all three operating Workspaces retain
full trial access and private catalogs; zero agreements/invoices/payments/receipts,
HTTPS login 200, queue flags/due messages zero. Persistent provider mode remains
disabled and all checkout/trial/recurring/sending gates false. The disabled-mode
inventory flags the staged live binding; an in-memory live-mode inventory confirms
no mixed-mode/unclassified evidence. This is expected staged configuration, not
permission to promote Test Mode data. Next: live webhook/runtime configuration and
receipt-worker review, while unresolved provider acceptance and JSK's trial remain.
See [live catalog evidence](implementation/billing-provider-readiness.md#live-keys-and-bound-monthly-catalog-2026-09-29).

## Confirmed billing seller configured with activation paused (2026-09-29)

At **11:45 IST**, the shared web/worker environment received only the four
confirmed seller settings: Rajesh Rathod H, the approved Vellore billing address,
unregistered GST status and explicit tax rate zero. Web retains
`rokkad:party-loan-pages-20260929-5143b3441f2b`; mail workers retain
`rokkad:billing-paused-99bda8c1cb27`. No application or schema deployment occurred.

Restricted read-only preflight and post-configuration checks passed in both
runtimes. All subscription-table fingerprints are unchanged; JSK remains full
access with its original 8 October trial end. The owner catalog remains private.
An unsaved monthly offer validates 149900 paise, zero GST and six members, with
12 collections/quantity one prepared. No plan, binding or agreement was saved.
HTTPS login returns 200 and web has zero restarts. Mail queue flags/due messages
are zero; feedback/recovery/health timers remain active, dispatch disabled.

Provider mode, checkout, trial signup, recurring authorization and sending remain
paused. No credential was added and no provider request, payment or email sent.
The owner confirmed live keys have not been generated. Razorpay's approved website
and Generate Key page are open for the required owner credential-generation
handoff; download to the named local CSV, never paste keys in chat.

The four-field candidate, prior environment, preflight and verification logs are
retained server-private under `billing-seller-20260929/` in the deployment folder;
automatic configuration rollback was prepared. Initial validation-harness issues
(placeholder defaults, CSS versus rendered cards, worker entrypoint/static assets)
were corrected before applying settings; they caused no persistent change.
Next: protected live credentials and exact monthly catalog preview/binding,
with provider acceptance and JSK's trial preserved. See the
[configuration checkpoint](implementation/billing-provider-readiness.md#confirmed-seller-configuration-2026-09-29).

## JCL borrower contact auto-sizing published (2026-09-29)

Owner confirmed **RA00594** and authorized automatic font sizing. JCL now uses
layout revision ID **5**, version **4**, published/assigned through audited template
services. Only `borrower.contact_block` changed: WRAP to SHRINK and fixed 12 pt
leading to automatic leading. Its starting 12 pt font, 6 pt padding, 60 x 30 mm
rectangle and (40,50) mm position remain unchanged; the existing 6 pt minimum and
overflow failure guard remain in effect. Complete contact text is retained.

Read-only review and post-publication official-mode rendering passed for both
RA00594 copies, including full-text extraction inside each printed contact frame.
Its contact renders at approximately **10.08 pt**. Short and longer fictional
contacts passed at 12 pt and 6.67 pt, with visual review using only fictional data.
Automatic approval review blocked downloading the real borrower review image;
real-data checks remained on production. C07565's two mixed-metal weight lines
still render on both copies. All active JCL series resolve the new revision;
the old published revision remains intact. Loan, event, approval, customer,
address, issued-document and number-sequence row hashes were unchanged.

No ticket was issued on the owner's behalf, and existing issued PDFs retain their
original bytes. No application deployment, schema or paper-profile change.
Server-local backup `production-20260929T053658Z.dump` passed archive validation;
private configuration, review/apply/verify and backup evidence is retained in
`ticket-contact-20260929/` on the deployment host. Layout hash:
`1beea9a243d997795e71d93bce8a47ad34eb50236c93e02e58d5829a98d420ca`.
Physical printer output remains unverified.

## JCL borrower contact overflow verified (2026-09-29)

Read-only production diagnosis reproduced the reported `(40,50) mm`
`borrower.contact_block` error on **RA00594**, including full-ticket rendering.
The owner's specific failing loan is not yet confirmed. The active JCL contact
frame is 60 x 30 mm, 12 pt font/leading, 6 pt padding and WRAP. This borrower's
address is already split across line1/line2/area/city/state/PIN/country; the document
selector joins those fields with commas before wrapping. Its full contact block
needs seven lines / 84 pt against 73.04 pt available. Moving address text between
fields alone does not address this template capacity limit.

In-memory contact-only checks fit with either 10 pt text or SHRINK plus automatic
leading; no proposal was published and no ticket issued. A future correction
should preserve full contact text, existing frame geometry, immutable issued PDFs
and the earlier mixed-metal weight fix. Scripts/evidence: local
`outputs/ticket-contact-check.py` and `outputs/ticket-contact-measure.py`; no customer
address text was exported. Application and production configuration are unchanged.

## Party loan pagination and date sorting deployed (2026-09-29)

Web runs `rokkad:party-loan-pages-20260929-5143b3441f2b`, a four-file update built
on the phone-entry release. Party detail's Loans tab now provides independent
20-row active/closed pages, range/count labels, Previous/Next and elided numbered
links. A shared loan-date selector offers newest first (default) and oldest first
with a primary-key tie-breaker. Page links preserve sort and the other list's page;
applying a new sort resets both lists. Full outstanding/collateral totals and
borrower-portal limit semantics remain unchanged.

All **67 focused tests passed** across Party UI, loan-history selectors and borrower
portal behavior. New persisted-loan coverage exercises 41 active and 41 closed
loans, tied/non-monotonic dates, other-borrower exclusion, complete outstanding,
independent navigation, malformed/out-of-range parameters and empty lists.
Candidate/deployed read-only checks under the restricted runtime role passed for
JSK, JCL and Lakshmi Pawnbroker. At verification, JSK P-000433 had 301 active and
five closed loans; both date orders and page ranges matched the database, with
unchanged totals across pages. Live browser checks confirmed sort persistence on
page 2, the single-row page 16 and mobile controls without page-wide overflow.

A fresh server-local backup and prior Compose/image references provide rollback;
private evidence is in `party-loan-pages-20260929/` on the deployment host. HTTPS
login/startup passed. The existing static volume, resolved environment, production
settings and mail-worker images are unchanged. No schema migration or lending
record mutation was performed. Documentation links and whitespace checks passed.
See the [Party contract](domain/party.md).

## Compact customer phone entry deployed (2026-09-29)

Web now runs `rokkad:phone-entry-20260929-fb66afff9ef0`, built from the paused
billing release with seven reviewed Party form/display/static files. Customer
phone entry uses the existing `django-phonenumber-field` dependency with a compact
single field, India as default, international country-code support, and mobile
and landline validation on save. Valid numbers display with international spacing
and retain E.164 storage. Phone, Mobile and WhatsApp contacts share this behavior;
email and website contacts keep their respective validation. Invalid legacy values
remain visible unchanged. No model migration or bulk customer-data rewrite.

Validation: **84 distinct tests passed** across phone handling, Party UI and staged
imports, including canonical storage, rejected edits, legacy display and mixed
contact types. Desktop/mobile browser checks covered formatting, error display and
contact-type switching. Candidate and deployed checks passed under the restricted
runtime role in read-only transactions across JSK, JCL and Lakshmi Pawnbroker;
production customer creation rendered correctly in the browser. HTTPS login and
the hashed JavaScript asset passed. A fresh server-local backup and previous
image/static/compose references provide rollback; private evidence is retained in
`phone-entry-20260929/` on the deployment host.

Production settings and resolved environment are unchanged, including paused
billing and sending. Mail workers retain the preceding billing-paused image;
this release changes no worker code. See the [Party contract](domain/party.md).

## Razorpay resolution verified against payment evidence (2026-09-29)

Read the verified-sender support thread: at **17:37 IST on 28 September**, Razorpay
marked ticket **21146138** Resolved because the annual subscription is Active and
recommended Live Mode validation. The 17:43 notice says it will close after four
days without a reply. The response does not resolve the unpaid final invoice or
answer the failure-simulation question in **21146171**; that ticket's acknowledgement
is grouped in the same Gmail thread.

Fresh GET-only checks at **10:18:37 IST on 29 September** show annual payment
`pay_ThBR0fQ4nwVW3p` still Created, invoice Issued, subscription Active with one of
two cycles paid. The failure simulation remains Captured/Paid, with its previously
cancelled subscription at two paid cycles. The scheduled authorization is still
Created and subscription Expired with zero paid. Local financial/mail counts are
unchanged. Ticket resolution therefore does not satisfy these acceptance gates.

A focused follow-up was owner-authorized and sent from admin@rokkad.com at
**10:21 IST** to the verified support thread, requesting renewed investigation of
21146138 and specific guidance for 21146171. Gmail confirms Message sent and shows
the exact reply; provider-side reopened status is not yet verified. Preserve the
uncertain attempts and continue paused live preparation separately; do not use a
real collection to bypass outstanding acceptance. No provider write, production
change, live credential action or payment occurred. See the
[provider checkpoint](plans/monthly-billing-pilot.md#support-resolution-verification-2026-09-29).

## Private catalog deployed with billing paused (2026-09-28)

Web runs `rokkad:billing-paused-99bda8c1cb27` from **16:05 IST**; mail workers and
watchdog/operator references were aligned at **16:06 IST**. A fresh verified
server-local backup and retained image/static/configuration copies provide rollback.
No migration was required. Compose changed image/static references and made the
already-disabled trial flag explicit; other resolved configuration is unchanged.

All three operational Workspaces passed private-catalog, dashboard, recurring,
overdue and loan-detail checks. Catalog pages show prepared-agreement guidance,
without plan cards or annual prices. Billing/Loans fingerprints across five
Workspaces and access are unchanged, including JSK's trial. Stored ticket hashes,
public pages and static checks passed. No new plan, binding or invoice was created.

At **16:07 IST**, web is running with zero restarts and HTTPS login 200; restricted
worker runtime and feedback/recovery/health pass, with monitoring timers active.
Queue flags/due messages remain zero, attempts six and receipts zero. Dispatch is
disabled/marker absent, invitation-only, limit one. Billing provider, purchases,
trial signup and sending remain paused. Credentials, seller settings and alerts
were preserved. Next: protected live seller/provider configuration and catalog
preparation, with JSK's trial and outstanding acceptance preserved. See the
[release record](implementation/billing-paused-release-20260928.md#private-catalog-update-deployed-2026-09-28).

## Private pilot catalog implementation (2026-09-28)

When checkout and trial signup are both paused, the owner catalog now returns no
plans and guides owners to their prepared recurring agreement. That agreement
continues to show frozen price/cycle/seats/duration even when the mutable Plan
changes. Live catalog preview/binding also requires trial signup paused before
provider access. Explicit self-service checkout retains annual offers; trial-only
signup omits annual purchase copy. No new setting, model or migration.

Generic catalog feature/operation/support claims and dashboard warehouse/legacy
features/estimated overage charges are removed. Member-capacity guidance and real
invoices remain; stored prices, annual defaults, entitlements and trial dates are
unchanged. This is an operator-prepared monthly pilot, not a new public catalog.

Validation covered **128 distinct tests** across pricing/publication, recurring
owner pages, checkout, seller rendering, live catalog/recurring and access policy.
The initial broader run found one old dashboard-copy assertion; it was updated and
all 12 access-policy tests passed on rerun. Other checks: no schema drift, supported
app boundaries, documentation links and whitespace. Provider calls were mocked.
Production is unchanged at this implementation checkpoint; paused deployment is
next. See the [decision](adr/2026-09-28-private-operator-billing-catalog.md).

## JSK pilot facts and transition review (2026-09-28)

Owner confirmed Rajesh Rathod H's no-GST registration status and documented billing
address, selected 12 monthly collections, and named **JSK** as the first pilot.
Read-only production review at **15:50 IST** verified Workspace 2, its canonical
active owner and matching billing email, three members, no pending invitations,
full access and no existing mandate/open agreement/outstanding invoice.

JSK's trial ends **8 October at 23:39 IST**. Immediate recurring creation correctly
blocks an unexpired trial; its dates and access are preserved. Scheduled live
conversion remains unsupported. Other acceptance still applies; this date is not
a launch commitment. The unsaved confirmed-seller preview produced 149900 paise,
zero GST and six members with zero database queries/provider requests.

Catalog review found generic plan cards still show legacy feature/operation labels
and annual prices, with automatic annual-price population on save. Resolve that
presentation before creating a new active monthly pilot plan; no shared plan was
edited and no new plan/binding was saved. At **15:49 IST**, GET-only checks found
both preserved Test Mode payments still Created with unchanged local record counts.
Support inbox status was not refreshed. No production configuration, live key,
payment, email or access changes. See the
[confirmed pilot review](plans/monthly-billing-pilot.md#confirmed-jsk-pilot-review-2026-09-28).

## Seller invoice update deployed with billing paused (2026-09-28)

Web now runs `rokkad:billing-paused-60c7beeb8191` as of **15:44 IST**; all mail
worker references and the watchdog/operator command were aligned at **15:45 IST**.
This deploys the frozen seller and explicit tax implementation below. No migration
was required; no seller profile, live credentials or provider resources were set up.

A fresh server-local backup passed archive/catalog and SHA-256 verification before
the switch. Billing and every directly Workspace-owned Loans table retain matching
before/after fingerprints across all five Workspaces. Existing plans, three trials
and access are unchanged; invoices/payments/recurring evidence remain empty.
Restricted runtime, owner pages, stored loan-ticket hashes, public pages and the
static asset check passed. Unconfigured live seller settings are rejected.

Final checks at **15:45 IST**: web running with zero restarts and HTTPS login 200;
feedback/recovery/health successful and timers active; no mail queue/health flags,
zero due messages, six unchanged historical attempts and zero receipts. Dispatch
remains disabled/marker absent with invitation-only limit one. Provider mode is
disabled; checkout, recurring authorization and sending remain false. Credentials,
settings and existing alerts were preserved. No payment or email was sent.

The previous image/static volume and worker configuration copies are retained for
rollback. Next: finalize seller status/address, mandate duration and named pilot,
then complete live configuration and outstanding provider acceptance before a
separately approved first collection. See the
[deployment record](implementation/billing-paused-release-20260928.md#seller-invoice-update-deployed-2026-09-28).

## Frozen seller and explicit live tax implementation (2026-09-28)

New live offers/orders and recurring authorization now require a reviewed seller
name/address, explicit `unregistered` tax status and zero tax rate. Base tax has no
implicit default; tests and the isolated rehearsal keep their explicit illustrative
18%. Registered-supplier treatment is deliberately unsupported in this pilot.

New live checkout and plan-binding snapshots freeze issuer details; recurring paid
invoices inherit those details. HTML/PDF invoices, checkout/authorization and receipts
show the seller and no-GST wording. Historical invoices retain saved tax and never
inherit today's seller. Current profile changes block new authorization but do not
block same-mode payment recovery, cancellation or existing-order identity retries.
Existing database guards reject snapshot rewrites; no migration or backfill needed.

Validation: **221 tests passed** in the final billing/mail regression run, including
12 seller/configuration/document cases, zero-tax catalog guards, recurring cycles,
recovery/refunds/replays and historical preservation. The preceding focused run
also passed live-workflow and checkout coverage; its single old receipt-amount
expectation was corrected and passes in the final run. **Four checkout JavaScript
retry tests passed**, as did schema-drift, import-boundary, documentation-link and
whitespace checks. The one-page unsaved invoice PDF was text-checked and visually
reviewed with the existing PyMuPDF renderer; no clipping or overlap. No new dependency.

All provider/mail calls in tests were mocked. No production configuration, seller
profile, catalog or financial evidence changed; production remains on the earlier
paused image. Next is a paused web/worker deployment, followed by final business
review and live configuration. See the [seller decision](adr/2026-09-28-frozen-billing-seller.md)
and [configuration runbook](implementation/billing-provider-readiness.md#frozen-seller-and-explicit-tax-settings-2026-09-28).

## Monthly pilot preparation and provider review (2026-09-28)

The owner selected a monthly-only INR 1,499 pilot, owner plus five staff, with
operator-prepared agreements, and supplied **Rajesh Rathod H** as the invoice name.
Replies indicate personal-PAN/no-GST registration; Razorpay GST settings show
addition unsupported for this business type. The draft collects no GST, pending
final seller/tax review. No PAN number was requested or recorded.

At **15:16 IST**, GET-only provider checks found both preserved payments still
Created: annual agreement Active (one of two paid), invoice Issued; scheduled
agreement Expired (zero paid). Refreshed support-email search still contains only
acknowledgements. No retry/refund/cancellation or new support message. At **15:19
IST**, an unsaved six-member monthly offer under a read-only isolated transaction
produced 149900 paise with zero tax; bindings/invoice count were unchanged.

The [pilot preparation](plans/monthly-billing-pilot.md) records selected scope,
invoice draft and remaining decisions. Source review identifies the next change:
explicit live seller/tax readiness and frozen issuer details across HTML/PDF and
receipts. Base tax still defaults to 18%; invoices omit seller details and always
show GST. Automatic annual price population also means a missing annual price
alone cannot enforce monthly scope.

No production configuration, code, catalog or payment state changed. Billing/mail
stay paused. Annual launch is deferred; monthly scope does not waive other
applicable acceptance. The focused read-only offer preview and documentation
whitespace checks pass; no application test suite rerun was needed.

## Mail workers aligned with paused billing release (2026-09-28)

At **15:03 IST**, dispatch, feedback, recovery and the watchdog/operator command
were aligned with `rokkad:billing-paused-4a131587ee80`, the verified production web
image. Only three service image references and the watchdog command image changed.
Existing invocations finished before replacement; feedback/recovery/health schedules
resumed enabled and active. Their supervised runs passed. Dispatch was explicitly
skipped by its absent marker and retains `--limit 1 --invitations-only`; its timer
remains disabled. Shared sending is false.

At **15:05 IST**, restricted worker role `rokkad_prod_runtime` had neither superuser
nor BYPASSRLS privileges. Provider mode remains disabled; checkout, recurring and
sending are false. Six historical attempts, zero receipts and four delivery outcomes
are unchanged; there are no due rows, queue flags or health alerts. The operator
check passes. Web has zero restarts and HTTPS login returns 200. No email or payment
was sent. Credentials, production Compose/settings and sticky alerts are unchanged.

Private rollback copies, hashes and execution evidence are in
`/root/rokkad-billing-release-20260928/mail-workers`. No application code or schema
changed. Worker alignment is complete; next is the remaining provider/commercial
and live configuration acceptance before an explicitly authorized paying pilot.
See the [worker record](implementation/platform-mail.md#worker-image-alignment-2026-09-28).

## Paused billing release deployed (2026-09-28)

At **14:55 IST**, the approved release `rokkad:billing-paused-4a131587ee80` replaced
the web image, using separate static volume
`rokkad_production_static_billing_4a131587ee80`. Image ID remains the verified
`sha256:33ed455872008db4b70c92f9eff9ea5572b6b3b47ab4c28fefe3813f109b0d48`.
A fresh 55,820,977-byte server-local database backup at **14:51:58 IST** passed
archive-catalog and checksum verification. The previous image/static volume remain
available; no rollback or database restore was needed.

Applied exactly subscriptions migrations 0012–0017 through the migration-owner
role. Restricted startup, runtime grants and RLS checks pass; no pending migrations
remain and all new recurring tables are empty. Fingerprints of existing billing
records and every directly Workspace-owned Loans model across five Workspaces
match before migration, after migration and after deployment. One plan and three
trials are preserved; operational Workspaces 1–3 retain full access and test
Workspaces 4–5 remain recovery-only.

Owner dashboard/overdue/loan detail/billing/plans/recurring pages passed for the
three operational Workspaces. Existing stored ticket PDFs were hash-verified where
present. Public HTTPS login, developer/policy pages and the exact new recurring
JavaScript asset passed. Web runs with zero restarts; ordinary lending writes
remain enabled and no owner credential was passed to web.

Compose changes are limited to image/static references and explicit paused flags:
provider mode disabled, checkout false, recurring false and platform sending false.
Other configuration and the production settings file are unchanged. At **14:56 IST**,
billing inventory had no payment evidence or blockers; mail had zero due messages
and no queue flags. Dispatch stays disabled/marker absent, with feedback, recovery
and health active on existing images. No payment or email was sent.

Private evidence: `/root/rokkad-billing-release-20260928`. The
[release record](implementation/billing-paused-release-20260928.md#deployment-result)
contains the backup digest, before/after evidence and rollback boundaries. No new
application code was introduced; the pinned release tests and migration-preservation
test remain applicable. Next is updating the mail worker images with sending still
paused, followed by remaining provider/commercial and live configuration acceptance.

## Paused billing release prepared (2026-09-28)

Built `rokkad:billing-paused-4a131587ee80` from committed application source,
recording image ID `sha256:33ed455872008db4b70c92f9eff9ea5572b6b3b47ab4c28fefe3813f109b0d48`.
The private source-only package excludes credentials/data; no production service
was replaced. Read-only inventory found one plan, three existing trial subscriptions
and zero invoices, payments, legacy mandates or invoice receipts. Preserve the
plan/trials; there is no payment-mode ambiguity to resolve in production.

Exactly six subscriptions migrations (0012–0017) are pending for the candidate.
Already-applied migration files match after line-ending normalization. One new
disposable-database upgrade test passed, preserving three fictional trials,
plan pricing, entitlements and operator access with zero financial/recurring
backfill; CI includes it. No production migration occurred.

Candidate checks against production passed with restricted credentials and a
read-only transaction: runtime/RLS, migration planning, dependency integrity and
static collection (865 files in a disposable container). Owner default grants
cover new runtime tables/sequences. Readiness reports disabled billing, no live
configuration and `launch_ready=false`. Shared email/debug-toolbar and HSTS policy
warnings are recorded in the release notes.

Candidate mail readiness passes with the existing worker configuration. At
**14:44 IST**, no deliveries were due and no queue flags existed. Sending stayed
false, dispatch disabled/marker absent; feedback/recovery/health timers remain
active. Web, settings, static volume, schema and records are unchanged. Private
evidence is in `/root/rokkad-billing-release-20260928`.

Final verification matched all 1,254 runtime source-file hashes and reconfirmed the
unchanged web image and timer states. Documentation links (616) and whitespace
checks pass.

The [release record](implementation/billing-paused-release-20260928.md) pins the
candidate, previous image/static volume, migration order and rollback procedure.
Next: fresh backup, separate static assets, owner migration and web deployment
with all billing/sending flags still paused. Live activation and unresolved
provider/commercial acceptance remain separate.

## Mode-matched live recurring workflows (2026-09-28)

FW-019 now supports immediate-start live recurring agreements through the existing
creation, owner authorization, paid-cycle, cancellation and explicit held/refund
review services. Matching configured keys and immutable binding mode are required.
New live creation/authorization additionally require the default-off recurring
flag, webhook secret and no test/unclassified billing evidence. Catalog registration
still requires both purchase flags paused.

Pausing new authorizations preserves existing financial recovery and cancellation,
including GET-only reconciliation of an unknown creation attempt. Durable creation
and cancellation claims still prevent repeat provider POSTs. Authorization alone
grants no access; verified invoices determine exact paid periods, future payments
stay held and replays cannot reactivate access. Live consent/receipt wording no
longer calls the payment Test Mode. Scheduled live starts and live reservation
release remain blocked pending separate policy/provider work.

This is local implementation using fictional identities, dummy live-prefixed keys
and mocked provider/SES responses. No live credentials, actual provider writes,
email, production deployment or migration were used. Default flags and monitored
mail operations are unchanged. Configuration diagnostics report live code support
but continue to return `launch_ready=false`. See the
[decision](adr/2026-09-28-mode-matched-live-recurring-workflows.md) and
[release gates](implementation/billing-provider-readiness.md#live-recurring-workflow-support-2026-09-28).

Validation: all **135 existing billing regressions** passed. The new receipt fixture
initially lacked canonical mail settings; after correcting that test setup and
adding annual live coverage, the final **63-test live/cycle run passed**, comprising
**28 live-mode cases** and 35 paid-cycle cases. Coverage includes committed attempts,
uncertain recovery without reposting, cross-mode rejection, signed replay, exact
monthly/annual periods, held/refund review, cancellation and mocked receipt dispatch.
Both browser authorization-retry tests pass, as do 613 current documentation links
and whitespace checks. CI includes the new live suite; no schema change is needed.

Next: prepare the paused production release and review legacy billing evidence,
alongside the remaining provider and commercial acceptance. Last external checks
remain the 14:14 IST observations below; no new provider outcome is claimed.

## Live catalog preparation boundary (2026-09-28)

FW-019 now supports platform-only review and local registration of a known live
Razorpay plan. `prepare_recurring_agreement ... bind --mode live --preview` fetches
the provider plan and reports verified local price/tax/cycle/seat terms without
saving. Registration freezes those same terms in the existing immutable binding;
repeated identical terms reuse the binding. It never creates a provider plan,
mandate, charge, invoice, paid access or email.

Live preparation requires explicit matching live credentials, both purchase flags
paused, and no conflicting test bindings or test/unclassified invoices. Guards run
before provider access and again before persistence; changed offers are refused.
Test preview works while authorization is paused, while Test Mode registration
retains its prior enable gate. Live agreement creation and all live recurring
financial workflows remain unsupported. No live credentials or actual live catalog
were used, no production deployment/migration occurred, and the working commercial
offer remains unpublished. See the
[decision](adr/2026-09-28-live-recurring-catalog-preparation.md) and
[operator workflow](implementation/billing-provider-readiness.md#live-catalog-preparation-2026-09-28).

Validation: **39 tests passed** across recurring preparation, provider configuration
and initial catalog coverage. After final guard additions, all **13 catalog tests
passed**, covering mode/authority boundaries, paused flags, monthly/yearly amounts,
idempotency, offer changes, provider failure, contaminated evidence before/during
verification, preview side effects and continued live-mandate refusal. CI includes
the new suite. Documentation links and whitespace checks pass.

At **14:14 IST**, GET-only checks still found annual agreement 5 Active with one
paid cycle, final payment Created and invoice Issued; scheduled agreement 6 Expired
with zero paid cycles and its INR 5 token Created. Local records are unchanged.
The ticket-number inbox search still showed only the 11:49/11:50 acknowledgements
for 21146138/21146171. Preserve both unresolved attempts. Next is live recurring
agreement/payment implementation and mode-isolation tests, alongside remaining
provider acceptance and commercial review; catalog preparation alone is not launch
readiness. Monitored mail state from the previous checkpoint remains unchanged.

## Monitored single-invitation delivery (2026-09-28)

The owner approved the monitored invitation check and selected admin@rokkad.com.
Canonical Workspace/form/invitation services prepared the empty **Rokkad Invitation
Activation TEST** (production Workspace 5), with a Viewer invitation (5), while
sending stayed disabled. Delivery `89479b30-f62b-470b-bb43-f368b3f47483` was sent
once through the reviewed invitation-only image in a bounded transient systemd
job using `--delivery`, `--limit 1` and `--invitations-only`. Sending was enabled
only inside that process; shared configuration, dispatch marker and general
dispatch timer stayed paused throughout.

At **14:09 IST**, the invitation reached the selected Gmail **Inbox** in three
seconds. **SPF/DKIM/DMARC PASS**, TLS, notification sender and support@rokkad.com
Reply-To were verified. The received HTTPS invitation link correctly rejected the
current owner's different email. This fresh invitation remains pending, with only
the owner membership in the empty test Workspace; no new acceptance is claimed.
Evidence: `outputs/invitation-activation-inbox-20260928.png`,
`outputs/invitation-activation-auth-20260928.png` and
`outputs/invitation-activation-identity-20260928.png`.

Feedback and recovery timers are now **enabled and active**, alongside health
monitoring. Canonical feedback recorded **Send and Delivery**, with exactly one
attempt for this invitation (six total historical attempts). At **14:11 IST**, the
due queue was empty, health had no flags, and source SQS/DLQ showed zero available
and in-flight messages. General dispatch remains disabled and marker absent;
receipt/live billing activation is unchanged. Private evidence is under
`/root/rokkad-invitation-activation-20260928`.

This operations checkpoint changes no application source or schema. Existing
39-test dispatch acceptance remains applicable; documentation links/whitespace
are checked. The bounded delivery check is complete. Ongoing invitation dispatch
would be a separate scope expansion; FW-019 next returns to provider acceptance
and reviewed live billing implementation, with mailbox billing continuity still open.

## Paused invitation worker and IAM cleanup (2026-09-28)

Mail activation preflight found that the deployed web and original mail worker
do not yet contain the newer billing-mode/receipt safeguards. To bound initial
activation, `dispatch_platform_mail --invitations-only` excludes invoice receipts
before the batch limit and rejects explicit receipt dispatch or global recovery
with that scope. Existing invitation authority, suppression and delivery evidence
remain in force. **39 dispatch/mail/operations tests pass**; CI includes the new
regressions. No schema or billing behavior changed.

The minimal command-only image `rokkad:invitation-worker-20260928-31f6aa88dd72`
is installed in the production dispatch unit with `--limit 1 --invitations-only`,
**paused**. The runtime is restricted, the deployed image has no pending migrations,
the production mail queue has zero due rows and zero invoice receipts, and source
SQS/DLQ each show zero available/in-flight messages. No sticky alerts were present.
Sending remains false, the dispatch marker absent, and dispatch/feedback/recovery
timers disabled; only health monitoring remains enabled. Web, other workers and
the database schema are unchanged. This does not deploy the full billing branch.

At **14:00 IST**, AWS saved `RokkadPlatformMailRuntime` **version 3 as default**,
removing only the already-expired `SandboxAcceptanceRecipientUntilSeptember28`
statement. The two existing SES-send/SQS-consume statements remain unchanged;
versions 1 and 2 remain available. Evidence:
`outputs/mail-policy-cleanup-saved-20260928.png`. No email was sent.

Next is a separately scoped, monitored invitation activation with feedback/recovery
running, fresh queue review and an authorized recipient. General receipt dispatch
still requires the reviewed billing deployment and live-mode acceptance. Provider
test outcomes and Google Workspace billing continuity remain open. See the
[paused installation and rollback](implementation/platform-mail.md#paused-invitation-worker-and-iam-cleanup-2026-09-28).

## Receipt inbox/authentication/reply acceptance (2026-09-28)

The paid Test Mode receipt is present in admin@rokkad.com's **Inbox**, with correct
amount, exact period and simulated-payment notice. Gmail's original-message report
confirms **SPF PASS, DKIM PASS (notify.rokkad.com), DMARC PASS**, TLS and delivery
after three seconds. The received Reply-To is billing@rokkad.com.

After explicit owner approval, one TEST-only reply was sent from admin to billing
with reference `RECEIPT-REPLY-20260928-01`. Because these addresses share a mailbox,
the Sent copy alone was not treated as delivery proof. After owner sign-in, Google
Admin's exact-message/recipient log independently confirmed **1/1 delivered** to
the billing Gmail mailbox at **13:40:50 IST**, taking **0.93 seconds**. Receipt
content, inbox, authentication and this billing reply path are accepted. Evidence:
`outputs/receipt-inbox-authentication-20260928.png` and
`outputs/receipt-billing-reply-delivered-20260928.png`.

At **13:43 IST**, GET-only Razorpay checks still found the annual final payment
Created and invoice Issued. The short scheduled agreement is now **Expired**, with
zero paid cycles; its INR 5 token remains Created. The canonical owner refresh
recorded expiry, retaining its reservation and all access/financial records. No
new charge, cancellation, refund or resend was made. Ticket-number email searches
show only the two acknowledgements; no substantive provider answer was found.

General mail dispatch and live billing remain disabled. Next is a reviewed mail
activation preflight (deployed worker/source version, IAM, queues, alerts and
bounded send scope), alongside unresolved recurring/provider and live-mode work.
Google Admin also displays prepayment pending and 12 days left in the Workspace
trial; owner billing completion is a human-inbox continuity dependency. No account
or payment settings were changed. This increment changes evidence/docs only;
documentation links and whitespace are checked, with no new application tests needed.

## Controlled receipt path and new paid Test Mode fixture (2026-09-28)

Loan/UI source is committed and pushed as `7c875778` on the release branch.
The next FW-019 increment adds the exact-recipient, default-preview receipt command,
with restricted rehearsal-runtime checks, current owner authorization, atomic
attempt/audit evidence and no automatic repeat after uncertainty or throttling.
All 56 targeted receipt/configuration/mail tests pass. No general dispatch or live
billing gate was loosened; no new migration is needed.

The separate `receipt_rehearsal` Workspace (8) completed monthly Test Mode
capture, verified recovery and replay. Invoice 10 / cycle 8 records INR 1,768.82
for the owner-selected `admin@rokkad.com` contact, frozen from the new billing
account. With explicit owner send approval, the TEST-labelled receipt was delivered
to its recipient mail server with one attempt and correlated SES Send/Delivery events.
The two older unsettled provider payments still report Created and are preserved.
Recurring authorization is off again locally. The new settled Test Mode agreement
is cancelled, with paid dates and invoice/payment/cycle/receipt counts unchanged.
Inbox placement, received authentication headers and reply handling remain to check.

A separate server worker now keeps SES credentials server-private, using a temporary
encrypted connection bound only to server loopback. After explicit owner approval,
the reviewed source image was built and a root-only temporary configuration was
installed. A second approval specifically covered temporary transfer of the restricted
database credential and Test Mode keys; the local signing secret stayed local.
Server readiness and exact-receipt preview passed before the one-off send. The
temporary credential file is now removed and its SSH process/listener stopped.
General dispatch remains disabled; only the existing health timer is active.
Production containers and mail timers remain unchanged. Browser acceptance shows
**Delivered to recipient mail server** (`outputs/receipt-rehearsal-delivered.png`). See the
[exact fixture and command](implementation/billing-provider-readiness.md#addressed-receipt-command-and-paid-fixture-2026-09-28).

## Loan and UI source checkpoint (2026-09-28)

At the owner's request, the remaining loan/application-shell/public-page changes
are now selected for their own source commit after the FW-019 checkpoint. This
includes the Workspace collateral-photo rule and forced-RLS migration 0028,
borrower totals across all active loans, per-item LTV guidance, the dedicated
overdue page, compact loan-entry help, shared navigation/footer and previously
approved legal/developer content. Existing deployment evidence below remains
historical; this source checkpoint does not deploy or migrate production.

The 234-test loan/UI run passed 232 cases, including lifecycle/media/economics,
RLS enforcement, borrower totals, approval, document evidence, overdue permissions
and public/rehearsal pages. Its two failures were stale registry counts after
adding the photo-policy model. Counts now expect 117 and explicitly include that
model; all four registry tests pass on rerun. Eight JavaScript checks passed,
and Django detects no missing migrations. The borrower race/failure checks are
now included in GitHub Actions. Existing accounting and approved evidence remain
unchanged by the display work.

## FW-019 source checkpoint and receipt rehearsal preparation (2026-09-28)

The owner requested a commit/push of progress and continuation of FW-019. The
checkpoint selects recurring billing, provider-mode guards, the platform-mail
foundation, private rehearsal tooling and accumulated documentation. Separate loan,
public-page and application-shell code remains in the working tree; documentation
entries for that work describe those earlier working-tree/deployment checkpoints,
not inclusion of those code changes in this billing/mail commit. No credentials,
private output evidence or generated fixtures are included. GitHub Actions now
includes the new recurring/mail suites and payment-retry/rehearsal helper tests.

Validation uses an exported copy of the staged code. An initial run against the
shared automated-test database encountered its unrelated newer loan table during
flush; this was a test-schema mismatch, and that test database was subsequently
cleaned with the full working-tree model registry. The independent rerun uses a
fresh dedicated test database, preserving the private billing rehearsal database.
The fresh-schema run passed **381 Django tests** in 239 seconds and removed its
temporary database. Four checkout JavaScript tests, ten rehearsal-helper tests,
Python parsing and the current-document link check also passed. Provider calls
and email sending were mocked in the automated suites.

The next receipt rehearsal is prepared for **admin@rokkad.com**, selected by the
owner. Read-only server checks at 12:44 IST found valid mail configuration, no
queued messages or alerts, restricted credential-file permissions and the health
timer active. Dispatch, feedback and recovery timers remain disabled; no service
was changed. Invoice 9 was rendered in a read-only local transaction as a labelled
Test Mode content reference, with zero send attempts and all nine local receipts
still queued. Its fictional contact remains immutable. Actual delivery needs a
new isolated paid fixture with the chosen contact, a narrowly targeted send path,
and final approval of the prepared message. No payment, provider agreement or
email was created by these readiness checks. See the
[receipt preparation notes](implementation/billing-provider-readiness.md#receipt-rehearsal-preparation-after-the-checkpoint).

## Explicit billing mode, receipt safeguards and SES approval (2026-09-28)

AWS SES production access is **approved** in Mumbai. After the owner signed in,
the support console showed case **179042575700203** approved at **11:20:42 IST**
today, with **50,000 messages/day**, **14/second**, and immediate sandbox exit.
Screenshot: `outputs/ses-production-approved-20260928.png`. No AWS settings were
changed and no message was sent. General sending remains disabled; approval does
not establish paid-receipt delivery or worker readiness.

FW-019 now requires explicit `BILLING_PROVIDER_MODE`, disabled by default, and
matching credentials before SDK/signature/webhook processing. New one-off invoices
freeze mode; recurring receipts use their immutable agreement binding. Historical
unclassified one-off evidence is not rewritten and cannot be processed as live.
Recurring live mode remains unsupported. A sanitized `check_billing_configuration`
command separates configuration, read-only evidence counts, mail configuration and
unverified launch gates. See the [decision](adr/2026-09-28-explicit-billing-provider-mode.md).

Test receipt previews now carry a Test Mode/no-real-money notice. Ordinary receipt
dispatch requires both live process mode and recorded live invoice mode; test or
unclassified receipts are refused without changing their queue rows or sending.
Invitation handling is unchanged. A controlled recipient-specific receipt delivery
rehearsal is still needed before monitored activation.

Actual restricted-role check found two test plan bindings, five open reservations,
two unclassified historical one-off invoices and nine queued receipts. All seven
recurring receipts rendered with test labels using explicit local preview sender
settings; the queue stayed unchanged. The isolated runtime correctly reports its
incomplete SES configuration. No database/schema or production deployment change.
Loopback review was restarted with new recurring authorization and mail still off.

Validation covered **218 tests**. The broad run passed 216 and found two mail-page
fixtures dependent on an absent collected-static manifest; those fixtures now use
ordinary test static storage. The final **47-test** mail/configuration/receipt rerun
passed. An earlier focused run also exposed a transport-failure fixture that now
explicitly uses mocked live mode to exercise the real-send path. No provider test
payment was retried or changed. See the
[readiness runbook](implementation/billing-provider-readiness.md).

## Refunded recurring agreement release and replacement safety (2026-09-28)

FW-019 adds an explicit Test Mode operator command to release a cancelled,
fully refunded agreement after all access reviews are complete. It compares the
complete provider invoice set and paid count, verifies refunds and order attempts,
then rechecks authority, Subscription revision and settlement under the Company
lock. Release and audit are atomic; provider writes and access changes are absent.
Unpaid/unknown attempts, scheduled tokens and unreturned periods stay reserved.
See the [decision](adr/2026-09-28-refunded-recurring-reservation-release.md).

Replacement creation reuses the durable request-key workflow. Its first verified
due payment can buy its exact period even when the refunded historical term had a
later end date, provided the cancelled Subscription still matches the release
review. Old agreement/payment/release replays cannot restore refunded access or
close the new reservation. The owner page explains closed agreement history.

Actual acceptance passed at **12:20 IST** on `annual_rehearsal`: agreement **4**
closed with release event **64**, using the ordinary owner and restricted runtime
role. Every Subscription/entitlement field, original dates and financial counts
were preserved; access remains read-only. Release and paid-cycle replay passed.
Browser verification shows closed-after-refund guidance and the original invoice.
No replacement mandate or charge was created in Razorpay during this increment.

The full **137-test** billing suite passed, followed by **12 release tests** after
the final other-invoice guard. Coverage includes exact shorter replacement periods,
provider mismatches/outage, unsettled attempts, stale review/authority, scan
completeness, rollback and immutable closed history. No schema change or production
deployment. New authorization/mail/callbacks remain off; catalog actor inactive.

Final GET after the scheduled start still shows the annual renewal Created/Issued
and the scheduled INR 5 authorization Created, with no scheduled invoice/access.
Both attempts remain preserved; support tickets 21146138 / 21146171 are pending.
Live-mode operations, receipts/SES, general replacement/prepaid policy and remaining
provider acceptance are open. See the
[checkpoint](implementation/recurring-agreements.md#refunded-agreement-release-and-replacement-2026-09-28).

## Scheduled billing tests, support cases and recurring refund acceptance (2026-09-28)

FW-019 now freezes an optional future `start_at` in the durable Test Mode creation
attempt, verifies it on provider observations/recovery, and rejects invoice periods
before it. Request-key replay preserves the original schedule without reposting.
The owner page distinguishes scheduled billing from authorization/token payment;
new authorization is blocked once a still-Created agreement's start has passed.
Existing prepaid/trial conversion remains excluded. See the
[schedule decision](adr/2026-09-28-scheduled-recurring-test-start.md).

With explicit owner authorization, submitted Razorpay support tickets **21146138**
(annual renewal) and **21146171** (failure simulation). Both submissions are visibly
confirmed. The existing support phone confirmation initially required a separate
automatic-approval clarification; the owner approved it and submission succeeded.
Razorpay indicates 4-8 business hours for an update, not resolution. The original
annual payment remains Created/Issued; its mandate remains Active and preserved.

A sixth fixture, `scheduled_start` (Workspace 7, agreement 6,
`sub_ThM7GiBY7yxoHg`), has the exact provider-verified start **12:20:21 IST** today.
Checkout showed the expected refundable INR 5 authorization. The bank-page handoff
opened blank and Checkout later reported failure, but API token payment
`pay_ThM8vfcR0fWZik` still reports Created without error. There are no provider
invoices or local paid access. No retry or cancellation was attempted. This is
**not** naturally due held-access acceptance and does not remove the October wait.
Resume with GET-only reconciliation of both pending attempts; never recreate them.

Recurring invoices now use a cycle-aware full-refund decision through the existing
owner review. Fresh provider/local full-refund evidence is mandatory. Retain access
preserves current terms; end access requires an ended provider mandate and the
exact current refunded cycle with no other unreturned paid periods needing protection.
Decisions/audits are atomic and replay cannot restore access. The reservation stays
held. See the [refund decision](adr/2026-09-28-recurring-refund-access-review.md).

Actual acceptance passed on the earlier cancelled `annual_rehearsal` agreement:
the owner performed Razorpay's final fictional refund confirmation after automatic
approval review required user handoff. Refund `rfnd_ThMJ3PKV1YHev4` is processed for
INR 17,688.20. Recording it preserved every Subscription/entitlement field. The
ordinary owner's browser decision then ended only this refunded term; purchased
dates and entitlement evidence stayed intact and the Workspace became read-only.
Provider invoice replay and review replay preserved that result and all counts.
Nine invoices/payments/queued receipts, seven cycles, one BillingResolution and
zero held-access resolutions remain in the isolated database.

All **127** agreement, owner, cycle, held-access, refund, existing review and recovery
tests pass after correcting two test fixtures (new provider refund read and explicit
Workspace context). Browser review and independent restricted-role acceptance passed.
No schema change or production deployment. New authorization/mail/callback/tunnel
remain off and the catalog actor is inactive. Replacement/reservation release,
live-mode operations, real receipts/SES and remaining provider acceptance are open.
Exact IDs, evidence and resumption steps are in the
[runbook](implementation/recurring-agreements.md#scheduled-start-support-and-refund-continuation-2026-09-28).

## Overdue payments moved off the dashboard (2026-09-28)

The dashboard keeps its overdue count card with **View overdue payments** and
omits the overdue table. The dedicated Workspace Loans page at
`/w/<slug>/loans/overdue-payments/` reuses canonical schedule-based queues,
20-loan pagination, existing repayment/review actions and incomplete-schedule
warnings. Other queues remain on the dashboard. Old `?queue=overdue` bookmarks
redirect while preserving page and activity-date parameters; the back link
restores the activity selection. No new financial calculations or schema changes.

All 38 focused operator-journey, counter-selector, batch/RLS and shell tests pass:
35 passed initially; three older journey fixtures passed after supplying the
existing required draft-submission token. New coverage verifies pagination,
empty/foreign Workspaces, data-view denial, anonymous access, GET-only behavior,
no-store responses, legacy redirects and the absence of dashboard loan rows.
Desktop and 390px mobile review confirmed usable links and no horizontal page
overflow; the table scrolls within its own container on narrow screens.

Deployed `rokkad:overdue-page-20260928-47571dab51d5` from the exact previous
public-pages image with six scoped application files. Original dashboard/view
fingerprints were checked before packaging; the Loans route was patched from
production to exclude unrelated local work. Fresh backup, startup, candidate
and live read-only restricted-role checks passed for JSK/JCL/Lakshmi. Counts at
verification were 1,277 / 1,998 / 2,114, with no excluded schedules. Live browser
review verified JSK's compact card, 20-row follow-up page and navigation.
Private release/rollback evidence is under `overdue-page-20260928/` on the server.

## Public legal policies and developer credits deployed (2026-09-28)

Replaced placeholder/duplicated privacy and personal-use terms with readable
business-software policies, and aligned cancellation/refund wording. The owner
approved the public operator/contact/address, seven-working-day refund review,
five-working-day approved refund initiation, and support-assisted closure with
no automatic deletion promise. Added `/developers/` and a shared footer link with
equal credit to Rajesh Rathod H and Dilip Kumar H and their supplied qualifications.
The [decision record](plans/public-legal-pages-review.md) records exact approvals,
operational follow-through and legal-review limitations.

All 23 public/auth and shell smoke tests passed; an existing homepage assertion
was updated to the current product-story markup. Desktop and 390px mobile browser
review confirmed readable layouts, equal cards, contact jump and footer links.
Whitespace and 580 documentation-link checks passed. Candidate and live checks
rendered all four public pages and JSK/JCL/Lakshmi workspace footers under the
restricted runtime role in a read-only transaction; all public HTTPS checks passed.

Deployed `rokkad:public-pages-20260928-e6c0045900ff` from the exact prior image,
changing only eight application files and reusing existing static assets. A fresh
operational backup and rollback compose snapshot are retained in private server
evidence under `public-pages-20260928/`. No schema or financial changes. The local
billing rehearsal banner and unrelated pending work were excluded. Publishing
these pages does not establish existing-customer acceptance or certify legal
compliance; mailbox monitoring and appropriate legal review remain operational
responsibilities.

## Loan form guidance decluttered and deployed (2026-09-28)

Preserved the existing loan form while replacing the two large introductory
panels with **How this works** and a compact **Metal prices** status row.
Process guidance and branch setup start collapsed; **+ Add customer** now sits
beside the Customer field and the photo rule sits in the Collateral section.
**Details** and **Recheck** remain available. Missing prices/policies, stale-price
or loan-date warnings, and request failures automatically expand price details.
Draft submission rules, form values/photos, and approval validation are unchanged.

All 92 focused Django tests and seven JavaScript event tests passed. Browser
review confirmed collapsed/expanded guidance, keyboard activation, healthy and
missing-price states, and desktop/390px mobile layouts without horizontal page
overflow. System, JavaScript syntax, whitespace and documentation checks passed.

Deployed `rokkad:loan-form-20260928-645aa7320997` from the exact previous image
with only four application files changed. A fresh static volume serves the
verified hashed price-check script. Backup, startup, candidate and live read-only
checks passed in JSK, JCL and Lakshmi; borrower totals and LTV guidance retain
their verified results. No schema or financial changes. Private deployment
evidence and rollback compose snapshot are under `loan-form-layout-20260928/`.

## Loan entry guidance, photo policy and app shell deployed (2026-09-28)

Delivered the [loan-entry improvement plan](plans/loan-entry-and-shell-improvements.md).
Photos are optional by default. **Loan setup → Loan entry** lets setup administrators
require a usable photo for every item before approval, including renewal successors;
drafts still save without photos. Approval freezes the applied rule. Optional
approvals permit an absent collateral image on tickets while unavailable/corrupt
selected images remain errors. Partial uploads retain the correct item association.
The new Loans-owned configuration table uses forced RLS and audited setting changes.

Borrower selection now shows all active-loan recorded principal, interest, fees and
total, with a details link and no partial/zero fallback for failed reads. LTV guidance
beside appraisal shows the actual policy percentage, eligible value and per-item
maximum, refreshing after appraisal/series/date/principal changes without filling
principal. Market-dependent methods explain missing same-day prices. Shared header
and footer retain the brand with compact navigation and real help/privacy/terms links.

All 254 targeted tests passed, covering draft/photo mapping, approval, renewal
rollback, ticket issue/reprint, RLS, settings permissions/audit, valuation, balances
and shell rendering. The final saved-loan wording correction passed all 21 collateral
media tests. JavaScript response-race/clear/failure checks, syntax, system, migration
drift, source-boundary, documentation and whitespace checks passed. Desktop and
390px mobile browser review confirmed navigation, borrower card, optional-photo
label and footer without page overflow.

Production image `rokkad:loan-entry-20260928-1b7e30d10d45` derives from the exact
previous image and contains only 31 reviewed application files; unrelated billing
work is excluded. Owner migration applied Loans 0028; runtime remains restricted.
Before/after backups passed. Candidate and deployed read-only checks passed in
JSK, JCL and Lakshmi; all remain optional by default. JSK P-000433 matches INR
15,676,540 recorded outstanding (about 0.22 seconds for the new panel). Live hashed
CSS/JS assets matched the release. No loan balances or issued documents changed.
Private release manifests, checks and rollback compose snapshots are under
`loan-entry-20260928/` in the production deployment directory.

## Party outstanding total corrected and deployed (2026-09-28)

Fixed the September 27 summary truncation: canonical active-loan balances are
summed before the history display limit. Party and its shared borrower-portal
selector now retain the full total even when only 20 rows are requested. Draft,
approved and closed records retain their existing balance semantics. The Party
page formats the total with Indian grouping and explains the limited row display.

All 64 focused selector, Party UI and portal tests pass, including more than 20
loans, zero-row display and mixed lifecycle states. System and whitespace checks
pass. Candidate and deployed restricted-role, read-only production checks confirm
JSK P-000433 has 303 active loans and INR 15,676,540 recorded outstanding, with
20 displayed rows. Its selector took 2.076 seconds after deployment; this minimal
fix retains per-loan canonical reads. JCL and Lakshmi party pages and independent
balance sums also pass. No financial records or schema were changed.

Deployed `rokkad:party-total-20260928-8d12cc28239b`, derived from the exact running
mail image with only the selector and Party template replaced. Unrelated local
subscription work was excluded; static volumes and production settings remain.
Pre-change server-only backup `production-20260927T204632Z.dump` passed archive
catalog validation. Deployment/source hashes and read-only evidence are private
under `party-total-20260928/` in the production deployment directory.

## Annual renewal pending; production critical path recorded (2026-09-28)

FW-019 continued in a fifth fictional recurring Workspace (`annual_completion`),
reusing the annual binding without administrator activation. Initial capture and
owner recovery passed, with six-seat paid access through 28 September 2027.
One accelerated final annual **Charge as Success** attempt remains Created and its
invoice Issued as of **01:34:08 IST**, after more than ten minutes. Agreement is
Active with paid_count=1; completion and annual renewal remain unaccepted. The
provider dashboard says bank authentication is pending and shows no test approval
action. No retry or premature cancellation was attempted.

Unpaid recovery left all Subscription/entitlement fields and money/receipt counts
unchanged. Current totals: nine invoices/payments/queued receipts, seven cycles,
zero resolutions. Four old mandates remain cancelled; the fifth stays active with
its pending payment preserved. Authorization, mail, callback/tunnel and catalog
actor are off; the bounded watcher exited. Resume with GET-only reconciliation
of the saved identities. No schema, production application change or live charge.

Added final-cycle/Completed-state regression coverage; all 56 cycle/owner tests
pass. Documented the [production critical path](plans/subscription-monetization-rollout.md#production-critical-path-reviewed-2026-09-28):
provider failure/recovery, due access, refunds/replacements, live-mode implementation,
receipts/SES, commercial review and monitored activation. Existing monthly holds
start 28 October, a fixture-dependent checkpoint, not a launch commitment. A
shorter scheduled-start test remains an unaccepted candidate.

The annual illustrative total exceeds Razorpay's INR 15,000 domestic-card
unattended-debit threshold; the customer AFA journey needs acceptance. That is not
a proven diagnosis of the pending simulator attempt. Both diagnostic support drafts
remain unsent. See [exact evidence and resumption steps](implementation/recurring-agreements.md#annual-final-charge-attempt-and-production-critical-path-2026-09-28).

## Annual recurring acceptance and invoice date fix (2026-09-28)

FW-019 now passes actual annual Test Mode authorization/capture, owner recovery,
repeat recovery and cancellation in a fresh fictional `annual_rehearsal` Workspace.
The frozen offer is INR 14,990 plus illustrative INR 2,698.20 tax, six total members,
with an explicit two-cycle test duration. Following owner approval, the isolated
passwordless catalog actor was enabled solely for binding and disabled immediately.

The real initial invoice exposed a duration bug: 28 September 2026 01:08:48 IST
through 28 September 2027 00:00 IST is slightly less than 365 elapsed days. Recovery
initially rejected it without local financial/access writes. Annual validation now
also accepts an exact next-calendar-anniversary midnight IST boundary when the
elapsed duration is strictly between 364 and 365 days. Provider dates remain exact;
other verification and future-access checks are unchanged. See the
[decision](adr/2026-09-28-annual-invoice-calendar-boundary.md).

After the fix, recovery recorded one invoice/payment/cycle/queued receipt and applied
paid access through the provider end, with six members. Repeated recovery and
post-settlement cancellation preserved all Subscription and entitlement fields and
financial counts. Independent restricted-role checks confirmed all four mandates
Cancelled with no next charge and retained local reservations. Current totals:
eight invoices/payments/queued receipts, six cycles, zero access resolutions.
Authorization, mail, callback/tunnel and the catalog actor are off. No migration,
production deployment or live charges.

Validation: 69 distinct cycle/access/owner tests pass across the main and focused
runs. The initial run found a missing Workspace context in the new test; after
correcting its setup, it and the additional future-annual replay test passed.
Coverage includes the real timestamp pair, leap/calendar boundaries, wrong seconds,
fixed provider timezone, duplicate recovery and future access remaining held.

Annual accelerated renewal/final-cycle completion remains untested. Actual
failure/Pending/Halted recovery, naturally due held access and other launch gates
remain open. The failure-simulation support draft remains unsent. See the
[annual rehearsal](implementation/recurring-agreements.md#annual-provider-acceptance-2026-09-28).

## Recurring failure rehearsal and owner guidance (2026-09-28)

FW-019 continued in a fresh fictional `failure_recovery` Workspace using the
verified monthly Test Mode binding and three-cycle agreement. Initial authorization
and capture passed, and owner invoice recovery created the initial period through
28 October with six members. Webhook/tunnel and mail stayed off throughout.

Selected **Charge as failure** exactly once on the active provider agreement. The
attempt remained Created for several minutes, became Authorized at 00:54:48 IST,
then was observed Captured at 00:55:08 IST. The invoice became paid and the agreement
stayed Active with paid_count=2. No completed failure, Pending or Halted state was
observed. This differs from the documented simulator expectation; the cause is
unknown. Failure/recovery acceptance therefore remains open. No repeat charge or
early cancellation was used to force an outcome.

Before settlement, actual unpaid-invoice recovery granted nothing and preserved
the saved Subscription, entitlements and financial/receipt counts. After capture,
owner recovery recorded the exact October-November period once with access held;
repeat recovery added nothing. Cancellation was requested only after settlement,
and independent GET confirmed Cancelled with no next charge. Existing paid access
and entitlements still match the pre-failure baseline.

Added owner guidance for verified Pending/Halted states and regression coverage
for failure/status recovery preserving paid access, grace/read-only boundaries,
future capture/replay and delayed Pending hints refetching current Active state.
All 50 recurring-cycle/owner tests pass. No schema change or production deployment.
Current isolated totals: seven invoices/payments/queued receipts, five cycles,
zero held-access resolutions. All three provider test mandates are cancelled;
new authorizations, webhook/tunnel, mail and live billing remain off.

A diagnostic support draft is saved locally, **not sent**. Next: clarify/reproduce
the Test Mode failure behavior before accepting actual Pending/Halted recovery;
annual recurring and naturally due held-period acceptance also remain open. See
the [rehearsal record](implementation/recurring-agreements.md#failure-simulation-continuation-2026-09-28).

## Explicit held-period access review (2026-09-28)

FW-019 adds `apply_recurring_period`, an owner/platform-authorized Test Mode
command requiring a reason and the reviewed subscription revision. It refetches
provider evidence and checks local refunds, current agreement, Workspace lifecycle,
plan, overlapping/newer terms and seat capacity before applying only a started,
unexpired held period. Exact saved dates and frozen entitlements are used; explicit
overrides and platform restrictions survive. Provider cancellation does not discard
paid time, but closed/replaced agreements remain blocked.

Migration 0017 adds one immutable access resolution per cycle with PostgreSQL
linkage/history guards. Application, before/after evidence and actor/reason audit
commit together. Repeated commands and payment replay never reactivate access.
Original invoices/cycles and renewal settings stay unchanged; no extra receipts.
Owner pages, invoice detail and newly rendered receipts recognize resolved holds.

Validation: 71 tests passed across held-access, recurring-cycle, owner and refund
review suites, then 39 held-access/checkout tests passed after three new boundary
cases (98 distinct tests overall). This includes restricted-role concurrent
application/immutability, refund and ownership races, rollback, stale review,
future/expired periods, first paid access and preserved platform restrictions.
Migration drift check passes. Migration 0017 was applied only to the isolated
billing rehearsal database and the local server restarted with authorization off.

Actual provider-backed verification refused the existing 28 October renewal today.
All Subscription/entitlement rows and financial/audit/receipt counts stayed
unchanged: five invoices/payments/queued receipts, three cycles, zero resolutions.
No rehearsal clock/provider dates were changed. The due-success path is tested
with isolated fixtures; it has not been exercised against a naturally due provider
hold. Both test mandates remain cancelled; webhook/tunnel, mail and live billing
remain off. No production deployment.

Next: remaining provider failure/pending/halted recovery and due-period acceptance.
See the [decision](adr/2026-09-28-held-recurring-access-resolution.md) and
[operator workflow](implementation/recurring-agreements.md#applying-a-held-period).

## Future recurring payment recorded with access held (2026-09-28)

FW-019 now records fully verified future recurring invoices as immutable paid
financial evidence, with `access_action=review` and an explicit future-period
marker. Existing subscription fields and entitlements remain unchanged. Owner
pages, invoice detail and receipts explain that reaching the start date or replaying
the invoice does not activate held access. Review payments remain visible across
older/replaced agreements through a paginated Workspace list. A first future
payment creates only a non-active financial parent, with no trial or entitlements.

Actual owner recovery recorded the captured INR 1,768.82 Test Mode renewal for
28 October through 28 November once. Repeat recovery added no duplicate records.
Independent restricted-role verification compared the entire existing Subscription
and entitlement rows with their pre-recovery snapshot: unchanged, with paid access
still ending 28 October. The isolated database now has five invoices/payments/queued
receipts and three recurring cycles. Receipt wording was rendered and verified;
email dispatch remains off.

Validation: 70 recurring-cycle/owner/checkout tests passed, followed by three
focused passes for the refined annual and owner-page cases, including one new
pagination test (71 distinct tests overall). Coverage includes future monthly and
annual periods, signed replay, replay after start/refund, rollback, manual-term
protection and restricted-role concurrency. No schema changes. Both provider test
mandates remain cancelled; new authorization, webhook/tunnel, mail and live billing
remain off. No production deployment.

Next is an authorized, audited workflow to apply eligible held periods when due;
failure/pending/halted recovery and remaining provider acceptance also remain open.
See the [decision](adr/2026-09-28-future-recurring-payment-evidence.md) and
[acceptance record](implementation/recurring-agreements.md#future-period-financial-recording-2026-09-28).

## Renewal diagnosis and unpaid-invoice recovery (2026-09-28)

FW-019 continued with a fresh fictional three-cycle monthly agreement in
`renewal_followup`. Initial card authorization/capture passed again. With the
temporary webhook disabled, owner recovery fetched the paid invoice and created
one cycle/invoice/payment/queued receipt, proving actual missing-webhook recovery.
Authorization alone created no paid access. The new paid period is 28 September
00:16:47 IST through 28 October 00:00 IST, six members.

The previous fixture's pending renewal later failed with
`card_mandate_not_active`; its earlier cancellation prevents attributing that
failure to the simulation alone. On the fresh active agreement, **Charge as Success**
was requested exactly once. The payment stayed Created for several minutes, then
captured successfully about six minutes later: paid invoice, two total provider
captures and paid_count=2. An intermediate token read reported Failed alongside
recurring Confirmed; that did not predict the final payment result. Do not cancel
or re-charge merely because the simulator is slow.

The accelerated paid invoice covers 28 October to 28 November, still in the future.
Actual owner recovery correctly rejected it under the existing started-period
rule. It is retained in provider/local diagnostic evidence, not a local paid cycle;
only the initial period remains applied. Future-period financial recording/access
requires a reviewed implementation before full renewal acceptance. After capture
settled, owner cancellation succeeded and independent GET confirmed cancelled.

Owner recovery of the unpaid invoice preserved paid access and financial/receipt
counts. Improved its generic invalid-identity error to explain that Razorpay has
not marked the invoice paid and existing access is unchanged. All 39 paid-cycle/
owner tests pass, including a new no-write recovery regression; the actual browser
also displays the improved message. No schema change. New authorizations are
disabled again; webhook/tunnel, mail dispatch and live billing remain off.
See the [diagnostic continuation](implementation/recurring-agreements.md#renewal-diagnostic-continuation-2026-09-28)
for retained evidence and remaining work. The provisional support draft was marked
superseded without sending it. No production deployment.

## Actual recurring Test Mode initial payment and cancellation (2026-09-28)

FW-019 provider rehearsal passed initial Checkout authorization, captured monthly
payment, signed webhook processing, known-invoice recovery and owner cancellation
in a fresh fictional Workspace. The explicit three-cycle test agreement used
INR 1,499 plus illustrative 18% tax, six total members and no provider customer
notifications. This test duration does not define the commercial offer.

Exactly one recurring cycle/invoice/payment and one queued receipt were added.
The verified paid period is 28 September 2026 00:01:43 IST through 28 October
2026 00:00 IST. Same-event and new-event-ID signed replays returned 200 without
duplicating records/access; conflicting reuse returned 400. The early capture
callback initially lacked explicit invoice billing timestamps and failed closed;
Razorpay's retry succeeded after those fields appeared. All received events are
now processed. No dates were inferred and no verification rules were weakened.

Actual owner cancellation produced one request, dispatch and confirmation;
independent provider reads and the cancellation webhook confirmed cancelled.
Local paid access remains active through the verified end, with six members.
The agreement reservation remains held for financial reconciliation.

Renewal acceptance is incomplete. Dashboard **Charge this now > Charge as failure**
issued an unpaid future-period invoice but left its payment attempt Created, with
no completed failure/pending event observed. Provider current-period dates advanced;
Rokkad correctly retained the original paid dates. Successful subsequent collection,
completed failure/pending/halted recovery and accelerated future-period handling
still need acceptance. The cancelled fixture must not be reused as a renewable
agreement or force-cleared. See the [evidence and next steps](implementation/recurring-agreements.md#actual-provider-rehearsal-2026-09-28).

Cleanup verified: Test webhook disabled, tunnel/callback stopped, local recurring
flag false, fictional non-login catalog operator inactive, restricted runtime
retained. Review server remains on loopback port 8083. Previous Orders evidence
is intact; database totals are three invoices/payments/queued receipts and one
recurring cycle. No email dispatch, live money or production change. This increment
changes documentation/evidence only; current documentation links and scoped
whitespace checks pass. Full FW-019 and commercial launch remain open.

## Recurring owner authorization and cancellation (2026-09-27)

Continued FW-019 with an owner page for prepared Test Mode agreements: frozen
price/tax/member count/duration, gated Checkout authorization, provider status,
paid periods and recovery of a known paid invoice. Server-held subscription IDs
anchor signature verification; authorization alone grants no access. Failed browser
confirmation retries the same identity. The old placeholder cancellation button
now links to the real recurring flow.

Cancellation saves immutable request and dispatch evidence before contacting
Razorpay. Post-commit delivery cancels future charging immediately, verifies the
result independently and preserves purchased access. Concurrent requests, timeout
and local persistence failure cannot reissue the POST. Unknown results remain
visibly pending; a command recovers undelivered requests or fetches a dispatched
outcome. The agreement reservation remains for financial reconciliation. Canonical
ownership, CSRF and explicit Workspace transaction/RLS boundaries remain intact.

Validation: 76 backend tests pass across the runs (15 owner/cancellation, 23 paid-cycle,
14 agreement and 24 Orders tests), including restricted-role concurrent cancellation, plus two real
Checkout-script retry tests. Isolated browser review exposed missing local source
assets; the billing rehearsal settings now serve them with WhiteNoise finders.
No new schema, provider recurring object, real payment, email dispatch or production
deployment. The local database still has no prepared agreement and the recurring
flag remains false. Browser review covers the empty owner page; prepared states
and provider failures are covered by mocked automated tests.
Owner/operator/webhook status writes also reject delayed nonterminal observations
after a terminal mandate state while preserving late financial-evidence review.
Schema drift, diff whitespace and current documentation links also pass.

See the [decision](adr/2026-09-27-recurring-owner-actions.md) and
[runbook](implementation/recurring-agreements.md#owner-authorization-and-cancellation).
Next is real recurring Test Mode acceptance in a fresh fictional Workspace;
operator preparation needs an explicit test duration. Self-service creation,
scheduled conversion, financially settled reservation release, final recurring
refund access review and commercial launch review remain pending.

## Verified recurring paid cycles and recovery (2026-09-27)

Continued FW-019 with immutable RecurringCycle evidence linked to ordinary
Invoice/Payment records. The signed webhook and owner recovery command fetch
provider agreement, plan, invoice and payment, verify identity/amount/currency/
settlement and the purchased period, then atomically record payment, exact paid
dates, entitlements, audit and durable receipt intent. Different event IDs cannot
duplicate a cycle; overlapping periods fail closed. Older cycles cannot shorten
or reactivate newer paid access. Creation can remain disabled while known Test
Mode payment evidence is recovered; live keys are rejected.

Authorization and failure/cancellation lifecycle events only record verified
provider observations, with no invented human actor. Shared refund evidence
preserves newer paid terms; the manual end-access action rejects recurring cycles
pending separate agreement/cancellation review. Closed/replaced agreements,
archived Workspaces and conflicting terms retain paid financial evidence with
access held for review. Receipts now distinguish recurring periods from one-off
purchases. No owner recurring Checkout/cancellation UI is exposed yet.

Validation: 23 paid-cycle tests pass, including signed replay, annual/monthly
periods, missing-event recovery, atomic rollback, refunds, grace/read-only,
cross-Workspace guards, receipt wording and restricted-role concurrent capture.
The 65 existing agreement/Orders/recovery/review tests also pass. Schema drift,
diff-whitespace and current-doc links pass. Applied Subscriptions 0015/0016 only
to the isolated local billing database, checked restricted role reads and restarted
its review server. Agreement/cycle tables remain empty, creation flag false and
the two previous Orders invoices/payments intact. No recurring provider object,
real payment, email dispatch or production deployment occurred.

See the [paid-cycle decision](adr/2026-09-27-recurring-paid-cycles.md) and
[runbook](implementation/recurring-agreements.md#paid-cycle-processing-and-recovery).
Owner authorization, confirmed cancellation, scheduled transitions from existing
paid terms, recurring refund-access review and real provider acceptance remain.

## Recurring agreement foundation and durable recovery (2026-09-27)

Continued owner-selected FW-019 with frozen provider-plan bindings, durable
Workspace agreement attempts and append-only actor/recovery evidence. The
operator command commits its attempt before a bounded provider create call;
timeout, invalid response and post-success local failure cannot cause an automatic
second creation. Recovery fetches the known subscription and plan and verifies
Workspace/attempt notes, terms and provider identity. One open agreement per
Workspace is enforced in PostgreSQL and shares the Company lock with manual
checkout exclusion. Provider mandate status never writes paid access or receipts.

Preparation is default-off and Test Mode-only. Canonical owners/platform operators
retain their existing boundary; catalog registration requires platform authority.
New immediate agreements reject existing paid/trial time, legacy mandates,
outstanding invoices, non-active Workspaces and excess members/invitations.
No customer Checkout/cancellation route or paid-cycle grant is enabled.
See the [decision](adr/2026-09-27-recurring-agreement-evidence.md) and
[operator runbook](implementation/recurring-agreements.md).

Validation: 14 recurring tests pass, including concurrent in-flight attempts,
uncertain-provider and local-commit recovery, tenant authorization and restricted
runtime evidence guards. All 24 existing Orders checkout tests pass. Migration
drift check and current-doc link check pass. Applied Subscriptions 0013/0014 only
to the isolated loopback billing rehearsal database; restricted role reads pass,
new tables are empty and recurring flag remains false. Restarted its local review
server. No provider recurring object, production migration/deployment, customer
charge, new access or email was created. Paid-cycle processing, owner authorization,
confirmed cancellation and real recurring acceptance remain the next FW-019 work.

## Razorpay Orders provider rehearsal passed; presentation/retry fixes (2026-09-27)

The owner created the Test Mode webhook. In the isolated billing database,
Razorpay wallet simulations captured INR 1,768.82 monthly and INR 17,688.20 annually
(agreed base prices plus illustrative 18% test tax). Signed provider webhooks
created two paid invoices, two payment records, two purchased terms, six-member
entitlements and exactly two queued receipts. The annual term appends twelve
months after the monthly end, through 2027-10-27. Automatic renewal remains false.

A rejected international test card produced a processed payment.failed event and
no access/payment/receipt. Domestic card/netbanking attempts did not complete;
wallet with simulated OTP succeeded. Do not claim all payment methods accepted.
The annual browser confirmation encountered a temporary provider read failure;
its signed capture still committed. Owner-authorized reconciliation fetched actual
provider evidence and confirmed the same payment without extending access again.

Same-event and different-event-ID capture replays changed no term, payment or
receipt; conflicting payload reuse returned 400. Simulated monthly refunds of
INR 100 and INR 1,668.82 reached processed state and were independently verified
by the app. Replays retained two refund rows and INR 1,768.82 total. The newer paid
annual term remained active and unchanged; no final refund access decision was
fabricated. No failed webhook rows remain.

Fixed dashboard/detail templates that read nonexistent is_paid/paid_date fields;
paid invoices now show canonical status/date. Annual details use the frozen billing
cycle instead of a hard-coded monthly description or nonexistent period fields.
Checkout now switches to Retry payment confirmation after a provider response:
it reuses payment identity/signature, disables cycle changes and never creates
another order on retry. Two Node tests execute the actual script with simulated
provider/network confirmation errors and verify one order, identical retries and
successful redirect. Real isolated invoice rendering checks passed. See the
[rehearsal runbook](implementation/billing-test-rehearsal.md) for acceptance limits
and cleanup. No live money, production data, deployment or general mail sending
was changed. Recurring mandates/cycles/cancellation remain separate FW-019 work.
The temporary Test Mode webhook is disabled and its tunnel/callback are stopped;
the isolated local billing page and database remain available for review.

## Party outstanding summary truncation confirmed (2026-09-27)

Read-only restricted-runtime production reconciliation for JSK borrower
P-000433 confirms 303 ACTIVE loans, while Party's summary displays and sums only
the latest 20: INR 783,500. All active loans have canonical recorded principal
INR 14,328,300, interest INR 1,348,240 and fees zero, total INR 15,676,540.
The omitted 283 loans explain the INR 14,893,040 difference.

Root cause: `get_party_pawn_loan_history_summary` calculates `active_outstanding`
from `active_rows` after applying `active[:limit]`, while its count uses all loans.
The shared portal selector also consumes this truncated total. Correction remains
pending: aggregate every applicable loan independently of displayed row limits,
retain canonical balance derivation, and cover more-than-20-loan regressions.
These are recorded balances, not a current payoff/interest-projection quote.
Investigation changed no application code, production data or deployment.

## Isolated billing runtime and signed HTTPS callback ready (2026-09-27)

Created an empty dedicated loopback PostgreSQL database and migrated it through
Subscriptions 0012 with the owner-only migration settings. Restricted runtime
checks passed; fictional ordinary owner and unpublished six-member test offer are
seeded only there. The local checkout opens with the agreed prices, illustrative
18% tax and a clear Test Mode banner. DPAPI test keys and separate local signing
secrets stay outside OneDrive; email dispatch and live checkout remain off.

Added guarded billing rehearsal settings and a callback-only WSGI listener. After
explicit owner approval of Cloudflare transmission, a temporary HTTPS tunnel
passed unrelated-path 404, unsigned-callback 400, signed synthetic event 200 and
replay 200 checks. These are transport tests, not provider-payment acceptance.
Prepared the four supported events in Razorpay Test Mode; owner secret entry and
submission are pending under the browser credential-entry handoff rule. Ten helper
and five rehearsal-settings tests passed. See the [runbook](implementation/billing-test-rehearsal.md)
for boundaries, startup, cleanup and remaining capture/refund/receipt acceptance.

## Razorpay account approved; all test API access checks passed (2026-09-27)

The owner reports account approval with both Live and Test modes activated,
test keys generated and Subscriptions visible. Live-key generation is unknown;
no live keys were requested or accessed. At 16:56:35 UTC, decrypted the previously
saved test credentials only in process memory and performed bounded read-only
requests: Payments, Plans and Subscriptions all returned HTTP 200. The earlier
endpoint-specific 401 obstacle is resolved; no further rotation or support
escalation is needed on that evidence. No credentials or entity bodies were printed.

Updated the rollout, active/future registers and stable memory. This verifies
test API access, not checkout/webhook/renewal acceptance. No provider object,
payment, database or deployment setting was changed; production checkout remains
disabled. Next delivery remains isolated test runtime and provider rehearsal,
with recurring implementation still outstanding.

## Razorpay support authentication advice checked against identical requests (2026-09-26)

The owner relayed support's generic advice to regenerate/use Test Mode keys.
Reproduced the discrepancy at 15:19:40 UTC with the already-regenerated pair:
Payments HTTP 200, Plans and Subscriptions HTTP 401. All requests used identical
Basic Authorization headers, the same HTTPS API host, no redirects and no proxy
environment inheritance. Razorpay's Python SDK `client.plan.all` also returned
HTTP 401 with identical authentication. Sanitized evidence contains only endpoint,
timestamp, status, authentication-equality booleans and SDK exception type; no
credential or provider entity bodies. No allowlisted request-ID header was returned.
Prepared a technical-support escalation recommendation; no message sent by agent.
The endpoint-specific denial's root cause is still unconfirmed. No key rotation,
payment, subscription or runtime change was made.

## Regenerated test credentials verified and encrypted; Subscriptions API unavailable (2026-09-26)

Privately imported the owner's regenerated Downloads CSV. The same test key pair
returns HTTP 200 from `GET /v1/payments?count=1` but HTTP 401 from both Plans and
Subscriptions list endpoints. Core authentication is valid; the earlier blanket
authentication-failure conclusion was incorrect because it used a product-specific
endpoint. Do not request another regeneration on this evidence. The reason for
product-specific denial still needs Razorpay confirmation; dashboard visibility
does not establish API access.

Updated both credential helpers to verify the core Payments endpoint; all five
focused helper tests passed. Reverified the Payments collection response and saved
the whole credential with current-user Windows DPAPI outside OneDrive. No values
were printed, source CSVs are unchanged, and no payment/subscription was created.
The form listener/tab are closed. Existing prepaid checkout can proceed toward
isolated provider rehearsal; recurring acceptance additionally needs the API-access
issue resolved. Live activation and production checkout remain unconfirmed/disabled.

## Test credential CSV read; provider authentication rejected (2026-09-26)

The owner supplied an exact CSV path in Downloads as the preferred credential
handoff. Read it privately in memory, validated one row and a test-mode Key ID,
and attempted the fixed read-only Razorpay plans endpoint. The sanitized diagnostic
returned HTTP 401. No credential contents or provider response bodies were printed;
no encrypted credential was saved because verification failed. Original CSV is
unchanged. Stopped the form listener and closed its Chrome tab. API access remains
unverified; check the current Test Mode key pair/account before the next attempt.
No payment, subscription, database or production setting changed.

## Credential form Chrome submission corrected (2026-09-26)

The owner twice reported submitting the form, but no successful save was recorded.
Browser inspection first found an invalid root URL and then a rejected POST.
The form's no-referrer policy was incompatible with its strict Origin check in
Chrome. Changed the policy to same-origin, preserving Host/Origin/token checks and
withholding referrers from other origins. Added sanitized rejection diagnostics
and a regression assertion. Five tests passed; a real Chrome submission using an
invalid dummy key now passes the request guard and reaches credential validation
without any provider call or save. The corrected empty form is reopened for owner
entry. Actual API verification/save remains pending; no credentials were exposed.

## Browser-based private test-key entry ready (2026-09-26)

The direct terminal attempt also appeared blank to the owner. Added
`scripts/razorpay_test_key_form.py` and opened its loopback-only temporary form in
Chrome for owner entry. Both fields are masked; token/Host/Origin validation,
bounded requests and no-store/CSP headers protect the form. Test IDs only, fixed
read-only Razorpay verification, no redirects/proxy inheritance, sanitized status
and Windows DPAPI encryption keep credentials outside chat, logs and OneDrive.
The helper refuses overwrite and stops after success or a 15-minute timeout.
Five focused tests passed and Windows encryption smoke-check passed. The empty
form rendered in Chrome and is retained for handoff. Credential verification/save
is still pending owner entry; no payment, subscription or production change.
See [the entry procedure](plans/subscription-monetization-rollout.md#test-mode-preparation).

## Razorpay private test-key entry prepared (2026-09-26)

The owner generated and saved test keys. Added the Windows interactive helper
`scripts/save_razorpay_test_credentials.ps1`: test-ID guard, fixed read-only HTTPS
plan request with no redirects, sanitized outcome, user-restricted directory and
DPAPI-encrypted credential outside OneDrive. It refuses existing-file overwrite
and never prints secrets or provider response bodies. PowerShell parsing passed;
the tool-launched prompt was not visible to the owner, so direct interactive
launch from Windows Run is the next step. No successful API authentication
or local credential save has yet been recorded.

Docker daemon is unavailable. A read-only check confirms the existing migration
connection uses loopback PostgreSQL and its owner can create an isolated database.
No database, runtime, HTTPS callback or production setting was changed. See the
[setup procedure](plans/subscription-monetization-rollout.md#test-mode-preparation).

## Razorpay test dashboard access confirmed by owner (2026-09-26)

The owner confirms Test Mode offers API-key generation and Payment Products ->
Subscriptions opens. Keys are not yet generated. This establishes dashboard
availability, not successful API authentication, recurring payment acceptance or
live activation. The documented local Compose stack separates development data,
but no payment rehearsal runtime/HTTPS callback has been started or verified.
No credentials were accessed and production checkout remains disabled. Updated
the [test-mode checkpoint](plans/subscription-monetization-rollout.md#test-mode-preparation).

## Razorpay SaaS reclassification and KYC reported complete (2026-09-26)

The owner reports Razorpay successfully reclassified Rokkad as software (SaaS),
allowed application submission and completed KYC. This resolves the previous NBFC
document obstacle for submission. The owner believes test access is available;
Dashboard/API access, Subscriptions availability and live activation have not been
independently verified. FW-002 preparation resumes under selected FW-019. Updated
the [test-mode preparation](plans/subscription-monetization-rollout.md#test-mode-preparation)
with mode/key checks, isolated runtime and existing checkout acceptance before
recurring acceptance. No keys were accessed, provider calls made, settings changed
or live checkout enabled.

## Razorpay onboarding requests NBFC evidence (2026-09-26)

The owner reports starting Razorpay onboarding, verifying rokkad.com and receiving
a request for an NBFC registration certificate or service level agreement with an
NBFC-certified company. Activation is unconfirmed. Recorded this checkpoint in the
[active rollout](plans/subscription-monetization-rollout.md#provider-onboarding-clarification).
The intended collection is B2B software subscription fees, not borrower funds.
Provider category review is recommended; the selected category and applicant legal
entity still need confirmation. No support message, document submission, website
change or live billing activation was performed.

## FW-019 selected; offer preparation validated locally (2026-09-26)

The owner started [subscription monetization delivery](plans/subscription-monetization-rollout.md),
confirmed working INR 1,499/month or INR 14,990/year prices and clarified owner
plus five staff (six members total). Prices remain unpublished. No Razorpay
merchant account exists yet; provider acceptance still precedes paid onboarding.

The first local increment removes fixed prices from tier labels and the fixed
20% annual-discount claim. Plan cards calculate actual annual savings (INR 2,998
for this offer), explain owner-inclusive member limits and tax-exclusive prices,
and stop advertising universal 14-day trials when disabled. Subscription migration
0012 updates choices/help text only; no catalog rows or purchased terms are repriced.
The legacy missing-annual-price fallback is unchanged; use the explicit agreed
annual amount. No migration was applied to the ordinary development or production
database, and no plan was seeded or activated.

All 28 focused tests passed with
`python manage.py test apps.subscriptions.test_plan_pricing apps.subscriptions.test_checkout --settings django_project.settings.test --noinput`
using `.venv314`: actual/absent annual savings, disabled checkout/trial presentation,
configured trial duration and both agreed prices with a six-member frozen
entitlement, alongside existing checkout verification/replay/rollback coverage.
Provider calls remain mocked. Documentation links passed. The active rollout
records recurring contracts, paid-cycle processing, cancellation, recovery and
provider/pilot acceptance as remaining work. No deployment, real charge or
automatic renewal was performed; production checkout remains disabled.

## Subscription monetization proposal captured (2026-09-26)

Recorded [FW-019](plans/future-work.md#fw-019-workspace-subscription-monetization-and-razorpay-automatic-renewal)
at the owner's request: per-Workspace monthly/yearly subscriptions, proposed
INR 1,499/month or INR 14,990/year with five seats, separately quoted onboarding
and messaging, and Razorpay automatic renewal. Prices are validation candidates,
not published commitments. Captured the existing one-off checkout foundation,
recurring billing gap, cancellation/payment recovery, access continuity, provider
fee references and pilot acceptance. FW-002 provider acceptance remains shelved
and required before paid onboarding; storage billing depends on FW-015 metering.
Documentation only; no implementation, provider setup or billing activation.

## Blog, community forum and support tickets captured (2026-09-26)

Recorded three unscheduled ideas at the owner's request in the
[future-work register](plans/future-work.md): FW-016 product blog, FW-017 community
forum and FW-018 private support ticket system. Captured publishing/moderation,
ticket handling, access boundaries and links to existing operator, email and media
work. No implementation, provider selection or deployment changes.

## R2 cleanup and Workspace storage metering captured (2026-09-26)

Added [FW-015](plans/future-work.md#fw-015-safe-orphan-media-cleanup-and-workspace-storage-usage)
at the owner's request: inventory reported orphaned R2 media, provide safe reviewed
cleanup, and track/display per-Workspace storage with auditable measurements for
potential future billing. Includes historical/reference protection, retention,
concurrent uploads, tenant isolation and explicit handling of unassigned bytes.
Unscheduled documentation only; no R2 inspection/deletion, runtime change, quotas
or billing activation. Coordinate with platform operations (FW-010) and complete
Workspace archives (FW-012).

## Platform email operational acceptance passed; dispatch paused (2026-09-26)

Added private deployment-operator queue inspection and recipient suppression with
operator/reference audit attribution, preserving existing bounce/complaint reasons.
No new platform-superuser account, Workspace endpoint or permission was created.
Rejected feedback now exits nonzero while valid events still commit and acknowledge;
invalid events remain available for retry/dead-letter handling.

Worker-only image `rokkad:mail-ops-20260926-1b55551552cd` is installed on the
existing three services. Web remains `rokkad:mail-20260926-2f39723e810c`.
No schema change or web restart. The five-minute health timer is enabled; dispatch,
feedback and recovery timers remain disabled after bounded scheduling tests.
Both sending gates remain off. Private journal/health alerts latch worker failures
until reviewed; this is local operator monitoring, not external paging.

Live acceptance proved paused dispatch skips execution, feedback/recovery run,
synthetic worker failure reaches the alert hook and health check, and explicit
acknowledgement restores healthy status. The existing simulator suppression was
rechecked through the audited operator command. Delivery hashes and attempt count
were unchanged; no emails were sent. Source and dead-letter SQS console counts
were both zero available/zero in flight. Automatic DLQ monitoring is not installed;
the operator procedure includes a manual AWS console check.

All 61 focused mail, operations, watchdog and checkout tests passed, including an
isolated checkout-to-paid-receipt-to-delivery workflow and duplicate prevention.
Payment/SES boundaries in that workflow are mocked; it is not a real payment or
a live paid-receipt email. Prior live billing-sender transport proof remains separate.
Private manifests, original service units and `operations-acceptance.json` remain
under server `platform-mail-ops-20260926/`; no sensitive evidence was copied locally.
See the [operator procedure](implementation/platform-mail.md#operator-checks-and-stop-mail-requests).
SES approval and a fresh bounded activation review remain; approval alone must not
enable sending. These working-tree changes have not been committed or pushed.

## JCL mixed-metal ticket weight fit corrected (2026-09-26)

Reproduced C07565's production print failure: the weight field at (25,130) mm
contained two metal totals, but its 10 mm height, 6 pt padding and fixed 12 pt
leading with WRAP could not fit both lines. Published JCL layout revision 4
from revision 3 through the audited template services, retaining the paper
profile and all frame geometry. Only this field now uses 10 pt text, zero
padding, automatic leading and SHRINK (existing 6 pt minimum).

Restricted-runtime official-mode rendering passed for both C07565 copies and
four single-/mixed-metal cases, preserving full weight precision. Visual review
confirmed both actual weight lines clear the printed border at 10 pt. All active
JCL series resolve the corrected revision. Loan, event, approval, issue and
number-sequence row hashes were unchanged; no ticket was issued on the user's
behalf. No application deployment or schema change was needed.

Layout hash: `7978427b752a8206f9033f2c5a5f34c00d0634680fb1c45f8a90834d2b5c2c7d`.
Server-only pre-change backup `production-20260926T125152Z.dump` passed archive
catalog validation. Earlier published layouts and issued PDF artifacts remain
intact. Physical printer acceptance remains with the user.

## External combined alias test received (2026-09-26)

After explicit approval resolving the earlier personal-mailbox access block, sent
exactly one clearly labelled test from the owner's Gmail to `support@rokkad.com`
and `billing@rokkad.com`, reference `ROKKAD-ALIAS-20260926`. Confirmed Gmail's sent
acknowledgement and the matching message in the **admin inbox**, with both aliases
in To. Original receiving headers show `Delivered-To: support@rokkad.com` and
SPF/DKIM/DMARC PASS for the external Gmail sender. This proves external receipt
through support into the intended mailbox; the combined message does not isolate
the billing alias's independent envelope-delivery path. Both aliases' configuration
and their respective application Reply-To selections were already verified.

Personal mailbox inspection was limited to the compose controls and the exact
test search; no unrelated personal messages were opened. No second message,
branch/customer data, payment or sending-configuration change. SES approval and
operator opt-out/alert acceptance remain outstanding; general dispatch stays off.

## SES production access requested; invitation acceptance verified (2026-09-26)

With explicit terms/acknowledgement approval, submitted Mumbai SES production
access for transactional mail, website `https://rokkad.com`, contact
`admin@rokkad.com`, English. Console confirmed submission and **Under review**.
AWS case **179042575700203** requested sending frequency, recipient sourcing,
bounce/complaint/unsubscribe handling and examples. Submitted a factual response
covering event-triggered requested team invitations and paid SaaS receipts, low
initial volume without an invented numeric forecast, source-backed queue/retry
controls, verified domain/authentication and simulator results. No marketing,
borrower campaigns, real customer records, credentials or live invitation tokens
were shared. The response distinguishes planned human opt-out handling from the
implemented automatic bounce/complaint suppression; it does not claim a marketing
unsubscribe interface. Provider approval is still pending.

Completed the received invitation through ordinary Google sign-in as
`admin@rokkad.com`, then explicitly accepted the Viewer invitation. Server read-only
verification confirms a verified email, accepted invitation and exactly one
membership: Viewer in the isolated test Workspace. Its lack of a subscription
correctly blocks business screens; no trial/payment was fabricated to bypass it.
Restored the original owner's Google session after testing. Evidence remains
server-private in `acceptance/invitation-accepted.json`.

Reply composers selected `support@rokkad.com` and `billing@rokkad.com`; labelled
self-mailbox reply tests were sent. This is not proof of external alias delivery.
Automatic approval review blocked inventory of the owner's personal Gmail session
because existing permission covered the admin mailbox. A specific request for one
external message to both aliases is pending; no personal mail was inspected.
General mail dispatch/timers remain disabled. After approval, finish external
alias delivery, operator opt-out/alert handling and bounded monitored activation.

## Controlled SES delivery and feedback tests passed (2026-09-26)

With explicit recipient/test approval, verified `admin@rokkad.com` in Mumbai SES,
created the empty **Rokkad Email Acceptance — TEST** Workspace and a Viewer
invitation through the normal services. No branch/customer data or branch access
was used. The first two inbox attempts were definitively rejected; a diagnostic
retry exposed missing IAM access to the sandbox recipient identity. With explicit
approval, saved policy version 2 adding only that identity, the two existing From
addresses, the admin recipient and Mumbai, expiring **2026-09-28 00:00 UTC**.
No wildcard grant, new key or sender was added. The third attempt was accepted;
one invitation arrived, with SES Send/Delivery reconciled to its existing attempt.

The separate billing-sender test arrived and explicitly said **no payment was
taken**, not an invoice/receipt. No invoice, payment or subscription was fabricated
or modified. Its transport/event evidence is server-private, separate from the
application's source-backed receipt queue; this proves sender/transport, not a
real paid-receipt workflow. Both inbox messages passed Gmail SPF, DKIM and DMARC,
used `bounce.notify.rokkad.com`, TLS, and the correct support/billing Reply-To.
Billing Send/Delivery feedback was also correlated and acknowledged privately.

AWS simulator hard-bounce and complaint tests reconciled through the normal
consumer, persisted recipient suppression and refused retries without another
transport attempt. A later Delivery event did not overwrite Complaint. An initial
suppression probe hit the expected duplicate-invitation constraint and rolled back;
the corrected probe reused existing test records. No app code change was needed.

The received invitation points to canonical HTTPS rokkad.com. Opening it in the
existing owner's session correctly rejected the different recipient identity;
acceptance as admin@rokkad.com is still pending. Human reply round trips, supervised
ongoing dispatch/alerts and SES production access remain pending. Automatic sending
and all timers remain disabled. A one-shot run of the installed feedback service
completed successfully with exit 0; the dispatch enablement marker is absent.
Synthetic evidence/scripts stay private on the
server; no token/key or database backup was copied into the repository.

## Platform mail deployed with sending disabled (2026-09-26)

After explicit approval, created `RokkadPlatformMailRuntime` and programmatic user
`rokkad-platform-mail-runtime`, with no console access and only that policy.
Transferred its single access key through a one-use loopback form and SSH to
`/root/rokkad-platform-mail.env`; verified root ownership/mode 0600 and the expected
AWS identity through STS. No local credential file/download or key output; clipboard
cleared and receiver stopped. Web does not receive these dedicated AWS credentials.

Built and deployed `rokkad:mail-20260926-2f39723e810c`, an application-only overlay
on `0f582472`, with exact source/archive manifests retained privately on the server.
This is a manifest-identified working-tree candidate, not a new Git commit or push.
The code is the previously validated 217-test implementation. Server-local backups
completed before/after; owner migration applied only `platform_mail.0001_initial`,
with no historical replay. Restricted runtime checks confirm NOSUPERUSER/NOBYPASSRLS,
empty mail tables before reopening, valid status template and startup guards.

Dedicated offline settings are ready with canonical rokkad.com links, the two
notify.rokkad.com senders and support/billing Reply-To aliases. Scoped SQS receive
succeeded (zero events). The deployed login page returns HTTP 200. Dispatch,
feedback and recovery systemd service/timer units validate; all timers are disabled.
Dispatch also requires a separate root-owned enablement marker, currently absent.
`PLATFORM_EMAIL_ENABLED=False` remains in the public and private worker settings.

No test/application messages were sent. SES remains sandboxed; controlled inbox,
reply, provider-event, bounce/complaint and production-access acceptance are pending.
Shared Django account-security/Notify mail remains captured. See the
[runbook](implementation/platform-mail.md) for activation and rollback boundaries.

## Private SES feedback resources connected (2026-09-26)

Prepared the unsaved `RokkadPlatformMailRuntime` IAM policy for two platform sender
addresses in Mumbai and ReceiveMessage/DeleteMessage on the source queue only.
AWS JSON validation reports zero errors, warnings and security findings; checked
SES v2 resource/condition support against AWS's authorization reference. Policy,
programmatic user/key and private server installation await explicit access and
credential-transfer approval. Sending remains disabled.

With explicit permission approval, created and connected Mumbai SNS topic
`rokkad-platform-events`, SQS source queue of the same name and
`rokkad-platform-events-dlq`. SES event destination is enabled for send, rendering
failure, reject, delivery, bounce, complaint and delay; no open/click tracking.
SNS subscription is Confirmed, SQS protocol, Raw message delivery Disabled.

Verified both queues use SSE-SQS. Source retention is four days, visibility two
minutes, long poll ten seconds, redrive after five receives. Dead-letter retention
is fourteen days and its allowlist contains only the source queue. Narrowed the
wizard-generated SNS source pattern to this account's exact `rokkad-platform`
configuration-set ARN; removed the redundant subscription-generated SQS grant,
leaving only the SNS service grant bound to this account and topic ARN.

Configuration is verified in AWS console, not yet proven by a real SES event.
No runtime principal/key, application deployment, worker, sending activation or
message test was created/performed. SES sandbox exit remains pending. The
[runbook](implementation/platform-mail.md) records the remaining gates.

## Durable platform mail implemented locally; AWS feedback prepared (2026-09-26)

New `platform_mail` control-plane queue records invitation/paid-receipt intent
inside source transactions, claims once, calls SES outside transactions, and tracks
real provider IDs with conservative unknown-acceptance handling. Private SNS/SQS
feedback validates correlation, deduplicates and suppresses permanent bounce/spam
complaint recipients. Authorized retries and separate delivery status appear in
outgoing invitations and paid invoice detail. No historical replay or borrower/
account-security transport switch. Migration `platform_mail.0001` is local only.

Validation: the final combined run passed **217 tests**, including payment
rollback/transport failures, onboarding savepoint recovery, expiry/revocation/grant
changes, cross-workspace retries, feedback ordering and two concurrent workers
using a restricted PostgreSQL role. Existing orgs/invitation and billing recovery/
review regressions pass with queued-status expectations. Migration drift check
reports no changes; curated documentation link check passed (517 links).

SES now confirms custom MAIL FROM **Successful**. Created `rokkad-platform` with
required TLS, shared IPs, archive disabled. Prepared seven delivery/failure event
types and the `rokkad-platform-events` SNS topic form, not yet submitted. Private
SNS/SQS permissions are awaiting requested action-time browser approval; runtime keys, deployment,
worker supervision, live tests and sandbox exit remain pending. No messages sent.
See [decision](adr/2026-09-26-durable-platform-mail.md) and
[operations](implementation/platform-mail.md).

## Human aliases saved and SES DKIM verified (2026-09-26)

With explicit action-time approval, saved support/billing aliases to the owner's
`admin@rokkad.com` mailbox and created SES `notify.rokkad.com` in Mumbai. Published
three generated RSA 2048 Easy DKIM CNAMEs and custom MAIL FROM bounce MX/SPF in
Linode. Exact CNAME targets verified against the authoritative nameserver; bounce
MX/SPF also resolve correctly. SES now shows identity **Verified**, DKIM
**Successful**; custom MAIL FROM remains **Pending** at this checkpoint.

Google Admin confirms existing DKIM signing is active. Saved root DMARC monitoring
(`p=none`, aggregate reports to the admin mailbox), confirmed resolving from
the authoritative nameserver. Existing Google root MX/SPF and website records are unchanged.
SES remains sandboxed (200/day, one/second), Healthy, on its existing Essentials
plan. No pricing changes, runtime keys, production-access request, deployment or
test/application messages. Receipt/reply tests, durable delivery and provider event
handling remain outstanding; details are in the [rollout](plans/platform-email-rollout.md).

## Email accounts created; provider/domain setup prepared (2026-09-26)

The owner created Google Workspace and AWS accounts. Browser review confirmed
the active `admin@rokkad.com` Business Starter mailbox and SES in Mumbai with zero
identities. The current SES plan is Essentials, not changed by the agent. Prepared
support/billing aliases and an SES `notify.rokkad.com` identity with RSA 2048 Easy
DKIM and `bounce.notify.rokkad.com` custom MAIL FROM. Both forms remain unsaved,
pending requested action-time authorization for aliases and SES sending authority.
Linode DNS inventory preserves Google root MX/SPF and an existing Google DKIM TXT
record. No new DNS records, credentials, purchases, sends or deployment occurred.
See the [rollout](plans/platform-email-rollout.md) for remaining acceptance gates.

## SES rollout selected; configuration foundation validated locally (2026-09-26)

The owner approved separating human inboxes from automated mail, selected Amazon
SES and requested all focused reliability improvements. They confirmed no Google
Workspace or AWS account exists yet; signup/MFA is with the owner. The
[active rollout](plans/platform-email-rollout.md) records the staged work and
[decision](adr/2026-09-26-platform-email-separation.md) preserves the boundaries.

Implemented typed port/TLS/SSL values, finite timeout and validation, capture by
default, sender/future Reply-To settings, a non-secret offline configuration command
and deployment warning. The check honors Django MAILERS precedence and never
equates valid settings with actual delivery. Eleven focused tests passed under
`django_project.settings.test`; the local diagnostic correctly reports capture
and missing reply configuration. No database migration was needed.

This increment is local only. Production still uses its existing capture override;
no provider/DNS change, purchase, message or deployment occurred. Durable delivery,
Reply-To wiring, templates/UI, provider receipt reconciliation and authenticated
sending remain pending approved stages, not implemented functionality.

## Email communication review: production delivery disabled (2026-09-26)

Completed [email configuration and workflow review](plans/email-communication-review.md),
tracked as FW-014. Read-only non-secret production inspection confirmed the web
processes use `production_settings`, which explicitly selects Django's in-memory
email backend; no alternative mailer is configured. Default sender domain is
`rokkad.com`, not evidence of current personal SMTP sending. Public DNS shows
Google MX/SPF and no root DMARC record in the lookup. No mailbox account was audited.
Reviewed invitation sends inside transactions, best-effort billing receipts, raw
SMTP setting types and Notify's lack of real email-provider receipt correlation.
Recommended domain-owned inboxes plus authenticated transactional sending and
durable delivery handling. Provider/sender selection and implementation are pending.
No messages, DNS/configuration changes, purchases or deployment occurred.

## Tamil Nadu statutory forms future work recorded (2026-09-26)

Added [FW-013](plans/future-work.md#fw-013-tamil-nadu-prescribed-forms-and-pledge-book-in-englishtamil)
for prescribed English/Tamil forms and pledge-book generation per applicable
Workspace/licence. Read the owner's CRA Rules PDF and recorded a preliminary form
inventory, current-law/Tamil wording review, existing printing foundations, data
coverage and financial reconciliation needs. The Rules are distinguished from the
Act; PDF generation is not a complete legal-compliance or filing claim. Documentation
only; no new forms, economic-policy changes, filings or production deployment.

## Complete Workspace restore scenario recorded (2026-09-26)

Added [FW-012](plans/future-work.md#fw-012-complete-workspace-export-and-guided-restore-into-a-fresh-workspace)
as the main-register link to the existing M7 complete-archive milestone. Captures
the owner's export -> private Google Drive storage -> fresh Workspace restore ->
continued business scenario. Code/contracts confirm current Party bundles and
bounded per-loan restoration do not provide a complete Workspace backup. Recorded
coverage, binary/configuration/numbering, consistent snapshot, fresh-destination,
security exclusions and continuation acceptance requirements. Documentation only;
no export, cloud upload, import, infrastructure backup or implementation started.

## WhatsApp messaging product scope recorded (2026-09-26)

Added [FW-011](plans/future-work.md#fw-011-platform-and-workspace-whatsapp-messaging-and-phone-verification)
for platform operational/billing alerts, Workspace-owned borrower messaging and
contact-verification codes. Linked the existing Workspace integration-acceptance
plan and Notify v2 foundations rather than treating delivery as unimplemented.
Recorded separate sender/audience ownership, onboarding, consent, policy eligibility,
phone-verification limits, UI, cost controls and delivery acceptance. Meta's current
restrictions require review of the proposed lending/collection use cases. Future
work only; no messages, registrations or application/production changes.

## Platform administration future work recorded (2026-09-26)

Added [FW-010](plans/future-work.md#fw-010-platform-administrator-role-operational-workflows-and-ui)
after checking the future-work register and existing platform/control-plane docs.
The owner identified unclear platform-admin responsibilities, operational journeys
and UI. Recorded discovery, role/action mapping, console design and operating-guide
scope while preserving existing superuser-only override, audit, RLS and subscription
access foundations. Unscheduled; documentation only, no implementation approval.

## Borrower identity follow-up shelved at owner request (2026-09-26)

Shelved [FW-009](plans/future-work.md#fw-009-consent-based-borrower-identity-verification--aadhaar-assisted-onboarding)
after the completed desk review. Contracting legal-entity clarification, written
eligibility/hosting enquiries and pricing, integration selection and the small pilot
will resume only on explicit owner instruction. The review and unsent enquiry are
preserved. Recheck current requirements/pricing on resumption. Documentation only.

## Borrower identity feasibility desk review complete (2026-09-26)

Completed the owner-authorized [FW-009 desk review](plans/borrower-identity-feasibility.md).
Compared Aadhaar app sharing, QR/XML, hosted DigiLocker and online e-KYC against
current UIDAI evidence and existing Party code. Recommended investigating a
registered-lender app-sharing arrangement first, with hosted DigiLocker as an
alternative; eligibility, permitted SaaS hosting and all-in pricing remain unconfirmed.
Recorded a bounded first workflow, storage/verification gaps, cost reference,
unsent eligibility/quote questions and pilot gates. No vendor account, registration,
outbound message, real identity processing or application/production change occurred.
Documentation validation only; implementation and provider selection remain pending.

## Borrower identity verification idea captured (2026-09-26)

Recorded [FW-009: Aadhaar-assisted borrower onboarding](plans/future-work.md#fw-009-consent-based-borrower-identity-verification--aadhaar-assisted-onboarding)
as unscheduled discovery, not implementation approval. The entry captures the
owner's identity-confidence and faster-onboarding goals, existing Party foundations,
consent/minimal retention, contact-verification limits and Workspace isolation.
First resolve permitted lender/platform roles and UIDAI/provider eligibility;
existing verification flags do not establish an integrated Aadhaar check.
The owner subsequently agreed to the feasibility-first approach and potential promise,
"Verify customer identity and reduce manual entry." Integration selection and
implementation remain pending; the next deliverable is a feasibility recommendation.
Documentation only; no application, production or customer-data changes.

## Guided unpaid-loan valuation review deployed (2026-09-26)

Production runs `rokkad:rc-20260926-0f582472`. Startup and post-deployment checks
passed with restricted runtime access and forced RLS. No migration or static
asset change was required. The review route and staff handbook passed in all
three workspaces; the available JSK approved loan was checked through comparison,
detail and applicable disbursal discovery. JCL and Lakshmi had no approved loans
at this checkpoint, so their route checks exercised the guarded unavailable state.

Business fingerprints covering loans, approval snapshots, events, issued-document
records and number sequences were unchanged during the rollback-only GET checks.
No actual loan was reapproved, redated or disbursed during deployment. Runtime
settings/proxy configuration remained unchanged. Verified before/after backups
and private release evidence remain on the server. Source is committed locally;
this rollout did not publish a GitHub push.

## Guided unpaid-loan valuation review implementation (2026-09-26)

Implemented [Review updated valuation](adr/2026-09-26-unpaid-loan-valuation-review.md)
for approved native itemized loans before actual payment. Stale approvals show
the action on loan detail and disbursal, with old/current quote prices and dates,
collateral limits, rates, policy terms, fees and net cash. An explicit unpaid
attestation and current edit/approval permission authorize atomic reapproval
for today; loan number, photographs, earlier approvals and PDF evidence remain.
Disbursal is a separate step. Missing quotes and LTV violations block reapproval.
Signed review checks and an immutable approval marker protect changed inputs,
retries and concurrent submissions. No schema migration is required. Historical
payout guidance remains separate and the workspace handbook explains both paths.
Validation: 103 Python tests passed across updated valuation, earlier payouts,
draft UI and price readiness, including simultaneous confirmations, restricted
runtime execution, drift, rollback, replay and permission guards. Migration drift
check reports no changes. Production rollout evidence will follow this checkpoint.

## New-loan submission protection deployed (2026-09-26)

Production runs `rokkad:rc-20260926-9f9f67e4`, incorporating the protection in
`807a78a4` and edit clarification in `9f9f67e4`. Loans 0027 was the only pending
migration and ran with the owner-only migration connection. Runtime startup,
forced RLS, the submission constraint/trigger, signed new-form identities and
the staff handbook passed checks in JCL, JSK and Lakshmi. Published JavaScript
hashes match the committed source; the web container is running without restarts.

All 91 Python checks passed after the clarification, plus 9 browser-event checks.
Repeatedly following the split-panel edit link and saving corrections retained
one loan and one number in regression tests. Production verification used GETs
and rolled-back authentication sessions; no real test loan was created.

Prepared assets before briefly stopping old web writers. Before/after hashes
matched existing loans, loan events, issued-document records and number sequences
through migration. Reported duplicate JSK records were not cancelled, deleted or
renumbered. Runtime settings and proxy configuration remained unchanged. Both
operational backups and private deployment evidence remain on the server.

Open pre-upgrade New loan forms lack the signed reference and fail closed. Check
recent loans before opening a fresh form; do not infer that a network error means
the previous save failed. Current forms retain their reference across validation
and preview responses; completed resubmissions return the original saved loan.

## Correct-draft link investigation and clearer editing copy (2026-09-26)

The owner identified the single-item split hint's Correct draft link as a
possible cause. A rollback-only production check on JSK 06707 followed that
exact rendered link three times: each GET opened its existing loan-specific
edit route; loan count and numbering remained unchanged. The edit service
updates that ID under a lock and does not allocate a new loan number. Available
container logs did not provide matching requests for the incident window, so
the original physical click sequence remains unconfirmed.

The shared edit form misleadingly said saving creates a draft. It now says
editing keeps the same number, uses Save changes and has an explicit edit action.
The single-row split hint uses Edit this draft and explains that editing does
not create another loan. Regression coverage follows the rendered link repeatedly
and saves repeated corrections. Keep browser progress feedback and durable
server protection: a button guard alone cannot cover every repeated request.

## New-loan submission protection implementation (2026-09-26)

Implemented the [durable form-identity decision](adr/2026-09-26-new-loan-submission-identity.md):
workspace/actor-bound signed identity, one saved loan/number/photo set under
concurrent or repeated submissions, early recovery after lost responses, clear
no-changes-applied replay message, immutable database identity and browser Saving
state. Preview/error retries retain the reference; ordinary draft corrections
remain repeatable. The workspace handbook explains save, retry and correction.
Existing reported JSK records are not cancelled or renumbered by this work.
Validation: 91 Python tests passed across draft UI, submission identity/concurrency/
populated migration and price readiness; 9 browser-event checks passed. Migration
drift check reports no changes. Existing UI fixtures now use independent IDs when
cloning loans, current Indian-money output and a fixed date for ordinary disbursal
UI assertions. Production deployment evidence will follow this checkpoint.

## Duplicate new-draft submission investigation (2026-09-26)

Read-only production inspection of the reported six JSK records found identical
borrower/terms/photo evidence created by the same staff user within four seconds.
Five remain DRAFT; the sixth was approved, had a document issued and was later
CANCELLED. None has a recorded financial event. This strongly supports repeated
new-form submission; database history alone cannot identify individual clicks.

The new-draft endpoint allocates a new loan and number on each successful POST;
it has no durable submission identity. The browser price-preflight guard only
covers its asynchronous quote check, not the subsequent save request. Updating
an existing draft uses its loan ID and retains its number. Preview does not
create a loan. Recommended next fix: server-enforced idempotency for a new-form
submission, plus a visible saving state and repeat-submit guard, with concurrent
request/retry tests. Do not deduplicate by borrower/amount alone: separate genuine
loans can have identical terms.

Existing cleanup is reasoned cancellation, not operational hard deletion or
number reuse. Determine whether any intended draft should be retained before
cancelling the unwanted records. No loans, documents, numbers, code or runtime
configuration were changed by this investigation.

## Earlier payout, daily quote confirmation and actor attribution (2026-09-26)

Owner-approved implementation adds a separate administrator-reviewed native earlier
payout action, preserving actual date, historical policy/quote references and all
prior evidence. Signed actor-bound review, reason and cash attestation precede
atomic approval/disbursal; repeated confirmation is idempotent. Historical quotes
must already have been recorded by the actual date; today's or retrospectively
entered quotes cannot substitute. Ordinary same-day origination remains guarded.

Rates now appends explicit daily unchanged-price confirmations with protected
source-quote relationship and recording actor/time. Database guards preserve
workspace boundaries, prices and append-only evidence; workspace locking serializes
quote commands. Loan Overview/history now distinguish creator, approver, recorder,
effective date, recording time and correction reasons. Both detail layouts share it.
The workspace handbook and developer/staff docs explain the workflow and boundaries.

Validation: 80 focused tests pass, including historical completion/correction,
actor-bound review, authorization, quote evidence and concurrency, schema upgrade,
restricted-role RLS cross-workspace rejection, ordinary origination/redisbursal,
economic policies and handbook rendering. Migration drift check passes.

Deployed application `100222ba` after server-only backup and owner-only Rates 0004
migration. Candidate and deployed restricted-runtime checks passed for all three
workspaces' details, Rates and handbook. HTTPS and runtime startup passed; proxy,
settings and static assets were preserved. The initial smoke-test script used an
incorrect Lakshmi slug; correcting the script resolved it before activation.

The affected JSK draft's earlier-payout review is available with its actual
September 25 date and original approval/quote. No real loan was approved or
disbursed and no price confirmation was recorded by deployment. Read-only checks
verified loan, photo, approval, event, schedule, document, sequence and quote
evidence unchanged. Before/after backups and private delivery evidence remain
on the server. The user must review and confirm the actual payout themselves.

## Overnight draft date and quote guidance correction (2026-09-26)

**Owner correction after deployment:** the affected loan's cash was actually paid
and its printed ticket handed over on September 25. This supersedes the earlier
unpaid-draft statement below. The owner explicitly requested restoring September
25, which was applied through the audited draft service after a backup and
rollback-only preview. Principal, interest, borrower, tenure, photos, issued
documents, approval history and counters were preserved. No disbursal event was
created. The loan remains DRAFT in the application and the historical review
gate still blocks completion; do not report it as ready to disburse or move its
date forward again. Private restoration evidence is saved on the server.
The owner reopened the daily-quote/date policy discussion; the proposed redesign
is recorded under [FW-005](plans/future-work.md#fw-005-historical-market-valued-loan-entry).
No freshness or historical-admission policy change has been approved or deployed.

A previous-day draft selected prices at its saved loan date, then failed today's
freshness check before reaching the loan-date guard. Adding a valid current-day
quote could therefore never resolve the displayed instruction. Review/approval
now validates the date first, including the legacy unitemized path, and identifies
both dates with an explicit draft-edit recovery. Preflight gives the same date
guidance; the review links authorized editors directly to the draft. Dates are
never advanced automatically and actual historical payouts must retain their date.

The existing same-day quote/date contract remains unchanged. The workspace loan
handbook now explains daily quotes per required metal, unchanged-price entry,
overnight unpaid drafts, appraisal-only exemption and servicing independence.
Also corrected appraisal suggestion's machine-readable numeric attribute to keep
commas only in visible display, so applying an Indian-formatted amount remains a
valid numeric input. No schema or calculation-policy change.

Local validation: 38 focused origination, quote-readiness and redisbursal tests
plus eight appraisal/handbook tests pass, including fresh quote plus previous-day
draft, date-first legacy fallback, review recovery link, date preservation,
quote changes and immutable history.

Deployed application `7972b95b`. Candidate and deployed checks passed under the
restricted runtime role: current-date review ready, simulated previous-day date
guidance correct, handbook present, and loan financial evidence unchanged by
verification. Static assets, runtime settings and domain proxy were preserved.
The owner confirmed the affected loan was unpaid and intended for today's
disbursal. Its date was advanced through the normal audited draft-update service,
preserving number, photos, counters and earlier approvals; it remains DRAFT for
the user's confirmation. No approval, payout or financial event was created by
the repair. Before/after server-only backups passed archive catalogue checks.
Private deployment and repair evidence remain on the production server.

## Main-domain cutover completed (2026-09-26)

Owner-authorized DNS now sends root/www IPv4 and IPv6 to the new server.
`https://rokkad.com` serves the existing production database and application
`67be05b5`; www and rehearsal GET/HEAD requests redirect there with paths intact.
Stale rehearsal form submissions receive an explicit 409 and are not replayed
across hostnames. No import, schema change, financial posting, counter reset or
application rebuild occurred. The landing mockup choice remains pending.

`https://legacy.rokkad.com` proxies through the new edge to the pinned old server
over verified HTTPS. The old code/configuration/services and business records were
not modified, and editing remains available as requested; the owner/staff must
continue enforcing the old-system write pause. The explicitly approved legacy
Google callback was saved without changing credentials or existing callbacks.
Actual Google sign-ins returned to the old JCL dashboard at legacy and the new
JCL dashboard at root. Both systems keep separate host-only sessions.

All five authoritative DNS servers returned the new root addresses. Server HTTPS
checks passed for root, www, rehearsal and legacy; main IPv6 passed separately.
Before/after restricted-runtime checks passed for JCL, JSK and Lakshmi loan
forms/list/detail/guide pages, policy settings and financial fingerprints, with
test session writes rolled back. Canonical Site/host/CSRF settings were updated;
mail/MX/TXT/NS records were preserved. Browser DNS cached the old site briefly
before naturally resolving the new endpoint; interactive sign-in then passed.

Private evidence: `domain-cutover-20260926/activation.json`, `check-before.json`,
`check-after.json`, validation logs and pre-change settings/proxy snapshots.
Post-switch server-only archive:
`backups/operational/production-20260926T012400Z.dump` (55,718,136 bytes), SHA-256
`49956e1fecbf3e9a8b2376ca9e3b32c9b2b0bf8bf5af0e1d82f80243beac2b06`;
archive catalogue checked. Hourly backups remain enabled.

The untouched old Certbot timer uses nginx and its upstream certificate expires
December 2. The new edge forwards root/www HTTP ACME challenge paths to preserve
that renewal route; a real old-server renewal was not forced. Observe successful
renewal before expiry. Backup retention/off-server recovery remain outstanding.
See the [cutover runbook](implementation/linode-production-cutover.md) for routing,
certificate ownership and recovery constraints. Never restore an old snapshot or
route new financial work back to legacy as a rollback.

## SaaS landing-page design review (2026-09-25)

The owner requested explicit loan management SaaS positioning and a choice of
mockups before any production change. Added [three interactive landing concepts](plans/landing-page-positioning.md):
A (product first), B (journey first), C (business first). All identify the
pawn-lending audience and subscription/browser delivery while preserving the
borrower, debt and physical pledge story. The loan list illustration contains only
labelled invented examples. Guided Excel loan import remains labelled as planned.

The preview passed 24 concept/theme/viewport combinations (A/B/C, light/dark,
1024/736/390/320px), navigation-target and local CTA checks, with no horizontal
overflow or JavaScript errors. Decorative icon placeholders use the conversation
runtime; the standalone inspection wrapper omits that icon initialization.
The source is documentation-only and the owner selection is pending. No application
template, production route, deployment or business record was changed.

## Loan journey handbook and product story (2026-09-25)

Added the [developer journey reference](flows/loan-journey.md), reproducible shared
PNG overview, and read-only workspace handbook at `/w/<slug>/loans/guide/`.
Navigation, Loans and loan details link the handbook. It explains the supported
lifecycle, physical custody, corrections, coverage/unknown evidence, imported
opening boundaries and paper closure transition. FW-007 was already recorded;
its review and links now explicitly connect the manual/Excel old-loan gap to the
handbook and product story.

The public landing page now tells the customer/pledge/collection/return story with
illustrative loan and custody cards, six benefit areas and honest migration
positioning. No customer records appear in the illustrations. Saved drafts expose
a split card in Overview, explaining one-row/quantity limitations; existing
create/edit/state guards and split services are unchanged.

Validation: 10 guide-access/discovery/display/template tests, two existing split
identity/permission regressions, and two native/imported loan-layout browser
regressions pass. Landing and handbook content were visually reviewed at desktop
and mobile sizes, with no horizontal overflow and the PNG loaded. Documentation
links pass. No schema migration or loan calculation changes.

Deployed application `67be05b5` as `rokkad:rc-20260925-67be05b5`, image
`sha256:e8ff2eb91cc58e0ab72d8bc83e340c4366bdb32a373066eb33485bf86966ec68`, with
static volume `rokkad_production_static_67be05b5`. Candidate and deployed checks
passed for the guide, loan list/detail links, public landing and published CSS/PNG
hashes. The restricted runtime role and forced RLS checks pass. Per-workspace
financial/document fingerprints were unchanged; JCL/Lakshmi 80%, JSK 95% LTV and
JSK WH interest exceptions remain intact. All three workspaces had zero saved
drafts at verification; there was no production-eligible split to display. Local
synthetic tests cover its visibility and actual identity-preserving split.

Private acceptance: `acceptance-20260925/loan-journey-deployment.json`. Server-only
before/after backups passed catalogue checks; the post-update backup is
`production-20260925T180715Z.dump` (55,717,719 bytes), SHA256
`06340dc1565316ce08d940c9a28d8ac0fe868ba98b0acda6abfbb3e7be6656de`.
The retained production database remains at `rehearsal.rokkad.com`; the old server
and live-domain DNS were not changed. Application and documentation are on the
tracked release branch; no merge into `rls-mvp` was performed.

## Release documentation consolidation (2026-09-25)

Reviewed and consolidated the previously unstaged delivery notes and September 24
acceptance report. Current guidance now points to application `713e0b64`, Loans
migration 0026 and retained production at the temporary hostname; older image,
numbering, access and readiness statements are explicitly historical. Current
ownership and JSK policy exceptions take precedence over the initial defaults.
Unnecessary staff email addresses are omitted from the new public-facing notes.
Documentation links and whitespace checks pass. This checkpoint changes no
application code, deployed image, database, DNS or financial records.

Git ancestry confirms release branch creation from `rls-mvp` at `a9f793fc` on
September 24, followed by consolidation `ec96cce6` on the release branch itself.
The owner authorized publishing `release/2026-09-24-rc1` to the existing public
`origin` repository and setting its upstream, without merging into `rls-mvp`.
The outgoing-history review found no new database dump/credential-file paths or
matches for the checked token/private-key formats; ignored local artifacts remain
outside the release. This bounded check is not a full historical secret audit.

## Camera selection, printed quantities and Indian monetary display (2026-09-25)

Customer create/edit, customer gallery and collateral capture now offer front/rear
choices plus available named cameras after permission. Changing a live choice
reopens capture immediately; tracks are stopped before switching, on cancellation,
submission, page hide and navigation. Generation guards discard late permission
responses and captures. Ordinary file upload remains available. Gallery capture
preserves the camera aspect ratio instead of stretching every photo to 480x360.

Native and imported tickets print known frozen quantities beside descriptions.
Imported copies now carry source quantity through their projection; unknown
historical quantities are not invented. Previously issued native PDFs remain
unchanged. Presentation-only Decimal formatting groups monetary amounts in lakhs
and crores across operational pages, reports, customer portal and newly generated
PDFs. Actual paise remain; whole rupees omit .00. Input/wire values and financial
evidence are unchanged; no migration or financial-data update is required.

Validation: synthetic Chromium checks cover all three camera controls, named
selection, front/rear switching, capture/preview, cancellation, out-of-order
permission responses, cleanup and upload fallback. Django regression suites passed
(62 document/import/display/export checks and 107 UI/report/overlay checks);
all six Node customer-photo checks passed.

Deployed `713e0b64` (main implementation `0a073957`) to production at
`rehearsal.rokkad.com`, image
`sha256:a045348992a0d1f63fab41ea0634a9afda4de98391078bbe3ebd84ca5ef28792`,
static volume `rokkad_production_static_713e0b64`. Candidate and deployed checks
passed for all three workspaces under the restricted runtime role and forced
RLS. Each branch's two longest imported-ticket description sets rendered with
source quantities; PDF text extraction required whitespace normalization for
wrapped quantities. Financial-row and issued-document fingerprints stayed equal
within each check. JSK WH rates and branch LTV policies remained intact. Public
login and all six changed camera/summary asset hashes passed. No migration or
live business transaction was performed by these checks.

Server evidence: `acceptance-20260925/camera-money-deployment.json` under
`/home/rokkad/deploy/cutover-20260924`. Before/after backups stayed on that server;
after backup `backups/operational/production-20260925T145913Z.dump` is 55,717,830
bytes, SHA256 `191208efba013f8965bcce9cd29b97277da0e3fce371123542b10a0ccc00a986`.
Physical Android/iPhone camera hardware has not been exercised here.

## Collateral entry, visible interest and ticket amounts (2026-09-25)

The owner approved overrides by staff with `loan.approve`. New collateral rows
start at 75% purity and quantity 1; row weights/amounts are totals. Nullable model
fields preserve unknown historical quantities. Blank overrides use policy;
explicit rates require a reason and service authorization, with creation/update
logs and frozen approval evidence. Splits preserve terms; renewals retain counts
and resolve retained items using successor policy. Detail headers expose the
monthly effective rate and collateral shows actual item rates. Price preflight
explains its stored-rate lookup and displays current policy defaults without
modifying overrides. New ticket generation omits whole-rupee decimals and prints
approved quantities; existing PDF bytes and loan values are preserved.
All 165 regression tests pass, including authorization, zero-rate overrides,
frozen approval/disbursal, renewal compatibility, populated migration replay,
imported tickets and PDF rendering. Chromium verifies series/metal hint changes
preserve typed overrides; migration drift is clean. Release `706d6f57` and
migration 0026 are deployed with static volume `rokkad_production_static_706d6f57`.
Restricted-runtime candidate and deployed checks pass for setup, new-loan and
detail pages in all three Workspaces. Read-only checks leave loan, event,
collateral, numbering, release, snapshot and fee fingerprints unchanged. JSK's
95% LTV and WH 1.1%/3% rates remain intact; published JavaScript matches source.
Evidence: `acceptance-20260925/collateral-entry-deployment.json`.
Post-deployment server-only backup:
`backups/operational/production-20260925T141512Z.dump` (55,715,460 bytes; SHA-256
`cd8eb63fd94757da69689a36006d06e4590c81ac46d9d88628033c01db4d7994`).
See the [staff guide](flows/collateral-entry-and-interest.md),
[decision](adr/2026-09-25-collateral-quantity-and-interest-overrides.md), and
[portable-metadata extension](plans/collateral-portability-metadata.md).

## Same-day calculation policy revisions (2026-09-25)

JSK's attempted 80% to 95% LTV change exposed scope/date uniqueness rejecting
same-day policy saves. Economic and metal-rate policies now append sequential
revisions, retain earlier rows, and resolve latest date then revision within the
existing scope priority. Workspace locking serializes competing saves; the full
configuration remains atomic and audited. Setup preloads current saved settings
and exposes a history-copy link, avoiding accidental resets to starter values.
Migration 0025 preserves existing IDs/values as revision 1. All 147 economic,
setup, draft and corrected-disbursal tests pass, including populated migrations,
concurrent first saves, restricted-RLS DML, LTV retry without consumed numbers,
and frozen approval/disbursal evidence. Migration drift is clean.
Release `4d66147a` and migration 0025 are deployed at `rehearsal.rokkad.com`.
JSK now uses 95% maximum LTV from 25/09/2026 (policy 4, revision 2), preserving
all other calculation values, previous rows, fees and WH 1.1%/3% overrides.
JCL and Lakshmi remain at 80%. Restricted-runtime checks pass for all three
setup pages; hashes across 76 JSK business models are unchanged by the setting
update. No customer loan was created or disbursed. Runtime settings and the
existing static volume are unchanged. Evidence:
`acceptance-20260925/economic-revisions-deployment.json`.
Post-deployment server-only backup:
`backups/operational/production-20260925T115828Z.dump` (55,660,065 bytes; SHA-256
`2b0b1c29de34edeb6c004aa4a0e6bfc21fbe41aad44df93dfc55be692ffe9a98`). See the
[decision](adr/2026-09-25-same-day-economic-policy-revisions.md) and
[operator guide](flows/changing-loan-calculation-settings.md).

## Selected loan detail layout and customer header (2026-09-25)

Owner selected Tabs and Classic only; B/C are removed from the live layout menu
and retired saved values fall back to Tabs. Original mockup HTML is untouched.
Classic keeps its existing header/action layout as the comparison reference.
Tabs now matches the mockup's top navigation, bold number/status, date/series and
customer card. Private default photo falls back to initials when absent or
unreadable; default contact/address use at most two scoped read queries per page.
More actions is a grouped, keyboard-accessible dropdown over the original actions.
No financial command, workflow, numbering, PDF, permission or migration changes.
All 97 regression checks pass, including workspace/default-selection boundaries,
loan detail permissions, imported tickets/releases and browser layout parity.
See the updated [staff guide](flows/loan-detail-layouts.md). Release `c3679e03`
is deployed with static volume `rokkad_production_static_c3679e03`. Final browser
checks also pass after menu styling/keyboard refinements. Candidate and deployed
restricted-RLS GET checks pass on six loan pages across JCL, JSK and Lakshmi;
business-row fingerprints and runtime settings are unchanged. Published CSS/JS
hashes match source. Evidence: `acceptance-20260925/tab-refinement-deployment.json`.
Post-deployment server-only backup:
`backups/operational/production-20260925T113556Z.dump` (55,659,513 bytes; SHA-256
`8316ea4bd1b1be0c710d6ed8c301febf9c837b504d2a34b6207cd13bd7502a14`).

## Four-layout loan detail trial (2026-09-25)

Owner approved Tabs (preferred/default), Service desk, Expandable sections and
Classic for a daily-use trial before deciding what to retire. One canonical
server render preserves all forms, permissions, evidence and URLs; the browser
rearranges existing nodes and remembers the choice per user/workspace. See the
[decision](adr/2026-09-25-loan-detail-layout-trial.md) and
[staff guide](flows/loan-detail-layouts.md). No schema or financial-service changes.
All 87 UI/imported-ticket/release/browser checks pass, including seven loan/access
states, 320/390/736/1280px widths, original control identity, photo selections,
CSRF preservation, keyboard tabs, deep links, storage failures and Classic without
JavaScript. Release `cac28117` is deployed at `rehearsal.rokkad.com` with static
volume `rokkad_production_static_cac28117`. Candidate and deployed checks passed
under restricted runtime RLS in JCL, JSK and Lakshmi (five detail pages), with
unchanged business-row fingerprints. Public CSS/JS hashes match the tested source;
runtime settings are unchanged. No migrations or financial commands were run.
Evidence: `acceptance-20260925/loan-layouts-deployment.json`. Server-only backup:
`backups/operational/production-20260925T100217Z.dump` (55,652,527 bytes; SHA-256
`91a293108d0a67e922f8a90bb8a6bcdd45f7cf851601bb8c3a9ab2b184a44758`).

## Loan detail design alternatives (2026-09-25)

Owner requested mockups before choosing a production redesign. Three interactive
options share a feature inventory: horizontal tabs (recommended), a service
sidebar and expandable sections. Draft/approved/native/imported/closed/blocked
examples use synthetic data and local action previews. See the
[design and feature map](plans/loan-detail-redesign.md). Chromium checked 108
layout/state/section combinations and desktop/phone widths. That initial design
stage changed no production code or data. The owner subsequently approved the
four-layout trial documented above.

## Corrected disbursal regression (2026-09-25)

JSK 06703 exposed a lifecycle mismatch: reversal and draft correction were allowed,
but retained one-to-one snapshots prevented re-disbursal. The fix preserves each
attempt, adds guarded current snapshot links, and versions replacement schedules.
Equal-amount corrections receive distinct event identity while ACTIVE retries
remain idempotent. See the [decision](adr/2026-09-25-corrected-disbursal-attempts.md)
and [staff workflow](flows/correct-a-disbursed-loan.md). The 173-test lifecycle/UI/
release regression suite and a further 20-test correction/document/history run
passed, including real competing database connections and restricted-role writes.
The first deployment migration rolled back on PostgreSQL deferred FK checks before
index creation; the old application was restored. The ordering fix passes all nine
correction tests, including a populated upgrade from migration 0022 with unchanged
source events. Release `511c7cd8` and migrations 0023/0024 are now deployed at
`rehearsal.rokkad.com`, retaining static volume `rokkad_production_static_7dad893a`.
Candidate and deployed restricted-runtime checks verify current snapshot links in
all three branches and JSK 06703's detail/review at INR 7,150. Its original
INR 7,149.95 snapshot and reversal remain; automation recorded no new disbursal.
Deployment evidence: `acceptance-20260925/redisbursement-deployment.json`.
Final check leaves 06703 in DRAFT. Post-deployment server-only backup:
`backups/operational/production-20260925T082336Z.dump` (55,646,091 bytes;
SHA-256 `ab9de593d9009b5520a8ece05edd4e15254380a6bff6f4c6ee5ebdaa1a727c7d`).

## Paper closure transition (2026-09-25)

Owner approved implementation of a separate fast paper-entry workflow with 50
loans per atomic submission, shared actual date, suggested amounts/borrower
defaults, per-row cash and collector evidence, explicit interest concessions and
branch-specific owner retirement. Implementation passed 107 targeted tests and
the synthetic Chromium UI check. Fifty real test loans took
about 2.0 seconds to preview and 7.0 seconds to complete locally. Identical
simultaneous submissions close once. See the [decision](adr/2026-09-25-paper-closure-transition.md) and
[staff guide](flows/paper-closure-transition.md). Existing counter batch remains
20 loans with one exact combined collection today.

Release `7dad893a` and migration 0022 are deployed at `rehearsal.rokkad.com` with
static volume `rokkad_production_static_7dad893a`. Candidate and deployed runtime
checks passed for 50 imported active loans per branch (about 1.5–1.6 seconds per
preview), entry/guide/owner settings/history pages, forced RLS and hashed static
delivery. Financial rows, releases, counters and transition settings were unchanged
by these read-only checks; no real closures were submitted. Signed-in Chromium
verified the hosted staff guide. All branches remain paper-first, with no retirement
date configured. Owner chooses dates later after staff readiness/reconciliation.

Server evidence: `acceptance-20260925/paper-closures-deployment.json`. Server-only
before/after database backups passed catalog checks; latest
`production-20260925T074416Z.dump`, 55,620,036 bytes, SHA-256
`320ff354a61974b58639891ba105d3ff2ee8c60c4dc8bfb503abe0178d123987`.
After paper records exist, older application rollback needs review because those
versions do not understand unknown handover times. Preserve new transactions.

Paper date-only handover evidence is preserved without invented timestamps.
Strict restore-package export refuses paper histories until its profile supports
that evidence; a labelled reconciliation CSV and full database backups retain it.

## JSK WH series interest override (2026-09-25)

Owner requested WH gold 1.1%/month and silver 3%/month, retaining other series' rates.
Existing rate policies had only Workspace/licence scopes. Added optional series
scope, per-scope uniqueness, a database parent guard and series-first resolution.
Preview, draft creation/edit, approval, split and renewal pass their series. Setup
offers an audited atomic gold/silver override form; calculation and fees stay unchanged.
Production review identifies JSK WH as series 9, licence 3; unprefixed series is 8.
Existing defaults are gold 2%, silver 4%, effective September 25; there are no JSK
drafts at review time. Migration 0021 and release `a8e78108` are deployed; active
WH policies 9/10 are gold 1.1% and silver 3%, effective 25/09/2026. All other
active series resolve to gold 2%, silver 4%. Runtime checks confirm existing JSK
loans, collateral, approvals, events and numbering remain unchanged. A read-only
mixed-metal calculation gives INR 41/month for INR 1,000 gold + INR 1,000 silver.
Candidate and deployed setup/new-loan pages pass. Server-only backups before and
after activation passed catalog checks; evidence is
`acceptance-20260925/wh-interest-deployment.json`.

Validation: 99 economic-policy/economics/draft/default-setup tests, 59 setup UI
tests, three RLS tests (after correcting the test savepoint), and focused frozen
approval/disbursement and series-only readiness checks pass. No migration drift.
The readiness selector now also passes the series to interest resolution.
Follow-up release `58858717` is live, retaining static volume
`rokkad_production_static_26855c3c`. Candidate/deployed verification passed;
evidence: `acceptance-20260925/series-readiness-deployment.json`. Latest server-only
backup is `production-20260925T065036Z.dump` (55,610,193 bytes; SHA-256
`81ec712171f3eedcd19009f7474e393d51b664c0d79cf7fe07ca4f5a1f40a3f8`).
Do not roll back to pre-series application code while series overrides are active;
see the [series policy ADR](adr/2026-09-25-series-interest-rate-overrides.md).

## Loan series labels and borrower filtering (2026-09-25)

Loan details, summary, edit-number explanation, list rows and series filter now use
the pawn sequence prefix (or No prefix), matching the new-loan picker. Internal
migration codes and numbering counters remain intact. The list borrower filter is
a Select2 picker for existing borrowers, including inactive/archived customers with
loans. Its signed token is bound to the Workspace URL, the endpoint requires Loans
view permission, and results are private/no-store. Existing borrower links and older
text-filter URLs continue to work.

Search starts at two characters after 300ms, returns 20 matches per page and fetches
one extra match rather than counting every match. Default contact/address prefetching
takes three data queries per page, verified with 23 borrowers; series labels are
also prefetched across list rows. Sixty-three loan draft/directory checks pass across
the main and corrected-label runs; the expanded revoked-permission/pagination checks
and existing Party label check pass. Chromium verified selecting and clearing the
real Select2 widget submits exactly one filter request each. No migration required.

Release `26855c3c` is live at `rehearsal.rokkad.com`, with static volume
`rokkad_production_static_26855c3c`. Candidate and deployed checks confirm JCL C07549
shows Series C and all three borrower filters work. The sampled search data work
took three queries and approximately 10–24ms per branch (excluding HTTP/access
checks). Loan rows and counters were unchanged. Server-only before/after backups
passed catalog checks; latest is `production-20260925T061702Z.dump`, 55,604,722 bytes,
SHA-256 `41211bfafd8bb5ffd95f1f6d1d567745fd2de91604f587f03583f93d4f31ea48`.
Evidence: `acceptance-20260925/loan-directory-deployment.json`. The reporting harness
now captures query count before later HTTP requests reset Django's query log.

## Customer photos, borrower identification and dates (2026-09-25)

Added the authorized customer photo gallery with one selected default, preserving
existing profile file references and earlier uploads. The new directly owned table
has forced RLS, registry coverage and a database parent guard. Default selection,
removal fallback and merge preservation use the existing Party permission boundary.
Borrower autocomplete adds one default address and phone fallback with prefetched
children. Collateral file/camera selection now shows a local preview, including
dynamic rows. Existing multi-photo collateral evidence and one-photo ticket selection
remain supported.

Human date display and new document rendering use DD/MM/YYYY; native HTML date
values and source dates retain ISO representation. Previously issued PDFs retain
their bytes. Validation: 248 application/document tests passed; three restricted-role
RLS checks passed after making their retained-database fixture names unique; 31 legacy
media checks passed. Chromium exercised previews, replacement, dynamic rows, removal
cleanup and reset. Synthetic PDF date placement was visually checked.

Release `8fa5d273` is deployed to the retained production database at
`rehearsal.rokkad.com`. Candidate and deployed checks verified all three workspaces,
restricted runtime RLS, private gallery delivery, loan page dates, reconstructed
ticket dates, and unchanged native C07548 reprints. Backfill preserved 13 JCL,
249 JSK and 880 Lakshmi default photos (1,142 total). Static assets use the new
`rokkad_production_static_8fa5d273` volume; prior files and volume remain available.
Server-only backups before and after deployment passed catalog checks. The latest is
`backups/operational/production-20260925T055540Z.dump` under the cutover directory,
55,604,722 bytes, SHA-256
`1577021c986650c1aaa5c08739f4b99dabf1b9942bdf3584a4928e932d2eaa54`.
Acceptance: `acceptance-20260925/party-gallery-deployment.json`; no customer photos,
PDFs or database backups were copied into this workspace.

## JCL ticket header and amount emphasis (2026-09-25)

Owner requested a bolder business name/amount and licence-specific proprietor in
place of the contact line beside the icon. Release `e5822c02` adds optional licence
proprietor fields (current record and immutable amendments), ticket projection and
editable bold V4 text frames. Existing layout hashes stay unchanged unless bold is
enabled. The embedded rupee font has a genuine bold face derived from the bundled
variable font, with no runtime font-building dependency.

The accepted September 24 source licence rows identify `J hanumanramji` for JCL
813/94 and `rajesh rathod` for 1513/2017. The reviewed template uses each loan's
licence, a 20pt bold business name and bold principal with bounded fit in its
existing amount cell. The icon, stationery, contact footer and other branch
templates remain unchanged. Native issued artifacts, including C07548, retain
original bytes; new first issues and reconstructed imported copies use the update.

Validation: 146 focused setup, native issuance/reprint, concurrency, imported-copy
and document tests pass across the main run and corrected typography fixture run.
Migration drift passes. Synthetic side-by-side PDF visually reviewed with the
same background assets/geometry; no customer PDFs exported. Migration 0020 and deployment completed. JCL layout revision 3 is active with hash
`45dd712739f1fb472108cd9da2831e4ac8b7c3a6500ef8b6a1afe30d576beda6`.
All four active series passed real imported-copy rendering; native C07548 rendered
with the revised template and correctly bound proprietor/bold fields. Its existing
issued artifact remains byte-identical, and authenticated preview returned HTTP
200. Authenticated native reprint and all-branch imported-copy checks pass. Loan
rows, events, approvals, issue counts and counters are unchanged by configuration.
The proprietor/address changes are audited licence amendments; the old published
layout remains intact. The initial geometry comparison stopped safely before
activation, preserving installed optional-photo/words-fit settings absent from the
older local pack. Reviewed geometry was re-rendered and checked before activation.

Image `rokkad:rc-20260925-e5822c02`; archive SHA-256
`eb443308488962ca741f440d35bd80940fa1458136f724a7efd69b9893f23180`.
Private evidence: `acceptance-20260925/jcl-header-deployment.json` and
`acceptance-20260925/jcl-header/{review,apply,verify}.json`. The same directory
contains `jcl-reviewed-layout.zip` and `jcl-profile.json` for recovery; do not
reinstall the older cutover pack over this accepted configuration.
Fresh server-only post-configuration backup `production-20260925T052701Z.dump`,
55,537,895 bytes, catalogue verified, SHA-256
`33129300f406986a61468b2120045c77264bbb6c82e745497fd74427880543c3`.
Native preview link: `/w/jcl/loans/setup/documents/revisions/3/preview.pdf?loan=19174`.
No old-server or DNS changes.

## Native ticket photo-evidence regression (2026-09-25)

JCL C07548 exposed a native first-print HTTP 500: the shared display helper reused
its source `evidence` variable for photo metadata, discarding the approval ID and
fingerprint required for issuance. Commit `a5a38bb9` separates photo evidence from
source evidence without weakening approval checks or altering loan data.

The exact KeyError was reproduced locally. All 73 setup/document UI, ticket
concurrency, imported-copy and issuance tests pass after the fix. Regression
assertions cover retained approval ID/fingerprint with present photos and an
optional absent portrait, real first issuance and immutable artifact reprinting.
Deployed `rokkad:rc-20260925-a5a38bb9`. Candidate rendering of actual C07548 passed
under a database-enforced read-only transaction. The deployed authenticated route
then issued its official one-page PDF and returned identical bytes/issue ID on
reprint. Approval evidence matches; loan, event, approval and numbering rows remain
unchanged. The temporary verification login session was removed. Public HTTPS
login also passes. No schema, old-server or DNS changes were made.

Source archive SHA-256:
`3fedd74c54797b68cf700dfe69dc81e0a6eccca390b5cce754f30d6219d51f99`.
Server-only pre-deployment backup `production-20260925T045224Z.dump`,
55,533,066 bytes, catalogue verified, SHA-256
`e08057fe6e4f7ded67e72db20d802ce68d7080c6b36b4bebfcddb9feedfd4da9`.
Private evidence under `cutover-20260924/acceptance-20260925`:
`native-ticket/acceptance.json` and `ticket-fix-deployment.json`.
Future shared ticket-display changes must run the rich-photo native issuance UI
tests as well as imported-preview/rendering tests; no-photo fixtures missed this
regression during the earlier preview release.

## Printable imported loan copies (2026-09-25)

Deployed release `55a6e0eb` adds the owner-approved **Print imported loan copy**
action after successful JCL/JSK preview review. It replaces the large watermark
only for that copy with a small **Reprinted from imported records** footer on every
page. Existing previews and native official ticket requirements remain unchanged.
Frozen source terms and original numbers/dates are preserved; current customer
contact/photo and template settings remain explicitly distinguished.

Validation: 84 focused rendering, issuance and imported-document tests passed;
migration drift and documentation-link checks pass. Local synthetic copy PDFs
were rendered and visually inspected. The candidate rendered 9 real samples across
all active series under a database-enforced read-only transaction. Deployed
authenticated HTTP checks pass in JCL, JSK and Lakshmi for the copy and preview,
button visibility, private/no-store responses and unchanged loan/event/approval/
issue counts and numbering. Test sessions were rolled back. Customer PDFs and
backup contents remain on the server. No schema, DNS or old-server changes.

Image `rokkad:rc-20260925-55a6e0eb`; source archive SHA-256
`7a1c6befa96b77cff1dc461d7296656b47851416d4e505d8abb41ce6545ea201`.
Private evidence under `cutover-20260924`: `acceptance-20260925/imported-copy/acceptance.json`
and `acceptance-20260925/copy-deployment.json`. Fresh pre-deployment backup:
`backups/operational/production-20260925T041251Z.dump`, 55,529,798 bytes,
SHA-256 `0874b84bea32887a7868fdff3f0d0d0a87044ef9847ecdd2351428db129c718d`;
archive catalogue verified. Previous image `660571b9` is retained for code rollback.

## Imported loan ticket preview and familiar series labels (2026-09-25)

Deployed release `660571b9` adds a separate read-only PDF preview for imported opening loans,
using accepted frozen source terms with explicit reconstructed/non-official marking.
Native official tickets retain their approval requirement. The new-loan picker
shows configured prefixes (or No prefix) alongside licence numbers instead of
internal LINODE codes. See the
[preview decision](adr/2026-09-25-imported-loan-ticket-preview.md).

The new button appears prominently and in Loan documents, including when a
repayment schedule exists. Current customer contact/photo and printed business
details are distinguished from frozen imported loan facts. Unverified source
valuations remain unknown; no current rates or fabricated approval are used.
The route generates an in-memory marked PDF with private/no-store headers;
it never persists an official issue, uploads an artifact or changes finance/counters.

Validation: 102 focused document, origination UI and ticket-evidence concurrency
tests passed; the final schedule-guidance refinement passed all 8 preview tests
(one additional regression). Migration drift and documentation-link checks pass.
Synthetic PDF pages were rendered and visually inspected locally. The candidate
rendered 9 real source samples across all active series in a database-enforced
read-only transaction. Customer PDFs and private evidence remain on the server.
Authenticated HTTP checks on the final deployed image pass all three branches:
correct series labels, prominent preview button, PDF response/marking/no-store
and unchanged issues/approvals/events/loan counts/counters. Temporary test sessions
were rolled back. JCL produced one page; JSK and Lakshmi produced two pages for
the selected samples. No schema, source-server, DNS or financial changes were made.

An actual Chrome loan page also showed the new button. Chrome's extension UI
blocked subsequent PDF-viewer automation. Automatic approval review separately
rejected copying server-generated QA images into OneDrive because their claimed
synthetic content was not independently established as safe for export. That copy
was not performed or retried; server PDF/HTTP checks and local synthetic visual QA
completed. Do not claim final real-customer PDF screenshots were inspected.

Image `rokkad:rc-20260925-660571b9`, source archive SHA-256
`09753c7d27192bfd6e202c78db5be0b36d1d91d539d5b7f967b36ed2f3363a4e`.
Private evidence: `acceptance-20260925/imported-preview/acceptance.json` and
`preview-final-deployment.json`. Pre-release server-only backup
`production-20260925T034552Z.dump` passed catalog validation, SHA-256
`38214eb5e5b396a216a0bc318b5233fcacaa588949ea6d3e90698cbb90e42340`.

## JSK unnamed-series continuation corrected (2026-09-25)

The owner reported the active unnamed JSK series showing a next number of 1.
Read-only diagnosis confirmed a migration defect in `linode_run.build_package`:
an empty source series name becomes the invented prefix `LEGACY1-`, and suffix
matching against that invented prefix finds no old numbers, leaving last-used 0.
Production series 8 / `LINODE-1` therefore had pawn sequence 15 configured as
`LEGACY1-`, width 5, next 1. Source JSK series 1 has 3,212 numeric loan records
(including closed loans), maximum 6,702, so continuation must be **06703 with an
empty prefix**. WH remains correctly configured for WH02145. The 599 operational
loans in the unnamed destination series are all imported openings: no new loans
or synthetic-prefix numbers have been issued there. Existing identifiers are intact.

Release `c55932cd` is deployed as `rokkad:rc-20260925-c55932cd`. Migration 0019
permits empty sequence prefixes in model validation and setup forms; the packager
preserves them and reserves the complete matching source range. All 31 focused
numbering, setup-service and Linode-run tests pass; migration drift check passes.
The restored-clone correction/next allocation/forward-only replay passed with
changes rolled back. Its first attempt failed only at rollback/context teardown;
the temporary operator script's context order was corrected before production.

The owner-approved production correction committed atomically under the restricted
runtime role through audited configuration/reservation services: sequence 15 now
has empty prefix, width 5 and next 6703; series 8 is named **Legacy unprefixed**.
Guard checks found no new/non-imported loans or synthetic-prefix numbers there.
All other JSK sequences, including WH and release, are unchanged. Full-row hashes
for all 1,514 JSK operational loans and their import records match before/after.
The deployed authenticated new-loan page returns HTTP 200 and preview data
**06703 / WH02145**; test-session writes were rolled back and no loans were issued.
Runtime migration/RLS startup and public HTTPS login checks pass. Host settings,
sealed source package, old site and DNS are unchanged.

Private evidence: `acceptance-20260925/numbering-{clone,apply,deployment}.json`.
Pre/post-change server-only backups passed archive-catalog checks. Post-change
`production-20260925T032545Z.dump` is 55,529,111 bytes, SHA-256
`ff42fb0b578677af3918d27001c71f69be404ae72856bf257f5c3924f0b327ca`.
These new backups were catalog-checked, not independently restored in this step.

The earlier new-lending acceptance exercised WH and missed the unnamed branch.
Future acceptance must check every active series, including numeric-only ones.
Preserve sealed package/import evidence and all new production activity;
never reimport or reset production to repair configuration.

## Approved staff access and Lakshmi ownership applied (2026-09-25)

The owner's explicit staff mapping is applied under the restricted production
database role. Five ordinary active users were added with their exact existing
Google subjects and matching verified source-email claims, unusable local
passwords and no Django staff/superuser flags. Dilip is Admin in JCL/JSK,
Hanumanram in JCL, Gopi in JSK, and Shankar is now Lakshmi's canonical Owner
through the audited ownership-transfer service. Rajesh remains Owner of JCL/JSK
and retains Admin access in Lakshmi. Membership counts are JCL 4, JSK 3, Lakshmi 2.

Umesh is JCL's only Member. The ordinary local-role editing service added exactly
`loan_approve`, `loan_disburse`, `loan_repay` and `loan_release` to JCL Member,
leaving every other role/Workspace grant set unchanged. This is a Workspace-wide
Member-role setting and applies to future members of that role. Umesh has customer,
draft and full selected daily lending access without setup/team/billing ownership
authority. The second Lakshmi address has approved conditional Admin access but
no membership or invitation yet: actual matching Google identity/email verification
is still required. The current target has neither a Google link nor membership
for that address. No fake provider subject or password account was provisioned.

Clone validation passed all 15 staff/Workspace access combinations (including
cross-branch denial), 15 dashboard responses and 18 new-loan/repayment/release
page responses, with all cloned writes rolled back. The first clone attempt
rejected an overlong membership reason; the operator reason was shortened to the
existing 64-character limit without changing application constraints. The same
validated operation then committed atomically in production. Independent read-only
verification confirmed six total users, nine memberships, correct canonical owners,
Google links and selected financial action permissions. Every branch number counter
is unchanged; no financial transactions or messages were submitted. Individual
staff Google callbacks still require their first sign-ins; the owner's real callback
was already verified. No old-server changes or live-domain DNS changes were made.

Private evidence is in `acceptance-20260925/staff-onboarding-{clone,apply}.json`;
the source identity bundle stays root-private on the server. A fresh pre-change
server-only archive passed catalog validation (SHA-256
`7c3ebb7fa0c02147ab9403f81201d80561e74e8a475f35370fb22613688505c5`).
The post-change server-only archive also passed catalog validation (55,527,393
bytes; SHA-256 `a287b8345b310308bc97438daca906e2982b2bc361b57b3963e9fa1f585b9d1d`).

## Production on temporary hostname (2026-09-25)

The owner explicitly selected real retained business transactions at
`rehearsal.rokkad.com` for one or two days, with the live-domain switch later,
and reconfirmed no old-source changes since the September 24 23:01 dump.
At 02:00 UTC the hostname was routed to `rokkad_production_20260924` using
`rokkad:rc-20260925-d078db38`. The older rehearsal web container is stopped;
its database/media are retained. No old-server or DNS changes were made.
Public HTTPS/login and production-specific secure cookies pass. Host allowlisting,
CSRF origin and the Django Site now use the temporary hostname. Owner Google
identity and all three Workspace ownerships are verified; no new business rows
were entered by the agent. All future business writes must survive the later
hostname change; do not restore the old snapshot over them.

The initial browser Google initiation failed with `redirect_uri_mismatch`.
After explicit owner approval, the existing OAuth client was saved with the
additional `https://rehearsal.rokkad.com` JavaScript origin and
`https://rehearsal.rokkad.com/accounts/google/login/callback/` redirect URI.
Both existing rokkad.com/www callbacks and the client secret are unchanged.
Actual Google sign-in as `rajeshrathodh@gmail.com` then completed successfully:
the browser showed "Successfully signed in as rajeshrathodh" and Owner access to
JCL, JSK and Lakshmi Pawn Broker. This verifies the external callback, beyond
the earlier mocked/initiation checks. No business transactions were submitted.
Current live-domain A/AAAA still point to the old server.

A subsequent read-only production access audit confirmed exactly one user, one
Google-linked account and one Owner Membership in each of the three Workspaces;
there are no other staff memberships. Legacy staff identities/permissions have
not been carried forward. Staff onboarding requires reviewed Google identities,
branch membership and roles. Outbound email still uses the in-memory backend, so
do not promise invitation-email delivery. No access grants were made by this audit.

The subsequent authorized read-only legacy review found six non-owner candidate
staff accounts across seven memberships in the three selected branches. Five have
exactly one Google identity with matching email and a verified provider claim;
one Lakshmi account has no Google link. The private source-derived mapping is
`acceptance-20260925/staff-access-review.json` on the new server, with no passwords,
tokens or Google subjects copied. Unrelated legacy workspaces/accounts are excluded.
The proposed mapping preserves branch scope, uses Admin for legacy Admin/Owner
memberships under the already-selected canonical owner, and carries no Django
staff/superuser privileges. At that review checkpoint, owner decisions were pending on those four Admin users,
the JCL Member's financial duties (the current Member role lacks approval,
disbursal, repayment and release), and inclusion of the unlinked Lakshmi account.
Production roles and unlimited seat capacity at that checkpoint were checked read-only;
no accounts, grants, role changes or invitations were created.

`rokkad-production-backup.timer` is active hourly. An initial server-only custom
dump passed its archive-catalog check (55,524,230 bytes; SHA-256
`787d68bc0a0be650d21cf11ababe923d3652cec1c0b416b570417735db608b2b`). The previously
restored post-configuration baseline remains intact. Hourly copies are under
`cutover-20260924/backups/operational`, protected by a non-overlap lock and a 5 GiB
free-space guard. This short-transition setup has no pruning, external alert or
off-server recovery; review retention/space and independent recovery promptly.
The original server-only backup preference remains in force.

Private deployment evidence: `temporary-production.json`, `production-release.json`,
`acceptance-20260925/temporary-production-identity.log` and operational `latest.json`.
The earlier sections below describe pre-activation checkpoints.

## Approved lending setup applied to isolated production (2026-09-25)

Release `d078db38` / image `rokkad:rc-20260925-d078db38` adds the explicit owner-only
document-pending continuation. The 118 focused tests pass; a separate fresh database
passed the 12 continuation tests, and the restored production clone passed upgrade,
migration drift and runtime startup checks. Image ID:
`sha256:74f1c89cc2f090f19ba703b79290968451582d42cbe8323dc04c060394f669fc`.
Clean source archive SHA-256:
`3666bda2122a6321ec332d352c732d8621bcd93a916d569d9219be58497f25be`.

The owner-approved configuration is applied through ordinary services under the
restricted role: all four existing licence identities continue from September 25
to January 10, 2030 with original documents explicitly pending, and all branches use
the reviewed JSK flexible-payment product and economics. Gold is 2% monthly,
silver 4%, with one advance period, simple/full-month calculation, 80% LTV,
lower-of-calculated/appraised valuation and a fixed INR 10 deducted document fee.
The owner supplied pure-metal buying references of INR 15,500/g gold and INR 255/g
silver for September 25. Required selling fields use the same valuation reference,
explicitly identified as having no separately supplied retail selling quote.

The restored-copy trial passed new-loan approval, actual configured ticket issuance,
disbursal and visible pending-document guidance in every branch. Tested next numbers
were JCL RA00585, JSK WH02145 and Lakshmi D01621. All test transactions rolled back;
the actual counters are unconsumed. JCL's accepted printed business name/address
were carried forward through new amendments after the first clone print correctly
rejected missing header fields. No TEST licences or borrowers were promoted, and
no GST file was substituted for licence evidence.

Before applying setup, production and clone contents matched the prior backup
(excluding the clone's new migration record). After applying it, all 161 tables
were compared: only the ten expected migration/licence/policy/product/rate/audit
tables changed. Every imported customer/financial row and number sequence remained
unchanged. Detailed results are in `acceptance-20260925/lending-preservation.json`.
Post-configuration backup restored to `rokkad_production_ready_restore_20260925`:
all 161 tables matched and runtime/RLS/migrations passed. Backup SHA-256:
`85dab079fbb313d1ba1120ab250de7ec10ab8ef9f3b8c4b3659ccc8fe68ffab2`.
The new image also passed non-root, read-only private web startup, Google login UI
and HTTPS redirect. `production-release.json` records the exact image/configuration
and recovery identity. The one assessed deployment warning is HSTS not yet enabled;
decide its rollout after production TLS is verified rather than claiming it passed.

Production compose (`127.0.0.1:8001`, separate static volume) and an additive Caddy
candidate are staged and syntax-checked. Static collection passed, but production
web is stopped and the proxy candidate has not been loaded. DNS still points both
`rokkad.com` and `www.rokkad.com` to `172.232.126.126` and
`2600:3c08::f03c:94ff:fe48:1618`; a switch to `172.235.9.64` must also update/remove
the old AAAA records to avoid split routing. This is preparation, not an approved
traffic switch. Actual Google callback/TLS, staff/access and server-loss recovery
arrangements and explicit owner routing approval remain outstanding. Backups remain
on the server as instructed; current owner access runs through October 8 plus grace.

## Final workflow acceptance and owner document deferral (2026-09-25)

Final restored-copy acceptance passed three-branch payment/release/reversal flows,
18 workflow page/PDF responses, 36 reader/editor/collector checks, three-branch
full/grace/read-only boundaries, forbidden-write checks and six private-media
readback/anonymous/cross-Workspace checks. Source placeholders remain labelled;
nonblank candidates are not presumed to be usable photographs. All 161 public
tables in both production and the restored copy match the post-import backup.
The private loopback-only web startup also passed as non-root with a read-only
container, Google login UI and HTTPS redirect; its temporary container was removed.
Actual Google callback and public routing remain untested/unchanged. Detailed
evidence stays in `cutover-20260924/acceptance-20260925/` on the server.

The owner then explicitly deferred original licence documents, confirmed both JCL
licences plus JSK/Lakshmi through January 10, 2030, and selected JSK's reviewed
configuration for all branches. An audited owner-only `ATTESTATION` continuation
now exists locally, retaining every source/numbering/RLS guard and visible pending
document status. The GST PDF is not used as substitute licence evidence. Normal
document verification remains unchanged. The focused 118-test suite and migration
drift check pass. Fresh migration, restored-target upgrade and application of the
approved settings are in progress; deployment/activation is not yet claimed.

The initial production trial ends October 8 at approximately 23:39 IST; grace ends
October 15 at the same time. There is one ordinary Owner Membership per branch and
no additional staff assignments. Actual sign-in, operational access arrangements,
current valuation prices and recovery policy remain to review before routing.

## Final import, media and local recovery verified (2026-09-25)

The final import exited successfully. All three branches passed complete Party,
opening-loan, closed-history and interest-evidence reconciliation: 8,639 customers,
6,391 outstanding loans and 39,215 closed-history records, with three approved
unused source exclusions. The continuation completed at 02:10 IST September 25
with state `MIGRATION_AND_LOCAL_RECOVERY_VERIFIED`.

All 28,422 verified media references are attached. An identical retry recognized
all attachments without duplicates; business fingerprints remained unchanged.
The 3,614 missing source files remain explicitly missing. Standard product draft
preparation and JCL/JSK template checks across imported series also passed.

The post-media backup remains server-only. Its restore to
`rokkad_production_restore_20260925` matched all 161 public tables and passed
restricted runtime, forced RLS and migration checks. Backup SHA-256:
`5c25cb320f32fd6a4850b37b73304095dd21c8d7210de186cab687bf8ad42401`.
Private evidence is in `cutover-20260924/finalization/completed.json` and
`run/backup-verification.json` on the new server. This verifies local recovery,
not off-server disaster recovery.

Public production web has not started and routing remains unchanged. Actual
Google callback, final workflow checks, staff/new-lending/access setup, recovery
policy and explicit owner routing approval remain outstanding. The completed
import does not by itself mean production is ready to open. The queued-state
sections below describe earlier checkpoints.

## Durable production storage configured; continuation queued (2026-09-25)

With explicit approval, account token `rokkad-production-runtime-20260925-v2` is
active with Object Read & Write access only to `rokkad-production-media`, with no
automatic expiry. Its credentials were transferred through a one-use loopback
form and SSH into a root-owned mode-0600 server file, then installed in the separate
production runtime environment. No credential file was saved in the local project.
The initial unused token that appeared in tool output was explicitly revoked;
Cloudflare rejects it with HTTP 401, and its server file was removed.

The replacement passed disposable-object write/read/list/deletion checks without
changing business objects. Existing JCL/JSK asset hashes and template retry passed
using the durable credential, as did Google login UI/initiation, restricted-role,
RLS and migration configuration checks. A new private workspace encryption key is
prepared for future channel credentials; no integration was enabled. Public web
and routing remain closed/unchanged. The temporary migration token remains separate
and expires September 28; it has not been revoked while migration/rehearsal use remains.

Server unit `rokkad-cutover-finalize-20260925.service` is running and currently
waiting for exact database reconciliation. On success it prepares the standard
product drafts, checks templates across all imported series, plans/attaches the
28,422 verified media references, verifies an identical retry and unchanged business
fingerprints, then creates a server-only backup and restores it to
`rokkad_production_restore_20260925` with full table comparisons and runtime/RLS checks.
It stops on any error and never opens web, changes DNS, contacts payment/messaging providers or enters
synthetic business transactions. Private state/logs live in
`/home/rokkad/deploy/cutover-20260924/finalization/`. These queued steps are **not yet
reported complete**. Actual login, final journeys, licensing/new-lending and access
dates, recovery policy and owner routing approval remain separate gates.

## Final media source capture completed (2026-09-25)

All 32,036 exact media references in the final September 24 archive were checked
read-only against the old server. **28,422 references** have hash-verified private
R2 originals: 28,347 existing copies passed read-back verification and **75 files**
were newly copied. The same **3,614 source files remain missing**; no shared-path
candidates were substituted. JCL has 11,664 preserved / 3,159 missing references,
JSK 4,722 / 455, and Lakshmi 12,036 / 0. This is a complete bounded path/read pass,
not an atomic filesystem snapshot; checks ran 18:12:51–18:35:33 UTC September 24.
The old site and services remain unchanged.

Sealed final media references SHA-256:
`3316eef14ef0f537dc90d6fe0eadb1d7b86289dcc03de04f1be5c8f9240f82d8`.
Customer-photo evidence SHA-256:
`cca7719930a50f4db05d1d4b5b4da45135f3e0204f337cb71da40d1a9150b1e9`.
The exact production media target is bound to the actual database/server, restricted
role, source and Workspace IDs; target SHA-256
`e3053687d6f62fa6bad63a13ee3f2d16192a6b1c32b0b730a24acb1538fc6bbd`.
Detailed batches and seals remain server-only in `cutover-20260924/media/`.
Database admission/reconciliation is still running; application-media planning
and attachment wait for its successful completion.

The owner explicitly approved Cloudflare dashboard preparation and creation/private
transfer of a bucket-only, non-expiring production R2 runtime token. The first
unused token was exposed in tool output during navigation, then revoked and
replaced with explicit approval as recorded above. It was never installed in the
application configuration.

## Final package sealed; clean production import started (2026-09-24)

The owner explicitly requires the old site to remain unchanged. Its Gunicorn
service remains running; the staff write pause is operational, not a technical
freeze. Any new source entries require renewed reconciliation before switching.
The owner confirmed JCL RA00575/C07545 and JSK WH02133 are outstanding; JCL C07537
is unused/cancelled. Earlier unchanged decisions remain source-hash bound.

The complete September 24 package is sealed as
`650becbb16bcd44c2cb9af2281eaeb3d5497dda72a546aaa790b2cc125028400`.
It prepares 8,639 customers, 6,391 outstanding loans, 39,215 closed-history records
and three unused exclusions. Opening balances are dated September 24;
post-opening servicing requires September 25 or later. Detailed source, decisions
and package evidence remain under `/home/rokkad/deploy/cutover-20260924/` only.

Clean database `rokkad_production_20260924` has passed owner migrations and runtime
grants with distinct `rokkad_prod_owner` / restricted `rokkad_prod_runtime` roles.
Workspaces JCL/JSK/Lakshmi have ordinary Owner Memberships for the chosen Google
identity. Explicitly approved Google configuration/subject transfer completed
directly over SSH into a root-private file; credentials were not printed or saved
locally. The existing subject is linked in the new database. Restricted runtime,
forced RLS, migration completion, visible Google login UI and login initiation
checks pass; the redirect uses the existing client and canonical production callback. Its test
session rolled back, with no provider request or mail. An interactive Google
callback is not yet verified. Initial 14-day trials are preparation state, with
production access dates still to review before opening. No checkout or mail ran.

Source `9ab5e4bd` adds explicit allauth proxy-hop configuration, defaulting to zero;
the single-Caddy production topology is configured for one hop. Seventeen focused
deployment/Google compatibility tests passed. The clean image is
`rokkad:rc-20260924-9ab5e4bd`, ID
`sha256:58c6b97a1586e3ee05238930c92f30c017fe889475b16a797204c17ebd2dcbfc`.
Rehearsal remains on `fd011920`. Exact final-source verification passed and the
isolated production admission/reconciliation job has started; completion is not
yet claimed. Public production web/routing remain unchanged.

Accepted JCL and JSK layout/profile pairs are installed as production Workspace
defaults (new target revision/profile IDs 1/1 and 2/2); background read-back hashes
and identical installer retry passed. These preserve the ₹ format, optional
borrower photo and JSK preprinted-stationery correction. JCL had seven imported
series at installation; JSK series were not yet admitted. Repeat the complete
series assignment check after import, and prepare the standard draft loan products
for these operator-created Workspaces before opening new-lending setup.

Temporary R2 credentials are now explicitly authorized for final migration into
`media/application/production/linode-rls`, not continuing production operation.
The final dump has 32,036 media references; fresh exact-path checks and conditional
R2 copy/read-back verification are running, with batch evidence retained privately.
Fresh media completion/admission, final reconciliation, recovery verification, durable
runtime credentials and final routing approval remain outstanding. The earlier
rehearsal-only credential limitation is superseded only for this approved migration.

## Final-source candidate supplied; branch freeze reported (2026-09-24)

The owner supplied `C:\Users\rajes\backup_20260924_230136.sql` after today's entries
and confirmed all three branches stopped writes after this backup. This is the
candidate final snapshot, not an independently verified technical writer freeze
or authorization to change production routing. The file is an 11,711,243-byte
PostgreSQL custom archive despite its `.sql` extension; SHA-256
`e2c91ded1d56b6391c0a9dc9c72f0392238490c654612ba477a8e002d5de09e6`.

Read-only `linode_migration check-source` validated the previous package's seals
and compared this archive with the September 23 snapshot without executing SQL.
JCL adds 35 loans, JSK 18 and Lakshmi 23 (**76 new source loans**). JSK adds 29
payment and 29 release rows; Lakshmi adds 24 of each. Existing changes comprise
30 JSK loans, 24 Lakshmi loans and two Lakshmi addresses. No rows were removed
within the adapter's inspected tables. Counts describe source rows, not yet
accepted operational classifications or reconciled opening balances.

The changed archive requires new Party/opening/closed-history preparation and
review, including the new payments/releases, opening-date recalculation, final
media delta and target bindings. Nothing was imported or copied into the project
folder; detailed source records were inspected in memory and only aggregates
reported. Authentication/proxy, production setup and recovery requirements remain.
Keep old writes paused; if they resume, this snapshot must be superseded. See the
[final-source checkpoint](implementation/linode-production-cutover.md#september-24-final-source-candidate).

## Recovery and daily-workflow acceptance completed (2026-09-24)

On image `rokkad:rc-20260924-fd011920`, the latest server-only backup restored into
`rokkad_acceptance_20260924` with all **117** checked table fingerprints matching
in **38.98 seconds**. Restricted runtime/RLS and migration checks passed. Across
JCL, JSK and Lakshmi, partial-principal repayment, receipt, full release, memo,
idempotent retry and newest-first reversal passed, restoring original exposure;
18 page/PDF responses passed. All financial changes were rolled back in the
disposable copy, with container-local document storage and no shared R2 writes.
Reader/editor/collector probes passed another **36** page/permission checks.

The existing administrator browser session, borrower filter and prominent loan
date/ticket action passed fresh browser checks, including phone/tablet layouts.
Hindi switching works but recent labels remain partly English. This does not
establish actual staff acceptance, Google login or visual receipt/memo approval.

The next technical increment is concrete authentication/proxy configuration:
rehearsal has no Google app configured, and allauth trusts zero forwarded hops,
so the inspected Caddy topology can group clients under one IP-based login limit.
Hosted HTTPS/secure cookies are enabled; HSTS is already 3,600 seconds. Cloud
firewall rules were not inspected. Production credentials, actual staff/lending
setup, recovery destination and the new frozen-source import remain to be reviewed.
No production routing, shared media or application code changed. See the
[acceptance report](implementation/rehearsal-acceptance-20260924.md).

## Dependency refresh verified and deployed to rehearsal (2026-09-24)

The owner's installed updates are now recorded in fourteen direct pins and matching
constraints, including Django 6.1.1/allauth 65.19.4 and the additionally updated
PyJWT 2.15.0. The corrected candidate is source `fd011920`, image
`rokkad:rc-20260924-fd011920`, image ID
`sha256:55ad097dc208746fed3f9417a68e357e13c2062f979c89a099087f2458fad934`.

The final Linux image scan checked **71 distributions, zero skipped, zero known
advisories**, with no ignore list. This clears the earlier Python dependency gate.
The final broad regression passed **1,911 tests across 202 modules** in 684.503
seconds. A real Select2 upgrade regression was fixed: borrower autocomplete now sets
its signed URL token after base attribute construction. Existing cache-unavailable,
expiry, separate-worker, RBAC and cross-Workspace checks remain intact. Five new
Google token compatibility tests are included in CI; no real provider calls ran.

Fresh/restored migrations, non-root static/startup, owner-role rejection, draft-product
creation/rollback and runtime access probes passed, preserving 116 existing tables
in the restored copy. After a server-only backup, the rehearsal image was switched
and HTTPS home/login checks passed. Rehearsal verification preserved all **117**
checked business, preference, user/membership/social-account and access-decision
tables. Synthetic password login, borrower search in all three Workspaces, subscription
boundaries and existing JCL/JSK PDF checksums passed; all synthetic mutations rolled
back. Production routing remains unchanged. No financial writes or remote Git push
were performed. See the [refresh report](implementation/dependency-refresh-20260924.md).

Next is final operator acceptance and production cutover preparation: actual login
and staff journeys, reviewed production configuration/credentials and recovery,
then the complete frozen-source snapshot/import described in the cutover runbook.
Known-advisory clearance is not a blanket security certification or cutover approval.

## Consolidated release candidate validated; security gate blocked (2026-09-24)

The owner authorized consolidating the rehearsal increments into one versioned
release candidate. Source `520c8ecb` is on `release/2026-09-24-rc1`, with an ordinary clean-source
Docker build, pinned Python image/dependency constraints, template-installer inclusion
and CI coverage for the new boundaries. The existing tracked SQL backup is removed
from this branch's index while its local file remains intact; private artifacts are
excluded. Fresh and restored-upgrade migrations passed, preserving all 99 existing
Party/Loans/subscription tables and five preference/audit tables. The final
201-module regression passed **1,906 tests** in 668 seconds after correcting obsolete
assertions and access fixtures; no application-policy or audit-guard weakening was
needed. Documentation links, import boundaries and whitespace checks passed.

The clean image is `rokkad:rc-20260924-520c8ecb`, image ID
`sha256:e4942264d0300fe9395cab8eb864fa6a65a3e6f7cfbfe929f869fca3737e5f9c`.
It passed restricted-role startup, non-root static collection, owner-role startup
rejection, packaged ticket-installer and dependency-consistency checks. Fresh and
restored databases passed both automatic draft-product creation paths and rollback
probes. All three restored Workspaces passed owner/staff access-policy checks and
JCL/JSK saved PDF checksum checks. Existing contents in all 104 checked tables were
preserved. Private database backups/evidence remain on the server.

The final-image dependency advisory scan checked 72 distributions with zero skips
and flagged 11 packages, including Django/allauth. This is a production promotion blocker;
the candidate must not be described as production-ready merely because functional
checks pass. See the [candidate report](implementation/release-candidate-20260924.md).
Rehearsal remains on its prior image; no production cutover or repository push is
part of this assembly step. Next: review advisories, update direct dependency pins
and constraints together, rebuild and repeat validation before production promotion.

## Subscription access continuity deployed (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-access-continuity-v2-20260924`
(`sha256:6e1f1ede2833fc3fd79a2f73f7c9729b15a65e5861a1e658688dc80a018d35d6`).
Natural trial/paid-term expiry enters seven days of normal access, then read-only
lists/details/reports, saved documents and permitted exports. Staff receive an
explanation and owner contact guidance rather than an owner-only Billing redirect.
Platform administrators can record dated full/read-only decisions and return to
normal policy from Billing > Platform access controls or the audited command.
Latest decisions replace earlier ones without rewriting subscription/payment dates;
suspension/archive, RBAC and RLS remain independent. New checkout is disabled by
default until provider acceptance; existing payment evidence/reconciliation paths
remain intact. Servicing-only access is deferred as FW-008.

Ninety-four distinct targeted tests passed across access policy, billing, checkout,
notification delivery, automatic product preparation and opening exports. The
Billing-layout banner correction passed its additional regression run. Migration
drift and diff whitespace checks passed. Owner-only additive migrations 0010/0011
passed on a restored hosted copy and the rehearsal database. Comparisons preserved
all 99 existing Party/Loans/subscription tables through migration, rollback probes
and extension recording. Under `rokkad_runtime`, all three Workspaces passed owner
and staff read/denial checks, grace/extension/revocation boundaries, immutable audit
evidence and lifecycle precedence. Saved JCL/JSK PDF bytes matched their checksums;
Lakshmi had no existing issued PDF for that check. Synthetic users, memberships,
expiry changes and test decisions were rolled back. No loan financial transaction,
provider call or outbound notification was performed.

The final candidate matched all 37 packaged source files and passed ordinary-owner
Billing checks for all three Workspaces. HTTPS recovered after restart; Chrome
confirmed the platform form/history and visible dated access banner on Billing.
Real normal-access decisions 13/14/15 cover JCL/JSK/Lakshmi until **2026-10-24 23:59
Asia/Kolkata**, using the existing platform administrator and an explicit interim
rehearsal reason. Existing subscription and entitlement records were preserved.

The private backup, restored-copy validation and aggregate evidence stay on the
server under `/home/rokkad/deploy/rehearsal/access-continuity-20260924/evidence/`;
the database dump is referenced by its private `backup.json` and remains server-only.
Prior images and both `web-compose.before-access-continuity[-v2]-20260924.yml`
snapshots are retained. The final production release must include this increment,
apply its migrations and review actual target Workspace access dates separately;
production cutover remains pending. See the
[decision](adr/2026-09-24-subscription-access-continuity.md),
[operator guide](domain/subscriptions.md), and
[cutover requirements](implementation/linode-production-cutover.md).

## Automatic draft loan products deployed (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-product-defaults-20260924`. Both customer
Workspace creation services prepare the four standard product drafts after Owner
Membership creation, in the same transaction and explicit RLS context. A failure
rolls back the Workspace and its setup together. Nothing is automatically enabled.
Loan setup now offers “Choose your lending products” and “Enable for new loans,”
with repayment, term, grace and availability review; the manual seed button is
removed. The existing authorized POST remains compatible, and the idempotent
operator command remains the documented existing-Workspace/recovery path.

Twenty distinct targeted tests passed after correcting the new test's allowed-host
fixture. Coverage includes both creation paths under a restricted SQL role,
cross-Workspace isolation/context cleanup, rollback after product preparation,
preservation of custom terms/names/active/retired states on retry, activation-only
form availability and existing setup authorization/lifecycle behavior. Hosted
creation/retry/failure probes also passed under `rokkad_runtime`; their synthetic
Workspaces were rolled back. All three product pages passed ordinary-owner checks.

Existing-record comparisons passed before and after preparation: JCL and JSK needed
no additions; Lakshmi received four missing DRAFT versions. Existing product records
were unchanged, with no schema migration or financial transaction. The deployed JCL
page passed browser/desktop visual verification and HTTPS passed after restart.
Private configuration snapshots and aggregate evidence remain on the server under
`/home/rokkad/deploy/rehearsal/product-defaults-20260924/evidence/`. The prior image
and `web-compose.before-product-defaults-20260924.yml` remain available for rollback.
Final production must include this code and explicitly prepare existing/import-created
Workspaces as documented in the cutover runbook; production cutover remains pending.
See the [decision](adr/2026-09-24-automatic-draft-loan-products.md).

## Guided legacy migration captured for future work (2026-09-24)

At the owner's request, [FW-007](plans/future-work.md#fw-007-guided-customer-facing-legacy-migration)
now explicitly tracks a guided customer-facing legacy-import journey: source and
column mapping, borrower/setup resolution, history/opening/archive classification,
missing-evidence review, reconciliation, preview, approved import and safe retry.
It records the existing foundation, remaining operator dependency, acceptance
criteria and resume trigger. This is unscheduled future work; no implementation,
deployment or data import was performed for this documentation update.
The owner's follow-up scenarios are now explicit in FW-007: start fresh in a new
series with paper history left outside, or continue new lending while migrating
existing paper loans through proposed manual/Excel intake. Existing-borrower
matching, numbering separation, per-loan/batch handover and partial-portfolio
coverage are recorded as design/acceptance requirements, not delivered UI features.

## Loans by year deployed (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-loan-years-20260924`. Reports > Loans by year
groups all operational loans by their original calendar loan year, with current
active/closed/cancelled/draft-or-approved counts and canonical active principal at
the selected report date. Two charts show counts and active principal. Year links
open the corresponding date-filtered loan list. Full CSV/XLSX/PDF exports are
available; charts combine earlier years beyond the latest twelve, while tables and
exports retain every year. Import timestamps and historical archive-only records
are explicitly excluded from the grouping basis/scope. Unavailable active balances
are counted rather than silently treated as zero.

Fourteen targeted tests passed, including original-date grouping across current
states, unavailable balances, financial selector regressions and all analytical
export formats. Hosted counts, active principal, CSV totals and every year drill-down
matched canonical source records in JCL (4 years / 2,406 loans), JSK (7 / 1,525) and
Lakshmi (5 / 2,440). Browser verification confirmed report selection, year/state
counts, formatted totals and no chart errors. HTTPS passed after restart. No schema
migration or financial action was performed. Aggregate evidence remains server-only
under `/home/rokkad/deploy/rehearsal/year-report-20260924/evidence/verification.json`;
the previous image and `web-compose.before-loan-years-20260924.yml` are retained.

## Borrower filters and portfolio analysis deployed (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-portfolio-analysis-v2-20260924`. The loan list
has a dedicated borrower name/code/phone filter and exact, Workspace-validated
borrower links from customer details, loan details, loan-list borrower names and
the statement directory. Inactive borrowers remain included; filters compose with
status/licence/series/date and persist across pages. A selected borrower is clearly
labelled and can be removed without clearing the other filters.

Reports now offer four additional sections with charts, full tables and CSV/XLSX/PDF:

- Active totals by licence: count, recorded principal/interest/total due, overdue
  count and unavailable-balance count; licence links open its active loans.
- Active totals by series: the same figures, with licence-qualified series labels
  and links to active loans in the series.
- Collateral by metal/custody: item count, known gross/net weight in grams, known
  approved appraisal sum and missing-evidence counts. Current active holdings in
  vault/with funding lender are included; released/transferred source items are not.
- Maturity profile: not past maturity, 1-30, 31-90, 91-180 and over 180 days past
  maturity, with principal/counts. This is maturity ageing, not instalment DPD.

Money uses the canonical recorded balance fold at the selected date, with current
active membership. Collateral values are latest dated approved appraisal references,
not current market values or lending coverage. JCL has 2,421 items missing gross
weight and approved appraisal; neither field is invented. Incomplete sums/charts
are labelled, and unverified legacy valuations remain excluded. Chart grouping
after twelve categories never truncates tables/exports. Currency displays use the
rupee symbol; chart tooltips retain exact formatted values and phone axes use
compact labels. PDF report scope uses a normal paragraph beneath the title.

Validation: 23 distinct targeted tests passed, covering borrower filters/inactive
customers, pagination regressions, canonical repayment-adjusted grouping, repeated
series codes across licences, maturity boundaries, missing balances, latest approved
appraisals/date cutoffs/custody and all three export formats. Twelve hosted analytical
pages (four sections in each Workspace) matched canonical active counts/principal
and current item/net-weight aggregates. Their complete CSV totals and all group
drill-down counts matched; the seven existing JCL CSV hashes remained unchanged.
Borrower pagination and cross-Workspace denial passed under the restricted runtime
connection. Four additional page checks passed after the display-only polish.

Browser checks passed for report discovery, licence drill-down, combined borrower
search, exact borrower links, collateral/maturity charts and desktop/390px layout;
no chart errors were logged. Individual hosted active summaries took 2.2-3.7 seconds;
collateral summaries took about 0.1 seconds. Complete balance aggregates still read
the whole active portfolio; these timings are not a load-test guarantee.
HTTPS passed after restart. No migration or financial transaction was performed.
Aggregate evidence remains server-only at
`/home/rokkad/deploy/rehearsal/portfolio-analysis-20260924/evidence/verification.json`.
Prior images and `web-compose.before-portfolio-analysis[-v2]-20260924.yml` remain
available for rollback. Production cutover has not been performed.

## Focused operational reports deployed (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-report-pages-v3-20260924`. Reports select one
of eleven sections; record lists paginate 50 source records before loading related
evidence. Borrower statements have name/code/phone search. Selected dates, source
links and pagination filters are preserved. Full portfolio summary and existing
CSV/XLSX/PDF downloads remain Workspace-wide; they intentionally still calculate
the complete portfolio. Integrity pages explicitly cover only the 50 loans checked
on that page, potentially with multiple findings per loan.

The integrity checker now recognises migration-opening events as valid financial
origins alongside disbursal and renewal-opening events. This removes 2,404 false
missing-disbursal warnings in JCL without suppressing balance derivation errors or
other evidence checks. No financial data or calculations changed.

Validation: 20 distinct targeted report selector/export/UI tests passed, including
bounded database reads, complete exports, date-sensitive reversal evidence and
opening-origin validation. Hosted checks passed for all eleven JCL sections,
next/last pages where applicable, and default reports in JSK and Lakshmi. All seven
full CSV datasets matched baseline hashes; complete summary totals matched the
canonical report; other integrity findings were unchanged. Browser checks passed
for pagination, statement search, selected date and desktop/390px layout. After
deployment JCL summary displayed zero integrity findings with unchanged totals.

A single hosted comparison measured default JCL report generation at 6.148 seconds
and 2,203,055 HTML bytes before, versus 0.289 seconds and 53,662 bytes after. This
is an observed comparison, not a performance guarantee. HTTPS passed after startup.
No schema migration or financial actions were needed. Aggregate verification stays
server-only at
`/home/rokkad/deploy/rehearsal/report-pages-20260924/evidence/verification.json`.
Previous images and `web-compose.before-report-pages-v3-20260924.yml` are retained.
Staff usability acceptance and final production cutover remain separate work.

## Staff workflow review and fixes deployed (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-staff-ui-20260924`. Borrower/loan search and
work queues now precede dashboard analytics; a Business overview shortcut keeps
those figures accessible. Loan details expose a Payment receipts section and
navigation link when repayments exist, with direct print links to the original
receipt route. Reversed payments retain their receipt with a clear reversed label.
Read-only customer views now hide edit, photo, role, contact, address, relationship
and merge controls using the existing canonical edit permission. Direct routes
retain their existing enforcement; a viewer's merge-tab bookmark shows Overview.
Release batches no longer highlights Releases simultaneously in the sidebar.

Validation: 54 customer/receipt-navigation/counter tests and one repayment-only
role integration test passed (55 total). The latter verifies the receipt source
link after repayment and preserves revocation/replay denial. On the candidate
image, 36 hosted page checks passed for explicit reader, editor and collector
roles under the restricted runtime connection. All temporary users, roles,
memberships, grants and test sessions were rolled back. Membership denial follows
the existing redirect to Workspace selection; forbidden operations return 403.
No hosted financial actions or official PDFs were submitted. Existing financial
rehearsal acceptance is unchanged.

Browser checks covered dashboard search to loan, collection screen, release list,
reports, deployed dashboard at desktop/390px, Business overview navigation and
retained administrator customer controls. There are no current hosted REPAYMENT
events in the three Workspaces, so receipt rendering/source/reversal behavior was
verified in automated fixtures, not a live receipt print. HTTPS passed after
startup. No schema migration was needed; previous image and Compose are retained.
Server-only aggregate evidence:
`/home/rokkad/deploy/rehearsal/staff-workflow-20260924/evidence/verification.json`.

**Resolved by the reports increment above:** the JCL operational report rendered 7,248 table
body rows, many borrower statement links and no section shortcuts. Replace the
all-in-one report with focused selection and pagination while keeping selected-date
and export semantics. Do not treat the existing HTTP 200 as a usable report at
production volume. This review is technical workflow verification, not full staff
acceptance, Hindi/device coverage or production-cutover approval.

## Preferences dependency retired and loan number/date UI simplified (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-prefs-retired-20260924`. Removed
`django-dynamic-preferences` and its unused `persisting-theory` dependency from
requirements and the deployed image, along with obsolete registries, services,
forms and templates. Existing Workspace/company raw models are ordinary Django
models. Migration `configuration.0003_retain_legacy_preference_data` adopts
existing global/user tables or creates them on fresh installs. All existing raw
values and audit history remain; retained models do not drive business settings.
The user relationship remains in Django's deletion graph. Old migration history
and content types are retained; no preference data purge was performed.

New-loan forms show only the selected series' expected number, with live updates,
a clear unselected prompt and unavailable-number errors. This remains a preview;
allocation still occurs atomically on save. Loan details show the business loan
date immediately below the heading and separately label the draft creation time
or, for imported loans, the time imported into Rokkad.

Validation: 17 initial configuration/route/number-allocation tests and 10 focused
retention/preview/draft-page tests passed. An isolated fresh database migrated
without package migrations. A restored rehearsal clone with synthetic preference
rows retained all five preference/audit tables byte-for-byte and left 87 loan and
party tables unchanged; both databases passed migration drift checks. Twelve
ordinary-owner hosted page probes passed before and after the owner-only
rehearsal migration, including anonymous/cross-Workspace denial. Browser checks
confirmed selected/inactive/empty-series behavior and prominent date placement.
No financial actions or official PDF issues were submitted. HTTPS recovered from
brief startup 502s and passed. Previous image/Compose are retained for rollback.

Migration evidence and the pre-change backup remain server-only under
`/home/rokkad/deploy/rehearsal/preferences-retirement-20260924/` and `backups/`;
page/preference evidence is under `ui-readiness-20260924/evidence/`. The two
isolated validation databases remain on the server. This completes dependency
retirement; broader staff journey acceptance and final production cutover remain
separate work. See the [decision](adr/2026-09-24-retire-preference-editing-surfaces.md).

## First preferences/navigation readiness cleanup deployed (2026-09-24)

Rehearsal now runs `rokkad:rehearsal-ui-20260924`. Central and legacy preference
bookmarks show authorized read-only guidance to real settings; POST is rejected.
The generic dynamic-preferences editor route and sidebar Preferences link are
removed. Workspace preference admin is read-only. Five preference/audit tables
were privately inventoried on rehearsal and contain zero rows; no data or schema
was deleted. At this first checkpoint, the package, model bases and compatibility code were
retained; the subsequent retirement is recorded above. See the [retirement decision](adr/2026-09-24-retire-preference-editing-surfaces.md).

Reports, Historical loans and Release batches now have visible Records & reports
entries, including for data readers without Settings access. Setup labels are
clearer and the overlapping Preferences link is gone. Loan details keep balances,
terms, printing and next actions visible; valuation, collateral and history are
grouped into disclosures. Collateral starts open for approval review and history
for closed loans. Fragment links open/focus their containing section.

Eight focused route/authorization/navigation tests passed under test settings;
12 ordinary-owner hosted page checks passed, including denied preference writes,
anonymous denial and a cross-Workspace loan denial. Browser checks passed at
desktop and 390px phone widths: mobile navigation, collateral/history links and
keyboard expansion. Rehearsal returned HTTP 200 after a transient startup 502.
No financial actions or official PDF issues were submitted. Previous image and
Compose file are retained for rollback. Server-only inventory/verification:
`/home/rokkad/deploy/rehearsal/ui-readiness-20260924/evidence/`.
See the [feature map](flows/workspace-feature-map.md). Wider staff journey acceptance
remains open; this first release was not full production
readiness or a complete application redesign.

## Pre-cutover preferences and UI review (2026-09-24)

The owner raised production-readiness concerns about legacy preferences,
navigation, discoverability and crowded screens. Initial repository inspection
found the dynamic-preferences package still wired to models/forms/routes, but no
current business consumer of the central preference service or legacy wrapper
outside their implementation/tests. Retired accounting/legacy loan settings remain
registered and exposed. Bootstrap is already loaded; navigation placement and
screen hierarchy need review. This is not a completed browser usability audit.
See [findings and proposed scope](implementation/production-readiness-ui-preferences-review.md).
No preferences were deleted, business behavior changed or deployment performed.

## Rehearsal ticket shortcut and media exception review (2026-09-23)

The loan details page now shows a large **Print loan ticket** action directly
below its heading for APPROVED/ACTIVE loans that satisfy the existing ticket
eligibility flag. Drafts, loans without approval evidence and closed/cancelled
loans do not receive the prominent action; their existing document section is
unchanged. It opens the ordinary ticket PDF route in a new tab. No issuance,
approval, disbursal or permission rules changed. Seven state/eligibility render
cases, the actual hosted JCL practice-loan page, anonymous denial and HTTPS passed.
The template-only image `rokkad:rehearsal-ticket-button-20260923` is deployed to
rehearsal; the previous Compose configuration/image remain available for rollback.
Candidate verification initially lacked the collected-static volume; mounting the
existing volume read-only resolved that verification setup failure before rollout.
No new official ticket was issued by these checks; physical printing is untested.

All 3,614 remaining exact branch paths were rechecked read-only on the old Linode
and remain missing. The exception review resolves them to 102 active collateral
references, 3,507 historical references and five customer photographs. Of these,
2,465 have no preserved shared candidate; 1,149 have unverified shared candidates.
The latter contain 1,144 known blank images and five unverified customer images.
344 exception references use a path also referenced by another branch; path/name
matching cannot certify ownership. No shared candidates were attached and no
financial data changed. Detailed results are server-only under
`/home/rokkad/deploy/rehearsal/media-exceptions-20260923/`; retained originals and
all 28,347 completed attachments are unchanged. Record these as unresolved media
exceptions for final cutover; do not claim complete photo recovery.

## Hosted database imported and verified (2026-09-23)

**Hosted media increment verified:** 28,347 references are attached using
29,489 separate private application objects: 1,148 Party photographs, 6,082 active
collateral and 21,117 historical-loan photographs. All receipt/target bindings and
object keys/sizes reconcile. Each copied object was read back and SHA-256 verified.
All 32,567 earlier preservation objects remain intact; 55 new originals bring
the retained total to 32,622. Fifteen ordinary-owner HTTP
probes passed exact-byte/private-cache checks plus anonymous and cross-Workspace
denial. All 252 before/after business-data fingerprints match. Of the attached
references, 25,054 match previously confirmed blank-source-image hashes; transfer
success does not make these usable photographs.

The main 28,223-reference plan SHA-256 is
`10e9f5ea7340fd7de907670c79d100657c7a6f6ea4793adc9e49471b15c17f33`;
its planning took 208.94 seconds and apply/recheck took 1,883.56 seconds. A second
69-reference plan reused exact branch files preserved before their new database
references appeared (SHA-256
`3284853c5f10a1e832170e099afcc720dd98a00fc3689cf780fab44631dc3730`).
Both full identical retries recognized all 28,292 existing attachments and
created nothing. The main process completed successfully; a lingering SSH client
was closed after its aggregate success report and exited server process were
verified independently.
This is hosted rehearsal, despite the target-bound command's generic
`PRODUCTION_MEDIA_ATTACHED` label; `production_ready` remains false.

The owner authorized checking/copying the remaining 55 newer references. All
were found on the old live Linode (JCL 27, JSK 9, Lakshmi 19), read without source
writes, copied directly to private R2 with conditional creation and SHA-256
read-back verification, and attached as active collateral photographs. Increment
plan SHA-256: `ce9a08dcc9133654462a34b9ea30dfe9d543557d00f0e84cac5601f90508c215`.
Apply created 55 receipts; identical retry recognized all 55 and created nothing.
All 252 business-data fingerprints still match. The 15 private-access probes
include a newly attached photograph in each Workspace. Of these 55 source files,
53 match known blank-image hashes; copying cannot recover absent image content.
Still excluded: 2,465 previously missing files and 1,149 unverified shared
candidates. Only the 55 paths received a fresh source check; older preserved
bytes date from September 21 and later same-path replacement is not ruled out.
Authoritative detailed evidence stays on the server under
`/home/rokkad/deploy/rehearsal/media-reuse/` and `media-increment-20260923/`.
Local preparation inputs/scripts are
under `outputs/server-rehearsal-20260923/`; do not claim a local copy of completed
reports. Automatic approval review rejected exporting the full dump and recursive
customer/media-reference metadata to OneDrive. The owner chose to keep the backup
on the server; detailed reports also remain there.

Latest post-increment backup:
`backups/rokkad_cutover_rehearsal-media-20260923T111730Z.dump`
under the host deployment directory; 55,446,392 bytes; reverified SHA-256
`ec603f5a5d62487611f3d5f7f34dc3f89fc07a5395201758e11e29ef7a8a017a`.
The preceding `20260923T105639Z` snapshot is retained. The increment completion
manifest seals 26 private evidence files on the server.
The earlier full restore check is retained separately; this new snapshot has not
received another full restore test and was not downloaded to OneDrive.

**Ticket cutover readiness:** the owner requires JCL/JSK templates ready by default
at production reopening. Latest configuration is exported to private
`outputs/server-rehearsal-20260923/cutover-templates-final-20260923/`, superseding
the earlier production-readiness exports. `scripts/install_cutover_ticket_templates.py`
verifies explicit database/host/runtime-role/storage/mode and manifest bindings,
imports/reuses configuration, activates layout/profile pairs as Workspace defaults,
and checks every series for conflicting overrides. It passed on rehearsal for
eight JCL and three JSK series; rerun created no duplicate revisions/assignments.
Wrong database/storage/manifest/mode rejection checks passed. Both branch previews
now return 200 without a manually supplied profile. Current defaults: JCL layout
7/profile 2, JSK layout 4/profile 3, both published. No TEST licence/loan is in the
template packs. See the updated cutover runbook for the target contract and command.
Actual production target values, final release build containing INR_SYMBOL and
installer execution are cutover steps, not completed production deployment.

The owner requested JCL new-lending practice on the hosted rehearsal. Ordinary
setup services created synthetic licence 5 (`TEST-JCL-HOSTED-20260923`), series 13
(`TEST-JCL`) and activated flexible product version 6. Licence-scoped sample
policies use 2% monthly gold/silver interest, latest appraisal valuation, 80%
maximum LTV and one month upfront. The supporting image explicitly says it is not
a legal licence; its stored hash was verified. All setup checks pass and both
authenticated licence/new-loan pages return 200 with the TEST setup visible.
Next numbers are `TEST-JCL-L-00001` and `TEST-JCL-R-00001`; previews consumed none.
The 2,404 JCL imported loans, existing licences and counters were unchanged.
No practice loan was created. Final-source licence verification still requires
the actual cutover attestation; no rehearsal exception was added.
Private operator script: `outputs/server-rehearsal-20260923/prepare_jcl_practice.py`.
These practice settings/data must not be promoted to production.

The owner then authorized importing the saved accepted JCL/JSK ticket bundles.
Both layout/profile hashes match the September 23 export manifest. Hosted JCL
layout revision 3/profile 2 are published and assigned only to TEST series 13;
JSK layout revision 4/profile 3 remain unassigned drafts. JCL's four stored assets
passed SHA-256 checks. Synthetic marked previews rendered and were visually
inspected: JCL one A4 landscape sheet, JSK two A5 preprinted-stock pages. Synthetic
photos are explicitly absent; this is not actual-loan or physical-printer proof.
Existing loan/issued-document counts and JCL's original `test` draft are unchanged.
Private scripts, installation report and previews are under
`outputs/server-rehearsal-20260923/` (`installed-templates/`). No live production
templates or assignments changed.

JCL's first hosted practice loan (19105, principal 18,600) exposed amount-in-words
overflow: its frame at (72,140) mm used WRAP with fixed 12 pt leading and 6 pt
padding. New layout revision 5/version 2 changes only that frame to SHRINK with
automatic leading, preserving geometry and the renderer's 6 pt minimum. It is
assigned to TEST series 13 with profile 2. The actual-loan preview returns 200,
contains the full amount in words and renders as one A4 sheet. Old published
revision 3 and issued documents are unchanged. The saved September 23 transfer
bundle still has the earlier definition; export revision 5 when preparing the
next deployment bundle.

The owner requested the rupee symbol on tickets. Optional `INR_SYMBOL` layout
formatting now renders monetary values with the bundled Unicode font, e.g.
₹18,600.00, without modifying stored payload values. All 29 precision-overlay
tests pass under test settings in a network-disabled container. Hosted web now
uses `rokkad:rehearsal-rupee-20260923`, derived from `a9f793fc` with the formatter,
validator and regression test changes. JCL TEST series 13 uses layout revision
6/version 3 and profile 2; JSK draft revision 4 has the same principal format.
JCL loan 19105's marked preview contains the actual rupee glyph and was visually
checked; issued-document rows and old published revisions are unchanged. JSK has
no actual-loan preview for this update. Export current revisions for subsequent
deployment; the saved original template bundles predate both display fixes.

The owner requested blank space instead of an issuance error when no borrower
photo is attached. Existing `optional_photo` configuration now enables this on
all borrower-photo frames in JCL revision 7/version 4 (TEST series 13) and JSK
draft revision 4. JCL loan 19105 passed `prepare_ticket_document(preview=False)`
and official-mode rendering with ABSENT/optional evidence and a blank photo
space; no issue was created by verification. Old published definitions and
issued-document rows are unchanged. Selected-but-unreadable media still fails;
collateral-photo requirements remain unchanged. No application code change was
needed for this behavior. Export these latest revisions for future rollout.

The supplied September 23 snapshot is now admitted and reconciled on
`https://rehearsal.rokkad.com`. Final state: `HOSTED_DATABASE_REHEARSAL_VERIFIED`.
All 45,533 source loans reconcile exactly once: 6,368 operational openings,
39,162 closed-history records and three retained unused/cancelled exclusions.
All 8,634 customers, 3,499 contacts and 6,726 addresses are imported. Opening
principal is 203,977,183, interest 22,865,291 and fees zero as of September 23.

| Workspace | Customers | Openings | Closed history | Excluded |
| --- | ---: | ---: | ---: | ---: |
| JCL | 5,885 | 2,404 | 26,664 | 1 |
| JSK | 646 | 1,524 | 3,811 | 2 |
| Lakshmi | 2,103 | 2,440 | 8,687 | 0 |

Every source identity, Party field, opening document/evidence, balance, collateral,
obligation and next interest boundary reconciled. Missing/cross-Workspace RLS
checks passed on populated data; registered-model runtime/RLS checks also passed.
Nineteen representative loan page/export/payment/release/retry simulations passed,
with servicing rolled back. These include the newly outstanding inactive-source
borrowers and D01234's single-item 11,500 correction. Real HTTPS login and 29
authenticated Workspace/business pages passed. The first isolated render check
lacked the collected-static volume; mounting the existing web volume read-only
fixed the test environment. No application code or imported values were changed.

Admission took 5,857.4 seconds; complete reconciliation took 92.0 seconds (99.2
minutes combined). This excludes offline preparation, media and later smoke/recovery
checks; it is not a final-cutover downtime promise. A 49,909,423-byte imported-state
backup was restored into the separately retained `rokkad_import_restore_20260923`.
All 160 table content fingerprints matched, and restored runtime/RLS/migration
checks passed. Backup SHA-256:
`481a07bfdf9bd34163d97e2d5ff385df79c4d59aa2b327a2a8db2997cdcde718`.
A separate local copy in `outputs/server-rehearsal-20260923/import-results/`
matches that checksum and byte count. This is a verified copy, not a scheduled
production off-server backup/recovery policy.

Private final evidence is in
`outputs/server-rehearsal-20260923/import-results/run/`; its completion manifest
SHA-256 is `0a470b7e15b676785d7f4b577ebd3ba81759694337d47268c468e03f56dcad0e`
and all 24 listed evidence-file hashes were checked after download.
At the database-only checkpoint photographs/documents were not attached. The
preserved-media reuse above now supersedes that state: 28,292 references are
attached and verified, with 55 newer references and older source gaps outstanding.
September 23 is the opening date: current servicing permits payments/releases
from September 24. The live system is unchanged; no final production cutover occurred.

The owner explicitly instructed proceeding with admission. Three empty hosted
Workspaces were created: `rehearsal-jcl` (1), `rehearsal-jsk` (2), and
`rehearsal-lakshmipawnbroker` (3). The importer is the ordinary, non-staff,
non-superuser `hosted-import-owner` with Owner Memberships; `rehearsal-admin`
has Admin Memberships for browser access. All import database operations use
the restricted runtime role. No production source or routing was changed.

Fresh September 23 opening documents passed existing financial/source validators
offline. The package is newly prepared input, not a capture of a previously
accepted database. It retains 13 payment-exclusion decisions only after exact
loan/payment hash comparison, all 190 earlier owner-closed source graphs,
the two explicit borrower-active overrides with original inactive source facts,
and corrected duplicate-entry evidence. Its SHA-256 is
`cfc13d37d6eb5d052c7f6b9e1e509fa215a83a857a30390eefb66e5bf734a80b`;
private files are in `outputs/hosted-reviewed-package-20260923/`.
Prepared opening principal totals 203,977,183 and interest 22,865,291, fees zero.

The dedicated `rokkad-rehearsal-operator:a9f793fc` image adds PostgreSQL 15 client
tools to the deployed release; the web image is unchanged. Source/archive and
all three source-index checks passed. Container `rokkad-reviewed-import-20260923`
admitted records through existing staged Party and signed Loans services.
The initial launch exited before execution while file transfer was incomplete;
the complete transfer checksum was verified and extraction retried before the
successful launch. No business writes occurred in that failed launch.

Server evidence is under `~/deploy/rehearsal/import/run/`. Full reconciliation,
restricted-role/RLS checks, rolled-back servicing samples, authenticated HTTPS
pages and a separately restored post-import backup passed as recorded above.
Fresh media reconciliation remains
separate; the owner has been asked for its backup or permission to copy live media.

## Fresh hosted source reviewed; owner exceptions resolved (2026-09-23)

The supplied `C:\Users\rajes\backup_20260923_115257.sql` is a PostgreSQL custom
archive (11,694,433 bytes), SHA-256
`3be7cedd0eaf0556b8aa1c70b5c843b6b8c7d3c016665a783243eb663ca44a21`.
A private copy on the rehearsal host matches that checksum. Scoped read-only
extraction and Party/opening/closed-history preparation completed with database
connections explicitly prohibited. No legacy SQL was executed against a destination.

Owner replies were retained verbatim and bound to exact source IDs: both new JCL
RA00554/C07517 are outstanding; JCL RA00549 and JSK WH02133 are unused/cancelled;
Lakshmi D01234 is a duplicate-entry correction, not repayment or collateral return.
Its corrected original principal is 11,500, monthly interest 230, original date
August 24. The existing anniversary/upfront-interest calculator gives zero additional
interest through September 23 and the next increase September 25. This is a review
calculation, not a posting.

All 45,533 loans are classified without overlap: JCL 2,404 outstanding, 26,664
closed-history and one unused; JSK 1,524 outstanding, 3,811 closed-history and two
unused; Lakshmi 2,440 outstanding and 8,687 closed-history. The 190 earlier JCL
owner-reported closures retain unchanged source evidence and unknown closure dates.
The two new outstanding cases are explicit exceptions to the old inactive-customer
interpretation. Destination Party eligibility still needs explicit handling during
admission while preserving original inactive source evidence.

Private evidence: `outputs/hosted-source-20260923/` (sealed preparation retained),
and `outputs/hosted-owner-decisions-20260923/` (new owner-answer/classification seal
`79373241ae47be0fe4bddf8a2fdf0f9a9a85448daa156b3b6439cfc432325055`).
Verified all 117 preparation file checksums and complete/disjoint source coverage.
This source-review checkpoint preceded admission. The completed destination
admission and timed verification are recorded above; fresh media remains separate.

## Hosted HTTPS rehearsal ready for a new source dump (2026-09-23)

The owner selected `rehearsal.rokkad.com` and added its Linode DNS record. Public
HTTP redirects to HTTPS; Caddy obtained a valid certificate. The application runs
release `a9f793fc` through the existing runtime-check/Gunicorn launcher with a
read-only host settings module extending `prod_r2`. Application port 8000 binds
only to loopback; PostgreSQL has no published port. Static files are collected,
raw `/media/` paths return 404, cookies are Secure and separately named, and the
existing rehearsal banner is enabled. Email uses the in-memory backend.

The owner explicitly approved transferring the existing temporary R2 migration
credentials after automatic review initially blocked that secret transfer.
The host uses only `media/application/production/hosted-rehearsal-20260923` for
new application objects. Upload and ten checksum-verified reads passed (roughly
0.32-0.41 seconds per read in the recorded probe); the synthetic object was removed.
Unsigned S3 access returned HTTP 400 `InvalidArgument: Authorization`, a reviewed
authentication rejection. This is not an independent audit of bucket public-domain
settings. Temporary credentials still require replacement before production.

The owner delegated the administrator identity choice: `rehearsal-admin`, with
unverified placeholder email `rehearsal-admin@example.invalid`, was created.
Its generated password is stored only in the host's mode-0600
`~/deploy/rehearsal/admin-login.json`, readable by `rokkad`. Real HTTPS login,
authenticated Workspace page, all 14 login-page static assets, secure session cookie,
TLS hostname validation and raw-media denial passed. No Workspaces or legacy
business records were imported. Two HSTS subdomain/preload warnings are deliberately
retained; this temporary hostname sets one-hour HSTS without subtree/preload scope.

A 1.28 MB schema-stage backup was restored into the separate retained
`rokkad_restore_check_20260923` database. All 160 table row counts, restricted-runtime
RLS and pending-migration checks matched. This proves local schema-stage recovery,
not off-server disaster recovery or restoration of a later imported dataset.
Private reports remain in `outputs/server-rehearsal-20260923/` and on the host.
The new supplied dump is reviewed as recorded above; do not capture the old live
source or reuse an older rehearsal package implicitly. Continue from that snapshot under
the [hosted deployment notes](implementation/linode-production-cutover.md#hosted-rehearsal-deployment).

## Hosted rehearsal database initialized (2026-09-23)

The owner created the separate Linode, completed Ubuntu 26.04 updates/reboot,
verified key-based `rokkad` SSH/sudo access, installed Docker/Compose and built
release `a9f793fc`. The dedicated PostgreSQL 16.15 container has persistent storage
and no published host port. The owner explicitly authorized direct SSH setup.
The agent verified the empty `rokkad_cutover_rehearsal` database, generated new
owner/runtime passwords, saved separate mode-0600 settings files owned by
`rokkad` under `~/deploy/rehearsal/`, and applied owner-only migrations.
The previous manually entered database passwords are superseded.

All 111 migrations applied; 160 public tables exist and no migrations are pending.
Restricted-runtime database deployment checks and canonical forced-RLS checks
pass for all 114 registered protected models; runtime DML grants are verified.
`rokkad_runtime` is neither superuser nor RLS-bypassing and owns no protected
tables. The pending-migration command emits the existing debug-toolbar middleware
warning; the database-tagged deployment check reports no issues. This is database
validation, not complete HTTPS/application deployment acceptance.

Credential-free evidence is retained in `outputs/server-rehearsal-20260923/` and
on the host. No web container, real email/R2 configuration, Workspace/owner setup,
legacy import, source freeze or DNS switch was performed. Email/R2 settings are
explicit inactive placeholders. Continue hosted deployment and disposable migration
rehearsal under the [cutover runbook](implementation/linode-production-cutover.md).

## Production media target admission implemented (2026-09-23)

`linode_media` now accepts a non-rehearsal target only with `prod_r2`, a reviewed
manifest and its exact SHA-256. It binds configured/connected database identity,
restricted runtime role, private R2 endpoint/bucket/prefix, source UUID/archive
checksum and Workspace IDs/slugs. Production plans retain the manifest checksum
in a required header, including empty plans. Apply checks all rows before any
copy, rejects duplicate identities and changed bindings, and preserves receipt
idempotency and user-removed media. Rehearsal keeps its original plan format.

All 41 focused target, existing media and deployment-entrypoint tests pass in
`test_rokkad_ticket_template_feature`, using local filesystem copies. Coverage
includes restricted-role plan/apply/retry, unchanged rehearsal admission, changed
database/server/role/storage/source/mapping, private TLS configuration, unbound
plans, changed manifests, late invalid rows, privileged-role/unauthorized-owner
denial and empty plans. Evidence: `outputs/production-media-target-tests.log`.
No R2 objects, production data or rehearsal business records were changed.

The owner reconfirmed that the separate Linode server is not created. Actual
deployment identities/manifest, durable R2 credentials, hosted checks and a fresh
timed migration are still pending. The importer reports media completion separately
from production readiness. See the [operator runbook](implementation/linode-media-attachments.md)
and [cutover checklist](implementation/linode-production-cutover.md).

## Owner accepted the imported-loan practice run (2026-09-23)

The owner reported completing the practice run and that all was good. Record the
imported-collection workflow as user-accepted; do not ask for the same acceptance
again. This is the owner's reported outcome, separate from automated test and
read-only page-verification evidence below. No new financial actions were performed
by the agent while recording acceptance. Any practice transactions stay in rehearsal;
the final production migration still starts from a fresh frozen source snapshot.

Next bounded task is production media admission. Read-through confirms the
`linode_media` command still deliberately accepts rehearsal databases only, while
`R2MediaCopies` and `prod_r2` already support private application storage. The
[cutover runbook](implementation/linode-production-cutover.md) now specifies the
required exact target and storage binding before lifting that command restriction.
No media-import code, credentials, infrastructure or production state changed in
this acceptance update. The separate destination server is last recorded as not
created; hosted deployment and a fresh timed migration remain pending.

## Imported interest-only and partial-principal payments (2026-09-23)

Implemented the owner-confirmed payment rule in the existing Record payment
workflow. Imported openings now preview and record fee/interest/principal
allocation with atomic interest catch-up, unchanged first-month coverage and
highest-rate-first item principal reduction. Reduced principal changes charges
from the next original monthly boundary; the inclusive calendar still increases
interest the day after the anniversary. Current charges are preserved and the
cumulative baseline is rounded once to whole rupees.

Subsequent release settles the remaining debt. Newest-first payment reversal
compensates its coupled catch-up, restores item balances and preserves historical
as-of reads. Paying all debt does not close the loan or return collateral; explicit
full release remains required. Native periodic accrual, renewal, auction and
generic event posting remain guarded. Existing native repayment paths are reused.

New `opening-payments/1` evidence is retained through `loan-opening-export/2`,
including immutable repayment allocation rows. Restore uses the same financial
writers and rejects a rebuilt graph mismatch. V1 definitions and fixtures remain
unchanged; histories without payments still export as v1. See the
[decision](adr/2026-09-23-opening-partial-payments.md),
[v2 contract](contracts/loan-opening-export-v2.md) and
[operator flow](flows/legacy-opening-import.md).

The initial combined regression passed 88 tests (47.845 s) covering opening
servicing, export/restore, contracts and native allocation. Final regression passed
120 tests (62.786 s), including the payment form preview/commit and PDF receipt,
existing loan UI/documents, staff/cross-Workspace denial, mixed item rates, same-day
payments, month-end boundaries, cumulative rounding, old-release reversal followed
by payment, tamper rejection, paired rollback and portable restoration. Logs:
`outputs/opening-payments-regression-tests.log` and
`outputs/opening-payments-final-tests.log`. All financial test writes are isolated in
`test_rokkad_ticket_template_feature`; no rehearsal or production loan was paid,
released or otherwise mutated. No model change or migration is required.

Committed implementation on `rls-mvp` at `6f5049d9`. Import boundaries pass for
717 tracked Python files; 377 curated documentation links pass. Restarted only
the verified local rehearsal server on port 8081. Under restricted `rokkad_runtime`,
authenticated HTTP GET checks verified imported-loan detail and Record payment
pages for JCL, JSK and Lakshmi. Per-workspace loan state/update-time and event
fingerprints match before/after; no financial submission was made. Evidence:
`outputs/opening-payment-pages-verification.json`. Production remains unchanged;
the cutover runbook still requires branch rehearsal and destination readiness.

## Cutover readiness audit and template export (2026-09-23)

Owner confirmed both interest-only and partial-principal collections are required
on migrated loans. Recorded this as a go-live blocker in the existing
[cutover runbook](implementation/linode-production-cutover.md), with the bounded
implementation and validation scope. Owner confirmed reduced-principal interest
starts at the next original monthly anniversary for all three branches, preserving
the current month's already-earned interest. Existing guarded repayment, continuation,
release/reversal and opening export were inspected. No financial code changed.
The export contract also needs to preserve repayment allocation evidence when
that servicing path is added. Opening servicing currently rejects the opening
date itself, so the runbook now explicitly plans overnight reopening on D+1 or later.

All 43 targeted opening release, continuation, obligation, event-storage and
deployment tests pass (19.345 s) in the isolated test database. They validate the
existing supported paths, not the requested payment extension. Log:
`outputs/ticket-template-rollout-20260922/cutover-readiness-tests.log`.

Exported current published JCL revision/profile 1/1 and corrected JSK 4/2 read-only
to `outputs/production-readiness-20260923/templates/`. Verified layout/profile
hashes and embedded background bytes. The configuration-only bundle has a manifest,
two layout packs and two profile definitions; it excludes rehearsal business data
and assignments. Destination setup must resolve its own IDs. No production access,
server creation, source freeze, routing change or financial mutation occurred.

## Production cutover planning resumed (2026-09-23)

Owner requested commit verification and discussion of production cutover. Verified
`rls-mvp` at `f2c6014d`, with a clean tracked tree and private untracked outputs;
the implementation is committed locally, not pushed. Updated the existing
[cutover runbook](implementation/linode-production-cutover.md) to reflect completed
ticket work and the bounded readiness work still required. This is planning only.

Code review confirms `linode_media` still admits rehearsal databases only and
ordinary repayment on imported openings remains guarded; full-release continuation
is the supported imported collection path. These must not be hidden by successful
new TEST-loan workflows. Permanent R2 credentials, destination-host media reliability,
server provisioning, current legal licence/numbering verification and a fresh timed
rehearsal remain. The last recorded server status is not created. Receipt/release
memo and essential bilingual/device checks remain separate from accepted tickets.
No new code, infrastructure, production writes, source freeze or routing changes.

## JSK preprinted business details corrected (2026-09-23)

Owner clarified that JSK's name/address/contact are already on its stationery.
Removed only `license.business_name` and `license.business_address` frames from
a clone of its published rehearsal template. New revision id 4 (version 2) is
published and assigned to TEST series 14 with existing PREPRINTED profile 2.
Licence number, borrower details/photos, collateral, amounts, tenure, timestamp,
geometry and wrapping choices remain. Stored business details and old published
revision 2 are unchanged. No JCL, imported-licence or production changes.

The existing validator required a printed business-name frame, so added a bounded
v4 `business_name_preprinted` confirmation in the ordinary editor. Only this
business-name coverage requirement can be satisfied by the declaration; other
required fields and complete internal evidence remain enforced. Profile checks
reject PLAIN stock. The default is omitted from canonical data to preserve old
hashes, and old schemas reject the new property. Updated the JSK calibration
builder, starter help, operator guide and stock-choice ADR; no model/migration.

All 110 focused overlay, setup UI, print-profile, issuance and historical-evidence
tests pass (25.084 s), including three new declaration/editor checks. Import
boundaries pass for 715 tracked Python files; 370 curated documentation links
pass. Restarted only local port 8081 on `rls-mvp`. Both corrected A5 preview pages
were rendered and visually checked without business-heading duplication; photos
are present after retrying transient R2 unavailability. The normal reprint of
JSK issue 3 remains byte-identical. No loan, licence or issue rows changed.

Corrected layout hash:
`a5bb8e375ca1afaa6c3cbafb81f39d5a7a0fb8ef9b6be6bd92409f04038fc419`.
Evidence is in `outputs/ticket-template-rollout-20260922/` under
`jsk-preprinted-correction.json`, `jsk-preprinted-verification.json`,
`jsk-preprinted-corrected-preview.pdf`, and `preprinted-business-tests.log`.
The existing issued TEST ticket retains its original heading by design; the
correction applies to new issues. Historical reprints are not regenerated.

## TEST-series template activation completed (2026-09-23)

Activated the reviewed pairs through the authenticated, CSRF-protected **Use
this template** HTTP action on local port 8081: JCL layout/profile 1/1 for TEST
series 13, and JSK 2/2 for TEST series 14. Both layout/profile pairs are now
PUBLISHED, with exactly one active assignment of each type per TEST series.
Their definition hashes are unchanged. Workspace defaults and every other
series' effective layout/profile remain unchanged, including Lakshmi.

Compared full-row fingerprints for 83 Loans/Party tables in each of the three
rehearsal workspaces before/after activation (excluding the four publication and
assignment tables). All match. Previous assignments are preserved; only the
two intended pairs were added. Both existing JCL artifacts pass authenticated
read-back checks, and the normal ticket route still returns the identical saved
PDF for issue 2. Issue 1 is the KFS schedule; it is not the historical ticket.

Finished the active printing path using JSK practice loan TEST-JSK-L-00001.
The normal route created exactly one issue (3), bound to layout/profile 2/2 and
SERIES scope, with payload-v2 source evidence containing the confirmed business
details. A repeat request returned the same issue and byte-identical PDF. Both
issued A5 pages were rendered and visually inspected; no clipping, background,
preview watermark or printed monthly rate. SHA-256:
`0b168a4a9b8b2fc525850d18ccb552dfe349813de7961baea1a8dc549e5c07d6`.
One R2 read timed out on the first attempt; retry succeeded. This records a
successful retry, not resolution of the intermittent storage connectivity issue.

Final comparison confirms all original rows across those 83 tables/workspace
remain unchanged, excluding only the explicitly added JSK issue from its digest.
No new loan, disbursal, payment or production mutation occurred in this step.
No application code or migrations changed. Physical print alignment remains
untested, with the merge gate already waived by the owner.

Local evidence is under `outputs/ticket-template-rollout-20260922/`:
`activation-before.json`, `activation-after.json`, `activation-after_issue.json`,
`activation-http.json`, `activation-history-verification.json`, and
`jsk-test-issue-verification.json`. The JCL new-layout preview remains available;
its previously issued ticket correctly retains the old PDF. The next document
review is payment receipts and release memos, continuing the original print-review
scope without changing production or imported-licence verification.

## JSK rehearsal ticket sample prepared (2026-09-23)

Created owner-authorized synthetic JSK practice setup through existing services
under restricted `rokkad_runtime`: licence 6 (`TEST-JSK`), series 14, customer
11634 and loan 18859 (`TEST-JSK-L-00001`). The licence contains the confirmed
Jai Sri Krishna business address/contact. Supporting document, customer/photo,
collateral/photo and appraisal are explicitly TEST fixtures. Normal draft and
approval services produced the immutable approval; no direct state/snapshot
seeding, disbursal, repayment or official document issue was performed.

Seeded the ordinary four default product drafts and activated the flexible
product version 10 for practice. Added calculation and metal-rate policies only
for the TEST licence (latest-appraisal valuation, 75% LTV, 1% sample monthly
rate, first month upfront). Sample terms are Rs 10,000, three months, one 5 g
synthetic gold chain with Rs 40,000 sample appraisal; these are not real lending
or market evidence. Imported licences remain inactive/unverified. Before/after
hashes match for all pre-existing JSK licences, series, counters, loans, collateral,
issues, product versions, customers and addresses.

The actual stored weight precision exposed a duplicate weight-frame overflow.
Changed only rehearsal JSK draft 2's two weight frames to SHRINK with automatic
leading, keeping their coordinates, sizes, maximum font and 6 pt floor. Full
values are retained. Latest layout hash is
`fe74191a68a38ac9aa7fba27adcb886e4f62994ba7744ec4a5daf615da9c2467`;
the accepted sandbox source and original recovery pack are unchanged.

Authenticated HTTP checks pass for both workspaces' guide, editor, activation
review and fresh previews. Both JSK pages were rendered and visually checked:
A5 Original/Duplicate, confirmed business details, full sample values/photos,
tenure and timestamp; no printed monthly interest or background. The two existing
JCL issued PDFs still pass R2 checksum verification. This is digital verification;
physical alignment remains untested with its merge gate already waived.

Both rehearsal layout/profile pairs remain unassigned drafts. Next rollout step
is Use this template scoped to the TEST series, preserving imported-series setup.
Evidence and fresh PDFs are under `outputs/ticket-template-rollout-20260922/`,
including `jsk-practice-result.json` and `jsk-preview-verification.json`.
No application code, migrations or production changes.

## JCL door number corrected; JSK details confirmed (2026-09-23)

The owner corrected JCL's door number to **58**, superseding the No. 56 value
and door-number artwork concern below. Applied an ordinary audited amendment to
rehearsal practice licence 5 (revision 7). Both refreshed preview headers show
No. 58 and the existing phone; JCL loan, issue and other licence hashes remain
unchanged. The Original artwork already prints No. 58 and was not modified.

Recorded JSK's owner-confirmed details for setup: **Jai Sri Krishna**, No. 155,
Azad Road, Thorapadi, Vellore 632001; contact **9489481436**. JSK's imported
licence remains an unverified legacy reference; these details have not been
written to that record. It still needs a separate approved practice sample for
rehearsal printing, or completion of the existing imported-licence verification
workflow for actual new lending. No business details are now awaiting the owner.
Both template pairs remain drafts. No production changes or application changes.
Local confirmed values and correction evidence are retained under
`outputs/ticket-template-rollout-20260922/`.

## JCL owner-confirmed print details saved (2026-09-23)

On `rls-mvp`, amended only rehearsal JCL's synthetic practice licence 5 through
the existing restricted-runtime service, creating immutable licence revision 6.
Business name is `J Champalal`; address is No. 56, Main Road, Lathif Sahib Street,
RN Palayam, Vellore 632001; contact 7598260045. Legal TEST licence identity and
all other licences are unchanged. Before/after hashes also confirm JCL loans and
issued-document rows are unchanged. No production writes or template activation.

Authenticated preview initially encountered an R2 read timeout; a retry succeeded.
The fresh marked A4 PDF was rendered and visually checked: both copies show the
complete licence-sourced heading/address/contact without clipping. The existing
Original background contains an older No. 58 Tamil footer address, separate from
the updated header; reconcile this artwork before activating the template.
Both rehearsal template pairs remain drafts. JSK address/phone and its approved
rehearsal sample remain outstanding. Local evidence is in
`outputs/ticket-template-rollout-20260922/jcl-business-details.json` and the
refreshed JCL preview. No application code or migration changes.

## Merged ticket templates installed in rehearsal (2026-09-23)

Continued from the original `rls-mvp` checkout (`e26b6363`), not the retained
feature worktree. Backed up both local databases and applied exactly Loans
0016/0017 using `django_project.settings.migration`: `rokkad_shared_dev` and
`rokkad_baseline_rehearsal_linode_20260921`. Both now have no pending migrations.
The custom-format backups are archive-list checked and SHA-256 recorded in the
private `outputs/ticket-template-rollout-20260922/` directory (work began before
midnight). Before/after original-column fingerprints match across 91 development
and 87 rehearsal Loans/Party tables; migration introduced no business-data changes.

Accepted recovery packs were compared with the isolated sandbox's current hashes.
Imported JCL layout revision 1 / plain A4 paired profile 1 and JSK layout revision
2 / preprinted A5 Original+Duplicate profile 2 into their **rehearsal** workspaces,
using the restricted `rokkad_runtime` role and existing services. JCL's four
background assets were read back from the rehearsal's private R2 application
prefix and checksum-verified. JSK has no backgrounds. Both pairs remain unassigned
drafts. No Lakshmi template was invented and no development workspace was assigned.

The actual JCL practice identifiers and missing-business-detail placeholders
exceeded the accepted sample frames. Adjusted only the imported JCL draft's
licence number, loan number and business name/address fields to SHRINK with
automatic leading, retaining geometry, maximum font sizes, the 6 pt floor and
all source values. The accepted source sandbox and recovery packs are unchanged.
The marked A4 preview now renders successfully with practice-loan data/photos;
its full sheet was visually inspected. Licence business details remain visibly
unconfigured. JSK has no approved preview loan in this rehearsal and correctly
returns the existing explanatory 409; its accepted synthetic preview remains
available in the separate sandbox.

Restarted only local port 8081 from `rls-mvp`. Authenticated HTTP checks pass for
both workspaces' layout list, updated guide, editor and activation review. Both
retained issued PDFs pass read-back SHA-256 verification. After draft installation,
82 existing non-configuration tables still match their original fingerprints,
including customers, loans, collateral, licences, sequences, issues and assignments.
Runtime checks report only the existing disabled-debug-toolbar warning.

Pending activation: the owner has been asked for JCL's printed business name,
address/phone and JSK's address/phone (JSK name remains the approved `Jai Sri
Krishna`). Imported licences are still unverified legacy references; ordinary
licence amendment must not bypass their verification requirement. JCL's existing
practice licence is separately synthetic and can be amended through normal setup.
No loan/licence data, production configuration or source Linode server was changed.

## Ticket designer accepted for merge (2026-09-22)

Integration completed: `rls-mvp` fast-forwarded from `8b0e1ba3` to `e2fae88d`
with no conflicts. Feature implementation is `3243147d`; documentation and
in-app guide updates are `e2fae88d`. The updated guide rendering test passes,
378 local documentation links pass, and diff whitespace is clean. The original
checkout stays on `rls-mvp`; the feature worktree, checkpoint and local untracked
artwork/output files are retained. No remote push was performed.

The owner explicitly accepted the JCL/JSK print previews, chose to skip physical
printing checks, and authorized merging `feature/ticket-template-designer` into
`rls-mvp`. This supersedes the physical-print merge hold below; printer alignment
remains untested, not a passed check. Updated the starter guide, accepted ADR,
feature plan and agent memory before integration. The implemented checkpoint
`3243147d` passed all 197 focused document/licence tests; subsequent changes in
this merge-preparation slice update documentation and in-app help text only.
The beginner guide now describes optional backgrounds, precision controls,
per-copy signatures, stock-aware previews and the single activation action.

Rollout remains separate: apply owner-only migrations 0016/0017 to the intended
database and transfer/review/assign layouts, backgrounds and paper profiles in
the intended workspaces. No production deployment, database migration, source
freeze or sandbox/rehearsal template activation is part of this Git merge.
The optional JCL Conditions reverse still contains fixed-rate wording; review
that wording before enabling that reverse. The accepted default is the front pair.

## Paired ticket activation implemented (2026-09-22)

Added **Use this template** to supported ticket editors/revision pages. Owners
and Admins choose a saved draft/published paper profile and Workspace default or
Series, review paper/stock/copy/scaling settings, then submit one CSRF-protected
action. Existing layout/profile publication and assignment services execute in
one transaction, retaining their audit events. Failed validation rolls back
publications, assignments and audit together. A Workspace row lock serializes
paired activations, including initially empty scopes; repeated submissions do
not create duplicate assignments. Reviewed definition hashes reject stale drafts.
Existing licence/series overrides retain precedence; effective pairs are checked
including series with their own paper-profile override. No new model/migration.

Verified clone/edit/preview/activate/new-issue workflow and byte-identical old
reprints, including unchanged source snapshot and issue/profile references.
Restricted-role cross-Workspace denial, concurrent activations, CSRF, setup
permission, retired/stale choices, rollback and Hindi controls are covered.
The 69 setup/evidence/concurrency checks pass. The final 197-test focused
document/licence regression also passes (41.501 s), including nine new activation
checks. Log: `outputs/ticket-template-tests/activation-regression.log`. This is
the focused feature suite, not a full-repository test run.
Restricted sandbox system checks, import boundaries (715 tracked Python files),
370 current-document links and staged whitespace checks also pass. No migration
was added or applied for this activation slice.

Restarted only the isolated browser sandbox on port 8082. Authenticated HTTP
checks pass for both real draft review pages and fresh marked previews: JCL one
A4 landscape sheet; JSK two A5 data-only sheets. Inspected all three rendered
pages; no layout changes were made. Browser automation timed out, so no browser
interaction or responsive visual acceptance is claimed for the new review page.
Accepted sandbox drafts/profiles remain unactivated by this work; no production
or rehearsal changes. Local print-check PDFs are under `output/pdf/`.

The owner explicitly reports that physical printing has **not** been tested.
The requested merge remains conditional on JCL/JSK physical acceptance. Finish
the paper checks at 100% scale, correct any offsets in drafts, then merge after
acceptance. Do not treat automated/PDF checks as physical printer acceptance.

## Preview acceptance and merge-readiness review (2026-09-22)

The owner accepted the refreshed JSK preview after printed interest was removed;
both JCL and JSK now have owner-accepted digital previews. Physical printer
acceptance is still separate. No merge, template publication/assignment or target
database migration was requested or performed during this review.

Compared feature head `e29c0609` with `rls-mvp` at `8b0e1ba3`: baseline remains an
ancestor, with no tracked changes in either checkout and no branch divergence.
Local untracked outputs/artwork are intentionally retained. Reran all 188 focused
document/licence checks on the isolated test database: PASS (28.604 s; local log
`outputs/ticket-template-tests/merge-readiness.log`). Import boundaries pass for
713 tracked Python files; 370 current-document links and diff whitespace pass.
Owner-only dry-run migration drift check against the sandbox reports no changes.
This is the focused feature gate, not a claim of a full-repository test run.

The implementation extends the existing versioned layouts, profiles and issuance
pipeline with opt-in precision overlays, explicit paper stock, immutable rich
source evidence, licence print details and per-copy signature choices. It does
not replace the renderer/model architecture or introduce financial posting logic.
The agreed completion gates still include the simplified paired Use this template
action, its end-to-end operator check, and physical JCL/JSK calibration. Existing
separate publish/assignment services work and remain available.

Recommendation: finish that bounded activation slice and physical acceptance,
then merge; do not reopen the architecture. Actual rollout also requires owner
migrations 0016/0017 and import/review/assignment of the accepted layout assets
and print profiles in the intended workspaces. Git merge alone does not transfer
sandbox database configuration, local artwork or credentials. JCL Conditions
fixed-rate wording must be reviewed before using those reverse sides.

## JSK printed interest omitted (2026-09-22)

At the owner's request, removed both monthly-interest frames from JSK sandbox
draft revision 2 and set its existing `require_interest_rate` choice to false,
matching JCL. Updated the reusable JSK calibration builder and local recovery
pack. Preserved all other draft fields and geometry, including wrapping, tenure
and timestamp. Strict validation and the live two-page A5 preview pass; neither
copy contains an interest label or percentage. Compared loan rates, approval
payloads/fingerprints and issue counts before/after: unchanged. No publication,
assignment, renderer change or migration. Previously downloaded sample PDFs are
historical previews; use the editor's fresh preview for this change.

## Collateral wrapping with smaller text, no continuation sheets (2026-09-22)

The owner superseded the briefly selected continuation-sheet option: preserve
one ticket sheet per copy and reduce the font while wrapping. Updated only the
existing JCL/JSK sandbox drafts' collateral-description fields and JSK summary
label to `SHRINK`, automatic leading, and a 500-character sizing threshold. This
threshold is not truncation: every character remains in the paragraph. Frame
positions/sizes and source values are unchanged. Recorded the same choice in the
reusable frame mapper. No continuation/schema/renderer change remains.

A five-item long-description example that exceeded JSK's former fixed-font frame
now fits both copies. Verified complete descriptions by PDF text extraction,
visually inspected all three output pages, and confirmed unchanged output counts:
two A5 JSK pages and one paired A4 JCL page. JSK uses 7-9 pt for these sample
fields; JCL has sufficient room at 12 pt. Examples are
`output/pdf/jsk-wrapped-collateral-preview.pdf` and
`output/pdf/jcl-wrapped-collateral-preview.pdf`. No official issue was created;
the owner's existing sandbox issues were preserved. Updated local recovery packs.

The existing 6 pt minimum still bounds shrinking. A list that cannot fit even at
that size still requires more frame space or shorter descriptions; it is never
silently clipped, drawn over other frames or paginated automatically. No full
suite rerun was required for this draft-configuration-only change.

## JSK preprinted A5 calibration draft (2026-09-22)

The owner reviewed JCL's sandbox editor and reported that everything works as
expected. This accepts that reviewed workflow, not a physical printer test or
production activation. JCL remains draft revision 1 and was not changed here.

Created `jsk-template-sandbox-sample-only` in the same isolated sandbox, accessible
with `ticket-designer`. JSK draft revision 2 and draft print profile 4 produce two
actual-size A5 pages, Original then Duplicate, in PREPRINTED mode. There are no
background assets or signature frames. The owner confirmed both signing areas
on each copy and requested `Jai Sri Krishna`, with other business details from
the licence. The synthetic licence holds that name and explicitly sample licence
number/address; rate and tenure bind approved loan facts, not licence metadata.
Business and term fields are movable additions whose physical placement remains
to be tested on JSK stock. No stationery guide was supplied.

`build_jsk_calibration_layout()` in the frame review script reuses all 23 mapped
source frames and the existing timestamps, plus licence and approved-term fields.
The source inventory is unchanged. Calibration adjustments: duplicate principal
width 120 to 108 mm to stay on A5; 9 pt loan numbers with bounded shrinking;
original principal width 30 mm/font 10 pt; original collateral photo at
(68,108,25,25) mm; duplicate collateral photo moved to y=106 mm; duplicate
description width 75 mm; original customer photo y=64 mm; duplicate customer
contact width 60 mm. These avoid observed photo/value collisions and wrapping
into photographs, but do not establish parity with physical stationery.

Verified normal HTTP login, both editor copy views, preview endpoint, two A5 page
dimensions and copy contents. Longer customer text wraps; excessive collateral
text blocks rather than truncates. Restricted-role cross-workspace reads deny
the JSK layout from JCL context. Both layout/profile remain unassigned drafts,
with no official issues. Exported the local recovery pack and visually reviewed
`output/pdf/jsk-preprinted-a5-calibration-preview.pdf`. No renderer/domain change,
migration or full regression rerun was needed. The briefly considered incomplete
draft validation change was removed after the owner's stationery clarification.

Next: user prints both pages at 100% on JSK stationery, one-sided, one page per
A5 sheet, and reports alignment. Confirm the added header/terms do not duplicate
stock text. JCL physical duplex calibration and Conditions rate wording remain
pending before publication/assignment; unified activation and merge remain later.

## JCL draft available in the isolated browser sandbox (2026-09-22)

Provisioned `rokkad_ticket_template_sandbox` with a dedicated restricted runtime
login and ordinary owner-only migrations. The feature server listens on
`127.0.0.1:8082`; its local media, secrets and synthetic fixtures live under the
Git-ignored `outputs/ticket-template-sandbox/`. Separate session/CSRF cookies and
a sample-data banner distinguish it from the existing migration rehearsal.
No existing rehearsal database, production storage or server was changed.

Workspace `jcl-template-sandbox-sample-only` contains the reviewed JCL layout as
draft revision 1, all four supplied backgrounds, three draft print profiles and
one synthetic preview customer/loan. This is a document fixture, not a lending
workflow rehearsal. The original/duplicate fronts retain the approved heading,
tenure and signature choices. `Condition1.pdf` and `D31.pdf` supply the two backs
unchanged. No layout/profile is assigned or published; no official issue exists.

Normal HTTP sign-in, both editor copy views and background endpoints, A5 original,
A4 paired fronts and A4 duplex previews pass under the restricted runtime role.
Cross-workspace access cannot see the layout. Visually reviewed the two-page
duplex preview; application currency formatting required a 10 pt principal field
inside its original 30 mm frame to avoid the artwork's In Words label. Exported
the resulting draft pack locally for recovery. This run did not repeat the full
188-test suite: app/domain behavior is unchanged.

Before publication, review the supplied Conditions artwork's fixed interest
wording (including 12% per annum); it does not track a loan's approved rate.
Printer duplex alignment and physical acceptance remain pending. See the
[sandbox access instructions](plans/ticket-template-designer.md#local-browser-sandbox).

## JCL heading line separation (2026-09-22)

The owner's small layout correction is applied to both copies: business name
alone at 16 pt, an editable `Pawn Brokers` text frame at 11 pt, then the existing
licence address/contact block at 9 pt. The latter supports an address followed
by a phone line; no separate contact-data model or automatic name splitting was
introduced. The sample business name is `JCL (Sample)` and all contact values
remain synthetic. Updated the frame review to support literal text frames.

Regenerated and visually checked the public-renderer A5 original and A4 pair at
`output/pdf/jcl-original-heading-preview.pdf` and
`output/pdf/jcl-original-duplicate-heading-preview.pdf`. All heading lines fit
above the borrower box; both retain tenure, signature artwork and timestamp.
Existing previews/source artwork and runtime data are unchanged. Renderer/text
checks and frame-review generation pass; no full regression rerun was needed
for this layout-only correction.

## Per-copy signature choices and validated JCL pair (2026-09-22)

The precision editor now asks separately for Original and Duplicate whether to
use editable frames, areas already in the background PDF, or preprinted paper.
Clients confirm that both borrower and pawnbroker/agent areas are present. Existing
areas remove duplicate signature frames from that copy; switching back supplies
two draggable frames where needed. Clients retain numeric positioning controls.
Original/Duplicate canvas links show each copy's background and applicable frames.

Confirmations live in the existing versioned layout, tied to the selected asset
key/hash. A changed background prompts reconfirmation and blocks publication and
rendering until reviewed. Profile stock mismatches are rejected; integrity checks
recognise both confirmed stock and separate role-labelled frames. Unchanged
confirmations survive clone/export/import with the same artwork. This is client
confirmation, not automatic visual recognition. The usual setup permission,
draft locking, audit history, immutability and stored-reprint path are reused.

V4 has an explicit optional printed-interest requirement, enabled by default.
JCL disables it as requested; internal approval/issue evidence still requires the
rate. Older schemas and hashes retain their defaults. See the
[decision](adr/2026-09-22-ticket-signature-area-choices.md).

Prepared `output/pdf/jcl-original-duplicate-preview.pdf` (A4 landscape) and
`output/pdf/jcl-original-signature-preview.pdf` (A5). Both now use the public
validator/print-profile renderer instead of the earlier geometry-only route.
Reviewed both supplied backgrounds, removed fixed tenure from separate copies,
confirmed their existing signature areas and retained the duplicate's redemption
section. Synthetic six-month tenure and timestamp appear on both; a twelve-month
render verifies dynamic tenure. No rate field is printed. Source artwork and
previous previews remain intact. Reverse-side terms and a real printer test remain
pending. No app server, workspace template assignment or official document changed.
Validation: 188 isolated document/licence tests pass. Coverage includes per-copy
confirmation, background replacement, stock-mode mismatch, automatic frames,
published-edit/Viewer denial, copy-specific canvas backgrounds, pack round-trip,
optional printed rate with mandatory source evidence, and existing reprint/RLS
regressions. Current-document links, import boundaries and diff checks pass.

## JCL variable-tenure artwork proof (2026-09-22)

At the owner's request, the original-front preview now binds `loan.tenure` in
place of the artwork's fixed `3 months`. Removed that text from a separate
`output/pdf/jcl-background-variable-tenure.pdf`; preserved the supplied `org.pdf`
and its SHA-256. The movable field at (64.7, 147.4) mm aligns with the existing
redemption sentence. It uses the existing approved-tenure projection, not a new
calculation or editable loan value. The sample PDF shows six months; a second
in-memory render proves a twelve-month payload changes the text with neither
the old three-month text nor the six-month sample retained. Both final PDFs were
rasterised and visually checked. Interest remains unprinted at the owner's
request for now; publication's existing rate requirement is unchanged.

Updated the JCL original candidate and local geometry review. Duplicate tenure
placement still awaits its artwork review. The proof remains unofficial and
non-activatable pending static-background signature coverage and the deferred
printed-interest decision. No running app, database, issue or existing PDF changed.
Confirmed from the current editor that pointer dragging updates X/Y, Save block
persists it, v4 supports 0.1 mm positioning, and size/font use numeric controls.
The canvas shows frame rectangles/bindings; PDF preview is the rendered text check.

## Licence business heading above the JCL borrower block (2026-09-22)

The JCL candidate now includes centred `license.business_name` (16 pt) and
`license.business_address` (10 pt), in the blank area beside the logo above the
borrower block. Regenerated and visually reviewed the supplied-background A5
proof with clearly synthetic business details and the existing timestamp.

The current licence previously had only a staff-facing name and no address.
Added separate optional printed business name/address fields to licence setup,
detail, and immutable revision capture. Migration 0017 leaves existing values
blank. V4 editor bindings read the loan's current licence at first issue and
retain the values in source evidence; reprints retain the saved PDF. Selected
blank business fields block new issuance and show explicit preview placeholders.
No fallback to workspace identity or extraction from artwork. Licence business
name now satisfies v4's visible business-name requirement. Earlier schemas and
published layouts remain unchanged. Runtime/rehearsal migration is not applied.
Validation: all 183 isolated document/licence tests pass, including the actual
setup POST, immutable licence history, blank-field handling, rendered values,
and exact-byte reprints after changing the licence's business name/address.
Import-boundary and current-document link checks pass; model migration drift
is clean. Migration 0017 is exercised only in the isolated feature test database.

## JCL supplied-background preview (2026-09-22)

Created `output/pdf/jcl-background-preview.pdf` from the owner's local
`template_pack/template_pack/org.pdf`, using synthetic customer/loan data and
labelled photo placeholders. This is a watermarked A5 original-front artwork
proof through the existing v4 rendering primitives, not an issued ticket or an
activatable layout. No database, server, template assignment or source PDF changed.
The public profile renderer still correctly rejects the incomplete candidate;
this offline proof does not change publication/issuance validation.

Visually checked the Tamil artwork and rendered fields. Local proof adjustments:
customer photo at (12.1, 53) mm aligns with the padded customer text; QR moves
from y=80 to 65 mm inside the customer box; collateral photo moves from y=110
to 104 mm to clear the weight row. Timestamp fits below the business footer.
These adjustments are recorded in the ignored proof builder/review JSON under
`outputs/ticket-template-tests/jcl-background/`, not applied to saved templates
or the source frame mapping. Checked A5 size, expected text and unchanged source
SHA-256. Original/duplicate pairing and physical printer calibration remain pending.
The supplied artwork fixes redemption at three months and has no interest-rate
field; those must be reconciled with approved terms before activation, alongside
the pending reviewed static-artwork coverage contract.

## Printed generation timestamp (2026-09-22)

New precision-ticket starters and the JCL/JSK candidates include a small
`Generated` date/time frame on both copies. The registered `document.generated_at`
field uses the application's default timezone, including abbreviation and UTC
offset (currently IST / UTC+05:30). It shares the frozen source capture instant;
it describes PDF generation, not a physical printer event or loan approval time.
Saved reprints retain the original timestamp, and older PDFs are not rewritten.
The timestamp is also visible among the issue's captured fields and remains an
ordinary editable frame. JSK Duplicate places it to the right of the summary
label; other candidate fronts use the bottom area. No migration or running-server
change. All 159 isolated tests pass, including timestamps on both PDF copies and
byte-identical reprinting a day later. The generated footer was visually checked.

## Accessible issue evidence and cleaner precision tickets (2026-09-22)

Owner/Admin access is **Settings > Documents & printing > Document layouts >
Issued documents > Evidence**. The existing evidence page now shows the issuer,
issue time, retained verification reference, captured customer/loan values,
selected photo identities/checksums and asset hashes alongside the existing
source/layout/profile/PDF evidence. Historical issues without a separate snapshot
are labelled; no current Party values are substituted. Evidence/list pages are
non-cached. The loan's print panel links to its exact ticket history; snapshot
ticket numbers are searchable. This does not broaden setup permissions.

Opening an artifact or performing a normal stored reprint now checks the actual
PDF bytes against its retained hash. Missing or mismatching bytes produce a safe
409 response; metadata remains inspectable and no new PDF is substituted. The
existing Integrity diagnostics screen checks layouts, profiles, assets and PDFs.
A displayed checksum is not itself a completed verification or digital signature.

V4 now separates visible ticket content from the complete internal payload:
workspace/Party/loan/approval IDs, fingerprints and verification text need not
print. New v4 starters omit those fields and internal collateral IDs. Every front
still requires business/license identity, customer, number/date/principal, rate,
tenure, collateral description/metal/weight coverage and signature space. Compact
description/weight fields can replace the full table. A QR, conditional field,
back-only block or table omitting descriptions/weights cannot bypass coverage.
The renderer still requires complete internal fields/sections and verification;
new source snapshots retain the verification reference. V1/v2/v3 rules and saved
artifacts remain unchanged. No migration is added in this slice.

Validation: 159 isolated tests pass, including new paper/payload separation,
captured evidence access, exact history filtering, denied Member/foreign-Workspace
reads, corrupted/unavailable artifact rejection and legacy compatibility. Synthetic
PDF output was inspected with MuPDF. The JCL/JSK review was regenerated: remaining
gaps are business identity/terms and signature areas supplied by artwork/stock,
not internal audit identifiers. Reviewed static-stock declarations and paired
activation remain pending. Feature only; no runtime server or merge into rls-mvp.

## JCL customer-row alignment (2026-09-22)

Owner review identified JCL's source photo frame overlapping the collateral
description. The candidate generator now places the photo, contact block and
loan number on the same 50 mm top edge in both copies. The 25 mm photo ends at
75 mm; the description starts at 90 mm. The source inventory remains unchanged;
the generated review records the photo's 75-to-50 mm move as owner-requested.
Regenerated HTML/JSON and checked alignment and separation directly. No renderer,
database, mandatory-field rules or production templates changed in this correction.

## Ticket contact/photo evidence and frame candidates (2026-09-22)

The feature branch now exposes customer name, relationship, address, phone/contact
block, principal in Indian-English words (including paise), approved collateral
descriptions, net weight by metal, approved appraisal total, license number and a
compact loan summary. V4 image frames can bind the customer profile photograph or
the first item's first approved photograph. These are transient render inputs,
never copied into template assets or exported packs. Older payloads/layouts retain
their existing interpretation.

First issue captures those values, chosen address and selected photo identities/
checksums in nullable `LoanDocumentIssue.source_snapshot` (payload v2). Migration
0016 adds Workspace/schema checks and database immutability; old rows stay null.
It has been exercised only in `test_rokkad_ticket_template_feature`. A loan row
lock serializes first prints. Stored reprints return before projection/media
rebuilding, even after customer edits or media failure. Address ambiguity opens
a scoped, non-cached selection page without changing Party defaults. Absent photos
require an explicit optional-frame setting; unreadable, changed or unprovable
approved photos block official issue. Previews show labelled placeholders.

Validation: 155 isolated checks pass, including exact-byte reprints, two real
PostgreSQL first-print requests, restricted-role snapshot mutation/deletion and
foreign-Workspace denial, photo checksum/item selection, no later-photo fallback,
address selection and privacy of exported packs. Synthetic two-copy PDF output
was visually inspected with MuPDF (Poppler is not installed). This checks the
new bindings, not real stationery or physical printer parity.

`scripts/review_ticket_frame_mapping.py` produces a local synthetic HTML geometry
review and candidate JSON for all 35 mapped JCL/JSK frames. It makes no database
changes and is **not an import pack or renderer preview**. Candidates explicitly
fail today's visible-evidence contract: internal IDs/full collateral table and
verification remain mandatory. JSK duplicate frame 19's width reduction from
120 to 108 mm is flagged for review. No artwork or semantic differences have been
silently accepted. Next: implement the already-designed v4 visible business
coverage/static-stock declarations, then copy-aware editing/paired activation and
real-artwork/printer acceptance. No parent/rehearsal/production changes or merge.

## Stationery guides and legacy text spacing (2026-09-22)

The isolated ticket feature now supports print-profile v2 paper stock: plain
paper prints selected backgrounds; preprinted stationery treats them as guides,
shown only in Design preview. Print preview, downloaded test print and official
issuance omit those backgrounds. Design previews carry the existing unofficial
watermark plus an explicit guide warning. The renderer rejects guide requests
without preview mode. Existing profile v1 canonical definitions remain unchanged.

V4 text frames support 0.1-point padding and line spacing, including legacy 6 pt
insets and 12 pt leading, plus escaped explicit line breaks. Padding cannot consume
the rectangle; leading cannot be less than the font size. Overflow still blocks
output, and bounded shrinking keeps explicit line spacing and a 6 pt font floor.
Zero/default spacing preserves the earlier v4 hashes. Tables/images/QR do not
accept these text controls. Older schema rendering remains unchanged.

The overlay editor selects a local draft/published profile or resolves the sample
loan's assigned profile. Profile setup exposes paper stock and separate design/
print previews; these responses are not cached. Foreign-workspace profile choices
are absent and direct requests fail closed. Publication/assignment and immutable
issue services are reused; no migrations or new document tables are introduced.

Validation: all 138 isolated tests pass. New checks cover guide suppression,
explicit preview-only enforcement, profile versioning/forms, legacy text metrics,
overflow, editor saves, draft previews, official issue and exact-byte reprint after
changing stock mode. Synthetic A5 design/print/official images were reviewed with
MuPDF. These are mechanics tests, not real JCL/JSK stationery or printer acceptance.

Next: mapped customer/contact and approved-photo bindings/source evidence are
still needed to assemble complete JCL/JSK templates, followed by copy-aware editing
and visual/physical calibration. Static-stock declarations and paired activation
remain pending. No feature web server, production changes or merge into `rls-mvp`.

## Isolated precision ticket overlays (2026-09-22)

Implemented on `feature/ticket-template-designer` only: opt-in layout v4 supports
background-free loan tickets, optional printed backgrounds, value-only scalar
fields/custom labels, and 0.1 mm position/size controls. The existing overlay
editor saves these settings and its drag canvas preserves fractional positions.
Geometry validation rejects non-finite, over-precise and out-of-page rectangles;
v4 Letter bounds match actual paper dimensions. Default creation remains v3.

`scripts/test_ticket_templates.py` uses `django_project.settings.test`, a pinned
local `test_rokkad_ticket_template_feature` database, local media and memory email.
The existing development env file supplies local connection credentials only;
no credential file or production media is copied into the feature worktree.
No feature web server is running and no new application migration is needed.

Validation: all 131 focused tests pass, covering renderer/forms, A5 actual-size independent copy positions,
asset ownership/missing assets, compatibility, persistence, issuance/reprints,
and the complete setup UI suite. The new end-to-end test creates, edits, previews,
publishes and issues v4, then confirms a replacement template does not change
the original issue bytes. Synthetic MuPDF image inspection confirms background-
free and merged output. A Node canvas smoke check verifies fractional initial
coordinates, 0.1 mm drag, edge clamping and pointer cleanup. Supported-app
boundaries and diff checks pass. The parent remains at checkpoint `8b0e1ba3`.

Remaining: stock-aware profiles and guide-only backgrounds, text padding/leading,
richer customer/photo evidence, copy-aware authoring and paired activation, plus
real JCL/JSK artwork and printer acceptance. Existing mandatory fields and
verification remain enforced. This is the overlay foundation, not completed
production-template parity. The original `rls-mvp` rehearsal remains separate.

## Ticket frame mapping and engineering decisions (2026-09-22)

Feature-only design work maps all 12 frames in JCL's default template and all 23
in JSK's default template from the September 21 dump. The
[mapping contract](implementation/ticket-template-frame-mapping.md) and its
sanitized JSON inventory preserve source geometry/settings and candidate bindings.
No customer records, photos, production PDFs or credentials are included.

Selected targets: additive layout v4, stock-aware print-profile v2, richer ticket
payload v2, first-issue source evidence on the existing issue, and one copy-aware
editor with atomic Workspace/Series activation. No second printing engine or
legacy domain dependency. Old published versions and exact-artifact reprints
remain compatibility requirements. See the proposed ADR and bounded plan.

Findings: JSK Duplicate amount frame 19 exceeds A5 width by 12 mm; legacy text
padding/leading and JCL's 148.5 mm half-A4 canvas affect alignment. Legacy live
valuation, misleading license-name binding and separate quantity cannot silently
be treated as equivalent to approved appraisal, license number and native item
descriptions. These remain visible acceptance differences.

Validation checks the 35 inventory rows against source configuration, coordinate
conversion/bounds, proposed binding coverage and documentation links. This slice
is documentation/design data only: no renderer, migrations, data, runtime settings
or production changes; no new PDF/physical-printer acceptance. Next is isolated
feature runtime/fixtures, then the bounded overlay and stock-profile extension.

## Isolated ticket-template design experiment (2026-09-22)

The owner authorized `feature/ticket-template-designer`, based on checkpoint
`8b0e1ba3` and kept in `.worktrees/ticket-template-designer`. The original checkout
remains on `rls-mvp`; the named checkpoint branch is
`checkpoint/rls-mvp-before-ticket-designer-20260922`. Both are local references;
no remote push or deployment was requested.

The [design plan](plans/ticket-template-designer.md) defines the simple authoring
journey, required frame capabilities, JCL/JSK acceptance examples, remaining
schema/evidence decisions and merge/fallback gates. The
[proposed ADR](adr/2026-09-22-ticket-template-authoring-experiment.md) retains the
existing issuance pipeline while simplifying authoring. This slice changes docs
only; printing code, schemas and saved layouts are unchanged. A separate feature
database/media/port must be provisioned before runtime testing; none is created
by this slice. No new visual PDF or physical printer acceptance is claimed.

## Baseline checkpoint before ticket-template experiment (2026-09-22)

The owner requested a committed fallback and a separate feature branch before
developing the simpler client-managed ticket editor. This checkpoint preserves
the existing working-tree dashboard template/test, import navigation, boundary
check and supporting domain/plan/ADR documentation. These are pre-existing work,
not ticket-editor implementation. Printing behavior and schemas are unchanged.

Validation: the modified dashboard permission/Workspace-queue regression passes
under `django_project.settings.test`; supported-app import boundaries and
`git diff --check` pass. This is a source checkpoint, not a fresh full-suite or
production acceptance claim. Local `.tmp/`, `outputs/`, databases, credentials and
production media are excluded from the commit and retained locally.

The ticket experiment will use its own worktree. Before runtime experimentation,
it must use a separate database and media location; switching Git revisions alone
cannot roll back database or storage changes. Keep the accepted rehearsal and
live production untouched. The feature branch will hold its own bounded design
and acceptance plan before printing code changes.

## Owner workflow acceptance and visible loan closure (2026-09-22)

The owner reviewed customer/photo creation, loan/collateral entry, terms,
approval/disbursal, payment, settlement and collateral return in JCL rehearsal,
reporting that the process was smooth apart from closure visibility. The completed
`TEST-JCL-L-00001` is canonically CLOSED, has zero principal/interest/fees due and
its collateral is With Customer. This is acceptance of the reported test sequence,
not a claim that every device, language, printer or exception path was reviewed.

Closed loans now have a prominent green confirmation banner with history/release
links, a consistent checkmark/text badge in the summary and directory, and a green
directory-card border. Active badges are blue. Closed summaries explain that the
original terms are reference information. Status comes only from the existing
loan state; this presentation does not infer payment/return from other closure
types or change lifecycle, balances, custody or reversal rules.

All 56 existing loan UI tests pass. Chrome review confirmed the actual completed
test loan, zero balances and returned custody, plus the banner and directory card
at phone width. Normal browser sizing was restored. English/Hindi labels compile;
this turn did not repeat the full workflow or physical-device acceptance. The local
rehearsal server is refreshed; no production change was made.

## JCL collateral upload recovery and local migrations (2026-09-22)

A manual JCL draft submission failed when R2's TLS connection ended unexpectedly.
Database inspection confirmed complete rollback: no test loan or collateral row,
2,355 existing loans unchanged, and test loan/release counters still at 1. Rehearsal
had no pending migrations. The three reported migrations belonged to
`rokkad_shared_dev`: portability 0015, loans 0014 and loans 0015. A 28.8 MB custom
backup was created and its catalog checked before applying those migrations with
owner-only settings. Both local databases now report no pending migrations.

Collateral storage exceptions now return a translated form error with entered
details retained and photo-reselection guidance. Create/edit operations roll back;
failure to clean up an earlier uploaded file is logged without masking the original
error. R2 web settings use standard retries with two total attempts per request,
5-second connect and 15-second read timeouts, retaining TLS verification. These
are socket/request limits, not an overall request-duration guarantee.

Real-storage probes succeeded for 54 KB and 2.1 MB synthetic images. A full Django
form submission using actual rehearsal R2 storage subsequently uploaded and
hash-verified a 2.1 MB image in about five seconds; its synthetic customer/draft
were rolled back and its object removed. One earlier form probe timed out and
correctly rendered a recoverable error, so intermittent connectivity remains an
observed limitation, not a proven permanent network fix. The local 8081 server was
restarted with the change and the fresh loan form checked in Chrome. No Linode
deployment or source change occurred. Private backup/logs/scripts are under
`outputs/jcl-upload-fix-20260922/`.

Validation: all 109 draft UI/service, collateral media and deployment tests passed
on a fresh test database. Regression cases cover SSL/provider/filesystem failures,
retained form data, successful retry without duplicate numbering, edit rollback
preserving saved photographs, and cleanup failure preserving the recoverable error.
Gettext, import-boundary and diff checks pass.

## JCL manual workflow practice setup (2026-09-22)

At the owner's request, local `rehearsal-jcl-20260921` now has a separate
`TEST ONLY - JCL workflow practice` license (ID 5) and `TEST practice` series
(ID 13). Its synthetic document explicitly says it is not a legal license;
validity dates 2026-09-22 through 2027-09-21 are test data. Loan/release previews
are `TEST-JCL-L-00001` / `TEST-JCL-R-00001`. Do not carry this setup into production.

The existing active flexible-payment product and workspace policies were reused,
not changed: gold 2% monthly, one month upfront, 80% maximum LTV, lower of calculated
and appraised value, and the existing INR 10 document fee. Gold has a usable
September 22 quote; silver does not yet have a valuation quote. Start the manual
walkthrough with gold and a new clearly named test customer, using today's date.
Approval on a later day may require a new same-day quote.

Creation used the existing audited setup services under the restricted runtime
role and explicit Workspace context. The private test document was read back and
hash-verified. Before/after checks preserved all existing licenses and counters
and the 2,355-loan count. Browser GET confirmed the test series/product are selected
and the non-consuming next number appears. No customer or loan was created by this
preparation. Imported licenses remain inactive; no cutover attestation was made.
The rehearsal now includes this synthetic setup alongside the accepted import.
Full user workflow acceptance remains pending. Private execution evidence:
`outputs/jcl-workflow-test-20260922/setup-result.json`.

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
| Workspace/RLS, local role grants, private-media routes, business setup | Implemented; access/media checkpoint `4d15577` published |
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
