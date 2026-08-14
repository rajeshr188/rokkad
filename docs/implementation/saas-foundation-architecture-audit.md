---
status: active
owner: project
updated: 2026-08-14
tags: [saas, architecture, tenancy, security, mvp, audit]
related: [../AGENT_MEMORY.md, ../STATUS.md, django-tenants-architecture-audit.md, workspace-context.md, ../ui/authorization_cleanup_inventory.md, ../adr/2026-07-02-tenant-billed-subscription-architecture.md]
---

# SaaS Foundation Architecture Audit

## 1. Executive summary

Rokkad has a credible schema-per-tenant MVP foundation, but it is **not ready for first production deployment without a focused P0 hardening pass**. The public/tenant data split is broadly correct, the request path verifies membership before switching into a tenant schema, and important team-management operations have service and test coverage. The architecture should be simplified in place rather than split into more Django apps.

The launch blockers are concrete:

1. `ALLOW_COMPANY_HARD_DELETE=True` is a destructive production default. A public-admin action can make `Company.hard_delete()` enable schema deletion.
2. Email verification is optional (`ACCOUNT_EMAIL_VERIFICATION = "optional"`) even though invitations and global identity are email-based.
3. Workspace admission combines membership authorization with subscription availability. `SecureWorkspaceMiddleware._validate_workspace_access()` delegates to `SubscriptionAccessService.evaluate_access()`, so billing failure can deny all tenant access, including recovery/support surfaces. A second `SubscriptionValidationMiddleware` repeats the same concern and fails open on exceptions.
4. `UserProfile.workspace` remains a mutable global selected-workspace pointer and middleware still uses it as a tenant-resolution fallback. It is useful UX state, but it must not remain an authority for tenant selection.
5. Ownership has two sources of truth: `Company.owner` and `CompanyOwnership`. The latter has no constraint guaranteeing one active owner and its transfer method does not update `Company.owner`.
6. Invitations also have two persisted concepts: `CompanyInvitation` and `PendingInvitation`. A signal-created compatibility row adds state and lifecycle ambiguity without being the invitation authority.
7. RBAC evaluation is centralized enough to retain, but its implementation mixes a hard-coded role map, Django `Permission` rows, and installed-but-lightly-used Guardian object permissions. Role names are global and case-sensitive business keys.
8. Tenant provisioning is synchronous and spans irreversible schema creation/seeding plus public rows. Failure recovery is not modeled as a lifecycle state.
9. Background/command tenant context is inconsistent. Most new work is explicit, but at least `girvi.management.commands.import_statement_items` uses a display name as a schema identifier, and task safety is not enforced by one common boundary.
10. Production observability is partial: schema-aware logs and public audit rows exist, but correlation IDs, provisioning/job failure visibility, unknown-domain monitoring, and immutable operator event policy are incomplete.

Recommended decision: keep `accounts`, `orgs`, `subscriptions`, and `onboarding`; do not create separate `memberships`, `authorization`, `entitlements`, or `audit` apps for MVP. Make `orgs` the small public control plane, make `subscriptions` the billing/entitlement policy owner, retain tenant business apps, and remove duplicate concepts.

## 2. Scope and method

This is a documentation-only audit. No runtime files, models, migrations, or data were changed. Evidence was taken from current settings, models, middleware, services, views, URLConfs, commands, tests, migrations, active ADRs, and existing audits. Existing documents were treated as leads and checked against runtime code.

The working tree already contained extensive unrelated changes. Conclusions involving those files describe the state inspected on 2026-08-14 and should be revalidated after that work is consolidated.

## 3. Current runtime architecture

### 3.1 Schema ownership

Public schema (`SHARED_APPS`):

- Identity: `accounts.CustomUser`, `UserProfile`, Django auth/session, allauth.
- Tenant registry: `orgs.Company` (`TenantMixin`) and `orgs.Domain` (`DomainMixin`).
- Access graph: `Membership`, `Role`, `CompanyInvitation`.
- Control-plane state: onboarding, subscriptions/billing, platform audit, preferences.

Tenant schemas (`TENANT_APPS`):

- Party/contact, Loans/Girvi, Accounting/DEA, Product/inventory, Rates, Terms, Notify and Notify v2.

This placement is correct for schema tenancy. Global users and memberships must be discoverable before a schema switch; business records must not be.

### 3.2 Request chain

```text
HTTP request
  -> session/authentication (public shared tables)
  -> SecureWorkspaceMiddleware
       -> reset to public for registry reads
       -> resolve domain, path hint, then profile fallback
       -> check domain/path mismatch
       -> authenticate
       -> check public Membership
       -> check SubscriptionAccessService
       -> connection.set_tenant(workspace)
  -> RateMiddleware
  -> SubscriptionValidationMiddleware (second billing check)
  -> tenant URLConf/view
  -> module access helper -> get_effective_permissions()
  -> tenant ORM
```

