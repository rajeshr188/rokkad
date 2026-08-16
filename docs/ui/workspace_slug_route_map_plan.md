---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, routes, workspace, tenant]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/public_auth_alias_template_rollout_review.md
  - docs/ui/canonical_route_aliases_plan.md
  - docs/ui/route_template_inventory.md
---

# Workspace Slug Route Map Plan

This phase follows the public/auth alias-template rollout. It plans the full
target `/w/<workspace_slug>/...` route map before adding runtime slug routes.

## Goal

Introduce workspace-scoped SaaS URLs incrementally while preserving the current
working routes:

- `/app/...` global control-plane aliases;
- `/workspace/<id>/settings/...` workspace settings aliases;
- `/orgs/...` compatibility routes;
- tenant ERP prefixes such as `/party/`, `/girvi/`, `/product/`, `/dea/`.

The desired future route family is:

- `/w/<workspace_slug>/`
- `/w/<workspace_slug>/operations/`
- `/w/<workspace_slug>/parties/`
- `/w/<workspace_slug>/sales/`
- `/w/<workspace_slug>/purchase/`
- `/w/<workspace_slug>/loans/`
- `/w/<workspace_slug>/inventory/`
- `/w/<workspace_slug>/commodity/`
- `/w/<workspace_slug>/accounting/`
- `/w/<workspace_slug>/reports/`
- `/w/<workspace_slug>/settings/...`

## Non-Goals

- Do not add slug routes until the slug source and middleware behavior are
  explicitly designed.
- Do not remove current id-based workspace settings aliases.
- Do not remove current tenant ERP prefixes.
- Do not turn the public URLConf into a tenant ERP URLConf.
- Do not use the deprecated Contact app as the canonical Parties route target.

## Current Baseline

Current workspace identity sources:

- Domain mapping through the ordinary shared `orgs.Domain` model.
- Path workspace id extraction for `/orgs/workspace/<id>/...`,
  `/orgs/company/<id>/...`, and `/workspace/<id>/settings/...`.
- User profile fallback during the current transition.

Current gap:

- `Company` has `schema_name`, but no explicit user-facing slug field.
- The schema name is not automatically a product-safe public slug because it is
  also database/schema infrastructure.
- Current settings aliases use workspace ids, not slugs.
- Current tenant ERP routes assume the selected tenant/schema context and do not
  carry a workspace slug in the path.

## Decisions Required Before Runtime Routes

1. Slug source

   Decide whether `/w/<workspace_slug>/...` uses `Company.schema_name` as a
   compatibility slug or adds a separate immutable `slug` field. A separate slug
   is cleaner for long-term product URLs, but it requires a shared-schema
   migration and uniqueness/backfill policy.

2. Slug resolver ownership

   Slug extraction should belong beside the existing workspace path resolution
   in `SecureWorkspaceMiddleware`, not inside individual tenant app views.

3. Domain/path conflict policy

   Domain mapping should remain authoritative. If a request arrives on a tenant
   domain for workspace A with `/w/workspace-b/...`, the request must fail
   closed or redirect to the domain workspace, matching the existing id mismatch
   guard.

4. Membership check order

   Slug resolution must not switch schema before membership/subscription checks.
   The existing middleware contract validates access before setting tenant
   context and must remain intact.

5. Canonical route targets

   First implementation should use thin redirect/alias views:

   | Future URL | Initial Target |
   | --- | --- |
   | `/w/<slug>/` | workspace dashboard for the resolved workspace |
   | `/w/<slug>/parties/` | `party_list` |
   | `/w/<slug>/loans/` | Girvi dashboard/list entrypoint |
   | `/w/<slug>/inventory/` | Product/stock entrypoint |
   | `/w/<slug>/accounting/` | DEA dashboard |
   | `/w/<slug>/settings/` | workspace settings home |
   | `/w/<slug>/settings/preferences/` | dynamic preferences builder |
   | `/w/<slug>/settings/team/` | workspace team list |
   | `/w/<slug>/settings/invitations/` | sent workspace invitations |

   Sales, purchase, operations, commodity, reports, roles, billing, modules,
   numbering, security, and portal paths should either redirect to the nearest
   current surface or return a clear "not available yet" placeholder only after
   product ownership is decided.

6. Navigation rollout

   Do not switch all navigation at once. Add slug aliases, add tests, then move
   one navigation cluster at a time from id/settings or tenant-prefix URLs.

## Safe Implementation Slices

### Phase 10.1: Plan And Guard Baseline

Status: complete.

Add this plan and guard tests only. Runtime behavior stays unchanged and
`/w/<workspace_slug>/...` remains intentionally absent.

### Phase 10.2: Slug Source Decision

Status: complete.

Decide and document whether the product uses `schema_name` as the initial slug
or adds a dedicated `Company.slug`.

Decision:

Use `Company.schema_name` as the initial compatibility slug for `/w/<workspace_slug>/...`
aliases.

Rationale:

- It already exists on the shared `Company` tenant model.
- It is already unique enough for tenant schema resolution.
- It avoids a shared-schema migration while route behavior is still being
  proven.
