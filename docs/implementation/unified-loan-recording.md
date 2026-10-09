---
status: implemented-local
owner: loans
updated: 2026-10-09
tags: [loans, paper-entry, repayment, origination, verification]
related: [../plans/unified-loan-recording.md, ../adr/2026-10-02-unified-loan-recording.md]
---

# Unified loan recording implementation

## Editable paper identity suggestions (9 October)

The owner requests prefilling routine paper New loan's Original loan number and
Paper book / page / loan reference with the selected series' next automatic number.
`prepare_paper_number_defaults` uses the existing non-consuming preview. Both
fields stay editable. No selected/usable series leaves them blank for actual
source entry. Saved draft, archive and correction identities retain their source.

Initial GET and nonfinancial entry/terms refreshes fill blank fields or values
still equal to the previous suggestion. A small unsigned hidden
`paper_number_suggestion` marker identifies that presentation default; it is not
a declared financial form field and never enters `_data`, signed review or stored
origination evidence. Series/purpose switching retains custom identities, item
facts, photos and intent. Without JavaScript, Apply series setup uses the same
server behavior. Financial preview/confirmation and error redisplay preserve the
actual submitted fields, even when blank; the usual required/duplicate checks apply.

The reference follows loan-number typing while it still equals the preceding loan
number. A different book/page reference remains independent. Terms responses
refresh displayed suggestions under revision checks, including a second check
after response-body reading so late responses cannot replace edited facts. Loan
numbering advances only on successful admission through the unchanged service;
confirmation and exact retry retain the reviewed number as the counter changes.

Verification artifacts: `.tmp/paper-number-prefill-20261009/`. The scoped 89-test
suite covers routine paper, simplification, series availability, multi-item
recording and direct entry. Fictional localhost browser checks cover editable
prefills, linked/custom references, asynchronous series refresh, retained photos,
desktop/mobile and native no-JavaScript Apply series setup. Production rollout
is separate; browser checks make no financial submission.

## UR-23: compact purpose and retained entry facts

`web/entry_presentation.py` resolves GET defaults and handles explicit read-only
`action=entry_change` POSTs. The ordinary Series field is the only selector; an
explicit purpose exception remains under Entry/Change. Scope validation rejects
foreign series. Common customer/date/product/series and physical item facts cross
between adapters; paper number/reference/exceptions/activity and native appraisal,
override and submission identity are retained per purpose. The bounded JSON form
cache carries untrusted strings only and is never canonical evidence. Review tokens
and confirmation are excluded. Normal financial POSTs keep their explicit purpose.

Both views bypass preview/admission/draft submission on a presentation change.
Incomplete typed facts are rendered without claiming financial validity; the next
normal POST creates fresh forms and runs normal validation/services. No accounting,
valuation, financial service, lifecycle or schema rule changes in this slice.

`loan-entry.js` replaces only the shared entry root using the ordinary POST response,
keeps actual file input nodes locally and excludes files from change requests.
Abort/revision checks discard stale responses or retry with newly edited facts.
Existing native widgets, price checks, add/remove controls and camera initialize
on `loan-entry:ready`; edit-draft controls remain supported. Removed rows stay hidden
across switches. Failure retains the original form/photos and offers retry.
Without JavaScript the same read-only POST retains strings; file inputs need
reselection, with an explicit warning.

Final 142 affected tests pass (78.846s), covering native draft save/validation,
paper admission and four new scope/no-posting/retention cases. Actual desktop,
mobile and no-JavaScript checks pass; desktop admits P-0056 after a round trip.
Selected photos survive JavaScript round trips; changing purpose after review
discards its signature. Native earlier-date metal-price preflight remains blocked.
Saved PDFs retain exact bytes. Private evidence is
`.tmp/loan-entry-refinement-20261003`; candidate 8078 and all 1,529 runtime files
match `rokkad:entry-refined-20261003-a80e473e`, through existing migration 0057.
Existing loan rows and file bytes were unchanged during update; production is
unchanged. Real staff/hardware and hosted release acceptance remain pending.

## UR-19–22: shared collateral entry and scoped purpose defaults

Migration 0057 adds `default_entry_purpose` to existing economic configuration,
with INHERIT/DIRECT/PAPER choices and a database constraint. Resolution uses today's
latest revision per scope; inheritance moves to license then Workspace, and the
system fallback is DIRECT. GET entry selection may use the default; POST purpose
is explicit so preferences cannot reinterpret submitted facts. The common purpose
navigation and collateral template are reused by native and paper creation. Native
approval/rate/photo services remain unchanged. No new Workspace-owned table is added.

Paper creation preserves backward-compatible flat requests while the new editor
uses bounded Django formsets and canonical item agreements. Server-side standing
terms resolve each item's original-date metal rate and aggregate principal, rounded
monthly/advance interest and fees. The recorded item profile is versioned as
`recorded-anniversary/2`; existing version 1 contracts keep their calculation.
Signed review binds all item amounts/rates, source facts and derived totals.

Typed receipt fields capture staff-specified principal per item, with exact-total,
balance, membership, precision and review/retry validation. The ordinary writer
persists canonical allocation lines and labels the retained split STAFF_SPECIFIED;
direct repayment's highest-rate-first path remains unchanged. Full closure covers
all items. Original-term and receipt corrections/replay retain old snapshots and
require explicit reviewed replacement splits when earlier changes alter principal.
Current ordinary renewal supports the new recorded source through existing current
approval; optional already-completed linked paper renewal still retains its older
one-group boundary. Independent multi-item paper entry/closure needs no ancestry.

UR-19-22 verification: 502 regressions pass in 445.006s; 105 overlapping final
receipt/draft checks pass in 61.683s. The browser confirmed actual desktop/mobile
admission, explicit item receipt splits, full closure, no-JavaScript add/review,
series-default routing/direct override and unchanged saved PDFs. Confirmation
checkbox events are excluded from review invalidation; changing transaction facts
still removes stale review. Independent runtime checks reproduce 10,000 principal,
280 advance interest, 10 document charge, 9,710 proceeds, a 1,500/500 item principal
payment, remaining 4,500/3,500 and next-anniversary interest 230. Current monitoring
retains the known 8,000 exposure with unconfirmed-book provenance. Schema-matched
native export includes all item agreements/allocations.

