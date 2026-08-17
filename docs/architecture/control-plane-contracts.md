---
status: accepted
owner: project
updated: 2026-08-17
tags: [architecture, saas, control-plane, workspace, rls, rbac, billing]
related:
  - saas-control-plane-architecture-audit.md
  - ../adr/2026-08-17-workspace-request-authority-and-rls-context.md
  - ../adr/2026-08-17-workspace-ownership-authority.md
  - ../adr/2026-08-17-workspace-authorization-contract.md
  - ../adr/2026-08-17-workspace-lifecycle-and-billing-boundary.md
  - ../adr/2026-08-17-workspace-entitlement-contract.md
---

# Control-Plane Contracts

This is the normative developer and agent reference for Rokkad's SaaS control
plane. The accepted audit preserves the evidence and roadmap; this document
defines the decisions that new code must follow. The product term **Workspace**
currently maps to `orgs.Company` in persistence.

## 1. Responsibility map

| Concern | Canonical answer |
|---|---|
| Request identity | An explicit Workspace domain or Workspace-bearing path |
| Request context | `request.workspace` |
| Navigation preference | `UserProfile.workspace` |
| Database row isolation | `workspace_context(workspace.id)` and forced PostgreSQL RLS |
| User–Workspace relationship | `Membership(user, company)` |
| Ownership authority | `Company.owner_id` |
| Workspace action authorization | Target `WorkspaceAccess` policy |
| Operational availability | Target Workspace lifecycle policy |
| Commercial contract | `Subscription` effective billing state |
| Features and limits | Target entitlement service using stable codes |

Authentication, membership, authorization, RLS, lifecycle, billing, and
entitlement are separate checks. Passing one never implies passing another.

### Repository evidence behind the lock

| Area | Current evidence and constraint |
|---|---|
| Resolution | Phase 1 implements explicit Domain/path candidates only, rejects conflicts for every actor, validates Membership, and establishes matching request/RLS context. Subscription enforcement is a later middleware stage. |
| Fallbacks | `apps/orgs/tenant_context.py` resolves requests only from `request.workspace`; profile preference has a separate navigation-only resolver, and context processors do not infer authority from profile or `request.tenant`. |
| RLS | `apps/tenancy/context.py` already provides atomic transaction-local context, same-ID nesting, conflict rejection, and cleanup. `WorkspaceOwnedModel` validates direct ownership against its Python context. |
| Relationship/ownership | `Membership` is the sole ordinary relationship with a required role. `Company.owner_id` is protected canonical ownership, mirrored by exactly one Owner Membership; `CompanyOwnership` is retired. |
| Authorization | `apps/orgs/permissions.py`, `decorators_v2.py`, `role_policy.py`, and four surviving app `access.py` modules combine hardcoded maps, `Role.permissions`, role/owner shortcuts, and installed Guardian support. |
| Lifecycle | `Company.lifecycle_state` stores the four accepted operational states; the transition service is row-locked, reason-required, authorized, and audited. Ordinary hard deletion is disabled. |
| Billing/entitlements | `Subscription.status`, `is_active`, dates, Plan flags/limits, `SubscriptionEntitlement`, middleware, decorators, and `SubscriptionAccessService` can produce overlapping access answers. |

These existing constraints make the decisions implementable incrementally; they
do not make the competing mechanisms coequal target APIs.

## 2. Request Workspace authority

### 2.1 Resolution contract

A Workspace request must carry an explicit Workspace identity through:

1. a registered Workspace domain; or
2. a Workspace-bearing path, preferably `/w/<workspace-slug>/...` and, during
   transition, a recognized path containing a Workspace ID.

If domain and path both identify a Workspace, they must identify the same row.
A disagreement fails closed for every actor, including platform administrators.
There is no precedence rule that silently chooses one conflicting identity.

After identity resolution, the request pipeline must:

```text
explicit identity
  -> existing operational Workspace
  -> authentication
  -> Membership or explicit platform-admin override
  -> request.workspace
  -> workspace_context(request.workspace.id)
  -> PostgreSQL app.workspace_id
```

The target resolver returns a typed outcome: global, resolved, not found,
conflict, lifecycle denied, or membership denied. It must not redirect or write
profile preferences; middleware translates the outcome into an HTTP response.

### 2.2 Global and Workspace contexts