- It keeps the rollout focused on URL/middleware safety, not workspace rename
  product policy.

Constraints:

- Treat this as a compatibility slug, not a final branded workspace URL system.
- Do not expose schema names as editable marketing slugs.
- Do not promise slug rename support in this phase.
- Revisit a dedicated immutable `Company.slug` only after the route-map is
  stable and workspace rename/branding requirements are clear.

Rejected for now:

- Adding `Company.slug` immediately. This is cleaner long term, but it would
  require a shared-schema migration, backfill, uniqueness rules, admin/forms
  decisions, and redirect policy before the route-map itself is proven.

Compatibility implications:

- no migration is needed;
- route docs must state this is a compatibility slug;
- future rename behavior remains constrained.

### Phase 10.3: Middleware Slug Extraction

Status: complete.

Teach `SecureWorkspaceMiddleware` to extract `/w/<workspace_slug>/...` as a path
workspace candidate, preserving the existing domain/path mismatch and
membership-before-tenant-context order.

Implemented baseline:

- `SecureWorkspaceMiddleware.WORKSPACE_SLUG_PATTERNS` recognizes future
  `/w/<workspace_slug>/...` paths.
- `_extract_workspace_slug_from_path()` extracts the slug.
- `_resolve_workspace_from_path()` resolves slug paths by `Company.schema_name`
  after existing id-based paths and ignores the public schema slug.
- No URL patterns have been added yet, so `/w/<workspace_slug>/...` still does
  not resolve at the Django URL layer.

### Phase 10.4: Add Minimal Slug Aliases

Status: complete.

Add the smallest live route set first:

- `/w/<workspace_slug>/`
- `/w/<workspace_slug>/settings/`
- `/w/<workspace_slug>/settings/preferences/`
- `/w/<workspace_slug>/settings/team/`
- `/w/<workspace_slug>/settings/invitations/`

These should target existing working views or redirects without changing tenant
business workflows.

Implemented baseline:

- `CANONICAL_WORKSPACE_SLUG_URLPATTERNS` is included after current
  control-plane aliases.
- Slug aliases resolve in both current public and tenant URLConfs because the
  project still shares authenticated/global routes during this transition.
- Slug views redirect to existing id-based dashboard/settings views after
  resolving `Company.schema_name`.
- Tenant ERP section aliases such as `/w/<workspace_slug>/parties/`,
  `/w/<workspace_slug>/loans/`, `/w/<workspace_slug>/inventory/`, and
  `/w/<workspace_slug>/accounting/` remain intentionally absent.

### Phase 10.5: Add Tenant ERP Section Aliases

Status: complete.

Add section aliases in small groups, preferring redirects to existing tenant
entrypoints at first:

- parties -> Party
- loans -> Girvi
- inventory -> Product/stock
- accounting -> DEA
- reports -> existing DEA/Girvi report entrypoints where appropriate

Skip Contact because Party is the canonical replacement.

Implemented baseline:

- `/w/<workspace_slug>/parties/` redirects to `party_list`.
- `/w/<workspace_slug>/loans/` redirects to `girvi_dashboard`.
- `/w/<workspace_slug>/inventory/` redirects to `product_product_home`.
- `/w/<workspace_slug>/accounting/` redirects to `dea_home`.
- `/w/<workspace_slug>/contact/` remains absent because Contact is being
  phased out in favor of Party.
- Operations, sales, purchase, commodity, and reports remain absent until their
  product targets are selected.

### Phase 10.6: Navigation Cutover

Status: complete.

Move tenant topbar/sidebar/settings links to slug aliases after route and
middleware coverage is stable. Keep old URLs available.

Implemented baseline:

- Tenant sidebar dashboard link now targets `workspace_slug_dashboard`.
- Tenant sidebar Parties, Girvi, and Product links now target
  `workspace_slug_parties`, `workspace_slug_loans`, and
  `workspace_slug_inventory`.
- Workspace settings sidebar home, preferences, team, and sent invitations now
  target slug aliases when `ew.schema_name` is available.
- Setup, invite member, subscription, reports, business events, commodity,
  accounting tools, rates, notifications, and data tools remain on current
  working routes until dedicated aliases are introduced.

### Phase 10.7: Review And Commit

Status: complete.

Review route resolution, redirects, middleware behavior, docs, and tests before
committing the full slug route-map phase.

Review is documented in `docs/ui/workspace_slug_route_map_review.md`.

## Tests Needed

- Route absence tests for Phase 10.1.
- Slug resolver tests covering domain, path, profile, and mismatch cases.
- Membership-before-schema-switch tests for slug paths.
- Public URLConf exclusion tests for tenant ERP slug paths.
- Tenant URLConf resolution tests for each live slug alias.
- Redirect target tests proving old route names and paths still work.
- Navigation tests proving workspace identity is visible and stable.

## Next Recommended Step

Proceed with Phase 10.7: review the workspace slug route-map phase, run the
focused regression set, and prepare the phase-level commit.
