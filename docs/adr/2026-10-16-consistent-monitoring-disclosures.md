---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, evidence, presentation, capture]
related: [2026-10-16-independent-monitoring-inputs.md, 2026-10-05-servicing-operations-and-future-capture.md, ../plans/loan-boundary-simplification-20261016.md]
---

# Consistent monitoring disclosures and capture expectations

The owner's subsequent [represented-position decision](2026-10-16-represented-position-transaction-coverage.md)
supersedes the requirement for continuing book checks merely because of origin.
Keep separate evidence dimensions and optional exact capture declarations; a
supported recorded position does not require a separate book attestation.

The owner authorized LS-05 after LS-04. Loan detail can calculate live amounts
while its replaceable saved assessment remains unassessed/stale. Those statements
must identify their different basis. Portfolio and dashboard totals must agree
about which saved evidence is usable.

## Decision

Extend the existing evidence-quality selector and shared template. Display saved
assessment freshness, financial calculation support, valuation usability,
transaction coverage and future recording practice independently. Label live reads
explicitly; a GET never refreshes saved assessments or posts interest. Independent
LS-04 observations remain visible when full financial projection is unavailable.
Keep evidence disclosures inside the existing loan Overview region and collapsed
by default, with the principal status labels visible in their summary.

Separate advisory interpretation from severity. Describe identified measured
conditions, missing/inconsistent evidence, both, or unavailable risk. Original
classifier flags/severity, transitions, alerts, action hints and communication
authority are unchanged. Missing evidence does not become healthy and viewing an
unknown result does not clear an earlier breach. Stale saved advisory is a labelled
reference, never a current result. Failed-attempt financial diagnostics may still
show supported arithmetic while current totals remain unavailable.

Reuse immutable transaction reviews for recording practice. Ordinary Rokkad
capture is an explicit operating assumption, not a book attestation. Existing
paper/opening compatibility requirements mean continuing book checks until staff
review a different expectation. A signed complete review through today can select
Rokkad-only; later paper activity/correction can suspend it until another review.
The same choices apply regardless of entry origin. The review screen shows the
current expectation; a fresh review still defaults to paper/mixed unless staff
explicitly choose otherwise. No new capture table, setting or automatic transition.

## Shared usability rules

One selector module supplies guarded JSON monetary annotations and financial /
coverage predicates to both aggregate readers, plus matching per-loan checks.
Use current date/version/deadline status, finite bounded nonnegative money,
recorded-plus-projected reconciliation and explicit financial-integrity checks.
Coverage also needs usable exposure/shortfall, collateral value, LTV and no blockers.
An unavailable saved reference limit does not remove an otherwise known coverage
ratio/shortfall. It still supplies no invented headroom.

Keep four independent completeness indicators on the dashboard. Missing recording
basis is unknown, not silently complete. Partial monetary totals remain inspectable
with exclusions. Valuation and book-verification messages give different next
actions. Dashboard GET remains one aggregate query; portfolio GET uses saved
results and bounded-page book disclosures, never per-loan risk recalculation.
Operations' latest-current timestamp follows the same date/version/deadline test.

Current appraisal displayed in loan detail also respects the assessment instant,
version ordering and correction invalidation. Retained future/superseded evidence
is not removed from history.

No schema, signed-review, published portable profile or snapshot calculation
version change: this slice presents existing V11 facts and consistently excludes
unusable evidence. Financial formulas, agreements and servicing authority remain
unchanged. Delivery remains coordinated with earlier undeployed slices. See the
[implementation record](../implementation/loan-boundary-ls05-20261016.md).