Private QA evidence is `.tmp/multi-item-paper-20261003`. The first broad run's
single recovery deadlock was against autovacuum, established in PostgreSQL logs;
the isolated rerun disables vacuum on disposable QA tables only. Product recovery
locking and restricted-role restoration checks remain unchanged. Python parsing
(540 Loans files), migration consistency and scoped whitespace checks pass. The
global import guard retains eight baseline billing-import findings in four Loans
test files; no new finding is introduced. The fictional local candidate is updated,
with verified backups; real staff/hardware and hosted deployment remain pending.

## UR-15–18: standing defaults and routine entry

Migration 0056 adds optional standard tenure to the existing Workspace-owned
economic policy, with a 1–600 month constraint and ordinary setup field. No old
policy or loan tenure is seeded or rewritten. Lakshmi's accepted setup value is
12 months. Original-date defaults reuse existing series/license/Workspace policy,
metal-rate and license fee resolution; current monitoring resolves separately.
An unambiguous eligible Flexible Partial Payment version is preferred.

The ordinary paper form now shows transaction facts and jewellery, loads its
standing agreement and calculates advance interest and net proceeds. A native
submit fallback works without JavaScript. Actual supported exceptions and their
source reason are expanded only when needed; old activity and complete-book
verification are optional sections. Server-side re-resolution binds final signed
review and preserves original financial snapshots, dates, source references and
physical-cash meaning. Unsupported setup is explained instead of silently omitted.

Routine confirmation records displayed facts without fabricating a whole-book
review. Archive admission retains complete reconciliation. Unverified paper closure
does not assert complete history. Receipt entry still uses ordinary total-only
allocation. Snapshot V5 retains usable known monitoring amounts and provisional/
unavailable counts; detail verification is passive except explicitly missing
activity. Borrower reminders and auction readiness keep their coverage gates.

UR-18 is complete locally: 422 final regressions pass in 369.684 seconds, and a
156-case affected rerun passes (overlapping). Actual desktop/mobile/no-JavaScript
entry and review pass, including preservation of typed facts during automatic
refresh. The browser caught action-button names shadowing the form action property;
fetch now reads the explicit HTML action attribute. Browser-posted dated receipt
and paper closure reconcile under runtime RLS. All 1,519 runtime source files match
the scoped candidate image `rokkad:paper-simple-20261003-c5462662` at localhost 8078,
with migration 0056, owner refusal and restricted production startup verified.
Old loan contracts are unchanged. A verified physical database backup, media copy,
prior containers/images and a fresh matching-schema ordinary-Loans native ZIP are
retained privately in `.tmp/paper-simplification-20261003/`. Production is unchanged.
The final template keeps unused activity collapsed after a successful review and
uses the readable monitoring label. Its 18 focused form/monitoring checks pass,
and actual desktop/mobile/no-JavaScript acceptance was repeated successfully.
See the [decision](../adr/2026-10-03-standing-terms-and-routine-paper-entry.md).

## UR-08–UR-10: operational completion slices

The local completion programme adds ordinary paper-book checkpoints and atomic
multi-loan transaction reviews, optional original closing numbers with explicit
system-number provenance, and later customer handover confirmation. The checkpoint
table is directly Workspace-owned, forced-RLS and append-only (migration 0047).
Handover evidence is a guarded immutable LoanChangeLog plus ordinary custody rows
(0048); it changes no money or original release item timestamp. Release artifact
fingerprints include handover evidence, preserving old issued bytes.

Original and recorded-successor principal/rate/date corrections use retained
policy/disbursal/schedule snapshots, compensation and chronological receipt replay.
A successor correction reconciles its predecessor's actual renewal cash in the
same transaction. Original numbers and source documents remain. An unchanged
native successor is a signed locked dependency, retaining its original approval.
Single dated paper closures can correct date/amount/confirmed recipient while
retaining confirmed or unspecified custody. Contract/closing correction logs are
immutable (0049/0052). Coverage becomes stale and needs another paper check.

Migration 0051 retains multiple principal-opening lines per item, unique per event
and item; 0054 guards one active opening under the item lock. Date-only custody
revisions use a self `restatement_of` link (0053). The insert guard preserves
source, item, Workspace and transition. Its deferred constraint requires the
matching canonical financial correction, actual date, recording actor, reason
and superseded/replacement IDs. Current custody omits superseded rows. This does
not simulate a physical undo/redo or disable ordinary starting-state checks.

Reviewed imported openings now use ordinary Renew with their bounded collection
baseline and remaining obligations. Catch-up interest is recognized once through
the dedicated opening storage boundary, then its settlement terminates the old
schedule and transfers custody. Current renewal requires an explicitly selected
current successor product and ordinary current approval; paired reversal restores
the opening source/catch-up together. Known completed paper renewal retains actual
terms/date/net cash and creates a recorded successor. Original cutover evidence
and the pre-cutover unavailable-history boundary remain intact.

Verification: 32 focused domain/document/opening tests and the final overlapping
52-test run passed (43.229 seconds). Nine captured fictional pages passed desktop,
390px mobile and no-JavaScript checks with installed static assets, no overflow or
page errors. The before/after handover PDFs were reconciled and visually inspected;
old bytes remain readable. The subsequent broader run passed 599 regressions in
421.791 seconds. The UR-11/12 integration selection passed 125 tests in 51.604
seconds on a fresh database, including native entry, funding, statutory handling,
corrections, opening renewals, recovery and tenant guards. A further 147 boundary
tests passed in 141.454 seconds, covering archive duplicate guards, transaction
reviews/notifications and shared receipt corrections. Counts overlap.
The final fresh-database selection passed **745 tests in 463.689 seconds**,
including the document fallback corrected after the first broad attempt.
Model drift is absent and all 1,401 frozen QA source files match the checkout.

Remaining programme: additional real business profiles and actual staff/release
acceptance. Local technical verification is complete for the implemented profile.
Shared-batch
date/custody amendments, arbitrary custody reversals, concessions/capitalization
and unsupported original terms are not enabled by these correction commands.
All new migrations are local, with no Workspace rollout or production deployment.

## UR-11/UR-12: native recovery and current auction integration