Evidence: `MIDDLEWARE` in `django_project/settings/base.py`; `apps.orgs.middleware_v2.SecureWorkspaceMiddleware`; `django_project.middleware.SubscriptionValidationMiddleware`.

### 3.3 Workflow reconstruction

| Workflow | Actual chain | Assessment |
|---|---|---|
| Signup/login | allauth URL -> allauth adapter/backend -> public `CustomUser`/email/session -> profile signal -> home/workspace UX | Functional, but verification is optional and Google login-on-GET increases avoidable auth surface. |
| Tenant creation | onboarding/orgs view -> `apps.orgs.services.control_plane` -> public schema -> `Company.save()`/schema creation or clone -> seed command -> `Domain` -> owner `Membership` -> profile selection | Correct responsibilities are emerging; provisioning is not represented as retryable state. |
| Workspace access | middleware domain/path/profile resolution -> public membership -> subscription -> `set_tenant` -> tenant URLConf | Membership-before-switch is strong; profile fallback and billing coupling weaken the boundary. |
| Workspace switch | `accounts.views.switch_workspace`/orgs routes -> membership validation -> update `UserProfile.workspace` -> redirect | Safe only while every destination re-resolves and revalidates. Selected workspace is UX state, not authority. |
| Invitation | team view/form -> control-plane service/`CompanyInvitation.create()` -> synchronous adapter email -> accept view -> membership creation; signals also maintain `PendingInvitation` | One real invitation model plus a redundant shadow model; delivery is coupled to request success. |
| Membership | public `Membership` -> role-policy/control-plane mutations -> `get_effective_permissions()` -> module guards | Good central evaluator; no explicit active state, and role deletion uses `CASCADE`. |
| Ownership | `Company.owner`, owner membership, and optional `CompanyOwnership` history -> ownership service/view where used | Multiple truths; invariant is not database-enforced. |
| Subscription | workspace -> `Subscription` -> `Plan`/snapshot entitlements -> access service -> middleware/decorators/context | Correct public ownership; enforcement and lifecycle semantics remain over-broad/inconsistent. |
| Tenant lifecycle | create -> normal active-by-absence -> `is_deleted` archive/restore -> gated hard delete/schema drop | Missing explicit provisioning/suspended states; hard-delete default is unsafe. |
| Background work | task/command-specific schema argument or loops -> `tenant_context`/`schema_context` -> tenant ORM | No universal contract; safety depends on each implementation. |

## 4. Dependency map

```text
accounts (global identity)
   <- orgs (Company, Domain, Membership, Role, Invitation, Audit)
         <- onboarding (provisioning UX/state)
         <- subscriptions (workspace billing and entitlements)
         <- tenant app access helpers

tenant business apps
   -> orgs tenant-context + permission APIs
   -> subscriptions entitlement API where needed
   -> other tenant-domain facades/selectors
```

Problematic directions:

- `orgs` middleware imports `subscriptions`, making basic tenant admission depend on billing.
- `subscriptions.services` imports membership/invitation models to enforce seats; acceptable at a use-case boundary, but not as a generic access evaluator responsibility.
- Tenant app access modules duplicate nearly identical wrappers around `get_effective_permissions()`.
- Tenant Loans services intentionally enter the public schema for workspace configuration. These crossings need named public-control-plane facades; direct schema switching inside domain services is difficult to review.
- `apps.orgs.models` imports `AuditLog` at module bottom to expose it to migrations, a sign that the public control-plane model module has grown beyond one cohesive unit.

No evidence supports splitting this into microservices or many new Django apps. A small number of explicit service modules is sufficient.

## 5. Architecture scorecard

