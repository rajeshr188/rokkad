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

Phase 12 is complete for architecture, identity, selector contracts, and shell
readiness. It intentionally does not expose live `/portal/...` routes yet.

## Completed

- Phase 12.1 documented the customer/member portal boundary and kept target
  routes absent.
- Phase 12.2 chose Party as the portal customer identity source and documented a
  future explicit `PartyPortalAccess`-style tenant binding.
- Phase 12.3 added fail-closed read-only selector contracts for dashboard,
  loans, invoices, payments, documents, and statements.
- Phase 12.4 upgraded `base_customer_portal.html` into a real portal-only shell
  with pending navigation and no ERP/sidebar leakage.
- Phase 12.5 closes the phase by deferring live routes until the access-grant
  model exists.

## Route Decision

Do not add live `/portal/...` routes with placeholder views.

The current access helper is intentionally fail-closed and the selector
contracts intentionally raise `PortalSelectorNotImplemented`. Adding routes now
would create a customer-facing surface that cannot yet prove tenant Party access
from database state.

The target routes remain absent:

- `/portal/`
- `/portal/loans/`
- `/portal/invoices/`
- `/portal/payments/`
- `/portal/documents/`
- `/portal/statements/`

## Required Before Live Routes

- Add a tenant-schema `PartyPortalAccess` model or equivalent explicit grant.
- Add migrations and tenant rollout guidance for the access grant.
- Implement a real tenant binding lookup for `resolve_portal_identity()`.
- Replace fail-closed selector stubs with Party-scoped query implementations.
- Add cross-party denial tests for loans, invoices, payments, documents, and
  statements.
- Add route tests proving portal users do not receive tenant ERP navigation or
  staff-only actions.

## Compatibility Findings

- `PORTAL_CUSTOMER` is a Party role marker, not an authenticated web access
  grant.
- Matching email, phone, WhatsApp, or PAN remains verification input only, not
  authorization.
- Staff workspace membership must not imply portal customer access.
- Portal shell rendering is ready, but its navigation remains disabled and
  marked pending.

## Verification

- `python manage.py test django_project.test_customer_portal_phase12_intent django_project.test_customer_portal_identity_intent django_project.test_customer_portal_selector_contracts_intent django_project.test_template_layout_intent django_project.test_shell_render_smoke --keepdb`
- `python manage.py check`
- `git diff --check`

## Next Recommended Step

Proceed with Phase 13.2 tenant route canonicalization before adding live portal
routes. Convert remaining visible tenant sidebar/dashboard entry links to
existing slug aliases while keeping legacy tenant roots active.