| Context | Examples | Required state |
|---|---|---|
| Global control plane | account/profile/security, Workspace list/create/selector, incoming invitation acceptance | `request.workspace is None`; PostgreSQL Workspace context unset |
| Workspace | Workspace dashboard/team/settings/billing, Party, Loans, Notify v2, Rates | validated `request.workspace`; matching PostgreSQL context active |

A global request remains global even when `UserProfile.workspace` is populated.
A Workspace domain may explicitly scope an otherwise unscoped path. On a global
domain, an unscoped business route must fail closed or redirect to an explicit
Workspace URL; it must never infer authority from profile state.

Platform administrators must also select an explicit Workspace. The accepted
superuser-only override may bypass Membership, but never identity resolution,
conflict detection, lifecycle policy, RLS context, or audit.

Membership removal denies the next Workspace request and clears an invalid
navigation preference. It cannot retroactively cancel a transaction already in
progress; long-running work must revalidate at its own authorization boundary.

## 3. `UserProfile.workspace`

`UserProfile.workspace` remains a nullable navigation preference meaning “last
or default Workspace used for navigation.” It is not request, authorization,
ownership, RLS, or service context. A later migration should rename it to
`preferred_workspace` or `last_workspace` after compatibility callers move.

| Use | Status |
|---|---|
| Show a default/last Workspace in a global selector | Allowed |
| Choose the initial explicit redirect after login | Allowed after current Membership and lifecycle validation |
| Update after an authorized Workspace switch | Allowed |
| Clear after Membership removal or Workspace unavailability | Required |
| Resolve an ordinary Workspace request | Forbidden |
| Establish `request.workspace` or PostgreSQL context | Forbidden |
| Authorize a view, service, task, or command | Forbidden |
| Select business data or infer ownership | Forbidden |
| Provide a context-processor fallback for Workspace authority | Forbidden |

Multiple browser tabs are independent because each Workspace page carries its
own identity. Updating the preference in one tab does not change the authority
of another tab's explicit URL.

## 4. Request context and PostgreSQL RLS context

`request.workspace` is the validated Django Workspace object for one HTTP
request. `app.workspace_id` is a transaction-local PostgreSQL setting used by
forced RLS. They are different representations with one invariant: whenever a
Workspace request executes Workspace-owned SQL, both identify the same row.

`apps.tenancy.context.workspace_context(workspace_id)` remains the only normal
API for establishing database context.

Its contract is:

- accept a positive numeric Workspace primary key (or value coercible to it);
- open `transaction.atomic()` and use transaction-local `set_config`;
- set both Python execution context and PostgreSQL `app.workspace_id`;
- permit nesting only for the same Workspace ID;
- reject conflicting nested IDs before executing scoped work;
- restore the surrounding value on normal exit;
- roll back and reset Python context on exceptions;
- leave no Workspace context after the outermost scope exits.

HTTP middleware owns this scope for request processing. Background jobs and
management commands must receive an explicit `workspace_id` in their payload or
arguments and open one context per atomic unit. Tests use the same API; RLS
adversarial DML runs under the restricted runtime role. Global control-plane
operations run without it.

Direct SQL that sets `app.workspace_id`, connection-global tenant state, and
schema-context helpers are forbidden for new application code. Streaming or
deferred response code must not perform Workspace queries after middleware has
closed the context; it must materialize data inside the request scope or own a
new explicit context outside HTTP.

## 5. Membership

`Membership(user, company)` is the only ordinary User–Workspace relationship.
Its existing uniqueness constraint is canonical. Target rules are:

- one Membership at most per User and Workspace;
- a role is required for every Membership;
- absence means no ordinary access; no parallel active/inactive membership
  flag is needed until a concrete suspend-member requirement exists;
- removal deletes the Membership, clears matching navigation preference, and
  denies future authorization;
- an invitation is pending intent, not Membership; verified idempotent
  acceptance creates the Membership;
- platform administrators are the only accepted no-Membership override;
- seat usage counts Memberships, with pending invitations reserved when the
  invitation workflow requests capacity;
- business applications must not create their own staff, employee-login, or
  Workspace-membership authority.

## 6. Workspace ownership

`Company.owner_id` is the sole authoritative owner. Exactly one user owns every
persisting Workspace. That user must also have the Workspace's single mirrored
Owner Membership; the Membership supplies permissions but does not determine
ownership. Other Memberships must not use the semantic Owner role.

