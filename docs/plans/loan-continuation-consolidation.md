---
status: active
owner: project
updated: 2026-10-06
tags: [loans, plan, continuation]
---

# Loan continuation consolidation

This follows LD-01–08. The owner's 6 October brief authorizes a plan and the
smallest safe first implementation slice, not production deployment or conversion.
The pasted brief is authoritative; its shared ChatGPT link was unavailable.

## Delivery order

1. **LC-01: real admission characterization and continuation reads — locally complete.** Exercise
   direct origination, completed-paper admission, history/4 import and reviewed
   opening/4 admission with equivalent agreements and positions. Consolidate the
   unposted-interest facts used by repayment preview and exposure/risk, preserving
   profile-specific writers and legacy forecast semantics. Compare anniversary,
   rounding, advance, principal reductions, recorded/collection balances and risk
   inputs; prove read-only behavior, cutover bounds and once-only recognition.
2. **LC-02: evidence presentation and forecast continuation — locally complete.** Consume shared
   continuation in maturity forecasts/delinquency where semantically appropriate.
   Show independent assessment, transaction coverage, valuation and calculation
   support in dashboard, portfolio, reports, exports and previews. Audit ordinary
   direct loans' mixed-paper capture assumptions as well as imported loans.
3. **LC-03: action orchestration — locally complete.** Unify release, renewal and auction preparation
   around shared facts. Preserve each writer's source documents, allocations,
   custody, idempotency, dependent reversals, authorization and forced RLS.
   Keep historical renewal recording distinct from renew-now eligibility.
4. **LC-04: admission presentation — locally complete.** One routine Record completed payout action;
   retain adapters/redirects for valid retained approvals and reversed-origin
   corrections. Characterize both before retiring the older earlier-payout route.
   Never overwrite frozen approval or create a second financial origin.
5. **LC-05: bounded evidence extensions — locally complete.** Explicit terminal-position closed
   admission for verified agreement/closure with incomplete receipts (no invented
   receipts or reversals of nonexistent settlements); multi-item opening paper
   receipts with supplied splits; multi-item archive admission; explicit fee
   allocation; delegated import preparation/reconciliation; same-day cutover
   precision. Each extension needs its own supported evidence version and tests.
6. **LC-06: quote-age workflow — locally complete.** Propose the latest applicable quote, display
   source and age, and apply an owner-selected maximum age. Keep prospective
   approval, monitoring and retrospective facts separate. The owner selected
   **seven days by default, configurable by the Workspace owner** on 6 October.
   This is an LC-06 implementation decision, not a change to quote checks in LC-02.
7. **LC-07: release acceptance — technical preparation verified locally; production acceptance pending.** Inventory production cohorts and unsupported
   contracts, obtain real source examples/staff acceptance, rehearse recovery and
   deployment gates. Synthetic tests are not source-book or production acceptance.

## Required continuation facts

Frozen agreement and original anchor; actual effective date and financial-history
boundary; current item principal and current-period bases; recorded principal,
recognized unpaid interest and fees; eligible unposted charges, paid/advance
coverage and descriptive once-only recognition plan; allocation semantics;
transaction coverage/evidence quality; explicit unknown/unsupported outcomes.
Recorded debt, collection debt and risk exposure are distinct uses of these facts.

LC-01 deliberately exposes existing calculation evidence rather than introducing
a generic formula framework, another finance engine, configurable strategy system
or new database tables. Full orchestration and presentation remain later slices.

## Validation and delivery

LC-01 now centralizes collection/exposure unposted-interest selection through the
read-only continuation selector. Its descriptive adapter evidence stays distinct
from posting authority. Native period, recorded cumulative and opening catch-up
writers, allocation and reversal semantics are unchanged. Legacy daily projection
moved without changing its algorithm (AST comparison passes). No new tables.

Real admission tests use ordinary draft update/approval/disbursal and repayment;
reviewed paper preview/admission with actual item splits; staged history/4
preview/commit/replay; and reviewed opening/4 preview/commit with explicit current
bases/advance coverage. DML executes under the fixture's restricted non-bypass RLS
role. **20 tests pass** for single/multiple items and paise/whole-rupee policies,
both against the consolidated read consumers (53.102s) and restored HEAD consumers
(52.121s). A two-item example charges 100.52 in paise or 100 in whole rupees, rather
than rounding a combined total; after the supplied reduction the next charge is
98.51 or 98. The covered anniversary has zero additional interest. Opening history
starts at verified cutover and does not acquire invented earlier receipts.

The **419-test affected run** passes 418 cases (356.157s). Its one document fixture
failure reproduces with HEAD readers and is repaired by supplying the fake event's
required `payload`; the complete **9-test document module passes** (0.150s).
All selected checks are verified across those runs, without claiming a single clean
419-test rerun. The fixed-date native fixture also freezes its clock consistently.
Django system checks and migration drift checks pass; changed Python files parse
and whitespace checks pass. Logs/labels remain ignored under
`.tmp/continuation-20261006/`.

## LC-02 implementation and acceptance

