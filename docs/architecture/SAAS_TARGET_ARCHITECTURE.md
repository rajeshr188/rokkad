---
status: proposed
owner: project
updated: 2026-08-14
tags: [saas, architecture, django-tenants, mvp, security]
related: [../implementation/saas-foundation-architecture-audit.md, ../implementation/django-tenants-architecture-audit.md, ../implementation/workspace-context.md, ../adr/2026-07-02-tenant-billed-subscription-architecture.md, ../STATUS.md]
---

# Canonical MVP SaaS Target Architecture

## 1. Status and decision boundary

This document proposes the canonical first-production SaaS architecture for Rokkad. It is intentionally smaller than the source audit and deliberately rejects several recommendations that would add machinery without solving an MVP problem.

This is a review document only. It authorizes no runtime changes, migrations, deletions, or data conversion. Implementation begins only after this target has been reviewed and accepted.

The target remains a Django monolith using PostgreSQL schema-per-tenant isolation through `django-tenants`. It does not introduce RLS, microservices, an event bus, a workflow engine, a generic policy engine, or new Django apps for membership, RBAC, entitlements, provisioning, or audit.

## 2. Architecture in one page

```text
PUBLIC SCHEMA

accounts
  User ----------- UserProfile (personal/navigation settings only)
    |
    +---- Membership ---- Role
              |
              v
orgs       Company ---- Domain
              |
              +---- CompanyInvitation
              +---- AuditLog
              |
              v
subscriptions
           Subscription ---- Plan
                 |
                 +---- SubscriptionEntitlement
                 +---- BillingAccount
                 +---- ProviderWebhookEvent / SubscriptionEvent

onboarding
  UI/checklist only -> calls orgs provisioning service

                         authoritative Domain or /w/<schema>/ path
                                          |
                                          v
                              membership checked in public
                                          |
                                          v
                              connection.set_tenant(company)
                                          |
                                          v
TENANT SCHEMA

party | loans/girvi | accounting/dea | product | rates | notify_v2 | terms
```

The request decision order is:

```text
authenticate global User
  -> resolve Company from authoritative route/domain
  -> require non-archived/non-suspended Company
  -> require Membership
  -> switch PostgreSQL schema
  -> require action permission
  -> require feature/limit entitlement where the action is plan-gated
  -> execute tenant service
```

Authentication, tenant selection, authorization, and entitlement are separate decisions. They may be orchestrated in sequence, but none substitutes for another.

## 3. Audit finding dispositions

These decisions cover every detailed finding in the source audit.

