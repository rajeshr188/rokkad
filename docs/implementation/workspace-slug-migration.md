---
status: complete
owner: project
updated: 2026-09-08
tags: [workspace, routing, migration, phase-11]
related: [../adr/2026-08-18-immutable-workspace-slug.md, ../architecture/current-workspace-resolution-chain-using-postgres-rls.md]
---

# Phase 11 Workspace slug migration

## Pre-migration `schema_name` inventory

Every active occurrence was classified before cutover:

| Category | Previous uses | Phase 11 treatment |
|---|---|---|
| Routing identity | Middleware path lookup, org wrapper lookup, Workspace reversals, billing redirects, Phase 10 client helpers | Replaced with `Company.slug` |
| Visible links | Management shell, Workspace switcher/sidebar/settings, Party, Loans, subscriptions, setup and invitation templates | Replaced with `.slug` |
| Provisioning | Workspace creation, onboarding creation and generated Domain name | Creation now assigns a collision-safe slug; Domain uses it |
| Compatibility tests | `SimpleNamespace` route fixtures, route-map/source guards, Phase 10 browser contract | Updated to provide/assert `slug` |
| Legacy django-tenants residue | `Company.schema_name`, `build_schema_name`, public-schema checks, backup/import arguments and smoke-command labels | Retained as non-routing historical metadata |
| Documentation/history | Earlier route-map decisions that explicitly selected `schema_name` temporarily | Preserved as historical decisions; current architecture docs supersede them |

## Canonical resolution

```text
domain (optional) ──> Domain.tenant ─┐
                                    ├─ identities must agree
/w/<slug>/... ──> Company.slug ─────┘
                                    ↓
                             Membership/access
                                    ↓
                            request.workspace
                                    ↓
                       workspace_context(workspace.id)
                                    ↓
                         PostgreSQL forced RLS
```

No profile fallback or schema-name lookup participates in this chain.

## Development-data migration

Migration `orgs.0005_company_immutable_slug` adds a nullable character field,
backfills deterministic unique values, then applies the final unique non-null
`SlugField`. Local development rows migrated without collision or deletion.

## Compatibility policy

Unscoped business routes retain their existing explicit-domain compatibility
policy. Old `/w/<schema_name>/...` paths are not retained because the project is
still in development and maintaining two equal Workspace identifiers would
undermine the migration. Unknown or legacy path identifiers fail closed.

## Remaining `schema_name` uses

- The database column and builder remain until broad tenancy-residue cleanup.
- Public-schema compatibility predicates remain historical infrastructure checks.
- Backup/import surfaces whose parameter literally names a legacy schema retain
  that terminology.
- Archived audits and migration files remain immutable historical evidence.

None of these remaining uses resolves a canonical Workspace route.

## Checkpoint verification (2026-09-08)

The fresh-database combined gate passes 664 tests: full Loans discovery, all
orgs/subscriptions test modules, the control-plane and Phase 9 aggregate gates,
Phase 10/11 route contracts, shell rendering, Workspace business entrypoints,
slug-route intent, and invitation/team-flow intent. Use explicit module labels
and `--top-level-directory . --settings django_project.settings.test --noinput`
to avoid loading the same RLS fixtures through different module names.

Django checks, migration drift, applied migrations, and whitespace checks pass.
The read-only SaaS foundation inventory reports four Workspaces and zero
integrity findings. This checkpoint includes the billing dashboard member-count
repair and isolated in-memory test caches.
