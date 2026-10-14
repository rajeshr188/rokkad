---
status: investigation
owner: loans
updated: 2026-10-11
tags: [dashboard, monitoring, evidence, production]
---

# JCL Financial health: unavailable amounts and incomplete coverage

The owner reports unavailable metrics on the production JCL dashboard. Read-only
diagnostics ran on 11 October through the existing production web image, its
restricted NOSUPERUSER/NOBYPASSRLS database role, explicit Workspace context and
PostgreSQL READ ONLY transactions with a 12-second statement timeout. No records,
assessments, services, migrations or deployments were changed.

## Observed position

At the last check, JCL has 2,631 active loans: no current saved assessments, 52
stale assessments, 2,579 unassessed and no failed assessments. One new active loan
appeared between the two probes; these counts are a live checkpoint.

Of the 52 saved assessments, 50 are dated 8 October under the current V6 contract
and two are dated 25 September under V3. Even a saved status of CURRENT is not
current for this dashboard unless its date is today and its contract is V6.
All 52 last saved assessments report MISSING_APPRAISAL. The 50 V6 assessments
have SUPPORTED financial calculation and UNCONFIRMED transaction coverage; those
are old results, not a fresh calculation for the unassessed population.

Frozen valuation methods on active loans are LATEST_APPRAISAL (2,377) and
LOWER_OF_CALCULATED_AND_APPRAISAL (254). Across 2,650 active collateral items,
257 have an approved appraisal effective by today; 256 have a positive legacy
latest-appraised-value field. That field alone is not an approved appraisal.
These counts do not establish why each historical valuation method was selected.

No running container's configured command invokes reassess_pawn_loans. Inspected
Rokkad systemd units have no loan-risk reassessment service. The six active timers
serve platform mail (four), database backups and storage inventory; platform-mail
health is not loan health. This inspection does not establish every possible
external scheduler or nested process, but finds no dedicated recurring loan worker.

## Meaning

The dashboard reads saved assessments, not live per-loan risk calculations. It
does not refresh or post interest on GET. With zero usable current assessments,
financial and coverage sums are NULL and render Unavailable. The shortfall count
is zero across zero evaluated loans, not proof that no loans are undercovered.
Closed loans, including imported closed positions, do not enter these totals.

Assessment freshness, financial calculation support, transaction verification
and valuation evidence are independent. Usable subset sums remain visible with
explicit counts; provisional book verification makes whole-portfolio completeness
false without suppressing individual calculated balances or monitoring. An
accepted opening position does not need reconstructed pre-cutover receipts for
current monitoring. Missing current valuation must not be repaired by inventing
historical appraisals or making an old value appear newly assessed.

## Recommended follow-up

1. Review imported loans' current monitoring basis. If the business intends
   weight/purity/current-metal-price monitoring, assess an explicit authorized
   current monitoring choice independently of frozen original terms. The current
   selector takes valuation method from the frozen loan policy; the monitoring
   policy controls freshness/custody/thresholds but has no method override.
2. Configure the existing bounded recurring reassessment command with restricted
   runtime credentials and explicit Workspace IDs. Manual batch refresh processes
   at most 50 candidates, so one refresh does not populate a whole portfolio.
3. Review calculation failures and current valuation blockers after refresh;
   supply genuine current quotes/appraisals as appropriate. Book confirmation
   starts at accepted opening coverage, not at a fictional complete lifetime.
4. Clarify dashboard labels for assessed coverage, valuation coverage and book
   verification; show known totals and distinguish zero from not evaluated.

This is investigation and recommendation, not authorization to change live policy
or start a worker. PC-01 through PC-06 remain locally verified and undeployed;
commit/release preparation is a separate next step. See
[dashboard definitions](../flows/business-dashboard.md),
[loan monitoring](../flows/loan-health-monitoring.md) and
[PC-06](portable-graphs-pc06.md).
