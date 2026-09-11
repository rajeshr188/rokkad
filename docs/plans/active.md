---
status: active
owner: project
updated: 2026-09-11
tags: [plans, active]
---

# Active work

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
