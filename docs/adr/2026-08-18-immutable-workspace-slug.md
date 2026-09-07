---
status: accepted
owner: project
updated: 2026-08-18
tags: [workspace, routing, slug, rls]
related: [../architecture/control-plane-contracts.md, ../implementation/workspace-slug-migration.md]
---

# Immutable Workspace slug

## Decision

`Company.slug` is the sole Workspace identifier accepted by canonical
`/w/<workspace_slug>/...` routes. It is unique, non-null, URL-safe, assigned at
creation, and immutable after the first save.

`Company.schema_name` remains legacy schema-tenancy metadata. It may still be
used by explicitly historical backup/import code, but it is not request identity
and must not be queried by Workspace path resolution.

## Request contract

Domain lookup and slug-path lookup independently resolve a `Company`. If both
are present they must resolve the same row. Membership validation then establishes
`request.workspace` and `workspace_context(workspace.id)` exactly as before.
`UserProfile.workspace` remains navigation preference only.

## Migration

Existing rows are processed in primary-key order. The initial slug is
`slugify(schema_name or name)`; empty values use `workspace-<id>`, and collisions
receive deterministic numeric suffixes. No Workspace or business data is deleted.

Legacy schema-name paths are not retained as a second route identity. They fail
closed. A future rename requires a deliberate redirect/alias model and audited
workflow rather than mutating `Company.slug`.

## Consequences

- Workspace display-name changes do not change URLs.
- PostgreSQL RLS continues to use numeric Workspace IDs.
- Domain routing is unchanged except that newly generated subdomains use the
  canonical slug.
- Historical `schema_name` terminology can be retired separately.