`CompanyOwnership` is not authoritative. Its current helper is not atomic, does
not update `Company.owner`, and its uniqueness constraint cannot represent a
user owning the same Workspace in two separate tenures. Phase 2 retires it as
live state after any useful rows are reconciled. Structured
`OWNERSHIP_TRANSFER` audit events retain history.

The target operation is:

```python
transfer_workspace_ownership(
    *, workspace, new_owner, actor, previous_owner_role, reason
)
```

It must run atomically, lock the Workspace and affected Memberships, verify that
the actor is the current owner or an audited platform administrator, require the
new owner to be an existing member, reject self/no-op and stale-owner races,
set `Company.owner`, promote the target Membership to Owner, demote the previous
owner to the explicitly supplied non-owner role, and append one audit event.
User deletion must be blocked while the user owns a Workspace; ownership must
be transferred first. Workspace deletion follows lifecycle/retention policy,
not owner deletion cascade.

## 7. Workspace authorization

Phase 2 introduces one request-independent policy value:

```python
access = resolve_workspace_access(actor=user, workspace=workspace)
access.can("party.view")
access.require("loans.create")
```

`WorkspaceAccess` contains the actor, Workspace, Membership (nullable only for
platform override), platform-override flag, and effective action-code set. It
answers membership and RBAC questions only. Workspace lifecycle and
entitlements are evaluated by their own policies.

The action catalog uses stable namespaced codes such as `party.view`,
`loans.create`, and `team.member.remove`. `Role.permissions` becomes the stored
role-to-action assignment through an internal mapping from Django permissions.
Hardcoded role maps may seed defaults but must not be a second runtime source.
Direct role-name comparisons, `Company.owner` shortcuts, Guardian object checks,
and per-app access helpers are transitional until routed through
`WorkspaceAccess`.

Use by layer:

- middleware/resolver constructs `request.workspace_access` after explicit
  Workspace and access validation;
- views call `request.workspace_access.require(action)`;
- services accept an actor/access object and do not depend on `request`;
- templates consume flags/tags derived from the same access object and never
  query Membership;
- jobs/commands reconstruct access from explicit actor and Workspace when an
  actor-authorized action is required;
- domain services may add object/lifecycle rules after Workspace authorization.

Implementation status (2026-08-17): Phase 2 is complete for the control plane.
Ownership reconciliation and constraints are in `orgs.0002`; the atomic
transfer command lives in `apps.orgs.services.control_plane`; and
`apps.orgs.access` supplies the policy used by middleware, control-plane views,
decorators, and role policy. Conversion of surviving business-app access
helpers remains the already accepted Phase 9 cross-app conformance work.

The accepted platform-admin policy remains superuser-only. Overrides require
an explicit Workspace and auditable use.

### 7.1 Checks that must remain separate

| Check | Question answered |
|---|---|
| Authentication | Who is the actor? |
| Membership | Is the actor related to this Workspace? |
| Authorization/RBAC | May the actor perform this action? |
| Workspace lifecycle | May this kind of operation occur now? |
| Billing state | Is the commercial contract in this state? |
| Entitlement | Has this Workspace been granted this feature or limit? |
| RLS | Which Workspace owns rows visible/writable to this transaction? |

RLS is never action authorization. Entitlement is never Membership. A paid
subscription never grants a user access.

## 8. Workspace operational lifecycle

The smallest useful target state machine has four stored states. Shared-schema
creation is synchronous, so `PROVISIONING` is not justified. `DELETED` is not a
stored state because the row no longer exists after approved erasure.

| State | Meaning | Entry/reads/mutations | Billing recovery | Export | Reactivation |
|---|---|---|---|---|---|
| `ACTIVE` | Normal operation | Members may enter; authorized reads and mutations | Yes | By permission | N/A |
| `SUSPENDED` | Platform safety/compliance hold | Ordinary business entry and mutations denied; owner/admin/platform get limited control-plane diagnostics | Yes | Owner/admin/platform through an explicit recovery path | Platform after cause is cleared |
| `ARCHIVED` | Customer has taken Workspace out of operation | No ordinary entry or business mutation; owner/platform may view control-plane metadata | Existing obligations only; no automatic renewal | Owner/platform through an explicit archive export path | Owner or platform; billing is evaluated separately |
| `DELETION_PENDING` | Retention/grace period before approved erasure | No ordinary entry or business mutation | Settle obligations only; no purchase/renewal | Authorized export until retention deadline | Cancel back to `ARCHIVED` before irreversible erasure |

