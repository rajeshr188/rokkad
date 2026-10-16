---
status: verified-locally
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, evidence, verification]
related: [../plans/loan-boundary-simplification-20261016.md, ../adr/2026-10-16-monitoring-evidence-instant.md]
---

# LS-01: Explicit assessment evidence time

## Scope

The owner approved the origination/monitoring review in its recommended order.
This first slice characterizes existing financial/admission boundaries and fixes
live evidence timing before changing origination orchestration. The shared
financial/collateral correction source was committed in 7681aac0 while the
deployed Party-merge overlay remains separate. Preserve those changes.

No production queries, data/policy changes, migrations, Git publication or
deployment accompany this slice. All fixtures are fictional and local.

## Implementation

- Capture one aware instant at live refresh start and pass it into valuation.
  Select only rates/appraisals effective at or before it. An exact-boundary value
  is eligible. Preserve local-date age, monthly interest and DPD semantics.
- Dated read-only valuation defaults to local day-end restatement. Explicit
  cutoffs must match the local business date; future live cutoffs are refused.
- Extend the Rates facade with optional scheduled-evidence metadata. Normal
  callers retain their existing query behavior. Scheduled lookup uses the same
  tenant/metal/currency/purity and corrected/withdrawn quote eligibility scope.
- Retain the earliest upcoming required quote or approved appraisal in current
  valuation output. An irrelevant source cannot expire a method's assessment.
- Save evidence/next-effective instants in risk provenance. Shared object and SQL
  currentness checks expire a result at its deadline. The existing bounded worker
  then selects it without another data write. Communication readiness uses the
  existing shared currentness check, as do dashboard/portfolio/detail readers.
- Before returning from atomic persistence, reject a crossed date/deadline so
  the projection and any transitions/alert changes roll back together.
- Bump only the derived snapshot contract to V10. Old results are retained and
  become stale; no agreement, original decision, monetary event or custody changes.

Keep prepared financial inputs, source fingerprints, current monitoring choices,
existing worker locks, forced RLS and immutable financial evidence. The extra
scheduled-appraisal query is bounded once per valuation, not once per item;
optional scheduled quote lookup is once per distinct required metal. Existing
multi-item query-bound tests account for this additional evidence read.

## Verification

The initial characterization selected a later-today appraisal during a morning
assessment, reproducing the static review finding.

The wider **193-case selection ran in 672.900 seconds** with one failure: a
prepared-read parity comparison now included two legitimately different capture
timestamps. Both reads now share the same explicit cutoff. The other 192 cases
passed, including four-origin anniversary/rounding/continuation, shared servicing,
current valuation choices, bronze, collateral/agreement corrections, source
invalidation, risk recovery, communication readiness and restricted-role/upgrade
checks. This run preceded the final placement of the deadline/date guard after
transition persistence; the final affected selection below tests that placement.

The final **58-case affected selection passes in 30.791 seconds**:

- Eight new timing cases, including rollback both after calculation and after
  transition writes, live exact-boundary evidence, invalid explicit cutoffs,
  scheduled quote/appraisal activation, SQL/object/dashboard agreement and worker
  reselection without another source write.
- Full monitoring-completeness, efficiency, live-date, orchestration and pure risk
  modules, including the corrected cutoff-parity case and financial no-writes.
- The Rates quote-evidence module, retaining correction/withdrawal, effective-time,
  scope, actor and immutable evidence behavior.
- Completed payout retaining genuine approval/current monitoring without original
  valuation, plus minimal closed/terminal position admission without invented
  financial history.

The 193- and 58-case selections overlap and are not a unique combined count.
Import boundaries pass for 1,226 Python files; Django checks, migration/model
consistency (no changes), 1,475 local documentation links and whitespace pass.

Use `--settings django_project.settings.test` and the dedicated
`DB_MIGRATION_NAME=rokkad_ls01_20261016`, producing only
`test_rokkad_ls01_20261016`. Tests run serially; none use development rows or live
worker commands.
The dedicated test database was removed after verification; its absence was
independently checked through the PostgreSQL catalogue.

## Release requirements

No schema migration is introduced. Release matching web, monitoring and scheduled
communication readers before V10 refresh writes; older writers must not replace
newer projections. Existing current rows fail the new version check and require
ordinary reassessment. There is no artificial mass update of old evidence.

LS-02 remains next: completed-payout review by purpose with retained original
approval and explicit evidence review. This slice does not change that interface.
