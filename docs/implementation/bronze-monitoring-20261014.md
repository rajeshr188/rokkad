---
status: verified-local
owner: project
updated: 2026-10-14
tags: [rates, monitoring, bronze, validation]
related: [../plans/bronze-monitoring-20261014.md, ../adr/2026-10-14-bronze-reference-price-valuation.md]
---

# Bronze monitoring delivery

The existing BRONZE collateral and Bronze quote enums are reused. The facade,
dated origination quote guard, Rates latest/daily screens and unchanged-price
confirmation now support bronze. Entry guidance explains the 100% bronze reference
grade and per-gram buying basis without a copper/alloy conversion. Paper collateral
forms and canonical recorded-item validation admit bronze; standing setup offers
an optional explicitly supplied bronze monthly rate without defaulting from gold.

Bronze participates in ordinary quote-driven snapshot invalidation and before/after
source fingerprints, including corrected prior scopes. Tests found a stored
currency quantum precision issue; normalizing 0.0100 to 0.01 enforces intended
paise rounding in current valuation. Freshness, custody, frozen agreements and financial
services remain unchanged. V9 makes earlier saved risk calculations outdated and
eligible for ordinary bounded reassessment. There is no new schema or per-loan
override. Existing setup/business-package v3 can retain the current metal choice.

## Validation

The wider 286-case run passes 283 cases. Its three errors are resolved: namespace
app discovery required absolute imports in the new bronze and existing reference
UI tests; the settings-only restricted-role test needed its deferred collateral
fixture checks validated before switching roles. Its adversarial DML still runs
with the same restricted grants and asserts actual RLS/range guards.

The 165-case affected rerun passes 164 cases; it exposes a Hindi label regression.
Keeping the existing translated Pure metal label alongside bronze reference grade
corrects it. The final 16-case confirmation passes, including that real Hindi
screen, bronze direct/paper entry, quote confirmation/correction/withdrawal,
current/live-saved parity, paise rounding for all three metals, source fingerprint
changes/invalidation, V8 rejection/V9 catch-up, mixed paper file export and actual
business-package source/destination restoration. These counts overlap; do not sum
them as distinct tests. All observed failures are resolved.

The broader checks also cover current policy scope/amendments, source preservation,
gold/silver lifecycle, worker/portfolio, quote age, concurrency and restricted-role
isolation. System checks, model/migration consistency (no new migration), published
setup-profile preservation, tracked and all three new-source import boundaries,
documentation links and whitespace checks pass. The exact owner-created isolated
`test_rokkad_bronze_monitoring_20261014` database is removed. Fictional helper/log
artifacts remain in ignored `.tmp/bronze-monitoring-20261014`; review apps and real
development/production databases remain unchanged.

## Operational next steps

The owner supplied a bronze reference of INR 3,000/kg, exactly INR 3/g. Confirmation
of the selling price and source name remains pending; no positive selling figure
or external source is invented. Record the reviewed real quote through ordinary
Rates after coordinated matching V9 web/worker delivery, then amend JCL's existing
Workspace monitoring policy with predecessor/reason and retained other limits.
The metal choice will also replace current lower-of monitoring in that scope.
Check actual reassessment blockers afterwards; current coverage is not an assurance
that collateral is sufficient or the paper books are complete.

There is no production quote, monitoring-policy change, financial posting, worker
change, deployment or commit in this local implementation. Published older
loan-history profiles keep their existing enums; bronze is retained through the
ordinary servicing-file and full business-package paths tested above.

Read-only release preparation confirms the production web and monitoring still
share `rokkad:dashboard-sections-20261012-fb9c494297df`, both running with zero
restarts. Root free capacity is 8.71 GiB and all six existing timers are enabled
and active. This inventory is not a new backup recovery test or a candidate
release rehearsal; those coordinated checks remain in the ordered release step.
