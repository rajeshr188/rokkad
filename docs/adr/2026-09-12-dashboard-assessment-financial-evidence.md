---
status: accepted
owner: loans
updated: 2026-09-12
tags: [dashboard, monitoring, evidence]
---

# ADR: Dashboard financial evidence in saved assessments

The owner approved financial-health cards after the first business-dashboard
increment. Existing snapshots contain economic exposure and collateral coverage,
but cannot identify unfinalized interest separately. Subtracting today's recorded
balance from an earlier assessment would mix evidence from different times.

## Decision

Extend existing snapshot JSON provenance with `financial.projected_interest`,
`financial.recorded_total_due` and `financial.integrity_findings`, copied directly
from the canonical exposure selector during assessment. No new monetary formula,
table or migration is introduced. The current projection contract becomes
`LOAN_RISK_SNAPSHOT_V3`.

Older snapshots become stale through existing current-contract read predicates
and are selected by the existing bounded refresh job. Their saved evidence is
not rewritten by a dashboard GET. A refresh updates derivative assessments, not
loan events, interest finalizations or frozen terms. Deploy web and workers from
the same checkpoint; an older worker cannot produce the required V3 evidence.

The dashboard adds one aggregate over ACTIVE loans and saved assessments in the
explicit Workspace. It never invokes per-loan assessment calculations. Existing
`data.view` permission gates the cards; the Loan health administration link also
requires existing `workspace.settings.manage` permission.

Financial totals require current, usable evidence on every active loan. Missing,
malformed or inconsistent amounts and integrity findings make whole-portfolio
financial totals unavailable. Unknown collateral coverage does not by itself
invalidate usable financial evidence. Coverage totals have their own completeness
check. Empty portfolios show zero.

Sum each loan's full collateral shortfall, preserving its existing exposure basis:
maturity payoff for bullet/flexible loans, economic exposure for amortizing loans.
Surplus collateral on another loan cannot cancel a shortfall. With incomplete
coverage, show only the explicitly labelled known affected-loan count and withhold
whole-portfolio monetary coverage totals. Eligible collateral value is not labelled
raw market value. Assessment freshness and evidence sufficiency remain distinct.

## Rollout

Existing active assessments need one ordinary refresh to populate the breakdown.
The authorized Loan health action or bounded worker can perform it. An assessment
refresh does not repair stale quotes, appraisals or integrity findings; those need
their existing correction workflows. No worker is implicitly started by this
change. Closed loans remain outside refresh and live portfolio totals.

The one-hour launch-capacity target remains unproven and large-scale testing stays
shelved under [FW-004](../plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).
See [dashboard definitions](../flows/business-dashboard.md) and
[Status](../STATUS.md) for validation evidence.
