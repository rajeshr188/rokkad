---
status: proposed
owner: project
updated: 2026-08-13
tags: [configuration, preferences, django-tenants, loans, architecture, audit]
related:
  - ../plans/centralized-preferences-architecture-plan.md
  - dynamic-preferences.md
  - django-tenants-architecture-audit.md
  - ../domain/loans-regulatory-setup-and-policy.md
  - ../constitution.md
---

# Settings and Configuration Architecture Audit

## 1. Executive summary

Configuration is fragmented across deployment settings, two public-schema
`django-dynamic-preferences` per-instance registries, global and user preference
tables, shared control-plane models, typed tenant-domain policy models, model
defaults, service constants, JSON payloads, seed commands, and historical
snapshots. The repository has already started correcting this: the new Loans app
uses effective-dated typed policies and immutable approval/disbursal snapshots,
and DEA/Accounting own sequences and periods as domain state. That architecture
is substantially safer than the older Girvi preference design.

The current `apps.configuration` foundation should therefore be narrowed, not
expanded into a universal settings system. Its public-schema
`WorkspacePreferenceModel` is appropriate for lightweight control-plane flags
and UI defaults explicitly keyed by `Company`, but it is the wrong destination
for financial calculation, accounting, numbering, risk, compliance, document,
inventory valuation, or integration policy. Most of its registered keys have no
runtime consumer and duplicate newer typed models or domain records.

Recommended direction:

1. Keep environment/Django settings for deployment topology and platform
   secrets.
2. Keep public-schema typed models for tenant registry, membership,
   subscriptions/entitlements, global person preferences, and membership UI
   preferences.
3. Keep business policy in typed, domain-owned models inside tenant schemas.
4. Preserve contractual terms and policy provenance on immutable loan/document/
   accounting snapshots.
5. Retain dynamic preferences only for low-risk UI/display state and, during
   migration, the three audited control-plane switches currently in use.
6. Retire duplicate central registrations and the legacy Girvi registry after
   typed migration or Girvi retirement evidence exists.

The highest immediate risks are not missing abstraction. They are: public-table
preference reads that look tenant-local but are not; global fallbacks for
business-critical policy; duplicated legacy and central keys; mutable Girvi
workflow preferences; membership-specific UI values stored as global user
preferences; broad exception swallowing in preference reads; and tenant jobs or
commands that can run with the wrong schema.

## 2. Current django-tenants architecture

### Schema boundary

```text
public schema
  django_tenants + apps.orgs (Company, Domain, Membership, invitations)
  auth/accounts (global CustomUser and UserProfile)
  apps.configuration + dynamic_preferences + dynamic_preferences.users
  onboarding, subscriptions, pages, sessions, allauth and other shared apps

tenant schema selected by Company.schema_name
  contact, party, loans, accounting, girvi, product, terms, rates,
  notify, notify_v2, dea
```

`Company(TenantMixin)` is the tenant model and `Domain(DomainMixin)` is the
domain model. `Company.auto_create_schema=True` and `auto_drop_schema=False`.
`TENANT_MODEL` and `TENANT_DOMAIN_MODEL` point to these models. The configured
router is `TenantSyncRouter`; tenant migrations must use `migrate_schemas`.

Authentication is shared. `accounts.CustomUser` is in `SHARED_APPS`, so one
person has one public user identity and can belong to multiple workspaces.
`apps.orgs.Membership` is a public-schema `user + company + role` association.
Workspace switching resolves a `Company`, verifies membership, then
`SecureWorkspaceMiddleware` calls `connection.set_tenant(workspace)`. Public
operations reset or explicitly enter the public schema. `UserProfile.workspace`
is a selected-workspace compatibility pointer, not membership or tenant
ownership.

Tenant creation occurs through the onboarding/control-plane services. Normal
save can create the schema; clone mode can create the public `Company` without
automatic schema creation and then provision explicitly. Default tenant data is
seeded by `seed_workspace_defaults`; `seed_all_workspaces` and parity checks operate
cross-tenant. `apps.orgs.signals` reacts to Company creation, with automatic
seeding gated by `TENANT_AUTO_SEED_ON_CREATE`. Mandatory business configuration
must not be added to a generic `post_save` receiver because Company signals run
in control-plane context and schema readiness varies.

Tests commonly create `Company(auto_create_schema=False)` for public-only
configuration tests, or create a real tenant and call
`connection.set_tenant(self.tenant)`/`schema_context(...)` for tenant models.
`TenantAwareDiscoverRunner` is configured. Runtime helpers include
`schema_context`, `tenant_context`, `connection.set_tenant`,
`connection.set_schema_to_public`, and `apps.orgs.tenant_context` for request
workspace resolution.