`pawn_recovery.py` defines `ordinary-loans-native-recovery/1` with an explicit
89-model ordinary-Loans inventory; a changed inventory refuses export until the
profile is updated. It captures actual identities/timestamps and connected paper,
opening/native renewal, financial corrections, custody, funding/storage, reviews,
archive evidence, setup and retained files. Model shapes, trigger/function/check/FK
definitions and forced-RLS policy fingerprints bind the matching restore schema.
No source actors are impersonated through new business actions.

The ordinary read-only download supplies the ZIP and independently retainable
checksum in its filename/header. The owner-only `pawn_recovery` command previews
by inserting the exact rows and reconciling, then rolling back. Commit requires
empty ordinary-Loans tables, original Workspace/Party/actor/Rates/portability
identities and separately retained checksum. Existing media must match; newly
written media are removed after failed reconciliation. Original document bytes,
every typed row, agreed/recognized balances, reviews and custody must match the
source. Sequences only advance. Runtime cannot restore or disable evidence guards.
Cross-Workspace remapping and external original-source objects remain outside this
native backup; full database/media recovery is necessary for prerequisites.

Recorded-origin current auctions now require confirmed paper coverage through today
under the loan lock at initiation/start/completion. The existing administrator,
overdue, statutory-readiness and vault checks remain. Completion recognizes the
anniversary-interest delta in a canonical event, retaining its identity and prior
review in the recovery payload without a fictional calendar accrual. It allocates
available schedule capacity, terminates the schedule, disposes custody and appends
coverage for the now-closed loan. Coupled reversal restores the original agreement
and reverses exactly that recognition. Generic recorded-history reversal stays
blocked. Shortfall/surplus, historical sales and imported-opening auctions stay
outside the ordinary full-debt recovery profile. New document labels have typed
registry bindings. Migration 0055 matches the custody guard's business date to the
existing India timezone, including the UTC/India midnight boundary.

Recovery tests include corrected terms/receipts, paired renewal/date/custody
revisions, coverage, handover, retained PDF bytes, statutory attachments, rollback,
media conflicts, missing prerequisite identities, checksum/empty-destination gates
and restricted-role refusal. The original reused QA database retained unrelated
fixture rows and produced global-count failures; the fresh 125-test run passed.
The final broad release selection passed on a separate fresh isolated database.
The [operator/release guide](../flows/paper-first-operator-and-release.md) names the
actual paper examples and target checks still needed; no real-record sign-off,
production migration or rollout has been claimed.

## UR-07: independent paper loans and subsequent renewal

The primary form records one loan, with optional deducted advance interest and
document charge. `recording.funding` explicitly identifies PROCEEDS or confirmed
CASH. Ordinary `values.net_cash` remains contract proceeds; reports and recorded
copies label unknown physical cash. Existing submissions keep their previous
meaning. Unknown closing handover uses migration 0045's PAPER_CLOSED choice on the
existing item/custody-event models, retains last-known storage and records no
`returned_at`. Financial closure still uses the canonical full-settlement writer.

`recorded_closures.py` and `recorded_renewal_actions.py` provide actor/Workspace-bound
signed, expiring previews; confirmation locks the scoped source, reruns reconciliation
and compares its transaction fingerprint and review. Exact authorized retries return
existing results; changed facts, intervening activity, duplicate numbers/references
and backwards dates are refused. The completed-renewal action reuses the existing
recorded renewal writer with NET_SETTLEMENT, successor advance interest and document
charge. Photos and storage allocation carry to retained collateral. Ordinary renewal
now recognizes the source's agreed anniversary interest while retaining normal
current approval for its native successor.

Recorded contract and current position routes render fixed document projections and
retain official issued bytes through the existing document service. Their original
contract source and date-specific financial/coverage fingerprint are explicit;
projection and issuance share the scoped loan lock. A changed completeness review
creates a new position copy while the old issued bytes remain available. No historical
approval or fixed future amortization promise is fabricated. Existing native
configured layouts stay on their existing path.

Verification used the isolated local PostgreSQL test database
`test_paper_first_20261003`, ordinary test settings and the source archive mounted
into the existing local candidate image. No deployment has occurred. See the
[UR-07 decision](../adr/2026-10-03-independent-paper-loans-and-renewal.md) for profile
limits and the remaining portability, recovery and imported-opening renewal work.

The broad suite passed 508 tests in 333.608 seconds (admission/corrections/archive,
native entry, reports, exports, opening restore, risk, reminders, registry/RLS and
Notify). Follow-up suites passed 98 tests in 130.459 seconds (native lifecycle and
current paired renewal reversal from a paper source), 154 in 68.819 seconds
(documents, retained bytes and coverage changes), 90 in 67.196 seconds (unknown
handover, settlement correction and pledge register) and 15 in 8.488 seconds
(final routine paper profile including changed-collateral refusal). Counts overlap.

Captured fictional Django responses passed Playwright desktop (1440 px), mobile
(390 px) and JavaScript-disabled checks for entry/closure/renewal and their signed
review/confirmation controls, without overflow or page errors. Contract and current
position PDFs retained the original deductions/net payout and were visually
inspected across both pages. Tests assert repeated requests return identical issued
bytes, and a coverage-only change creates a new position copy while retaining the
old bytes. No live customer records were written for browser QA. Private captures
are under `.tmp/paper-first-20261003/`.

Makemigrations check/dry-run found no drift; Django system checks passed. The static
guard passed 841 tracked Python files; syntax covered all 499 Loans Python files and
runtime boundary checks included untracked files. Existing unrelated test-fixture
billing-model imports are outside that runtime check. Local documentation links and
diff whitespace checks passed. After QA, only the isolated
`test_paper_first_20261003` database was removed; existing local candidate services
and databases were retained.

The owner authorized implementation on 2 October. The
[tracking plan](../plans/unified-loan-recording.md) tracks UR-01 through UR-07.
Earlier sections preserve their delivered checkpoints: UR-01 adds dated opening-loan
receipts, UR-02 the recorded-contract foundation and UR-03 reviewed never-entered
admission. UR-05 subsequently adds bounded archive admission; UR-07 provides the
clarified routine independent-entry/servicing workflow described above. Broader
portability/recovery and amendments remain explicitly pending.

## UR-01: dated paper receipts on existing opening loans

The existing screen offers receiving/recording now or recording money already
received on paper. Paper entry takes a total amount, actual date and receipt or
book/page reference. Preview shows the calculated interest/principal allocation
at that date. Confirmation requires the signed review and an explicit statement
that the money was already received. No scan or historical metal price is required.

