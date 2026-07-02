---
status: proposed
owner: project
updated: 2026-07-02
tags: [implementation, subscriptions, saas, architecture]
related: [../adr/2026-07-02-tenant-billed-subscription-architecture.md]
---

# Subscription Architecture Blueprint

## Purpose

This document turns the subscription architecture decision into a concrete implementation blueprint. It proposes the model layout, service boundaries, access flow, and signatures for the initial implementation slice.

## Guiding Rules

- The workspace/company is the customer and billing unit.
- Membership is the user-to-workspace relationship.
- Subscription is evaluated per workspace, not per user.
- Billing state lives in the public schema.
- Tenant modules consume a service-layer entitlement decision.

## Proposed Models

### 1. BillingAccount

Purpose: represent the billing identity for a workspace.

Suggested fields:

- id
- company (FK to Company)
- provider (CharField, e.g. razorpay, stripe)
- provider_customer_id (CharField, nullable)
- billing_email (EmailField, nullable)
- billing_name (CharField, nullable)
- phone (CharField, nullable)
- currency (CharField, default="INR")
- tax_id (CharField, nullable)
- address_line1 (TextField, nullable)
- address_line2 (TextField, nullable)
- city (CharField, nullable)
- state (CharField, nullable)
- postal_code (CharField, nullable)
- country (CharField, nullable)
- is_default (BooleanField, default=True)
- created_at
- updated_at

Suggested constraints:

- one billing account per company
- one default billing account per company

### 2. Plan

Purpose: define reusable product tiers and limits.

Suggested fields:

- id
- code (slug-like unique identifier)
- name
- description
- billing_interval (monthly/yearly)
- price_amount
- price_currency
- trial_days
- is_active
- sort_order
- created_at
- updated_at

Suggested existing fields to preserve:

- max_users
- max_products
- max_warehouses
- max_transactions_per_month
- max_invoices_per_month
- has_advanced_reporting
- has_multi_warehouse
- has_approvals_workflow
- has_api_access
- has_custom_fields
- extra_user_price

### 3. Subscription

Purpose: represent the active billing contract for a workspace.

Suggested fields:

- id
- company (FK to Company)
- billing_account (FK to BillingAccount, nullable)
- plan (FK to Plan)
- status (trial, active, past_due, suspended, cancelled, expired)
- billing_interval
- current_period_start
- current_period_end
- trial_end_at
- cancel_at_period_end (BooleanField, default=False)
- canceled_at (DateTimeField, nullable)
- provider_subscription_id (CharField, nullable)
- provider_status (CharField, nullable)
- auto_renew (BooleanField, default=True)
- is_active (BooleanField, default=True)
- created_at
- updated_at

Suggested constraints:

- one active subscription per company, or one subscription row with lifecycle history as state transitions
- use explicit status rather than relying on `is_active` alone

### 4. SubscriptionEntitlement

Purpose: represent effective entitlement state for a workspace.

Suggested fields:

- id
- subscription (FK to Subscription)
- feature_code (CharField)
- feature_type (module, limit, boolean, usage)
- value (TextField or JSONField)
- source (plan, override, manual, provider)
- is_enabled (BooleanField, nullable)
- created_at
- updated_at

Suggested examples:

- module:accounting -> enabled=true
- module:loan_management -> enabled=true
- limit:max_users -> 10
- limit:max_products -> 5000
- feature:advanced_reporting -> enabled=false

### 5. Invoice

Purpose: hold invoice billing records.

Suggested fields:

- id
- subscription (FK to Subscription)
- invoice_number
- status
- currency
- subtotal
- tax_amount
- total_amount
- issued_at
- due_at
- paid_at
- provider_invoice_id
- provider_payment_id
- created_at
- updated_at

### 6. Payment

Purpose: hold payment attempts and outcomes.

Suggested fields:

- id
- invoice (FK to Invoice)
- subscription (FK to Subscription)
- provider (CharField)
- provider_payment_id
- provider_order_id
- amount
- currency
- status
- payment_method
- failure_reason
- captured_at
- refunded_at
- created_at
- updated_at

### 7. ProviderWebhookEvent

Purpose: persist provider webhook events safely.

Suggested fields:

- id
- provider (CharField)
- event_type (CharField)
- provider_event_id (CharField, nullable)
- payload (JSONField)
- signature (CharField, nullable)
- processed (BooleanField, default=False)
- processing_error (TextField, nullable)
- processed_at (DateTimeField, nullable)
- created_at
- updated_at

### 8. SubscriptionEvent

Purpose: capture lifecycle history and audit events.

Suggested fields:

- id
- subscription (FK to Subscription)
- actor_user (FK to User, nullable)
- event_type (CharField)
- old_status (CharField, nullable)
- new_status (CharField, nullable)
- metadata (JSONField, default=dict)
- created_at

## Service Layer Signatures

### SubscriptionAccessService