### Where preference tables actually live

Because `dynamic_preferences`, `dynamic_preferences.users`, `apps.configuration`,
and `apps.orgs` are shared-only apps, these tables are physically in `public`:

- package global preference table;
- package `UserPreferenceModel` table;
- `configuration.WorkspacePreferenceModel`;
- legacy `orgs.CompanyPreferenceModel`;
- `configuration.PreferenceAuditLog`.

Workspace preference rows are separated logically by a foreign key to public
`Company`, not physically by tenant schema. They remain visible through the
PostgreSQL search path while a tenant schema is active. This is valid for a
control-plane store, but the code and documentation must not describe it as
tenant-schema configuration. Dynamic-preferences registration is process-wide;
schema switching does not change which registry is selected.

## 3. Current configuration inventory

| Configuration or mechanism | Current location/storage | Scope and consumers | Significance / duplicate | Recommended destination |
| --- | --- | --- | --- | --- |
| Database, hosts, email, security, tenancy, storage, cache | `django_project/settings/*.py`, environment | Deployment | Critical; some unsafe literal/default values | Keep in environment/settings; validate at startup |
| SMTP, Razorpay, Google OAuth, workspace encryption key, Meta API version | settings/environment | Platform secret/config | Secrets are correctly outside preference APIs; test Razorpay defaults are unsafe outside dev | Secret manager/environment with fail-closed production checks |
| `Company`, `Domain`, `Membership`, invitations | `apps.orgs`, public tables | SaaS control plane | Correct schema | Keep typed public models |
| Plans, subscriptions, entitlements, billing | `apps.subscriptions`, public tables | Platform/tenant subscription | Correctly domain-owned | Keep typed public models; capability checks precede tenant options |
| Central global/workspace/user preferences | `apps.configuration` and package tables, public | Platform fallback, workspace override, user UI | Mixed ownership; most registrations unused | Narrow to UI/control-plane; remove business catalog |
| Legacy Girvi preferences | Girvi registrations + `orgs.CompanyPreferenceModel`, public | Workspace loan defaults/policy | Duplicates central keys and newer Loans models | Typed Girvi policy during coexistence or retire with Girvi |
| Accounting integration/activation/workflow switches | central workspace preferences, public | Runtime flags in Loans/Girvi/Accounting | Active and audited, but activation/workflow are operational state/policy | Move to typed public capability/rollout state or typed tenant `AccountingSettings`; keep adapter during migration |
| Accounting periods, books, ledgers, currency config and sequences | Accounting/DEA tenant models | Tenant domain | Correct typed state; duplicates registered preference ideas | Keep domain models; delete unused preference registrations |
| Loans economic/rate/fee/monitoring policies | Loans tenant models | Workspace/license effective-dated policy | Correct model, constraints and versioning | Keep; use selectors/services only |
| Loan products and immutable versions | Loans tenant models | Product defaults and contractual product definition | Correct | Keep typed/versioned domain models |
| Loan approval, disbursal and policy snapshots | Loans tenant models/JSON snapshots | Per-loan historical fact | Correct historical boundary | Keep immutable; include source IDs/versions and normalized critical fields |
| Loan/Girvi numbering | tenant sequence/series models | Tenant/license/series | Correct domain state; central prefixes/strategy duplicate it | Keep locked typed sequences |
| Loan document layouts, revisions, assignments, print profiles and issues | Loans tenant models | Tenant configuration + historical issue | Correct versioned domain design | Keep; delete generic document-template preferences |
| Loan monitoring/risk thresholds | `LoanMonitoringPolicy`, tenant | Current effective-dated risk policy | Correct; JSON used only for extensible mapping | Keep typed; strengthen DB ordering constraints |
| Loan communication policy/consents | Loans tenant models | Current tenant policy and party/loan evidence | Correct domain ownership | Keep typed; snapshot consent/template/provider evidence on sends |
| Notify event types, policies, templates, integrations | notify/notify_v2 tenant models | Tenant notification/integration config | Seeded typed domain data | Keep; remove duplicate notification preferences unless consumed |
| Currency, rates, commodity defaults | rates/DEA tenant models plus unused preferences | Tenant domain/current facts | Duplicated | Prefer domain models and explicit selection services |
| Inventory valuation/unit/barcode defaults | unused central preferences plus model defaults | Tenant domain | Registered but no proven consumer | Introduce typed Product/Inventory settings only when a workflow needs them; otherwise delete |
| UI page size, theme, landing page, widgets | dynamic user/workspace preferences, public | Person or membership UI | Appropriate type, wrong scope for workspace-specific values | Global `UserPreferences` for person-wide; `MembershipPreferences` for workspace UI |
| Selected workspace | `UserProfile.workspace` and session/request | User/session navigation | Compatibility state, not a business preference | Prefer session selection; retain pointer only as documented fallback |
| Seed defaults | orgs/party/notify/DEA/Loans commands and migrations | Tenant baseline | Multiple entry points can drift | One idempotent provisioning orchestrator invoking domain seeders |
| Constants/model field defaults | domain/models/services | Code baseline | Some are safe constructor defaults; others silently become policy | Treat as bootstrap defaults only and expose typed policy before runtime variability |
| JSON configuration | policy mappings, document definitions, snapshots | Mixed | Valid for layouts/evidence; risky for core financial values | Typed fields for invariants; versioned JSON only for bounded extensibility/evidence |