The supported calculation is the existing reviewed opening collection profile:
original anniversary interest, with reduced principal affecting the next charging
anniversary. It is not selected as a universal paper-loan contract. The date must
be strictly after the opening checkpoint and at least as late as all recorded
financial events. Earlier-today receipts are supported. Later activity, outstanding
fees and principal reductions across multiple principal-bearing items require
further supported handling; this slice refuses them with a specific explanation.
Interest-only payments can cover multiple items. Paying all debt retains custody
and requires the existing explicit full-release action.

The wrapper in [paper_repayments.py](../../apps/tenant_apps/loans/services/paper_repayments.py)
uses the existing collection calculator and canonical repayment writer. It locks
the scoped loan, checks normal repayment authority and business-write availability,
and signs Workspace, loan, recorder, request, source facts, allocation and latest
event. Review expires after one hour. Confirmation rechecks all inputs under the
same loan lock; an intervening event or changed amount/date/reference requires
review again. Authorized exact retries return the existing event without new cash.
Changed retry facts and reuse of a paper reference with another request are refused.

No schema migration or new parallel balance is introduced. Immutable repayment
payloads and change logs carry `paper-repayment/1` metadata: source reference and
normalized duplicate key, actual date with DAY precision, received total,
derived-allocation basis and receipt confirmation. Original receiver stays unknown;
the ordinary event creator/time identifies the current recorder. Existing events
remain untouched. Ordinary current receipts keep their existing payload shape.

Source-reference uniqueness is per loan, including retained reversed receipts.
A book/page reference must distinguish each receipt within that loan. Re-entering
a corrected receipt under the same reference is not the correction workflow;
broader source-linked correction support remains UR-04. Cross-loan numbering and
archive admission identity are UR-03/UR-05 work.

## Readers, documents and restoration

Existing as-of balances, future interest/exposure and correction services consume
the same canonical events. Financial settlement does not return collateral.
Loan history shows the paper reference and identifies calculated allocation.
Receipt projections distinguish paper origin from ordinary current entry through
the existing required document-status field, and supply the paper reference and
actual entry timestamp as additional fields. Custom layouts can omit optional
fields, but retain their required effective-date/status bindings.

Opening collection replay validates the added metadata, amount/date binding and
source-reference uniqueness. Opening export/restore preserves the metadata while
recording the destination actor/time normally. Original local actors/times remain
in the retained source export, not impersonated as destination users. The existing
version 2 opening export already retains versioned nested repayment JSON; sealed
older documents and field lists are unchanged.

Repayment precision validation now normalizes a stored quantum such as `0.010000`
to `0.01`, preventing storage scale from admitting sub-cent amounts. Non-finite,
nonpositive and out-of-range amounts are refused before calculation.

## Verification and remaining boundary

The final Linux run reports **163 tests passed in 60.732 seconds**, on fictional
fixtures in a separate disposable test database. Coverage includes dated and
earlier-today entry, partial interest, future exposure, unknown current valuation,
source reference/retry checks, changed/expired review, authority and foreign
Workspace refusal, rollback, unchanged custody, corrections, fee/multiple-item
refusal, native entry refusal, ordinary repayment compatibility, documents and
opening export/restore. Existing opening event storage, native lifecycle, document
layout and risk/monitoring suites pass alongside the new cases.

The first focused run exposed the currency-precision issue described above. The
first broad run also required the isolated harness's scratch directory and an old
HTTP assertion to recognize the existing formatted `1,010` display while checking
numeric `total_due` independently. These are resolved in the final run.

Chromium checks the captured fictional Django review response at 1440/390 pixels
and without JavaScript: selected purpose/date/reference, signed hidden review,
readable allocation and no page errors or document-width overflow. Desktop and
mobile screenshots are inspected. These are captured-response layout checks;
posting and permission behavior are verified by the Django HTTP/service tests,
not a production browser session. Configured Bootstrap assets are supplied
unchanged for local QA.

All 1,293 application/template files still match the tested frozen source archive.
The supported-app boundary check, scoped whitespace check and documentation links
pass. Local evidence is under `.tmp/unified-recording-20261002/`; this is an
uncommitted source snapshot, not a deployed release. No production deployment,
real cash posting, archive conversion, migration or existing local pilot
replacement occurs in this slice.

The full adaptation still needs ordinary admission of recorded origination,
never-entered mixed timelines, renewal/closure admission, corrections that
affect later activity, archive source linking, scoped entry completeness and
downstream reminder integration. Recording one receipt does not certify that a
loan's or Workspace's entire paper book has been entered. Current valuation and
transaction completeness remain separate requirements.

## UR-02: recorded contract and payout storage

[Migration 0041](../../apps/tenant_apps/loans/migrations/0041_recorded_origination_basis.py)
extends the existing `LoanPolicySnapshot` and `PawnLoanDisbursalSnapshot`; there is
no new Workspace table or ledger. Existing policy/disbursal rows default to their
existing origination/approved meaning. Approved payouts still require an approval.
Recorded payouts require a recorded contract basis and must have no approval FK.
PostgreSQL checks bind the snapshot to its own Workspace/loan/policy/event and
match source metadata, actual date, contract identity, payout values and monitoring
selection. Existing append-only triggers and forced RLS remain in place.

[Recorded evidence validation](../../apps/tenant_apps/loans/services/recorded_origination_evidence.py)
requires matching versioned `recorded-origination/1` JSON in the snapshot and
ordinary DISBURSAL event. It retains original number, principal, rates, tenure,
explicit interest/rounding rules, item particulars and a paper reference. Original
actor can remain unknown; the event/snapshot retain the actual recording user/time.
Date-only source evidence does not invent a historical clock time. No historical
quote, approved appraisal or previously configured digital origination policy is
required. Gross, deductions, net cash and item allocations must reconcile.

Initial storage validation supports simple monthly interest, the existing explicit
partial-month rules, two-decimal currency, no fees and zero or one advance month.
This is a tested technical boundary, not confirmation of Lakshmi's exact paper
contract. The upcoming admission command must verify the selected product and
actual agreed rules. Storage validation alone does not authorize or reconcile
admission, reserve original numbering, detect the same source across archives and
imports, or certify custody/completeness. No public command or form activates this
new origin yet; tests create fictional fixture aggregates directly.

