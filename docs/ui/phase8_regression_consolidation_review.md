---
status: active
owner: ui
updated: 2026-06-30
tags: [ui, saas-ia, phase-8, regression, review]
related:
  - docs/ui/saas_information_architecture_audit.md
  - docs/ui/phase8_regression_consolidation_plan.md
  - docs/ui/phase7_modern_fintech_ui_polish_review.md
  - docs/ui/authorization_cleanup_inventory.md
---

# Phase 8 Regression Consolidation Review

Phase 8 is complete as the regression and documentation closeout for the current SaaS information architecture plan.

This phase intentionally did not add new routes, remove compatibility URLs, redesign screens, create missing public templates, or roll out the full `/w/<workspace_slug>/...` target map. It strengthened guardrails first so those deferred changes can be handled in smaller follow-on phases.

## Completed Scope

- Added `docs/ui/phase8_regression_consolidation_plan.md` as the regression-first implementation plan.
- Added `django_project/test_phase8_regression_consolidation_intent.py` to guard Phase 8 scope, guard-file inventory, regression buckets, and deferred alias/design work.
- Strengthened route-boundary tests for current `/app/...` and `/workspace/<id>/settings/...` aliases, legacy URLs, tenant ERP prefixes, public URLConf tenant exclusion, and intentionally absent future aliases.
- Strengthened template/shell tests for base-template ownership, static stylesheet ownership, no inline-style reintroduction in extracted shells, and documented root shell inline-style debt.
- Strengthened public/auth render tests for current renderable public pages, allauth login/signup/password reset, Google OAuth CTA gating, current django-invitations compatibility, invalid invite fail-closed behavior, and documented missing public templates.
- Strengthened workspace/setup/onboarding tests for canonical and legacy setup routes, canonical setup-state form targets, membership-safe workspace switching, safe `next` handling, audit logging, and existing onboarding runtime regression files.
- Strengthened invitation/team tests for direct accept adapter behavior, authenticated email mismatch fail-closed behavior, sent-invitation workspace context, revoke return targets, role/member mutation boundaries, control-plane policy checks, and invitation/team audit actions.
- Strengthened authorization tests for exact tenant ERP prefix coverage, middleware workspace-required coverage, Party/Product/Rates/Notify/utility data-tool guards, Contact's documented legacy gap, the intentionally public Notify v2 webhook, and DEA/Girvi as separate domain-specific permission tracks.

## Deferred Scope

- `/pricing/`
- Short auth aliases: `/login/`, `/signup/`, `/password/reset/`
- Public invitation alias: `/invitations/accept/<key>`
- Missing public templates referenced by `pages.views`
- Full `/w/<workspace_slug>/...` tenant route-map rollout
- Deeper high-fidelity product redesign
- Full customer/member portal route plane
- Subscription/billing ownership cleanup and gating
- DEA and Girvi domain-specific permission hardening beyond the generic SaaS route-group scope

## Compatibility Findings

- Existing `/accounts/...`, `/invitations/accept-invite/<key>`, `/orgs/...`, `/app/...`, and `/workspace/<id>/settings/...` routes remain compatibility-stable.
- The current public/auth short aliases are still absent by design.
- `/contact/` remains a mixed-boundary naming risk: it is a public page path in the public URLConf and a tenant Contact prefix in the tenant URLConf.
- Missing public templates for `/tenant/`, `/cancellation-and-refund/`, `/help/`, and `/faq/` remain documented debt.
- Workspace setup remains advisory and non-blocking.
- Contact broad cleanup remains skipped in favor of Party cutover.

## Verification

Commands used for Phase 8.8 review:

```powershell
.venv314\Scripts\python.exe manage.py test django_project.test_phase8_regression_consolidation_intent django_project.test_route_intent django_project.test_template_layout_intent django_project.test_phase7_public_auth_intent django_project.test_phase7_public_auth_render_smoke django_project.test_shell_render_smoke django_project.test_onboarding_phase6_intent django_project.test_invitation_team_flow_intent django_project.test_authorization_surface_intent apps.onboarding.tests_setup_checklist apps.onboarding.tests_setup_state apps.onboarding.tests_completion_redirects --keepdb
.venv314\Scripts\python.exe manage.py check
.venv314\Scripts\python.exe -m compileall django_project
git diff --check
```

Expected log noise:

- `django_project.test_phase7_public_auth_render_smoke` deliberately exercises currently missing public templates and asserts they remain documented. Django logs `TemplateDoesNotExist` stack traces for those requests while the tests still pass.
- Invalid current invitation accept links deliberately return HTTP 410 during render compatibility tests.
- `git diff --check` may report CRLF normalization warnings on Windows; those are not whitespace errors.

## Commit Boundary

Phase 8 can be committed as one phase-level set covering regression tests and documentation only.

No runtime URL behavior, template rendering behavior, authorization behavior, onboarding behavior, or invitation/team behavior should be included in this commit beyond test/documentation guard updates.

## Next Recommended Step

Commit the Phase 8 set, then start a new follow-on phase for the deferred public/auth and route-map rollout:

- implement `/pricing/` and missing public templates;
- add short auth aliases as compatibility aliases or redirects;
- add `/invitations/accept/<key>` as an explicit alias to the orgs-owned accept adapter;
- plan the full `/w/<workspace_slug>/...` route-map rollout as an incremental alias/redirect phase.