| Area | Score | Reason |
|---|---:|---|
| Identity & Authentication | 3/5 | allauth and global identity are appropriate; optional verification and unclear destructive user lifecycle remain. |
| Tenant / Workspace Management | 2/5 | creation works, but lifecycle state, provisioning recovery, naming, and ownership invariants need work. |
| Tenant Isolation | 3/5 | correct schema split and membership-before-switch; custom middleware/profile fallback/jobs are material risks. |
| Membership | 3/5 | public unique membership is correct and tested; no active state and unsafe role FK lifecycle. |
| Invitations | 2/5 | functional lifecycle, but duplicate pending state and synchronous delivery complicate correctness. |
| RBAC | 3/5 | one effective-permission API is widely consumed; hard-coded/global roles plus dormant Guardian path need consolidation. |
| Subscription | 2/5 | workspace ownership and provider-event models exist; state enforcement and recovery access are not launch-clean. |
| Entitlements | 2/5 | snapshots/feature rows and a service exist, but absent entitlement often means allowed and checks are not consistently mapped to modules. |
| Audit | 3/5 | useful public audit model and key team events; mutability, generic FK semantics, and coverage policy are incomplete. |
| Notifications | 2/5 | auth/invite email works and tenant Notify v2 is substantial; invitation/auth delivery reliability is still request-coupled. |
| Background Jobs | 2/5 | some explicit tenant loops exist; no enforced schema envelope or universal idempotency/failure contract. |
| Files | 3/5 | tenant storage backend is configured; public and tenant upload authorization/path tests need a focused launch proof. |
| Observability | 2/5 | schema logging exists; request correlation and operational failure dashboards/alerts are missing. |
| Data Lifecycle | 1/5 | archive exists, but deletion/retention/export/user deletion and schema-drop safety are incomplete. |
| Admin / Support | 2/5 | Django admin and audit exist; safe support access and failed-provisioning/billing workflows are insufficient. |
| API / Integrations | 3/5 | current WhatsApp/provider work has signature/idempotency controls; no unified credential/tenant-association policy across integrations. |
| Testing | 3/5 | unusually broad intent/unit coverage; real multi-schema attack, task context, lifecycle, and destructive-operation tests are gaps. |
| Overall Maintainability | 2/5 | good recent service extraction is offset by very large views/models, compatibility routes, duplicate concepts, and overlapping middleware. |

## 6. MVP readiness matrix

| Capability | Status | MVP priority |
|---|---|---:|
| Global identity and sessions | NEEDS CLEANUP | P1 |
| Mandatory verified email | SECURITY RISK | P0 |
| Public/tenant app placement | READY | Retain |
| Membership-before-schema-switch | READY | Retain/test |
| Profile workspace as tenant fallback | ARCHITECTURAL DEFECT | P0 |
| Tenant provisioning | NEEDS CLEANUP | P0 |
| Tenant suspension | MISSING | P0 |
| Safe archive/restore | NEEDS CLEANUP | P1 |
| Hard tenant deletion | SECURITY RISK | P0 |
| Membership uniqueness/access | READY | Retain |
| Membership deactivation | MISSING | P1 |
| Ownership invariant/transfer | ARCHITECTURAL DEFECT | P0 |
| Invitation lifecycle | NEEDS CLEANUP | P1 |
| Central permission evaluation | NEEDS CLEANUP | P1 |
| Guardian object permissions | NOT REQUIRED | Remove/defer |
| Tenant-billed subscription | READY as boundary | Retain |
| Billing recovery access | ARCHITECTURAL DEFECT | P0 |
| Feature/capacity entitlements | NEEDS CLEANUP | P1 |
| Public audit trail | NEEDS CLEANUP | P1 |
| Invitation/auth email | NEEDS CLEANUP | P1 |
| Tenant-aware background jobs | SECURITY RISK | P0 |
| Tenant-aware files | NEEDS CLEANUP | P1 |
| Correlation/health/failure visibility | MISSING | P1 |
| Data export/retention/erasure policy | MISSING | P2 before broad production use |
| Platform support workflow | NEEDS CLEANUP | P1 |
| Enterprise custom RBAC/plans/impersonation | POST-MVP | P3 |

## 7. Detailed findings

### F-01 — Hard deletion is enabled by default

- **Classification:** confirmed security/data-lifecycle defect
- **Severity / priority:** Critical / P0
- **Evidence:** `django_project/settings/base.py` sets `ALLOW_COMPANY_HARD_DELETE=True`; `Company.hard_delete()` sets `auto_drop_schema=True`; `CompanyAdmin.hard_delete_companies` exposes an operator path.
- **Current behavior:** an explicit hard delete can permanently remove the schema with no production-safe configuration default, backup proof, retention delay, or typed confirmation contract.
- **Desired behavior:** normal deletion archives; schema purge is an offline, separately authorized, audited, environment-gated operation after retention and backup checks.
- **Recommended change:** default false via environment, remove bulk hard-delete admin action, introduce a `purge_workspace --schema --confirm-schema` management operation, and audit initiation/completion/failure.
- **Risk of change:** low; may require adjusting tests/dev scripts.

### F-02 — Optional email verification undermines invitation identity

- **Classification:** confirmed security gap
- **Severity / priority:** High / P0
- **Evidence:** `ACCOUNT_EMAIL_VERIFICATION = "optional"`, `ACCOUNT_UNIQUE_EMAIL=True`; invitations bind by email in `CompanyInvitation` and acceptance/team flows.
- **Current behavior:** an unverified account may authenticate while email is the principal invitation/account-recovery identifier.
- **Desired behavior:** mandatory verification before tenant membership acceptance or tenant access; social-provider emails must satisfy provider verification policy.
- **Recommended change:** make verification mandatory in production and test signup, invite-before-signup, account-email change, and recovery.
- **Risk of change:** medium; existing dev users may require verification/reset.

### F-03 — Tenant authority includes profile fallback