| Finding | Decision | Canonical response |
|---|---|---|
| F-01 Hard deletion enabled by default | **FIX NOW** | Make hard deletion disabled by default and remove it from ordinary/bulk admin workflows. Keep explicit model capability only for controlled development/operations until a later purge policy exists. |
| F-02 Optional email verification | **SIMPLIFY** | Keep general signup verification optional for MVP, but require the authenticated account to prove control of the matching invited email before invitation acceptance creates membership. Keep ordinary allauth; add no custom identity service. |
| F-03 Profile workspace used as tenant fallback | **FIX NOW** | Stop using `UserProfile.workspace` as schema authority. Retain it as navigation preference only. Domain or `/w/<schema_name>/` is authoritative. |
| F-04 Billing coupled to tenant admission | **SIMPLIFY** | Membership and tenant state decide schema access. Subscription checks occur after tenant context at explicitly gated product boundaries. Do not build a generic `FULL/READ_ONLY/BILLING_ONLY` access-mode engine. |
| F-05 Competing ownership sources | **DELETE** | Delete `CompanyOwnership` after reference/data verification. `Company.owner` is the sole current-owner authority; `AuditLog` records transfers. |
| F-06 Duplicate invitation state | **DELETE** | Delete `PendingInvitation` and its bridging signals after preserving invite-before-signup behavior directly through `CompanyInvitation`. |
| F-07 Three RBAC mechanisms | **SIMPLIFY** | Keep `Role`, Django `Permission`, and `get_effective_permissions()`. Remove hard-coded role permission sets and Guardian if final assignment/reference checks show no required object permissions. Do not create an authorization app. |
| F-08 Weak role/membership lifecycle | **SIMPLIFY** | Change assigned-role deletion to `PROTECT` and make role required after data repair. Do **not** add membership status/suspension for MVP; removal deletes membership through a guarded service and the audit row preserves the action. |
| F-09 No durable provisioning state machine | **REJECT RECOMMENDATION** | Do not add a provisioning workflow/state machine or background provisioning system. Keep one synchronous service, validate before creation, record failure in logs/audit, and perform best-effort cleanup of a newly failed tenant. Add a retry command only if real failures demonstrate the need. |
| F-10 Tenant lifecycle represented by deletion boolean | **SIMPLIFY** | Keep `is_deleted` as archive state and add only `is_suspended` for platform suspension. Do not replace booleans with a multi-state lifecycle enum before launch. Provisioning is synchronous: a saved usable tenant is active; failed creation is cleaned up. |
| F-11 Subscription semantics fragmented | **SIMPLIFY** | Keep one workspace `Subscription`, `Plan`, and existing effective entitlement rows. Consolidate checks behind two small functions: subscription usable and entitlement value. Delete unused plan flags only after reference proof. No generic policy engine. |
| F-12 Tenant context is convention | **FIX NOW** | Require explicit tenant identity and context for every tenant command/job. Fix display-name/schema confusion and add shared helper functions plus two-tenant tests. A helper is enough; no task framework is required. |
| F-13 Audit not a complete security ledger | **KEEP AS-IS** | Keep `AuditLog` and ensure required services emit events. Do not build append-only database enforcement or an event-sourcing system for MVP. Make admin read-only as a small hardening step when touched. |
| F-14 Public notifications coupled to requests | **DEFER POST-MVP** | Synchronous allauth/invitation email is acceptable for first release if failure is visible and resend exists. Do not add a public email-delivery table, outbox, or worker merely for invitations. Tenant operational notifications remain in Notify v2. |
| F-15 Missing correlation and boundary alarms | **DEFER POST-MVP** | Keep schema-aware logs and Django error reporting. Add basic health checks before deployment, but defer structured correlation infrastructure and dashboards until operations justify them. |
| F-16 Incomplete adversarial isolation proof | **FIX NOW** | Add a compact two-tenant production test gate for middleware, commands/jobs, cache/files, and cross-tenant identifiers. Do not attempt to rewrite the entire test suite. |

## 4. Recommendations explicitly not adopted

### 4.1 No provisioning state machine

The audit proposed `PROVISIONING`, `ACTIVE`, `PROVISIONING_FAILED`, `SUSPENDED`, and `ARCHIVED`. This is too much state for synchronous MVP provisioning and creates difficult transition, recovery, and UI obligations. The target uses:

- successful creation means active;
- `is_suspended` means platform access is temporarily blocked;
- `is_deleted` means owner-initiated recoverable archive;
- failed new provisioning is logged, audited where a Company row exists, and cleaned up.

If production evidence shows partial provisioning cannot be cleaned up reliably, a failure state may be added later.

### 4.2 No membership suspension lifecycle

The MVP needs add, role-change, leave, and remove. A separate membership status duplicates the effect of removal and complicates unique membership, reinvitation, seat counting, and every authorization query. Removal through a guarded service plus an audit event is sufficient. Tenant-wide suspension belongs to `Company`, not every membership.

### 4.3 No generic subscription access-mode engine

A `FULL`, `READ_ONLY`, `BILLING_ONLY`, `SUSPENDED` policy object is attractive but premature. The launch rules need only:

- membership is required to enter a tenant;
- billing pages remain reachable by authorized owners/admins;
- plan-gated actions call the entitlement service;
- a non-usable subscription blocks normal paid mutations or module entry according to a small documented route matrix.

These rules can be expressed with decorators/mixins and two service functions. Read-only grace mode should be added only when a commercial policy requires it.

### 4.4 No public notification job subsystem

Invitation and identity email volume is initially low. Synchronous delivery with visible errors and resend is operationally adequate. A public outbox, retry worker, delivery-attempt model, and provider abstraction would add deployment and correctness burden. Notify v2 remains tenant operational messaging; it should not absorb global authentication email.

### 4.5 No database-enforced append-only audit framework

The existing public `AuditLog` is adequate evidence for MVP administrative actions. Read-only admin and service-owned writes are enough. Triggers, hash chains, event sourcing, and a separate audit service are rejected.