Allowed transitions are `ACTIVE -> SUSPENDED`, `SUSPENDED -> ACTIVE`,
`ACTIVE|SUSPENDED -> ARCHIVED`, `ARCHIVED -> ACTIVE`,
`ARCHIVED -> DELETION_PENDING`, and `DELETION_PENDING -> ARCHIVED` during the
grace period. Physical deletion is a privileged retention workflow after
`DELETION_PENDING`, never an ordinary model `delete()` call.

Lifecycle is operational policy, not RLS: data remains Workspace-owned and
isolated in every stored state. Lifecycle transitions do not silently change
subscription state, and billing events do not silently archive a Workspace.

Implementation status (2026-08-17): Phase 3 is complete. Migration `orgs.0003`
maps the old archive flag to `ARCHIVED` and removes it. `apps.orgs.lifecycle`
owns the transition graph and access matrix;
`transition_workspace_lifecycle()` performs row-locked, reason-required,
audited changes; and secure middleware applies the lifecycle boundary before
granting either Membership or platform access. Ordinary model/admin deletion is
disabled. Physical retention erasure is intentionally not implemented here.

## 9. Billing and subscription

The Workspace is the customer and has one commercial `Subscription`.
`BillingAccount` holds provider/customer/contact identity. `Subscription`
holds commercial terms and stored transition state. Provider events are
idempotent inputs to a billing transition service, never direct authority for
Workspace identity or RLS.

The target stored states retain the repository's current vocabulary:
`TRIAL`, `ACTIVE`, `PAST_DUE`, `CANCELLED`, and `EXPIRED`. One billing policy
computes effective state from stored status, relevant dates, and processed
provider events. `Subscription.status` is the stored source; `is_active` and
time-dependent mutation in `save()` are deprecated duplicate authorities.

Only billing transition services may change state. Webhook processing must
persist provider identity, deduplicate/replay safely, lock the Subscription,
validate the transition, and append a `SubscriptionEvent` in the same atomic
unit. `PAST_DUE`, `CANCELLED`, and `EXPIRED` never block access to billing
recovery routes. Billing policy feeds entitlement evaluation; it does not
establish Membership, Workspace lifecycle, request context, or RLS.

Implementation status (2026-08-17): Phase 4 is complete. Effective billing
state is derived by `apps.subscriptions.billing` without model-save mutation;
stored transitions are row-locked and append `SubscriptionEvent` evidence.
`Subscription.is_active` is removed. Provider webhook events have durable,
provider-scoped replay identity, and billing recovery routes remain exempt from
commercial blocking without losing explicit Workspace/RLS context.

## 10. Entitlements

The target public API is a single Workspace-scoped service:

```python
entitlements.enabled(workspace, "loans.core")
entitlements.require(workspace, "notify_v2.whatsapp")
entitlements.limit(workspace, "workspace.max_members")
```

Business apps know stable codes and typed results only. They do not know plan
names, Razorpay state, trials, pricing, invoices, or override storage.

Rules:

- feature codes are namespaced, immutable identifiers registered centrally;
- the owning business capability defines a code's meaning, while the control
  plane validates the registry and resolves values;
- boolean features return a boolean; numeric limits return a non-negative
  integer or an explicit unlimited value;
- a missing, malformed, disabled, or commercially unavailable paid entitlement
  fails closed;
- any always-on/core capability is an explicit registry default, not an
  accidental missing-row fallback;
- plan fields are commercial configuration inputs, not runtime APIs;
- `SubscriptionEntitlement` becomes the effective Workspace projection;
- explicit overrides require provenance, actor, reason, and optional expiry and
  must not be silently overwritten by model `save()`;
- seat limits use the same `limit()` contract and remain transactionally
  enforced at invitation/membership boundaries.

Entitlement denial limits a capability. It must not clear `request.workspace`,
change RLS, or erase access to billing recovery and authorized data export.

