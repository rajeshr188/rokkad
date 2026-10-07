---
status: active
owner: project
updated: 2026-10-07
tags: [loans, origination, plan, release]
related: [loan-continuation-consolidation.md, ../adr/2026-10-07-shared-loan-entry-and-explicit-origination-correction.md]
---

# Loan origination completion and production acceptance

## Authorization and starting point

On 7 October the owner accepted the architecture analysis and all recommendations,
including the four remaining deployment items, and requested incremental delivery.
This plan covers implementation, verification and release preparation. Present the
concrete final release result before rollout; this planning checkpoint does not
post a correction into production.

The tested runtime candidate is ef3c82a5; e963b079 records its completed
production-copy verification. Full CI passes. The approved 6 October server-only
copy upgrades from Loans 0032 to 0063 with dependencies. All 183 original
non-metadata table projections preserve source values. Cold recovery matches all
202 candidate tables and 199 sequence positions. Restricted runtime/source reads
pass; all 6,707 ordinary active/closed loans are calculable under retained contracts.
These dated results do not certify source books, current monitoring or changed code.

The remaining deployment items are D01623's correction, actual source/staff
acceptance, actual media recovery and server capacity. Before LO-02, New loan dispatched
to direct and paper editors; the shared editor is now verified below. Existing SIMPLE workflow already combines owner
approval and disbursal atomically; EXTENDED supports separate actions.
See the [execution record](../implementation/loan-candidate-publication-20261006.md).

## Intended outcome and limits

One familiar routine editor and review capture customer, series, original date,
agreement terms, collateral items, per-item principal/rates and payout amounts.
Existing Workspace/licence/series defaults select current lending or completed
recording, with a per-loan override. Source channel remains provenance.

Standing terms are defaults; supported actual historical exceptions remain
available. Original valuation is optional evidence for completed recording,
independent of current monitoring. Prospective lending retains applicable licence,
quote-age, appraisal/LTV, photo and authority checks. SIMPLE exposes one final
confirmation while retaining authorization/payout evidence internally. EXTENDED
retains its permissions and separate responsibility. Saving a draft creates no debt.

Imports can keep batch preparation while feeding PawnLoan. Opening and terminal
positions preserve explicit history boundaries. Archives stay browsable without
automatic admission. No new loan model, generic form/formula engine, broad
authorization configurability, guessed receipts or automatic contract conversion.

## Delivery slices

### LO-00: starting behavior and early operational checks

**Status: baseline documented; fresh capacity/storage discovery performed;
distinct-object inventory and recovery/headroom remedies pending.**

Characterize direct draft/save, SIMPLE/EXTENDED confirmation, paper entry,
imports/openings and retained-native corrections before editing. Inspect current
disk/inodes, PostgreSQL/WAL growth, backup locations, staging isolation and actual
file/object storage coverage without printing credentials or downloading customer
artifacts. Measure room needed for builds, checkpoints, migrations and normal work;
yesterday's free-space figure is not current capacity.

Identify safe remedies and required photos/attachments/issued files, including
object versions and checksums. Remove only verified disposable rehearsal assets.
Broader cleanup or paid expansion needs a concrete proposal.

**Done when:** starting behavior is recorded and storage/capacity gaps have named
remedies. Run operational discovery early alongside local development; no further
heavy shared-host rehearsal until measured capacity is adequate.

### LO-01: explicit correction for a fully reversed native origin

**Status: correction implemented; financial/recovery/concurrency tests and
approved D01623 staging demonstration pass. Final 75 adjacent checks pass.
See the [execution note](../implementation/actual-paper-origination-correction-lo01.md).**

Add a reviewed correction for the demonstrated draft with all native payouts
reversed, no live origin and no incompatible dependent servicing/custody graph.
Review actual agreement, original date, item amounts, deductions and proceeds.
Retain loan/number/item identities and old approvals, payouts, reversals, photos
and issued documents. Establish one unreversed supported recorded origin with
explicit correction reason/actor. Do not fabricate a historical approval or
automatically fall back after retained-native validation fails.

Inspect origin guards, schedule uniqueness, native reissue, readers and portability
before choosing the smallest coherent change using existing financial writers.
Broader correction shapes require their own supported review.

Generated D01623 fixtures use confirmed facts: 24 September 2026; 2,100 principal
at 4%; one month advance 84; document charge 10; proceeds 2,006; tenure three
months. No later payment/closure was confirmed on 6 October; verify the latest
position before any subsequent real-source action.

**Done when:** conservation, old-evidence retention, chronology, stale-review
rejection, duplicate/concurrent retries, reversal/dependencies, servicing,
monitoring inputs and restricted-role isolation tests pass. Recovery and supported
export retain correction evidence; narrower export limits are explicit. Demonstrate
the approved staging case correction without production financial writes.

