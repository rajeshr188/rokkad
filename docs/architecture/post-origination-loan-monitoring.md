---
status: active
owner: loans
updated: 2026-10-16
tags: [architecture, monitoring, pawn-loan, risk, evidence]
related: [../flows/loan-health-monitoring.md, ../domain/pawn-loan-financial-read-models.md]
---

# Post-origination loan risk monitoring

The [16 October hardening candidate](../implementation/loans-architecture-hardening-20261016.md)
completes policy lifecycle/review, readiness, staff work views and optional cohort
assurance without changing the canonical financial calculator or posting boundary.
Combined source uses snapshot V13 and package/setup profile 4. Its Loans 0089 and
both independent 0090 guard migrations join at 0091; data_portability 0030 carries
the compatible profile. Compatible web, worker and scheduled readers must be
released together. These local acceptance results are not production deployment
evidence. Worker assignment visibility and bounded measurements are delivered;
indexed scheduling, reuse and pool changes remain gated by representative evidence.

Developer reference for implemented ordinary PawnLoan monitoring, including
MR-02–07. The owner reference is the in-app **Loan monitoring guide**, linked from
Loan health, Operations console and dashboard Financial health after its release.
Its content is [risk_guide.html](../../templates/loans/setup/risk_guide.html).
Operational instructions remain in [Loan health](../flows/loan-health-monitoring.md).
For worker timing, failure/restart behaviour, daily expiry and proposed scaling,
see the [worker lifecycle reference](monitoring-worker-lifecycle-and-scaling.md).
The [16 October JCL coverage review](../implementation/jcl-monitoring-coverage-review-20261016.md)
distinguishes completed refresh from missing valuation and book evidence.

## Purpose and boundaries

LS-05 uses a shared evidence disclosure for live loan calculations and saved
portfolio results. Saved freshness is separate from live financial support;
advisory cause separates measured conditions from missing evidence without changing
severity. Recording practice comes from ordinary capture assumptions or existing
reviewed choices, independently of origination label. Dashboard and Loan health
share [aggregate usability checks](../../apps/tenant_apps/loans/selectors/assessment_evidence.py).
Missing recording basis is unknown; partial totals disclose their exclusions.
See the [decision](../adr/2026-10-16-consistent-monitoring-disclosures.md).

Origination establishes an actual agreement and supported starting position.
Monitoring repeatedly checks debt, contractual repayment performance, eligible
collateral cover and the evidence supporting those conclusions. Direct, recorded
paper and imported active loans share this pipeline; continuation adapters supply
different starting evidence, not separate paper risk engines. Earlier unavailable
history remains unavailable. Accepted closed positions remain browsable outside
the ACTIVE portfolio. Khata uses its own cover/overdue rules, not this worker.

Monitoring writes derivative snapshots, immutable risk transitions and internal
alerts. It does not originate debt, finalize interest, rewrite frozen terms,
fabricate quotes/appraisals, initiate recovery or send borrower messages.
Servicing/communication keep their independent authority and posting boundaries.

## Agreement, monitoring policy and source evidence

- Frozen agreement/product determines repayment structure, interest, actual terms
  and saved maximum LTV. Later setup changes do not rewrite existing debt.
- Effective-dated monitoring policy determines current valuation, maturity/DPD/LTV
  attention thresholds, freshness and eligible custody. Resolution prefers a
  complete licence override, otherwise the Workspace default; it is not a
  field-by-field merge. Amendments retain predecessor, author and reason.
- Actual events/allocations, schedules, collateral/custody, Rates quotes, approved
  appraisals and book review supply evidence. Configuration cannot replace facts.

Preserving a saved valuation method does not freeze its original rupee value.
For paper/imported loans, an admitted monitoring method need not prove original
lending valuation. Changing current monitoring must not rewrite original economics.

LS-04's [monitoring input reader](../../apps/tenant_apps/loans/selectors/monitoring_inputs.py)
separates current choices from saved compatibility references. Independent current
collateral observation requires no original approval or saved disbursal policy.
The combined LTV/risk read still needs supported financial exposure. Existing
precision is preserved from the saved agreement; observation without one uses an
explicit paise default, not invented borrower terms. Saved reference maximum LTV
determines reference headroom, while current policy thresholds classify risk.
Unknown reference limits supply no headroom or limit-status claim; they do not
erase a known exposure/value ratio or full shortfall. Preserving an unknown saved
method leaves valuation unavailable until an explicit current method is chosen.
See the [decision](../adr/2026-10-16-independent-monitoring-inputs.md).

