---
status: active
owner: project
updated: 2026-08-17
tags: [control-plane, cleanup, tenancy, authorization]
related: [../architecture/control-plane-contracts.md, ../STATUS.md]
---

# Phase 7 residue cleanup

Phase 7 removes names and integration points that imply schema tenancy or a
second authorization authority. Historical documents remain evidence and are
not rewritten as current guidance.

Completed first slice:

- removed the temporary `request.tenant` mirror;
- renamed middleware context establishment and diagnostics to Workspace terms;
- removed empty django-tenants settings and public-schema URLConf settings;
- removed unused Guardian runtime registration, backend, configuration, and
  object-permission decorator after confirming zero assignments and callers;
- retained `WorkspaceAccess` as the sole control-plane authorization API;
- reconciled invitation alias tests with the accepted safe GET/login contract;
- replaced the last live `TENANT_APPS` import error with
  `WORKSPACE_APP_LABELS` terminology.
- made `django_project.workspace_urls` the active URLConf and removed the
  obsolete `tenant_urls` import shim after moving active callers;
- changed Party portal identity resolution to use only `request.workspace`;
- removed cross-schema options from `reset_sequences`; it now operates only on
  the shared `public` schema;
- removed retired accounting and tenant-schema wording from current public and
  Notify v2 UI copy.
- renamed the active seed commands to `seed_workspace_defaults` and
  `seed_all_workspaces`, and removed unreachable retired-Product seed code.

Still pending:

- remove the now-unused Guardian line from the UTF-16 requirements manifest;

## Transitional name classification

ADR `2026-08-17-transitional-tenancy-names.md` records the accepted boundary:

- `apps.tenant_apps` is deferred naming debt across 197 live files and three
  migrations; renaming it does not strengthen RLS;
- `Company.schema_name` is currently a Workspace routing key, not a PostgreSQL
  schema selector;
- the field will be retired only through a separate additive `Company.slug`
  migration with backfill and bounded inbound compatibility.

## Legacy inbound route classification

The current compatibility routes have been inspected and are not authorization
or RLS authorities. They only redirect already-resolved Workspace requests:

| Surface | Current behavior | Classification |
| --- | --- | --- |
| `/contact/**` | Redirects old bookmarks to the Party list | DEFER TO LATER PHASE |
| `/girvi/**` | Redirects old bookmarks to the Loans list | DEFER TO LATER PHASE |
| Listed `/notify/...` routes | Redirect compatible legacy entry points to Notify v2 batch history | DEFER TO LATER PHASE |
| `/company_dashboard/` | Redirects through explicit Workspace resolution to the canonical slug dashboard | DEFER TO LATER PHASE |
| Integer `/workspace/<id>/...` and `/orgs/...` routes | Inbound control-plane compatibility for pre-slug links | DEFER TO LATER PHASE |

Deleting these routes now would break bookmarks and external links without
materially simplifying the RLS boundary. Remove them only after route telemetry
or an explicit compatibility deadline shows that callers have migrated. The
legacy Notify URLConf intentionally enumerates known paths instead of accepting
an unrestricted catch-all.