Implementation status (2026-08-17): Phase 4 is complete. The namespaced typed
registry and `enabled()`/`require()`/`limit()` API live in
`apps.subscriptions.entitlements`. Plan projection writes canonical effective
rows, never overwrites explicit overrides, and override actor/reason provenance
is constrained in PostgreSQL. Missing, malformed, expired, and commercially
unavailable grants fail closed. Seats, module gating, and feature decorators use
this API; the mixed `SubscriptionAccessService` remains compatibility-only and
has no runtime middleware or control-plane caller.

## 11. Data-plane contract

Party, Loans, Notify v2, Rates, and every future Workspace app may rely on:

- authenticated `request.user` where the route requires an actor;
- validated `request.workspace` on Workspace routes;
- target `request.workspace_access` for namespaced action authorization;
- `workspace_context(workspace_id)` outside HTTP;
- `WorkspaceOwnedModel` or an explicitly audited equivalent for every owned
  concrete table;
- the canonical entitlement service;
- explicit `workspace_id` in jobs, commands, imports, exports, cache keys,
  storage paths, and logs.

Forbidden for new code:

- `request.user.profile.workspace` as current Workspace;
- `request.tenant`;
- manual `SET app.workspace_id`;
- plan-name or provider-state checks in business apps;
- business-app Membership queries that recreate access policy;
- owner-field or role-name authorization shortcuts;
- relying only on queryset filtering instead of forced RLS;
- treating RLS as action authorization;
- silent fallback to a different Workspace;
- a task or command that discovers Workspace from ambient process state.

## 12. API status catalog

| API or concept | Status | Replacement / rule | Implementation phase |
|---|---|---|---|
| `request.workspace` | CANONICAL | Sole active HTTP Workspace | Phase 1 hardening |
| Explicit domain and `/w/<slug>/` identity | CANONICAL | Candidates must agree | Phase 1 |
| Recognized Workspace-ID paths | TRANSITIONAL | `/w/<immutable-slug>/...` | Phase 6 |
| `UserProfile.workspace` as navigation default | ALLOWED | Later rename to preferred/last Workspace | Phase 1, then Phase 7 cleanup |
| `UserProfile.workspace` as request authority | FORBIDDEN FOR NEW CODE | Explicit resolver + `request.workspace` | Phase 1 removal |
| `resolve_request_workspace(request)` | TRANSITIONAL | Direct `request.workspace`; target resolver owns establishment | Phase 1 |
| `allow_profile_fallback=True` | REMOVE | Preference-aware global navigation helper only | Phase 1 |
| `request.tenant` | TRANSITIONAL | `request.workspace` | Phase 1 callers; Phase 7 removal |
| `workspace_context(workspace_id)` | CANONICAL | Only normal RLS-context setter | — |
| `current_workspace_id()` | ALLOWED | Validation/internal ownership support, not request resolution | — |
| `WorkspaceOwnedModel` | CANONICAL | Required owned-table base/equivalent | — |
| `Company.schema_name` as routing slug | TRANSITIONAL | Immutable `Workspace.slug` field/name | Phase 6/7 |
| `Membership(user, company)` | CANONICAL | Sole ordinary relationship | Phase 2 constraints |
| `Company.owner_id` | CANONICAL | Sole ownership authority | Phase 2 hardening |
| Owner Membership | ALLOWED DERIVED MIRROR | Must match `Company.owner_id` | Phase 2 |
| `CompanyOwnership` as active authority | REMOVE | `Company.owner_id` + transfer audit | Phase 2 |
| `get_effective_permissions()` | TRANSITIONAL | `WorkspaceAccess` | Phase 2 |
| App-specific access helpers/decorators | TRANSITIONAL | `WorkspaceAccess` action codes | Phase 2 and Phase 9 |
| Direct role-name/owner checks | DEPRECATED | `WorkspaceAccess.require()` | Phase 2 and Phase 9 |
| Guardian object permissions | DEPRECATED | Remove unless a concrete object-ACL requirement is accepted | Phase 2/7 |
| `Company.is_deleted` | REMOVED | `Company.lifecycle_state` + lifecycle service | Phase 3 complete |
| `Subscription.status` | CANONICAL STORED STATE | Effective billing policy | Phase 4 |
| `Subscription.is_active` | DEPRECATED | Effective billing state | Phase 4 |
| `Subscription.can_access_feature()` | DEPRECATED | Entitlement service | Phase 4 |
| `SubscriptionAccessService` mixed access | DEPRECATED | Separate WorkspaceAccess, billing policy, entitlements | Phases 2 and 4 |
| Plan feature booleans/limits | ALLOWED CONFIG INPUT | Never a data-plane runtime API | Phase 4 |
| `SubscriptionEntitlement` effective rows | CANONICAL TARGET PROJECTION | Access only through entitlement service | Phase 4 |
| Direct plan-name checks | FORBIDDEN FOR NEW CODE | Stable feature/limit codes | Phase 4 cleanup |
| `TENANT_APPS`, public-schema terminology, schema helpers | REMOVE | Shared-schema Workspace language | Phase 7 |

