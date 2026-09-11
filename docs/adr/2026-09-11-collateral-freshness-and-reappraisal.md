---
status: accepted
owner: loans
updated: 2026-09-11
tags: [loans, appraisal, monitoring, evidence]
---

# ADR: Monitoring freshness and active-loan reassessment

The owner approved increment 3 of the [Rates/appraisal review](../implementation/rates-appraisal-monitoring-review.md).
It extends the [appraisal authority decision](2026-08-13-pawn-collateral-appraisal-authority.md).

## Decision

- Use the effective Workspace/license monitoring policy's `rate_freshness_days`
  and `appraisal_freshness_days` for current collateral valuation and risk. Compare
  local calendar dates with inclusive limits: age 7 passes a limit of 7, age 8
  fails, and zero means same-day evidence. Preserve the configured values.
- Required evidence depends on the frozen loan valuation method. Calculated-only
  needs a current positive quote; appraisal-only needs a current approved appraisal;
  lower-of needs both. Optional stale evidence can be displayed without blocking
  a method that does not consume it. Missing/invalid/stale required evidence or
  an unresolved monitoring policy produces unknown coverage and LTV, never zero
  exposure or a healthy assessment. Display raw evidence values and dates separately
  from the eligible policy-selected value.
- Monitoring custody exclusions are respected within the supported held states
  (vault or funding lender). Excluded collateral cannot contribute to eligible value.
- These are monitoring policies. This increment does not impose their age limits
  on origination, repayment or release commands or change frozen loan terms.
  A separate origination-age contract would need explicit design and matching
  preflight/command validation; quote availability alone is not freshness approval.
- Reassessment is a current-time action for held collateral on an ACTIVE loan.
  Reuse `data.view`, `data.edit` and `loan.approve` authorization. No new role,
  automatic staff promotion, or license access scope is introduced. Readers may
  see history; only the authorized reviewer can record an approved new appraisal.
- Require a positive reviewed value, physical-inspection or external-report method,
  supporting reference and review reason. Evidence references are text identifiers,
  not public-storage links. Existing collateral photos remain accessible through
  their authorized routes. This increment adds no report-upload store.
- Append an immutable appraisal version linked to the previous version. Lock the
  loan then collateral, and compare the version the operator reviewed. Concurrent
  or duplicate submissions cannot silently overwrite or append competing reviews.
  Backdating and future dating are unavailable in this workflow. Subsequent
  corrections append another reviewed current-time version.
- Capture weight/purity, quote identity, quote effective time, price and reference
  metal estimate observed when recording. These describe reference context, not
  proof that the staff appraisal was calculated from that estimate. The human
  reviewed value remains independent. Preserve original draft, approval and
  disbursal evidence. As-of dates before reassessment continue selecting older evidence.
- PostgreSQL additionally rejects appraisal UPDATE/DELETE and cross-item or
  cross-Workspace predecessor links. Protect recorded actor identities from deletion.
  Existing legacy evidence keeps its values and possibly unknown authors.
- Mark this loan's saved risk snapshot stale in the same transaction as the new
  appraisal. On rollout, mark existing saved snapshots stale because the valuation
  rules changed. Do not send borrower messages, create financial events or trigger
  auctions from this action. The live loan detail reads current evidence immediately.

## Remaining work

Increment 4 now implements snapshot completeness, date-based expiry, bounded
repeated refresh and explicit policy supersession without mutating earlier periods.
See the [subsequent decision](2026-09-11-complete-loan-monitoring.md).
Origination-age requirements remain a separate policy design item.
