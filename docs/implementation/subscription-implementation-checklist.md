---
status: proposed
owner: project
updated: 2026-07-02
tags: [implementation, subscriptions, checklist, saas]
related: [subscription-architecture-blueprint.md, ../adr/2026-07-02-tenant-billed-subscription-architecture.md]
---

# Subscription Implementation Checklist

## Recommended starting point

Start with a phased implementation checklist, not a broad rewrite. The safest first slice is:

1. add the missing public-schema billing models,
2. introduce a single access service,
3. switch middleware and billing views to that service,
4. keep existing subscription behavior working while the new layer becomes authoritative.

## Scope map to current Django apps

### Apps to touch first

- [apps/subscriptions](../../apps/subscriptions)
  - models, services, views, Razorpay integration, URLs
- [apps/orgs](../../apps/orgs)
  - workspace/company models, membership, role, access checks, middleware
- [accounts](../../accounts)
  - user/profile context used for workspace switching and billing UX
- [django_project](../../django_project)
  - middleware, context processors, shared URL patterns, navigation
- [templates](../../templates)
  - subscription status, billing dashboard, workspace settings links

## Phase 0 — Lock the target decisions

### Deliverables

- confirm the billing unit is the workspace/company
- confirm subscription state is evaluated per workspace
- confirm membership is the authorization layer for access, while subscription is the billing/access gate
- confirm public-schema billing state remains separate from tenant-schema ERP data

### Files to review

- [apps/subscriptions/models.py](../../apps/subscriptions/models.py)
- [apps/orgs/models.py](../../apps/orgs/models.py)
- [django_project/middleware.py](../../django_project/middleware.py)
- [apps/orgs/middleware_v2.py](../../apps/orgs/middleware_v2.py)

## Phase 1 — Model cleanup and compatibility layer

### Goal

Add the missing billing-domain models while keeping current data and flows intact.

### Add these models in [apps/subscriptions/models.py](../../apps/subscriptions/models.py)

- BillingAccount
  - linked to Company
  - provider customer info and billing contact fields
- SubscriptionEntitlement
  - linked to Subscription
  - stores feature/module/limit values
- ProviderWebhookEvent
  - stores provider payloads and processing state
- SubscriptionEvent
  - stores lifecycle change history

### Keep these existing models working

- Plan
- Subscription
- Invoice
- Payment
- UsageMetrics
- PriceOverride

### Implementation tasks

- add migration(s) for the new models
- backfill one BillingAccount per existing company/subscription
- backfill initial entitlements from existing Plan booleans and limits
- keep the existing Subscription row as the compatibility anchor while new models are introduced

## Phase 2 — Introduce a single subscription access service

### Goal

Centralize access decisions so middleware, views, decorators, and templates all use the same logic.

### Create a new service module

Suggested location:
- [apps/subscriptions](../../apps/subscriptions) / services.py or services/access.py

### Proposed service signatures

```python
class SubscriptionAccessService:
    def evaluate_access(self, *, user, workspace) -> AccessDecision: ...

    def can_access_workspace(self, *, user, workspace) -> bool: ...

    def can_access_feature(self, *, user, workspace, feature_code: str) -> bool: ...

    def ensure_access(self, *, user, workspace, feature_code: str | None = None) -> AccessDecision: ...
```

### Service responsibilities

- resolve membership
- check workspace access
- check subscription status
- evaluate entitlements
- return a single decision object with reason/message

### Replace these call sites

- [django_project/middleware.py](../../django_project/middleware.py)
- [apps/orgs/middleware_v2.py](../../apps/orgs/middleware_v2.py)
- [apps/orgs/views.py](../../apps/orgs/views.py)
- [django_project/context_processors.py](../../django_project/context_processors.py)

## Phase 3 — Replace user-centric billing assumptions

### Goal

Remove stale assumptions that still treat the billing relationship as if it belonged to a user.

### Files to fix