- **Classification:** probable isolation defect/design smell
- **Severity / priority:** High / P0
- **Evidence:** middleware resolution order includes `UserProfile.workspace`; `resolve_request_workspace()` correctly makes profile fallback opt-in, showing the intended stricter contract.
- **Current behavior:** routes without a domain/path tenant can inherit a mutable last-selected workspace and then switch schema after membership/billing checks.
- **Why it matters:** membership prevents a direct cross-tenant read, but global URLs can unexpectedly execute tenant-aware behavior, making boundaries and cache/file context harder to prove.
- **Recommended change:** resolve tenant schema only from an authoritative tenant domain or canonical `/w/<slug>/` path. Keep profile selection only for redirects/navigation.
- **Risk of change:** medium; legacy root routes and redirects need inventory.

### F-04 — Billing and membership are coupled in tenant admission

- **Classification:** confirmed architectural defect
- **Severity / priority:** High / P0
- **Evidence:** `SecureWorkspaceMiddleware._validate_workspace_access()` calls `SubscriptionAccessService.evaluate_access()`; `SubscriptionValidationMiddleware` performs another evaluation and catches all exceptions by logging and allowing the request.
- **Current behavior:** no/inactive subscription can prevent entering the schema, while errors in the second layer fail open. Billing dashboards/recovery and read-only export/support behavior are not expressed as policy.
- **Desired behavior:** middleware establishes identity + tenant + membership + tenant lifecycle. A separate policy layer decides product mode (`FULL`, `READ_ONLY`, `BILLING_ONLY`, `SUSPENDED`) and feature entitlements.
- **Recommended change:** remove billing from schema selection; replace the second broad middleware with one explicit access-mode policy after tenant context, with named exempt recovery routes and fail-closed mutation enforcement.
- **Risk of change:** high; all tenant route classes require characterization tests.

### F-05 — Ownership has competing sources of truth

- **Classification:** confirmed integrity defect
- **Severity / priority:** High / P0
- **Evidence:** `Company.owner`, owner `Membership`, and `CompanyOwnership`; `CompanyOwnership.transfer_ownership()` closes/creates history but does not update `Company.owner`; uniqueness only covers `(user, company)`, not one active row.
- **Current behavior:** these records can disagree and authorization may consult different representations.
- **Desired behavior:** `Company.owner` is the sole current-owner pointer; owner membership is mandatory; history is audit data, not authority.
- **Recommended change:** delete `CompanyOwnership` if unused, or convert it to immutable ownership events maintained only by a transactional transfer service. Add constraints/service locks preventing owner removal or multiple owner roles.
- **Risk of change:** medium; data reconciliation and migration required.

### F-06 — Invitation state is duplicated

- **Classification:** confirmed design smell/redundancy
- **Severity / priority:** Medium / P1
- **Evidence:** authoritative `CompanyInvitation` plus signal-maintained `PendingInvitation`; migrations `0016`, `0021`; `apps.orgs.signals` creates/consumes shadow rows.
- **Current behavior:** two tables can represent the same pending intent, with the shadow record used to bridge signup timing.
- **Desired behavior:** `CompanyInvitation` alone owns state. Signup/acceptance queries it by normalized verified email.
- **Recommended change:** characterize all signal flows, migrate any unique information (none is evident), then delete `PendingInvitation` and related signals.
- **Risk of change:** medium; invite-before-signup behavior must remain tested.

### F-07 — RBAC contains three mechanisms

- **Classification:** confirmed maintainability defect
- **Severity / priority:** Medium / P1
- **Evidence:** `Role.permissions` uses Django `Permission`; `RolePermissions` hard-codes sets by role name; Guardian is installed and `decorators_v2.py` reads object perms; most tenant modules consume `get_effective_permissions()`.
- **Current behavior:** the effective evaluator is the practical authority, but the database role permissions and Guardian path make it unclear where a permission originates.
- **Desired behavior:** one MVP model: membership -> one workspace role -> explicit permission codes evaluated through one function. Platform admin is separate.
- **Recommended change:** retain `get_effective_permissions()` as public API; choose DB-backed role permissions or a fixed code policy, not both. For MVP, fixed built-in roles plus optional role rows are simplest. Remove Guardian if no proven object-level assignment remains.
- **Risk of change:** high; create a permission-surface matrix before changing semantics.

### F-08 — Role lifecycle and membership state are weak

- **Classification:** probable integrity defect/missing capability
- **Severity / priority:** Medium / P1
- **Evidence:** `Membership.role` is nullable and `on_delete=CASCADE`; membership has no active/suspended state; role names are globally unique and code compares names.
- **Current behavior:** deleting a role can delete memberships; a null role has unclear access semantics; removal destroys membership history.
- **Desired behavior:** role deletion is protected while assigned; role is non-null after migration; membership supports `ACTIVE`/`SUSPENDED` (or `ended_at`) and removal is auditable.
- **Recommended change:** use `PROTECT`, define a safe default/repair path, and model membership deactivation without enterprise complexity.
- **Risk of change:** medium.

