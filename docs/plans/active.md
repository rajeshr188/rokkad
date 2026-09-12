---
status: active
owner: project
updated: 2026-09-12
tags: [plans, active]
---

# Active work

The owner approved the [Rates/appraisal improvement order](../implementation/rates-appraisal-monitoring-review.md).
Increment 1 (quote readiness and actionable loan errors) is validated locally.
Increment 2 (effective-dated, auditable quote history) is implemented and validated;
Rates migration 0003 is applied locally. Increment 3 (monitoring freshness and
active-loan reassessment) is implemented and validated; Loans 0006 is applied locally. Increment 4 is implemented locally: complete active-loan monitoring, date-based
freshness, bounded repeated refresh and immutable policy amendments.
See [Loan health](../flows/loan-health-monitoring.md); validation passed and Loans 0007 is applied locally.
The owner's newly stated launch volumes require a capacity-hardening increment
before production readiness claims. The owner has now shelved further large-scale
testing until better hardware is available under
[FW-004](future-work.md#fw-004-launch-scale-loan-monitoring-capacity). The selected
one-hour freshness target remains unproven; do not restart long local tests
without owner resumption. See the
[capacity review](../implementation/rates-appraisal-monitoring-review.md#launch-capacity-requirements-and-review-2026-09-11).
Operator UI/content and amendment submission review is complete; checkpoint
`21a48aee` is published. Closed-loan cleanup and the first homogeneous 3,000/10,000
RLS baseline/read-reuse optimization are implemented locally. Mixed-history
3,000/10,000-active benchmarks now pass, with additional closed loans, all four
product structures, repayment/reversal evidence and price invalidation. Schedule
allocation prefetch and per-loan worker transactions with bounded Workspace turns
are implemented. The continuous 100 x 3,000-active baseline failed the one-hour target locally:
121,869 of 300,000 loans were observed assessed by 3,589 seconds. The 100 x 10,000
dataset is prepared; one phase stopped after a 706-second measurement gap, and
the next retry was stopped at owner request after 19,185 assessments were observed
at 940.65 seconds. Remaining large-scale testing is shelved in FW-004. Measured
query-optimization candidates and the acceptance requirements are preserved for
later prioritization; these partial upper-size runs establish no capacity claim.
See the [full-load report](../implementation/monitoring-capacity-test.md) and [mixed results](../implementation/rates-appraisal-monitoring-review.md#mixed-workload-and-worker-increment-2026-09-11).
The optional worker is configured in code but has not been started against normal
development or production data. Origination
age enforcement and frozen quote provenance are implemented locally for methods
that consume Rates. The first version requires today's loan/disbursal dates,
blocks changed or old approved quotes and preserves completed-action replay.
Appraisal-only date behavior is unchanged. Historical entry and overrides need
their own contract before extending this scope. See the
[origination review](../implementation/origination-rate-freshness-review.md).
See the [quote operator guide](../flows/metal-rate-entry.md). Existing form cleanup is published.

Follow [incremental project hardening](project-hardening.md), based on the
[architecture review](../architecture/2026-09-09-project-review.md). The active plan
selects work; [Status](../STATUS.md) records the checkpoint and validation.

R08/R09/R10/R13 documentation, onboarding and residue cleanup are complete.
R11 dashboard visibility/batching and R07 Loans routing are complete locally.
All Loans route families use direct Workspace adapters; response rewriting is
removed. The Loans views portion of R12 is complete: focused modules own all
handlers and views.py retains compatibility imports. See the
[module map](../implementation/loans-view-organization.md). Foundation, operator
commands and billing hardening are included in the local checkpoint.
Application checkpoints are published through fdb5e97f.
Orgs view organization is complete and published, including account/preferences
and slug adapters. See the
[orgs module map](../implementation/orgs-view-organization.md). Broader
model/form/renewal-service review selected document forms, now published
with compatible public imports; see the
[review](project-hardening.md#remaining-r12-module-review). The three license/series
setup forms are also extracted and published. Remaining form families have been
reviewed; the three economic-setup forms are published as 7c043eb0.
The eight funding forms preserve compatible public imports.
Funding and the five storage/physical-verification forms are published as fdb5e97f.
Verify publication CI; intake/lifecycle forms remain together pending a concrete need. See the
[form-family review](project-hardening.md#remaining-form-families-reviewed-after-16be7149).
Model and renewal-service moves remain deferred.

Razorpay setup/provider testing is shelved as
[FW-002](future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance).
License scoping is shelved as
[FW-001](future-work.md#fw-001-optional-owner-configurable-license-scope).
Neither resumes from proceeding with unrelated cleanup. Physical phone/camera and
printer checks remain deferred; production acceptance is separate.

Prior delivery plans and contradictory old "next" steps are preserved in the
[active-plan snapshot](../archive/context/2026-09-09/plans/active.md), not current work.
