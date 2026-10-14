---
status: complete
owner: project
updated: 2026-10-14
tags: [onboarding, ux, authentication, validation]
related: [../implementation/new-user-journey-audit-20261014.md, ../STATUS.md]
---

# Improve the existing new-user journey

The owner approved the audit's recommended order on 14 October, with regression
protection. Implement in the current checkout; commit, deployment, real mail
delivery and staff acceptance remain separate actions.

| Slice | Scope | Status |
| --- | --- | --- |
| NJ-01 | Public contact and compatible email/username signin (NU-01/02) | Implemented and verified locally |
| NJ-02 | Verification, explicit trial activation and supporting account screens (NU-03/08) | Implemented and verified locally |
| NJ-03 | Separate monitoring readiness and clear workflow/valuation choices (NU-04/06) | Implemented and verified locally |
| NJ-04 | Focused setup navigation, phone actions and current public copy (NU-05/07/09) | Implemented and verified locally |
| NJ-05 | Restricted-role regressions and empty-business desktop/phone acceptance | Completed with fictional local data; real staff/provider acceptance separate |

Keep existing accounts/usernames, invitations, normal staff navigation, standing
terms, financial services and numbering behavior compatible. Keep trial consent,
verification, ownership, lifecycle, entitlements, CSRF and forced RLS checks.
Monitoring availability must never silently create a policy or imply lending
authorization. Use current six-step navigation and services; no wizard model,
new commercial mode or new financial workflow.

Acceptance includes public versus tenant routing, both login identifiers,
verification/resend/reset, legacy onboarding continuation, bounded same-Workspace
returns, trial refusal/replay, scoped monitoring availability and ordinary
direct/paper origination regressions. Synthetic browser results are not real
staff acceptance or mail-provider delivery acceptance.

All 340 distinct selected regression checks are verified across the broader run
and the corrected route-intent rerun. The 70 focused checks are a subset, not
additional distinct checks. The initial route failure was a stale test expectation
about two existing public billing routes; runtime route ordering was preserved.
An isolated walkthrough reaches an ordinary active loan using the existing
combined owner review/payout service. Earlier paper entry reaches its separate
review with the original date, standing tenure and agreed amounts; reviewing
consumes no additional number. Desktop and 390px English/Hindi checks pass.
See [implementation and acceptance evidence](../implementation/new-user-journey-refinement-20261014.md)
and the [handoff decision](../adr/2026-10-14-new-user-journey-handoffs.md).
No production deployment, provider email or paid subscription occurs in this work.
