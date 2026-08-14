---
status: active
owner: ui
updated: 2026-07-01
tags: [ui, saas-ia, portal, identity, party]
related:
  - docs/ui/customer_portal_phase12_plan.md
  - apps/tenant_apps/party/portal_access.py
---

# Customer Portal Identity Phase 12

Phase 12.2 chooses the portal identity model and adds a fail-closed access
helper scaffold. It does not add live `/portal/...` routes.

## Decision

Use Party as the customer/member identity source and add an explicit future
tenant-schema access grant between an authenticated user and a tenant Party.

Working name:

```text
PartyPortalAccess
```

Recommended fields:

- `user`: authenticated platform user.
- `party`: tenant Party allowed to access portal data.
- `status`: invited, active, suspended, revoked.
- `verified_at`: when access was confirmed.
- `verified_by`: staff user or system process that granted access.
- `metadata`: invitation, consent, or migration context.
- audit timestamps.

The existing canonical Party role seed is `PORTAL_CUSTOMER`. That role marks
Parties that may be portal-capable, but it is not enough by itself to authenticate
a web user.

## Why Not Email Inference

Do not infer portal access from matching email, phone, WhatsApp number, or PAN.
Those are useful verification inputs, not authorization. Portal access must be
based on an explicit grant so one person cannot see another Party's data because
of shared contact details, recycled numbers, or data-entry mistakes.

## Helper Scaffold

`apps.tenant_apps.party.portal_access.resolve_portal_identity()` now exists as a
fail-closed boundary helper. Until a real `PartyPortalAccess` model or lookup is
implemented, it raises `PortalIdentityNotConfigured`.

The helper accepts an injectable binding lookup so later phases can wire the
real tenant lookup without changing portal view contracts.

## Route Policy

Keep `/portal/...` routes absent until:

- `PartyPortalAccess` or equivalent binding exists.
- Portal access helper has tenant database coverage.
- Read-only selectors accept `PortalIdentity`.
- `base_customer_portal.html` becomes a real portal shell.
- Route tests prove portal users cannot access staff ERP or another Party's data.

## Next Recommended Step

Proceed with Phase 12.3: define read-only selector contracts for loans,
invoices, payments, documents, and statements using `PortalIdentity`.