Contract interest rules and a separately recorded monitoring choice share the
existing policy storage. The monitoring choice includes method, LTV, selection
date and reason. Current valuation identifies `recorded-monitoring-basis:<id>`
instead of implying a past lending approval. Missing current prices or appraisals
leave coverage unknown. New quotes/reappraisals affect ongoing coverage, without
rewriting original terms or filling a missing original valuation. Recorded-contract
interest and economic-exposure projection normalize the stored currency quantum
to its numeric precision; existing origination calculations retain their behavior.

The pledge-book reader uses retained paper particulars and explicitly identifies
their source; missing original valuation and borrower/address stay unknown. It
does not substitute current customer details. Approval-based loan tickets remain
unavailable without approval. Existing history export refuses a recorded origin
with a profile-specific explanation; a lossless portable profile is still required
before release. Backups retain ordinary event/snapshot JSON. Original payout
reversal is refused because the existing reversal would return it to APPROVED;
that would be a false history. Ordinary later repayment/reversal readers continue
to consume the same financial records.

### UR-02 verification

The broad Linux run executed **311 tests in 213.380 seconds**: **309 passed**.
The only two errors were missing published history JSON/schema files in the
disposable container, not changed application behavior. After adding the repository
`docs/contracts/` fixtures, both exact pure schema/example test methods passed
independently in 0.008 seconds. Their original database setup is unnecessary for
those methods; no database behavior is inferred from this separate rerun. The
application/template source was unchanged between the broad run and fixture check.

Ten new tests cover source/date preservation without quotes, approvals or original
appraisals; as-of principal; agreed interest and advance credits; currency precision;
unknown then current coverage; separate current physical appraisal; repayment,
retry and reversal; incomplete/inconsistent evidence; honest pledge-book and
unsupported document/export/correction boundaries; restricted-role SQL, immutable
rows, cross-loan references and Workspace isolation. Existing native approval,
economics, redisbursal, balances, schedules, interest, monitoring/reappraisal,
opening servicing/restoration, documents, pledge books and v1/v2 history portability
tests also run. The initial focused run exposed three test-fixture mistakes
(missing as-of argument, monitoring metadata and conflicting Workspace context),
which were corrected before the broad run.

`makemigrations loans --check --dry-run` reports no changes. Test databases apply
migration 0041 successfully. The test command warns that the deliberately unused
base database does not exist before Django creates its separate test database;
it does not connect to a live lending database. Populated production migration and
rollback/release rehearsal remain deployment work. No browser QA is claimed for
this slice because it adds no entry screen.

All 1,296 application/template files still match the tested source; the final QA
archive also contains 24 published contract files. The tracked-app boundary check,
scoped whitespace/syntax checks, 896 curated documentation links and 24 links in
five changed guides pass. Evidence and runner scripts are under
`.tmp/unified-origination-20261002/`. The new migration has been applied only to
disposable test databases. Production and the existing local pilot are unchanged.

## UR-03: complete paper-history admission

**Scope correction after owner clarification:** the verified implementation below
supports unchanged/reduced principal on renewal, but not top-ups. The owner clarified
that top-ups are part of the required business workflow. The earlier custody answer
was interpreted too narrowly; zero top-up is not an agreed business restriction.
UR-03A tracks the extension and explicit cash/interest settlement evidence before
UR-04. Existing test counts do not establish support for the clarified top-up scope.

The ordinary New loan route delegates an explicit paper-entry purpose to
[recorded_history.py](../../apps/tenant_apps/loans/web/recorded_history.py).
Preparation stays in the bound form; preview executes the complete command inside
a rolled-back savepoint. Confirmation re-executes under a Workspace aggregate lock
and compares the signed, actor/Workspace/submission-bound request and result. Reviews
expire after one hour. Exact committed retries return the original loan; changed
facts require a new review. No public incomplete active loan, separate paper ledger,
new table or additional migration is introduced in this slice.

The [admission service](../../apps/tenant_apps/loans/services/recorded_history.py)
checks business-write availability and action permissions, scoped borrower/series/
contract identities, source reference, normalized number collisions across ordinary
loans/archive evidence/imported source numbers and live counter ranges. The shared
history/opening setup path also refuses an admitted original number under a new
import identity. Workspace and ordered sequence locks serialize competing admissions
and current numbering; matching counters only advance. Arbitrary original numbers
outside current patterns are retained. Archive matches are refused pending UR-05's
explicit source link; this does not establish identity between unrelated sources
that use different numbers/references.

Supported facts are one collateral group, simple FULL_MONTH interest, two-decimal
HALF_UP monthly amounts, zero/one original advance month, no fees or concessions,
up to 30 chronological transactions, five full carry-forward renewals and a ten-year
entered history. Current non-amortising bullet/flexible product versions supply the
matching maturity/grace contract; they do not approve original collateral value.
Dates and unknown original operators remain distinct from recording actor/time.
The source total and calculated receipt split remain separately identifiable.

The owner confirmed that the current month retains its earlier principal and that
reduced principal applies from the next loan anniversary. The UI requires explicit
confirmation of the precise `recorded-anniversary/1` rule: charge a full month from
the original date and each month-end-clamped anniversary; a receipt on that day
changes the following charge. Closure on a maturity anniversary therefore includes
the new full-month charge. Renewal starts a new agreement/anniversary. This is not
the older reviewed-opening day-after-anniversary convention and is never silently
applied to those loans.

[Collection calculation](../../apps/tenant_apps/loans/services/recorded_collections.py)
records a cumulative interest delta with the anniversary bases in ordinary immutable
INTEREST_ACCRUAL events before collections. It does not fabricate completed-period
accrual documents or restart a month after each receipt. Existing schedules and
allocations remain immutable; due/maturity/delinquency read models replace the
original fixed interest projection with the agreed principal-sensitive amount.
Projection uses only financial events through its requested as-of date. Allocation
to the original schedule is capped at its remaining capacity; later collection
interest stays traceable in source events. Closed/renewed settlement terminates the
schedule normally. Current exposure and valuation retain their separate provenance.