Implementation and selected verification are complete locally. Native shared monthly,
recorded anniversary and shared-policy opening bullet/flexible remaining obligations
consume the continuation reader with a distinct maturity horizon and reporting-date
knowledge limit. Opening forecasts now reflect later known principal reductions,
while source schedules and prior profile meanings remain immutable. Forecast
results explicitly reject use as a present collection balance. Opening balance
and repaid counters describe the checkpoint and post-cutover history; they do not
claim reconstructed original payments.

Evidence disclosure covers repayment previews, ordinary details, Loan health,
dashboard, recorded-position reports/Party statements and CSV/XLSX/PDF exports.
Current assessment, transaction coverage, eligible valuation and calculation support
are independent. V6 snapshots include financial-history/principal basis; V5 needs
refresh. Unsupported or inconsistent financial results do not become known zero.
Ordinary capture is labelled as an assumption; retained earlier-payout evidence now
requires book review even with a native contract. Known missing paper activity
cannot be overridden by origin. No notice/recovery prerequisite is relaxed.

Acceptance: actual four-path admissions must agree after later principal reduction,
in single/multiple-item and paise/whole-rupee agreements; historical forecasts must
ignore future payments; reads must not post; dates/maturity/cutover and advance must
remain intact. Integration must demonstrate current calculation with stale valuation
and provisional books, stale saved assessment with a supported payment preview,
native missing-paper coverage, export column/date consistency and restricted scope.
Affected financial, admission, risk, report and send-time guard regressions must pass.

Validation: 28 real-admission checks pass (75.488s), including eight new forecast
cases; four real quality integrations pass (8.455s). The 482-test affected run
passes 480 (408.385s), with two test expectations corrected for precise wording
and missing overdue evidence. All 39 final focused checks pass (15.119s), including
both cases and final presentation/export changes. Selected checks are verified
across runs, not one clean 482-test rerun. Three further HTTP checks pass (4.269s)
after the sidebar distinguishes opening principal from original payout amounts.
Django checks, no migration drift,
27 Python parses, nine template compilations and whitespace checks pass. Evidence
is private under `.tmp/lc02-20261006/`. No publication or production action.

## LC-03 implementation and acceptance

Common settlement preparation now consumes validated continuation for full
release, renewal performed now and current auction completion. Modern native
simple/full-month contracts automatically recognize completed periods in the
authorized atomic command; legacy/non-full-month prerequisites remain. Specialized
source writers retain their recognition identities, paired catch-up/reversal,
custody, allocation, permissions, exact retries and successor approval. Completed
paper renewal remains a factual recording workflow.

Opening collections use immutable allocation capacity rather than the LC-02
dynamic forecast. Shared monthly native renewal/auction cap scheduled allocation
while retaining all actual interest collected after maturity. Policy/2 auction cash
uses paise independently of interest rounding. Opening renewal catch-up reversal
preserves exact source amount spelling. No financial origin or schedule is rewritten.

All **14 new real-admission settlement tests** pass in the final run, covering
single/multiple items, paise/whole-rupee policies, anniversary quotes and actual
release, renew-now and auction commands. The **541-test affected regression**
passes 539 (649.203s), with two PostgreSQL recovery-test deadlocks. Both recovery
tests pass on isolated rerun. All **29 final targeted checks** pass (77.446s),
including those recovery cases, all 14 settlement tests and partial-month policy
checks with a new explicit-finalization compatibility case. Selected checks pass
across runs; this is not a claim of one clean 541-test rerun. Django checks,
no migration drift, 34 changed/new Python parses and whitespace checks pass.
Private evidence is under `.tmp/lc03-20261006/`; see the
[delivery record](../implementation/loan-settlement-continuation.md).

## LC-04 implementation and acceptance

One routine completed-payout action preserves genuine retained approvals and
reversed-origin correction adapters. Old GET links redirect; already issued POST
reviews and same-form retries keep their authorized commands. General unpaid
draft admission does not acquire a historical quote requirement. Retained-native
evidence/authorization failures never fall back into that general writer. Recorded
and opening graphs cannot use native reissue. No origin or evidence is converted.

New paper entry optionally maps existing source licence evidence with Workspace,
series/licence and original-date checks. Review freezes the mapping; unknown
validity stays unknown. Existing drafts keep their mapping and request shape.
Missing mapping still permits recording but blocks bounded history export.

All **257 affected regression tests pass** (293.327s) and all **18 final LC-04
checks pass** (6.514s), including three additional boundaries after the broad run.
Django checks, no migration drift, six template compilations, 41 Python parses and
whitespace checks pass. Private evidence is under `.tmp/lc04-20261006/`; see the
[delivery record](../implementation/completed-payout-presentation-lc04.md).

## LC-05 implementation and acceptance

All six extensions are implemented locally through versioned evidence: supplied
multi-item opening paper splits, actual fee components, multi-item archive
reconciliation, delegated preparation, precisely timed checkpoints and verified
terminal closed positions. These reuse ordinary loans, source documents and
allocation lines. Original profiles are unchanged; no existing loan is upgraded.