## 13. Invariant catalog

| ID | Invariant |
|---|---|
| CP-WORKSPACE-001 | A Workspace request has exactly one explicit Workspace identity. |
| CP-WORKSPACE-002 | Domain and path identities must agree or the request fails closed. |
| CP-WORKSPACE-003 | A global request has `request.workspace = None` and no PostgreSQL Workspace context. |
| CP-WORKSPACE-004 | `UserProfile.workspace` never grants request authority. |
| CP-WORKSPACE-005 | Workspace selection never changes the authority of another explicit browser tab. |
| CP-RLS-001 | Workspace-owned SQL runs only with the corresponding transaction-local PostgreSQL context. |
| CP-RLS-002 | New application code never sets `app.workspace_id` directly. |
| CP-RLS-003 | Conflicting nested Workspace contexts fail before scoped work. |
| CP-MEMBERSHIP-001 | `Membership` is the sole ordinary User–Workspace relationship. |
| CP-MEMBERSHIP-002 | Invitation acceptance creates Membership; invitation state alone grants no access. |
| CP-OWNERSHIP-001 | Every persisting Workspace has exactly one authoritative `Company.owner_id`. |
| CP-OWNERSHIP-002 | The sole Owner Membership mirrors the canonical owner and is not a second authority. |
| CP-OWNERSHIP-003 | Ownership transfer is atomic, locked, reasoned, and audited. |
| CP-AUTH-001 | RLS does not substitute for Membership or action authorization. |
| CP-AUTH-002 | Business apps authorize through stable action codes, not roles or owner fields. |
| CP-AUTH-003 | Platform override requires explicit Workspace identity and audit. |
| CP-LIFECYCLE-001 | Workspace lifecycle is independent of Subscription state. |
| CP-LIFECYCLE-002 | Archive/suspension never changes Workspace ownership of business rows. |
| CP-BILLING-001 | The Workspace, not a user, is the subscribed customer. |
| CP-BILLING-002 | Provider callbacks are idempotent inputs to explicit billing transitions. |
| CP-ENTITLEMENT-001 | Business apps never inspect plan names or provider state. |
| CP-ENTITLEMENT-002 | Missing or malformed paid entitlements fail closed. |
| CP-ENTITLEMENT-003 | Entitlement denial does not alter request identity or RLS context. |
| CP-DATAPLANE-001 | Every Workspace-owned concrete row has direct non-null ownership and forced RLS. |
| CP-JOB-001 | Every Workspace job/command receives explicit `workspace_id` and opens its own context. |

These invariants become executable contract tests in Phase 8, with earlier
phases adding focused tests as each target is implemented.

## 14. Implementation impact map

| Locked decision | Phase | Principal impact |
|---|---|---|
| Explicit Workspace authority; no profile fallback | 1 | `middleware_v2`, resolver, context processors, subscription middleware interaction, global/workspace tests |
| Profile Workspace is navigation-only | 1 | account/orgs/onboarding/subscription callers, switch redirects, templates |
| Canonical RLS context contract | 1 and 8 | middleware cleanup tests, task/command contract tests; primitive stays intact |
| Membership is canonical and role is required | 2 | Membership constraint/data cleanup, invitation/member services |
| `Company.owner_id` is sole owner | 2 | atomic transfer service, FK deletion behavior, Owner Membership reconciliation, retire `CompanyOwnership` |
| `WorkspaceAccess` and namespaced actions | 2, then 9 | permission registry, decorators/mixins/templates, surviving app access modules |
| Four-state Workspace lifecycle | 3 | model migration, transition service, middleware/policy, archive/restore/admin paths |
| Billing effective-state policy | 4 | Subscription model/services, middleware, provider webhooks, recovery routes |
| Canonical entitlement service | 4 | feature registry, projection/overrides, seats, module UI, business callers |
| Global vs Workspace shells/routes | 6 | URLConfs, layouts, compatibility redirects |
| Transitional tenancy terminology/APIs removal | 7 | `request.tenant`, `schema_name`, `TENANT_APPS`, stale commands/tests/docs |
| Cross-app conformance | 8 and 9 | invariant CI gates, Party/Loans/Notify v2/Rates audit and conversion |

