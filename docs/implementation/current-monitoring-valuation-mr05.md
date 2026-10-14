---
status: active
owner: loans
updated: 2026-10-12
tags: [implementation, monitoring, valuation, tests]
---

# MR-05 current monitoring valuation

The [decision](../adr/2026-10-12-current-monitoring-valuation-policy.md) adds a
current valuation choice without changing original agreement or origination.

## Implementation

Loans migration 0073 adds `LoanMonitoringPolicy.valuation_basis` with
`ORIGINAL_AGREEMENT` as the preserving default and a database permitted-value
constraint. Existing policies are never updated by the service; an explicit
authorized amendment records actor, reason, predecessor and prospective date.
Older callers omitting the field preserve the predecessor's choice and legacy
grace. Whole-policy licence override remains the existing resolution rule.

The current collateral selector uses the effective policy choice, or the original
loan snapshot method under the default. For paper/imported origins the saved
method may be a monitoring selection without original valuation proof; presentation
does not claim that proof. It retains existing loan currency quantum,
custody checks, rate/appraisal freshness, debt/exposure basis and LTV math. Direct
approval, paper admission and frozen economic agreements are unchanged. Snapshot
V8 records the actual/original method, monitoring policy and evidence-age limits;
older saved contracts appear outdated until successful refresh.

Loans setup shows the choice and saved history, explains required evidence and
removes the ineffective policy-grace input. Actual grace stays with the frozen
product/accepted opening contract; alert severity stays derived. Loan health
shows financial support, paper-book status, chosen valuation and per-item evidence
separately from saved freshness. Live loan detail identifies the current and
original method; the dashboard explains its effective monitoring basis.
Inconsistent financial failures are counted even when their assessment is ERROR,
without making failed amounts eligible for totals.

Existing business package profiles 1 and 2 retain their exact published schemas.
They accept policies that preserve the original method and reject exports with
an explicit override, explaining the need for a newer setup profile. Restore
defaults to preservation. This holds a wider setup transfer rather than silently
discarding its monitoring policy; it does not limit ordinary loan servicing.

## Validation

Local validation is complete against frozen source in
`.tmp/mr05-review-20261012/source`, using the guarded disposable
`test_rokkad_mr05_20261012` database and separate uniquely named populated
upgrade databases. Shared review and production databases are unchanged.

The first 11-case run passed ten cases; a custody-query mock also intercepted a
financial query. Preparing the real exposure before that mock fixed the fixture.
The broader 207-case run then passed, including monitoring concurrency/recovery,
direct approval, paper admission, setup, dashboard and business package/continuation.
The final source clarifies saved-basis labels and adds financial-failure display
acceptance. All 13 final MR-05 cases pass. That command also selected a nonexistent
projection test class; the corrected module subsequently passes all five checks
without database creation. These are test-selection/fixture corrections, not
unresolved application failures. The passing broad source is archived separately.

Acceptance proves:

- Default preservation and unknown stale appraisal; an explicit metal choice
  supplies eligible current coverage without changing events, schedules,
  original appraisals, agreements or payout evidence.
- All three explicit methods require their own fresh evidence; custody exclusion
  and stale/missing required evidence still block coverage.
- Today/future amendments, licence override, actor/reason checks, immutable basis
  and older submissions that preserve the predecessor's basis and hidden grace.
- Actual direct-loan detail/setup/portfolio rendering, V7-to-V8 freshness, and
  visible financial inconsistency with failed amounts excluded from dashboard totals.
- A recorded paper loan has usable current metal coverage while incomplete books
  remain provisional; neither whole-portfolio completeness nor original approval
  is invented.
- Published setup profiles retain default-policy compatibility and explicitly
  refuse an override they cannot encode.
- A populated 0072-to-0073 upgrade preserves every previous policy field and
  defaults to the saved method with the immutable trigger still enabled. Invalid
  basis insertion is refused by the database.

All fifteen candidates match final tested source. Syntax, application boundaries,
whitespace and model/migration state pass; no shared database was migrated. The
disposable database and separately created upgrade database are removed.

## Remaining release work

MR-06 must run the live MR-04 owner preflight, apply migrations 0072/0073 through
owner settings, coordinate the web/worker checkpoint and verify representative
loans. Changing actual Workspace monitoring choices is an explicit owner/admin
setup decision; local implementation neither changes JCL's basis nor proves its
missing source evidence complete. The bounded recurring worker and measured
production acceptance remain pending. A wider business setup profile retaining
explicit monitoring choices is recorded under [FW-012](../plans/future-work.md#fw-012-complete-workspace-export-and-guided-restore-into-a-fresh-workspace).