- [apps/subscriptions/views.py](../../apps/subscriptions/views.py)
- [apps/subscriptions/razorpay_service.py](../../apps/subscriptions/razorpay_service.py)
- [templates/subscriptions/invoice_detail.html](../../templates/subscriptions/invoice_detail.html)
- [templates/subscriptions/dashboard.html](../../templates/subscriptions/dashboard.html)

### Changes

- stop using subscription.user-style assumptions
- route checkout/payment completion through the workspace/company and billing account
- use workspace/company context for invoice and email generation
- keep the current UI flow intact while the internal model path becomes tenant-based

## Phase 4 — Add explicit entitlement evaluation

### Goal

Move from boolean plan flags to a real entitlement layer.

### Implement

- a plan-to-entitlement mapping layer
- a feature lookup service
- an enforcement point for feature gating in access checks

### Suggested entitlement examples

- accounting module enabled
- loan module enabled
- advanced reporting enabled
- multi-warehouse enabled
- staff seat limit
- products limit
- invoices limit

### Integration points

- workspace dashboard access
- tenant module entry routes
- billing/upgrade prompts
- workspace settings surfaces

## Phase 5 — Enforce seat limits and membership policy

### Goal

Prevent overages and make team growth follow the active plan.

### Files to touch

- [apps/orgs/services/control_plane.py](../../apps/orgs/services/control_plane.py)
- [apps/orgs/models.py](../../apps/orgs/models.py)
- [apps/orgs/views.py](../../apps/orgs/views.py)

### Rules to enforce

- invitations should respect seat limit
- membership creation should respect seat limit
- role changes should not silently bypass plan capacity
- owner transfer should preserve billing continuity and role validity

## Phase 6 — Introduce billing-admin and ownership separation

### Goal

Separate billing administration from ownership without breaking existing owner flows.

### Recommended approach

- keep Owner as the primary workspace owner
- add a dedicated billing-admin capability or role on membership
- update billing routes to allow billing-admins while preserving owner-only destructive actions

### Files to update

- [apps/subscriptions/views.py](../../apps/subscriptions/views.py)
- [apps/orgs/permissions.py](../../apps/orgs/permissions.py)
- [templates/components/navigation/sidebar.html](../../templates/components/navigation/sidebar.html)

## Phase 7 — Webhook processing and provider lifecycle

### Goal

Make provider events safe, replayable, and auditable.

### Implement

- webhook ingestion endpoint remains in [apps/subscriptions/views.py](../../apps/subscriptions/views.py)
- persist each event in ProviderWebhookEvent
- process idempotently
- emit SubscriptionEvent entries

### Recommended states

- trial
- active
- past_due
- suspended
- cancelled
- expired

## Phase 8 — UI and settings integration

### Goal

Make billing and entitlement status visible from the workspace shell.

### Files to update

- [templates/company/workspace_dashboard.html](../../templates/company/workspace_dashboard.html)
- [templates/components/navigation/sidebar.html](../../templates/components/navigation/sidebar.html)
- [templates/components/subscription_status.html](../../templates/components/subscription_status.html)
- [templates/subscriptions/dashboard.html](../../templates/subscriptions/dashboard.html)

### UI responsibilities

- show current plan and status
- show trial/renewal state
- show entitlement warnings
- show billing admin actions

## Phase 9 — Tests and regression coverage

### Add tests for

- one user owns multiple workspaces with different plans
- one user is owner in one workspace and staff in another
- trial expired blocks access
- payment failed blocks access after grace period
- feature disabled by plan blocks module access
- seat limit prevents new member invitation
- owner transfer preserves billing continuity
- billing admin can manage billing without owner override
- suspended workspace access is blocked

### Relevant test locations

- [apps/subscriptions](../../apps/subscriptions)
- [apps/orgs/tests.py](../../apps/orgs/tests.py)
- [django_project](../../django_project)

## Recommended first slice

If we want to implement this safely, the first slice should be:

1. add BillingAccount and SubscriptionEntitlement models,
2. add SubscriptionAccessService,
3. wire middleware and billing views to the service,
4. keep the current Plan/Subscription data model intact as the compatibility base.

That gives us the foundation without a risky full rewrite.
