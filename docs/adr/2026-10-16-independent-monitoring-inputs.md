---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, valuation, compatibility]
related: [2026-10-12-current-monitoring-valuation-policy.md, 2026-10-16-supported-loan-financial-reads.md, ../plans/loan-boundary-simplification-20261016.md]
---

# Current monitoring inputs are separate from lending-decision evidence

The owner approved LS-04 after LS-03. Current monitoring policy already chooses
saved-method compatibility, calculated metal value, latest approved appraisal or
lower-of-both. The remaining collateral reader still required a frozen disbursal
policy even for an independently selected method.

## Decision

Use the ordinary read-only `selectors.monitoring_inputs` resolver over existing
storage. Its frozen result identifies the applicable current policy/method,
saved compatibility method, calculation precision, saved reference LTV limit
and their sources. It neither reads historical approvals nor reconstructs them.
Existing servicing agreement readers remain responsible for financial terms.

Split collateral observation from debt assessment. The supported
`get_pawn_loan_collateral_observation` reads current prices/appraisals, measurements,
correction applicability, freshness and custody. The existing combined valuation
reader uses that observation with supported financial exposure to calculate LTV.
Missing financial projection can block a complete assessment without preventing
the independent observation. Ordinary risk refresh still requires supported,
consistent financial inputs; an observation alone cannot create a CURRENT result.

Explicit current methods work without a saved disbursal policy. Preserving an
unknown saved method gives unavailable valuation with a specific blocker; never
silently substitute metal valuation. Missing policy/evidence and ineligible custody
retain their existing guards. Live cutoff and scheduled-evidence expiry remain.

## Numerical compatibility and distinct limits

Existing loans retain the normalized saved agreement currency quantum and current
ROUND_DOWN metal-value calculation. This compatibility default preserves their
numerical results and is labelled `SAVED_AGREEMENT`, independent of historical
approval proof. For a collateral observation with no saved agreement, use the
explicit monitoring paise default (`0.01`, `MONITORING_PAISE_DEFAULT`). It creates
no borrower interest terms or servicing capability. No new setup field is needed.
Appraisal amounts retain their existing meaning and are not rounded again.

Saved maximum LTV remains a separate reference: `SAVED_LENDING_REFERENCE` for a
native saved policy, `RECORDED_MONITORING_REFERENCE` for recorded-contract policy,
or unavailable. It supplies existing reference-limit status/headroom, not today's
risk attention thresholds. Never replace an unknown reference with the current
monitoring breach threshold. With known exposure/value but no reference, ratio
and full shortfall remain calculable; reference headroom is unknown and status is
`REFERENCE_LIMIT_UNAVAILABLE`. Current risk classification uses its existing
monitoring thresholds. Existing known-limit formulas and results are unchanged.

## Evidence and release

Snapshot V11 identifies these derived semantics and retains precision/reference
provenance separately from the current method/policy and original saved-method
label. V10 results require ordinary refresh. This does not rewrite financial
events, original quotes/approvals, saved agreements, custody, documents or book
reviews. No schema or published portable profile changes: the new result types
are per-calculation Python objects and risk snapshots remain derivative evidence.

Matching web, worker and scheduled readers must precede V11 writes during a
coordinated release. This local slice changes no production policy, refreshes no
live portfolio and creates no new loan class. See the
[verification record](../implementation/loan-boundary-ls04-20261016.md).