### Dynamic-preferences usage reality

The central registry currently declares 68 keys: 5 platform-only, 57
workspace+global, and 6 user keys. Repository call-site search found meaningful non-test central
runtime reads only for:

- `accounting__integration_mode`;
- `accounting__successor_enabled`;
- `accounting__workflow_mode`.

The Girvi adapter reads 15 legacy keys through the legacy registry. The central
migration command copies those rows to lowercase keys, but current Girvi runtime
continues to resolve the legacy registry, so applying the command does not cut
over the consumer. The remaining central keys are registrations, forms, tests,
or documentation rather than proven runtime configuration.

## 4. Problems and risks

1. **Misleading schema semantics.** A model named workspace preference is in
   public, while important business data is expected to be tenant-local.
2. **Global fallback for business rules.** `get_workspace()` falls back to a
   mutable global row. A platform edit can alter every workspace without an
   explicit tenant decision or policy version.
3. **Duplicate sources.** Legacy `Loan__...`, central `loan__...`, typed Loans
   policies, and code defaults overlap without one authoritative resolver.
4. **Registered-but-unused catalog.** UI exposure suggests settings work even
   when no runtime consumer exists. This is operationally deceptive.
5. **Wrong ownership.** Ledger identifiers, numbering strategy, financial year,
   risk, document assignment, valuation and notification rules are domain
   configuration, not generic strings.
6. **Global/user/membership confusion.** All six UI user keys attach to the
   global user. Dashboard widgets, page size and landing page can reasonably
   differ by workspace and therefore belong to membership.
7. **Historical risk in Girvi.** Interest rates are persisted on loan items and
   deduction amounts/release settlements have snapshot coverage, but accrual
   timing and catch-up/auto-post/backfill flags remain mutable operational
   policy. Their intended temporal effect is not versioned.
8. **Exception swallowing.** `PreferenceService._safe_get()` catches every
   exception and returns a default, potentially hiding registry, database,
   schema or deserialization failures in critical workflows.
9. **Partial audit.** Only writes through `PreferenceService` create
   `PreferenceAuditLog`; package forms/admin/direct manager writes can bypass it.
10. **Weak invariant surface.** Dynamic integer/decimal/string preferences
    cannot enforce cross-field rules, FK existence, effective dating or database
    constraints.
11. **Wrong-schema jobs.** Requests establish tenant context, but jobs,
    commands, signals and callbacks must do so explicitly. Known risky legacy
    examples include a Girvi import command using tenant name as schema and
    task paths called out by the tenancy audit.
12. **Cache ambiguity.** The default cache is tenant-aware, but public-table
    per-workspace managers and the separate `select2` cache make implicit active
    schema an unsafe identity. Explicit workspace/schema keys are required.
13. **Secrets leakage risk.** Workspace integration credentials are database
    configuration, but must remain encrypted and excluded from generic
    preference audit/admin/template serialization. Platform secrets must never
    move into dynamic preferences.

## 5. Proposed configuration taxonomy

