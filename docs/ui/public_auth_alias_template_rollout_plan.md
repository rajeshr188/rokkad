---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, public, auth, aliases, routes]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/phase8_regression_consolidation_review.md
  - docs/ui/phase7_public_auth_polish_plan.md
  - docs/ui/route_template_inventory.md
---

# Public/Auth Alias and Template Rollout Plan

This phase follows the Phase 8 regression closeout. It implements the deferred public/auth and route-map work incrementally, with compatibility URLs preserved until each alias is proven stable.

## Goal

Move the product closer to the SaaS IA target route map without a big-bang URL rewrite:

- add `/pricing/`;
- create missing public templates referenced by `pages.views`;
- add short auth aliases for login, signup, and password reset;
- add `/invitations/accept/<key>` as an orgs-owned invitation accept alias;
- plan the full `/w/<workspace_slug>/...` route-map rollout separately after public/auth aliases are stable.

## Non-Goals

- Do not remove `/accounts/...`, `/invitations/accept-invite/<key>`, `/orgs/...`, `/app/...`, or `/workspace/<id>/settings/...` compatibility routes.
- Do not implement `/w/<workspace_slug>/...` in the same slice as public/auth aliases.
- Do not redesign public/auth pages deeply; keep visual polish focused and compatible with `base_public.html`, `base_auth.html`, and `static/css/public.css`.
- Do not route tenant ERP business data into public pages.

## Current Baseline

Current implemented routes:

- `/`
- `/about/`
- `/privacy-policy/`
- `/terms-and-conditions/`
- `/contact/` in the public URLConf
- `/accounts/login/`
- `/accounts/signup/`
- `/accounts/password/reset/`
- `/invitations/accept-invite/<key>`

Current missing or deferred routes/templates:

- `/login/`
- `/signup/`
- `/password/reset/`
- `/invitations/accept/<key>`
- `/w/<workspace_slug>/...`

Current ambiguity:

- `/contact/` is a public page path in the public URLConf and a tenant Contact prefix in the tenant URLConf. Do not use `/contact/` as a representative tenant route in future public URLConf tests; use child paths such as `/contact/customer/`.

## Safe Implementation Slices

### Phase 9.1: Plan And Guard Baseline

Status: complete.

Add this plan and guard tests only. Keep runtime behavior unchanged. Guard the current absence of deferred aliases so the next slices can prove exactly what changed.

### Phase 9.2: Pricing And Missing Public Templates

Status: complete.

Add:

- `PricingPageView`
- `templates/pages/pricing.html`
- `templates/pages/tenant.html`
- `templates/pages/cancellation_and_refund.html`
- `templates/pages/contact.html`
- `templates/pages/help.html`
- `templates/pages/faq.html`
- route name `pricing` at `/pricing/`
- missing templates for tenant, cancellation/refund, contact, help, and FAQ pages

Acceptance:

- Public pages render through `base_public.html`.
- Public pages load `css/public.css`.
- No tenant ERP data is queried.
- Existing `/about/`, `/privacy-policy/`, `/terms-and-conditions/`, and `/contact/` behavior stays compatible.

### Phase 9.3: Short Auth Aliases

Status: complete.

Add aliases or redirects:

- `/login/` -> allauth login
- `/signup/` -> allauth signup
- `/password/reset/` -> allauth password reset

Preferred behavior:

- Use redirects or thin alias views that preserve allauth form handling, CSRF behavior, `next`, social login context, and route names.
- Keep `/accounts/...` as the canonical compatibility implementation until all templates and integrations are verified.

### Phase 9.4: Public Invitation Accept Alias

Status: complete.

Add:

- `/invitations/accept/<key>` as an alias to the orgs-owned `team_accept_invitation` adapter.

Acceptance:

- Authenticated matching users accept through `apps.orgs.services.control_plane.accept_invitation`.
- Authenticated email mismatches fail closed.
- Unauthenticated users retain django-invitations fallback behavior.
- Existing `/invitations/accept-invite/<key>` remains available.

### Phase 9.5: Public/Auth Alias Review

Status: complete.

Review route behavior, render behavior, compatibility paths, docs, and tests before starting `/w/<workspace_slug>/...`.

### Future Phase: `/w/<workspace_slug>/...` Route Map

Roll out the target workspace route map as a separate alias/redirect phase:

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

This needs its own route-resolution design because the current active tenant model supports domain resolution plus path/profile fallback, while canonical settings aliases currently use workspace id, not slug.

## Tests To Add Or Update

- Route tests proving `/pricing/` and public templates render.
- Render tests replacing the Phase 8 missing-template assertions once templates exist.
- Alias tests for `/login/`, `/signup/`, `/password/reset/`.
- Invitation alias tests for `/invitations/accept/<key>`.
- Public URLConf tests proving tenant ERP child paths remain excluded.
- Compatibility tests proving old allauth and django-invitations paths still work.

## Next Recommended Step

Commit this public/auth alias-template phase, then start a separate `/w/<workspace_slug>/...` route-map planning phase before adding slug routes.