### 4.6 No premature migration squash or development database reset requirement

Historical migrations are noisy but functional. They do not affect runtime comprehensibility. Perform ordinary migrations for accepted target changes. Revisit a squash only immediately before a stable production baseline and only if clean-install and upgrade tests justify it.

### 4.7 No billing-admin role for MVP

The proposed subscription ADR suggests a dedicated billing-admin capability. The first release can restrict billing management to workspace Owner and Admin. A separate billing role is deferred until a real customer needs delegated billing without operational administration.

### 4.8 No entitlement override system beyond what already exists

Keep existing `SubscriptionEntitlement` rows if they are already used as effective snapshots. Do not add enterprise overrides, policy documents, rule precedence, or per-user entitlements. Entitlements belong to the tenant subscription only.

## 5. Core models and responsibilities

### 5.1 Public-schema models

#### `accounts.CustomUser`

- Global authentication identity.
- One account may belong to many workspaces.
- Email is unique. Verification is required for invitation acceptance, not ordinary tenant access.
- Contains no tenant ownership or active-tenant authority.

#### `accounts.UserProfile`

- Personal timezone, avatar, phone and address.
- `workspace` may remain temporarily as last-selected navigation preference.
- It must never select a database schema or authorize access.
- Longer term, rename the field to make the preference semantics explicit; this is not required in the first safety phase.

#### `orgs.Company`

- The `django-tenants` tenant registry model.
- Owns immutable `schema_name`, display name, current owner, archive flag, suspension flag, branding and timestamps.
- `auto_drop_schema` remains false.
- Does not own plan features, module settings, business policy, or tenant business data.

#### `orgs.Domain`

- Maps a validated host to one Company.
- Domain resolution is authoritative when present.
- A domain never supplies authorization; membership is still required.

#### `orgs.Membership`

- The sole user-to-company access relationship.
- Unique `(user, company)`.
- Has exactly one required Role.
- Existence means active membership; removal deletes it through a guarded service.
- Owner membership cannot be removed while the user is `Company.owner`.

#### `orgs.Role`

- A small global catalog of workspace roles: Owner, Admin, Member, Viewer, and Accountant only if current accounting behavior requires it.
- Holds Django `Permission` rows as the single permission source.
- Names are stable seeded identifiers, not arbitrary tenant-defined roles for MVP.
- Assigned roles use `PROTECT`.

#### `orgs.CompanyInvitation`

- The only invitation record.
- Belongs to Company and Role; records inviter, normalized email, key, sent time, status and response time.
- Pending uniqueness is case-insensitive per `(company, email)`.
- Owns pending, accepted, declined, revoked and derived expired behavior.

#### `orgs.AuditLog`

- Records important public control-plane/security actions.
- Required for workspace create/archive/restore/suspend/reactivate, invitation lifecycle, membership add/remove, role change, ownership transfer, subscription changes, platform override and denied tenant access.
- It is evidence, not a domain event bus and not a source of current state.

#### `subscriptions.Plan`

- Global commercial offer.
- Contains only currently sold plan identity, price/billing cycle, trial duration, active flag, and limits/features actually enforced at launch.
- Unreferenced speculative flags should be removed after a usage inventory.

#### `subscriptions.Subscription`

- Exactly one workspace billing contract.
- Belongs to Company, never User.
- Stores plan, lifecycle status, relevant dates, renewal/cancellation fields and provider subscription identifier.
- Subscription status does not prove user authorization and does not choose schema.

#### `subscriptions.SubscriptionEntitlement`

- Effective tenant-level feature or numeric limit attached to the Subscription.
- Used only for features/limits actually enforced.
- Absence follows an explicit default per known entitlement; it must not silently mean “allowed” for a paid feature.
- No per-user entitlement rows.

#### Existing billing evidence models

- Keep `BillingAccount`, `ProviderWebhookEvent`, and `SubscriptionEvent` because provider association, replay safety and lifecycle evidence are current concrete needs.
- Do not add Invoice/Payment models until the application stores its own invoice/payment records rather than provider references.

#### `onboarding` models

- Keep existing progress/setup records only for UX continuity.
- They do not own Company lifecycle, permissions, subscription policy, or schema operations.

