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

- classify the `apps.tenant_apps` package name and persisted `schema_name`
  field separately because both have wide migration/import impact;
- remove the now-unused Guardian line from the UTF-16 requirements manifest;
- inventory legacy inbound aliases before deletion.