| Type | Owner | Mutability/effect | Storage rule |
| --- | --- | --- | --- |
| Deployment/platform configuration | Operator/deployment | Deploy/restart | Environment and Django settings |
| Public SaaS configuration | Platform admin | Current platform behavior | Typed public model; dynamic only for harmless flags |
| Plan capability | Subscription system | Entitlement interval | Typed public Plan/Entitlement records |
| Tenant domain configuration | Workspace authorized role | Current/future tenant behavior | Typed model in tenant schema, owned by domain |
| Branch/location configuration | Tenant branch/location | Current/future scoped behavior | Typed tenant model with branch FK, only when branch exists |
| Global user preference | Person | Presentation across all workspaces | Typed public one-to-one or dynamic user preference |
| Membership preference | Person within workspace | Workspace presentation/default navigation | Typed public membership one-to-one/JSON with allowlisted UI fields |
| Session/UI state | Browser/request | Ephemeral | Session/local storage; no business effect |
| Feature flag | Platform/rollout owner | Temporary release control | Deployment flag or typed public rollout assignment; never financial policy |
| Secret/credential | Platform or tenant integration owner | Rotatable | Environment/secret manager or encrypted tenant integration model |
| Tenant default | Tenant domain | Initializes future records | Typed effective policy/product; snapshot on creation/approval |
| Current tenant policy | Tenant domain | Applies from effective date to eligible operations | Effective-dated typed tenant model |
| Contractual snapshot | Source document | Immutable historical meaning | Normalized immutable fields plus versioned evidence JSON |

## 6. Proposed schema placement

### Public schema

- Company, Domain, global User and UserPreferences;
- Membership and MembershipPreferences;
- invitations, onboarding/provisioning state and workspace audit;
- Plans, subscriptions, entitlements, billing and rollout assignments;
- platform-wide harmless defaults/maintenance state if database-editable;
- encrypted platform-managed integration metadata only when it is genuinely
  cross-tenant (platform secrets remain external).

Public membership preferences are recommended because both User, Membership and
Company already live in public, workspace switching occurs there, and UI
preferences can be read before entering a tenant schema. This avoids duplicating
global users inside every tenant schema.

### Tenant schemas

- Loans economic, rate, fee, product, monitoring, communication, approval and
  numbering policy;
- Accounting books, periods, ledgers, currency, posting controls and sequences;
- inventory valuation/numbering policy when actually required;
- notification templates/policies and tenant integration configuration;
- document layouts/assignments/revisions;
- branch/location overrides;
- all contractual snapshots and operational records.

Tenant models may retain `workspace` FKs as explicit ownership/future-RLS
preparation, but schema isolation does not depend on adding `tenant_id` to every
table. Services must validate any retained workspace FK against the active
tenant.

## 7. Proposed target architecture

```text
environment/settings
  deployment topology + platform secrets

public control plane
  orgs: Company, Domain, Membership, MembershipPreferences
  accounts: User, UserPreferences
  subscriptions: Plan, Entitlement, Subscription
  rollout/configuration: temporary platform/workspace activation assignments

tenant domain plane
  loans: economic/rate/fee/product/monitoring/communication policies,
         license/series/sequences, document configuration, snapshots
  accounting/dea: book/currency/period/posting policy and sequences
  notify_v2: policies/templates/integrations
  product: inventory policy only where a real workflow consumes it
```

Use small domain APIs where resolution is non-trivial:

- `resolve_pawn_economic_policy(workspace, license, as_of)` (already aligned
  with Loans services);
- `resolve_loan_monitoring_policy(...)`;
- `get_accounting_runtime_config()` with an active-schema assertion;
- `get_membership_preferences(user, company)` in public context;
- `get_notification_policy(event, as_of)`.

Do not create a generic `TenantSettings` facade. A common helper may assert
active schema and build cache keys, but validation and precedence remain in the
owning domain.

Valid precedence:

```text
code bootstrap default -> effective workspace policy -> effective license/branch
override -> immutable source-document snapshot

plan capability (hard ceiling) -> tenant option inside that ceiling

workspace UI default -> membership UI preference -> session-only UI state
```

Invalid precedence: global dynamic row or user/membership/session preference
overriding LTV, interest, accounting recognition, approval, risk/NPA,
numbering, posting, permission or compliance rules.

## 8. django-dynamic-preferences decision matrix

The rows below cover every registered central preference, grouped only where
scope, destination and decision are identical.