### F-09 — Provisioning has no durable state machine

- **Classification:** confirmed reliability gap
- **Severity / priority:** High / P0
- **Evidence:** control-plane creation performs public rows, schema create/clone, seed command, domain, membership, and profile updates; `TenantMixin.auto_create_schema=True`; optional auto-seed signal exists.
- **Current behavior:** failure can leave a company/schema/domain/seed set partially provisioned, and retry/cleanup depends on operators.
- **Desired behavior:** `PROVISIONING -> ACTIVE` or `PROVISIONING_FAILED`, with idempotent steps and an operator retry. Access is denied until active.
- **Recommended change:** keep synchronous MVP provisioning if desired, but persist status/error/step, use one service, eliminate duplicate auto-seed paths, and define compensation for a failed fresh schema.
- **Risk of change:** high; schema operations are not transactional with ordinary public rows.

### F-10 — Tenant lifecycle is represented by one deletion boolean

- **Classification:** missing capability
- **Severity / priority:** High / P0
- **Evidence:** `Company.is_deleted`, `archive()`, `restore()`; no explicit provisioning, active, suspended, cancellation-pending, or purge state.
- **Current behavior:** billing status is partly used as tenant availability; operational suspension cannot be expressed independently.
- **Desired behavior:** small platform lifecycle: `PROVISIONING`, `ACTIVE`, `SUSPENDED`, `ARCHIVED`, `PROVISIONING_FAILED`. Billing mode is separate.
- **Recommended change:** introduce a constrained status and transactional lifecycle service; retain `is_deleted` only during migration, then remove it.
- **Risk of change:** medium/high.

### F-11 — Subscription semantics are richer than enforcement semantics

- **Classification:** confirmed design gap
- **Severity / priority:** High / P1
- **Evidence:** `Plan` has hard-coded limits/booleans; `SubscriptionEntitlement` and provider events also exist; access rejects `past_due`, `cancelled`, `expired`; missing entitlement is generally treated as enabled.
- **Current behavior:** plan columns, entitlement snapshots, subscription booleans/status, middleware, decorators, and templates can produce different answers.
- **Desired behavior:** one service returns billing access mode and explicit feature/limit decisions. Authorization never asks the billing service whether the member has a role permission.
- **Recommended change:** retain workspace `Subscription`, a small `Plan`, explicit effective entitlements, and provider-event idempotency. Delete speculative unused plan flags after usage search. Define grace/read-only/cancelled behavior.
- **Risk of change:** medium/high.

### F-12 — Background tenant context is convention, not enforcement

- **Classification:** confirmed isolation risk
- **Severity / priority:** High / P0
- **Evidence:** commands/tasks use a mixture of `tenant_context`, `schema_context`, direct `connection.set_tenant`, and manual loops; `import_statement_items` uses `tenant.name`; no common task envelope exists.
- **Current behavior:** a forgotten or incorrect schema argument can query public/stale context. Connection reuse magnifies the impact.
- **Desired behavior:** every tenant job accepts immutable `workspace_id` or `schema_name`, resolves the active tenant in public context, enters `tenant_context`, asserts `connection.schema_name`, and restores context.
- **Recommended change:** add one helper/base task/command pattern, migrate SaaS and notification jobs first, fix display-name schema lookup, and add two-tenant tests.
- **Risk of change:** medium.

### F-13 — Audit is useful but not yet a complete security ledger

- **Classification:** optional improvement/missing policy
- **Severity / priority:** Medium / P1
- **Evidence:** public `AuditLog` covers auth, workspace, team, billing, ownership, and access actions; ordinary model permissions can still mutate/delete rows; `company` cascades audit history on company deletion.
- **Current behavior:** key services log events, but coverage is call-site dependent and schema purge deletes related public audit history.
- **Desired behavior:** append-only operator/business administration events survive archive and are emitted transactionally for defined P0/P1 actions.
- **Recommended change:** protect audit admin from edits/deletes, use `SET_NULL` for purged company references with stable IDs/names in data, publish an event coverage table, and avoid logging secrets/large request arguments.
- **Risk of change:** low/medium.

### F-14 — Public notifications are coupled to web requests

- **Classification:** reliability gap
- **Severity / priority:** Medium / P1
- **Evidence:** `CompanyInvitation.send_invitation()` calls the adapter synchronously and then records `sent`; auth email uses allauth SMTP; invitation delivery has no durable attempt row.
- **Current behavior:** transient SMTP failure can fail the user action or leave ambiguous delivery; retry and idempotency are limited.
- **Desired behavior:** invitation intent commits first; delivery occurs on transaction commit through a small retryable job, recording last attempt/error. Do not build a generic omnichannel platform for this.
- **Recommended change:** add a minimal public email-delivery boundary or reuse a proven job mechanism without coupling public identity mail to tenant Notify models.
- **Risk of change:** medium.

