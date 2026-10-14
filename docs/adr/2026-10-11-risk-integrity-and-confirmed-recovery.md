---
status: accepted
owner: loans
updated: 2026-10-11
tags: [monitoring, risk, integrity, alerts]
---

# ADR: Financial integrity and confirmed risk recovery

MR-03 of the [combined monitoring plan](../plans/combined-loan-monitoring-20261011.md)
corrects healthy-looking assessments from inconsistent financial evidence and
false alert cures. It retains the canonical financial selectors, existing live
snapshot, immutable transition model and mutable staff work-item model.

## Financial boundary

Canonical exposure keeps integrity findings for diagnosis. Missing obligations on
an active unsettled loan or any unpaid position, over-allocation and negative debt cannot support a successful
risk assessment. Delinquency rejects inconsistent or negative obligation amounts;
the risk selector and snapshot writer reject exposure integrity findings.
Collateral may still have a known independently supported value, but its LTV is
unknown when the debt basis is inconsistent.

A cancelled zero-debt renewal successor legitimately has no active schedule.
Missing-schedule protection does not invalidate that neutral portable position.

A failed assessment uses existing ERROR status. Clear current monetary, DPD, LTV
and performance metrics rather than retaining earlier success values as this
attempt's result. Preserve diagnostic source provenance; financial findings are
labelled INCONSISTENT and performance UNKNOWN. This does not change recorded loan
balances, recognize interest, repair history or change frozen agreements.
Missing appraisal alone remains unknown collateral coverage on an otherwise
successful financial assessment, not a financial-integrity failure.

The saved projection contract becomes V7. Earlier V6 assessments are outdated by
existing read/worker predicates, without rewriting retained evidence. Release web
and workers from the same checkpoint and perform an ordinary today refresh.

## Recovery boundary

- A failed or outdated assessment cannot demonstrate recovery. Unknown DPD is
  not zero; unknown valuation is not below the LTV threshold.
- LTV bands are ordered. Breach becoming critical records escalation, not breach
  cure. Critical improving to breach records recovery from the critical threshold
  while keeping the breach work item open.
- Retain open alerts when the relevant condition cannot be evaluated. With known
  evidence, update an existing alert's severity for its own condition, retaining
  its original source-event relationship.
- Resolve only after a successful assessment establishes that the condition is
  absent. Link the applicable cure/recovery event. If a retained open alert has
  outlived its old projection flags, append ALERT_CONDITION_CLEARED using today's
  actual assessment before resolving it. Do not invent a retrospective cure for
  previously resolved legacy alerts.
- Successful repeat refreshes with unchanged risk state produce no new incident.
  A later recurrence with identical values must have a distinct transition and
  alert. Include the preceding persisted event ID in the transition trigger;
  the existing loan/snapshot locks and atomic write serialize the occurrence.
  Timestamps and random IDs are unnecessary for this distinction.

These are internal work items. No borrower communication, financial posting,
appraisal, quote, auction or custody action is triggered. Restricted runtime and
Workspace boundaries remain; database protection of risk references/events is
the separately selected MR-04 slice.

See [MR-03 implementation and tests](../implementation/risk-integrity-recovery-mr03.md).
