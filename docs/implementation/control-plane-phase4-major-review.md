---
status: accepted
owner: project
updated: 2026-08-17
tags: [workspace, subscriptions, entitlements, authorization, rls, review]
related: [../architecture/control-plane-contracts.md, ../architecture/saas-control-plane-architecture-audit.md, ../STATUS.md]
---

# Control-plane Phase 4 major review

## Verdict

The control-plane foundation is stable enough to proceed to Phase 5. Workspace
lifecycle, Subscription lifecycle, the typed entitlement authority,
control-plane authorization, and forced RLS all pass their current acceptance
gates. One billing-boundary blocker was found and fixed during this review:
`SubscriptionValidationMiddleware` caught billing evaluation failures and
continued the request. It now fails closed with HTTP 503.

The effective business-request chain is:

```text
explicit Workspace path/domain
  -> active Membership and Workspace lifecycle
  -> transaction-local workspace_context
  -> PostgreSQL forced RLS
  -> effective Subscription billing decision
  -> business view authorization
  -> typed feature/limit entitlement when the feature is optional
```

A Workspace without a Subscription is redirected to its Workspace-scoped plan
selection page. An active Subscription or current trial can enter business
apps. An expired trial or other commercially unavailable state can enter only
billing recovery surfaces. A billing-store error returns 503.

## Findings by disposition

### BLOCKER

| Finding | Disposition |
| --- | --- |
| Billing middleware swallowed any exception and allowed the protected request to continue. This could expose Party, Loans, Notify v2, or Rates whenever billing evaluation failed. | Fixed in this review. The boundary logs the exception and returns HTTP 503. Full-client acceptance coverage proves the fail-closed behavior. |

There are no open blockers after the fix and verification below.

### FIX IN CURRENT PHASE

| Finding | Disposition |
| --- | --- |
| No end-to-end acceptance test proved that a Workspace with no Subscription cannot enter a real business route. | Fixed. The test now exercises `/w/<slug>/parties/` through the complete middleware stack. |
| The commercial-gate matrix did not cover allowed active/trial states and expired-trial recovery beside missing billing. | Fixed. Five cases now cover missing, active, current trial, expired trial, and billing database failure. |
| Billing templates used ambiguous non-Workspace route reversals after canonical billing URLs became slug-scoped. | Fixed in the current worktree; live billing links now include the explicit Workspace slug or present a Workspace selector. |
| A new Workspace reached billing recovery but the local Plan catalog was empty, while the old seed command advertised retired Product/Inventory-era capacity. | Fixed. The idempotent surviving-product catalog is seeded locally and the plan page no longer advertises retired capabilities. |

### DEFER TO NEXT PHASE

| Finding | Reason |
| --- | --- |
| Invitation acceptance and onboarding still have parallel paths and legacy bridge state. | This is the accepted Phase 5 scope: one verified, idempotent membership-acceptance command with expiry, email, retry, and seat-race tests. |
| Trial expiry is derived safely at request time but does not automatically append a stored transition event. | Access is already correct and fail closed. Add an operational reconciliation command/job when background execution contracts are consolidated. |
| `SubscriptionAccessService` remains as a compatibility surface although the request middleware no longer uses it. | Retire it after remaining tests/callers are converted, without reopening the Phase 4 authority decision. |

### DEFER TO LATER PHASE

| Finding | Target |
| --- | --- |
| Surviving business apps retain direct owner/role authorization checks instead of consuming only `WorkspaceAccess`. | Phase 9 data-plane audit. Control-plane endpoints already use the canonical policy. |
| Core module feature codes such as `loans.core` are defined by the entitlement contract but are not yet required at every module entry point. | Phase 8 contract gates and Phase 9 caller convergence. The commercial Subscription gate protects all business apps now; typed entitlements protect optional features/limits. |
| Legacy terminology, compatibility routes, diagnostic source counters, and obsolete permission helpers remain. | Phases 6 and 7 UI/URL and residue cleanup. |
| Physical Workspace deletion and long-term retention policy remain intentionally unimplemented. | A later lifecycle/operations phase after retention requirements are decided. |

### OUT OF SCOPE

- Pricing strategy, plan packaging, discounts, and product-catalog redesign.
- Production payment-provider credentials and commercial provider selection.
- Encoding RBAC, billing, or entitlements in PostgreSQL RLS policies.
- Reintroducing DEA/accounting or retired apps.
- Business-domain object invariants unrelated to the control-plane boundary.

## Stability assessment

| Boundary | Assessment | Evidence |
| --- | --- | --- |
| Workspace lifecycle | Stable | Explicit states, locked/reasoned/audited transitions, lifecycle middleware enforcement, and lifecycle suite passing. |
| Subscription lifecycle | Stable for Phase 4 | One stored status, derived effective trial state, locked event-backed transitions, replay-safe provider identity, recovery-only denial, and full request-gate matrix. |
| Entitlements | Stable authority; caller rollout incomplete | Namespaced typed API, fail-closed missing/malformed grants, explicit override provenance, and plan projection tests. Core module convergence is later work. |
| Authorization | Stable control plane; data-plane convergence incomplete | Canonical Membership/ownership and `WorkspaceAccess` pass privilege and transfer tests. Direct business-app checks remain explicitly deferred. |
| RLS | Stable | 95 registered Workspace-owned tables use enabled and forced policies; restricted-role tests pass for Party, Loans, Notify v2, and Rates. |

## Verification checkpoint

- 141/141 Subscription, Workspace lifecycle, ownership/RBAC, and org tests pass.
- 17/17 billing-gate and restricted-role RLS tests pass.
- Django system check passes.
- `makemigrations --check --dry-run` reports no model changes.
- `check_saas_foundation` reports zero integrity findings, zero missing owner
  memberships, zero incorrect owner roles, and zero null Membership roles.
- `git diff --check` passes.

The next recommended execution step is Phase 5 invitation and onboarding
consolidation. Do not begin business-app authorization convergence early; keep
that bounded to the accepted Phase 9 audit.
