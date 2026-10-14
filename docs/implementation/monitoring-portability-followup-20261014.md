---
status: verified-local
owner: project
updated: 2026-10-14
tags: [monitoring, portability, diagnosis]
related: [../adr/2026-10-14-monitoring-choice-business-package.md, current-monitoring-valuation-mr05.md]
---

# Monitoring portability and JCL coverage follow-up

MR-05's monitoring choice, MR-06's recurring worker and MR-07's shared calculation
optimization are deployed. MR-05's business-package profile limitation was still
present when the owner requested this follow-up. The current checkout now adds
package/setup version 3 to preserve explicit monitoring choices; verification is
recorded below. This work makes no production policy/worker change.

## Live read-only diagnosis

On 14 October, restricted runtime reads with explicit JCL context and READ ONLY
transactions report:

| Dimension | Result |
| --- | --- |
| Active ordinary loans | 2,680 |
| Current assessments | 2,680 |
| Stale / failed / unassessed | 0 / 0 / 0 |
| Usable financial calculations from entered records | 2,680 |
| Current assessments lacking collateral coverage | 2,376 |
| Usable collateral coverage | 304 |
| Provisional paper-book coverage | 2,378 |
| Complete transaction coverage under existing workflow rules | 302 |

Every unknown collateral result reports `MISSING_APPRAISAL`. JCL has one
Workspace-level policy, version 1, effective 25 September, using
`ORIGINAL_AGREEMENT`: 2,377 active loans retain `LATEST_APPRAISAL`, and 303 retain
`LOWER_OF_CALCULATED_AND_APPRAISAL`. No explicit current valuation amendment has
been saved. Current financial support means the entered records can be calculated;
it is not proof that unentered paper transactions do not exist.

Among the 2,376 affected loans, 2,367 have CURRENT saved metal-price inputs; nine
have MISSING price evidence. A further aggregate-only read identifies those nine
as loans with BRONZE collateral: no non-positive net weights, non-positive purity,
or purity above 100 was found in this cohort. Bronze is not automatically a bad
record; the current Rates facade supports calculated GOLD/SILVER value only.
No item has ineligible custody. This aggregate input check does not promise that
a metal-only policy makes every assessment usable, validate jewellery physically,
or choose a policy for the owner. The cohort spans licence IDs 1 and 2; review the
scope before amending, since a licence policy also applies to other loans under
that licence. Keep new-lending checks and frozen loan agreements distinct.

The later aggregate read confirms both licences contain saved appraisal-only and
lower-of loans (licence 1: 1,900 appraisal-only / 228 lower-of; licence 2: 477 / 77).
The unavailable count remains 2,376; totals differ slightly from the earlier
snapshot as live loans continue to be created. There is no existing per-loan or
per-metal current valuation override. A Workspace/licence metal-only amendment
therefore also replaces the method for loans with usable appraisals, and adding
an appraisal would not cure bronze coverage under that metal-only policy.
The owner must choose the intended current risk valuation before an amendment.
An explicit method for mixed precious/non-precious portfolios would require a
separately reviewed extension; no automatic fallback or policy change is made.
Keeping the preserving choice instead requires genuine current approved
appraisals, not invented historical origination evidence. Paper-book reviews are
independent and must establish the entered position through the checked date.

The owner subsequently selected current calculated metal monitoring and requested
bronze reference quotes/calculation support. The
[bronze implementation](bronze-monitoring-20261014.md) extends the existing metal
path rather than adding the potential exception workflow discussed above. This
is local work until coordinated delivery; the earlier live diagnosis remains a
record of the deployed configuration at that time.

Production web and monitoring share
`rokkad:dashboard-sections-20261012-fb9c494297df`. Both are running with zero
restarts. Monitoring settings are explicit Workspace IDs `1 2 3`, batch size 10,
busy pause 5 seconds and idle/error pause 300 seconds. An assessment run performs
the same financial, overdue and current collateral calculation used by live loan
reads; it saves derivative risk projections/transitions, not financial charges.

The worker selects active loans without a CURRENT, today-dated V8 assessment.
Each loan commits in its own Workspace transaction with claim/source rechecks.
After a round across configured Workspaces it pauses five seconds while making
progress, otherwise five minutes. These are polling intervals, not a promise that
each loan is reassessed every five minutes. A new local day makes older assessments
due; supported changes to loan/collateral/appraisal/rate/policy evidence invalidate
the affected assessments. A CURRENT assessment with missing valuation does not
re-enter every idle poll; it becomes due after invalidation or the next day. A
manual refresh uses the same guards. Dashboard GET does not refresh or post charges.

Thus recurring refresh and clearer four-dimensional presentation were applied.
The portfolio has been refreshed; missing appraisals and incomplete books have
not been fabricated or automatically resolved. A deliberate current metal-monitoring
choice can address the appraisal-only requirement when actual recorded metal inputs
are usable, while the nine input gaps and paper-book coverage need their own review.

## Portability correction

Package version 3 extends setup version 2 only with the bounded enum field.
Any retained explicit choice selects it automatically; packages 1/2 retain their
published fields and preserving-default restore. Version 3 preserves policy scopes,
dates, version/predecessor chains, freshness thresholds and choices without
rewriting original loan valuation or approving destination lending.
The existing atomic preview/confirmation, file cleanup, checksums, idempotent
receipt, source licence/quote adapters, forced RLS and exclusions remain.
Unknown/missing enum fields, downgraded manifests and older-version exports of
explicit choices fail closed. Migration 0026 extends the immutable receipt profile
guard and prevents downgrade with retained version-3 receipts.

The initial test startup found an unrelated model-specific RLS registry lookup
that eagerly evaluated a missing app-wide fallback during concurrent WhatsApp
work. The lookup now evaluates its fallback only when required, so registered
models still reach actual table/forced-RLS verification. No isolation check is
skipped. A regression exercises a registered model without an app-wide fallback.

## Validation and remaining decisions

All 74 initial focused checks pass. The wider 257-case run passes 255 immediately;
its two fixture failures are resolved in the final 60-case affected rerun, which
passes completely. An existing continuation fixture needed a new current quote:
the original 5 October observation is retained rather than redated or exempted
from the seven-day approval rule. The new source-quote assertion now uses the
actual published transfer-profile constant. These runs overlap; do not sum their
counts. They verify older packages, explicit policy amendments/licence scopes,
source quote/storage retention, original loan-method preservation, rollback preview,
real repeatable-read command restore, retries, unknown/missing/downgraded fields,
immutable receipts and downgrade refusal, financial/funding/storage continuation,
monitoring/worker behavior and forced-RLS registration.

System checks, model/migration consistency, tracked and affected-untracked import
boundaries, contract-field/guard preservation, documentation links and whitespace
checks pass. The exact isolated `test_rokkad_monitoring_portability_20261014`
database is removed after verification. Source live diagnosis and synthetic
test helpers/logs are kept in ignored `.tmp/monitoring-portability-20261014`.
The independent owner review app on port 8112 and the older port-8000 snapshot
remain untouched. Production portability rollout, real package acceptance and
actual JCL policy/evidence review remain separate from development verification.

The optional export of individual loan numbers and collateral attributes for the
nine-record input review was refused by automatic approval review. Only aggregate
production diagnosis was performed; an individual-record local file needs explicit
payload/destination authorization. That optional review list is not a prerequisite
to completing the profile implementation.
