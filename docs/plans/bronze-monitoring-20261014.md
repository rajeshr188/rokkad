---
status: active
owner: project
updated: 2026-10-14
tags: [monitoring, rates, evidence, rollout]
related: [../adr/2026-10-14-bronze-reference-price-valuation.md]
---

# Bronze support and JCL current monitoring

The owner approved current calculated metal monitoring and bronze price support.
Do the work in this order:

1. **Complete locally:** extend existing bronze models through quote lookup, entry guidance, dated
   eligibility, daily confirmation and paper collateral entry. Make standing
   bronze interest optional and explicit; preserve gold/silver behavior.
2. **Complete locally:** verify real loan lifecycle, source retention, current/live-saved parity,
   freshness, corrections/invalidation, scope guards and package compatibility.
3. Prepare a coordinated matching web/monitoring release with V9 and the existing
   business-package v3 follow-up. Keep unrelated pending work out of the release.
   Rehearse prior-reader recovery and verify backup/capacity before switching.
4. Record the owner's real positive bronze buying/selling quote, source and
   effective time through ordinary authorized Rates. No fictional production quote.
5. Amend JCL's current Workspace monitoring policy to CALCULATED_METAL_VALUE,
   retaining its other thresholds/freshness/custody rules and predecessor evidence.
   Shared licences mean this replaces current lower-of monitoring too. Then allow
   the bounded worker to reassess and check aggregate remaining blockers.
6. Review actual residual evidence problems and supported paper positions. Do not
   blanket-confirm books or invent repayments, historical appraisals or purity.

Implementation and regression evidence will be recorded in the
[delivery note](../implementation/bronze-monitoring-20261014.md).
Actual quote facts, controlled production delivery, policy amendment and source
book checks are distinct from local implementation. No individual-record export
is required or authorized by the earlier aggregate diagnosis.

The owner's supplied bronze reference is INR 3,000/kg = INR 3/g. The selling
price/source question remains pending; do not silently use the same figure for
selling or invent a market source. Local verification and exact test-database
cleanup are complete, with overlapping run counts documented in the delivery note.
