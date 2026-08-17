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

Still pending:

- rename the active `tenant_urls` module without changing route behavior;
- classify the `apps.tenant_apps` package name and persisted `schema_name`
  field separately because both have wide migration/import impact;
- remove obsolete schema-oriented management-command options and current docs;
- remove the now-unused Guardian line from the UTF-16 requirements manifest;
- inventory legacy inbound aliases before deletion.
