---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Company (Tenant / Schema) Lifecycle Guide

Each `Company` in rokkad maps to a PostgreSQL tenant schema via `django-tenants`.
This document covers the full lifecycle: creation through permanent removal.

---

## States

```
[non-existent]
      â”‚
      â–¼
  [active]  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º  [archived / soft-deleted]
  is_deleted=False                                    is_deleted=True
      â–²                                                     â”‚
      â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ restore() â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                                            â”‚
                                                            â–¼ (requires ALLOW_COMPANY_HARD_DELETE=True)
                                                    [permanently deleted]
                                                    schema dropped, row removed
```

---

## 1. Creation

### What happens

1. `workspace_create` view (`apps/orgs/views.py`) handles the POST inside `schema_context(public)`.
2. A `Company` row is saved â€” `TenantMixin.save()` translates `auto_create_schema = True` into a `CREATE SCHEMA` call.
3. The `schema_name` is derived from the company name: `name.lower().replace(" ", "_")`.
4. A `Domain` row is created (e.g. `mycompany.localhost`).
5. The requesting user is given an **Owner** `Membership` and the workspace is set as their active workspace.
6. An `AuditLog` entry is written with action `COMPANY_CREATE`.

### Seed defaults afterwards

After schema creation the schema is empty â€” seed it before using it:

```bash
# Seed a single tenant
python manage.py seed_tenant_defaults --schema <schema_name>

# Or seed every tenant at once
python manage.py seed_all_tenants

# Seed the public schema (roles + permissions)
python manage.py seed_public_defaults
```

`seed_tenant_defaults` provisions:
- DEA core ledgers and voucher types
- Terms / rates fixtures
- Product categories, attributes, movement types
- Notify configs

### Settings that affect creation

| Setting | Default | Effect |
|---|---|---|
| `TENANT_AUTO_SEED_ON_CREATE` | `False` | Auto-run seed on schema create |
| `ONBOARDING_TEMPLATE_CLONE_MODE` | `"NODATA"` | Clone mode when provisioning from template |

---

## 2. Update / Normal Operation

- `workspace_update` view (requires `workspace_edit` permission, Owner/Admin role).
- Fields editable from UI: `name`, `owner`, `theme`, `logo`.
- Schema name is **not** changed after creation (renaming a PostgreSQL schema is a manual DBA operation).
- Changes are logged with action `COMPANY_UPDATE`.

---

## 3. Soft Delete (Archive)

### What happens

Calling `company.archive()` (or `company.delete()` without `hard=True`):
- Sets `is_deleted = True`, saves `updated_at`.
- **Schema is preserved.** All data remains intact.
- The company is excluded from `Company.objects` (the default manager filters `is_deleted=False`).
- `workspace_detail` returns HTTP 404 for archived companies.
- The requesting user's active workspace is reset to the public schema if it pointed to the archived company.

### Via the UI

`workspace_delete` view (POST, requires `workspace_delete` permission, must be the `owner`):
- Calls `company.archive()`.
- Logs `COMPANY_DELETE`.

### Via the admin

`CompanyAdmin` uses `all_objects` manager so archived companies remain visible.
Use the **"soft deleted"** list filter to scope the view.

### Via the shell

```python
from apps.orgs.models import Company
c = Company.all_objects.get(name="my-company")
c.archive()  # reversible
```

---

## 4. Restore

Only possible for archived (`is_deleted=True`) companies.

### Via the admin

Select archived companies â†’ **"Restore selected companies"** action.

### Via the shell

```python
from apps.orgs.models import Company
c = Company.all_objects.get(name="my-company")
c.restore()  # sets is_deleted=False
```

No schema changes occur â€” the data was never touched.

---

## 5. Hard Delete (Permanent)

**Irreversible.** Drops the PostgreSQL schema and removes the `Company` row and all related rows (Membership, Domain, CompanyPreferenceModel, etc.) via CASCADE.

### Guard rails

Hard delete is blocked by default. Two conditions must both be true:

1. `ALLOW_COMPANY_HARD_DELETE=True` in settings/env  **or** `force=True` is passed programmatically.
2. `schema_name != "public"` (public schema is always protected).

If the guard is not satisfied, `hard_delete()` raises `ValueError` and returns without deleting.

`auto_drop_schema` is `False` by default â€” `hard_delete()` explicitly sets it to `True` immediately before calling `super().delete()` so the schema drop only happens on that explicit path.

### Via the admin

Select companies â†’ **"Permanently delete selected companies"** action.
Per-company `ValueError` messages are shown for any that are blocked.

### Via the shell

```python
import os
os.environ["ALLOW_COMPANY_HARD_DELETE"] = "True"  # or set in .env

from apps.orgs.models import Company
from django.conf import settings
settings.ALLOW_COMPANY_HARD_DELETE = True

c = Company.all_objects.get(name="my-company")
c.hard_delete()  # drops schema + deletes row
```

Or bypass the settings check with `force=True` (use with caution):

```python
c.hard_delete(force=True)
```

---

## 6. Managers Quick Reference

| Manager | What it returns |
|---|---|
| `Company.objects` | Active companies only (`is_deleted=False`) |
| `Company.all_objects` | All companies including archived |
| `Company.all_objects.all_with_deleted()` | Same as `all_objects`, alias method |

---

## 7. Audit Log Actions

| Action | Trigger |
|---|---|
| `COMPANY_CREATE` | Successful workspace creation |
| `COMPANY_UPDATE` | Settings changed |
| `COMPANY_DELETE` | Workspace archived (soft delete) |

Audit logs are **immutable** â€” `AuditLogAdmin` has no add, change, or delete permission.

---

## 8. Caveats & Gotchas

- **Schema rename is not supported** â€” `schema_name` is set once from the company name and never updated. Rename requires a manual `ALTER SCHEMA` in PostgreSQL plus updating the `Company` row.
- **`auto_drop_schema = False` by default** â€” prevents accidental schema drops via Django ORM signals or partial deletes.
- **`Company.objects` hides archived companies** â€” any queryset that should include soft-deleted records must use `Company.all_objects`.
- **Hard delete cascades** â€” Membership, Domain, CompanyPreferenceModel, AuditLog rows referencing the company are removed by the database CASCADE. Media files are **not** automatically purged.
- **Public schema is indestructible** â€” both `archive()` (it's a no-op guard on the model) and `hard_delete()` raise or are blocked for `schema_name == "public"`.
- **Seeding is not automatic** â€” unless `TENANT_AUTO_SEED_ON_CREATE=True`, a freshly created tenant schema has no default data. Run `seed_tenant_defaults` manually.

