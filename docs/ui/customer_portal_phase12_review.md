---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, portal, review, closeout]
related:
  - docs/ui/customer_portal_phase12_plan.md
  - docs/ui/customer_portal_identity_phase12.md
  - docs/ui/customer_portal_selector_contracts_phase12.md
  - docs/ui/customer_portal_shell_phase12.md
---

# Customer Portal Phase 12 Review

Phase 12 was completed as an architecture, identity, selector-contract, and
shell-readiness phase. Its original live-route deferral is now superseded by the
Party rollout read-only portal MVP.

## Completed

- Phase 12.1 documented the customer/member portal boundary and kept target
  routes absent.
- Phase 12.2 chose Party as the portal customer identity source and documented a
  future explicit `PartyPortalAccess`-style tenant binding.
- Phase 12.3 added fail-closed read-only selector contracts for dashboard,
  loans, invoices, payments, documents, and statements.
- Phase 12.4 upgraded `base_customer_portal.html` into a real portal-only shell
  with pending navigation and no ERP/sidebar leakage.
- The later Party rollout added the access-grant model, Party-scoped selectors,
  tenant-only `/portal/...` routes, and read-only portal screens.

## Superseded Route Decision

The original Phase 12 decision was: do not add live `/portal/...` routes with
placeholder views.

That warning remains valid for placeholder routes, but the route absence itself
is superseded. Tenant portal routes are now live because they resolve an active
`PartyPortalAccess`, validate `PortalIdentity`, and read through Party-scoped
selectors.

The current live tenant route set is:

- `/portal/`
- `/portal/loans/`
- `/portal/invoices/`
- `/portal/payments/`
- `/portal/documents/`
- `/portal/statements/`

Public URLConf still does not expose `/portal/...`.

## Portal Domain Strategy

The MVP keeps the customer/member portal tenant-path only. Customers use the
tenant route set under `/portal/...`; the public URLConf does not expose portal
routes, and there is no branded portal subdomain yet.

A branded portal subdomain or public-schema entrypoint should be designed only
after the read-only portal has real users and the invitation/customer-auth
lifecycle is stable. That future design must still resolve an explicit tenant
and apply the same `PartyPortalAccess` checks before exposing Party data.

## Live Route Requirements Now Met

- `PartyPortalAccess` exists as a tenant-schema access grant.
- `resolve_portal_identity()` performs a database-backed active-grant lookup.
- Portal selectors validate `PortalIdentity` before reading tenant data.
- Tenant tests cover active-grant resolution, inactive-grant denial, and
  cross-party document isolation.
- Route tests prove `/portal/...` is tenant-only and absent from public routes.

## Compatibility Findings

- `PORTAL_CUSTOMER` is a Party role marker, not an authenticated web access
  grant.
- Matching email, phone, WhatsApp, or PAN remains verification input only, not
  authorization.
- Staff workspace membership must not imply portal customer access.
- Portal shell navigation is enabled only for read-only customer portal routes.
- Customer-facing portal mutation routes remain out of scope.
- Existing portal access grant state changes are service-owned and auditable;
  customer-facing invite or self-service mutation routes remain out of scope.

## Verification

- `python manage.py test django_project.test_customer_portal_phase12_intent django_project.test_customer_portal_identity_intent django_project.test_customer_portal_selector_contracts_intent django_project.test_customer_portal_phase12_review_intent apps.tenant_apps.party.tests.test_party_portal --keepdb`
- `python manage.py test django_project.test_template_layout_intent django_project.test_shell_render_smoke --keepdb`
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`

## Next Recommended Step

Keep the portal read-only. The next portal-specific step should be invitation
and customer-auth lifecycle design for creating grants, email verification, and
first-login activation before any customer-facing mutation workflow is designed.