### LO-02: one shared routine loan editor

**Status: complete locally; 168 adjacent and 62 final focused Django checks,
14 JavaScript checks and desktop/mobile Chromium interactions pass.
See the [implementation note](../implementation/shared-routine-loan-editor-lo02.md).**

Use ordinary Django forms/formsets and shared template sections for customer,
series, dates, agreement, collateral rows and economics. Replace routine two-editor
dispatch with shared presentation, retaining purpose-specific validation/commands.
Specialized backlog/import preparation remains separate.

- Sum total principal from actual per-item principals. Shared add/remove item
  controls and labels work for both purposes.
- Standing tenure/rate/advance/document-charge terms supply defaults. Actual
  older exceptions remain available without repeated routine agreement questions.
- Current lending shows applicable valuation and lending guidance. Completed
  entry records agreed amounts without retrospective current-price approval.
- Original number/date and recording time remain distinct; source mappings survive.
- Series/licence/Workspace defaults apply predictably. Purpose switching retains
  common facts, item membership and photos, with no silent loss.
- Known receipts/closure remain optional additional history; routine staff need not
  discover an inferred paper renewal chain before recording a loan.

**Done when:** both purposes visibly share the routine editor and item controls.
HTTP/UI verification covers defaults/exceptions, switching, direct entry, customer
creation, numbering and invalid-form retries. Openings/archives are not forced
through an original payout workflow.

### LO-03: shared review and final confirmation

**Status: complete locally; shared review and atomic SIMPLE confirmation verified.**

Routine SIMPLE owners now use Review loan then Confirm payout; Save draft and
EXTENDED remain. Paper/saved/correction review shares the agreement/amounts layout
and Record completed payout action. New signed owner reviews bind actor/date and
complete economic/photo policy, retaining exact retry proof in immutable approval
JSON. Issued v1 and recorded review contracts remain accepted. Direct/paper PDFs,
exact proof/media recovery, adjacent regressions and desktop/mobile keyboard/layout
checks pass. See the [delivery note](../implementation/shared-origination-review-lo03.md)
and [Status](../STATUS.md) for check counts and release boundaries.

Show one review layout for date, agreement, item principal/rates, advance, charges
and proceeds. Final actions distinguish Confirm payout and Record completed payout.
Use existing atomic SIMPLE approval/disbursal, preserving EXTENDED actions.
The current combined service is owner-only; do not silently extend owner powers
to staff. Source verification is distinct from prospective lending authorization.

Saved-draft completed entry and LO-01 correction use the familiar review with
retained-history information where needed. Preserve issued signed reviews/retries
and safe legacy-route compatibility. Do not retire a writer without compatible
readers for its accepted evidence.

**Done when:** one review/final confirmation completes routine SIMPLE lending;
completed entry needs no historical digital quote; stale inputs, changed quotes
or policies, foreign reviews and repeated submits cannot create wrong/repeated
debt. Printed documents show truthful dates and origination basis.

### LO-04: servicing, monitoring and legacy compatibility

**Status: implemented and locally verified, 7 October.**

Actual four-path admission/servicing and settlement matrices pass except two new
test-clock errors, now corrected and passing in the final seven-check regression
run. The 112-check broad run passed 110; the 84-check affected run passed 82 and
reproduced only those same fixture errors. No remaining failed case is unresolved.
Verification includes mixed item rates, actual paper allocation on every origin,
captured rounding, repayment/retry/reversal, full release, supported renewal/auction,
monitoring, checkpoint advances, portable evidence and explicit legacy correction.

Fixed the accepted sparse paper split/opening replay mismatch while retaining exact
item and monetary conservation checks. Interest inventory now separates dated
continuation holds from contract compatibility and exposes captured rounding/timing
and actual collection versus retained policy quantum. Native reversed-charge and
over-covered future-advance limitations remain explicitly held and documented;
there is no automatic old-contract adoption or invented history. See the
[LO-04 implementation and disposition](../implementation/origination-servicing-compatibility-lo04.md).

Exercise actual direct, recorded, complete-history and opening admissions with
equivalent supported flexible monthly agreements. Compare receipts, anniversary
boundaries, captured-policy rounding, reductions, advances, full closure, supported
renewal/auction and correction. Opening continuation starts at its checkpoint;
earlier history is not invented. Fix demonstrated source-tag-only restrictions
where action prerequisites are actually equivalent.

Paper receipts follow the owner's interest-first convention with actual item
principal splits. Outstanding fees require their actual component. Paper
closure/new issuance does not require an invented predecessor link; current linked
renewal retains settlement, funding and custody evidence. Do not invent physical
cash or custody movements.

Verify recorded debt, collection amount, forecast exposure, current valuation,
assessment freshness and book coverage independently of original valuation.
Unknown evidence stays visible; notices/recovery retain their guards. Explain how
staff refresh valuation or review books using existing controls.