[Renewal admission](../../apps/tenant_apps/loans/services/recorded_renewals.py)
settles all source interest and any principal actually paid, carries the positive
remaining principal into RENEWAL_OPENING, and records standard renewal/principal/
custody links. The old loan closes; old custody transfers to the successor while
physical collateral remains held. There is no successor DISBURSAL, top-up or
fictional cash payout. Full closure uses the ordinary release writer with the actual
release number, date-only return evidence and recorded recipient; no historical
price or invented return timestamp is needed.

Ordinary loan details expose source, entry time and confirmed-through date. Current
and later dated receipts without subsequent recorded activity, and ordinary full
release, use the agreed calculation. Pledge-book entries show paper terms, renewal
cash separately from carry and actual return recipient; missing original appraisal
and borrower/address snapshots remain unknown. Release/renewal memos identify paper
recording, source reference and actual entry time; renewal cash is described as
already received and missing old valuation stays unknown. Admitted timeline reversals require
UR-04's dependency review. Further ordinary renewal, notices, auctions, approval-based
tickets, the unsupported fixed-schedule KFS and portable export remain guarded, not silently processed with
a different profile. UR-06 must finish broader completeness/report/document/reminder
coverage before rollout; admission is local only.

### UR-03 verification

The combined Linux run passed **508 tests in 282.588 seconds** on fictional
fixtures. It covers recorded active/closed/renewed histories, same-day and month-end
allocation, advance interest, as-of/future projection, ordinary servicing, source
and archive guards, expired/changed review, original-number reservation, retry,
concurrent identical/distinct submissions, scoped borrowers, restricted-role
admission/isolation and atomic rollback. Native origination, receipts, releases,
notices, delinquency, documents, opening restore/export and history schema suites
also pass. The restricted-role test settles its original Workspace's deferred
custody constraints before deliberately switching the RLS identity.

Initial checks exposed carried-principal decimal scale, an unscoped borrower
lookup and an added native obligation query; all are corrected. The original
obligation reader's two-query regression test passes. Existing mock-loan fixtures
now declare their policy relation; concession document expectations match the
already established compact currency formatting while retaining numeric checks.

Four files subsequently changed for paper release/renewal document status, truthful
past-tense cash wording, unknown valuation and the unsupported fixed-schedule KFS
guard. Their focused document/UI/history run passed **171 tests in 60.743 seconds**
against the final frozen source. All 1,327 archived application/template/contract
files match the tested snapshot; model/migration consistency passes. The isolated
test database was removed after verification. Evidence is retained locally in `.tmp/unified-history-20261002/`.

Chromium checks the fictional Django review at 1440/390 pixels and without
JavaScript, including source number, signed review, visible allocations and no
page-width overflow or JavaScript errors. Screenshots are inspected. These are
captured-response layout checks; Django HTTP tests verify posting and retries.
Supported-app import checks pass for tracked source and the eight new unified
recording Python files. Documentation links and scoped whitespace are checked.
No production database, real loan, archive or existing local pilot is changed.


## UR-03A: explicit renewal cash and independent custody

This extension supersedes UR-03's zero-top-up/held-only limit above. Ordinary paper
entry now supports carry with reduction/top-up, or actual full principal repayment
and a fresh advance. The source debt settles and successor opens exactly once;
new principal equals old less principal paid plus gross advance. Existing renewal
fields and versioned cash JSON avoid any new table or migration.

Both separate interest receipt and explicit offset from the advance reconcile to
actual cash received/paid. No new-contract advance interest, fee, concession or
capitalization is inferred. Collateral handling is independent: held transfer or
actual same-day return/repledge of the same group, with recipient and dated custody
events. Original actors/times remain unknown; the current recorder is retained.

Signed review and retry digests include the new facts. Existing UR-03 command input
without extended fields retains its original carry-only meaning and exact retries;
the browser requires explicit renewal fields. Old posted evidence is not rewritten.
Review, loan detail, renewal report/export, pledge book and renewal memo show gross cash,
offset and carry. The model top_up_amount represents gross advance for this profile;
its display says gross new advance, including full redraw. Original approved/native
renewal behavior remains unchanged. Risk exposure uses the successor principal and
new anniversary terms. Broader report/export integration remains UR-06.

### UR-03A verification

The combined fictional-data run passed **522 tests in 299.410 seconds**. After final
source-principal/payout-evidence and review wording changes, **126 tests passed in
35.353 seconds**, covering paper history, reports/exports, documents/layouts and
native lifecycle. Tests reconcile unchanged/reduced/increased carry, full principal
repayment/fresh advance, separate/partial/full interest offset, both custody paths,
successor interest/exposure, earlier as-of exposure, receipts/closure, two renewals,
duplicate retries, altered signed facts, invalid/missing cash and atomic rollback.
Restricted-role tests admit returned/repledged history, resolve deferred custody
checks, and verify foreign-Workspace loans, renewals, custody and events remain hidden.

Initial checks caught excessive decimal scale on derived carry and a repledged
successor incorrectly starting in IN_VAULT before its custody event. Normalize
contract principal to currency precision and create that successor item initially
WITH_CUSTOMER, then record and project its vault entry in the same transaction.
No database guard was relaxed. Two mistyped test labels were corrected; final
report/lifecycle suites passed. Existing signed UR-03 requests may need a fresh
preview when their review shape changes; already admitted exact retries remain
idempotent without rewriting evidence.

Desktop/mobile/no-JavaScript checks of the captured Django response pass at
1440/390 pixels with no page overflow or script errors. The responsive review table
scrolls horizontally on narrow screens. Renewal memo and release/renewal export PDFs
were rendered, text-checked and visually inspected for cash/offset/custody evidence.
All 1,327 application/template/contract files match the final test snapshot; migration
consistency, tracked and changed-file import boundaries, whitespace and 930 local
documentation links pass. Local evidence: `.tmp/unified-renewal-20261002/`.
The isolated test database was removed after verification.
No production, existing pilot, real loan or historical archive has been changed.

## UR-04: supported receipt correction and dependency review

The [correction service](../../apps/tenant_apps/loans/services/recorded_corrections.py)
and [ordinary Loans screen](../../apps/tenant_apps/loans/web/recorded_corrections.py)
support missing receipts, replacements and voids on an active admitted anniversary
contract with one vault-held collateral group. A successor's own receipts can be
corrected; its predecessor renewal remains frozen. The
[ADR](../adr/2026-10-02-recorded-receipt-corrections.md) defines business-date
restatement, source retention and explicit same-day ordering.

