---
status: proposed
owner: loans
updated: 2026-09-12
tags: [loans, rates, origination, evidence]
---

# New-loan rate freshness review

The owner selected **same-day quotes required at approval** on 2026-09-12.
This applies only to valuation methods that consume Rates. The remaining behavior
below is a proposal for the next implementation increment, not an implemented
gate or an approved exception workflow. Existing monitoring limits remain separate.
See the [Rates/appraisal review](rates-appraisal-monitoring-review.md) and
[monitoring freshness decision](../adr/2026-09-11-collateral-freshness-and-reappraisal.md).

## Current behavior and gaps

| Boundary | Reviewed behavior | Required follow-up |
| --- | --- | --- |
| Quote selection | The Rates facade selects the latest applicable Workspace quote, using effective time, entry time and ID. Draft economics and approval request the loan date. | Availability is enforced, but there is no origination-age limit. A date lookup includes all applicable times on that date. |
| Form guidance | Setup and HTMX preflight display quote price, identity, source, effective date and age relative to the loan date. | Guidance must distinguish available from fresh enough, and match final command validation. |
| Approval | Economics are resolved again, LTV and allocations validated, and immutable calculated/selected values recorded. | The approval payload does not retain the selected market quote ID, effective time, source snapshot or exact per-gram price. The interest-rate policy ID is different evidence. |
| Appraisal | Approval appends the accepted draft appraisal with the loan date as its effective date. | An accepted draft value is not proof of a new physical inspection. This review does not impose a new appraisal-inspection interval. |
| Simple workflow | Signed review and approval/disbursal run atomically with existing owner/action checks. The review expires after one hour and checks input/economic changes. | Token age is not quote age. Include quote identity and freshness decisions in reviewed evidence, including equal-price corrections. |
| Extended workflow | Disbursal rehydrates frozen approval economics and does not fetch a newer market quote. | An approval can wait across days. A new quote must not silently change approved terms. |
| Renewal | Renewal resolves successor economics and calls approval, then records its own successor activation evidence. | Cover renewal preview and confirmation; enforcement solely in the ordinary disbursal command would miss this path. |

Reviewed entry points: `rates/facade.py`, `loans/selectors/rate_readiness.py`,
`loans/web/rate_readiness.py`, and Loans services `pawn_economics.py`,
`pawn_lifecycle.py`, `pawn_disbursal.py`, `loan_workflow.py`, `pawn_renewals.py`.

## Recommended behavior

1. For ordinary current-day origination, require a positive same-day quote for
   each consumed metal. Use the application's configured local date at the action,
   and exclude quotes effective after the action time. Calculated-only needs its
   quote; lower-of needs its quote and accepted appraisal; appraisal-only keeps
   its existing appraisal rules and does not acquire a Rates requirement.
2. Allow saving an incomplete draft. Show missing/stale evidence beside the
   relevant metal, with the effective date and an authorized Rates link. Preserve
   form entries and selected photos through the existing another-tab/check-again
   flow. Enforce the same rule in approval commands, even without JavaScript.
3. Freeze selected quote ID, Workspace, metal, unit/currency/purity, exact buying
   price, effective/recorded times, source snapshot and freshness decision in
   approval evidence. Freeze the applied rule and evaluation time as well. Preserve
   existing calculated values; never reconstruct a historical quote from today's
   latest price or rewrite completed approval/disbursal evidence.
4. For a delayed disbursal, recommend checking the frozen quote is still same-day
   and has not been corrected/withdrawn or replaced by a newer applicable quote.
   If it fails, require a fresh review and approval. Reuse the existing
   reasoned return-to-draft action and append a new approval version. Staff without
   the required permissions should see guidance to an authorized reviewer.
   This disbursal rule is proposed; the owner's answer selected approval age only.
5. Start with a blocking rule and an actionable recovery path. Do not add an
   override permission or infer one from owner status. An exceptional override,
   if subsequently requested, needs its own explicit permission and immutable
   actor/reason/evidence design. Do not automatically add configuration fields
   or copy the monitoring policy's age limits into origination.

For example, a draft approved on Monday with Monday's gold quote can complete
the simple workflow immediately. Under the proposed delayed-disbursal rule,
disbursing it on Tuesday requires Tuesday's quote and a new approval; Monday's
approval remains in history. A same-day price change before confirmation also
requires reviewing the new evidence.

## Date and compatibility decisions before enforcement

Backdated loan dates are currently used for policy and quote resolution. The
owner's same-day-at-approval choice must not silently substitute today's quote
into historical loan-date economics. Recommended first scope: ordinary current-day
origination, with an explicit actionable rejection of historical/future-dated
approval until a separate backdated-entry contract is chosen. This date restriction
is a proposal and must be reviewed before changing existing behavior.

Existing approved-but-undisbursed loans can lack quote provenance. Recommend
requiring return to draft and reapproval under the new rule; do not guess their
quote identity. Already active/closed loans and authorized idempotent disbursal
replays retain their original evidence and behavior. Their monitoring, repayments
and releases remain governed by the existing contracts.

## Smallest coherent next increment

Confirm the proposed delayed-disbursal and historical-date behavior, record the
accepted contract in an ADR, then implement quote provenance together with one
shared origination eligibility calculation. Connect it to preflight, approval,
simple review, renewal review/confirmation and disbursal as applicable. Preserve
existing action permissions, explicit Workspace context and RLS.

Validation must cover same-day/stale/missing/future-effective quotes, local midnight,
method-specific requirements, gold/silver combinations, review-to-command quote
changes and corrections, unauthorized callers, foreign Workspace quotes, delayed
disbursal, old approvals, renewal atomic rollback and completed-action replay.
Existing frozen amounts and repayment/reversal results must remain unchanged.

Large-scale monitoring capacity remains shelved in
[FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).
