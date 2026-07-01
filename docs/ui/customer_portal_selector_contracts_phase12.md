---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, portal, selectors, party]
related:
  - docs/ui/customer_portal_phase12_plan.md
  - docs/ui/customer_portal_identity_phase12.md
  - apps/tenant_apps/party/portal_selectors.py
---

# Customer Portal Selector Contracts Phase 12

Phase 12.3 defines the first read-only selector contracts for the future
customer/member portal. It does not add live `/portal/...` routes.

## Contract Boundary

Every portal selector must accept a verified `PortalIdentity` and validate it
through `validate_portal_identity()` before reading tenant data.

The current selectors intentionally raise `PortalSelectorNotImplemented` after
identity validation. This is deliberate: the contracts exist so portal views can
be designed against stable read models, but no route should silently return
empty data until real Party-scoped data sources are wired and tested.

## Read Models

`apps.tenant_apps.party.portal_selectors` defines:

- `PortalLoanSummary`
- `PortalInvoiceSummary`
- `PortalPaymentSummary`
- `PortalDocumentSummary`
- `PortalStatementSummary`
- `PortalDashboardSummary`

The summaries are read-only dataclasses shaped for dashboard/list pages. They
avoid exposing model objects as a required public contract; implementation
selectors can later populate `items` with narrow read models.

## Selector Entry Points

- `get_portal_loans_summary(identity, limit=20)`
- `get_portal_invoices_summary(identity, limit=20)`
- `get_portal_payments_summary(identity, limit=20)`
- `get_portal_documents_summary(identity, limit=20)`
- `get_portal_statements_summary(identity, limit=20)`
- `get_portal_dashboard_summary(identity)`

## Future Data Sources

- Loans: Girvi Party loan-history facade/selectors filtered by
  `identity.party`.
- Invoices: DEA invoice selectors filtered by customer Party.
- Payments: DEA/Girvi payment read models filtered by source Party and source
  document ownership.
- Documents: Party document rows plus generated Girvi/customer documents,
  filtered by Party.
- Statements: read-only DEA/Girvi statement selectors filtered by Party.

## Route Policy

Keep `/portal/...` routes absent until these selector contracts are backed by
real tenant queries and authorization tests prove:

- missing/inactive portal identity is denied;
- one Party cannot read another Party's loans, invoices, payments, documents,
  or statements;
- staff workspace membership alone does not grant portal access;
- portal pages use a portal shell without tenant ERP navigation leakage.

## Next Recommended Step

Proceed with Phase 12.4: upgrade `base_customer_portal.html` into a real portal
shell and portal-only navigation while keeping live `/portal/...` routes absent.
