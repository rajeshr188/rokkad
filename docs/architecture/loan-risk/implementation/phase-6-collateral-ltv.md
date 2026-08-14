---
status: implemented
owner: loans
updated: 2026-08-11
tags: [loans, collateral, appraisal, ltv]
related: [roadmap.md, ../concepts/collateral-valuation.md, ../concepts/ltv-monitoring.md]
---

# Phase 6: Collateral valuation and LTV

Migration `0042` introduces immutable, versioned appraisal evidence with
effective time, review status, method, evidence reference, actor, and
supersession. Existing positive `latest_appraised_value` values are preserved
as explicitly labelled legacy evidence using each item's last known update
time; the compatibility field is not removed yet.

The workflow-neutral collateral selector resolves only evidence effective by
the requested date, includes eligible custody, computes intrinsic metal value
from net weight and purity, applies the frozen loan valuation method, and
returns item-level source identities and blockers. Missing evidence and
ineligible custody make aggregate valuation and LTV unknown rather than
healthy.

The pure LTV calculator keeps policy breach, headroom, and full economic
shortfall separate. It uses the product-aware LTV exposure basis from Phase 4
and identifies the frozen loan policy snapshot as the applicable compliance
profile. Release and renewal remain on their current selectors until parity
tests authorize a later cutover. Freshness thresholds remain a Phase 7
monitoring-policy interpretation.