### 5.2 Tenant-schema models

Tenant schemas own all workspace operational data:

- Party/customer/supplier and portal grants.
- Pawn and funding loans, collateral, schedules, repayments, releases, custody and loan evidence.
- Accounting ledgers, periods, vouchers, journal entries and immutable posting evidence.
- Product, inventory and rates.
- Tenant configuration that affects business calculations or compliance.
- Notify v2 templates, tenant provider configuration, notice intents, jobs, attempts and receipts.
- Tenant files/documents and their authorization metadata.

Tenant models may reference the shared user model for actor evidence because shared tables are visible on the tenant search path. They must not use public Company rows as a substitute for tenant isolation. Existing explicit workspace fields in tenant models are defense-in-depth and must match `request.tenant`/active schema where present.

## 6. App responsibility and dependency direction

Allowed direction:

```text
accounts
   ^
   |
orgs <-------- onboarding
   ^               |
   |               v
subscriptions   orgs provisioning API
   ^
   |
tenant apps ---- orgs context/RBAC API
   |
   +------------ subscriptions entitlement API
```

Rules:

1. `accounts` must not import tenant business apps.
2. `orgs` may depend on accounts and `django-tenants`; its core membership/tenant resolution must not depend on subscriptions.
3. `subscriptions` may depend on Company and Membership for workspace/billing administration and seat limits.
4. `onboarding` calls orgs and subscriptions services; it does not implement provisioning itself.
5. Tenant apps consume stable orgs permission/context functions and subscription entitlement functions.
6. `orgs`, accounts and subscriptions must not import Loans, Girvi, DEA, Product, Party or Notify models.
7. Tenant-to-public reads requiring a schema change belong in a named integration/facade function. Views and model methods must not scatter `schema_context("public")` calls.
8. Cross-tenant loops exist only in platform management commands/jobs, never normal request services.

## 7. Identity, membership and RBAC

### Canonical model

```text
User
  -> Membership(user, company, role)
      -> Role
          -> Django Permission codenames
```

`Company.owner` is a separate invariant identifying the single legal/administrative owner. It does not bypass the requirement for an Owner membership.

### Permission evaluation

`get_effective_permissions(user, company)` remains the canonical API:

1. platform admin receives the documented global override;
2. non-members receive an empty set;
3. members receive the permissions assigned to their Role;
4. tenant app decorators/mixins ask for explicit permission codenames;
5. templates use permissions only to hide/show controls and never provide the enforcement boundary;
6. mutation services enforce critical domain permissions again when callable outside their HTTP view.

Hard-coded role-name permission maps should not remain alongside `Role.permissions`. Guardian object permissions should be removed if no production requirement and no active assignments are found. Object ownership rules such as “this portal user may see this Party” remain explicit tenant-domain selector rules, not Guardian assignments.

### Platform administrators

- `is_platform_admin()` is the only global bypass.
- Platform access must be logged.
- Platform admin does not silently impersonate a tenant user.
- A support impersonation framework is post-MVP.

## 8. Subscription and entitlement model

### Canonical model

```text
Company
  -> Subscription
      -> Plan
      -> SubscriptionEntitlement(feature_code, enabled/value)
```

### Separation of decisions

Authorization:

> Does this membership’s role allow the action?

Entitlement:

> Does this workspace’s current subscription enable the module/feature or capacity?

Both are required for a plan-gated action. An Owner does not receive an unpaid feature by ownership, and a paid feature does not grant a Member an administrative permission.

### Minimal service API

Keep or reshape existing services toward only these operations:

- `subscription_is_usable(company) -> bool/decision`
- `get_entitlement(company, code) -> enabled/value`
- `require_entitlement(company, code)`
- `check_capacity(company, code, current, increment=1)`

Do not pass User or Membership into pure entitlement evaluation. Billing-management views check RBAC separately.

### MVP commercial policy

- Trial and active subscriptions are usable.
- Past-due, cancelled and expired behavior must be explicitly mapped per route before implementation; do not let middleware invent it.
- Billing/subscription management remains reachable to Owner/Admin even when normal paid access is blocked.
- Seat limits are enforced atomically before invitation creation and direct membership creation.
- Only real launch feature codes remain. Unknown entitlement codes fail closed.
- No enterprise override hierarchy, per-user entitlement, usage-metering platform, or billing-admin role.