## 15. Phase 1 readiness

Phase 1 is bounded to request context and resolution. It will not implement
ownership, RBAC consolidation, lifecycle fields, billing repair, entitlements,
or URL/UI redesign.

### 15.1 Runtime areas Phase 1 will change

1. `apps/orgs/middleware_v2.py`
   - remove profile Workspace from candidate selection;
   - make domain/path conflict fail closed for platform admins too;
   - classify global versus Workspace requests explicitly;
   - establish `request.workspace` only after identity and access validation;
   - stop synchronizing profile preference as a middleware side effect;
   - keep `request.tenant` as a temporary mirror only;
   - keep `workspace_context()` entry/cleanup behavior intact;
   - separate Workspace establishment from subscription denial so billing
     recovery can retain explicit Workspace context.
2. `apps/orgs/tenant_context.py`
   - retire authoritative `allow_profile_fallback` behavior;
   - narrow any preference lookup to a separately named global-navigation
     helper;
   - make ordinary consumers use `request.workspace` directly.
3. Context processors
   - remove profile and `request.tenant` authority fallbacks from permission,
     Workspace, subscription, and theme context;
   - expose global preference separately from effective Workspace.
4. Preference mutation flows
   - keep explicit POST selection as navigation preference;
   - validate preference before redirects;
   - do not let invitation/onboarding preference writes establish current
     request authority.

### 15.2 URL assumptions to characterize

- Workspace domains are explicit identity.
- `/w/<workspace_slug>/...` is explicit identity.
- `/orgs/workspace/<id>/...`, `/orgs/company/<id>/...`, and
  `/workspace/<id>/settings/...` are transitional explicit identity.
- root `/party/`, `/loans/`, `/rates/`, `/notify-v2/`, and `/data-tools/` are
  valid only when the domain supplies identity; on a global domain they must
  fail closed or redirect to an explicit route.
- shared global routes currently appear in both URLConfs; Phase 1 classifies
  context, while Phase 6 owns physical URL/UI separation.

### 15.3 Known implicit-profile callers to modify or characterize

- `django_project.context_processors` permission, Workspace, and subscription
  context;
- account Workspace management helpers;
- onboarding profile/completion redirects;
- subscription plan/dashboard/checkout views;
- orgs selector, invitation, membership, and management screens using
  `allow_profile_fallback=True`;
- legacy templates that read `request.user.profile.workspace` as if it were
  active context;
- the separate `SubscriptionValidationMiddleware` and Workspace middleware's
  embedded subscription check;
- `request.tenant` consumers in Notify v2, navigation/template tags, and tests.

Phase 1 should change only callers whose behavior affects context authority.
Pure display of the navigation preference may remain until Phase 6/7 if it is
clearly named and cannot grant access.

### 15.4 Required Phase 1 tests

- global request with and without a saved preference remains global;
- explicit domain only, slug path only, and matching domain+path resolve once;
- conflicting domain+path fails for member and platform admin;
- missing/deleted/unknown identity fails closed;
- non-member and removed member never establish request or database context;
- platform admin requires explicit identity and receives matching RLS context;
- two tabs with different explicit Workspaces remain independent after a
  preference switch;
- unscoped business paths on global host never use profile fallback;
- `request.workspace.id`, `current_workspace_id()`, and PostgreSQL setting
  match during the view and are cleared after success and exception;
- same-Workspace nesting succeeds and conflicting nesting fails;
- global context processors expose no effective Workspace permissions,
  subscription, or theme from preference;
- billing recovery routes keep their explicit Workspace context even when the
  subscription is not commercially active.

No architectural decision remains open for Phase 1. HTTP status/redirect copy
and the final resolver result type are implementation details constrained by
these contracts.
