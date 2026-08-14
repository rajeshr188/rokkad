---
status: accepted
owner: project
updated: 2026-08-13
tags: [loans, pawn-loan, collateral, appraisal, risk]
related:
  - 2026-08-09-loans-effective-dated-calculation-policy.md
  - 2026-08-11-loans-product-obligation-and-risk-architecture.md
---

# ADR: Pawn Collateral Appraisal Authority

## Context

Draft collateral stores `latest_appraised_value` so an operator can capture and
correct proposed economics. Later architecture added immutable
`CollateralAppraisal` evidence, but the first immutable row was created only at
disbursal and active-loan selectors could fall back to the mutable draft field.
Release readiness also read that draft field directly. This left two possible
authorities for post-approval valuation.

## Decision

1. `PawnCollateralItem.latest_appraised_value` is proposed draft input only. It
   remains editable while its PawnLoan is `DRAFT` and supports draft preview,
   validation, splitting, and approval preparation.
2. Approval freezes each populated proposal as an immutable approved
   `CollateralAppraisal`, economically effective from the PawnLoan contract
   date. `created_at` separately records when approval occurred. The approval
   payload records the appraisal identity.
3. Reopening returns the contract to the correction boundary. Reapproval appends
   a new appraisal version that supersedes the prior version; history is never
   edited or deleted.
4. Disbursal consumes approval evidence and does not originate appraisal rows.
5. Post-approval valuation, release, exposure, LTV, risk monitoring, and reporting
   use the latest approved appraisal effective on the requested as-of date. They
   never fall back to `PawnCollateralItem.latest_appraised_value`.
6. Missing approved evidence is an explicit valuation blocker, not a compatibility
   fallback.

## Consequences

- Draft usability remains unchanged.
- Approval becomes the legal/economic appraisal acceptance boundary.
- Risk and release results have an immutable appraisal identity and reproducible
  as-of behavior.
- The pre-production migration rebuild can remove the historical appraisal
  backfill because no production rows require compatibility promotion.
- A future post-disbursal reappraisal workflow must append a reviewed appraisal
  version through its own command; it must not edit the collateral draft field.
