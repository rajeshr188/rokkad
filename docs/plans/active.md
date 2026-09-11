---
status: active
owner: project
updated: 2026-09-11
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
before production readiness claims. Next recommendation: agree freshness targets
and benchmark representative 3,000/10,000-active-loan Workspaces under RLS; then
remove repeated reads and improve bounded scheduling/lock duration. See the
[capacity review](../implementation/rates-appraisal-monitoring-review.md#launch-capacity-requirements-and-review-2026-09-11).
Operator UI/content and amendment submission review is complete. Publish this
checkpoint, then prioritize closed-loan cleanup, representative RLS benchmarks,
measured optimization and multi-organization load validation, in that order.
The optional worker is configured in code but has not been started. Origination
age requirements remain an explicit separate policy design item.
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