### F-15 — Observability lacks request/job correlation and boundary alarms

- **Classification:** missing operational capability
- **Severity / priority:** Medium / P1
- **Evidence:** logging includes schema via `TenantContextFilter`; audit includes user/company/IP; no consistent correlation ID, provisioning health view, task failure registry, or unknown-host alert was found.
- **Recommended change:** add request ID, workspace ID/schema and user ID to structured logs; health checks for DB/Redis/email readiness; alert on unknown tenant host, provisioning failure, repeated access denial, webhook/task failure. Never log tenant secrets.
- **Risk of change:** low.

### F-16 — Test volume is high but isolation proof is incomplete

- **Classification:** confirmed test gap
- **Severity / priority:** High / P0/P1
- **Evidence:** tenant-aware test runner and many authorization intent/unit tests exist; many tests manually call `connection.set_tenant`; existing docs acknowledge missing true cross-tenant integration coverage.
- **Current behavior:** helpers and source structure are well characterized, but fewer tests demonstrate adversarial two-schema behavior through the real middleware/task stack.
- **Recommended change:** build a compact production gate listed in section 12, including two tenants with colliding primary keys and file/cache/job cases.
- **Risk of change:** low.

## 8. Good architecture to retain

- Keep PostgreSQL schema-per-tenant and `django-tenants` for the MVP. Do not introduce RLS now; the accepted RLS exploration is a future migration strategy, not the current architecture.
- Keep users, companies/domains, memberships, invitations, billing and platform audit in the public schema.
- Keep business/financial records in tenant schemas.
- Keep membership validation before `connection.set_tenant()`.
- Keep domain/path mismatch rejection and explicit public-schema resets.
- Keep `resolve_request_workspace()` with `request.tenant` as authority and profile fallback disabled by default.
- Keep tenant-aware DB router, `migrate_schemas`, test runner, cache keying, file storage and logging filter.
- Keep the `get_effective_permissions()` public API while simplifying its internals.
- Keep workspace-billed subscriptions and provider webhook idempotency models.
- Keep soft archive as the default destructive action.
- Keep service-owned team role/invitation mutations and current authorization characterization tests.

## 9. Deletions and consolidations

Candidates require a final reference/data check before deletion:

| Candidate | Recommendation | Survivor |
|---|---|---|
| `PendingInvitation` and bridging signals | Delete after invite-before-signup characterization | `CompanyInvitation` |
| `CompanyOwnership` as current authority | Delete, or retain only immutable history | `Company.owner` + audit event |
| Guardian object-permission path | Remove if assignment search remains empty | `get_effective_permissions()` |
| Duplicate subscription middleware | Replace both admission billing check and broad validation middleware with one access-mode policy | subscription/entitlement service |
| Auto-seed signal plus explicit provisioning seed | Choose one explicit provisioning path | control-plane provisioning service |
| `old_settings.py` | Archive/delete after deployment tooling search | `django_project/settings/*` |
| Legacy root/profile-fallback tenant routing | Retire incrementally after canonical link/POST migration | domain or `/w/<slug>/` routes |
| Unused Plan booleans/limits | Delete after reference inventory | explicit MVP entitlements |
| Commented model/deletion code | Delete | version control/history |
| Contact/Girvi/legacy Notify compatibility apps | Follow their existing product-specific retirement plans; do not mix into foundation P0 | Party/Loans/Notify v2 when gates pass |

## 10. Database and migration review

The migrations show organic churn (`CompanyInvitation` create/delete/recreate, old user workspace fields, later `UserProfile`, added shadow invitations). This is historical noise, not by itself a runtime defect.

Do not squash migrations before the target models are settled. Recommended sequence:

1. Reconcile actual local/public data for ownership, roles, invitations and subscriptions.
2. Implement the target changes in ordinary migrations and validate every tenant with `migrate_schemas --shared` for shared changes and `migrate_schemas` for tenant changes.
3. Because production data is not yet valuable, optionally reset development databases after the new boundary lands.
4. Only then consider a pre-production migration baseline/squash. Preserve a tagged pre-squash chain and test a clean install plus upgrade from the last shared development checkpoint.

Proposed shared-schema changes:

- `Company.status` with constrained lifecycle values; later remove `is_deleted`.
- Optional provisioning error/step timestamps (fields on Company are enough for MVP; no workflow framework).
- `Membership.role`: eventually non-null and `PROTECT`; add `status` or `ended_at`.
- Remove `PendingInvitation`.
- Remove or demote `CompanyOwnership`; preserve history in `AuditLog`.
- Normalize invitation email (application normalization plus a case-insensitive uniqueness strategy suitable for PostgreSQL).
- Make audit company reference survivable across purge.
- Consolidate plan/entitlement fields after usage inventory.