Inventory older contract differences and their disposition. Correct demonstrated
financial discrepancies explicitly where supported, without silently repricing
posted amounts. Unknown history and arbitrary source conventions are not promised
by universal presentation.

**Done when:** supported operations agree where facts agree, source-only
restrictions are resolved, and actual remaining legacy differences have a tested,
explicit disposition. No second finance engine or automatic conversion.

### LO-05: real source and staff acceptance

**Status: owner accepted RA00500/C07557/06716 book comparisons on 7 October;
corrected-paper display and shared workflow screen review pending.**

The owner is the reviewer and confirmed post-25-September JCL/JSK originations
as direct. After receiving the comparison sheet, the owner confirmed that the
RA00500, C07557 and 06716 comparisons match and are correct and satisfactory.
The dated acceptance record retains the project-chat declaration; no in-app book
review is posted by this release acceptance. Read-only restricted-runtime checks compare RA00500, corrected staging
D01623, JCL C07557 and JSK 06716 (direct payout followed by paper closure).
Authorized GETs, document projections, continuation and current monitoring reads
pass. Source rows/customer HTML remain server-only. The bounded current-source
overlay is not an exact final build, browser/media recovery or staff attestation.
No real partial-repayment event exists in the selected snapshot cohort; generated
LO-04 coverage supplements the available real closure. See the
[comparison sheet and pending acceptance record](../implementation/loan-source-staff-acceptance-lo05.md).

Use RA00500 for opening acceptance and corrected D01623 for paper payout.
Select a real JCL/JSK direct loan and real receipt/closure examples where available.
Record actual reviewer/date/source/result; generated scenarios supplement testing
but cannot attest books. Do not repeat questions about confirmed D01623 terms.

Walk the shared interface through defaults, items, deductions, printing, payment
split, closure/custody and monitoring quality. Disposition cohorts: supported
actions, held debt-sensitive actions and required reviews/prices.

**Done when:** representative comparisons and staff acceptance are recorded.
Essential business mismatches return to the responsible implementation slice.
Release does not require every valuation/book flag to be green or all archives
reconstructed; it requires truthful limits and action-specific enforcement.

### LO-06: final candidate, actual media recovery and capacity

**Status: discovery begins in LO-00; final rehearsal follows code freeze.**

Commit/publish the complete candidate and run full CI/appropriate changed-area
checks. Build one exact artifact with runtime contracts for web/workers.
Earlier green CI/recovery cannot certify new code.

Recheck live migration baseline; capture a fresh consistent server-only checkpoint
with actual media/object versions and document links. Upgrade/restore only in the
approved private isolated environment with owner migrations, restricted runtime,
disabled providers and no public listener. Sensitive artifacts stay at the approved
destination, outside local OneDrive; identify any new destination before use.

Compare original projections, all restored tables/sequences and individual media
hashes. Open representative real files and verify issued bytes. Cold recover with
the matching reader, runtime/source/servicing reads and archive-performance checks.
Document off-host recovery separately: same-host recovery cannot prove resilience
to loss of that host.

Measure free space/operating headroom throughout. Confirm retention and recovery
runbook; do not globally prune unrelated assets.

**Done when:** exact candidate CI, fresh database/media recovery, runtime isolation,
source integrity and measured capacity pass, with essential gaps explicitly resolved.

### LO-07: concrete rollout review and production release

**Status: pending LO-01 through LO-06.**

Present target, commit/image, migration range, acceptance, checkpoints, interruption
and compatible recovery procedure. Execute only when requirements and deployment
authorization are satisfied. Do not silently post D01623's correction into
production as part of a software deployment.

Owner settings run migrations; restricted roles run web/workers. Verify direct,
paper/imported reads, representative origination/servicing, document access,
monitoring quality and jobs. Smoke checks must not create unintended advances or
customer messages. Watch errors, retries, performance and disk growth.

**Done when:** reviewed production candidate runs, smoke checks pass and recovery
remains usable. Any production correction is its own explicit reviewed financial
action. Do not downgrade to an incompatible reader after new evidence is written.

## Working order and reporting

Start LO-00 discovery and LO-01 implementation, then LO-02, LO-03 and LO-04.
Prepare real examples and media/capacity evidence early. Finish LO-05/LO-06 against
the final candidate, then LO-07. Workstreams do not imply additional-agent delegation.

Update this plan and STATUS after each slice with changed behavior, tests, limits
and next step. Use appropriate targeted tests during development; full CI/heavy
recovery belongs at integration unless a changed financial/schema boundary needs
an earlier rehearsal. Do not repeat approval for authorized implementation.
Source attestations come from the business. Important new financial correction
details require an ADR and posting/reversal/isolation tests.