## 9. Invitation lifecycle

```text
PENDING
  -> ACCEPTED
  -> DECLINED
  -> REVOKED
  -> EXPIRED (derived from sent time + configured expiry)
```

Rules:

1. Inviter must have `team_invite` permission.
2. Email is normalized before lookup/storage.
3. One pending invitation per normalized email/company.
4. Invitation stores the intended Role.
5. Seat capacity is checked at invitation and checked again inside acceptance transaction.
6. Acceptance requires an authenticated account with a verified `EmailAddress` whose normalized email matches the invitation.
7. Acceptance locks/rechecks the invitation, creates or confirms one Membership, then marks accepted atomically.
8. Repeated acceptance is idempotent and cannot change an existing member’s role silently.
9. Revocation/decline/expiry never creates a Membership.
10. `PendingInvitation` does not exist in the target.
11. Email failure leaves a pending invitation that can be resent; it does not require a delivery subsystem for MVP.

## 10. Tenant lifecycle

The MVP lifecycle is deliberately small:

```text
create successfully -> active
active <-> suspended       (platform operator)
active -> archived         (owner/platform; recoverable)
archived -> active         (owner/platform restore)
```

Representation:

- `is_suspended`: platform operational/security suspension.
- `is_deleted`: recoverable archive, retained for compatibility and clear current behavior.
- subscription state remains separate.

Rules:

1. Public tenant can never be suspended, archived or hard deleted through workspace services.
2. A suspended or archived Company cannot enter its tenant schema through normal application requests.
3. Archive preserves Company, Domain, schema, files, membership, audit and billing evidence.
4. Restore does not silently alter subscription status.
5. Hard schema deletion is not an MVP user lifecycle. It is disabled by default and reserved for explicitly approved operations/development cleanup.
6. Provisioning is one synchronous orchestration. Validation occurs before Company creation; the service cleans up fresh partial artifacts on failure.
7. Schema name is immutable once Company creation succeeds.

## 11. Ownership rules

1. `Company.owner` is the only current-owner authority.
2. Exactly one owner exists for every non-public Company.
3. Owner must have an Owner-role Membership in the Company.
4. Owner membership cannot be removed, downgraded or used to leave while ownership remains.
5. Ownership transfer requires the current owner or platform admin and a target user with a verified account.
6. Transfer runs under `transaction.atomic()` with the Company and relevant Membership rows locked.
7. The service creates/updates the new owner membership, changes `Company.owner`, converts the old owner to Admin (unless an explicit reviewed choice says otherwise), and writes one audit event.
8. `Company.creator` remains historical provenance only and grants no rights.
9. `CompanyOwnership` is removed; ownership history is read from audit evidence.

## 12. Critical invariants

### Identity and access

1. One global account per normalized email; the invited email must be verified before invitation acceptance.
2. One Membership per `(user, company)`.
3. Every Membership has one protected Role.
4. No membership means no tenant access, regardless of profile selection or subscription.
5. Exactly one Company owner with a matching Owner membership.

### Tenancy

6. `schema_name` is valid, unique, reserved-name safe and immutable.
7. Domain/path tenant identity is authoritative; profile state is never authoritative.
8. Membership and tenant availability are checked in public before `set_tenant`.
9. Tenant ORM work occurs only after explicit tenant context is established.
10. A request/job never retains the prior tenant’s context after completion.
11. Public-schema code does not query tenant models.

### Invitations and billing

12. One pending invitation per normalized email/company; acceptance is atomic and idempotent.
13. Subscription belongs to Company, not User.
14. Permission and entitlement decisions are independent.
15. Unknown paid features fail closed; seat capacity is checked transactionally.

### Lifecycle and evidence

16. Archive never drops schema or tenant files.
17. Hard delete is disabled by default and never exposed in ordinary UI.
18. Posted accounting evidence is unaffected by SaaS lifecycle changes.
19. Security/control-plane mutations emit AuditLog evidence.
20. Tenant files, caches, jobs and provider callbacks carry tenant identity.

## 13. Tenant-context rules

### 13.1 HTTP requests

Public routes:

- Explicitly reset to public schema.
- Use public URLConf.
- May read only shared/control-plane models.
- `UserProfile.workspace` may choose a redirect target but not a schema.

Tenant routes:

1. Reset to public before tenant registry lookup.
2. Resolve Company from validated domain or canonical `/w/<schema_name>/` path.
3. If both exist, they must identify the same Company.
4. Require authentication, non-archived/non-suspended Company and Membership.
5. Call `connection.set_tenant(company)` once.
6. Set `request.tenant`; downstream code uses it as the workspace authority.
7. Apply RBAC at view and critical service boundaries.
8. Apply subscription/entitlement checks only to mapped paid surfaces.
9. Error/redirect paths reset public context when leaving the tenant route plane.

Legacy tenant routes that lack domain/path identity may remain only as redirects to canonical routes. They must not use profile fallback to execute tenant views.

### 13.2 Management commands

- Shared-only commands explicitly enter public schema.
- Single-tenant commands require `--schema` (preferred) or immutable Company ID, resolve Company in public, reject public/archived/suspended where appropriate, and wrap all tenant ORM in `tenant_context(company)`.
- All-tenant commands enumerate Company rows in public, then enter/exit each tenant independently.
- Never use Company display name as schema identifier.
- Assert/log schema at the unit-of-work boundary.
- One tenant failure must not cause the next tenant to inherit its schema; command exit behavior must report failures.
- Schema migrations use `migrate_schemas`; shared model changes use `migrate_schemas --shared`.

### 13.3 Background jobs

- Every tenant job payload includes `company_id` or `schema_name`; never a model instance or selected-profile state.
- Job begins in/reset to public, resolves the Company, validates expected availability, enters `tenant_context`, asserts the active schema, performs one bounded unit of work, and exits.
- Retry/idempotency belongs to the concrete operation, not a generic SaaS framework.
- Scheduled all-tenant work dispatches or iterates one explicit tenant unit at a time.
- Cache keys, file paths, logs and provider identifiers include tenant identity.
- Provider callbacks must cryptographically authenticate and resolve exactly one tenant before tenant ORM access.

## 14. Components to keep

- `django-tenants`, PostgreSQL schema tenancy and `TenantSyncRouter`.
- Current `SHARED_APPS`/`TENANT_APPS` boundary, subject to legacy app retirement plans.
- `CustomUser` and allauth.
- `Company`, `Domain`, `Membership`, `Role`, `CompanyInvitation`, `AuditLog`.
- `UserProfile` as personal/navigation state.
- `Plan`, `Subscription`, `SubscriptionEntitlement`, `BillingAccount`, provider/subscription event models.
- `get_effective_permissions()` as the stable RBAC API.
- `resolve_request_workspace()` with `request.tenant` authority and no default profile fallback.
- Custom workspace middleware’s membership-before-schema-switch property.
- `auto_drop_schema=False`, recoverable archive/restore, tenant-aware cache/file/log configuration.
- Explicit orgs control-plane services and tenant-app domain services.
- Tenant-aware test runner and `migrate_schemas` guidance.
- Notify v2 as tenant operational delivery; legacy Notify follows its separately accepted retirement plan.

## 15. Components to consolidate

1. Workspace creation paths into one orgs provisioning service used by onboarding and any admin/operator entrypoint.
2. Workspace switching/resolution into authoritative domain/path resolution plus navigation-only profile preference.
3. Team invitation, acceptance, membership mutation and ownership transfer into small transactional orgs services.
4. Permission calculation into `Role.permissions` + `get_effective_permissions()`.
5. Subscription usability and entitlement lookup into the minimal subscriptions service API.
6. Repeated tenant-app permission wrapper implementations where a shared helper can remove exact duplication without erasing domain-specific permission names.
7. Tenant command/job context setup into small helpers for public resolution and `tenant_context`; do not build a framework.
8. Subscription enforcement currently split between workspace middleware, subscription middleware, decorators and context processors into explicit route/service guards. Context processors remain display-only.

## 16. Components to delete

Delete only after reference search, data inspection, characterization tests and target approval:

- `PendingInvitation` and its signal bridge.
- `CompanyOwnership` current/history model.
- Hard-coded `RolePermissions` sets once database role permissions are complete.
- Guardian dependency, backend and decorators if no required object assignments exist.
- Duplicate subscription middleware after route guards replace it.
- Any duplicate automatic tenant-seeding signal if explicit provisioning already performs seeding.
- Commented obsolete fields/deletion implementations in `accounts.models` and similar foundation files.
- `django_project/old_settings.py` after deployment/import search.
- Unused Plan flags/limits demonstrated to have no runtime, template, test, seed or reporting consumer.
- Legacy tenant-executing profile-fallback routes after canonical redirects are complete.

Do not delete Contact, Girvi, legacy Notify, or other tenant business compatibility surfaces as part of this SaaS foundation change. They have separate domain cutover requirements.

## 17. Required database changes

Shared schema only unless noted:

1. Add `Company.is_suspended` with default false.
2. Change `Membership.role` to `PROTECT`; repair null roles, then make non-null.
3. Reconcile owner/member/role inconsistencies before adding service guardrails. A database constraint cannot easily enforce cross-table owner membership, so service transactions plus consistency checks are canonical.
4. Normalize invitation emails and implement PostgreSQL case-insensitive pending uniqueness. Prefer an expression/conditional unique constraint compatible with the chosen Django/PostgreSQL versions.
5. Remove `PendingInvitation` after backfill/reconciliation proves `CompanyInvitation` is sufficient.
6. Remove `CompanyOwnership` after ownership reconciliation.
7. Migrate role permissions into `Role.permissions`, then remove competing hard-coded permission policy.
8. Remove Guardian tables/dependency only after assignment verification and clean migration planning; leaving unused historical tables temporarily is safer than a rushed destructive migration.
9. Remove unused Plan fields only after a documented usage inventory.
10. No tenant-schema model changes are intrinsically required for the core architecture. Tenant apps may need targeted context/assertion fixes without schema changes.

Migration execution rules:

- Create ordinary forward migrations; do not reset or squash as part of this work.
- Apply shared changes with `migrate_schemas --shared` and validate tenant migration state with `migrate_schemas`.
- Test a clean database and the current development upgrade path.
- Back up/reconcile public control-plane rows before destructive cleanup migrations.

## 18. Required production tests

### P0 isolation and identity

1. An unverified invited email blocks invitation acceptance and membership creation; ordinary signup and existing membership access remain unchanged.
2. Two Companies and schemas contain rows with identical primary keys; each domain/path sees only its own row.
3. Profile workspace poisoning cannot select a schema.
4. Domain/path mismatch is denied and audited.
5. Unknown domain and legacy root routes cannot inherit a tenant schema.
6. Archived and suspended Companies cannot enter tenant context.
7. Connection begins from a stale tenant and middleware/command/job safely resets and selects the intended tenant.

### P0 membership, ownership and RBAC

8. Non-member denied before `set_tenant`; platform override is explicit and audited.
9. Owner/Admin/Member/Viewer/Accountant permission matrix for representative read/mutation/admin/accounting actions.
10. Assigned Role cannot be deleted; Membership cannot have null role.
11. Owner cannot leave, be removed or downgraded before transfer.
12. Concurrent ownership transfer leaves exactly one owner and correct memberships.

### P0 invitation and tenant context

13. Invite new user, invite existing user, wrong email, unverified email, expiry, decline, revoke and replay.
14. Concurrent acceptance produces one Membership and one accepted invitation.
15. Seat limit checked at invite and acceptance.
16. Tenant command/job requires explicit tenant, rejects display-name lookup, processes two tenants independently, restores context and reports partial failure.

### P1 subscription and lifecycle

17. Trial/active/past-due/cancelled/expired route matrix.
18. Billing management remains reachable to authorized Owner/Admin when normal paid access is blocked.
19. Permission cannot grant a missing entitlement; entitlement cannot grant a missing permission.
20. Unknown feature code fails closed; numeric limits are enforced atomically.
21. Archive/restore preserves schema/data/files and never changes subscription silently.
22. Hard delete is false by default, unavailable in ordinary UI/bulk admin, and public tenant cannot be deleted.

### P1 boundary infrastructure

23. Cache keys and identical filenames do not cross tenants.
24. File download rechecks tenant and object permission; direct storage URL is not an authorization boundary.
25. Provider webhook signature, tenant association and replay idempotency.
26. Required AuditLog events are emitted for all control-plane mutations and denied access.
27. Clean install, shared migrations, tenant migrations and migration drift checks pass.