## Pipeline and source map

```mermaid
flowchart TD
    A[Active scoped loan and reporting date] --> B[Continuation and obligations]
    B --> C[Exposure and delinquency]
    A --> D[Independent current collateral observation]
    C --> L[LTV from supported debt and current value]
    D --> L
    L --> E[Risk classification and book coverage]
    E --> F[Source-checked current snapshot]
    F --> G[Immutable transitions and staff alerts]
    F --> H[Loan health and Financial health summaries]
```

| Responsibility | Source / entry point |
|---|---|
| Supported per-calculation financial inputs and normalized opening obligations/grace | [financial_inputs.py](../../apps/tenant_apps/loans/selectors/financial_inputs.py), `get_pawn_loan_financial_inputs` |
| Resolve contract, recorded position and recognition preview | [continuation.py](../../apps/tenant_apps/loans/selectors/continuation.py), `resolve_loan_continuation` |
| Fold schedule/dated allocations | [obligation_state.py](../../apps/tenant_apps/loans/selectors/obligation_state.py), `calculate_obligation_state_as_of` |
| Financial exposure and integrity findings | [exposure.py](../../apps/tenant_apps/loans/selectors/exposure.py), `get_pawn_loan_exposure` |
| Contractual DPD/grace | [delinquency selector](../../apps/tenant_apps/loans/selectors/delinquency.py), [calculator](../../apps/tenant_apps/loans/domain/delinquency.py) |
| Effective monitoring policy | [monitoring_policy.py](../../apps/tenant_apps/loans/selectors/monitoring_policy.py) |
| Current method, compatibility precision and saved reference limit | [monitoring_inputs.py](../../apps/tenant_apps/loans/selectors/monitoring_inputs.py) |
| Per-item value and evidence | [collateral_valuation.py](../../apps/tenant_apps/loans/selectors/collateral_valuation.py) |
| LTV/headroom/shortfall | [ltv.py](../../apps/tenant_apps/loans/domain/ltv.py) |
| Classification/action hint | [risk selector](../../apps/tenant_apps/loans/selectors/risk.py), [domain](../../apps/tenant_apps/loans/domain/risk.py) |
| Represented-position coverage and optional book assurance | [transaction_coverage.py](../../apps/tenant_apps/loans/selectors/transaction_coverage.py), [transaction_completeness.py](../../apps/tenant_apps/loans/selectors/transaction_completeness.py) |
| Today-only persistence | [risk_snapshots.py](../../apps/tenant_apps/loans/services/risk_snapshots.py) |
| Transitions and incidents | [risk_transitions.py](../../apps/tenant_apps/loans/domain/risk_transitions.py), [risk_alerts.py](../../apps/tenant_apps/loans/services/risk_alerts.py) |
| Bounded worker | [risk_jobs.py](../../apps/tenant_apps/loans/services/risk_jobs.py) |
| Source invalidation | [risk_signals.py](../../apps/tenant_apps/loans/risk_signals.py) |
| Projection summaries | [risk_portfolio.py](../../apps/tenant_apps/loans/selectors/risk_portfolio.py), [dashboard_health.py](../../apps/tenant_apps/loans/selectors/dashboard_health.py) |

MR-07 introduced per-calculation financial reuse; LS-03 promotes it into the
supported loan/date/Workspace-checked interface within a composed refresh.
Represented-position coverage reuses those financial inputs after financial/valuation
reads, retaining optional book assurance separately without another financial read.
Appraisals use one per-loan query; each metal quote is read once per call.
Standalone selectors still work independently. There is no cross-request cache
or financial-result change. See [MR-07](../implementation/monitoring-efficiency-mr07.md).

## Amounts, due dates and performance

With recorded outstanding principal P, interest I, fees F and additional eligible
unrecorded interest through the reporting date U:

| Metric | Implemented meaning |
|---|---|
| Recorded total due | P + I + F; a recorded balance, not schedule-derived due-now |
| Economic exposure | P + I + F + U |
| Estimated unfinalized interest | U, distinct from I and from collected cash/realized profit |
| Due now | Unpaid contractual obligations due on/before the reporting date |
| Overdue | Unpaid contractual obligations due before that date |
| Maturity payoff | Remaining scheduled principal/interest plus recorded outstanding fees |
| Coverage exposure | Maturity payoff for single-payment bullet, periodic-interest bullet and flexible partial-payment; economic exposure for amortizing structures |
| DPD | Days since the oldest unpaid overdue due date; zero if none |
| Days to maturity | Contractual maturity minus reporting date |

Dated receipts/reversals and allocations determine remaining obligations. A
partial payment does not reset DPD while the oldest obligation remains unpaid.
Interest eligibility, recognition and payment due dates are separate. The shared
anniversary contract (5 April/upfront first month → next charge on 6 May) does not
by itself create monthly instalment obligations on flexible loans.

Integrity checks reject negative debt/projections, unsettled positions without
supported schedules, principal mismatch and inconsistent recorded component totals.
ERROR clears unsafe current money/DPD/LTV and retains diagnostics. Book failure
after supported exposure must not mislabel the financial calculation unsupported.

**Grace integration limit:** frozen product/opening terms supply grace.
`calculate_delinquency` returns `escalation_eligible` when the date is after oldest
due date plus grace, without shifting DPD. Current classification/alert code does
not consume it as a suppression gate. Do not promise grace-delayed alerts.

## Valuation, freshness and custody

The selector reads the latest APPROVED appraisal effective on/before the captured
assessment instant, ordered by effective time then version. Rates comes through
its existing facade using the same instant. Today's live valuation excludes
later-today evidence; dated read-only reports default to local day-end restatement.
Evidence age still uses inclusive local calendar days. V10 also retains the next
required quote/appraisal effective time so saved results expire when scheduled
evidence becomes applicable. See the [decision](../adr/2026-10-16-monitoring-evidence-instant.md).
This implementation awaits coordinated release; the prior production contract
remains unchanged until that release.

Calculated value supports GOLD, SILVER and BRONZE. The buying quote is INR per
gram at a 100% reference grade: pure gold/silver or the bronze material itself.
No copper/alloy conversion is inferred. The existing `24k` quote key remains
compatible. Normalize the saved currency quantum before quantizing: stored
0.0100 means paise, not four decimal places. V9 corrects that current valuation
precision and adds bronze price invalidation/source checks without rewriting
original lending or financial evidence. See the
[bronze decision](../adr/2026-10-14-bronze-reference-price-valuation.md).

| Method | Required evidence and value |
|---|---|
| CALCULATED_METAL_VALUE | Buying rate × net weight × purity / 100, quantized using saved currency quantum and ROUND_DOWN; usable fresh rate |
| LATEST_APPRAISAL | Latest applicable approved value, with usable fresh appraisal |
| LOWER_OF_CALCULATED_AND_APPRAISAL | Per-item minimum; both sources must be usable |
| ORIGINAL_AGREEMENT policy choice | Resolve the saved method, then apply current evidence/age/custody checks |

Age limits are inclusive local calendar days. Missing, invalid, future,
unconfigured and stale evidence remain distinguishable. Model defaults are seven
days for quotes and 90 for appraisals, not a claim about every live policy.
Appraisal-only does not require an unused metal quote; metal-only does not require
an unused appraisal; lower-of requires both.

Custody must be IN_VAULT or WITH_FUNDING_LENDER and policy-permitted. A required
item blocker makes full loan valuation unknown. Do not sum known items and present
that subset as complete collateral coverage. Refresh does not inspect jewellery
or renew evidence dates. Selected value is not guaranteed net sale proceeds.

With exposure E, eligible value V and the loan's saved maximum LTV A:

```text
LTV = E / V
policy headroom = V × A − E
full shortfall = max(E − V, 0)
```

Missing/nonpositive V or blockers leave metrics unknown. LTV-domain status compares
with saved A; classifier thresholds are independent current monitoring settings.
Negative headroom can precede full shortfall and a configured monitoring breach.

Fictional E=₹10,000/A=80% example (not recommended limits):