## 11. Minimal target architecture

Do not create new apps just to mirror nouns.

### `accounts/` — identity

- Global `User` and lightweight profile.
- allauth signup, verified email, login/logout, recovery, social identity.
- Selected workspace is navigation preference only.

### `orgs/` — public SaaS control plane

- `Company`: tenant registry, schema identifier, display name, current owner, lifecycle/provisioning state.
- `Domain`: verified routing identity for a company.
- `Membership`: global user-to-company relationship and one role.
- `Role`: small built-in workspace roles and explicit permission codes.
- `CompanyInvitation`: single invitation lifecycle.
- `AuditLog`: append-only important platform administration events.
- Services: provision, switch/resolve, invite/accept, change role, suspend/reactivate, transfer ownership, archive/purge.

### `subscriptions/` — billing and entitlements

- `Plan`: product offer, not authorization.
- `Subscription`: one workspace billing contract and explicit lifecycle.
- Effective entitlements: enabled features and numeric limits.
- Provider customer/webhook state with signature checks and idempotency.
- One policy API returning access mode, feature decision, and limit.

### `onboarding/` — orchestration UX

- Collect setup inputs and call the org provisioning service.
- Track checklist/product onboarding; do not own tenant creation rules.

### Tenant apps — business data

- Consume `request.tenant`, permission API, and entitlement API.
- Never resolve a tenant from a user profile.
- Never query another tenant or public control-plane table through implicit search-path assumptions.
- Background work always carries explicit tenant identity.

## 12. Critical invariants and minimum production tests

### Invariants

1. One global identity per normalized verified email.
2. Company schema name is immutable after activation, unique, validated, and never derived ad hoc from display name.
3. Every non-public request obtains its tenant from an authoritative domain/path.
4. No tenant schema is selected until active company + authenticated active membership pass.
5. Exactly one current owner; owner has an active owner membership and cannot be removed before transfer.
6. One membership per user/company; assigned roles cannot be deleted.
7. One pending invitation per normalized email/company; acceptance is atomic and idempotent.
8. Authorization and entitlement are independent decisions and both are required for a paid action.
9. Subscription failure never prevents safe billing recovery, support diagnostics, or an explicitly chosen read-only/export path.
10. Tenant jobs resolve the company in public context, enter it explicitly, assert schema, and restore context.
11. Archive never drops a schema. Purge is offline, explicit, audited and environment-gated.
12. Tenant files and caches include tenant identity; provider credentials and logs cannot leak across tenants.

### Minimum production test gate

1. Signup verification, password reset, email change, social verified-email behavior.
2. Provisioning success, duplicate/reserved schema rejection, seed failure, retry, domain rollback, failed-state access denial.
3. Two-tenant middleware tests with colliding record IDs: domain/path mismatch, profile poisoning, unknown host, unauthenticated route, archived/suspended tenant.
4. Workspace switch cannot select a non-membership and cannot make a global route tenant-authoritative.
5. Invite-before-signup, invite-existing-user, wrong-email acceptance, expiry/revoke/decline, replay, concurrent acceptance, seat limit.
6. Owner transfer atomicity; owner removal blocked; role deletion protected; inactive member denied.
7. Permission matrix for Owner/Admin/Member/Viewer plus platform admin; every mutation route denies absent permission.
8. Subscription access modes for trial/active/grace/past-due/cancelled/expired; billing recovery works; feature absence and numeric limits fail closed.
9. Task/command test starts in public/stale tenant context, processes two schemas, and restores public context; retry is idempotent.
10. Cache and file tests prove identical keys/filenames and object IDs do not cross tenants; download endpoints re-authorize.
11. Webhook signature, tenant association, replay and out-of-order event tests.
12. Archive/restore/purge safety, public-tenant purge rejection, configuration default false, audit survival.
13. Audit coverage for tenant create/fail/suspend, invite/accept, member/role/owner changes, subscription changes, denied access and purge.
14. Clean database bootstrap and shared/tenant migration drift checks using `migrate_schemas`.

## 13. Remediation plan

### Phase 0 — Remove dangerous architecture (P0)

- **Objective:** make schema selection and destructive operations fail safe.
- **Changes:** disable hard delete by default/remove bulk action; mandatory verified email; remove profile fallback as schema authority; separate subscription policy from tenant resolution; fix tenant task/command context; add company lifecycle/provisioning state; reconcile ownership.
- **Affected:** settings, accounts/allauth config, `orgs` models/middleware/control-plane/admin, subscriptions middleware/service, tenant commands/tasks.
- **Dependencies:** route inventory and current working-tree consolidation.
- **Migration impact:** shared Company/ownership/lifecycle changes; use `migrate_schemas --shared`.
- **Tests:** isolation/destruction/auth/provisioning/task gate above.
- **Risk:** high, especially middleware and provisioning; deliver in small reversible slices.
- **Result:** authenticated membership selects an active tenant; billing no longer controls schema identity; purge cannot happen accidentally.

