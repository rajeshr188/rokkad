---
status: superseded
owner: project
updated: 2026-07-02
tags: [adr, subscriptions, saas, tenancy]
related:
  - ../implementation/subscription-architecture-blueprint.md
  - ../architecture/control-plane-contracts.md
  - 2026-08-17-workspace-lifecycle-and-billing-boundary.md
  - 2026-08-17-workspace-entitlement-contract.md
  - ../STATUS.md
---

# Tenant-Billed Subscription Architecture for Rokkad

> Superseded on 2026-08-17. The Workspace-as-customer direction remains valid,
> while the accepted lifecycle, billing, and entitlement contracts now live in
> the linked Phase 0.5 ADRs and canonical control-plane contract.

Date: 2026-07-02
Status: Superseded
Owners: Platform Architecture, Billing, Tenant Security

## Summary

Rokkad will treat the workspace/company as the subscribed customer and the billing unit. Subscription state, billing identity, and entitlement evaluation will live in the public schema, while tenant-specific ERP modules will remain tenant-scoped and access-controlled through a shared subscription service.

This decision formalizes the current direction already implied by the existing subscription model while closing the gaps around billing admins, entitlement checks, seat limits, and provider-driven lifecycle events.

## Context

Rokkad is a multi-tenant SaaS mini ERP for jewellery businesses. A user can own multiple workspaces and can also be a member of other workspaces. Each workspace is a separate tenant/business. The product needs to support:

- public/global onboarding and workspace management,
- tenant-scoped accounting, loan, inventory, product, and reporting modules,
- multiple users per tenant,
- owner and non-owner team membership,
- billing and plan administration for each tenant,
- feature gating by plan and tenant state.

The current implementation already attaches a subscription to the company/workspace in [apps/subscriptions/models.py](../../apps/subscriptions/models.py), but it still mixes tenant-billing intent with user-centric assumptions. Subscription enforcement is also spread across middleware, decorators, templates, and context processors instead of being handled via one service boundary.

## Decision

Rokkad will adopt the following architecture:

1. Tenant-billed subscription model
   - The workspace/company is the billing entity.
   - A subscription belongs to the tenant/workspace, not directly to a user.

2. Public-schema subscription state
   - Subscription lifecycle, billing account, invoices, payments, provider events, and plan/entitlement state will live in the public schema.
   - Tenant schemas remain responsible for business documents and operational ERP data.

3. Membership-based authorization
   - Access to a tenant is granted through membership and role.
   - Subscription state is evaluated after membership, not instead of it.

4. Tenant-level entitlements
   - Plan features and limits will be represented as tenant entitlements evaluated at access time.
   - Feature checks will be centralized and service-driven.

5. Explicit billing-admin separation
   - The owner remains the primary business owner.
   - Billing administration will be modeled explicitly via a dedicated billing-admin capability or role, rather than inferred from owner-only code paths.

6. Provider-driven lifecycle handling
   - Payment provider events will be persisted and processed idempotently through a webhook event model.
   - Subscription transitions such as trial, active, overdue, suspended, cancelled, and upgraded/downgraded will be handled through explicit state transitions.

## Consequences

### Positive

- Aligns billing with the real SaaS ownership model: tenant is the customer.
- Supports one user owning many workspaces and being a member of others.
- Makes entitlement checks explicit and testable.
- Reduces hidden coupling between billing and user identity.
- Improves the separation between public-schema billing state and tenant-schema operational data.

### Negative

- Requires additional models and service boundaries.
- Requires a migration from the current mixed implementation.
- Requires updates to middleware, permission checks, templates, and billing flows.

## Architectural Principles

1. The tenant is the customer.
2. Membership authorizes user access inside a tenant.
3. Subscription state authorizes the tenant’s continued use of paid capabilities.
4. Entitlements decide what features and limits are available.
5. Billing and provisioning must be auditable and idempotent.
6. Public-schema billing data must never be mixed with tenant business tables.

## Recommended Model Structure

### Public schema

- User
- Company / Workspace / Tenant
- Membership
- BillingAccount
- Plan
- Subscription
- SubscriptionEntitlement
- Invoice
- Payment
- ProviderWebhookEvent
- SubscriptionEvent

### Tenant schema

- accounting
- inventory
- loan management
- sales
- purchase
- commodity accounting
- reports
- customer/vendor/party data

## Proposed Model Responsibilities

### BillingAccount

Represents the billing identity for a workspace. This is the object that can be associated with a payment provider customer ID and billing contact information.

### Subscription

Represents the active billing contract for a workspace. It is not owned by a user.

### SubscriptionEntitlement

Represents effective feature/module/limit access for a workspace. These values can be derived from the active plan and overridden for enterprise/custom agreements.

### ProviderWebhookEvent

Stores provider events such as payment succeeded, payment failed, subscription updated, or cancelled. Each event must be processed once and replay-safe.

### SubscriptionEvent

Tracks lifecycle changes such as trial started, trial expired, payment failed, subscription activated, upgraded, downgraded, suspended, and cancelled.

## Implementation Boundaries

### Public schema services

- subscription billing service
- entitlement evaluation service
- webhook handling service
- billing policy service

### Tenant-agnostic access service

- membership check
- workspace selection
- subscription status check
- entitlement check
- feature/limit enforcement

## Acceptance Criteria

The implementation will be considered complete when:

- a tenant can have one active subscription regardless of how many users belong to it,
- billing admins can manage billing without being the workspace owner,
- seat limits are enforced during invitation and membership changes,
- module access is blocked by entitlement evaluation,
- failed payments and suspension states block access appropriately,
- provider webhook replays are safe and idempotent,
- public-schema billing state remains separate from tenant operational data.

## Open Questions

The following decisions should be finalized before implementation:

1. Should billing admins be implemented as a dedicated role or as a permission-based capability on membership?
2. Should seat limits be enforced only on invitations, or also on direct role changes and membership creation?
3. Should entitlements be stored as explicit rows or as a compact policy document?
4. Should provider webhook events be stored in the public schema only, or in a separate billing domain service boundary?

## Review Trigger

Revisit this decision when:

- the billing layer becomes production-critical,
- the product needs enterprise custom plans,
- a provider integration requires more than one billing product,
- support or finance teams need explicit billing-admin workflows.