| V | LTV | Headroom | Full shortfall |
|---:|---:|---:|---:|
| ₹14,000 | 71.4% | ₹1,200 | ₹0 |
| ₹12,000 | 83.3% | −₹400 | ₹0 |
| ₹11,000 | 90.9% | −₹1,200 | ₹0 |
| ₹9,000 | 111.1% | −₹2,800 | ₹1,000 |

## Classification, transition evidence and staff alerts

Performance uses configured Watch/Substandard thresholds (model defaults 1/90
DPD). Maturity warning defaults to 30 days. LTV warning uses `>= warning`, breach
uses `> breach`, critical uses `>= critical`. Required blockers/missing LTV produce
VALUATION_UNKNOWN. A recorded-balance versus contractual-overdue interpretation
difference produces OVERDUE_INTERPRETATION_VARIANCE; investigate, do not invent
payments or automatically call it inconsistent debt.

| Overall severity | Conditions |
|---|---|
| CRITICAL | LTV_CRITICAL or DPD_SUBSTANDARD |
| HIGH | LTV_BREACH, VALUATION_UNKNOWN, OVERDUE_INTERPRETATION_VARIANCE or PAST_MATURITY |
| MEDIUM | LTV_WARNING, PAYMENT_OVERDUE or MATURITY_APPROACHING |
| LOW | None of those flags |

Action hints are IMMEDIATE_REVIEW, PRIORITY_REVIEW, MONITOR or NONE. Explicitly
incomplete books can supply RECONCILE_PAPER_RECORDS without pretending debt or
valuation failed. Performance, severity, freshness and book completeness must not
be collapsed into one healthy boolean. Internal alert severity is kind-specific
and can differ from overall severity. Not every flag creates a separate alert:
current kinds are DPD worsening, LTV breach, maturity and assessment failure.

Snapshots are mutable current projections. Immutable `LoanRiskEvent` records
material transitions, not a full assessment on every refresh. Alerts retain the
original source, update continuing severity and resolve with confirming evidence.
Worsening is not cure; unknown/failed evidence cannot clear a known financial or
coverage risk. Later identical incidents remain distinct without duplicating
unchanged refreshes. Database guards protect anchors, matching Workspace/loan
references and append-only events. See [recovery](../implementation/risk-integrity-recovery-mr03.md)
and [evidence protection](../implementation/risk-evidence-guards-mr04.md).

Borrower notices are separate authorized commands with readiness, source binding
and preview/confirmation. Monitoring itself performs no borrower communication.

## Four evidence dimensions and summaries

| Dimension | Meaning |
|---|---|
| Freshness | CURRENT status, today's local date, current snapshot contract (V13) and no reached scheduled-evidence deadline |
| Financial support | Consistent continuation/obligation evidence supports amounts |
| Transaction coverage | Accepted origination/checkpoint and consistent recorded activity support the represented position, without explicitly unresolved activity |
| Valuation coverage | Required per-item evidence and custody support value/LTV |

The owner's later treatment decision supersedes compulsory paper/opening book
reviews. Direct, paper and imported origins use the same represented-position
coverage contract. Missing, aged or changed positive book assurance is informational;
an explicit unresolved-activity report remains provisional and unsupported financial
evidence remains unavailable. A supported opening does not fabricate earlier receipts.
Optional ROKKAD_ONLY declarations and book checks retain their original exact
meanings and immutable rows. Published portable profiles still carry their original
book-coverage claims, not a newly asserted lifetime cash history. See the
[decision](../adr/2026-10-16-represented-position-transaction-coverage.md).

Loan health sums the usable current financial subset and discloses provisional
and unavailable counts. Its monetary `totals_complete` does not require every
collateral valuation known. Dashboard health separates financial and coverage
subsets. Financial completeness requires all loans financially usable and no
known unresolved activity; coverage completeness also requires every loan's cover usable.
Unknown is not zero. Subset sums/counts must not claim whole-portfolio certainty.
Sum per-loan shortfalls: surplus on another loan must never offset them.

