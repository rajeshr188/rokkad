---
status: accepted
owner: project
updated: 2026-08-17
tags: [adr, workspace, cleanup, routing, migrations]
related:
  - 2026-08-14-shared-schema-workspace-rls-tenancy.md
  - 2026-08-17-workspace-request-authority-and-rls-context.md
  - ../implementation/control-plane-phase7-residue-cleanup.md
---

# Transitional tenancy names after the RLS cutover

## Context

The runtime now uses one shared PostgreSQL schema with forced RLS, but two
schema-era names remain:

- the Python package `apps.tenant_apps` contains the supported Party, Loans,
  Notify v2, and Rates business apps;
- `Company.schema_name` is the unique identifier used as the Workspace route
  slug and registered-domain label.

The package name occurs in 197 live source files and three migration files.
Renaming it would create a broad import and migration serialization change
without altering runtime isolation. `schema_name` is read by middleware,
control-plane services, onboarding, subscriptions, URL generation, tests, and
commands. Renaming that field in place would change the live routing contract.

Neither name selects a PostgreSQL schema, changes `search_path`, or establishes
RLS context. RLS context is established only from the resolved Workspace ID.

## Decision

1. Keep `apps.tenant_apps` as a transitional package name. Do not add behavior
   that interprets it as a schema boundary. Reconsider only as a dedicated
   repository-wide package migration with migration-import compatibility.
2. Keep `Company.schema_name` temporarily as the persisted compatibility
   routing key. Treat its value as a Workspace slug, never as a database schema.
3. Do not rename `schema_name` in place. A later routing migration will add an
   immutable, unique `Company.slug`, backfill it from `schema_name`, dual-read
   old inbound links for a bounded period, switch URL generation and domain
   resolution to `slug`, and remove `schema_name` only after callers and data
   are verified.
4. New runtime code should use Workspace terminology. It may read
   `schema_name` only where the current routing compatibility key is required.

## Consequences

Phase 7 can finish without a high-churn rename that provides no security or
domain benefit. Some naming debt remains visible, but the architectural
boundary is explicit and testable. The future slug migration is a data and URL
compatibility change and therefore belongs in its own phase with redirects,
constraints, and rollback coverage.

## Future slug migration gates

- `slug` is non-null, unique, indexed, immutable after creation, and rejects
  the reserved `public` value;
- all canonical `/w/<slug>/...` generation uses `Company.slug`;
- domains and explicit paths resolve the same Workspace or fail closed;
- old `schema_name` links have a documented compatibility deadline;
- RLS continues to use only the numeric Workspace ID;
- migration drift, route intent, two-Workspace isolation, and invitation and
  subscription flows pass before the old field is removed.