Verified terminal admission creates an ordinary CLOSED loan with its original
agreement and sole zero checkpoint at closure. Earlier receipts/payout totals and
pre-closure financial positions remain unavailable; custody is known only when
source evidence establishes it. It cannot gain financial transactions or reopen
through reversal of a settlement never recorded. Archives remain immutable.

Owner review/commit remains mandatory for prepared imports. Staff can stage and
save scoped mappings but cannot approve debt or create customer/catalog records.
Changes invalidate earlier reviews. Actual opening item splits and fee amounts
are checked on writing, replay and portability. Review/5 carries a real timestamp;
older date-only reviews remain end-of-day. Current same-day settlements and paper
receipts use evidenced action times. Date-only paper closures/renewals remain
after-cutover operations. Opening export/4 preserves new evidence and timed closure
restoration; servicing bundles preserve terminal evidence and unknown custody.

All **475 affected regressions pass** (388.162s), followed by **37 final checks**
(27.232s). The earlier recovery deadlock passes in isolation and the complete
final run. Django checks, no migration drift, nine template compilations, 81
Python parses, runtime inventories and whitespace checks pass. Both migrations
were verified in disposable QA only. See the
[delivery record](../implementation/bounded-loan-evidence-lc05.md) and
[contracts](../contracts/bounded-loan-evidence-lc05.md). Private evidence is under
`.tmp/lc05-20261006/`.

**Next: LC-07**, release acceptance. LC-06 implementation and verification are documented below.

No production deployment, bulk conversion or source-book acceptance is included.
The quote-age business decision is implemented locally in LC-06.
Production cohorts, full original history and actual valuation
equality remain unverified. LC-07 retains its scope above.

## LC-06 implementation and acceptance

The latest applicable quote is eligible within a Workspace owner's configured
age, default seven inclusive local calendar days; zero is same-day. The existing
Loans setup > Loan entry page and forced-RLS settings record are reused. Owner
writes are scoped, audited and subject to business-write availability. Photo
administrators retain their existing authority, independently of this owner rule.

New approvals freeze the v2 quote-age rule, applied limit and each quote's age.
Source identity stays immutable. Signed simple, renewal and updated-valuation
reviews bind the limit; pending payout checks enforce current eligibility,
configuration and identity. Legacy v1 approvals retain same-day meaning. Completed
retries and historical recording retain original evidence/dates. Independent
monitoring policy, paper/imported agreement terms and financial history remain
unchanged. Khata prospective consumers bind the same limit in their new reviews.

The **143-test affected run passes** (59.478s). The broader **480-test run passes
477** (431.644s), with one recovery deadlock and two obsolete test fixtures. All
**52 follow-up checks pass** (33.575s), including those three cases, all 23 new
quote-age tests, two new Khata tests and exact non-default setting recovery.
All **25 final boundary/presentation checks pass** (8.314s). Selected checks pass
across runs; this is not one clean 480-test rerun. Django checks, no migration
drift, six LC-06 template compilations, 104 Python parses, JSON inventories and
whitespace checks pass. Migration 0063 was applied only to disposable QA.
See [delivery](../implementation/prospective-quote-age-lc06.md) and
[decision](../adr/2026-10-06-configurable-prospective-quote-age.md).

LC-01–06 are locally complete. LC-07 has verified local recovery/deployment gates;
real source/staff acceptance and production cohort/recovery verification remain. No production
deployment, automatic archive conversion or source-book acceptance is claimed.

## LC-07 technical preparation and remaining acceptance

The dated release inventory reuses existing continuation/evidence/eligibility and
archive-directory readers. PostgreSQL enforces a repeatable-read/read-only snapshot;
attempted DML is rejected and context/transaction cleanup is verified. Calculation,
book coverage, saved assessment freshness and valuation eligibility remain separate.
Unsupported positions have no invented balances; draft/approved states, terminal
closed positions and latest unadmitted source identities retain their boundaries.
Common action prerequisites do not authorize an operation or replace command checks.

All **225 release-focused regressions pass** (252.483s), followed by **87 final
fixture/tenancy/inventory regressions** (64.917s). The shared tenancy clock helper removes
four existing test imports of billing internals, and statutory auction tests use a
real approval/payout. Application-boundary checks pass without a guard exception.

The full candidate image passes restricted-runtime startup, schema drift and
rejection of owner/pending-migration startup. Full pre-migration and migrated cold
restores match every one of **202 public tables and nine media files**. The fictional
local source remains unchanged. Migration changes apply only to disposable targets.

**Remaining:** current production inventory and unsupported-case disposition;
actual source-book/staff acceptance; committed/CI release identity and a current
production backup/off-device recovery check before separately authorized deployment.
The local 15-loan legacy cohort and generated source examples do not fulfill those
acceptance gates. No automatic contract adoption or archive conversion is proposed.
See [delivery](../implementation/loan-release-acceptance-lc07.md) and
[operator guide](../flows/loan-continuation-release-acceptance.md).