| Current preference(s) | Current scope/schema | Recommended scope/storage | Decision and reason |
| --- | --- | --- | --- |
| `platform__trial_days` | Global/public | Plan/subscription typed public model | **MOVE**; trial is commercial policy, not a loose preference |
| `platform__support_email`, `platform__default_timezone` | Global/public | Typed platform config or deployment setting | **MOVE**; validated operator-owned values |
| `platform__feature_defaults` | Global/public string JSON | Typed rollout/capability records | **DELETE/REPLACE**; unvalidated feature bag |
| `platform__maintenance_mode` | Global/public | Deployment/typed public operational flag | **MOVE**; needs reliable fail-safe access, not preference fallback |
| `accounting__financial_year_start_month/day` | Global + workspace/public | Tenant Accounting settings or period setup | **MOVE**; cross-field date validation and historical periods |
| `accounting__default_currency` | Global + workspace/public | Tenant DEA `CurrencyConfiguration`/AccountingBook | **MERGE**; typed model already exists |
| `accounting__voucher_prefix`, `invoice_prefix`, `numbering_strategy` | Global + workspace/public | Tenant typed sequence/series models | **MOVE/DELETE duplicate**; concurrency and uniqueness are domain concerns |
| six `accounting__default_*_ledger` keys | Global + workspace/public strings | Tenant typed account mappings/FKs | **MOVE**; validate account purpose/existence |
| `accounting__rounding_policy` | Global + workspace/public | Typed accounting/economic policy and snapshot | **MOVE**; financial/historical effect |
| `accounting__successor_enabled` | Workspace/public active read | Typed public rollout state plus tenant readiness | **MOVE** after compatibility period; currently KEEP as audited adapter |
| `accounting__workflow_mode` | Workspace/public active read | Typed tenant Accounting settings | **MOVE**; authorization/workflow policy |
| `accounting__integration_mode` | Workspace/public active read | Typed tenant accounting integration policy or public cutover assignment | **MOVE**; keep adapter until Loans/Girvi cutover is coordinated |
| five `commodity__*` keys | Global + workspace/public | Tenant rates/DEA commodity typed configuration | **MOVE/DELETE duplicates**; rate source and fixing affect historical facts |
| `loan__default_interest_calculation_method` | Global + workspace/public | `PawnLoanEconomicPolicy` + snapshot | **DELETE duplicate** |
| `loan__default_date` | Global + workspace/public | Membership/session UI convenience | **MOVE**; not business policy |
| `loan__interest_deduction_enabled`, `minimum_document_charge` | Global + workspace/public | Typed fee/economic policy + disbursal snapshot | **MOVE** |
| `loan__collateral_haircut_percent` | Global + workspace/public | Typed valuation/LTV policy | **MOVE**; clarify haircut versus maximum LTV |
| three `loan__default_*_interest_rate` keys | Global + workspace/public | `PawnMetalInterestRatePolicy` + snapshot | **DELETE duplicate** |
| `loan__accrual_timing`, `auto_post_accruals`, four catch-up/backfill/fail-closed flags | Global + workspace/public | Typed Girvi operational policy during coexistence; Loans typed policy/job policy | **MOVE**; current mutable workflow policy requires effective dating/audit |
| `loan__grace_period_days` | Global + workspace/public | Product/economic/monitoring policy as semantics dictate | **MOVE**; separate contractual grace from operational grace |
| `loan__notice_timing_days`, `auction_timing_days` | Global + workspace/public | Monitoring/notice/auction policy | **MOVE**; legal/operational policy, effective-dated |
| `loan__default_document_template` | Global + workspace/public string | Versioned layout assignment | **DELETE duplicate** |
| five `inventory__*` keys | Global + workspace/public | Typed inventory policy only when consumed | **DELETE now or MOVE when workflow exists**; currently aspirational |
| five `notifications__*` keys | Global + workspace/public | Notify v2 policy/integration/template models | **DELETE/MERGE**; typed domain exists; rules JSON is unsafe |
| four `documents__*` keys | Global + workspace/public | Domain versioned layouts/assignments/profiles | **DELETE/MERGE** |
| `ui__default_table_page_size`, `ui__default_landing_page` | Global + workspace/public | Workspace UI defaults (dynamic acceptable) | **KEEP DYNAMIC** if actually consumed; otherwise delete until needed |
| `ui__theme`, `ui__date_display_format` | User/public | Global UserPreferences/dynamic user | **KEEP DYNAMIC**; person-wide presentation |
| `ui__sidebar_collapsed` | User/public | Session or global user | **KEEP**, preferably session for device-specific state |
| `ui__dashboard_widgets`, `ui__table_page_size`, `ui__default_landing_page` | User/public | MembershipPreferences | **MOVE**; workspace-specific presentation |
| 15 legacy `Loan__*`/`Interest_Rate__*` registrations | Global + Company/public | Typed Girvi policy or retirement; existing document fields remain snapshots | **REPLACE/DELETE** after consumer cutover; do not maintain two dynamic registries |