Purpose: centralize all subscription, membership, and entitlement checks for access decisions.

Suggested interface:

```python
class SubscriptionAccessService:
    def evaluate_access(
        self,
        *,
        user: User,
        workspace: Company,
    ) -> AccessDecision: ...

    def can_access_workspace(
        self,
        *,
        user: User,
        workspace: Company,
    ) -> bool: ...

    def can_access_feature(
        self,
        *,
        user: User,
        workspace: Company,
        feature_code: str,
    ) -> bool: ...

    def ensure_access(
        self,
        *,
        user: User,
        workspace: Company,
        feature_code: str | None = None,
    ) -> AccessDecision: ...
```

Suggested return object:

```python
@dataclass
class AccessDecision:
    allowed: bool
    reason: str
    message: str
    membership: Membership | None
    subscription: Subscription | None
    entitlements: list[SubscriptionEntitlement]
    feature_enabled: bool = True
```

### EntitlementService

Purpose: calculate effective entitlements for a workspace from plan and overrides.

Suggested interface:

```python
class EntitlementService:
    def get_effective_entitlements(self, *, subscription: Subscription) -> list[SubscriptionEntitlement]: ...

    def get_feature_value(self, *, subscription: Subscription, feature_code: str) -> object: ...

    def is_feature_enabled(self, *, subscription: Subscription, feature_code: str) -> bool: ...

    def get_limit(self, *, subscription: Subscription, limit_code: str) -> int | None: ...
```

### BillingService

Purpose: manage plan changes, invoices, and billing transitions.

Suggested interface:

```python
class BillingService:
    def create_subscription(
        self,
        *,
        company: Company,
        plan: Plan,
        billing_account: BillingAccount | None = None,
    ) -> Subscription: ...

    def change_plan(
        self,
        *,
        subscription: Subscription,
        new_plan: Plan,
        effective_at: datetime | None = None,
    ) -> Subscription: ...

    def suspend_subscription(self, *, subscription: Subscription, reason: str) -> Subscription: ...

    def reactivate_subscription(self, *, subscription: Subscription) -> Subscription: ...
```

### PaymentProviderService

Purpose: abstract provider interactions such as Razorpay or Stripe.

Suggested interface:

```python
class PaymentProviderService:
    def create_checkout_session(
        self,
        *,
        company: Company,
        plan: Plan,
        success_url: str,
        cancel_url: str,
    ) -> dict: ...

    def handle_webhook(self, *, payload: dict, signature: str | None = None) -> None: ...
```

### MembershipPolicyService

Purpose: enforce seat limits and role-specific billing access.

Suggested interface:

```python
class MembershipPolicyService:
    def can_add_member(self, *, workspace: Company, actor: User) -> bool: ...

    def can_invite_member(self, *, workspace: Company, actor: User, role: str) -> bool: ...

    def enforce_seat_limit(self, *, workspace: Company) -> None: ...
```

## Access Flow

The access decision should be evaluated in this order:

1. Resolve the selected workspace.
2. Resolve the user’s membership in that workspace.
3. If no membership exists, deny access.
4. If the workspace is suspended, deny or redirect to billing.
5. If the subscription is inactive or past due, deny or redirect to billing.
6. If the feature requested is not enabled by entitlement, deny access.
7. Allow access.

## Middleware and View Integration

### Middleware

The current middleware should delegate to `SubscriptionAccessService.evaluate_access()` rather than performing ad hoc checks.

### Decorators and Mixins

Views and CBVs should use a shared decorator/mixin that calls the same access service.

### Templates

Template-level subscription banners should consume a single context object produced by the service layer, not direct model access.

## Migration Strategy for the First Slice

### Phase 1

- add new public-schema models: `BillingAccount`, `SubscriptionEntitlement`, `ProviderWebhookEvent`, `SubscriptionEvent`
- keep the current `Subscription` model as the compatibility anchor
- add service layer but route through the existing subscription row first

### Phase 2

- replace direct checks in middleware/decorators with `SubscriptionAccessService`
- keep old code paths as compatibility wrappers for one release cycle

### Phase 3

- enforce seat limits in membership and invitation flows
- add billing-admin capability and update billing UI access

### Phase 4

- replace Razorpay-specific assumptions with provider-agnostic webhooks and billing events
- remove old user-based subscription assumptions

## Proposed Initial Tests

- one user owns multiple workspaces with different plans
- one user is owner in one workspace and staff in another
- expired trial blocks access to tenant modules
- failed payment blocks access after grace period
- feature disabled by plan blocks module access
- seat limit prevents new member invitation
- owner transfer preserves billing continuity
- billing admin can manage billing without owner override

## Recommended First PR Scope

The first implementation slice should only introduce:

- model additions,
- access service,
- middleware/view integration,
- seat-limit enforcement for invitations and membership add,
- entitlement evaluation for a small set of features.

It should not yet attempt full enterprise billing or a complete provider rewrite.