New supported-position borrower intents use an explicit versioned position claim
without inventing a review. The compatibility JSON key is `transaction_review`;
`contract=recorded-position-coverage/1`, `review_id=null` identifies the new meaning.
Genuinely current review-bound intents and already issued intents retain their old
contract. New intents freeze exact financial source/date/amount; dispatch remains
loan-locked and checks consent, current risk, contact, provider and confirmed content.
Migration 0090 preserves prior uniqueness while adding position-specific identity
and immutable new content; downgrade refuses retained position intents. Auction
readiness uses supported positions but retains statutory/custody/settlement gates.
Neither monitoring nor an auction without book assurance manufactures a book review.

## Refresh, concurrency and isolation

Live persistence accepts today's local date only, including final success/error
checks. The service validates Workspace/access/ACTIVE state, fingerprints sources,
calculates, locks/rechecks loan and snapshot, and verifies sources again before
saving. Changed evidence is rejected for retry. Standalone calculation is followed
by atomic persistence; the worker wraps it in its per-loan Workspace transaction.

Source-save invalidation runs inside the source transaction under active RLS.
Loan/schedule/allocation/item/appraisal changes invalidate the loan; applicable
rate/policy changes invalidate their scope. New-day and scheduled-evidence
staleness are derived even without an update. Raw SQL/QuerySet.update does not emit post_save; supported
mutation paths must preserve explicit invalidation.

LS-06 measures these guards locally before changing them. A separate-lock,
CURRENT-only scope update does not demonstrate a useful improvement at 2,500
synthetic rows and is removed; simply skipping stale rows would miss a worker
about to publish CURRENT. Keep existing transactional updates and worker claims.
The measured policy/worker deadlock is addressed by FOR NO KEY UPDATE on the
policy setup Workspace lock, in both service and database guard (migration 0086).
This retains writer serialization while allowing KEY SHARE checks for appended
risk evidence. Joining 0087 changes no data. No financial contract, V11 or source
scope changes. See the [decision](../adr/2026-10-16-measured-monitoring-invalidation.md)
and [bounded measurements](../implementation/loan-boundary-ls06-20261016.md).

The worker requires explicit positive Workspace IDs and restricted runtime. Each
candidate is claimed/rechecked with skip-locked row locking in a separate committed
Workspace transaction. Closure, a competing worker or a lock can cause a skip.
One failure does not roll back earlier loans or stop other explicit Workspaces.
Current pilot uses ten candidates/Workspace turn, five-second busy/300-second idle
pauses and 0.35 CPU/512 MiB. These are not launch-scale acceptance or immediate
refresh guarantees. Already-current loans are not all recalculated every five
minutes. SIGTERM unwinds the current transaction and stops cleanly.

Dashboard GET reads projections and does not refresh/post charges. App guide GET
is static owner/admin documentation and must not call calculation/refresh/posting
services. Existing Loans setup permission and explicit Workspace routing apply.
Dated selectors restate available knowledge; they do not certify what staff knew
or saw in a historical assessment.

## Verification and limitations

Affected changes need checks for entry-origin parity; anniversary/advance/rounding;
oldest-obligation partial payments; valuation methods/date/custody/multi-item
blockers; threshold equality; inconsistent refusal; unknown non-cure, severity and
real recovery; repeated incidents; today-only writes; source changes/concurrent
closure; restricted RLS/unset/foreign context; immutable events and completeness.
Use [test settings](../implementation/testing-and-migrations.md) and release gates
in [MR-06](../implementation/monitoring-release-mr06.md), [MR-07](../implementation/monitoring-efficiency-mr07.md)
and the [dashboard release](../implementation/dashboard-performance-release-20261012.md).

Current monitoring cannot detect unentered paper transactions, inspect jewellery,
independently verify purity, predict defaults or guarantee proceeds. It is not a
full collections case-management, regulatory NPA/provisioning or automatic recovery
system. Grace suppression is not integrated. Full captured assessment history
requires a demonstrated need; transitions do not provide that history.
Launch-scale acceptance remains [FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).
Explicit monitoring choices are now retained by the locally implemented
setup/business-package version 3, with older profiles unchanged. Production
portability delivery and destination acceptance remain separate; see the
[14 October follow-up](../implementation/monitoring-portability-followup-20261014.md).

Maintain this reference together with the owner guide, operator flow and code.
Documentation adds no architecture decision, schema, policy or financial behavior.
