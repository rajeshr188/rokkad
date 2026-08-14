---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, public, auth, aliases, review]
related:
  - docs/ui/public_auth_alias_template_rollout_plan.md
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/phase8_regression_consolidation_review.md
---

# Public/Auth Alias and Template Rollout Review

This review closes the public/auth alias and template rollout phase that followed Phase 8 regression consolidation.

The phase intentionally stops before the full `/w/<workspace_slug>/...` route-map rollout. That route-map needs its own resolution design because current canonical settings aliases use workspace ids, while the target map uses workspace slugs.

## Completed Scope

- Added `docs/ui/public_auth_alias_template_rollout_plan.md`.
- Added `django_project/test_public_auth_alias_template_rollout_intent.py`.
- Added `/pricing/` with route name `pricing` through `PricingPageView`.
- Added public templates:
  - `templates/pages/pricing.html`
  - `templates/pages/tenant.html`
  - `templates/pages/cancellation_and_refund.html`
  - `templates/pages/contact.html`
  - `templates/pages/help.html`
  - `templates/pages/faq.html`
- Added pricing card support classes to `static/css/public.css`.
- Added short auth redirect aliases:
  - `/login/` -> `/accounts/login/`
  - `/signup/` -> `/accounts/signup/`
  - `/password/reset/` -> `/accounts/password/reset/`
- Added `/invitations/accept/<key>` as `public_invitation_accept`, pointing to `apps.orgs.views.team_accept_invitation`.

## Compatibility Findings

- Existing allauth `/accounts/...` paths remain the implementation paths.
- Existing django-invitations `/invitations/accept-invite/<key>` remains available.
- Short auth aliases preserve query strings, including `next`.
- The new public invitation alias uses the orgs-owned adapter already characterized in Phase 4 and guarded in Phase 8.
- `/contact/` remains a route-boundary ambiguity: the public URLConf owns a public `/contact/` page, but the active tenant URLConf treats `/contact/` as a tenant app prefix. Tests avoid using `/contact/` as a representative tenant path and use `/contact/customer/` instead.

## Deferred Scope

- Full `/w/<workspace_slug>/...` route-map rollout.
- Deeper high-fidelity public marketing redesign.
- Customer/member portal route plane.
- Subscription/billing ownership cleanup.

## Verification

Recommended verification before committing this phase:

```powershell
.venv314\Scripts\python.exe manage.py test django_project.test_public_auth_alias_template_rollout_intent django_project.test_route_intent django_project.test_phase7_public_auth_intent django_project.test_phase7_public_auth_render_smoke django_project.test_phase8_regression_consolidation_intent --keepdb
.venv314\Scripts\python.exe manage.py check
.venv314\Scripts\python.exe -m compileall django_project pages
git diff --check
```

Expected log noise:

- Invalid invitation accept paths deliberately return HTTP 410 in render compatibility tests.
- `git diff --check` may report CRLF normalization warnings on Windows; those are not whitespace errors.

## Commit Boundary

This phase can be committed as one set covering:

- public/auth alias-template plan and review;
- route aliases for pricing, short auth redirects, and public invitation accept;
- missing public templates;
- focused public CSS additions;
- route/render/intent test updates;
- status, memory, and audit updates.

## Next Recommended Step

Commit this public/auth alias-template phase, then start a separate `/w/<workspace_slug>/...` route-map planning phase before adding slug routes.