## 19. Ordered implementation phases

No phase begins until this architecture is accepted. Each phase must leave the repository deployable and update `docs/STATUS.md`.

### Phase 0 — Characterize and reconcile

Objective: prove current behavior and data before changing authority.

- Inventory Guardian assignments, role permissions, Plan field usage, `PendingInvitation`, `CompanyOwnership`, profile-fallback routes, subscription guards and seeding paths.
- Add focused characterization for signup/invite, tenant resolution, subscription routes and ownership.
- Add consistency commands or read-only reports for owner membership, null roles, duplicate/case-variant invitations and subscription cardinality.
- No deletions or semantic changes.

### Phase 1 — Isolation and destructive-operation safety

Objective: remove launch-critical tenant boundary risks.

- Disable hard delete by default and remove ordinary/bulk exposure.
- Require a matching verified allauth `EmailAddress` inside the invitation-acceptance service.
- Remove profile fallback from schema selection; convert remaining legacy entrypoints to redirects.
- Add `is_suspended` and enforce archive/suspension before schema switch.
- Fix tenant commands/jobs and display-name schema usage.
- Add adversarial two-tenant tests.

### Phase 2 — Canonical membership, ownership and invitations

Objective: establish one access graph and one source of truth.

- Protect and require Membership role after repair.
- Implement/standardize guarded transactional membership and ownership services.
- Reconcile and delete `CompanyOwnership`.
- Move invite-before-signup behavior to `CompanyInvitation`; reconcile and delete `PendingInvitation`/signals.
- Normalize invitation email and add correct uniqueness/idempotency tests.

### Phase 3 — RBAC consolidation

Objective: one permission source and evaluation API.

- Build permission matrix from current behavior.
- Seed `Role.permissions` completely.
- Make `get_effective_permissions()` consume that source.
- Remove hard-coded role maps.
- Remove Guardian only after assignment/reference proof.
- Migrate tenant module guards in small tested groups; do not rename all permission codes cosmetically.

### Phase 4 — Subscription and entitlement separation

Objective: ensure billing never chooses tenant identity and entitlement never replaces authorization.

- Publish the route/status/feature matrix for the actual launch plans.
- Simplify subscriptions service API.
- Remove subscription decision from workspace schema admission.
- Replace duplicate middleware enforcement with explicit paid-surface guards.
- Keep Owner/Admin billing recovery reachable.
- Remove only proven-unused Plan fields.

### Phase 5 — Provisioning consolidation and production gate

Objective: one understandable creation path and launch proof.

- Consolidate onboarding/admin creation into one synchronous orgs service.
- Validate schema/domain/owner/plan inputs before creation.
- Remove duplicate seed trigger; add failure cleanup and operator-readable error/audit behavior.
- Run complete required production test suite, clean install and tenant-aware migration checks.
- Update deployment/runbook documentation.

### Post-MVP

- Async/retryable identity and invitation email if delivery volume/failures justify it.
- Request correlation and richer operational dashboards.
- Delayed legal-retention purge/export/erasure workflow.
- Delegated billing permission/role.
- Read-only grace mode if commercial policy requires it.
- Custom tenant roles or object permissions if a concrete use case cannot be expressed by built-in roles and domain selectors.
- RLS migration preparation/execution only under its separate architecture program.

## 20. Acceptance summary

The canonical MVP foundation is four existing application boundaries:

- `accounts`: global identity and proof of invited-email ownership;
- `orgs`: tenant registry, membership, simple RBAC, invitations, ownership and audit;
- `subscriptions`: workspace billing and explicit tenant entitlements;
- tenant apps: isolated business data and workflows.

The design becomes production-worthy by removing ambiguous authority, not by adding layers. Domain/path chooses the tenant, Membership chooses who enters, Role permissions choose what the member may do, Subscription entitlements choose what the workspace has purchased, and the PostgreSQL schema contains the workspace’s business data. Every background boundary carries tenant identity explicitly. Archive is recoverable; schema deletion is exceptional. This is the smallest coherent architecture that protects tenant isolation, authorization and business evidence without turning the MVP into an enterprise platform project.