The review executes the actual correction inside a rolled-back transaction. It
shows source dependencies, old/new receipt facts and principal/interest allocations,
plus current balances. Confirmation repeats under the loan lock, verifies actor,
Workspace, input digest and unchanged event fingerprints, and commits atomically.
The command requires administrator, repayment/accrual and Workspace-write authority.
Compensations retain their source business dates and reverse obligation allocations;
replay uses the ordinary repayment writer and anniversary calculation. Immutable
metadata links the batch, original/root receipt and reason. Source records, printed
documents and their original recording times are not edited. No new table or
migration is required.

Known receipts retain their total/date/reference, with the original event supplying
the recorder trail. A corrected target may change those facts explicitly. Retained
paper references cannot be reused by a different receipt. Changed/expired reviews,
different retry facts, overpayment and unsupported dependencies roll back the whole
operation. Generic individual reversal cannot split this profile's receipt/interest
history. Subsequent ordinary repayments continue from corrected debt. Detail,
pledge-book, report and receipt-document readers identify historical corrections
and avoid representing compensations/replays as new cash movements.

**Boundary:** this is not full cross-lifecycle correction. A source with renewal
settlement, closure, auction or incompatible custody/accrual/correction displays
its dependencies and cannot post through this route. Actual revised settlement,
successor/custody facts and their consistent documents need a remaining UR-04
extension. Native and migration-opening histories retain their existing supported
paths. The original completeness cutoff is retained; no broad completeness or
reminder/export support is implied.

The first focused run passed **174 tests in 67.115 seconds**, covering concurrency,
rollback, changed/expired reviews, receipt root/reference retention, same-day order,
restricted-role isolation, successor boundaries, closed-history refusal, later
servicing, risk/as-of reads, reports and existing document/lifecycle behavior.
The broad regression run passed **568 tests in 327.261 seconds**. After adding old
date/reference comparisons and readable correction descriptions, the final run
passed **135 tests in 39.424 seconds**, including a rendered, text-checked corrected
receipt. The PDF and desktop/mobile review screenshots were visually inspected.
Chromium checks at 1440/390 pixels and with JavaScript disabled pass; narrow tables
scroll within their container without page overflow. All 1,331 archived source
files match the final tested snapshot. Migration consistency, 841 tracked-file and
11 changed-file import-boundary checks, whitespace and current documentation links
pass. Local evidence lives in `.tmp/unified-correction-20261002/`.
The isolated correction test database was removed after verification.
No production, existing pilot, archive or real loan changed. UR-04 remains open for
cross-lifecycle correction; this checkpoint delivers its receipt/accrual boundary.

## UR-04 settlement extension (2–3 October)

The [settlement ADR](../adr/2026-10-02-recorded-settlement-corrections.md) extends
the prior receipt-only checkpoint. The same ordinary correction form now supports
a later recorded renewal or full return with unchanged date, numbers, successor
agreement and custody. Operators supply actual settlement cash, explicit interest
offset, source reference and confirmation. Conflicts show actual versus required
cash and roll back; no inferred cash/refund/concession or new successor opening.

[Settlement correction services](../../apps/tenant_apps/loans/services/recorded_settlement_corrections.py)
validate the retained lifecycle evidence, bind forward successor state to signed
review and write canonical replacement settlement/closing/allocation records. The
shared renewal cash reconciler is used by both original admission and correction.
Original loan state stays CLOSED; repayment's private closed replay requires a
compensated recorded settlement. Obligation termination is compensated and replaced.
No new models, migrations or custody movements are introduced.

[Current settlement selectors](../../apps/tenant_apps/loans/selectors/recorded_settlements.py)
project the latest financial particulars while retaining original release/renewal
identity and evidence. Loan/release views, settlement reports and exports, pledge
books/activity and regenerated memos expose current facts and correction provenance.
The release browser disables sorting by the obsolete original settlement amount.
Existing saved documents and statutory page snapshots remain retained evidence.

The correction supports up to five forward successors, active or closed. Signed
state binds their events, contracts, states, custody and current date. Subsequent
activity invalidates preview; exact retries are safe. Current successor monitoring
continues from unchanged terms/events. Source as-of reads reflect corrected dates.

Broader amendments to origination/successor terms, settlement date, funding method,
custody remain outside this command. Shared batch receipts now use the extension
below. Native/opening
correction behavior, archive admission, completeness refresh and notice/export
guards retain their existing scope. UR-04 remains open for those broader amendments.

The broad regression run passed **598 tests in 376.269 seconds**. Final UI,
release/renewal reader, pledge-book, export, document and release-batch checks passed
**233 tests in 172.665 seconds**. Coverage includes full closure, carry/reduction/top-up,
redraw, interest offset, returned/repledged custody, successive renewals and a closed
successor, same-day receipt/settlement, repeated correction, rollback, stale review,
concurrency, exact retries, restricted-role isolation, current risk and historical
balances. Tests assert that successor events and physical custody are not duplicated.

Desktop/mobile/no-JavaScript response checks pass. Corrected release/renewal memos
were text-checked and visually inspected; section headings now stay with their
tables. Migration consistency, 841 tracked-file/21 changed-file import boundaries,
1,334 source snapshot hashes and 949 curated documentation links pass. Local evidence
is under `.tmp/unified-settlement-20261002/`. No production or pilot data is changed.
The final readable agreement/custody labels passed **31 settlement tests in 46.838
seconds**, followed by fresh desktop/mobile/no-JavaScript captures. The isolated
settlement test database was removed after verification.

## UR-04 release-batch correction extension (3 October)

The [batch service](../../apps/tenant_apps/loans/services/recorded_batch_corrections.py)
locks the batch and sorted member loans, normalizes changed/unchanged selections,
binds every member to signed review and reuses receipt/settlement replay atomically.
Individual revised cash must reconcile to that loan, and the sum must equal the
entered actual combined collection. Exact retries serialize on the batch; changed
facts, stale reviews and incomplete membership are refused.