## 9. Loans-specific configuration analysis

| Value | Category | Current/target source | Historical rule |
| --- | --- | --- | --- |
| Interest method, part-month method/slab, capitalization, rounding | Tenant default/current effective policy | `PawnLoanEconomicPolicy` | Freeze at approval/disbursal in `LoanPolicySnapshot` |
| Metal interest rate | Tenant default | `PawnMetalInterestRatePolicy` | Freeze selected rate and policy provenance per approved loan/item |
| Fees, deductions, advance interest | Tenant default/policy | `PawnLoanFeePolicy` and economic policy | Persist assessed components and resulting amounts |
| Tenure/maturity/payment schedule | Tenant/product default | Immutable `LoanProductVersion` + origination inputs | Store contractual tenure, maturity and schedule; never re-read product |
| Maximum LTV/valuation method | Current origination policy | Economic policy, optional license override | Freeze origination policy; monitoring uses separately versioned current thresholds |
| Warning/breach/critical LTV | Current monitoring policy | `LoanMonitoringPolicy` | Risk snapshot records policy/version and valuation evidence |
| DPD/overdue/substandard/NPA classification | Current monitoring/compliance policy | `LoanMonitoringPolicy` or a dedicated classification policy | Effective-date changes; store each assessment result/provenance |
| Grace period | Two distinct concepts | Product contractual grace vs monitoring operational grace | Rename explicitly and snapshot contractual grace only |
| Numbering | Current series state | `LoanNumberSequence`, funding/Girvi sequences | Allocated number is immutable; previews never consume |
| Lifecycle/approvals | Domain invariant plus tenant workflow policy | Code state machine; typed approval policy if variability is proven | Store approval snapshot and transition audit; user prefs never override |
| Payment allocation | Contract/domain rule | Typed product/economic policy and allocation service | Persist allocation lines; do not recompute history from current policy |
| Notice/auction timing | Current legal/operational policy | Monitoring/notice/auction models | Snapshot notice intent, frozen economics, template and consent/provider evidence |

The new Loans implementation largely gets the default/policy/snapshot boundary
right. The remaining audit focus should be semantic duplication (especially
grace, LTV and rounding), DB constraints for ordered monitoring thresholds, and
ensuring every snapshot records the source policy ID/version/effective date.
Girvi should not be redesigned into a parallel rich policy platform if its
retirement remains intended; introduce only the smallest typed, auditable policy
needed to make remaining mutable workflow flags temporally correct.

## 10. User and membership preference architecture

Create public `accounts.UserPreferences(user one-to-one)` only for person-wide
language, timezone, accessibility, date format and optionally theme. Create
public `orgs.MembershipPreferences(membership one-to-one)` for landing page,
dashboard layout, table columns/page size, saved filters and default branch.
Keep device/transient collapsed-panel state in session/local storage.

Resolution is explicit:

```text
global UI code default -> workspace UI default -> membership preference
-> request/session UI override
```

The API requires both authenticated user and Company, resolves Membership in
public schema, and rejects non-members. It must never return or accept business
policy keys. Do not attach tenant-specific preferences directly to global User,
and do not create tenant-schema user preference rows for public users.

## 11. Tenant provisioning strategy

Use one explicit, idempotent provisioning orchestrator after schema creation:

1. create Company/membership/domain in public and record provisioning state;
2. create/clone/migrate schema;
3. enter `tenant_context(company)`;
4. invoke domain seeders in dependency order (Party, Accounting/DEA, Notify,
   Loans baseline products/policies only where mandatory);
5. validate readiness and seed parity;
6. return to public and mark workspace ready.

Keep schema migrations responsible for table shape and immutable reference data
needed by every schema. Use services/commands for operator-editable baseline
rows. Avoid lazy `get_or_create` in financial runtime because missing mandatory
configuration should fail readiness, not silently invent policy. Signals may
enqueue the orchestrator after `post_schema_sync`, but must pass `schema_name`
and never create tenant rows without an explicit tenant context.

## 12. Schema-context safety

- Requests: assert `connection.schema_name == workspace.schema_name` at typed
  business configuration service boundaries.
- Background/scheduled jobs: payload contains immutable `workspace_id` and
  `schema_name`; resolve Company in public; validate equality/schema existence;
  wrap the complete tenant operation in `tenant_context`.
- Management commands: require `--schema`; exclude public/deleted tenants;
  validate `schema_exists`; use `schema_name`, never Company display name.
