---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, phase-7, public, auth, visual-polish]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/phase7_modern_fintech_ui_polish_plan.md
  - docs/ui/route_template_inventory.md
---

# Phase 7.6 Public/Auth Polish Plan

Phase 7.6 is an inventory and guard-test slice before changing public or authentication visuals. No route changes are included in this slice.

The goal is to prepare the public SaaS funnel and authentication surfaces for a fintech-style polish pass without changing routes, form actions, django-allauth behavior, django-invitations behavior, redirects, middleware, permissions, or schema boundaries.

## Current Route Inventory

Current public/platform routes are owned by `pages.urls` through `PUBLIC_PLATFORM_URLPATTERNS` in `django_project.shared_urlpatterns`.

Active public page routes:

- `/` -> `home`
- `/about/` -> `about`
- `/tenant/` -> `tenant`
- `/privacy-policy/` -> `privacy_policy`
- `/cancellation-and-refund/` -> `cancellation_and_refund`
- `/terms-and-conditions/` -> `terms_and_conditions`
- `/contact/` -> `contact`
- `/help/` -> `help`
- `/faq/` -> `faq`

Compatibility public/global routes still mixed into `pages.urls`:

- `/dashboard/` -> `dashboard`
- `/company_dashboard/` -> `company_dashboard`
- `/workspace/` -> `workspace_home`
- `/invitations/` -> `workspace_invitations`
- `/workspace/<workspace_id>/select/` -> `workspace_select`
- `/download-templates/` -> `download_template_pack`

Authentication and invitation entrypoints are owned by `AUTH_URLPATTERNS`:

- `/accounts/...` -> django-allauth account routes
- `/accounts/...` -> django-allauth socialaccount routes
- `/invitations/...` -> django-invitations routes

## Current Template Inventory

Public page templates that already use `base_public.html`:

- `templates/pages/home.html`
- `templates/pages/about.html`
- `templates/pages/privacy_policy.html`
- `templates/pages/terms_and_conditions.html`

Authentication templates that already use `base_auth.html`:

- `templates/account/login.html`
- `templates/account/logout.html`
- `templates/account/signup.html`
- `templates/account/password_reset.html`
- `templates/account/password_reset_done.html`
- `templates/account/password_reset_from_key.html`
- `templates/account/password_reset_from_key_done.html`
- `templates/account/password_change.html`
- `templates/account/password_set.html`

Authenticated account/global templates correctly stay on `base_global.html`:

- `templates/account/userprofile_detail.html`
- `templates/account/userprofile_form.html`
- `templates/account/workspace_management.html`

## Gaps To Keep Visible

- The target `/pricing/` route from the SaaS IA target map is not implemented yet.
- The target short auth aliases `/login/`, `/signup/`, and `/password/reset/` are not implemented yet; current compatibility paths remain allauth `/accounts/...`.
- The target `/invitations/accept/<key>` shape is not implemented yet; current direct accept behavior remains owned by django-invitations plus the orgs adapter characterized in Phase 4.
- Some `pages.views` classes reference templates that are not present in the current template tree: `pages/tenant.html`, `pages/cancellation_and_refund.html`, `pages/contact.html`, `pages/help.html`, and `pages/faq.html`.
- `templates/pages/home.html` contains legacy inline gradient-heavy CSS, placeholder remote imagery, and mojibake in the rupee statistic. The next visual pass should replace this with a restrained product-specific SaaS funnel.
- `templates/account/login.html` and `templates/account/signup.html` preserve working allauth/social-auth forms, but their layout is visually inconsistent with the desired fintech funnel.

These are intentionally recorded as future work. Phase 7.6 does not implement missing routes or missing templates.

## Guardrails For The Next Visual Slice

- Keep `base_public.html` for public marketing/legal pages.
- Keep `base_auth.html` for login, signup, logout, password reset, password change, and password set templates.
- Keep authenticated profile/workspace-management account pages on `base_global.html`.
- Preserve all form `method`, CSRF tokens, allauth route names, social login provider URLs, and django-invitations entrypoints.
- Do not move public pages into the management shell.
- Do not add tenant ERP data, selected-workspace business data, or workspace settings navigation to public/auth pages.
- Do not implement the full `/w/<workspace_slug>/...` target route map in this visual-polish slice.

Phase 7.7 completed the first public/auth visual pass:

- `static/css/public.css` now owns the shared public/auth visual vocabulary;
- `base_public.html` and `base_auth.html` load that stylesheet and use full-width public/auth shell wrappers;
- `templates/pages/home.html` no longer carries inline landing-page CSS or the remote placeholder dashboard image;
- `templates/account/login.html`, `templates/account/signup.html`, and `templates/account/password_reset.html` now share the same auth panel/card vocabulary;
- allauth form methods, CSRF tokens, Google social login URLs, and password-reset form action are preserved;
- pricing and short auth aliases remain a separate future route-alias phase.

## Next Recommended Slice

Phase 7.8 completed the first public/auth render review:

- `/` renders the Phase 7.7 public funnel with the shared `css/public.css` stylesheet;
- `/accounts/login/`, `/accounts/signup/`, and `/accounts/password/reset/` render with the auth shell and shared auth layout;
- auth pages no longer crash when a Google client id exists but no django-allauth `SocialApp` is configured;
- Google CTA and Google One Tap markup are shown only when `GOOGLE_OAUTH_ENABLED` is true;
- render smoke coverage now guards the no-`SocialApp` case.

## Next Recommended Slice

Proceed with Phase 7.9: polish tenant ERP dashboard/navigation density without changing business workflows, route names, tenant isolation, or posting behavior.
