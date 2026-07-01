---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, portal, customer, tenant]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/workspace_slug_phase11_review.md
  - docs/ui/authorization_cleanup_inventory.md
---

# Customer Portal Phase 12 Plan

Phase 12 starts the customer/member portal route-map work from the SaaS IA
target structure. This first slice is planning and guard coverage only. It does
not add live `/portal/...` routes yet.

## Current State

- `templates/base_customer_portal.html` exists as a shell alias, but it is only
  a thin alias over `layouts/base.html`.
- No first-party `portal` app or URL group is currently installed.
- The target `/portal/...` routes are intentionally absent from current URLConfs.
- Party has a canonical `PORTAL_CUSTOMER` role seed, but no user-to-party portal
  identity binding exists yet.
- Party owns customer/member profile, contact, identifier, document, and
  relationship data.
- Girvi exposes Party-centric loan history through
  `apps.tenant_apps.girvi.facade.get_party_loan_history_summary`.
- DEA owns sales/purchase invoice voucher data and payment voucher/accounting
  documents; portal invoice/payment selectors do not exist yet.

## Boundary Decision

The customer/member portal should be a tenant-scoped customer-facing surface,
not a global account dashboard and not a normal tenant ERP screen.

Initial route ownership should be a dedicated portal app or URL group that is
included only where tenant context can be resolved safely. The portal must not
read data from a selected staff workspace alone; it needs an explicit portal
identity binding from authenticated user to tenant Party.

## Identity Model

Before live routes:

- Define how an authenticated user is linked to one or more tenant Parties.
- Reuse Party as the customer/member identity source.
- Prefer a dedicated portal-access relation over inferring access from matching
  email or phone alone.
- Support a user belonging to multiple tenant/customer identities without data
  crossing between workspaces.
- Keep staff workspace membership separate from portal customer access.

## Target Routes

```text
/portal/             portal dashboard
/portal/loans/       my loans
/portal/invoices/    my invoices
/portal/payments/    my payments
/portal/documents/   my documents
/portal/statements/  my statements
```

These routes remain absent until Phase 12 adds a portal app/URL group with
explicit identity and tenant-boundary checks.

## Data Ownership

- `loans`: Girvi facade/selectors filtered by the authenticated portal Party.
- `invoices`: DEA invoice selectors filtered by customer Party.
- `payments`: DEA/Girvi payment read models filtered by source Party and source
  document ownership.
- `documents`: Party documents plus generated Girvi/customer documents, filtered
  by Party.
- `statements`: read-only statement selectors derived from DEA/Girvi, filtered
  by Party.

## Non-Negotiables

- Portal routes must fail closed without a verified tenant Party binding.
- Portal users must never see tenant ERP navigation or staff-only actions.
- Staff workspace membership must not automatically imply customer portal
  access.
- Portal pages must use `base_customer_portal.html` or a stricter descendant.
- Portal selectors must not expose another Party's loans, invoices, payments,
  documents, or statements.
- Mutating workflows are out of scope for the first portal slice.

## Implementation Order

### Phase 12.1: Plan And Guard Baseline

Status: complete.

Document the portal boundary, keep `/portal/...` routes absent, and guard the
absence until identity/tenant ownership is designed.

### Phase 12.2: Portal Identity Design

Status: complete.

Design the tenant Party binding model and access helper. Decide whether it
lives in a new portal app, Party, or orgs. Do not add live public routes yet.

### Phase 12.3: Read-Only Selector Contracts

Define selectors for loans, invoices, payments, documents, and statements. Each
selector must accept a verified tenant Party identity and fail closed otherwise.

### Phase 12.4: Shell And Navigation

Upgrade `base_customer_portal.html` into a real portal shell with portal-only
navigation, workspace/customer identity display, and no ERP/sidebar leakage.

### Phase 12.5: Live Portal Routes

Add `/portal/...` routes only after identity, selector, shell, and access tests
exist.

## Next Recommended Step

Proceed with Phase 12.2: choose and document the portal identity model, then add
the access-helper scaffold and tests without exposing live `/portal/...` routes.

Phase 12.2 is complete in `docs/ui/customer_portal_identity_phase12.md`. The
next step is Phase 12.3: define read-only selector contracts around
`PortalIdentity`.