- Signals: treat schema as explicit input. Cross-app signal handlers must not
  assume save-time context, especially Company provisioning and callbacks.
- Provider callbacks: resolve an integration/workspace in a public-safe routing
  boundary, then enter only that tenant schema; reject ambiguous routing.
- Tests: add two real tenant schemas for isolation tests; always reset public in
  teardown; test service failure under public/wrong tenant.

Caching is not currently justified for most configuration. If introduced, use
`config:{schema_name}:{domain}:{scope-id}:{version-or-key}`. Cache resolved
immutable policy by policy/version, not an unversioned “current” object. Invalidate
on transaction commit after a new version/assignment; never reuse a manager
cache whose identity depends only on whichever schema happens to be active.

## 13. Migration/refactor plan

### Phase 0 — freeze and characterize

- Stop adding business-critical keys to dynamic preferences.
- Turn the inventory in this document into executable registry/call-site tests.
- Record actual database rows per registry and identify UI-edited but unread
  keys before deletion.

### Phase 1 — harden current access

- Replace broad `_safe_get` exception swallowing with missing-key handling and
  observable failures.
- Require public context for public preference writes and tenant match for
  business feature-switch consumers.
- Close or permission-gate package `/dynamic_preferences/` routes.
- Ensure every active write surface goes through an audited service.

### Phase 2 — establish user/membership preferences

- Add typed public UserPreferences and MembershipPreferences (or retain dynamic
  storage behind those exact scopes).
- Migrate the six UI keys by semantic scope; move selected workspace to session
  ownership and document compatibility fallback.

### Phase 3 — migrate three active accounting switches

- Decide public rollout assignment versus tenant Accounting settings per key.
- Add typed models, permissions, audit and active-schema assertions.
- Dual-read with equality diagnostics, migrate explicit rows, switch reads,
  then remove registrations.

### Phase 4 — resolve Girvi coexistence

- Decide whether Girvi will remain active long enough to justify one
  effective-dated `GirviOperationalPolicy`.
- Snapshot/record temporal policy provenance for accrual/catch-up/posting
  operations.
- Do not copy legacy rows to unused central dynamic keys. Cut directly to typed
  policy or retire with Girvi.

### Phase 5 — remove aspirational duplicates

- Delete central accounting, commodity, loan, inventory, notification and
  document registrations with no consumer.
- Point settings UI to real typed domain setup screens.
- Remove migration mappings and compatibility forms after verification.

### Phase 6 — provisioning and schema safety

- Consolidate tenant seed orchestration and provisioning state.
- Standardize tenant-aware commands/jobs/callbacks and add wrong-schema tests.

### Phase 7 — constraints, audit and historical proof

- Add DB constraints where possible: policy ranges, ordered dates, uniqueness
  and positive sequence widths; keep cross-row/conditional validation in
  services and model `clean()`.
- Audit important policy creation/activation with actor, old/new version and
  reason. Prefer append-only policy versions over generic before/after blobs.
- Prove defaults changes do not alter existing loans/documents/postings.

### Phase 8 — cleanup migrations and documentation

- Remove legacy routes, registries, facade, audit rows and obsolete tests only
  after zero-read evidence.
- Since production compatibility is not required, consider resetting/squashing
  development migrations app-by-app after the target model graph stabilizes;
  use `migrate_schemas --shared` and tenant migration replay verification.
- Supersede the older centralized-preferences plan with the accepted outcome.

## 14. File-by-file change plan