### Phase 1 — SaaS core correctness (P0/P1)

- **Objective:** one source of truth for membership, ownership, invitation and permission.
- **Changes:** remove `PendingInvitation`; protect/non-null roles; add membership deactivation; transactional ownership transfer; consolidate RBAC and remove unused Guardian path; normalize invitation emails; define subscription access modes and explicit entitlements.
- **Affected:** orgs models/services/views/forms/signals, subscriptions models/services, module guards.
- **Migration impact:** shared migrations and data reconciliation.
- **Tests:** concurrency/idempotency and complete role/route matrices.
- **Risk:** medium/high.
- **Result:** one understandable answer to “who is this user here?” and “may they act?”.

### Phase 2 — MVP completeness (P1)

- **Objective:** make operation and recovery production-usable.
- **Changes:** retryable invitation delivery; provisioning/support dashboard or commands; append-only audit policy; health checks; correlation IDs; file/download and cache isolation proof; billing recovery and read-only behavior.
- **Affected:** orgs, subscriptions, accounts mail integration, logging/health settings, storage endpoints.
- **Migration impact:** small public delivery/provisioning fields if required.
- **Tests:** delivery retry, audit coverage, health and file/cache isolation.
- **Risk:** medium.
- **Result:** operators can diagnose and recover the expected first-release failures.

### Phase 3 — Production hardening (P2)

- **Objective:** retention, erasure, backup and operational maturity.
- **Changes:** export/retention policy, backup/restore drill, delayed purge workflow, rate limiting, centralized job failure reporting, credential rotation runbooks.
- **Migration impact:** only if purge/export request tracking is required.
- **Risk:** medium.
- **Result:** controlled lifecycle beyond initial launch.

### Phase 4 — Deliberately post-MVP (P3)

- Custom enterprise roles/ABAC, delegated billing organizations, SSO/SAML/SCIM, operator impersonation, multi-provider billing abstraction, branded portal domains, cross-region tenancy, RLS conversion, event sourcing, microservices.

## 14. Final MVP readiness checklist

- [ ] Production hard delete defaults off and purge is separately controlled.
- [ ] Mandatory verified email is exercised end-to-end.
- [ ] Tenant schema comes only from domain/canonical workspace path.
- [ ] Company lifecycle and provisioning failure/retry are explicit.
- [ ] Membership, owner and role invariants are database/service enforced.
- [ ] `CompanyInvitation` is the only invitation state.
- [ ] One permission evaluator and one defined permission vocabulary remain.
- [ ] Tenant admission is independent of subscription access mode.
- [ ] Billing recovery/read-only rules are explicit and tested.
- [ ] Every tenant job/command carries and verifies tenant identity.
- [ ] Audit, logs and health checks expose workspace/schema/request/job identity safely.
- [ ] Files, caches and provider callbacks pass two-tenant isolation tests.
- [ ] Archive/restore and delayed purge are operationally documented and tested.
- [ ] Clean install and migrations pass with tenant-aware commands.

## 15. Direct answer: what should the first-release SaaS architecture be?

If historical complexity is removed, the first release needs only these core concepts:

1. **User** — one global, verified identity and authentication lifecycle.
2. **Company/Workspace** — the public registry row for a PostgreSQL tenant schema, its immutable schema identity, owner and operational lifecycle.
3. **Domain** — authoritative host-to-workspace routing.
4. **Membership** — the single statement that a user belongs to a workspace, with active state and one role.
5. **Role/permission policy** — four or five boring built-in roles evaluated by one function; no speculative object-permission framework.
6. **Invitation** — one atomic, expiring, idempotent path to membership.
7. **Subscription** — the workspace’s billing contract, independent of user authorization.
8. **Entitlements** — explicit feature and capacity decisions derived from the subscription.
9. **Audit event** — append-only evidence for important platform administration.
10. **Provisioning service** — the one explicit, retryable orchestration boundary that creates schema, seeds it, creates domain, owner membership and active state.

Users, workspace registry/domain, memberships, invitations, subscriptions/entitlements and platform audit belong in the **public schema**. Parties, loans, collateral, inventory, accounting, operational notifications and business files belong in the **tenant schema**.

The critical path is:

```text
verified User
  -> authoritative Domain or /w/<workspace>/ path
  -> ACTIVE Company
  -> ACTIVE Membership
  -> set tenant schema
  -> role permission decision
  -> subscription entitlement decision (only when relevant)
  -> tenant business service
```

That is the clean MVP boundary: a small public control plane that proves identity, tenant, membership and commercial access; isolated tenant schemas that own business data; explicit services for every mutation; and tests that attempt to cross the boundary. Nothing more elaborate is required for launch.
