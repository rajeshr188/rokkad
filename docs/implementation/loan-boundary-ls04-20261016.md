---
status: verified-locally
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, architecture, verification]
related: [../adr/2026-10-16-independent-monitoring-inputs.md, ../plans/loan-boundary-simplification-20261016.md]
---

# LS-04: independent current monitoring inputs

This local slice follows the owner-approved order. It preserves existing LS-01/03
reads, LS-02 completed-payout review, committed undeployed corrections and the
deployed Party-merge overlay. Unrelated WhatsApp setup documentation is preserved.

## Implementation

- Add [monitoring_inputs.py](../../apps/tenant_apps/loans/selectors/monitoring_inputs.py)
  to resolve current valuation selection, compatibility precision and saved
  reference limit over existing immutable policy storage.
- Split the existing
  [collateral reader](../../apps/tenant_apps/loans/selectors/collateral_valuation.py)
  into independent current observation and the compatible combined debt/LTV read.
  Reuse one evidence-selection/calculation loop, including the LS-01 live cutoff
  and next-evidence deadline. No original approval is required to observe value.
- Preserve existing quantum, limits, arithmetic, freshness and custody semantics
  for supported loans. Explicit paise-default observation is possible without a
  saved policy; preserve-unknown method remains unavailable. Missing agreement
  evidence still limits servicing/full assessments rather than inventing debt.
- Keep reference headroom distinct from current-policy risk classification.
  An unknown reference limit stays unknown; it does not remove otherwise known
  exposure/value ratio or full-debt shortfall.
- V11 adds precision/reference provenance to derivative snapshots. Same-day V10
  projections become stale; ordinary workers can refresh them with matching code.
  No schema, business-setup or published loan-exchange contract changes.

## Verification

All **269 affected regression cases pass** in **285.082 seconds** in isolated local
`test_rokkad_ls04_20261016`. The initial 38-case development run found two incorrect
fixture expectations: Rates persists its normalized paise quote, so a supplied
3000.127 becomes 3000.13 before collateral calculation. The expectations now match
that retained source fact; the final full affected modules pass. The selections
overlap and are not a combined unique count.

Coverage includes all three current valuation methods, saved-method compatibility,
unavailable saved method, legacy observations without approval/policy, current
appraisal recording, whole-rupee precision normalization, distinct reference/risk
limits, financial failure independence, restricted-role isolation, stale V10
selection, temporal expiry, bronze, query reuse, paper books, four-origin parity,
financial/collateral corrections, issued-document preservation and portable/exact
recovery. No financial DML is produced by observation reads. Existing original
policy, approval, events and schedules are preserved.

Django system and migration checks pass, with no model changes. Import-boundary,
documentation-link and whitespace checks pass, including new source files. The
owner guide explains reference limits separately from attention thresholds.
The exact disposable test database is removed after testing and absence verified;
ordinary development/production data remain untouched.

No production inspection, policy change, deployment or live reassessment is
authorized or performed by this slice. LS-01 through LS-04 remain local and await
coordinated delivery with the separate pending corrections. V11 readers must be
present on web/worker/scheduled processes before new writes. LS-05 consistent
risk/evidence presentation is next; this slice does not claim a new partial-risk
dashboard or make incomplete financial history fully assessable.