Canonical events retain versioned batch evidence. Original batch, release lines,
agreements and custody are unchanged. The ordinary batch detail offers review;
single-loan correction links redirect there. Shared selectors supply current
individual settlements and reviewed aggregate to detail/history/CSV; memos retain
batch/source provenance. No new model or migration. Mixed batches allow unsupported
native/opening loans only as unchanged members. Broader lifecycle amendments remain
pending. The batch/settlement/release regression run passed **87 tests in 193.101
seconds**, including paper batches, mixed native/admitted members, failed-member
rollback, stale reviews, duplicate/concurrent confirmation and restricted-role RLS.
Desktop/mobile/no-JavaScript review checks pass; corrected batch release PDF pages
were text-checked and visually inspected. Final correction/report/monitoring/document
integration passed **105 tests in 102.097 seconds**, including the simplified
closure form, current batch listing and subsequent reversal of an unchanged native
member. Migration consistency, 841 tracked/27 changed Python import boundaries
and 952 curated documentation links pass. All correction sources match the tested
snapshot: 1,343 hashes match; the concurrent unrelated change in
`tests/test_khata_guidance.py` adds a fixture refresh and is excluded from this
slice's hash check without altering that file. Evidence is under
`.tmp/unified-batch-correction-20261003/`; the isolated test database was removed.
No production/pilot data is changed.

## UR-05 initial archive admission (3 October)

The [archive admission service](../../apps/tenant_apps/loans/services/archive_admission.py)
reuses recorded-history validation, preview/replay and canonical posting for one
fully closed loan without renewals. It checks all source-family snapshots, normalized
known claims, existing Party mappings and actual settlement, binding the selected
snapshot and supporting-source statement to signed review. Unknown normalized facts
can be supplied; raw-source interpretation remains explicitly checked by staff.

Migration 0042 adds a nullable protected archive FK to the existing immutable/RLS
HistoricalLoanImport registry, plus an insert guard binding source, Workspace,
recorded origination and CLOSED loan. Its existing unique scoped source identity
protects complete-history/opening routes. Workspace locking serializes claims and
numbering. Only validated matching archive snapshots are exempted from the ordinary
number guard during this command; public manual entry retains the archive blocker.

Archive detail opens the ordinary form, archive list/detail display linked loans,
and ordinary loan detail links back to retained source and media. Source-only export
is unchanged; recorded-origin financial portability remains UR-06. No media copies,
backfilled approval or historical price records are created. Renewal-chain source
admission and conflicting-claim amendments remain out of scope.

The regression run passed **335 tests in 342.664 seconds**, covering archive readers,
opening/history import/export, existing paper admission and corrections, numbering,
reports, documents, monitoring and tenant registry. Final form/snapshot-link and
ordinary paper-entry checks passed **86 tests in 66.712 seconds**. Coverage includes
missing-fact supplementation, conflicting snapshots, source payment matching,
borrower mapping, later snapshot invalidation, cross-route duplicate rejection,
concurrency, rollback, exact retries and immutable Workspace/source bindings tested
under a restricted role. Original source export bytes and zero closed exposure are
asserted. Desktop/mobile/no-JavaScript reviews pass and were visually inspected.

Migration consistency, 841 tracked/10 changed Python import boundaries, 1,347 source
snapshot hashes and 1,029 curated documentation links pass. Evidence is under
`.tmp/unified-archive-admission-20261003/`; the isolated test database was removed.
Migration 0042 is not deployed. No production/pilot data or source archives were converted.


## UR-06 transaction coverage, monitoring and reminder checkpoint (3 October)

`LoanTransactionReview` stores append-only scoped coverage. Migration 0043 enables
forced RLS, non-null Workspace ownership, a protected loan/reviewer, request-key
uniqueness, an immutable database guard and registry coverage. The preview/confirm
service binds actor, Workspace, loan, date, result, reference, all financial event
fingerprints, state and the previous review. It locks the loan on confirmation and
handles exact retries. The supported interactive bound is 1,000 financial events.

Atomic timeline admission writes initial reviews for original and renewal members.
Previously admitted loans without a review remain unconfirmed until staff check
sources. Opening review starts at the opening checkpoint, not at invented original
receipts. Native loans remain system-recorded unless explicitly assigned a review.
Any later financial event/correction invalidates a paper confirmation. Active date
rollover becomes behind; closed coverage needs to reach final activity only.

Shared selectors label provisional debt/risk independently of valuation freshness.
Snapshot V4 freezes coverage and includes review changes in the refresh fingerprint.
Report and borrower statement HTML/CSV/XLSX/PDF expose status and cutoff; portfolio
and dashboard definitive totals are unavailable while paper coverage is incomplete.
Report PDF columns use compact wrapping for wide exports.

Supported paper/opening repayment and overdue reminders use the existing reviewed
risk-notice command, consent, templates and provider checks. Anniversary and opening
continuation interest are included. Migration 0044 binds paper notices to their
review with scoped insert checks and frozen content. Uniqueness is per source risk
event/channel/template/review; obsolete messages are retained and a new review can
support a new intent. Native intent uniqueness remains unchanged.

Notify's common dispatch boundary invokes the Loans-owned review guard, including
batch sends and direct retries. It locks the loan, reloads job state and verifies
current coverage/source/date/amount, active loan and alert, current assessment,
consent, contact and frozen rendered message/provider payload. Failed checks never
call the provider. A source admission or confirmation never queues notices.

Verification passed **358 regressions in 268.845 seconds**, **143 final checks
in 62.584 seconds** and two final canonical-collection checks in 0.963 seconds.
Tests exercise concurrent confirmation, exact retries, changed source
reviews, post-correction invalidation, opening scope, consent/message/source changes,
provider suppression, obsolete-intent replacement, immutable notice bindings and
restricted-role foreign-parent/row mutation rejection. Existing paper history,
corrections, archive admission, monitoring, reports, documents, opening restore and
Notify regressions pass. No external messages were sent.

Desktop/mobile/no-JavaScript checks pass against captured fictional HTTP responses.
Report and borrower statement PDFs were text-checked and visually inspected after
compact wide-table layout refinement. Migration consistency and Python import
boundary checks pass (841 tracked and 29 changed Python files); 1,356 final source
hashes and 955 curated documentation links match/pass. Local QA is under `.tmp/unified-monitoring-20261003`; the
isolated `test_unified_monitoring_20261003` database was removed. No pilot/production
writes or deployment occurred.
Remaining UR-06 work: recorded contract/variable-principal schedule documents,
versioned restorable recorded-origin portability and subsequent renewal/auction
recovery. Existing guards for these operations remain. The plan stays in progress.