| File/module | Planned change |
| --- | --- |
| `apps/configuration/dynamic_preferences_registry.py` | Retain only proven lightweight UI/control-plane keys; delete domain duplicates |
| `apps/configuration/services.py` | Narrow API, remove broad catch, enforce scope/context, deprecate generic business access |
| `apps/configuration/models.py` | Retire workspace K/V and generic audit after migrations; or rename explicitly as public control-plane preferences |
| `apps/configuration/views.py`, `forms.py`, `urls.py`, template | Stop presenting unused keys; link to domain setup screens |
| `apps/configuration/management/commands/migrate_preferences_to_workspace.py` | Replace copy-to-duplicate migration with typed migrations; then delete |
| `apps/orgs/models.py` | Add MembershipPreferences/provisioning state if accepted; retire CompanyPreferenceModel |
| `apps/orgs/preferences.py`, `registries.py`, preference views/forms | Remove legacy facade/registry after Girvi cutover |
| `accounts/models.py` | Add explicit global UserPreferences or document dynamic global scope |
| `apps/tenant_apps/girvi/dynamic_preferences_registry.py` and adapter | Replace with minimal typed operational policy or remove with Girvi |
| Girvi accrual/creation/repayment/release/renewal services and command | Resolve policy once, record provenance, require tenant context |
| `apps/tenant_apps/loans/models/core.py`, `monitoring.py`, `communication.py` | Preserve typed policy; strengthen semantic names/constraints/provenance |
| Loans economic/monitoring/notice services | Remain authoritative configuration APIs; assert tenant context |
| `apps/tenant_apps/accounting/feature_flags.py` and `apps/configuration/accounting_integration.py` | Migrate active switches to typed state/settings |
| DEA currency/period/numbering/account mapping models/services | Remain authoritative; remove duplicate K/V registrations |
| notify_v2 policy/template/integration models/services | Remain authoritative; encrypted credential redaction and audit |
| `apps/orgs/signals.py`, onboarding/control-plane services, seed commands | One explicit idempotent provisioning workflow |
| relevant tests | Add two-tenant isolation, precedence, historical, invalid-policy and wrong-schema coverage |
| `django_project/settings/base.py`, `dev.py`, `prod.py` | Validate secrets, remove insecure production defaults/literals, document deployment-only settings |

## 15. Deletion candidates

| Candidate | Action | Evidence gate |
| --- | --- | --- |
| Registered central keys with no non-test consumer | **DELETE** | Registry/call-site report plus UI/database-row inventory |
| Duplicate central loan/commodity/accounting/document/notify keys | **REPLACE/MERGE** | Typed domain resolver and migration tests pass |
| Legacy Girvi global/company registrations and `CompanyPreferences` | **DELETE** | No runtime imports/rows needed; Girvi typed cutover or retirement complete |
| `migrate_preferences_to_workspace` mappings | **DELETE** | Typed migration replaces copy and no dual registry remains |
| Generic central preference page sections for nonfunctional keys | **DELETE/REPLACE** | Domain setup navigation exists |
| Package unscoped dynamic-preferences route | **DELETE** or superuser-lock | Custom scoped UIs cover retained keys |
| String JSON preferences for features, reminder rules, print defaults | **DELETE/REPLACE** | Typed records/versioned definitions exist |
| `django_project/old_settings.py` | **DELETE** if not imported | Settings/import/deployment search confirms no indirect use |
| Test Razorpay credential defaults and unconditional secure-cookie overrides in base | **REPLACE** | Environment-specific settings checks pass |

Do not delete solely from Python call-site absence: check templates, URL names,
admin registration, app loading, migrations, command discovery and stored rows.

## 16. Open architectural decisions

### A. Location of the three active accounting switches

- Option A: public typed workspace rollout/capability records.
- Option B: tenant `AccountingSettings`/policy.
- Recommended: split by ownership. `successor_enabled` is public rollout state;
  workflow mode is tenant accounting policy; integration mode is a typed cutover
  assignment in public until coexistence ends, then tenant accounting policy.

### B. Girvi policy investment

- Option A: introduce effective-dated typed GirviOperationalPolicy.
- Option B: freeze legacy preferences and retire Girvi consumers into Loans.
- Recommended: B if retirement has a committed near-term gate; otherwise a
  minimal A for only the actively mutable accrual/posting flags. Do not recreate
  the full Loans policy architecture in Girvi.

### C. Retained UI preference storage

- Option A: keep dynamic user/per-instance storage.
- Option B: typed UserPreferences and MembershipPreferences.
- Recommended: B for scope clarity and validation; a small JSON field is
  acceptable for dashboard layout/table columns, with a schema/version and size
  limit. Dynamic preferences may remain behind global cosmetic values if it
  reduces migration cost.

### D. Explicit workspace FKs inside tenant models

- Option A: retain them on policy/configuration models.
- Option B: rely only on schema isolation.
- Recommended: A where already present, because it supports validation, audit
  provenance and the accepted possible RLS path; do not add it mechanically to
  every tenant table.

## Acceptance test matrix

The implementation is not complete until tests prove: tenant A/B typed policy
isolation; public global user preferences remain global; membership preferences
differ by workspace; plan ceilings cannot be overridden; defaults initialize
new loans but never mutate existing contractual snapshots; effective policy
changes affect only the intended as-of operations; invalid LTV/DPD/date/rounding
combinations fail; numbering is atomic and tenant-local; jobs fail without the
matching schema; provider callbacks route to one tenant; retained dynamic
preferences resolve the intended public row; and secrets never appear in logs,
admin lists, templates or audit payloads.
